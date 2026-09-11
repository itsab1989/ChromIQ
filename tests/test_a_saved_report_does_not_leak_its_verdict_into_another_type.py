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


#: A measurement WITH a nine-step grey ramp, which is what makes the grey rows
#: carry numbers. The shared `_PATCHES` fixture has no ramp, so on it the grey
#: rows read N-A and the whole "a number nobody graded" case is invisible,
#: which is how it reached a release branch.
_GREY_HDR = """CTI3

DESCRIPTOR "Argyll Calibration Target chart information 3"
KEYWORD "DEVICE_CLASS"
DEVICE_CLASS "OUTPUT"
COLOR_REP "RGB_XYZ"

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS {n}
BEGIN_DATA
{rows}
END_DATA
"""


def _grey_ramp_ti3() -> str:
    rows, i = [], 0
    for step in range(9):
        g = step * 100.0 / 8.0
        i += 1
        y = 0.05 + 0.9 * (g / 100.0) ** 2.2
        # a deliberate tint, so grey balance is neither zero nor absent
        rows.append(f"{i} {g:.4f} {g:.4f} {g:.4f} "
                    f"{y * 0.98:.4f} {y:.4f} {y * 1.02:.4f}")
    for r in (0, 50, 100):
        for g in (0, 50, 100):
            for b in (0, 50, 100):
                i += 1
                y = 0.2 + 0.006 * (r + g + b)
                rows.append(f"{i} {r:.4f} {g:.4f} {b:.4f} "
                            f"{y * 0.95:.4f} {y:.4f} {y * 1.08:.4f}")
    return _GREY_HDR.format(n=len(rows), rows="\n".join(rows))


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


# ---------------------------------------------------------------------------
# …and "nothing was checked" has TWO causes, which one sentence answered as one
# ---------------------------------------------------------------------------
def test_a_chart_that_DID_supply_the_values_is_not_told_to_add_them(tmp_path,
                                                                    qapp):
    """A second adversarial round drove a chart WITH a nine-step grey ramp:
    both grey rows carried real numbers, both over their limits, and both read
    INFO because nobody recorded how the sheet was printed (CH-17). Nothing was
    checked, and the sentence said the chart had supplied none of the values
    and sent the reader to Create Chart to add patches that are already there.

    MUTATION: use one sentence for both causes and this goes red.
    """
    from workflow.compliance_sets import (INFO, N_A, Limit, set_summary,
                                          SUMMARY_REASONS)
    v = Limit.value(1.5)
    # every bearing row N-A: the chart really did supply nothing
    missing = set_summary([(v, N_A), (v, N_A)], set_is_iso=False, graded=True)
    assert missing.reason == SUMMARY_REASONS["nothing_checked"]
    assert "add those patches" in missing.reason

    # every bearing row INFO: the values are there and nobody graded them
    ungraded = set_summary([(v, INFO), (v, INFO)], set_is_iso=False, graded=True)
    assert ungraded.word == N_A
    assert ungraded.reason == SUMMARY_REASONS["nothing_graded"], ungraded.reason
    assert "supplied none" not in ungraded.reason
    assert "Create Chart" not in ungraded.reason

    # …and a mixture is not told the chart supplied nothing either
    mixed = set_summary([(v, N_A), (v, INFO)], set_is_iso=False, graded=True)
    assert mixed.reason == SUMMARY_REASONS["nothing_graded"]


def test_a_row_with_a_number_nobody_graded_says_why_on_paper(tmp_path, qapp):
    """The note under the table listed N-A rows only, so a row that HAS a
    number and was not judged said why in a tooltip and nowhere else.

    **AND IT MUST NOT SAY IT UNDER THE WRONG HEADING.** The first version of
    this test asserted the row appeared in `_not_computed` and never read the
    heading that list is printed under, so it passed green while the page
    called a computed row "not computed" and told the reader to add patches
    that are already on the chart. A third adversarial round read the printed
    page. This test now asks the list that is actually true of these rows, and
    `test_the_page_does_not_call_a_measured_row_not_computed` guards the
    heading.

    MUTATION: fold the two lists back together and this goes red.
    """
    from tests.test_import_measurement_module import _verify_env
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.compliance_sets import INFO
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_grey_ramp_ti3(), encoding="utf-8")
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        from workflow.run_compliance import set_run_report_type
        # T2, NOT T4. On the Printing record every row is INFO because the type
        # says so, and the note is deliberately silent there: the summary
        # already says the document judges nothing, and naming two of eight
        # rows would imply the other six were graded.
        set_run_report_type(run, REPORT_TYPE_FULL)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        reps = dlg._runs_for_report()
        rows, _rc = dlg._verdict_rows(reps[0])
        with_reason = [x for x in rows
                       if x.get("word") == INFO and x.get("reason")]
        assert with_reason, (
            "this chart has no ungraded row with a reason, so the case is not "
            "exercised; `_grey_ramp_ti3` is supposed to produce two")
        listed = {label for label, _why in dlg._measured_not_graded(reps[0])}
        assert not dlg._not_computed(reps[0]) or all(
            lbl not in listed for lbl, _w in dlg._not_computed(reps[0])), \
            "a row is in both lists at once"
        from workflow.compliance_sets import ROW_BY_ID
        for x in with_reason:
            rid = x.get("row_id") or x.get("key")
            if rid in ROW_BY_ID:
                from core.i18n import tr
                assert tr(ROW_BY_ID[rid].label) in listed, (
                    f"{rid} has a number nobody graded and the page never "
                    f"says why")
    finally:
        dlg.close()


