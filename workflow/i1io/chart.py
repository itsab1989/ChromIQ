"""An i1iO chart: the layout engine's own strip chart, plus what the table needs.

THE STRIPS RUN ALONG THE ARM. The engine lays every chart out in strips down
the long side of the page; for the i1iO each strip is one line the arm scans
in one move. The chart is therefore printed on a PORTRAIT A4 or Letter sheet
and laid ACROSS the table (a quarter turn), so its long side, and with it every
strip, runs along the arm's scan axis (the table's X: PROTOCOL 3.1 and 4.4, the
`m2` scan moves change X only, along the 32 cm side of the measuring area).
Strip letters, patch numbers, the contrast spacers between the patches of a
strip, the gap between strips and the `.ti2`'s strip structure then mean what
they mean on every ChromIQ chart: "C7" is the 7th patch of strip C.

The patches, their values, the randomising, the pages, the labels, the
spacers, the TIFF, the PDF, the ``.ti2`` and ``.strips.json`` are the engine's
(`workflow.layout_engine.chart.build_chart`), with the settings an i1iO chart
fixes (:func:`fixed_build_kwargs`). This module adds the rest:

* three numbered aiming marks. On the table (sheet turned) they sit top-left
  (1), bottom-left (2) and bottom-right (3), the order i1Profiler asks for;
  on the portrait page that is top-right, top-left and bottom-left. Their
  digits, the chart's name, the page "N/M", the sheet text and the ChromIQ
  wordmark are printed turned, so they read the right way up on the table.
  No arrow: the person aims at the numbers, so either quarter turn is aimed
  in the right order and the fit from the three points places every patch;
* a check, before anything is written, that every patch, every strip's
  run-in and run-out and every mark is on the sheet and clear of each other
  (:func:`check_sheet`);
* the side file ``<stem>.i1io.json``: every mark, strip and patch in
  millimetres on the page, for the measuring step.

Every number comes from `workflow.i1io.table_facts`, with its source. Nothing
here talks to a table.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import table_facts as F

#: The sheets Guided offers for the i1iO: portrait, laid across the table.
GUIDED_PAPERS = ("A4", "Letter")

#: The build-kwargs key that carries the label wishes past
#: `fixed_build_kwargs` (kept for callers; the labels are the engine's own).
LABELS_KEY = "_i1io_labels"

#: Schema of the side file (also in the `.ti2` keyword CHROMIQ_I1IO_LAYOUT).
SCHEMA = 1


class I1ioSheetRefused(ValueError):
    """The sheet cannot hold an i1iO chart (the reason is in the message)."""


def paper_for(paper) -> str:
    """The i1iO sheet for a person coming from *paper*: Letter for anyone on a
    US sheet, A4 for everyone else (Guided picks no paper by locale anywhere,
    so the paper already on screen is the best evidence)."""
    return ("Letter" if str(paper or "") in ("Letter", "LetterR", "Legal",
                                             "11x17", "203x254")
            else "A4")


@dataclass(frozen=True)
class Labels:
    """The engine's own label switches for an i1iO chart: the strip letters
    (above every strip, beyond its run-in) and the patch numbers (beside the
    first strip). The table needs neither; the person does."""
    columns: bool = True     # the patch numbers (the engine's row indicators)
    rows: bool = True        # the strip letters (the engine's strip indicators)
    size: float = F.LABEL_SIZE_MM.value


def label_wishes(kw: dict) -> Labels:
    """The engine's label switches as *kw* holds them."""
    return Labels(columns=kw.get("row_indicators") is not False,
                  rows=kw.get("draw_indicators", True) is not False,
                  size=float(kw.get("indicator_size_mm") or 0.0)
                  or F.LABEL_SIZE_MM.value)


