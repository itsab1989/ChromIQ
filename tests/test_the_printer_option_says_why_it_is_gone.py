"""Knut, beta 9, on Tools ▸ Build profile with scanner or camera:

    *"the option 'Profile my printer from this scan (scanner as the
    instrument)' is only available when 'A chart I made in ChromIQ' is
    selected. This should be possible to do whatever target a user has, so
    should be available for both cases."*

**The gate is right and the silence was not.** Printer mode is
``scanin -c <scan> <cht> <scanner.icc> <pbase>``, and it reads
``<pbase>.ti2`` — the table of device values that were sent to the printer.
A bought standard target (IT8, ColorChecker, LaserSoft) has no such table:
it was printed and measured by its manufacturer, and its reference file
(.cie / .txt / .ti3 / .cxf) lists what the target *is*, never what any
printer was asked to make. There is nothing for a printer profile to be
built from, so the option cannot be offered there.

What was wrong is that switching to a standard target made the tick vanish
with no word of explanation — in a window whose own subtitle, still on
screen in that mode, promises *"…or, from a scan of a chart you printed, a
profile for your printer"*. Verified on screen 2026-09-05: 31 visible
labels in standard mode, not one of them mentioning why.

And the capability Knut actually wants **already exists on the other side
and is undiscoverable**: the radio says "A chart I made in ChromIQ", but
#105's bring-your-own-.cht path accepts a chart made anywhere, as long as
it has a .ti2 and printtarg's .cht pages. That is what the new text says.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.settings import DEFAULTS  # noqa: E402


class _FakeSettings:
    """DEFAULTS with a hermetic output root — see tests/test_scanin_dialog.py
    for why `custom_output_path` must never be left at its "" default here."""

    def __init__(self, **overrides):
        import tempfile
        self._store = {**DEFAULTS, **overrides}
        if not self._store.get("custom_output_path"):
            self._store["custom_output_path"] = tempfile.mkdtemp(
                prefix="chromiq-bj-")

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def _out_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("bj-printer-gate")


@pytest.fixture
def dlg(_app, _out_dir):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    d = ScannerProfileDialog(object(), _FakeSettings(
        custom_output_path=str(_out_dir)))
    yield d
    d.deleteLater()


# --------------------------------------------------------------- the gate
def test_the_gate_itself_is_unchanged(dlg):
    """The verdict is "justified", so the behaviour must not have drifted:
    a standard target still cannot be put into printer mode."""
    dlg._mode_chromiq.setChecked(True)
    assert dlg._printer_cb.isVisible() or not dlg.isVisible()
    dlg._printer_cb.setChecked(True)
    assert dlg._printer_mode() is True

    dlg._mode_standard.setChecked(True)
    assert dlg._printer_cb.isChecked() is False, (
        "switching to a standard target must also switch printer mode off")
    assert dlg._printer_mode() is False
    # …and ticking it behind the mode's back still cannot turn printer mode on.
    dlg._printer_cb.setChecked(True)
    assert dlg._printer_mode() is False, (
        "_printer_mode() must be gated on the mode, not only on the checkbox")


def test_standard_mode_now_says_why_the_printer_option_is_not_there(dlg):
    """The whole of Knut's report, in one assertion: a user who looks for the
    option must find a sentence instead of nothing."""
    dlg._mode_standard.setChecked(True)
    note = dlg._mode_note
    assert note.isVisibleTo(dlg), "the explanation is not shown in standard mode"
    txt = note.text()
    # It has to name the control that is missing, or the reader cannot connect
    # the explanation to the thing they were looking for.
    assert "Profile my printer from this scan" in txt
    # It has to give the REASON, not just the fact.
    assert "printed" in txt.lower()
    # It has to say where to go instead, by the name on screen…
    assert "A chart I made in ChromIQ" in txt
    # …and it has to say that the other side is not ChromIQ-only, which is the
    # half that answers what Knut actually asked for. Without this sentence a
    # user with an i1Profiler or printtarg chart is told, correctly, that a
    # bought target will not do — and wrongly infers that their own chart
    # will not either.
    assert "another program" in txt
    assert ".ti2" in txt and ".cht" in txt


def test_the_explanation_is_hidden_when_the_option_is_present(dlg):
    """A standing warning about a control that IS there is noise."""
    dlg._mode_standard.setChecked(True)
    assert dlg._mode_note.isVisibleTo(dlg)
    dlg._mode_chromiq.setChecked(True)
    assert not dlg._mode_note.isVisibleTo(dlg)
    assert dlg._printer_cb.isVisibleTo(dlg)


def test_the_explanation_and_the_tick_are_never_both_shown_or_both_hidden(dlg):
    """They are two halves of one statement; a state with neither is the bug
    this file exists for, and a state with both contradicts itself."""
    for standard in (False, True, False, True):
        dlg._mode_standard.setChecked(standard)
        assert dlg._printer_cb.isVisibleTo(dlg) != dlg._mode_note.isVisibleTo(dlg)


# ------------------------------------------------- the undiscoverable route
def test_the_source_help_says_a_chart_from_another_program_belongs_there(dlg):
    """#105 accepts a chart made outside ChromIQ (a .ti2 plus printtarg's .cht
    pages) under a radio whose label says "made in ChromIQ". A user with an
    i1Profiler or printtarg chart reads the two labels and concludes ChromIQ
    cannot do it — which is what Knut did."""
    from ui.tooltip_button import TooltipButton
    body = next((t._body for t in dlg.findChildren(TooltipButton)
                 if t._title == "Which source?"), None)
    assert body, "the “Which source?” help has gone"
    assert "another program" in body
    assert ".ti2" in body and ".cht" in body
    # and it must say WHY the printer side is one-sided, in the same place.
    assert "PRINTER" in body or "printer" in body


def test_the_source_help_explains_the_standard_target_side_too(dlg):
    """Half an explanation is how the original text read."""
    from ui.tooltip_button import TooltipButton
    body = next((t._body for t in dlg.findChildren(TooltipButton)
                 if t._title == "Which source?"), None)
    # The bullet HEAD is a plain-language category, not the control's label —
    # `tests/test_a_bullet_names_the_button_it_is_about.py` requires that of any
    # bullet whose message is not translated, because a Spanish reader shown
    # "• A standard target I own" is being sent to a radio that reads "Un
    # objetivo estándar propio". The label is quoted inside the sentence.
    tail = body[body.index("• A target you bought"):]
    assert "“A standard target I own”" in tail, (
        "the bullet no longer says which control it is about")
    assert "manufacturer" in tail, (
        "the standard-target bullet does not say who printed the target")
    assert "Profile my printer from this scan" in tail


# ------------------------------------- the switch is said (Knut, 4.3.25)
# *"Knut didn't notice that the usage scenario had been switched."* Choosing
# a bought target while the printer scenario is lit takes the user off it, and
# the note used to explain only why the option is greyed. It now says, first,
# that ChromIQ changed the scenario, to which one, and how to get a printer
# profile instead; and it says that ONLY when a switch really happened.
_CHANGED = "ChromIQ has changed the usage scenario for you"


def _labels(d):
    return {k: label for k, label, _g, _f in d._scenarios()}


def test_the_note_says_the_scenario_was_switched_and_to_which(dlg):
    from ui.dialogs import scanner_colprof as sc
    dlg._mode_chromiq.setChecked(True)
    dlg._scenario_radios[sc.SCENARIO_PRINTER].setChecked(True)
    assert dlg._printer_mode()
    dlg._mode_standard.setChecked(True)
    txt = dlg._mode_note.text()
    labels = _labels(dlg)
    assert txt.startswith(_CHANGED), txt
    head = txt.split("\n\n")[0]
    now = dlg._scenario_for(dlg._active_ctx)
    assert now != sc.SCENARIO_PRINTER
    # from which, to which, and the way back, all by the names on screen
    assert f"from “{labels[sc.SCENARIO_PRINTER]}” to “{labels[now]}”" in head
    assert dlg._scenario_radios[now].isChecked()
    assert "“A chart I made in ChromIQ”" in head
    assert head.count(labels[sc.SCENARIO_PRINTER]) == 2
    # …and the reason it always gave is still there, word for word.
    assert txt.endswith(dlg._mode_note_reason)


def test_without_a_switch_the_note_is_the_reason_alone(dlg):
    dlg._mode_chromiq.setChecked(True)
    dlg._printer_cb.setChecked(False)
    dlg._mode_standard.setChecked(True)
    assert dlg._mode_note.text() == dlg._mode_note_reason
    assert _CHANGED not in dlg._mode_note.text()


def test_the_switch_sentence_does_not_outlive_the_switch(dlg):
    """Back to a chart and to a bought target again, with the printer
    scenario no longer lit: nothing was switched this time."""
    dlg._mode_chromiq.setChecked(True)
    dlg._printer_cb.setChecked(True)
    dlg._mode_standard.setChecked(True)
    assert dlg._mode_note.text().startswith(_CHANGED)
    dlg._mode_chromiq.setChecked(True)
    dlg._mode_standard.setChecked(True)
    assert dlg._mode_note.text() == dlg._mode_note_reason


def test_choosing_a_scenario_yourself_ends_the_switch_sentence(dlg):
    """After the user's own choice, "ChromIQ changed it for you" is old news
    and could name a scenario that is no longer lit."""
    from ui.dialogs import scanner_colprof as sc
    dlg._mode_chromiq.setChecked(True)
    dlg._printer_cb.setChecked(True)
    dlg._mode_standard.setChecked(True)
    assert dlg._mode_note.text().startswith(_CHANGED)
    dlg._scenario_radios[sc.SCENARIO_INSTRUMENT].setChecked(True)
    assert dlg._mode_note.text() == dlg._mode_note_reason


def test_with_own_saved_settings_the_note_says_no_scenario_is_selected(_app, _out_dir):
    """A bought-target bucket saved before scenarios existed is on no
    scenario, so there is no "to which" to name: the note says why none is."""
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    from ui.dialogs import scanner_colprof as sc
    d = ScannerProfileDialog(object(), _FakeSettings(
        custom_output_path=str(_out_dir),
        scanner_colprof_configs={"standard": {"quality": "m"}}))
    try:
        d._mode_chromiq.setChecked(True)
        d._printer_cb.setChecked(True)
        d._mode_standard.setChecked(True)
        assert d._scenario_for(d._active_ctx) is None
        txt = d._mode_note.text()
        head = txt.split("\n\n")[0]
        assert head.startswith(_CHANGED)
        assert f"“{_labels(d)[sc.SCENARIO_PRINTER]}” is no longer selected" in head
        assert "your own settings for bought targets are in force" in head
        assert "“A chart I made in ChromIQ”" in head
        assert not any(rb.isChecked() for rb in d._scenario_radios.values())
    finally:
        d.deleteLater()


def test_the_switch_sentence_is_translated_with_the_labels_on_screen():
    """Both variants are catalogue keys, and in every language the quoted
    names come in as placeholders, so they always match the radios."""
    import inspect
    import json
    from pathlib import Path
    from ui.dialogs import scanin_dialog
    src = inspect.getsource(scanin_dialog.ScannerProfileDialog._refresh_mode_note)
    assert src.count("{printer}") >= 4 and "{scenario}" in src
    root = Path(scanin_dialog.__file__).resolve().parents[2] / "data" / "i18n"
    for cat in sorted(root.glob("*.json")):
        data = json.loads(cat.read_text(encoding="utf-8"))
        keys = [k for k in data if k.startswith(_CHANGED)]
        assert len(keys) == 2, (cat.name, keys)
        for k in keys:
            assert data[k] and data[k] != k, (cat.name, k)
