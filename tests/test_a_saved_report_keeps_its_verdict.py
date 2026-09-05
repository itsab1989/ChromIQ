"""A saved measurement report keeps the verdict it was given.

The Pass thresholds are a GLOBAL setting — `report_pass_threshold_avg` and
`report_pass_threshold_max` in `core/settings.py` — re-read every time the
Measurement Report window is built. A saved report stored neither the
thresholds it had been judged with nor the verdict it was given, and
`accuracy_verdict` ran at DISPLAY time. So nudging one spin box silently
re-graded every historical report the user had ever made: a run recorded as
Pass in March read Fail in September, with nothing on the page to say why or
that anything had changed.

A dated record that changes its own verdict after the fact is not a record.

Knut, #182, 2026-09-04: *"Verdict should be saved for each dated run."*

That, and only that, is what these tests pin. The wider #182 design — a
thresholds window, compliance presets, thresholds bound to a verification run —
is still being ruled on and none of it is here.

Three things have to hold together:

1. a report saved from now on carries `pass_thresholds` and `verdict`;
2. the window shows THOSE, and the spin boxes cannot move them;
3. a report saved before this existed is left exactly as it lies on disk, is
   still graded live so the feature is not deleted from every report the user
   owns — and SAYS SO, so it cannot claim in silence to have been judged by
   numbers set years later.
"""
from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.settings import AppSettings                     # noqa: E402
from workflow import measurement_report as mr             # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _report(**over) -> dict:
    """A report whose five graded metrics all sit at 2.5 ΔE00 — between the
    2.0 default average threshold (so: Fail) and the 3.0 maximum (so: Pass).
    One number, and moving either threshold flips a different half of the
    table, which is what makes a re-grade visible at all."""
    r = {
        "schema": mr.REPORT_SCHEMA,
        "created": "2026-03-01T10:00:00",
        "chart": "P",
        "ti3": "P.ti3",
        "patches": 100,
        "de00": {"avg_all": 2.5, "avg_low95": 2.5, "avg_high5": 2.5,
                 "max_all": 2.5, "max_low95": 2.5, "std": 0.4},
    }
    r.update(over)
    return r


# --------------------------------------------------------------------------
# 1. What is written
# --------------------------------------------------------------------------
def test_stamping_records_the_thresholds_and_the_verdict():
    r = mr.stamp_verdict(_report(), 2.0, 3.0)
    assert r["pass_thresholds"] == {"avg": 2.0, "max": 3.0}
    v = r["verdict"]
    assert {row["key"] for row in v["rows"]} == {k for k, _ in mr.ACCURACY_METRICS}
    # 2.5 fails the 2.0 average threshold and passes the 3.0 maximum one.
    by_key = {row["key"]: row for row in v["rows"]}
    assert by_key["avg_all"]["pass"] is False
    assert by_key["max_all"]["pass"] is True
    assert v["all_pass"] is False
    assert v["source"] == mr.VERDICT_SOURCE_ALL
    assert v["graded"] is True


def test_the_verdict_is_stamped_before_it_is_saved_not_after():
    """THE GUARD on the ordering. A report stamped after `save_report` would
    put the verdict in memory and leave the file on disk exactly as broken as
    before — and every test above would still be green."""
    src = inspect.getsource(
        __import__("ui.tabs.tab_measure", fromlist=["TabMeasure"])
        .TabMeasure._maybe_save_measurement_report)
    assert "stamp_verdict" in src, \
        "the Measure tab saves a report without recording its verdict"
    assert src.index("stamp_verdict(") < src.index("save_report("), \
        "the verdict is stamped after the file is written, so the file has none"


def test_the_thresholds_come_from_the_settings_not_the_module_defaults():
    """The user's configured thresholds are what the measurement was judged
    against. Falling back to 2.0/3.0 would record a verdict nobody asked for."""
    src = inspect.getsource(
        __import__("ui.tabs.tab_measure", fromlist=["TabMeasure"])
        .TabMeasure._maybe_save_measurement_report)
    assert "report_pass_threshold_avg" in src
    assert "report_pass_threshold_max" in src


