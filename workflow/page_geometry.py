"""Page-geometry helpers: PPD media dimensions, orientation, mismatch detection.

Used by the print chart tab to auto-pick CUPS orientation-requested, warn the
user when their selected PageSize does not match the TIFF that printtarg
generated, and feed exact dimensions to PostScript setpagedevice so the PS
document and `lp -o PageSize=...` agree.
"""
from __future__ import annotations

import pathlib
import re
from pathlib import Path

import tifffile

from core.logger import get_logger
from core.text_io import read_text

log = get_logger(__name__)

_PT_PER_INCH = 72.0

# CUPS orientation-requested values (RFC 2911 / PWG)
ORIENTATION_PORTRAIT = 3
ORIENTATION_LANDSCAPE = 4

# Tolerances
_ASPECT_TOL = 0.02   # 2% — treat aspects within this band as "same orientation"
# When we know the printer's printable area (from the PPD) the chart raster
# should land inside it closely; allow a small band for printtarg's own margin.
_FIT_TOL_IMAGEABLE = 0.04
# Without that info we can only compare to the full sheet, which always loses
# the printer's hardware margins, so the band has to be much wider.
_FIT_TOL_PAPER = 0.08


def get_page_size_points(ppd_path: str | None, value: str) -> tuple[float, float] | None:
    """Return (w_pt, h_pt) for a PageSize *value* declared in *ppd_path*.

    Parses `*PaperDimension <value>: "<w> <h>"` from the PPD file. Returns
    None if the PPD is unavailable or the value is not declared.
    """
    if not ppd_path or not value:
        return None
    try:
        text = read_text(pathlib.Path(ppd_path), lenient=True)
    except OSError:
        return None

    # Match exact value first, then strip common borderless suffixes if needed.
    candidates = [value]
    for suffix in (".Borderless", ".FullBleed", "Borderless", "FullBleed"):
        if value.endswith(suffix):
            candidates.append(value[: -len(suffix)])

    for cand in candidates:
        pattern = re.compile(
            rf'^\*PaperDimension\s+{re.escape(cand)}(?:/[^:]+)?:\s*"([\d.]+)\s+([\d.]+)"',
            re.MULTILINE,
        )
        m = pattern.search(text)
        if m:
            try:
                return float(m.group(1)), float(m.group(2))
            except ValueError:
                continue
    return None


def get_imageable_area_points(ppd_path: str | None, value: str) -> tuple[float, float] | None:
    """Return the printable (w_pt, h_pt) for a PageSize *value* in *ppd_path*.

    Parses `*ImageableArea <value>: "<llx> <lly> <urx> <ury>"` and returns the
    rectangle's width and height (urx-llx, ury-lly).  Returns None if the PPD is
    unavailable or the entry is absent.  This is the closest proxy to what
    `printtarg` actually rasters onto the page (it insets patches by a margin),
    so it makes a more reliable "wrong paper?" check than the full sheet size.
    """
    if not ppd_path or not value:
        return None
    try:
        text = read_text(pathlib.Path(ppd_path), lenient=True)
    except OSError:
        return None

    candidates = [value]
    for suffix in (".Borderless", ".FullBleed", "Borderless", "FullBleed"):
        if value.endswith(suffix):
            candidates.append(value[: -len(suffix)])

    for cand in candidates:
        pattern = re.compile(
            rf'^\*ImageableArea\s+{re.escape(cand)}(?:/[^:]+)?:\s*'
            r'"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"',
            re.MULTILINE,
        )
        m = pattern.search(text)
        if m:
            try:
                llx, lly, urx, ury = (float(g) for g in m.groups())
            except ValueError:
                continue
            w, h = urx - llx, ury - lly
            if w > 0 and h > 0:
                return w, h
    return None


def read_tiff_dimensions_points(tiff_path: Path, fallback_dpi: float = 300.0) -> tuple[float, float]:
    """Return the TIFF's first page (w_pt, h_pt) using its XResolution tag.

    Shares the same DPI-extraction logic as PostScriptGenerator so the two
    callers can't disagree about page dimensions.
    """
    with tifffile.TiffFile(str(tiff_path)) as tif:
        page = tif.pages[0]
        dpi = _read_dpi(page, fallback_dpi)
        shape = page.shape
    # shape is (H, W) or (H, W, C)
    h_px, w_px = shape[0], shape[1]
    return w_px * _PT_PER_INCH / dpi, h_px * _PT_PER_INCH / dpi


