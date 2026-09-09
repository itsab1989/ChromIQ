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

import math

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


def stagger_dy(ph: float, strip: int, *, round_to_int: bool = True) -> float:
    """Vertical offset for the strip at index *strip*, on a FLAT-TOP honeycomb.

    THE FLIP MOVES THE STAGGER TO THE OTHER AXIS AND TO THE OTHER INDEX, and
    both halves of that matter. On a pointy-top sheet consecutive patches DOWN a
    strip alternate sideways, which makes each horizontal ROW straight. On a
    flat-top sheet consecutive STRIPS alternate up and down, which makes each
    vertical COLUMN straight — and a straight column is the whole point of the
    option, because that is what an instrument travels along.

    So this is indexed by the strip, not by the patch, and applied to y.
    """
    dy = -ph * STAGGER_FRACTION if strip % 2 == 0 else ph * STAGGER_FRACTION
    return round(dy) if round_to_int else dy


def vertices(x0: float, y0: float, w: float, ph: float,
             *, flat_top: bool = False,
             round_to_int: bool = False) -> list[tuple[float, float]]:
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
    if flat_top:
        # THE SAME HEXAGON, TURNED 30 DEGREES. Not a different shape and not a
        # stretched one: the apexes move from the top and bottom to the left and
        # right, so the sixth-of-the-slot overhang is taken off the WIDTH, and
        # the flat sides become the top and bottom edges. Everything below is
        # the pointy expression with x and y exchanged.
        t6 = w * APEX_FRACTION
        top, bottom = y0, y0 + ph
        cy = y0 + ph / 2.0
        pts = [
            (x0 - t6, cy),               # left apex
            (x0 + t6, top),              # upper left
            (x0 + 5 * t6, top),          # upper right
            (x0 + w + t6, cy),           # right apex
            (x0 + 5 * t6, bottom),       # lower right
            (x0 + t6, bottom),           # lower left
        ]
    else:
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


def side_neighbours(strip: int, step: int, *, flat_top: bool
                    ) -> "list[tuple[int, int] | None]":
    """``(strip, step)`` of the patch facing each of the six sides, in the same
    order as :func:`vertices` and :func:`ring_quads`.

    A ring's side is shared with exactly one neighbour, so each side can be
    coloured by the ordinary pair rule against that patch. `spacer_for_mode` is
    symmetric in its two arguments (checked over 20,000 random pairs), so this
    patch's half-band and the neighbour's half-band come out the same colour and
    the two halves read as ONE shared spacer, which is what Basti asked for:
    *"two touching patches should share a spacer on the side that touches."*

    Indices may be out of range; the caller resolves them and treats a miss as
    the paper.

    POINTY-TOP, ring order (top apex, upper-right, lower-right, bottom apex,
    lower-left, upper-left) so the sides are UR-diagonal, RIGHT flat,
    LR-diagonal, LL-diagonal, LEFT flat, UL-diagonal. The lattice staggers x by
    the STEP's parity, so a step above or below sits half a patch to one side
    and the diagonal neighbours change strip with that parity.

    FLAT-TOP, ring order (left apex, upper-left, upper-right, right apex,
    lower-right, lower-left) so the sides are UL-diagonal, TOP flat,
    UR-diagonal, LR-diagonal, BOTTOM flat, LL-diagonal. Here the lattice
    staggers y by the STRIP's parity, so the flat sides are shared within the
    strip and it is the diagonals that cross to the neighbouring strips.
    """
    p, j = strip, step
    if flat_top:
        # even strips sit HIGH (dy negative), odd strips sit LOW
        up = -1 if p % 2 == 0 else 0
        return [
            (p - 1, j + up),          # upper-left diagonal
            (p, j - 1),               # TOP flat side, same strip
            (p + 1, j + up),          # upper-right diagonal
            (p + 1, j + up + 1),      # lower-right diagonal
            (p, j + 1),               # BOTTOM flat side, same strip
            (p - 1, j + up + 1),      # lower-left diagonal
        ]
    # even steps sit LEFT (dx negative), odd steps sit RIGHT
    right = 0 if j % 2 == 0 else 1
    return [
        (p + right, j - 1),           # upper-right diagonal
        (p + 1, j),                   # RIGHT flat side, same step
        (p + right, j + 1),           # lower-right diagonal
        (p + right - 1, j + 1),       # lower-left diagonal
        (p - 1, j),                   # LEFT flat side, same step
        (p + right - 1, j - 1),       # upper-left diagonal
    ]