def test_a_gamut_split_is_judged_on_its_within_gamut_figures():
    """Knut, 2026-08-10: colours the profile could never print are not counted
    against it. The STORED verdict has to make the same choice the window makes,
    or the record and the display disagree about the same sheet."""
    r = _report(gamut_split={"de00_in": {"avg_all": 1.0, "avg_low95": 1.0,
                                         "avg_high5": 1.0, "max_all": 1.0,
                                         "max_low95": 1.0},
                             "de00_out": {"avg_all": 9.0}})
    mr.stamp_verdict(r, 2.0, 3.0)
    assert r["verdict"]["source"] == mr.VERDICT_SOURCE_IN_GAMUT
    assert r["verdict"]["all_pass"] is True


def test_a_raw_drift_check_records_no_pass_or_fail():
    """A sheet printed raw is a drift check, not an accuracy check. `None` says
    that; `False` would record a failure that was never claimed."""
    r = _report(is_verification=True, reference_source="design",
                printing={"colour": "raw"})
    mr.stamp_verdict(r, 2.0, 3.0)
    assert r["verdict"]["graded"] is False
    assert r["verdict"]["all_pass"] is None


def test_a_report_with_no_reference_records_no_verdict_either():
    r = _report()
    r.pop("de00")
    mr.stamp_verdict(r, 2.0, 3.0)
    assert r["verdict"]["source"] == mr.VERDICT_SOURCE_NONE
    assert r["verdict"]["all_pass"] is None
    assert all(row["pass"] is None for row in r["verdict"]["rows"])


def test_a_stamped_report_survives_a_round_trip_through_json(tmp_path):
    p = mr.save_report(mr.stamp_verdict(_report(), 1.5, 2.5), tmp_path)
    back = json.loads(p.read_text(encoding="utf-8"))
    assert back["pass_thresholds"] == {"avg": 1.5, "max": 2.5}
    assert back["verdict"]["all_pass"] is False


# --------------------------------------------------------------------------
# 2. Nothing already on disk is touched
# --------------------------------------------------------------------------
def test_the_schema_is_not_bumped():
    """A bump makes the window treat EVERY saved report as stale and rebuild it
    from the run's .ti3 — which is the re-grading this whole fix is about, done
    wholesale. The new keys are optional and detected by their absence instead.
    """
    assert mr.REPORT_SCHEMA == 7


def test_an_old_report_is_read_without_being_rewritten(tmp_path):
    """CLAUDE.md principle 4: nothing the user created is destroyed or
    rewritten. Reading an old report must not put a verdict into it."""
    p = tmp_path / "reports" / "report_old.json"
    p.parent.mkdir(parents=True)
    original = json.dumps(_report(), indent=2)
    p.write_text(original, encoding="utf-8")
    rep = json.loads(p.read_text(encoding="utf-8"))
    assert mr.recorded_verdict(rep) is None
    assert mr.recorded_thresholds(rep) is None
    assert p.read_text(encoding="utf-8") == original


def test_a_damaged_verdict_block_reads_as_no_verdict_not_as_a_crash():
    for bad in ({}, {"verdict": None}, {"verdict": {}},
                {"verdict": {"rows": "yes"}}, {"verdict": []}):
        assert mr.recorded_verdict(bad) is None
    for bad in ({}, {"pass_thresholds": None}, {"pass_thresholds": {}},
                {"pass_thresholds": {"avg": "two", "max": 3}}):
        assert mr.recorded_thresholds(bad) is None


# --------------------------------------------------------------------------
# 3. What the window shows
# --------------------------------------------------------------------------
def _dialog(qapp, tmp_path, avg=2.0, mx=3.0):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("report_pass_threshold_avg", avg)
    s.set("report_pass_threshold_max", mx)
    return MeasurementReportDialog(s, None)


