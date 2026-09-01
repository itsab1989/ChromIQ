"""§R1.2 — the row labels are POSITIONED by "Clip", not by the patch block.

Knut, beta 6, three times over: *"I think it is important that the row label's
position are movable and definable using currently defined parameters, just
like the strip labels, and not fixed."* Beta 6 built the LIMIT half of his rule
(they may never come closer to the page edge than Clip) and not the POSITION
half: the labels were placed at ``x0 - 1 mm - text width`` from the patch
block, with Clip as a floor they never reached. Sweeping Clip from 0 to 25 mm
with the left margin pinned moved them **0.00 mm** on all four of his presets.

THE MARGIN IS PINNED IN EVERY TEST HERE, and that is the point. On the
ColorMunki and Scanner presets Clip *appears* to move the labels even on the
old code, because it raises the automatic left-margin floor, which moves the
patch block, which drags the labels along. A test that leaves the margin at its
minimum passes on the broken build.
"""
from __future__ import annotations

import numpy as np
import pytest

from workflow.layout_engine import geometry, instruments, papers, raster
from workflow.layout_engine.presets import LayoutRecipe
from workflow.layout_engine.ti1_reader import ColorTarget

_DPI, _N = 150, 240
_PX = _DPI / 25.4
#: Wide enough that the automatic raise cannot reach it, so nothing but the
#: Clip setting can move anything. This is the pin.
_PINNED_MARGIN = 50.0


def _recipe(*, clip: float, instrument="i1", border=False,
            margin_l: float = _PINNED_MARGIN, rows=True):
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = instrument, "A4", "area_first"
    r.area_method, r.area_cols, r.area_rows = "by_grid", 8, 12
    r.show_strip_indicators, r.show_row_indicators = True, rows
    r.clip_border = border
    r.clip_border_width_mm = 26.0
    r.clip_side = "left"
    r.clip_content_mode = "off"
    r.text_edge_clip_mm = clip
    r.margin_top = r.margin_right = r.margin_bottom = 10.0
    r.margin_left = margin_l
    r.dpi, r.randomize, r.seed = _DPI, False, 1
    return r


def _render(r):
    kw = r.build_kwargs()
    g = instruments.geom_from_build_kwargs(kw)
    w_mm, h_mm = papers.dimensions_mm(r.paper)
    lay = geometry.compute(g, w_mm, h_mm, _N)
    t = ColorTarget(color_rep="iRGB", device_fields=["RGB_R", "RGB_G", "RGB_B"],
                    patches=[((30.0, 70.0, 55.0), (40.0, 45.0, 50.0))
                             for _ in range(_N)])
    res = raster.render_pages(
        t, lay, g, seed=1, randomize=False, paper_w_mm=w_mm, paper_h_mm=h_mm,
        dpi=_DPI, draw_indicators=bool(kw.get("draw_indicators", True)),
        clip_content_mode="off",
        patch_pattern=kw.get("patch_pattern") or "0-9,@-9,@-9;1-999")
    place = geometry.placement(g, w_mm, h_mm, lay)
    return np.asarray(res.images[0].convert("L")), g, place


def _label_ink_mm(r) -> "tuple[float, float]":
    """(left, right) edge of the ROW-LABEL ink in mm, as a difference against
    a control render with the row indicators off at the identical geometry.

    A difference, not "dark pixels in the left 40 mm": that would count the
    clip border, the helper markers and the patches themselves, and would go
    on reporting a number after the labels stopped being drawn at all.
    """
    page, g, _place = _render(r)
    off = _recipe(clip=r.text_edge_clip_mm, instrument=r.instrument,
                  border=r.clip_border, margin_l=r.margin_left, rows=False)
    off.margin_left = g.margin_l          # identical patch block
    control, _cg, _cp = _render(off)
    h = min(page.shape[0], control.shape[0])
    w = min(page.shape[1], control.shape[1])
    diff = (page[:h, :w].astype(int) - control[:h, :w].astype(int)) < -40
    cols = np.where(diff.any(axis=0))[0]
    assert len(cols), "no row-label ink at all — the control cancelled them out"
    return float(cols.min()) / _PX, float(cols.max() + 1) / _PX