def _read_dpi(page: tifffile.TiffPage, fallback: float) -> float:
    """Pixels-per-inch from a TIFF page, honouring its ResolutionUnit.

    ArgyllCMS `printtarg` writes the resolution in pixels-per-*centimetre*
    (ResolutionUnit = 3), so the raw XResolution value (~118 for a 300-dpi
    chart) must be scaled by 2.54 to get DPI — otherwise every derived size
    comes out 2.54× too large.
    """
    tag = page.tags.get("XResolution")
    if tag is None:
        return float(fallback)
    v = tag.value
    if isinstance(v, tuple) and len(v) == 2 and v[1]:
        res = float(v[0]) / float(v[1])
    else:
        try:
            res = float(v)
        except (TypeError, ValueError):
            return float(fallback)
    if res <= 0:
        return float(fallback)

    unit_tag = page.tags.get("ResolutionUnit")
    try:
        unit = int(getattr(unit_tag, "value", 2))
    except (TypeError, ValueError):
        unit = 2
    if unit == 1:          # no absolute unit — XResolution is just an aspect ratio
        return float(fallback)
    if unit == 3:          # pixels per centimetre → pixels per inch
        res *= 2.54
    return res


def compute_orientation(
    tiff_w_pt: float, tiff_h_pt: float,
    page_w_pt: float, page_h_pt: float,
) -> int:
    """Return CUPS orientation-requested (3=portrait, 4=landscape) so the
    TIFF's wide/tall axis matches the page's wide/tall axis.

    Square-ish charts (aspect within ±2%) default to portrait.
    """
    if tiff_w_pt <= 0 or tiff_h_pt <= 0 or page_w_pt <= 0 or page_h_pt <= 0:
        return ORIENTATION_PORTRAIT

    tiff_landscape = tiff_w_pt > tiff_h_pt * (1.0 + _ASPECT_TOL)
    tiff_portrait  = tiff_h_pt > tiff_w_pt * (1.0 + _ASPECT_TOL)
    page_landscape = page_w_pt > page_h_pt * (1.0 + _ASPECT_TOL)
    page_portrait  = page_h_pt > page_w_pt * (1.0 + _ASPECT_TOL)

    # If TIFF is landscape but the selected media is taller-than-wide, rotate.
    if tiff_landscape and page_portrait:
        return ORIENTATION_LANDSCAPE
    # If TIFF is portrait but the selected media is wider-than-tall, rotate.
    if tiff_portrait and page_landscape:
        return ORIENTATION_LANDSCAPE
    return ORIENTATION_PORTRAIT


def check_size_mismatch(
    tiff_w_pt: float, tiff_h_pt: float,
    page_w_pt: float, page_h_pt: float,
    imageable_pt: tuple[float, float] | None = None,
) -> str | None:
    """Return a human-readable warning if the chart doesn't match the selected
    paper after auto-rotation, else None.

    `printtarg` rasters the chart inside the printer's printable area (with its
    own small margin), so when *imageable_pt* (the printable w×h from the PPD)
    is supplied the chart is compared against that with a tight tolerance.
    Otherwise it falls back to comparing against the full sheet with a much
    wider tolerance, because the chart will always be missing the printer's
    hardware margins.  Both chart orientations are tried.
    """
    if tiff_w_pt <= 0 or tiff_h_pt <= 0 or page_w_pt <= 0 or page_h_pt <= 0:
        return None

    def _fits_ref(ref_w: float, ref_h: float, tol: float) -> bool:
        if ref_w <= 0 or ref_h <= 0:
            return False

        def ok(w: float, h: float) -> bool:
            return abs(w - ref_w) / ref_w <= tol and abs(h - ref_h) / ref_h <= tol

        return ok(tiff_w_pt, tiff_h_pt) or ok(tiff_h_pt, tiff_w_pt)

    # The chart is the right paper if it matches EITHER the full sheet (a
    # full-bleed printtarg -M render — ChromIQ's default, so a 210×297 chart on
    # A4 paper must not warn even though it exceeds the printable area, #84) OR
    # the printer's imageable area (an -m render cropped to the printable box).
    # Only when it matches neither has it likely been generated for a different
    # paper size.
    if _fits_ref(page_w_pt, page_h_pt, _FIT_TOL_PAPER):
        return None
    if imageable_pt and _fits_ref(imageable_pt[0], imageable_pt[1], _FIT_TOL_IMAGEABLE):
        return None

    tiff_mm = (tiff_w_pt * 25.4 / _PT_PER_INCH, tiff_h_pt * 25.4 / _PT_PER_INCH)
    page_mm = (page_w_pt * 25.4 / _PT_PER_INCH, page_h_pt * 25.4 / _PT_PER_INCH)
    return (
        f"Possible paper mismatch: the chart raster is "
        f"{tiff_mm[0]:.0f} × {tiff_mm[1]:.0f} mm but the selected paper is "
        f"{page_mm[0]:.0f} × {page_mm[1]:.0f} mm — it may have been generated "
        f"for a different paper size. If you continue, the printer will scale "
        f"or crop it. Regenerate the chart for this paper to be safe."
    )
