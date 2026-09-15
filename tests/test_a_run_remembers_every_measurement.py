"""A run that was measured several times keeps every measurement in its history.

Found by the combined adversary round of 2026-09-15, attacking the fix the
round before it had just made (B8-200). That fix stopped two reports OF ONE
MEASUREMENT being listed as two measurement runs, and keyed the rule on
``(_origin_dir, ti3 file name)``. A measurement is not that pair.

**MEASURING A RUN AGAIN REUSES THE FILE NAME.** The previous ``.ti3`` is
archived into the run's ``old/`` folder and the new one is written under the
same stem, because the stem is the sanitised project name. With *Save
measurement report* on, each measurement leaves its own dated report in the
run's ``reports/``. So one run folder legitimately accrues one report per
measurement, and that accrual IS the over-time trend (#40, Knut) that the
window's own subtitle promises: *"keep a dated report so you can compare
measurements of the same chart over time"*.

WHAT A USER SAW (``~/Desktop/ChromIQ-beta18-proof/combined-round-2/``,
``E1-report-window-on-a-run-measured-many-times.png``). A real project off a
real disk, ``printer-test/runs/run1``: eleven dated reports of eleven distinct
measurements, fifty-five archived measurements in ``old/``. The window said

* **"printer-test · 1 run"**, one row, ``2026-08-08 13:36``;
* **"No. of Measurements: 1"** and a date range of ``2026-08-08 – 2026-08-08``
  for a session that ran from 11:48 to 13:36;
* *"A trend graph needs at least two measurement runs. Add another measurement,
  or, if the profile you have loaded already holds more than one run, tick
  'Show all measurement runs' above"* **with that box already ticked**;
* while the line above it read **"Already generated for this run: Full colour
  check (11)"**. The window knew about eleven and listed one.

Ten of the eleven measurements were absent from the list, the tables, the PDF
and the trend. Three more projects on the same disk were already in that state,
one of them with seventeen distinct measurements in a single run folder.

THE KEY IS THE ONE THIS CLASS ALREADY HAS. ``_run_key`` is
``_origin_dir | created | ti3``, and its own docstring gives the reason for
each part. Two reports of ONE measurement still merge under it, because
``build_report`` stamps ``created`` from the MEASUREMENT and not from the
moment Generate was pressed, which is precisely what the round before measured;
two MEASUREMENTS never do.

AND THE WRITING SIDE HAD TO MOVE WITH IT. With the history restored,
``_reports_to_generate`` saw several rows per folder again and kept the first,
which is the OLDEST. Pressing Generate would then have filed a report of a
sheet measured hours earlier, stamped with this window's limits and this
window's type, while the page in front of the user described a different sheet.
The row the window is ON wins now.
"""
from __future__ import annotations

import inspect
import json
import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _env_and_run(tmp_path, qapp):
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


def _measure_again(run, nudge: float, when: float) -> None:
    """What measuring the same run a second time leaves behind: the SAME file
    name, different readings, a later time on the file. ``build_report`` dates
    a report from the file when the .ti3 carries no measured-at keyword, so
    this is what tells the two measurements apart."""
    from tests.test_import_measurement_module import _cgats, _PATCHES
    shifted = [(min(100.0, r + nudge), g, b) for r, g, b in _PATCHES]
    run.measurement_ti3.write_text(_cgats("CTI3", shifted), encoding="utf-8")
    os.utime(run.measurement_ti3, (when, when))


def _three_measurements_of_one_run(tmp_path, qapp, monkeypatch):
    """One run, measured three times, each measurement reported once.

    The report is filed the way a MEASUREMENT files one, which is
    `TabMeasure._maybe_save_measurement_report`: build from the .ti3 that has
    just been written, then save. Pressing Generate in the report window is a
    different act on a different subject and is exercised by its own checks
    below.
    """
    from workflow.measurement_report import build_report, save_report
    s, proj, run = _env_and_run(tmp_path, qapp)
    base = time.time() - 3 * 3600
    for i, nudge in enumerate((0.0, 4.0, 8.0)):
        _measure_again(run, nudge, base + i * 1800)
        # No wait between them: `list_project_reports` orders by the
        # measurement's `created`, and `save_report` gives three files of one
        # second the names `report_<stamp>[_2][_3].json` by itself.
        save_report(build_report(run.measurement_ti3), run.dir)
    files = sorted((run.dir / "reports").glob("report_*.json"))
    created = {json.loads(p.read_text(encoding="utf-8"))["created"]
               for p in files}
    assert len(files) == 3 and len(created) == 3, (
        "the control failed: %d report files carrying %d distinct measurement "
        "dates" % (len(files), len(created)))
    return s, proj, run, sorted(created)


# ---------------------------------------------------------------------------