def inset(pts: "list[tuple[float, float]]", d: float
          ) -> "list[tuple[float, float]]":
    """The same convex polygon with every EDGE moved *d* inward along its own
    normal. Pass a negative *d* to grow it.

    EVERY EDGE, NOT A SCALE ABOUT THE CENTRE. Scaling is the same thing only
    for a REGULAR polygon, where all six edges are equidistant from the middle.
    A hexagon is only regular while the patch keeps its natural proportions,
    and a user who types a patch size in Manual can stretch it: measured on a
    20.0 x 17.32 mm slot asking for a 1.5 mm ring, the scaling version moved
    two of the six edges by 2.1 mm and two by 1.2 mm, 40 % out either way. The
    spacer is a distance the user asked for, so it has to be that distance on
    all six sides.

    Used to make room for the spacer RING: the gap between two neighbouring
    patches is `2*d`, taken out of the patches' own area rather than out of the
    page, so a ring costs no patches.
    """
    n = len(pts)
    cx = sum(x for x, _ in pts) / n
    cy = sum(y for _, y in pts) / n
    # Each edge becomes a line moved `d` toward the centroid; the new vertices
    # are where consecutive moved lines cross.
    lines = []
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        ex, ey = x2 - x1, y2 - y1
        L = math.hypot(ex, ey)
        if L == 0:
            return list(pts)
        # unit normal, pointed at the centroid
        nx, ny = -ey / L, ex / L
        if (cx - x1) * nx + (cy - y1) * ny < 0:
            nx, ny = -nx, -ny
        # the line a*x + b*y = c, moved d along its normal
        lines.append((nx, ny, nx * x1 + ny * y1 + d))
    out = []
    for i in range(n):
        a1, b1, c1 = lines[i - 1]
        a2, b2, c2 = lines[i]
        det = a1 * b2 - a2 * b1
        if abs(det) < 1e-12:            # parallel edges: nothing to intersect
            return list(pts)
        out.append(((c1 * b2 - c2 * b1) / det, (a1 * c2 - a2 * c1) / det))
    return out


def ring_quads(outer: "list[tuple[float, float]]",
               inner: "list[tuple[float, float]]"
               ) -> "list[list[tuple[float, float]]]":
    """The six trapezoids between *outer* and *inner*, in vertex order.

    Quad *i* is the band along the edge from vertex *i* to vertex *i+1*, which
    is the side facing exactly one neighbour. That is what lets each side take
    its own colour: Basti, 2026-09-09, *"maybe each of the six sides can have
    different colors"*. A side is then coloured by the ordinary pair rule
    against the patch it faces, so "Black & white" keeps meaning what it means.
    """
    n = len(outer)
    return [[outer[i], outer[(i + 1) % n], inner[(i + 1) % n], inner[i]]
            for i in range(n)]


def contains(x0: float, y0: float, w: float, ph: float,
             x: float, y: float, *, flat_top: bool = False) -> bool:
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
    if w <= 0 or ph <= 0:
        return False
    if flat_top:
        # x and y exchanged, exactly as in `vertices`.
        t6 = w * APEX_FRACTION
        cy = y0 + ph / 2.0
        dy = abs(y - cy) / (ph / 2.0)
        if dy > 1.0:
            return False
        left = x0 - t6 + dy * 2.0 * t6
        right = x0 + w + t6 - dy * 2.0 * t6
        return left <= x <= right
    t6 = ph * APEX_FRACTION
    cx = x0 + w / 2.0
    dx = abs(x - cx) / (w / 2.0)
    if dx > 1.0:
        return False
    top = y0 - t6 + dx * 2.0 * t6
    bot = y0 + ph + t6 - dx * 2.0 * t6
    return top <= y <= bot
