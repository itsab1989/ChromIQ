"""4.3.10, forum post 149811 (jctay's Canon Selphy CP1500), Basti's two rulings
of 2026-10-23. Both tests below fail on 4.3.9's code.

1. **From Profile Gamut places every reachable grey step again.** 4.3.5 (k82)
   spaced as many grey steps as fit at the chart's spacing, at least 8, between
   the black and the WHITE CORNER as the profile prints them. On a printer
   whose black is not neutral no neutral can be printed anywhere near the black
   corner (jctay's: none darker than L* 24.2 while the black prints at L* 13.6
   with a cast), so the steps nearest the dark slices all collapsed onto the
   same few greys, the chart had 8 steps between L* 24 and 90 with a hole in
   the dark half, and the report's grey rows read N-A ("bunched together")
   on every chart of his. Now: every distinct reachable step of the grey wedge
   up to about one patch in eight (4.3.4's count), spaced evenly from the
   darkest to the lightest grey the profile REACHES when there are more.

2. **Evenness asks for the patch block's spread in each direction.** Knut's
   area floor (60 % of the page, confirmed 2026-09-23) refused jctay's 4 x 6 in
   i1Pro card, whose patches reach across 71 % of its width and 78 % of its
   height but cover 55 % of its area: the instrument's fixed margins weigh
   heavily on a small card. Since 4.3.10 a page counts when the block reaches
   across at least 65 % of the width AND 65 % of the height.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import gamut_target as gt              # noqa: E402
from workflow import measurement_report as MR        # noqa: E402
from workflow import page_coverage as PC             # noqa: E402


# ---------------------------------------------------------------------------
# 1. the grey steps
# ---------------------------------------------------------------------------
def _jctay_like():
    """The candidate list's own neutral colours, as reachable on jctay's
    rebuilt profile (absolute, safe margin, measured by agent 28): every
    neutral from L* 24.2 to 94.3 round-trips, none darker. The corners as
    the profile prints them: paper white L* 95.3, and a black of L* 13.6 with
    a strong cast (chroma 17.8), so not neutral."""
    labs = gt.load_master_labs()
    neutral = [i for i, lab in enumerate(labs)
               if math.hypot(lab[1], lab[2]) < 1.0 and 24.0 <= lab[0] <= 94.5]
    corners = [(95.3, 0.4, -2.1), (13.6, 7.9, -15.9)]
    return labs, neutral, corners


def _levels(labs, idx):
    return sorted(labs[i][0] for i in idx)


def test_every_reachable_grey_step_up_to_the_budget():
    """A 577-colour chart (jctay's size): its budget is 72, more than the
    wedge holds, so every distinct reachable step is on it, and the report's
    grey rule finds 8 roughly evenly spaced steps among them.

    MUTATION: 4.3.9's `_grey_steps` (steps between the corners, as many as
    fit at the chart's spacing): 8 steps between L* 24 and 90, and
    `pick_even_grey_steps` finds no step near L* 34.4."""
    labs, neutral, corners = _jctay_like()
    steps = gt._grey_steps(neutral, labs, corners, 577)
    lv = _levels(labs, steps)
    assert len(lv) >= 30, lv
    assert lv[0] == pytest.approx(24.2, abs=0.1)
    assert lv[-1] == pytest.approx(94.3, abs=0.1)
    assert min(np.diff(lv)) >= MR.GREY_LEVEL_TOL, lv
    picked, missing = MR.pick_even_grey_steps(lv)
    assert picked is not None, missing


def test_more_reachable_steps_than_the_budget_are_spaced_from_the_darkest_reachable_grey():
    """A 100-colour chart: budget 12, so 12 steps from the darkest to the
    lightest REACHABLE grey, both ends included, evenly spaced.

    MUTATION: space them between the black and the white CORNER (4.3.9):
    the darkest step is no longer L* 24.2 and the dark gaps grow."""
    labs, neutral, corners = _jctay_like()
    steps = gt._grey_steps(neutral, labs, corners, 100)
    lv = _levels(labs, steps)
    assert len(lv) == gt._neutral_budget(100) == 12
    assert lv[0] == pytest.approx(24.2, abs=0.1)
    assert lv[-1] == pytest.approx(94.3, abs=0.1)
    gaps = np.diff(lv)
    even = (lv[-1] - lv[0]) / 11
    assert gaps.max() < 1.6 * even and gaps.min() > 0.4 * even, gaps
    assert MR.pick_even_grey_steps(lv)[0] is not None


def test_a_grey_that_only_repeats_a_corner_is_not_a_step():
    """The paper white as a neutral candidate (relative intent puts white at
    L* 100, the white corner too): never a step."""
    labs, _n, _c = _jctay_like()
    neutral = [i for i, lab in enumerate(labs)
               if math.hypot(lab[1], lab[2]) < 1.0 and lab[0] >= 24.0]
    corners = [(100.0, 0.0, 0.0), (15.0, 7.0, -15.0)]
    lv = _levels(labs, gt._grey_steps(neutral, labs, corners, 577))
    assert max(lv) < 100.0 - gt.GREY_CORNER_REPEAT_DE76 + 1e-9, lv


# ---------------------------------------------------------------------------
# 2. the evenness spread
# ---------------------------------------------------------------------------
def _jctay_card(tmp_path):
    """jctay's verification chart laid out by the app's own engine as his log
    describes it: i1Pro, 4 x 6 in, patch first, margins T5.5 R4 B1 L5, a
    20 mm clip border, 8 x 8.2 mm patches, 577 colours + 8 corners."""
    from workflow.layout_engine.chart import build_chart
    rng = np.random.default_rng(149811)
    rows = [f"{i + 1} {r:.4f} {g:.4f} {b:.4f}"
            for i, (r, g, b) in enumerate(rng.uniform(0, 100, (585, 3)))]
    ti1 = tmp_path / "CP1500.ti1"
    ti1.write_text("\n".join(
        ["CTI1", "", 'DESCRIPTOR "jctay card"', 'ORIGINATOR "test"',
         'COLOR_REP "RGB"', "", "NUMBER_OF_FIELDS 4", "BEGIN_DATA_FORMAT",
         "SAMPLE_ID RGB_R RGB_G RGB_B", "END_DATA_FORMAT", "",
         f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA", *rows, "END_DATA", ""]),
        encoding="utf-8")
    build_chart(ti1, ti1.with_suffix(""), instrument="i1", paper="4x6",
                layout_mode="patch_first", margins=(5.5, 4.0, 1.0, 5.0),
                clip_border_width=20.0, patch_w=8.0, patch_h=8.2,
                strip_pattern="0-9,@-9,@-9;1-999", patch_pattern="A-Z, A-Z",
                randomize=True, seed=149786)
    return ti1.with_suffix(".ti2")


def test_jctays_card_is_judged_by_its_spread(tmp_path):
    """Five pages of 9 strips by 13 rows. Each page: 70.9 % of the width,
    77.8 % of the height, 55.2 % of the area. 4.3.9 refused every page (area
    under 60 %); 4.3.10 counts them all.

    MUTATION: judge the area share against 0.60 again in
    `evenness_from_residuals`: `evenness_page_coverage_too_small`."""
    PC.clear_cache()
    ti2 = _jctay_card(tmp_path)
    grid = MR.chart_grid(ti2)
    assert grid["pages"] == [9, 9, 9, 9, 9] and grid["rows"] == 13
    for page in grid["coverage"]:
        assert page["coverage"] < 0.60                  # the old floor's no
        w, h = page["spans"]
        assert w == pytest.approx(0.709, abs=0.01), page
        assert h == pytest.approx(0.778, abs=0.01), page
        assert min(w, h) >= MR.EVENNESS_MIN_PAGE_SPAN
    ids = sorted(grid["slot"])
    ev = MR.evenness_from_residuals(grid, {i: (0.0, 0.0, 0.0) for i in ids},
                                    shuffles=20)
    assert ev.get("reason") != MR.REASON_EVENNESS_PAGE_COVERAGE, ev
    assert ev["pages_used"] == [1, 2, 3, 4, 5], ev
    assert ev["pages_uncovered"] == []


def test_the_spread_is_asked_in_both_directions_from_the_same_margins():
    """`spans_of` is the share of the width and of the height, from the four
    "Measured from Preview" margins, and a block short in either direction
    is refused.

    MUTATION: swap top/bottom for left/right in `spans_of`."""
    w, h = PC.spans_of(101.6, 152.4, 19.98, 9.57, 23.37, 10.41)
    assert w == pytest.approx((101.6 - 29.55) / 101.6)
    assert h == pytest.approx((152.4 - 33.78) / 152.4)
    # the half-page A4 chart the area floor was built for: 46 % of the width
    hw, hh = PC.spans_of(210, 297, 26, 87, 38, 19)
    assert hw < MR.EVENNESS_MIN_PAGE_SPAN <= hh
    grid = MR.evenness_grid_from_layout(
        [12], 26, 312, coverage=[{"coverage": hw * hh, "spans": [hw, hh]}])
    ev = MR.evenness_from_residuals(grid, np.zeros((312, 3)), shuffles=20)
    assert ev["reason"] == MR.REASON_EVENNESS_PAGE_COVERAGE


def test_a_report_saved_under_the_area_rule_reads_as_it_was_saved():
    """A block saved before 4.3.10 has `min_coverage` and area shares and no
    `min_span`: its note and the presets window's left-out sentence keep the
    old words and figures; a new block gets the spread sentence.

    MUTATION: read every block as a spread block in
    `_evenness_coverage_sentence`."""
    from ui.dialogs.measurement_report_dialog import _evenness_coverage_sentence
    from ui.dialogs.preset_verification_dialog import _left_out_sentences
    old = {"evenness": {"pages_uncovered": [1], "coverage": [0.557],
                        "min_coverage": 0.6}}
    assert _evenness_coverage_sentence(old) == (
        "the patches on page 1 of the measured chart cover 55.7 % of the "
        "page; at least 60 % is needed")
    new = {"evenness": {"pages_uncovered": [1], "coverage": [0.31],
                        "spans": [[0.4625, 0.8073]], "min_span": 0.65}}
    assert _evenness_coverage_sentence(new) == (
        "the patches on page 1 of the measured chart reach across 46.2 % of "
        "the page's width and 80.7 % of its height; to compare the nine areas "
        "of a page, the patches need to reach across at least 65 % of the "
        "width and at least 65 % of the height, so that the nine areas lie "
        "spread over the whole page")
    assert "cover 43.1 % of the page, less than 60 %" in _left_out_sentences(
        [["uncovered", 9, 0.4316]])
    assert ("reach across 52.3 % of the page's width and 82.5 % of its "
            "height") in _left_out_sentences([["uncovered", 9, [0.5233, 0.825]]])
