"""#182 E4, beta 38: the i1Pro 3 Plus family as its own evenness case (B8-829).

Knut, 5789263863 (E4): *"For i1Pro 3 Plus instrument preset, the charts have
11 columns by 15 rows per strip. It is likely a one page target will not
fulfil the requirement, but a multipage preset should then be possible to use.
This should be checked and verified as a separate case, as it is a good
test."*

Checked on all 24 built-in i1Pro 3 Plus presets, with the report's own
arithmetic (the presets window's prediction, held to a real build below):

* the grid is 11 strips by **14** rows on A4 and 11 by **13** on Letter (not
  15), 16 by 21 on A3, and 7 by 12 on the two 84-patch charts;
* by the 9 by 9 floor and the noise rule alone, Knut's expectation holds: the
  one-page A4 and Letter charts are too noisy on a typical print, every chart
  of two pages or more can be judged, and so can the one-page A3;
* **but no i1Pro 3 Plus preset passes E2's 75 % page coverage.** The family's
  own margins (28 mm clip band, 40 mm top, 20 mm bottom, 10 mm right) leave
  the patches 65.3 % of an A4 page, 64.6 % of a Letter page and 74.7 % of an
  A3 page. So today every one of them reads N-A on both rows: the 84-patch
  charts for the grid, the rest for the coverage. That collision is a
  question for Knut, not a fault to fix here.

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

#: slug -> (strips on every page, rows, pages, coverage of each page in %)
FAMILY = {
    "p3_a4_84p_1page_portrait_w25_0mm": (7, 12, 1, 65.4),
    "p3_a4_154p_1page_portrait_w16_0mm": (11, 14, 1, 65.3),
    "p3_a4_308p_2pages_portrait_w16_0mm": (11, 14, 2, 65.3),
    "p3_a4_462p_3pages_portrait_w16_0mm": (11, 14, 3, 65.3),
    "p3_a4_616p_4pages_portrait_w16_0mm": (11, 14, 4, 65.3),
    "p3_a4_924p_6pages_portrait_w16_0mm": (11, 14, 6, 65.3),
    "p3_a4_1232p_8pages_portrait_w16_0mm": (11, 14, 8, 65.3),
    "p3_a4_1540p_10pages_portrait_w16_0mm": (11, 14, 10, 65.3),
    "p3_a4_2002p_13pages_portrait_w16_0mm": (11, 14, 13, 65.3),
    "p3_letter_84p_1page_portrait_w25_0mm": (7, 12, 1, 64.7),
    "p3_letter_143p_1page_portrait_w16_0mm": (11, 13, 1, 64.6),
    "p3_letter_286p_2pages_portrait_w16_0mm": (11, 13, 2, 64.6),
    "p3_letter_429p_3pages_portrait_w16_0mm": (11, 13, 3, 64.6),
    "p3_letter_572p_4pages_portrait_w16_0mm": (11, 13, 4, 64.6),
    "p3_letter_858p_6pages_portrait_w16_0mm": (11, 13, 6, 64.6),
    "p3_letter_1144p_8pages_portrait_w16_0mm": (11, 13, 8, 64.6),
    "p3_letter_1430p_10pages_portrait_w16_0mm": (11, 13, 10, 64.6),
    "p3_letter_2002p_14pages_portrait_w16_0mm": (11, 13, 14, 64.6),
    "p3_a3_336p_1page_portrait_w16_0mm": (16, 21, 1, 74.7),
    "p3_a3_672p_2pages_portrait_w16_0mm": (16, 21, 2, 74.7),
    "p3_a3_1008p_3pages_portrait_w16_0mm": (16, 21, 3, 74.7),
    "p3_a3_1344p_4pages_portrait_w16_0mm": (16, 21, 4, 74.7),
    "p3_a3_1680p_5pages_portrait_w16_0mm": (16, 21, 5, 74.7),
    "p3_a3_2016p_6pages_portrait_w16_0mm": (16, 21, 6, 74.7),
}

#: Under the grid and noise rules ALONE (the coverage floor set aside), the
#: presets that cannot answer both rows at ChromIQ default's 1.5 / 1.0: the
#: two 84-patch charts (7 strips), and the one-page A4 and Letter charts
#: (about 12 patches per ninth; estimated noise 2.0 / 1.2).
NOT_BY_GRID_OR_NOISE = {
    "p3_a4_84p_1page_portrait_w25_0mm": MR.REASON_EVENNESS_GRID_TOO_SMALL,
    "p3_letter_84p_1page_portrait_w25_0mm": MR.REASON_EVENNESS_GRID_TOO_SMALL,
    "p3_a4_154p_1page_portrait_w16_0mm": MR.REASON_EVENNESS_NOISY_PAIRWISE,
    "p3_letter_143p_1page_portrait_w16_0mm": MR.REASON_EVENNESS_NOISY_PAIRWISE,
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
    Knut's "11 by 15" is 11 by 14 on A4 and 11 by 13 on Letter.

    MUTATION: add one to `steps` in `_predicted_grid` (15 rows on A4) and
    every A4 row goes red."""
    p = next(x for x in _presets() if x.slug == slug)
    strips, rows, pages, pct = FAMILY[slug]
    grid = PE._evenness_grid_for(_chart(p), dict(p.layout_recipe))
    assert grid["rows"] == rows
    assert grid["pages"] == [strips] * pages
    cov = MR._page_coverages(grid["coverage"], pages)
    assert [round(c * 100, 1) for c in cov] == [pct] * pages


