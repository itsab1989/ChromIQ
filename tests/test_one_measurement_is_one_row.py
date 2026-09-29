"""One measurement is ONE row in the Measurement Report window.

Found by the combined adversary round of 2026-09-15, driving the merged tree on
screen: the state that shows it is now reached by an ordinary journey, because
the Measurement tab's import door saves a dated report by side effect and the
user's first press of **Generate report** then saves a second one of the same
measurement. Two files, one measurement — and the window read the files.

WHAT A USER SAW (`~/Desktop/ChromIQ-beta18-proof/combined-round-1/`,
`D2-report-window-with-two-saved-reports.png`):

* the list said **"2 runs"** and carried two rows reading
  `2026-09-15 14:12 — printing method not recorded`, word for word identical;
* **"No. of Measurements: 2"**, of a chart measured once;
* *Trend over time (this printer)* drew flat lines from the measurement to
  itself, between one date and the same date;
* and unticking EITHER row emptied the page, because `build_report` stamps
  `created` from the MEASUREMENT rather than from the moment Generate was
  pressed, so both rows carried the same `_run_key`. Measured: 2 rows, **1**
  distinct key, and hiding one row left **0**.

It is the other half of a rule this window already applies on the way out.
`_reports_to_generate` says *"one report per MEASUREMENT rather than one per
report already saved of it"* and keys on `(origin, ti3 name)`; the reading side
kept the old rule, so the count the writer had just stopped doubling was
doubled again on the way back in.

**NOTHING HERE TOUCHES SEVERAL REPORT TYPES PER RUN.** Knut, 2026-09-11: *"A
user should be allowed to print several report types for a run … The Report
window must thus show which type of reports have been generated"*. Which types
exist is said by its own line (`_generated_types_line`, "Already generated for
this run: …"), every file stays on disk, and
`tests/test_a_run_may_hold_several_report_types.py` still passes. A row was
never how that was shown and could not be: every such row carries the same
date and reads identically.
"""
from __future__ import annotations

import pytest

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _one_run_project(tmp_path, qapp):
    from tests.test_import_measurement_module import _cgats, _env, _PATCHES
    s, fm, _ctl = _env(tmp_path)
    proj = fm.project()
    run = proj.current_run()
    run.ensure_dir()
    run.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    return s, proj, run


