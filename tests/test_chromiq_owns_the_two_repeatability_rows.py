"""ChromIQ's own two repeatability rows (#182, B8-660 / B8-661).

Every other numeric row in the Report limits table comes from a document
somebody else wrote. These two do not: they are computed from the user's own
measurements of the user's own prints, no standard defines them, nobody
licenses them, and they can be judged for a printer user who holds no
document at all.

So these tests hold two things that are easy to lose:

* the rows ARE judged, and refused with a reason a reader can act on when the
  chart or the history cannot supply them;
* nothing about them claims a standard, and the standard's own repeatability
  row is left exactly as it was.
"""
from pathlib import Path

import pytest

from workflow import compliance_sets as cs
from workflow import measurement_report as mr
from workflow import ti3_analysis as ta

ROW_A = "repeat_patches_de00_max"
ROW_B = "repeat_measurement_de00_max"


# ---------------------------------------------------------------------------
# fixtures: real .ti3 files on disk, because both rows read files
# ---------------------------------------------------------------------------
def _ti3(rows: "list[tuple[str, tuple, tuple]]") -> str:
    """A CGATS .ti3 of ``(sample_id, (r, g, b), (x, y, z))`` rows."""
    out = [
        "CTI3", "", 'DESCRIPTOR "Argyll Calibration Target chart information 3"',
        'ORIGINATOR "Argyll chartread"',
        'KEYWORD "DEVICE_CLASS"', 'DEVICE_CLASS "OUTPUT"',
        'KEYWORD "COLOR_REP"', 'COLOR_REP "RGB_XYZ"',
        "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
        f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA",
    ]
    for sid, (r, g, b), (x, y, z) in rows:
        out.append(f"{sid} {r:.4f} {g:.4f} {b:.4f} {x:.4f} {y:.4f} {z:.4f}")
    out += ["END_DATA", ""]
    return "\n".join(out)


def _plain_rows(n: int, *, shift: float = 0.0, devices=None):
    """*n* ordinary patches, each a different device colour."""
    rows = []
    for i in range(n):
        v = 5.0 + (i * 90.0) / max(1, n - 1)
        dev = devices(i) if devices else (v, v, v)
        rows.append((f"P{i + 1}", dev, (v + shift, v + shift, v + shift)))
    return rows


def _write(p: Path, rows) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_ti3(rows), encoding="utf-8")
    return p


def _values(ti3: Path) -> dict:
    return mr.row_values(mr.build_report(ti3))


# ---------------------------------------------------------------------------
# Row A — repeat patches within one sheet
# ---------------------------------------------------------------------------
def test_row_a_is_judged_when_the_sheet_repeats_two_colours(tmp_path):
    """Two groups, and the row reports the worst pair of them, in ΔE00."""
    rows = _plain_rows(20)
    # paper repeated, and black repeated, which is what a real chart does
    rows += [("W1", (100.0, 100.0, 100.0), (95.0, 100.0, 108.0)),
             ("W2", (100.0, 100.0, 100.0), (94.0, 99.0, 107.0)),
             ("K1", (0.0, 0.0, 0.0), (2.0, 2.0, 2.0)),
             ("K2", (0.0, 0.0, 0.0), (2.4, 2.4, 2.4))]
    t3 = _write(tmp_path / "sheet.ti3", rows)
    rep = mr.build_report(t3)
    block = rep["repeat_within_sheet"]
    assert block["eligible"] is True and block["reason"] is None
    assert block["n_groups"] == 2
    assert block["n_comparisons"] == 2          # one pair in each group
    assert block["max"] > 0.0
    cell = mr.row_values(rep)[ROW_A]
    assert cell["value"] == block["max"] and cell["reason"] is None


def test_row_a_is_refused_when_the_chart_repeats_nothing(tmp_path):
    """A chart that never asks for the same colour twice cannot answer it, and
    the reason says which of the two shortfalls it is."""
    t3 = _write(tmp_path / "sheet.ti3", _plain_rows(30))
    rep = mr.build_report(t3)
    assert rep["repeat_within_sheet"]["n_groups"] == 0
    cell = mr.row_values(rep)[ROW_A]
    assert cell["value"] is None
    assert cell["reason"] == mr.REASON_NO_REPEAT_PATCHES


