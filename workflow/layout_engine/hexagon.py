"""The hexagon, written once.

Every hexagonal patch ChromIQ draws is the same shape: **pointy top and bottom,
flat vertical sides**, with the two apexes reaching a sixth of the slot height
beyond the slot, which is the overhang the geometry reserves as ``hxeh`` so that
neighbouring rows interlock the way ``printtarg -h`` does.

That shape was written out FIVE times in shipped code and a sixth time in the
suite:

===  =========================================================  ==============
 #   site                                                        form
===  =========================================================  ==============
 1   ``raster._hexagon_points``                                  int tuples
 2   ``ui/tiff_preview._patch_hexagon``                          QPainterPath
 3   ``ui/tiff_preview._strip_zigzag_path.verts``                dict of floats
 4   ``ui/tiff_preview._in_hexagon``                             two inequalities
 5   ``ui/scan_grid_marquee._cell_uv``                           unit-square floats
===  =========================================================  ==============

Sites 2 and 3 were byte-identical arithmetic fifty lines apart in one file, and
``_patch_hexagon``'s docstring promised in English that it matched the zigzag —
where a shared function makes it mechanical.

**THEY AGREED BEFORE THIS MODULE EXISTED, AND THAT IS THE POINT.** Swept over
9,360 hexagons, sites 2/3/5 are identical to 1e-14 and site 4 is algebraically
exact against them; site 1 differs only by its own ``round()``, by at most half
a pixel. So pooling fixes no bug that exists today. It exists because a second
ORIENTATION is being added, and five independent copies get five independent
chances to disagree about it.

WHY ROUNDING IS A PARAMETER AND DEFAULTS TO OFF
-----------------------------------------------
Site 1 rounds every vertex because Pillow's ``polygon`` needs integers. Site 3
must not, and says so in capitals where it is used: snapping the vertices looks
like the fix for the uneven halo and measured *worse* (spread 0.14 -> 0.21
device px), and on a 7 mm hexagon it moves each vertex by 2.7 % of the patch,
off the ink it is describing. A pooled function that returned integers "because
the renderer needs them" would silently revert that measured finding on the
Measure overlay, magnified by the preview zoom.

So the renderer asks for rounding and nobody else does.

This module imports nothing but ``math`` — no ``core.*``, no Qt, no Pillow, no
sibling. ``raster`` already imports no ``workflow.*`` module at all, and
``ui/scan_grid_marquee`` imports no ``layout_engine`` module at all; a bare,
dependency-free module keeps both of those true and avoids paying for
``tifffile``/``PIL``/``numpy`` at marquee import time.
"""
from __future__ import annotations

# The apexes reach 1/6 of the slot height beyond the slot at each end, so the
# drawn hexagon is 4/3 of the slot tall. `instruments.py` reserves exactly this
# as `hxeh`, and `test_a_hexagon_is_taller_than_its_row_pitch.py` measures the
# ink against it.
APEX_FRACTION = 1.0 / 6.0

# Alternate rows step a quarter of the patch width sideways, so consecutive
# rows in a column interlock rather than stack.
STAGGER_FRACTION = 0.25


def stagger_dx(w: float, step: int, *, round_to_int: bool = True) -> float:
    """Sideways offset for the patch at index *step* in its strip.

    Even rows go left, odd rows go right, by a quarter of the patch width.
    Rounded by default because both shipped callers round: ``raster`` when it
    places the polygon and ``geometry`` when it records the patch rect, and the
    two MUST agree or the recorded box describes a place no ink is.
    """
    dx = -w * STAGGER_FRACTION if step % 2 == 0 else w * STAGGER_FRACTION
    return round(dx) if round_to_int else dx


def vertices(x0: float, y0: float, w: float, ph: float,
             *, round_to_int: bool = False) -> list[tuple[float, float]]:
    """The six vertices of the hexagon filling the slot at *(x0, y0)*, *w* x *ph*.

    Order is top apex, upper right, lower right, bottom apex, lower left, upper
    left — a closed ring, so it can be handed straight to a polygon fill or a
    path.

    **No stagger is applied here.** Two of the callers have it baked into the
    rect they are given already (``geometry.patch_rects_px`` applied it when it
    recorded the box) and only the renderer applies it itself, so folding it in
    would double it for everyone else. Ask ``stagger_dx`` and add it to *x0*.

    With *round_to_int*, every vertex is rounded to the nearest integer, which
    is what the page renderer needs and what nobody else may have — see the
    module docstring. Note that ``cx`` is then rounded INDEPENDENTLY of the left
    and right edges, which is what the renderer has always done; the float path
    leaves it exact.
    """
    t6 = ph * APEX_FRACTION
    left, right = x0, x0 + w
    cx = x0 + w / 2.0
    pts = [
        (cx, y0 - t6),               # top apex
        (right, y0 + t6),            # upper right
        (right, y0 + 5 * t6),        # lower right
        (cx, y0 + ph + t6),          # bottom apex
        (left, y0 + 5 * t6),         # lower left
        (left, y0 + t6),             # upper left
    ]
    if round_to_int:
        return [(round(x), round(y)) for x, y in pts]
    return pts


def contains(x0: float, y0: float, w: float, ph: float,
             x: float, y: float) -> bool:
    """Is *(x, y)* inside the hexagon filling that slot?

    The slot and the hexagon are not the same shape: the slot's four corners lie
    outside the patch and the hexagon's apexes lie outside the slot. Hit-testing
    the slot meant a click on a drawn apex selected the neighbour, and a click
    in a corner selected a patch whose ink is not there (7.2-7.7 % of the click
    area, and 86-92 % of corner clicks).

    Derived from the same vertices rather than restated: at the centre line the
    edge is the apex, ``t6`` beyond the slot; at either flat side it is the
    shoulder, ``t6`` inside it; and the edge between them is straight, so it is
    linear in the distance from the centre.
    """
    if w <= 0:
        return False
    t6 = ph * APEX_FRACTION
    cx = x0 + w / 2.0
    dx = abs(x - cx) / (w / 2.0)
    if dx > 1.0:
        return False
    top = y0 - t6 + dx * 2.0 * t6
    bot = y0 + ph + t6 - dx * 2.0 * t6
    return top <= y <= bot
