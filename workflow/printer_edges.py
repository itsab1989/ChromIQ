"""The edge of the paper a printer does not print, and what of a chart falls
into it (Basti, 2026-10-25, from jctay's forum post 149836).

jctay's Canon SELPHY CP1500 printed a 100 x 150 mm chart on its 100 x 148 mm
paper at 100 %, centred, with only empty margin outside the paper by ChromIQ's
own account, and the ruler helper markers (0.9 to 2.9 mm from the paper's
edges) were missing on paper and the text at the bottom was cut: the printer
itself leaves a band along its edges unprinted, and nothing said so.

THREE SOURCES, the person's own first:

* **Preferences** -> Printing -> "Edge this printer does not print": one value
  in mm per printer, all four edges, saved per printer
  (``printer_edge_override_mm``, a JSON object ``{printer: mm}``). It wins,
  because a borderless driver that enlarges the picture (the SELPHY does)
  reports no margin at all;
* **Windows**: the driver's minimum margins for a page the chart's size
  (``QPageLayout.minimumMargins``), the same numbers the 4.3.14 print log line
  writes;
* **macOS and Linux (CUPS)**: the queue's PPD, ``*ImageableArea`` of the page
  size that matches the chart (within 5 mm), else of ``*DefaultPageSize``.

What falls into the edge is read off the chart's own page image
(`workflow.overhang`'s ink, helper-marker and caption readers), placed on the
paper the way every print route places it: centred, at 100 %, moved by the
overhang plan when there is one. Usually only the ruler helper markers and the
text the chart prints along its edges are there; patches only when a margin
is narrower than the printer's edge, and the note then says so rather than
calling them text. Never a block: it is a note under the preview and on the
Print Chart tab.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

MM_PER_PT = 25.4 / 72.0
#: The Preferences key, a JSON object {printer name: mm}.
OVERRIDE_KEY = "printer_edge_override_mm"
#: A PPD page size this close to the chart (mm, each side) is the chart's.
MATCH_MM = 5.0
#: Below this nothing is called lost (rounding of sizes and pixels).
TOL_MM = 0.2


@dataclass(frozen=True)
class Edges:
    """Unprinted edge on each side, in mm, and where the numbers came from:
    ``"override"`` (Preferences), ``"driver"`` (Windows), ``"ppd"`` (CUPS)."""
    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    source: str = ""

    def any(self) -> bool:
        return max(self.left, self.top, self.right, self.bottom) > TOL_MM

    def as_dict(self) -> dict:
        return {"left": self.left, "top": self.top, "right": self.right,
                "bottom": self.bottom}


# ---- the person's own value ------------------------------------------------
def overrides(settings) -> "dict[str, float]":
    try:
        raw = settings.get(OVERRIDE_KEY, "") if settings is not None else ""
        d = json.loads(raw) if isinstance(raw, str) and raw else (raw or {})
        return {str(k): float(v) for k, v in dict(d).items()}
    except Exception:      # noqa: BLE001 - a bad value is no value
        return {}


def set_override(settings, printer: str, mm: "float | None") -> None:
    """Store *mm* for *printer*; None removes it (the printer's own value
    is used again)."""
    d = overrides(settings)
    if mm is None:
        d.pop(printer, None)
    else:
        d[printer] = round(float(mm), 2)
    settings.set(OVERRIDE_KEY, json.dumps(d, sort_keys=True))


# ---- the printer's own value ----------------------------------------------
def _ppd_path(printer: str) -> "Path | None":
    for base in ("/etc/cups/ppd", "/private/etc/cups/ppd"):
        p = Path(base) / f"{printer}.ppd"
        if p.is_file():
            return p
    return None


def ppd_edges_mm(ppd_text: str, chart_mm: "tuple[float, float]"
                 ) -> "tuple[Edges, tuple[float, float]] | None":
    """(edges, paper mm) from a PPD's ``*ImageableArea`` for the page size
    that matches *chart_mm* (either way round), else the default size."""
    dims = {}
    for m in re.finditer(r'^\*PaperDimension\s+([^/:\s]+)[^:]*:\s*'
                         r'"\s*([\d.]+)\s+([\d.]+)\s*"', ppd_text, re.M):
        dims[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    areas = {}
    for m in re.finditer(r'^\*ImageableArea\s+([^/:\s]+)[^:]*:\s*'
                         r'"\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*"',
                         ppd_text, re.M):
        areas[m.group(1)] = tuple(float(g) for g in m.groups()[1:])
    cw, ch = chart_mm
    pick = None
    for name, (w, h) in dims.items():
        wm, hm = w * MM_PER_PT, h * MM_PER_PT
        if name in areas and (
                (abs(wm - cw) <= MATCH_MM and abs(hm - ch) <= MATCH_MM)
                or (abs(wm - ch) <= MATCH_MM and abs(hm - cw) <= MATCH_MM)):
            if pick is None or abs(wm - cw) + abs(hm - ch) < pick[1]:
                pick = (name, abs(wm - cw) + abs(hm - ch))
    if pick is None:
        m = re.search(r'^\*DefaultPageSize:\s*(\S+)', ppd_text, re.M)
        if m and m.group(1) in dims and m.group(1) in areas:
            pick = (m.group(1), 0.0)
    if pick is None:
        return None
    w, h = dims[pick[0]]
    llx, lly, urx, ury = areas[pick[0]]
    e = Edges(left=llx * MM_PER_PT, bottom=lly * MM_PER_PT,
              right=max(0.0, w - urx) * MM_PER_PT,
              top=max(0.0, h - ury) * MM_PER_PT, source="ppd")
    return e, (w * MM_PER_PT, h * MM_PER_PT)


def _windows_edges(printer: str, chart_mm) -> "tuple[Edges, tuple] | None":
    try:
        from PyQt6.QtCore import QMarginsF, QSizeF
        from PyQt6.QtGui import QPageLayout, QPageSize
        from PyQt6.QtPrintSupport import QPrinter
        pr = QPrinter(QPrinter.PrinterMode.HighResolution)
        pr.setPrinterName(printer)
        size = QPageSize(QSizeF(float(chart_mm[0]), float(chart_mm[1])),
                         QPageSize.Unit.Millimeter)
        pr.setPageLayout(QPageLayout(size, QPageLayout.Orientation.Portrait,
                                     QMarginsF(0, 0, 0, 0),
                                     QPageLayout.Unit.Millimeter))
        lay = pr.pageLayout()
        m = lay.minimumMargins()
        per = 25.4 / 72.0 if lay.units() == QPageLayout.Unit.Point else 1.0
        full = lay.fullRect(QPageLayout.Unit.Millimeter)
        return (Edges(m.left() * per, m.top() * per, m.right() * per,
                      m.bottom() * per, "driver"),
                (float(full.width()), float(full.height())))
    except Exception:      # noqa: BLE001
        log.debug("driver margins not readable", exc_info=True)
        return None


def _query_driver(printer: str, chart_mm) -> "tuple[Edges, tuple] | None":
    """The printer's own edge, by platform. Tests replace this function: no
    test ever asks a real printer."""
    if not printer:
        return None
    if sys.platform == "win32":
        return _windows_edges(printer, chart_mm)
    p = _ppd_path(printer)
    if p is None:
        return None
    try:
        text = p.read_text(encoding="latin-1", errors="replace")
    except OSError:
        return None
    return ppd_edges_mm(text, chart_mm)


def edges_for(printer: str, chart_mm: "tuple[float, float]", settings=None
              ) -> "tuple[Edges, tuple[float, float]]":
    """(edges, paper mm) for *printer* and a chart of *chart_mm*. The paper
    is the driver's page that matches the chart, else the chart's own size.
    No printer, or nothing known: no edge."""
    paper = (float(chart_mm[0]), float(chart_mm[1]))
    found = None
    try:
        found = _query_driver(printer, chart_mm)
    except Exception:      # noqa: BLE001
        found = None
    if found is not None:
        paper = found[1]
        # the paper the chart's way round
        if (paper[0] > paper[1]) != (chart_mm[0] > chart_mm[1]) \
                and abs(paper[0] - paper[1]) > 0.5:
            paper = (paper[1], paper[0])
    own = overrides(settings).get(printer) if printer else None
    if own is not None:
        return Edges(own, own, own, own, "override"), paper
    if found is None:
        return Edges(), paper
    return found[0], paper


# ---- what of the chart is in it -------------------------------------------
@dataclass
class Loss:
    """What of a chart page falls into the unprinted edge."""
    markers: "dict[str, int]" = field(default_factory=dict)   # side: count
    caption: "list[str]" = field(default_factory=list)        # sides
    text: "dict[str, float]" = field(default_factory=dict)    # side: depth mm
    #: sides on which PATCHES fall into the edge (review of 4.3.14: the note
    #: said "nothing your instrument measures is in it" whatever was there)
    patches: "list[str]" = field(default_factory=list)
    #: how much further in, per side, everything would have to start
    needed_mm: "dict[str, float]" = field(default_factory=dict)

    def any(self) -> bool:
        return bool(self.markers or self.caption or self.text or self.patches)


def _limits_on_chart(edges: Edges, chart_mm, paper_mm, shift_mm=(0.0, 0.0)):
    """The edge band in the chart's own frame: chart x below ``lo_x`` or above
    ``hi_x`` (and the same for y, top-down) is not printed."""
    cw, ch = chart_mm
    pw, ph = paper_mm
    x0 = (pw - cw) / 2.0 + shift_mm[0]
    y0 = (ph - ch) / 2.0 + shift_mm[1]
    return (edges.left - x0, pw - x0 - edges.right,
            edges.top - y0, ph - y0 - edges.bottom)


def losses(tiff_path, frame: int, edges: Edges, paper_mm,
           shift_mm=(0.0, 0.0)) -> Loss:
    """What of page *frame* of *tiff_path* falls into *edges* when the chart is
    printed at 100 % on *paper_mm*, centred and moved by *shift_mm*."""
    out = Loss()
    if not edges.any():
        return out
    from workflow import overhang as O
    got = O._ink_mm(tiff_path, frame)
    if got is None:
        return out
    ink, mm = got
    import numpy as np
    h_px, w_px = ink.shape
    chart_mm = (w_px * mm, h_px * mm)
    lo_x, hi_x, lo_y, hi_y = _limits_on_chart(edges, chart_mm, paper_mm,
                                              shift_mm)
    cut = np.zeros_like(ink, dtype=bool)
    xs = np.arange(w_px) * mm
    ys = np.arange(h_px) * mm
    cut[:, xs < lo_x - TOL_MM] = True
    cut[:, xs + mm > hi_x + TOL_MM] = True
    cut[ys < lo_y - TOL_MM, :] = True
    cut[ys + mm > hi_y + TOL_MM, :] = True
    lost = ink & cut
    if not lost.any():
        return out
    # the helper markers and the caption, recognised as overhang does
    known = np.zeros_like(ink, dtype=bool)
    try:
        marks = O.helper_markers(tiff_path, frame) or {}
    except Exception:      # noqa: BLE001
        marks = {}
    for side, boxes in marks.items():
        n = 0
        for b in boxes:
            x0, y0 = int(b.left / mm), int(b.top / mm)
            x1, y1 = int(np.ceil(b.right / mm)), int(np.ceil(b.bottom / mm))
            region = lost[max(0, y0):y1, max(0, x0):x1]
            known[max(0, y0):y1, max(0, x0):x1] = True
            if region.any():
                n += 1
        if n:
            out.markers[side] = n
    try:
        cap = O.caption_box(tiff_path, frame)
    except Exception:      # noqa: BLE001
        cap = None
    if cap is not None:
        x0, y0 = int(cap.left / mm), int(cap.top / mm)
        x1, y1 = int(np.ceil(cap.right / mm)), int(np.ceil(cap.bottom / mm))
        if lost[max(0, y0):y1, max(0, x0):x1].any():
            out.caption.append(_side_of(cap, chart_mm))
        known[max(0, y0):y1, max(0, x0):x1] = True
    # …AND THE PATCHES, which the note must never pass off as text (review
    # of 4.3.14): a chart whose margin is narrower than the printer's edge
    # loses patch area there, and that is the one loss that spoils a
    # measurement.
    try:
        pb = O.patch_box(tiff_path, frame)
    except Exception:      # noqa: BLE001
        pb = None
    if pb is not None:
        x0, y0 = int(pb.left / mm), int(pb.top / mm)
        x1, y1 = int(np.ceil(pb.right / mm)), int(np.ceil(pb.bottom / mm))
        sub = lost[max(0, y0):y1, max(0, x0):x1]
        if sub.any():
            pcols = np.where(sub.any(axis=0))[0] + max(0, x0)
            prows = np.where(sub.any(axis=1))[0] + max(0, y0)
            for side, hit in (("top", prows[0] * mm < lo_y),
                              ("bottom", (prows[-1] + 1) * mm > hi_y),
                              ("left", pcols[0] * mm < lo_x),
                              ("right", (pcols[-1] + 1) * mm > hi_x)):
                if hit:
                    out.patches.append(side)
        known[max(0, y0):y1, max(0, x0):x1] = True
    rest = lost & ~known
    if rest.any():
        rows = np.where(rest.any(axis=1))[0]
        cols = np.where(rest.any(axis=0))[0]
        if cols.size and cols[0] * mm < lo_x:
            out.text["left"] = lo_x - cols[0] * mm
        if cols.size and (cols[-1] + 1) * mm > hi_x:
            out.text["right"] = (cols[-1] + 1) * mm - hi_x
        if rows.size and rows[0] * mm < lo_y:
            out.text["top"] = lo_y - rows[0] * mm
        if rows.size and (rows[-1] + 1) * mm > hi_y:
            out.text["bottom"] = (rows[-1] + 1) * mm - hi_y
    # how much further in everything lost would have to start, per side
    allx = np.where(lost.any(axis=0))[0]
    ally = np.where(lost.any(axis=1))[0]
    if allx.size and allx[0] * mm < lo_x:
        out.needed_mm["left"] = lo_x - allx[0] * mm
    if allx.size and (allx[-1] + 1) * mm > hi_x:
        out.needed_mm["right"] = (allx[-1] + 1) * mm - hi_x
    if ally.size and ally[0] * mm < lo_y:
        out.needed_mm["top"] = lo_y - ally[0] * mm
    if ally.size and (ally[-1] + 1) * mm > hi_y:
        out.needed_mm["bottom"] = (ally[-1] + 1) * mm - hi_y
    return out


def _side_of(box, chart_mm) -> str:
    cw, ch = chart_mm
    d = {"left": box.left, "right": cw - box.right, "top": box.top,
         "bottom": ch - box.bottom}
    return min(d, key=d.get)


def losses_for_chart(pages, edges: Edges, paper_mm, shift_mm=(0.0, 0.0)
                     ) -> Loss:
    """`losses` over every page, merged (the worst of each)."""
    out = Loss()
    for path, frame in pages:
        one = losses(path, frame, edges, paper_mm, shift_mm)
        for k, v in one.markers.items():
            out.markers[k] = max(out.markers.get(k, 0), v)
        for s in one.caption:
            if s not in out.caption:
                out.caption.append(s)
        for s in one.patches:
            if s not in out.patches:
                out.patches.append(s)
        for k, v in one.text.items():
            out.text[k] = max(out.text.get(k, 0.0), v)
        for k, v in one.needed_mm.items():
            out.needed_mm[k] = max(out.needed_mm.get(k, 0.0), v)
    return out
