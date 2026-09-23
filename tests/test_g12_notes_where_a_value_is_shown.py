"""G12 (#182, beta 39): notes wherever a verdict is shown, and the Printing
record's detailed sections.

Knut, 2026-09-22 (5774852534): *"what happens in the Report type "Printing
Record" when "Show detailed..." checkmark is ON. The sections with detailed
data still shows PASS and FAIL, or if a metric could not be checked. Should
there be a note there instead, so a user knows why a metric could not be
checked?"* We proposed *"notes wherever a verdict is shown, suppressed where
none is"* (5774887435) and he answered *"OK"* (5775260868).

So, as built (spec §12 CH-31a, awaiting confirmation):

* the Printing record's detailed table carries no verdict word and no Result
  column; a row that could not be worked out reads "—" with a numbered note;
* its N-A rows carry the notes that explain an absence, under a heading and a
  closing sentence that say nothing about verdicts or failures;
* a note that COMMENTS a verdict stays off the record;
* on every type, the detailed table carries the same note numbers as the
  Report Results grid, and lists the notes it points at under itself.

Each test names the mutation it was proved red against.
"""
from __future__ import annotations

from tests.helpers import legacy_run_meta
import html as _html
import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_beta37_round_fixes import (_settings,          # noqa: E402
                                           _stamped_profiling_run)

_WORDS = ("PASS", "FAIL", "COND", "INFO", "N-A")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ",
                                                     fragment)))


