"""With an empty notes box, the right-edge warning must not blame chart notes.

The app ships with **"Stamp settings down the right edge" ON**:
`chart_stamp_commands` has no default in the store and the tick is set True when
the row is built, and no layout recipe can clear it, because the recipe's own
`stamp_command` is a different control (the layout summary along the BOTTOM).

So on a fresh install, with nothing typed, selecting one of Knut's CR30 presets
printed:

    The chart notes down the right edge share that edge with the clip border,
    so they are printed over the patches...

about chart notes that do not exist. Found by the adversary round of
2026-09-13, which also showed that the two "6 GREEN" claims made that morning
held only because the owner's own preferences carry `chart_stamp_commands = 0`:
on app defaults the six straight presets were **6 RED** and the six scanner ones
**2 GREEN / 4 RED**, every red one this message.

The line IS there and it DOES land on the patches, so the warning is right. It
was only wrong about whose text it was.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    """A tab on APP DEFAULTS, which is the whole point of this file.

    Nothing is copied from the owner's preferences; that is what hid this.
    """
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    return t


def _straight_key():
    from ui.tabs.tab_chart import BUILTIN_PRESET_GROUPS
    for _instr, entries in BUILTIN_PRESET_GROUPS:
        for (label, _o, k) in entries:
            if "A4-450p" in label and "Straight" in label:
                return k
    pytest.skip("the straight-strip presets are not registered")


def _notes(tab):
    """The overlap notices, WITH the sheet's own measurement.

    Knut's ruling of 2026-09-15 (#182): the four patch-area checks read
    "Measured from Preview" and say nothing without it, so the report is built
    from the recipe's own geometry, which is where the patch area lands on a
    rectangular chart that fills its page.
    """
    from ui.tabs.tab_chart import TabChart
    from tests.margin_reports import report_for
    return TabChart._engine_text_notes(
        tab, report_for(tab._current_layout_recipe()))[1]


def test_the_stamp_is_on_by_default_and_no_recipe_can_clear_it():
    """The precondition, pinned, because it is the surprising half.

    If the default ever changes this test should be revisited rather than
    silently pass for a new reason.
    """
    import inspect

    import ui.tabs.tab_chart as tc
    src = inspect.getsource(tc.TabChart)
    assert "chart_stamp_commands" in src
    from workflow.layout_engine.presets import LayoutRecipe
    assert not hasattr(LayoutRecipe, "chart_stamp_commands"), (
        "a recipe can now carry the right-edge stamp; this branch may be moot")
    assert hasattr(LayoutRecipe(), "stamp_command"), (
        "the recipe's own `stamp_command` is gone; it is a DIFFERENT control "
        "(the layout summary along the bottom) and the comment says so")


def test_an_empty_notes_box_is_never_blamed(tab):
    tab._seed_knut_preset(_straight_key())
    assert tab._manual_stamp_cmd_check.isChecked(), (
        "the default changed; this test's premise is gone")
    assert not tab._manual_chart_notes_edit.text()

    got = [w for w in _notes(tab) if "right edge" in w]
    assert got, (
        "the stamp's line lands on the patches on this preset and nothing is "
        "said about it")
    for w in got:
        assert "chart notes down the right edge" not in w, (
            "the notes box is empty and the message blames chart notes:\n" + w)
    joined = " ".join(got)
    assert "settings stamp" in joined, joined
    assert "Stamp settings down the right edge" in joined, (
        "the lever that always works is not named:\n" + joined)


def test_a_typed_note_still_gets_the_per_lever_wording(tab):
    """The three original messages are for a user who typed something, and they
    keep their own remedies."""
    tab._seed_knut_preset(_straight_key())
    tab._manual_chart_notes_edit.setText("Canon Pro-1000, colour management off")
    got = [w for w in _notes(tab) if "right edge" in w]
    assert got, "a typed note on this preset must still be warned about"
    joined = " ".join(got)
    assert "chart notes down the right edge" in joined, joined
    assert "Nothing you typed is on that edge" not in joined, (
        "the empty-box message is shown to somebody who typed a note:\n"
        + joined)


def test_the_two_controls_leave_the_measured_frame_alone(tab, tmp_path):
    """…AND SINCE KNUT'S RULING OF 2026-09-15 THEY MUST NOT REFRESH IT.

    This test used to assert the opposite. The call was added on 2026-09-13
    because toggling the stamp tick gave **0 refreshes**, six times out of six,
    and the red message stood until something else repainted. That was right
    while the notices were PREDICTED from the boxes; the ruling makes them
    measurements of the sheet in the preview, and neither of these two controls
    can change that sheet:

        "the margin warnings need only be updated upon the chart being updated
         with Generate Chart ... they are only usable after the Measured from
         Preview margin values have been completed."

    The reader is not left with nothing: `_refresh_unapplied_warning` paints
    the red "press Generate Chart" sentence, which Knut names as already
    correct, and `tests/test_a_moved_margin_box_leaves_the_panel_alone.py`
    pins that half.

    MUTATION: put `self._update_margin_inspector()` back into
    `_on_chart_settings_touched` and this goes red.
    """
    from ui.tabs.tab_chart import TabChart

    tif = tmp_path / "chart.tif"
    tif.write_bytes(b"")
    tab._margin_tiffs = [tif]

    n = {"v": 0}
    real = TabChart._update_margin_inspector

    def spy(self):
        n["v"] += 1
        return real(self)

    TabChart._update_margin_inspector = spy
    try:
        n["v"] = 0
        tab._manual_stamp_cmd_check.setChecked(
            not tab._manual_stamp_cmd_check.isChecked())
        assert n["v"] == 0, (
            "toggling the stamp tick re-measured the 'Measured from Preview' "
            "frame, which describes a sheet the tick cannot change")

        n["v"] = 0
        tab._manual_chart_notes_edit.setText("Canon Pro-1000, no colour "
                                             "management, Highest quality")
        assert n["v"] == 0, "typing a note re-measured the frame"
    finally:
        TabChart._update_margin_inspector = real


def test_it_does_nothing_at_all_when_there_is_no_chart_to_measure(tab):
    """Typing before anything is built must not cost a measurement."""
    from ui.tabs.tab_chart import TabChart

    tab._margin_tiffs = []
    tab._margin_ti2 = None
    n = {"v": 0}
    real = TabChart._update_margin_inspector

    def spy(self):
        n["v"] += 1
        return real(self)

    TabChart._update_margin_inspector = spy
    try:
        tab._manual_chart_notes_edit.setText("x")
        assert n["v"] == 0, "the panel was measured with no chart on screen"
    finally:
        TabChart._update_margin_inspector = real
