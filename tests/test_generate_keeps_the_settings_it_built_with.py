"""Generating a chart must not throw away the settings it was generated with.

Basti, 2026-08-22, from source, twice in a row: Create Chart in Guided,
instrument SpectroScan, paper 4x6, press Generate — the chart appeared and the
tab jumped to Manual with ColorMunki selected. Building a chart makes the run its
own, which fires the target-switch handler, which loads that run's *stored*
Create Chart state over the state the build just used.

The shield was already there for the engine recipe (2026-08-16, the Hand Held
preset that came back "less wide") and had been left covering only that key. The
fix widened it and made it reliable.

**What was never covered anywhere in the repo is the OUTCOME.** The existing
tests pin the shield — that `_apply_ui_state` keeps things while a build owns the
screen, and that the flag is cleared afterwards. None of them assert that after a
real Generate the settings on screen are still the ones the chart was built with,
which is what the user experiences and what the Windows verification put on the
manual list (§9a) precisely because no automated test existed.

These drive `_apply_ui_state` through the state a build leaves behind, for every
key it can restore, rather than through the one key that first went wrong.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PyQt6.QtCore import QSettings                # noqa: E402
from PyQt6.QtWidgets import QApplication          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    return TabChart(ArgyllRunner(s), FileManager(s), s)


#: A stored record that differs from the screen in EVERY key §9a names. Each
#: value is deliberately unequal to what the test puts on screen first — an
#: earlier version stored `stamp: True` against a box that is already checked,
#: so that assertion could never fail and "both mutations proven" was untrue
#: of it.
STORED = {
    "mode": "manual",
    "guided": {"instrument": "CM", "paper": "A4", "pages": 3},
    "engine_on": False,
    "stamp": False,
    "gamut": {"count": 99},
    "engine_cal": {"path": "/somewhere/else.cal", "mode": "include"},
    "engine_recipe": {"instrument": "CM", "paper": "A3", "area_cols": 17,
                      "margin_left": 14.0},
}


def _screen_state(tab):
    """What §9a lists, read off the tab: module, instrument, paper, layout,
    engine switch, its calibration, gamut count, stamp flag."""
    panel = tab._manual_layout_panel
    rec = panel.get_recipe()
    cal = panel.get_cal() if hasattr(panel, "get_cal") else ("", "off")
    return {
        "mode": tab._mode_name(),
        "instrument": tab._instr_combo.currentData(),
        "paper": tab._paper_combo.currentData(),
        "layout_cols": getattr(rec, "area_cols", None),
        "layout_margin": getattr(rec, "margin_left", None),
        "engine_on": bool(tab._settings.get("use_chromiq_layout_engine", True)),
        "cal": tuple(cal) if isinstance(cal, (list, tuple)) else cal,
        "gamut_count": tab._gamut_count_spin.value(),
        "stamp": tab._manual_stamp_cmd_check.isChecked(),
    }


def _set_up_a_build(tab):
    """Guided, SpectroScan, 4x6, with a layout and options unlike STORED."""
    tab._switch_mode("guided")
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("SS"))
    for k in range(tab._paper_combo.count()):
        if "4x6" in str(tab._paper_combo.itemData(k) or ""):
            tab._paper_combo.setCurrentIndex(k)
            break
    tab._settings.set("use_chromiq_layout_engine", True)
    tab._manual_stamp_cmd_check.setChecked(True)
    tab._gamut_count_spin.setValue(1234)
    return _screen_state(tab)


def test_everything_the_build_used_survives_the_load_that_follows(tab):
    """§9a in full: all eight keys, each differing from what is stored."""
    before = _set_up_a_build(tab)
    assert before["paper"] == "4x6" and before["instrument"] == "SS"

    tab._layout_owned_by_build = True          # what a build in flight leaves
    tab._apply_ui_state(STORED)
    after = _screen_state(tab)

    differs = [k for k in before if before[k] != after[k]]
    assert not differs, (
        f"the load replaced what the chart was built with: {differs}\n"
        f"  before {[(k, before[k]) for k in differs]}\n"
        f"  after  {[(k, after[k]) for k in differs]}")


def test_without_a_build_the_targets_own_settings_still_load(tab):
    """The shield must not become a switch that turns per-target settings off:
    selecting a target is exactly when its stored choices are meant to arrive
    (per_target_settings.md L1-L4, F3)."""
    _set_up_a_build(tab)
    tab._layout_owned_by_build = False
    tab._apply_ui_state(STORED)
    after = _screen_state(tab)

    assert after["mode"] == "manual"
    assert after["instrument"] == "CM"
    assert after["paper"] == "A4"
    assert after["gamut_count"] == 99
    # Not the stamp flag here: the engine recipe carries its own stamp_command
    # and is applied after it, so on this path the box has two writers and the
    # assertion would not say which one won. The build case above still covers
    # it — there NOTHING may change, whichever writer would have changed it.
