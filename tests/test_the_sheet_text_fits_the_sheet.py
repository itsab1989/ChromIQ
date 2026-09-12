"""Knut's #182 comment of 2026-09-11T21:23:10Z, the three findings.

**F1. The warning's numbers were wrong and it fired on a sheet that fits.**

    "When the right margin is set to 32.5mm and clip-border width is 24mm, the
    text to the right of the patch area looks like this, without giving any
    margin warning text […] When changing the right margin to 32mm (keeping
    other settings as is), the margin warning came […] Both images show very
    good white empty space to the left and right of the chart notes text "test
    text". This means that the measurements and the warning text is wrong with
    its text. The warning says "... need 3.8mm at 10pt and have 3.6mm..." The
    test-32.5.tif image shows 39 pixels from the patch area right edge to the
    top of the "t" of chart text "test text", and 59px to the bottom of the
    chart text. At 200 dpi and A4 page, this gives 39/1654*210=4.95mm of white
    space above the chart text, and 59/1654*210 = 7.49mm […] And the warning
    says it only needs 3.8mm, and still gives a warning...."

**TWO NUMBERS, TWO DIFFERENT QUESTIONS, and only one of them is the question
the warning asks.** Measured on the sheets the app itself wrote from his own
run 1 recipe, driven through the real window by
`scripts/drive_182_sheet_text_fit.py`:

* the code's *"have 3.6 mm"* answered **"how much paper is between the patch
  area and a reserve made of the clip band with another 'Text distance from
  edge' strip stacked on top of it"** -- ``margin - clip - band - pad``. That
  second strip is not on the sheet: the 4 mm "Clip" asks for lies INSIDE the
  band's own 24 mm.
* his ruler answered **"how much paper is between the patch area's right edge
  and the nearest ink on the other side"**, which is what
  `tiff_metadata._stamp_one` computes as ``W - max(_pad, clip_band)``. A MAX.

On the app's own sheet at 200 dpi the note's ink lands **25.15 mm to 27.56 mm**
in from the paper edge at BOTH of his right margins -- his 4.95 mm and 7.49 mm
from the patch edge, to the tenth -- and there are 7.66 mm of paper for a line
that needs 2.7 mm.

**F2. The automatic floor is 7 pt, not 8**, and the floor's other half was
silent: at 8 pt his 141-character note printed 129 characters and an ellipsis.

**F3. The clip band may print closer to the paper edge than "Text distance from
edge" asks**, and must say so.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                             # noqa: E402

from workflow import text_edge_fit as tef                 # noqa: E402
from workflow import tiff_metadata as tm                  # noqa: E402

#: His own two sheets: A4 at 200 dpi, a 24 mm clip border on the right with its
#: own text, "Text distance from edge" -> Clip at 4.0 mm, Chart Notes "test
#: text" at a typed 10 pt.
KNUT_BAND_MM = 24.0
KNUT_CLIP_MM = 4.0
KNUT_DPI = 200.0
KNUT_SIZE_PT = 10.0


# ------------------------------------------------------------------ F1
@pytest.mark.parametrize("margin_mm", [32.5, 32.0])
def test_neither_of_his_two_sheets_earns_a_warning(margin_mm):
    """Both print the note on clear paper, so neither may warn."""
    assert tef.chart_note_overlap(
        "right", margin_mm, KNUT_CLIP_MM, KNUT_DPI, KNUT_BAND_MM,
        KNUT_SIZE_PT) is None, (
            f"a {margin_mm} mm right margin still warns about a note that has "
            f"{margin_mm - KNUT_BAND_MM - tef.SAFETY_PAD_MM:.2f} mm of paper")


def test_the_room_is_the_room_the_stamper_measures_out():
    """The predicate and `_stamp_one` must subtract the SAME reserve.

    `_stamp_one` computes ``_right_limit = W - max(_pad, clip_band)`` and puts
    the note between there and the patch block. Adding the two instead of
    taking the larger cost 4.00 mm on Knut's sheet, which is the whole of the
    "Clip" box, counted twice.
    """
    for margin in (28.0, 32.0, 32.5, 40.0):
        got = tef.chart_note_overlap("right", margin, KNUT_CLIP_MM, KNUT_DPI,
                                     KNUT_BAND_MM, KNUT_SIZE_PT)
        want_avail = margin - max(KNUT_CLIP_MM, KNUT_BAND_MM) - tef.SAFETY_PAD_MM
        if want_avail + tef.EPS_MM >= tef.note_min_width_mm(KNUT_DPI,
                                                            KNUT_SIZE_PT):
            assert got is None, f"{margin} mm warns with {want_avail:.2f} mm free"
        else:
            assert got is not None
            assert got.available_mm == pytest.approx(want_avail, abs=0.001)


def test_the_sum_that_was_there_is_gone_and_it_is_measurably_gone():
    """With no band on the edge the two arithmetics agree, so the band is the
    case that proves it: 4 mm apart, every time."""
    with_band = tef.chart_note_overlap("right", 26.0, 4.0, 200.0, 24.0, 10.0)
    assert with_band is not None
    assert with_band.available_mm == pytest.approx(26.0 - 24.0 - 0.34, abs=0.001)
    assert with_band.available_mm > (26.0 - 4.0 - 24.0 - 0.34) + 3.9, (
        "the page-edge reserve is still being counted twice")
    # No band: the reserve IS "Clip", and nothing changed there.
    no_band = tef.chart_note_overlap("right", 6.0, 4.0, 200.0, 0.0, 0.0)
    assert no_band is not None
    assert no_band.available_mm == pytest.approx(6.0 - 4.0 - 0.34, abs=0.001)


def test_a_band_narrower_than_clip_lets_clip_decide_again():
    """MAX, not "the band wins". A 2 mm band is inside the 4 mm reserve."""
    o = tef.chart_note_overlap("right", 6.0, 4.0, 200.0, 2.0, 0.0)
    assert o is not None
    assert o.available_mm == pytest.approx(6.0 - 4.0 - 0.34, abs=0.001)


# ------------------------------------------------------------------ F2
#: His run 2 note, verbatim from `runs/run2/meta.json` in the `test.zip` he
#: attached. 141 characters, and the part that gets cut is the end.
KNUT_LONG_NOTE = (
    'i1Pro 1/2/3 600 patch target for 13x18cm / 5x7" photo card - print with '
    'borderless setting / NO expansion, retain size, color management: OFF'
)
#: The card that note is printed on, and the reserve it keeps.
CARD_H_MM = 180.0
CARD_EDGE_MM = 4.0


def test_his_long_note_survives_at_the_floor_that_is_shipped():
    """The whole point of lowering the floor: the sentence is printed whole."""
    lost = tm.note_characters_lost(KNUT_LONG_NOTE, CARD_H_MM, CARD_EDGE_MM,
                                   3.0, 200.0, 0.0, "Inter")
    assert lost == 0, (
        f"{lost} characters of Knut's own note are still cut off the card")


def test_at_eight_point_it_was_not(monkeypatch):
    """…and the floor is what decides it, which is why 7 was worth asking for.

    The mutation this guards against is the floor going back up: at 8 pt the
    same note on the same card loses its tail.
    """
    monkeypatch.setattr(tef, "AUTO_SHRINK_FLOOR_PT", 8.0)
    lost = tm.note_characters_lost(KNUT_LONG_NOTE, CARD_H_MM, CARD_EDGE_MM,
                                   3.0, 200.0, 0.0, "Inter")
    assert lost > 0, (
        "an 8 pt floor no longer cuts the note, so this file is measuring "
        "something other than the fault Knut reported")


def test_a_note_that_fits_reports_nothing_lost():
    assert tm.note_characters_lost("short", 297.0, 4.0, 4.0, 200.0) == 0
    assert tm.note_characters_lost("", 297.0, 4.0, 4.0, 200.0) == 0


def test_a_note_far_too_long_loses_a_lot_and_says_how_many():
    long = "x" * 2000
    lost = tm.note_characters_lost(long, 180.0, 4.0, 3.0, 200.0, 0.0, "Inter")
    assert lost > 1000, lost
    # …and a taller sheet loses less of the same note.
    on_a3 = tm.note_characters_lost(long, 420.0, 4.0, 3.0, 200.0, 0.0, "Inter")
    assert 0 < on_a3 < lost


def test_the_predictor_asks_the_fitter_itself():
    """A second copy of the rule is the fault this project keeps re-finding.

    The predictor must agree with `fit_rotated_line` exactly, so mutating the
    fitter moves the prediction.
    """
    import numpy as np
    dpi = 200.0
    H = int(round(CARD_H_MM * dpi / 25.4))
    pad = int(round(CARD_EDGE_MM * dpi / 25.4))
    strip_h = H - 2 * pad
    shown, _f = tm.fit_rotated_line("y" * 900, strip_h, 24,
                                    anchor_px=tm._NOTE_PATCH_GAP_PX,
                                    font_family="Inter", size_pt=0.0, dpi=dpi)
    kept = len(shown) - 1 if shown.endswith("…") else len(shown)
    assert tm.note_characters_lost("y" * 900, CARD_H_MM, CARD_EDGE_MM,
                                   24 * 25.4 / dpi, dpi, 0.0,
                                   "Inter") == 900 - kept
    # The renderer still draws exactly what the fitter chose.
    strip = tm._render_fitted_rotated_line("y" * 900, strip_h, 24, np.uint8, 3,
                                           anchor_px=tm._NOTE_PATCH_GAP_PX,
                                           font_family="Inter", dpi=dpi)
    assert strip.shape == (strip_h, 24, 3)


# ------------------------------------------------------------------ F3
def test_the_page_edge_distance_is_a_limit_and_is_never_spent():
    """Knut, 2026-09-12, correcting himself the morning after:

        "I was confused about the question, when you already know the
         text-edge distance is a limit on every side. The text on each of the
         4 sides shall NOT cross the text-edge distance limit on every side.
         If the patch area with its margins are pushing against these limits,
         the text shall overlap in the other direction, inward and over the
         edges of the patch area instead."

    For one evening `clip_content_inset_mm` took the content and surrendered
    the reserve to it. It takes two arguments again, and no call can spend it.
    """
    import inspect
    assert list(inspect.signature(tef.clip_content_inset_mm).parameters) == \
        ["band_mm", "text_edge_clip_mm"]
    need4 = tef.clip_text_needed_mm(4)
    for band in (need4 - 3.0, need4, need4 + 0.2, need4 * 3):
        asked = min(4.0, band * tef.CLIP_INSET_MAX_FRAC)
        assert tef.clip_content_inset_mm(band, 4.0) == pytest.approx(asked), (
            f"the reserve moved on a {band:.2f} mm band")


def test_text_that_will_not_fit_reaches_over_the_patches_by_the_shortfall():
    need4 = tef.clip_text_needed_mm(4)
    band = need4                      # the whole band, reserve and all
    inset = tef.clip_content_inset_mm(band, 4.0)
    over = tef.clip_text_overhang_mm(band, 4.0, 4)
    assert over == pytest.approx(inset), (
        "a band exactly as wide as the text must overhang by its reserve")
    # …and the room inside the band plus the overhang is exactly what the text
    # needs: not a millimetre is lost and not a millimetre is invented.
    assert (band - inset) + over == pytest.approx(need4)


def test_a_band_with_room_reaches_over_nothing():
    need1 = tef.clip_text_needed_mm(1)
    assert tef.clip_text_overhang_mm(need1 * 4.0, 4.0, 1) == 0.0
    assert tef.clip_text_squeeze(need1 * 4.0, 4.0, 1) is None


def test_nothing_reaches_over_for_content_that_has_no_lines():
    assert tef.clip_text_overhang_mm(10.0, 4.0, 0) == 0.0
    assert tef.clip_text_squeeze(10.0, 4.0, 0) is None


def test_the_overhang_and_the_squeeze_are_one_fact():
    """A predicate and a distance that can disagree is two rules."""
    for band in (8.0, 10.0, 12.0, 16.0, 24.0, 60.0):
        for n in (1, 2, 4, 8):
            o = tef.clip_text_squeeze(band, 4.0, n)
            over = tef.clip_text_overhang_mm(band, 4.0, n)
            assert (o is not None) == (over > tef.EPS_MM), (band, n, o, over)
            if o is not None:
                assert over == pytest.approx(o.overlap_mm, abs=1e-9)


def test_the_renderer_is_handed_the_band_plus_the_overhang_on_the_patch_side():
    """The geometry, not only the arithmetic, and on the correct side."""
    from workflow.layout_engine import geometry, instruments
    from workflow.layout_engine.presets import LayoutRecipe
    need4 = tef.clip_text_needed_mm(4)
    for side in ("right", "left"):
        r = LayoutRecipe()
        r.instrument, r.paper, r.layout_mode = "CM", "A4", "area_first"
        r.clip_border, r.clip_border_width_mm = True, round(need4, 1)
        r.clip_side, r.clip_content_mode = side, "text"
        r.text_edge_clip_mm = 4.0
        r.margin_right = r.margin_left = 40.0
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        plain = geometry.clip_area_mm(g, 297.0, 210.0)
        over_rect = geometry.clip_area_mm(g, 297.0, 210.0, 4, 0.0)
        assert plain is not None and over_rect is not None
        zone = g.lbord + g.border
        over = tef.clip_text_overhang_mm(zone, 4.0, 4)
        assert over > 0.05, "pick a band that actually overflows"
        assert over_rect[2] == pytest.approx(plain[2] + over, abs=0.001)
        if side == "right":
            # grows LEFT, toward the patches; the page-edge end cannot move
            assert over_rect[0] == pytest.approx(plain[0] - over, abs=0.001)
            assert over_rect[0] + over_rect[2] == pytest.approx(
                plain[0] + plain[2], abs=0.001)
        else:
            # grows RIGHT, toward the patches; the page-edge end cannot move
            assert over_rect[0] == pytest.approx(plain[0], abs=0.001)
        # The top and bottom reserve is untouched: the overflow is across only.
        assert over_rect[1] == pytest.approx(plain[1], abs=0.001)
        assert over_rect[3] == pytest.approx(plain[3], abs=0.001)


def test_the_overhang_never_crosses_the_page_edge_distance():
    """The whole point: the rectangle's page-edge end is where it always was."""
    from workflow.layout_engine import geometry, instruments
    from workflow.layout_engine.presets import LayoutRecipe
    for band in (10.0, 12.0, 16.0, 24.0):
        r = LayoutRecipe()
        r.instrument, r.paper, r.layout_mode = "CM", "A4", "area_first"
        r.clip_border, r.clip_border_width_mm = True, band
        r.clip_side, r.clip_content_mode = "right", "text"
        r.text_edge_clip_mm = 4.0
        r.margin_right = 40.0
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        zone = g.lbord + g.border
        inset = tef.clip_content_inset_mm(zone, 4.0)
        for n in (1, 2, 4, 8, 16):
            a = geometry.clip_area_mm(g, 297.0, 210.0, n, 0.0)
            assert a is not None
            # the far side of the rectangle, measured from the paper's edge
            edge_gap = 210.0 - (a[0] + a[2])
            assert edge_gap == pytest.approx(inset, abs=0.001), (
                f"band {band}, {n} lines: the text is {edge_gap:.2f} mm from "
                f"the paper edge and “Clip” asks for {inset:.2f}")


