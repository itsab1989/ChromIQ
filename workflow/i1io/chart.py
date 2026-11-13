"""An i1iO chart: the layout engine's own grid, plus what the table needs.

The patches, their values, the randomising, the pages, the TIFF, the PDF, the
``.ti2`` and ``.strips.json`` are the ordinary layout engine's
(`workflow.layout_engine.chart.build_chart`), with the settings an i1iO chart
fixes (:func:`fixed_build_kwargs`). This module adds the rest:

* three numbered aiming marks at the sheet's corners, top-left (1),
  bottom-left (2) and bottom-right (3), the order i1Profiler asks for;
* an arrow at the top centre (this edge goes towards the back of the table,
  where the arm parks), the page "N/M" beside it on a chart of several sheets,
  and the chart's name at the bottom, all without words, so nothing printed
  needs translating;
* a check, before anything is written, that every patch, every row's run-in and
  run-out and every mark is on the sheet, inside the arm's reach and clear of
  each other (:func:`check_sheet`);
* the side file ``<stem>.i1io.json``: every mark and every patch in
  millimetres, and the scan rows, for the measuring step.

Every number comes from `workflow.i1io.table_facts`, with its source. Nothing
here talks to a table.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import table_facts as F

#: The sheets Guided offers for the i1iO: landscape, inside the arm's reach.
GUIDED_PAPERS = ("A4R", "LetterR")

#: Schema of the side file (also in the `.ti2` keyword CHROMIQ_I1IO_LAYOUT).
SCHEMA = 1


class I1ioSheetRefused(ValueError):
    """The sheet cannot hold an i1iO chart (the reason is in the message)."""


def fixed_build_kwargs(kw: dict) -> dict:
    """*kw* (a layout-engine build-kwargs dict) with everything an i1iO chart
    fixes set to the i1iO's value: its patch size, no gaps or spacers, its
    margins, centred patches, and none of the engine's own furniture (labels,
    clip border, helper markers, bottom text, the right-edge stamp), whose
    place on the sheet belongs to the marks. Used by the capacity estimate and
    by the build alike, so the two cannot disagree."""
    out = dict(kw)
    out.update(
        patch_w=F.PATCH_ALONG_MM.value, patch_h=F.PATCH_ACROSS_MM.value,
        pscale=1.0, sscale=1.0, spacer_on=False, spacer_mode="none",
        spacer_width=None, inter_patch=0.0, strip_gap=0.0, edge_spacers=False,
        margins=F.margins_mm(), use_instrument_margins=True,
        layout_mode="patch_first", patch_area_align="center",
        hflag=False, hex_flat_top=False, density=1, cm_stagger=False,
        max_strip=None, offset_x=0.0, offset_y=0.0, nolpcbord=True,
        nolimit=True, clip_band=0.0, clip_content_mode="off",
        draw_indicators=False, row_indicators=False, helper_markers=False,
        chart_text="", stamp_command=False, side_stamp=False,
    )
    return out


def sheet_size(paper: str) -> "tuple[float, float]":
    """``(width, height)`` of *paper* in mm, refused unless it lies landscape
    inside the arm's reach."""
    from workflow.layout_engine.papers import dimensions_mm
    w, h = dimensions_mm(paper)
    rw, rh = F.REACH_MM.value
    if w < h:
        raise I1ioSheetRefused(
            f"An i1iO chart is printed on a landscape sheet (this one is "
            f"{w:g} x {h:g} mm): the arm scans along the sheet's long side.")
    if w > rw + 1e-6 or h > rh + 1e-6:
        raise I1ioSheetRefused(
            f"This sheet ({w:g} x {h:g} mm) is larger than the area the i1iO's "
            f"arm can reach ({rw:g} x {rh:g} mm).")
    return w, h


# ---- where everything goes, in mm -----------------------------------------

@dataclass(frozen=True)
class Mark:
    number: int
    corner: str
    centre_mm: "tuple[float, float]"


