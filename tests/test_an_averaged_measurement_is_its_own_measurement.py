"""Averaging replaces a run's measurement and leaves no archive behind.

Found by the combined adversary round of 2026-09-15 (B8-211), attacking the
three rounds before it. The Measurement Report window's idea of "which
measurement is this row" had been re-keyed four times in one day and settled on
*one reading session's ``.ti3``, told from the next by the stamp*
``build_report`` *writes into a report of it* — with the FOLDER settling it
wherever that stamp has moved for an innocent reason (B8-206).

**A FOLDER IS A PROXY, AND IT ONLY SEES THE DOORS THAT LEAVE SOMETHING
BEHIND.** The two folder tests stand for "this folder has held more than one
measurement under that name": an archive in ``old/<when>/``, or a second report
date. "Measure again to average" leaves neither.
``Run.promote_measurement_to_read`` MOVES ``<stem>.ti3`` into
``reads/readN.ti3``, so the next read's ``MeasurementSession.begin`` finds no
file to archive; ``_run_average_and_proceed`` then writes the averaged sheet
straight over ``Run.measurement_ti3``. The run ends holding a measurement
nobody has a report of, with nothing in ``old/`` at all.

WHAT A USER SAW, driven in a real window with the app's own moves
(``Run.promote_measurement_to_read``, ``MeasurementSession``,
``build_report``/``save_report``) and ArgyllCMS ``average``, on two real reads
of one chart copied out of a working folder
(``~/Desktop/ChromIQ-beta18-proof/combined-round-4/``,
``C-C-Averaged-Old-Report.png`` and ``C-C-Averaged-Today.png``):

* the saved report held **ΔE00 average 11.776, paper white A14 L\\* 92.72**;
  the averaged sheet in the run reads **13.513, C5 L\\* 91.74**;
* with a report the current builder rebuilds, the single row on screen was
  dated with the SAVED report's date and carried the AVERAGED sheet's numbers
  (the B8-205 shape);
* with a report it does not rebuild, there was no row for the averaged
  measurement at all, no point for it on the trend, and *Generate report* would
  have filed a report about the older sheet (the B8-208 shape).

``E-E-Averaged-Old-Report.png`` is the same window afterwards: two rows, the
saved one keeping 11.776 / L\\* 92.72 under its own date and the averaged
measurement carrying 13.513 / L\\* 91.74 under today's, and two trend points.

THE FIX ASKS THE FILE. A saved report keeps three facts about the measurement
it was built from — how many readings it held, and its lightest and darkest
patch — and ``workflow.measurement_report.measurement_facts`` is now the one
rule that writes them, with ``facts_disagree`` reading them back. It is
one-sided on purpose: agreement is not proof, so the folder tests still run
underneath, and ``reads/`` joins them there.

NOT IN A DATED VERIFICATION FOLDER, which is B8-206's own sentence rather than
a new exception: such a folder holds exactly one measurement, and the demo
package writes a STUB report into each one to give the history its date --
schema 5, no accuracy block, ``"patches": 240`` and a paper white of L\\* 95.4
beside a real 64-patch sheet whose white is L\\* 99.53 (measured on
``Demo-Switching`` and ``Demo-Prefs-Speed``, both dates). Asking the file there
would take the accuracy figures off exactly the rows B8-206 exists to keep.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_a_report_row_keeps_its_own_measurement import (  # noqa: E402
    _env_and_run, _folder, _measure_again, _stale, _window_on)


# ---------------------------------------------------------------------------
# the state: a run measured, reported, then averaged
# ---------------------------------------------------------------------------

def _averaged_run(tmp_path, *, stale: bool):
    """Measure, save a report, then do what "Measure again to average" does.

    The app's OWN move is used for the half that matters —
    `Run.promote_measurement_to_read`, which is what empties the run folder so
    that nothing is ever archived. The averaged output is written as a third,
    distinct sheet, which is what ArgyllCMS `average` leaves there.

    Returns (settings, run, saved_report_dict).
    """
    from workflow.measurement_report import build_report, save_report
    s, run = _env_and_run(tmp_path)
    base = time.time() - 4 * 3600

    # --- the measurement the report is about
    _measure_again(run, 1.0, base)
    rep = build_report(run.measurement_ti3)
    path = save_report(rep, run.dir)
    if stale:
        _stale(path)

    # --- "Measure again to average": the app MOVES the measurement away, so
    #     the next read's session finds nothing to archive.
    run.clear_reads()
    run.promote_measurement_to_read()
    _measure_again(run, 0.90, base + 1800)          # the second read
    run.promote_measurement_to_read()
    # --- and the average is written straight over the run's measurement
    _measure_again(run, 0.95, base + 3600)

    # THE CONTROLS, because a probe that cannot tell the sheets apart proves
    # nothing: no archive anywhere, and the sheet standing in the run is not
    # the one the report was built from.
    assert not (run.dir / "old").exists(), \
        "the control failed: averaging left an old/ archive after all"
    assert len(run.reads()) == 2, \
        "the control failed: %d read(s) in reads/" % len(run.reads())
    live = build_report(run.measurement_ti3)
    assert abs(float(live["paper_white"]["lab"][0])
               - float(rep["paper_white"]["lab"][0])) > 0.5, (
        "the control failed: the averaged sheet and the reported one have the "
        "same paper white, so this cannot tell them apart")
    return s, run, json.loads(path.read_text(encoding="utf-8")), rep


# ---------------------------------------------------------------------------
# the fault itself
# ---------------------------------------------------------------------------

def test_an_averaged_run_keeps_its_reports_own_numbers(tmp_path, qapp):
    """THE REBUILD HALF. The row keeps the numbers it was saved with.

    MUTATION: remove BOTH the `facts_disagree` call and the `reads/` test from
    `_measurement_for` and this goes red, the row reading the averaged sheet's
    paper white under the saved report's date. Either one alone catches this
    state, which is the point of having both: the file settles it for a report
    that records its measurement, the folder for one too old to.
    """
    s, run, saved, rep = _averaged_run(tmp_path, stale=True)
    want = float(rep["paper_white"]["lab"][0])
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        rows = {str(r.get("created")): r for r in dlg._runs_for_document()}
        row = rows[str(saved["created"])]
        got = float((row.get("paper_white") or {}).get("lab")[0])
        assert abs(got - want) < 0.005, (
            "the row dated %s was saved with paper white L* %.2f and is "
            "showing %.2f, which is the averaged sheet's"
            % (saved["created"], want, got))
    finally:
        dlg.close()


def test_the_averaged_measurement_gets_a_row_of_its_own(tmp_path, qapp):
    """THE HISTORY HALF. The sheet the window is open on is in its own history.

    MUTATION: remove BOTH the `facts_disagree` call and the `reads/` test and
    this goes red with one row for two measurements, and `_subject_of` then
    hands the window the older sheet.
    """
    from workflow.measurement_report import created_stamp_for
    s, run, saved, _rep = _averaged_run(tmp_path, stale=False)
    mine = created_stamp_for(run.measurement_ti3)
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        dates = [str(r.get("created")) for r in dlg._runs_for_document()]
        assert mine in dates, (
            "the averaged measurement (%s) has no row of its own; the window "
            "lists %r" % (mine, dates))
        assert str(dlg._report.get("created")) == mine, (
            "the window is about %s, not the measurement it was opened on (%s)"
            % (dlg._report.get("created"), mine))
    finally:
        dlg.close()


def test_generate_would_file_about_the_averaged_sheet(tmp_path, qapp):
    """…and the button acts on the same answer. Filing a report stamped with
    this window's limits about a sheet the reader is not looking at is the
    consequence B8-208 was found for.

    MUTATION: remove BOTH the `facts_disagree` call and the `reads/` test and
    this goes red, naming the saved report's date.
    """
    from workflow.measurement_report import created_stamp_for
    s, run, saved, _rep = _averaged_run(tmp_path, stale=False)
    mine = created_stamp_for(run.measurement_ti3)
    dlg = _window_on(s, run.measurement_ti3, qapp)
    try:
        about = [str(g.get("created")) for g in dlg._reports_to_generate()]
        assert about == [mine], (
            "Generate report would file about %r, not the measurement in hand "
            "(%s)" % (about, mine))
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# the rule itself, from both ends
# ---------------------------------------------------------------------------


def _two_sheets(tmp_path):
    """Two readings of one chart that a reader can actually tell apart.

    `_folder` scales the RED channel only, and `_cgats` derives XYZ_Y from
    GREEN, so its sheets share a paper white L* to the last decimal — the
    control caught it. Every channel is scaled here, which is what
    `_measure_again` does and for the same recorded reason.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    run = tmp_path / "runs" / "run1"
    run.mkdir(parents=True)
    for name, factor in (("a.ti3", 1.0), ("b.ti3", 0.90)):
        (run / name).write_text(
            _cgats("CTI3", [(r * factor, g * factor, b * factor)
                            for r, g, b in _PATCHES]), encoding="utf-8")
    return run


