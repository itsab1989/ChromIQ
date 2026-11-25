"""The i1Profiler test chart (``.txf``) and order file of an i1iSis chart.

i1Profiler does not read a layout from a file: it COMPUTES the i1iSis grid
from the device, the page, the margins, the patch size (as the slider
PERCENT), the header, tight margins, the barcode and the patch count, by the
rule in `workflow.isis.chart.split` (REQUIREMENTS §1, §9). So the ``.txf``
written here gives i1Profiler a page exactly half a patch larger than
ChromIQ's grid in both directions (``(C + 0.5) x pw`` across, ``(R + 0.5) x
ph`` along, beside the side borders and the overhead i1Profiler counts):
its rule then finds Cmax = C and Rmax = R, and because the rule is a fixed
point (``split(N, C, R) == (C, R, P)``, proved on 9,849,000 cases by the
study and pinned by ``tests/test_isis_txf_forces_the_grid.py``) i1Profiler
lays out exactly ChromIQ's sheet. The patch list is every printed cell in
ChromIQ's placement order (column by column, page by page), so i1Profiler's
entry ``j`` is the patch ChromIQ printed in that cell; each carries
ChromIQ's own name of it (``SampleName``), which i1Profiler copies into its
measurement.

The order file records that order with the chart's SHA-256, so the import
pairs a measurement back by position and cross-checks it by name and by the
device values.

RGB charts only in stage 1: i1Profiler's test-chart file is written by the
RGB workflow writer (`workflow.i1profiler_export.write_pwxf`); any other ink
set gets a plain line saying no test chart was written.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from core.i18n import tr

from . import chart_facts as F

log = logging.getLogger(__name__)

ORDER_KIND = "isis"
ORDER_VERSION = 1


def txf_name(stem: str) -> str:
    return f"{stem}-i1profiler-isis.txf"


def order_name(stem: str) -> str:
    return f"{stem}-i1profiler-isis.order.json"


def percent_of(mm: float) -> float:
    """i1Profiler's patch slider percent for a size: (mm - 6) / 14 x 100."""
    lo, hi = F.PATCH_MIN_MM.value, F.PATCH_MAX_MM.value
    return round((float(mm) - lo) / (hi - lo) * 100.0, 6)


def header_percent_of(mm: float) -> float:
    """i1Profiler's header slider: (H - 32) / 48 x 100."""
    lo, hi = F.HEADER_MIN_MM.value, F.HEADER_MAX_MM.value
    return round((float(mm) - lo) / (hi - lo) * 100.0, 6)


def i1profiler_overhead_mm(header: float, barcode: bool) -> float:
    """What i1Profiler's row check takes off the page besides the rows:
    header + 0.5 + bar 6 + clear 6 (+ 14 with the barcode) + trailer 25.5
    (REQUIREMENTS §13: 70.0 and 84 measured)."""
    return (header + F.BAR_TOP_EXTRA_MM.value + F.BAR_HEIGHT_MM.value
            + F.CLEAR_UNDER_BAR_MM.value
            + (F.CLEAR_UNDER_BAR_BARCODE_MM.value - F.CLEAR_UNDER_BAR_MM.value
               if barcode else 0.0)
            + F.TRAILER_MIN_MM.value)


@dataclass
class TxfDesign:
    """Everything the ``.txf`` says about the layout."""
    device: str
    page_w: float
    page_h: float
    margins: tuple          # top, right, bottom, left
    pw: float
    ph: float
    header: float
    tight: bool
    barcode: bool
    columns: int
    rows: int
    pages: int