def _window_on(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    return dlg


def _generate(dlg, monkeypatch, qapp):
    monkeypatch.setattr(dlg, "_say_generated", lambda saved, failed: None)
    dlg._on_generate_report()
    qapp.processEvents()


def _report_files(run) -> list:
    d = run.dir / "reports"
    return sorted(p.name for p in d.glob("report_*.json")) if d.is_dir() else []


def _two_saved_reports(tmp_path, qapp, monkeypatch):
    """A run whose one measurement has TWO saved reports, the everyday way:
    press Generate report twice."""
    s, proj, run = _one_run_project(tmp_path, qapp)
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        _generate(dlg, monkeypatch, qapp)
        _generate(dlg, monkeypatch, qapp)
    finally:
        dlg.close()
    assert len(_report_files(run)) == 2, (
        "the control failed: two presses left %r" % (_report_files(run),))
    return s, proj, run


# ---------------------------------------------------------------------------

def test_two_saved_reports_of_one_measurement_are_one_row(tmp_path, qapp,
                                                          monkeypatch):
    """THE FAULT ITSELF, counted the way the window counts it.

    MUTATION: delete the `_one_row_per_measurement` call from `_gather_runs`
    and this goes red with 2 rows.
    """
    s, _proj, run = _two_saved_reports(tmp_path, qapp, monkeypatch)
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        rows = dlg._runs_for_document()
        assert len(rows) == 1, (
            "one measurement with %d saved reports of it is showing as %d "
            "measurement rows: %r" % (len(_report_files(run)), len(rows),
                                      [r.get("created") for r in rows]))
    finally:
        dlg.close()


def test_hiding_one_row_never_hides_another(tmp_path, qapp, monkeypatch):
    """The consequence a user meets: unticking one row emptied the page.

    Kept as its own check because it is the half that is about `_run_key`, and
    a future change that re-admits duplicate rows without re-admitting the key
    collision would still be wrong but would pass the count above.

    MUTATION: delete the `_one_row_per_measurement` call from `_gather_runs`
    and this goes red - hiding one of the two rows leaves none.
    """
    s, proj, run = _two_saved_reports(tmp_path, qapp, monkeypatch)
    # **A SECOND MEASUREMENT, BECAUSE OF B8-392.** A window whose list holds
    # ONE measurement turns "Show all measurement runs" off and greys it (Knut,
    # 2026-09-18), and the row ticks only decide anything while it is on. This
    # test is about `_run_key`, so it is put where the ticks speak. The
    # MUTATION still lands: without `_one_row_per_measurement` the doubled
    # measurement is two rows sharing one key, and hiding that key takes two
    # rows off instead of one.
    from tests.test_import_measurement_module import _cgats, _PATCHES
    run2 = proj.new_run()
    run2.ensure_dir()
    run2.measurement_ti3.write_text(
        _cgats("CTI3", [(min(100.0, r + 3.0), g, b) for r, g, b in _PATCHES]),
        encoding="utf-8")
    # …with a report of its own, because that is what puts another run's
    # measurement into this window's history at all.
    dlg2 = _window_on(s, run2.measurement_ti3, qapp)
    try:
        _generate(dlg2, monkeypatch, qapp)
    finally:
        dlg2.close()
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        # EVERY MEASUREMENT TICKED. It was `_all_runs_check`, removed with
        # the feature behind it on Knut's 2026-09-20 ruling (B8-590); what
        # decides the measurements a report covers is the list, and "Select
        # all" is the button he asked for.
        dlg._select_all_btn.click()
        qapp.processEvents()
        assert len(dlg._runs_for_report()) > 1, (
            "the window still holds one measurement, so the ticks decide "
            "nothing and this test would prove nothing")
        rows = dlg._runs_for_document()
        keys = [dlg._run_key(r) for r in rows]
        assert len(set(keys)) == len(keys), (
            "%d rows share only %d keys, so one tick speaks for several"
            % (len(keys), len(set(keys))))
        before = len(dlg._runs_for_report())
        dlg._hidden_runs.add(keys[0])
        after = len(dlg._runs_for_report())
        assert after == before - 1, (
            "unticking one row took %d rows off the page" % (before - after))
    finally:
        dlg.close()


def test_the_row_kept_is_the_newest_report_of_that_measurement(tmp_path, qapp,
                                                               monkeypatch):
    """So the row carries the type and the limits most recently asked for.

    `save_report` names a second report of the same second `…_2.json`, so the
    file name is the write order; the tie-break reads it.

    MUTATION: flip `>=` to `<=` in `_one_row_per_measurement` and this goes red.
    """
    s, _proj, run = _two_saved_reports(tmp_path, qapp, monkeypatch)
    files = sorted((run.dir / "reports").glob("report_*.json"))
    # A mark only the LAST file carries, so the row can name which one it is.
    newest = files[-1]
    doc = json.loads(newest.read_text(encoding="utf-8"))
    doc["chart"] = "the newest report of this measurement"
    newest.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        rows = dlg._runs_for_document()
        assert len(rows) == 1
        assert rows[0].get("chart") == "the newest report of this measurement", (
            "the row kept is not the newest saved report: %r"
            % rows[0].get("chart"))
    finally:
        dlg.close()


def test_the_bookkeeping_this_needs_never_reaches_a_saved_file(tmp_path, qapp,
                                                               monkeypatch):
    """`_report_file` is session-only, like `_origin_dir` and `_fresh`.

    The saved document is a record a later ChromIQ reads; a path into one
    person's temp folder is not part of it. The writer strips every key that
    starts with an underscore, which is what this pins.
    """
    s, _proj, run = _two_saved_reports(tmp_path, qapp, monkeypatch)
    for p in (run.dir / "reports").glob("report_*.json"):
        doc = json.loads(p.read_text(encoding="utf-8"))
        leaked = sorted(k for k in doc if k.startswith("_"))
        assert not leaked, f"{p.name} carries window bookkeeping: {leaked}"


def test_several_runs_still_each_get_their_own_row(tmp_path, qapp, monkeypatch):
    """THE FEATURE THIS MUST NOT EAT: the trend across a printer's builds
    (#40, Knut). Two RUNS are two measurements and stay two rows, however many
    reports each of them holds.

    MUTATION: drop `origin` from the key in `_one_row_per_measurement` - every
    run's measurement carries the SAME file name (the sanitised project name),
    so the whole project collapses to one row and this goes red.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    s, proj, run1 = _one_run_project(tmp_path, qapp)
    run2 = proj.new_run()
    run2.ensure_dir()
    shifted = [(min(100.0, r + 3.0), g, b) for r, g, b in _PATCHES]
    run2.measurement_ti3.write_text(_cgats("CTI3", shifted), encoding="utf-8")

    for run in (run1, run2):
        dlg = _window_on(s, run.measurement_ti3, qapp)
        try:
            # K31: a report is saved where its TICKED measurements decide, so
            # each run's own report is made with that run's sheet ticked
            # alone (with both ticked it would be one report across the runs,
            # in the project's reports/, and no run would get its own).
            mine = dlg._run_key(dlg._report)
            dlg._hidden_runs = {dlg._run_key(r) for r in dlg._history
                                if dlg._run_key(r) != mine}
            dlg._sync_limit_controls()
            _generate(dlg, monkeypatch, qapp)
            _generate(dlg, monkeypatch, qapp)
        finally:
            dlg.close()

    dlg = _window_on(s, run1.measurement_ti3, qapp)
    try:
        # The window opens on the latest report of run1 (B8-388), and that
        # document was generated while only run1 was loaded, so it records
        # "Show all measurement runs" OFF (B8-392's rule 4 was in force when it
        # was made). Loading a report with the settings it was made with is
        # exactly what Knut asked for; this test is about the ROWS, so it opens
        # the window's history up again first.
        #
        # …and since B8-490 that report brings its own MEASUREMENT ticks with
        # it too, and it was generated while only run1 was loaded, so run2's
        # row comes back unticked. "New report…" is the control that means
        # "start from everything loaded", which is the state this is about,
        # and "Select all" (B8-590, in place of the removed "Show all
        # measurement runs" box) says the same thing about the list.
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        dlg._select_all_btn.click()
        qapp.processEvents()
        rows = dlg._runs_for_document()
        origins = {str(r.get("_origin_dir") or "") for r in rows}
        assert origins == {str(run1.dir), str(run2.dir)}, (
            "the two runs' measurements are showing as %r" % (sorted(origins),))
        assert len(rows) == 2, (
            "two runs with two reports each are showing as %d rows" % len(rows))
    finally:
        dlg.close()


@pytest.fixture(autouse=True)
def _each_press_answers_create_new(monkeypatch):
    """**K4 (Knut on beta 34): Generate on a selected report now asks**,
    whether or not a setting moved, because pressing it on a report with
    nothing changed created a new one in silence. These checks press Generate
    repeatedly to count what a CREATING press writes, which is what a user
    reaches by answering "Create New"; so that is the answer, given through
    the question's one method. The question itself is guarded in
    `tests/test_generate_report_asks_what_to_do.py`.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    monkeypatch.setattr(MeasurementReportDialog, "_ask_update_or_create_new",
                        lambda self: "new")
