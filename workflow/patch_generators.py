"""Device-RGB patch-set generators for the chart layout editor.

Each generator returns a list of ``(R, G, B)`` device-value tuples on the
**0..100** scale — exactly the "device-value program" the editor mutates
(see :mod:`workflow.ti2_relayout`). They are pure: no Qt, no Argyll, no I/O,
so they unit-test cleanly and can be combined and spliced into a program in
any order.

The five generators back the New-chart dialog's "Generate colour sets" mode
(GitHub #37): an even RGB cube, Fitzpatrick skin-tone ramps, enhanced blues /
turquoise, enhanced foliage greens, and near-neutral greys.

A note on "device RGB": ChromIQ builds *unprofiled* test charts, so these are
printer device codes, not colorimetric targets. The skin / blue / green
palettes are sRGB-reasoned starting points chosen to concentrate patches where
the issue asks for denser coverage; they are deliberately easy to retune.
"""
from __future__ import annotations

import colorsys
import math


def _clamp(v: float) -> float:
    return 0.0 if v < 0.0 else 100.0 if v > 100.0 else v


def _hsv(h_deg: float, s: float, v: float) -> tuple[float, float, float]:
    """HSV (hue in degrees, s/v in 0..1) → device RGB on the 0..100 scale."""
    r, g, b = colorsys.hsv_to_rgb((h_deg % 360.0) / 360.0, s, v)
    return (r * 100.0, g * 100.0, b * 100.0)


# ---------------------------------------------------------------------------
# 1. Even RGB cube — N steps per axis ⇒ N**3 patches.
# ---------------------------------------------------------------------------
def rgb_cube(n: int) -> list[tuple[float, float, float]]:
    """An evenly spaced ``n`` × ``n`` × ``n`` device-RGB cube (``n**3`` patches).

    ``n`` is the number of steps **per axis** (the issue's "N×N"), so each of
    R/G/B is sampled at ``n`` evenly spaced levels from 0 to 100 inclusive.
    """
    n = max(2, int(n))
    levels = [i / (n - 1) * 100.0 for i in range(n)]
    return [(r, g, b) for r in levels for g in levels for b in levels]


def rgb_cube_count(n: int) -> int:
    return max(2, int(n)) ** 3


# ---------------------------------------------------------------------------
# 2. Fitzpatrick skin tones — 6 types × parallel hue ramps × a lightness sweep.
# ---------------------------------------------------------------------------
# Representative sRGB anchors (0..255) for the six Fitzpatrick skin phototypes,
# light (I) to dark (VI). Each type becomes one or more tonal ramps around its
# anchor so a group of patches spans the natural light→dark spread of that
# category. The light end is pulled paler (towards porcelain white) and the
# dark end is given a faint cool/blue undertone — both ranges the original
# single ramp missed (GitHub #37 follow-up).
_FITZPATRICK_ANCHORS = (
    (255, 224, 196),   # I   — very fair / pale white
    (241, 194, 167),   # II  — fair / white
    (224, 172, 138),   # III — medium / light brown
    (198, 134, 95),    # IV  — olive / moderate brown
    (141, 85, 56),     # V   — brown / dark brown
    (84, 56, 47),      # VI  — very dark brown (faintly cool/blue undertone)
)


# The skin locus is a warm CIELAB wedge: the Pantone SkinTone Guide's 110
# colours divide into a "yellow" and a "red" group at the 60° hue angle, and
# real-skin hue angles sit roughly between deep-red ruddiness and golden yellow.
# Ranges fan the undertone within this band (clamped, so no range escapes into
# the yellow-green / olive tints the old HSV sweep drifted into — GitHub #53,
# grounded in the Pantone SkinTone chart + Fitzpatrick/ITA literature).
_SKIN_HUE_LO = 35.0
_SKIN_HUE_HI = 78.0
_SKIN_UNDERTONE_FAN = 15.0          # total ° spread of undertone across ranges


def _lab_to_srgb(lab):
    """(N,3) CIELab (D65) → (N,3) sRGB on 0..1, clamped to gamut. Inverse of
    :func:`_srgb_to_lab`."""
    import numpy as np
    a = np.asarray(lab, dtype=float)
    L, A, B = a[:, 0], a[:, 1], a[:, 2]
    fy = (L + 16.0) / 116.0
    fx = fy + A / 500.0
    fz = fy - B / 200.0
    f = np.stack([fx, fy, fz], axis=1)
    f3 = f ** 3
    xyz = np.where(f3 > 0.008856, f3, (f - 16.0 / 116.0) / 7.787)
    xyz = xyz * np.array([0.95047, 1.0, 1.08883])
    m = np.array([[0.4124, 0.3576, 0.1805],
                  [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]])
    lin = xyz @ np.linalg.inv(m).T
    lin = np.clip(lin, 0.0, None)
    srgb = np.where(lin <= 0.0031308, 12.92 * lin,
                    1.055 * np.power(lin, 1.0 / 2.4) - 0.055)
    return np.clip(srgb, 0.0, 1.0)


def skin_tones(per_type: int, ranges: int = 3) -> list[tuple[float, float, float]]:
    """A skin-tone spread for the 6 Fitzpatrick phototypes, light → dark.

    Built in CIELAB so every patch stays inside the real skin locus (#53). Each
    of the six Fitzpatrick anchors fixes a lightness (its ITA / melanin level)
    and an undertone (its CIELAB hue angle — lighter types lean golden-yellow,
    deeper types lean red, just like real skin and the Pantone SkinTone Guide).

    * ``ranges`` fans the **undertone**: each ramp is rotated a little around
      the anchor's hue (rosier ↔ more golden), clamped to the skin wedge
      (≈ 35°–78°), so added ranges are genuine skin-undertone variants rather
      than the parallel HSV lines that used to wander into yellow-green / olive.
    * ``per_type`` sweeps **lightness** dark → light along the anchor's ITA
      pathway, with chroma tapering at the pale and deep extremes (real skin is
      least chromatic when very light or very dark). The light end reaches
      *further toward mid-tone the darker the anchor*, so deep phototypes (V/VI)
      span a comparable tonal length to the pale ones instead of bunching into a
      short, dense ramp (GitHub #37 — Knut's "darkest range too dense" note).

    Total = ``6 * ranges * per_type``, ordered type-by-type, then ramp-by-ramp,
    each ramp dark → light. ``ranges = 1`` is a single central-undertone ramp.
    """
    import numpy as np

    per_type = max(1, int(per_type))
    ranges = max(1, int(ranges))
    labs = _srgb_to_lab([[r / 255.0, g / 255.0, b / 255.0]
                         for r, g, b in _FITZPATRICK_ANCHORS])
    out: list[tuple[float, float, float]] = []
    for L0, a0, b0 in labs:
        chroma0 = math.hypot(a0, b0)
        hue0 = math.degrees(math.atan2(b0, a0))
        # Lightness endpoints: stretch a fixed fraction of the headroom up to
        # near-white and down toward deep tone, so every anchor (pale or deep)
        # covers a comparable tonal length.
        l_light = L0 + (96.0 - L0) * 0.32
        l_dark = L0 - (L0 - 18.0) * 0.32
        for ri in range(ranges):
            tr = (ri / (ranges - 1) - 0.5) if ranges > 1 else 0.0
            hue = max(_SKIN_HUE_LO, min(_SKIN_HUE_HI,
                                        hue0 + tr * _SKIN_UNDERTONE_FAN))
            hr = math.radians(hue)
            ramp_lab = []
            for i in range(per_type):
                t = i / (per_type - 1) if per_type > 1 else 0.5
                L = l_dark + (l_light - l_dark) * t
                # Chroma peaks in the mid-tones, eases off at both ends.
                chroma = chroma0 * (1.0 - 0.35 * (2.0 * t - 1.0) ** 2)
                ramp_lab.append((L, chroma * math.cos(hr),
                                 chroma * math.sin(hr)))
            for r, g, b in _lab_to_srgb(ramp_lab):
                out.append((float(r) * 100.0, float(g) * 100.0, float(b) * 100.0))
    return out


def skin_tones_count(per_type: int, ranges: int = 3) -> int:
    return 6 * max(1, int(ranges)) * max(1, int(per_type))


