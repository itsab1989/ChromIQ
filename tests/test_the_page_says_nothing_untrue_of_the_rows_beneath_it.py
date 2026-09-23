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

import pytest

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
    # K31: the type is the REPORT's, chosen in the pulldown as a user does.
    from tests.helpers.report_window import choose_report_type
    choose_report_type(dlg, tid)
    dlg._forget_limits()
    dlg._sync_limit_controls()
    return dlg._runs_for_report()


def test_a_type_that_judges_nothing_does_not_tell_you_what_to_add(tmp_path,
                                                                  qapp):
    """On a Printing record a chart with no grey ramp printed, on one page:
    "You chose the Printing record, which judges none of it", and under it
    "Not computed on this chart: … add the missing patches to the chart in
    Create Chart to have it checked." Under a type that checks nothing.

    **THE NOTE IT WAS WRITTEN FOR IS GONE, and the rule outlived it.** That
    block was removed on 2026-09-21: Knut ruled that an N-A cell carries a
    raised number pointing at a note instead, so the explanation is now an
    item in the numbered list. The thing this test guards is unchanged, and
    it is retargeted rather than deleted: whatever explains an unanswerable
    row must stay silent on a type that answers nothing.

    **AND SINCE G12 (beta 39) THAT IS NARROWER.** A note explaining an N-A is
    printed on the Printing record now (Knut, 2026-09-22: "so a user knows why
    a metric could not be checked"), under "Notes on the values above:". So
    on T4 a note may only sit on an N-A row; the ones commenting a verdict
    (the grey rows' printing note on the Full colour check) must stay off.

    MUTATION (re-proved 2026-09-23): in `_notes_list_html` replace
    `record = self._ungraded_by_type()` with `record = False` and this goes
    red: the record's list is headed as notes on verdicts. (Its first
    mutation, the `_ungraded_by_type` guard at the top of
    `_note_the_absences`, is the guard G12 removed.)
    """
    from core.i18n import tr
    dlg, run = _dialog(tmp_path, qapp)
    try:
        full = _as(dlg, run, REPORT_TYPE_FULL)
        body = dlg._report_body_html(full, for_pdf=True)
        head = _html.escape(tr("Notes on the verdicts above:"))
        assert head in body, "this chart computes everything, so nothing is proved"
        assert dlg._numbered_notes(full), "and the list really has items in it"

        rec = _as(dlg, run, REPORT_TYPE_RECORD)
        body = dlg._report_body_html(rec, for_pdf=True)
        assert head not in body, (
            "a report that judges nothing told the reader what to add to have "
            "it checked")
        # only notes that explain an absence, each on an N-A row (G12)
        from workflow.compliance_sets import N_A
        rows, _rc = dlg._verdict_rows(rec[0])
        assert all(x["word"] == N_A for x in rows if x.get("notes")), \
            "a note comments a verdict on a report that gives none"
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


# RETIRED BY K31 (beta 40): `test_a_loose_measurement_keeps_its_own_verdict_in_company`.
# It pinned the fallback that showed a report as Full colour check when the
# loaded runs had been set to different report types. Since K31 a run carries
# no report type: the type is the report's, chosen once for the whole report,
# so there is no disagreement left to fall back from (_types_of_loaded_runs
# is gone).


def test_the_legend_promises_a_note_only_where_there_is_one(tmp_path, qapp):
    """The legend gained a fourth cause of INFO and the promise "the note under
    the results says which". A row that is INFO because the SET PUTS NO LIMIT
    on it carries no reason and is in no note, so the promise was false for the
    first cause it lists.

    K28 (item 3) removed that cause: a row whose limit is "–" is no longer in
    the document at all, so there is no unlimited INFO row left to promise
    anything about, and the bullet names the one case its note covers.

    MUTATION: put "when this limit set puts no limit on the row" back among
    the causes, or stop `_drop_dash_rows` dropping, and this goes red.
    """
    from core.i18n import tr
    dlg, run = _dialog(tmp_path, qapp, _grey_ramp_ti3())
    try:
        reps = _as(dlg, run, REPORT_TYPE_FULL)
        rows, _rc = dlg._verdict_rows(reps[0])
        unlimited = [x for x in rows
                     if x["word"] == INFO and not x.get("reason")]
        assert not unlimited, [x["row_id"] for x in unlimited]
        body = dlg._report_body_html(reps, for_pdf=True)
        assert "puts no limit on the row" not in body
        assert _html.escape(tr("the note under the results names the rows in "
                               "that last case")) in body or \
            "that last case" in body, \
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


@pytest.fixture(autouse=True)
def _every_type_as_for_a_measurement_in_no_run(monkeypatch):
    """**K13 (Knut, beta 34) made the Printing record a profiling-only type**,
    and these checks drive every type on a VERIFICATION fixture, where T4
    would now fall back to T2 and each check would be asked of the fallback.
    What they test is how each type RENDERS, which is still reachable: a saved
    beta-34 Printing record of a verification is shown as recorded, and a
    measurement outside any project keeps every type. So the window is told
    it has no kind. K13's own rule is guarded in
    `tests/test_the_report_type_pulldown_stores_on_the_run.py`.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    monkeypatch.setattr(MeasurementReportDialog, "_window_kind",
                        lambda self: None)
