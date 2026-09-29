"""FROM PROFILE GAMUT is the Manual page, and the warnings have to know it.

Found by adversary round 21 against v4.3.0-beta.17, driving the real app in a
real window (`scripts/adv21d_the_gamut_module_hears_nothing.py`).

`_engine_text_notes` opened with::

    manual = (self._manual_btn is not None and self._manual_btn.isChecked())
    if not (manual and …):
        return warns, over

and `_switch_mode("gamut")` does ``self._manual_btn.setChecked(False)``.

The FROM PROFILE GAMUT module IS the Manual page with the targen group swapped
out (#133 §10). "Margins (mm)", "Sheet text", "Text distance from edge" and the
helper-marker boxes are Manual's own live widgets there, the auto-update
preview runs, and `_on_generate_gamut` builds the sheet from exactly those
boxes. So every text-overlap notice in "Measured from Preview" was silent in
the one module whose sheet those boxes lay out, and that includes the four
bottom-height wordings, the rise search, the larger-paper sentence and the
locked-margins sentence this change set added.

MEASURED ON SCREEN, 2026-09-15. i1Pro, A4, margins 12/12/6/12 with "Use
instrument margins" unticked, helper markers on top and bottom, one line of
sheet text at 36 pt. ONE chart, ONE "Measured from Preview" report (left 26.0,
right 12.0, top 13.0, bottom 7.8 mm), read three times without touching a
layout box:

* MANUAL prints "▼ 3 warnings", the third being *"The sheet text along the
  bottom runs into the patches. It is printed 5.0 mm up from the paper edge and
  needs 15.5 mm of room, and the patches come down to 7.5 mm, leaving 2.5 mm.
  Raise “Bottom” under “Margins (mm)” by about 13.5 mm."*
* FROM PROFILE GAMUT prints **none of them**;
* MANUAL again brings all three back.

Photographed all three ways.

`_helper_marker_lines_frac`, eighty lines further down the same file, documents
this exact trap and keys on `_current_mode()` for it. So does this now.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from workflow.layout_engine.presets import LayoutRecipe    # noqa: E402


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
    yield t
    t.deleteLater()


def _colliding() -> LayoutRecipe:
    """The sheet the round drove: one line of 36 pt over a 6 mm bottom margin."""
    r = LayoutRecipe()
    r.instrument, r.paper = "i1", "A4"
    r.layout_mode, r.use_instrument_margins = "area_first", False
    r.margin_top, r.margin_right = 12.0, 12.0
    r.margin_bottom, r.margin_left = 6.0, 12.0
    r.text_edge_top_mm = r.text_edge_mm = r.text_edge_clip_mm = 4.0
    r.helper_markers = r.helper_markers_top_bottom = True
    r.helper_marker_edge_mm = r.helper_marker_len_mm = 2.0
    r.chart_text = "ChromIQ 21"
    r.chart_text_size_mm = 36.0 * 25.4 / 72.0
    r.stamp_command = False
    return r


def _bottom(tab) -> list[str]:
    from ui.tabs.tab_chart import TabChart
    from tests.margin_reports import report_for
    return [w for w in TabChart._engine_text_notes(
                tab, report_for(tab._current_layout_recipe()))[1]
            if "into the patches" in w and "sheet text along the bottom" in w]


def test_manual_says_it(tab):
    """The control. Without this the test below could pass on a silent panel."""
    tab._manual_layout_panel.set_recipe(_colliding())
    assert _bottom(tab), (
        "the mode that always warned has gone quiet, so the gamut test below "
        "would prove nothing")


def test_the_gamut_module_says_it_too(tab):
    """MUTATION: put `self._manual_btn.isChecked()` back in the gate and this
    goes red, because `_switch_mode("gamut")` unchecks that button."""
    tab._manual_layout_panel.set_recipe(_colliding())
    said_in_manual = _bottom(tab)
    tab._switch_mode("gamut")
    assert tab._mode_name() == "gamut"
    assert not tab._manual_btn.isChecked(), (
        "the module no longer unchecks the Manual button, so this test is "
        "measuring nothing; re-measure before deleting it")
    tab._manual_layout_panel.set_recipe(_colliding())
    said_in_gamut = _bottom(tab)
    assert said_in_gamut == said_in_manual, (
        "the FROM PROFILE GAMUT module lays the sheet out with Manual's own "
        "layout boxes and says nothing about a collision they cause:\n"
        f"  manual: {said_in_manual}\n  gamut:  {said_in_gamut}")


def test_guided_still_says_nothing(tab):
    """THE HALF THAT MUST NOT CHANGE. Guided owns a different set of settings
    and has no layout panel of its own; widening the gate to it would put a
    remedy naming "Margins (mm)" in front of a reader who has no such box."""
    tab._manual_layout_panel.set_recipe(_colliding())
    tab._switch_mode("guided")
    assert tab._current_mode() == "guided"
    assert not _bottom(tab), (
        "Guided now carries the Manual panel's warnings, which name controls "
        "it does not show")


def test_the_gate_asks_the_mode_and_not_the_button():
    """The spelling, because the behavioural test above needs a live widget and
    this one cannot be defeated by a stand-in that happens to look right."""
    import inspect
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._engine_text_notes)
    head = src.split("r = self._current_layout_recipe()")[0]
    # THE CODE, NOT THE PROSE ABOUT IT. The gate carries a comment that quotes
    # the old spelling by name, so a rule read off the raw text fails on the
    # explanation of its own fix.
    head = "\n".join(ln.split("#", 1)[0] for ln in head.splitlines())
    assert "_current_mode() == \"manual\"" in head, (
        "the notices gate no longer asks which page is showing")
    assert "_manual_btn.isChecked()" not in head, (
        "the gate is back on the mode BUTTON, which the FROM PROFILE GAMUT "
        "module unchecks while showing the very boxes these notices are about")
