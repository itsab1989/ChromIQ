"""The red warn ring must not depend on the order overlay items are drawn in.

Basti, on screen (2026-08-30, "red overlays for flagged patches are partly
covered by other patches"): on a hexagonal chart the flagged patch's red ring
is partly missing wherever a neighbouring patch interlocks with it.

Cause: TiffPreview paints the patch overlay in ONE pass — each item fills its
patch and draws its own warn ring in the same iteration, so a neighbour drawn
later fills over the ring drawn before it. The hexagonal branch strokes the
ring ON the hexagon path (half the pen outside the patch, and the hexagons
tessellate edge-to-edge), so the covering is structural there; the rectangular
branch insets the ring wholly inside its own box, which is why rectangles are
immune (measured: 0 differing pixels across both adjacencies).

These tests render the SAME two overlay items in both list orders and require
the rendered image to be identical — the definition of "no item's ring is at
another item's mercy". The hex case is the fault and is a strict xfail until
the paint loop is split into a fill pass and a ring pass; the rect case
already holds and pins the immunity the fix must not lose.
"""
from __future__ import annotations

import pytest
from PIL import Image
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor


def _render(tmp_path, qapp, hex_mode: bool, items):
    from ui.tiff_preview import TiffPreview
    tif = tmp_path / f"flat_{int(hex_mode)}_{len(items)}.tif"
    if not tif.exists():
        Image.new("RGB", (500, 640), (240, 240, 240)).save(tif)
    p = TiffPreview()
    p.resize(520, 640)
    p.load_tiff([tif])
    p.set_hex_zigzag(hex_mode)
    p.set_patch_overlay(0, list(items), replace_page=True)
    p.show()
    qapp.processEvents()
    img = p.grab().toImage()
    p.close()
    return img


def _adjacent_items(flagged_first: bool, both_flagged: bool = False):
    # Two vertically adjacent slots, exactly as an engine chart records them
    # (shared edge, no gap). In hex mode each drawn hexagon pokes h/6 past its
    # slot, so the two interlock — the geometry of every SS/CR30 hex chart.
    a = (QRect(160, 160, 120, 120), QColor("#3050ff"), QColor("#3050ff"), True)
    b = (QRect(160, 280, 120, 120), QColor("#20c060"), QColor("#20c060"),
         bool(both_flagged))
    return [a, b] if flagged_first else [b, a]


#: Classify a pixel well enough to say "this was ring, and now it is patch".
def _kind(c):
    if abs(c.red() - 255) < 50 and c.green() < 100 and c.blue() < 100:
        return "ring"
    if c.blue() > 150 and c.red() < 120:
        return "fill"
    if c.green() > 140 and c.red() < 120:
        return "fill"
    return "other"


def _ring_pixels_lost(first, last) -> int:
    """Pixels that are the red ring in one draw order and a patch FILL in the
    other. That — not whole-image equality — is what "the ring was covered"
    means.

    WHY NOT `first == last`. Two hexagons overshoot their slots by h/6 and so
    genuinely INTERLOCK, and whichever fill is drawn second wins the overlap:
    737 pixels of one fill become the other's, in the apex band, no matter how
    the rings are handled. A whole-image assertion can therefore never pass and
    would condemn the fix it was written to demand. Measured after the two-pass
    fix landed: 850 pixels still differ, 737 of them fill-over-fill, and ZERO
    of them ring-turned-into-fill.
    """
    assert first.size() == last.size()
    lost = 0
    for y in range(first.height()):
        for x in range(first.width()):
            a, b = _kind(first.pixelColor(x, y)), _kind(last.pixelColor(x, y))
            if (a == "ring") != (b == "ring") and "fill" in (a, b):
                lost += 1
    return lost


def _has_a_ring(img) -> int:
    """Guard against a vacuous pass: an empty render loses no ring either.

    My own first probe scored a perfect zero because it drew nothing at all.
    """
    return sum(1 for y in range(img.height()) for x in range(img.width())
               if _kind(img.pixelColor(x, y)) == "ring")


def test_hex_warn_ring_survives_a_neighbour_drawn_after_it(tmp_path, qapp):
    first = _render(tmp_path, qapp, True, _adjacent_items(flagged_first=True))
    last = _render(tmp_path, qapp, True, _adjacent_items(flagged_first=False))
    assert _has_a_ring(first) > 100, "nothing was drawn; the test proves nothing"
    assert _ring_pixels_lost(first, last) == 0, (
        "the flagged hexagon's ring is painted over by a neighbour's fill")


def test_hex_two_adjacent_flagged_rings_both_survive(tmp_path, qapp):
    """The case no ordering can fix: whichever item is last, the other's ring
    used to be covered. Only two passes saves both."""
    first = _render(tmp_path, qapp, True,
                    _adjacent_items(flagged_first=True, both_flagged=True))
    last = _render(tmp_path, qapp, True,
                   _adjacent_items(flagged_first=False, both_flagged=True))
    assert _has_a_ring(first) > 100, "nothing was drawn; the test proves nothing"
    assert _ring_pixels_lost(first, last) == 0


def test_rect_warn_ring_is_draw_order_invariant(tmp_path, qapp):
    """Rectangular charts are immune (the ring is inset inside its own box) —
    pin that, so the two-pass fix cannot regress it."""
    first = _render(tmp_path, qapp, False, _adjacent_items(flagged_first=True))
    last = _render(tmp_path, qapp, False, _adjacent_items(flagged_first=False))
    assert first == last