def marks(w: float, h: float) -> "list[Mark]":
    """The three aiming marks, in the order the person aims at them."""
    i = F.MARK_INSET_MM.value
    return [Mark(1, "top-left", (i, i)),
            Mark(2, "bottom-left", (i, h - i)),
            Mark(3, "bottom-right", (w - i, h - i))]


def mark_zone(mark: Mark) -> "tuple[float, float, float, float]":
    """``(x0, y0, x1, y1)`` the mark and its digit take, plus the clearance."""
    cx, cy = mark.centre_mm
    half = F.MARK_CROSS_MM.value / 2.0
    clear = F.MARK_CLEAR_MM.value
    digit = 1.0 + F.MARK_DIGIT_MM.value * 0.75
    x0, x1 = cx - half, cx + half
    if digit_on_left(mark):
        x0 -= digit
    else:
        x1 += digit
    return (x0 - clear, cy - half - clear, x1 + clear, cy + half + clear)


def digit_on_left(mark: Mark) -> bool:
    """The digit sits on the side of the mark towards the middle of the
    sheet, never towards the paper edge a printer may not reach."""
    return mark.corner.endswith("right")


def page_patches(geom, layout, w: float, h: float, page: int
                 ) -> "list[tuple[int, int, int, float, float, float, float]]":
    """``(global slot, pass, position, x0, y0, x1, y1)`` in mm for every patch
    slot on *page*, exactly as `geometry.patch_rects_px` walks them."""
    from workflow.layout_engine import geometry
    place = geometry.placement(geom, w, h, layout)
    steps = layout.steps_in_pass
    first = page * layout.patches_per_page
    last = min(layout.total_patches, first + layout.patches_per_page)
    out = []
    for wp in range(last - first):
        p, j = wp // steps, wp % steps
        x0, y0 = place.x_of(p), place.y_of(j)
        out.append((first + wp, p, j, x0, y0, x0 + place.pwid, y0 + place.plen))
    return out


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def anchor_bars(row) -> "list[tuple[float, float, float, float]]":
    """The two black bars of a scan row, ``(x0, y0, x1, y1)``: one in the
    run-in before the first patch and one in the run-out after the last."""
    gap, bar = F.ANCHOR_BAR_GAP_MM.value, F.ANCHOR_BAR_MM.value
    y0, y1 = row[0][4], row[0][6]
    left, right = row[0][3], row[-1][5]
    return [(left - gap - bar, y0, left - gap, y1),
            (right + gap, y0, right + gap + bar, y1)]


def scan_rows(cells, w: float):
    """The scan rows of one page: ``[(y_centre, run_start_x, run_end_x,
    [cells in X order])]``, a row being every patch at one position down the
    page, read along X with :data:`F.RUN_MM` of blank paper at each end."""
    rows: dict[int, list] = {}
    for cell in cells:
        rows.setdefault(cell[2], []).append(cell)
    run = F.RUN_MM.value
    out = []
    for j in sorted(rows):
        row = sorted(rows[j], key=lambda c: c[3])
        y = (row[0][4] + row[0][6]) / 2.0
        out.append((y, row[0][3] - run, row[-1][5] + run, row))
    return out


def check_sheet(geom, layout, w: float, h: float) -> None:
    """Refuse a layout the table could not read: a patch or a row's run off
    the sheet or into a mark, or a mark off the sheet."""
    edge = F.RUN_EDGE_MM.value
    zones = [mark_zone(m) for m in marks(w, h)]
    for zx0, zy0, zx1, zy1 in zones:
        if zx0 < 0 or zy0 < 0 or zx1 > w or zy1 > h:
            raise I1ioSheetRefused("An aiming mark would not fit on the sheet.")
    for page in range(layout.pages):
        cells = page_patches(geom, layout, w, h, page)
        for cell in cells:
            box = cell[3:]
            if box[0] < 0 or box[1] < 0 or box[2] > w or box[3] > h:
                raise I1ioSheetRefused("A patch would lie off the sheet.")
            if any(_overlap(box, z) for z in zones):
                raise I1ioSheetRefused("A patch would touch an aiming mark.")
        for y, x_start, x_end, row in scan_rows(cells, w):
            if x_start < edge - 1e-6 or x_end > w - edge + 1e-6:
                raise I1ioSheetRefused(
                    "A row has no room before its first or after its last "
                    "patch for the arm to reach its speed and to stop.")
            run = (x_start, row[0][4], x_end, row[0][6])
            if any(_overlap(run, z) for z in zones):
                raise I1ioSheetRefused("A row's run would cross an aiming mark.")
            for bar in anchor_bars(row):
                if bar[0] < x_start - 1e-6 or bar[2] > x_end + 1e-6:
                    raise I1ioSheetRefused("A row's bar would lie outside its run.")


