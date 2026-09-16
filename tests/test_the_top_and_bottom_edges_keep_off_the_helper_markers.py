"""The strip letters and the sheet text keep clear of the ruler helper markers.

Knut, #182, 2026-09-12, once per edge:

    "When helper markers ON: The top-side of the strip labels should be placed
    the following distance from the page top edge: The defined "T" in "Text
    distance from edge" + "Label offset" […], or the defined "Distance from
    page edge" + "Marker length" + 1.0mm + "Label offset" […], whichever is
    largest of the two."

and, for the bottom:

    "Currently, placed "Custom text" and "Stamp layout summary on the sheet"
    text is not moved with changing "B" in "Text distance from edge", and also
    overlaps with the helper markers (if enabled)."

**WHAT WAS MEASURED BEFORE THE FIX**, on the app's own A4 sheets, driven
through the real window (`scripts/drive_182_top_bottom_edges.py`, tag
`before`), markers at "Distance from page edge" 4.0 mm and "Marker length"
2.0 mm, so the dashes occupy 4.0 to 6.0 mm at each edge and Knut's reserve is
7.0 mm:

| | the ink, before | the ink, after |
|---|---|---|
| the strip letters | **5.84 mm**, inside the dashes | 8.38 mm |
| the sheet text, from the bottom | **3.89 mm**, through the dashes | 7.95 mm |

**AND "B" DID MOVE THE TEXT ALL ALONG.** Swept on the same sheets at 2, 4, 8
and 16 mm, the block's ink sat 3.13, 5.08, 9.06 and (off the measured window)
mm up from the paper, so the first half of his bottom report is not reproduced
on the ChromIQ engine path: what moved the text off where he expected it is the
marker reserve, which is the second half. This file pins both anyway, because a
regression in either looks identical on the sheet.

**The markers themselves are never suppressed.** `geometry.helper_marker_lines_mm`
keeps his #152 ruling that a dash is drawn even across other furniture; what
changed is that the TEXT now steps aside, so in the ordinary case there is
nothing to cross.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                             # noqa: E402
import pytest                                                  # noqa: E402

from workflow import text_edge_fit as tef                      # noqa: E402
from workflow.layout_engine import (                           # noqa: E402
    geometry, instruments, papers, raster)
from workflow.layout_engine.presets import LayoutRecipe        # noqa: E402
from workflow.layout_engine.ti1_reader import ColorTarget      # noqa: E402

DPI = 200
_XYZ = (18.0, 19.0, 21.0)


def _target(n: int = 60) -> ColorTarget:
    return ColorTarget(
        color_rep="iRGB", device_fields=["RGB_R", "RGB_G", "RGB_B"],
        patches=[((200.0, 40.0, 40.0), _XYZ) for _ in range(n - 1)]
        + [((100.0, 100.0, 100.0), (95.0, 100.0, 108.0))])


def _recipe(**kw) -> LayoutRecipe:
    r = LayoutRecipe()
    r.instrument, r.paper = "i1", "A4"
    # Area-first, so the typed margins are the law AND stay the typed ones:
    # "Use instrument margins" also gives the law but replaces them.
    r.layout_mode, r.use_instrument_margins = "area_first", False
    r.margin_top = r.margin_bottom = 15.0
    r.margin_left = r.margin_right = 12.0
    r.text_edge_top_mm = r.text_edge_mm = r.text_edge_clip_mm = 4.0
    r.chart_text, r.stamp_command = "CUSTOM TEXT HERE", False
    r.show_strip_indicators, r.show_row_indicators = True, False
    r.helper_markers = False
    r.helper_marker_edge_mm, r.helper_marker_len_mm = 4.0, 2.0
    r.helper_markers_top_bottom = r.helper_markers_sides = True
    r.clip_border = False
    r.randomize, r.seed_fixed, r.seed = False, True, 5
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def _render(r: LayoutRecipe, **draw_over):
    """One sheet from *r*, with *draw_over* replacing render-time arguments.

    **THE GEOMETRY COMES FROM `r` WHATEVER `draw_over` SAYS**, which is the
    whole reason the override exists. Isolating one element by rendering the
    same recipe with it switched OFF does not work here: turning the sheet text
    off changes `bottom_reserve_mm`, area-first then derives a different patch
    size, and every patch on the page moves. A diff of those two sheets is the
    patch block, not the text, and the first version of this file measured
    exactly that and reported the text starting at the left margin when it
    starts at the "Clip" reserve.
    """
    kw = r.build_kwargs()
    g = raster.apply_furniture_reserves(
        instruments.geom_from_build_kwargs(kw), kw)
    w_mm, h_mm = papers.dimensions_mm(r.paper)
    t = _target()
    lay = geometry.compute(g, w_mm, h_mm, len(t.patches))
    args = dict(
        seed=5, randomize=False, paper_w_mm=w_mm, paper_h_mm=h_mm, dpi=DPI,
        draw_indicators=kw.get("draw_indicators", True),
        indicator_size_mm=kw.get("indicator_size_mm", 0.0),
        strip_label_offset_mm=kw.get("strip_label_offset_mm", 0.0),
        chart_text=r.chart_text, chart_text_size_mm=r.chart_text_size_mm,
        stamp_text="", text_edge_mm=kw.get("text_edge", 4.0),
        helper_markers=bool(r.helper_markers),
        helper_marker_edge_mm=r.helper_marker_edge_mm,
        helper_marker_len_mm=r.helper_marker_len_mm,
        helper_markers_top_bottom=bool(r.helper_markers_top_bottom),
        helper_markers_sides=bool(r.helper_markers_sides))
    args.update(draw_over)
    return raster.render_pages(t, lay, g, **args).images[0], g, h_mm


def _moved(a, b) -> "tuple[float, float, float, float] | None":
    """Where two sheets differ: (y0, y1, x0, x1) in mm from the page's origin.

    Diffing is the only way to isolate ONE element: with the markers on, the
    dashes and the letters land within a millimetre of each other, so a run of
    inked rows merges them into one.
    """
    x, y = (np.asarray(i.convert("L")).astype(int) for i in (a, b))
    d = x != y
    rows, cols = np.flatnonzero(d.any(axis=1)), np.flatnonzero(d.any(axis=0))
    if not len(rows):
        return None
    return (rows[0] * 25.4 / DPI, (rows[-1] + 1) * 25.4 / DPI,
            cols[0] * 25.4 / DPI, (cols[-1] + 1) * 25.4 / DPI)


# ------------------------------------------------------ the arithmetic itself
def test_the_reserve_is_knuts_own_worked_example():
    """4.0 + 2.0 + 1.0 = 7.0, and it beats a 4.0 mm text-edge distance."""
    assert tef.helper_marker_reserve_mm(True, 4.0, 2.0) == pytest.approx(7.0)
    assert tef.edge_reserve_mm(4.0, True, 4.0, 2.0) == pytest.approx(7.0)


def test_markers_off_or_this_edge_unmarked_cost_nothing():
    assert tef.helper_marker_reserve_mm(False, 4.0, 2.0) == 0.0
    assert tef.helper_marker_reserve_mm(True, 4.0, 2.0, False) == 0.0
    assert tef.edge_reserve_mm(4.0, False, 4.0, 2.0) == pytest.approx(4.0)


def test_the_bigger_text_edge_distance_still_wins():
    """It is a MAX, not a sum: 12 mm of "T" beats a 7 mm marker reserve."""
    assert tef.edge_reserve_mm(12.0, True, 4.0, 2.0) == pytest.approx(12.0)


def test_the_label_offset_rides_on_top_of_whichever_reserve_wins():
    assert tef.strip_label_top_mm(4.0, 3.0, True, 4.0, 2.0) == pytest.approx(10.0)
    assert tef.strip_label_top_mm(4.0, 3.0) == pytest.approx(7.0)


def test_knuts_bottom_width_examples_come_out_at_his_numbers():
    """His A4 pair: 196 mm with the markers on, 202 mm with them off."""
    assert tef.bottom_text_room_mm(210.0, 4.0, True, 4.0, 2.0) == pytest.approx(196.0)
    assert tef.bottom_text_room_mm(210.0, 4.0, False) == pytest.approx(202.0)


# --------------------------------------------------------- the ink on the page
#: Long enough to overflow, and it has to be MEASURED long rather than merely
#: look long. At the 3.2 mm size "auto" starts from, the 122-character sentence
#: this file first used takes 194.2 mm of an A4's 202 mm of room: it fits, so
#: nothing shrank, and a mutation that switched the shrinking off entirely
#: still passed. `test_the_long_line_really_does_not_fit_at_the_starting_size`
#: keeps this string honest.
LONG = ("Canon PRO-300 on Hahnemuehle Photo Rag 308 gsm, printed with "
        "colour management switched off in the driver, 2880x1440 dpi, "
        "second pass, high-speed off, platen gap widest")


def test_the_strip_letters_clear_the_marker_band():
    """The letters land below the dashes, not through them."""
    r = _recipe(helper_markers=True)
    band = _moved(_render(r)[0], _render(r, draw_indicators=False)[0])
    assert band is not None, "the strip letters were not drawn at all"
    marker_end = 4.0 + 2.0
    assert band[0] >= marker_end, (
        f"the letters' ink begins at {band[0]:.2f} mm, inside the "
        f"4.0 to {marker_end:.1f} mm dash band")


def test_the_sheet_text_clears_the_marker_band():
    r = _recipe(helper_markers=True)
    img, _, h = _render(r)
    band = _moved(img, _render(r, chart_text="")[0])
    assert band is not None, "the sheet text was not drawn at all"
    from_bottom = h - band[1]
    assert from_bottom >= 4.0 + 2.0, (
        f"the sheet text's ink stops {from_bottom:.2f} mm up from the paper, "
        "inside the dash band that runs from 4.0 to 6.0 mm")


@pytest.mark.parametrize("b_mm", [2.0, 4.0, 8.0, 12.0])
def test_the_sheet_text_moves_with_b(b_mm):
    """Knut's first bottom report, checked against the ink at four values."""
    r = _recipe(text_edge_mm=b_mm)
    img, _, h = _render(r)
    band = _moved(img, _render(r, chart_text="")[0])
    assert band is not None
    from_bottom = h - band[1]
    assert from_bottom >= b_mm - 0.2, (
        f'with "B" at {b_mm} mm the text stops {from_bottom:.2f} mm up from '
        "the paper, inside the reserve")