def test_the_band_the_renderer_paints_is_the_band_the_panel_predicts():
    """Screen, sheet and template export read one function or they drift."""
    from workflow.layout_engine import geometry, instruments, raster
    from workflow.layout_engine.presets import LayoutRecipe
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = "CM", "A4", "area_first"
    r.clip_border, r.clip_border_width_mm = True, 12.0
    r.clip_side, r.clip_content_mode = "right", "text"
    r.text_edge_clip_mm = 4.0
    r.margin_right = 40.0
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    lines = ["a", "b", "c", "d"]
    area = geometry.clip_area_px(g, 297.0, 200, 210.0, len(lines), 0.0)
    assert area is not None
    strip = raster.render_clip_strip("text", width_px=area[2],
                                     height_px=area[3], dpi=200,
                                     text="\n".join(lines),
                                     font_family="Inter")
    assert strip.width == area[2] and strip.height == area[3]


def test_the_block_is_anchored_at_the_page_edge_end_whichever_way_it_reads():
    """"Flip 180" turns the content over; it must not choose which end
    overflows.

    THE BLOCK, NOT LINE 1. Turning the content over necessarily reverses the
    reading order within the block, so where line 1 sits is not the question;
    where the BLOCK sits is. It is measured as the span of inked columns across
    the band, which is exactly "which end it is anchored to" and is not
    disturbed by a glyph's ascent padding swapping ends with its descent. Three
    earlier probes compared blank margins at the two ends and were defeated by
    precisely that.

    Measured before this was built: with "Flip 180" on, a right-hand band put
    the block against the PATCHES and grew it toward the paper edge, which is
    the direction Knut's ruling of 2026-09-12 forbids.
    """
    import numpy as np
    from workflow.layout_engine import raster
    dashes = "\u2014" * 60
    text = "\n".join([dashes, "second line", "third line", "fourth line"])
    W, H = 200, 2100                      # slack: a typed size cannot fill this
    size_mm = 7.0 * 25.4 / 72.0

    def _block(flip, compensate):
        strip = raster.render_clip_strip(
            "text", width_px=W, height_px=H, dpi=200, text=text,
            font_family="Inter", text_size_mm=size_mm,
            anchor_far=(flip and compensate))
        if flip:
            strip = strip.rotate(180, expand=True)
        cols = np.flatnonzero(
            (np.asarray(strip.convert("L")) < 200).any(axis=0))
        assert len(cols), "the clip strip printed nothing"
        return int(cols[0]), int(cols[-1])

    # HALF A LINE is the tolerance, because the two states do not ink their
    # line boxes identically: the block is the same 4 lines either way, but
    # which line lands at which end changes, and a line's ascent padding is not
    # its descent padding. Anything that moves the block by a whole line or
    # more has moved which END it is anchored to, which is the fault.
    half_line = 0.5 * tef.CLIP_LINE_SPACING * tef.pt_to_px(7.0, 200)
    plain, flipped = _block(False, True), _block(True, True)
    assert abs(plain[0] - flipped[0]) <= half_line and \
        abs(plain[1] - flipped[1]) <= half_line, (
            f"the flip moved the block from columns {plain} to {flipped}, so "
            f"it can still grow toward the paper edge")
    assert plain[0] < W * 0.25, (
        f"the block does not start at the page-edge end: columns {plain}")
    # …and without the compensation it DOES move, which is what makes this
    # test worth having: the mutation it guards is a real one.
    naive = _block(True, False)
    assert naive[0] - plain[0] > 4 * half_line, (
        f"turning the strip over no longer moves the block ({plain} vs "
        f"{naive}), so anchor_far is guarding nothing")