def test_row_a_is_refused_when_the_sheet_repeats_only_one_colour(tmp_path):
    """ONE group is one colour, and the row is offered as a property of the
    SHEET. The refusal is its own code, because the thing to do about it is
    different from having no repeats at all."""
    rows = _plain_rows(20)
    rows += [("W1", (100.0, 100.0, 100.0), (95.0, 100.0, 108.0)),
             ("W2", (100.0, 100.0, 100.0), (94.0, 99.0, 107.0))]
    t3 = _write(tmp_path / "sheet.ti3", rows)
    rep = mr.build_report(t3)
    assert rep["repeat_within_sheet"]["n_groups"] == 1
    cell = mr.row_values(rep)[ROW_A]
    assert cell["value"] is None
    assert cell["reason"] == mr.REASON_TOO_FEW_REPEAT_GROUPS


def test_row_a_needs_no_reference_values_at_all(tmp_path):
    """THE POINT OF THE ROW. It compares the sheet's repeats with EACH OTHER,
    so it is answerable where every reference row is not."""
    rows = _plain_rows(20)
    rows += [("W1", (100.0, 100.0, 100.0), (95.0, 100.0, 108.0)),
             ("W2", (100.0, 100.0, 100.0), (94.0, 99.0, 107.0)),
             ("K1", (0.0, 0.0, 0.0), (2.0, 2.0, 2.0)),
             ("K2", (0.0, 0.0, 0.0), (2.4, 2.4, 2.4))]
    t3 = _write(tmp_path / "sheet.ti3", rows)          # no sibling .ti2
    vals = _values(t3)
    assert vals["substrate_de00_max"]["reason"] == mr.REASON_NEEDS_REFERENCE_FILE
    assert vals[ROW_A]["value"] is not None


# ---------------------------------------------------------------------------
# Row B — the same chart measured again
# ---------------------------------------------------------------------------
def _verification(root: Path, date: str, rows) -> Path:
    return _write(root / "runs" / "run1" / "verifications" / date /
                  "Chart-verify.ti3", rows)


def test_row_b_is_refused_on_the_first_measurement(tmp_path):
    rows = _plain_rows(40)
    t3 = _verification(tmp_path, "2026-01-01_100000", rows)
    cell = _values(t3)[ROW_B]
    assert cell["value"] is None
    assert cell["reason"] == mr.REASON_NO_EARLIER_MEASUREMENT


def test_row_b_is_judged_from_the_second_measurement_onward(tmp_path):
    rows = _plain_rows(40)
    _verification(tmp_path, "2026-01-01_100000", rows)
    second = _verification(tmp_path, "2026-02-01_100000",
                           _plain_rows(40, shift=1.5))
    rep = mr.build_report(second)
    block = rep["repeat_across_sheets"]
    assert block["eligible"] is True and block["reason"] is None
    assert block["n_shared"] == 40
    assert block["compared_with"] == "2026-01-01_100000"
    assert mr.row_values(rep)[ROW_B]["value"] == block["max"] > 0.0


def test_row_b_compares_with_the_measurement_immediately_before_it(tmp_path):
    """NOT with the first of the series. Repeatability is the scatter between
    repeats; a worst-over-all-history would grow for ever and leave one bad
    day condemning every measurement after it.

    Three dates: the first far away, the second and third close together. The
    third must report the SMALL step, not the large one.
    """
    _verification(tmp_path, "2026-01-01_100000", _plain_rows(40))
    _verification(tmp_path, "2026-02-01_100000", _plain_rows(40, shift=9.0))
    third = _verification(tmp_path, "2026-03-01_100000",
                          _plain_rows(40, shift=9.3))
    rep = mr.build_report(third)
    assert rep["repeat_across_sheets"]["compared_with"] == "2026-02-01_100000"
    small = rep["repeat_across_sheets"]["max"]

    far = mr.build_report(
        Path(tmp_path / "runs/run1/verifications/2026-02-01_100000/"
                        "Chart-verify.ti3"))
    assert far["repeat_across_sheets"]["compared_with"] == "2026-01-01_100000"
    assert small < far["repeat_across_sheets"]["max"], (
        "the third date reported its distance from the FIRST measurement, "
        "which is drift from a baseline and not repeatability")


