"""The strip letters are judged where the RENDERER puts them, and by their ink.

Two faults, measured on beta 18 by driving the real app
(`~/Desktop/ChromIQ-beta18-proof/knut-sweep-geometry/`):

**1. In "Prioritise patch size" the top-edge notice could not fire at all.**
`geometry.placement` anchors the label band on "T" only when the margins are
the law; in the other mode it anchors on the TOP MARGIN and "T" is not
consulted. The panel worked the reserve out of "T" in both modes, so in
patch-first it was judging a number that describes nothing on the sheet. 24
states across four geometries, the letters driven onto the patches by every
lever that works, and **not one notice** — photographed with A B C D E printed
in the middle of the second row of hexagons under a panel reading "Margins: OK"
(`phase5/crops/ZOOM-CR30hexP-pf-off20.png`). The same levers in area-first
produced a notice in 14 of 24.

**2. The reach was the em BOX, and PIL anchors the letters by their ASCENDER.**
The ink begins about 1.33 mm below the anchor and ends below the box, so the
warning arrived a millimetre late: at "T" 8 there was 0.93 mm of letter ink on
the first row of patches and the panel said nothing, and at "T" 12 the message's
own remedy (raise Top by 3.9 mm) left **1.1 mm of every letter still on the
patches** while going silent (section 2.2).

Whether "T" SHOULD be inert in that layout is the design authority's call and is
recorded as an open item; that the notice must describe the sheet is not.
"""
from __future__ import annotations

import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import text_edge_fit as tef                       # noqa: E402
from workflow.layout_engine import geometry, instruments, raster  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe         # noqa: E402

_PAPER = (210.0, 297.0)


def _geom(**kw):
    r = LayoutRecipe()
    r.instrument, r.paper, r.dpi = "i1", "A4", 300
    r.use_instrument_margins = False
    r.margin_top = r.margin_bottom = r.margin_left = r.margin_right = 12.0
    r.text_edge_top_mm = 4.0
    for k, v in kw.items():
        setattr(r, k, v)
    return instruments.geom_from_build_kwargs(r.build_kwargs()), r


# ------------------------------------------------- 1. the renderer's anchor
@pytest.mark.parametrize("mode", ("area_first", "patch_first"))
def test_the_helper_is_the_same_answer_as_placement(mode):
    """`strip_label_leader_top_mm` MIRRORS the two lines of `placement` that set
    `Placement.leader_top`, and a mirror is only worth something while it is
    checked.

    MUTATION: drop the `margins_are_law` branch from the helper and this goes
    red for one of the two modes.
    """
    for top in (6.0, 12.0, 20.0, 30.0):
        for t in (0.0, 4.0, 12.0):
            g, _r = _geom(layout_mode=mode, margin_top=top, text_edge_top_mm=t)
            lay = geometry.compute(g, *_PAPER, 120)
            place = geometry.placement(g, *_PAPER, lay)
            assert geometry.strip_label_leader_top_mm(g) == pytest.approx(
                place.leader_top, abs=1e-9), (
                f"{mode}, top {top}, T {t}: the panel would predict "
                f"{geometry.strip_label_leader_top_mm(g)} where the renderer "
                f"anchors the band at {place.leader_top}")


def test_in_patch_first_the_anchor_is_the_top_margin_and_not_t():
    """The measured fact behind the fix: "T" at 0, 2, 4, 8, 16 and 25 mm put
    the letters at 13.377 to 17.780 mm every time, identical to the
    thousandth."""
    seen = set()
    for t in (0.0, 2.0, 4.0, 8.0, 16.0, 25.0):
        g, _r = _geom(layout_mode="patch_first", text_edge_top_mm=t)
        seen.add(round(geometry.strip_label_leader_top_mm(g), 6))
    assert len(seen) == 1, f'"T" moved the band in patch-first: {sorted(seen)}'
    assert seen == {12.0}, seen
    # …and in the other mode it moves one millimetre per millimetre.
    moved = {round(geometry.strip_label_leader_top_mm(
        _geom(layout_mode="area_first", text_edge_top_mm=t)[0]), 3)
        for t in (4.0, 9.0, 12.0)}
    assert len(moved) == 3, moved