# ---------------------------------------------------------------------------
# Shared layered hue-region filler for the blues / greens spreads.
# ---------------------------------------------------------------------------
def _hue_region_layered(
    count: int,
    h0: float, h1: float,
    s_lo: float, s_hi: float,
    v0: float, v1: float,
    layers: int = 1,
) -> list[tuple[float, float, float]]:
    """``count`` patches spread over ``layers`` non-parallel sheets in one band.

    A single sheet sweeps hue ``h0``→``h1`` across its columns and value
    ``v0``→``v1`` down its rows. With ``layers`` > 1 the ``count`` is split
    across that many sheets, each sitting at a **different saturation shell**
    (from the punchy ``s_hi`` edge in toward the softer ``s_lo`` core) and
    **tilted** so its hue skews with brightness in a per-layer direction — the
    sheets fan out rather than stacking parallel, filling the 3-D wedge of the
    band instead of a single flat blanket. The grid of each sheet is kept as
    square as possible and the whole is trimmed to exactly ``count``.
    """
    count = max(1, int(count))
    layers = max(1, int(layers))
    base, rem = divmod(count, layers)
    out: list[tuple[float, float, float]] = []
    for li in range(layers):
        n = base + (1 if li < rem else 0)
        if n <= 0:
            continue
        tl = li / (layers - 1) if layers > 1 else 0.5
        s_layer = s_hi - (s_hi - s_lo) * tl     # each layer its own saturation
        skew = (tl - 0.5) * 22.0                # degrees of hue tilt vs value
        n_h = max(1, round(math.sqrt(n)))
        n_v = max(1, math.ceil(n / n_h))
        sheet: list[tuple[float, float, float]] = []
        for vi in range(n_v):
            tv = vi / (n_v - 1) if n_v > 1 else 0.5
            v = v0 + (v1 - v0) * tv
            for hi in range(n_h):
                th = hi / (n_h - 1) if n_h > 1 else 0.5
                h = h0 + (h1 - h0) * th + skew * (tv - 0.5)
                sheet.append(_hsv(h, min(1.0, max(0.0, s_layer)), v))
        out.extend(sheet[:n])
    return out[:count]


# ---------------------------------------------------------------------------
# 3. Enhanced blues / turquoise — for wide-gamut spaces (AdobeRGB etc.).
# ---------------------------------------------------------------------------
def blues(count: int, layers: int = 3) -> list[tuple[float, float, float]]:
    """``count`` patches concentrated in the green-turquoise→blue→blue-violet
    band (hue ≈ 150°–262°) — the corner wide-gamut spaces stretch furthest. The
    band now reaches down into the **greenish turquoise** the original spread
    missed, and ``layers`` non-parallel saturation shells give the turquoise
    wedge real volume coverage instead of one flat blanket.
    """
    return _hue_region_layered(count, 150.0, 262.0, 0.55, 0.98, 0.45, 1.0, layers)


def blues_count(count: int) -> int:
    return max(1, int(count))


# ---------------------------------------------------------------------------
# 4. Enhanced greens — forest / jungle / foliage.
# ---------------------------------------------------------------------------
def greens(count: int, layers: int = 2) -> list[tuple[float, float, float]]:
    """``count`` patches across the foliage greens (hue ≈ 80°–160°), spanning
    yellow-greens through deep forest greens with varied brightness so nature
    images are well covered. ``layers`` non-parallel saturation shells fill the
    green wedge in depth rather than as a single sheet.
    """
    return _hue_region_layered(count, 80.0, 160.0, 0.50, 0.95, 0.30, 0.95, layers)


def greens_count(count: int) -> int:
    return max(1, int(count))


# ---------------------------------------------------------------------------
# 4b. Sunrises — the warm band: yellows, oranges, reds and pinks.
# ---------------------------------------------------------------------------
def sunrises(count: int, layers: int = 3) -> list[tuple[float, float, float]]:
    """``count`` patches across the warm "sunrise" band — golden yellows through
    oranges and reds into pinks (hue ≈ 335°–60°, wrapping through red at 0°) —
    the warm side of the cube the blues and greens sets leave uncovered (#53).

    Built exactly like :func:`blues` and :func:`greens`: ``layers`` non-parallel
    saturation shells fill the wedge in depth rather than as one flat sheet, so
    the soft pinks at the low-saturation core and the vivid reds / oranges on the
    outer shell are both sampled, across mid-to-light brightness.

    The band now reaches further into the **dark** warm tones (value floor 0.30,
    matching the greens set) so it starts near the neutral axis instead of mid
    lightness — closing the bright opening that used to sit between the warm and
    cool bands around the dark corner (Knut, #78).
    """
    return _hue_region_layered(count, -25.0, 60.0, 0.45, 0.98, 0.30, 1.0, layers)


def sunrises_count(count: int) -> int:
    return max(1, int(count))


# ---------------------------------------------------------------------------
# 4c. Flamingos — the pink / magenta / indigo band the others leave out.
# ---------------------------------------------------------------------------
def flamingos(count: int, layers: int = 3) -> list[tuple[float, float, float]]:
    """``count`` patches across the pink → magenta → indigo band (hue ≈
    262°–335°) — the wedge between where :func:`blues` ends (≈ 262°) and
    :func:`sunrises` begins (≈ 335°), which nothing else covered (Knut, #78).

    This is the big pink/magenta gap visible in the 3-D cube when blues, greens
    and sunrises are all on. Built exactly like the other hue-band sets:
    ``layers`` non-parallel saturation shells fill the wedge in depth — soft
    pinks and lilacs at the low-saturation core, vivid magentas and violets on
    the outer shell — and it reaches from the dark tones (value floor 0.30, like
    sunrises) up to fully saturated, so the band joins the warm and cool sides
    cleanly without overlapping either.
    """
    return _hue_region_layered(count, 262.0, 335.0, 0.50, 0.98, 0.30, 1.0, layers)


def flamingos_count(count: int) -> int:
    return max(1, int(count))


# ---------------------------------------------------------------------------
# 5. Near-neutral greys — neutral axis + 6 hue-shifted rings.
# ---------------------------------------------------------------------------
# Unit channel masks for the six hue vertices around the neutral axis:
# Red, Yellow, Green, Cyan, Blue, Magenta.
_HUE_MASKS = (
    (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1), (1, 0, 1),
)


# Orthonormal basis of the plane perpendicular to the neutral axis (both sum to
# zero, unit length, mutually orthogonal) — so cosθ·U + sinθ·V traces a true
# circle of unit Euclidean radius in "constant-mean" (pure-chroma) space.
_PLANE_U = (1.0 / math.sqrt(2), -1.0 / math.sqrt(2), 0.0)
_PLANE_V = (1.0 / math.sqrt(6), 1.0 / math.sqrt(6), -2.0 / math.sqrt(6))


def _ring_tints(g: float, radius: float, n: int,
                phase: float) -> list[tuple[float, float, float]]:
    """``n`` balanced hue tints on a ring of Euclidean radius ``radius``.

    The tints sit at evenly spaced hue angles (starting at ``phase`` degrees) in
    the plane perpendicular to the neutral axis, so the ring is a pure hue
    excursion around grey ``g`` — the mean of R/G/B stays at ``g``, not a
    lightness change. ``radius`` is the RGB-space (Euclidean) distance from the
    neutral point, in device units on the 0..100 scale.
    """
    out: list[tuple[float, float, float]] = []
    for k in range(n):
        th = math.radians(phase + k * 360.0 / n)
        cos_t, sin_t = math.cos(th), math.sin(th)
        out.append(tuple(
            _clamp(g + radius * (cos_t * _PLANE_U[j] + sin_t * _PLANE_V[j]))
            for j in range(3)))
    return out


def near_neutral_greys(steps: int, offset: float,
                       rings: int = 1) -> list[tuple[float, float, float]]:
    """A neutral grey ramp plus, at each step, ``rings`` rings of hue tints.

    ``steps`` neutral greys are spread from black to white. At each grey level
    ``g`` one or more concentric hue rings circle the neutral axis: ring *n* has
    ``6 * n`` tints (6, 12, 18, …) at chroma radius ``n * offset``, so outer
    rings keep roughly the same angular spacing as the inner one and fill the
    near-neutral disk rather than forming spokes (each ring is phase-rotated to
    interleave with its neighbours). Every tint is a *balanced* shift — the mean
    of R/G/B stays at ``g`` — a true hue excursion, not a lightness change.

    With ``rings == 0`` it is a *pure* neutral ramp — just the ``steps`` greys,
    no hue tints — so ``offset`` has no effect. With ``rings == 1`` it is the
    original 6-tint hexagon, identical to before.
    Total = ``steps * (1 + 6 + 12 + … )`` = ``steps * (1 + 3 * rings * (rings+1))``.

    ``offset`` is in device units on the 0..100 scale (e.g. 6.25 ≈ 16/256).
    """
    steps = max(1, int(steps))
    rings = max(0, int(rings))
    out: list[tuple[float, float, float]] = []
    for i in range(steps):
        g = (i / (steps - 1) if steps > 1 else 0.5) * 100.0
        out.append((g, g, g))
        out.extend(_grey_tints(g, offset, rings))
    return out


