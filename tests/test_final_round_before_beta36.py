"""The final challenge round before 4.3.0-beta.36, 2026-09-23, on screen.
Report: ~/Desktop/ChromIQ-beta36-proof/final-challenge/REPORT.md.

FC-2 (and B8-803) a profiling sheet loaded beside dated verifications: one
     press wrote one type into BOTH kinds of folder, which K19 then hid from
     both readouts, so the press looked like it did nothing (FC-1 was seen
     downstream of it).
FC-3 report text still told a ChromIQ user how ChromIQ works (K18).
FC-6 (open, B8-811) the title names the verification chart's file.
FC-8 after Clear list, Unlock still spoke of "this measurement".
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_both_kinds_loaded_generate_is_refused_and_says_why(tmp_path, qapp):
    """MUTATION: drop `_kinds_are_mixed()` from the handler and the press
    writes Printing records into the dated folder: red."""
    from tests.test_k19_counts_follow_the_run_type import (
        _run_with_a_profiling_record)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, run, vs = _run_with_a_profiling_record(tmp_path)
    dlg = MeasurementReportDialog(s, None, initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        dlg._add_source(run.dir / "sheet.ti3")
        qapp.processEvents()
        assert dlg._kinds_are_mixed()
        assert not dlg._generate_btn.isEnabled()
        assert "each has its own kind of report" in dlg._generate_btn.toolTip()
        before = set(run.dir.rglob("report_*.json"))
        dlg._say_generated = lambda saved, failed: None
        dlg._ask_update_or_create_new = lambda: "new"
        dlg._on_generate_report()
        qapp.processEvents()
        assert set(run.dir.rglob("report_*.json")) == before, (
            "a press with both kinds loaded wrote a report")
    finally:
        dlg.close()


def test_the_guide_explains_no_chromiq_mechanics(tmp_path, qapp):
    """FC-3. MUTATION: put any of these clauses back and this goes red."""
    import html as _html
    import re
    from tests.test_import_measurement_module import _verify_env
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, _ctl, _run = _verify_env(tmp_path)
    dlg = MeasurementReportDialog(s, None)
    try:
        g = re.sub(r"\s+", " ", _html.unescape(dlg._how_to_read_html()))
    finally:
        dlg.deleteLater()
    for said in ("ChromIQ copied", "in Preferences", "the report window",
                 "Save a report after", "ChromIQ converts",
                 "your finished profile", "your measurement file"):
        assert said not in g, said


def test_the_recorded_verdict_sentence_names_no_ChromIQ_action(tmp_path, qapp):
    """FC-3: *"Only unlocking the run's limits recalculates it"* was an
    instruction, and untrue as worded (unlocking recalculates nothing)."""
    import inspect
    from ui.dialogs import measurement_report_dialog as M
    src = inspect.getsource(M.MeasurementReportDialog._verdict_provenance)
    assert "Only unlocking" not in src


def test_after_clear_list_unlock_says_nothing_is_loaded(tmp_path, qapp):
    """FC-8. MUTATION: drop the branch and it speaks of "this measurement"."""
    from tests.test_round_3b_text_findings import _loose_window
    dlg = _loose_window(tmp_path)
    try:
        dlg._on_clear_list()
        qapp.processEvents()
        tip = dlg._unlock_check.toolTip()
        assert "No measurement is loaded yet." in tip, tip
    finally:
        dlg.deleteLater()
