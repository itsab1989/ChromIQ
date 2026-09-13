"""The chart-note length warning must measure the line the SHEET carries.

Knut, 2026-09-13:

    "If 'Stamp settings down the right edge' is ON and a chart notes text is
     added, where the two together become too long for the page height and set
     limits, then the ending is replaced by '...' but there is no warning at
     all... Similarly, this also happens if ... while also showing clip-border
     on right side. Same missing warning."

`chart_creator` joins the note with the targen line, the engine's name and the
ChromIQ version and stamps all of it down one edge. The panel measured the notes
box alone, and said so in a comment: *"with the stamp on, the real line is
LONGER than what is checked here and this can only under-report, never cry
wolf."* Right about the direction, wrong about the consequence: under-reporting
to zero is silence.

Measured on his testHex chart before the fix, driving the real app:

    stamp OFF, 177-char note   nothing cut,   no warning       correct
    stamp ON,  177-char note   37 chars cut,  NO WARNING       the fault
    the same + a clip border   37 chars cut,  NO WARNING       the fault
    stamp OFF, 376-char note   128 cut,       warns, says 128  correct
    stamp ON,  376-char note   236 cut,       warns, says 128  worse

What is lost in the 177-character case is `"t engine | ChromIQ 4.3.0-beta.7"`:
the ChromIQ version, which is one of the two things the stamp exists to record.

`ChartCreator.stamp_lines` is now the one list, and both the stamper and the
panel ask it. A second copy in the panel would have drifted exactly the way the
margin inspector's copy of `measure_from_engine` did.
"""
from __future__ import annotations

import ast
import inspect
import os
import textwrap

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")