def _grey_tints(g: float, offset: float,
                rings: int) -> list[tuple[float, float, float]]:
    """The hue-tint rings circling a single neutral grey ``g`` (not the grey
    itself). Shared by ``near_neutral_greys`` (the combined primitive) and the
    standalone ``near_neutrals`` set so they place identical rings. ``rings == 0``
    → no tints, so ``offset`` is unused (a pure neutral point)."""
    rings = max(0, int(rings))
    if rings == 0:
        return []
    if rings == 1:
        # Preserve the exact original R/Y/G/C/B/M hexagon (and its values).
        out: list[tuple[float, float, float]] = []
        for mask in _HUE_MASKS:
            m = sum(mask) / 3.0
            out.append(tuple(_clamp(g + offset * (c - m)) for c in mask))
        return out
    # Hexagon vertices sit sqrt(6)/3 · offset from neutral in RGB space;
    # match that for ring 1 so the offset control feels the same in both
    # modes, then space outer rings at integer multiples.
    base_radius = math.sqrt(6) / 3.0 * offset
    out = []
    for r in range(1, rings + 1):
        n = 6 * r
        phase = (r - 1) * (360.0 / n) / 2.0   # interleave with inner ring
        out.extend(_ring_tints(g, r * base_radius, n, phase))
    return out


def near_neutral_greys_count(steps: int, rings: int = 1) -> int:
    rings = max(0, int(rings))
    tints = 3 * rings * (rings + 1)               # 6 + 12 + … = sum(6r)
    return max(1, int(steps)) * (1 + tints)


def neutral_ramp(steps: int) -> list[tuple[float, float, float]]:
    """A pure neutral grey ramp from black to white — ``steps`` greys, no tints
    (a plain black-and-white wedge).

    The most important region for a clean profile. Independent of ``near_neutrals``
    (the off-axis tint rings), so the number of pure neutrals can be chosen
    separately from the near-neutral hue coverage.
    """
    steps = max(1, int(steps))
    out: list[tuple[float, float, float]] = []
    for i in range(steps):
        g = (i / (steps - 1) if steps > 1 else 0.5) * 100.0
        out.append((g, g, g))
    return out


def neutral_ramp_count(steps: int) -> int:
    return max(1, int(steps))


def near_neutrals(steps: int, offset: float,
                  rings: int = 1) -> list[tuple[float, float, float]]:
    """The off-axis hue tints circling ``steps`` neutral levels — **without** the
    pure neutral centre at each level (that is ``neutral_ramp``'s job).

    At each of ``steps`` levels from black to white, ``rings`` concentric rings of
    balanced hue tints (6, 12, 18 …) sit at chroma radius driven by ``offset`` —
    exactly the rings ``near_neutral_greys`` produced, just without the centre.
    ``rings`` is at least 1 (with no rings there is nothing to place; use
    ``neutral_ramp`` alone for pure neutrals). By construction,
    ``neutral_ramp(S) + near_neutrals(S, O, R)`` reproduces the old combined
    ``near_neutral_greys(S, O, R)`` exactly — same patches, same count.
    """
    steps = max(1, int(steps))
    rings = max(1, int(rings))
    out: list[tuple[float, float, float]] = []
    for i in range(steps):
        g = (i / (steps - 1) if steps > 1 else 0.5) * 100.0
        out.extend(_grey_tints(g, offset, rings))
    return out


def near_neutrals_count(steps: int, rings: int = 1) -> int:
    rings = max(1, int(rings))
    tints = 3 * rings * (rings + 1)               # 6 + 12 + … = sum(6r)
    return max(1, int(steps)) * tints


# ---------------------------------------------------------------------------
# 6. Gamut edges — the wireframe of the RGB cube (the device's gamut boundary).
# ---------------------------------------------------------------------------
# The eight cube corners and the twelve edges joining them. A printer's most
# saturated reproducible colours live on this surface, and it is where profiles
# carry the most error — so sampling the boundary densely is worthwhile.
_CUBE_CORNERS = {
    "K": (0.0, 0.0, 0.0),     "R": (100.0, 0.0, 0.0),
    "G": (0.0, 100.0, 0.0),   "B": (0.0, 0.0, 100.0),
    "Y": (100.0, 100.0, 0.0), "C": (0.0, 100.0, 100.0),
    "M": (100.0, 0.0, 100.0), "W": (100.0, 100.0, 100.0),
}
_CUBE_EDGES = (
    ("K", "R"), ("K", "G"), ("K", "B"),   # black → primaries
    ("R", "Y"), ("R", "M"), ("G", "Y"),   # primaries → secondaries
    ("G", "C"), ("B", "C"), ("B", "M"),
    ("Y", "W"), ("C", "W"), ("M", "W"),   # secondaries → white
)


def _edge_param(p, fixed_idx, fixed_vals, var_idx, tol):
    """Parameter ``t`` in 0..1 of ``p`` along an edge (the edge's two other
    channels pinned at ``fixed_vals``), or ``None`` if ``p`` isn't on it."""
    if all(abs(p[j] - v) <= tol for j, v in zip(fixed_idx, fixed_vals)):
        t = p[var_idx] / 100.0
        if -0.01 <= t <= 1.01:
            return min(1.0, max(0.0, t))
    return None


def _fill_line_midpoints(anchors, k: int, tip_first: bool = False) -> list[float]:
    """``k`` new positions in 0..1 that bisect gaps between the sorted ``anchors``
    (fixed points already on the line), re-splitting after each insertion — a 1-D
    gap-fill, so new points land at the midpoints between the closest surrounding
    patches.

    By default the **largest** gap is bisected each time (even spread). With
    ``tip_first`` the gap nearest the start of the line (t = 0) is bisected
    instead, so points cluster toward that end — used by the corner-emphasis set
    so the first/closest patch hugs the gamut corner rather than landing in a
    bigger gap further out (Knut)."""
    occupied = sorted(anchors)
    added: list[float] = []
    for _ in range(k):
        merged = sorted(occupied + added)
        if tip_first:
            gi = min(range(len(merged) - 1), key=lambda i: merged[i])
        else:
            gi = max(range(len(merged) - 1),
                     key=lambda i: merged[i + 1] - merged[i])
        added.append((merged[gi] + merged[gi + 1]) / 2.0)
    return added


def gamut_edges(per_edge: int, existing=None,
                tol: float = 1.0) -> list[tuple[float, float, float]]:
    """``per_edge`` patches along each of the 12 edges of the RGB cube.

    This traces the device's gamut boundary — the black→primary, primary→
    secondary and secondary→white ramps that bound everything the printer can
    reproduce.

    When ``existing`` patches are given (e.g. the 3D cube, already placed on the
    boundary), each edge's new patches are laid at the **midpoints of the gaps**
    between the patches already on that edge — so the saturated set fills the
    spaces the cube left rather than re-sampling the same points (#53). With no
    ``existing`` patches on an edge the layout is the original even spacing,
    endpoints (corners) included.

    Total = ``12 * per_edge``.
    """
    per_edge = max(1, int(per_edge))
    existing = list(existing or [])
    out: list[tuple[float, float, float]] = []
    for a, b in _CUBE_EDGES:
        ca, cb = _CUBE_CORNERS[a], _CUBE_CORNERS[b]
        var_idx = next(j for j in range(3) if ca[j] != cb[j])
        fixed_idx = [j for j in range(3) if ca[j] == cb[j]]
        fixed_vals = [ca[j] for j in fixed_idx]
        occ = [t for t in (_edge_param(p, fixed_idx, fixed_vals, var_idx, tol)
                           for p in existing) if t is not None]
        if occ:
            # Fill the gaps between what's already here (corners are anchors too).
            ts = _fill_line_midpoints(occ + [0.0, 1.0], per_edge)
        else:
            ts = [i / (per_edge - 1) if per_edge > 1 else 0.5
                  for i in range(per_edge)]
        for t in ts:
            out.append(tuple(_clamp(ca[j] + (cb[j] - ca[j]) * t) for j in range(3)))
    return out


def gamut_edges_count(per_edge: int) -> int:
    return 12 * max(1, int(per_edge))


# The 6 faces of the cube (one channel pinned at 0 or 100) — the gamut *surface*,
# of which the 12 edges are just the wireframe. (channel-to-pin, pinned-value).
_CUBE_FACES = (
    (0, 0.0), (0, 100.0), (1, 0.0), (1, 100.0), (2, 0.0), (2, 100.0),
)