def fixed_build_kwargs(kw: dict) -> dict:
    """*kw* (a layout-engine build-kwargs dict) with what an i1iO chart fixes:
    patch-first, centred, no edge spacers (they would print on the run-in), no
    helper markers (no ruler), no clip border, no bottom text or stamp (their
    place is the turned text line), the strip letters at the page's top text
    edge, and margins never below the safe minimum (`table_facts.margins_mm`:
    the letters and the run-in above every strip, the run-out below, the
    marks' zones at the sides). What a person may set is kept, inside the
    table's limits: the patch size, the spacers (none, coloured or black and
    white; default coloured), the gaps, the labels and the margins. Used by
    the capacity estimate and by the build alike, so the two cannot disagree."""
    out = dict(kw)
    # Engine terms: patch_h is the length ALONG a strip (the scan), patch_w
    # the width across it.
    along, across = F.patch_size_mm(kw.get("patch_h"), kw.get("patch_w"))
    labels = label_wishes(kw)
    mode = kw.get("spacer_mode")
    if mode not in ("none", "colored", "bw"):
        mode = F.SPACER_MODE.value
    if kw.get("spacer_on") is False and kw.get("spacer_mode") is None:
        mode = "none"
    least = F.margins_mm(labels.rows, labels.size)
    asked = kw.get("margins")
    try:
        asked = tuple(float(v) for v in asked) if asked else None
    except (TypeError, ValueError):
        asked = None
    margins = (tuple(max(a, m) for a, m in zip(asked, least))
               if asked and len(asked) == 4 else least)
    strip_gap, inter_patch = F.gaps_mm(kw.get("strip_gap"),
                                       kw.get("inter_patch"))
    out.update(
        patch_w=across, patch_h=along, pscale=1.0, sscale=1.0,
        spacer_on=mode != "none", spacer_mode=mode,
        spacer_width=F.SPACER_MM.value if mode != "none" else None,
        inter_patch=inter_patch, strip_gap=strip_gap, edge_spacers=False,
        margins=margins, use_instrument_margins=True,
        layout_mode="patch_first", patch_area_align="center",
        density=1, cm_stagger=False, max_strip=None, offset_x=0.0,
        offset_y=0.0, nolpcbord=True, nolimit=True, clip_band=0.0,
        clip_content_mode="off", helper_markers=False, chart_text="",
        stamp_command=False, side_stamp=False, strip_indicator_gap=0.0,
        text_edge_top=4.0, strip_label_offset_mm=0.0,
        strip_label_offset_x_mm=0.0,
        # the letters and numbers turned to read upright on the table
        indicator_rotation=F.LABEL_TURN_DEG.value,
        row_indicator_rotation=F.LABEL_TURN_DEG.value,
    )
    out[LABELS_KEY] = labels
    return out


def sheet_size(paper: str) -> "tuple[float, float]":
    """``(width, height)`` of *paper* in mm, refused unless it lies PORTRAIT
    and, laid across the table, inside the arm's reach."""
    from workflow.layout_engine.papers import dimensions_mm
    w, h = dimensions_mm(paper)
    rx, ry = F.REACH_MM.value
    if w > h:
        raise I1ioSheetRefused(
            f"An i1iO chart is printed on a portrait sheet (this one is "
            f"{w:g} x {h:g} mm) and laid across the table, so its strips run "
            f"along the arm.")
    if h > rx + 1e-6 or w > ry + 1e-6:
        raise I1ioSheetRefused(
            f"This sheet ({w:g} x {h:g} mm), laid across the table, is larger "
            f"than the area the i1iO's arm can reach ({rx:g} x {ry:g} mm).")
    return w, h


# ---- where everything goes, in mm on the portrait page -----------------------

@dataclass(frozen=True)
class Mark:
    number: int
    corner: str            # on the TABLE, the sheet laid across it
    centre_mm: "tuple[float, float]"   # on the PAGE


def marks(w: float, h: float) -> "list[Mark]":
    """The three aiming marks, in the order the person aims at them. The
    sheet lies across the table turned a quarter turn CLOCKWISE (its top edge
    to the person's right, so strip A is the top strip on the table), so the
    table's top-left is the page's bottom-left, and so on."""
    i = F.MARK_INSET_MM.value
    return [Mark(1, "top-left", (i, h - i)),
            Mark(2, "bottom-left", (w - i, h - i)),
            Mark(3, "bottom-right", (w - i, i))]