def _record_dialog(tmp_path):
    """A profiling sheet on the Printing record, detail ON. The sheet has no
    repeat patches, no earlier measurement and no chart layout, so four rows
    read N-A and each carries a reason."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow import measurement_report as mr
    _run, ti3 = _stamped_profiling_run(tmp_path, "chromiq_default",
                                       "ChromIQ default (recommended)")
    dlg = MeasurementReportDialog(_settings(tmp_path), None, initial_ti3=ti3)
    assert dlg._report_type_now() == mr.REPORT_TYPE_RECORD
    dlg._detail_check.setChecked(True)
    return dlg


def _detail_part(body: str) -> str:
    from core.i18n import tr
    k = body.find(_html.escape(tr("Detailed data per measurement run")))
    assert k >= 0, "the detailed section is not in the document"
    return body[k:]


def _colour_table(detail: str) -> str:
    """The first run's "Colour accuracy" table and what follows it up to the
    paper-white heading."""
    from core.i18n import tr
    end = detail.find(_html.escape(tr("Paper white and darkest black (L*)")))
    return detail[:end if end > 0 else len(detail)]


def test_the_printing_records_detailed_table_gives_no_verdict_word(tmp_path,
                                                                   qapp):
    """No PASS, FAIL, COND, INFO or N-A, and no Result column, in the detailed
    table of a document that judges nothing. The absent value reads "—" with
    the raised number of its note.

    MUTATION (proved red 2026-09-23): in `_run_detail_html` replace
    `record = self._ungraded_by_type()` with `record = False`; the Result
    column comes back holding INFO and N-A."""
    from core.i18n import tr
    dlg = _record_dialog(tmp_path)
    try:
        body = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
        table = _text(_colour_table(_detail_part(body)))
        assert tr("Metric") in table, "the detailed table is not there"
        for w in _WORDS:
            assert not re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", table), (
                f"the Printing record's detailed table says {w}")
        assert tr("Result") not in table.split(tr("Notes on the values above:"))[0]
        # the absent value carries its marker: "— 1)"
        assert re.search(r"— 1\)", table), table[:600]
    finally:
        dlg.deleteLater()


def test_a_printing_record_explains_every_absence_with_a_note(tmp_path, qapp):
    """Every N-A row of the record carries a numbered note naming why, in the
    Results grid and under the detailed table, under a heading about values,
    and the closing sentence says nothing about failures.

    MUTATION (proved red 2026-09-23): put `if self._ungraded_by_type():
    return rows` back at the top of `_note_the_absences`; the markers and both
    lists are gone."""
    from core.i18n import tr
    from workflow.compliance_sets import N_A
    dlg = _record_dialog(tmp_path)
    try:
        reps = dlg._runs_for_report()
        rows, _rec = dlg._verdict_rows(reps[0])
        absent = [x for x in rows if x.get("word") == N_A]
        assert absent, "no N-A row on this sheet, so nothing is exercised"
        for x in absent:
            assert x.get("notes"), f"{x['row_id']} reads N-A and carries no note"
        body = dlg._report_body_html(reps, for_pdf=True)
        text = _text(body)
        head = tr("Notes on the values above:")
        assert text.count(head) == 2, (
            "one list under the Results grid and one under the detailed table")
        for x in absent:
            said = dlg._reason_sentence(x.get("reason"), reps[0], x)
            assert said and text.count(said) == 2, (x["row_id"], said)
        assert tr("Notes on the verdicts above:") not in text
        assert tr("A row that could not be worked out says nothing about"
                  " the printer and is not counted as a failure;"
                  " each note above says why.") not in text
        assert tr("A value that could not be worked out says nothing about "
                  "the printer; each note above says why.") in text
    finally:
        dlg.deleteLater()


def test_the_record_heading_is_about_values_not_verdicts(tmp_path, qapp):
    """The list heading is chosen per type, in one renderer.

    MUTATION (proved red 2026-09-23): in `_notes_list_html` replace
    `record = self._ungraded_by_type()` with `record = False`; the record's
    lists read "Notes on the verdicts above:"."""
    from core.i18n import tr
    dlg = _record_dialog(tmp_path)
    try:
        out = dlg._notes_list_html([(1, "Row", "a sentence")], "", closing=True)
        assert tr("Notes on the values above:") in _text(out)
        assert "failure" not in out
    finally:
        dlg.deleteLater()


@pytest.fixture
def _no_kind(monkeypatch):
    """K13 made the record a profiling-only type; the verdict-comment note is
    exercised on a verification sheet, as in
    `test_a_saved_report_does_not_leak_its_verdict_into_another_type`."""
    from ui.dialogs import measurement_report_dialog as mrd
    monkeypatch.setattr(mrd.MeasurementReportDialog, "_window_kind",
                        lambda self: None)
    monkeypatch.setattr(mrd.MeasurementReportDialog, "_bar_kind",
                        lambda self: (False, None))


def test_the_record_prints_no_note_that_comments_a_verdict(tmp_path, qapp,
                                                           _no_kind):
    """A note that comments a verdict (here the grey rows' printing note)
    lives and dies with the verdict: on the record only the notes that
    explain an absence are left, each on an N-A row.

    MUTATION (proved red 2026-09-23): delete `row["notes"] = []` from
    `_ungrade`; the grey note reaches the record."""
    from tests.test_a_saved_report_does_not_leak_its_verdict_into_another_type \
        import _grey_ramp_ti3
    from tests.test_import_measurement_module import _verify_env
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.compliance_sets import N_A
    from workflow.measurement_report import (NOTE_PRINTING_UNRECORDED,
                                             REPORT_TYPE_FULL,
                                             REPORT_TYPE_RECORD)
    from tests.helpers.report_window import choose_report_type
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_grey_ramp_ti3(), encoding="utf-8")
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    try:
        choose_report_type(dlg, REPORT_TYPE_FULL)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        full = [c for (_n, c, _r) in dlg._note_numbering(dlg._runs_for_report())]
        assert NOTE_PRINTING_UNRECORDED in full, (
            "the comment note is not there on the graded type, so nothing is "
            "proved")
        choose_report_type(dlg, REPORT_TYPE_RECORD)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        reps = dlg._runs_for_report()
        rows, _rec = dlg._verdict_rows(reps[0])
        for x in rows:
            if x.get("notes"):
                assert x["word"] == N_A, (
                    f"{x['row_id']} reads {x['word']} on the record and "
                    "carries a note")
        codes = [c for (_n, c, _r) in dlg._note_numbering(reps)]
        assert NOTE_PRINTING_UNRECORDED not in codes
    finally:
        dlg.close()


def _graded_dialog(tmp_path):
    from tests.test_report_window_limit_controls import _verified_run
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import REPORT_TYPE_FULL
    from workflow import run_compliance as rc  # noqa: F401
    from tests.helpers.report_window import choose_report_type
    _proj, run, ti3s = _verified_run(tmp_path, dates=2)
    dlg = MeasurementReportDialog(_settings(tmp_path), None,
                                  initial_ti3=ti3s[-1])
    choose_report_type(dlg, REPORT_TYPE_FULL)
    dlg._forget_limits()
    dlg._sync_limit_controls()
    dlg._refresh()
    dlg._detail_check.setChecked(True)
    return dlg


def _markers_by_row(fragment: str, labels: dict) -> dict:
    """{row label: "1) 2)"} read off a rendered table fragment."""
    out = {}
    for rid, label in labels.items():
        m = re.search(re.escape(_html.escape(label))
                      + r"</td>.*?</tr>", fragment, flags=re.S)
        if not m:
            continue
        sup = re.findall(r"<sup[^>]*>&nbsp;([^<]*)</sup>", m.group(0))
        out[rid] = " ".join(sup)
    return out


def test_a_graded_detailed_table_carries_the_documents_note_numbers(tmp_path,
                                                                    qapp):
    """Notes wherever a verdict is shown: the Result cell of the detailed table
    carries the SAME marker the Report Results grid gives the row, and the
    notes it points at are listed under the table.

    MUTATION (proved red 2026-09-23): in `_run_detail_html` pass `mark=""`
    instead of `mark=mark_for(row)`; the detailed markers and the list under
    the table are gone."""
    from core.i18n import tr
    from workflow.compliance_sets import ROW_BY_ID
    dlg = _graded_dialog(tmp_path)
    try:
        reps = dlg._runs_for_report()
        nums = dlg._note_numbering(reps)
        assert nums, "no note on this document, so nothing is proved"
        body = dlg._report_body_html(reps, for_pdf=True)
        detail = _detail_part(body)
        results = body[:body.find(_html.escape(
            tr("Detailed data per measurement run")))]
        noted = {rid for (_n, _c, rids) in nums for rid in rids}
        labels = {rid: tr(ROW_BY_ID[rid].label) for rid in noted
                  if rid in ROW_BY_ID}
        in_detail = _markers_by_row(_colour_table(detail), labels)
        assert in_detail and any(in_detail.values()), (
            "no marker in the detailed table")
        in_grid = _markers_by_row(results, labels)
        for rid, marks in in_detail.items():
            if marks:
                assert marks in in_grid.get(rid, ""), (rid, marks, in_grid)
        table = _text(_colour_table(detail))
        assert tr("Notes on the verdicts above:") in table
    finally:
        dlg.deleteLater()


def test_the_record_does_not_say_the_result_judges_the_gamut(tmp_path, qapp):
    """The gamut paragraph under the detailed table said "The Result judges the
    within-gamut figures"; the record has no Result column.

    MUTATION (proved red 2026-09-23): change `if split and record:` to
    `if False:` in `_run_detail_html`."""
    dlg = _record_dialog(tmp_path)
    try:
        r = dict(dlg._runs_for_report()[0])
        de = r.get("de00") or {}
        r["gamut_split"] = {"n_in": 30, "n_out": 10, "profile": "P.icc",
                            "de00_in": dict(de), "de00_out": dict(de)}
        text = _text(dlg._run_detail_html(r))
        assert "Within what the profile (P.icc) can print" in text
        assert "The Result judges" not in text
    finally:
        dlg.deleteLater()
