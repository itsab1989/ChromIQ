"""Create Chart swaps to the right chart when Run type / Profile run changes
(#130, Knut beta-2 test #4): switching Profiling↔Verification must load THAT
target's own chart, so edits and the next generation apply to the right chart —
not silently overwrite the other one."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                      # noqa: E402
from PyQt6.QtWidgets import QApplication                # noqa: E402

from core.argyll_runner import ArgyllRunner             # noqa: E402
from core.file_manager import FileManager, Project      # noqa: E402
from core.settings import AppSettings                   # noqa: E402
from core.measurement_target import (                   # noqa: E402
    RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION)
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FM:
    def __init__(self, root: Path):
        self._root = root

    def working_dir(self) -> Path:
        return self._root

    def project(self) -> Project:
        return Project.load(self._root)


def _settings(tmp_path) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


def _make_profiling_chart(run):
    run.ensure_dir()
    run.chart_ti1.write_text("ti1")
    run.chart_ti2.write_text("ti2")
    (run.dir / f"{run.stem}_01.tif").write_text("tif")


def _make_verify_chart(run):
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti1.write_text("ti1")
    run.verify_chart_ti2.write_text("ti2")
    (run.verifications_dir / f"{run.verify_stem}_01.tif").write_text("tif")


def _tab(settings):
    from ui.tabs.tab_chart import TabChart
    return TabChart(ArgyllRunner(settings), FileManager(settings), settings)


def test_switch_runtype_loads_matching_chart(qapp, tmp_path, monkeypatch):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    _make_profiling_chart(run)
    _make_verify_chart(run)

    tab = _tab(_settings(tmp_path))
    shown: list = []
    monkeypatch.setattr(tab, "_display_run_chart",
                        lambda ti2, tiffs, ti1: shown.append(Path(ti2)))

    ctl = MeasurementTargetController(_FM(proj.root))
    tab.set_target_controller(ctl)

    ctl.set_profile_run("run1")                 # profiling is the default type
    assert shown and shown[-1] == run.chart_ti2         # loaded the profiling chart

    shown.clear()
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert shown and shown[-1] == run.verify_chart_ti2  # swapped to the verify chart

    shown.clear()
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert shown and shown[-1] == run.chart_ti2         # swapped back to profiling


def test_switch_to_verification_without_chart_leaves_tab(qapp, tmp_path, monkeypatch):
    """Switching to Verification when no verify chart exists yet must NOT load
    (or overwrite) anything — the user is about to create it."""
    proj = Project.create(tmp_path / "Q", "Q")
    run = proj.current_run()
    _make_profiling_chart(run)                  # profiling chart only, no verify

    tab = _tab(_settings(tmp_path))
    shown: list = []
    monkeypatch.setattr(tab, "_display_run_chart",
                        lambda *a: shown.append(a))

    ctl = MeasurementTargetController(_FM(proj.root))
    tab.set_target_controller(ctl)
    ctl.set_profile_run("run1")
    shown.clear()

    ctl.set_run_type(RUN_TYPE_VERIFICATION)     # no verify chart on disk
    assert shown == []                          # tab left untouched


def test_new_run_target_does_not_load(qapp, tmp_path, monkeypatch):
    """'New run' (no run selected yet) has no existing chart to load."""
    proj = Project.create(tmp_path / "R", "R")
    _make_profiling_chart(proj.current_run())

    tab = _tab(_settings(tmp_path))
    shown: list = []
    monkeypatch.setattr(tab, "_display_run_chart", lambda *a: shown.append(a))

    ctl = MeasurementTargetController(_FM(proj.root))
    tab.set_target_controller(ctl)
    ctl.set_profile_run("")                      # "New run" sentinel
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert shown == []


def test_same_target_key_does_not_reload(qapp, tmp_path, monkeypatch):
    """A verification-date change (same run + type) must not reload the chart."""
    proj = Project.create(tmp_path / "S", "S")
    run = proj.current_run()
    _make_profiling_chart(run)
    _make_verify_chart(run)

    tab = _tab(_settings(tmp_path))
    shown: list = []
    monkeypatch.setattr(tab, "_display_run_chart",
                        lambda ti2, tiffs, ti1: shown.append(Path(ti2)))

    ctl = MeasurementTargetController(_FM(proj.root))
    tab.set_target_controller(ctl)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    shown.clear()
    ctl.set_verification_id("2026-06-01_090000")   # same run+type, different date
    assert shown == []                              # no reload