# ---- drawing ---------------------------------------------------------------

def _font(px: int):
    from workflow.layout_engine import raster
    path, variation = raster._font_file_and_variation("Inter", True, False)
    return raster._font(px, "Inter", bold=True), path, variation


def draw_furniture(render, w: float, h: float, dpi: int, *, name: str,
                   geom=None, layout=None) -> None:
    """Draw the marks, the arrow, the page and the name onto every page of
    *render* (`raster.RenderResult`): into the page image, from which the
    separated TIFF folds them into the black ink, and into the PDF display
    list when there is one. In place."""
    from PIL import ImageDraw
    s = dpi / 25.4

    def px(mm: float) -> int:
        return int(round(mm * s))

    black = (0, 0, 0)
    pages = len(render.images)
    line = max(1, px(F.MARK_LINE_MM.value))
    half = F.MARK_CROSS_MM.value / 2.0
    fhalf = F.MARK_FRAME_MM.value / 2.0
    digit_px = px(F.MARK_DIGIT_MM.value)
    small_px = px(3.0)
    dfont, dpath, dvar = _font(digit_px)
    sfont, spath, svar = _font(small_px)
    for index, img in enumerate(render.images):
        draw = ImageDraw.Draw(img)
        geom_list = (render.patch_geom[index]
                     if getattr(render, "patch_geom", None) is not None else None)

        def rect(x0: int, y0: int, x1: int, y1: int) -> None:
            """A filled box, half-open like the PDF's `vrect`."""
            if x1 <= x0 or y1 <= y0:
                return
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=black)
            if geom_list is not None:
                geom_list.append(("vrect", (x0, y0, x1, y1), black))

        def text(left: int, centre_y: int, txt: str, font, path, var, size):
            bb = draw.textbbox((0, 0), txt, font=font)
            top = centre_y - (bb[3] + bb[1]) // 2
            draw.text((left - bb[0], top), txt, font=font, fill=black)
            if geom_list is not None and path:
                ascent = font.getmetrics()[0]
                geom_list.append(("text", left - bb[0], top + ascent, txt, path,
                                  size, 0, 0, black, var))
            return bb[2] - bb[0]

        # The rows' anchor bars (`anchor_bars`): black, drawn per row, so
        # rows that touch make one continuous bar down each side.
        if geom is not None and layout is not None:
            for _y, _x0, _x1, row in scan_rows(
                    page_patches(geom, layout, w, h, index), w):
                for bx0, by0, bx1, by1 in anchor_bars(row):
                    rect(px(bx0), px(by0), px(bx1), px(by1))
        for mark in marks(w, h):
            cx, cy = mark.centre_mm
            x, y = px(cx), px(cy)
            hl = line // 2
            rect(px(cx - half), y - hl, px(cx + half), y - hl + line)
            rect(x - hl, px(cy - half), x - hl + line, px(cy + half))
            fx0, fy0, fx1, fy1 = (px(cx - fhalf), px(cy - fhalf),
                                  px(cx + fhalf), px(cy + fhalf))
            rect(fx0, fy0, fx1, fy0 + line)
            rect(fx0, fy1 - line, fx1, fy1)
            rect(fx0, fy0, fx0 + line, fy1)
            rect(fx1 - line, fy0, fx1, fy1)
            if digit_on_left(mark):
                bb = draw.textbbox((0, 0), str(mark.number), font=dfont)
                left = px(cx - half - 1.0) - (bb[2] - bb[0])
            else:
                left = px(cx + half + 1.0)
            text(left, y, str(mark.number), dfont, dpath, dvar, digit_px)
        # The arrow: this edge towards the back of the table.
        cx, cy = w / 2.0, F.MARK_INSET_MM.value
        tip, base, hw = cy - 3.5, cy + 0.5, 2.5
        steps = max(1, px(base - tip))
        for k in range(steps):
            y0 = px(tip) + k
            half_w = hw * (k + 1) / steps
            rect(px(cx - half_w), y0, px(cx + half_w), y0 + 1)
        rect(px(cx - 0.6), px(base), px(cx + 0.6), px(cy + 3.5))
        if pages > 1:
            text(px(cx + 4.0), px(cy), f"{index + 1}/{pages}", sfont, spath,
                 svar, small_px)
        # The chart's name, centred between marks 2 and 3, cut to fit.
        left = mark_zone(marks(w, h)[1])[2] + 4.0
        right = mark_zone(marks(w, h)[2])[0] - 4.0
        full = str(name or "")
        label, keep = full, len(full)
        while label:
            bb = draw.textbbox((0, 0), label, font=sfont)
            if (bb[2] - bb[0]) <= px(right - left):
                break
            keep -= 1
            label = full[:keep] + "…" if keep > 0 else ""
        if label:
            bb = draw.textbbox((0, 0), label, font=sfont)
            width = bb[2] - bb[0]
            start = px((left + right) / 2.0) - width // 2
            text(start, px(h - F.MARK_INSET_MM.value), label, sfont, spath,
                 svar, small_px)