def _fill_plane_midpoints(occupied, k: int, seed: int = 0,
                          candidates: int = 12, relax: int = 3):
    """``k`` new (u, v) points in the 0..100 square placed in the sparsest spots
    around the fixed ``occupied`` points, then relaxed onto their cell centroids
    — the 2-D version of :func:`fill_gaps`, so face patches land at the midpoints
    between the patches already on that face."""
    import numpy as np
    rng = np.random.default_rng(seed)
    fixed = np.array(occupied, dtype=float) if len(occupied) else np.empty((0, 2))
    arr = fixed.copy()
    added = np.empty((k, 2), dtype=float)
    for i in range(k):
        cand = rng.uniform(0.0, 100.0, size=(max(1, candidates), 2))
        if len(arr):
            d2 = ((cand[:, None, :] - arr[None, :, :]) ** 2).sum(2).min(axis=1)
            pick = cand[int(d2.argmax())]
        else:
            pick = cand[0]
        added[i] = pick
        arr = np.vstack([arr, pick[None, :]])
    base = len(fixed)
    if relax > 0 and k:
        n_s = min(20000, max(2000, 60 * k))
        for _ in range(int(relax)):
            sites = np.vstack([fixed, added]) if base else added
            samp = rng.uniform(0.0, 100.0, size=(n_s, 2))
            owner = (((samp[:, None, :] - sites[None, :, :]) ** 2)
                     .sum(2).argmin(1))
            for j in range(k):
                sel = samp[owner == base + j]
                if len(sel):
                    added[j] = sel.mean(0)
    return added


def gamut_faces(per_face: int, existing=None,
                tol: float = 1.0) -> list[tuple[float, float, float]]:
    """An ``per_face × per_face`` sampling on each of the cube's 6 faces.

    Where :func:`gamut_edges` traces the gamut wireframe, this samples the gamut
    *surface* — the saturated boundary the printer can just reach. ``per_face =
    0`` means no face sampling.

    With no ``existing`` patches on a face the points sit at grid cell centres
    ``(i + 0.5) / per_face`` (the original even layout). When ``existing``
    patches already lie on a face (e.g. the 3D cube's face points), the new
    patches instead fill the **midpoints of the gaps** between them — an even
    blue-noise-then-centroidal fill of that face's empty space (#53), so the
    saturated set complements the cube rather than doubling up on it.

    Total = ``6 * per_face**2``.
    """
    per_face = max(0, int(per_face))
    if per_face == 0:
        return []
    existing = list(existing or [])
    n = per_face * per_face
    out: list[tuple[float, float, float]] = []
    for fi, (fixed, val) in enumerate(_CUBE_FACES):
        free = [k for k in range(3) if k != fixed]
        occ = [(p[free[0]], p[free[1]]) for p in existing
               if abs(p[fixed] - val) <= tol]
        if occ:
            uv = _fill_plane_midpoints(occ, n, seed=fi)
            for u, v in uv:
                p = [0.0, 0.0, 0.0]
                p[fixed] = val
                p[free[0]] = float(_clamp(u))
                p[free[1]] = float(_clamp(v))
                out.append((p[0], p[1], p[2]))
        else:
            for i in range(per_face):
                for j in range(per_face):
                    p = [0.0, 0.0, 0.0]
                    p[fixed] = val
                    p[free[0]] = (i + 0.5) / per_face * 100.0
                    p[free[1]] = (j + 0.5) / per_face * 100.0
                    out.append((p[0], p[1], p[2]))
    return out


def gamut_faces_count(per_face: int) -> int:
    pf = max(0, int(per_face))
    return 6 * pf * pf


# ---------------------------------------------------------------------------
# 6b. Even stepwise edges / faces — keyed to the 3D cube's own grid.
# ---------------------------------------------------------------------------
# The gap-filling variants above place a *count* of patches per edge/face and
# bisect the largest gaps — which is even only when there is roughly one patch
# per cube interval; ask for more and the spacing goes lumpy (Knut, #78). These
# variants instead place a fixed number of patches *between each pair of adjacent
# cube steps*, so the infill is exactly even at any density. They derive the
# grid straight from the cube's steps-per-axis (``cube_n``) rather than from the
# patches already placed, so the cube and its boundary fill stay locked together
# by construction. Pass ``cube_n = 2`` when the cube is off (fill between the two
# corners only).
def _interior_fracs(per_gap: int) -> list[float]:
    """``per_gap`` evenly spaced fractions strictly inside the unit interval
    (excluding both ends): 1 → [0.5]; 2 → [1/3, 2/3]; 3 → [0.25, 0.5, 0.75]…"""
    return [(j + 1) / (per_gap + 1) for j in range(per_gap)]


def gamut_edges_between(cube_n: int, per_gap: int,
                        include_corners: bool = False) -> list[tuple[float, float, float]]:
    """``per_gap`` evenly spaced patches in **every interval between adjacent
    cube steps**, along all 12 edges of the RGB cube.

    With the cube at ``cube_n`` steps per axis each edge carries ``cube_n`` cube
    points and ``cube_n - 1`` intervals, so each edge gets exactly
    ``per_gap * (cube_n - 1)`` new patches — none coinciding with a cube point,
    all evenly spaced. This is the even gamut-wireframe infill the cube leaves
    between its own edge samples (``per_gap = 1`` drops one patch midway between
    each pair of cube dots — the layout Knut found looks right).

    With ``include_corners=True`` the eight cube corners are added too — used
    when Saturated edges runs **without** the 3D cube, so the corner tips (the
    most saturated colours) aren't dropped the way the between-only fill leaves
    them out (Nelson via Knut, #78). When the cube is on it supplies the corners,
    so this stays off.
    """
    cube_n = max(2, int(cube_n))
    per_gap = max(0, int(per_gap))
    out: list[tuple[float, float, float]] = []
    if include_corners:
        out.extend(_CORNER_PTS)
    if per_gap == 0:
        return out
    fr = _interior_fracs(per_gap)
    for a, b in _CUBE_EDGES:
        ca, cb = _CUBE_CORNERS[a], _CUBE_CORNERS[b]
        for i in range(cube_n - 1):
            t0, t1 = i / (cube_n - 1), (i + 1) / (cube_n - 1)
            for f in fr:
                t = t0 + (t1 - t0) * f
                out.append(tuple(_clamp(ca[j] + (cb[j] - ca[j]) * t)
                                 for j in range(3)))
    return out


def gamut_edges_between_count(cube_n: int, per_gap: int,
                              include_corners: bool = False) -> int:
    return (12 * max(0, int(per_gap)) * (max(2, int(cube_n)) - 1)
            + (8 if include_corners else 0))


def gamut_faces_between(cube_n: int, per_gap: int) -> list[tuple[float, float, float]]:
    """An even ``per_gap`` infill across each face's **interior lattice** — the
    2-D analogue of :func:`gamut_edges_between`.

    Refine the face into one uniform grid that subdivides every cube interval
    into ``per_gap + 1`` parts on **both** axes, then keep the points that are
    neither a cube point nor on the face's perimeter. Crucially this *includes*
    the points that sit on the cube grid lines **between** adjacent cube dots, so
    the fill is an even lattice with no empty channels — an earlier
    inside-each-cell-only version left a cross-shaped gap along those lines
    (Knut, #78). The perimeter (the face's four cube edges) is left to
    :func:`gamut_edges_between`, so the two don't fight over the boundary.

    The cube supplies the lattice's cube points and the edges set its border, so
    cube + edges + faces together read as one even grid. A face gets
    ``((cube_n - 1)*(per_gap + 1) - 1)**2 - (cube_n - 2)**2`` patches.
    """
    cube_n = max(2, int(cube_n))
    per_gap = max(0, int(per_gap))
    if per_gap == 0:
        return []
    step = per_gap + 1
    last = (cube_n - 1) * step                     # max grid index (perimeter)
    out: list[tuple[float, float, float]] = []
    for fixed, val in _CUBE_FACES:
        free = [k for k in range(3) if k != fixed]
        for iu in range(1, last):                  # interior only (drop perimeter)
            for iv in range(1, last):
                if iu % step == 0 and iv % step == 0:
                    continue                       # a cube point — already placed
                p = [0.0, 0.0, 0.0]
                p[fixed] = val
                p[free[0]] = _clamp(iu / last * 100.0)
                p[free[1]] = _clamp(iv / last * 100.0)
                out.append((p[0], p[1], p[2]))
    return out


