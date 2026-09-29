"""Find the printed patch block in a scan WITHOUT asking what a patch looks like.

WHY THIS EXISTS.
The placement ladder in :mod:`workflow.scan_placement` is search, refine, check.
Measured on Knut's CR30 honeycomb (2026-09-11, ``AUTO-ALIGN-ON-HEXAGONS.md``),
steps 2 and 3 work on a honeycomb exactly as they do on a grid of squares --
the refinement reshapes it onto the patches and the check separates a right
placement from a wrong one by 0.969 against 0.514, with the floor at 0.80.
Only step 1 fails, and it fails completely: ``scanin`` returns *not recognised*
with **zero** candidates from every starting point, because its recogniser
builds an XLIST/YLIST out of the chart's horizontal and vertical edges and an
interlocking hexagon has no continuous horizontal edge to give it.

So this module is a step 1 for charts scanin cannot recognise. It never asks
what a patch looks like. It asks only where the INK is, which is a question a
honeycomb answers as plainly as a chequerboard.

THE SHAPE OF THE ANSWER IS WHAT MAKES IT SAFE.
It proposes; it never decides. Every quad it returns goes on to the ladder's own
refinement and then to :func:`workflow.scan_placement.seated_verdict` and
:func:`workflow.scan_auto_align.reference_agreement_at` on the corners about to
be applied, exactly like scanin's own answers. Measured over the sweep in
``~/Desktop/ChromIQ-hex-autoalign``, every case this module got wrong was
refused downstream at an agreement of 0.06-0.39 against the 0.80 floor. The
downside of this module is "auto align still does not work"; it is never "auto
align put the grid somewhere wrong".

WHY SEVERAL ROUTES AND NOT ONE.
The first prototype of this (2026-09-11) was a single pipeline, and four
variants of its region-finding step scored between 0/30 and 30/30 on ONE
chart's synthetic scans. That swing is not noise and it is not tunable away:
bounding *all* the ink bounds the PAGE, because strip labels, row numbers and
the notes band are ink too and sit outside the block, while bounding one
connected component bounds the block only when the block IS one component.
Which is right depends on the chart.

Choosing between them by hand is how that prototype got its 30/30, and it is
why it was not landed. So this module does not choose. It proposes a handful of
quads from independent routes -- the largest ink component, the ink components
merged, the ink profile trimmed at two thresholds, the region the user drew --
and scores every one of them, four ways up, with the ladder's OWN
:func:`~workflow.scan_auto_align.reference_agreement_at`. The best wins. A route
that is wrong for this chart simply scores badly and loses, and a route that is
wrong for EVERY chart costs a fraction of a second and nothing else.

AND WHY THE COLOURS CANNOT FINISH THE JOB ON THEIR OWN.
None of these routes bounds the PATCH BLOCK. They bound the INK, and on an
interlocking honeycomb the ink is not the patch block: a flat-top hexagon's
apexes reach a sixth of the slot past the first and last columns, so a quad
drawn round the ink is about ``1/(3*columns)`` too wide -- 1.9 % on an
18-column sheet, measured 1.2 % on the largest-blob route. The agreement cannot
see a stretch that small (it scored 1.0000 on quads 11 and 16 px apart), so the
winner used to be decided by float noise, and it moved when the user's Sample
area moved. :data:`SEARCH_SAMPLE_AREA` takes the setting out of it and
:data:`AGREEMENT_TIE_BAND` gives the decision to the measure that can see it.

WHAT IT WILL NOT DO.
It will not overrule a placement somebody made. When *current_corners* are a
real placement (the window passes them only when the marquee says the user put
them there, never for its own opening rectangle), a proposal must beat them by
:data:`~workflow.scan_auto_align.IMPROVEMENT_MARGIN` or this module returns
nothing and the ladder refines the user's own corners, which is what it does
today.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from core.logger import get_logger
from workflow.layout_engine.hexagon import APEX_FRACTION

log = get_logger(__name__)

__all__ = ["HexBlockResult", "find_block", "block_candidates", "apex_factors",
           "convex_hull", "min_area_quad", "scaled_about_centre"]

#: The longest side the picture is reduced to before anything is measured.
#: Everything here is about WHERE a large region is, not about its detail, and
#: at 1000 px a 300 dpi A4 scan still carries 12 samples across a 12 mm patch.
#: The quads come back in full-resolution pixels either way.
WORK_MAX_SIDE = 1000

#: A candidate must cover at least this much of the picture to be worth
#: scoring. The patch block of a chart that fills its sheet covers 40-60 %; a
#: sheet photographed small in a big frame can be far less, so this is only a
#: guard against a stray blob, not a judgement about framing.
MIN_AREA_FRACTION = 0.02

#: The share of each patch this module scores its candidates on, as an AREA --
#: and deliberately NOT the user's Sample area spinbox.
#:
#: WHICH QUAD IS THE CHART IS A FACT ABOUT THE PICTURE, and it must not change
#: because somebody moved a spinbox that says how much of each patch to read.
#: It did: the fraction was passed straight down from the window, so the routes
#: were scored differently at 50 % than at 60 % and a different one could win.
#: Knut, 2026-09-11, on a CR30 honeycomb, reported exactly that as "the
#: alignment varies" -- and his own log shows the opposite of variation at one
#: setting: four presses at 60 % returned the SAME answer to every decimal
#: (rho 0.9690, drift 0.04849, moved 0.261 pitch), and his two screenshots of
#: them are identical to the pixel. What moved was the setting.
#:
#: 0.60 is the number :data:`~workflow.scan_auto_align.SEATING_SAMPLE_AREA`
#: already uses for the drift gate, for the same reason written out there.
SEARCH_SAMPLE_AREA = 0.60

#: How close in agreement two candidates must be before the PICTURE, rather
#: than the colours, decides between them.
#:
#: The agreement is a rank correlation over the patch luminances, and on a
#: chart it can predict it SATURATES: measured on a two-page CR30 honeycomb
#: (12 mm flat-top patches, 300 dpi simulated scan, ground truth known to the
#: pixel because the scan is the chart's own page put through a known
#: rotation), three candidate quads whose worst corner was 11.0, 16.0 and 12.0
#: px from the truth all scored **1.0000**, and so did the truth. A measure
#: that cannot separate the truth from a quad 16 px out cannot choose between
#: them, so the winner was decided by the last bits of a float.
#:
#: :func:`~workflow.scan_auto_align.seating_drift` can separate them, because
#: it asks the patches instead of the colours. On the same two pages it ranked
#: every candidate in the right order: truth 0.0140, then 0.0427 (11.0 px),
#: 0.0705 (16.0 px), 0.3316 (48.4 px).
#:
#: The band is the ladder's own
#: :data:`~workflow.scan_auto_align.IMPROVEMENT_MARGIN`: a difference in
#: agreement smaller than that is one the ladder itself already refuses to move
#: a grid for. It is small enough that a quad a whole pitch out -- which scores
#: 0.514 against a right one's 0.969 on this very chart -- can never be in the
#: band of a right one, so the colours keep their veto over what the chart is
#: and the drift only picks between placements of it.
AGREEMENT_TIE_BAND = 0.02

#: How many candidates the seating is measured for. Each one costs a pass over
#: the picture (0.26 s on a 300 dpi A4 scan here), and the agreement saturates,
#: so without a cap a chart with nine routes would pay for eighteen. Eight is
#: the four routes a honeycomb page typically offers, each with its apex
#: correction; the rest keep the order the agreement gave them.
MAX_SEATED = 8


@dataclass
class HexBlockResult:
    """The winning quad and everything the log needs to say where it came from."""

    #: TL/TR/BR/BL in FULL-RESOLUTION image pixels, or None
    corners: list[tuple[float, float]] | None = None
    #: reference agreement at those corners, by the ladder's own measure
    rho: float | None = None
    #: agreement at the corners the user had, when they had any
    rho_before: float | None = None
    #: which route proposed the winner, for the log only
    route: str = ""
    #: how many quads were proposed and scored
    candidates: int = 0
    #: the seating drift of the winner, in patch pitches, when the tie-break
    #: measured one (:data:`AGREEMENT_TIE_BAND`) -- for the log only
    drift: "float | None" = None
    #: why there is no answer, when there is none
    reason: str = ""
    #: every route's best score, for the log and for the sweep records
    scores: list[tuple[str, float]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.corners is not None


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------
def convex_hull(points: Sequence[tuple[float, float]]
                ) -> list[tuple[float, float]]:
    """The convex hull of *points*, counter-clockwise in a y-DOWN image, as a
    list with no repeated endpoint. Andrew's monotone chain."""
    pts = sorted({(float(x), float(y)) for x, y in points})
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return ((a[0] - o[0]) * (b[1] - o[1])
                - (a[1] - o[1]) * (b[0] - o[0]))

    lower: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def min_area_quad(points: Sequence[tuple[float, float]]
                  ) -> "list[tuple[float, float]] | None":
    """The smallest-area rotated rectangle around *points*, as four corners.

    Rotating calipers over the convex hull, which is EXACT: the minimum-area
    enclosing rectangle always has a side flush with a hull edge. The earlier
    prototype swept 0.25-degree steps over +-12 degrees instead, which is both
    slower and wrong outside that window -- a sheet dropped on the glass at 20
    degrees was simply not findable.

    The corners come back wound the way :func:`workflow.scan_auto_align.
    _agreement` winds the chart's own bounding box (clockwise with y down), so
    the four cyclic rotations of the answer are the four ways the chart can sit
    in it and none of them is a mirror image.
    """
    hull = convex_hull(points)
    if len(hull) < 3:
        return None
    best = None
    n = len(hull)
    for i in range(n):
        px, py = hull[i]
        qx, qy = hull[(i + 1) % n]
        ex, ey = qx - px, qy - py
        length = math.hypot(ex, ey)
        if length < 1e-9:
            continue
        ux, uy = ex / length, ey / length
        vx, vy = -uy, ux
        us = [h[0] * ux + h[1] * uy for h in hull]
        vs = [h[0] * vx + h[1] * vy for h in hull]
        u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
        area = (u1 - u0) * (v1 - v0)
        if best is None or area < best[0]:
            best = (area, ux, uy, vx, vy, u0, u1, v0, v1)
    if best is None:
        return None
    _, ux, uy, vx, vy, u0, u1, v0, v1 = best
    corners = [(u * ux + v * vx, u * uy + v * vy)
               for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
    return _wound_like_the_chart(corners)


def _wound_like_the_chart(corners: Sequence[tuple[float, float]]
                          ) -> list[tuple[float, float]]:
    """The same four corners, wound clockwise in a y-down image and starting
    at the one nearest the top-left. The winding is what stops a proposal being
    the chart's mirror image; the starting corner only makes a log line and a
    test readable, because all four rotations are scored anyway."""
    quad = [(float(x), float(y)) for x, y in corners]
    shoelace = sum(quad[i][0] * quad[(i + 1) % 4][1]
                   - quad[(i + 1) % 4][0] * quad[i][1] for i in range(4))
    if shoelace < 0:
        quad = [quad[0], quad[3], quad[2], quad[1]]
    k = min(range(4), key=lambda i: quad[i][0] + quad[i][1])
    return quad[k:] + quad[:k]


def apex_factors(boxes: Sequence) -> tuple[float, float]:
    """How far an INK-bounded quad overruns the PATCH-SLOT quad this chart's
    boxes describe, as a factor per axis: ``(along the top edge, down the
    side)``.

    THE INK IS NOT THE PATCH BLOCK, AND ON A HONEYCOMB IT NEVER IS. Every route
    in this module bounds ink. A hexagon, though, reaches a sixth of its slot
    past the slot on the axis its apexes point along
    (:data:`workflow.layout_engine.hexagon.APEX_FRACTION`) -- that overhang is
    what makes the rows interlock -- while the ``.cht`` boxes, which are what
    the marquee quad is defined against, are the SLOTS. So a quad drawn round
    the ink of an 18-column flat-top sheet is ``1/(3*18)`` = 1.9 % too wide,
    and the far columns' sample boxes land a sixth of a patch outside their
    hexagons. Measured on a two-page CR30 honeycomb at 300 dpi with the truth
    known to the pixel: the largest-blob route came back 1.0203 and 1.0296 too
    wide (predicted 1.0185 and 1.0278), worst corner 24.6 and 24.4 px.
    Corrected by this factor: 5.9 and 5.4 px, and the seating drift fell from
    0.1305 to 0.0249 and from 0.1340 to 0.0207.

    WHICH AXIS, read off the boxes rather than guessed. A flat-top honeycomb
    has straight COLUMNS, so its distinct box x positions are a slot width
    apart and its y positions half a slot height apart; a pointy-top one is the
    same statement turned. Anything that is not one of those two patterns gets
    ``(1.0, 1.0)`` -- no correction, which is what this module did before.

    The factor is the SPAN, not the column count, so it is right for a page
    with any number of columns on it, the part-full last one included.
    """
    if len(boxes) < 4:
        return 1.0, 1.0
    ws = sorted((b.x2 - b.x1) for b in boxes)
    hs = sorted((b.y2 - b.y1) for b in boxes)
    w, h = ws[len(ws) // 2], hs[len(hs) // 2]
    if w <= 0 or h <= 0:
        return 1.0, 1.0
    xs = sorted({round(b.x1, 2) for b in boxes})
    ys = sorted({round(b.y1, 2) for b in boxes})
    dx = sorted(b - a for a, b in zip(xs, xs[1:]))
    dy = sorted(b - a for a, b in zip(ys, ys[1:]))
    if not dx or not dy:
        return 1.0, 1.0
    dx, dy = dx[len(dx) // 2], dy[len(dy) // 2]
    spanx = max(b.x2 for b in boxes) - min(b.x1 for b in boxes)
    spany = max(b.y2 for b in boxes) - min(b.y1 for b in boxes)
    flat_top = dx > 0.75 * w and dy < 0.75 * h
    pointy = dy > 0.75 * h and dx < 0.75 * w
    over = APEX_FRACTION * 2.0
    if flat_top and spanx > 0:
        return spanx / (spanx + over * w), 1.0
    if pointy and spany > 0:
        return 1.0, spany / (spany + over * h)
    return 1.0, 1.0


def scaled_about_centre(quad: Sequence[tuple[float, float]],
                        fu: float, fv: float) -> list[tuple[float, float]]:
    """*quad* scaled about its own centre, along its OWN axes: *fu* along the
    top edge, *fv* down the side. Turned candidates therefore get the
    correction on the axis the chart would sit on in that orientation."""
    quad = [(float(x), float(y)) for x, y in quad]
    cx = sum(p[0] for p in quad) / 4.0
    cy = sum(p[1] for p in quad) / 4.0
    ux, uy = quad[1][0] - quad[0][0], quad[1][1] - quad[0][1]
    length = math.hypot(ux, uy)
    if length < 1e-9:
        return quad
    ux, uy = ux / length, uy / length
    out = []
    for x, y in quad:
        dx, dy = x - cx, y - cy
        a = (dx * ux + dy * uy) * fu
        b = (-dx * uy + dy * ux) * fv
        out.append((cx + a * ux - b * uy, cy + a * uy + b * ux))
    return out


def _plausible(quad: Sequence[tuple[float, float]],
               size: tuple[int, int]) -> bool:
    """Could this quad be a printed block at all? Finite, inside the picture,
    and not a speck. Deliberately NOT an aspect-ratio test: the ink bounds and
    the chart's patch bounds differ by a spacer ring on some charts and by a
    label column on others, and a shape test tight enough to be worth having
    was the step that threw the right answer away."""
    w, h = size
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    if not all(map(math.isfinite, xs + ys)):
        return False
    pad = 0.02 * max(w, h)
    if min(xs) < -pad or min(ys) < -pad or max(xs) > w + pad or max(ys) > h + pad:
        return False
    side = min(math.hypot(quad[1][0] - quad[0][0], quad[1][1] - quad[0][1]),
               math.hypot(quad[3][0] - quad[0][0], quad[3][1] - quad[0][1]))
    if side < 8:
        return False
    area = abs(sum(quad[i][0] * quad[(i + 1) % 4][1]
                   - quad[(i + 1) % 4][0] * quad[i][1]
                   for i in range(4))) / 2.0
    return area >= MIN_AREA_FRACTION * w * h


# ---------------------------------------------------------------------------
# connected components, in numpy, without scipy
# ---------------------------------------------------------------------------
def _components(mask):
    """``(labels, sizes)`` for the 4-connected components of a boolean mask.

    Union-find over ROW RUNS rather than over pixels. The prototype's
    pixel-by-pixel flood fill was a Python loop over every set pixel and cost
    more than everything else here put together; a scan has far fewer runs than
    ink pixels, and scipy is not a dependency of this application.
    """
    import numpy as np
    h, w = mask.shape
    padded = np.zeros((h, w + 2), bool)
    padded[:, 1:w + 1] = mask
    edges = np.diff(padded.astype(np.int8), axis=1)
    srow, scol = np.nonzero(edges == 1)
    erow, ecol = np.nonzero(edges == -1)
    n = srow.size
    if n == 0:
        return np.zeros((h, w), np.int32), np.zeros(1, np.int64)

    parent = list(range(n))

    def find(a: int) -> int:
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:
            parent[a], a = root, parent[a]
        return root

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # runs are produced in row-major order, so each row's runs are contiguous
    row_start = np.searchsorted(srow, np.arange(h), side="left")
    row_end = np.searchsorted(srow, np.arange(h), side="right")
    for y in range(1, h):
        i, j = int(row_start[y]), int(row_start[y - 1])
        i_end, j_end = int(row_end[y]), int(row_end[y - 1])
        while i < i_end and j < j_end:
            if ecol[i] <= scol[j]:        # run i ends before run j starts
                i += 1
            elif ecol[j] <= scol[i]:      # run j ends before run i starts
                j += 1
            else:
                union(i, j)
                if ecol[i] < ecol[j]:
                    i += 1
                else:
                    j += 1

    roots = np.fromiter((find(i) for i in range(n)), np.int64, n)
    uniq, compact = np.unique(roots, return_inverse=True)
    labels = np.zeros((h, w), np.int32)
    for i in range(n):
        labels[srow[i], scol[i]:ecol[i]] = compact[i] + 1
    sizes = np.zeros(uniq.size + 1, np.int64)
    np.add.at(sizes, compact + 1, (ecol - scol).astype(np.int64))
    return labels, sizes


# ---------------------------------------------------------------------------
# the routes
# ---------------------------------------------------------------------------
def _prepare(scan: Path, max_side: int):
    """``(luminance, saturation, scale)`` of the reduced picture, or None."""
    import numpy as np
    from PIL import Image, ImageFilter
    try:
        img = Image.open(scan)
        img.load()
    except Exception:      # noqa: BLE001 -- an unreadable scan is not an answer
        return None
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if not w or not h:
        return None
    scale = min(1.0, max_side / float(max(w, h)))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                         Image.Resampling.BILINEAR)
    # A median filter, not a blur: speckle in a scan is impulsive, and a blur
    # spreads one bright fleck into a patch of "paper" that the sheet step then
    # believes.
    img = img.filter(ImageFilter.MedianFilter(3))
    arr = np.asarray(img).astype(np.float32)
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    sat = (mx - mn) / np.maximum(mx, 1.0)
    lum = arr.mean(axis=2)
    return lum, sat, scale


def _sheet_mask(lum, sat, inside):
    """The sheet: the largest bright, barely coloured region inside *inside*.

    PAPER FIRST, THEN INK, and this is the order that matters. Taking the
    largest blob of "not paper" straight out of the picture is right on a clean
    scanner bed and catastrophic on a dark one, where the BED is then the
    largest thing that is not paper: the prototype proposed the whole picture
    and scored 0.00 in 8 of 10 cluttered cases. A chart is ink on a sheet, and
    the sheet is the thing with the strong edge against everything else.
    """
    import numpy as np
    bright = float(np.percentile(lum[inside], 97)) if inside.any() else 0.0
    paperish = inside & (lum > bright * 0.80) & (sat < 0.12)
    if not paperish.any():
        return inside, False
    labels, sizes = _components(paperish)
    sizes = sizes.copy()
    sizes[0] = 0
    if not sizes.any():
        return inside, False
    big = int(sizes.argmax())
    ys, xs = np.nonzero(labels == big)
    if xs.size < 50:
        return inside, False
    box = np.zeros(lum.shape, bool)
    box[ys.min():ys.max() + 1, xs.min():xs.max() + 1] = True
    return inside & box, True


def _ink_mask(lum, sat, inside, darkness: float, colour: float):
    """Ink is anything inside the sheet that is darker than the paper or
    coloured. Both halves are needed: a saturated yellow patch is no darker
    than the paper it sits on, and a neutral grey patch has no colour at all."""
    import numpy as np
    neutral = inside & (sat < 0.08)
    if neutral.any():
        paper = float(np.percentile(lum[neutral], 92))
    elif inside.any():
        paper = float(np.percentile(lum[inside], 92))
    else:
        return np.zeros(lum.shape, bool)
    return inside & ((lum < paper * darkness) | (sat > colour))


def _extreme_points(mask):
    """Points that contain the convex hull of *mask*: the first and last set
    pixel of every row and of every column. At most ``2*(w+h)`` of them, where
    the mask itself can hold half a million -- and the hull of the subset is
    the hull of the whole, because every hull vertex is extreme in its own row
    or its own column."""
    import numpy as np
    h, w = mask.shape
    pts = []
    rows = mask.any(axis=1)
    if rows.any():
        first = mask.argmax(axis=1)
        last = w - 1 - mask[:, ::-1].argmax(axis=1)
        ys = np.nonzero(rows)[0]
        pts.append(np.stack([first[ys], ys], axis=1))
        pts.append(np.stack([last[ys], ys], axis=1))
    cols = mask.any(axis=0)
    if cols.any():
        firsty = mask.argmax(axis=0)
        lasty = h - 1 - mask[::-1, :].argmax(axis=0)
        xs = np.nonzero(cols)[0]
        pts.append(np.stack([xs, firsty[xs]], axis=1))
        pts.append(np.stack([xs, lasty[xs]], axis=1))
    if not pts:
        return []
    allpts = np.concatenate(pts, axis=0)
    return [(float(a), float(b)) for a, b in allpts]


def _profile_trimmed(mask, quad, keep: float):
    """The quad again, trimmed to where the ink is DENSE along each axis.

    The block's own axes come from *quad*, so this needs no second guess about
    rotation. Projected onto them, a row of patches makes a tall plateau and a
    line of strip labels makes a low ripple, so the longest run of bins holding
    at least *keep* of the plateau's height is the block and everything outside
    it is furniture. This is the route that survives a chart whose block is not
    one connected component, and the one that trims a notes band off a chart
    whose block is.
    """
    import numpy as np
    ys, xs = np.nonzero(mask)
    if xs.size < 64:
        return None
    ex, ey = quad[1][0] - quad[0][0], quad[1][1] - quad[0][1]
    length = math.hypot(ex, ey)
    if length < 1e-9:
        return None
    ux, uy = ex / length, ey / length
    vx, vy = -uy, ux
    u = xs * ux + ys * uy
    v = xs * vx + ys * vy
    span = []
    for coord in (u, v):
        lo, hi = float(coord.min()), float(coord.max())
        if hi - lo < 4:
            return None
        bins = max(16, min(240, int(hi - lo)))
        hist, edges = np.histogram(coord, bins=bins, range=(lo, hi))
        plateau = float(np.percentile(hist, 75))
        if plateau <= 0:
            return None
        over = hist >= keep * plateau
        best = cur = best_end = 0
        for i, flag in enumerate(over):
            if flag:
                cur += 1
                if cur > best:
                    best, best_end = cur, i
            else:
                cur = 0
        if best == 0:
            return None
        span.append((float(edges[best_end - best + 1]), float(edges[best_end + 1])))
    (u0, u1), (v0, v1) = span
    corners = [(cu * ux + cv * vx, cu * uy + cv * vy)
               for cu, cv in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
    return _wound_like_the_chart(corners)


def block_candidates(scan: Path,
                     image_size: tuple[int, int],
                     search_region: "tuple[float, float, float, float] | None" = None,
                     max_side: int = WORK_MAX_SIDE,
                     ) -> list[tuple[str, list[tuple[float, float]]]]:
    """``(route name, quad)`` for every block this picture could be showing.

    Several routes, none of them trusted: see the module docstring. The quads
    come back in FULL-RESOLUTION image pixels, so a caller never has to know
    what the picture was reduced to.
    """
    import numpy as np
    prep = _prepare(Path(scan), max_side)
    if prep is None:
        return []
    lum, sat, scale = prep
    h, w = lum.shape
    # THE REGION IS A HINT AND NOT A FENCE, WHICH IS THE OPPOSITE OF WHAT IT IS
    # FOR SCANIN. `scan_placement.search_region_for` hands over any quad
    # covering less than 70 % of the sheet, and the window computes it from the
    # corners CURRENTLY on screen -- which, on a scan just loaded, are the
    # app's own opening rectangle, sized to the patch block's aspect and
    # centred. On a part-full last page that rectangle is tall and narrow and
    # sits in the middle of the sheet, so it cuts the real block in half:
    # measured on page 2 of the CR30 chart, searching only inside it ended
    # 337 px out and was refused, while searching the whole picture ended
    # 2.6 px out. A second search is cheap and a wrong answer here costs
    # nothing (it simply scores badly and loses), so both are searched and the
    # agreement decides.
    zones: list[tuple[str, "np.ndarray"]] = []
    if search_region is not None:
        x0, y0, x1, y1 = [c * scale for c in search_region]
        mask = np.zeros((h, w), bool)
        mask[max(0, int(y0)):min(h, int(y1) + 1),
             max(0, int(x0)):min(w, int(x1) + 1)] = True
        if mask.any():
            zones.append(("region", mask))
    zones.append(("frame", np.ones((h, w), bool)))

    out: list[tuple[str, list[tuple[float, float]]]] = []
    seen: list[list[tuple[float, float]]] = []
    up = 1.0 / scale if scale else 1.0

    def offer(name: str, quad) -> None:
        if quad is None:
            return
        full = [(x * up, y * up) for x, y in quad]
        if not _plausible(full, image_size):
            return
        for old in seen:
            if all(math.hypot(a[0] - b[0], a[1] - b[1]) < 3.0
                   for a, b in zip(old, full)):
                return
        seen.append(full)
        out.append((name, full))

    regions: list[tuple[str, "np.ndarray"]] = []
    for zone, zmask in zones:
        sheet, found_sheet = _sheet_mask(lum, sat, zmask)
        regions.append((f"{zone}-sheet", sheet))
        if found_sheet:
            # the sheet step can be the thing that goes wrong (a chart printed
            # edge to edge has no paper margin to find), so the unrestricted
            # zone is kept as a candidate route of its own
            regions.append((zone, zmask))

    for tag, region in regions:
        for darkness, colour, dtag in ((0.93, 0.16, ""), (0.88, 0.22, "-hard")):
            ink = _ink_mask(lum, sat, region, darkness, colour)
            if not ink.any():
                continue
            labels, sizes = _components(ink)
            sizes = sizes.copy()
            sizes[0] = 0
            if not sizes.any():
                continue
            big = int(sizes.argmax())
            biggest = labels == big
            whole = min_area_quad(_extreme_points(biggest))
            offer(f"{tag}{dtag}-largest-blob", whole)
            # every blob worth a tenth of the biggest, merged: a block split by
            # wide spacer gaps, or a honeycomb whose columns do not touch
            keep_ids = np.nonzero(sizes >= 0.10 * sizes[big])[0]
            merged = np.isin(labels, keep_ids) & ink
            offer(f"{tag}{dtag}-merged-blobs",
                  min_area_quad(_extreme_points(merged)))
            if whole is not None:
                small_quad = [(x / up, y / up) for x, y in whole]
                offer(f"{tag}{dtag}-profile-half",
                      _profile_trimmed(ink, small_quad, 0.50))
                offer(f"{tag}{dtag}-profile-quarter",
                      _profile_trimmed(ink, small_quad, 0.25))
    if search_region is not None:
        x0, y0, x1, y1 = search_region
        offer("the-region-you-drew",
              _wound_like_the_chart([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
    return out


# ---------------------------------------------------------------------------
# the answer
# ---------------------------------------------------------------------------
def find_block(scan: Path,
               boxes: Sequence,
               expected_y: dict,
               image_size: tuple[int, int],
               current_corners: "Sequence[tuple[float, float]] | None" = None,
               sample_frac: float = SEARCH_SAMPLE_AREA,
               search_region: "tuple[float, float, float, float] | None" = None,
               max_side: int = WORK_MAX_SIDE,
               ) -> HexBlockResult:
    """Where the chart is: the colours say which quad holds the chart, and the
    patches say which placement of it is seated.

    Each route's quad is scored the four ways the chart can sit inside it, with
    :func:`workflow.scan_auto_align.reference_agreement_at` -- the same number
    the window quotes and the same number the ladder's floor is set against, so
    a proposal is chosen by the measure that will later judge it rather than by
    an opinion of this module's own.

    That measure saturates, though, and on a honeycomb it saturates on quads
    that are visibly different (see :data:`AGREEMENT_TIE_BAND`), so candidates
    within a hair of the best are separated by
    :func:`~workflow.scan_auto_align.seating_drift` instead -- the ladder's
    other measure, and the one that asks the patches rather than the colours.
    The colours keep the veto: nothing outside the band can win, so a quad that
    reads as a different chart is never reached by the tie-break.

    *sample_frac* is a FIXED share of each patch (:data:`SEARCH_SAMPLE_AREA`)
    and not the user's Sample area; the ladder does not pass its own.

    *current_corners* are passed only when somebody actually placed them. A
    proposal that does not beat them by
    :data:`~workflow.scan_auto_align.IMPROVEMENT_MARGIN` is dropped, and the
    ladder then refines the user's own corners exactly as it does today.
    """
    from workflow.scan_auto_align import (IMPROVEMENT_MARGIN, agreement_scorer,
                                          drift_sampler, seating_drift)

    res = HexBlockResult()
    cands = block_candidates(scan, image_size, search_region, max_side)
    res.candidates = len(cands)
    if not cands:
        res.reason = "no-ink-found"
        return res
    score = agreement_scorer(scan, expected_y)
    if score is None:
        res.reason = "picture-not-readable"
        return res

    if current_corners:
        before = [tuple(p) for p in current_corners]
        res.rho_before = score(boxes, before, sample_frac)

    # EVERY ROUTE BOUNDS THE INK, AND THE MARQUEE IS DEFINED ON THE SLOTS.
    # On a honeycomb those differ by the apexes' overhang, which is known from
    # the chart's own boxes (:func:`apex_factors`), so each route is offered
    # twice: as it came, and corrected. Neither is trusted -- both are scored,
    # and the seating below picks. The correction is applied to each TURN, in
    # that turn's own frame, because which axis the apexes point along is part
    # of which way up the chart is.
    fu, fv = apex_factors(boxes)
    corrected = (abs(fu - 1.0) > 1e-6 or abs(fv - 1.0) > 1e-6)

    best = None
    scored: list[tuple[float, str, list[tuple[float, float]]]] = []
    for name, quad in cands:
        variants = [(name, False)]
        if corrected:
            variants.append((f"{name}+apex", True))
        for tag, fix in variants:
            mine = None
            for k in range(4):
                turned = quad[k:] + quad[:k]
                if fix:
                    turned = scaled_about_centre(turned, fu, fv)
                rho = score(boxes, turned, sample_frac)
                if rho is None:
                    continue
                if mine is None or rho > mine[0]:
                    mine = (rho, tag, turned)
            if mine is None:
                continue
            scored.append(mine)
            if best is None or mine[0] > best[0]:
                best = mine
            res.scores.append((tag, round(mine[0], 4)))
    if best is None:
        res.reason = "nothing-scoreable"
        return res

    # THE COLOURS SAY WHICH QUAD, THE PATCHES SAY WHICH PLACEMENT.
    # Everything still inside the band agrees with this chart as well as the
    # winner does, so the choice between them is not a colour question any
    # more; `seating_drift` is asked instead. A drift that cannot be measured
    # is no evidence either way and leaves the candidate where the agreement
    # put it, which is what the module did before this existed.
    band = sorted((c for c in scored if c[0] >= best[0] - AGREEMENT_TIE_BAND),
                  key=lambda c: -c[0])[:MAX_SEATED]
    if len(band) > 1:
        graded = []
        # ONE READ OF THE PICTURE FOR ALL OF THEM. The seating depends on the
        # corners; what it reads out of the scan first does not.
        sampler = drift_sampler(scan)
        for rho, name, quad in band:
            try:
                drift = seating_drift(scan, boxes, quad, sampler=sampler)
            except Exception:      # noqa: BLE001 -- a tie-break may not crash
                log.warning("could not measure the seating of route %s", name,
                            exc_info=True)
                drift = None
            graded.append((drift, rho, name, quad))
            log.debug("hex block search: %s rho %.4f drift %s", name, rho,
                      "none" if drift is None else format(drift, ".4f"))
        seated = [g for g in graded if g[0] is not None]
        if seated:
            drift, rho, name, quad = min(seated, key=lambda g: (g[0], -g[1]))
            best = (rho, name, quad)
            res.drift = drift

    rho, name, quad = best
    if res.rho_before is not None and rho < res.rho_before + IMPROVEMENT_MARGIN:
        res.reason = "no-better"
        res.rho = rho
        res.route = name
        return res
    res.corners = quad
    res.rho = rho
    res.route = name
    log.info("hex block search: %d quads, best %s at %.3f%s", len(cands), name,
             rho, "" if res.drift is None else f" (drift {res.drift:.4f})")
    return res
