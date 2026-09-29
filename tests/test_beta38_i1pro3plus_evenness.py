"""#182 E4, beta 38: the i1Pro 3 Plus family as its own evenness case (B8-829).

Knut, 5789263863 (E4): *"For i1Pro 3 Plus instrument preset, the charts have
11 columns by 15 rows per strip. It is likely a one page target will not
fulfil the requirement, but a multipage preset should then be possible to use.
This should be checked and verified as a separate case, as it is a good
test."* He named the chart in 5792928823: it is the 11 by 14 one.

At 75 % page coverage (E2 as first built) no preset of the family could be
judged. Knut lowered the floor to 60 % in 5792912682: *"lower the threshold to
60%. instrument's minimum margins are general rules that not always works."*
With it his expectation holds, checked on all 24 built-in presets with the
report's own arithmetic (the presets window's prediction, held to a real
build below):

* the grid is 11 strips by **14** rows on A4 and 11 by **13** on Letter, 16 by
  21 on A3, and 7 by 12 on the two 84-patch charts;
* every page covers 64.6 % (Letter), 65.3 % (A4) or 74.7 % (A3) of the
  paper, all over 60 %, so coverage refuses none of them;
* the two 84-patch charts are refused by the grid (7 strips);
* the one-page A4 (154) and Letter (143) charts pass both floors and hold
  12 to 30 patches in a ninth (15 and 14 as the noise weighs them, B8-1451).
  Until beta 45 a typical print's own noise on them was over ChromIQ
  default's limits and the window refused them. Since Knut's filter (#182
  5855780690, the presets-window text he accepted) no window withholds a row
  on the estimated noise of a print that does not exist yet: they answer
  both rows, and the report decides from the noise of the printed sheet;
* every chart of two pages or more answers both rows, and so does the
  one-page A3 (35 to 42 patches in a ninth).

Every test names the mutation it was run against.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_report as MR                  # noqa: E402
from workflow import page_coverage as PC                       # noqa: E402
from workflow import preset_eligibility as PE                  # noqa: E402

PAIR, FROM_MEAN = "uniformity_sd", "uniformity_de00_max_from_mean"
_TWO = (PAIR, FROM_MEAN)

GRID = MR.REASON_EVENNESS_GRID_TOO_SMALL
NOISE = (MR.REASON_EVENNESS_NOISY_PAIRWISE, MR.REASON_EVENNESS_NOISY_FROM_MEAN)

#: slug -> (strips on every page, rows, pages, coverage of each page in %,
#:          estimated noise (pairwise, from the mean) on a typical print, or
#:          None where the grid refuses the chart first). B8-1451: the noise
#:          is the window's model on the ninths' effective count (their
#:          harmonic mean); the one-draw shuffle it replaced read within 0.07
#:          of every figure here (1.35 / 0.84 on the two-page A4, 1.38 /
#:          0.83 now)
FAMILY = {
    "p3_a4_84p_1page_portrait_w25_0mm": (7, 12, 1, 65.4, None),
    "p3_a4_154p_1page_portrait_w16_0mm": (11, 14, 1, 65.3, (1.80, 1.06)),
    "p3_a4_308p_2pages_portrait_w16_0mm": (11, 14, 2, 65.3, (1.25, 0.74)),
    "p3_a4_462p_3pages_portrait_w16_0mm": (11, 14, 3, 65.3, (1.03, 0.60)),
    "p3_a4_616p_4pages_portrait_w16_0mm": (11, 14, 4, 65.3, (0.89, 0.52)),
    "p3_a4_924p_6pages_portrait_w16_0mm": (11, 14, 6, 65.3, (0.72, 0.42)),
    "p3_a4_1232p_8pages_portrait_w16_0mm": (11, 14, 8, 65.3, (0.63, 0.37)),
    "p3_a4_1540p_10pages_portrait_w16_0mm": (11, 14, 10, 65.3, (0.56, 0.33)),
    "p3_a4_2002p_13pages_portrait_w16_0mm": (11, 14, 13, 65.3, (0.49, 0.29)),
    "p3_letter_84p_1page_portrait_w25_0mm": (7, 12, 1, 64.7, None),
    "p3_letter_143p_1page_portrait_w16_0mm": (11, 13, 1, 64.6, (1.87, 1.10)),
    "p3_letter_286p_2pages_portrait_w16_0mm": (11, 13, 2, 64.6, (1.30, 0.76)),
    "p3_letter_429p_3pages_portrait_w16_0mm": (11, 13, 3, 64.6, (1.05, 0.62)),
    "p3_letter_572p_4pages_portrait_w16_0mm": (11, 13, 4, 64.6, (0.91, 0.53)),
    "p3_letter_858p_6pages_portrait_w16_0mm": (11, 13, 6, 64.6, (0.74, 0.43)),
    "p3_letter_1144p_8pages_portrait_w16_0mm": (11, 13, 8, 64.6, (0.64, 0.38)),
    "p3_letter_1430p_10pages_portrait_w16_0mm": (11, 13, 10, 64.6, (0.57, 0.34)),
    "p3_letter_2002p_14pages_portrait_w16_0mm": (11, 13, 14, 64.6, (0.48, 0.28)),
    "p3_a3_336p_1page_portrait_w16_0mm": (16, 21, 1, 74.7, (1.15, 0.68)),
    "p3_a3_672p_2pages_portrait_w16_0mm": (16, 21, 2, 74.7, (0.81, 0.48)),
    "p3_a3_1008p_3pages_portrait_w16_0mm": (16, 21, 3, 74.7, (0.66, 0.39)),
    "p3_a3_1344p_4pages_portrait_w16_0mm": (16, 21, 4, 74.7, (0.57, 0.34)),
    "p3_a3_1680p_5pages_portrait_w16_0mm": (16, 21, 5, 74.7, (0.51, 0.30)),
    "p3_a3_2016p_6pages_portrait_w16_0mm": (16, 21, 6, 74.7, (0.47, 0.28)),
}

#: What "Which presets can be used for verification?" says of each preset's
#: two evenness rows, against ChromIQ default (1.5 / 1.0): absent where both
#: are answered, else the reasons (pairwise, from the mean).
REFUSED = {
    "p3_a4_84p_1page_portrait_w25_0mm": (GRID, GRID),
    "p3_letter_84p_1page_portrait_w25_0mm": (GRID, GRID),
}


def _presets():
    from ui.tabs.tab_chart import KNUT_PRESETS
    return [p for p in KNUT_PRESETS if p.group == "i1Pro 3 Plus"]


def _chart(p) -> Path:
    from core.resource_path import resource_path
    return Path(resource_path(p.ti1_asset))


@pytest.fixture(autouse=True)
def _fresh_caches():
    PE.clear_cache()
    PC.clear_cache()
    yield
    PE.clear_cache()
    PC.clear_cache()


def _missing(p) -> dict:
    return dict(PE.assess(_chart(p), MR.REPORT_TYPE_FULL, "chromiq_default",
                          recipe=dict(p.layout_recipe)).missing)


def test_the_family_is_the_24_presets_this_file_pins():
    """MUTATION: add or drop an i1Pro 3 Plus preset without deciding its
    evenness case here, and this goes red."""
    assert sorted(p.slug for p in _presets()) == sorted(FAMILY)


@pytest.mark.parametrize("slug", sorted(FAMILY))
def test_each_presets_grid_and_coverage_as_predicted(slug):
    """The page grid and each page's coverage the presets window predicts.
    Knut's "11 by 15" is 11 by 14 on A4 (5792928823) and 11 by 13 on Letter,
    and every page of every preset clears the 60 % floor.

    MUTATION: add one to `steps` in `_predicted_grid` (15 rows on A4) and
    every A4 row goes red."""
    p = next(x for x in _presets() if x.slug == slug)
    strips, rows, pages, pct, _noise = FAMILY[slug]
    grid = PE._evenness_grid_for(_chart(p), dict(p.layout_recipe))
    assert grid["rows"] == rows
    assert grid["pages"] == [strips] * pages
    cov = MR._page_coverages(grid["coverage"], pages)
    assert [round(c * 100, 1) for c in cov] == [pct] * pages
    assert all(c >= MR.EVENNESS_MIN_PAGE_COVERAGE for c in cov)


@pytest.mark.parametrize("slug", sorted(FAMILY))
def test_each_presets_estimated_noise_on_a_typical_print(slug):
    """The noise the presets window estimates for a typical print of each
    preset: about 2.0 / 1.2 on one A4 or Letter page, falling with every page
    added, because the same ninth of every page is counted together.

    MUTATION: judge only the FIRST page used in `evenness_from_residuals`
    (`used[:1]`) and every multi-page chart reads its one-page noise."""
    p = next(x for x in _presets() if x.slug == slug)
    want = FAMILY[slug][4]
    b = PE._estimated_evenness(_chart(p), dict(p.layout_recipe))
    if want is None:
        assert b["reason"] == GRID, b
        return
    got = (b["noise_pairwise_p95"], b["noise_from_mean_p95"])
    assert got == pytest.approx(want, abs=0.02), got
    assert b["pages_used"] == list(range(1, FAMILY[slug][2] + 1))


@pytest.mark.parametrize("slug", sorted(FAMILY))
def test_a_one_page_i1pro3plus_chart_fails_and_a_multi_page_one_answers(slug):
    """Knut's E4 expectation, as shipped at 60 %, and since his filter (#182
    5855780690): the two 84-patch charts cannot be judged (their grid); every
    other chart answers both rows, the one-page 154 and 143 included, because
    the window no longer withholds a row on the estimated noise.

    MUTATION: put `EVENNESS_MIN_PAGE_COVERAGE` back to 0.75 and every preset
    past the grid reads "cover at least 75 %"; this goes red on 22."""
    p = next(x for x in _presets() if x.slug == slug)
    m = _missing(p)
    want = REFUSED.get(slug)
    if want is None:
        assert PAIR not in m and FROM_MEAN not in m, m
    else:
        assert (m.get(PAIR), m.get(FROM_MEAN)) == want, m


def test_the_family_splits_four_refused_twenty_answering():
    """The count the register quoted (B8-829) was 4 of the 24 refused, all
    four one-page charts. Since Knut's filter (#182 5855780690) it is 2: the
    two 84-patch charts, for their grid; the other 22 answer both rows.

    MUTATION: put `EVENNESS_MIN_PAGE_COVERAGE` back to 0.75 and none answers."""
    answered = [p.slug for p in _presets()
                if not ({PAIR, FROM_MEAN} & set(_missing(p)))]
    assert len(answered) == 22
    assert sorted(set(FAMILY) - set(answered)) == sorted(REFUSED)
    assert all(FAMILY[s][2] == 1 for s in REFUSED)


@pytest.mark.parametrize("slug", ["p3_a4_308p_2pages_portrait_w16_0mm",
                                  "p3_a3_336p_1page_portrait_w16_0mm"])
def test_a_real_build_agrees_with_the_prediction(tmp_path, slug):
    """Built for real, the smallest multi-page A4 chart and the one-page A3
    chart: the `.ti2` says the same grid, and "Measured from Preview"'s own
    margins give the same coverage, over the 60 % floor.

    MUTATION: as `test_each_presets_grid_and_coverage_as_predicted`; and a
    `coverage_of` that drops the right margin reads 69.1 % on the A4 page."""
    import json
    from dataclasses import asdict
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    p = next(x for x in _presets() if x.slug == slug)
    rec = LayoutRecipe.from_dict(dict(p.layout_recipe))
    res, used = build_from_recipe(str(_chart(p)), str(tmp_path / "b"), rec)
    ti2 = Path(res.ti2_path)
    lay = json.loads(ti2.with_suffix(".strips.json").read_text("utf-8"))
    lay.update({"engine": "chromiq", "recipe": asdict(used)})
    ti2.with_suffix(".channels.json").write_text(json.dumps({"layout": lay}),
                                                 encoding="utf-8")
    strips, rows, pages, pct, _noise = FAMILY[slug]
    got = MR.chart_grid(ti2)
    assert (got["pages"], got["rows"]) == ([strips] * pages, rows)
    cov = MR._page_coverages(got["coverage"], pages)
    assert got["coverage_source"] == PC.SOURCE_ENGINE
    for c in cov:
        assert c * 100 == pytest.approx(pct, abs=0.15)
        assert c >= MR.EVENNESS_MIN_PAGE_COVERAGE