@pytest.mark.parametrize("t_mm", [4.0, 6.0, 8.0, 12.0, 20.0])
def test_the_strip_letters_move_with_t(t_mm):
    """"T" moves them, all the way, with nothing clamping it any more.

    The clamp was `geometry.placement`'s ``min(reserve, margin_t - band)``, and
    Knut removed it in comment 5649810914: the letters hold their distance from
    the page edge and overlap the patch area where the top margin cannot hold
    them. With a 15 mm top margin and a 7 mm band the old clamp bit at 8 mm, so
    the last two values here are past it and would have been silently pinned to
    the margin before. `test_the_letters_hold_their_distance_and_overlap_the_
    patches` pins what happens on the other side of the same line.
    """
    r = _recipe(text_edge_top_mm=t_mm)
    band = _moved(_render(r)[0], _render(r, draw_indicators=False)[0])
    assert band is not None
    assert band[0] >= t_mm - 0.2, (
        f'with "T" at {t_mm} mm the letters begin {band[0]:.2f} mm from the '
        "paper edge, inside the distance that was asked for")


def test_the_letters_hold_their_distance_and_overlap_the_patches():
    """A too-small top margin no longer slides them up. Knut, 5649810914:

        "I want the function that I specified, where the strip labels do not
         cross the "Text distance from edge" value […] and then the text
         overlaps on top of the patch area top edge (according to top margin)."

    This test is the reverse of the one it replaces, and deliberately so: that
    one pinned the clamp, with a note saying the post asked for it to go and
    that only he could say so. He has. So the two facts to hold are that the
    reserve is KEPT (it is a limit on this edge like the other three) and that
    the band is allowed to run past the margin onto the patches.
    """
    r = _recipe(margin_top=6.0)
    band = _moved(_render(r)[0], _render(r, draw_indicators=False)[0])
    assert band is not None
    assert band[0] >= 4.0 - 0.2, (
        f"the letters begin {band[0]:.2f} mm from the paper edge, inside the "
        '4 mm "T" reserve; the reserve is a limit and the clamp is back')
    assert band[1] > 6.0, (
        f"the letters end {band[1]:.2f} mm down, still inside the 6 mm top "
        "margin, so something is still holding them off the patches")