def test_the_window_shows_the_recorded_verdict_not_todays(qapp, tmp_path):
    """THE GUARD. The report was judged Fail on its average at 2.0. The window
    now opens with the thresholds loosened to 9.0, which would grade the same
    numbers Pass — and must not."""
    saved = mr.stamp_verdict(_report(), 2.0, 3.0)
    dlg = _dialog(qapp, tmp_path, avg=9.0, mx=9.0)
    try:
        rows, recorded = dlg._verdict_rows(saved)
        assert recorded is True
        assert {r["key"]: r["pass"] for r in rows}["avg_all"] is False
    finally:
        dlg.deleteLater()


def test_moving_a_spin_box_does_not_move_a_recorded_verdict(qapp, tmp_path):
    """The complaint, driven end to end: the same report object, the window's
    thresholds changed underneath it, the verdict unchanged."""
    saved = mr.stamp_verdict(_report(), 2.0, 3.0)
    dlg = _dialog(qapp, tmp_path)
    try:
        before = dlg._report_results_html([saved])
        dlg._avg_thr_spin.setValue(9.0)
        dlg._max_thr_spin.setValue(9.0)
        after = dlg._report_results_html([saved])
        assert before == after, \
            "the saved report was re-graded when a threshold moved"
        # …and the grid says what it was judged against, so a reader can tell
        # a recorded verdict from a live one without opening the file.
        assert "2.0 / 3.0" in after
    finally:
        dlg.deleteLater()


def test_a_report_with_no_recorded_verdict_is_still_graded_and_says_so(
        qapp, tmp_path):
    """Blanking every historical report would delete a working feature from
    every file the user owns. It is graded live — and the page says the numbers
    are today's, not the ones in force when the sheet was measured."""
    old = _report()
    dlg = _dialog(qapp, tmp_path)
    try:
        rows, recorded = dlg._verdict_rows(old)
        assert recorded is False
        assert {r["key"]: r["pass"] for r in rows}["avg_all"] is False
        html = dlg._report_results_html([old])
        assert "not recorded" in html
        note = dlg._verdict_provenance(old, recorded)
        assert "Nothing is wrong with this report" in note and "2.0" in note
    finally:
        dlg.deleteLater()


def test_an_old_report_is_re_graded_when_a_spin_box_moves(qapp, tmp_path):
    """The other side of the same coin, pinned deliberately: for a report that
    carries no verdict the spin boxes still work, because that is all there is.
    If this ever stops being true it is a decision, not a drift."""
    old = _report()
    dlg = _dialog(qapp, tmp_path)
    try:
        assert {r["key"]: r["pass"]
                for r in dlg._verdict_rows(old)[0]}["avg_all"] is False
        dlg._avg_thr_spin.setValue(9.0)
        assert {r["key"]: r["pass"]
                for r in dlg._verdict_rows(old)[0]}["avg_all"] is True
    finally:
        dlg.deleteLater()


def test_the_recorded_thresholds_are_the_ones_printed_in_the_detail_table(
        qapp, tmp_path):
    """The Threshold column of a run's own accuracy table is part of the
    record: 2.0 and 3.0, whatever the window is set to now."""
    saved = mr.stamp_verdict(_report(), 2.0, 3.0)
    dlg = _dialog(qapp, tmp_path, avg=9.0, mx=9.0)
    try:
        html = dlg._run_detail_html(saved)
        assert "9.0" not in html, "the detail table used today's thresholds"
        assert "recorded when the report was saved" in html
    finally:
        dlg.deleteLater()


_TI2 = """CTI1

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 3
BEGIN_DATA
1 "A1" 100 100 100 95.0 100.0 108.0
2 "A2" 0 0 0 1.0 1.0 1.0
3 "A3" 100 0 0 41.0 21.0 2.0
END_DATA
"""
_TI3 = _TI2.replace("CTI1", "CTI3").replace("41.0 21.0 2.0", "36.0 18.0 3.0")