@pytest.mark.parametrize("slug", sorted(FAMILY))
def test_today_no_i1pro3plus_preset_answers_the_evenness_rows(slug):
    """With the rules as shipped (9 by 9, 75 % coverage, the noise rule), both
    rows are missing on every one: the 84-patch charts for their grid, every
    other for its coverage, the A3 ones by 0.3 of a point.

    MUTATION: lower `EVENNESS_MIN_PAGE_COVERAGE` to 0.74 and the six A3
    presets answer both rows; this goes red on them."""
    p = next(x for x in _presets() if x.slug == slug)
    m = _missing(p)
    want = (MR.REASON_EVENNESS_GRID_TOO_SMALL if FAMILY[slug][0] < 9
            else MR.REASON_EVENNESS_PAGE_COVERAGE)
    assert (m.get(PAIR), m.get(FROM_MEAN)) == (want, want), m


@pytest.mark.parametrize("slug", sorted(FAMILY))
def test_by_grid_and_noise_alone_one_page_fails_and_several_pages_pass(
        slug, monkeypatch):
    """Knut's expectation, checked with the coverage floor set aside: the
    one-page A4 and Letter charts cannot be judged (grid, or noise on a
    typical print), every multi-page chart can, and so can the one-page A3
    (16 by 21, 35 patches in each ninth).

    MUTATION: judge only the FIRST page used in `evenness_from_residuals`
    (`used[:1]`) and every multi-page A4 and Letter chart falls back to the
    one-page noise; this goes red on them."""
    monkeypatch.setattr(MR, "EVENNESS_MIN_PAGE_COVERAGE", 0.0)
    p = next(x for x in _presets() if x.slug == slug)
    m = _missing(p)
    want = NOT_BY_GRID_OR_NOISE.get(slug)
    if want is None:
        assert PAIR not in m and FROM_MEAN not in m, m
    else:
        assert m.get(PAIR) == want, m


@pytest.mark.parametrize("slug", ["p3_a4_308p_2pages_portrait_w16_0mm",
                                  "p3_a3_336p_1page_portrait_w16_0mm"])
def test_a_real_build_agrees_with_the_prediction(tmp_path, slug):
    """Built for real, the smallest multi-page A4 chart and the one-page A3
    chart: the `.ti2` says the same grid, and "Measured from Preview"'s own
    margins give the same coverage, so the A3 page really is under 75 %.

    MUTATION: as `test_each_presets_grid_and_coverage_as_predicted`; and a
    `coverage_of` that drops the right margin lifts the A3 page over 75 %."""
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
    strips, rows, pages, pct = FAMILY[slug]
    got = MR.chart_grid(ti2)
    assert (got["pages"], got["rows"]) == ([strips] * pages, rows)
    cov = MR._page_coverages(got["coverage"], pages)
    assert got["coverage_source"] == PC.SOURCE_ENGINE
    for c in cov:
        assert c * 100 == pytest.approx(pct, abs=0.15)
        assert c < MR.EVENNESS_MIN_PAGE_COVERAGE