def test_the_bottom_line_starts_at_the_patch_area_left_margin():
    """Knut, 2026-09-14, superseding the centring rule he gave two days before:

        for the sake of beauty, I find it better that the two bottom text type
        (in Sheet text frame) should be left-aligned against the patch area
        left margin, instead of centred against available horizontal space.

    So on this recipe the ink begins at the 12 mm left margin, not at the
    105.0 mm centre of his two bounds and not at the 4.0 mm "Clip" reserve the
    line started at before either rule. The bounds themselves are UNCHANGED,
    which is his own *"Leave limit detection as is for the left side"*.

    MUTATION: put the centring arithmetic back in `raster.render_pages` and
    this goes red at 101 mm.
    """
    lo, hi = tef.bottom_text_bounds_mm(210.0, 4.0)
    assert (lo, hi) == pytest.approx((4.0, 206.0))
    r = _recipe(chart_text="IIIIIIIIII")
    band = _moved(_render(r)[0], _render(r, chart_text="")[0])
    assert band is not None
    assert band[2] == pytest.approx(12.0, abs=0.6), (
        f"the line runs {band[2]:.2f} to {band[3]:.2f} mm; left-aligned on a "
        "12 mm left margin it has to begin at 12 mm")
    assert band[3] < 105.0, (
        f"the line ends at {band[3]:.2f} mm, which is past the centre of the "
        "page: ten narrow characters cannot reach there from 12 mm unless "
        "they are still being centred")


