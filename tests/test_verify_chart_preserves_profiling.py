"""#130 (Knut bug): a verification chart must live ONLY in runs/runN/
verifications/ — generating it must NOT destroy the run's profiling chart at the
run root. The two charts coexist."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from core.argyll_runner import ArgyllRunner                     # noqa: E402
from core.file_manager import FileManager, Project              # noqa: E402
from core.measurement_target import RUN_TYPE_VERIFICATION       # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from ui.tabs.tab_chart import TabChart                          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_verify_generation_keeps_profiling_chart_at_run_root(qapp, tmp_path):
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    tab = TabChart(ArgyllRunner(s), fm, s)
    ctl = MeasurementTargetController(fm)
    tab.set_target_controller(ctl)

    proj = Project.create(tmp_path / "P", "P"); run = proj.current_run(); run.ensure_dir()
    fm.set_target_name("P")
    stem = run.stem
    # A profiling chart (+ a built profile + measurement) at the run root.
    (run.dir / f"{stem}.ti1").write_text("prof-ti1")
    (run.dir / f"{stem}.ti2").write_text("prof-ti2")
    (run.dir / f"{stem}.tif").write_text("prof-tif")      # single page
    run.measurement_ti3.write_text("prof-meas")
    run.profile_icc.write_text("prof-icc")

    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_VERIFICATION)

    # --- the flow the build method + _on_generate_finished perform ---
    tab._verify_profiling_backup = tab._snapshot_profiling_chart()
    # verify generation overwrites the run root with the (smaller) verify chart
    (run.dir / f"{stem}.ti1").write_text("verify-ti1")
    (run.dir / f"{stem}.ti2").write_text("verify-ti2")
    (run.dir / f"{stem}.tif").write_text("verify-tif")
    run.adopt_run_chart_as_verify()          # move it into verifications/
    tab._restore_profiling_chart()           # put the profiling chart back

    # Profiling chart is intact at the run root…
    assert (run.dir / f"{stem}.ti2").read_text() == "prof-ti2"
    assert (run.dir / f"{stem}.tif").read_text() == "prof-tif"
    assert run.measurement_ti3.read_text() == "prof-meas"   # never touched
    assert run.profile_icc.read_text() == "prof-icc"
    # …and the verify chart lives only in verifications/.
    assert run.verify_chart_ti2.read_text() == "verify-ti2"
    assert (run.verifications_dir / f"{run.verify_stem}.tif").read_text() == "verify-tif"
    # The verify chart's stem is NOT at the run root.
    assert not (run.dir / f"{run.verify_stem}.ti2").exists()


def test_no_profiling_chart_snapshot_is_noop(qapp, tmp_path):
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    tab = TabChart(ArgyllRunner(s), fm, s)
    tab.set_target_controller(MeasurementTargetController(fm))
    Project.create(tmp_path / "Q", "Q").current_run().ensure_dir()
    fm.set_target_name("Q")
    # A fresh run with no profiling chart → nothing to snapshot.
    assert tab._snapshot_profiling_chart() is None