def _creator():
    """A real ChartCreator, built the way the app builds it."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    s = AppSettings()
    return __import__("workflow.chart_creator", fromlist=["ChartCreator"]) \
        .ChartCreator(ArgyllRunner(s), FileManager(s), s)


def test_the_stamper_and_the_panel_ask_the_same_function():
    """One list, two callers, and neither of them builds its own.

    `_stamp_tiff_metadata` used to assemble the lines inline. If it goes back to
    that, the panel is measuring a string nothing prints.
    """
    from workflow.chart_creator import ChartCreator

    assert callable(getattr(ChartCreator, "stamp_lines", None)), (
        "the shared line list is gone")

    src = textwrap.dedent(inspect.getsource(ChartCreator._stamp_tiff_metadata))
    called = {n.func.attr for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "stamp_lines" in called, (
        "the stamper builds its own list again; the panel now measures "
        "something else")

    import ui.tabs.tab_chart as tc
    panel = textwrap.dedent(inspect.getsource(tc.TabChart._engine_text_notes))
    pcalled = {n.func.attr for n in ast.walk(ast.parse(panel))
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "stamp_lines" in pcalled, (
        "the panel is back to measuring the notes box alone")


def test_the_line_grows_with_the_stamp_and_shrinks_without_it():
    """The list itself, against a real ChartParams, with no window.

    The point is arithmetic the panel depends on: switching the stamp on makes
    the printed line longer than the notes box, which is the whole reason the
    old check could not see the truncation.
    """
    cre = _creator()

    notes = "Canon Pro-1000, colour management OFF, Highest quality"
    from workflow.chart_creator import ChartParams
    p = ChartParams()
    p.chart_notes = notes
    p.stamp_commands = False
    assert cre.stamp_lines(p, 425) == [notes]

    p.stamp_commands = True
    with_stamp = cre.stamp_lines(p, 425)
    assert with_stamp[0] == notes
    assert len(with_stamp) >= 3, with_stamp
    assert any(l.startswith("targen ") for l in with_stamp), with_stamp
    assert any(l.startswith("ChromIQ ") and l != "ChromIQ layout engine"
               for l in with_stamp), (
        "the ChromIQ version is one of the two things the stamp records")

    from workflow.tiff_metadata import _JOIN
    assert len(_JOIN.join(with_stamp)) > len(notes) + 40, (
        "the stamp adds a substantial tail, which is the fault's cause")


def test_the_patch_count_reaches_the_targen_line():
    """`-f<N>` is IN the line, so the wrong N is the wrong LENGTH.

    `params.patches` is 0 on a chart laid out from a .ti1, and the first
    version of this fix printed "-f0", two characters short of "-f425".
    """
    from workflow.chart_creator import ChartParams

    cre = _creator()
    p = ChartParams()
    p.chart_notes = "x"
    p.stamp_commands = True
    targen = [l for l in cre.stamp_lines(p, 425) if l.startswith("targen ")]
    assert targen and "-f425" in targen[0], targen


def test_the_stamp_is_offered_as_a_lever_only_while_it_is_on():
    """A remedy that does nothing is the fault this issue keeps recording.

    Switching the stamp off recovers 108 of the 236 characters lost on Knut's
    own case, so it is usually the cheapest lever, and it is meaningless when
    the stamp is already off.
    """
    import ui.tabs.tab_chart as tc

    src = textwrap.dedent(inspect.getsource(tc.TabChart._engine_text_notes))
    i = src.find("Switching “Stamp settings down the right edge” off")
    assert i > 0, "the lever is not offered at all"
    # It is bound to `_stamp_on`, not appended unconditionally.
    tail = src[i:i + 260]
    assert "if _stamp_on else" in tail, (
        "the stamp lever is offered whether or not the stamp is on:\n"
        + tail)


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", True)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    return t


def _too_long(tab) -> str:
    """A note that FITS on its own and does not fit once the stamp joins it.

    The length is found by asking the shipped fitter, which is what actually
    cuts the line on the sheet, rather than by hard-coding a number that goes
    stale the moment a font or a margin moves.
    """
    from workflow import tiff_metadata as tm
    tab._manual_stamp_cmd_check.setChecked(True)
    pm = tab._collect_manual()
    pm.stamp_commands = True
    pm.chart_notes = ""
    tail = tm._JOIN.join(tab._creator.stamp_lines(pm, 500))
    assert tail, "the stamp produced no lines at all"
    unit = "Canon Pro-1000 on Hahnemuehle Photo Rag 308 gsm, "
    for n in range(1, 40):
        note = (unit * n)[:n * len(unit)]
        joined = note + tm._JOIN + tail
        if _cut(tab, note) == 0 and _cut(tab, joined) > 0:
            return note
    pytest.skip("no note length on this paper splits the two cases")


def _cut(tab, text: str) -> int:
    """Characters the SHEET would cut from *text*, from the shipped fitter."""
    from workflow import tiff_metadata as tm
    from workflow.layout_engine import papers
    r = tab._current_layout_recipe()
    _pw, ph = papers.dimensions_mm(str(r.paper))
    return tm.note_characters_lost(
        text, ph, float(r.text_edge_clip_mm),
        max(0.0, float(r.margin_right) - float(r.text_edge_clip_mm)),
        float(getattr(r, "dpi", 300) or 300), 0.0,
        str(getattr(r, "chart_text_font", "") or ""),
        float(r.text_edge_top_mm), float(r.text_edge_mm))


def _notes(tab) -> list[str]:
    from ui.tabs.tab_chart import TabChart
    return TabChart._engine_text_notes(tab)[1]


def test_the_stamp_turns_a_silent_truncation_into_a_warning(tab):
    """Knut's case (a), end to end through the panel's own method.

    The same note, the same paper, the stamp the only difference. Before this
    fix the second half of it said nothing at all.
    """
    note = _too_long(tab)
    tab._manual_chart_notes_edit.setText(note)

    tab._manual_stamp_cmd_check.setChecked(False)
    quiet = [w for w in _notes(tab) if "too long for" in w]
    assert not quiet, (
        "the note fits on its own and the panel warns about it anyway: "
        + "; ".join(quiet))

    tab._manual_stamp_cmd_check.setChecked(True)
    loud = [w for w in _notes(tab) if "too long for" in w]
    assert loud, (
        "the stamp makes the printed line too long and the panel says nothing")
    assert "Stamp settings down the right edge" in loud[0], (
        "the cheapest lever is not offered:\n" + loud[0])


def test_the_count_it_names_is_within_a_character_of_the_sheet(tab):
    """Not just "a warning": the right number.

    Exact when the panel's targen switches are the build's. One character out
    on a chart laid out from an armed .ti1, whose own white/black/grey counts
    the build takes and these widgets do not carry, measured on Knut's testHex:
    the sheet cuts 37 and this says 36.
    """
    import re

    from workflow import tiff_metadata as tm
    note = _too_long(tab)
    tab._manual_chart_notes_edit.setText(note)
    tab._manual_stamp_cmd_check.setChecked(True)

    pm = tab._collect_manual()
    pm.chart_notes = note
    pm.stamp_commands = True
    n = tab._estimate_patch_total() or int(getattr(pm, "patches", 0) or 0)
    joined = tm._JOIN.join(tab._creator.stamp_lines(pm, int(n)))
    want = _cut(tab, joined)
    assert want > 0

    msg = [w for w in _notes(tab) if "too long for" in w][0]
    m = re.search(r"last (\d+) characters", msg)
    got = int(m.group(1)) if m else 1
    assert abs(got - want) <= 1, (
        f"the message says {got} where the fitter cuts {want}:\n{msg}")
