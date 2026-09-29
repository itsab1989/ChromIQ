"""B8-1451 (beta 45 challenge 1, F1): the presets window's evenness sentence
said what was not true, and presets contradicted each other.

* "Each ninth of the page holds at least 200 patches" on a 10-page chart
  that puts about 20 in a ninth of each page. The report counts the same
  ninth of EVERY page it reads together (§16 item 3), and the count was that
  pooled one, so the sentence has to say the pages are counted together.
* Under ISO 12647-7:2016 values one preset said about 170 patches in a ninth
  would do, while another holding 216 was withheld: 118 such pairs. The
  needed count was worked out from each chart's own random draw.

What holds now, for every built-in preset the window lists, under every
"Judged against" and both report types the challenge drove (Any, Full
colour check):

1. the noise is ONE model for every chart
   (`MR.EVENNESS_NOISE_PER_ROOT_PATCH` over the root of the ninths'
   effective count, `MR.evenness_effective_count`), and the multiplier is
   the report's own shuffle, re-measured here;
2. one limit gives one needed count, a row is withheld exactly when the
   effective count is under it, and no answered preset counts fewer;
3. every number in the sentence is the page grid's: the pooled counts
   are the sums of each page's ninths, over the pages the report reads,
   and a chart of several pages says so.

Every test names the mutation it was proven red against
(`~/Desktop/ChromIQ-beta45-proof/fixes-1a/mutations.txt`).
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                       # noqa: E402

from workflow import compliance_sets as CS                     # noqa: E402
from workflow import measurement_report as MR                  # noqa: E402
from workflow import preset_eligibility as PE                  # noqa: E402

ROWS = tuple(MR.EVENNESS_ROWS)


# ---------------------------------------------------------------------------
# 1. the model
# ---------------------------------------------------------------------------
def _shuffle_noise(strips_per_page, rows, seed, sigma=1.0, shuffles=1000):
    total = sum(strips_per_page) * rows
    g = MR.evenness_grid_from_layout(strips_per_page, rows, total,
                                     coverage=[1.0] * len(strips_per_page))
    rng = np.random.default_rng(1000 + seed)
    b = MR.evenness_from_residuals(g, rng.normal(0, sigma, (total, 3)),
                                   shuffles=shuffles, seed=seed)
    return b


def test_the_multiplier_is_the_reports_own_shuffle():
    """The model's two multipliers ARE the report's shuffle on residuals of
    one unit, times the root of the patches in a ninth: re-measured on ideal
    60 by 60 pages (400 in each ninth), six seeds, within 4 %.

    MUTATION, proven red: ``"pairwise": 7.7`` (the multiplier with the
    typical residual folded in twice)."""
    got = {k: [] for k in MR.EVENNESS_NOISE_PER_ROOT_PATCH}
    for seed in range(6):
        b = _shuffle_noise([60], 60, seed)
        n = min(b["counts"])
        for k in got:
            got[k].append(b[f"noise_{k}_p95"] * n ** 0.5)
    for k, vals in got.items():
        want = MR.EVENNESS_NOISE_PER_ROOT_PATCH[k]
        assert abs(np.mean(vals) / want - 1) < 0.04, (k, np.mean(vals), want)


def test_the_effective_count_is_the_harmonic_mean_rounded_down():
    """MUTATION, proven red: `evenness_effective_count` returning the fewest
    (15 becomes 12 on the uneven page)."""
    assert MR.evenness_effective_count([72] * 9) == 72
    uneven = [12, 18, 12, 20, 30, 20, 12, 18, 12]
    assert MR.evenness_effective_count(uneven) == 15
    assert MR.evenness_effective_count([5, 0, 5]) is None
    assert MR.evenness_effective_count([]) is None


def test_on_an_uneven_page_the_model_reads_what_the_report_reads():
    """Why the harmonic mean and not the fewest: Knut's two-page i1Pro 3 Plus
    chart (11 strips by 14 rows twice, 24 to 60 patches in a ninth). The
    report's shuffle on typical residuals, averaged over eight seeds, reads
    within 6 % of the model on the effective count; the fewest alone would
    read a noise a tenth higher, and refuse the chart §16.6 confirmed.

    MUTATION, proven red: as `test_the_effective_count_is_the_harmonic_mean_
    rounded_down`."""
    counts = None
    shuffled = {k: [] for k in MR.EVENNESS_NOISE_PER_ROOT_PATCH}
    for seed in range(8):
        b = _shuffle_noise([11, 11], 14, seed, sigma=MR.EVENNESS_TYPICAL_SIGMA,
                           shuffles=500)
        counts = b["counts"]
        for k in shuffled:
            shuffled[k].append(b[f"noise_{k}_p95"])
    eff = MR.evenness_effective_count(counts)
    assert (min(counts), eff) == (24, 31), counts
    for k, vals in shuffled.items():
        model = PE.model_noise(k, eff)
        assert abs(model / np.mean(vals) - 1) < 0.06, (k, model, vals)
    assert PE.model_noise("pairwise", min(counts)) / np.mean(
        shuffled["pairwise"]) > 1.08


def _numeric_limits():
    out = set()
    for s in CS.SETS:
        for rid in ROWS:
            lim = CS.effective_limits(s.id, {}).get(rid)
            if lim is not None and lim.is_numeric and lim.number > 0:
                out.add((rid, float(lim.number)))
    return sorted(out)


@pytest.mark.parametrize("rid,limit", _numeric_limits())
def test_one_limit_gives_one_needed_count_and_the_line_is_exact(rid, limit):
    """The needed count sits exactly on the rule's line: one patch fewer
    reads a noise that is not below the limit (`evenness_withheld`: noise
    >= limit withholds), the count itself reads under it.

    MUTATION, proven red: `model_need` without its settling loops (a
    rounded figure exactly on 1.0 then passes on one side and not the
    other)."""
    key = MR.EVENNESS_ROWS[rid]
    need = PE.model_need(key, limit)
    assert PE.model_noise(key, need) < limit <= PE.model_noise(key, need - 1)


# ---------------------------------------------------------------------------
# 2 and 3. every preset the window lists
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _page_ninths(grid: dict, used_pages: "list[int]") -> "list[list[int]]":
    """Each used page's nine counts, by the report's own band arithmetic,
    read off the grid and not off the block."""
    ids, page, strip, row = MR._grid_arrays(grid)
    out = []
    for p in used_pages:
        m = page == p - 1
        n = int(m.sum())
        areas = (MR._bands_of(strip[m], np.full(n, grid["pages"][p - 1])) * 3
                 + MR._bands_of(row[m], np.full(n, grid["rows"])))
        out.append([int(x) for x in np.bincount(areas, minlength=9)])
    return out


@pytest.fixture(scope="module")
def sweep(qapp):
    """Every built-in preset the window lists, laid out as the window lays it
    out, assessed under every "Judged against" of both report types the
    challenge drove."""
    from core.settings import AppSettings
    from ui.tabs.tab_chart import verification_preset_rows
    rows = [r for r in verification_preset_rows(AppSettings())
            if r.chart is not None]
    grids = {}
    for r in rows:
        PE.chart_row_values(r.chart, r.recipe, lay_out=True)
        grids[r.label] = PE._evenness_grid_for(Path(r.chart), r.recipe, True)
    sets = [PE.ALL_METRICS] + list(CS.selectable_set_ids({}))
    cases = {}
    for tid in (PE.ANY_REPORT_TYPE, MR.REPORT_TYPE_FULL):
        for sid in sets:
            cases[(tid, sid)] = [(r, PE.assess(r.chart, tid, sid,
                                               recipe=r.recipe))
                                 for r in rows]
    return rows, grids, cases


def test_the_sweep_sees_what_the_challenge_saw(sweep):
    """Guard the guard: the list is the window's, and it holds multi-page
    presets whose ninths differ.

    MUTATION, proven red: `verification_preset_rows` returning [] (every
    other test here would pass on nothing)."""
    rows, grids, cases = sweep
    assert len(rows) > 150, len(rows)
    many = [r for r in rows if len(grids[r.label].get("pages") or ()) > 1]
    assert any(r.label.startswith("A4-2040p-10pages") for r in many)


def test_no_preset_is_withheld_for_the_estimated_noise_of_a_typical_print(
        sweep):
    """Since Knut's filter (#182 5855780690, the presets-window text he
    accepted from 5855451413 section 6): a chart that meets the page rules
    can be judged on both evenness rows, under every report type and every
    "Judged against", and the report alone decides from the noise of the
    printed sheet. So no preset is missing an evenness row for noise, none
    carries a count sentence, and a row is answered exactly when the laid-out
    chart has a value for it (its pages meet the page rules).

    MUTATION, proven red: put the `evenness_withheld` step back into
    `assess_rows` (ChromIQ tight withholds the one-page presets again)."""
    _rows, _grids, cases = sweep
    bad = []
    seen = 0
    for (tid, sid), rs in cases.items():
        for r, a in rs:
            missing = dict(a.missing)
            for rid in ROWS:
                if rid not in a.asked:
                    continue
                seen += 1
                if missing.get(rid) in MR.EVENNESS_NOISE_REASONS \
                        or a.noise_count(rid):
                    bad.append((tid, sid, rid, r.label, missing.get(rid)))
                has = PE.chart_row_values(r.chart, r.recipe)[rid]
                if (has.get("value") is not None) != (rid in a.answered):
                    bad.append(("answered differs from the page rules", sid,
                                rid, r.label))
    assert not bad, bad[:10]
    assert seen > 300, seen
