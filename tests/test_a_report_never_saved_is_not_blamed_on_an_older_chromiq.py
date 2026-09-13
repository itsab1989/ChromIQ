"""A report built live must not be described as one an old ChromIQ mangled.

Knut, 2026-09-13, reading the report window on
`Report-Limits-Custom-Columns`::

    The statemend "It was saved by a version of ChromIQ that did not yet keep
    the verdict together with the measurements, so no PASS or FAIL of its own
    was stored for it." seems wrong.

It was. The sheet he opened is the run's OWN profiling measurement, and
ChromIQ saves a report under a dated verification, not under the sheet a
profile was built from — so `_load_runs` fell through to its last resort,
which builds the report there and then. That branch was the only one of the
three that did not set `_fresh`, and `_recorded(r) is None and not
r.get("_fresh")` is exactly the state the window reads as "saved by an older
ChromIQ, verdict lost". Nothing had been saved, so nothing could have been
lost: the window invented a history for a file that has none, and told the
reader their data was damaged.

The two sentences are the whole point of the file: one is about a report that
EXISTS on disk without a verdict, the other about a report that does not exist
at all, and only one of them may ever be printed for a given column.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: The clause that may only be said of a report actually found on disk.
BLAMES_AN_OLD_VERSION = "did not yet keep the verdict together with the"


def _run_with_no_saved_report(tmp_path, qapp):
    """A run whose own measurement is on disk with no report beside it, which
    is what every project has until a measurement is made with "Save a
    measurement report after each measurement" ticked."""
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, _ctl, run = _verify_env(tmp_path)
    ti3 = run.dir / f"{run.stem}.ti3"
    ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    assert not list(run.reports_dir.glob("report_*.json")) \
        if run.reports_dir.is_dir() else True
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    return dlg, run, ti3


def test_the_column_is_marked_fresh(tmp_path, qapp):
    """MUTATION: drop the `_fresh = True` from `_load_runs`'s last resort and
    this goes red, which is the state that shipped in beta 8."""
    dlg, _run, _ti3 = _run_with_no_saved_report(tmp_path, qapp)
    try:
        reps = dlg._runs_for_report()
        assert reps, "the window found no column at all"
        assert reps[0].get("_fresh") is True, (
            "a report built live is not marked _fresh, so the window reads it "
            "as one an older ChromIQ saved and stripped the verdict from")
        assert dlg._recorded(reps[0]) is None, (
            "this fixture is meant to have NO saved verdict; if it has one the "
            "test below proves nothing")
    finally:
        dlg.close()


def test_the_page_does_not_say_an_old_version_lost_the_verdict(tmp_path, qapp):
    """The sentence Knut quoted, searched for in the document the window draws
    and in the PDF, because they are two renderers and he read the first."""
    dlg, _run, _ti3 = _run_with_no_saved_report(tmp_path, qapp)
    try:
        reps = dlg._runs_for_report()
        for for_pdf in (False, True):
            body = dlg._report_body_html(reps, for_pdf=for_pdf)
            assert BLAMES_AN_OLD_VERSION not in body, (
                f"{'the PDF' if for_pdf else 'the window'} blames an older "
                f"ChromIQ for a report that was never saved by any version")
    finally:
        dlg.close()


def test_the_judged_against_cell_does_not_read_not_recorded(tmp_path, qapp):
    """"Judged against: not recorded" is the same claim in the Report Results
    table: it says a record was looked for and found empty. These words were
    worked out just now, against a set the window can name."""
    dlg, _run, _ti3 = _run_with_no_saved_report(tmp_path, qapp)
    try:
        reps = dlg._runs_for_report()
        cell = dlg._thresholds_cell(reps[0])
        assert "not recorded" not in cell, (
            f"the Report Results table still says the verdict was not "
            f"recorded: {cell}")
        assert dlg._judged_label_for(reps[0]) in cell, (
            "the cell names no limit set, so the reader cannot tell what the "
            "words above it were worked out against")
    finally:
        dlg.close()


def test_a_report_that_really_is_old_is_still_named_as_one(tmp_path, qapp):
    """THE OTHER HALF, and the reason this is not a one-line deletion. A report
    saved WITHOUT a verdict block, which is what a pre-#182 ChromIQ wrote, must
    still get the sentence about an older version: the fix must distinguish
    "nothing was saved" from "something was saved and it holds no verdict",
    not silence both."""
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import build_report, save_report
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    rep = build_report(str(v.measurement_ti3))
    rep.pop("verdict", None)              # exactly what an older ChromIQ wrote
    save_report(rep, v.dir)
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        reps = dlg._runs_for_report()
        old = [r for r in reps if not r.get("_fresh")]
        assert old, "the saved report was not picked up, so nothing is proved"
        assert dlg._recorded(old[0]) is None
        assert BLAMES_AN_OLD_VERSION in dlg._verdict_provenance(old[0], False), (
            "a report that really was saved without a verdict no longer says "
            "so, which is the fix over-reaching")
    finally:
        dlg.close()
