"""A dated row in the Measurement Report shows the sheet it was measured from.

Found by the combined adversary round of 2026-09-15 (B8-205), attacking the
round before it. Round 2 restored one row per MEASUREMENT, so a run measured
seventeen times finally listed seventeen dates. Every one of those rows then
turned out to be carrying the numbers of the same sheet.

**THE REBUILD READ WHATEVER WAS IN THE RUN FOLDER TODAY.**
``MeasurementReportDialog._gather_runs`` recomputes a saved report whose schema
or block set is out of date, so that rows added to the report since it was
saved are not blank for ever. It took the measurement to recompute from as
``p.parent.parent / ti3.name`` — the run folder, plus the name of the file the
window was opened on. Every measurement of one run carries that same name: the
stem is the sanitised project name, and measuring again copies the previous
``.ti3`` into ``old/<when>/`` and writes the new one over it. So for every
report except the newest, that path is a DIFFERENT measurement.

The rebuild kept the saved date and the saved verdict and replaced every
number.

WHAT A USER SAW (``~/Desktop/ChromIQ-beta18-proof/combined-round-3/``,
``B1-seventeen-dates-one-sheet.png``). A real project off a real disk,
``CR30-Test/runs/run1``: seventeen distinct measurements, twenty-two archived
copies in ``old/``. The window listed all seventeen dates across five weeks,
and every row read **8 patches, ΔE00 average 11.948, paper white L\\* 66.97** —
the sheet measured on 8 September. The row dated 29 August had been saved with
**20 patches, ΔE00 15.907, white L\\* 92.39**. The over-time trend (#40), which
is what the window's own subtitle promises, drew seventeen points in five
perfectly flat lines. Sixteen of the seventeen rows had their numbers replaced.

Surveyed over that whole disk: of 54 saved reports, **four** describe the
measurement still live in their run folder.

THE FIX IS AN IDENTITY, NOT A PATH. ``created_stamp_for`` is the rule
``build_report`` stamps a report's ``created`` with, lifted out so there are
two callers and one rule; ``_measurement_for`` hands back the run's
measurement only while its own stamp is still this report's, and ``None``
otherwise. A report whose measurement cannot be told apart keeps the numbers it
was saved with.

``C1-FIXED-seventeen-dates-seventeen-sheets.png`` is the same window
afterwards: seventeen rows, seventeen distinct number sets, seventeen distinct
trend values.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------------------
# the state: one run, measured three times, each measurement reported once
# ---------------------------------------------------------------------------

def _env_and_run(tmp_path):
    from tests.test_import_measurement_module import _cgats, _env, _PATCHES
    s, fm, _ctl = _env(tmp_path)
    run = fm.project().current_run()
    run.ensure_dir()
    run.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    return s, run


def _measure_again(run, factor: float, when: float) -> None:
    """What measuring the same run again leaves behind: the same file name,
    different readings, a later time on the file.

    A FACTOR, NOT AN OFFSET, and every channel. `_cgats` derives XYZ_Y from
    GREEN and the paper white these tests tell the sheets apart by is the patch
    with the largest L*; that patch is (100, 100, 100), so adding to it and
    clamping left three sheets with one identical paper white. The control in
    `_three_reported_measurements` caught it.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    shifted = [(r * factor, g * factor, b * factor) for r, g, b in _PATCHES]
    run.measurement_ti3.write_text(_cgats("CTI3", shifted), encoding="utf-8")
    os.utime(run.measurement_ti3, (when, when))


def _stale(path: Path) -> None:
    """Make a saved report stale the way every report on a real disk is stale:
    a block the current builder always writes is simply not in it."""
    rep = json.loads(path.read_text(encoding="utf-8"))
    rep.pop("grey_balance", None)
    rep.pop("summary_patches", None)
    path.write_text(json.dumps(rep), encoding="utf-8")


