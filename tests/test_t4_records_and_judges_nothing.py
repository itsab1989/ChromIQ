"""T4, "Printing record (not graded)": the same numbers, no verdict.

#182 W-A, report type 4 (issue section 19). Knut's brief: *"a raw or profiling
sheet, every row INFO"*, *"no, by design"* to the question of whether it can
print PASS.

Three things have to be true at once, and each was a way to get this wrong.

**The numbers are the measured ones.** T4 withholds the judgement, not the
measurement. A document that also changed the figures would be a different
measurement, not a different report.

**Nothing is written.** A saved report keeps its recorded verdicts on disk;
choosing T4 decides what is drawn from them. Switch back to Full colour check
and the same words come back, in the same report file.

**The explanation is in the OUTPUT.** Knut allowed INFO only on that condition,
and twice on this project an explanation reached a `title=` tooltip that no PDF
page carries. It has to be in the rendered text.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.compliance_sets import (INFO, N_A, SUMMARY_REASONS,  # noqa: E402
                                      is_ungraded_reason)
from workflow.measurement_report import (REPORT_TYPE_FULL,  # noqa: E402
                                         REPORT_TYPE_RECORD,
                                         report_type_is_built)


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


def test_t4_is_offered_as_something_chromiq_can_produce():
    assert report_type_is_built(REPORT_TYPE_RECORD)


def test_every_row_that_was_judged_reads_INFO(tmp_path, qapp):
    """MUTATION: make `_ungrade` return its rows untouched and this goes red."""
    dlg, run = _dialog(tmp_path, qapp)
    try:
        graded = _as(dlg, run, REPORT_TYPE_FULL)
        words_before = [w["word"] for w in dlg._verdict_rows(graded[0])[0]]
        assert any(w not in (INFO, N_A) for w in words_before), \
            "this measurement is not judged at all, so it proves nothing here"

        rec = _as(dlg, run, REPORT_TYPE_RECORD)
        rows = dlg._verdict_rows(rec[0])[0]
        assert rows, "no rows at all"
        for row in rows:
            assert row["word"] in (INFO, N_A), (row.get("row_id"), row["word"])
    finally:
        dlg.close()


def test_a_row_nobody_could_measure_keeps_N_A(tmp_path, qapp):
    """"We could not measure this" is not a judgement being withheld, and
    turning it into INFO would claim a number exists.

    MUTATION: ungrade every row unconditionally and this goes red.
    """
    dlg, run = _dialog(tmp_path, qapp)
    try:
        full = _as(dlg, run, REPORT_TYPE_FULL)
        na = {r["row_id"] for r in dlg._verdict_rows(full[0])[0]
              if r["word"] == N_A}
        assert na, "every row was computed, so this proves nothing"
        rec = _as(dlg, run, REPORT_TYPE_RECORD)
        still = {r["row_id"] for r in dlg._verdict_rows(rec[0])[0]
                 if r["word"] == N_A}
        assert still == na, f"lost: {na - still}"
    finally:
        dlg.close()


def test_the_numbers_are_the_measured_ones(tmp_path, qapp):
    """T4 withholds the verdict, never the measurement.

    MUTATION: change any figure on the T4 path and this goes red.
    """
    dlg, run = _dialog(tmp_path, qapp)
    try:
        full = _as(dlg, run, REPORT_TYPE_FULL)
        before = {k: v for k, v in full[0].items()
                  if k in ("de00", "white", "black", "grey_balance",
                           "ramps_30_70")}
        rec = _as(dlg, run, REPORT_TYPE_RECORD)
        after = {k: v for k, v in rec[0].items() if k in before}
        assert after == before
    finally:
        dlg.close()


def test_the_column_word_is_INFO_and_says_why_in_its_own_words(tmp_path, qapp):
    """The 12b sentence says the sheet "was measured to build a profile". On a
    verification measurement a user deliberately chose to record, that is
    false, so T4 has a reason of its own.

    MUTATION: reuse SUMMARY_REASONS["not_graded"] and this goes red.
    """
    dlg, run = _dialog(tmp_path, qapp)
    try:
        rec = _as(dlg, run, REPORT_TYPE_RECORD)
        sm = dlg._column_summary(rec[0])
        assert sm.word == INFO, sm.word
        assert sm.reason == SUMMARY_REASONS["record_type"], sm.reason
        assert "build a profile" not in sm.reason
        assert is_ungraded_reason(sm.reason)
    finally:
        dlg.close()


def test_a_saved_PASS_does_not_survive_into_the_record(tmp_path, qapp):
    """THE EARLY RETURN. A saved report carries its own overall word, and the
    fast path handed it straight back, so a document whose whole point is that
    nothing is judged would have printed a green PASS at the head of its own
    column.

    MUTATION: drop `and not self._ungraded_by_type()` from that early return
    and this goes red.
    """
    from workflow.compliance_sets import PASS
    dlg, run = _dialog(tmp_path, qapp)
    try:
        # The saved verdict is built from the report's OWN judged rows, so the
        # limits it is read against are the run's real ones. A hand-written
        # row with no limit behind it answers N-A for a reason that has
        # nothing to do with T4, and would have passed this test while proving
        # nothing.
        full = _as(dlg, run, REPORT_TYPE_FULL)
        rows, _ = dlg._verdict_rows(full[0])
        saved = [dict(x, word=PASS, **{"pass": True}) for x in rows
                 if x["word"] != N_A]
        assert saved, "nothing was judged, so a saved PASS cannot be staged"
        r = dict(full[0])
        r["verdict"] = {"rows": saved, "overall": PASS, "graded": True,
                        "summary": {"checked": len(saved), "total": len(saved),
                                    "failed": 0, "cond": 0, "not_computed": 0,
                                    "reason": SUMMARY_REASONS["pass"]}}
        assert dlg._column_summary(r).word == PASS, \
            "the staged PASS is not even read in Full colour check"

        _as(dlg, run, REPORT_TYPE_RECORD)
        assert dlg._column_summary(r).word == INFO, \
            "a saved PASS was printed on a report that judges nothing"
    finally:
        dlg.close()


def test_the_explanation_is_in_the_rendered_text_not_a_tooltip(tmp_path, qapp):
    """Knut allowed INFO on condition the report OUTPUT explains it, and twice
    on this project an explanation reached only a `title=` attribute, which no
    PDF page carries. Checked on the PDF body, which is the harder of the two.

    MUTATION: drop `record_type` from `is_ungraded_reason` and this goes red,
    because the footnote is chosen by exact equality on the sentence.
    """
    import html as _html
    dlg, run = _dialog(tmp_path, qapp)
    try:
        rec = _as(dlg, run, REPORT_TYPE_RECORD)
        import re
        needle = _html.escape(SUMMARY_REASONS["record_type"].split(".")[0])
        for for_pdf in (False, True):
            body = dlg._report_body_html(rec, for_pdf=for_pdf)
            places = [m.start() for m in re.finditer(re.escape(needle), body)]
            assert places, f"for_pdf={for_pdf}: the reason is nowhere at all"
            # THE SENTENCE APPEARS TWICE and one of them is a tooltip: the
            # Overall cell's `title=`. Checking the FIRST occurrence found that
            # one and called the whole thing a tooltip. What matters is that at
            # least one is rendered text, so the rule is written that way.
            rendered = [i for i in places
                        if not re.search(r"title='[^']*$", body[:i])]
            assert rendered, (
                f"for_pdf={for_pdf}: every copy of the explanation is inside a "
                f"title= attribute, which no PDF page carries")
    finally:
        dlg.close()


def test_nothing_on_disk_moved_and_the_words_come_back(tmp_path, qapp):
    """T4 is a way of DRAWING a report, not of changing one.

    MUTATION: write the ungraded words back into the report and this goes red.
    """
    import json
    dlg, run = _dialog(tmp_path, qapp)
    try:
        full = _as(dlg, run, REPORT_TYPE_FULL)
        before_words = [w["word"] for w in dlg._verdict_rows(full[0])[0]]
        on_disk = sorted((run.dir / "reports").rglob("*.json")) \
            if (run.dir / "reports").exists() else []
        snap = {p: p.read_text(encoding="utf-8") for p in on_disk}

        _as(dlg, run, REPORT_TYPE_RECORD)
        dlg._report_body_html(dlg._runs_for_report(), for_pdf=False)

        again = _as(dlg, run, REPORT_TYPE_FULL)
        assert [w["word"] for w in dlg._verdict_rows(again[0])[0]] == before_words
        for p, text in snap.items():
            assert p.read_text(encoding="utf-8") == text, f"{p.name} was rewritten"
            json.loads(text)
    finally:
        dlg.close()