def gamut_faces_between_count(cube_n: int, per_gap: int) -> int:
    cn = max(2, int(cube_n))
    pg = max(0, int(per_gap))
    if pg == 0:
        return 0
    interior = (cn - 1) * (pg + 1) - 1
    return 6 * (interior * interior - (cn - 2) * (cn - 2))


# ---------------------------------------------------------------------------
# 6c. Gamut-corner emphasis — Highlights-&-shadows-style spirals at the 8 corners.
# ---------------------------------------------------------------------------
# The eight extreme corners of the device cube (K/R/G/B/C/M/Y/W) are the most
# saturated, hardest-to-map colours — where profiles carry the most error. This
# set fills a phyllotaxis spiral *cone* just inside each corner (the same idea as
# Highlights & shadows, which does it at the white/black corners, generalised to
# all eight). Two controls mirror H&S: 'per end' patches per corner, reaching
# 'depth' device units in toward the cube centre (Knut/Nelson, #78).
_CORNER_PTS = (
    (0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (0.0, 100.0, 0.0), (0.0, 0.0, 100.0),
    (0.0, 100.0, 100.0), (100.0, 0.0, 100.0), (100.0, 100.0, 0.0),
    (100.0, 100.0, 100.0),
)

# Cone half-spread: the spiral's radius as a fraction of its depth (≈ 31°).
_CORNER_CONE_SLOPE = 0.6


def _perp_basis(d):
    """Two orthonormal vectors spanning the plane perpendicular to unit vector
    ``d`` (Gram-Schmidt from whichever axis is least parallel to ``d``)."""
    seed = (1.0, 0.0, 0.0) if abs(d[0]) < 0.9 else (0.0, 1.0, 0.0)
    dot = sum(seed[j] * d[j] for j in range(3))
    u = [seed[j] - dot * d[j] for j in range(3)]
    un = math.sqrt(sum(x * x for x in u)) or 1.0
    u = [x / un for x in u]
    v = [d[1] * u[2] - d[2] * u[1],          # v = d × u
         d[2] * u[0] - d[0] * u[2],
         d[0] * u[1] - d[1] * u[0]]
    return u, v


# The six *chromatic* corners (R/G/B/C/M/Y) — the white and black corners are
# omitted because Highlights & shadows already builds cones there (Knut, #78).
_CHROMATIC_CORNERS = tuple(c for c in _CORNER_PTS
                           if c not in ((0.0, 0.0, 0.0), (100.0, 100.0, 100.0)))


def gamut_corners(per_end: int, reach: float,
                  include_corners: bool = False) -> list[tuple[float, float, float]]:
    """A phyllotaxis spiral *cone* just inside each of the 6 **chromatic** cube
    corners (R/G/B/C/M/Y) — Highlights & shadows generalised from the white/black
    corners to the colour ones (it already covers white and black).

    Each corner gets ``per_end`` patches (``6 * per_end`` in all) spiralling in
    along the corner's diagonal toward the cube centre: successive points step
    deeper (up to ``reach`` device units) and rotate by the golden angle, with the
    cone widening as it goes, so the cluster is dense at the saturated tip and
    fans out inward without spokes. The exact corner tip is **not** included (it's
    owned by the cube, the edges or the corner-edges set) unless
    ``include_corners=True`` — then the six chromatic tips are added (white/black
    stay with Highlights & shadows).
    """
    per_end = max(1, int(per_end))
    reach = 2.0 if reach < 2.0 else 60.0 if reach > 60.0 else float(reach)
    out: list[tuple[float, float, float]] = []
    if include_corners:
        out.extend(_CHROMATIC_CORNERS)
    for corner in _CHROMATIC_CORNERS:
        # Unit direction from the corner toward the cube centre (the diagonal).
        dvec = [50.0 - corner[j] for j in range(3)]
        dn = math.sqrt(sum(x * x for x in dvec)) or 1.0
        d = [x / dn for x in dvec]
        u, v = _perp_basis(d)
        for k in range(per_end):
            t = (k + 0.5) / per_end           # 0..1: tip → deepest
            dd = reach * t                    # distance in along the diagonal
            rr = _CORNER_CONE_SLOPE * dd      # cone radius at this depth
            ang = math.radians(k * _GOLDEN_DEG)
            ca, sa = math.cos(ang), math.sin(ang)
            out.append(tuple(
                _clamp(corner[j] + d[j] * dd + (u[j] * ca + v[j] * sa) * rr)
                for j in range(3)))
    return out


def gamut_corners_count(per_end: int, include_corners: bool = False) -> int:
    return 6 * max(1, int(per_end)) + (6 if include_corners else 0)


# ---------------------------------------------------------------------------
# 6d. Corner edges — extra patches on the wireframe just inside each corner tip.
# ---------------------------------------------------------------------------
# The TC9.18 / TC9.24 trick: a few extra samples on the gamut edge lines right by
# each corner (the most saturated edge). They sit *on* the 12 cube edges, near the
# tips, slotted into the gaps between whatever the 3D cube / Saturated edges
# already placed there, so they add density without colliding (Nelson via Knut,
# #78). Each corner has three edge branches; with both ends of every cube edge
# sampled that's 8 × 3 = 24 branch-ends.
_CORNER_EDGE_NEAR = 20.0      # device units from the tip the extra patches fill


def gamut_corner_edges(per_branch: int, existing=None,
                       include_corners: bool = False,
                       tol: float = 1.5) -> list[tuple[float, float, float]]:
    """``per_branch`` patches on each of the three edge branches at every corner,
    clustered near the tip and slotted into the gaps left by ``existing`` patches
    on that branch (so they interleave with the cube / edges samples instead of
    landing on them). ``8 * 3 * per_branch`` in all; with ``include_corners`` the
    eight exact tips are added too (used when nothing else supplies them)."""
    per_branch = max(0, int(per_branch))
    out: list[tuple[float, float, float]] = []
    if include_corners:
        out.extend(_CORNER_PTS)
    if per_branch == 0:
        return out
    existing = list(existing or [])
    near_t = _CORNER_EDGE_NEAR / 100.0
    for corner in _CORNER_PTS:
        for j in range(3):                       # three branches: flip one axis
            span = (100.0 - corner[j]) - corner[j]    # +100 or -100
            # Existing points lying on this branch (other two coords pinned),
            # within the near-tip region, as a fraction t of the edge.
            anchors = [0.0, near_t]
            for p in existing:
                if all(abs(p[k] - corner[k]) <= tol for k in range(3) if k != j):
                    t = (p[j] - corner[j]) / span
                    if tol / 100.0 < t <= near_t:
                        anchors.append(t)
            for t in _fill_line_midpoints(sorted(anchors), per_branch,
                                          tip_first=True):
                pos = [corner[0], corner[1], corner[2]]
                pos[j] = _clamp(corner[j] + span * t)
                out.append((pos[0], pos[1], pos[2]))
    return out


def gamut_corner_edges_count(per_branch: int, include_corners: bool = False) -> int:
    return 24 * max(0, int(per_branch)) + (8 if include_corners else 0)


# ---------------------------------------------------------------------------
# 7. Highlight & shadow detail — the two tonal ends, across the hue wheel.
# ---------------------------------------------------------------------------
# Golden angle — successive points spiral to fill a disk evenly (phyllotaxis),
# so a cone's patches spread without radial spokes or gaps.
_GOLDEN_DEG = 180.0 * (3.0 - math.sqrt(5.0))         # ≈ 137.508°

# A highlight/shadow cone disc only yields its core to the near-neutral greys
# when it sits within this many device units (0..100) of an actual grey step in
# lightness — i.e. when a grey disc is really there to clash with. ≈ 3 eight-bit
# code values; discs that fall in the gaps between grey steps fill to the axis.
_GREY_CLASH_TOL = 1.5


def _allocate_by_weight(total: int, weights: list[float]) -> list[int]:
    """Split ``total`` items across bins in proportion to ``weights`` (a weight
    of 0 skips the bin). Every eligible bin gets at least one; the remainder is
    handed out by largest fractional remainder, so the totals always add up."""
    elig = [i for i, w in enumerate(weights) if w > 0.0]
    alloc = [0] * len(weights)
    if not elig:
        return alloc
    if total <= len(elig):                           # not enough to seed each one
        for i in sorted(elig, key=lambda i: -weights[i])[:total]:
            alloc[i] = 1
        return alloc
    for i in elig:
        alloc[i] = 1
    rem = total - len(elig)
    wsum = sum(weights[i] for i in elig)
    quota = {i: rem * weights[i] / wsum for i in elig}
    for i in elig:
        alloc[i] += int(quota[i])
    left = rem - sum(int(quota[i]) for i in elig)
    for i in sorted(elig, key=lambda i: -(quota[i] - int(quota[i])))[:left]:
        alloc[i] += 1
    return alloc


def highlight_shadow_detail(per_end: int,
                            reach: float = 16.0,
                            *,
                            greys_enabled: bool = False,
                            greys_steps: int = 16,
                            greys_offset: float = 5.0,
                            greys_rings: int = 1) -> list[tuple[float, float, float]]:
    """``per_end`` patches into the extreme highlights + ``per_end`` into the
    extreme shadows, as two **mirror-image, filled cones** around the neutral
    axis — narrowing to the paper-white / pure-black corner and fanning inward.

    The cube's even grid samples the very-light and very-dark tones coarsely,
    yet those two ends are where printers band (highlights) and block up at the
    ink limit (shadows). The shadow cone is the exact point-inversion of the
    highlight cone (``(r,g,b) → (100-r, 100-g, 100-b)``), so — the RGB cube
    being symmetric about its centre — the two ends come out congruent. Each
    cone is *filled*: at every lightness level a phyllotaxis spiral lays patches
    from the neutral axis out to the gamut-limited cone surface, so the
    near-neutral light/dark tones are covered too, not just an outer shell.

    ``reach`` (device units, 0..100) is how far in from each end the cones
    reach; ``per_end`` is the patch count at each end (total ``2 * per_end``).

    The cones interlock with the near-neutral greys set:

    * ``greys_enabled=True`` drops a cone disc's core (inside the greys'
      outermost ring, sized from ``greys_offset`` / ``greys_rings``) *only where
      a grey disc actually sits* — i.e. when the disc is within a couple of code
      values of one of the ``greys_steps`` grey levels. Discs that fall in the
      gaps between grey steps keep filling to the axis, so few grey steps leave
      the cones mostly intact while many steps carve out more. The dropped
      patches aren't lost: the per-end budget is re-laid in the rims that remain.
    * ``greys_enabled=False`` lets the cones reach in to the neutral axis, so
      H&S also covers the near-neutral light/dark tones nothing else would.
    """
    per_end = max(1, int(per_end))
    reach = max(2.0, min(45.0, float(reach)))
    unit = math.sqrt(6) / 3.0          # RGB-space chroma radius of a unit hue mask

    # Tonal levels from just below the white corner in to `reach`. The cone
    # radius is gamut-limited (0.85 of the headroom, so no hue ever clamps), so
    # it narrows to a point at the corner — the cone reaches the very end.
    n_lev = max(1, round(math.sqrt(per_end * 0.5)))
    depths = [reach * (i + 1) / n_lev for i in range(n_lev)]      # 100-L, tip→base
    r_max = [0.85 * d / unit for d in depths]

    # Per-level inner radius. When greys are on, a disc only yields its core if a
    # grey step really sits at (near) its lightness — discs in the gaps between
    # steps fill to the axis. The clearance is capped just under the base cone's
    # radius so the widest level can always hold patches.
    r_clear = 0.0
    step_ls: list[float] = []
    if greys_enabled:
        off = max(0.0, float(greys_offset))
        greys_outer = max(1, int(greys_rings)) * unit * off
        r_clear = min(greys_outer + 0.5 * unit * max(1.0, off), 0.9 * r_max[-1])
        s = max(1, int(greys_steps))
        step_ls = [(k / (s - 1) if s > 1 else 0.5) * 100.0 for k in range(s)]

    def _inner(L: float) -> float:
        if not step_ls:
            return 0.0
        near = min(abs(L - sl) for sl in step_ls) <= _GREY_CLASH_TOL
        return r_clear if near else 0.0

    r_in = [_inner(100.0 - d) for d in depths]

    # Budget each level by its (annulus) area, so density is even across the cone
    # (levels too close to the corner to clear a grey core get nothing).
    weights = [max(0.0, r_max[i] * r_max[i] - r_in[i] * r_in[i])
               for i in range(n_lev)]
    counts = _allocate_by_weight(per_end, weights)

    highlights: list[tuple[float, float, float]] = []
    seq = 0
    for i, m in enumerate(counts):
        if m <= 0:
            continue
        L = 100.0 - depths[i]
        span = r_max[i] * r_max[i] - r_in[i] * r_in[i]
        for j in range(m):
            t = j / (m - 1) if m > 1 else 0.0
            r = math.sqrt(r_in[i] * r_in[i] + span * t)   # areal fill, r_in → r_max
            highlights.append(_ring_tints(L, r, 1, seq * _GOLDEN_DEG)[0])
            seq += 1

    shadows = [(100.0 - r, 100.0 - g, 100.0 - b) for (r, g, b) in highlights]
    return highlights + shadows


def highlight_shadow_detail_count(per_end: int) -> int:
    return 2 * max(1, int(per_end))


# ---------------------------------------------------------------------------
# 8. Image palette — the most representative colours of a loaded image.
# ---------------------------------------------------------------------------
def _srgb_to_lab(rgb01):
    """(N,3) sRGB in 0..1 → (N,3) CIELab (D65). NumPy-vectorised."""
    import numpy as np
    a = np.asarray(rgb01, dtype=float)
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805],
                  [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]])
    xyz = lin @ m.T
    white = np.array([0.95047, 1.0, 1.08883])
    f = xyz / white
    f = np.where(f > 0.008856, np.cbrt(f), 7.787 * f + 16.0 / 116.0)
    L = 116.0 * f[:, 1] - 16.0
    return np.stack([L, 500.0 * (f[:, 0] - f[:, 1]),
                     200.0 * (f[:, 1] - f[:, 2])], axis=1)


