"""K3 (Knut on beta 34): a note about "the standard" printed where no
standard is the reference.

    *"I opened demo project Report-Limits-Threshold-Series, and run 3 ... Full
    colour check, with quick check limit set ... 1) Grey balance of the grey
    ramp, average, Grey balance of the grey ramp, largest: The standard calls
    this metric recommended rather than required ... The test refers to the
    standard, which is not used as reference or to compare results against
    for the current settings. This is a bug."*

The run's stored copy of "Quick check" (and the saved report's record) still
marked the two grey rows "should", from when that set did. The set no longer
does, and a set of ChromIQ's own is no standard, so a stored "should" under
it is read as the plain limit it is: no brackets, no note. A set derived from
a standard keeps the distinction.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

NOTE = "The standard calls this metric recommended rather than required"


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_a_chromiq_set_never_carries_a_recommendation():
    """MUTATION: make `set_marks_recommendations` answer True for every set
    and the first assert goes red."""
    from workflow.compliance_sets import limits_from_json
    stored = {"grey_balance_neutral_ramp_avg": [3.0, "should"]}
    assert not limits_from_json(stored, "chromiq_quick")[
        "grey_balance_neutral_ramp_avg"].is_should
    assert limits_from_json(stored, "chromiq_quick")[
        "grey_balance_neutral_ramp_avg"].number == 3.0
    assert limits_from_json(stored, "custom_iso_12647_8")[
        "grey_balance_neutral_ramp_avg"].is_should
    assert limits_from_json(stored)["grey_balance_neutral_ramp_avg"].is_should


def _run_with_a_should_copy(tmp_path, set_id):
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    from workflow.measurement_report import (build_report, save_report,
                                             stamp_verdict)
    from workflow.run_compliance import bind_run
    from workflow.compliance_sets import limits_from_json
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    bind_run(run, set_id, None)
    meta = run.load_meta()
    thr = dict(meta.compliance_thresholds)
    # EVERY NUMERIC ROW marked "should", not only the two grey rows of the
    # demo: this fixture has no grey ramp, so those read N-A, and a note only
    # travels with a PASS or FAIL. The rows that ARE judged here carry it.
    for rid, n in list(thr.items()):
        n = n[0] if isinstance(n, list) else n
        if isinstance(n, (int, float)):
            thr[rid] = [float(n), "should"]
    meta.compliance_thresholds = thr
    run.save_meta(meta)
    rep = build_report(v.measurement_ti3)
    stamp_verdict(rep, limits_from_json(thr), set_id=set_id, set_label=set_id,
                  edited=False)
    save_report(rep, v.dir)
    return s, v


def _page(s, v, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        return dlg._view.toPlainText()
    finally:
        dlg.close()


def test_the_quick_check_page_says_nothing_about_a_standard(tmp_path, qapp):
    """The demo pack's run 3, rebuilt: a Quick check copy and a saved record
    that both still say "should". MUTATION: drop the `set_id` from any of the
    three `limits_from_json` call sites, or the recorded-row strip in
    `_verdict_rows`, and the note comes back."""
    s, v = _run_with_a_should_copy(tmp_path, "chromiq_quick")
    text = _page(s, v, qapp)
    assert NOTE not in text, "the page speaks of a standard under Quick check"


def test_a_set_derived_from_a_standard_keeps_its_note(tmp_path, qapp):
    """The control: the distinction is real under a standard's set, and the
    rule must not remove it there."""
    s, v = _run_with_a_should_copy(tmp_path, "custom_iso_12647_8")
    text = _page(s, v, qapp)
    assert NOTE in text, "the note vanished where a standard IS the reference"


def test_the_runs_own_copy_is_read_without_the_relic(tmp_path):
    """`run_limits` is what a LIVE judgement uses (a measurement with no
    saved record, the automatic report). MUTATION: drop the set id from its
    `limits_from_json` call and this goes red."""
    from tests.test_import_measurement_module import _verify_env
    from workflow.run_compliance import bind_run, run_limits
    _s, _fm, _ctl, run = _verify_env(tmp_path)
    bind_run(run, "chromiq_quick", None)
    meta = run.load_meta()
    thr = dict(meta.compliance_thresholds)
    thr["grey_balance_neutral_ramp_avg"] = [3.0, "should"]
    meta.compliance_thresholds = thr
    run.save_meta(meta)
    lim = run_limits(run, None).limits["grey_balance_neutral_ramp_avg"]
    assert not lim.is_should and lim.number == 3.0


def test_the_loaded_documents_limits_and_its_column_summary_carry_no_relic(
        tmp_path, qapp):
    """The two remaining readers of a SAVED record's thresholds: the loaded
    document's limits (what "Judged against" and Edit limits show) and the
    column summary (whose sentence has a form "... over a recommended
    value"). One judged row is made to FAIL under a stale "should", so a
    summary that still read it as a recommendation would say so.

    NOT A MUTATION GUARD FOR `_column_summary`'s call, said out loud: the
    column summary ignores "should" today (`set_summary` counts words, not
    recommendations), so dropping the set id there is an equivalent mutant.
    This check stands against a future summary that starts reading it. The
    loaded document's limits have their own guard below.
    """
    import datetime as _dt
    import shutil
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, v = _run_with_a_should_copy(tmp_path, "chromiq_quick")
    # A SECOND, LATER DATE to open the window on, and the first date's
    # measurement REMOVED: a saved report whose .ti3 is still there is rebuilt
    # from it, and then the record below would never be read.
    v2 = v.run.new_verification(_dt.datetime(2030, 1, 1))
    v2.ensure_dir()
    shutil.copy2(v.measurement_ti3, v2.measurement_ti3)
    # make every judged row fail, in the record, still marked "should"
    for f in (v.dir / "reports").glob("report_*.json"):
        p = json.loads(f.read_text(encoding="utf-8"))
        comp = p.get("compliance") or {}
        thr = comp.get("thresholds") or {}
        for rid, n in list(thr.items()):
            if isinstance(n, list) and isinstance(n[0], (int, float)):
                thr[rid] = [0.0001, "should"]
        # NO STORED SUMMARY, as an older record has none: `_column_summary`
        # returns a stored one as it is, and works it out from the recorded
        # thresholds only when there is none, which is the path under test.
        (p.get("verdict") or {}).pop("summary", None)
        for row in (p.get("verdict") or {}).get("rows") or []:
            if row.get("value") is not None and row.get("threshold") is not None:
                row.update(threshold=0.0001, should=True, word="FAIL",
                           **{"pass": False})
        f.write_text(json.dumps(p), encoding="utf-8")
    v.measurement_ti3.unlink()
    dlg = MeasurementReportDialog(s, None, initial_ti3=v2.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        dlg._select_all_btn.click()
        qapp.processEvents()
        old_row = next(r for r in dlg._runs_for_report()
                       if str(v.dir) in str(r.get("_origin_dir")))
        dl = dlg._document_limits()
        if dl is not None:
            assert not any(l.is_should for l in dl.limits.values()), (
                "the loaded document's limits still carry a recommendation")
        from workflow.compliance_sets import summary_text
        summ = dlg._column_summary(old_row)
        assert summ.conditional == 0 and summ.failed > 0, summ
        assert "recommended" not in (summ.reason + summary_text(summ)).lower(), summ
    finally:
        dlg.close()


def test_the_loaded_quick_check_documents_limits_carry_no_recommendation(
        tmp_path, qapp):
    """`_document_limits` is what Update stamps a rewritten record with, so a
    relic read there would put the flag and the note back into the NEW
    record. MUTATION: drop the set id from its `limits_from_json` call and
    this goes red."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, v = _run_with_a_should_copy(tmp_path, "chromiq_quick")
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        dl = dlg._document_limits()
        assert dl is not None, "no saved document is loaded, so this proves nothing"
        assert not any(l.is_should for l in dl.limits.values()), (
            "the loaded Quick check document's limits carry a recommendation")
    finally:
        dlg.close()
