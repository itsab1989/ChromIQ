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
    text = _cgats("CTI3", shifted)
    # THE READINGS CHANGE, THE CHART DOES NOT (#182 A10). Measuring again
    # reads the same patches, so the device values stay the chart's own and
    # only the colour columns move. Scaling them too left the sheet with no
    # patch printed with no ink, and since beta 42 the paper white is that
    # patch, not the lightest reading.
    lines = text.splitlines()
    i0 = lines.index("BEGIN_DATA") + 1
    for k, (r, g, b) in enumerate(_PATCHES):
        cells = lines[i0 + k].split()
        cells[2:5] = [f"{r:.4f}", f"{g:.4f}", f"{b:.4f}"]
        lines[i0 + k] = " ".join(cells)
    run.measurement_ti3.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
    # **FROM "New report…" (B8-490).** Since Knut's beta-25 ruling a window
    # that opens showing a saved report brings that report's own two tick
    # boxes with it, and a per-measurement record is about ONE date, so "Show
    # all measurement runs" comes up OFF where the Preferences default used to
    # leave it ON. "New report…" is the control that means "start from the
    # defaults with everything loaded", which is the state these checks are
    # about, and it repaints, which a tick box deliberately does not.
    dlg._saved_combo.setCurrentIndex(0)
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


def _folder(tmp_path, names, stamps=None):
    """A run folder holding the named .ti3 files, with a time on each."""
    from tests.test_import_measurement_module import _cgats, _PATCHES
    run = tmp_path / "runs" / "run1"
    run.mkdir(parents=True)
    for i, n in enumerate(names):
        f = run / n
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(_cgats("CTI3", [(r * (1 - i * 0.05), g, b)
                                     for r, g, b in _PATCHES]), encoding="utf-8")
        if stamps and stamps[i] is not None:
            os.utime(f, (stamps[i], stamps[i]))
    return run


def test_the_reports_own_name_wins_while_the_folder_has_that_file(tmp_path):
    """A run folder holds `<name>.ti3` beside `preconditioning.ti3` and
    `merged.ti3`, and a report about one of them must never be rebuilt from
    another. While the file the report NAMES is in the folder, that is the
    file, and nothing falls back.

    MUTATION: take the name from `opened_on` first and this goes red.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import created_stamp_for
    run = _folder(tmp_path, ["chart.ti3", "merged.ti3"],
                  [time.time() - 7200, time.time() - 3600])
    want = created_stamp_for(run / "merged.ti3")
    assert created_stamp_for(run / "chart.ti3") != want
    got = MeasurementReportDialog._measurement_for(
        {"created": want, "ti3": "merged.ti3"}, run, run / "chart.ti3")
    assert got == run / "merged.ti3", got
    # …and the report about the chart is not answered with merged.ti3 either.
    got = MeasurementReportDialog._measurement_for(
        {"created": created_stamp_for(run / "chart.ti3"), "ti3": "chart.ti3"},
        run, run / "merged.ti3")
    assert got == run / "chart.ti3", got


def test_a_renamed_target_still_finds_its_own_measurement(tmp_path):
    """RENAMING A TARGET RENAMES THE MEASUREMENT AND LEAVES THE REPORTS NAMING
    THE OLD STEM, and the demo package ships exactly that state with dates it
    wrote by hand. Driven on screen on `Demo-Switching/runs/run2`: refusing it
    took the ΔE block off both dated rows and emptied the trend, where the code
    before B8-205 had them right. One measurement has ever been in this folder,
    so the file the window is about is that measurement.

    MUTATION: remove the `opened_on` fall-back and this goes red; remove the
    "no archive, no other date" guard and
    `test_a_measurement_whose_stamp_moved_is_not_claimed` goes red instead.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    run = _folder(tmp_path, ["new-name-verify.ti3"], [time.time() - 60])
    got = MeasurementReportDialog._measurement_for(
        {"created": "2026-05-20T09:05:00", "ti3": "old-name-verify.ti3"},
        run, run / "new-name-verify.ti3")
    assert got == run / "new-name-verify.ti3", got