def image_palette(pixels, count: int,
                  seed: int = 0) -> list[tuple[float, float, float]]:
    """The ``count`` most representative colours of ``pixels``, as device RGB.

    ``pixels`` is an ``(N, 3)`` array-like of 0..255 RGB (e.g. a decoded,
    down-sampled image). The colours are clustered perceptually (k-means in
    CIELab with a k-means++ start) so the result spans the image's real colour
    families rather than over-counting one busy area. Cluster centres are
    returned on the 0..100 device scale, brightest first.

    Pure and deterministic (fixed ``seed``): the UI handles loading / decoding
    the file and hands the pixels here, so this stays unit-testable.
    """
    import numpy as np

    count = max(1, int(count))
    px = np.asarray(pixels, dtype=float).reshape(-1, 3)
    if px.size == 0:
        return []
    if px.max() > 1.0:
        px = px / 255.0
    lab = _srgb_to_lab(px)

    rng = np.random.default_rng(seed)
    uniq = np.unique(lab, axis=0)
    k = min(count, len(uniq))
    # k-means++ seeding on the unique colours.
    centres = [uniq[rng.integers(len(uniq))]]
    for _ in range(1, k):
        d2 = np.min([np.sum((uniq - c) ** 2, axis=1) for c in centres], axis=0)
        tot = d2.sum()
        probs = d2 / tot if tot > 0 else None
        centres.append(uniq[rng.choice(len(uniq), p=probs)])
    C = np.array(centres)
    # A few Lloyd iterations over the full pixel set.
    for _ in range(16):
        assign = np.argmin(((lab[:, None, :] - C[None, :, :]) ** 2).sum(2), axis=1)
        newC = np.array([lab[assign == j].mean(0) if np.any(assign == j) else C[j]
                         for j in range(k)])
        if np.allclose(newC, C):
            break
        C = newC

    # Map each Lab centre back to device RGB via the nearest source pixel
    # (avoids an inverse-Lab round-trip and keeps centres in-gamut for real
    # image colours).
    out: list[tuple[float, float, float]] = []
    for c in C:
        idx = int(np.argmin(((lab - c) ** 2).sum(1)))
        r, g, b = px[idx]
        out.append((float(r) * 100.0, float(g) * 100.0, float(b) * 100.0))
    out.sort(key=lambda p: 0.3 * p[0] + 0.59 * p[1] + 0.11 * p[2], reverse=True)
    return out


def image_palette_count(count: int, has_image: bool) -> int:
    return max(1, int(count)) if has_image else 0