# ---- the side file -----------------------------------------------------------

def write_side_file(path: Path, *, geom, layout, w: float, h: float,
                    paper: str, dpi: int, seed: int, randomize: bool,
                    strip_pattern: str, patch_pattern: str, label_rule: str,
                    designed: int) -> Path:
    """Write ``<stem>.i1io.json``: every mark and patch in mm, and the rows."""
    from workflow.layout_engine import permutation
    from .support import HEAD_MODEL, TABLE_MODEL, TARGET_INSTRUMENT
    slots = permutation.location_permutation(layout.total_patches, seed,
                                             randomize)
    sample_of = {slot: i + 1 for i, slot in enumerate(slots)}
    pages = []
    for page in range(layout.pages):
        cells = page_patches(geom, layout, w, h, page)
        rows = []
        for y, x_start, x_end, row in scan_rows(cells, w):
            rows.append({
                "y_mm": round(y, 4),
                "run_mm": [round(x_start, 4), round(x_end, 4)],
                "anchor_bars_mm": [[round(v, 4) for v in (b[0], b[2])]
                                   for b in anchor_bars(row)],
                "patches": [{
                    "loc": permutation.location_label(
                        c[0], layout.steps_in_pass, strip_pattern,
                        patch_pattern, label_rule),
                    "sample_id": sample_of[c[0]],
                    "centre_mm": [round((c[3] + c[5]) / 2.0, 4),
                                  round((c[4] + c[6]) / 2.0, 4)],
                } for c in row],
            })
        pages.append({"page": page + 1, "rows": rows})
    doc = {
        "schema": SCHEMA,
        "instrument": TARGET_INSTRUMENT,
        "table_model": TABLE_MODEL,
        "head_model": HEAD_MODEL,
        "paper": paper,
        "paper_mm": [w, h],
        "patch_mm": [geom.pwid, geom.plen],
        "gap_mm": [0.0, 0.0],
        "scan_axis": "x",
        "marks_mm": [{"number": m.number, "corner": m.corner,
                      "centre_mm": list(m.centre_mm)} for m in marks(w, h)],
        "page_count": layout.pages,
        "pages": pages,
        "generation": {"seed": seed, "randomize": bool(randomize), "dpi": dpi,
                       "designed_patches": designed,
                       "padding_patches": layout.padding},
        "table_facts": F.as_record(),
    }
    path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    return path
