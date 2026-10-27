"""Fix round r7 of 4.3.18: Auto align only turns a chart a quarter inside the
recogniser's rectangle when the turned grid still has the chart's shape.

Turning the corner order by a quarter lays the chart's x axis along the quad's
y edge. On a chart that is not square that is not a placement of the chart at
all: a 30 x 20 chart in its own 30 x 20 quad, turned a quarter, is a 20 x 30
grid squeezed into it, every patch 2.25 times as tall, relative to its width,
as on paper. Its colours can still read, though: with a chart whose colours
run down its columns chosen for a scan whose colours run along its rows, the
squeezed grid read 0.998 and was ACCEPTED 30 patches out, on a dark and a
light lid alike, in 4.3.17 and in every 4.3.18 round before this one.

Now `turns_that_fit` keeps only the ways up that give the patches their own
shape (within `TURNED_SHAPE_TOLERANCE`), so the case is refused with
M-SCAN-ALIGN-OFF-PATCHES, whose last paragraph is the wrong-chart advice. A
chart within about 12 % of square keeps all four ways up, as before, and a
chart really turned on the glass is still found, because the recogniser's
rectangle is then turned too.
"""
from __future__ import annotations

import math
import subprocess
from collections import namedtuple

import numpy as np
import pytest

from workflow import scan_auto_align as A
from workflow.scan_auto_align import (
    TURNED_SHAPE_TOLERANCE, auto_align, corners_from_candidate, pitch_search,
    agreement_scorer, turns_that_fit)

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

Box = namedtuple("Box", "name x1 y1 x2 y2")
PITCH = 10.0
SCALE = 2.0          # pixels per chart unit


def _boxes(nx, ny):
    return [Box(f"P{r * nx + c + 1}", c * PITCH, r * PITCH,
                (c + 1) * PITCH, (r + 1) * PITCH)
            for r in range(ny) for c in range(nx)]


def _bbox(nx, ny):
    return (0.0, 0.0, nx * PITCH, ny * PITCH)