# ------------------------------------------------------ 2. the notice fires
def test_patch_first_can_report_a_top_overlap_at_all():
    """The state that was photographed silent: the letters driven onto the
    patches with "Label offset", in "Prioritise patch size".

    MUTATION: pass `anchor_mm=None` at the call site and this goes red.

    `margin_anchored` is the layout's own answer to "does the renderer hang the
    band from the top margin?", and it is what selects this wording. It used to
    be inferred from the anchor being a different NUMBER from the reserve, which
    is a guess the strip-indicator gap and the chart offset Y both break; see
    `tests/test_a_top_notice_names_the_layout_the_user_is_in.py`, B8-241.
    """
    g, _r = _geom(layout_mode="patch_first", strip_label_offset_mm=14.0)
    anchor = geometry.strip_label_leader_top_mm(g)
    hit = tef.strip_label_overlap(
        12.0, 4.0, max(0.0, float(g.label_ink_bottom_mm) - 14.0), 14.0,
        anchor_mm=anchor,
        margin_anchored=geometry.strip_label_band_is_margin_anchored(g),
        ink_reach_mm=float(g.label_ink_reach_mm),
        tol_mm=tef.edge_tolerance_mm(300))
    assert hit is not None, (
        "the letters are 14 mm below an anchor that is the 12 mm top margin "
        "and the panel still reports nothing")
    assert hit.binding == tef.LABEL_HELD_BY_TOP_MARGIN, hit.binding
    assert not hit.from_markers


def test_the_message_does_not_offer_t_where_t_moves_nothing():
    """The remedy has to name a control that moves the ink.

    The wording follows `margin_anchored`, never a comparison of two numbers.
    """
    hit = tef.strip_label_overlap(12.0, 4.0, 5.0, 14.0, anchor_mm=12.0,
                                  margin_anchored=True, ink_reach_mm=19.0)
    assert hit is not None and hit.binding == tef.LABEL_HELD_BY_TOP_MARGIN


def test_the_two_older_bindings_are_untouched():
    """Area-first still separates "T" from the ruler markers, which is what
    lets the message name the one that is really binding."""
    plain = tef.strip_label_overlap(6.0, 4.0, 7.0)
    assert plain is not None and plain.binding == tef.LABEL_HELD_BY_TEXT_EDGE
    marked = tef.strip_label_overlap(6.0, 1.0, 7.0, 0.0, True, 4.0, 2.0)
    assert marked is not None and marked.binding == tef.LABEL_HELD_BY_MARKERS
    assert marked.from_markers and marked.reserve_mm == pytest.approx(7.0)


# ------------------------------------------------------- 3. the ink, not the box
def test_the_geometry_carries_the_ink_box_and_it_is_not_the_em_box():
    """Measured off a probe in `raster._furniture_reserves_mm`: DejaVuSans at a
    4.911 mm em inks from 1.355 mm to 5.165 mm below the anchor.

    MUTATION: set `ink_reach` to `_drawn` and this goes red.
    """
    g, _r = _geom(layout_mode="area_first")
    assert g.label_ink_top_mm > 0.0, (
        "the letters' ink is still assumed to start at the band's anchor")
    assert g.label_ink_reach_mm > g.label_ink_top_mm
    assert g.label_ink_reach_mm != pytest.approx(g.label_ink_bottom_mm), (
        "the ink reach is the em box again, which is what made the warning "
        "arrive a millimetre late")


def test_the_reach_is_used_and_the_box_is_not():
    """A `LabelOverlap` given a reach reports THAT, and one without falls back
    to the old sum so every call written before beta 19 still means what it
    meant."""
    with_reach = tef.LabelOverlap(4.0, False, 0.0, 4.9, 12.0, 0.0, "", 5.99)
    assert with_reach.reaches_mm == pytest.approx(9.99)
    without = tef.LabelOverlap(4.0, False, 0.0, 4.9, 12.0)
    assert without.reaches_mm == pytest.approx(8.9)


def test_the_ink_offset_is_what_the_sheet_really_draws():
    """The 1.33 mm, measured rather than asserted: the probe is drawn with the
    same font, size and anchor `render_pages` uses."""
    from PIL import Image, ImageDraw
    dpi = 300
    ind_px = 58                                     # a 4.911 mm em at 300 dpi
    f = raster._font(ind_px, raster.DEFAULT_INDICATOR_FONT, False, False)
    im = Image.new("RGBA", (ind_px * 6, ind_px * 6), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((ind_px * 2, ind_px * 2), "W8", font=f,
                            fill=(0, 0, 0, 255), anchor="la")
    bb = im.getbbox()
    top = (bb[1] - ind_px * 2) * 25.4 / dpi
    bottom = (bb[3] - ind_px * 2) * 25.4 / dpi
    assert top == pytest.approx(1.355, abs=0.05), top
    assert bottom == pytest.approx(5.165, abs=0.05), bottom
    assert bottom > ind_px * 25.4 / dpi, (
        "the ink stops inside the em box, so this whole correction is moot "
        "and the measurement that produced it was wrong")