def test_a_measurement_whose_stamp_moved_is_not_claimed(tmp_path):
    """The whole point of the None. Once the run has been measured again the
    file under that name is a different sheet, and the archive
    `MeasurementSession.begin` leaves behind is what says so.

    MUTATION: drop the `old/` check and this goes red.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import created_stamp_for
    run = _folder(tmp_path, ["chart.ti3", "old/2026-01-02_030405/chart.ti3"],
                  [time.time(), time.time() - 9000])
    was = created_stamp_for(run / "old" / "2026-01-02_030405" / "chart.ti3")
    assert was != created_stamp_for(run / "chart.ti3")
    assert MeasurementReportDialog._measurement_for(
        {"created": was, "ti3": "chart.ti3"}, run, run / "chart.ti3") is None


def test_two_dates_in_one_folder_are_two_measurements(tmp_path):
    """The other half of the folder evidence, and the half that works when the
    archive is gone. Two saved reports of one file carrying two different
    dates cannot both be about the one measurement standing there.

    MUTATION: drop the `dates_here` check and this goes red.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import created_stamp_for
    run = _folder(tmp_path, ["chart.ti3"], [time.time()])
    now = created_stamp_for(run / "chart.ti3")
    two = {now, "2026-01-02T03:04:05"}
    assert MeasurementReportDialog._measurement_for(
        {"created": "2026-01-02T03:04:05", "ti3": "chart.ti3"},
        run, run / "chart.ti3", dates_here=two) is None
    # …and with only its own date recorded, the same report is accepted.
    assert MeasurementReportDialog._measurement_for(
        {"created": "2026-01-02T03:04:05", "ti3": "chart.ti3"},
        run, run / "chart.ti3",
        dates_here={"2026-01-02T03:04:05"}) == run / "chart.ti3"


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


# ---------------------------------------------------------------------------
# why the archived copy is not rebuilt from, pinned as facts rather than
# as a sentence in a docstring (round 3 wrote a false one there first)
# ---------------------------------------------------------------------------

def test_an_archived_measurement_is_never_the_rebuild_source(tmp_path):
    """The archive IS findable and IS readable, and is still refused.

    The first reason written down for refusing it was that an archived
    measurement can find no design reference. It can: `_find_reference_ti2`
    climbs three levels for a dated verification, and from
    `runs/runN/old/<when>/` those same three levels land on the run root. This
    test states the fact that was got wrong, so the next reader does not have
    to take a docstring's word for it, and then states the refusal.

    MUTATION: add an `old/` search to `_measurement_for` and this goes red.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import (_find_reference_ti2, _sheet_kind,
                                             created_stamp_for)
    run = tmp_path / "runs" / "run1"
    (run / "old" / "2026-01-02_030405").mkdir(parents=True)
    run.joinpath("c.ti2").write_text(_cgats("CTI2", _PATCHES), encoding="utf-8")
    run.joinpath("c.ti3").write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    archived = run / "old" / "2026-01-02_030405" / "c.ti3"
    archived.write_text(_cgats("CTI3", [(r * 0.8, g * 0.8, b * 0.8)
                                        for r, g, b in _PATCHES]), encoding="utf-8")
    # AN EARLIER TIME ON THE ARCHIVE, or the control is not the state. Written
    # in the same second as the live file the two carry the same stamp, the
    # live file answers for the archived report, and the test passes for a
    # reason that has nothing to do with what it is about. It did, first time.
    then = time.time() - 4 * 3600
    os.utime(archived, (then, then))
    assert created_stamp_for(archived) != created_stamp_for(run / "c.ti3")
    # The fact the docstring got wrong: it finds the run's CURRENT chart.
    assert _find_reference_ti2(archived) == run / "c.ti2"
    # …and one of the two real reasons: it stops being a profiling sheet.
    assert _sheet_kind(run / "c.ti3") == "profiling"
    assert _sheet_kind(archived) == "standalone"
    # The refusal itself.
    assert MeasurementReportDialog._measurement_for(
        {"created": created_stamp_for(archived), "ti3": "c.ti3"},
        run, run / "c.ti3") is None


def test_the_keyword_is_read_through_parse_ti3s_own_regex(tmp_path):
    """ONE RULE, TWO READERS, AND THEY MUST NOT PART COMPANY. `build_report`
    hands `created_stamp_for` the keywords `parse_ti3` found; `_measurement_for`
    makes it read the file. A file whose keyword line one reader sees and the
    other does not would silently stop matching itself.

    128 .ti3 files on one real disk agreed, and NOT ONE of them carried this
    keyword, so that sample said nothing about this branch. These lines do: the
    tab is the separator a hand-rolled "split on the first space" loses, and
    `_KW_RE` allows any whitespace.

    MUTATION: read the keyword with `s.partition(" ")` again and the tab case
    goes red.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.measurement_report import build_report, created_stamp_for
    for i, kw in enumerate((
            'CHROMIQ_MEASURED "2026-03-04T05:06:07"',
            'CHROMIQ_MEASURED\t"2026-03-04T05:06:07"',
            'CHROMIQ_MEASURED   "2026-03-04T05:06:07"',
            'CHROMIQ_MEASURED 2026-03-04T05:06:07')):
        p = tmp_path / f"k{i}.ti3"
        p.write_text(_cgats("CTI3", _PATCHES, extra_keywords=kw + "\n"),
                     encoding="utf-8")
        assert created_stamp_for(p) == "2026-03-04T05:06:07", kw
        assert build_report(p)["created"] == created_stamp_for(p), kw


