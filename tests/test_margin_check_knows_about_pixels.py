"""No shipped chart may accuse itself of breaking its own margins (#167).

Every built-in preset that carries a layout recipe declares four margins and
asks the ChromIQ engine to lay the chart out inside them. Two things must hold
and neither had a test:

1. **The engine must actually hold the box.** `geometry.realized_margins_mm` is
   the layout's own answer, before any raster exists.
2. **The margin inspector must not report a violation for a chart the engine
   laid out correctly.** It reads the patch rectangles, which are rounded to
   whole device pixels, so it sees a value up to one pixel short of the truth.

(2) was false for **45 of the 119** recipe-carrying built-ins: every ColorMunki
chart on the right edge (23.945 vs 24.0) and every i1Pro 3 Plus one on the left
(27.94 vs 28.0). Both families declare `dpi: 200`, where one pixel is 0.127 mm
and the fixed 0.05 mm display allowance from #85 no longer covers the rounding.
The user's first act with a factory preset was a red error about the factory
preset. Nothing was wrong with the chart, the recipe or the engine.
"""
from __future__ import annotations

import pytest

from workflow.hex_support import recipe_is_hexagonal
from workflow.layout_engine import geometry, instruments, papers
from workflow.layout_engine.presets import LayoutRecipe
from workflow.margin_inspector import MarginReport, check_violations


def _builtin_presets_with_recipes():
    """(slug, preset) for every built-in chart preset that carries a recipe.

    Discovered from the module rather than a hand-kept list, so a new family
    is covered the day it is added.
    """
    import ui.tabs.tab_chart as tc
    seen: dict = {}
    for name in dir(tc):
        val = getattr(tc, name)
        if isinstance(val, list) and val and isinstance(val[0], tc._Ti1Preset):
            for p in val:
                if p.layout_recipe:
                    seen.setdefault(p.slug, p)
    return sorted(seen.items())


_LAID_OUT: dict = {}


def _laid_out(preset):
    """(geom, layout, paper_w, paper_h, dpi) for one preset's recipe.

    Cached: resolving an area-first recipe binary-searches the patch width over
    40 real layouts, which is ~0.27 s per chart and the whole cost of this file.
    """
    if preset.slug in _LAID_OUT:
        return _LAID_OUT[preset.slug]
    rec_d = preset.layout_recipe
    rec = LayoutRecipe.from_dict(rec_d)
    kw = {**rec.build_kwargs(), "area_target_count": preset.patches}
    geom = instruments.geom_from_build_kwargs(kw)
    w_mm, h_mm = papers.dimensions_mm(rec_d.get("paper", "A4"))
    layout = geometry.compute(geom, w_mm, h_mm, preset.patches)
    _LAID_OUT[preset.slug] = (geom, layout, w_mm, h_mm,
                              int(rec_d.get("dpi") or 300))
    return _LAID_OUT[preset.slug]


def _own_thresholds(preset):
    """The chart's own declared minimums, as `_chart_own_margins` builds them."""
    rec_d = preset.layout_recipe
    if rec_d.get("use_instrument_margins", True):
        return None
    return {"L": float(rec_d.get("margin_left", 0.0)),
            "R": float(rec_d.get("margin_right", 0.0)),
            "T": float(rec_d.get("margin_top", 0.0)),
            "B": float(rec_d.get("margin_bottom", 0.0))}


def _inspector_report(preset):
    """What `margin_inspector.measure_from_engine` would report for page 0.

    Same three steps that function takes: the patch rectangles' bounding box,
    the edge-spacer overhang, the hexagon apex overhang.
    """
    geom, layout, w_mm, h_mm, dpi = _laid_out(preset)
    rects = [r for r in geometry.patch_rects_px(geom, w_mm, h_mm, layout, dpi)
             if r["page"] == 0]
    px2mm = 25.4 / dpi
    x0 = min(r["x"] for r in rects)
    x1 = max(r["x"] + r["w"] for r in rects)
    y0 = min(r["y"] for r in rects)
    y1 = max(r["y"] + r["h"] for r in rects)
    if geom.edge_spacers:
        sp = round(geom.pspa * dpi / 25.4)
        y0, y1 = y0 - sp, y1 + sp
    if recipe_is_hexagonal(preset.layout_recipe):
        hh = max(r["h"] for r in rects)
        y0, y1 = y0 - hh / 6.0, y1 + hh / 6.0
    return MarginReport(
        left_mm=max(0.0, x0 * px2mm), right_mm=max(0.0, w_mm - x1 * px2mm),
        top_mm=max(0.0, y0 * px2mm), bottom_mm=max(0.0, h_mm - y1 * px2mm),
        strip_width_mm=rects[0]["w"] * px2mm,
        page_w_mm=w_mm, page_h_mm=h_mm,
        strip_length_mm=(y1 - y0) * px2mm,
        dpi=dpi,
    )