@pytest.mark.parametrize("side,expect_lo,expect_hi,expect_start", [
    ("left", 26.0, 206.0, 26.0),
    ("right", 4.0, 184.0, 12.0),
])
def test_a_clip_border_bounds_the_bottom_line_on_its_own_side(
        side, expect_lo, expect_hi, expect_start):
    """Two more rows of his table, and the ones only a chart with a band shows.

    Knut, comment 5651269930::

        Clip-border ON (side=left):   (0+Clip-border width) and (210 - Clip)
        Clip-border ON (side=right):  (0+Clip)              and (210 - Clip-border width)

    The band and the bottom line share that strip of paper: since the clip band
    now runs from the "T" bound to the "B" bound it reaches down across the
    line's own row, so the line has to start clear of it. Measured on the
    app's own sheet by `scripts/drive_182_layout_rulings.py` at a 26 mm border:
    the centre moves from 105.03 mm to 116.04 with the border on the left and
    to 94.02 with it on the right, against the 116.00 and 94.00 his rows ask
    for.
    """
    lo, hi = tef.bottom_text_bounds_mm(210.0, 4.0, clip_border_mm=26.0,
                                       clip_side=side)
    assert (lo, hi) == pytest.approx((expect_lo, expect_hi))
    # AND WHERE THE LINE NOW STARTS INSIDE THEM (Knut, 2026-09-14): the left
    # bound is the floor and the 12 mm left margin is the anchor, so a border
    # on the LEFT (26 mm, wider than the margin) still pushes the line to 26
    # while a border on the RIGHT leaves it at the margin.
    assert tef.bottom_text_anchor_mm(
        210.0, 4.0, clip_border_mm=26.0, clip_side=side,
        margin_left_mm=12.0, margin_right_mm=12.0) == pytest.approx(expect_start)
    r = _recipe(chart_text="IIIIIIIIII", chart_text_size_mm=3.2,
                clip_border=True, clip_border_width_mm=26.0, clip_side=side)
    band = _moved(_render(r)[0],
                  _render(r, chart_text="")[0])
    assert band is not None
    assert band[2] == pytest.approx(expect_start, abs=0.6), (
        f"with the border on the {side} the line begins at {band[2]:.2f} mm "
        f"and it has to begin at {expect_start:.2f} mm")


