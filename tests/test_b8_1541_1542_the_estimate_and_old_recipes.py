"""B8-1541 and B8-1542: the layout estimate, and recipes older than layout_mode.

B8-1541. In "Prioritise chart area" the Chart layout information's estimate
column read 96 patches on 1 page beside 240 on 3 "on screen". MEASURED ON
SCREEN (scripts/drive_b8_1541_layout_estimate.py): the estimate was right. The
panel defines it as what Generate would produce, and pressing Generate built
exactly the estimate in every case driven: By columns / rows and By patch width,
1, 2 and 3 pages, and patch-first. The "on screen" column showed the previous
chart's patches re-laid out by "Auto-update preview" (its window says so: it
"re-lays-out the patches already in your chart"), and the amber marks that
difference, which is what it is for. So nothing was changed in the app; what is
guarded here is the promise: with "Auto patch count" on, Generate takes the
estimate's count, and the engine then sizes the patches FOR that count
(`area_target_count`). If that sizing ever moved the layout, the estimate would
promise one chart and Generate build another.

B8-1542. `layout_mode` arrived on 2026-06-28 together with area-first, so a
stored recipe without it was laid out patch-first. After B8-1540 area-first
ignores a typed patch size, so reading such a recipe as area-first (the dataclass
default) threw its typed size away. One reading, `stored_layout_mode`, used by
`LayoutRecipe.from_dict`, and every helper that rebuilds a stored recipe goes
through `from_dict`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from workflow.layout_engine import geometry, instruments, papers
from workflow.layout_engine.presets import LayoutRecipe, stored_layout_mode

ROOT = Path(__file__).resolve().parents[1]


def _recipe(**kw) -> LayoutRecipe:
    # area_ratio 1.0: the panel's own default (its box runs 10 % to 1000 %),
    # so this is the recipe the app hands Generate.
    base = dict(instrument="i1", paper="A4", margin_top=20.0,
                margin_right=20.0, margin_bottom=20.0, margin_left=20.0,
                use_instrument_margins=False, area_ratio=1.0)
    base.update(kw)
    return LayoutRecipe(**base)


_CASES = [
    pytest.param(dict(layout_mode="area_first", area_method="by_grid",
                      area_cols=8, area_rows=12), id="by-columns-rows"),
    pytest.param(dict(layout_mode="area_first", area_method="by_width"),
                 id="by-patch-width"),
    pytest.param(dict(layout_mode="patch_first", patch_w_mm=14.0,
                      patch_h_mm=10.0), id="patch-first"),
]


@pytest.mark.parametrize("pages", [1, 2, 3])
@pytest.mark.parametrize("kw", _CASES)
def test_generate_builds_the_layout_the_estimate_promised(kw, pages):
    r = _recipe(**kw)
    w, h = papers.dimensions_mm(r.paper)
    # The estimate, as `_refresh_layout_estimate` makes it with Auto on and
    # no patch set armed: a capacity fill of the pages asked for.
    est_kw = r.build_kwargs()
    g0 = instruments.geom_from_build_kwargs(est_kw)
    total = geometry.patches_per_sheet(g0, w, h) * pages
    promised = geometry.compute(g0, w, h, total)
    # Generate: that count laid out, with the count handed to the engine as
    # `build_chart` hands it (`area_target_count`, from the .ti1).
    gen_kw = {**r.build_kwargs(), "area_target_count": total}
    g1 = instruments.geom_from_build_kwargs(gen_kw)
    built = geometry.compute(g1, w, h, total)
    assert (built.pages, built.patches_per_page, built.steps_in_pass,
            built.total_patches) == (promised.pages, promised.patches_per_page,
                                     promised.steps_in_pass,
                                     promised.total_patches)
    assert built.pages == pages
    assert (round(g1.pwid, 2), round(g1.plen, 2)) == (round(g0.pwid, 2),
                                                      round(g0.plen, 2))


# ---- B8-1542 ---------------------------------------------------------------

def _old(**kw) -> dict:
    """A recipe as a build before 2026-06-28 stored it: no layout_mode."""
    d = _recipe().to_dict()
    d.pop("layout_mode")
    d.update(kw)
    return d


@pytest.mark.parametrize("kw", [dict(patch_w_mm=14.0, patch_h_mm=10.0),
                                dict(patch_w_mm=14.0), dict(offset_x_mm=6.0)],
                         ids=["size", "width-only", "offset"])
def test_an_old_recipe_with_patch_first_settings_reads_patch_first(kw):
    r = LayoutRecipe.from_dict(_old(**kw))
    assert r.layout_mode == "patch_first"
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    if "patch_w_mm" in kw:
        assert round(g.pwid, 2) == 14.0


def test_an_old_recipe_without_them_keeps_the_area_first_default():
    """3b6d655c's rule, unchanged for everything B8-1540 did not affect. A
    patch scale alone is not a patch-first setting: area-first shows it and
    honours it (B8-1590), so such a recipe opens as it did in beta 44."""
    assert LayoutRecipe.from_dict(_old()).layout_mode == "area_first"
    assert LayoutRecipe.from_dict(_old(pscale=1.3)).layout_mode == "area_first"
    assert stored_layout_mode({}) == "area_first"


def test_a_recipe_that_names_its_mode_keeps_it():
    d = _recipe(layout_mode="area_first", patch_w_mm=14.0).to_dict()
    assert LayoutRecipe.from_dict(d).layout_mode == "area_first"


def test_the_helpers_read_an_old_recipe_as_the_chart_does():
    """The ring cap reads the recipe through `from_dict`, so an old
    patch-first honeycomb gets its patch-first ring, not an area-first one."""
    from workflow.hex_support import ring_mm_of
    d = _old(instrument="CM", hflag=True, patch_w_mm=14.0, patch_h_mm=14.0,
             margin_left=6.0, margin_right=6.0, margin_top=6.0,
             margin_bottom=6.0)
    want = instruments.geom_from_build_kwargs(
        LayoutRecipe.from_dict(d).build_kwargs())
    assert ring_mm_of(d) == pytest.approx(
        float(getattr(want, "hex_ring_mm", 0.0) or 0.0))


_SITES = ("ui/tabs/tab_chart.py", "ui/tabs/tab_measure.py",
          "workflow/margin_inspector.py", "workflow/hex_support.py")


@pytest.mark.parametrize("rel", _SITES)
def test_no_helper_rebuilds_a_stored_recipe_by_hand(rel):
    """`LayoutRecipe(**{k: v ... })` is the pattern that read an old recipe
    with the dataclass default; the four places that used it go through
    `from_dict` now."""
    src = (ROOT / rel).read_text(encoding="utf-8")
    assert not re.search(r"LayoutRecipe\(\s*\*\*", src), rel