def test_row_b_refuses_a_chart_that_was_rebuilt_between_the_two_dates(tmp_path):
    """A patch counts only when both files agree what colour it was ASKED for.

    Otherwise a regenerated chart reads as the printer moving, which is the
    mispairing that produced a trend point of ΔE 41 on this project once.
    """
    _verification(tmp_path, "2026-01-01_100000", _plain_rows(40))
    # same sample ids, different device values: a different chart
    second = _verification(
        tmp_path, "2026-02-01_100000",
        _plain_rows(40, shift=1.5,
                    devices=lambda i: (99.0 - i, 99.0 - i, 99.0 - i)))
    rep = mr.build_report(second)
    assert rep["repeat_across_sheets"]["n_shared"] < mr.REPEAT_ACROSS_MIN_PATCHES
    cell = mr.row_values(rep)[ROW_B]
    assert cell["value"] is None
    assert cell["reason"] == mr.REASON_TOO_FEW_SHARED_PATCHES


def test_row_b_is_refused_on_a_sheet_that_is_in_no_dated_folder(tmp_path):
    """A file in Downloads has no series to be the second of."""
    t3 = _write(tmp_path / "loose.ti3", _plain_rows(40))
    assert _values(t3)[ROW_B]["reason"] == mr.REASON_NO_EARLIER_MEASUREMENT


# ---------------------------------------------------------------------------
# One definition of "a repeat patch" in the application
# ---------------------------------------------------------------------------
def test_device_repeat_groups_drops_singletons_and_keeps_chart_order():
    import numpy as np
    rgb = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [5.0, 5.0, 5.0],
                    [9.0, 9.0, 9.0], [9.0, 9.0, 9.0], [9.0, 9.0, 9.0]])
    assert [len(g) for g in ta.device_repeat_groups(rgb)] == [2, 3]


def test_the_report_and_the_ti3_info_window_group_repeats_the_same_way(
        tmp_path, monkeypatch):
    """`_duplicate_scatter` (Ti3 Info) and the report's row must not hold two
    definitions of the same population: two definitions are two numbers that
    can disagree on screen.

    **ASKED BEHAVIOURALLY, BECAUSE THE SOURCE-STRING VERSION OF THIS TEST WAS
    THEATRE.** It asserted that "device_repeat_groups" appears in the block's
    source, and a mutation that replaced the call with an inline grouping loop
    PASSED IT: the import line at the top of the function still carried the
    name. The mutation is run against this file, so the guard has to fail it.

    Both callers are given a grouping function that answers something only a
    shared implementation could produce, and both must report it.

    MUTATION: give `repeat_within_sheet_block` its own grouping loop and this
    goes red, because the block stops seeing the replacement.
    """
    import numpy as np
    rows = _plain_rows(20)
    rows += [("W1", (100.0, 100.0, 100.0), (95.0, 100.0, 108.0)),
             ("W2", (100.0, 100.0, 100.0), (94.0, 99.0, 107.0)),
             ("K1", (0.0, 0.0, 0.0), (2.0, 2.0, 2.0)),
             ("K2", (0.0, 0.0, 0.0), (2.4, 2.4, 2.4))]
    t3 = _write(tmp_path / "sheet.ti3", rows)
    assert mr.build_report(t3)["repeat_within_sheet"]["n_groups"] == 2

    # one group, and a group nothing in this chart could produce by device
    # value: only a caller that really asks the shared function can see it.
    monkeypatch.setattr(ta, "device_repeat_groups", lambda rgb: [[0, 1, 2]])
    assert mr.build_report(t3)["repeat_within_sheet"]["n_groups"] == 1, (
        "the report's row does not ask ti3_analysis.device_repeat_groups; it "
        "holds a second definition of what a repeat patch is")
    rgb = np.zeros((3, 3))
    assert ta._duplicate_scatter(rgb, np.zeros((3, 3)))[1] == 1, (
        "the Ti3 Info window's figure does not ask the shared function either")