def test_a_border_narrower_than_the_reserve_keeps_the_reserve():
    """The one clause of his table that is genuinely ambiguous.

    Every row he tabulated has the border WIDER than the reserve, so the two
    readings agree. A border narrower than the reserve is a case he does not
    cover, and taking his words literally there would let the line into a
    reserve that is a limit on all four sides everywhere else in this module.
    ``max(border, reserve)`` is his table wherever his table speaks, and this
    pins the choice so that changing it is deliberate. **Reported for his
    ruling; if he wants the border to win even when it is smaller, this is the
    test to change.**
    """
    assert tef.bottom_text_bounds_mm(
        210.0, 8.0, clip_border_mm=3.0, clip_side="left") \
        == pytest.approx((8.0, 202.0))
    assert tef.bottom_text_bounds_mm(
        210.0, 8.0, clip_border_mm=3.0, clip_side="right") \
        == pytest.approx((8.0, 202.0))


def test_a_longer_bottom_line_grows_only_to_the_right():
    """Knut's own consequence, measured rather than restated.

        This means a long text only gets warning when hitting towards the right
        side limits.

    A left-aligned line grows only to the right; the centred one this replaced
    split the growth between the two ends, which is what the assertions below
    used to say. Ten characters against thirty, at a TYPED size so nothing
    shrinks and the comparison is about placement alone.
    """
    short = _moved(_render(_recipe(chart_text="I" * 10,
                                   chart_text_size_mm=3.2))[0],
                   _render(_recipe(chart_text="", chart_text_size_mm=3.2))[0])
    longer = _moved(_render(_recipe(chart_text="I" * 30,
                                    chart_text_size_mm=3.2))[0],
                    _render(_recipe(chart_text="", chart_text_size_mm=3.2))[0])
    assert short is not None and longer is not None
    grew_left = short[2] - longer[2]
    grew_right = longer[3] - short[3]
    assert grew_right > 1.0, (
        f"the longer line only reaches {grew_right:.2f} mm further right; it "
        "has to grow somewhere")
    assert abs(grew_left) < 0.3, (
        f"the line grew {grew_left:.2f} mm to the LEFT, so its left edge "
        "moved: it is being centred, not left-aligned")


def test_the_long_line_really_does_not_fit_at_the_starting_size():
    """The premise of the next two tests, checked rather than assumed.

    If :data:`LONG` fits at 3.2 mm there is nothing for "auto" to shrink and
    the shrink test passes while proving nothing, which is exactly what
    happened with the shorter sentence this file started with.
    """
    r = _recipe(chart_text=LONG, chart_text_size_mm=3.2)
    band = _moved(_render(r)[0], _render(r, chart_text="")[0])
    assert band is not None
    # THE ROOM THIS RECIPE HAS, which is measured from the 12 mm left margin
    # the line is anchored at, not from the 4 mm "Clip" bound (Knut,
    # 2026-09-14). Asking for the anchor-less figure here overstated the room
    # by 8 mm.
    _room = tef.bottom_text_room_mm(210.0, 4.0, margin_left_mm=12.0,
                                    margin_right_mm=12.0)
    assert _room == pytest.approx(194.0)
    assert band[3] - band[2] > _room, (
        f"the line takes {band[3] - band[2]:.2f} mm and the sheet has "
        f"{_room:.2f}; it fits, so it cannot show that anything shrinks")