def digit_offset(mark: Mark) -> "tuple[float, float]":
    """Where a mark's digit sits from its centre, on the page: towards the
    middle of the sheet across the strips, never towards a paper edge."""
    away = F.MARK_CROSS_MM.value / 2.0 + 1.0 + F.MARK_DIGIT_MM.value / 2.0
    cx = mark.centre_mm[0]
    return ((-away, 0.0) if cx > F.MARK_INSET_MM.value * 2 else (away, 0.0))


def mark_zone(mark: Mark) -> "tuple[float, float, float, float]":
    """``(x0, y0, x1, y1)`` the mark and its digit take, plus the clearance."""
    cx, cy = mark.centre_mm
    half = F.MARK_CROSS_MM.value / 2.0
    clear = F.MARK_CLEAR_MM.value
    dx, _dy = digit_offset(mark)
    dh = F.MARK_DIGIT_MM.value / 2.0
    x0, x1 = min(cx - half, cx + dx - dh), max(cx + half, cx + dx + dh)
    return (x0 - clear, cy - half - clear, x1 + clear, cy + half + clear)


def page_patches(geom, layout, w: float, h: float, page: int
                 ) -> "list[tuple[int, int, int, float, float, float, float]]":
    """``(global slot, strip on the page, position, x0, y0, x1, y1)`` in mm
    for every patch slot on *page*, exactly as `geometry.patch_rects_px` walks
    them (strip by strip, down each strip)."""
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


def scan_strips(cells):
    """The scan lines of one page: ``[(x_centre, run_start_y, run_end_y,
    [cells top to bottom])]``, one per strip, read along the page's Y (the
    table's X) with :data:`F.RUN_MM` of blank paper at each end."""
    strips: dict[int, list] = {}
    for cell in cells:
        strips.setdefault(cell[1], []).append(cell)
    run = F.RUN_MM.value
    out = []
    for p in sorted(strips):
        col = sorted(strips[p], key=lambda c: c[4])
        x = (col[0][3] + col[0][5]) / 2.0
        out.append((x, col[0][4] - run, col[-1][6] + run, col))
    return out


