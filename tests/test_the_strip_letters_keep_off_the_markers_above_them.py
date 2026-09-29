"""The strip letters are judged against the furniture ABOVE them too.

Every check before this one compared the letters with the patch area BELOW.
A tester drove them the other way on beta 19 and found the top edge unguarded:

    When "Prioritise patch size..." and helper markers are on (4mm distance and
    2mm marker length), and then setting top margin (in Page geometry frame) to
    5mm, the strip labels overlap with the "helper marker distance from
    page"+"marker length"+1.0mm rule. But there is no warning message. Same
    happens if Label offset is set to -5mm or -5.5mm, while top margin setting
    is 10.0mm.

Two levers, one inequality. In **"Prioritise chart area"** the band is placed at
`edge_reserve_mm` = `max("T", edge + len + 1.0)`, so the markers are cleared by
construction and only a NEGATIVE "Label offset" can reach them. In **"Prioritise
patch size"** `geometry.placement` anchors the band on `margin_t + offset_y` and
the markers are never consulted at all, which is his first case.

The test is on the INK, not on the anchor: his second case moves the letters
without moving the anchor, so an anchor-based check would have caught one and
missed the other.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from workflow import text_edge_fit as tef                  # noqa: E402


#: His markers: 4 mm from the page edge, 2 mm long, so the dashes and the
#: 1.0 mm of clear paper they ask for reach 7.0 mm down the page.
EDGE_MM, LEN_MM = 4.0, 2.0
REACH_MM = 7.0


def test_the_reach_is_the_rule_he_quoted():
    assert tef.helper_marker_ink_reach_mm(EDGE_MM, LEN_MM) == pytest.approx(
        REACH_MM), "the 'distance + length + 1.0 mm' rule moved"


def test_his_first_case_the_top_margin_drives_them_in():
    """Patch-first, top margin 5 mm: the band hangs at 5 and the dashes end at 7.

    MUTATION: return None unconditionally from `strip_label_marker_overlap` and
    this goes red.
    """
    hit = tef.strip_label_marker_overlap(
        5.0,               # anchor: patch-first hangs the band on the margin
        1.3,               # the letters' own ink top, below the anchor
        True, EDGE_MM, LEN_MM, True,
        label_offset_mm=0.0, margin_anchored=True)
    assert hit is not None, "the letters run through the dashes in silence"
    assert hit.reach_mm == pytest.approx(REACH_MM)
    assert hit.ink_top_mm == pytest.approx(6.3)
    assert hit.overlap_mm == pytest.approx(0.7, abs=0.01)
    assert hit.margin_anchored is True


@pytest.mark.parametrize("offset", [-5.0, -5.5])
def test_his_second_case_a_negative_label_offset_drives_them_in(offset):
    """Top margin 10 mm and "Label offset" -5 or -5.5: same collision.

    The anchor does not move here, which is why the check is on the ink.
    `label_ink_top_mm` carries the offset already (`raster._furniture_reserves_mm`
    adds `strip_label_offset_mm` to the probe), so the ink top is 10 + offset +
    the letters' own inset.
    """
    hit = tef.strip_label_marker_overlap(
        10.0, offset + 1.3, True, EDGE_MM, LEN_MM, True,
        label_offset_mm=offset, margin_anchored=True)
    assert hit is not None, (
        f"a {offset} mm Label offset puts the letters on the dashes in silence")
    assert hit.overlap_mm > 0.0


def test_a_sheet_that_clears_them_stays_quiet():
    """The control: nothing fires where there is clear paper.

    A warning that fires while the user is looking at the thing working is how
    people learn to ignore warnings.
    """
    assert tef.strip_label_marker_overlap(
        9.0, 1.3, True, EDGE_MM, LEN_MM, True, margin_anchored=True) is None
    # …and the area-first reserve clears them by construction.
    anchor = tef.edge_reserve_mm(2.0, True, EDGE_MM, LEN_MM, True)
    assert anchor == pytest.approx(REACH_MM)
    assert tef.strip_label_marker_overlap(
        anchor, 1.3, True, EDGE_MM, LEN_MM, True) is None


def test_it_says_nothing_when_this_edge_carries_no_markers():
    """Markers off, or switched off for top and bottom, means no rule to break."""
    assert tef.strip_label_marker_overlap(
        5.0, 1.3, False, EDGE_MM, LEN_MM, True, margin_anchored=True) is None
    assert tef.strip_label_marker_overlap(
        5.0, 1.3, True, EDGE_MM, LEN_MM, False, margin_anchored=True) is None


def test_the_panel_asks_the_question_and_offers_the_right_lever():
    """The check is wired in, and each layout is offered a lever that moves ink.

    MUTATION: delete the `strip_label_marker_overlap` call from
    `_engine_text_notes` and the first assertion goes red.
    """
    import inspect
    from ui.tabs import tab_chart as tc
    src = inspect.getsource(tc.TabChart._engine_text_notes)
    assert "strip_label_marker_overlap(" in src, (
        "nothing in the panel asks whether the letters clear the markers")
    body = "\n".join(l for l in src.splitlines()
                     if not l.strip().startswith("#"))
    assert "printed over the ruler" in body
    # Patch-first: the band hangs from the top margin, so "Top" moves it and
    # "T" does not. Area-first: the reserve already clears the markers, so the
    # only way in is the offset and naming "Top" there would be noise.
    assert "Prioritise patch size" in body
    assert "_mk.margin_anchored" in body, (
        "one wording is used for both layouts, so one of them names a lever "
        "that moves no ink")