def _three_reported_measurements(tmp_path):
    """Three measurements of one run, one saved report each, the two older
    ones stale. Returns (settings, run, [(created, patches, avg_all), ...])."""
    from workflow.measurement_report import build_report, save_report
    s, run = _env_and_run(tmp_path)
    base = time.time() - 3 * 3600
    saved: list = []
    files: list = []
    for i, factor in enumerate((1.0, 0.92, 0.84)):
        _measure_again(run, factor, base + i * 1800)
        rep = build_report(run.measurement_ti3)
        files.append(save_report(rep, run.dir))
        de = rep.get("de00") or {}
        saved.append((str(rep["created"]), rep["patches"],
                      de.get("avg_all"),
                      float((rep["paper_white"]["lab"])[0])))
    for p in files[:-1]:
        _stale(p)
    created = [row[0] for row in saved]
    assert len(set(created)) == 3, (
        "the control failed: three measurements carry %d distinct dates (%r)"
        % (len(set(created)), created))
    assert len({row[3] for row in saved}) == 3, (
        "the control failed: the three measurements are not distinguishable "
        "by their paper white (%r)" % ([row[3] for row in saved],))
    return s, run, saved


def _window_on(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    return dlg


# ---------------------------------------------------------------------------
# the fault itself
# ---------------------------------------------------------------------------

def test_each_row_carries_its_own_measurements_numbers(tmp_path, qapp):
    """THE FAULT: three dated rows, three sheets, three sets of numbers.

    MUTATION: put the rebuild's source back to
    `run_ti3 = p.parent.parent / ti3.name` and this goes red, with all three
    rows reading the paper white of the newest measurement.
    """
    s, run, saved = _three_reported_measurements(tmp_path)
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        rows = {str(r.get("created")): r for r in dlg._runs_for_document()}
        assert len(rows) == 3, "%d row(s) for three measurements" % len(rows)
        for created, patches, avg, white in saved:
            r = rows[created]
            got = float((r.get("paper_white") or {}).get("lab")[0])
            assert abs(got - white) < 0.005, (
                "the row dated %s was saved with paper white L* %.2f and is "
                "showing %.2f" % (created, white, got))
            assert r.get("patches") == patches
    finally:
        dlg.close()


def test_the_trend_draws_a_different_point_for_each_measurement(tmp_path,
                                                                qapp):
    """The consequence the window is FOR (#40). A flat line across three
    genuinely different sheets is the thing a reader acts on.

    MUTATION: put the rebuild's source back to `p.parent.parent / ti3.name`
    and this goes red with one distinct value for three points.
    """
    from workflow.measurement_report import report_trend
    s, run, saved = _three_reported_measurements(tmp_path)
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        trend = report_trend(dlg._runs_for_report())
        whites = [round(float(p["white_L"]), 3) for p in trend
                  if p.get("white_L") is not None]
        assert len(whites) == 3 and len(set(whites)) == 3, (
            "the trend drew %d point(s) carrying %d distinct paper whites: %r"
            % (len(trend), len(set(whites)), whites))
    finally:
        dlg.close()


def test_the_measurement_still_in_the_run_folder_is_still_rebuilt(tmp_path,
                                                                  qapp):
    """THE BEHAVIOUR THIS MUST NOT EAT. The reason the rebuild exists is that a
    report saved before a row existed would otherwise read N-A for ever, and
    that reason still holds for the report of the measurement that IS in the
    run folder. Its stamp matches, so it is rebuilt and the block comes back.

    MUTATION: make `_measurement_for` return None unconditionally and this goes
    red with no grey block on the newest row.
    """
    s, run, saved = _three_reported_measurements(tmp_path)
    newest = saved[-1][0]
    # The control: it really is missing from the file on disk.
    path = sorted((run.dir / "reports").glob("report_*.json"))[-1]
    _stale(path)
    assert "grey_balance" not in json.loads(path.read_text(encoding="utf-8"))
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        rows = {str(r.get("created")): r for r in dlg._runs_for_document()}
        assert "grey_balance" in rows[newest], (
            "the report of the measurement that is still in the run folder "
            "was not rebuilt, so a row it could compute stays blank")
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# the identity itself
# ---------------------------------------------------------------------------

def test_created_stamp_for_is_the_stamp_build_report_writes(tmp_path):
    """ONE RULE, TWO CALLERS. The match is only sound while the function that
    finds a report's measurement answers exactly what the function that built
    the report wrote into it.

    MUTATION: make `created_stamp_for` fall back to `datetime.now()` instead of
    the file's own time and this goes red.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.measurement_report import build_report, created_stamp_for
    plain = tmp_path / "plain.ti3"
    plain.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    os.utime(plain, (time.time() - 90000, time.time() - 90000))
    assert build_report(plain)["created"] == created_stamp_for(plain)

    dated = tmp_path / "dated.ti3"
    dated.write_text(_cgats("CTI3", _PATCHES,
                            extra_keywords='CHROMIQ_MEASURED "2026-03-04T05:06:07"\n'),
                     encoding="utf-8")
    assert created_stamp_for(dated) == "2026-03-04T05:06:07"
    assert build_report(dated)["created"] == created_stamp_for(dated)


def test_a_date_only_measured_keyword_reads_the_same_both_ways(tmp_path):
    """The other branch of the same rule: an i1Profiler export whose date has
    no time on it. Kept separate because it is the branch a cheap header scan
    is most likely to get wrong.

    MUTATION: drop the date-only branch from `created_stamp_for` and this goes
    red.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.measurement_report import build_report, created_stamp_for
    p = tmp_path / "dateonly.ti3"
    p.write_text(_cgats("CTI3", _PATCHES,
                        extra_keywords='CHROMIQ_MEASURED "2026-03-04"\n'),
                 encoding="utf-8")
    assert created_stamp_for(p) == "2026-03-04T00:00:00"
    assert build_report(p)["created"] == created_stamp_for(p)


def test_a_report_naming_another_chart_is_not_rebuilt_from_this_run(tmp_path):
    """A run folder can hold reports that name a different measurement — a
    project copied out of another one, which is on the real disk this round
    read. The name comes from the REPORT.

    MUTATION: take the name from `opened_on` instead of `rep["ti3"]` and this
    goes red.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import created_stamp_for
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    mine = run_dir / "mine.ti3"
    mine.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    stamp = created_stamp_for(mine)
    assert MeasurementReportDialog._measurement_for(
        {"created": stamp, "ti3": "somebody-elses.ti3"}, run_dir, mine) is None
    assert MeasurementReportDialog._measurement_for(
        {"created": stamp, "ti3": "mine.ti3"}, run_dir, mine) == mine


def test_a_measurement_whose_stamp_moved_is_not_claimed(tmp_path):
    """The whole point of the None. Once the run has been measured again the
    file under that name is a different sheet, and nothing may be recomputed
    from it.

    MUTATION: drop the `created_stamp_for(live) == want` condition and this
    goes red.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import created_stamp_for
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    m = run_dir / "chart.ti3"
    m.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    was = created_stamp_for(m)
    assert MeasurementReportDialog._measurement_for(
        {"created": was, "ti3": "chart.ti3"}, run_dir, m) == m
    later = time.time() + 600
    os.utime(m, (later, later))
    assert MeasurementReportDialog._measurement_for(
        {"created": was, "ti3": "chart.ti3"}, run_dir, m) is None


def test_no_row_is_told_its_measurement_could_not_be_read(qapp):
    """A SENTENCE IS A PROMISE. `REASON_NOT_COMPUTED` means "the block is
    missing from this saved report"; it says nothing about whether any file can
    be read, and it is now reached by reports whose own measurement is sitting
    in the run's `old/` folder. The sentence said *"the measurement file could
    not be read again"*, which was untrue in both cases that reach it.

    MUTATION: put the old sentence back and this goes red.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import REASON_NOT_COMPUTED
    dlg = MeasurementReportDialog.__new__(MeasurementReportDialog)
    text = MeasurementReportDialog._reason_sentence(
        dlg, REASON_NOT_COMPUTED, {})
    assert text, "the reason has no sentence at all"
    assert "could not be read" not in text, text
    assert "saved report" in text, text