def test_a_long_bottom_line_on_auto_shrinks_until_it_fits():
    """Proved by comparison, because "it fits" can be true without shrinking.

    The same sentence at a TYPED 3.2 mm (the size "auto" starts from, and one
    nothing shrinks) is the control: if the automatic one is not smaller, no
    shrinking happened.

    **MEASURED ON THE TYPE'S HEIGHT, NOT ON WHERE THE LINE ENDS.** The right
    edge stopped being able to answer this the day the line was left-aligned:
    :data:`LONG` is longer than the page even at the 7 pt floor, so both the
    automatic and the typed render are cut by the paper edge at 210.06 mm and
    the two right edges are identical while the sizes are not. The band's
    HEIGHT is the size itself, and the paper cannot clip it.
    """
    r = _recipe(chart_text=LONG, chart_text_size_mm=0.0)
    blank = _render(r, chart_text=" ")[0]
    auto = _moved(_render(r)[0], blank)
    fixed = _moved(_render(r, chart_text_size_mm=3.2)[0], blank)
    assert auto is not None and fixed is not None
    assert (auto[1] - auto[0]) < (fixed[1] - fixed[0]) - 0.3, (
        f"auto's type stands {auto[1] - auto[0]:.2f} mm tall and a typed "
        f"3.2 mm stands {fixed[1] - fixed[0]:.2f} mm; auto did not shrink")
    # …and a line that CAN reach the floor and fit is narrower on the paper,
    # which is the same fact where the paper is not in the way.
    # 130 characters: `raster.sheet_text_width_mm` puts it at 247.7 mm at
    # 3.2 mm and 188.3 mm at the 7 pt floor, so it straddles this recipe's
    # 194 mm of room and the shrink both starts and finishes inside the page.
    mid = LONG[:130]
    r2 = _recipe(chart_text=mid, chart_text_size_mm=0.0)
    blank2 = _render(r2, chart_text=" ")[0]
    a2 = _moved(_render(r2)[0], blank2)
    f2 = _moved(_render(r2, chart_text_size_mm=3.2)[0], blank2)
    assert a2 is not None and f2 is not None
    assert a2[3] < f2[3] - 1.0, (
        f"auto reaches {a2[3]:.2f} mm and a typed 3.2 mm reaches "
        f"{f2[3]:.2f}; auto did not shrink")


def test_the_shrink_stops_at_seven_point_and_then_the_panel_must_speak():
    """*"…and then stops shrinking."* The floor is a floor, not a promise.

    :data:`LONG` still needs more line than an A4 has once it reaches 7 pt, so
    the last millimetres go over the reserve and
    :func:`text_edge_fit.bottom_text_overflow` is what says so. A renderer that
    kept shrinking past the floor to make everything fit would be the other
    fault: unreadable type instead of a warning.
    """
    r = _recipe(chart_text=LONG, chart_text_size_mm=0.0)
    auto = _moved(_render(r)[0], _render(r, chart_text="")[0])
    assert auto is not None
    assert auto[3] > 210.0 - 4.0, (
        f"auto stopped at {auto[3]:.2f} mm, so it shrank past the 7 pt floor")
    assert tef.bottom_text_overflow(
        210.0, 4.0, auto[3] - auto[2],
        margin_left_mm=12.0, margin_right_mm=12.0) is not None