# ---------------------------------------------------------------------------
# The help text promises the conditions the code applies
# ---------------------------------------------------------------------------
def test_the_repeatability_conditions_quote_the_real_thresholds():
    """The two numbers in the help icons are the two the report applies.

    MUTATION: change either constant without changing the sentence, or change
    either sentence's number, and this goes red, because the window would be
    promising a condition the report does not apply.
    """
    a = cs.ROW_BY_ID[ROW_A].detect
    assert f"at least {mr.REPEAT_WITHIN_MIN_GROUPS} such groups" in a
    assert ta.REPEAT_DEVICE_DECIMALS == 2
    assert "two decimal places" in a
    b = cs.ROW_BY_ID[ROW_B].detect
    assert f"At least {mr.REPEAT_ACROSS_MIN_PATCHES} patches" in b


def test_the_shared_patch_floor_is_the_five_per_cent_the_table_is_cut_at():
    """14 is not a taste. It is ``ceil(ln 0.5 / ln 0.95)``: the count at which
    the largest of what was read first has an even chance of having touched
    the worst twentieth of the chart, which is the same 5 % the best-95,
    worst-5 and 95th-percentile rows are cut at."""
    import math
    n = mr.REPEAT_ACROSS_MIN_PATCHES
    assert 0.95 ** n <= 0.5
    assert 0.95 ** (n - 1) > 0.5
    assert n == math.ceil(math.log(0.5) / math.log(0.95))


# ---------------------------------------------------------------------------
# …and nothing here claims a standard
# ---------------------------------------------------------------------------
def test_both_rows_say_in_their_own_words_that_they_are_chromiqs_own():
    for rid in (ROW_A, ROW_B):
        row = cs.ROW_BY_ID[rid]
        assert "ChromIQ's own" in row.detect, rid
        assert "No standard defines it" in row.detect, rid


def test_the_heading_over_them_names_chromiq_and_no_standard():
    heading = cs.GROUP_LABELS["repeatability"]
    assert heading == "Repeatability, measured by ChromIQ"
    for word in ("iso", "12647", "fogra", "standard"):
        assert word not in heading.lower(), heading


def test_neither_row_carries_a_number_in_a_read_only_iso_column():
    """THE CELL THAT WOULD BE THE FALSE ATTRIBUTION. Those two columns hold a
    standard's published values; no standard published these, so the honest
    cell is the one that says the set defines no limit here.

    MUTATION: add either row id to `_ISO_ROWS` and this goes red.
    """
    cs.reset_iso_cache()
    for sid in cs.ISO_SET_IDS:
        f = cs.factory_limits(sid)
        for rid in (ROW_A, ROW_B):
            assert f[rid].kind == "none", (sid, rid, f[rid])
            assert cs.limit_text(f[rid]) == "–"
        assert rid not in cs._ISO_ROWS[sid]


def test_the_standards_own_repeatability_row_is_untouched():
    """`repeatability_de00_max` is a standard's criterion over that standard's
    own timed protocol. Pointing it at a number ChromIQ can compute would be
    precisely the false attribution that has been removed from this window
    three times; these are NEW rows, and that one does not move.

    MUTATION: give `repeatability_de00_max` a status other than
    `unmeasurable`, or a `metric_key`, and this goes red.
    """
    row = cs.ROW_BY_ID["repeatability_de00_max"]
    assert row.status == "unmeasurable"
    assert row.group == "not_evaluated"
    assert row.note == "a timed protocol, not a property of one sheet"
    assert not row.detect and not row.remedy
    for sid in cs.SET_IDS:
        lim = cs.factory_limits(sid)["repeatability_de00_max"]
        assert not lim.is_numeric, (sid, lim)
    for parent in cs.ISO_SET_IDS:
        assert "repeatability_de00_max" not in cs.custom_defaults(parent)


def test_neither_new_row_steals_one_of_the_five_old_metric_keys():
    for rid in (ROW_A, ROW_B):
        assert cs.ROW_BY_ID[rid].metric_key is None, rid