def _scan(tmp_path, nx, ny, lum, *, bed=20, turn=0, name="scan"):
    """A flat render of the chart on paper on a scanner bed, turned *turn*
    degrees clockwise on the glass. Returns (path, true corners, size)."""
    rng = np.random.default_rng(0)
    margin = 3 * PITCH * SCALE
    w = int(nx * PITCH * SCALE + 2 * margin) + 100
    h = int(ny * PITCH * SCALE + 2 * margin) + 100
    img = np.full((h, w), float(bed), np.float32)
    img[50:h - 50, 50:w - 50] = 240
    ox = oy = 50 + margin
    for i, b in enumerate(_boxes(nx, ny)):
        img[int(oy + b.y1 * SCALE):int(oy + b.y2 * SCALE),
            int(ox + b.x1 * SCALE):int(ox + b.x2 * SCALE)] = 10 + 2.2 * lum[i]
    img += rng.normal(0, 2.0, img.shape)
    q = [(ox, oy), (ox + nx * PITCH * SCALE, oy),
         (ox + nx * PITCH * SCALE, oy + ny * PITCH * SCALE),
         (ox, oy + ny * PITCH * SCALE)]
    for _ in range(turn // 90):
        hh = img.shape[0]
        img = np.rot90(img, -1)
        q = [(hh - y, x) for x, y in q]
    p = tmp_path / f"{name}.tif"
    Image.fromarray(img.clip(0, 255).astype(np.uint8)).convert("RGB").save(p)
    return p, q, (img.shape[1], img.shape[0])


def _candidate(q, bbox):
    """scanin's -v2 line whose `corners_from_candidate` is *q*."""
    minx, miny, maxx, maxy = bbox
    ex = ((q[1][0] - q[0][0]) / (maxx - minx), (q[1][1] - q[0][1]) / (maxx - minx))
    ey = ((q[3][0] - q[0][0]) / (maxy - miny), (q[3][1] - q[0][1]) / (maxy - miny))
    ir = math.atan2(-ex[1], ex[0])
    c, s = math.cos(ir), math.sin(ir)
    t0 = q[0][0] - minx * ex[0] - miny * ey[0]
    t3 = q[0][1] - minx * ex[1] - miny * ey[1]
    return (f"cc = 0.8, irot = {math.degrees(ir):f}, xoff = {c * t0 - s * t3:f}, "
            f"yoff = {s * t0 + c * t3:f}, xscale = {math.hypot(*ex):f}, "
            f"yscale = {math.hypot(*ey):f}\n")


class _Runner:
    def __init__(self, *logs):
        self.logs = list(logs)

    def __call__(self, args, **kw):
        return subprocess.CompletedProcess(
            args, 0, stdout=self.logs.pop(0) if self.logs else "", stderr="")


def _align(p, q, size, nx, ny, want):
    cie = p.with_suffix(".cie")
    cie.write_text("")
    return auto_align("scanin", p, p, cie, _boxes(nx, ny), want, size,
                      runner=_Runner(_candidate(q, _bbox(nx, ny))))


def _worst(a, b):
    return max(math.dist(u, v) for u, v in zip(a, b)) / (PITCH * SCALE)


# ---------------------------------------------------------------------------
# the shape rule itself
# ---------------------------------------------------------------------------
def test_a_quarter_turn_of_a_three_by_two_chart_does_not_fit_its_own_quad():
    bbox = _bbox(30, 20)
    q = corners_from_candidate((0.8, 0.0, 0.0, 0.0, 4.0, 4.0), bbox)
    assert turns_that_fit(_boxes(30, 20), q) == [0, 2]


def test_the_rule_follows_the_recognisers_own_turn():
    """A chart turned on the glass gives a turned rectangle, in marquee
    order, so its own way up and the half turn fit, and the quarter turns
    do not."""
    bbox = _bbox(30, 20)
    for irot in (90.0, 270.0, 180.0, 2.5):
        q = corners_from_candidate((0.8, irot, 0.0, 0.0, 4.0, 4.0), bbox)
        assert turns_that_fit(_boxes(30, 20), q) == [0, 2], irot


def test_a_square_chart_and_a_nearly_square_one_keep_all_four():
    for nx, ny in ((20, 20), (21, 20), (20, 21)):
        q = corners_from_candidate((0.8, 0.0, 0.0, 0.0, 4.0, 4.0), _bbox(nx, ny))
        assert turns_that_fit(_boxes(nx, ny), q) == [0, 1, 2, 3], (nx, ny)


def test_a_foreshortened_view_still_keeps_its_own_way_up():
    """A view off square shortens one axis; the right way up is the one that
    stretches the patches least, so it is always kept."""
    bbox = _bbox(30, 20)
    for xs, ys in ((4.0, 3.4), (3.4, 4.0), (4.0, 4.6)):
        q = corners_from_candidate((0.8, 0.0, 0.0, 0.0, xs, ys), bbox)
        assert 0 in turns_that_fit(_boxes(30, 20), q), (xs, ys)


def test_the_tolerance_is_the_documented_one():
    assert TURNED_SHAPE_TOLERANCE == pytest.approx(1.25)


# ---------------------------------------------------------------------------
# the case that was accepted, and what must still be found
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bed", [20, 238])
def test_the_wrong_chart_is_no_longer_accepted_turned(tmp_path, bed):
    """A row ramp scanned, a column ramp chosen: turned a quarter, the one
    reads as the other (0.998), 30 patches out. Refused now, with the
    message that says to check the chart chosen."""
    nx, ny = 30, 20
    scan_lum = [(i % nx) * 100 / nx for i in range(nx * ny)]
    chart_lum = {f"P{i + 1}": (i // nx) * 100 / ny for i in range(nx * ny)}
    p, q, size = _scan(tmp_path, nx, ny, scan_lum, bed=bed)
    squeezed = q[3:] + q[:3]
    sc = agreement_scorer(p, chart_lum)
    assert sc(_boxes(nx, ny), squeezed, 0.6) > 0.95, (
        "the squeezed grid no longer reads this scan, so the test proves "
        "nothing")
    r = _align(p, q, size, nx, ny, chart_lum)
    assert not r.ok, f"accepted {_worst(r.corners, q):.1f} pitches out"
    assert r.reason == "off-the-patches", (r.reason, r.rejected)


def test_pitch_search_never_answers_with_a_squeezed_grid(tmp_path):
    nx, ny = 30, 20
    scan_lum = [(i % nx) * 100 / nx for i in range(nx * ny)]
    chart_lum = {f"P{i + 1}": (i // nx) * 100 / ny for i in range(nx * ny)}
    p, q, size = _scan(tmp_path, nx, ny, scan_lum)
    got = pitch_search(agreement_scorer(p, chart_lum), _boxes(nx, ny), q, size)
    assert got is None or got[2][2] in (0, 2), got


def _shuffled(n, seed=2):
    return list(np.random.default_rng(seed).permutation(n) * 100.0 / n)


@pytest.mark.parametrize("turn", [0, 90, 180, 270])
def test_a_chart_turned_on_the_glass_is_still_placed(tmp_path, turn):
    nx, ny = 30, 20
    lum = _shuffled(nx * ny)
    want = {f"P{i + 1}": v for i, v in enumerate(lum)}
    p, q, size = _scan(tmp_path, nx, ny, lum, turn=turn)
    r = _align(p, q, size, nx, ny, want)
    assert r.ok, (r.reason, r.rejected)
    assert _worst(r.corners, q) < 0.2


def test_a_half_turn_the_recogniser_got_wrong_is_still_put_right(tmp_path):
    nx, ny = 30, 20
    lum = _shuffled(nx * ny)
    want = {f"P{i + 1}": v for i, v in enumerate(lum)}
    p, q, size = _scan(tmp_path, nx, ny, lum, turn=90)
    r = _align(p, q[2:] + q[:2], size, nx, ny, want)
    assert r.ok, (r.reason, r.rejected)
    assert _worst(r.corners, q) < 0.2


def test_a_square_chart_is_still_turned_a_quarter_when_the_colours_say_so(tmp_path):
    """On a square chart the quarter turn is a real placement, and the
    colours decide it as before."""
    nx = ny = 20
    lum = _shuffled(nx * ny, seed=5)
    want = {f"P{i + 1}": v for i, v in enumerate(lum)}
    p, q, size = _scan(tmp_path, nx, ny, lum, turn=90)
    r = _align(p, q[1:] + q[:1], size, nx, ny, want)
    assert r.ok, (r.reason, r.rejected)
    assert _worst(r.corners, q) < 0.2


def test_the_module_exports_the_rule():
    assert "turns_that_fit" in A.__all__
