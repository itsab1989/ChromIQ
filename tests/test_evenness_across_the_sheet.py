"""Maximum ΔE00, between two of the nine sheet areas (#182, Knut, 2026-09-22; B8-814).

Knut's rulings (issue comment 5785774676), each held here by behaviour:

1. every patch against its own aim, averaged per area, no matching by grey or
   brightness;
2. three by three areas per page by the patches' positions, whole strips and
   rows, remainder to the MIDDLE band, every page pooled;
3. "nine locations" = the largest ΔE00 between two areas, "largest difference
   from the mean" = the largest ΔE00 between an area and the mean of the nine;
4. 1.5 and 1.0 in ChromIQ's own default set;
5. at least 9 strips and 9 rows on a page, else N-A with the reason;
6. no verdict while the sheet's own noise (shuffled, fixed seed) is not below
   the limit;
7. the likely causes as a note on every evenness verdict;
8. the presets window and the pre-flight answer by the report's own rule.

Every test names the mutation it was run against. The charts are synthetic and
written here: a `.ti2` whose `SAMPLE_LOC` puts each patch on a known strip and
row, and a `.ti3` whose readings are the chart's own aims plus a residual this
file chooses, so what each area should read is known before the report runs.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import compliance_sets as CS                     # noqa: E402
from workflow import measurement_report as MR                  # noqa: E402
from workflow import preset_eligibility as PE                  # noqa: E402
from workflow.layout_engine.permutation import alpha_label     # noqa: E402
from workflow.ti3_analysis import _lab_to_xyz_array            # noqa: E402

PAIR, FROM_MEAN = "uniformity_sd", "uniformity_de00_max_from_mean"
DEFAULT = CS.effective_limits("chromiq_default", None)


# ---------------------------------------------------------------------------
# a chart and a sheet this file controls
# ---------------------------------------------------------------------------
def _write_chart(folder: Path, pages=(12,), rows=12, seed=3,
                 stem="chart", coverage=0.85) -> "tuple[Path, list]":
    """A laid-out `.ti2`: *pages* strips per page, *rows* rows, every slot
    filled, patches shuffled over the slots so that id order says nothing
    about position. Returns the path and ``[(sid, page, strip, row, rgb)]``.

    *coverage* is the share of each page the patch block covers, written
    beside the chart as a derived geometry (#182 E2), or None for a chart
    whose files do not say where its patches sit."""
    rng = np.random.default_rng(seed)
    n = int(sum(pages)) * rows
    slots = rng.permutation(n)
    starts = np.cumsum([0] + list(pages))
    rgb = rng.uniform(5, 95, (n, 3)).round(2)
    xyz = _lab_to_xyz_array(np.column_stack([
        30 + 0.6 * rgb[:, 1], rgb[:, 0] - 50, rgb[:, 2] - 50]))
    lines = ["CTI2", "", 'DESCRIPTOR "evenness test"', 'ORIGINATOR "test"',
             f'STEPS_IN_PASS "{rows}"',
             f'PASSES_IN_STRIPS2 "{",".join(str(p) for p in pages)}"',
             'STRIP_INDEX_PATTERN "A-Z, A-Z"',
             'PATCH_INDEX_PATTERN "0-9,@-9,@-9;1-999"',
             'INDEX_ORDER "STRIP_THEN_PATCH"', "",
             "NUMBER_OF_FIELDS 8", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    where = []
    for i in range(n):
        s, r = divmod(int(slots[i]), rows)
        page = int(np.searchsorted(starts, s, side="right") - 1)
        loc = f"{alpha_label(s + 1)}{r + 1}"
        sid = str(i + 1)
        where.append((sid, page, int(s - starts[page]), r, rgb[i]))
        lines.append(f'{sid} "{loc}" {rgb[i][0]:.4f} {rgb[i][1]:.4f} '
                     f'{rgb[i][2]:.4f} {xyz[i][0]:.6f} {xyz[i][1]:.6f} '
                     f'{xyz[i][2]:.6f}')
    lines += ["END_DATA", ""]
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / f"{stem}.ti2"
    p.write_text("\n".join(lines), encoding="utf-8")
    if coverage is not None:
        from tests.page_geometry import write_page_geometry
        write_page_geometry(p, pages, rows, coverage)
    return p, where


def _write_sheet(ti2: Path, where, residual, *, rgb_shift=None,
                 order=None) -> Path:
    """The measured `.ti3` beside *ti2*: each patch's aim Lab plus
    ``residual(page, strip, row, rng) -> (dL, da, db)``."""
    aims = MR._reference_labs(ti2)
    rng = np.random.default_rng(11)
    rows = []
    for sid, page, s, r, rgb in where:
        d = residual(page, s, r, rng)
        lab = np.asarray(aims[sid]) + np.asarray(d)
        xyz = _lab_to_xyz_array(lab[None])[0]
        dev = rgb if rgb_shift is None else rgb_shift(sid, rgb)
        rows.append(f"{sid} {dev[0]:.4f} {dev[1]:.4f} {dev[2]:.4f} "
                    f"{xyz[0]:.6f} {xyz[1]:.6f} {xyz[2]:.6f}")
    if order is not None:
        rows = [rows[i] for i in order]
    text = "\n".join(["CTI3", "", 'DESCRIPTOR "evenness test sheet"',
                      'ORIGINATOR "test"', "", "NUMBER_OF_FIELDS 7",
                      "BEGIN_DATA_FORMAT",
                      "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
                      "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(rows)}",
                      "BEGIN_DATA", *rows, "END_DATA", ""])
    p = ti2.with_suffix(".ti3")
    p.write_text(text, encoding="utf-8")
    return p


def _even(sigma=0.3):
    return lambda page, s, r, rng: rng.normal(0, sigma, 3)


def _words(rep, limits=DEFAULT):
    return {x["row_id"]: x for x in MR.judge(rep, limits)
            if x["row_id"] in (PAIR, FROM_MEAN)}


@pytest.fixture
def chart(tmp_path):
    return _write_chart(tmp_path / "c")


# ---------------------------------------------------------------------------
# 2. the areas
# ---------------------------------------------------------------------------
def test_the_remainder_goes_to_the_middle_band():
    """Knut, 5745765820: *"Where the remainder goes. Answer: middle section."*

    MUTATION: give the remainder to the last band (``[b, b, n - 2b]``) and
    this goes red on 10 and 11.
    """
    assert MR.evenness_bands(9) == [3, 3, 3]
    assert MR.evenness_bands(10) == [3, 4, 3]
    assert MR.evenness_bands(11) == [3, 5, 3]
    assert MR.evenness_bands(47) == [15, 17, 15]


def test_the_positions_come_from_the_chart_and_not_from_the_file_order(chart):
    """The `.ti3` rows arrive in any order; each patch's area is where the
    CHART printed it. The same sheet with its rows reversed reads the same.

    MUTATION: assign areas by row index in `evenness_from_residuals` instead
    of by the chart's slot, and the gradient below lands in the wrong bands
    and the pairwise figure collapses.
    """
    ti2, where = chart
    grad = lambda page, s, r, rng: (0.0, 0.0, (s - 5.5) / 5.5 * 1.2)  # noqa: E731
    a = MR.build_report(_write_sheet(ti2, where, grad))["evenness"]
    b = MR.build_report(_write_sheet(ti2, where, grad,
                                     order=list(range(len(where)))[::-1]))
    b = b["evenness"]
    assert a["pairwise"] == b["pairwise"] and a["from_mean"] == b["from_mean"]
    assert a["pairwise"] > 1.5, a
    # left band against right band: the gradient runs across the STRIPS
    worst = sorted(a["worst_pair"])
    assert {w // 3 for w in worst} == {0, 2}, worst


# ---------------------------------------------------------------------------
# 1 + 3: what the two numbers are
# ---------------------------------------------------------------------------
def test_an_even_sheet_passes_both_rows_and_carries_the_causes_note(chart):
    """A sheet printed evenly, with a small independent residual per patch.

    MUTATION: drop `notes=[NOTE_EVENNESS_CAUSES]` from `row_values` and the
    note assertion goes red; make `judge` ignore `evenness_withheld` and the
    noise sentence below still holds, so the second test carries that one.
    """
    ti2, where = chart
    rep = MR.build_report(_write_sheet(ti2, where, _even(0.3)))
    ev = rep["evenness"]
    assert ev["eligible"] and ev["counts"] == [16] * 9
    w = _words(rep)
    assert w[PAIR]["word"] == CS.PASS and w[FROM_MEAN]["word"] == CS.PASS
    for x in w.values():
        assert MR.NOTE_EVENNESS_CAUSES in x["notes"], x


def test_a_gradient_across_the_sheet_fails_the_pairwise_row_first(chart):
    """A left-to-right drift: P is about twice D, so 1.5 on P fires while
    1.0 on D does not. This is the reason the two limits differ (§16).

    MUTATION: swap the two keys in `EVENNESS_ROWS` and both words flip.
    """
    ti2, where = chart
    grad = lambda page, s, r, rng: (0.0, 0.0,  # noqa: E731
                                    (s - 5.5) / 5.5 * 1.1 + rng.normal(0, .15))
    rep = MR.build_report(_write_sheet(ti2, where, grad))
    ev = rep["evenness"]
    assert ev["pairwise"] > 1.5 > ev["from_mean"] * 1.5 >= 0, ev
    w = _words(rep)
    assert w[PAIR]["word"] == CS.FAIL, w
    assert w[FROM_MEAN]["word"] == CS.PASS, w
    assert MR.NOTE_EVENNESS_CAUSES in w[PAIR]["notes"]


def test_one_area_off_fails_the_from_mean_row_first(chart):
    """A blotch: one ninth of the page 1.35 lighter than its aims. P is about
    1.125 D, so 1.0 on D fires while 1.5 on P does not.

    MUTATION: swap the two keys in `EVENNESS_ROWS` and both words flip (the
    gradient test above goes red on the same mutation).
    """
    ti2, where = chart
    blot = lambda page, s, r, rng: ((1.35 if (s >= 8 and r >= 8) else 0.0)  # noqa: E731
                                    + rng.normal(0, .15), 0.0, 0.0)
    rep = MR.build_report(_write_sheet(ti2, where, blot))
    ev = rep["evenness"]
    assert 1.0 < ev["from_mean"] < ev["pairwise"] < 1.5, ev
    assert ev["worst_area"] == 8
    w = _words(rep)
    assert w[FROM_MEAN]["word"] == CS.FAIL and w[PAIR]["word"] == CS.PASS


def test_the_pairwise_figure_is_the_largest_pair():
    """Two areas off in opposite directions: the two furthest apart are
    those two, and the figure is their difference, not the next pair's.

    MUTATION: take the second-largest pair in `_nine_numbers` and the figure
    drops to one area's own offset.
    """
    grid = MR.evenness_grid_from_layout([12], 12, 144, coverage=[1.0])
    strip, row = np.asarray(grid["strip"]), np.asarray(grid["row"])
    resid = np.zeros((144, 3))
    resid[(strip < 4) & (row < 4), 0] = 0.9           # area 0 lighter
    resid[(strip >= 8) & (row >= 8), 0] = -0.6        # area 8 darker
    ev = MR.evenness_from_residuals(grid, resid, shuffles=20)
    from workflow.profile_engine.metrics import delta_e_2000
    base = np.asarray([MR.EVENNESS_BASE_LAB])
    want = delta_e_2000(base + [0.9, 0, 0], base + [-0.6, 0, 0])[0]
    assert ev["pairwise"] == pytest.approx(want, abs=1e-3)
    assert sorted(ev["worst_pair"]) == [0, 8]


def test_the_mean_counts_each_area_once(tmp_path):
    """Areas of different size: the mean of the nine is the mean of nine
    colours, not of every patch.

    MUTATION: take the MEDIAN of the nine area colours as `centre` in
    `_nine_numbers` (a centre that ignores the one area that is off) and the
    from-the-mean figure moves off the hand-computed value.
    """
    grid = MR.evenness_grid_from_layout([11], 11, 121, coverage=[1.0])   # bands 3/5/3
    ids = grid["ids"]
    resid = np.zeros((len(ids), 3))
    strip, row = np.asarray(grid["strip"]), np.asarray(grid["row"])
    resid[(strip < 3) & (row < 3), 0] = 0.9            # area 0, 9 patches
    ev = MR.evenness_from_residuals(grid, resid, shuffles=20)
    assert ev["counts"][4] == 25 and ev["counts"][0] == 9
    from workflow.profile_engine.metrics import delta_e_2000
    labs = np.tile(np.asarray(MR.EVENNESS_BASE_LAB), (9, 1))
    labs[0, 0] += 0.9
    want = delta_e_2000(labs[:1], labs.mean(0, keepdims=True))[0]
    assert ev["from_mean"] == pytest.approx(want, abs=1e-3)


# ---------------------------------------------------------------------------
# 6: the noise guard
# ---------------------------------------------------------------------------
def test_a_noisy_sheet_is_not_judged_and_says_its_noise(chart):
    """Large per-patch residuals and no place effect at all: whatever the two
    numbers read is noise, and the report must not call it a verdict.

    MUTATION: remove the `evenness_withheld` step from `judge` and both rows
    read PASS or FAIL on noise; this goes red.
    """
    ti2, where = chart
    rep = MR.build_report(_write_sheet(ti2, where, _even(2.5)))
    ev = rep["evenness"]
    assert ev["noise_pairwise_p95"] >= 1.5 and ev["noise_from_mean_p95"] >= 1.0
    w = _words(rep)
    assert w[PAIR]["word"] == CS.N_A
    assert w[PAIR]["reason"] == MR.REASON_EVENNESS_NOISY_PAIRWISE
    assert w[FROM_MEAN]["reason"] == MR.REASON_EVENNESS_NOISY_FROM_MEAN
    assert not w[PAIR]["notes"], "a note on an absence is the window's job"


def test_the_noise_rule_is_strictly_below(chart):
    """*"no verdict when the noise's 95th percentile is not below the
    limit"*: equal is not below.

    MUTATION: `>=` to `>` in `evenness_withheld` and the equal case is judged.
    """
    lim = CS.Limit.value(1.2)
    cell = {"value": 0.5, "noise_p95": 1.2}
    assert MR.evenness_withheld(PAIR, cell, lim) == \
        MR.REASON_EVENNESS_NOISY_PAIRWISE
    assert MR.evenness_withheld(PAIR, dict(cell, noise_p95=1.19), lim) is None
    assert MR.evenness_withheld("all_de00_avg", cell, lim) is None


def test_the_noise_is_reproducible(chart):
    """A fixed seed, so a report opened twice says the same thing.

    MUTATION: seed the shuffle from the clock and the two figures differ.
    """
    ti2, where = chart
    t3 = _write_sheet(ti2, where, _even(0.8))
    a, b = (MR.build_report(t3)["evenness"] for _ in range(2))
    assert a["noise_pairwise_p95"] == b["noise_pairwise_p95"]
    assert a["noise_from_mean_p95"] == b["noise_from_mean_p95"]


def test_an_ungraded_sheet_shows_its_number_whatever_the_noise(tmp_path):
    """The noise rule withholds a PASS or FAIL. A profiling sheet is INFO
    everywhere and keeps its number.

    MUTATION: apply `evenness_withheld` to every word in `judge` and the
    profiling row turns N-A.
    """
    ti2, where = _write_chart(tmp_path / "P" / "runs" / "run1", stem="P")
    rep = MR.build_report(_write_sheet(ti2, where, _even(2.5)))
    assert rep["sheet_kind"] == "profiling"
    w = _words(rep)
    assert w[PAIR]["word"] == CS.INFO and w[PAIR]["value"] is not None


# ---------------------------------------------------------------------------
# 5: the geometric floor
# ---------------------------------------------------------------------------
def test_nine_by_nine_is_the_floor_exactly(tmp_path):
    """8 strips: N-A with the grid named. 9 strips: computed.

    MUTATION: `>` for `>=` against `EVENNESS_MIN_GRID` and nine is refused.
    Raising `EVENNESS_MIN_GRID` to 12 (the one-line change Knut may ask for)
    moves both halves of this test with it, by design; the help text still
    saying 9 is what goes red then
    (`test_the_help_text_quotes_the_numbers_the_code_uses`).
    """
    k = MR.EVENNESS_MIN_GRID
    ti2, where = _write_chart(tmp_path / "a", pages=(k - 1,), rows=20)
    ev = MR.build_report(_write_sheet(ti2, where, _even(0.2)))["evenness"]
    assert ev["reason"] == MR.REASON_EVENNESS_GRID_TOO_SMALL
    assert ev["largest_page"] == [k - 1, 20]
    ti2, where = _write_chart(tmp_path / "b", pages=(k,), rows=k)
    ev = MR.build_report(_write_sheet(ti2, where, _even(0.2)))["evenness"]
    assert ev["eligible"], ev


def test_a_short_last_page_is_left_out_not_fatal(tmp_path):
    """printtarg's usual "22,22,5": the page under the floor does not count,
    the others are judged, and the report says which pages were used.

    MUTATION: refuse the whole chart when any page is under the floor.
    """
    ti2, where = _write_chart(tmp_path / "c", pages=(12, 12, 4), rows=12)
    ev = MR.build_report(_write_sheet(ti2, where, _even(0.2)))["evenness"]
    assert ev["eligible"] and ev["pages_used"] == [1, 2]
    assert ev["n_patches"] == 2 * 12 * 12


def test_no_chart_beside_the_measurement_is_na_and_stays_off_the_strip(
        tmp_path, chart):
    """A stand-alone measurement has no layout to read positions from.

    MUTATION: drop `EVENNESS_FILE_REASONS` from the strip's filter and the
    report window's strip tells the reader to add patches for a missing FILE.
    """
    ti2, where = chart
    t3 = _write_sheet(ti2, where, _even(0.2))
    lone = tmp_path / "elsewhere" / "lone.ti3"
    lone.parent.mkdir()
    lone.write_text(t3.read_text(encoding="utf-8"), encoding="utf-8")
    ev = MR.build_report(lone)["evenness"]
    assert ev["reason"] in (MR.REASON_EVENNESS_NO_LAYOUT, MR.REASON_NO_REFERENCE)
    assert MR.REASON_EVENNESS_NO_LAYOUT in MR.EVENNESS_FILE_REASONS
    # ...and the report WINDOW, opened on that measurement under ChromIQ
    # default (which limits both rows), keeps them off its strip
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core.settings import AppSettings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = MeasurementReportDialog(s, None, initial_ti3=lone)
    try:
        rows, _rec = dlg._verdict_rows(dlg._report)
        mine = {x["row_id"]: x for x in rows if x["row_id"] in (PAIR, FROM_MEAN)}
        assert mine and all(x["word"] == CS.N_A for x in mine.values()), mine
        assert "Evenness" not in dlg._mismatch_text()
    finally:
        dlg.deleteLater()


def test_a_patch_the_measurement_disagrees_with_is_left_out(chart):
    """A sheet whose device values differ from the chart's for some ids is a
    different chart under the same ids: those patches cannot be placed.

    MUTATION: drop the device check in `evenness_block` and the count stays
    at the full chart.
    """
    ti2, where = chart
    shift = lambda sid, rgb: rgb + (10.0 if int(sid) % 10 == 0 else 0.0)  # noqa: E731
    ev = MR.build_report(_write_sheet(ti2, where, _even(0.2),
                                      rgb_shift=shift))["evenness"]
    assert ev["n_mismatched"] == len(where) // 10
    assert ev["n_patches"] == len(where) - len(where) // 10


def test_a_saved_report_without_the_block_is_rebuilt():
    """ALWAYS_BUILT_BLOCKS is what makes an older saved report stale.

    MUTATION: leave "evenness" out of the tuple and a report saved by beta 36
    would read `not_computed` on both rows for ever.
    """
    from ui.dialogs.measurement_report_dialog import ALWAYS_BUILT_BLOCKS
    assert "evenness" in ALWAYS_BUILT_BLOCKS
    vals = MR.row_values({"patches": 10})
    assert vals[PAIR]["reason"] == MR.REASON_NOT_COMPUTED


# ---------------------------------------------------------------------------
# 4: the rows and their limits
# ---------------------------------------------------------------------------
def test_the_rows_are_computable_under_their_own_heading():
    """MUTATION: leave either row `unmeasurable` or under "Not evaluated by
    ChromIQ" and this goes red."""
    for rid in (PAIR, FROM_MEAN):
        row = CS.ROW_BY_ID[rid]
        assert row.status == "build" and row.group == "evenness", rid
        assert row.unit == "ΔE00"
    assert CS.GROUP_LABELS["evenness"] == "Evenness across the sheet"
    assert "spread" not in CS.ROW_BY_ID[PAIR].label


def test_the_limits_knut_gave_and_the_half_and_double_rule():
    """1.5 and 1.0 in ChromIQ default (Knut, 2026-09-22; the 1.0 awaits his
    confirmation), the same in tight and quick (E3), default's own numbers in
    both Custom columns, and nothing in the two read-only ISO columns.

    MUTATION: change either default number and this goes red.
    """
    f = {s: CS.factory_limits(s) for s in CS.SET_IDS}
    assert (f["chromiq_default"][PAIR].number,
            f["chromiq_default"][FROM_MEAN].number) == (1.5, 1.0)
    # E3 (Knut, 2026-09-23): tight and quick carry default's numbers too.
    assert (f["chromiq_tight"][PAIR].number,
            f["chromiq_tight"][FROM_MEAN].number) == (1.5, 1.0)
    assert (f["chromiq_quick"][PAIR].number,
            f["chromiq_quick"][FROM_MEAN].number) == (1.5, 1.0)
    for s in ("custom_iso_12647_7", "custom_iso_12647_8"):
        assert (f[s][PAIR].number, f[s][FROM_MEAN].number) == (1.5, 1.0), s
    # THE TWO READ-ONLY ISO COLUMNS HOLD WHAT THE SHIPPED FILE GIVES THEM
    # (#182 S-2, §23), read from that file here and never written into this
    # source, and none of ChromIQ's own numbers. A row the file leaves out has
    # no number at all. MUTATION: fill a read-only column from ChromIQ
    # default's evenness numbers and this goes red on any row the shipped
    # figure differs from them, and on every row the file does not carry.
    from tests.helpers.iso_files import shipped_limits
    for s in ("iso_12647_7", "iso_12647_8"):
        shipped = shipped_limits(s)
        for rid in (PAIR, FROM_MEAN):
            if rid in shipped:
                assert f[s][rid] == shipped[rid], (s, rid)
            else:
                assert not f[s][rid].is_numeric, (s, rid)


def test_the_help_text_quotes_the_numbers_the_code_uses():
    """The help icon says 9, 500 and 95th percentile; the code must agree.

    MUTATION: change `EVENNESS_MIN_GRID` or `EVENNESS_SHUFFLES` without the
    sentence and this goes red.
    """
    d = CS.ROW_BY_ID[PAIR].detect
    assert f"at least {MR.EVENNESS_MIN_GRID} strips and " \
           f"{MR.EVENNESS_MIN_GRID} rows" in d
    assert f"{MR.EVENNESS_SHUFFLES} times" in d
    assert "95th percentile" in d
    for rid in (PAIR, FROM_MEAN):
        blurb = CS.ROW_BY_ID[rid].blurb
        for cause in ("banding", "print head", "paper", "drifting"):
            assert cause in blurb, (rid, cause)


def test_the_causes_note_is_customer_text():
    """K18: report text never explains ChromIQ or sends the reader to it.

    MUTATION: add "in Create Chart" or "ChromIQ" to the note and this goes red.
    """
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog

    class _Bare:
        _NOTE_TEXT_SEP = MeasurementReportDialog._NOTE_TEXT_SEP

    said = MeasurementReportDialog._note_sentence(_Bare(), "evenness_causes")
    assert "banding" in said and "drifting" in said, said
    for word in ("ChromIQ", "Create Chart", "preset", "Use ", "add "):
        assert word not in said, word


# ---------------------------------------------------------------------------
# where on the page
# ---------------------------------------------------------------------------
def test_the_report_names_the_area_by_the_labels_printed_on_it(chart):
    """Knut: *"indications of which part of the page are not uniform"*. The
    worst area is named by its strip letters and row numbers.

    MUTATION: `argmin` for `argmax` on the worst area and the named strips
    are the wrong ones.
    """
    ti2, where = chart
    blot = lambda page, s, r, rng: ((1.6 if (s >= 8 and r >= 8) else 0.0), 0, 0)  # noqa: E731
    rep = MR.build_report(_write_sheet(ti2, where, blot))
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.dialogs.measurement_report_dialog import (
        _evenness_where_sentence, _evenness_worst_area_sentence)
    first = _evenness_worst_area_sentence(rep)
    assert "strips I to L, rows 9 to 12" in first, first
    assert _evenness_where_sentence(rep).startswith(first)


# ---------------------------------------------------------------------------
# 8: the presets window and the pre-flight
# ---------------------------------------------------------------------------
def test_a_laid_out_small_chart_is_told_its_noise_would_be_too_high(tmp_path):
    """The Measure tab's pre-flight and the presets window's first line are
    about a LAID-OUT chart: the page grid is exact, the noise is estimated for
    a typical print, and the report's own rule decides.

    MUTATION: drop the `evenness_withheld` step from `assess_rows` and the
    9-by-9 chart reads as answering both rows.
    """
    small, _ = _write_chart(tmp_path / "s", pages=(9,), rows=9)
    large, _ = _write_chart(tmp_path / "l", pages=(22,), rows=26)
    PE.clear_cache()
    a = dict(PE.assess(small, MR.REPORT_TYPE_FULL, "chromiq_default").missing)
    assert a.get(PAIR) == MR.REASON_EVENNESS_NOISY_PAIRWISE, a
    b = PE.assess(large, MR.REPORT_TYPE_FULL, "chromiq_default")
    assert PAIR in b.answered and FROM_MEAN in b.answered, b.missing
    # the pre-flight asks with the loosest limit any set has; since E3
    # (Knut, 2026-09-23) every ChromIQ set carries 1.5
    c = dict(PE.assess_any(small).missing)
    loosest = PE.loosest_limits()[PAIR].number
    assert loosest == 1.5
    assert (PAIR in c) == (PE.chart_row_values(small)[PAIR]["noise_p95"]
                          >= loosest)
    PE.clear_cache()


def test_a_preset_not_laid_out_yet_says_so_and_keeps_its_star(tmp_path):
    """A `.ti1` without a recipe has no page grid until printtarg runs.

    MUTATION: file `REASON_EVENNESS_LAID_OUT_LATER` as a patch shortfall and
    every such preset loses its star.
    """
    ti2, _ = _write_chart(tmp_path / "t", pages=(12,), rows=12)
    ti1 = tmp_path / "bare" / "chart.ti1"
    ti1.parent.mkdir()
    ti1.write_text(ti2.read_text(encoding="utf-8").replace("CTI2", "CTI1"),
                   encoding="utf-8")
    PE.clear_cache()
    a = dict(PE.assess(ti1, MR.REPORT_TYPE_FULL, "chromiq_default").missing)
    assert a.get(PAIR) == PE.REASON_EVENNESS_LAID_OUT_LATER
    assert not PE.is_patch_shortfall(PE.REASON_EVENNESS_LAID_OUT_LATER)
    for code in PE.LAYOUT_SHORTFALL_REASONS:
        assert not PE.is_patch_shortfall(code), code
    PE.clear_cache()


def test_the_estimate_reproduces_the_real_sheets_noise():
    """The pre-print estimate is calibrated on NOISE (F1: p95 1.41 at 30
    patches per area on a real sheet against a held-out profile).

    MUTATION: calibrate `EVENNESS_TYPICAL_SIGMA` on the per-patch ΔE00 (0.4)
    and the estimate falls to about 0.5; this goes red.
    """
    grid = MR.evenness_grid_from_layout([30], 9, 270, coverage=[1.0])        # 30 per area
    rng = np.random.default_rng(MR.EVENNESS_SEED)
    noise = rng.normal(0, MR.EVENNESS_TYPICAL_SIGMA, (270, 3))
    ev = MR.evenness_from_residuals(grid, noise,
                                    shuffles=MR.EVENNESS_ESTIMATE_SHUFFLES)
    assert ev["counts"] == [30] * 9
    assert 1.2 <= ev["noise_pairwise_p95"] <= 1.65, ev["noise_pairwise_p95"]


@pytest.mark.parametrize("slug", ["i1_w8_a4_572p_1page_portrait_w8_0mm",
                                  "cm_a4_204p_1page_portrait_w10_0mm_fast_reading_speed"])
def test_the_predicted_grid_is_the_grid_the_engine_builds(tmp_path, slug):
    """The presets window predicts an engine preset's page grid without
    building it. Built for real here, and the `.ti2` the build wrote must
    say the same.

    MUTATION: take the strips per page from the layout's `strips_per_page`
    instead of counting the patches each page really holds, and both
    presets' grids move.
    """
    from core.resource_path import resource_path
    from ui.tabs.tab_chart import KNUT_PRESETS
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    p = next(x for x in KNUT_PRESETS if x.slug == slug)
    chart = Path(resource_path(p.ti1_asset))
    want = PE._predicted_grid(chart, dict(p.layout_recipe))
    res, _ = build_from_recipe(str(chart), str(tmp_path / "b"),
                               LayoutRecipe.from_dict(dict(p.layout_recipe)))
    got = MR.chart_grid(res.ti2_path)
    assert (want["pages"], want["rows"]) == (got["pages"], got["rows"])
