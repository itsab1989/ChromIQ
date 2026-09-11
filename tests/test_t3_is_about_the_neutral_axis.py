"""T3, "Grey and tone check": the neutral axis and the mid-tone ramps, alone.

#182 W-A. Knut's module H without the G7 name, kept because it is the only
short document about the neutral axis, and that is what a user wants before
deciding whether a printer is worth profiling.

The rows it leaves out are DROPPED, not shown as not applicable. A report whose
subject is the neutral axis does not gain by listing the colour rows it
deliberately omits, and a reader would otherwise have to work out which N-A
meant "not measured" and which meant "not this report's subject".

And the column's own word follows the rows it shows. Filtering only the table
would leave a Grey and tone check reading FAIL because of a colour row it never
mentions.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.compliance_sets import N_A, SUMMARY_REASONS  # noqa: E402
from workflow.measurement_report import (REPORT_TYPE_FULL,  # noqa: E402
                                         REPORT_TYPE_GREY,
                                         REPORT_TYPE_RECORD,
                                         report_type_is_built,
                                         rows_for_report_type)


def _dialog(tmp_path, qapp):
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    return dlg, run


def _as(dlg, run, tid):
    from workflow.run_compliance import set_run_report_type
    set_run_report_type(run, tid)
    dlg._forget_limits()
    dlg._sync_limit_controls()
    return dlg._runs_for_report()


def _ids(dlg, reps):
    return [x.get("row_id") or x.get("key")
            for x in dlg._verdict_rows(reps[0])[0]]


def test_t3_is_offered_as_something_chromiq_can_produce():
    assert report_type_is_built(REPORT_TYPE_GREY)
    assert rows_for_report_type(REPORT_TYPE_GREY)
    assert rows_for_report_type(REPORT_TYPE_FULL) is None, \
        "the full report must never be filtered"
    assert rows_for_report_type(REPORT_TYPE_RECORD) is None, \
        "the Printing record records everything; it only withholds the verdict"


def test_t3_covers_every_grey_row_there_is():
    """THE ROW SET IS DERIVED, NOT RESTATED.

    The behavioural tests below run on a chart with no 30-70 ramp, so dropping
    `ramps_30_70_dl_max` from T3 changed nothing any of them could see: the
    mutation did not land, which is the whole reason this test exists.

    So the set is checked against the row model instead. T3 must contain every
    row in the `grey_ramp` group, because that group IS the neutral axis, plus
    the 30-70 lightness ramp, which is the tone half of the same question. A
    grey row added to `ROWS` later turns this red until somebody decides
    whether the grey report should show it.
    """
    from workflow.compliance_sets import ROWS
    got = set(rows_for_report_type(REPORT_TYPE_GREY))
    grey_group = {r.id for r in ROWS if r.group == "grey_ramp"}
    assert grey_group, "the grey_ramp group vanished from ROWS"
    assert grey_group <= got, f"missing from the grey report: {grey_group - got}"
    assert "ramps_30_70_dl_max" in got, "the tone half of Grey and tone is gone"
    assert got == grey_group | {"ramps_30_70_dl_max"}, (
        f"unexplained extras: {got - grey_group - {'ramps_30_70_dl_max'}}")
    known = {r.id for r in ROWS}
    assert got <= known, f"not rows at all: {got - known}"


def test_only_the_grey_and_tone_rows_are_in_it(tmp_path, qapp):
    """MUTATION: make `_keep_rows_for_type` return its rows untouched and this
    goes red."""
    dlg, run = _dialog(tmp_path, qapp)
    try:
        full = set(_ids(dlg, _as(dlg, run, REPORT_TYPE_FULL)))
        grey = _ids(dlg, _as(dlg, run, REPORT_TYPE_GREY))
        wanted = set(rows_for_report_type(REPORT_TYPE_GREY))
        assert set(grey) <= wanted, f"not about grey: {set(grey) - wanted}"
        assert set(grey), "every row was dropped"
        assert full - wanted, "this chart has no colour rows, so nothing is proved"
        assert not (set(grey) & (full - wanted))
    finally:
        dlg.close()


def test_the_colour_rows_are_GONE_not_marked_not_applicable(tmp_path, qapp):
    """The difference a reader sees: a row that is absent says "not this
    report"; a row reading N-A says "we could not measure it".

    MUTATION: keep the colour rows and blank their words instead, and this
    goes red.
    """
    import html as _html
    from workflow.compliance_sets import ROW_BY_ID
    dlg, run = _dialog(tmp_path, qapp)
    try:
        full = _ids(dlg, _as(dlg, run, REPORT_TYPE_FULL))
        dropped = [r for r in full
                   if r not in set(rows_for_report_type(REPORT_TYPE_GREY))]
        assert dropped
        body = dlg._report_body_html(_as(dlg, run, REPORT_TYPE_GREY),
                                     for_pdf=True)
        for rid in dropped:
            row = ROW_BY_ID.get(rid)
            if row is None:
                continue
            assert _html.escape(row.label) not in body, \
                f"{rid} is still listed in a report that is not about it"
    finally:
        dlg.close()


def test_the_column_word_is_about_the_rows_it_SHOWS(tmp_path, qapp):
    """A Grey and tone check must not read FAIL because of a colour row it
    never mentions.

    MUTATION: filter only the results table and leave `_verdict_rows` whole,
    and this goes red.
    """
    dlg, run = _dialog(tmp_path, qapp)
    try:
        full = _as(dlg, run, REPORT_TYPE_FULL)
        f_sum = dlg._column_summary(full[0])
        grey = _as(dlg, run, REPORT_TYPE_GREY)
        g_sum = dlg._column_summary(grey[0])
        assert g_sum.total == len(rows_for_report_type(REPORT_TYPE_GREY)) \
            or g_sum.total < f_sum.total, (f_sum.total, g_sum.total)
        assert g_sum.total < f_sum.total
    finally:
        dlg.close()


def test_a_grey_check_on_a_chart_with_no_grey_ramp_says_so(tmp_path, qapp):
    """THE COMMONEST CASE, and it is where the false PASS was found. Most
    verification charts have no 8-step grey ramp, so both of T3's rows read
    N-A, nothing at all is checked, and the column used to summarise PASS under
    a sentence claiming every required value had been checked.

    MUTATION: drop the `checked == 0` clause in `set_summary` and this goes
    red.
    """
    dlg, run = _dialog(tmp_path, qapp)
    try:
        grey = _as(dlg, run, REPORT_TYPE_GREY)
        rows = dlg._verdict_rows(grey[0])[0]
        assert rows and all(x["word"] == N_A for x in rows), \
            "this chart does supply a grey ramp, so this case is not exercised"
        sm = dlg._column_summary(grey[0])
        assert sm.word == N_A, f"{sm.word} on a report where nothing was checked"
        assert sm.reason == SUMMARY_REASONS["nothing_checked"]
    finally:
        dlg.close()


def test_the_report_says_which_document_it_is(tmp_path, qapp):
    """A two page document about the neutral axis, handed to a reader with no
    line saying so, is indistinguishable from a full report that lost most of
    its rows."""
    import html as _html
    dlg, run = _dialog(tmp_path, qapp)
    try:
        for for_pdf in (False, True):
            body = dlg._report_body_html(_as(dlg, run, REPORT_TYPE_GREY),
                                         for_pdf=for_pdf)
            assert _html.escape(tr_name()) in body, \
                f"for_pdf={for_pdf}: the report does not name its own type"
    finally:
        dlg.close()


def tr_name() -> str:
    from core.i18n import tr
    from workflow.measurement_report import report_type_name
    return tr(report_type_name(REPORT_TYPE_GREY))
