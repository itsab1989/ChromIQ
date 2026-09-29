"""A tenth of a millimetre is not a collision, and a pixel is not a constant.

A tester, testing beta 18 on the SHIPPED presets, untouched:

    *"When loading any of the i1Pro3 profiles ... there is a warning where only
    0,1mm is lacking. It is saying 23.9mm left in the margin and the band is
    24mm ... There is not overlap actually visible, as 0,1mm is too small to
    see on page ... I suggest that there should be a threshold of 0,2mm on the
    judgement of text overlapping the patch area edges (measured margins) on
    any of the 4 sides."*

**AND IT IS PIXEL QUANTISATION, NOT THE NOTES BOX.** `clip_content_overlap`
compares an exact clip zone (28.000 mm) with the MEASURED margin, which lands on
a whole pixel. Driven on beta 18 at five resolutions, everything else identical
(`~/Desktop/ChromIQ-beta18-proof/knut-sweep-clipborder/`, group `D`):

| dpi | one pixel | measured left | asked | residue | warned |
|---|---|---|---|---|---|
| 72 | 0.353 mm | 27.869 | 28.0 | 0.131 | yes |
| 150 | 0.169 mm | 27.940 | 28.0 | 0.060 | yes |
| 200 | 0.127 mm | 27.940 | 28.0 | 0.060 | yes |
| 300 | 0.085 mm | 28.025 | 28.0 | -0.025 | no |
| 600 | 0.042 mm | 27.982 | 28.0 | 0.018 | no |

So a flat 0.2 mm is not enough: the dpi box accepts 72 to 1200 and the worst
case at 72 is a whole pixel, 0.353 mm. The rule is the LARGER of the two.

**AND IT MASKS NOTHING THAT REACHES PAPER.** Twin sheets, identical except for
the accused text, subtracted pixel by pixel (same folder, `twin_difference.txt`):
at a claimed 0.2 mm shortfall there is 1.10 mm of clear paper and zero text
pixels on the patches; ink first touches at a claimed shortfall of about 1.3 mm.
"""
from __future__ import annotations

import pytest

from workflow import text_edge_fit as tef


def test_the_tolerance_is_the_larger_of_two_tenths_and_one_pixel():
    """MUTATION: return the constant and this goes red at 72 and 150 dpi."""
    # One pixel passes 0.2 mm below 127 dpi, so 150, 200, 300 and 600 all take
    # the flat minimum and only the bottom of the dpi box takes the pixel.
    assert tef.edge_tolerance_mm(600) == pytest.approx(tef.MIN_EDGE_TOLERANCE_MM)
    assert tef.edge_tolerance_mm(300) == pytest.approx(tef.MIN_EDGE_TOLERANCE_MM)
    assert tef.edge_tolerance_mm(150) == pytest.approx(tef.MIN_EDGE_TOLERANCE_MM)
    assert tef.edge_tolerance_mm(127) == pytest.approx(tef.MIN_EDGE_TOLERANCE_MM)
    assert tef.edge_tolerance_mm(100) == pytest.approx(25.4 / 100)
    assert tef.edge_tolerance_mm(72) == pytest.approx(25.4 / 72)
    assert tef.edge_tolerance_mm(72) > tef.MIN_EDGE_TOLERANCE_MM, (
        "a fixed 0.2 mm does not cover the 0.353 mm pixel at the bottom of "
        "the dpi box, which is the whole reason this is a max")
    # No raster to ask: the flat minimum, never zero.
    assert tef.edge_tolerance_mm(0) == pytest.approx(tef.MIN_EDGE_TOLERANCE_MM)
    assert tef.edge_tolerance_mm("x") == pytest.approx(tef.MIN_EDGE_TOLERANCE_MM)


def test_the_tenth_of_a_millimetre_on_the_shipped_preset_is_silent():
    """His own case, in the arithmetic that produced it: an exact 28.000 mm
    clip zone against a margin the raster put at 27.940.

    MUTATION: drop `tol_mm` from `clip_content_overlap` and this goes red.
    """
    tol = tef.edge_tolerance_mm(200)
    assert tef.clip_content_overlap("left", 27.940, 28.0, 4.0,
                                    tol_mm=tol) is None, (
        "the 0.1 mm warning on a stock preset is still raised")
    # …and at 72 dpi, where a pixel is 0.353 mm and 0.2 would not cover it.
    assert tef.clip_content_overlap("left", 27.869, 28.0, 4.0,
                                    tol_mm=tef.edge_tolerance_mm(72)) is None


def test_a_collision_that_reaches_paper_still_warns():
    """The half that matters more. Ink first touches at a claimed shortfall of
    about 1.3 mm, measured on twin sheets, so everything from there up must
    still be reported at every resolution."""
    for dpi in (72, 150, 200, 300, 600):
        tol = tef.edge_tolerance_mm(dpi)
        o = tef.clip_content_overlap("left", 26.0, 28.0, 4.0, tol_mm=tol)
        assert o is not None and o.overlap_mm == pytest.approx(2.0), (
            f"a 2.0 mm overlap went unreported at {dpi} dpi")


def test_the_floor_reaches_all_four_of_the_patch_area_checks():
    """His words are *"on any of the 4 sides"*, so each of the four functions
    takes the tolerance and each of them honours it.

    MUTATION: leave any one of them on `EPS_MM` and this goes red for that one.
    """
    tol = 0.2
    assert tef.chart_note_overlap(
        "right", 5.0 + tef.note_min_width_mm(300) + tef.SAFETY_PAD_MM - 0.1,
        5.0, 300, tol_mm=tol) is None
    assert tef.clip_content_overlap("left", 27.94, 28.0, 4.0,
                                    tol_mm=tol) is None
    assert tef.bottom_text_block_overlap(8.3, 4.0, 1, 4.2,
                                         tol_mm=tol) is None
    assert tef.strip_label_overlap(11.0, 4.0, 7.0, tol_mm=tol) is None
    # …and every one of them still fires a millimetre further in.
    assert tef.clip_content_overlap("left", 27.0, 28.0, 4.0, tol_mm=tol)
    assert tef.bottom_text_block_overlap(7.0, 4.0, 1, 4.2, tol_mm=tol)
    assert tef.strip_label_overlap(10.0, 4.0, 7.0, tol_mm=tol)


def test_the_default_is_still_float_noise_and_not_the_threshold():
    """`EPS_MM` is what two floats describing one edge differ by, and it stays
    the default so nothing outside the four patch-area checks silently gains a
    fifth of a millimetre of slack."""
    assert tef.EPS_MM == 0.05
    assert tef.clip_content_overlap("left", 27.94, 28.0, 4.0) is not None
