"""B8-1540 (Knut, #182 5857405680): a patch size typed in "Prioritise patch
size, then fit to page" still ruled the chart after switching to "Prioritise
chart area, then fit patches to it" and "By columns / rows".

`instruments.geom_from_build_kwargs` derives an area-first patch size only
when the kwargs carry none, and `LayoutRecipe.build_kwargs` passed the
patch-first size through in every mode. Measured on screen (i1Pro, A4,
margins 20 mm, 14 x 10 mm typed, then 8 strips by 12 rows): 11 strips of 22
at 14 mm, 32 / 24 / 26 / 21 mm from the edges. The chart offset, hidden in
area-first for the same reason, leaked the same way.

The recipe still HOLDS the values, so switching back gives them back.

B8-1590 (Knut, #182 5858752082): the PATCH SCALE is not one of them. It is shown
in "Prioritise chart area" and his presets rely on it there ("it has been the
intention that it should work, and did work before"); beta 45 held it back and
changed 19 of his built-in presets. It reaches the engine in both modes."""
from __future__ import annotations

import pytest

from workflow.layout_engine import geometry, instruments, papers
from workflow.layout_engine.presets import LayoutRecipe


def _area_recipe(**over) -> LayoutRecipe:
    r = LayoutRecipe(instrument="i1", paper="A4")
    r.layout_mode = "area_first"
    r.area_method = "by_grid"
    r.area_cols, r.area_rows = 8, 12
    r.margin_top = r.margin_right = r.margin_bottom = r.margin_left = 20.0
    for k, v in over.items():
        setattr(r, k, v)
    return r


def _laid_out(r: LayoutRecipe):
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    w, h = papers.dimensions_mm(r.paper)
    lay = geometry.compute(g, w, h, 100_000)
    return round(g.pwid, 3), round(g.plen, 3), lay.patches_per_page, \
        g.offset_x, g.offset_y


_PATCH_FIRST_ONLY = {
    "patch size": dict(patch_w_mm=14.0, patch_h_mm=10.0),
    "chart offset": dict(offset_x_mm=6.0, offset_y_mm=6.0),
}


@pytest.mark.parametrize("what", list(_PATCH_FIRST_ONLY))
@pytest.mark.parametrize("method", ["by_grid", "by_width"])
def test_a_patch_first_setting_does_not_change_an_area_first_chart(what, method):
    clean = _laid_out(_area_recipe(area_method=method))
    typed = _laid_out(_area_recipe(area_method=method, **_PATCH_FIRST_ONLY[what]))
    assert typed == clean


@pytest.mark.parametrize("method", ["by_grid", "by_width"])
def test_the_patch_scale_changes_an_area_first_chart(method):
    """B8-1590: the one control area-first shows that B8-1540 had silenced."""
    clean = _laid_out(_area_recipe(area_method=method))
    scaled = _laid_out(_area_recipe(area_method=method, pscale=1.3))
    assert scaled != clean
    assert _area_recipe(pscale=0.95).build_kwargs()["pscale"] == 0.95


def test_by_columns_rows_lays_out_the_grid_asked_for_with_a_typed_size():
    _, _, per_page, _, _ = _laid_out(_area_recipe(
        patch_w_mm=14.0, patch_h_mm=10.0, pscale=1.3,
        offset_x_mm=6.0, offset_y_mm=6.0))
    assert per_page == 8 * 12


def test_the_recipe_keeps_what_was_typed_for_the_way_back():
    r = _area_recipe(patch_w_mm=14.0, patch_h_mm=10.0, pscale=1.3,
                     offset_x_mm=6.0, offset_y_mm=6.0)
    kw = r.build_kwargs()
    assert (kw["patch_w"], kw["patch_h"], kw["pscale"],
            kw["offset_x"], kw["offset_y"]) == (None, None, 1.3, 0.0, 0.0)
    assert (r.patch_w_mm, r.patch_h_mm, r.pscale, r.offset_x_mm,
            r.offset_y_mm) == (14.0, 10.0, 1.3, 6.0, 6.0)
    r.layout_mode = "patch_first"
    kw = r.build_kwargs()
    assert (kw["patch_w"], kw["patch_h"], kw["pscale"],
            kw["offset_x"], kw["offset_y"]) == (14.0, 10.0, 1.3, 6.0, 6.0)


def test_patch_first_still_honours_a_typed_size():
    r = _area_recipe(layout_mode="patch_first", patch_w_mm=14.0, patch_h_mm=10.0)
    pw, ph, _, _, _ = _laid_out(r)
    assert (pw, ph) == (14.0, 10.0)


def test_the_alignment_is_left_to_the_recipe():
    # Built-in area-first presets set "top-left" on purpose; only the hidden
    # size and offset are neutralised.
    kw = _area_recipe(patch_area_align="top-left").build_kwargs()
    assert kw["patch_area_align"] == "top-left"