# ---------------------------------------------------------------------------
# 9. Pastels — low-chroma midtones, the bulk of real photographic content.
# ---------------------------------------------------------------------------
def pastels(count: int, layers: int = 1) -> list[tuple[float, float, float]]:
    """``count`` gentle, low-chroma colours across the hue wheel and mid-to-light
    tones — the muted, desaturated region most photos actually live in.

    This fills the gap between the near-neutral greys (almost no chroma) and the
    vivid sets (full chroma): soft pinks, sages, dusty blues, taupes and the like.
    ``layers`` splits the patches across that many **chroma shells**, from barely
    tinted near-greys out to fuller pastels, so the muted band is filled in depth
    rather than as a single sheet (each shell's hues interleave with its
    neighbours'). With ``layers == 1`` it is one shell at a moderate pastel chroma.

    Total = ``count``.
    """
    count = max(1, int(count))
    layers = max(1, int(layers))
    base, rem = divmod(count, layers)
    out: list[tuple[float, float, float]] = []
    for li in range(layers):
        n = base + (1 if li < rem else 0)
        if n <= 0:
            continue
        tl = li / (layers - 1) if layers > 1 else 0.5
        s_shell = 0.12 + 0.18 * tl                # near-grey → fuller pastel
        n_h = max(1, round(math.sqrt(n)))         # hues across, tone down
        n_r = max(1, math.ceil(n / n_h))
        sheet: list[tuple[float, float, float]] = []
        for ri in range(n_r):
            tr = ri / (n_r - 1) if n_r > 1 else 0.5
            v = 0.55 + 0.34 * tr                  # mid → light
            for hi in range(n_h):
                h = ((hi + li / layers) / n_h) * 360.0   # interleave shells in hue
                sheet.append(_hsv(h, s_shell, v))
        out.extend(sheet[:n])
    return out[:count]


def pastels_count(count: int) -> int:
    return max(1, int(count))


# ---------------------------------------------------------------------------
# 10. Fill the gaps — blue-noise top-up of whatever the other sets left sparse.
# ---------------------------------------------------------------------------
def _nearest_site(samples, sites, chunk: int = 8192):
    """Index of the nearest ``sites`` row for each ``samples`` row (Euclidean),
    evaluated in sample chunks so the distance matrix never blows up memory.

    ONE MATMUL INSTEAD OF A BROADCAST CUBE, and it is the same answer.
    ``|a-b|^2 = |a|^2 - 2a.b + |b|^2``, and ``|a|^2`` is constant along the row
    being minimised, so only the last two terms are needed. The subtraction
    version built an ``n x m x 3`` array and reduced it; this hands the work to
    BLAS. Measured on a 4000-patch fill this function was 7.7 s of the 9.2 s
    spent inside `fill_gaps`, and the whole build drops from 11.2 s to 2.7 s.

    THE ANSWER HAS TO BE IDENTICAL, not merely close, because these indices
    decide which colours end up on the user's chart. Checked over three sizes
    up to 40,000 samples against 4,000 sites: zero differing owners. It is
    checked again by `test_the_faster_fill_is_the_same_fill.py`, which compares
    whole programs rather than this function alone.
    """
    import numpy as np
    out = np.empty(len(samples), dtype=np.intp)
    sq = (sites * sites).sum(1)
    for s in range(0, len(samples), chunk):
        blk = samples[s:s + chunk]
        d2 = sq[None, :] - 2.0 * (blk @ sites.T)
        out[s:s + chunk] = d2.argmin(1)
    return out


