"""Derive a chart's exact patch geometry from its rendered TIFF page(s).

Some charts never carry scan-recognition geometry: the prebuilt "by
Pharmacist" built-ins (a bundled render — no targen/printtarg runs at
selection), and printtarg charts whose creation-time ``-s`` capture was
discarded because scan-mode paginates a few tightly-packed layouts differently
(#108 — e.g. ColorMunki double density at ``-a0.91–0.93``). For those the
rendered TIFF itself is the ground truth: every patch is a flat, axis-aligned
rectangle of exactly its ``.ti2`` device colour, laid on a regular grid.

This module segments that grid and assigns each cell its ``.ti2`` SAMPLE_LOC,
refusing on ANY mismatch (correct-or-absent, the same policy as the ``-s``
capture):

* the detected grid must have exactly the ``.ti2``'s strips-per-page
  (``PASSES_IN_STRIPS2``) and steps-per-strip (``STEPS_IN_PASS``) counts;
* every cell's interior must be near-uniform AND match its patch's device RGB
  within the 8-bit quantisation tolerance — a shifted or transposed grid
  cannot pass, because strip neighbours are deliberately distinct colours.

The result is the scanner-layout block ``{"engine": "derived", "patches":
[{loc, page, x, y, w, h}, …], "dpi": …, "paper_mm": …}`` in the same schema as
an engine chart's exact geometry, so :mod:`workflow.scanin_target` builds the
``.cht``/``.cie`` pair from it unchanged.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


class RenderGeometryError(ValueError):
    """The TIFF render could not be segmented into the chart's exact patch
    grid (or the segmentation failed validation) — no geometry is produced."""


_LOC_RE = re.compile(r"^([A-Z]+)(\d+)$")

# Colour-jump threshold (8-bit channel delta) that counts as a patch/spacer
# edge, and the fraction of the probed span that must jump for a projection
# line to count as a grid boundary. Patches are flat fills, so real edges jump
# by far more than this; anti-aliased label glyphs never reach the fraction.
_EDGE_DELTA = 20
_COL_FRACTION = 0.35
_ROW_FRACTION = 0.55
# Interior sampling: shrink each cell this fraction per side before checking
# uniformity + expected colour, clear of the anti-aliased edge pixels.
_SHRINK = 0.28
# Per-channel tolerance vs round(device/100*255). printtarg and the engine
# both write the quantised device value; anything beyond rounding slack means
# the cell is NOT that patch.
_TOL = 3
_UNIFORM_STD = 2.0


def _load_page(path: Path) -> tuple[np.ndarray, float]:
    from PIL import Image
    im = Image.open(path)
    dpi = im.info.get("dpi")
    if not dpi:
        raise RenderGeometryError(f"{path.name} carries no dpi tag")
    arr = np.asarray(im.convert("RGB")).astype(np.int16)
    return arr, float(dpi[0])


def _grid_boundaries(candidates: list[int], n_cells: int, *,
                     axis_len: int) -> list[float] | None:
    """Fit ``n_cells + 1`` equally-spaced boundaries to the candidate edge
    positions. Chart grids are strictly periodic, so we search anchor pairs
    among the candidates and keep the grid that the most candidates confirm;
    at least 60 % of the interior boundaries must be confirmed by a real
    detected edge (±2 px) or the fit is rejected."""
    if len(candidates) < 2 or n_cells < 1:
        return None
    cand = np.asarray(sorted(candidates), dtype=float)
    best, best_hits = None, -1
    for i in range(len(cand)):
        for j in range(len(cand) - 1, i, -1):
            span = cand[j] - cand[i]
            if span < n_cells:          # pitch below 1 px — nonsense
                continue
            pitch = span / n_cells
            grid = cand[i] + pitch * np.arange(n_cells + 1)
            if grid[0] < -2 or grid[-1] > axis_len + 2:
                continue
            hits = sum(1 for g in grid if np.min(np.abs(cand - g)) <= 2.0)
            if hits > best_hits:
                best_hits, best = hits, grid
    if best is None or best_hits < int(0.6 * (n_cells + 1)):
        return None
    return [float(g) for g in best]


def _fit_starts(candidates: list[int], n: int,
                axis_len: int) -> list[list[float]]:
    """Candidate fits of ``n`` patch-start positions to the detected edge
    positions, best first — each fit is the ``n + 1`` cell boundary list (the
    last a virtual end one pitch past the final start).

    Row edges come as spacer top/bottom PAIRS, strips may or may not carry a
    leading/trailing spacer, and printtarg renders round each patch to the
    pixel grid so a long strip drifts against any constant pitch. So: rough
    pitch candidates come from the consecutive-gap structure (a gap, or the
    sum of two neighbouring gaps = patch + spacer); each (anchor, pitch) seed
    is grown by a drift-tolerant walk that snaps every next start to the
    nearest detected edge, then straightened by least squares. A spacer-top
    anchor scores exactly like the true patch-top anchor, so the caller
    validates each returned fit against the expected patch COLOURS and keeps
    the first that matches (the ground truth we hold anyway)."""
    if n < 1 or len(candidates) < 2:
        return []
    cand = np.asarray(sorted(candidates), dtype=float)
    gaps = np.diff(cand)
    rough = [float(g) for g in gaps]
    rough += [float(g1 + g2) for g1, g2 in zip(gaps, gaps[1:])]
    rough = sorted({round(p) for p in rough
                    if 4.0 <= p and p * (n - 1) <= axis_len + 2})
    fits: list[tuple[int, float, list[float]]] = []
    for pitch0 in rough:
        for c in cand:
            if c + pitch0 * (n - 1) > axis_len + 2:
                continue
            # drift-tolerant walk: snap each expected next start to the
            # nearest edge, carrying the correction forward
            pos, pitch = float(c), float(pitch0)
            starts, hits = [pos], 1
            for _ in range(1, n):
                exp = pos + pitch
                j = int(np.argmin(np.abs(cand - exp)))
                if abs(cand[j] - exp) <= 2.5:
                    pos = float(cand[j])
                    hits += 1
                else:
                    pos = exp
                starts.append(pos)
            if hits < max(3, int(0.6 * n)):
                continue
            idx = list(range(n))
            slope, intercept = np.polyfit(idx, starts, 1)
            grid = [float(intercept + slope * i) for i in range(n + 1)]
            fits.append((hits, float(intercept), grid))
    fits.sort(key=lambda t: -t[0])
    out: list[list[float]] = []
    for _hits, phase, grid in fits:
        if any(abs(phase - g[0]) <= 3.0 for g in out):
            continue                      # same anchor family already queued
        out.append(grid)
        if len(out) >= 4:
            break
    return out


def _column_candidates(img: np.ndarray, y0: int, y1: int) -> list[int]:
    core = img[y0:y1 + 1]
    dx = np.abs(np.diff(core, axis=1)).max(axis=2)
    frac = (dx > _EDGE_DELTA).mean(axis=0)
    return _cluster(np.where(frac > _COL_FRACTION)[0])


def _row_candidates(img: np.ndarray, x0: int, x1: int) -> list[int]:
    band = img[:, x0:x1 + 1]
    dy = np.abs(np.diff(band, axis=0)).max(axis=2)
    frac = (dy > _EDGE_DELTA).mean(axis=1)
    return _cluster(np.where(frac > _ROW_FRACTION)[0])


def _cluster(xs: np.ndarray) -> list[int]:
    out: list[list[int]] = []
    for x in xs.tolist():
        if out and x - out[-1][-1] <= 2:
            out[-1].append(x)
        else:
            out.append([x])
    return [int(round(sum(c) / len(c))) for c in out]


def _ink_rows(img: np.ndarray) -> tuple[int, int]:
    """First/last row carrying a solid run of ink (the patch block, give or
    take furniture) — used only to focus the column projection. The cut is
    adaptive (half the densest row) so a patch block narrower than the page
    still bounds correctly, while label/title text rows stay excluded."""
    nonwhite = (img.min(axis=2) < 240)
    frac = nonwhite.mean(axis=1)
    thresh = max(0.02, 0.5 * float(frac.max()))
    rows = np.where(frac >= thresh)[0]
    if not len(rows):
        raise RenderGeometryError("page appears blank")
    return int(rows[0]), int(rows[-1])


def _strip_index(letters: str) -> int:
    """Physical column index of a strip letter key under the default
    ``A-Z, A-Z`` pattern (bijective base 26 — A=0 … Z=25, AA=26, AB=27 …)."""
    v = 0
    for c in letters:
        v = v * 26 + (ord(c) - ord("A") + 1)
    return v - 1


def parse_ti2_strips(ti2_path: str | Path):
    """The chart's strip structure from its ``.ti2``: an ordered list of
    ``(loc_list, rgb_list)`` per strip (loc order = top→bottom within the
    strip) plus the strips-per-page split. The file rows come in the
    randomised patch order, so the PHYSICAL strip order is recovered from the
    loc letters (``A-Z, A-Z`` pattern — leftmost strip = A). A chart with a
    custom strip pattern simply fails colour validation downstream."""
    from workflow.ti3_analysis import parse_ti3
    data = parse_ti3(ti2_path)
    if not data.sample_locs or data.rgb is None or not len(data.rgb):
        raise RenderGeometryError("the .ti2 has no SAMPLE_LOC / RGB data")
    strips: dict = {}
    # The chart's own labels place each location (#182 5965589190): a chart
    # numbered by strip and lettered by patch is read as surely as "A12".
    from workflow.layout_engine.labels import labels_for_chart, location_key
    cl = labels_for_chart(ti2_path)
    for loc, rgb in zip(data.sample_locs, data.rgb):
        key = location_key(cl, loc)
        if key is not None:
            strips.setdefault((0, key[0]), []).append((key[1], loc, rgb))
            continue
        m = _LOC_RE.match(loc)
        if not m:
            raise RenderGeometryError(f"unparseable patch location {loc!r}")
        strips.setdefault((1, _strip_index(m.group(1))), []).append(
            (int(m.group(2)), loc, rgb))
    per_strip = []
    for key in sorted(strips):
        rows = sorted(strips[key])
        per_strip.append(([loc for _, loc, _ in rows],
                          [rgb for _, _, rgb in rows]))
    pp = data.keywords.get("PASSES_IN_STRIPS2", "")
    page_split = [int(x) for x in pp.split(",") if x.strip()] if pp else \
        [len(per_strip)]
    if sum(page_split) != len(per_strip):
        raise RenderGeometryError(
            f"PASSES_IN_STRIPS2 {pp!r} does not cover the {len(per_strip)} "
            "strips in the .ti2")
    return per_strip, page_split


def _expected_rgb8(rgb100: np.ndarray) -> np.ndarray:
    return np.round(np.asarray(rgb100, dtype=float) / 100.0 * 255.0)


def _validate_cell(img: np.ndarray, x0: float, x1: float, y0: float, y1: float,
                   want8: np.ndarray, loc: str) -> None:
    w, h = x1 - x0, y1 - y0
    ix0 = int(round(x0 + w * _SHRINK)); ix1 = int(round(x1 - w * _SHRINK))
    iy0 = int(round(y0 + h * _SHRINK)); iy1 = int(round(y1 - h * _SHRINK))
    inner = img[iy0:iy1, ix0:ix1].reshape(-1, 3).astype(float)
    if inner.size == 0:
        raise RenderGeometryError(f"patch {loc}: degenerate cell")
    med = np.median(inner, axis=0)
    if inner.std(axis=0).max() > _UNIFORM_STD:
        raise RenderGeometryError(
            f"patch {loc}: cell interior is not a flat colour fill "
            f"(std {inner.std(axis=0).max():.1f})")
    if np.abs(med - want8).max() > _TOL:
        raise RenderGeometryError(
            f"patch {loc}: rendered colour {med.astype(int).tolist()} does not "
            f"match the .ti2 device value {want8.astype(int).tolist()}")


def derive_layout_from_render(tiff_paths: list, ti2_path: str | Path) -> dict:
    """Segment the rendered page(s) into the ``.ti2``'s exact patch grid and
    return the scanner-layout block (see module docstring). *tiff_paths* must
    be the pages in print order. Raises :class:`RenderGeometryError` unless
    every patch is found AND colour-verified."""
    per_strip, page_split = parse_ti2_strips(ti2_path)
    if len(tiff_paths) != len(page_split):
        raise RenderGeometryError(
            f"{len(tiff_paths)} TIFF page(s) but the .ti2 lays out "
            f"{len(page_split)} page(s)")

    patches: list[dict] = []
    strips_out: list[dict] = []
    dpi_seen: float | None = None
    paper_mm: list[float] | None = None
    strip_idx = 0
    for page, (path, n_strips) in enumerate(zip(tiff_paths, page_split)):
        img, dpi = _load_page(Path(path))
        if dpi_seen is None:
            dpi_seen = dpi
            paper_mm = [round(img.shape[1] / dpi * 25.4, 1),
                        round(img.shape[0] / dpi * 25.4, 1)]
        elif abs(dpi - dpi_seen) > 0.5:
            raise RenderGeometryError("pages disagree on dpi")

        y0, y1 = _ink_rows(img)
        cols = _grid_boundaries(_column_candidates(img, y0, y1), n_strips,
                                axis_len=img.shape[1])
        if cols is None:
            raise RenderGeometryError(
                f"page {page + 1}: could not fit {n_strips} strip columns")
        page_strips = per_strip[strip_idx:strip_idx + n_strips]
        strip_idx += n_strips
        for s, (locs, rgbs) in enumerate(page_strips):
            sx0, sx1 = cols[s], cols[s + 1]
            n = len(locs)
            fits = _fit_starts(
                _row_candidates(img, int(sx0) + 3, int(sx1) - 3), n,
                axis_len=img.shape[0])
            if not fits:
                raise RenderGeometryError(
                    f"page {page + 1} strip {s + 1}: could not fit {n} patch "
                    "rows")
            # Try each candidate fit; the first whose EVERY cell passes the
            # colour check wins (a spacer-top anchored fit fails on cell 1).
            last_err: RenderGeometryError | None = None
            strip_patches: list[dict] | None = None
            for rows in fits:
                try:
                    strip_patches = _validated_strip(
                        img, sx0, sx1, rows, locs, rgbs, page)
                    break
                except RenderGeometryError as exc:
                    last_err = exc
            if strip_patches is None:
                raise last_err if last_err is not None else \
                    RenderGeometryError(
                        f"page {page + 1} strip {s + 1}: no valid fit")
            patches.extend(strip_patches)
            # Strip rect for the measure-tab overlay (same schema the engine
            # stores): the full column from first to last verified patch.
            tops = [p["y"] for p in strip_patches]
            bots = [p["y"] + p["h"] for p in strip_patches]
            strips_out.append({
                "page": page, "x": int(round(sx0)),
                "y": int(round(min(tops))),
                "w": int(round(sx1 - sx0)),
                "h": int(round(max(bots) - min(tops))),
            })
    seen = [p["loc"] for p in patches]
    if len(set(seen)) != len(seen):
        raise RenderGeometryError("duplicate patch locations after assignment")
    log.info("Derived exact geometry from render: %d patches on %d page(s)",
             len(patches), len(tiff_paths))
    return {"engine": "derived", "patches": patches, "strips": strips_out,
            "dpi": int(round(dpi_seen)), "paper_mm": paper_mm}


def _validated_strip(img: np.ndarray, sx0: float, sx1: float,
                     rows: list[float], locs: list[str], rgbs: list,
                     page: int) -> list[dict]:
    """Validate one strip under a row fit and return its patch dicts, raising
    :class:`RenderGeometryError` on the first cell that fails. The row grid
    spans patch+spacer PITCH cells; the spacer share is trimmed off by colour
    before the strict check."""
    out: list[dict] = []
    for i, (loc, rgb) in enumerate(zip(locs, rgbs)):
        want8 = _expected_rgb8(rgb)
        ty0, ty1 = _trim_to_colour(img, sx0, sx1, rows[i], rows[i + 1], want8)
        _validate_cell(img, sx0, sx1, ty0, ty1, want8, loc)
        out.append({
            "loc": loc, "page": page,
            "x": round(float(sx0), 1), "y": round(float(ty0), 1),
            "w": round(float(sx1 - sx0), 1),
            "h": round(float(ty1 - ty0), 1),
        })
    return out


def _trim_to_colour(img: np.ndarray, x0: float, x1: float, y0: float,
                    y1: float, want8: np.ndarray) -> tuple[float, float]:
    """Shrink a pitch cell (patch + its share of spacer) to the patch proper:
    drop top/bottom pixel rows whose row-median differs from the expected
    colour. At most 35 % of the cell may be trimmed per side — beyond that the
    cell simply isn't this patch, and validation will say so."""
    ix0, ix1 = int(round(x0 + (x1 - x0) * 0.25)), int(round(x1 - (x1 - x0) * 0.25))
    iy0, iy1 = int(round(y0)), int(round(y1))
    band = img[iy0:iy1, ix0:ix1].astype(float)
    if band.size == 0:
        return y0, y1
    ok = (np.abs(np.median(band, axis=1) - want8).max(axis=1) <= _TOL)
    limit = max(1, int(0.35 * len(ok)))
    top = 0
    while top < limit and not ok[top]:
        top += 1
    bot = 0
    while bot < limit and not ok[len(ok) - 1 - bot]:
        bot += 1
    return float(iy0 + top), float(iy1 - bot)