def test_a_line_that_fits_takes_the_room_it_has():
    """Nothing shrinks for the sake of shrinking, and "auto" is not 9 pt.

    **THIS TEST USED TO ASSERT THE OPPOSITE HALF OF ITS OWN NAME.** It compared
    the "auto" line against a typed 3.2 mm one and required them to be the same
    width, which pins "auto" to `SHEET_TEXT_DEFAULT_MM` — 9.07 pt — however much
    paper is free. A tester read that off a real sheet on beta 18: *"When
    Size=auto for the sheet text, the bottom text is still not automatically
    sized. The size of text is kept quite small even when there is a lot of
    space in both available width and height. Set a reasonable upper limit ...
    (such as 15 or 16pt?)"*.

    So the property is the one the name always claimed: a line with room is
    drawn LARGER than the old default and no larger than the ceiling, and it is
    not shrunk below what it needs.

    MUTATION: start the search at `SHEET_TEXT_DEFAULT_MM` again and the first
    assertion goes red.
    """
    fits = ("Canon PRO-300 on Hahnemuehle Photo Rag 308 gsm, "
            "no colour management")
    r = _recipe(chart_text=fits, chart_text_size_mm=0.0)
    auto = _moved(_render(r)[0], _render(r, chart_text="")[0])
    fixed = _moved(_render(r, chart_text_size_mm=3.2)[0],
                   _render(r, chart_text="")[0])
    assert auto is not None and fixed is not None
    auto_w, fixed_w = auto[3] - auto[2], fixed[3] - fixed[2]
    assert auto_w > fixed_w + 1.0, (
        f"the auto line is {auto_w:.2f} mm wide against the old 3.2 mm "
        f"default's {fixed_w:.2f} mm, so it is still not using the room it has")
    ceiling = _moved(_render(r, chart_text_size_mm=tef.pt_to_mm(
        tef.AUTO_SIZE_CEILING_PT))[0], _render(r, chart_text="")[0])
    assert ceiling is not None
    assert auto_w <= (ceiling[3] - ceiling[2]) + 0.5, (
        f"the auto line is {auto_w:.2f} mm wide, past the "
        f"{tef.AUTO_SIZE_CEILING_PT:.0f} pt ceiling's "
        f"{ceiling[3] - ceiling[2]:.2f} mm")
    # …and it still keeps inside the bounds, which is the half that was right.
    assert auto[3] <= 210.0 - 4.0 + 0.5, (
        f"the auto line runs to {auto[3]:.2f} mm on a 210 mm sheet")


def test_a_typed_bottom_size_is_not_shrunk_and_the_panel_must_say_so():
    """Knut: *"Manually defined size value does not shrink."*

    So the same line at a typed 4.5 mm still overflows, and
    :func:`text_edge_fit.bottom_text_overflow` is what reports it.
    """
    r = _recipe(chart_text=LONG, chart_text_size_mm=4.5)
    band = _moved(_render(r)[0], _render(r, chart_text="")[0])
    assert band is not None
    assert band[3] > 210.0 - 4.0, (
        f"a typed size stopped at {band[3]:.2f} mm; it must be drawn exactly "
        "as typed, and this one does not fit")
    assert tef.bottom_text_overflow(
        210.0, 4.0, band[3] - band[2],
        margin_left_mm=12.0, margin_right_mm=12.0) is not None


# ------------------------------------------------------------- the warning
def test_the_overlap_names_the_reserve_that_is_binding():
    """His case 1 and his case 2 need different remedies, so they differ here."""
    plain = tef.strip_label_overlap(6.0, 4.0, 7.0)
    assert plain is not None and not plain.from_markers
    marked = tef.strip_label_overlap(6.0, 1.0, 7.0, 0.0, True, 4.0, 2.0)
    assert marked is not None and marked.from_markers
    assert marked.reserve_mm == pytest.approx(7.0)


def test_no_overlap_when_the_margin_holds_the_band():
    assert tef.strip_label_overlap(30.0, 4.0, 7.0) is None


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    """A real Create Chart tab. `_sheet_text_width_mm` stopped being a
    `staticmethod` when it learned to predict the layout stamp, which needs the
    tab's own patch-count estimate."""
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", True)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    yield t
    t.deleteLater()


