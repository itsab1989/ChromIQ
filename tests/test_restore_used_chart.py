"""#130 (Knut, 2026-07-25): the "Restore Used Chart" button — its availability
rules and the exact reason it gives when it is unavailable."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,  # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import (MeasurementTargetBar,       # noqa: E402
                                       MeasurementTargetController)
from workflow.verify_chart_snapshot import snapshot_chart  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _env(tmp_path, *, with_chart=True):
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"; root.mkdir(exist_ok=True)
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    proj = Project.create(root / "P", "P"); run = proj.current_run(); run.ensure_dir()
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    if with_chart:
        run.verify_chart_ti1.write_text("TI1")
        run.verify_chart_ti2.write_text("TI2")
        (run.verifications_dir / f"{run.verify_stem}.channels.json").write_text("{}")
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_VERIFICATION)
    return ctl, run


def test_disabled_on_new_verification_with_the_specified_reason(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    enabled, tip = ctl.restore_state()
    assert enabled is False
    assert tip == ("Select an existing Verification run date to restore its "
                   "used chart")


def test_disabled_when_the_date_has_no_stored_chart(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    ctl.set_verification_id(v.id)

    enabled, tip = ctl.restore_state()
    assert enabled is False
    assert tip == "Selected Verification run date has no available chart to restore"


def test_disabled_when_the_stored_chart_folder_is_empty(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    (v.dir / "chart").mkdir()                       # present but empty
    ctl.set_verification_id(v.id)

    enabled, _ = ctl.restore_state()
    assert enabled is False


def test_enabled_for_a_date_that_has_a_stored_chart(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    snapshot_chart(v)
    ctl.set_verification_id(v.id)

    enabled, tip = ctl.restore_state()
    assert enabled is True
    assert tip == "Restore chart used for selected verification run date"


def test_disabled_while_a_measurement_is_running(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    snapshot_chart(v); ctl.set_verification_id(v.id)
    assert ctl.restore_state()[0] is True

    ctl.set_measuring(True)
    enabled, tip = ctl.restore_state()
    assert enabled is False and "measurement" in tip.lower()

    ctl.set_measuring(False)
    assert ctl.restore_state()[0] is True


def test_button_hidden_unless_run_type_is_verification(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    bar = MeasurementTargetBar(ctl)
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert bar._restore_btn.isVisible() is False

    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    # offscreen never truly shows widgets; the enable/tooltip state is the check
    assert bar._restore_btn.toolTip().startswith("Select an existing")


def test_confirmation_only_when_the_live_chart_differs(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    snapshot_chart(v); ctl.set_verification_id(v.id)
    assert ctl.restore_needs_confirmation() is False

    run.verify_chart_ti2.write_text("SOMETHING ELSE")
    assert ctl.restore_needs_confirmation() is True


def test_restore_emits_chart_restored_and_puts_the_chart_back(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    snapshot_chart(v); ctl.set_verification_id(v.id)
    run.verify_chart_ti2.write_text("REPLACED")
    seen = {"n": 0}
    ctl.chart_restored.connect(lambda: seen.__setitem__("n", seen["n"] + 1))

    result = ctl.restore_used_chart()

    assert result is not None and result.ok
    assert run.verify_chart_ti2.read_text() == "TI2"
    assert seen["n"] == 1, "the tabs must be told to refresh"


def test_restore_is_a_no_op_when_nothing_is_selected(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    assert ctl.restore_used_chart() is None