def test_every_limit_set_that_carries_limits_judges_both_rows():
    """A row nothing judges is a row that arrives as decoration. Both rows
    carry a limit in every set that carries limits at all, and read "–" only
    in the two columns where "–" is the honest cell."""
    for sid in cs.SET_IDS:
        limits = cs.factory_limits(sid)
        if not cs.limit_bearing(limits):
            continue
        if sid in cs.ISO_SET_IDS:
            continue
        for rid in (ROW_A, ROW_B):
            assert limits[rid].is_numeric, (sid, rid)


def test_row_b_is_never_tighter_than_row_a():
    """Row B's population contains Row A's entirely and adds a second print
    and a second day, so its limit cannot be the tighter of the two."""
    for sid in cs.SET_IDS:
        limits = cs.factory_limits(sid)
        a, b = limits[ROW_A], limits[ROW_B]
        if not (a.is_numeric and b.is_numeric):
            continue
        assert b.number >= a.number, (sid, a.number, b.number)


# ---------------------------------------------------------------------------
# …and neither row demotes a column that was clean before it existed
# ---------------------------------------------------------------------------
def test_a_first_measurement_still_reads_pass_overall(tmp_path):
    """THE REGRESSION THESE ROWS WOULD OTHERWISE HAVE SHIPPED.

    `set_summary` demotes a column to COND when a REQUIRED row reads N-A. Row
    B is N-A on every FIRST measurement of a chart, which is the ordinary
    state of most reports anybody has, so without the carve-out a user who
    measured a verification sheet once and passed every accuracy limit would
    have read COND instead of PASS, for a question no single sheet can answer.

    MUTATION: remove either id from `compliance_sets.POPULATION_MAY_BE_ABSENT`,
    or drop the row id from the pairs `measurement_report.summarise` builds,
    and this goes red with COND.

    The demo projects cannot catch this: not one of their 60 measurements
    reads PASS overall under any set, so the before/after diff over the pack
    is silent here. This test is the detector.
    """
    # A FLAWLESS SHEET, built by the judging suite's own helper so the
    # measured values really do match the reference and every accuracy row
    # passes. Anything less and this test would prove nothing: the column has
    # to be clean BEFORE the two new rows arrive.
    from tests.test_report_judging import _colours, _ramp, _write_ti3
    t3 = _write_ti3(tmp_path / "v.ti3", _ramp(16) + _colours())
    rep = mr.build_report(t3)
    rep["printing"] = {"colour": "through-profile", "intent": "relative",
                       "route": "chromiq"}

    limits = cs.factory_limits("chromiq_default")
    judged = mr.judge(rep, limits)
    words = {r["row_id"]: r["word"] for r in judged}
    # the two new rows really are N-A here, or this proves nothing
    assert words[ROW_A] == cs.N_A and words[ROW_B] == cs.N_A
    assert not [w for w in words.values() if w == cs.FAIL], words

    s = mr.summarise(rep, limits, judged, "chromiq_default")
    assert s.word == cs.PASS, (
        f"a first measurement that failed nothing reads {s.word}; the two "
        "repeatability rows demoted a clean column")
    # …and the rows are still SHOWN and still counted as not computed, so
    # nothing is hidden from the reader: only the completeness arithmetic
    # leaves them out.
    assert s.not_computed >= 2
    assert ROW_A in words and ROW_B in words


def test_the_carve_out_is_exactly_two_rows_and_no_more():
    """A row joining this set is a column's completeness being weakened, so it
    is a deliberate act each time and never a drive-by."""
    assert cs.POPULATION_MAY_BE_ABSENT == {ROW_A, ROW_B}


