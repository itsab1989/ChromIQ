"""How far each page's patch block reaches across the paper (#182 E2).

**THE RULE SINCE 4.3.10 (Basti, 2026-10-23, replacing Knut's confirmed area
floor): the patch block's SPREAD IN EACH DIRECTION.** A page counts for
evenness when its patches reach across at least
`measurement_report.EVENNESS_MIN_PAGE_SPAN` of the paper's width AND of its
height (:func:`spans_of`). The area share below stays in every page's numbers
for the record, and to read a report saved under the old rule, but no longer
decides anything: jctay's 4 x 6 in i1Pro card (forum 149811) reached across
71 % of the width and 78 % of the height, a block spread over the whole card
with only the instrument's own margins left, and its area share of 55 % was
under the 60 % floor, so evenness was never judged on it; the half-page charts
the floor was built to refuse reach across 42 to 46 % of the width and are
refused by the spread too.

The history, Knut 2026-09-23:

Knut, asked whether the 75 % page-coverage requirement of the evenness rows
was still wanted (5789263863, E2): *"Could the Measured from Preview numbers be
used to calculate, so that these things are not re-measured on-screen? 9 strips
and 9 rows may still cover just a limited part of a page, thus the uniformity
test has limited value."* Built as proposed and approved (5789539407: "Yes"):

    coverage = (paper width - left - right) x (paper height - top - bottom)
               / (paper width x paper height)

where left, right, top and bottom are the distances from each paper edge to the
first patch, which is what Create Chart's "Measured from Preview" panel shows.

**THE PANEL'S OWN TWO MEASUREMENTS, IN THE PANEL'S OWN ORDER, AND NO THIRD.**
`TabChart._update_margin_inspector` asks
:func:`workflow.margin_inspector.measure_from_engine` first (a ChromIQ-engine
chart's recorded geometry, exact) and falls back to
:func:`workflow.margin_inspector.measure_margins` on the page TIFF. This module
asks the same two, in the same order, of the files beside a stored chart, so a
page's coverage is the number a reader could work out from the panel for the
same chart. One addition: a chart whose ``channels.json`` records a DERIVED
geometry (the prebuilt bundles, a printtarg chart whose scan geometry ChromIQ
read off its render) keeps its exact patch rectangles there, and a dated
verification snapshot keeps that file without the TIFFs
(`verify_chart_snapshot` does not copy images when a ``channels.json`` exists),
so those rectangles are read when no TIFF is there to measure.

Pure file logic, no Qt. Cached on each file's (path, mtime, size), because the
report builds evenness for every date a trend graph plots.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from core.logger import get_logger

log = get_logger(__name__)

_MM_PER_INCH = 25.4

#: Where the numbers came from, recorded in the block so a reader of a saved
#: report can tell a recorded geometry from a measured image.
SOURCE_ENGINE = "engine"
SOURCE_IMAGE = "image"
SOURCE_DERIVED = "derived"
SOURCE_PREDICTED = "predicted"

_CACHE: "dict[tuple, dict]" = {}


def coverage_of(page_w_mm: float, page_h_mm: float, left_mm: float,
                right_mm: float, top_mm: float, bottom_mm: float) -> float:
    """The share of the paper's AREA the patch block covers, 0..1.

    Knut's formula, and the only place it is written. Since 4.3.10 it is the
    record, not the rule (:func:`spans_of`). A margin larger than
    the paper (which no real chart has) gives 0, never a negative share."""
    w, h = float(page_w_mm), float(page_h_mm)
    if w <= 0 or h <= 0:
        return 0.0
    bw = max(0.0, w - float(left_mm) - float(right_mm))
    bh = max(0.0, h - float(top_mm) - float(bottom_mm))
    return (bw * bh) / (w * h)


def spans_of(page_w_mm: float, page_h_mm: float, left_mm: float,
             right_mm: float, top_mm: float, bottom_mm: float
             ) -> "tuple[float, float]":
    """(share of the paper's WIDTH, share of its HEIGHT) the patch block
    reaches across, each 0..1: the rule since 4.3.10 (Basti, 2026-10-23).
    The only place it is written. A margin larger than the paper gives 0."""
    w, h = float(page_w_mm), float(page_h_mm)
    if w <= 0 or h <= 0:
        return (0.0, 0.0)
    bw = max(0.0, w - float(left_mm) - float(right_mm))
    bh = max(0.0, h - float(top_mm) - float(bottom_mm))
    return (bw / w, bh / h)


def _page_numbers(w: float, h: float, left: float, right: float, top: float,
                  bottom: float) -> dict:
    """One page's numbers: the spread in each direction (the rule), the area
    share (the record), the margins and the paper."""
    sw, sh = spans_of(w, h, left, right, top, bottom)
    return {"coverage": coverage_of(w, h, left, right, top, bottom),
            "spans": [sw, sh],
            "margins_mm": [round(float(left), 2), round(float(right), 2),
                           round(float(top), 2), round(float(bottom), 2)],
            "paper_mm": [round(float(w), 2), round(float(h), 2)]}


def _report_coverage(rep) -> "Optional[dict]":
    if rep is None:
        return None
    return _page_numbers(rep.page_w_mm, rep.page_h_mm, rep.left_mm,
                         rep.right_mm, rep.top_mm, rep.bottom_mm)


def _stamp(p: Path) -> tuple:
    try:
        st = p.stat()
    except OSError:
        return ()
    return (st.st_mtime_ns, st.st_size)


def _layout_block(ti2: Path) -> "dict | None":
    ch = ti2.with_suffix(".channels.json")
    if not ch.is_file():
        return None
    try:
        doc = json.loads(ch.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    lay = doc.get("layout") if isinstance(doc, dict) else None
    return lay if isinstance(lay, dict) else None


def page_tiffs(ti2: Path, n_pages: int) -> "dict[int, Path]":
    """``{page index: TIFF}`` for the chart's page images beside *ti2*.

    printtarg and the engine write ONE page as ``<stem>.tif`` and several as
    ``<stem>_01.tif`` ... (see `Run.chart_tiffs`). Only those two spellings are
    read: ``<stem>*.tif`` would also take another chart whose name merely
    starts with this one's."""
    from core.file_manager import stem_files
    stem = ti2.stem
    out: "dict[int, Path]" = {}
    for p in stem_files(ti2.parent, stem, ".tif", ".TIF", ".tiff",
                        "_*.tif", "_*.TIF", "_*.tiff"):
        rest = p.stem[len(stem):]
        if rest == "":
            if n_pages <= 1:
                out.setdefault(0, p)
            continue
        m = re.fullmatch(r"_(\d+)", rest)
        if m and int(m.group(1)) >= 1:
            out.setdefault(int(m.group(1)) - 1, p)
    return out


def _derived_page(layout: dict, page: int) -> "Optional[dict]":
    """Coverage of one page from a derived geometry's patch rectangles."""
    rects = [r for r in (layout.get("patches") or [])
             if int(r.get("page", 0)) == page]
    pm = layout.get("paper_mm") or []
    if not rects or len(pm) != 2 or not pm[0] or not pm[1]:
        return None
    dpi = float(layout.get("dpi") or 300) or 300.0
    k = _MM_PER_INCH / dpi
    x0 = min(r["x"] for r in rects) * k
    x1 = max(r["x"] + r["w"] for r in rects) * k
    y0 = min(r["y"] for r in rects) * k
    y1 = max(r["y"] + r["h"] for r in rects) * k
    w, h = float(pm[0]), float(pm[1])
    return _page_numbers(w, h, x0, w - x1, y0, h - y1)


def _engine_page(ch: Path, layout: dict, page: int) -> "Optional[dict]":
    if layout.get("engine") != "chromiq":
        return None
    if not any(int(r.get("page", 0)) == page
               for r in (layout.get("patches") or [])):
        # `measure_from_engine` falls back to page 1 for a page it has no
        # rectangles for; a coverage must not borrow another page's.
        return None
    from workflow.margin_inspector import measure_from_engine
    got = measure_from_engine(ch, page)
    return _report_coverage(got[0]) if got else None


def chart_page_coverage(ti2_path: "str | Path", n_pages: int) -> dict:
    """``{"pages": [per-page dict or None], "source": ...}`` for a stored chart.

    Each page's dict carries ``spans`` (the shares of the paper's width and
    height the block reaches across, 0..1, the rule), ``coverage`` (the area
    share, 0..1, the record), ``margins_mm`` (left, right, top, bottom) and
    ``paper_mm``. A page none of the sources can measure is
    None. ``source`` is where the numbers came from (the first one that
    answered for page 1)."""
    ti2 = Path(ti2_path)
    ch = ti2.with_suffix(".channels.json")
    tiffs = page_tiffs(ti2, n_pages)
    key = (str(ti2), int(n_pages), _stamp(ti2), _stamp(ch),
           tuple((i, str(p), _stamp(p)) for i, p in sorted(tiffs.items())))
    out = _CACHE.get(key)
    if out is None:
        out = _CACHE[key] = _measure_pages(ti2, ch, tiffs, n_pages)
    if not any(out["pages"]):
        # not cached under this key: the live chart's own files are its key
        live = _live_chart_of_snapshot(ti2)
        if live is not None:
            got = chart_page_coverage(live, n_pages)
            if any(got["pages"]):
                return {"pages": got["pages"],
                        "source": got["source"] + "+live"}
    return out


def _measure_pages(ti2: Path, ch: Path, tiffs: "dict[int, Path]",
                   n_pages: int) -> dict:
    layout = _layout_block(ti2) or {}
    pages: "list[Optional[dict]]" = []
    sources: "list[str]" = []
    for pg in range(max(0, int(n_pages))):
        got, src = None, ""
        try:
            got = _engine_page(ch, layout, pg)
            src = SOURCE_ENGINE
            if got is None and pg in tiffs:
                from workflow.margin_inspector import measure_margins
                got = _report_coverage(measure_margins(tiffs[pg]))
                src = SOURCE_IMAGE
            if got is None and layout.get("engine") == "derived":
                got = _derived_page(layout, pg)
                src = SOURCE_DERIVED
        except Exception:      # noqa: BLE001 - one bad page must not break a report
            log.info("could not measure page %d of %s", pg + 1, ti2,
                     exc_info=True)
            got = None
        pages.append(got)
        sources.append(src if got is not None else "")
    return {"pages": pages,
            "source": next((s for s in sources if s), "")}


def _live_chart_of_snapshot(ti2: Path) -> "Optional[Path]":
    """The live verification chart a dated snapshot was copied from, when it
    is still the SAME chart.

    A dated verification is paired with ``verifications/<date>/chart/<stem>
    .ti2``, and `verify_chart_snapshot` leaves the page images out of that
    folder whenever a ``channels.json`` exists. For an engine chart that file
    holds the geometry; for a printtarg chart whose scan geometry was captured
    it holds only ``.cht`` text, so the snapshot alone cannot say where the
    patches sit. The live chart two folders up still has its pages, and when
    its ``.ti2`` is byte for byte the snapshot's it is the chart that was
    measured. Anything else is a different chart and is not read."""
    if ti2.parent.name != "chart":
        return None
    live = ti2.parent.parent.parent / ti2.name
    try:
        if live.is_file() and live.read_bytes() == ti2.read_bytes():
            return live
    except OSError:
        return None
    return None


def predicted_page_coverage(recipe, n_patches: int) -> dict:
    """The same, for an engine recipe that has not been built: the layout
    engine's own geometry, widened by
    :func:`~workflow.margin_inspector.engine_ink_bounds_px` exactly as
    :func:`~workflow.margin_inspector.measure_from_engine` widens a built
    chart's, so the prediction is the number the panel will show."""
    from workflow.layout_engine import geometry, instruments, papers
    from workflow.margin_inspector import engine_ink_bounds_px
    kw = recipe.build_kwargs()
    kw.setdefault("side_stamp", True)
    kw["area_target_count"] = int(n_patches)
    geom = instruments.geom_from_build_kwargs(kw)
    w_mm, h_mm = papers.dimensions_mm(kw["paper"])
    dpi = float(getattr(recipe, "dpi", 300) or 300)
    lay = geometry.compute(geom, w_mm, h_mm, int(n_patches))
    rects = geometry.patch_rects_px(geom, w_mm, h_mm, lay, int(dpi))
    rec = recipe.to_dict()          # B8-1570: today's rule, see margin_inspector
    pages: "list[Optional[dict]]" = []
    for pg in range(max(1, int(lay.pages))):
        on = [r for r in rects if int(r.get("page", 0)) == pg]
        if not on:
            pages.append(None)
            continue
        x0, x1, y0, y1, _pw = engine_ink_bounds_px(on, rec, dpi)
        k = _MM_PER_INCH / dpi
        left, right = x0 * k, w_mm - x1 * k
        top, bottom = y0 * k, h_mm - y1 * k
        pages.append(_page_numbers(w_mm, h_mm, left, right, top, bottom))
    return {"pages": pages, "source": SOURCE_PREDICTED}


def clear_cache() -> None:
    _CACHE.clear()
