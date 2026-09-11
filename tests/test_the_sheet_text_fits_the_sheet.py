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
def test_the_clip_band_gives_up_its_page_edge_reserve_before_cutting():
    """Knut, 2026-09-11: *"Yes, allow to print closer to the paper edge than
    'Text distance from edge' asks, but warn about it."*"""
    need4 = tef.clip_text_needed_mm(4)
    band = need4 + 0.2                     # fits the band, not band less Clip
    asked = tef.clip_inset_asked_mm(band, 4.0)
    assert asked > 0.0
    used = tef.clip_content_inset_mm(band, 4.0, 4)
    assert used < asked, "the reserve is still held against text that needs it"
    assert band - used + tef.EPS_MM >= need4, "the push did not go far enough"
    assert used >= 0.0, "the content was pushed off the paper"


def test_the_push_takes_no_more_than_it_needs():
    """A band with room to spare keeps every millimetre of "Clip"."""
    need1 = tef.clip_text_needed_mm(1)
    roomy = need1 * 4.0
    assert tef.clip_content_inset_mm(roomy, 4.0, 1) == pytest.approx(
        tef.clip_inset_asked_mm(roomy, 4.0))
    assert tef.clip_text_push(roomy, 4.0, 1) is None
    # A band one hair too small gives up one hair.
    tight = tef.clip_inset_asked_mm(need1 * 1.2, 4.0)
    band = need1 + tight - 0.05
    p = tef.clip_text_push(band, 4.0, 1)
    assert p is not None
    assert 0.0 < p.pushed_mm < tef.clip_inset_asked_mm(band, 4.0) + 1e-9


def test_nothing_is_pushed_for_content_that_has_no_lines():
    assert tef.clip_content_inset_mm(10.0, 4.0, 0) == pytest.approx(
        tef.clip_inset_asked_mm(10.0, 4.0))
    assert tef.clip_text_push(10.0, 4.0, 0) is None


def test_the_renderer_is_handed_the_pushed_band():
    """The geometry, not only the arithmetic."""
    from workflow.layout_engine import geometry, instruments
    from workflow.layout_engine.presets import LayoutRecipe
    need4 = tef.clip_text_needed_mm(4)
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = "CM", "A4", "area_first"
    r.clip_border, r.clip_border_width_mm = True, round(need4 + 0.2, 1)
    r.clip_side, r.clip_content_mode = "right", "text"
    r.text_edge_clip_mm = 4.0
    r.margin_right = 40.0
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    plain = geometry.clip_area_mm(g, 297.0, 210.0)
    pushed = geometry.clip_area_mm(g, 297.0, 210.0, 4, 0.0)
    assert plain is not None and pushed is not None
    assert pushed[2] > plain[2], (
        f"the band did not widen: {plain[2]:.2f} -> {pushed[2]:.2f} mm")
    # It widens toward the PAGE EDGE, so on a right-side band the rectangle's
    # left edge (the patch side) does not move.
    assert pushed[0] == pytest.approx(plain[0], abs=0.001)
    # And the top/bottom reserve is untouched: the push is across, not along.
    assert pushed[1] == pytest.approx(plain[1], abs=0.001)
    assert pushed[3] == pytest.approx(plain[3], abs=0.001)