def test_a_recalculation_re_stamps_the_TYPE_as_well_as_the_verdict(tmp_path,
                                                                   qapp):
    """Unlocking a run's limits rewrites every saved report with the run's
    current numbers. It left them claiming the type the run held when they
    were first saved, so the record said one thing and the run another.

    MUTATION: drop the `stamp_report_type` call from `_recalculate_run` and
    this goes red.
    """
    import json
    from workflow.measurement_report import report_type
    from workflow.run_compliance import set_run_report_type
    dlg, run, path = _saved(tmp_path, qapp)
    try:
        # the report was saved without a type, as an older build's would be
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc.pop("report_type", None)
        path.write_text(json.dumps(doc), encoding="utf-8")
        assert report_type(json.loads(path.read_text(encoding="utf-8"))) \
            == REPORT_TYPE_FULL

        set_run_report_type(run, REPORT_TYPE_RECORD)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        dlg._recalculate_run()
        qapp.processEvents()

        after = json.loads(path.read_text(encoding="utf-8"))
        assert after.get("report_type") == REPORT_TYPE_RECORD, (
            "the recalculation rewrote the verdict and left the type saying "
            "what the run no longer says")
        assert after.get("schema") == 7, "the schema moved"
    finally:
        dlg.close()


def test_the_page_does_not_call_a_measured_row_not_computed(tmp_path, qapp):
    """THE HEADING IS PART OF THE SENTENCE.

    A grey row carrying 1.341, on a chart with a nine-step ramp, was printed
    under "Not computed on this chart:" and followed by "add the missing
    patches to the chart in Create Chart to have it checked". Both halves are
    false of that row, and the second is the exact advice the round before had
    removed from the summary above it.

    MUTATION: put the INFO rows back into `_not_computed` and this goes red.
    """
    import html as _html
    from tests.test_import_measurement_module import _verify_env
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.compliance_sets import INFO, ROW_BY_ID
    from workflow.run_compliance import set_run_report_type
    from core.i18n import tr
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_grey_ramp_ti3(), encoding="utf-8")
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        set_run_report_type(run, REPORT_TYPE_GREY)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        reps = dlg._runs_for_report()
        rows, _rc = dlg._verdict_rows(reps[0])
        # A ROW WITH NO RECORDED REASON IS NOT IN THIS NOTE, AND SHOULD NOT BE.
        # `ramps_30_70_dl_max` comes out INFO with a real number because the
        # set puts no limit on it, which is what INFO means and needs no
        # explaining. The note is for a row that WAS limited and was left
        # ungraded anyway.
        measured = [x for x in rows if x.get("word") == INFO
                    and x.get("value") is not None and x.get("reason")]
        assert measured, "no measured-but-ungraded row with a reason on this chart"
        body = dlg._report_body_html(reps, for_pdf=True)

        head = _html.escape(tr("Not computed on this chart:"))
        i = body.find(head)
        if i >= 0:
            block = body[i:body.find("</div>", i)]
            for x in measured:
                rid = x.get("row_id")
                if rid in ROW_BY_ID:
                    assert _html.escape(tr(ROW_BY_ID[rid].label)) not in block, (
                        f"{rid} has a number and is listed as not computed")

        mine = _html.escape(tr("Measured but not graded, on at least one "
                               "measurement:"))
        j = body.find(mine)
        assert j >= 0, "the measured-but-ungraded rows have no note of their own"
        block2 = body[j:body.find("</div>", j)]
        assert "Create Chart" not in block2, \
            "the note tells the reader to add patches that are already there"
        for x in measured:
            rid = x.get("row_id")
            if rid in ROW_BY_ID:
                assert _html.escape(tr(ROW_BY_ID[rid].label)) in block2, rid
    finally:
        dlg.close()


def test_the_printing_record_does_not_single_out_two_of_eight_rows(tmp_path,
                                                                   qapp):
    """On T4 every row is INFO because the TYPE says so, and the summary says
    the report judges none of it. A note naming two of them as "measured but
    not graded" implies the other six were graded, and blames the printing
    condition for a choice the user made.

    MUTATION: drop the `_ungraded_by_type` guard from `_measured_not_graded`
    and this goes red.
    """
    import html as _html
    from core.i18n import tr
    from tests.test_import_measurement_module import _verify_env
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.compliance_sets import INFO
    from workflow.run_compliance import set_run_report_type
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_grey_ramp_ti3(), encoding="utf-8")
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        set_run_report_type(run, REPORT_TYPE_FULL)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        assert dlg._measured_not_graded(dlg._runs_for_report()[0]), \
            "the note is empty even on Full colour check, so nothing is proved"

        set_run_report_type(run, REPORT_TYPE_RECORD)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        reps = dlg._runs_for_report()
        rows, _rc = dlg._verdict_rows(reps[0])
        assert all(x["word"] == INFO or x["word"] == "N-A" for x in rows)
        assert not dlg._measured_not_graded(reps[0]), \
            "two of eight rows are singled out on a report that judges none"
        body = dlg._report_body_html(reps, for_pdf=True)
        head = _html.escape(tr("Measured but not graded, on at least one "
                               "measurement:"))
        assert head not in body, "the note is printed on a type that judges nothing"
    finally:
        dlg.close()