def test_no_builtin_preset_breaks_its_own_declared_margins():
    """Both answers for every built-in chart, in one pass over the presets.

    ``analytic`` is the engine's own placement (no pixels). ``reported`` is what
    the margin inspector puts on screen. The first passed all along and is kept
    so a future failure can be told apart from a reporting artefact; the second
    failed for 45 of the 119 charts before #167.
    """
    analytic: list[str] = []
    reported: list[str] = []
    n = 0
    for slug, preset in _builtin_presets_with_recipes():
        thr = _own_thresholds(preset)
        if not thr:
            continue
        n += 1
        geom, layout, w_mm, h_mm, _dpi = _laid_out(preset)
        realised = dict(zip("LRTB", geometry.realized_margins_mm(
            geom, w_mm, h_mm, layout)))
        for edge, got in realised.items():
            if got < thr[edge] - 1e-6:
                analytic.append(f"{slug} {edge}: {got:.4f} < {thr[edge]}")
        for v in check_violations(_inspector_report(preset), thr):
            reported.append(
                f"{slug}: {v.edge} {v.measured_mm:.4f} < {v.threshold_mm}")
    assert n > 100, f"only {n} built-in recipes found — the discovery broke"
    assert not analytic, ("the engine laid a chart inside its own margin box:\n"
                          + "\n".join(analytic))
    assert not reported, (
        f"{len(reported)} built-in charts accuse themselves of breaking their "
        f"own margins:\n" + "\n".join(reported))


@pytest.mark.parametrize("dpi", [200, 300, 600])
def test_a_shortfall_larger_than_one_pixel_is_still_a_violation(dpi):
    """The tolerance is one device pixel, not an amnesty.

    Without this the fix for the two tests above could be "stop checking".
    """
    px = 25.4 / dpi
    base = dict(left_mm=10.0, top_mm=10.0, bottom_mm=10.0,
                strip_width_mm=None, page_w_mm=210.0, page_h_mm=297.0, dpi=dpi)
    thr = {"L": 10.0, "R": 24.0, "T": 10.0, "B": 10.0}

    within = MarginReport(right_mm=24.0 - 0.9 * px, **base)
    assert check_violations(within, thr) == [], "sub-pixel shortfall must pass"

    over = MarginReport(right_mm=24.0 - 1.5 * px, **base)
    assert [v.edge for v in check_violations(over, thr)] == ["Right"], \
        "a shortfall of more than one pixel must still be flagged"

    gross = MarginReport(right_mm=18.0, **base)
    assert [v.edge for v in check_violations(gross, thr)] == ["Right"]


def test_the_85_display_allowance_survives_an_unknown_dpi():
    """A report with no dpi keeps exactly the old behaviour (#85)."""
    base = dict(right_mm=30.0, top_mm=40.0, bottom_mm=20.0, strip_width_mm=None,
                page_w_mm=210.0, page_h_mm=297.0)
    assert check_violations(MarginReport(left_mm=5.997, **base), {"L": 6.0}) == []
    assert [v.edge for v in check_violations(
        MarginReport(left_mm=5.90, **base), {"L": 6.0})] == ["Left"]


def test_a_coarse_chart_does_not_buy_a_bigger_allowance():
    """The tolerance is capped at one pixel of the coarsest chart we ship.

    `printtarg_dpi` is written from one place only — Create Chart Manual's
    "Save as defaults" — and read by Guided, which has no control for it. One
    "Resolution: 72 dpi" saved there re-rasters every future Guided chart at
    72 dpi and, without this cap, widened this SAFETY check 4.2x: a margin
    0.30 mm short went from flagged to missed.

    200 dpi is the floor because it is the coarsest the built-in charts use.
    """
    from workflow.margin_inspector import MarginReport, _tolerance_mm

    def rep(dpi):
        return MarginReport(6.0, 6.0, 6.0, 6.0, None, 210.0, 297.0, dpi=dpi)

    one_px_at_200 = 25.4 / 200.0
    assert _tolerance_mm(rep(200)) == pytest.approx(one_px_at_200)
    for coarse in (150, 100, 72, 36):
        assert _tolerance_mm(rep(coarse)) == pytest.approx(one_px_at_200), (
            f"a {coarse} dpi chart bought a bigger margin allowance than the "
            "coarsest chart ChromIQ ships")
    # …and a finer chart still gets its own, smaller, pixel.
    assert _tolerance_mm(rep(300)) < one_px_at_200
    assert _tolerance_mm(rep(600)) == pytest.approx(0.05)   # the display floor