def test_no_row_that_reads_na_demotes_the_column_any_more():
    """**THE CARVE-OUT IS GONE, BECAUSE KNUT MADE THE RULE GENERAL.**

    This test used to be the other half of the carve-out: it asked that an
    ORDINARY required row reading N-A still took the column to COND, so that
    the exemption for these two rows could be seen to be narrow. Asked the
    §15.5 question, Knut answered it on 2026-09-21 by widening it instead:

    > *"Not Applicable must not be counted as a fail, so the overall verdict
    > should show PASS, not COND, if all others pass. I say, a metric that is
    > not applicable should not have verdict conditional because COND does not
    > indicate which of the verdicts cause the COND … When all other metrics
    > PASS, that N-A is not applicable, thus not relevant for the verdict,
    > thus overall verdict becomes PASS (or FAIL if some metric fails)."*

    So the narrowness this guarded no longer exists to guard, and the test is
    turned round rather than deleted: the same three cases are asked for the
    answer the ruling gives. §15.6 of docs/design/measurement_report_limits.md
    records it, and the exempt set survives for two MESSAGES only (see
    `test_the_mismatch_strip_leaves_both_rows_out` below), never for a word.
    """
    v = cs.Limit.value(2.0)
    ordinary = cs.set_summary(
        [(v, cs.PASS, "all_de00_avg"), (v, cs.N_A, "grey_balance_neutral_ramp_avg")],
        set_is_iso=False, graded=True)
    assert ordinary.word == cs.PASS, (
        "an ordinary required row reading N-A demoted a clean column, which "
        "Knut ruled out on 2026-09-21")
    assert ordinary.not_computed == 1, "and the count is still reported"
    spared = cs.set_summary(
        [(v, cs.PASS, "all_de00_avg"), (v, cs.N_A, ROW_B)],
        set_is_iso=False, graded=True)
    assert spared.word == cs.PASS
    # a caller that passes plain pairs, with no row id to consult at all,
    # reaches the same answer: there is no row list left to consult.
    old_shape = cs.set_summary([(v, cs.PASS), (v, cs.N_A)],
                               set_is_iso=False, graded=True)
    assert old_shape.word == cs.PASS
    # …AND A FAIL STILL FAILS, which is the half of his ruling that is easy to
    # drop: "or FAIL if some metric fails".
    failed = cs.set_summary(
        [(v, cs.PASS, "all_de00_avg"), (v, cs.N_A, ROW_B),
         (v, cs.FAIL, "all_de00_max")], set_is_iso=False, graded=True)
    assert failed.word == cs.FAIL


def test_the_preset_window_does_not_ask_either_row():
    """**THE SAME SET GOVERNS ALL THREE SURFACES.** The preset window exists
    to help a user CHOOSE between charts, and neither row can do that: "has
    this chart been measured before" is not a property of a chart at all, and
    every one of the twenty-six charts in the demo pack is designed patch by
    patch with no repeated device value, so asking would mark all of them down
    for the same two rows.

    So `rows_asked` filters them out through the same
    `POPULATION_MAY_BE_ABSENT` the column summary and the mismatch strip use,
    and their four reason codes must NOT be classified in this module: a code
    `classified_reasons` claims but nothing can produce is a sentence nobody
    reads, and the pack's coverage guard would demand a preset pair for a
    boundary no preset can cross.

    MUTATION: drop the `POPULATION_MAY_BE_ABSENT` filter from `rows_asked` and
    this goes red.
    """
    from workflow import preset_eligibility as pe
    asked = pe.rows_asked(mr.REPORT_TYPE_FULL, "chromiq_default")
    assert asked, "the everyday combination asks a chart for nothing at all"
    for rid in (ROW_A, ROW_B):
        assert rid not in asked, rid
    for code in (mr.REASON_NO_REPEAT_PATCHES,
                 mr.REASON_TOO_FEW_REPEAT_GROUPS,
                 mr.REASON_NO_EARLIER_MEASUREMENT,
                 mr.REASON_TOO_FEW_SHARED_PATCHES):
        assert code not in pe.classified_reasons(), code


def test_the_mismatch_strip_never_names_a_row_it_cannot_advise_on():
    """The strip's message tells the reader to add patches in Create Chart,
    print the chart again and measure it. That sentence is false for a row
    that asks whether the chart has been measured twice, so the strip is built
    from the same set as everything else.

    MUTATION: drop the `POPULATION_MAY_BE_ABSENT` clause from
    `_mismatch_text` and `tests/test_report_window_limit_controls.py::
    test_a_full_chart_shows_no_strip` goes red.
    """
    import inspect
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = inspect.getsource(MeasurementReportDialog._mismatch_text)
    assert "POPULATION_MAY_BE_ABSENT" in src
