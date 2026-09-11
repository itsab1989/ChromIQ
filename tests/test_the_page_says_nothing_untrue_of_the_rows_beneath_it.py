"""Every sentence on the report page has to be true of the rows under it.

A fifth adversarial round read the page against the rows and found four places
where it was not, all of them in text written or rewritten by the four rounds
before it. Each is a sentence that survived because nobody had read it beside
the thing it describes.

The recurring shape, for the fifth time: **a guard on one door and not on the
identical door beside it.** One note was made silent on a type that judges
nothing; the note immediately above it in the same function, and the strip
above the whole report, were not.
"""
from __future__ import annotations

import html as _html
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.compliance_sets import INFO  # noqa: E402
from workflow.measurement_report import (REPORT_TYPE_FULL,  # noqa: E402
                                         REPORT_TYPE_RECORD)


def _grey_ramp_ti3() -> str:
    from tests.test_a_saved_report_does_not_leak_its_verdict_into_another_type import (
        _grey_ramp_ti3 as g)
    return g()


def _dialog(tmp_path, qapp, ti3_text=None):
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(ti3_text or _cgats("CTI3", _PATCHES),
                                 encoding="utf-8")
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


def test_a_type_that_judges_nothing_does_not_tell_you_what_to_add(tmp_path,
                                                                  qapp):
    """On a Printing record a chart with no grey ramp printed, on one page:
    "You chose the Printing record, which judges none of it", and under it
    "Not computed on this chart: … add the missing patches to the chart in
    Create Chart to have it checked." Under a type that checks nothing.

    MUTATION: drop the `_ungraded_by_type` guard from the not-computed note
    and this goes red.
    """
    from core.i18n import tr
    dlg, run = _dialog(tmp_path, qapp)
    try:
        full = _as(dlg, run, REPORT_TYPE_FULL)
        body = dlg._report_body_html(full, for_pdf=True)
        head = _html.escape(tr("Not computed on this chart:"))
        assert head in body, "this chart computes everything, so nothing is proved"

        rec = _as(dlg, run, REPORT_TYPE_RECORD)
        body = dlg._report_body_html(rec, for_pdf=True)
        assert head not in body, (
            "a report that judges nothing told the reader what to add to have "
            "it checked")
        assert "Create Chart" not in body
    finally:
        dlg.close()


def test_the_strip_is_silent_on_a_type_that_applies_no_limit_set(tmp_path,
                                                                 qapp):
    """The amber strip names the limit set and says what to add to the chart.
    On a Printing record no set is applied and nothing is checked, so every
    clause of it is about a document the user is not looking at.

    MUTATION: drop the `_ungraded_by_type` check from `_mismatch_text` and
    this goes red.
    """
    dlg, run = _dialog(tmp_path, qapp)
    try:
        _as(dlg, run, REPORT_TYPE_FULL)
        assert dlg._mismatch_text(), \
            "this chart supplies every row, so the strip proves nothing"
        _as(dlg, run, REPORT_TYPE_RECORD)
        assert not dlg._mismatch_text(), \
            "the strip names a limit set on a report that applies none"
        assert not dlg._mismatch.isVisible()
    finally:
        dlg.close()


def test_a_loose_measurement_keeps_its_own_verdict_in_company(tmp_path, qapp):
    """A run on the Printing record beside a measurement in no project, whose
    own saved report says Full colour check: the window saw no disagreement,
    because it only collected a type from sources that HAVE a run, and applied
    the run's type to both. Opened alone that file reads FAIL; in company it
    read INFO, every verdict withheld by a choice made on a different run.

    MUTATION: collect a type only from sources with a run context and this
    goes red.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.compliance_sets import N_A
    dlg, run = _dialog(tmp_path, qapp)
    try:
        loose = tmp_path / "downloads" / "loose.ti3"
        loose.parent.mkdir(parents=True, exist_ok=True)
        loose.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
        _as(dlg, run, REPORT_TYPE_RECORD)
        dlg._add_source(loose)
        dlg._refresh()
        qapp.processEvents()
        reps = dlg._runs_for_report()
        assert len(reps) == 2, f"{len(reps)} columns"
        assert len(dlg._types_of_loaded_runs()) > 1, \
            "the loose file's own type is still invisible to the fallback"
        assert dlg._report_type_now() == REPORT_TYPE_FULL
        for r in reps:
            rows, _rc = dlg._verdict_rows(r)
            assert any(x["word"] not in (INFO, N_A) for x in rows), \
                "a column was withheld by a choice its own file never made"
    finally:
        dlg.close()


def test_the_legend_promises_a_note_only_where_there_is_one(tmp_path, qapp):
    """The legend gained a fourth cause of INFO and the promise "the note under
    the results says which". A row that is INFO because the SET PUTS NO LIMIT
    on it carries no reason and is in no note, so the promise was false for the
    first cause it lists. It is scoped to the two cases the note covers now.

    MUTATION: promise the note for every cause and this goes red.
    """
    from core.i18n import tr
    dlg, run = _dialog(tmp_path, qapp, _grey_ramp_ti3())
    try:
        reps = _as(dlg, run, REPORT_TYPE_FULL)
        rows, _rc = dlg._verdict_rows(reps[0])
        unlimited = [x for x in rows
                     if x["word"] == INFO and not x.get("reason")]
        assert unlimited, "no unlimited INFO row here, so nothing is proved"
        listed = {lbl for lbl, _w in dlg._measured_not_graded(reps[0])}
        from workflow.compliance_sets import ROW_BY_ID
        for x in unlimited:
            rid = x.get("row_id")
            if rid in ROW_BY_ID:
                assert tr(ROW_BY_ID[rid].label) not in listed, (
                    f"{rid} has no limit and no reason; naming it in a note "
                    f"about ungraded rows would invent one")
        body = dlg._report_body_html(reps, for_pdf=True)
        assert _html.escape(tr("the note under the results names the rows in "
                               "the last two cases")) in body or \
            "last two cases" in body, \
            "the legend promises a note for every cause again"
    finally:
        dlg.close()


def test_the_legend_does_not_blame_drift_for_a_word_drift_never_shows(tmp_path,
                                                                      qapp):
    """A drift column prints the word "drift" in every cell, and never INFO.
    The legend listed a raw drift check among the causes of INFO, so page 2
    attributed a word to a state that produces a different one.

    MUTATION: put "raw drift check" back among the causes of INFO and this
    goes red.
    """
    from core.i18n import tr
    dlg, run = _dialog(tmp_path, qapp)
    try:
        body = dlg._report_body_html(_as(dlg, run, REPORT_TYPE_FULL),
                                     for_pdf=True)
        i = body.find(_html.escape("INFO: the number is shown"))
        assert i >= 0, "the legend no longer describes INFO at all"
        clause = body[i:i + 700]
        assert "drift check, which" not in clause, \
            "a drift check is named as a cause of INFO again"
        assert _html.escape(tr("drift")) in body, \
            "the page no longer says what a drift column shows instead"
    finally:
        dlg.close()
