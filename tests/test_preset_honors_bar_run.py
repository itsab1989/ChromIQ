"""#130 CRITICAL (Knut): a preset must build the chart into the run the
Profile-run bar shows ("Overwrite run N"), not the project's current (last) run.
The prebuilt "by Pharmacist" presets and the .ti1-based presets (TC9.18,
Spyderprint) bypassed the bar alignment and jumped the chart to the last run."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog               # noqa: E402

from core.argyll_runner import ArgyllRunner                     # noqa: E402
from core.file_manager import FileManager, Project              # noqa: E402
from core.measurement_target import RUN_TYPE_PROFILING          # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from ui.tabs.tab_chart import TabChart                          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _no_dialogs(monkeypatch):
    monkeypatch.setattr(QDialog, "exec", lambda self: 0, raising=False)


def _tab_with_three_runs(tmp_path):
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path)); s.set("use_chromiq_layout_engine", False)
    fm = FileManager(s)
    tab = TabChart(ArgyllRunner(s), fm, s)
    tab._switch_mode("manual")
    if not tab._manual_panel_inited:
        tab._init_manual_layout_panel()
    ctl = MeasurementTargetController(fm); tab.set_target_controller(ctl)
    proj = Project.create(tmp_path / "P", "P"); proj.current_run().ensure_dir()
    proj.new_run().ensure_dir(); proj.new_run().ensure_dir()   # run1, run2, run3
    fm.set_target_name("P"); tab._update_name_fields()
    return tab, fm, ctl


def test_prebuilt_preset_builds_into_bar_run_not_last(qapp, tmp_path):
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    assert Project.load(tmp_path / "P").current_run().id == "run3"   # last is current
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)

    tab._apply_prebuilt_preset("__chromiq_tc300_builtin__", "P")

    # The chart landed in run1 (the bar's selection), not run3.
    p = Project.load(tmp_path / "P")
    assert p.current_run().id == "run1"
    assert ctl.target.profile_run == "run1"
    assert p.run("run1").chart_ti2.exists()
    assert not p.run("run2").chart_ti2.exists()
    assert not p.run("run3").chart_ti2.exists()


def test_ti1_preset_aligns_to_bar_run(qapp, tmp_path, monkeypatch):
    """_generate_from_ti1 (TC9.18 / Spyderprint) must align the current run to the
    bar before generating — checked by capturing the run at generation time."""
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)
    captured = {}
    monkeypatch.setattr(
        tab._creator, "load_ti1_and_generate_preview",
        lambda *a, **k: captured.__setitem__(
            "run", Project.load(tmp_path / "P").current_run().id))
    ti1 = tmp_path / "P" / "runs" / "run1" / "seed.ti1"; ti1.write_text("CTI1\n")

    tab._generate_from_ti1(ti1)

    assert captured.get("run") == "run1"     # aligned to the bar, not run3
