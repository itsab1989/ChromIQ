"""Derive a **dense-grid** chart's patch geometry from its rendered TIFF page(s).

This is the i1Profiler counterpart to :mod:`workflow.layout_from_render`. That
module segments a *printtarg* chart — strips of patches separated by spacers,
described by a ``.ti2``. i1Profiler charts are the opposite shape: a single
**zero-gap grid** filled **column-major**, with no strips, no spacers and no
``.ti2`` we can trust (i1Profiler ignores the per-patch positions a ``.pwxf``
carries and re-lays the grid itself — verified in #120). So this module works
from the two things ChromIQ *does* hold: the rendered chart i1Profiler saved as
a TIFF, and the **ordered patch list** ChromIQ exported to i1Profiler.

## What i1Profiler's layout is (reverse-engineered in #120)

Given ``N`` patches, patch size ``pw × ph`` mm and a page, i1Profiler builds a
single logical grid of ``cols`` columns × ``rows_total`` rows
(``cols = floor(usable_width / pw)``, ``rows_total = ceil(N / cols)``), fills it
**column-major in list order** (``index = col*rows_total + row_global``), and
splits it into pages of a fixed row count, **balanced** across pages (a 50-row
grid over 2 pages is 25 + 25, not 20 + 20 + 10). Patch ``i`` of the exported
list therefore lands at:

    col        = i // rows_total
    row_global = i %  rows_total
    page       = row_global // rows_per_page
    row_on_page= row_global %  rows_per_page

Multi-page charts save as **separate** TIFF files (``…_1_2.tif``), not one
multi-frame file, so *tiff_paths* is the pages in print order.

## How this module recovers it

The grid is not assumed. Each page's patch block is located by masking to the
exported patch colours (i1Profiler renders device values byte-exact — no colour
transform on save), its column/row boundaries are read off the projection of
colour edges (every internal line is a real edge here, because column-major
neighbours are always different colours), and each cell is then **colour-checked
against the patch the fill rule predicts for it**. Any mismatch — a shifted
grid, a wrong column count, the wrong page order — raises
:class:`GridGeometryError` rather than emit a silently misregistered target
(correct-or-absent, the same policy as :mod:`workflow.layout_from_render`).

The result is the same scanner-layout block
``{"engine": "derived", "patches": [{loc, page, x, y, w, h}, …], "dpi": …,
"paper_mm": …}`` that :mod:`workflow.scanin_target` already consumes, so the
``.cht``/``.cie`` build and the whole scanin pipeline work unchanged.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


class GridGeometryError(ValueError):
    """The render could not be segmented into the expected dense patch grid, or
    a cell's colour did not match the patch the fill rule predicts — no
    geometry is produced (correct-or-absent)."""


# Colour-jump threshold (8-bit channel delta) that marks a cell edge, and the
# fraction of the block span a projection line must jump over to count as a grid
# boundary. Patch fills are flat, so real boundaries jump far more than this.
_EDGE_DELTA = 20
_BOUNDARY_FRACTION = 0.5
# Per-channel tolerance of a cell's interior median vs round(device/100*255).
# i1Profiler writes the device value verbatim; more than rounding slack means
# the cell is not that patch.
_TOL = 4
_UNIFORM_STD = 3.0
# Shrink each cell this fraction per side before sampling its interior, clear of
# any anti-aliased edge pixels.
_SHRINK = 0.30


def _load_page(path: Path) -> tuple[np.ndarray, float]:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(path)
    dpi = im.info.get("dpi")
    if not dpi or not dpi[0]:
        raise GridGeometryError(
            f"{path.name} carries no resolution (dpi) tag, so its patches "
            "cannot be placed in millimetres. Re-save the chart from "
            "i1Profiler as a TIFF (it stores the dpi).")
    arr = np.asarray(im.convert("RGB")).astype(np.int16)
    return arr, float(dpi[0])


def _rgb100_to_key8(rgb100: np.ndarray) -> np.ndarray:
    """(N,3) device values 0..100 → (N,) packed 8-bit colour keys."""
    v = np.round(np.clip(rgb100, 0, 100) / 100.0 * 255.0).astype(np.int64)
    return (v[:, 0] << 16) | (v[:, 1] << 8) | v[:, 2]


#: The page's own colours: i1Profiler draws its chart on white paper with black
#: frame marks. A patch set that holds paper white or black (almost every real
#: one does) shares them, so they cannot say where the patch BLOCK is.
_PAGE_KEYS = np.array([0xFFFFFF, 0x000000], dtype=np.int64)


def _block_bbox(img: np.ndarray, patch_keys: np.ndarray) -> tuple[int, int, int, int]:
    """Bounding box of the pixels whose colour is one of the exported patch
    colours — the patch block, excluding the page's registration furniture
    (a thin frame + marks).

    Pure white and pure black are left out of this search: they are the
    page's paper and its marks too, and counting them made the "block" the
    whole page, so a correct i1Profiler chart was refused whenever its patch
    set held white or black (2026-10-26). Only the box is found this way;
    every cell, white and black ones included, is still colour-checked
    afterwards. A set holding nothing else keeps the old search."""
    h, w = img.shape[:2]
    key = (img[:, :, 0].astype(np.int64) << 16) | \
          (img[:, :, 1].astype(np.int64) << 8) | img[:, :, 2].astype(np.int64)
    own = patch_keys[~np.isin(patch_keys, _PAGE_KEYS)]
    mask = np.isin(key, own if own.size else patch_keys)
    ys, xs = np.where(mask)
    if xs.size == 0:
        raise GridGeometryError(
            "none of the exported patch colours were found on the page — is "
            "this the chart for this patch set?")
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _cluster(xs: np.ndarray) -> list[int]:
    out: list[list[int]] = []
    for x in xs.tolist():
        if out and x - out[-1][-1] <= 2:
            out[-1].append(x)
        else:
            out.append([x])
    return [int(round(sum(c) / len(c))) for c in out]


def _boundaries(img: np.ndarray, bbox, axis: int) -> list[int]:
    """Grid-line positions along *axis* (0 = rows/horizontal lines, 1 =
    columns/vertical lines) within *bbox*, as clustered edge peaks."""
    x0, y0, x1, y1 = bbox
    core = img[y0:y1, x0:x1]
    if axis == 1:                                   # vertical lines: Δ across x
        d = np.abs(np.diff(core, axis=1)).max(axis=2)
        frac = (d > _EDGE_DELTA).mean(axis=0)
        base = x0
    else:                                           # horizontal lines: Δ down y
        d = np.abs(np.diff(core, axis=0)).max(axis=2)
        frac = (d > _EDGE_DELTA).mean(axis=1)
        base = y0
    peaks = np.where(frac > _BOUNDARY_FRACTION)[0]
    return [base + p for p in _cluster(peaks)]


def _uniform_grid(lo: float, hi: float, n: int) -> list[float]:
    pitch = (hi - lo) / n
    return [lo + pitch * i for i in range(n + 1)]


def _fit_count(edges: list[int], lo: int, hi: int) -> int | None:
    """Number of equal cells between *lo* and *hi* that the detected *edges*
    confirm: try each plausible count, keep the one whose uniform boundaries are
    all matched by a real edge (±2 px). Returns None if none fit."""
    span = hi - lo
    if span < 2 or len(edges) < 2:
        return None
    ev = np.asarray(edges, dtype=float)
    best_n, best_hits = None, 0.0
    # A cell can't be narrower than a few px; cap the search accordingly.
    for n in range(1, span // 3 + 1):
        grid = np.asarray(_uniform_grid(lo, hi, n))
        hits = sum(1 for g in grid if np.min(np.abs(ev - g)) <= 2.0)
        frac = hits / (n + 1)
        # Prefer the finest grid that every interior line confirms.
        if frac >= 0.9 and n > (best_n or 0):
            best_n, best_hits = n, frac
    return best_n


def _cell_ok(img: np.ndarray, x0, x1, y0, y1, want8) -> bool:
    w, h = x1 - x0, y1 - y0
    ix0, ix1 = int(round(x0 + w * _SHRINK)), int(round(x1 - w * _SHRINK))
    iy0, iy1 = int(round(y0 + h * _SHRINK)), int(round(y1 - h * _SHRINK))
    inner = img[iy0:iy1, ix0:ix1].reshape(-1, 3).astype(float)
    if inner.size == 0:
        return False
    if inner.std(axis=0).max() > _UNIFORM_STD:
        return False
    return bool(np.abs(np.median(inner, axis=0) - want8).max() <= _TOL)


def _cell_is_blank(img: np.ndarray, x0, x1, y0, y1) -> bool:
    w, h = x1 - x0, y1 - y0
    ix0, ix1 = int(round(x0 + w * _SHRINK)), int(round(x1 - w * _SHRINK))
    iy0, iy1 = int(round(y0 + h * _SHRINK)), int(round(y1 - h * _SHRINK))
    inner = img[iy0:iy1, ix0:ix1].reshape(-1, 3)
    return bool(inner.size and inner.min() >= 245)


def derive_grid_layout(tiff_paths: list, patch_rgb100, locs=None) -> dict:
    """Segment i1Profiler's saved chart page(s) into the exported patch grid and
    return the scanner-layout block (see the module docstring).

    *tiff_paths* are the pages in print order; *patch_rgb100* is the exported
    patch list as an ``(N, 3)`` array/sequence of device values 0..100, **in the
    order it was handed to i1Profiler** (= i1Profiler's column-major fill order);
    *locs* are the per-patch location labels (default ``"1"…"N"``, matching the
    ``SampleID`` a ``txt2ti3`` measurement carries). Raises
    :class:`GridGeometryError` unless every patch is found AND colour-verified.
    """
    rgb100 = np.asarray(patch_rgb100, dtype=float)
    if rgb100.ndim != 2 or rgb100.shape[1] != 3:
        raise GridGeometryError("patch_rgb100 must be an (N, 3) array of RGB")
    n_patches = len(rgb100)
    if locs is None:
        locs = [str(i + 1) for i in range(n_patches)]
    if len(locs) != n_patches:
        raise GridGeometryError("locs and patch_rgb100 length differ")
    want8 = np.round(rgb100 / 100.0 * 255.0)
    patch_keys = np.unique(_rgb100_to_key8(rgb100))
    n_pages = len(tiff_paths)
    if n_pages < 1:
        raise GridGeometryError("no TIFF pages given")

    # Load every page and find its patch block (the exported colours, masking
    # off the registration furniture around it).
    loaded: list[tuple[np.ndarray, tuple]] = []
    dpi_seen: float | None = None
    paper_mm: list[float] | None = None
    for pno, path in enumerate(tiff_paths):
        img, dpi = _load_page(Path(path))
        if dpi_seen is None:
            dpi_seen = dpi
            paper_mm = [round(img.shape[1] / dpi * 25.4, 1),
                        round(img.shape[0] / dpi * 25.4, 1)]
        elif abs(dpi - dpi_seen) > 0.5:
            raise GridGeometryError("the TIFF pages disagree on resolution (dpi)")
        loaded.append((img, _block_bbox(img, patch_keys)))

    # The column count is found by SEARCH, not by edge detection: down a column
    # the fill lays consecutive list entries, so a smooth ramp leaves no visible
    # boundary between rows — and a modular patch set can even hide the column
    # boundaries. Instead every plausible column count is tried and the one whose
    # WHOLE grid colour-matches the exported patches (under the #120 column-major
    # fill) is kept. A wrong count mismatches within the first few cells, so this
    # is cheap; a wrong count cannot pass, so it is safe.
    _img0, (x0, y0, x1, y1) = loaded[0]
    block_w = x1 - x0
    # An edge-detected column count, if the render offers one, is tried first so
    # the common case doesn't scan — but it is accepted only if it verifies.
    hint = _fit_count(_boundaries(_img0, loaded[0][1], axis=1), x0, x1)
    order = ([hint] if hint else []) + [
        c for c in range(2, block_w // 4 + 1) if c != hint]

    for cols in order:
        rows_total = math.ceil(n_patches / cols)
        rows_per_page = math.ceil(rows_total / n_pages)
        # Every page must be needed and covered by this (cols, page) split.
        if math.ceil(rows_total / rows_per_page) != n_pages:
            continue
        built = _build_grid(loaded, cols, rows_total, rows_per_page,
                            n_patches, want8, locs, (x0, y0, x1, y1))
        if built is not None:
            log.info("Derived i1Profiler grid geometry: %d patches, %d "
                     "column(s) x %d row(s) over %d page(s)",
                     n_patches, cols, rows_total, n_pages)
            return {"engine": "derived", "patches": built,
                    "dpi": int(round(dpi_seen)), "paper_mm": paper_mm}

    raise GridGeometryError(
        "could not line a regular patch grid up with this chart — the render "
        "does not look like the i1Profiler chart for this patch set (wrong "
        "file, wrong patch set, or a colour-managed/edited copy).")


def _build_grid(loaded, cols, rows_total, rows_per_page, n_patches, want8,
                locs, block) -> list[dict] | None:
    """Place and colour-verify every cell of a *cols*-wide column-major grid.
    Returns the patch rects, or None on the first cell that does not match (so
    the caller moves on to the next candidate column count). The grid origin and
    pitch are shared from page 1's *block* — constant margins mean a partial
    last page is placed from the same origin, not its own short block."""
    x0, y0, x1, y1 = block
    col_pitch = (x1 - x0) / cols
    row_pitch = (y1 - y0) / rows_per_page
    patches: list[dict] = []
    for pno, (img, _bbox) in enumerate(loaded):
        for c in range(cols):
            for r in range(rows_per_page):
                row_global = pno * rows_per_page + r
                if row_global >= rows_total:
                    continue                      # below the grid on this page
                idx = c * rows_total + row_global
                cx0 = x0 + c * col_pitch
                cy0 = y0 + r * row_pitch
                cx1, cy1 = cx0 + col_pitch, cy0 + row_pitch
                if idx >= n_patches:
                    if not _cell_is_blank(img, cx0, cx1, cy0, cy1):
                        return None               # ink where the grid ended
                    continue
                if not _cell_ok(img, cx0, cx1, cy0, cy1, want8[idx]):
                    return None
                patches.append({
                    "loc": locs[idx], "page": pno,
                    "x": round(float(cx0), 1), "y": round(float(cy0), 1),
                    "w": round(float(col_pitch), 1),
                    "h": round(float(row_pitch), 1),
                })
    return patches if len(patches) == n_patches else None