# ---------------------------------------------------------------------------
# …and the measurement in hand is in its own history even with no report of it
# ---------------------------------------------------------------------------

def _measured_again_with_the_report_switched_off(tmp_path):
    """One run: measured, reported, then measured AGAIN with *Save measurement
    report* off. The archive is the app's own — `MeasurementSession.begin` is
    what a real read calls — so the folder ends in the state a user reaches by
    switching one preference."""
    from workflow.measurement_report import build_report, save_report
    from workflow.measurement_session import MeasurementSession
    s, run = _env_and_run(tmp_path)
    first = time.time() - 7200
    _measure_again(run, 1.0, first)
    save_report(build_report(run.measurement_ti3), run.dir)
    sess = MeasurementSession(run.measurement_ti3, run.chart_ti2,
                              old_dir=run.old_dir)
    assert sess.begin() is not None, "the control failed: nothing was archived"
    _measure_again(run, 0.7, time.time())
    sess.finish(resumed=False)
    assert len(list((run.dir / "reports").glob("report_*.json"))) == 1, (
        "the control failed: the second measurement left a report of its own")
    return s, run


def test_a_measurement_with_no_report_of_its_own_is_still_its_own_row(
        tmp_path, qapp):
    """THE FAULT: the window opened on a measurement described an older one.

    The history test was `_report_is_about`, which matches on the run folder
    plus the bare file NAME, and every measurement of one run carries that
    pair. So eleven older reports answered "this measurement is already in the
    history", no row was added for the sheet in hand, and the subject fell
    through to the newest SAVED report.

    MUTATION: put the guard back to `self._report_is_about(r, ti3)` and this
    goes red, with the window describing the first measurement.
    """
    from workflow.measurement_report import build_report
    s, run = _measured_again_with_the_report_switched_off(tmp_path)
    now = build_report(run.measurement_ti3)
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        subject = dlg._report or {}
        assert str(subject.get("created")) == str(now["created"]), (
            "the window is opened on the measurement of %s and describes the "
            "one of %s" % (now["created"], subject.get("created")))
        white = float((subject.get("paper_white") or {}).get("lab")[0])
        assert abs(white - float(now["paper_white"]["lab"][0])) < 0.005
        assert len(dlg._runs_for_document()) == 2, (
            "%d row(s) for two measurements" % len(dlg._runs_for_document()))
    finally:
        dlg.close()


def test_generate_files_a_report_about_the_measurement_in_hand(tmp_path, qapp):
    """The consequence that writes to disk, kept apart from the one that only
    reads: with the subject wrong, Generate report filed a report about a sheet
    measured hours earlier, stamped with this window's limits and type.

    MUTATION: put the guard back to `self._report_is_about(r, ti3)` and this
    goes red, naming the older measurement's date.
    """
    from workflow.measurement_report import build_report
    s, run = _measured_again_with_the_report_switched_off(tmp_path)
    now = build_report(run.measurement_ti3)
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        about = [str(g.get("created")) for g in dlg._reports_to_generate()]
        assert about == [str(now["created"])], (
            "Generate would file about %r; the measurement in hand is %s"
            % (about, now["created"]))
    finally:
        dlg.close()


def test_a_run_with_one_measurement_does_not_list_it_twice(tmp_path, qapp):
    """THE THING THIS MUST NOT EAT, and the shape the first cut of it broke: a
    saved report and the measurement it is about are ONE row, not two, even
    when the stamp has moved under the report (a renamed target, or the demo
    package's hand-written dates).

    MUTATION: make `_is_this_measurement` compare `created` directly instead of
    asking `_measurement_for`, and this goes red with 2 rows for 1 measurement.
    """
    from workflow.measurement_report import build_report, save_report
    s, run = _env_and_run(tmp_path)
    _measure_again(run, 1.0, time.time() - 3600)
    rep = build_report(run.measurement_ti3)
    rep["created"] = "2026-05-20T09:05:00"      # a date the file does not carry
    save_report(rep, run.dir)
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        rows = dlg._runs_for_document()
        assert len(rows) == 1, (
            "one measurement is listed %d times: %r"
            % (len(rows), [r.get("created") for r in rows]))
    finally:
        dlg.close()
