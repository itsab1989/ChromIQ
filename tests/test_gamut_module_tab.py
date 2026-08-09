"""#133 feature B — the FROM PROFILE GAMUT module on the Create Chart tab.

The engine has its own tests (test_gamut_target.py); here the tab is driven:
the module button appears only for a verification target, the no-profile empty
state replaces the options with Generate disabled, Generate routes through the
gamut pipeline, and the adopted chart gets its reference + sidecar marker.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (                     # noqa: E402
    RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow import gamut_target as gt                   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _env(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    return s, fm, MeasurementTargetController(fm)


def _chart_tab(s, fm, ctl):
    from ui.tabs.tab_chart import TabChart
    tab = TabChart(ArgyllRunner(s), fm, s, None)
    tab.set_target_controller(ctl)
    return tab


def test_module_button_appears_only_for_a_verification_target(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    tab = _chart_tab(s, fm, ctl)
    assert not tab._gamut_btn.isVisibleTo(tab)

    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert tab._gamut_btn.isVisibleTo(tab)

    # Switching away hides the button AND leaves the module (T-like guard).
    tab._switch_mode("gamut")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert not tab._gamut_btn.isVisibleTo(tab)
    assert tab._mode_name() != "gamut"


def test_no_profile_shows_the_agreed_empty_state(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    tab = _chart_tab(s, fm, ctl)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")
    assert not tab._gamut_grp.isVisibleTo(tab)
    assert tab._gamut_empty_lbl.isVisibleTo(tab)
    assert "needs a finished profile first" in tab._gamut_empty_lbl.text()
    assert not tab._generate_btn.isEnabled()
    # And the Guided/Manual info box shows outside the module.
    tab._switch_mode("manual")
    tab._refresh_gamut_visibility()
    assert tab._verify_noprofile_lbl.isVisibleTo(tab)
    assert "no finished profile in this run yet" in tab._verify_noprofile_lbl.text()


def test_with_a_profile_the_options_show_and_the_info_box_hides(qapp, tmp_path, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.profile_icc.write_bytes(b"icc")
    tab = _chart_tab(s, fm, ctl)
    monkeypatch.setattr(tab, "_gamut_coverage", lambda *a, **k: 5413)
    tab._gamut_master_total = 5960
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")
    assert tab._gamut_grp.isVisibleTo(tab)
    assert not tab._gamut_empty_lbl.isVisibleTo(tab)
    assert not tab._verify_noprofile_lbl.isVisibleTo(tab)
    assert tab._generate_btn.isEnabled()
    tab._update_gamut_count_line()
    text = tab._gamut_count_lbl.text()
    assert "5413" in text and "5960" in text
    assert "8 cube corners" in text


def test_generate_routes_through_the_gamut_pipeline(qapp, tmp_path, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.profile_icc.write_bytes(b"icc")
    tab = _chart_tab(s, fm, ctl)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")

    def fake_select(profile, count, margin, intent, **kw):
        sel = gt.GamutSelection(
            master_version="TEST-r0", master_total=10, in_gamut_total=4,
            requested=count, intent=intent, margin=margin)
        sel.targets = [(i, (50.0, 0.0, 0.0), (10.0 * i, 20.0, 30.0))
                       for i in range(min(count, 4))]
        sel.corners = list(zip(gt.CORNER_DEVICES, gt.CORNER_DEVICES))
        return sel
    monkeypatch.setattr("workflow.gamut_target.select_gamut_targets",
                        fake_select)
    built: list = []
    monkeypatch.setattr(tab, "_generate_from_ti1",
                        lambda ti1, **kw: built.append(Path(ti1)))
    tab._gamut_count_spin.setValue(100)

    tab._on_generate()
    assert built, "gamut mode must route Generate through the gamut pipeline"
    assert built[0].parent == run.cache_dir
    assert built[0].exists()
    sel = tab._pending_gamut_selection
    assert sel is not None and sel.achieved == 4
    # The capped-and-said-so line (§13).
    assert "Only 4 of the requested 100" in tab._log.toPlainText()


def test_reference_and_marker_written_after_adopt(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    ti2 = run.verify_chart_ti2
    ti2.write_text("CTI2\n")
    tab = _chart_tab(s, fm, ctl)

    sel = gt.GamutSelection(
        master_version="TEST-r0", master_total=10, in_gamut_total=2,
        requested=2, intent="absolute", margin="safe")
    sel.targets = [(0, (50.0, 0.0, 0.0), (10.0, 20.0, 30.0))]
    sel.corners = [((100.0, 100.0, 100.0), (100.0, 0.0, 0.0))]
    tab._pending_gamut_selection = sel

    tab._write_gamut_reference_after_adopt(ti2)
    from workflow.verification_print import (STATE_CONVERTED,
                                             chart_conversion_state,
                                             colorimetric_reference_for)
    ref = colorimetric_reference_for(ti2)
    assert ref.exists()
    sidecar = json.loads(run.verify_chart_channels_json.read_text())
    assert sidecar["colorimetric_reference"] == ref.name
    # Feature A's Print tab will now force Raw for this chart.
    assert chart_conversion_state(ti2) == STATE_CONVERTED
    assert tab._pending_gamut_selection is None
    assert "print it exactly as it is" in tab._log.toPlainText()


def test_relayout_restores_the_reference_from_the_cache(qapp, tmp_path):
    """The auto-update preview re-lays out the chart with no fresh selection;
    the adoption step clears the verify files — the reference must come back
    from the module's cached copy, or the chart degrades to the A3c state."""
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    ti2 = run.verify_chart_ti2
    ti2.write_text("CTI2\n")
    tab = _chart_tab(s, fm, ctl)

    sel = gt.GamutSelection(
        master_version="TEST-r0", master_total=10, in_gamut_total=1,
        requested=1, intent="absolute", margin="safe")
    sel.targets = [(0, (50.0, 0.0, 0.0), (10.0, 20.0, 30.0))]
    gt.write_colorimetric_reference(
        sel, run.ensure_cache_dir() / "gamut-target-reference.ti3")

    tab._gamut_active = True
    tab._pending_gamut_selection = None          # a re-layout, not a generate
    tab._write_gamut_reference_after_adopt(ti2)
    from workflow.verification_print import (STATE_CONVERTED,
                                             chart_conversion_state,
                                             colorimetric_reference_for)
    assert colorimetric_reference_for(ti2).exists()
    assert chart_conversion_state(ti2) == STATE_CONVERTED

    # A targen chart replacing a gamut chart must NOT inherit the targets.
    colorimetric_reference_for(ti2).unlink()
    tab._gamut_active = False
    tab._write_gamut_reference_after_adopt(ti2)
    assert not colorimetric_reference_for(ti2).exists()