def test_the_panel_predicts_the_width_the_renderer_draws(tab):
    """The warning's number and the sheet's ink must come from one function.

    Two separate faults lived in the gap between them, and both shipped inside
    an hour of each other:

    * the panel measured its own font from ``r.chart_text_font``, which is
      empty on a recipe nobody has chosen a font for, so PIL handed back a
      fallback face and 206 mm of line was predicted as **378**;
    * `text_edge_fit` is imported inside `_engine_text_notes` and not at module
      scope, so reaching for it from the width helper raised NameError into a
      bare `except` and every "auto" chart predicted **0.0 mm**, which is the
      default, so the warning never fired at all.

    Neither is visible from the arithmetic. This asks the panel and the sheet
    the same question and requires the same answer.
    """
    from ui.tabs.tab_chart import TabChart
    from workflow.layout_engine.raster import sheet_text_width_mm
    r = _recipe(chart_text=LONG, chart_text_size_mm=3.2)
    predicted = tab._sheet_text_width_mm(r)
    drawn = sheet_text_width_mm([LONG], 3.2,
                                TabChart._DEFAULT_SHEET_TEXT_FONT,
                                False, False, float(getattr(r, "dpi", 300)))
    assert predicted == pytest.approx(drawn, abs=0.05), (
        f"the panel says {predicted:.2f} mm and the renderer draws "
        f"{drawn:.2f} mm")
    assert predicted > 0.0, "the panel predicted nothing at all"


def test_an_auto_sized_line_is_predicted_at_its_floor_and_not_at_zero(tab):
    """"auto" is the default, so a helper that throws there is silent always."""
    from ui.tabs.tab_chart import TabChart
    r = _recipe(chart_text=LONG, chart_text_size_mm=0.0)
    predicted = tab._sheet_text_width_mm(r)
    floor_mm = tef.pt_to_mm(tef.AUTO_SHRINK_FLOOR_PT)
    from workflow.layout_engine.raster import sheet_text_width_mm
    assert predicted == pytest.approx(
        sheet_text_width_mm([LONG], floor_mm,
                            TabChart._DEFAULT_SHEET_TEXT_FONT, False, False,
                            float(getattr(r, "dpi", 300))), abs=0.05)
    assert tef.bottom_text_overflow(210.0, 4.0, predicted) is not None, (
        "this line does not fit an A4 even at 7 pt, so the panel must warn")


# --- the merge that broke, and the shape that broke it ----------------------

def test_the_marker_reserve_has_exactly_one_arithmetic_and_one_constant():
    """TWO HALVES OF ONE ROUND WROTE THE SAME FUNCTION UNDER THE SAME NAME.

    One took the marker sizes, one took the switches as well, both were called
    `helper_marker_reserve_mm`, and both lived in this module. Python keeps the
    last definition, so every four-argument caller raised TypeError and 22
    geometry tests failed the moment the two were merged, while each half was
    green on its own. They also carried a 1.0 mm gap each, under two names.

    The two are different questions and have different names now: the ink's
    reach is the unconditional geometric fact, and the reserve is what a given
    edge must keep clear, which is nothing when the markers are off or that
    edge carries none. This pins that the gate never grows an arithmetic of its
    own again, because that is the half that can silently drift.
    """
    import inspect

    from workflow import text_edge_fit as tef

    src = inspect.getsource(tef.helper_marker_reserve_mm)
    assert "helper_marker_ink_reach_mm" in src, (
        "the gate must ask the fact rather than add the numbers itself")
    body = src.split('"""')[-1]
    assert "+" not in body, (
        "the gate is doing arithmetic again; there is one sum and it lives in "
        "helper_marker_ink_reach_mm")
    assert not hasattr(tef, "HELPER_MARKER_CLEARANCE_MM"), (
        "the second constant for the same 1.0 mm gap is back")


def test_the_two_questions_agree_where_they_must():
    from workflow import text_edge_fit as tef
    for edge, length in ((4.0, 2.0), (0.0, 0.0), (6.0, 3.0), (2.5, 1.5)):
        fact = tef.helper_marker_ink_reach_mm(edge, length)
        assert tef.helper_marker_reserve_mm(True, edge, length) == fact
        assert tef.helper_marker_reserve_mm(False, edge, length) == 0.0
        assert tef.helper_marker_reserve_mm(True, edge, length, False) == 0.0
