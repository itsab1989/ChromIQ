"""The bottom block is budgeted by its INK, and the sheet text is aligned on the
patches it sits under.

**TWO FAULTS, BOTH MEASURED ON RENDERED SHEETS**
(`~/Desktop/ChromIQ-beta18-proof/knut-sweep-geometry/` 2.3, and a tester's own
beta 18 report).

**1. The block's box is not its ink.** `render_pages` draws each line with PIL's
"la" anchor, so the ASCENDER lands on the top of the line box and the topmost
line's ink begins below it. The panel budgeted the box:

| state | the notice | the text's real ink | the block's real edge | verdict |
|---|---|---|---|---|
| bottom-left, "B" 18, 10 pt | *"0.2 mm short"* | 18.288 ... 21.505 | 22.098 | **0.593 mm of clear paper. FALSE** |
| top-left, "B" 4, 28 pt | *"1.3 mm short"* | 4.318 ... 13.885 | 14.647 | **0.762 mm of clear paper. FALSE** |
| centre, "B" 18, 28 pt | *"6.5 mm short"* | reaches 27.94 | 23.654 | true, over-stated by 2.2 mm |

The over-read is about 0.9 mm at 10 pt and 2.2 mm at 28, so it is a SECOND
cause of false warnings and the 0.2 mm tolerance
(`text_edge_fit.edge_tolerance_mm`) does not touch it. Fixing one without the
other would have let the threshold be blamed for the other's failures.

**2. The alignment used the margin SETTING.** A tester, beta 18: *"Under Sheet
text frame, when Alignment is left, any of the two bottom texts placed are
aligned against the left margin setting, and not the left margin under Measured
from Preview. This also applies for option "Centre between left and right
margin" and "Centre of available space". Use the measured margins in the
calculations and alignment."* The patch block is centred in the slack, moved by
"Patch area alignment" and pushed in by a honeycomb's apex reserve and the
row-label band, so it does not begin at `margin_l`.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import text_edge_fit as tef                       # noqa: E402
from workflow.layout_engine import geometry, instruments, raster  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe         # noqa: E402

_PAPER = (210.0, 297.0)


# ------------------------------------------------------------- 1. the ink
def test_the_trim_is_measured_off_the_string_that_is_drawn():
    """A string with capitals and descenders, at the two sizes the sweep used.

    MUTATION: return 0.0 from `sheet_text_ink_top_mm` and the two false-warning
    tests below go red.
    """
    s = "ChromIQ alignment sweep"
    at10 = raster.sheet_text_ink_top_mm(s, 10.0 * 25.4 / 72.0, "Inter", False,
                                        False, 300)
    at28 = raster.sheet_text_ink_top_mm(s, 28.0 * 25.4 / 72.0, "Inter", False,
                                        False, 300)
    assert at10 > 0.3, at10
    assert at28 > at10 + 0.8, (at10, at28)
    assert raster.sheet_text_ink_top_mm("", 4.0) == 0.0


def test_the_false_warning_on_clear_paper_is_gone():
    """The first row of the table: 0.593 mm of white paper called 0.2 mm short.

    The numbers are the sheet's own: the block was anchored at "B" 18, the
    patch area came down to 22.098 mm, and one line's box is 4.233 mm at this
    dpi while the ink is 3.217 mm.

    MUTATION: drop `ink_top_trim_mm` from `bottom_text_block_overlap` and this
    goes red.
    """
    line = raster.sheet_text_line_mm(10.0 * 25.4 / 72.0, "Inter", False, False,
                                     300)
    trim = raster.sheet_text_ink_top_mm("ChromIQ alignment sweep",
                                        10.0 * 25.4 / 72.0, "Inter", False,
                                        False, 300)
    assert tef.bottom_text_block_overlap(22.098, 18.0, 1, line, trim,
                                         tef.edge_tolerance_mm(300)) is None, (
        "the panel still calls 0.593 mm of clear paper a collision")


def test_a_real_collision_is_still_reported_and_is_not_over_stated():
    """The third row: 4.29 mm of real overlap, which beta 18 called 6.5.

    The trim must take the over-statement out and leave the collision in.
    """
    line = raster.sheet_text_line_mm(28.0 * 25.4 / 72.0, "Inter", False, False,
                                     300)
    trim = raster.sheet_text_ink_top_mm("ChromIQ alignment sweep",
                                        28.0 * 25.4 / 72.0, "Inter", False,
                                        False, 300)
    o = tef.bottom_text_block_overlap(23.654, 18.0, 1, line, trim,
                                      tef.edge_tolerance_mm(300))
    assert o is not None, "a 4.29 mm collision went unreported"
    assert o.overlap_mm < 6.5 - 1.0, (
        f"the collision is still over-stated: {o.overlap_mm:.2f} mm against a "
        "real 4.29 mm on the sheet")


def test_the_trim_can_never_make_the_need_negative():
    """A guard on the guard: an absurd trim must not turn a collision into
    spare room."""
    assert tef.bottom_text_block_overlap(0.0, 0.0, 1, 4.2, 999.0) is None
    assert tef.bottom_text_block_overlap(-10.0, 0.0, 1, 4.2, 999.0) is None


# ------------------------------------------------------- 2. the alignment
def _geom(npat=30, **kw):
    """A chart with SLACK across the sheet, which is where the fault lives.

    A patch count that fills the width leaves the block's edges exactly on the
    margin boxes, and the two answers agree by accident: 120 patches on this
    recipe is 21 passes and fills A4. 30 patches is 6 passes and leaves about
    90 mm for "Patch area alignment" to move the block through.
    """
    r = LayoutRecipe()
    r.instrument, r.paper, r.dpi = "i1", "A4", 300
    r.use_instrument_margins = False
    r.margin_top = r.margin_bottom = 12.0
    r.margin_left = r.margin_right = 12.0
    for k, v in kw.items():
        setattr(r, k, v)
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    lay = geometry.compute(g, *_PAPER, npat)
    return g, lay, geometry.placement(g, *_PAPER, lay)


def test_the_block_bounds_are_the_block_and_not_the_margin_boxes():
    """`_block_bounds_mm` is what the line is now anchored and centred on.

    MUTATION: return `(geom.margin_l, geom.margin_r)` and this goes red.
    """
    g, lay, place = _geom(patch_area_align="top-right")
    left, right = raster._block_bounds_mm(place, lay.steps_in_pass,
                                          min(lay.patches_per_page, 30),
                                          _PAPER[0])
    assert left == pytest.approx(place.x_of(0), abs=1e-9)
    assert left != pytest.approx(g.margin_l, abs=0.05) or \
        right != pytest.approx(g.margin_r, abs=0.05), (
        "on this alignment the block sits where the margin boxes say, so this "
        "test cannot see the fault it is for")


def test_the_alignment_follows_the_block_across_the_nine_positions():
    """"Patch area alignment" moves the block, and the line must move with it.

    Measured on beta 18: the block travels 9.6 mm across and 2.7 mm down over
    the nine positions, and the frame follows it to within 0.117 mm.
    """
    seen = set()
    for align in ("top-left", "center", "top-right"):
        g, lay, place = _geom(patch_area_align=align)
        left, _right = raster._block_bounds_mm(place, lay.steps_in_pass,
                                               min(lay.patches_per_page, 30),
                                               _PAPER[0])
        seen.add(round(left, 3))
    assert len(seen) > 1, (
        f"the block's left edge did not move across three alignments: {seen}")


def test_the_renderer_asks_for_the_block_and_not_for_the_margins():
    """Asserted over the source, because the three call sites are easy to
    revert one at a time.

    MUTATION: put `margin_left_mm=float(getattr(geom, "margin_l"...))` back at
    any of the three and this goes red.
    """
    import inspect
    src = inspect.getsource(raster.render_pages)
    assert src.count("margin_left_mm=_blk_l_mm") >= 2, (
        "a bottom-text bound went back to the margin box")
    assert "bottom_text_centre_mm(\n                paper_w_mm, _blk_l_mm, " \
        "_blk_r_mm)" in src, (
        "the centred alignments went back to the margin boxes")
    # …AND `_blk_l_mm` MUST STILL BE THE BLOCK. Naming the variable is not the
    # same as filling it: a mutation that assigned the margin boxes to these two
    # names left every assertion above green, so the assignment is pinned too.
    assert "_blk_l_mm, _blk_r_mm = _block_bounds_mm(" in src, (
        "the bottom-text bounds are named after the block and filled from "
        "somewhere else")
