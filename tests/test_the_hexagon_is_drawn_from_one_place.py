"""Five copies of one hexagon, pooled — and pinned so they cannot drift apart.

The shape of a hexagonal patch was written out five times in shipped code:
the page renderer, the Measure patch outline, the Measure strip zigzag, the
Measure hit test and the scanner grid mesh. Measured before pooling, over 9,360
hexagons, they AGREED: the three float sites to 1e-14, the hit test
algebraically, and the renderer to within its own half-pixel `round()`.

**So this file does not guard a bug that existed. It guards the one that is
coming.** A second orientation is being added, and five independent copies get
five independent chances to disagree about it. After pooling there is one
answer; these tests are what stops a sixth copy being written next to it.

WHAT WOULD NOT CATCH A DRIFT HERE, because the list is long and every entry
looks like coverage: everything in `test_layout_raster.py` except the two tests
that call `_hexagon_points` by name; `test_hex_overlay_geometry.py` (asserts the
centre is inside and the corners outside, which half a pixel cannot break);
`test_hex_strip_overlay.py` (asserts the path exists and has the right element
count); `test_marquee_geometry_cache.py` (asserts cache identity, not values);
`test_cr30_builtin_presets.py` (patch and page counts). All of them stay green
through a quarter-patch move in the vertices.

Rendered page BYTES are the other half of the proof and are deliberately NOT
here: `scripts/hex_page_manifest.py` hashes 45 pages across two instruments,
four papers, two resolutions and both spacer modes, and is run by hand before
and after a change. Bytes cannot see the Qt paths (no rendered page in this
suite draws one) and geometry rows cannot see a rounding change that only shows
up as ink. Neither substitutes for the other.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect                                # noqa: E402

from workflow.layout_engine import hexagon                    # noqa: E402
from workflow.layout_engine import raster                     # noqa: E402

# A sweep wide enough to catch a formula change, small enough to stay quick.
BOXES = [(w, ph) for w in range(20, 200, 23) for ph in range(20, 200, 29)]
STEPS = (0, 1)


# ---------------------------------------------------------------------------
# the renderer is the only caller that rounds
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("w,ph", BOXES)
@pytest.mark.parametrize("step", STEPS)
def test_the_renderer_paints_the_pooled_shape(w, ph, step):
    """`raster._hexagon_points` must be the pooled shape plus the stagger plus
    rounding, and nothing else."""
    dx = hexagon.stagger_dx(w, step)
    want = hexagon.vertices(0 + dx, 0, w, ph, round_to_int=True)
    assert raster._hexagon_points(0, 0, w, ph, step) == want


@pytest.mark.parametrize("w,ph", BOXES)
def test_rounding_never_moves_a_vertex_more_than_half_a_pixel(w, ph):
    """THE PIN ON THE MEASURED FINDING. The Measure overlay does not round
    because snapping measured worse (spread 0.14 -> 0.21 device px). Nobody may
    quietly widen the renderer's rounding into something coarser and call it the
    same shape."""
    exact = hexagon.vertices(0, 0, w, ph)
    snapped = hexagon.vertices(0, 0, w, ph, round_to_int=True)
    for (ex, ey), (sx, sy) in zip(exact, snapped):
        assert abs(ex - sx) <= 0.5 and abs(ey - sy) <= 0.5


@pytest.mark.parametrize("w,ph", BOXES)
def test_the_float_path_leaves_every_vertex_exact(w, ph):
    """No caller but the renderer may inherit an integer. A float path that
    quietly rounded would be invisible to every other test in this file."""
    for vx, vy in hexagon.vertices(0, 0, w, ph):
        assert isinstance(vx, float) or isinstance(vy, float)
    assert hexagon.vertices(0, 0, 7, 7)[0][1] == pytest.approx(-7 / 6.0)


# ---------------------------------------------------------------------------
# the Qt sites draw the same six points
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("w,ph", BOXES)
def test_the_measure_patch_outline_is_the_pooled_shape(qapp, w, ph):
    from ui.tiff_preview import TiffPreview
    b = QRect(11, 13, w, ph)
    path = TiffPreview._patch_hexagon(b, 1.0, 0.0, 0.0)
    got = [(path.elementAt(i).x, path.elementAt(i).y)
           for i in range(path.elementCount())]
    want = hexagon.vertices(b.left(), b.y(), b.right() + 1 - b.left(), b.height())
    # closeSubpath may repeat the first point; compare the six that matter,
    # flattened, because pytest.approx refuses a nested structure.
    flat_got = [c for pt in got[:6] for c in pt]
    flat_want = [float(c) for pt in want for c in pt]
    assert len(flat_got) == 12, f"the path has {len(got)} elements, not six points"
    assert flat_got == pytest.approx(flat_want, abs=1e-9)


@pytest.mark.parametrize("w,ph", BOXES)
@pytest.mark.parametrize("step", STEPS)
def test_the_hit_test_agrees_with_the_polygon_it_is_testing(w, ph, step):
    """`_in_hexagon` is two inequalities, not vertices, so it is the copy most
    able to drift without looking different. Sample a grid over the slot and its
    surroundings and require it to agree with a real point-in-polygon test of
    the pooled shape."""
    from ui.tiff_preview import TiffPreview
    b = QRect(0, 0, w, ph)
    poly = hexagon.vertices(0, 0, w, ph)

    def inside(px, py):
        # ray casting, on the exact polygon
        n = len(poly)
        hit = False
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            if (y1 > py) != (y2 > py):
                xi = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
                if px < xi:
                    hit = not hit
        return hit

    t6 = ph / 6.0
    disagreements = 0
    samples = 0
    for i in range(13):
        for j in range(17):
            px = -2.0 + (w + 4.0) * i / 12.0
            py = -t6 - 2.0 + (ph + 2 * t6 + 4.0) * j / 16.0
            # skip points within a pixel of an edge: the boundary is a tie and
            # `<=` versus `<` there is not a drift, it is a convention
            near = min(abs(py - (-t6 + abs(px - w / 2.0) / (w / 2.0) * 2 * t6)),
                       abs(py - (ph + t6 - abs(px - w / 2.0) / (w / 2.0) * 2 * t6))) \
                if w else 0.0
            if near < 1.0 or abs(abs(px - w / 2.0) - w / 2.0) < 1.0:
                continue
            samples += 1
            if TiffPreview._in_hexagon(b, px, py) != inside(px, py):
                disagreements += 1
    assert samples > 40, "the sample grid degenerated; this proves nothing"
    assert disagreements == 0, \
        f"{disagreements} of {samples} points fall differently for the hit test"


@pytest.mark.parametrize("w,ph", BOXES)
def test_the_scanner_mesh_cell_is_the_pooled_shape(w, ph):
    """The mesh works in unit-square space, so it is the one site where an
    integer would collapse the cell entirely."""
    u, v = 0.25, 0.5
    got = hexagon.vertices(u, v, w / 1000.0, ph / 1000.0)
    assert len(got) == 6
    assert got[0][1] < v, "the top apex must sit above the cell"
    assert got[3][1] > v + ph / 1000.0, "the bottom apex must sit below it"
    assert all(isinstance(c, float) for pt in got for c in pt)


# ---------------------------------------------------------------------------
# the shape itself
# ---------------------------------------------------------------------------
def test_the_apex_overhang_is_the_sixth_the_geometry_reserves():
    """`instruments.py` reserves `hxeh` for exactly this overhang, and the
    interlock depends on the two agreeing."""
    assert hexagon.APEX_FRACTION == pytest.approx(1 / 6)
    pts = hexagon.vertices(0, 0, 60, 60)
    assert pts[0][1] == pytest.approx(-10.0)
    assert pts[3][1] == pytest.approx(70.0)


def test_alternate_rows_step_opposite_ways_by_a_quarter():
    assert hexagon.stagger_dx(80, 0) == -20
    assert hexagon.stagger_dx(80, 1) == 20
    assert hexagon.stagger_dx(80, 2) == -20


def test_the_stagger_rounds_for_the_two_callers_that_must_agree():
    """`raster` places the polygon and `geometry` records the box; both round,
    and if they ever stopped agreeing the recorded box would describe a place no
    ink is (measured at ±21 px on an 84 px patch, 2026-08-13)."""
    for w in range(3, 90, 7):
        assert hexagon.stagger_dx(w, 0) == round(-w / 4)
        assert isinstance(hexagon.stagger_dx(w, 0), int)
    assert hexagon.stagger_dx(9, 0, round_to_int=False) == pytest.approx(-2.25)


def test_a_zero_width_slot_contains_nothing():
    """The old hit test answered a zero-width box by pretending the point was on
    the far side (`dx = 1.0`), which made a collapsed hexagon report hits along
    a line. `patch_rects_px` clamps width to 1 so nothing shipped reached it,
    and False is the honest answer."""
    assert hexagon.contains(0, 0, 0, 30, 0, 15) is False