def test_the_file_itself_tells_two_sheets_apart(tmp_path):
    """`facts_disagree` is the identity, asked of the FILE.

    MUTATION: compare nothing (return False unconditionally) and this goes red.
    """
    from workflow.measurement_report import build_report, facts_disagree
    run = _two_sheets(tmp_path)
    rep_a = build_report(run / "a.ti3")
    assert facts_disagree(rep_a, run / "a.ti3") is False, \
        "a report disagreed with the very file it was built from"
    assert facts_disagree(rep_a, run / "b.ti3") is True, \
        "two different sheets were called the same measurement"


def test_a_different_number_of_readings_is_a_different_measurement(tmp_path):
    """The other half of what a report records about its measurement, and the
    half that carries a real disk: one run's saved reports there describe
    sheets of 15, 60, 105 and 315 readings under one file name.

    MUTATION: drop the patch-count comparison from `facts_disagree` and this
    goes red.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.measurement_report import build_report, facts_disagree
    run = _two_sheets(tmp_path)
    short = run / "short.ti3"
    short.write_text(_cgats("CTI3", _PATCHES[:-2]), encoding="utf-8")
    full = build_report(run / "a.ti3")
    # the control: these two differ ONLY in how many readings they hold
    from workflow.measurement_report import measurement_facts
    assert measurement_facts(short)["paper_white"] == full["paper_white"], (
        "the control failed: the short sheet has a different paper white too, "
        "so this says nothing about the patch count")
    assert facts_disagree(full, short) is True


def test_facts_disagree_reads_a_report_of_every_schema_on_disk(tmp_path):
    """Schema 5 wrote ``paper_white`` as ``{"L":…, "a":…, "b":…}``; 6 and 7
    write ``{"loc":…, "lab":[L,a,b], …}``. Both are on a real disk (6 at
    schema 5, 19 at 6, 33 at 7, surveyed 2026-09-15), and a reader that knows
    one shape silently answers "I cannot tell" for the other.

    MUTATION: drop the ``{"L": …}`` branch of `_point_L` and this goes red.
    """
    from workflow.measurement_report import build_report, facts_disagree
    run = _two_sheets(tmp_path)
    a = build_report(run / "a.ti3")
    white_a = float(a["paper_white"]["lab"][0])
    old_shape = {"patches": a["patches"],
                 "paper_white": {"L": round(white_a, 1), "a": 0.0, "b": 0.0}}
    assert facts_disagree(old_shape, run / "a.ti3") is False
    assert facts_disagree(old_shape, run / "b.ti3") is True


def test_measurement_facts_is_the_rule_build_report_writes(tmp_path):
    """ONE RULE, TWO CALLERS. The reader of a report's record of its own
    measurement must not compute those numbers a second way; that is the drift
    `created_stamp_for` was lifted out to prevent, and this is the same shape.

    MUTATION: have `build_report` compute its own `paper_white` again, by any
    rule at all that is not this one, and this goes red.
    """
    from workflow.measurement_report import build_report, measurement_facts
    run = _two_sheets(tmp_path)
    rep = build_report(run / "a.ti3")
    facts = measurement_facts(run / "a.ti3")
    for key in ("patches", "paper_white", "max_black"):
        assert rep[key] == facts[key], (
            "build_report and measurement_facts disagree about %r: %r vs %r"
            % (key, rep[key], facts[key]))
    # …and the coupling is what makes `facts_disagree` safe to use on a report
    # this builder wrote: a report never disagrees with its own measurement.
    from workflow.measurement_report import facts_disagree
    assert facts_disagree(rep, run / "a.ti3") is False


def test_the_lightest_reading_is_the_paper_and_the_darkest_is_the_black(
        tmp_path):
    """`lightest_and_darkest` is asked TWICE inside `build_report` — once for
    the paper-white and max-black block, and once by the media-relative
    yardstick, which divides every reading by the paper white's XYZ. Lifting
    the first use into `measurement_facts` took away the local the second one
    had been reading, and three tests went red with a `NameError`; it is one
    function now so the two cannot answer differently.

    MUTATION: swap the two indices and this goes red.
    """
    from workflow.ti3_analysis import parse_ti3, xyz_to_lab
    from workflow.measurement_report import (build_report,
                                             lightest_and_darkest)
    run = _two_sheets(tmp_path)
    data = parse_ti3(run / "a.ti3")
    lab = [xyz_to_lab((x / 100.0, y / 100.0, z / 100.0)) for x, y, z in data.xyz]
    wi, bi = lightest_and_darkest(lab)
    Ls = [l[0] for l in lab]
    assert Ls[wi] == max(Ls) and Ls[bi] == min(Ls), (
        "lightest_and_darkest picked L* %.2f as the paper and %.2f as the "
        "black, out of %.2f..%.2f" % (Ls[wi], Ls[bi], min(Ls), max(Ls)))
    rep = build_report(run / "a.ti3")
    assert float(rep["paper_white"]["lab"][0]) == round(max(Ls), 2)
    assert float(rep["max_black"]["lab"][0]) == round(min(Ls), 2)
    assert lightest_and_darkest([]) is None


def test_a_measurement_that_cannot_be_read_is_not_evidence(tmp_path):
    """"I cannot tell" must never be read as "it is a different measurement".
    That is the shape that took the accuracy block off every dated
    verification once already (B8-206).

    MUTATION: let `facts_disagree` answer True when the file cannot be parsed
    and this goes red.
    """
    from workflow.measurement_report import facts_disagree
    run = _two_sheets(tmp_path)
    (run / "junk.ti3").write_text("not a CGATS file at all", encoding="utf-8")
    rep = {"patches": 240, "paper_white": {"L": 95.4}}
    assert facts_disagree(rep, run / "junk.ti3") is False
    assert facts_disagree(rep, run / "missing.ti3") is False
    assert facts_disagree({}, run / "a.ti3") is False


def test_a_reads_folder_says_the_run_has_held_another_measurement(tmp_path):
    """The folder half of the same door, for a report too old to record
    anything the file can be asked about. `reads/readN.ti3` is what
    `Run.promote_measurement_to_read` leaves behind, and it belongs in the
    enumeration beside `old/<when>/`.

    MUTATION: drop the `reads/` check and this goes red.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import created_stamp_for
    run = _folder(tmp_path, ["chart.ti3", "reads/read1.ti3"],
                  [time.time(), time.time() - 9000])
    was = created_stamp_for(run / "reads" / "read1.ti3")
    assert was != created_stamp_for(run / "chart.ti3")
    # a report that records nothing comparable: the file cannot settle it
    assert MeasurementReportDialog._measurement_for(
        {"created": was, "ti3": "chart.ti3"}, run, run / "chart.ti3") is None


