"""K19, Knut on #182, 2026-09-23: *"Already generated for this run: Colour
summary (one page) (1), Full colour check (18), Grey and tone check (2),
Printing record (not graded) (2)"* on a Verification window whose "Report
shown" holds no Printing record at all. The line counted the run's OWN folder,
where the profiling sheet's reports live, as well as the dated verifications.

*"the counting of reports when in run type verification shall only count
reports that can exist as report types for a verification run. Also, when run
type is profiling, then only reports that are of type 'Printing record' shall
be counted. This also applies to the population of the contents in the Report
shows pulldown"*.

And round 3A (R3A-3): a report that records no type was labelled one way in
the list and counted another in the line.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from workflow.measurement_report import (KIND_PROFILING,        # noqa: E402
                                         KIND_VERIFICATION,
                                         REPORT_TYPE_FULL,
                                         REPORT_TYPE_RECORD,
                                         build_report,
                                         generated_report_types,
                                         save_report)


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _run_with_a_profiling_record(tmp_path):
    """Knut's shape: dated verifications with graded reports, AND the run's
    own profiling sheet with its Printing record in the run's folder."""
    from tests.test_a_generated_report_is_one_document import _messy_project
    from tests.test_import_measurement_module import _cgats, _PATCHES
    s, fm, run, vs = _messy_project(tmp_path, dates=2)
    sheet = run.dir / "sheet.ti3"
    sheet.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    rep = build_report(sheet)
    rep["report_type"] = REPORT_TYPE_RECORD
    save_report(rep, run.dir)
    return s, fm, run, vs


def test_a_verification_counts_no_profiling_record(tmp_path):
    """MUTATION: count `run.dir` for a verification again, and the Printing
    record is in the line: red."""
    _s, _fm, run, _vs = _run_with_a_profiling_record(tmp_path)
    counts = generated_report_types(run, KIND_VERIFICATION)
    assert REPORT_TYPE_RECORD not in counts, counts
    assert sum(counts.values()) >= 2, counts


def test_a_profiling_run_counts_only_its_printing_record(tmp_path):
    """MUTATION: drop the `allowed` filter and the verifications' Full
    colour checks are counted on a profiling window: red."""
    _s, _fm, run, _vs = _run_with_a_profiling_record(tmp_path)
    counts = generated_report_types(run, KIND_PROFILING)
    assert counts == {REPORT_TYPE_RECORD: 1}, counts


def test_an_untyped_report_is_counted_as_it_is_labelled(tmp_path):
    """R3A-3. A report that records no type, in the run's own folder, is a
    profiling sheet's, and is drawn and labelled as a Printing record; the
    line counted it as a Full colour check.

    MUTATION: fall back to `report_type(doc)` for an untyped file: red."""
    from tests.test_a_generated_report_is_one_document import _messy_project
    from tests.test_import_measurement_module import _cgats, _PATCHES
    _s, _fm, run, _vs = _messy_project(tmp_path, dates=1)
    sheet = run.dir / "sheet.ti3"
    sheet.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    rep = build_report(sheet)
    rep.pop("report_type", None)
    save_report(rep, run.dir)
    counts = generated_report_types(run, KIND_PROFILING)
    assert counts == {REPORT_TYPE_RECORD: 1}, counts


def test_the_window_line_and_list_follow_the_verification_kind(tmp_path,
                                                               qapp):
    """The line and the pulldown on a real Verification window."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, run, vs = _run_with_a_profiling_record(tmp_path)
    dlg = MeasurementReportDialog(s, None, initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        assert dlg._window_kind() == KIND_VERIFICATION
        line = dlg._generated_types_line(run)
        assert "Printing record" not in line, line
        labels = [dlg._saved_combo.itemText(i)
                  for i in range(1, dlg._saved_combo.count())]
        assert labels, "the fixture's verification reports are not listed"
        assert not any("Printing record" in t for t in labels), labels
    finally:
        dlg.close()


def _with_legacy_strays(tmp_path):
    """The two strays each filter exists for, so each is tested on its own:
    a pre-K13 Full colour check of the PROFILING sheet (the folder rule
    alone would count it for a verification; the type rule alone would count
    it for nothing, which hides the folder rule), and a beta-34 Printing
    record in a DATED folder (the folder rule alone counts it)."""
    s, fm, run, vs = _run_with_a_profiling_record(tmp_path)
    full = build_report(run.dir / "sheet.ti3")
    full["report_type"] = REPORT_TYPE_FULL
    save_report(full, run.dir)
    rec = build_report(vs[0].measurement_ti3)
    rec["report_type"] = REPORT_TYPE_RECORD
    save_report(rec, vs[0].dir)
    return s, fm, run, vs


def test_each_filter_holds_on_its_own(tmp_path):
    """MUTATIONS: count `run.dir` for a verification (the old Full colour
    check of the profiling sheet joins the verification count), or drop the
    type filter (the dated Printing record joins it, and the profiling Full
    colour check joins the profiling count): each red."""
    _s, _fm, run, vs = _with_legacy_strays(tmp_path)
    ver = generated_report_types(run, KIND_VERIFICATION)
    only_dated = generated_report_types(run, None)
    assert REPORT_TYPE_RECORD not in ver, ver
    # every verification report the dated folders hold, and nothing else
    dated_files = sum(len(list((v.dir / "reports").glob("report_*.json")))
                      for v in vs)
    assert sum(ver.values()) == dated_files - 1, (ver, dated_files)
    assert generated_report_types(run, KIND_PROFILING) == \
        {REPORT_TYPE_RECORD: 1}, generated_report_types(run, KIND_PROFILING)
    assert only_dated.get(REPORT_TYPE_RECORD, 0) >= 2, only_dated


def test_the_list_offers_only_the_kinds_types(tmp_path, qapp):
    """Adding the profiling sheet makes it the window's subject, so the
    window becomes a PROFILING window (K13's rule, and the mixed-kind
    question B8-803 has with Knut). The list then offers the sheet's
    Printing record and NOT the pre-K13 Full colour check of the same sheet.

    MUTATION: drop the `_entry_type(...) in allowed` filter and the old Full
    colour check is listed on a profiling window: red. (Letting `mine` take
    the run's folder on a verification window is not reachable this way,
    because the added file leads; the count's folder rule is pinned above.)
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, run, vs = _with_legacy_strays(tmp_path)
    dlg = MeasurementReportDialog(s, None, initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        dlg._add_source(run.dir / "sheet.ti3")
        qapp.processEvents()
        assert dlg._window_kind() == KIND_PROFILING
        labels = [dlg._saved_combo.itemText(i)
                  for i in range(1, dlg._saved_combo.count())]
        assert any("Printing record" in t for t in labels), labels
        assert not any("Full colour check" in t for t in labels), labels
    finally:
        dlg.close()