# ---------------------------------------------------------------- the pin ---
def test_the_pin_holds_so_the_sweep_proves_something():
    """The premise. If the patch block moves with Clip, every number below is
    measuring the patches dragging the labels, which is the very fault."""
    x0s, margins = set(), set()
    for clip in (2.0, 10.0, 25.0):
        _page, g, place = _render(_recipe(clip=clip))
        x0s.add(round(place.x_of(0), 2))
        margins.add(round(g.margin_l, 2))
    assert len(x0s) == 1 and len(margins) == 1, (
        f"the patch block moved during the sweep ({x0s}, {margins}); pin the "
        f"left margin higher or this test proves nothing")


# ------------------------------------------------------- the position rule ---
@pytest.mark.parametrize("instrument", ["i1", "CM", "SS", "CR30"])
def test_clip_moves_the_row_labels(instrument):
    near = _label_ink_mm(_recipe(clip=2.0, instrument=instrument))
    far = _label_ink_mm(_recipe(clip=25.0, instrument=instrument))
    assert far[0] > near[0] + 20.0, (
        f"{instrument}: Clip 2 mm put the labels at {near[0]:.2f} mm and "
        f"Clip 25 mm at {far[0]:.2f} mm — the setting Knut named does not "
        f"move them")


def test_the_labels_land_where_clip_says():
    """One for one, the way the strip labels follow "Top"."""
    for clip in (2.0, 6.0, 12.0, 20.0, 30.0):
        left, _right = _label_ink_mm(_recipe(clip=clip))
        assert clip <= left <= clip + 2.0, (
            f"Clip {clip:.0f} mm put the label ink at {left:.2f} mm; it should "
            f"start at Clip plus the band's 1 mm of air")


def test_a_wide_margin_no_longer_drags_the_labels_to_the_patches():
    """The fault in one assertion: the labels stayed 1 mm from the patch block
    whatever Clip said, so they moved when the MARGIN moved and not when the
    setting for them moved."""
    at50 = _label_ink_mm(_recipe(clip=4.0, margin_l=50.0))
    at70 = _label_ink_mm(_recipe(clip=4.0, margin_l=70.0))
    assert abs(at50[0] - at70[0]) < 0.3, (
        f"widening the left margin from 50 to 70 mm moved the labels from "
        f"{at50[0]:.2f} to {at70[0]:.2f} mm — they are still anchored to the "
        f"patches instead of to the page edge")


# ------------------------------------------------------------ the limit ------
def test_the_clip_border_still_holds_them_off_it():
    """§R1.3, the half beta 6 did build, must survive the new anchor: with a
    26 mm border on the left, a 4 mm Clip may not put the labels under it."""
    left, _right = _label_ink_mm(_recipe(clip=4.0, border=True))
    assert left >= 26.0, (
        f"the labels start at {left:.2f} mm on a 26 mm clip border, so the "
        f"border is printed over them")


def test_they_never_reach_into_the_patch_block():
    """The other clamp: an absurd Clip may not push them over the patches."""
    r = _recipe(clip=60.0)
    _page, _g, place = _render(r)
    _left, right = _label_ink_mm(r)
    assert right <= place.x_of(0), (
        f"label ink ends at {right:.2f} mm and the patches start at "
        f"{place.x_of(0):.2f} mm")


# --------------------------------------------------- nothing else moved ------
def test_a_chart_at_the_automatic_minimum_margin_is_unchanged():
    """Every shipped preset sits at the automatic minimum left margin, where
    `floor + band` IS `x0 - 1 mm`. The new anchor must produce exactly the old
    placement there, or existing charts would re-print differently."""
    for instrument in ("i1", "CM", "SS", "CR30"):
        r = _recipe(clip=4.0, instrument=instrument, margin_l=1.0)
        _page, g, place = _render(r)
        assert g.margin_l > 1.0, "the margin was not raised, so this is not the case being tested"
        _left, right = _label_ink_mm(r)
        assert place.x_of(0) - 2.0 <= right <= place.x_of(0), (
            f"{instrument}: at the automatic minimum margin the labels ended "
            f"at {right:.2f} mm with the patches at {place.x_of(0):.2f} mm; "
            f"they used to end 1 mm before them")