def test_a_dated_verification_is_still_rebuilt_from_the_file_in_its_folder(
        tmp_path):
    """B8-206 MUST STAY FIXED. A dated verification folder holds exactly one
    measurement, and the demo package's stub report in it records a patch
    count and a paper white that are not that sheet's. Asking the file there
    would empty the two rows a tester reads out of the demo package.

    MUTATION: apply `facts_disagree` in a `verifications/<date>/` folder too
    and this goes red.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from core.file_manager import VERIFICATIONS_DIRNAME
    dated = tmp_path / "runs" / "run2" / VERIFICATIONS_DIRNAME / "2026-05-20_090500"
    dated.mkdir(parents=True)
    from tests.test_import_measurement_module import _cgats, _PATCHES
    ti3 = dated / "demo-verify.ti3"
    ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    stub = {"created": "2026-05-20T09:05:00", "ti3": "demo-verify.ti3",
            "patches": 240, "schema": 5,
            "paper_white": {"L": 95.4, "a": 0.8, "b": -2.1}}
    # the control: the stub really does contradict the sheet in the folder
    from workflow.measurement_report import facts_disagree
    assert facts_disagree(stub, ti3) is True
    assert MeasurementReportDialog._measurement_for(stub, dated, ti3) == ti3, (
        "the dated verification's own measurement was refused, which is the "
        "failure B8-206 records")