def test_auto_preview_toggle_shows_in_the_gamut_module(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.profile_icc.write_bytes(b"icc")
    tab = _chart_tab(s, fm, ctl)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")
    assert tab._auto_preview_row_w.isVisibleTo(tab)
    tab._switch_mode("guided")
    assert not tab._auto_preview_row_w.isVisibleTo(tab)


def test_auto_fills_the_manual_pages(qapp, tmp_path, monkeypatch):
    """Auto = per-sheet capacity × the Manual pages spin, minus the 8 corners
    that always ride along; the spin greys and shows the computed number."""
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.profile_icc.write_bytes(b"icc")
    tab = _chart_tab(s, fm, ctl)
    monkeypatch.setattr(tab, "_gamut_per_sheet", lambda: 105)
    monkeypatch.setattr(tab, "_gamut_coverage", lambda *a, **k: 5000)
    tab._gamut_master_total = 5960
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")
    if tab._manual_pages_spin is not None:
        tab._manual_pages_spin.setValue(2)
    tab._gamut_auto_check.setChecked(True)
    assert tab._gamut_effective_count() == 105 * 2 - 8
    tab._update_gamut_count_line()
    assert not tab._gamut_count_spin.isEnabled()
    assert tab._gamut_count_spin.value() == 202
    tab._gamut_auto_check.setChecked(False)
    tab._update_gamut_count_line()
    assert tab._gamut_count_spin.isEnabled()
