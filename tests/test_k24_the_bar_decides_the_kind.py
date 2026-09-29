"""K24, Knut on #182, 2026-09-23: *"The open measurement window strictly shows
and lists and counts report types that are allowed according to the set 'run
type' in the profile bar. So a user must exit the measurement report window
and change run type to profiling, then enter measurement report window again,
in order to show, list and count reports of 'printing record' type."*

The window took its kind from the measurement it was opened on, so a
profiling sheet added to a Verification window made it a Profiling window.
"""
from __future__ import annotations

import os
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _host(run_type):
    """A parent widget carrying the profile bar's controller, as MainWindow
    and every tab do."""
    from PyQt6.QtWidgets import QWidget
    w = QWidget()
    w._target_ctl = types.SimpleNamespace(
        target=types.SimpleNamespace(run_type=run_type))
    return w


def test_a_verification_bar_keeps_the_window_a_verification(tmp_path, qapp):
    """MUTATION: drop the `_bar_kind` lookup and the added profiling sheet
    makes the window a Profiling one, listing its Printing record: red."""
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from tests.test_k19_counts_follow_the_run_type import (
        _run_with_a_profiling_record)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import KIND_VERIFICATION
    s, _fm, run, vs = _run_with_a_profiling_record(tmp_path)
    host = _host(RUN_TYPE_VERIFICATION)
    dlg = MeasurementReportDialog(s, host, initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        dlg._add_source(run.dir / "sheet.ti3")
        qapp.processEvents()
        assert dlg._window_kind() == KIND_VERIFICATION
        labels = [dlg._saved_combo.itemText(i)
                  for i in range(1, dlg._saved_combo.count())]
        assert not any("Printing record" in t for t in labels), labels
        assert "Printing record" not in dlg._generated_types_line(run)
    finally:
        dlg.close()
        host.deleteLater()


def test_a_profiling_bar_makes_a_profiling_window(tmp_path, qapp):
    """Opened on a dated verification while the bar says Profiling: the
    window counts and lists the Printing record only."""
    from core.measurement_target import RUN_TYPE_PROFILING
    from tests.test_k19_counts_follow_the_run_type import (
        _run_with_a_profiling_record)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import KIND_PROFILING
    s, _fm, run, vs = _run_with_a_profiling_record(tmp_path)
    host = _host(RUN_TYPE_PROFILING)
    dlg = MeasurementReportDialog(s, host, initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        assert dlg._window_kind() == KIND_PROFILING
        line = dlg._generated_types_line(run)
        assert "Printing record" in line and "Full colour check" not in line, line
    finally:
        dlg.close()
        host.deleteLater()


def test_no_bar_falls_back_to_the_measurement(tmp_path, qapp):
    from tests.test_k19_counts_follow_the_run_type import (
        _run_with_a_profiling_record)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, run, vs = _run_with_a_profiling_record(tmp_path)
    dlg = MeasurementReportDialog(s, None, initial_ti3=vs[-1].measurement_ti3)
    try:
        assert dlg._bar_kind() == (False, None)
        assert dlg._window_kind() == "verification"
    finally:
        dlg.close()