def check_sheet(geom, layout, w: float, h: float) -> None:
    """Refuse a layout the table could not read: a patch or a strip's run off
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
        for _x, y_start, y_end, col in scan_strips(cells):
            if y_start < edge - 1e-6 or y_end > h - edge + 1e-6:
                raise I1ioSheetRefused(
                    "A strip has no room before its first or after its last "
                    "patch for the arm to reach its speed and to stop.")
            run = (col[0][3], y_start, col[0][5], y_end)
            if any(_overlap(run, z) for z in zones):
                raise I1ioSheetRefused("A strip's run would cross an aiming mark.")


def text_column(w: float, h: float) -> "tuple[float, float, float, float]":
    """The paper the turned text line may use, ``(x0, y0, x1, y1)``: the
    right-hand margin between marks 3 and 2 (on the table, the bottom edge
    between marks 2 and 3), where no strip and no run ever is."""
    top = mark_zone(marks(w, h)[2])[3] + 2.0
    bottom = mark_zone(marks(w, h)[1])[1] - 2.0
    return (w - F.MARK_SIDE_MM.value + 1.0, top,
            w - F.PRINTER_EDGE_MM.value, bottom)


# ---- drawing -----------------------------------------------------------------

def _font(px: int, family: str = "Inter", italic: bool = False,
          bold: bool = True):
    from workflow.layout_engine import raster
    path, variation = raster._font_file_and_variation(family, bold, italic)
    return raster._font(px, family, bold=bold, italic=italic), path, variation


def draw_furniture(render, w: float, h: float, dpi: int, *, name: str,
                   geom=None, layout=None, labels: "Labels | None" = None,
                   patterns: "tuple | None" = None, sheet_text: str = "",
                   text_ctx: "dict | None" = None) -> None:
    """Draw the marks and the turned text line onto every page of *render*:
    into the page image, from which the separated TIFF folds them into the
    black ink, and into the PDF display list when there is one. In place.

    THE TEXT IS TURNED a quarter turn anticlockwise on the page, so it reads
    the right way up on the sheet laid across the table (turned clockwise),
    from the page's bottom upwards."""
    from PIL import Image, ImageDraw
    s = dpi / 25.4

    def px(mm: float) -> int:
        return int(round(mm * s))

    black = (0, 0, 0)
    pages = len(render.images)
    line = max(1, px(F.MARK_LINE_MM.value))
    half = F.MARK_CROSS_MM.value / 2.0
    fhalf = F.MARK_FRAME_MM.value / 2.0
    digit_px = px(F.MARK_DIGIT_MM.value / 0.73)
    small_px = px(3.0 / 0.73)
    for index, img in enumerate(render.images):
        draw = ImageDraw.Draw(img)
        geom_list = (render.patch_geom[index]
                     if getattr(render, "patch_geom", None) is not None else None)

        def rect(x0: int, y0: int, x1: int, y1: int) -> None:
            if x1 <= x0 or y1 <= y0:
                return
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=black)
            if geom_list is not None:
                geom_list.append(("vrect", (x0, y0, x1, y1), black))

        def turned_text(txt: str, centre: "tuple[float, float]", size_px: int,
                        family: str = "Inter", italic: bool = False,
                        bold: bool = True, rgb=black,
                        anchor: str = "centre") -> "tuple[int, int]":
            """*txt* turned a quarter turn anticlockwise, centred on
            *centre* (mm), or with its START at *centre* (the text then runs
            UP the page from there) when *anchor* is "start". Returns its
            (width, height) on the page in pixels."""
            font, path, var = _font(size_px, family, italic, bold)
            bb = draw.textbbox((0, 0), txt, font=font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            tile = Image.new("L", (max(1, tw), max(1, th)), 0)
            ImageDraw.Draw(tile).text((-bb[0], -bb[1]), txt, font=font,
                                      fill=255)
            tile = tile.rotate(90, expand=True)           # anticlockwise
            cx, cy = px(centre[0]), px(centre[1])
            x0 = cx - tile.width // 2
            y0 = (cy - tile.height if anchor == "start"
                  else cy - tile.height // 2)
            img.paste(Image.new("RGB", tile.size, rgb), (x0, y0), tile)
            if geom_list is not None and path:
                ascent = font.getmetrics()[0]
                # The run turned about its (left, baseline) anchor: on the
                # page the baseline runs UP the tile at ascent from its left.
                geom_list.append(("text", x0 + (ascent - bb[1]),
                                  y0 + tw + bb[0], txt, path, size_px, 0, 90,
                                  rgb, var))
            return tile.width, tile.height

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
            dx, dy = digit_offset(mark)
            turned_text(str(mark.number), (cx + dx, cy + dy), digit_px)
        # THE TEXT LINE, turned, in the right-hand margin below mark 1 (on the
        # table: along the top edge, right of mark 1): the ChromIQ wordmark,
        # then the page "N/M", the chart's name and Manual's sheet text, cut
        # to fit with "…". Paper no strip can use, so none of it costs a patch.
        x0, y0, x1, y1 = text_column(w, h)
        cx = (x0 + x1) / 2.0
        y = y1                       # the text starts at the bottom, runs up
        wm = wordmark_box(geom, layout, w, h, index, labels)
        if wm is not None:
            wpx = px(wm[4] / 0.74)
            ww, wh = turned_text("Chrom", (cx, y), wpx, family="Instrument Serif",
                                 bold=False, rgb=(28, 27, 24), anchor="start")
            turned_text("IQ", (cx, y - wh / s - 0.3), wpx,
                        family="Instrument Serif", italic=True, bold=False,
                        rgb=(255, 69, 115), anchor="start")
            y = wm[1] - 4.0
        full = str(name or "")
        if pages > 1:
            full = f"{index + 1}/{pages}  ·  {full}" if full else \
                f"{index + 1}/{pages}"
        extra = str(sheet_text or "").strip()
        if extra:
            for key, value in (text_ctx or {}).items():
                extra = extra.replace("{" + key + "}", str(value))
            extra = extra.replace("{page}", f"{index + 1}/{pages}")
            full = f"{full}  ·  {extra}" if full else extra
        room = px(y - y0)
        font, _p, _v = _font(small_px)
        label, keep = full, len(full)
        while label:
            bb = draw.textbbox((0, 0), label, font=font)
            if (bb[2] - bb[0]) <= room:
                break
            keep -= 1
            label = full[:keep] + "…" if keep > 0 else ""
        if label:
            turned_text(label, (cx, y), small_px, anchor="start")


def wordmark_box(geom, layout, w: float, h: float, page: int,
                 labels: "Labels | None" = None):
    """Where the ChromIQ wordmark goes, ``(x0, y0, x1, y1, height)`` in mm on
    the page, or None when it is left off.

    THE LOGO NEVER COSTS A PATCH (Basti, 2026-11-13): it is no layout input,
    it is drawn only in the text column (`text_column`), where no strip and no
    run ever is, tried at full size and then smaller down to the smallest
    legible size, and left off only when even that does not fit."""
    x0, y0, x1, y1 = text_column(w, h)
    size = F.WORDMARK_MM.value
    while size >= F.WORDMARK_MIN_MM.value - 1e-9:
        length = 5.0 * size
        if size + 1.0 <= (x1 - x0) and y1 - length >= y0:
            return (x0, y1 - length, x1, y1, size)
        size -= 0.5
    return None


# ---- the side file -----------------------------------------------------------

def write_side_file(path: Path, *, geom, layout, w: float, h: float,
                    paper: str, dpi: int, seed: int, randomize: bool,
                    strip_pattern: str, patch_pattern: str, label_rule: str,
                    designed: int, labels: "Labels | None" = None) -> Path:
    """Write ``<stem>.i1io.json``: every mark, strip and patch in mm on the
    portrait page, for the measuring step."""
    from workflow.layout_engine import permutation
    from .support import HEAD_MODEL, TABLE_MODEL, TARGET_INSTRUMENT
    slots = permutation.location_permutation(layout.total_patches, seed,
                                             randomize)
    sample_of = {slot: i + 1 for i, slot in enumerate(slots)}
    pages = []
    for page in range(layout.pages):
        cells = page_patches(geom, layout, w, h, page)
        strips = []
        for x, y_start, y_end, col in scan_strips(cells):
            strips.append({
                "x_mm": round(x, 4),
                "run_mm": [round(y_start, 4), round(y_end, 4)],
                "patches": [{
                    "loc": permutation.location_label(
                        c[0], layout.steps_in_pass, strip_pattern,
                        patch_pattern, label_rule),
                    "sample_id": sample_of[c[0]],
                    "centre_mm": [round((c[3] + c[5]) / 2.0, 4),
                                  round((c[4] + c[6]) / 2.0, 4)],
                } for c in col],
            })
        wm = wordmark_box(geom, layout, w, h, page, labels)
        pages.append({"page": page + 1, "strips": strips,
                      "wordmark_mm": list(wm) if wm else None,
                      "text_column_mm": list(text_column(w, h))})
    doc = {
        "schema": SCHEMA,
        "instrument": TARGET_INSTRUMENT,
        "table_model": TABLE_MODEL,
        "head_model": HEAD_MODEL,
        "paper": paper,
        "paper_mm": [w, h],
        "orientation": "portrait page laid across the table, a quarter turn "
                       "clockwise (its top edge to the right): its Y is the "
                       "table's X",
        "scan_axis": "y",
        "patch_mm": [geom.pwid, geom.plen],
        "spacer_mm": round(geom.pspa, 4),
        "strip_gap_mm": round(geom.rrsp - geom.pwid, 4),
        "marks_mm": [{"number": m.number, "corner_on_table": m.corner,
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