def test_a_stale_rebuild_carries_the_recorded_verdict_across(qapp, tmp_path):
    """`_gather_runs` rebuilds a report whose schema predates the current one,
    keeping only its date. That rebuild recomputes today's STATISTICS from the
    same measurement, which is right — and it must not recompute the
    JUDGEMENT, or the fix has a hole in it exactly where the oldest reports
    are. Driven through the real gather, not read off the source."""
    run = tmp_path / "runs" / "run1"
    (run / "reports").mkdir(parents=True)
    (run / "c.ti2").write_text(_TI2, encoding="utf-8")
    (run / "c.ti3").write_text(_TI3, encoding="utf-8")
    old = {"schema": 2, "created": "2026-01-02T10:00:00", "chart": "c",
           "patches": 3,
           "de00": {"n": 3, "mean": 4.2, "median": 4.0, "min": 0.1, "max": 8.0}}
    mr.stamp_verdict(old, 2.0, 3.0)
    (run / "reports" / "report_2026-01-02_10-00-00.json").write_text(
        json.dumps(old), encoding="utf-8")

    dlg = _dialog(qapp, tmp_path, avg=9.0, mx=9.0)
    try:
        _name, runs = dlg._gather_runs(run / "c.ti3")
        assert len(runs) == 1
        rebuilt = runs[0]
        # It WAS rebuilt — the stale de00 had no avg_all and now does…
        assert (rebuilt.get("de00") or {}).get("avg_all") is not None
        # …and the judgement it was given came across untouched.
        assert mr.recorded_thresholds(rebuilt) == (2.0, 3.0)
        assert dlg._verdict_rows(rebuilt)[1] is True
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------------------
# Basti's standing rule: "friendly, extensive, easy to understand and correct"
# --------------------------------------------------------------------------
def test_an_unrecorded_verdict_does_not_read_as_a_fault(qapp, tmp_path):
    """"not recorded" must not look like an error or like missing data. The
    page has to say, in as many words, that nothing is wrong — otherwise the
    honest label becomes a new worry."""
    dlg = _dialog(qapp, tmp_path)
    try:
        note = dlg._verdict_provenance(_report(), recorded=False)
        assert "Nothing is wrong with this report" in note
        assert "did not yet keep the verdict" in note
        # …and it must not read as a fresh verdict either: it says the numbers
        # are today's and that moving the thresholds moves them.
        assert "changing those thresholds will change them" in note
        grid = dlg._report_results_html([_report()])
        assert "is not a fault" in grid
    finally:
        dlg.deleteLater()


def test_a_recorded_verdict_says_plainly_that_the_spin_boxes_cannot_move_it(
        qapp, tmp_path):
    dlg = _dialog(qapp, tmp_path)
    try:
        note = dlg._verdict_provenance(
            mr.stamp_verdict(_report(), 2.0, 3.0), recorded=True)
        assert "recorded when the report was saved" in note
        assert "do not change it" in note
        assert "2.0" in note and "3.0" in note
    finally:
        dlg.deleteLater()


def test_both_footnotes_survive_each_other(qapp, tmp_path):
    """A report can hold a raw-drift sheet AND a column with no recorded
    verdict. The first draft of this block ASSIGNED the drift note where it
    should have appended, so whichever came second silently deleted the other.
    """
    drift = _report(created="2026-04-01T10:00:00", is_verification=True,
                    reference_source="design", printing={"colour": "raw"})
    dlg = _dialog(qapp, tmp_path)
    try:
        html = dlg._report_results_html([_report(), drift])
        assert "Columns marked" in html, "the drift note was lost"
        assert "is not a fault" in html, "the unrecorded-verdict note was lost"
    finally:
        dlg.deleteLater()


def test_the_window_and_the_record_share_one_drift_rule():
    """Two copies of "is this sheet graded at all" would eventually disagree,
    and then a report would carry a verdict the window refuses to show."""
    from ui.dialogs import measurement_report_dialog as d
    r = _report(is_verification=True, reference_source="design",
                printing={"colour": "raw"})
    assert d._is_raw_drift(r) is True
    assert mr.is_drift_check(r) is True
    assert "is_drift_check" in inspect.getsource(d._is_raw_drift)
