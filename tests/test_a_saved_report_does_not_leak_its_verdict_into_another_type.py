"""A type that changes the document may not print the full report's verdict.

**FOUND BY AN ADVERSARIAL ROUND, ON THE DISK STATE EVERY REAL USER HAS.**

`stamp_verdict` writes `verdict.summary` and `verdict.overall` into every
report the app saves, computed over every row of the full report. The report
window's `_column_summary` hands that saved word straight back. A guard was
written so T4 could not do that, and the same door beside it was left open: a
**Grey and tone check**, which prints three rows, printed a red **FAIL** earned
by five colour rows it does not mention, with nothing on the page to account
for it.

The round that BUILT T3 missed it because a bare `.ti3` makes the window derive
the report live, which is the one state where that return does not fire. So
every test in this file saves a report the way `tab_measure` saves one, and
that is the whole point of the file.

The second face of the same defect: the `checked == 0` rule, which exists so a
column that checked nothing cannot read PASS, sits on the recompute path and
was therefore unreachable in the case it was written for.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.compliance_sets import (COND, FAIL, INFO, N_A,  # noqa: E402
                                      PASS, SUMMARY_REASONS)
from workflow.measurement_report import (REPORT_TYPE_FULL,  # noqa: E402
                                         REPORT_TYPE_GREY,
                                         REPORT_TYPE_RECORD,
                                         rows_for_report_type)


def _saved(tmp_path, qapp):
    """A run with a dated verification AND a saved report, as the app makes one."""
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    from workflow.measurement_report import (build_report, save_report,
                                             stamp_verdict)
    from workflow.run_compliance import ensure_bound
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    lim = ensure_bound(run, None, "chromiq_default")
    rep = build_report(str(v.measurement_ti3))
    stamp_verdict(rep, lim.limits, set_id=lim.set_id, set_label=lim.set_label)
    path = save_report(rep, v.dir)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    return dlg, run, path


def _as(dlg, run, tid):
    from workflow.run_compliance import set_run_report_type
    set_run_report_type(run, tid)
    dlg._forget_limits()
    dlg._sync_limit_controls()
    return dlg._runs_for_report()


def test_the_report_really_is_saved_or_this_file_proves_nothing(tmp_path, qapp):
    """The control. Every test below depends on the saved-summary path being
    the one taken, and a report without a recorded summary would make them all
    vacuous."""
    dlg, run, path = _saved(tmp_path, qapp)
    try:
        assert path.exists()
        reps = _as(dlg, run, REPORT_TYPE_FULL)
        rec = dlg._recorded(reps[0])
        assert rec is not None and rec.get("overall"), "nothing was stamped"
        assert isinstance(rec.get("summary"), dict)
    finally:
        dlg.close()


def test_the_grey_report_does_not_print_the_full_reports_word(tmp_path, qapp):
    """MUTATION: guard the early return on `_ungraded_by_type` alone, as it
    was, and this goes red."""
    dlg, run, _p = _saved(tmp_path, qapp)
    try:
        full = _as(dlg, run, REPORT_TYPE_FULL)
        f_sum = dlg._column_summary(full[0])
        grey = _as(dlg, run, REPORT_TYPE_GREY)
        g_sum = dlg._column_summary(grey[0])
        shown = len(dlg._verdict_rows(grey[0])[0])
        assert shown == len(rows_for_report_type(REPORT_TYPE_GREY)) or shown < f_sum.total
        assert g_sum.total <= shown, (
            f"the column counts {g_sum.total} rows and the document prints "
            f"{shown}: the verdict is about rows nobody can see")
        assert (g_sum.word, g_sum.reason) != (f_sum.word, f_sum.reason), \
            "the grey report printed the full report's verdict verbatim"
    finally:
        dlg.close()


def test_a_grey_report_that_checked_nothing_is_N_A_not_a_verdict(tmp_path, qapp):
    """THE FALSE-PASS FIX, FINALLY REACHABLE. It was written for exactly this
    case and sat on a path a saved report never takes; what a saved report
    showed instead was FAIL or COND, which is worse than the PASS it replaced,
    because a false pass is at least about rows the reader can see.

    MUTATION: drop the `checked == 0` clause, or the type guard on the early
    return, and this goes red.
    """
    dlg, run, _p = _saved(tmp_path, qapp)
    try:
        grey = _as(dlg, run, REPORT_TYPE_GREY)
        rows = dlg._verdict_rows(grey[0])[0]
        assert rows and all(x["word"] == N_A for x in rows), \
            "this chart supplies a grey ramp, so this case is not exercised"
        sm = dlg._column_summary(grey[0])
        assert sm.word == N_A, f"{sm.word} on a document where nothing was checked"
        assert sm.word not in (PASS, FAIL, COND)
        assert sm.reason == SUMMARY_REASONS["nothing_checked"]
    finally:
        dlg.close()


def test_the_printing_record_still_withholds_everything(tmp_path, qapp):
    """The door that WAS guarded must stay guarded once both share one rule."""
    dlg, run, _p = _saved(tmp_path, qapp)
    try:
        rec = _as(dlg, run, REPORT_TYPE_RECORD)
        rows = dlg._verdict_rows(rec[0])[0]
        assert rows and all(x["word"] in (INFO, N_A) for x in rows), str(rows)
        sm = dlg._column_summary(rec[0])
        assert sm.word == INFO
        assert sm.reason == SUMMARY_REASONS["record_type"]
    finally:
        dlg.close()


def test_the_full_report_still_shows_its_saved_word(tmp_path, qapp):
    """THE REGRESSION SURFACE OF THE FIX ITSELF. Knut ruled that a run keeps
    its values and its verdicts, so the type guard must not turn the saved word
    into a recomputed one for the type that is today's report.

    MUTATION: make `_type_changes_the_document` return True always and this
    goes red.
    """
    dlg, run, _path = _saved(tmp_path, qapp)
    try:
        reps = _as(dlg, run, REPORT_TYPE_FULL)
        live = dlg._column_summary(reps[0])

        # THE SAVED WORD HAS TO BE DISTINGUISHABLE FROM A RECOMPUTED ONE, or
        # this test cannot tell them apart: on an ordinary report they agree,
        # and the mutation that recomputes everything passed it. So the saved
        # word is moved to something a recompute would never produce from the
        # same rows, which is also the real case the rule exists for: Knut
        # ruled that a run keeps the verdict it was given even after the rules
        # around it move.
        assert live.word != PASS, "the live word already agrees; nothing is proved"
        moved = dict(reps[0])
        moved["verdict"] = dict(moved["verdict"], overall=PASS)
        moved["verdict"]["summary"] = dict(moved["verdict"]["summary"],
                                           reason=SUMMARY_REASONS["pass"])
        again = dlg._column_summary(moved)
        assert again.word == PASS, \
            "the saved verdict was recomputed instead of shown"
    finally:
        dlg.close()


def test_the_explanation_reaches_the_PDF_text(tmp_path, qapp):
    """The Overall word of a grey report is N-A and the reader cannot account
    for it from the table, so the sentence has to be printed. It reached only
    the cell's `title=`, which is a tooltip and which no PDF page carries. That
    is the THIRD time this exact fault has been fixed in this module.

    MUTATION: drop `nothing_checked` from `reason_needs_the_footnote` and this
    goes red.
    """
    import html as _html
    import re
    dlg, run, _p = _saved(tmp_path, qapp)
    try:
        grey = _as(dlg, run, REPORT_TYPE_GREY)
        needle = _html.escape(SUMMARY_REASONS["nothing_checked"].split(".")[0])
        for for_pdf in (False, True):
            body = dlg._report_body_html(grey, for_pdf=for_pdf)
            places = [m.start() for m in re.finditer(re.escape(needle), body)]
            assert places, f"for_pdf={for_pdf}: the sentence is nowhere"
            rendered = [i for i in places
                        if not re.search(r"title='[^']*$", body[:i])]
            assert rendered, (
                f"for_pdf={for_pdf}: every copy is inside a title= attribute")
    finally:
        dlg.close()


def test_the_column_counts_rows_that_carry_a_LIMIT(tmp_path, qapp):
    """`Summary.total` is documented as the limit-bearing rows, and the T4
    short-circuit returned every row instead. Latent, because the record
    sentence has no {total} placeholder; every other field of that dataclass is
    formatted straight into a user-visible sentence.

    MUTATION: count all rows and this goes red.
    """
    from workflow.compliance_sets import Limit, limits_from_json
    from workflow.measurement_report import recorded_compliance
    dlg, run, _p = _saved(tmp_path, qapp)
    try:
        rec = _as(dlg, run, REPORT_TYPE_RECORD)
        rows = dlg._verdict_rows(rec[0])[0]
        comp = recorded_compliance(rec[0]) or {}
        limits = limits_from_json(comp.get("thresholds")) or {}
        bearing = sum(1 for x in rows
                      if isinstance(limits.get(x.get("row_id")), Limit)
                      and limits[x["row_id"]].is_numeric)
        sm = dlg._column_summary(rec[0])
        assert sm.total == bearing, (
            f"total={sm.total} over {len(rows)} rows, {bearing} of which carry "
            f"a limit")
    finally:
        dlg.close()
