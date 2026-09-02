"""Interactive four-corner marquee over a scanned chart, with a live grid overlay
(#98).

The user drags four corner handles onto the printed patch area of the scan; a
grid of the chart's real patch boxes — perspective-mapped into that quad — is
drawn on top so they can *see* the alignment before running ``scanin``. On
confirm the four corners (image pixels, order **TL, TR, BR, BL**) become
``scanin -F``.

Coordinate note: the chart geometry is bottom-left millimetres, the image is
top-left pixels, so the grid mapping flips ``v`` (a patch at the chart *top*,
``ymax``, maps to the *top* of the quad).

The homography (unit square → the user's quad) is a pure function
(:func:`unit_quad_homography`) so it's unit-tested without Qt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QTransform
from PyQt6.QtWidgets import QWidget

from ui import neutral_styles


def unit_quad_homography(quad: list[tuple[float, float]]) -> np.ndarray:
    """3×3 homography mapping the unit square corners ``(0,0),(1,0),(1,1),(0,1)``
    (i.e. TL, TR, BR, BL in u-right/v-down coords) onto *quad* (four (x, y)).
    Exact for four points (DLT); normalised so ``H[2,2] == 1``."""
    src = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float)
    dst = np.array(quad, float)
    A = []
    for (u, v), (x, y) in zip(src, dst):
        A.append([u, v, 1, 0, 0, 0, -u * x, -v * x, -x])
        A.append([0, 0, 0, u, v, 1, -u * y, -v * y, -y])
    _, _, vt = np.linalg.svd(np.array(A))
    h = vt[-1].reshape(3, 3)
    return h / h[2, 2]


def apply_h(h: np.ndarray, u: float, v: float) -> tuple[float, float]:
    """Map a unit-square point ``(u, v)`` through homography *h* to pixels."""
    p = h @ np.array([u, v, 1.0])
    return float(p[0] / p[2]), float(p[1] / p[2])


def rectarg_edges(total_px: float, n: int) -> list[float]:
    """rectarg's integer-pixel column/row edges, normalised to [0,1]: each cell is
    ``floor(total/n)`` px, the leftover pixels going to the FIRST cells. Shared by
    the on-screen grid AND the scanin ``.cht`` so both line up exactly with a
    rectarg-rendered image (whose cells aren't perfectly uniform at low dpi)."""
    import math
    base = int(math.floor(total_px / n))
    rem = int(round(total_px - base * n))
    edges = [0.0]
    for i in range(n):
        edges.append(edges[-1] + base + (1 if i < rem else 0))
    tot = edges[-1] or 1.0
    return [e / tot for e in edges]


_FLINE = re.compile(r"(?m)^\s*F\s+_\s+_\s+" + r"\s+".join([r"([-\d.]+)"] * 8))


def fiducial_frame(text: str) -> tuple[float, float, float, float] | None:
    """The registration-mark frame ``(x0, x1, y0, y1)`` = (left, right, top,
    bottom) from the ``.cht``'s real ``F`` line — the four fiducial marks
    (``F _ _ x0 y0 x1 y1 x2 y2 x3 y3``, clockwise from top-left). None if absent.
    This is the box the marquee handles sit on in *fiducial* mode; scanin ``-F``
    maps its four corners to these coordinates."""
    m = _FLINE.search(text)
    if not m:
        return None
    v = [float(g) for g in m.groups()]
    xs, ys = v[0::2], v[1::2]
    return min(xs), max(xs), min(ys), max(ys)


def extrapolate_to_fiducials(
        corners: list[tuple[float, float]], text: str
) -> list[tuple[float, float]] | None:
    """Map a **patch-grid-aligned** marquee quad (four image-pixel corners, order
    TL, TR, BR, BL) out to the ``.cht``'s **fiducial frame**, so scanin ``-F``
    (whose ``.cht`` ``F`` line is the fiducials) receives corners on the marks —
    *derived* from the reliable patch alignment rather than placed by hand on
    marks the display image may not even show. Returns None if the file has no
    distinct fiducials or can't be parsed. This is what makes "Use fiducial marks"
    ON as reliable as OFF: one patch alignment, two consistent ``-F`` derivations."""
    if len(corners) != 4:
        return None
    fr = fiducial_frame(text)
    if fr is None:
        return None
    from workflow.cht_parser import ChtParseError, parse_cht
    try:
        geom = parse_cht(text)
    except ChtParseError:
        return None
    if not geom.patches:
        return None
    xs = [b.x1 for b in geom.patches] + [b.x2 for b in geom.patches]
    ys = [b.y1 for b in geom.patches] + [b.y2 for b in geom.patches]
    px0, px1, py0, py1 = min(xs), max(xs), min(ys), max(ys)
    fx0, fx1, fy0, fy1 = fr                       # left, right, top, bottom
    if px1 == px0 or py1 == py0:
        return None
    h = unit_quad_homography(corners)             # unit square (patch bbox) → quad
    def img(fx: float, fy: float) -> tuple[float, float]:
        return apply_h(h, (fx - px0) / (px1 - px0), (fy - py0) / (py1 - py0))
    return [img(fx0, fy0), img(fx1, fy0), img(fx1, fy1), img(fx0, fy1)]


def rectarg_align_cht(text: str, wpx: float, hpx: float) -> str:
    """Reposition a per-patch ``.cht`` so each box sits on rectarg's **integer-pixel
    edges** for a patch area of *wpx*×*hpx* pixels — the SAME edges the on-screen
    grid draws. This lines the interior columns/rows up with a rounded rectarg
    image (whose inner cells aren't evenly spaced) instead of drifting between the
    pinned corners. Returns the text unchanged if the boxes aren't a uniform
    (gaps-allowed) grid or the file can't be parsed. XLIST/YLIST are regenerated
    to match. Shared by scanin so the diagnostic matches the marquee exactly."""
    from workflow.cht_parser import ChtParseError, parse_cht
    try:
        boxes = parse_cht(text).patches
    except ChtParseError:
        return text
    if not boxes or wpx <= 0 or hpx <= 0:
        return text
    def gx(b): return round(b.x1, 2)
    def gy(b): return round(b.y1, 2)
    xl = sorted({gx(b) for b in boxes}); yt = sorted({gy(b) for b in boxes})
    nc, nr = len(xl), len(yt)
    if nc < 2 or nr < 2 or wpx < nc or hpx < nr:    # too small to round meaningfully
        return text
    xs = [b.x1 for b in boxes] + [b.x2 for b in boxes]
    ys = [b.y1 for b in boxes] + [b.y2 for b in boxes]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sw, sh = (x1 - x0) or 1.0, (y1 - y0) or 1.0
    dxs = [xl[i + 1] - xl[i] for i in range(nc - 1)]
    dys = [yt[i + 1] - yt[i] for i in range(nr - 1)]
    # Same pitch-relative uniformity rule as GridSpec._grid_structure (#108):
    # non-uniform charts (printtarg's wider first column) keep their true boxes.
    if (max(dxs) - min(dxs) > 0.1 * min(dxs)
            or max(dys) - min(dys) > 0.1 * min(dys)):
        return text                                # not a uniform grid
    bws = sorted({round(b.x2 - b.x1, 2) for b in boxes})
    bhs = sorted({round(b.y2 - b.y1, 2) for b in boxes})
    if bws[-1] - bws[0] > 0.05 * bws[-1] or bhs[-1] - bhs[0] > 0.05 * bhs[-1]:
        return text
    xi = {v: i for i, v in enumerate(xl)}; yi = {v: i for i, v in enumerate(yt)}
    ue, ve = rectarg_edges(wpx, nc), rectarg_edges(hpx, nr)
    newpos = {}
    xset, yset = set(), set()
    for b in boxes:
        ci, ri = xi[gx(b)], yi[gy(b)]
        nx, nx2 = x0 + ue[ci] * sw, x0 + ue[ci + 1] * sw
        ny, ny2 = y0 + ve[ri] * sh, y0 + ve[ri + 1] * sh
        newpos[b.name] = (nx, ny, nx2 - nx, ny2 - ny)
        xset |= {round(nx, 3), round(nx2, 3)}; yset |= {round(ny, 3), round(ny2, 3)}
    out, i, lines = [], 0, text.splitlines()
    while i < len(lines):
        p = lines[i].split()
        if p[:1] in (["XLIST"], ["YLIST"]):        # drop old lists (regenerate below)
            i += 1
            while i < len(lines) and lines[i].split() and lines[i].split()[0][:1] in "0123456789-.":
                i += 1
            continue
        if p[:1] == ["X"] and len(p) >= 11 and p[1] in newpos:
            nx, ny, w, hh = newpos[p[1]]
            out.append(f"  X {p[1]} {p[2]} {p[3]} {p[4]} {w:g} {hh:g} {nx:g} {ny:g} 0 0")
        else:
            out.append(lines[i])
        i += 1
    out.append(f"XLIST {len(xset)}"); out += [f"  {x:g} {sh:g} 1.0" for x in sorted(xset)]
    out.append(f"YLIST {len(yset)}"); out += [f"  {y:g} {sw:g} 1.0" for y in sorted(yset)]
    out.append("")
    return "\n".join(out)


def cht_has_fiducials(text: str) -> bool:
    """True if the ``.cht``'s fiducial (``F``) frame is distinct from the patch
    block, so framing by fiducials differs from framing by the patches."""
    fr = fiducial_frame(text)
    if fr is None:
        return False
    from workflow.cht_parser import ChtParseError, parse_cht
    try:
        geom = parse_cht(text)
    except ChtParseError:
        return False
    if not geom.patches:
        return False
    xs = [b.x1 for b in geom.patches] + [b.x2 for b in geom.patches]
    ys = [b.y1 for b in geom.patches] + [b.y2 for b in geom.patches]
    px0, px1, py0, py1 = min(xs), max(xs), min(ys), max(ys)
    span = max(px1 - px0, py1 - py0) or 1.0
    diff = abs(fr[0] - px0) + abs(fr[1] - px1) + abs(fr[2] - py0) + abs(fr[3] - py1)
    return diff > 0.02 * span


@dataclass
class GridSpec:
    """Normalised patch rectangles for the overlay, derived from the chart's
    exact geometry. Each rect is ``(u, v, w, h)`` in [0,1] with a **top-left**
    origin (the chart's bottom-left mm already flipped), so it maps straight
    through the quad homography. *aspect* is the patch block's width/height, so
    the marquee can seed a starting quad of the right shape."""
    rects: list[tuple[float, float, float, float]]
    aspect: float = 1.0
    ncols: int = 0        # set when the boxes sit on a uniformly-spaced grid (gaps
    nrows: int = 0        # allowed) → the overlay replicates rectarg's integer edges
    cells: list[tuple[int, int]] | None = None
    hexagonal: bool = False
    # ^ True for a SpectroScan hexagonal chart: the CELLS are drawn as the
    # patch's true shape so the user can see the mesh sitting on the hexagons.
    # The SAMPLED area stays rectangular — that is what a CHT carries and what
    # scanin reads. It does NOT fit inside the hexagon at every size: the
    # slanted sides cut the rectangle's corners off, so the dialog caps Sample
    # area from these proportions (scanin_runner.hex_max_sample_fraction).
    exact_rects: bool = False
    # ^ True when the rects ARE the render's pixel truth (engine charts):
    #   the rectarg integer-edge rebuild must not touch them — rectarg
    #   distributes fractional pitch differently and the drawn cells drift
    #   off the patches mid-chart (Basti, #108 showcase session).
    # ^ per-patch (col, row) index into the ncols×nrows grid, parallel to ``rects``.
    #   Set whenever the grid is uniformly spaced — including GAPPED grids like
    #   Hutchcolor (528 of a 29×22 grid) — so the interior columns/rows can be
    #   placed on rectarg's exact integer edges instead of drifting off a
    #   rounded image between the (pinned) corners.
    fiducial_rect: tuple[float, float, float, float] | None = None
    # ^ the .cht fiducial frame (u0, v0, u1, v1) in the SAME patch-bbox-normalised
    #   space as ``rects`` (so it maps through the same quad homography); extends
    #   outside [0,1] since fiducials sit around the patches. One geometry drives
    #   the grid, the on-screen fiducial frame, and the scanin -F derivation.
    ink_rect: tuple[float, float, float, float] | None = None
    # ^ engine charts (#119, Knut): the printed ink block extends one spacer
    #   strip beyond the patch grid on sides that have spacers, so a user
    #   naturally frames the WRONG boundary. This is that ink boundary
    #   (u0, v0, u1, v1) in the same normalised space, derived from the patch
    #   gaps themselves — any spacer size, or absent (None) when there are no
    #   gaps. Drawn as a dashed guide so "corners on the patches, spacers
    #   outside" is visible instead of guessed.

    @staticmethod
    def _grid_structure(patches, sw, sh):
        """(ncols, nrows, cells) if the boxes sit on a uniformly-spaced grid —
        **gaps allowed** (Hutchcolor is 528 of a 29×22 grid) — where *cells* is the
        per-patch ``(col, row)`` index; else ``(0, 0, None)``. Uniform spacing +
        indices let the overlay place the interior on rectarg's integer edges even
        when the grid isn't full, so it lines up with a rounded rectarg image."""
        def gx(p): return round(p.x1 if hasattr(p, "x1") else p["x"], 2)
        def gy(p): return round(p.y1 if hasattr(p, "y1") else p["y"], 2)
        xl = sorted({gx(p) for p in patches})
        yt = sorted({gy(p) for p in patches})
        nc, nr = len(xl), len(yt)
        if nc < 2 or nr < 2:
            return 0, 0, None
        dxs = [xl[i + 1] - xl[i] for i in range(nc - 1)]
        dys = [yt[i + 1] - yt[i] for i in range(nr - 1)]
        # Tolerance relative to the PITCH, not the whole span — a 2%-of-span
        # test waved through printtarg's wider first column (10.5 vs 7 mm on a
        # 262 mm chart), forcing 962 boxes onto equal cells (#108).
        if (max(dxs) - min(dxs) > 0.1 * min(dxs)
                or max(dys) - min(dys) > 0.1 * min(dys)):
            return 0, 0, None          # not uniform (e.g. a whole column missing)
        # Equal cells also require equal BOX sizes (#108).
        def gw(p): return round((p.x2 - p.x1) if hasattr(p, "x1") else p["w"], 2)
        def gh(p): return round((p.y2 - p.y1) if hasattr(p, "y1") else p["h"], 2)
        ws = sorted({gw(p) for p in patches})
        hs = sorted({gh(p) for p in patches})
        if ws[-1] - ws[0] > 0.05 * ws[-1] or hs[-1] - hs[0] > 0.05 * hs[-1]:
            return 0, 0, None
        xi = {v: i for i, v in enumerate(xl)}
        yi = {v: i for i, v in enumerate(yt)}
        return nc, nr, [(xi[gx(p)], yi[gy(p)]) for p in patches]

    @classmethod
    def from_patches(cls, patches: list[dict], hexagonal: bool = False) -> "GridSpec":
        """Build from engine ``channels.json["layout"]["patches"]`` (top-left px).
        Uses the patch-area bounding box to normalise; page filtering is the
        caller's job (pass one page's patches).

        *hexagonal* only changes how the cells are DRAWN — the rects, and so the
        sampled area, are identical either way."""
        if not patches:
            return cls([])
        xs = [p["x"] for p in patches] + [p["x"] + p["w"] for p in patches]
        ys = [p["y"] for p in patches] + [p["y"] + p["h"] for p in patches]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        sw, sh = (x1 - x0) or 1.0, (y1 - y0) or 1.0
        rects = [((p["x"] - x0) / sw, (p["y"] - y0) / sh, p["w"] / sw, p["h"] / sh)
                 for p in patches]
        nc, nr, cells = cls._grid_structure(patches, sw, sh)
        # The printed ink block extends one spacer strip beyond the patch
        # grid wherever the chart HAS spacers (#119, Knut) — and the spacer
        # is exactly the gap the patches keep between themselves, so it can
        # be read off the patch data for any spacer size, or skipped when
        # the chart has none.
        def _gap(lo_key: str, size_key: str) -> float:
            edges = sorted({round(p[lo_key], 2) for p in patches})
            gaps = []
            for a, b in zip(edges, edges[1:]):
                span = min(p[size_key] for p in patches
                           if round(p[lo_key], 2) == a)
                g = b - a - span
                if g > 0.5:                      # a real printed spacer
                    gaps.append(g)
            return sorted(gaps)[len(gaps) // 2] if gaps else 0.0

        def _gap_within_columns(lo_key: str, size_key: str, other_key: str) -> float:
            """The spacer along *lo_key* measured WITHIN each line of constant
            *other_key* (e.g. within a column, for the row spacer). Robust to a
            staggered chart: ColorMunki "offset every second column" interleaves
            the global y-edges at half-pitch, so the edge-to-edge :func:`_gap`
            sees no gap and the top/bottom spacer guide vanished (Knut). Grouping
            by column first restores the true row spacer."""
            lines: dict[float, list] = {}
            for p in patches:
                lines.setdefault(round(p[other_key], 1), []).append(p)
            gaps = []
            for grp in lines.values():
                grp.sort(key=lambda p: p[lo_key])
                for a, b in zip(grp, grp[1:]):
                    g = b[lo_key] - (a[lo_key] + a[size_key])
                    if g > 0.5:
                        gaps.append(g)
            return sorted(gaps)[len(gaps) // 2] if gaps else 0.0

        # Columns keep a regular x even on a vertically-staggered chart, so the
        # horizontal spacer is safe edge-to-edge; the vertical spacer must be read
        # per column so the stagger doesn't hide it (Knut).
        gx = _gap("x", "w")
        gy = _gap_within_columns("y", "h", "x") or _gap("y", "h")
        ink = ((-gx / sw, -gy / sh, 1.0 + gx / sw, 1.0 + gy / sh)
               if (gx or gy) else None)
        return cls(rects, aspect=sw / sh, ncols=nc, nrows=nr, cells=cells,
                   exact_rects=True, ink_rect=ink, hexagonal=hexagonal)

    @classmethod
    def from_cht(cls, text: str) -> "GridSpec":
        """Build from *any* Argyll ``.cht`` — the **one** geometry every standard
        target (bundled and "Other") goes through. Boxes are normalised into the
        **total patch-area bounding box** (the union of every patch box across all
        areas, e.g. an IT8's GS greyscale strip) — the reliable, always-visible
        reference the user aligns the four corners to. ``fiducial_rect`` carries
        the ``.cht``'s ``F``-line frame in the *same* normalised space, so the
        on-screen fiducial frame and the scanin ``-F`` derivation
        (:func:`extrapolate_to_fiducials`) share this single source of truth."""
        from workflow.cht_parser import ChtParseError, parse_cht
        try:
            geom = parse_cht(text)
        except ChtParseError:
            return cls([])
        if not geom.patches:
            return cls([])
        boxes = geom.patches
        xs = [b.x1 for b in boxes] + [b.x2 for b in boxes]
        ys = [b.y1 for b in boxes] + [b.y2 for b in boxes]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        sw, sh = (x1 - x0) or 1.0, (y1 - y0) or 1.0
        nc, nr, cells = cls._grid_structure(boxes, sw, sh)
        fr = fiducial_frame(text)                 # (left, right, top, bottom) cht units
        fid = (None if fr is None else
               ((fr[0] - x0) / sw, (fr[2] - y0) / sh,
                (fr[1] - x0) / sw, (fr[3] - y0) / sh))
        return cls([((b.x1 - x0) / sw, (b.y1 - y0) / sh,
                     (b.x2 - b.x1) / sw, (b.y2 - b.y1) / sh) for b in boxes],
                   aspect=sw / sh, ncols=nc, nrows=nr, cells=cells, fiducial_rect=fid)


_HANDLE_R = 8         # corner handle radius (screen px)
_HANDLE_OFFSET = 26   # handles sit this far OUTSIDE the true corner (screen px)
_HANDLE_DIRS = ((-1, -1), (1, -1), (1, 1), (-1, 1))   # TL, TR, BR, BL, outward
_SIDE_PAIRS = ((0, 1), (1, 2), (2, 3), (3, 0))   # top, right, bottom, left (corner idx)
_SIDE_R = 6           # mid-side handle radius (moves the whole edge, parallel)
#: The Measure green the marquee has always drawn its ants and handles in.
#: Kept as a module name because it *is* the light/dark value — see
#: :data:`_ACCENT_BY_MODE`, which is the thing to read.
_ACCENT = QColor("#56d6a5")

#: THE MARQUEE'S OWN COLOURS, PER APPEARANCE.
#:
#: Light and Dark keep the Measure green they always painted; Neutral takes the
#: handoff's single ``ACTION`` value, because a colourless theme has one accent
#: and the tab a window happens to belong to is not what a selection frame is
#: saying.
#:
#: **The under-stroke is not decoration.** Green over a printed chart separated
#: itself from the ink for free — no patch a printer lays down is that green. A
#: near-black ink has no such luck: over a solid black patch the ants would
#: vanish exactly where the user is trying to aim. So in Neutral every stroke is
#: drawn twice, the first pass 2 px wider in the surface value, and the ants
#: keep their edge over a patch of any density. Light and Dark have no
#: under-stroke, which is why this is a mapping and not a constant.
_ACCENT_BY_MODE = {
    "light":   QColor("#56d6a5"),
    "dark":    QColor("#56d6a5"),
    "neutral": QColor(neutral_styles.NM_ACTION),
}
_UNDER_BY_MODE = {
    "light":   None,
    "dark":    None,
    "neutral": QColor(neutral_styles.NM_BG_SURFACE),
}

#: The well the scan sits in. This widget IS the ground, so it carries the
#: viewer value itself rather than inheriting one.
#:
#: Neutral's is ``BG_PANEL`` — the panel grey, the owner's instruction for the
#: preview well applied here as well ("the same background colours as the light
#: grey used for the majority of the main window panel"). What makes this read
#: as a well is the scan's own edge against it, not a step down in value.
_BACKDROP_BY_MODE = {
    "light":   "#e8e8e8",
    "dark":    "#111",
    "neutral": neutral_styles.NM_BG_PANEL,
}
#: The "load a scan" line, on that backdrop. Dark ink on a light ground in
#: Neutral: nothing that works is allowed to be faint.
_EMPTY_TEXT_BY_MODE = {
    "light":   "#888",
    "dark":    "#888",
    "neutral": neutral_styles.NM_TEXT_DIM,
}


class ScanGridMarquee(QWidget):
    """Displays a scan fit-to-view with a draggable 4-corner quad + grid overlay."""

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(360, 300)
        self.setMouseTracking(True)
        self._img: QImage | None = None      # original, unrotated
        self._pix: QPixmap | None = None      # rotated, for display
        self._rotation = 0                    # 0/90/180/270, applied to _img
        self._img_w = self._img_h = 0         # dims of the (rotated) image
        self._grid = GridSpec([])
        self._show_fiducials = False # draw the .cht fiducial frame around the patches
        self._sample_frac = 0.5      # fraction of each patch AREA that scanin reads
        # Quad corners in IMAGE pixels, order TL, TR, BR, BL.
        self._corners: list[list[float]] = []
        self._drag = -1
        # View transform: image px → widget px is (fit_scale·zoom)·p + fit_off + pan.
        self._scale = 1.0                     # fit-to-view scale
        self._ox = self._oy = 0.0             # fit-to-view offset
        self._zoom = 1.0                      # user zoom on top of the fit (≥1)
        self._pan = [0.0, 0.0]                # user pan, widget px
        self._panning = False
        self._pan_ref: tuple[float, float, float, float] | None = None
        self._moving = False                  # dragging the whole grid to reposition
        self._move_ref: tuple | None = None
        self._side_drag = -1                  # dragging a mid-side handle (edge)
        self._side_ref: tuple | None = None
        self._allow_plain_wheel = False       # popped-out: plain wheel zooms too
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)   # for ⌘/Ctrl +/- zoom

    # ---------------------------------------------------------------- data
    def set_image(self, img: QImage) -> None:
        self._img = img
        self._rotation = 0
        self._rebuild_pixmap()
        self._reset_view()
        self._seed_corners()
        self.update()

    def reset_selection_grid(self) -> None:
        """Re-seed the quad from the chart geometry at the current image size — the
        "Reset Selection Grid" button. Recovers a placement that flew off-screen
        (e.g. after loading a different-resolution image)."""
        self._reset_view()
        self._seed_corners()
        self.update()

    def _seed_corners(self) -> None:
        """Starting quad: a centred rectangle matching the patch block's aspect
        ratio at ~90% of the image, so it's already the right shape to nudge onto
        the target — not a blind inset. Falls back to a plain inset when there's
        no grid to take an aspect from."""
        if not self._grid.rects or not self._img_w or not self._img_h:
            self._reset_corners()
            return
        iw, ih = float(self._img_w), float(self._img_h)
        ar = self._grid.aspect or (iw / ih)
        aw, ah = iw * 0.90, ih * 0.90
        if aw / ah > ar:
            h = ah; w = h * ar
        else:
            w = aw; h = w / ar
        cx, cy = iw / 2.0, ih / 2.0
        self._corners = [[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2],
                         [cx + w / 2, cy + h / 2], [cx - w / 2, cy + h / 2]]
        self.changed.emit()

    def _rebuild_pixmap(self) -> None:
        if self._img is None or self._img.isNull():
            self._pix = None
            self._img_w = self._img_h = 0
            return
        img = self._img
        if self._rotation:
            img = img.transformed(QTransform().rotate(self._rotation))
        self._pix = QPixmap.fromImage(img)
        self._img_w, self._img_h = img.width(), img.height()

    def _reset_view(self) -> None:
        """Back to fit-to-view (zoom 1, no pan)."""
        self._zoom = 1.0
        self._pan = [0.0, 0.0]
        self.update()

    def rotate_90(self) -> None:
        """Rotate the loaded scan 90° clockwise (for a sideways capture). Any
        placed corners rotate with it so the grid stays put."""
        if self._img is None:
            return
        h = self._img_h                                  # height before rotating
        self._corners = [[h - c[1], c[0]] for c in self._corners]
        self._rotation = (self._rotation + 90) % 360
        self._rebuild_pixmap()
        self._reset_view()
        self.changed.emit()
        self.update()

    def set_grid(self, grid: GridSpec) -> None:
        self._grid = grid
        if self._pix is not None:            # target changed with a scan loaded
            self._seed_corners()
        self.update()

    def set_show_fiducials(self, show: bool) -> None:
        """Show/hide the ``.cht`` fiducial frame drawn around the patch grid (the
        band the scanin ``-F`` extrapolates to when "Use fiducial marks" is on)."""
        self._show_fiducials = bool(show)
        self.update()

    def reframe(self, mL: float, mT: float, mR: float, mB: float,
                pw: float, ph: float, to_fiducial: bool) -> None:
        """Grow (or shrink) the quad by a fiducial band, keeping the patches on
        the same image spot. Margins ``mL/mT/mR/mB`` and patch size ``pw/ph`` are
        in .cht units. Going *to* fiducials, the current quad frames the patch
        area and the corners move OUT to the marks; coming back they move IN. Uses
        the quad homography, so it works on a skewed placement too."""
        if len(self._corners) != 4 or pw <= 0 or ph <= 0:
            return
        h = unit_quad_homography([(c[0], c[1]) for c in self._corners])
        if to_fiducial:                          # current quad = patch area → grow
            pts = [(-mL / pw, -mT / ph), (1 + mR / pw, -mT / ph),
                   (1 + mR / pw, 1 + mB / ph), (-mL / pw, 1 + mB / ph)]
        else:                                    # current quad = fiducials → shrink
            fw, fh = mL + pw + mR, mT + ph + mB
            a, b = mL / fw, (mL + pw) / fw
            c, d = mT / fh, (mT + ph) / fh
            pts = [(a, c), (b, c), (b, d), (a, d)]
        self._corners = [list(apply_h(h, u, v)) for u, v in pts]
        self.changed.emit()
        self.update()

    def set_sample_fraction(self, frac: float) -> None:
        """Fraction (0–1) of each patch's AREA that scanin samples — drawn as an
        inner rectangle inside every patch cell so the read zone is visible."""
        self._sample_frac = max(0.05, min(1.0, float(frac)))
        self.update()

    def set_wheel_zoom(self, on: bool) -> None:
        """When True (the popped-out window), a plain scroll wheel zooms;
        otherwise only Ctrl/Cmd+wheel zooms, so a plain wheel scrolls the dialog."""
        self._allow_plain_wheel = bool(on)

    def _reset_corners(self) -> None:
        """Seed the quad inset ~8% from the image edges (a sensible starting box
        the user nudges onto the patch area)."""
        w, h = self._img_w, self._img_h
        mx, my = w * 0.08, h * 0.08
        self._corners = [[mx, my], [w - mx, my], [w - mx, h - my], [mx, h - my]]
        self.changed.emit()

    def corners_image_px(self) -> list[tuple[float, float]]:
        """The four quad corners in image pixels (TL, TR, BR, BL) — feeds
        ``scanin -F``."""
        return [(c[0], c[1]) for c in self._corners]

    def image_size(self) -> tuple[int, int]:
        """(width, height) of the loaded (rotated) image, or (0, 0) if none —
        lets the dialog store a placement as fractions and restore it at any
        resolution."""
        return self._img_w, self._img_h

    def set_corners(self, corners: list[tuple[float, float]]) -> None:
        """Restore a saved placement (image px, TL/TR/BR/BL) — used to keep each
        page's quad when switching pages of a multi-page chart."""
        if corners and len(corners) == 4:
            self._corners = [[float(x), float(y)] for x, y in corners]
            self.update()

    def has_placement(self) -> bool:
        return bool(self._corners) and self._pix is not None

    # ---------------------------------------------------------------- view
    def _recompute_fit(self) -> None:
        if not self._img_w or not self._img_h:
            return
        aw, ah = self.width(), self.height()
        self._scale = min(aw / self._img_w, ah / self._img_h)
        self._ox = (aw - self._img_w * self._scale) / 2
        self._oy = (ah - self._img_h * self._scale) / 2

    def _to_widget(self, x: float, y: float) -> QPointF:
        s = self._scale * self._zoom
        return QPointF(self._ox + self._pan[0] + x * s, self._oy + self._pan[1] + y * s)

    def _to_image(self, x: float, y: float) -> tuple[float, float]:
        s = (self._scale * self._zoom) or 1.0
        return (x - self._ox - self._pan[0]) / s, (y - self._oy - self._pan[1]) / s

    # ---------------------------------------------------------------- paint
    def resizeEvent(self, e) -> None:  # noqa: N802
        self._recompute_fit()
        super().resizeEvent(e)

    def paintEvent(self, e) -> None:  # noqa: N802
        p = QPainter(self)
        mode = self._appearance()
        p.fillRect(self.rect(), QColor(_BACKDROP_BY_MODE[mode]))
        if self._pix is None:
            p.setPen(QColor(_EMPTY_TEXT_BY_MODE[mode]))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Load a scan of the printed chart")
            return
        self._recompute_fit()
        s = self._scale * self._zoom
        target = QRectF(self._ox + self._pan[0], self._oy + self._pan[1],
                        self._img_w * s, self._img_h * s)
        p.drawPixmap(target, self._pix, QRectF(self._pix.rect()))
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # THE UNDER-STROKE PASS. Same geometry, 2 px wider, in the surface
        # value, so the accent pass that follows keeps its edge over a patch of
        # any density. Only Neutral has one — see _UNDER_BY_MODE.
        under = _UNDER_BY_MODE[mode]
        if under is not None:
            self._ink_colour, self._ink_widen, self._ink_hollow = under, 2.0, True
            self._draw_grid(p)
            self._draw_quad(p)
        self._ink_colour, self._ink_widen, self._ink_hollow = (
            _ACCENT_BY_MODE[mode], 0.0, False)
        self._draw_grid(p)
        self._draw_quad(p)

    def _draw_grid(self, p: QPainter) -> None:
        if not self._grid.rects or len(self._corners) != 4:
            return
        h = unit_quad_homography(self._corners)
        # Knut's #119 equal-margin rule, the same maths scanin reads with
        # (workflow.scanin_runner.sample_margin): the sample box keeps the
        # SAME distance to the patch border on all four sides, its area is
        # exactly the chosen fraction, and each differently-shaped cell (a
        # Wolf Faust GS strip vs its square main grid) gets its own margin.
        # Computed per cell below; the aspect factor puts the normalised
        # u/v units on a common scale first.
        from workflow.scanin_runner import sample_margin
        asp = self._grid.aspect or 1.0
        outline = QPen(self._ink(90))             # full patch cell — faint
        outline.setWidthF(1.0 + self._ink_widen)
        sample = QPen(self._ink(220))             # sampled sub-area — solid
        sample.setWidthF(1.4 + self._ink_widen)
        fill = (Qt.BrushStyle.NoBrush if self._ink_hollow else self._ink(40))

        # Every chart draws its own float box rects (#119, Knut's CMP Studio
        # find): the old integer-edge rebuild placed interior cells for the
        # CORNER distance's pixel size, which matches an image only when the
        # corners are pixel-exact — and the demo scans are now painted on
        # the same float geometry the .cht carries, so the drawn grid, the
        # image and scanin agree without any rebuilding.
        cells = self._grid.rects

        for (u, v, w, hh) in cells:
            p.setPen(outline)
            p.setBrush(Qt.BrushStyle.NoBrush)
            if self._grid.hexagonal:
                # pointed top and bottom, flat vertical sides — the same shape
                # raster._hexagon_points draws, so the mesh reads as the chart
                t6 = hh / 6.0
                cxu = u + w / 2.0
                pts = ((cxu, v - t6), (u + w, v + t6), (u + w, v + hh - t6),
                       (cxu, v + hh + t6), (u, v + hh - t6), (u, v + t6))
            else:
                pts = ((u, v), (u + w, v), (u + w, v + hh), (u, v + hh))
            p.drawPolygon(*[self._to_widget(*apply_h(h, x, y)) for x, y in pts])
            mg = sample_margin(w * asp, hh, self._sample_frac)
            iu, iv = u + mg / asp, v + mg
            iw, ih = w - 2.0 * mg / asp, hh - 2.0 * mg
            p.setPen(sample)
            p.setBrush(fill)
            p.drawPolygon(*[self._to_widget(*apply_h(h, x, y)) for x, y in
                            ((iu, iv), (iu + iw, iv), (iu + iw, iv + ih), (iu, iv + ih))])
        p.setBrush(Qt.BrushStyle.NoBrush)

        # Ink-block guide (engine charts, #119): a dashed line one spacer
        # strip outside the patch grid, marking where the PRINTED block ends.
        # The corners belong on the patches — the spacer strips above/below
        # the outer rows stay outside the grid — and without this line users
        # framed the visible ink boundary instead (Knut).
        ir = self._grid.ink_rect
        if ir is not None:
            u0, v0, u1, v1 = ir
            ipen = QPen(self._ink(150))
            ipen.setWidthF(1.2 + self._ink_widen)
            ipen.setStyle(Qt.PenStyle.DotLine)
            p.setPen(ipen)
            p.drawPolygon(*[self._to_widget(*apply_h(h, x, y)) for x, y in
                            ((u0, v0), (u1, v0), (u1, v1), (u0, v1))])

        # Fiducial frame — the band the scanin -F extrapolates to when "Use
        # fiducial marks" is on. Drawn OUTSIDE the patch grid (its rect extends
        # past [0,1]) so the selection frame is visible while the corners stay on
        # the patches. Same homography as the grid → one geometry, one placement.
        fr = self._grid.fiducial_rect
        if self._show_fiducials and fr is not None:
            u0, v0, u1, v1 = fr
            fpen = QPen(self._ink(210))
            fpen.setWidthF(1.6 + self._ink_widen)
            fpen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(fpen)
            p.drawPolygon(*[self._to_widget(*apply_h(h, x, y)) for x, y in
                            ((u0, v0), (u1, v0), (u1, v1), (u0, v1))])

    def _handle_pos(self, i: int) -> QPointF:
        """The i-th grab handle, offset OUTSIDE the true corner along the diagonal
        so the big circle never hides the corner patch you're aiming at."""
        c = self._to_widget(*self._corners[i])
        dx, dy = _HANDLE_DIRS[i]
        return QPointF(c.x() + dx * _HANDLE_OFFSET, c.y() + dy * _HANDLE_OFFSET)

    def _side_handle_pos(self, i: int) -> QPointF:
        """Midpoint handle of side *i*, offset OUTWARD (perpendicular) — drag it to
        move that whole edge parallel, without touching two corners."""
        import math
        a, b = _SIDE_PAIRS[i]
        ca = self._to_widget(*self._corners[a]); cb = self._to_widget(*self._corners[b])
        mx, my = (ca.x() + cb.x()) / 2, (ca.y() + cb.y()) / 2
        ex, ey = cb.x() - ca.x(), cb.y() - ca.y()
        L = math.hypot(ex, ey) or 1.0
        px, py = -ey / L, ex / L                 # perpendicular
        cx = sum(self._to_widget(*c).x() for c in self._corners) / 4
        cy = sum(self._to_widget(*c).y() for c in self._corners) / 4
        if (mx + px - cx) ** 2 + (my + py - cy) ** 2 < (mx - px - cx) ** 2 + (my - py - cy) ** 2:
            px, py = -px, -py                    # point away from the centre
        return QPointF(mx + px * _HANDLE_OFFSET, my + py * _HANDLE_OFFSET)

    def _draw_quad(self, p: QPainter) -> None:
        if len(self._corners) != 4:
            return
        pen = QPen(self._ink(255))
        pen.setWidthF(2.0 + self._ink_widen)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        wc = [self._to_widget(*c) for c in self._corners]
        p.drawPolygon(*wc)
        conn = QPen(self._ink(255))
        conn.setStyle(Qt.PenStyle.DotLine)
        conn.setWidthF(1.2 + self._ink_widen)
        for i, c in enumerate(wc):
            hp = self._handle_pos(i)
            p.setPen(conn)                       # 45° dotted line to the corner
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(c, hp)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._ink(255))
            p.drawEllipse(hp, _HANDLE_R + self._ink_widen,
                          _HANDLE_R + self._ink_widen)
        for i in range(4):                       # mid-side handles (move an edge)
            a, b = _SIDE_PAIRS[i]
            mid = QPointF((wc[a].x() + wc[b].x()) / 2, (wc[a].y() + wc[b].y()) / 2)
            sp = self._side_handle_pos(i)
            p.setPen(conn)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(mid, sp)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._ink(255))
            p.drawEllipse(sp, _SIDE_R + self._ink_widen,
                          _SIDE_R + self._ink_widen)
        p.setBrush(Qt.BrushStyle.NoBrush)

    def _is_dark(self) -> bool:
        """Whether the scan well is being painted for a DARK ground.

        This widget IS the ground, so it asks the theme module from its own
        palette rather than measuring itself. Two answers, and two is all this
        one can give — kept because a caller that only needs "dark or not"
        should not have to know the appearance's name.
        """
        from ui.theme import is_dark
        return is_dark(self.palette())

    def _appearance(self) -> str:
        """WHICH appearance the well is being painted for, by name.

        The backdrop, the accent and the under-stroke are three-way choices
        (:data:`_BACKDROP_BY_MODE`, :data:`_ACCENT_BY_MODE`,
        :data:`_UNDER_BY_MODE`), and a light-grey third appearance answers
        :meth:`_is_dark` exactly as Light does. So this asks for the name, and
        a fourth appearance is a row in each table rather than an edit here.
        """
        from ui.theme import active_mode
        mode = active_mode(self.palette())
        return mode if mode in _BACKDROP_BY_MODE else "dark"

    # ------------------------------------------------------------------
    #: The colour and width the current pass paints with — set by
    #: :meth:`paintEvent` before each of the (at most two) passes over the
    #: overlay. ``_ink_hollow`` suppresses the translucent sample-area fill on
    #: the under-stroke pass: the under-stroke is there to give the ants an
    #: edge, not to lay a second veil over the user's patch.
    _ink_colour = _ACCENT
    _ink_widen = 0.0
    _ink_hollow = False

    def _ink(self, alpha: int) -> QColor:
        """The current pass's colour at *alpha*."""
        c = QColor(self._ink_colour)
        c.setAlpha(alpha)
        return c

    # ---------------------------------------------------------------- mouse
    def mousePressEvent(self, e) -> None:  # noqa: N802
        if self._pix is None:
            return
        pos = e.position()
        if e.button() == Qt.MouseButton.MiddleButton:   # middle drag always pans
            self._panning = True
            self._pan_ref = (pos.x(), pos.y(), self._pan[0], self._pan[1])
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        self._drag = -1
        self._side_drag = -1
        for i in range(len(self._corners)):
            if (self._handle_pos(i) - pos).manhattanLength() <= _HANDLE_R * 2.4:
                self._drag = i
                return
        if len(self._corners) == 4:              # mid-side handle → move that edge
            for i in range(4):
                if (self._side_handle_pos(i) - pos).manhattanLength() <= _SIDE_R * 2.8:
                    self._side_drag = i
                    ix, iy = self._to_image(pos.x(), pos.y())
                    self._side_ref = (ix, iy, [c[:] for c in self._corners])
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                    return
        if len(self._corners) == 4 and self._point_in_quad(pos):
            self._moving = True                  # inside the grid → move the whole grid
            ix, iy = self._to_image(pos.x(), pos.y())
            self._move_ref = (ix, iy, [c[:] for c in self._corners])
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:                                    # outside → pan the image
            self._panning = True
            self._pan_ref = (pos.x(), pos.y(), self._pan[0], self._pan[1])
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def _point_in_quad(self, pos) -> bool:
        pts = [self._to_widget(*c) for c in self._corners]
        inside = False
        n = len(pts)
        for i in range(n):
            xi, yi = pts[i].x(), pts[i].y()
            xj, yj = pts[i - 1].x(), pts[i - 1].y()
            if ((yi > pos.y()) != (yj > pos.y())) and \
               (pos.x() < (xj - xi) * (pos.y() - yi) / (yj - yi + 1e-9) + xi):
                inside = not inside
        return inside

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        pos = e.position()
        if self._drag >= 0:
            dx, dy = _HANDLE_DIRS[self._drag]    # handle is offset — move the corner
            x, y = self._to_image(pos.x() - dx * _HANDLE_OFFSET,
                                  pos.y() - dy * _HANDLE_OFFSET)
            x = max(0.0, min(self._img_w, x))
            y = max(0.0, min(self._img_h, y))
            self._corners[self._drag] = [x, y]
            self.changed.emit()
            self.update()
        elif self._side_drag >= 0 and self._side_ref is not None:
            ix, iy = self._to_image(pos.x(), pos.y())
            ox, oy, ref = self._side_ref
            dx, dy = ix - ox, iy - oy            # translate both corners of the edge
            a, b = _SIDE_PAIRS[self._side_drag]
            self._corners = [c[:] for c in ref]
            self._corners[a] = [ref[a][0] + dx, ref[a][1] + dy]
            self._corners[b] = [ref[b][0] + dx, ref[b][1] + dy]
            self.changed.emit()
            self.update()
        elif self._moving and self._move_ref is not None:
            ix, iy = self._to_image(pos.x(), pos.y())
            ox, oy, ref = self._move_ref
            dx, dy = ix - ox, iy - oy
            self._corners = [[c[0] + dx, c[1] + dy] for c in ref]
            self.changed.emit()
            self.update()
        elif self._panning and self._pan_ref is not None:
            sx, sy, px, py = self._pan_ref
            self._pan = [px + (pos.x() - sx), py + (pos.y() - sy)]
            self.update()

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        self._drag = -1
        self._side_drag = -1
        self._panning = False
        self._moving = False
        self.unsetCursor()

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.modifiers() & (Qt.KeyboardModifier.ControlModifier
                            | Qt.KeyboardModifier.MetaModifier):
            if e.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self._zoom_at_centre(1.25); return
            if e.key() in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
                self._zoom_at_centre(0.8); return
            if e.key() == Qt.Key.Key_0:
                self._reset_view(); return
        super().keyPressEvent(e)

    def _zoom_at_centre(self, factor: float) -> None:
        if self._pix is None:
            return
        cx, cy = self.width() / 2.0, self.height() / 2.0
        ix, iy = self._to_image(cx, cy)
        # Floor below the exact fit (0.9): on a borderless full-page scan the
        # corner handles sit outside the image and were unreachable at fit
        # zoom — Knut had to pan for every corner (#108).
        self._zoom = max(0.9, min(16.0, self._zoom * factor))
        if self._zoom <= 0.9 + 1e-9:
            self._pan = [0.0, 0.0]
        else:
            s = self._scale * self._zoom
            self._pan = [cx - self._ox - ix * s, cy - self._oy - iy * s]
        self.update()

    def mouseDoubleClickEvent(self, e) -> None:  # noqa: N802
        self._reset_view()                       # snap back to fit-to-view

    def wheelEvent(self, e) -> None:  # noqa: N802
        zoom_it = self._allow_plain_wheel or bool(
            e.modifiers() & (Qt.KeyboardModifier.ControlModifier
                             | Qt.KeyboardModifier.MetaModifier))
        if self._pix is None or not zoom_it:
            e.ignore()                       # plain wheel → let the dialog scroll
            return
        pos = e.position()
        ix, iy = self._to_image(pos.x(), pos.y())
        self._zoom = max(0.9, min(16.0, self._zoom * (1.0015 ** e.angleDelta().y())))
        if self._zoom <= 1.0:
            self._pan = [0.0, 0.0]               # fit → recentre
        else:                                    # keep point under cursor fixed
            s = self._scale * self._zoom
            self._pan = [pos.x() - self._ox - ix * s, pos.y() - self._oy - iy * s]
        self.update()
        e.accept()
