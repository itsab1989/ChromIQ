"""Clip text printed over the patch area lands ON the patches, not INSTEAD of them.

Knut, #182, 2026-09-12:

    "The text on each of the 4 sides shall NOT cross the text-edge distance
    limit on every side. If the patch area with its margins are pushing against
    these limits, the text shall overlap in the other direction, inward and
    over the edges of the patch area instead. When this happens the warning
    texts shall appear, informing the user, as described and defined earlier."

**THE TRAP THIS FILE EXISTS FOR.** `raster.render_clip_strip` returns an image
with an OPAQUE WHITE background and `render_page` used to paste it whole, which
is correct while the rectangle covers only the band's own reserved paper.
Extending that rectangle over the patch area without changing anything else
would not have printed the text on the patches: it would have WIPED every patch
under the band to paper white. A patch that reads as paper is not a wrong
colour a user might notice on screen, it is a plausible one that `chartread`
records and `colprof` builds into the profile.

So the overhang is composited through an ink mask, and this file measures that
on a page the renderer actually produced: under the overhang the patch colour
survives everywhere the glyphs are not.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                        # noqa: E402
import pytest                                             # noqa: E402

from workflow import text_edge_fit as tef                 # noqa: E402
from workflow.layout_engine import geometry, instruments, raster  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe   # noqa: E402
from workflow.layout_engine.ti1_reader import ColorTarget  # noqa: E402

#: A mid-grey patch set: far enough from paper white that "wiped to paper" and
#: "printed on" cannot be confused, and far enough from black that the glyph
#: ink is distinguishable from the patch.
_DEV = (50.0, 50.0, 50.0)
_XYZ = (18.0, 19.0, 21.0)
_LINES = ["clip line one", "clip line two", "clip line three", "clip line four",
          "clip line five", "clip line six"]


def _recipe(band_mm: float) -> LayoutRecipe:
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = "CM", "A4", "area_first"
    r.clip_border, r.clip_border_width_mm = True, band_mm
    r.clip_side, r.clip_content_mode = "right", "text"
    r.clip_text = "\n".join(_LINES)
    r.clip_text_size_mm = 0.0
    r.text_edge_clip_mm = 4.0
    # THE MARGIN AT THE BAND is the ordinary clip chart, and it is the only
    # arrangement in which the overflow can reach the patches at all:
    # `instruments.geom_from_build_kwargs` raises this margin to the band and
    # never above it, so a wider margin simply leaves clear paper in between.
    r.margin_right = band_mm
    r.margin_left = 14.0
    r.margin_top = r.margin_bottom = 10.0
    r.show_strip_indicators, r.show_row_indicators = False, False
    r.helper_markers = False
    r.randomize, r.seed_fixed, r.seed = False, True, 7
    return r


def _page(band_mm: float):
    r = _recipe(band_mm)
    kw = r.build_kwargs()
    g = instruments.geom_from_build_kwargs(kw)
    lay = geometry.compute(g, 210.0, 297.0, 120)
    target = ColorTarget(color_rep="iRGB",
                         device_fields=["RGB_R", "RGB_G", "RGB_B"],
                         patches=[(_DEV, _XYZ) for _ in range(120)])
    res = raster.render_pages(target, lay, g, seed=7, randomize=False,
                              paper_w_mm=210.0, paper_h_mm=297.0, dpi=200,
                              clip_content_mode="text",
                              clip_text=r.clip_text,
                              clip_text_size_mm=0.0,
                              clip_flip_180=False)
    return r, g, lay, np.asarray(res.images[0])


#: The band that makes the text overflow far enough to reach the patch area.
_BAND = 10.0


def test_the_case_is_set_up_so_the_text_really_does_reach_the_patches():
    """A test that measures a sheet with no overlap on it proves nothing."""
    r, g, _lay, _img = _page(_BAND)
    zone = g.lbord + g.border
    over = tef.clip_text_overhang_mm(zone, r.text_edge_clip_mm, len(_LINES))
    assert over > 1.0, f"only {over:.2f} mm reaches past the band"
    assert zone + over > float(g.margin_r) + 0.5, (
        "the overflow stops short of the patch area, so this file is looking "
        "at clear paper")


def _overhang_strips(g, lay, img):
    """For every patch the band's overhang covers, the PART of that patch the
    overhang actually lies on.

    THE WHOLE PATCH IS THE WRONG WINDOW, and the first version of this file
    used it and proved nothing: on this chart the overhang covers 77 px of a
    244 px patch column, so an opaque paste whitens 32 % of each patch and a
    "less than half is paper" assertion passes with the fault in place. What
    must be looked at is the strip the overhang lies on, where an opaque paste
    gives paper everywhere and a composite gives paper only between the glyphs.
    """
    rects = geometry.patch_rects_px(g, 210.0, 297.0, lay, 200)
    W = img.shape[1]
    mm2px = 200 / 25.4
    zone = g.lbord + g.border
    over = tef.clip_text_overhang_mm(zone, g.text_edge_clip_mm, len(_LINES))
    inner_px = W - int(round((zone + over) * mm2px))      # the overhang's edge
    band_px = W - int(round(zone * mm2px))
    out = []
    for rc in rects:
        x0, x1 = int(rc["x"]), int(rc["x"]) + int(rc["w"])
        lo, hi = max(x0, inner_px), min(x1, band_px)
        if hi - lo < 8:
            continue
        y0 = int(rc["y"])
        out.append((rc, img[y0:y0 + int(rc["h"]), lo:hi]))
    return out


def test_a_patch_under_the_text_keeps_its_colour_everywhere_the_glyphs_are_not():
    _r, g, lay, img = _page(_BAND)
    hit = _overhang_strips(g, lay, img)
    assert hit, "no patch falls under the overhang"
    worst = 0.0
    for rc, sub in hit:
        # Paper white is 255; the patch is mid grey. An opaque paste makes the
        # whole strip paper.
        worst = max(worst, float((sub.min(axis=2) > 240).mean()))
    assert worst < 0.5, (
        f"{worst:.0%} of the strip the clip text lies on reads as blank paper, "
        f"so the strip is being pasted over the patches instead of composited "
        f"onto them")


def test_the_text_really_is_printed_on_those_patches():
    """The other half: the ink IS there, so the overlap is not simply absent."""
    _r, g, lay, img = _page(_BAND)
    hit = _overhang_strips(g, lay, img)
    assert hit
    inked = sum(1 for _rc, sub in hit if (sub.min(axis=2) < 60).any())
    assert inked, "no glyph ink landed on any patch under the overhang"


def test_a_patch_clear_of_the_band_is_untouched():
    """The negative half. Nothing outside the overhang may change at all."""
    _r, g, lay, img = _page(_BAND)
    rects = geometry.patch_rects_px(g, 210.0, 297.0, lay, 200)
    hit = {id(rc) for rc, _sub in _overhang_strips(g, lay, img)}
    clear = [rc for rc in rects if id(rc) not in hit]
    assert clear
    for rc in clear[:40]:
        x0, y0 = int(rc["x"]), int(rc["y"])
        x1, y1 = x0 + int(rc["w"]), y0 + int(rc["h"])
        sub = img[y0:y1, x0:x1]
        assert (sub.min(axis=2) > 240).mean() < 0.02, (
            f"patch {rc.get('loc')} is clear of the clip band and has been "
            f"whitened anyway")


def test_a_band_wide_enough_puts_nothing_on_any_patch():
    """And with room, no patch is touched at all."""
    wide = tef.clip_band_needed_mm(4.0, len(_LINES)) + 1.0
    r, g, lay, img = _page(round(wide, 1))
    zone = g.lbord + g.border
    assert tef.clip_text_overhang_mm(zone, r.text_edge_clip_mm,
                                     len(_LINES)) == pytest.approx(0.0)
    rects = geometry.patch_rects_px(g, 210.0, 297.0, lay, 200)
    for rc in rects[:60]:
        x0, y0 = int(rc["x"]), int(rc["y"])
        x1, y1 = x0 + int(rc["w"]), y0 + int(rc["h"])
        sub = img[y0:y1, x0:x1]
        assert (sub.min(axis=2) < 60).mean() < 0.001, (
            f"patch {rc.get('loc')} carries clip-text ink on a band with room")


def _page_flipped(band_mm: float, flip: bool, size_pt: float):
    """A whole page through `render_pages`, with the flip and a TYPED size.

    A typed size is what leaves slack in the band; "auto" grows the type until
    the block fills it, and a block that fills its band cannot show which end
    it is anchored to.
    """
    r = _recipe(band_mm)
    r.clip_text_size_mm = size_pt * 25.4 / 72.0
    r.clip_flip_180 = flip
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    lay = geometry.compute(g, 210.0, 297.0, 120)
    target = ColorTarget(color_rep="iRGB",
                         device_fields=["RGB_R", "RGB_G", "RGB_B"],
                         patches=[(_DEV, _XYZ) for _ in range(120)])
    res = raster.render_pages(target, lay, g, seed=7, randomize=False,
                              paper_w_mm=210.0, paper_h_mm=297.0, dpi=200,
                              clip_content_mode="text", clip_text=r.clip_text,
                              clip_text_size_mm=r.clip_text_size_mm,
                              clip_flip_180=flip)
    return g, np.asarray(res.images[0])


def test_flipping_the_content_does_not_move_which_end_overflows_on_a_real_page():
    """The wiring, not only `_vtext`'s argument.

    `render_page` has to pass the flip down as the anchor, or turning the strip
    over moves the block to the patch side and it grows toward the paper edge
    again. Measured on a whole page, through the renderer, on a RIGHT-hand band
    whose page-edge end is the high column.
    """
    band, size_pt = 24.0, 5.0
    seen = {}
    for flip in (False, True):
        g, img = _page_flipped(band, flip, size_pt)
        W = img.shape[1]
        mm2px = 200 / 25.4
        zone = g.lbord + g.border
        inset = tef.clip_content_inset_mm(zone, g.text_edge_clip_mm)
        lo = W - int(round(zone * mm2px))
        hi = W - int(round(inset * mm2px))
        strip = img[:, lo:hi]
        cols = np.flatnonzero((strip.min(axis=2) < 120).any(axis=0))
        assert len(cols), f"nothing printed in the band (flip={flip})"
        seen[flip] = (int(cols[0]), int(cols[-1]), hi - lo)
    width = seen[False][2]
    # THE PAGE-EDGE END of a right-hand band is the HIGH column of the rect, and
    # the block must END there, within a line's worth of rounding. "In the
    # right-hand three quarters" is NOT enough: with six lines at 5 pt the
    # block is two thirds of this band, so a block anchored at the WRONG end
    # still reaches past three quarters and the mutation goes uncaught.
    line_px = tef.CLIP_LINE_SPACING * tef.pt_to_px(size_pt, 200)
    for flip, (first, last, _w) in seen.items():
        assert width - last <= line_px, (
            f"flip={flip}: the block sits at columns {first}..{last} of "
            f"{width} and stops {width - last} px short of the page-edge end, "
            f"so it is anchored at the patch end and grows toward the paper "
            f"edge")
    assert abs(seen[False][0] - seen[True][0]) <= line_px, (
        f"the flip moved the block: {seen[False]} vs {seen[True]}")