def fill_gaps(existing, total: int, candidates: int = 12,
              seed: int = 0, relax: int = 4) -> list[tuple[float, float, float]]:
    """Add patches until the program reaches ``total``, evenly filling the gaps.

    Given the already-chosen ``existing`` patches, this returns ``total -
    len(existing)`` new device-RGB patches, placed in two stages (#53):

    1. **Seed** — best-candidate (Mitchell) sampling: each new point is the
       farthest of several random candidates from everything so far, so the
       seeds drop into the sparsest regions first (a coarse density analysis).
    2. **Relax** — ``relax`` passes of Lloyd's iteration: every *added* point
       slides to the centroid of its Voronoi cell (the midpoint of the patches
       surrounding it), with the existing chart and the chosen sets held fixed.
       This turns the blue-noise seed into a balanced, centroidal fill — new
       patches sit at the midpoints of the empty space, the analysis re-done
       each pass — instead of an unorganised scatter.

    The centroid of a cell is the mean of the in-cube samples nearest that point,
    so added points stay within 0..100 and away from the fixed patches (no
    near-duplicates). Returns ``[]`` if the program already meets ``total``.
    """
    import numpy as np

    total = int(total)
    pts = [(float(p[0]), float(p[1]), float(p[2])) for p in existing]
    n_add = total - len(pts)
    if n_add <= 0:
        return []
    rng = np.random.default_rng(seed)
    fixed = np.array(pts, dtype=float) if pts else np.empty((0, 3))

    # 1. Blue-noise seeding — drop each point into the current sparsest region.
    arr = fixed.copy()
    added = np.empty((n_add, 3), dtype=float)
    for i in range(n_add):
        cand = rng.uniform(0.0, 100.0, size=(max(1, candidates), 3))
        if len(arr):
            d2 = ((cand[:, None, :] - arr[None, :, :]) ** 2).sum(2).min(axis=1)
            pick = cand[int(np.argmax(d2))]
        else:
            pick = cand[0]
        added[i] = pick
        arr = np.vstack([arr, pick[None, :]])

    # 2. Lloyd relaxation — settle each added point onto its cell centroid, with
    # the existing/seeded-from patches fixed, so the fill comes out balanced.
    base = len(fixed)
    # Scale the relaxation passes down for very large fills so a 30k top-up
    # stays bounded; small/typical fills get the full smoothing.
    passes = int(relax) if n_add <= 4000 else max(1, int(relax) * 4000 // n_add)
    if relax > 0 and n_add:
        n_s = min(40000, max(3000, 40 * n_add))
        for _ in range(passes):
            sites = np.vstack([fixed, added]) if base else added
            samp = rng.uniform(0.0, 100.0, size=(n_s, 3))
            owner = _nearest_site(samp, sites)
            # A SEGMENTED MEAN, NOT ONE BOOLEAN SCAN PER POINT. The loop walked
            # the whole owner array once for every added patch, so a 4000-patch
            # fill made 4000 passes over 40,000 samples per relaxation pass.
            # `bincount` does all of them in one. Cells with no samples keep
            # their previous position, exactly as `if len(sel)` did.
            cnt = np.bincount(owner, minlength=len(sites))[base:base + n_add]
            sums = np.empty((n_add, 3), dtype=float)
            for c in range(3):
                sums[:, c] = np.bincount(
                    owner, weights=samp[:, c],
                    minlength=len(sites))[base:base + n_add]
            hit = cnt > 0
            added[hit] = sums[hit] / cnt[hit][:, None]

    return [(float(x), float(y), float(z)) for x, y, z in added]


def fill_gaps_count(existing_count: int, total: int) -> int:
    return max(0, int(total) - int(existing_count))


# ---------------------------------------------------------------------------
# Minimum-distance enforcement — assure real spacing when sets are combined.
# ---------------------------------------------------------------------------
# Unit-ish directions (the 26 neighbours of a cell) used to search for a free
# spot around a patch that's too close to the ones already placed.
_NUDGE_DIRS = tuple((dx, dy, dz)
                    for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
                    if (dx, dy, dz) != (0, 0, 0))


def enforce_min_distance(patches, min_dist: float = 2.0, existing=None):
    """Return ``patches`` (order preserved, count unchanged) with each point
    moved as needed so it sits **at least ``min_dist``** device units (Euclidean,
    on the 0..100 scale) from every point kept before it.

    This is the real "ensure distance" the grid de-duplicator only approximates:
    :func:`deduplicate` guarantees patches land on *distinct cells*, but two
    patches in adjacent cells can still be almost touching. Here points are
    processed strictly in order — any ``existing`` points first (kept fixed,
    never moved), then each patch in turn — and a patch that lands within
    ``min_dist`` of anything already kept is pushed to the nearest free spot
    around it (a small dart-search over the 26 directions at growing radius),
    staying in 0..100. Because earlier points are never disturbed, enabling the
    sets one at a time from the top and spacing each against the ones above gives
    exactly this result (Knut, #78).

    A spatial hash keyed on ``min_dist`` keeps the neighbour test local, so this
    stays fast for the few-thousand-patch programs the generator panel builds.
    """
    if min_dist <= 0:
        return [(_clamp(p[0]), _clamp(p[1]), _clamp(p[2])) for p in patches]
    cell = float(min_dist)
    md2 = min_dist * min_dist
    grid: dict = {}

    def buck(q):
        return (int(q[0] // cell), int(q[1] // cell), int(q[2] // cell))

    def add(q):
        grid.setdefault(buck(q), []).append(q)

    def min_d2(q):
        bx, by, bz = buck(q)
        best = 1e18
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for k in grid.get((bx + dx, by + dy, bz + dz), ()):
                        d2 = ((q[0] - k[0]) ** 2 + (q[1] - k[1]) ** 2
                              + (q[2] - k[2]) ** 2)
                        if d2 < best:
                            best = d2
        return best

    for q in (existing or []):
        add((_clamp(q[0]), _clamp(q[1]), _clamp(q[2])))

    out: list[tuple[float, float, float]] = []
    for p in patches:
        q = (_clamp(p[0]), _clamp(p[1]), _clamp(p[2]))
        if min_d2(q) >= md2:
            add(q)
            out.append(q)
            continue
        best_q, best_d2, found = q, min_d2(q), None
        for rmul in (1.0, 1.5, 2.0, 2.6):
            radius = min_dist * rmul
            for dx, dy, dz in _NUDGE_DIRS:
                ln = math.sqrt(dx * dx + dy * dy + dz * dz)
                cand = (_clamp(q[0] + dx / ln * radius),
                        _clamp(q[1] + dy / ln * radius),
                        _clamp(q[2] + dz / ln * radius))
                d2 = min_d2(cand)
                if d2 >= md2:
                    found = cand
                    break
                if d2 > best_d2:
                    best_d2, best_q = d2, cand
            if found:
                break
        qf = found if found is not None else best_q
        add(qf)
        out.append(qf)
    return out


def _crowding_grid(points, cell: float) -> dict:
    """A spatial hash of ``points`` bucketed on a ``cell``-unit grid, for fast
    "is anything within ``cell``?" tests (the neighbour always lands in one of
    the 27 cells around a query)."""
    g: dict = {}
    for p in points:
        b = (int(_clamp(p[0]) // cell), int(_clamp(p[1]) // cell),
             int(_clamp(p[2]) // cell))
        g.setdefault(b, []).append((_clamp(p[0]), _clamp(p[1]), _clamp(p[2])))
    return g


def _has_within(q, grid: dict, cell: float, md2: float) -> bool:
    bx, by, bz = int(q[0] // cell), int(q[1] // cell), int(q[2] // cell)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for k in grid.get((bx + dx, by + dy, bz + dz), ()):
                    if ((q[0] - k[0]) ** 2 + (q[1] - k[1]) ** 2
                            + (q[2] - k[2]) ** 2) < md2:
                        return True
    return False


def count_too_close(existing, new, min_dist: float = 2.0) -> int:
    """How many of ``new`` sit **within ``min_dist``** (Euclidean device units)
    of any ``existing`` point — i.e. would duplicate *or crowd* a colour already
    there, not just land on the exact same grid cell. Exact duplicates are the
    ``min_dist = 0`` limiting case, so this never flags fewer than an exact-match
    check would (Knut, #78)."""
    if min_dist <= 0:
        return 0
    cell = float(min_dist)
    md2 = min_dist * min_dist
    grid = _crowding_grid(existing, cell)
    return sum(1 for p in new
               if _has_within((_clamp(p[0]), _clamp(p[1]), _clamp(p[2])),
                              grid, cell, md2))


def drop_too_close(existing, new, min_dist: float = 2.0):
    """Return only the ``new`` points that are **clear** of ``existing`` — at
    least ``min_dist`` from every one of them. The ones that would duplicate or
    crowd an existing colour are dropped (the "add only the new ones" path)."""
    if min_dist <= 0:
        return list(new)
    cell = float(min_dist)
    md2 = min_dist * min_dist
    grid = _crowding_grid(existing, cell)
    return [p for p in new
            if not _has_within((_clamp(p[0]), _clamp(p[1]), _clamp(p[2])),
                               grid, cell, md2)]


# ---------------------------------------------------------------------------
# Cross-set de-duplication — keep every patch unique when sets are combined.
# ---------------------------------------------------------------------------
def _dedupe_key(p: tuple[float, float, float], quantum: float) -> tuple[int, int, int]:
    return tuple(int(round(c / quantum)) for c in p)  # type: ignore[return-value]


def deduplicate(
    patches: list[tuple[float, float, float]],
    quantum: float = 0.5,
    step: float = 1.0,
) -> list[tuple[float, float, float]]:
    """Return ``patches`` with near-duplicates nudged apart so each is unique.

    Two patches collide when they round to the same point on a ``quantum``-unit
    grid (device units, 0..100). On a collision the later patch is nudged by a
    growing multiple of ``step`` along rotating channels — toward whichever side
    has room — until it lands on a free cell, staying within 0..100. Input order
    is preserved, so combining e.g. a cube with a grey ramp keeps shared corners
    from being printed twice (GitHub #37 follow-up).
    """
    seen: set[tuple[int, int, int]] = set()
    out: list[tuple[float, float, float]] = []
    for p in patches:
        r, g, b = (_clamp(p[0]), _clamp(p[1]), _clamp(p[2]))
        key = _dedupe_key((r, g, b), quantum)
        tries = 0
        while key in seen and tries < 600:
            ch = tries % 3
            delta = step * (1 + tries // 3)
            base = (r, g, b)[ch]
            cand = base + delta if base + delta <= 100.0 else base - delta
            nud = [r, g, b]
            nud[ch] = _clamp(cand)
            r, g, b = nud
            key = _dedupe_key((r, g, b), quantum)
            tries += 1
        seen.add(key)
        out.append((r, g, b))
    return out


def white_black(count: int = 1, have_white: int = 0,
                have_black: int = 0) -> list[tuple[float, float, float]]:
    """``count`` pure-white + ``count`` pure-black anchors, *minus* any already
    present (``have_white`` / ``have_black``) so the chart ends up with exactly
    ``count`` of each.

    Both matter for a good profile (the media white point and the maximum
    black). The copies are deliberately identical — e.g. to average several
    readings of paper white — so this set is meant to be appended *after*
    de-duplication and left out of it. Whatever the other sets (3D cube, greys
    ramp, saturated edges) already contribute counts toward ``count``."""
    count = max(0, int(count))
    whites = max(0, count - max(0, int(have_white)))
    blacks = max(0, count - max(0, int(have_black)))
    return [(100.0, 100.0, 100.0)] * whites + [(0.0, 0.0, 0.0)] * blacks


def white_black_count(count: int = 1, have_white: int = 0,
                      have_black: int = 0) -> int:
    count = max(0, int(count))
    return (max(0, count - max(0, int(have_white)))
            + max(0, count - max(0, int(have_black))))


def count_white_black(patches, quantum: float = 0.5) -> tuple[int, int]:
    """``(pure_white, pure_black)`` — how many of each ``patches`` already holds
    (on the same grid :func:`deduplicate` uses)."""
    wk = _dedupe_key((100.0, 100.0, 100.0), quantum)
    bk = _dedupe_key((0.0, 0.0, 0.0), quantum)
    w = b = 0
    for p in patches:
        k = _dedupe_key((_clamp(p[0]), _clamp(p[1]), _clamp(p[2])), quantum)
        if k == wk:
            w += 1
        elif k == bk:
            b += 1
    return w, b


def overlap_count(existing, new, quantum: float = 0.5) -> int:
    """How many of ``new`` land on a cell already occupied by ``existing`` (on
    the same ``quantum``-unit grid :func:`deduplicate` uses) — i.e. how many
    would be printed twice if appended to a chart that already holds
    ``existing``."""
    seen = {_dedupe_key((_clamp(p[0]), _clamp(p[1]), _clamp(p[2])), quantum)
            for p in existing}
    return sum(_dedupe_key((_clamp(p[0]), _clamp(p[1]), _clamp(p[2])), quantum)
               in seen for p in new)


def dedupe_against(existing, new, quantum: float = 0.5,
                   step: float = 1.0) -> list[tuple[float, float, float]]:
    """Return ``new`` with any patch that collides with ``existing`` (or with
    another ``new`` patch) nudged to a free cell — ``existing`` is left
    untouched. Order and count of ``new`` are preserved, so it can be appended
    to a chart already holding ``existing`` without printing any colour twice."""
    merged = deduplicate(list(existing) + list(new), quantum, step)
    return merged[len(existing):]


def only_new(existing, new, quantum: float = 0.5) -> list[tuple[float, float, float]]:
    """Return only the ``new`` patches that aren't already in ``existing`` —
    the repeats are dropped rather than relocated, so the result is shorter."""
    seen = {_dedupe_key((_clamp(p[0]), _clamp(p[1]), _clamp(p[2])), quantum)
            for p in existing}
    return [p for p in new
            if _dedupe_key((_clamp(p[0]), _clamp(p[1]), _clamp(p[2])), quantum)
            not in seen]