def test_every_measurement_of_a_run_is_its_own_row(tmp_path, qapp, monkeypatch):
    """THE FAULT ITSELF: three measurements, three rows.

    MUTATION: put the key in `_one_row_per_measurement` back to
    `(origin, Path(str(r.get("ti3") or "")).name)` and this goes red with one
    row, naming the newest measurement only.
    """
    s, _proj, run, created = _three_measurements_of_one_run(
        tmp_path, qapp, monkeypatch)
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        rows = dlg._runs_for_document()
        assert [str(r.get("created")) for r in rows] == created, (
            "a run measured %d times is showing %d row(s): %r"
            % (len(created), len(rows), [r.get("created") for r in rows]))
    finally:
        dlg.close()


def test_the_trend_gets_a_point_for_every_measurement(tmp_path, qapp,
                                                      monkeypatch):
    """The consequence the window is FOR. Kept apart from the row count because
    the trend is what the subtitle promises and what #40 asked for, and a row
    list that is right while the graph is empty would still be wrong.

    MUTATION: put the key back to `(origin, ti3 name)` and this goes red with
    one point, under the window's own "a trend graph needs at least two
    measurement runs".
    """
    from workflow.measurement_report import report_trend
    s, _proj, run, created = _three_measurements_of_one_run(
        tmp_path, qapp, monkeypatch)
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        trend = report_trend(dlg._runs_for_report())
        assert [str(p.get("created")) for p in trend] == created, (
            "the trend drew %d point(s) for %d measurements: %r"
            % (len(trend), len(created), [p.get("created") for p in trend]))
    finally:
        dlg.close()


def test_two_reports_of_one_measurement_are_still_one_row(tmp_path, qapp,
                                                          monkeypatch):
    """THE RULE THIS MUST NOT EAT, which is the round before's finding
    (B8-200): a run whose ONE measurement has two saved reports of it is one
    row, not two. `created` comes from the measurement, so both reports carry
    the same one and the key merges them.

    MUTATION: drop `created` from `_run_key` and this stays green while
    `test_every_measurement_of_a_run_is_its_own_row` goes red; drop the dedup
    call altogether and this goes red with 2 rows.
    """
    s, _proj, run = _env_and_run(tmp_path, qapp)
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        _generate(dlg, monkeypatch, qapp)
        _generate(dlg, monkeypatch, qapp)
    finally:
        dlg.close()
    assert len(list((run.dir / "reports").glob("report_*.json"))) == 2

    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        rows = dlg._runs_for_document()
        assert len(rows) == 1, (
            "one measurement with two saved reports is showing as %d rows: %r"
            % (len(rows), [r.get("created") for r in rows]))
    finally:
        dlg.close()


def test_generate_files_a_report_about_the_measurement_in_hand(
        tmp_path, qapp, monkeypatch):
    """Not the oldest one the folder remembers.

    The window is opened on the run's CURRENT measurement, and the history
    beside it now holds the earlier ones again. Generate writes one file, and
    it must describe the sheet the page describes, because it is stamped with
    this window's limits and this window's report type.

    MUTATION: in `_reports_to_generate`, go back to keeping the first row seen
    per key (`if key in seen: continue`) and this goes red, naming the oldest
    measurement.
    """
    s, _proj, run, created = _three_measurements_of_one_run(
        tmp_path, qapp, monkeypatch)
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        subject = str((dlg._report or {}).get("created"))
        assert subject == created[-1], (
            "the window opened on %r, not the run's current measurement %r"
            % (subject, created[-1]))
        gen = dlg._reports_to_generate()
        assert len(gen) == 1, (
            "Generate would write %d files for one run" % len(gen))
        assert str(gen[0].get("created")) == subject, (
            "Generate would file a report about %r while the window is on %r"
            % (gen[0].get("created"), subject))
    finally:
        dlg.close()


def test_generate_still_writes_one_file_per_press(tmp_path, qapp, monkeypatch):
    """The count must not start doubling again. Three presses on a run measured
    three times leave three new files, not nine and not twelve."""
    s, _proj, run, _created = _three_measurements_of_one_run(
        tmp_path, qapp, monkeypatch)
    before = len(list((run.dir / "reports").glob("report_*.json")))
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        for _ in range(3):
            _generate(dlg, monkeypatch, qapp)
    finally:
        dlg.close()
    after = len(list((run.dir / "reports").glob("report_*.json")))
    assert after == before + 3, (
        "three presses left %d new report files" % (after - before))


def test_the_row_rule_and_the_run_identity_are_the_same_key(tmp_path):
    """The two halves cannot drift apart again.

    `_run_key` is what a tick box, `_hidden_runs` and the one-page summary all
    key on; `_one_row_per_measurement` decides what a row IS. They were
    different expressions of the same idea for one commit, and the coarser one
    ate ten measurements out of eleven. This pins that the row rule asks
    `_run_key` rather than building a key of its own.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = inspect.getsource(
        MeasurementReportDialog._one_row_per_measurement.__func__
        if hasattr(MeasurementReportDialog._one_row_per_measurement, "__func__")
        else MeasurementReportDialog._one_row_per_measurement)
    body = src.split('"""')[-1]
    assert "_run_key(r)" in body, (
        "`_one_row_per_measurement` no longer keys on `_run_key`, so what "
        "counts as one row and what counts as one run can disagree again:\n"
        + body)
