"""Prioritise chart area means the margins are the law — row labels or not.

Knut, #93: *"the whole patch area shall always follow the margins as law,
especially when Prioritise chart area"*. Switching row indicators on made the
patch block stop 7.45 mm short of the right margin while still starting at the
left one.

DRIVEN THROUGH THE REAL RECIPE PATH, and rendered. The first version of this
test built a `Geom` by hand with `fill_beyond_ruler=True` and asserted on
`area_fit._usable` — a state that path never produces, because
`derive_area_patch_size` flips the mode to "patch_first" to get an automatic
patch size and `geom_from_build_kwargs` derives BOTH law flags from the mode.
So the test passed, the guard it guarded was dead code, and every rendered
right edge was bit-identical to the unfixed tree. A challenge caught it. What
is asserted now is the thing a user can see: where the ink stops.
"""
import numpy as np
import pytest

from workflow.layout_engine import geometry, instruments, papers, raster
from workflow.layout_engine.presets import LayoutRecipe
from workflow.layout_engine.ti1_reader import ColorTarget

_DPI = 150
_MARGIN = 6.0
_N = 240


def _page(instrument: str, paper: str, mode: str, rows: bool,
          margin_left: float = _MARGIN):
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = instrument, paper, mode
    r.show_row_indicators, r.show_strip_indicators = rows, True
    r.margin_top = r.margin_right = r.margin_bottom = _MARGIN
    r.margin_left = margin_left
    r.dpi, r.randomize, r.seed = _DPI, False, 1
    kw = r.build_kwargs()
    g = instruments.geom_from_build_kwargs(kw)
    w_mm, h_mm = papers.dimensions_mm(paper)
    lay = geometry.compute(g, w_mm, h_mm, _N)
    target = ColorTarget(
        color_rep="iRGB", device_fields=["RGB_R", "RGB_G", "RGB_B"],
        patches=[((20.0, 60.0, 40.0), (40.0, 45.0, 50.0)) for _ in range(_N)])
    res = raster.render_pages(target, lay, g, seed=1, randomize=False,
                              paper_w_mm=w_mm, paper_h_mm=h_mm, dpi=_DPI,
                              draw_indicators=True)
    return np.asarray(res.images[0].convert("L")), w_mm


def _rightmost_ink_mm(page, w_mm):
    """Where the ink stops, in mm from the left edge of the paper."""
    cols = np.where((page < 250).any(axis=0))[0]
    if not len(cols):
        pytest.fail("nothing was drawn on the page")
    return (cols.max() + 1) / (_DPI / 25.4)


@pytest.mark.parametrize("instrument", ["i1", "CM", "CR30"])
def test_the_band_takes_nothing_off_the_patch_area(instrument):
    """The band costs the MARGIN, never the patch area.

    This used to assert that the right edge was identical with and without row
    indicators. That was the right rule while the band was carved out of the
    usable width; it stopped being the rule when Knut's §R1.5 was built, since
    the left margin is now raised to hold the labels and a chart that does not
    fill the page therefore ends further right. What must still be true — and
    is the whole of §R1.4 — is that nothing is taken off the patch area a
    second time: a chart with labels lays out exactly like a chart with no
    labels and the same effective margin.
    """
    from workflow.layout_engine import instruments as _instr

    labelled = _recipe_geom(instrument, rows=True)
    plain = _recipe_geom(instrument, rows=False,
                         margin_left=labelled.margin_l)
    assert labelled.margin_l >= 6.0, "the margin was lowered, never allowed"
    on, w = _page(instrument, "A4", "area_first", rows=True)
    off, _ = _page(instrument, "A4", "area_first", rows=False,
                   margin_left=labelled.margin_l)
    assert _rightmost_ink_mm(on, w) == pytest.approx(
        _rightmost_ink_mm(off, w), abs=0.2), (
        f"{instrument}: with the same left margin, a chart with row labels "
        f"does not lay out like one without — the band is still being taken "
        f"off the patch area on top of the margin it was given")


def _recipe_geom(instrument, *, rows, margin_left=6.0):
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = instrument, "A4", "area_first"
    r.show_row_indicators, r.show_strip_indicators = rows, True
    r.margin_top = r.margin_right = r.margin_bottom = _MARGIN
    r.margin_left = margin_left
    r.dpi, r.randomize, r.seed = _DPI, False, 1
    return instruments.geom_from_build_kwargs(r.build_kwargs())


def test_the_derived_patch_size_is_the_same_for_the_same_box():
    """The calculation and the render must agree; this is where they parted.

    Compared at the SAME effective left margin, because the margin is now
    raised to hold the labels (§R1.5) — the patch size may differ when the box
    differs, and must not differ when it does not.
    """
    from workflow.layout_engine.area_fit import derive_area_patch_size

    labelled = _recipe_geom("CM", rows=True)
    sizes = {}
    for rows in (False, True):
        r = LayoutRecipe()
        r.instrument, r.paper, r.layout_mode = "CM", "A4", "area_first"
        r.show_row_indicators, r.show_strip_indicators = rows, True
        r.margin_top = r.margin_right = r.margin_bottom = _MARGIN
        r.margin_left = labelled.margin_l
        sizes[rows] = derive_area_patch_size(r.build_kwargs())
    # 0.05 mm, not exact: the patch size comes out of a 40-step binary search,
    # and two runs over the same box converge to within a couple of hundredths
    # of a millimetre. The rule is "the band does not change the size"; 20
    # microns is not the band.
    assert sizes[True][0] == pytest.approx(sizes[False][0], abs=0.05), (
        f"the row-label band changed the derived patch size: {sizes}")
    assert sizes[True][1] == pytest.approx(sizes[False][1], abs=0.05), (
        f"the row-label band changed the derived patch height: {sizes}")


def test_patch_first_still_reserves_the_band():
    """The other branch, so the fix cannot have simply removed the band."""
    off, w = _page("CM", "A4", "patch_first", rows=False)
    on, _ = _page("CM", "A4", "patch_first", rows=True)
    assert _rightmost_ink_mm(on, w) != pytest.approx(_rightmost_ink_mm(off, w),
                                                     abs=0.2), (
        "patch-first stopped reserving the row-label band, which it must")
