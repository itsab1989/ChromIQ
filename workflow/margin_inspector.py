"""Measure the realised page margins of a rendered chart preview.

The *patch area* is the block of patches and spacers printtarg lays out on the
sheet — **not** the strip-label band (A B C…), the rotated "ArgyllCMS…" title
down the right margin, nor any page label. Those are text outside the patch
area and are deliberately ignored (the i1Pro/jig only cares about where the
patches/spacers sit and how much white run-up surrounds them).

A *margin* is the white gap between a paper edge and the nearest patch or
spacer, on each of the four sides. Because printtarg only exposes a single
uniform ``-m`` margin (plus a fixed 26 mm i1Pro left clip border), the realised
per-side margins are an **output** of the whole layout — patch scale, spacer
size, ``-m``/``-M``, ``-L``, strip-length limit, paper size and orientation all
contribute. The only reliable way to know them is to measure the rendered page,
which is what this module does.

All values are reported in the **printtarg (TIFF) orientation** — i.e. exactly
what the preview shows. The jig is rotated 90° relative to this; that mapping is
explained in the startup help, not encoded here.

The patch-area bounding box is recovered with the same single-render geometry
the editor and Measure tab already use (:func:`workflow.ti2_relayout._patch_grid_bbox`),
so no black-and-white twin render is needed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from core.logger import get_logger
from core.strip_utils import parse_passes_per_page
from workflow.ti2_relayout import _imread_rgb, _patch_grid_bbox

log = get_logger(__name__)

_MM_PER_INCH = 25.4
_DEFAULT_DPI = 300.0
_WHITE = 240            # luminance ≥ this = bare paper (matches _patch_grid_bbox)
_PATCH_ROW_FILL = 0.5   # a dense patch row is ≥50% inked across the patch x-band
_PATCH_EDGE_FILL = 0.2  # a zig-zag half-row (≈half the strips) still counts as
                        # patch area when contiguous with the dense block (#91)


@dataclass(frozen=True)
class MarginReport:
    """Realised margins of one rendered page, in millimetres (printtarg frame).

    ``left/right/top/bottom`` are the white gaps from each paper edge to the
    patch area. ``strip_width_mm`` is the patch width across a strip. ``strip_
    length_mm`` is the patch-block extent along the reading direction (page
    height − top − bottom on a portrait page) — useful for the i1Pro jig's
    240 mm max strip length. ``page_w_mm`` / ``page_h_mm`` are the full sheet.
    """

    left_mm: float
    right_mm: float
    top_mm: float
    bottom_mm: float
    strip_width_mm: Optional[float]
    page_w_mm: float
    page_h_mm: float
    strip_length_mm: Optional[float] = None
    #: Resolution (px/inch) of the raster these margins were read off, when it
    #: is known. A chart is drawn on a pixel grid and every edge of it is
    #: rounded to a whole pixel, so no margin can be realised — or measured —
    #: more finely than 25.4/dpi mm; :func:`check_violations` needs that number
    #: to know how small a shortfall is meaningless (#167). ``None`` = unknown,
    #: which keeps the old fixed allowance.
    dpi: Optional[float] = None

    def as_dict(self) -> dict[str, float | None]:
        return {
            "L": self.left_mm, "R": self.right_mm,
            "T": self.top_mm, "B": self.bottom_mm,
            "strip": self.strip_width_mm, "strip_len": self.strip_length_mm,
        }


@dataclass(frozen=True)
class Violation:
    """One margin that fell below its configured minimum threshold."""

    edge: str           # "Left" | "Right" | "Top" | "Bottom"
    measured_mm: float
    threshold_mm: float


# edge label → MarginReport attribute + threshold-dict key
_EDGES = (
    ("Left", "left_mm", "L"),
    ("Right", "right_mm", "R"),
    ("Top", "top_mm", "T"),
    ("Bottom", "bottom_mm", "B"),
)


def check_violations(
    report: MarginReport, thresholds: dict | None,
) -> list[Violation]:
    """Edges whose measured margin is below the per-edge minimum threshold.

    ``thresholds`` is a ``{"L":mm, "R":mm, "T":mm, "B":mm, "desc":…}`` mapping
    (the entry for this chart's instrument+paper+orientation combo), or ``None``
    when no thresholds are defined for the combo — in which case nothing is
    checked (the inspector still shows the measured values). Thresholds are
    minimums to meet-or-exceed; there is no upper bound.
    """
    if not thresholds:
        return []
    tol = _tolerance_mm(report)
    out: list[Violation] = []
    for label, attr, key in _EDGES:
        raw = thresholds.get(key)
        if raw in (None, ""):
            continue
        try:
            thr = float(raw)
        except (TypeError, ValueError):
            continue
        measured = float(getattr(report, attr))
        if measured < thr - tol:
            out.append(Violation(label, measured, thr))
    return out


def _tolerance_mm(report: MarginReport) -> float:
    """How far below its minimum a measured margin may sit and not be a fault.

    Two floors; the larger wins.

    * **0.05 mm** — the panel prints one decimal, so a margin *shown* as
      "6.0 mm" must not be flagged against a 6 mm minimum merely because the
      float behind it is 5.997 (#85).
    * **One device pixel** — a chart is drawn on a raster and every edge of it
      is rounded to a whole pixel (``geometry.patch_rects_px`` rounds both the
      near and the far edge), so no margin can be *realised*, or read back,
      more finely than ``25.4 / dpi`` mm.

    The second floor is why this function exists. At 300 dpi one pixel is
    0.085 mm and #85's fixed 0.05 mm hides most of the quantisation; at 200 dpi
    it is 0.127 mm and 0.05 does not. **45 of the 119 built-in charts** — every
    one of Knut's ColorMunki charts on the right edge and every i1Pro 3 Plus one
    on the left — declare ``dpi: 200``, land their patch block EXACTLY on the
    declared margin analytically (``geometry.realized_margins_mm``: 0 of 119
    short), and were then reported 0.050–0.060 mm inside it because their block
    edge rounded to the next pixel. All 45 report clean at 300 dpi. That is a
    property of the raster, not of the layout (#167).

    One pixel is the bound the measured error actually needs, but NOT for the
    reason it is tempting to give. On the engine path the page edge does not
    round at all — paper_mm is an exact float and only the patch rectangles
    are integers — so Left and Right carry at most HALF a pixel (measured worst
    case over all 119 built-ins: 0.496 px). Top and Bottom reach 0.890 px for a
    different reason: measure_from_engine adds a separately rounded
    edge-spacer overhang, and on hex charts a rounded apex, so two roundings
    compound. Do not "tighten" this to half a pixel on the strength of the
    left/right numbers.

    A shortfall of one pixel is not the smallest one that is still flagged. The
    inspector can also over-report by up to 0.890 px, and that adds to the
    tolerance: measured on the worst built-in
    (cm_letter_1615p_5pages_portrait_w10_0mm_slow_reading_speed, Top edge,
    200 dpi) the smallest GENUINE shortfall this check reports is 0.24 mm
    (1.89 px). The old fixed-0.05 rule missed 0.20 mm on the same chart, so the
    blind spot grew by 0.04 mm and 45 false alarms went away.
    """
    tol = 0.05
    dpi = float(getattr(report, "dpi", 0.0) or 0.0)
    if dpi > 0:
        # CEILING AT ONE PIXEL OF THE COARSEST CHART CHROMIQ SHIPS (200 dpi,
        # 0.127 mm). Without it an unrelated setting silently widens a SAFETY
        # check: `printtarg_dpi` is written from one place only — Create Chart
        # Manual's "Save as defaults" — and read by Guided, which has no control
        # for it. One "Resolution: 72 dpi" saved there re-rasters every future
        # Guided chart at 72 dpi AND loosens this tolerance 4.2x, taking a
        # margin 0.30 mm short from FLAGGED to MISSED.
        #
        # 200 dpi is the floor because it is the coarsest the built-in charts
        # use (the rest are 300); a chart coarser than that has worse problems
        # than its margins, and should not buy itself a bigger allowance.
        tol = max(tol, min(_MM_PER_INCH / dpi, _MM_PER_INCH / 200.0))
    return tol


def measure_from_engine(
    channels_path: "Path | str", page_idx: int = 0,
) -> "tuple[Optional[MarginReport], Optional[float]] | None":
    """Build a :class:`MarginReport` from a ChromIQ-engine chart's exact geometry.

    The engine records every patch's exact pixel rectangle (per page) and the
    recipe in ``<stem>.channels.json``, so for engine charts we report the TRUE
    margins / patch size instead of detecting them from the rendered image. This
    fixes the image-detection artefacts Knut hit (patch width read as the strip
    *pitch*, and a large Strip gap corrupting the detected margins) (#93).

    Returns ``(report, ruler_mm)`` — ``ruler_mm`` is the instrument's physical
    strip-length limit (0/None when it has none), so the caller can warn when the
    strip is longer than the ruler. ``None`` when the chart isn't an engine chart
    or has no usable geometry (caller then falls back to image measurement).
    """
    import json

    try:
        doc = json.loads(Path(channels_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    layout = doc.get("layout") if isinstance(doc, dict) else None
    if not isinstance(layout, dict) or layout.get("engine") != "chromiq":
        return None
    all_rects = layout.get("patches") or []
    if not all_rects:
        return None
    rects = [r for r in all_rects if int(r.get("page", 0)) == page_idx]
    if not rects:
        rects = [r for r in all_rects if int(r.get("page", 0)) == 0]
    if not rects:
        return None
    pm = layout.get("paper_mm") or []
    if len(pm) != 2 or not pm[0] or not pm[1]:
        return None
    dpi = float(layout.get("dpi") or 300) or 300.0
    px2mm = _MM_PER_INCH / dpi
    paper_w_mm, paper_h_mm = float(pm[0]), float(pm[1])

    x0 = min(r["x"] for r in rects)
    x1 = max(r["x"] + r["w"] for r in rects)
    y0 = min(r["y"] for r in rects)
    y1 = max(r["y"] + r["h"] for r in rects)

    # Edge spacers bracket each strip with one spacer ABOVE the first patch and
    # one BELOW the last (raster.render_pages), so the printed content reaches
    # pspa past the patch rects along the strip axis. The recorded patch rects
    # don't include them, so add that overhang here — otherwise the top/bottom
    # margins under-report and the measured-margin guides land inside the edge
    # spacers, which then look like they overflow the margins (Knut #18). Along
    # the strip axis (vertical in the printtarg frame) only.
    rec = layout.get("recipe") or {}
    if rec.get("edge_spacers"):
        try:
            from dataclasses import fields as _fields
            from workflow.layout_engine import instruments
            from workflow.layout_engine.presets import LayoutRecipe
            _valid = {f.name for f in _fields(LayoutRecipe)}
            _rc = LayoutRecipe(**{k: v for k, v in rec.items() if k in _valid})
            _g = instruments.geom_from_build_kwargs(_rc.build_kwargs())
            _sp_px = round(_g.pspa * dpi / _MM_PER_INCH)
            if _sp_px > 0:
                y0 -= _sp_px
                y1 += _sp_px
        except Exception:  # pragma: no cover - defensive; fall back to patch rects
            pass

    # SpectroScan hexagonal patches are DRAWN beyond their slot rectangles: the
    # top/bottom apex pokes ph/6 past the slot (reserved as hxeh) — see
    # raster._hexagon_points. So the true ink extremes, and thus the margins
    # Knut wants the guides to mark, are the hex tips, not the slot box (#28).
    #
    # ONLY the apex. The ±¼·w row stagger is ALREADY in the recorded rects —
    # `geometry.patch_rects_px` applies it when it writes them, precisely so
    # that everything reading this geometry describes where the ink is. Adding
    # it again here double-counted it by w/4: 3.0 mm at a 12 mm hexagon, 5.0 mm
    # at 20 mm, reported as margin that does not exist. The hexagon's flat sides
    # span exactly the staggered slot, so no horizontal expansion is right.
    from workflow.hex_support import recipe_is_hexagonal
    if recipe_is_hexagonal(rec):
        h_px = max(r["h"] for r in rects)
        y0 -= h_px / 6.0          # upper apex of the top row
        y1 += h_px / 6.0          # lower apex of the bottom row

    report = MarginReport(
        left_mm=max(0.0, x0 * px2mm),
        right_mm=max(0.0, paper_w_mm - x1 * px2mm),
        top_mm=max(0.0, y0 * px2mm),
        bottom_mm=max(0.0, paper_h_mm - y1 * px2mm),
        strip_width_mm=rects[0]["w"] * px2mm,        # exact patch width (pwid)
        page_w_mm=paper_w_mm, page_h_mm=paper_h_mm,
        strip_length_mm=(y1 - y0) * px2mm,
        dpi=dpi,
    )
    ruler_mm: Optional[float] = None
    try:
        from workflow.layout_engine import instruments
        rec = layout.get("recipe") or {}
        inst = rec.get("instrument")
        if inst:
            ruler_mm = instruments.build(inst).ruler_mm or None
    except Exception:  # pragma: no cover - defensive
        ruler_mm = None
    return report, ruler_mm


def _tiff_dpi(path: Path, fallback: float) -> float:
    """Resolution baked into the TIFF, or ``fallback`` when absent.

    Read via tifffile (not Pillow) so device-native separated CMYK/N charts,
    which Pillow can't decode, still report their DPI. (#72 Tier D)
    """
    try:
        import tifffile

        with tifffile.TiffFile(str(path)) as tf:
            page = tf.pages[0]
            xr = page.tags.get("XResolution")
            unit = page.tags.get("ResolutionUnit")
            if xr and xr.value[1]:
                val = xr.value[0] / xr.value[1]
                if unit and int(unit.value) == 3:             # px/cm → px/inch
                    val *= 2.54
                if val > 1.0:
                    return float(val)
    except Exception as exc:  # pragma: no cover - corrupt/odd TIFFs
        log.debug("Could not read TIFF dpi from %s: %s", path, exc)
    return float(fallback)


def _estimate_patch_width_mm(block_w_mm: float, n_strips: int) -> Optional[float]:
    """Patch width in mm — the strip pitch across the strips.

    printtarg **always** lays strips out vertically (labels at top), regardless
    of the page's portrait/landscape orientation, so the strips tile across the
    page *width* and the patch width is the block width ÷ strip count. This is
    what a ruler measures across a strip and matches the ``.cht`` XLIST pitch
    (verified against ColorMunki double-/triple-density and landscape charts).
    """
    if n_strips < 1:
        return None
    return block_w_mm / n_strips


def measure_margins(
    tif_path: "Path | str",
    *,
    dpi: float | None = None,
    ti2_path: "Path | str | None" = None,
    paper_w_mm: float | None = None,
    paper_h_mm: float | None = None,
) -> Optional[MarginReport]:
    """Measure the four page margins of a single rendered chart page.

    ``tif_path`` is one printtarg page TIFF (full print resolution). ``dpi`` is
    used only when the TIFF carries no resolution tag. ``ti2_path`` (optional)
    enables the estimated strip-width readout via the chart's strip/step counts.

    ``paper_w_mm`` / ``paper_h_mm`` are the true sheet size. ChromIQ renders
    charts with printtarg ``-M`` (the page margin is *included* in the TIFF, so
    the TIFF already spans the full sheet) — in that case they're optional. But
    plain ``-m`` *subtracts* the margin from the raster, leaving a TIFF cropped
    to the imageable area; when the true paper size is supplied and the TIFF is
    smaller, the symmetric ``(paper − tiff) / 2`` margin printtarg trimmed is
    added back so the reported margins are paper-edge to patch on both modes.

    Returns ``None`` when the patch area can't be located (caller shows a
    "couldn't measure" placeholder rather than wrong numbers).
    """
    tif_path = Path(tif_path)
    if not tif_path.is_file():
        return None
    try:
        arr = _imread_rgb(tif_path)
    except Exception as exc:
        log.warning("Margin inspector: cannot read %s: %s", tif_path, exc)
        return None

    h_px, w_px = arr.shape[:2]
    res = _tiff_dpi(tif_path, dpi if dpi else _DEFAULT_DPI)
    px2mm = _MM_PER_INCH / res
    tif_w_mm = w_px * px2mm
    tif_h_mm = h_px * px2mm

    # printtarg -m crops the margin out of the TIFF; -M keeps it. When the true
    # paper size is known and the TIFF is smaller, restore the symmetric margin
    # printtarg trimmed so margins read paper-edge to patch in both modes.
    off_x = max(0.0, (paper_w_mm - tif_w_mm) / 2.0) if paper_w_mm else 0.0
    off_y = max(0.0, (paper_h_mm - tif_h_mm) / 2.0) if paper_h_mm else 0.0
    page_w_mm = paper_w_mm if (paper_w_mm and paper_w_mm >= tif_w_mm) else tif_w_mm
    page_h_mm = paper_h_mm if (paper_h_mm and paper_h_mm >= tif_h_mm) else tif_h_mm

    bbox = _patch_area_bbox(arr)
    if bbox is None:
        log.debug("Margin inspector: patch area not found in %s", tif_path)
        return None
    y0, y1, x0, x1 = bbox   # inclusive pixel coords

    left_mm = x0 * px2mm + off_x
    right_mm = (w_px - 1 - x1) * px2mm + off_x
    top_mm = y0 * px2mm + off_y
    bottom_mm = (h_px - 1 - y1) * px2mm + off_y

    # printtarg always lays strips vertically (labels at top), even on a
    # landscape page, so the strip length the instrument scans is always the
    # *vertical* patch-block extent = page height − top − bottom (#87).
    strip_length_mm = (y1 - y0 + 1) * px2mm

    strip_width_mm: Optional[float] = None
    if ti2_path is not None:
        try:
            passes = parse_passes_per_page(ti2_path)
            page_ix = _page_index_of(tif_path)
            if passes and 0 <= page_ix < len(passes):
                block_w_mm = (x1 - x0 + 1) * px2mm
                strip_width_mm = _estimate_patch_width_mm(block_w_mm, passes[page_ix])
        except Exception as exc:  # pragma: no cover - defensive
            log.debug("Margin inspector: patch width skipped: %s", exc)

    return MarginReport(
        left_mm=max(0.0, left_mm), right_mm=max(0.0, right_mm),
        top_mm=max(0.0, top_mm), bottom_mm=max(0.0, bottom_mm),
        strip_width_mm=strip_width_mm,
        page_w_mm=page_w_mm, page_h_mm=page_h_mm,
        strip_length_mm=strip_length_mm,
        dpi=res,
    )


def _dense_run(fill: np.ndarray) -> Optional[tuple[int, int]]:
    """First/last index of the patch block along one axis, given its fill
    profile (fraction inked per row/column).

    THE STRIP LABELS USED TO BE ABLE TO ANCHOR THE BOX. This took the globally
    outermost row over ``_PATCH_ROW_FILL`` and extended outward from there, so
    the white-gap stop guarded only the EXTENSION and never the ANCHOR itself.
    One-letter strip labels peak at 0.295 fill and are ignored; two-letter ones
    ("AW AX AY…") peak at 0.575 and became the anchor — so on any chart with
    roughly more than 21 strips per page the top of the box jumped up onto the
    labels. Knut reported it on pages 2-3 of the pharmacist bundle (21.4 mm
    where 45.5 mm is right); a plain `targen -f900` + `printtarg -ii1 -pA4`
    chart reads 38.95 mm on page 1 and 8.47 mm on page 2, which also fired a
    FALSE "top margin below the 38 mm instrument minimum" warning and inflated
    the strip length by 24 mm.

    "Longest inked run" is the obvious cure and is wrong: printtarg omits the
    black separator where two neighbouring patches differ enough, so a mostly
    white spacer row splits the block and the answer regresses by 8-13 mm on
    other bundled charts. What holds is to MERGE runs across a short white gap,
    then take the longest merged group that still contains a fully-inked row.

    THE MERGE IS CHAINED, and that is deliberate but worth knowing: the gap is
    compared against the ACCUMULATED group so far, not against the immediately
    preceding run, so the threshold grows as merging proceeds and the rule is
    more permissive than "shorter of its two neighbours" would be. Constructed
    profiles can be made to exploit it — `A(100) gap5 B(10) gap30 C(80)`
    swallows C, while `B(10) gap30 C(80)` alone refuses the same 30-px gap.
    Nothing real is close: measured at the boundary that matters (the
    strip-label band against the patch block) across 103 pages — 53 built, 40
    adversarial, 17 bundled and the demo projects — the smallest safety ratio
    is 1.44x on `SS -h -a0.5`, an unsupported extreme, and every i1Pro,
    i1Pro 3 Plus and ColorMunki page is at least 3.11x.

    The half-cell tolerance (``_PATCH_EDGE_FILL``) catches the zig-zag edge of
    a double-density (-h) chart, where the outermost strip row carries only
    ~half its patches (#91); requiring a fully-inked row in the winning group
    keeps the sparse, rotated strip-label / title band out of the box
    (#91 right-margin follow-up).
    """
    anchors = np.where(fill > _PATCH_ROW_FILL)[0]
    if anchors.size == 0:
        return None
    inked = fill > _PATCH_EDGE_FILL
    n = fill.shape[0]
    runs: list[list[int]] = []
    i = 0
    while i < n:
        if not inked[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and inked[j + 1]:
            j += 1
        runs.append([i, j])
        i = j + 1
    merged = [list(runs[0])]
    for a, b in runs[1:]:
        pa, pb = merged[-1]
        gap = a - pb - 1
        if gap < min(pb - pa + 1, b - a + 1):
            merged[-1][1] = b
        else:
            merged.append([a, b])
    best = None
    for a, b in merged:
        if fill[a:b + 1].max() > _PATCH_ROW_FILL and (
                best is None or (b - a) > (best[1] - best[0])):
            best = (a, b)
    return best


def _patch_area_bbox(arr: np.ndarray) -> Optional[tuple[int, int, int, int]]:
    """Inclusive ``(y0, y1, x0, x1)`` pixel box of the patches+spacers block.

    ``_patch_grid_bbox`` gives a usable starting **horizontal** extent (the
    editor only ever uses its x-range), but it still leaves the rotated
    strip-label / title column on the right edge, and its vertical extent is
    contaminated by that same text. So we use its x-range only as a search
    window and derive both axes ourselves: inside the patch band a patch
    row/column is almost fully inked (patches/spacers tile edge-to-edge),
    whereas the strip-label band, the bottom page label and any stray text are
    sparse and sit past a strip of bare paper. The dense run on each axis — with
    half-cell tolerance for the zig-zag (-h) edge — is the patch block, "where
    paper white meets a patch or spacer", with text excluded on every side.
    """
    grid = _patch_grid_bbox(arr)
    if grid is None:
        return None
    _, _, gx0, gx1 = grid
    if gx1 <= gx0:
        return None
    gray = arr.mean(axis=2)
    # Vertical extent from rows within the grid x-window.
    row_fill = (gray[:, gx0:gx1 + 1] < _WHITE).mean(axis=1)
    yr = _dense_run(row_fill)
    if yr is None:
        return None
    y0, y1 = yr
    # Horizontal extent from columns within the patch y-band — this trims the
    # sparse rotated strip-label column that the grid leaves on the right edge,
    # so the right margin is measured to the real patch edge, not into the label
    # gap (#91 right-margin follow-up).
    col_fill = (gray[y0:y1 + 1, gx0:gx1 + 1] < _WHITE).mean(axis=0)
    xr = _dense_run(col_fill)
    if xr is None:
        return None
    x0, x1 = gx0 + xr[0], gx0 + xr[1]
    return (y0, y1, x0, x1)


def _steps_in_pass(ti2_path: "Path | str") -> int | None:
    import re

    try:
        text = Path(ti2_path).read_text(errors="replace")
    except OSError:
        return None
    m = re.search(r'STEPS_IN_PASS\s+"?(\d+)"?', text)
    return int(m.group(1)) if m else None


def _page_index_of(tif_path: Path) -> int:
    """0-based page index from a ``<stem>_NN.tif`` filename (single page → 0)."""
    import re

    m = re.search(r"_(\d+)$", tif_path.stem)
    if not m:
        return 0
    # printtarg numbers pages from 1 (_01, _02, …); _patch_grid_bbox runs on
    # the per-page TIFF, so the index into `passes` is NN-1.
    return max(0, int(m.group(1)) - 1)