def design_for(side: dict) -> TxfDesign:
    """The ``.txf`` design that makes i1Profiler compute the side file's
    grid: a page half a patch larger than the grid both ways."""
    m = side["margins_mm"]
    margins = (float(m["top"]), float(m["right"]), float(m["bottom"]),
               float(m["left"]))
    pw, ph = (float(v) for v in side["patch_mm"])
    tight = bool(side.get("tight_margins"))
    d1 = (F.DIST1_TIGHT_MM if tight else F.DIST1_MM).value
    d2 = (F.DIST2_TIGHT_MM if tight else F.DIST2_MM).value
    side_mm = d1 + F.DIAMOND_W_MM.value + d2
    C, R, P = int(side["columns"]), int(side["rows"]), int(side["pages"])
    header = float(side["header_mm"])
    barcode = bool(side.get("barcode"))
    page_w = margins[1] + margins[3] + 2 * side_mm + (C + 0.5) * pw
    page_h = (margins[0] + margins[2]
              + i1profiler_overhead_mm(header, barcode) + (R + 0.5) * ph)
    return TxfDesign(device=str(side.get("device") or "i1iSis"),
                     page_w=page_w, page_h=page_h, margins=margins,
                     pw=pw, ph=ph, header=header, tight=tight,
                     barcode=barcode, columns=C, rows=R, pages=P)


def i1profiler_grid(design: TxfDesign, n: int) -> "tuple[int, int, int]":
    """The grid i1Profiler computes from *design* for *n* patches, by its own
    rule (REQUIREMENTS §1): what the ``.txf`` makes it expect."""
    import math
    from .chart import split
    t = F.COLUMN_FIT_TOLERANCE_MM.value
    d1 = (F.DIST1_TIGHT_MM if design.tight else F.DIST1_MM).value
    d2 = (F.DIST2_TIGHT_MM if design.tight else F.DIST2_MM).value
    side = d1 + F.DIAMOND_W_MM.value + d2
    mt, mr, mb, ml = design.margins
    cmax = math.floor((design.page_w - ml - mr - 2 * side + t) / design.pw
                      + 1e-9)
    cap = F.CAP_MM.value["xl" if design.device.endswith("XL") else "standard"]
    room = cap - 2 * side + (d1 if design.tight else 0.0)
    cmax = min(cmax, math.floor(room / design.pw + 1e-9))
    rmax = math.floor((design.page_h - mt - mb - i1profiler_overhead_mm(
        design.header, design.barcode)) / design.ph + 1e-9)
    return split(n, cmax, rmax)


@dataclass
class IsisExport:
    written: list = field(default_factory=list)
    skipped: str = ""
    txf: "Path | None" = None
    order: "Path | None" = None


def _read_ti2_rows(ti2: Path) -> "tuple[list[str], dict]":
    from workflow.i1profiler_import import read_first_cgats_table
    fields, rows = read_first_cgats_table(ti2)
    idx = {f: i for i, f in enumerate(fields)}
    return fields, {"idx": idx, "rows": rows}


def _attr(text: str, name: str, value: str) -> str:
    from xml.sax.saxutils import escape
    new, n = re.subn(rf'(\s{name}=")[^"]*(")',
                     lambda m: m.group(1) + escape(value, {'"': "&quot;"})
                     + m.group(2), text, count=1)
    if n != 1:
        raise ValueError(f"attribute {name} not found")
    return new


def _fmt(v: float) -> str:
    return f"{float(v):.2f}"


def _pct(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else repr(float(v))


def write_txf(ti2: Path, side: dict, out: Path, title: str,
              order: "list[tuple[int, str, dict]]") -> None:
    """Write the ``.txf``: the RGB workflow file of
    `workflow.i1profiler_export.write_pwxf` with the i1iSis design."""
    from workflow.i1profiler_export import (Target, WorkflowOptions,
                                            write_pwxf)
    d = design_for(side)
    tgt = Target("iRGB", "RGB", ["R", "G", "B"],
                 [(pos, vals) for pos, (_sid, _loc, vals)
                  in enumerate(order, start=1)])
    opt = WorkflowOptions(
        device=d.device, measurement_mode=1, paper_format=0,
        paper_orientation="Portrait", page_width_mm=d.page_w,
        page_height_mm=d.page_h, columns=d.columns, rows=d.rows,
        pages=d.pages, patch_w_mm=d.pw, patch_h_mm=d.ph,
        patch_w_percent=percent_of(d.pw), patch_h_percent=percent_of(d.ph),
        use_patch_defaults=False, title=title,
        header_edge_percent=header_percent_of(d.header))
    write_pwxf(tgt, out, title, opt,
               sample_names=[loc for _sid, loc, _v in order])
    # The rest of the i1iSis design, which the shared writer leaves at the
    # handheld defaults: the margins, tight margins, the barcode and a
    # custom page. The Location tags the writer adds follow the handheld
    # fill rule; i1Profiler ignores them on load and computes its own grid
    # (2026-10-27 study P4), and they are rewritten to the i1iSis placement
    # below so the file reads truthfully.
    text = out.read_text(encoding="utf-8")
    mt, mr, mb, ml = d.margins
    for name, value in (("PaperFormat", "Custom"),
                        ("PrintMarginTop", _fmt(mt)),
                        ("PrintMarginRight", _fmt(mr)),
                        ("PrintMarginBottom", _fmt(mb)),
                        ("PrintMarginLeft", _fmt(ml)),
                        ("TightMarginsEnabled", "True" if d.tight else "False"),
                        ("BarCodeEnabled", "True" if d.barcode else "False")):
        text = _attr(text, name, value)
    R, C = d.rows, d.columns

    def _loc(m):
        nonlocal_j[0] += 1
        j = nonlocal_j[0] - 1
        page, rest = divmod(j, C * R)
        col, row = divmod(rest, R)
        return (f'<cc:Tag Name="Column" Value="{col}"/>{m.group(1)}'
                f'<cc:Tag Name="Page" Value="{page + 1}"/>{m.group(2)}'
                f'<cc:Tag Name="Row" Value="{row}"/>')
    nonlocal_j = [0]
    text = re.sub(r'<cc:Tag Name="Column" Value="\d+"/>(\s*)'
                  r'<cc:Tag Name="Page" Value="\d+"/>(\s*)'
                  r'<cc:Tag Name="Row" Value="\d+"/>', _loc, text)
    out.write_text(text, encoding="utf-8", newline="")


def _entries(ti2: Path, side: dict, idx: dict, rows: list) -> list:
    """Every printed cell in placement order: (sample id, location, device
    values). Entry j of the ``.txf`` is the j-th of these."""
    by_loc = {}
    for r in rows:
        try:
            by_loc[r[idx["SAMPLE_LOC"]].strip('"')] = (
                r[idx["SAMPLE_ID"]],
                {c: float(r[idx[f"RGB_{c}"]]) for c in "RGB"})
        except (KeyError, IndexError, ValueError):
            continue
    from workflow.layout_engine.ti2_writer import (  # noqa: F401
        build_ti2_text)
    from .chart import placement_order
    from workflow.layout_engine import labels as _labels
    cl = _labels.labels_for_chart(ti2)
    patterns = (getattr(cl, "strip_pattern", None),
                getattr(cl, "patch_pattern", None),
                getattr(cl, "rule", None))
    if not all(patterns):
        patterns = None
    locs = placement_order(ti2, side, patterns)
    order = []
    for loc in locs:
        if loc not in by_loc:
            raise ValueError(f"cell {loc} is not in the chart")
        sid, vals = by_loc[loc]
        order.append((sid, loc, vals))
    return order


def order_of(ti2: "str | Path"):
    """The order `write_isis_export` writes for the i1iSis chart *ti2*, worked
    out from the chart and its side file again, for a chart whose order file
    is missing (exports/ is derived). None when that is not possible. Reads
    only, never raises."""
    try:
        from .support import read_side_file, side_file_for
        from workflow.i1profiler_turned import TurnedOrder
        ti2 = Path(ti2)
        side = read_side_file(ti2)
        if not side:
            return None
        _fields, data = _read_ti2_rows(ti2)
        idx, rows = data["idx"], data["rows"]
        if not all(k in idx for k in ("RGB_R", "RGB_G", "RGB_B")):
            return None
        entries = _entries(ti2, side, idx, rows)
        return TurnedOrder(side_file_for(ti2), [e[0] for e in entries],
                           [e[1] for e in entries], rows=int(side["rows"]),
                           columns=int(side["columns"]), kind=ORDER_KIND,
                           pages=max(1, int(side["pages"])))
    except Exception:  # noqa: BLE001 - no order, never a failure
        log.debug("i1iSis order could not be worked out", exc_info=True)
        return None


def write_isis_export(ti2: "str | Path", out_dir: "str | Path",
                      stem: str) -> IsisExport:
    """Write ``<stem>-i1profiler-isis.txf`` and its order file into
    *out_dir* for the i1iSis chart *ti2* (its side file beside it).
    Best-effort: never raises; ``skipped`` says why nothing was written."""
    from .support import read_side_file
    from workflow.i1profiler_turned import sha256_of
    res = IsisExport()
    try:
        ti2, out_dir = Path(ti2), Path(out_dir)
        side = read_side_file(ti2)
        if not side:
            res.skipped = tr("No i1Profiler test chart was written: the "
                             "chart's i1iSis side file is missing.")
            return res
        _fields, data = _read_ti2_rows(ti2)
        idx, rows = data["idx"], data["rows"]
        if not all(k in idx for k in ("RGB_R", "RGB_G", "RGB_B")):
            res.skipped = tr(
                "No i1Profiler test chart was written for this chart: in "
                "this version it is written for RGB charts only. The chart "
                "itself is fine.")
            return res
        order = _entries(ti2, side, idx, rows)
        out_dir.mkdir(parents=True, exist_ok=True)
        txf = out_dir / txf_name(stem)
        write_txf(ti2, side, txf, stem, order)
        d = design_for(side)
        pads = set(side.get("padding_locs") or ())
        doc = {
            "kind": ORDER_KIND, "version": ORDER_VERSION,
            "what": "ChromIQ i1iSis chart: entry j of the i1Profiler patch "
                    "list (1-based) is the chart patch named here",
            "chart": ti2.name, "chart_sha256": sha256_of(ti2),
            "device": d.device, "columns": d.columns, "rows": d.rows,
            "pages": d.pages, "patches": len(order),
            "txf_page_mm": [round(d.page_w, 3), round(d.page_h, 3)],
            "order": [dict({"sample_id": sid, "loc": loc},
                           **({"pad": True} if loc in pads else {}))
                      for sid, loc, _v in order],
        }
        order_path = out_dir / order_name(stem)
        order_path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        res.txf, res.order = txf, order_path
        res.written += [txf, order_path]
    except Exception:  # noqa: BLE001 - never break a chart build
        log.warning("i1iSis i1Profiler export failed", exc_info=True)
        res.skipped = tr("The i1Profiler test chart could not be written; "
                         "the chart itself is fine.")
    return res


def ensure_export(ti2: "str | Path") -> "IsisExport | None":
    """Write the ``.txf`` and order file of the i1iSis chart *ti2* into its
    exports folder when either is missing (they are derived files, swept by
    every build; the chart and its side file are what they come from). None
    for any other chart, and with the Beta off nothing is read. Never
    raises."""
    try:
        from .support import chart_names_isis, isis_enabled
        ti2 = Path(ti2)
        if not isis_enabled() or chart_names_isis(ti2) is not True:
            return None
        from core.file_manager import exports_subdir
        out = exports_subdir(ti2.parent)
        stem = ti2.name[:-4]
        if (out / txf_name(stem)).is_file() and (out / order_name(stem)).is_file():
            return None
        return write_isis_export(ti2, out, stem)
    except Exception:  # noqa: BLE001 - a derived file, never a failure
        log.warning("i1iSis export not written again", exc_info=True)
        return None
