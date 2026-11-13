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
  on the portrait page that is bottom-left, bottom-right and top-right. Their
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


def paper_label_code(paper: str) -> str:
    """The paper code whose LABEL a list shows for an i1iO sheet: its
    landscape twin ("A4" -> "A4R"), because the sheet is used landscape, as
    it lies on the table (the owner, 2026-11-13: never "A4 ... Portrait"
    where the person chooses the paper). The chart's own code, its files and
    printing stay portrait."""
    return {"A4": "A4R", "Letter": "LetterR"}.get(str(paper or ""), paper)


@dataclass(frozen=True)
class Labels:
    """The label switches for an i1iO chart: the strip letters (below every
    strip, beyond its run-out: on the table the strip's left end, drawn by
    `draw_furniture`) and the patch numbers (the engine's row indicators,
    beside the first strip: on the table along the top). The table needs
    neither; the person does."""
    columns: bool = True     # the patch numbers (the engine's row indicators)
    rows: bool = True        # the strip letters (Manual's "strip indicators")
    size: float = 0.0        # 0 = automatic, as the engine's labels


def label_wishes(kw: dict) -> Labels:
    """The label switches as *kw* holds them: what a person asked for, kept
    under LABELS_KEY once `fixed_build_kwargs` has run (it hands the engine
    its own switches, the letters off), so a second pass reads the wish and
    not the engine's switch."""
    held = kw.get(LABELS_KEY)
    if isinstance(held, Labels):
        return held
    return Labels(columns=kw.get("row_indicators") is not False,
                  rows=kw.get("draw_indicators", True) is not False,
                  size=label_size_mm(kw.get("indicator_size_mm")))


def label_size_mm(asked) -> float:
    """The label size an i1iO chart prints for *asked* (0 = the engine's
    automatic size): never above `table_facts.LABEL_MAX_MM` (review r3 M1)."""
    try:
        size = float(asked or 0.0)
    except (TypeError, ValueError):
        size = 0.0
    return min(max(size, 0.0), F.LABEL_MAX_MM.value)


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
    crosses = crosses_of(kw)
    clip = clip_width_of(kw)
    least = least_margins_mm(kw)
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
        spacer_width=(F.spacer_width_mm(kw.get("spacer_width"), along)
                      if mode != "none" else None),
        inter_patch=inter_patch, strip_gap=strip_gap, edge_spacers=False,
        margins=margins, use_instrument_margins=True,
        layout_mode="patch_first",
        # Manual's "Patch area alignment" when a person chose one for the
        # i1iO (ALIGN_KEY); else centred between the crosses, and without
        # them at the patch numbers, so what is left over goes to the
        # table's bottom edge, where the text line is (`free_text_plan`)
        patch_area_align=align_of(kw, crosses),
        density=1, cm_stagger=False, max_strip=None, offset_x=0.0,
        offset_y=0.0, nolpcbord=True, nolimit=True, clip_band=0.0,
        clip_content_mode="off", helper_markers=False, chart_text="",
        stamp_command=False, side_stamp=False, strip_indicator_gap=0.0,
        indicator_size_mm=label_size_mm(kw.get("indicator_size_mm")),
        # the strip letters are drawn by `draw_furniture`, at the strips'
        # other end; the engine draws only the patch numbers
        draw_indicators=False, row_indicators=bool(labels.columns),
        text_edge_clip=F.NUMBERS_EDGE_MM.value,
        text_edge_top=4.0, strip_label_offset_mm=0.0,
        strip_label_offset_x_mm=0.0,
        # the letters and numbers turned to read upright on the table
        indicator_rotation=F.LABEL_TURN_DEG.value,
        row_indicator_rotation=F.LABEL_TURN_DEG.value,
    )
    out[LABELS_KEY] = labels
    out[CROSSES_KEY] = crosses
    out[CLIP_KEY] = clip > 0
    if clip > 0:
        # THE CLIP BORDER (an option, off by default): the engine's notes
        # band down the page's LEFT edge (the table's top edge), from the
        # paper edge to *clip* mm in, its content from the "Clip" text
        # distance (10 mm, as the patch numbers) and CLIP_EDGE_MM from the
        # page's top and bottom, or clear of cross 1 in the bottom-left
        # corner (`clip_bottom_mm`). Off, none of these keys is touched, so
        # a chart without the band is built exactly as before.
        mode = str(kw.get("clip_content_mode") or "off")
        out.update(
            clip_band=clip, clip_border_width=clip, clip_side="left",
            clip_content_mode=mode if mode != "off" else "notes",
            text_edge_top=F.CLIP_EDGE_MM.value,
            text_edge=clip_bottom_mm(crosses))
    return out


def least_margins_mm(kw: dict) -> "tuple[float, float, float, float]":
    """The smallest margins ``(top, right, bottom, left)`` the i1iO chart
    *kw* (build kwargs) may have (`table_facts.margins_mm`): the runs, the
    strip letters' band, the crosses' bands or the printer's edge, the
    patch numbers and the clip border, as asked for. The build floors the
    margins with this, and Manual's margin boxes offer nothing below it."""
    labels = label_wishes(kw)
    return F.margins_mm(labels.rows, labels.size, numbers=labels.columns,
                        crosses=crosses_of(kw), clip_mm=clip_width_of(kw))


#: The build-kwargs key for "Aiming crosses" (Manual, Guided, recipes).
CROSSES_KEY = "i1io_crosses"

#: The build-kwargs key for the i1iO's clip border On/Off (Manual's "Clip
#: border", Guided's box, `LayoutRecipe.i1io_clip_border`). Its own key, not
#: `clip_content_mode`, whose recipe default "notes" would have switched the
#: band on for every i1iO recipe saved before the option existed.
CLIP_KEY = "i1io_clip_border"


def clip_width_of(kw: dict) -> float:
    """The clip border's width in mm when *kw* asks for one (CLIP_KEY), at
    least `table_facts.CLIP_MIN_MM`; 0.0 when it is off (the default)."""
    on = kw.get(CLIP_KEY)
    if not (F.CLIP_BORDER.value if on is None else bool(on)):
        return 0.0
    try:
        width = float(kw.get("clip_border_width") or 26.0)
    except (TypeError, ValueError):
        width = 26.0
    return max(width, F.CLIP_MIN_MM.value)


def clip_bottom_mm(crosses: bool) -> float:
    """How far the clip border's content keeps from the page's bottom edge:
    `table_facts.CLIP_EDGE_MM`, or with the crosses past cross 1's zone (the
    cross, its digit and its clearance, in the page's bottom-left corner)
    plus LABEL_CLEAR_MM."""
    if not crosses:
        return F.CLIP_EDGE_MM.value
    w, h = 210.0, 297.0              # the zone's distance from the edge is
    zone = mark_zone(marks(w, h)[0])  # the same on every sheet
    return max(F.CLIP_EDGE_MM.value,
               round(h - zone[1] + F.LABEL_CLEAR_MM.value, 4))


def clip_area(geom, w: float, h: float
              ) -> "tuple[float, float, float, float] | None":
    """``(x0, y0, x1, y1)`` in mm of the clip border's band on the page: the
    engine's own content rectangle (`geometry.clip_area_mm`) from the paper
    edge to the band's inner edge, or None without one."""
    from workflow.layout_engine import geometry
    area = geometry.clip_area_mm(geom, h, w)
    band = clip_band_mm(geom)
    if area is None or band is None:
        return None
    x, y, aw, ah = area
    return (band[0], y, max(band[1], x + aw), y + ah)


def clip_band_mm(geom) -> "tuple[float, float] | None":
    """``(x0, x1)`` on the page of the clip border *geom* lays out (the paper
    edge to its width), or None without one."""
    if float(getattr(geom, "lbord", 0.0) or 0.0) <= 0:
        return None
    return (0.0, float(geom.lbord) + float(geom.border))

#: The build-kwargs key for Manual's "Patch area alignment" chosen for the
#: i1iO (`Recipe.i1io_align`); absent or "" = the i1iO's own default.
ALIGN_KEY = "i1io_align"


def align_of(kw: dict, crosses: bool) -> str:
    """Where the patch block sits: the alignment chosen for the i1iO, else
    `table_facts.ALIGN_WITH_CROSSES` / `ALIGN_WITHOUT_CROSSES`."""
    asked = str(kw.get(ALIGN_KEY) or "")
    if asked in F.ALIGNMENTS:
        return asked
    return (F.ALIGN_WITH_CROSSES.value if crosses
            else F.ALIGN_WITHOUT_CROSSES.value)

#: What a chart's files record as the thing to aim at (`.ti2` keyword
#: CHROMIQ_I1IO_AIM and the side file's "aim"). A chart that records nothing
#: (made before the option) is AIM_UNKNOWN.
AIM_CROSSES = "crosses"
AIM_CORNERS = "corner patches"
AIM_UNKNOWN = "unknown"
AIM_KEYWORD = "CHROMIQ_I1IO_AIM"
#: Without the crosses: the three patches aimed at, per page, in aiming
#: order, e.g. "1: A1 W1 W24; 2: X1 AT1 AT24" ("2: crosses" for a page that
#: keeps them, `page_crosses`).
AIM_PATCHES_KEYWORD = "CHROMIQ_I1IO_AIM_PATCHES"
#: Whether the aiming points' numbers 1, 2, 3 are printed on the sheet: "yes"
#: beside every cross (they cost nothing, `digit_offset`), "no" on a chart
#: aimed at its corner patches. The later on-screen overlay adds numbers only
#: where none are printed: never a second set (the owner, 2026-11-13).
AIM_DIGITS_KEYWORD = "CHROMIQ_I1IO_AIM_DIGITS"


def aim_patches_value(geom, layout, w: float, h: float, crosses,
                      patterns: "tuple | None" = None) -> str:
    """The value of AIM_PATCHES_KEYWORD for a chart with *crosses* (one
    answer, or one per page)."""
    parts = []
    for page in range(layout.pages):
        if on_page(crosses, page):
            parts.append(f"{page + 1}: crosses")
            continue
        names = [p["patch"] for p in aim_points(geom, layout, w, h, page,
                                                False, patterns)]
        parts.append(f"{page + 1}: " + " ".join(names))
    return "; ".join(parts)


def crosses_of(kw: dict) -> bool:
    """Whether *kw* asks for the aiming crosses (default on)."""
    v = kw.get(CROSSES_KEY)
    return F.AIM_CROSSES.value if v is None else bool(v)


def aim_of(crosses: bool) -> str:
    return AIM_CROSSES if crosses else AIM_CORNERS


def aim_recorded(ti2_path) -> str:
    """What the chart *ti2_path* records as the thing to aim at:
    AIM_CROSSES, AIM_CORNERS, or AIM_UNKNOWN (no record, or unreadable).
    The side file ``<stem>.i1io.json`` beside it is asked when the `.ti2`
    has no keyword."""
    import re
    try:
        text = Path(ti2_path).read_text(encoding="utf-8", errors="replace")
    except (OSError, TypeError, ValueError):
        text = ""
    m = re.search(r'^\s*' + AIM_KEYWORD + r'\s+"([^"]*)"', text, re.M)
    if m and m.group(1) in (AIM_CROSSES, AIM_CORNERS):
        return m.group(1)
    try:
        p = Path(str(ti2_path))
        stem = str(p)[:-4] if str(p).lower().endswith(".ti2") else str(p)
        doc = json.loads(Path(stem + ".i1io.json").read_text(encoding="utf-8"))
        if doc.get("aim") in (AIM_CROSSES, AIM_CORNERS):
            return doc["aim"]
    except (OSError, TypeError, ValueError, AttributeError):
        pass
    return AIM_UNKNOWN


def aim_details(ti2_path) -> dict:
    """What a chart records about aiming, for the texts that tell a person
    what to aim at: ``{"aim": AIM_CROSSES | AIM_CORNERS | AIM_UNKNOWN,
    "pages": [{"page": n, "aim": ..., "patches": [names]}], "labels":
    bool}``. ``labels`` says whether the strip letters and patch numbers are
    printed (so a patch can be named); from the side file, else True."""
    aim = aim_recorded(ti2_path)
    out = {"aim": aim, "pages": [], "labels": True}
    if aim == AIM_UNKNOWN:
        return out
    try:
        p = str(ti2_path)
        stem = p[:-4] if p.lower().endswith(".ti2") else p
        doc = json.loads(Path(stem + ".i1io.json").read_text(encoding="utf-8"))
        out["labels"] = bool(doc.get("labels_printed", True))
        for page in doc.get("pages", []):
            out["pages"].append({"page": int(page.get("page", 0)),
                                 "aim": page.get("aim", doc.get("aim")),
                                 "patches": list(page.get("aim_patches")
                                                 or [])})
        return out
    except (OSError, TypeError, ValueError, AttributeError):
        pass
    import re
    try:
        text = Path(ti2_path).read_text(encoding="utf-8", errors="replace")
        m = re.search(r'^\s*' + AIM_PATCHES_KEYWORD + r'\s+"([^"]*)"', text,
                      re.M)
        for part in (m.group(1).split(";") if m else []):
            num, _sep, rest = part.strip().partition(":")
            names = rest.split()
            out["pages"].append({
                "page": int(num),
                "aim": AIM_CROSSES if names == ["crosses"] else AIM_CORNERS,
                "patches": [] if names == ["crosses"] else names})
    except (OSError, TypeError, ValueError):
        pass
    return out


def capacity(kw: dict, crosses: bool) -> int:
    """Patches per sheet for the i1iO build kwargs *kw* with or without the
    crosses (the same geometry the build uses)."""
    from workflow.layout_engine import geometry, instruments, papers
    k = {**kw, "instrument": "IO2", CROSSES_KEY: bool(crosses)}
    paper = k.get("paper") or "A4"
    w, h = papers.dimensions_mm(paper)
    return geometry.patches_per_sheet(instruments.geom_from_build_kwargs(k),
                                      w, h)


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
    """Where a mark's digit sits from its centre, on the page: beside the
    cross ALONG the strips, towards the middle of the page, in the side band
    the cross needs anyway, where no strip, run or label ever is. It costs
    no patch: beside the cross ACROSS the strips it widened both side bands
    by 5 mm and cost a strip on A4 and two on Letter (the owner, 2026-11-13).
    On the table the digit stands to the right of crosses 1 and 2 and to the
    left of cross 3, towards the middle of the edge, upright."""
    away = F.MARK_CROSS_MM.value / 2.0 + 1.0 + F.MARK_DIGIT_MM.value / 2.0
    cy = mark.centre_mm[1]
    return ((0.0, -away) if cy > F.MARK_INSET_MM.value * 2 else (0.0, away))


def mark_zone(mark: Mark) -> "tuple[float, float, float, float]":
    """``(x0, y0, x1, y1)`` the mark and its digit take, plus the clearance."""
    cx, cy = mark.centre_mm
    half = F.MARK_CROSS_MM.value / 2.0
    clear = F.MARK_CLEAR_MM.value
    dx, dy = digit_offset(mark)
    dh = F.MARK_DIGIT_MM.value / 2.0
    x0, x1 = min(cx - half, cx + dx - dh), max(cx + half, cx + dx + dh)
    y0, y1 = min(cy - half, cy + dy - dh), max(cy + half, cy + dy + dh)
    return (x0 - clear, y0 - clear, x1 + clear, y1 + clear)


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
    [cells in strip order, patch 1 first])]``, one per strip, read along the
    page's Y (the table's X) with :data:`F.RUN_MM` of blank paper at each
    end. Patch 1 is at the strip's BOTTOM on the page (`Geom.reverse_steps`:
    the table's left), so the run starts at the top of the highest cell."""
    strips: dict[int, list] = {}
    for cell in cells:
        strips.setdefault(cell[1], []).append(cell)
    run = F.RUN_MM.value
    out = []
    for p in sorted(strips):
        col = sorted(strips[p], key=lambda c: c[2])
        x = (col[0][3] + col[0][5]) / 2.0
        out.append((x, min(c[4] for c in col) - run,
                    max(c[6] for c in col) + run, col))
    return out


def on_page(crosses, page: int) -> bool:
    """Whether page *page* carries the crosses: *crosses* is one answer for
    the whole chart or a list with one per page (`page_crosses`)."""
    if isinstance(crosses, (list, tuple)):
        return bool(crosses[page]) if page < len(crosses) else True
    return bool(crosses)


def check_sheet(geom, layout, w: float, h: float,
                crosses: "bool | list" = True,
                reach: "float | None" = None) -> None:
    """Refuse a layout the table could not read: a patch or a strip's run off
    the sheet or into a mark, or a mark off the sheet. *crosses*: one answer
    or one per page. With a clip border (`clip_area`): the band touching a
    cross or a run, or its printed content (*reach*, mm from the paper edge,
    `raster.clip_content_reach_mm`) within LABEL_CLEAR_MM of a patch."""
    edge = F.RUN_EDGE_MM.value
    band = clip_area(geom, w, h)
    if band is not None and (reach is None or reach < 0):
        reach = getattr(geom, "clip_content_reach_mm", None)
        if reach is None or reach < 0:       # not measured: the whole band
            reach = band[2]
    for zx0, zy0, zx1, zy1 in [mark_zone(m) for m in marks(w, h)]:
        if zx0 < 0 or zy0 < 0 or zx1 > w or zy1 > h:
            raise I1ioSheetRefused("An aiming mark would not fit on the sheet.")
    for page in range(layout.pages):
        zones = ([mark_zone(m) for m in marks(w, h)]
                 if on_page(crosses, page) else [])
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
            if band is not None and _overlap(run, band):
                raise I1ioSheetRefused(
                    "A strip's run would cross the clip border.")
        if band is not None:
            if any(_overlap(band, z) for z in zones):
                raise I1ioSheetRefused(
                    "The clip border would touch an aiming cross.")
            if reach is not None and cells and (
                    reach + F.LABEL_CLEAR_MM.value
                    > min(c[3] for c in cells) + 1e-6):
                raise I1ioSheetRefused(
                    "The clip border's content would reach the patches.")


# ---- without the crosses: the corner patches --------------------------------

#: The four corners of a page's patch block, ON THE TABLE (the sheet a
#: quarter turn clockwise), the three aimed at first, in aiming order.
CORNERS = ("top-left", "bottom-left", "bottom-right", "top-right")


def corner_cells(geom, layout, w: float, h: float, page: int) -> dict:
    """``{corner on the table: cell}`` for page *page* (a cell as
    `page_patches` gives it). On the page, the table's top left is strip A's
    patch 1 (the page's bottom left: `Geom.reverse_steps`), its bottom left
    the last strip's patch 1, its bottom right the last strip's last patch
    and its top right strip A's last patch."""
    cells = page_patches(geom, layout, w, h, page)
    if not cells:
        return {}
    first = min(c[1] for c in cells)
    last = max(c[1] for c in cells)

    def end(strip: int, low_on_page: bool):
        col = [c for c in cells if c[1] == strip]
        # the larger page y is the page's bottom = the table's left
        return (max if low_on_page else min)(col, key=lambda c: c[4])

    return {"top-left": end(first, True), "bottom-left": end(last, True),
            "bottom-right": end(last, False), "top-right": end(first, False)}


def to_table_mm(h: float, point: "tuple[float, float]"
                ) -> "tuple[float, float]":
    """A point on the portrait page, in mm from the page's top left, as it
    lies on the table (the sheet a quarter turn clockwise), in mm from the
    sheet's top left corner there, x to the right and y down."""
    px, py = point
    return (round(h - py, 4), round(px, 4))


def aim_points(geom, layout, w: float, h: float, page: int,
               crosses: bool, patterns: "tuple | None" = None
               ) -> "list[dict]":
    """The three points the person aims at on page *page*, in aiming order:
    the crosses' centres, or without them the centres of the corner patches
    at the table's top left, bottom left and bottom right. Each
    ``{"number", "corner_on_table", "target", "page_mm", "table_mm"}``."""
    out = []
    if crosses:
        for m in marks(w, h):
            out.append({"number": m.number, "corner_on_table": m.corner,
                        "target": "cross", "patch": None,
                        "page_mm": [round(m.centre_mm[0], 4),
                                    round(m.centre_mm[1], 4)],
                        "table_mm": list(to_table_mm(h, m.centre_mm))})
        return out
    cells = corner_cells(geom, layout, w, h, page)
    for n, corner in enumerate(CORNERS[:3], start=1):
        c = cells.get(corner)
        if c is None:
            continue
        centre = ((c[3] + c[5]) / 2.0, (c[4] + c[6]) / 2.0)
        out.append({"number": n, "corner_on_table": corner,
                    "target": "patch", "slot": c[0],
                    "patch": patch_name(c[0], layout, patterns),
                    "page_mm": [round(centre[0], 4), round(centre[1], 4)],
                    "table_mm": list(to_table_mm(h, centre))})
    return out


def patch_name(slot: int, layout, patterns: "tuple | None" = None) -> str:
    """The name ChromIQ prints for the patch in *slot* ("A1": strip A, patch
    1), the strip letters running on across the pages."""
    from workflow.layout_engine import permutation
    sp, pp, rule = patterns or (permutation.DEFAULT_STRIP_PATTERN,
                                permutation.DEFAULT_PATCH_PATTERN,
                                permutation.ARGYLL)
    return permutation.location_label(slot, layout.steps_in_pass, sp, pp,
                                      rule)


def visible(rgb) -> bool:
    """Whether a patch of display colour *rgb* can be aimed at on paper:
    never near white (`table_facts.CORNER_NEVER_L`)."""
    return _lab_of_rgb(rgb)[0] < F.CORNER_NEVER_L.value


def page_crosses(target, layout, geom, w: float, h: float,
                 slots: "list[int]", crosses: bool) -> "list[bool]":
    """One answer per page: does it carry the crosses? All pages do when the
    chart has them. WITHOUT THEM a page still keeps its crosses when its
    three corner patches cannot be aimed at (the owner, 2026-11-13: "never
    tell the user to aim at a patch that is not printed"):

    * a page of ONE strip (the last page of a chart that does not fill it):
      its top-left and bottom-left corner would be one patch, and three
      points on one line place nothing;
    * a page whose corner holds no visible patch (a set with too few that
      are not near white, `corner_order`): paper is not a target.

    The crosses' places lie outside the patches of such a page (it has
    fewer strips than the sheet holds, or `check_sheet` refuses it), so
    nothing else moves."""
    from workflow.layout_engine import raster
    if crosses:
        return [True] * layout.pages
    media = target.media_patch()
    patches = list(target.patches) + [media] * layout.padding
    slot_to_patch = {slot: i for i, slot in enumerate(slots)}
    real = len(target.patches)
    out = []
    for page in range(layout.pages):
        cells = corner_cells(geom, layout, w, h, page)
        strips = {c[1] for c in page_patches(geom, layout, w, h, page)}
        ok = len(strips) >= 2 and len(cells) == 4
        for corner in CORNERS[:3]:
            if not ok:
                break
            i = slot_to_patch.get(cells[corner][0])
            ok = (i is not None and i < real and visible(
                raster.to_display_rgb(patches[i][0], target.color_rep)))
        out.append(not ok)
    return out


def _lab_of_rgb(rgb) -> "tuple[float, float, float]":
    """CIELAB (D65) of a display sRGB triple, 0..255."""
    def lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(float(v)) for v in rgb[:3])
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0
    fx, fy, fz = f(x), f(y), f(z)
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def _de(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def corner_order(slots: "list[int]", rgbs: "list", real: int, geom, layout,
                 w: float, h: float,
                 skip_pages: "set | None" = None) -> "list[int]":
    """*slots* (canonical patch index -> sheet slot, the engine's scrambled
    order) with clearly visible patches moved into the four corner slots of
    every page, for a chart aimed at its corner patches. *rgbs* are the
    display colours of every patch in canonical order (padding included),
    *real* how many of them are the set's own (the rest is padding paper,
    never chosen).

    ONLY POSITIONS MOVE: a chosen patch and the one in the corner change
    places, so the set and its count stay exactly as they were, and the
    result is a function of the seed and the set alone. A corner patch is
    mid to dark (`table_facts.CORNER_MAX_L`) and saturated or dark
    (CORNER_MIN_C, CORNER_DARK_L), never near white (CORNER_NEVER_L); of
    those, each corner takes the one that differs most from the paper and
    from its neighbours on the sheet. A set with too few such patches fills
    what it can, darkest first."""
    out = list(slots)
    n = len(out)
    if n == 0 or real <= 0:
        return out
    labs = [_lab_of_rgb(c) for c in rgbs]
    paper = _lab_of_rgb((255, 255, 255))

    def chroma(lab):
        return (lab[1] ** 2 + lab[2] ** 2) ** 0.5

    def strong(i):
        L = labs[i][0]
        return L <= F.CORNER_MAX_L.value and (
            chroma(labs[i]) >= F.CORNER_MIN_C.value
            or L <= F.CORNER_DARK_L.value)

    pool = [i for i in range(real) if strong(i)]
    spare = sorted((i for i in range(real)
                    if not strong(i) and labs[i][0] < F.CORNER_NEVER_L.value),
                   key=lambda i: (labs[i][0], i))
    # every corner slot and every neighbour of one, on every page
    corners: "list[tuple[int, list[int]]]" = []
    for page in range(layout.pages):
        if skip_pages and page in skip_pages:
            continue
        cells = page_patches(geom, layout, w, h, page)
        if len({c[1] for c in cells}) < 2:
            continue                  # one strip: it keeps its crosses
        at = {(c[1], c[2]): c[0] for c in cells}
        seen = set()
        for corner in CORNERS:
            c = corner_cells(geom, layout, w, h, page).get(corner)
            if c is None or c[0] in seen:
                continue
            seen.add(c[0])
            near = [at[k] for k in ((c[1] - 1, c[2]), (c[1] + 1, c[2]),
                                    (c[1], c[2] - 1), (c[1], c[2] + 1))
                    if k in at]
            corners.append((c[0], near))
    blocked = {slot for slot, _near in corners}
    for _slot, near in corners:
        blocked.update(near)
    patch_at = {slot: i for i, slot in enumerate(out)}
    taken: set = set()
    for slot, near in corners:
        here = patch_at[slot]

        def usable(i):
            return i not in taken and (out[i] not in blocked or i == here)

        for group in (pool, spare):
            choice, best = None, -1.0
            for i in group:
                if not usable(i):
                    continue
                score = min([_de(labs[i], paper)]
                            + [_de(labs[i], labs[patch_at[s]]) for s in near])
                if score > best + 1e-9:
                    choice, best = i, score
            if choice is not None:
                break
        if choice is None:
            continue
        taken.add(choice)
        if choice != here:
            a, b = out[here], out[choice]
            out[here], out[choice] = b, a
            patch_at[a], patch_at[b] = choice, here
    return out


def sheet_slots(target, layout, geom, w: float, h: float, seed: int,
                randomize: bool, crosses: bool) -> "list[int]":
    """The slot of every patch (padding included) on an i1iO chart: the
    engine's own order, and without the crosses `corner_order` on top. The
    `.ti2`, the TIFF, the side file and the `.cht` are all written from
    this one list, so they cannot disagree."""
    from workflow.layout_engine import permutation, raster
    slots = permutation.location_permutation(layout.total_patches, seed,
                                             randomize)
    if crosses:
        return slots
    media = target.media_patch()
    patches = list(target.patches) + [media] * layout.padding
    rgbs = [raster.to_display_rgb(dev, target.color_rep)
            for dev, _xyz in patches]
    return corner_order(slots, rgbs, len(target.patches), geom, layout, w, h)


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
                   text_ctx: "dict | None" = None,
                   crosses: "bool | list" = True) -> None:
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
            UP the page from there) when *anchor* is "start". With *anchor*
            "pen", *centre* is ``(baseline x, pen origin y)`` in mm: the
            text's BASELINE lies on that page x and its pen starts at that
            page y, as type is set, so two runs given the same baseline sit
            on it together whatever their ink (the wordmark: an italic "IQ"
            whose Q has a tail was centred by its ink and stood too high).
            Returns its (width, height) on the page in pixels."""
            font, path, var = _font(size_px, family, italic, bold)
            bb = draw.textbbox((0, 0), txt, font=font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            tile = Image.new("L", (max(1, tw), max(1, th)), 0)
            ImageDraw.Draw(tile).text((-bb[0], -bb[1]), txt, font=font,
                                      fill=255)
            tile = tile.rotate(90, expand=True)           # anticlockwise
            cx, cy = px(centre[0]), px(centre[1])
            if anchor == "pen":
                # Turned anticlockwise, the tile's row y of the ink box is
                # page column y, and its column x is page row (tw - 1 - x):
                # the baseline (ascent from the em top) is column
                # ascent - bb[1], the pen origin row tw - 1 + bb[0].
                ascent = font.getmetrics()[0]
                x0 = cx - (ascent - bb[1])
                y0 = cy - (tw - 1 + bb[0])
            else:
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

        here = on_page(crosses, index)
        for mark in (marks(w, h) if here else ()):
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
        # THE STRIP LETTERS, at the page's bottom beyond every strip's
        # run-out: on the table the LEFT end of the strip, read upright like
        # the start of a line of text (the owner, 2026-11-13). Each ends
        # LABEL_CLEAR_MM before its run-out; the bottom margin holds the
        # widest (`table_facts.letter_band_mm`).
        if geom is not None and layout is not None and (
                labels is None or labels.rows):
            for text, centre, size in strip_letters(geom, layout, w, h, index,
                                                    dpi, labels, draw):
                turned_text(text, centre, size, family=LETTER_FONT,
                            bold=False, anchor="start")
        # THE TEXT LINE: the ChromIQ wordmark, then the page "N/M", the
        # chart's name and Manual's sheet text, as ONE GROUP centred between
        # crosses 2 and 3 (the owner, 2026-11-13): on the table halfway
        # between them, and with each part's visual middle on the line
        # through their centres (`text_line_plan`). Paper no strip can use,
        # so none of it costs a patch.
        # WITHOUT THE CROSSES only where it costs nothing, shrunk before a
        # part is left off (`crosses_off_plan`).
        if here or geom is None or layout is None:
            plan = text_line_plan(w, h, page_line_text(name, index, pages,
                                                       sheet_text, text_ctx),
                                  dpi)
        else:
            plan = line_plan(geom, layout, w, h, index, name=name,
                             sheet_text=sheet_text, text_ctx=text_ctx,
                             dpi=dpi, labels=labels, crosses=False)
        if plan["wordmark"] is not None:
            wm = plan["wordmark"]
            turned_text("Chrom", (wm["baseline_x"], wm["chrom_y"]),
                        wm["size_px"], family=WORDMARK_FONT, bold=False,
                        rgb=WORDMARK_RGB, anchor="pen")
            turned_text("IQ", (wm["baseline_x"], wm["iq_y"]), wm["size_px"],
                        family=WORDMARK_FONT, italic=True, bold=False,
                        rgb=WORDMARK_IQ_RGB, anchor="pen")
        if plan["text"]:
            turned_text(plan["text"], (plan["text_baseline_x"],
                                       plan["text_y"]),
                        plan["text_size_px"], anchor="pen")


#: The wordmark as the engine draws it on every other chart
#: (`raster._wordmark_geometry`): Instrument Serif, "Chrom" near-black and an
#: italic "IQ" in the magenta accent, on ONE baseline, the same size, the
#: "IQ" set after "Chrom"'s advance and a kern of 0.02 of the size.
WORDMARK_FONT = "Instrument Serif"
WORDMARK_RGB = (28, 27, 24)
WORDMARK_IQ_RGB = (255, 69, 115)
WORDMARK_KERN = 0.02
#: The text line's size: 3 mm capitals.
TEXT_CAP_MM = 3.0
#: Paper between the wordmark and the text after it.
WORDMARK_GAP_MM = 4.0
#: The text is shortened before the wordmark shrinks, down to this many
#: characters (and "…"); below that the wordmark shrinks first.
TEXT_MIN_CHARS = 12


#: Between the parts of the text line.
TEXT_SEP = "  ·  "


def page_line_parts(name, index: int, pages: int, sheet_text: str = "",
                    text_ctx: "dict | None" = None) -> "tuple[str, str]":
    """The text line of page *index* in its two parts: ``(head, extra)``,
    the page "N/M" (more than one page) with the chart's name, and Manual's
    sheet text with its fields filled in."""
    head = str(name or "")
    if pages > 1:
        head = f"{index + 1}/{pages}{TEXT_SEP}{head}" if head else \
            f"{index + 1}/{pages}"
    extra = str(sheet_text or "").strip()
    if extra:
        for key, value in (text_ctx or {}).items():
            extra = extra.replace("{" + key + "}", str(value))
        extra = extra.replace("{page}", f"{index + 1}/{pages}")
    return head, extra


def page_line_text(name, index: int, pages: int, sheet_text: str = "",
                   text_ctx: "dict | None" = None) -> str:
    """The text line of page *index*: the page "N/M" (more than one page),
    the chart's name and Manual's sheet text with its fields filled in."""
    head, extra = page_line_parts(name, index, pages, sheet_text, text_ctx)
    if head and extra:
        return f"{head}{TEXT_SEP}{extra}"
    return head or extra


def _cap_mm(font, s: float) -> float:
    """The height of a capital "H" in *font*, in mm at *s* px per mm."""
    bb = font.getbbox("H")
    return (bb[3] - bb[1]) / s


def text_line_plan(w: float, h: float, full: str, dpi: int) -> dict:
    """Where the text line goes on a page, in mm (page x is the table's
    vertical, page y its horizontal, the text running UP the page):

    * every part's VISUAL MIDDLE (half its capital height above its
      baseline) lies on the line through the centres of crosses 2 and 3;
    * the group, wordmark + WORDMARK_GAP_MM + text, is centred halfway
      between the two crosses;
    * too long for the room between their zones, the text is shortened
      ("…") first, down to TEXT_MIN_CHARS characters, and only then does
      the wordmark shrink (4 mm down to 2 mm) or, at last, stay off.

    Returns ``{"wordmark": {...} | None, "text", "text_baseline_x",
    "text_y", "text_size_px", "group": (y_start, y_end), "line_x"}``."""
    from PIL import Image, ImageDraw
    s = dpi / 25.4
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    m = marks(w, h)
    line_x = m[1].centre_mm[0]                 # crosses 2 and 3: one x
    mid_y = (m[1].centre_mm[1] + m[2].centre_mm[1]) / 2.0
    _x0, room_y0, _x1, room_y1 = text_column(w, h)
    room = room_y1 - room_y0
    # the text size: TEXT_CAP_MM capitals (an "H" measured at 200 px)
    probe_font, _p, _v = _font(200, "Inter")
    cap200 = _cap_mm(probe_font, 1.0)
    text_px = max(1, int(round(200 * (TEXT_CAP_MM * s) / cap200)))
    text_font, _p, _v = _font(text_px, "Inter")

    def text_len(t: str) -> float:
        return probe.textlength(t, font=text_font) / s if t else 0.0

    def wordmark(size_mm: float):
        size_px = max(1, int(round(size_mm / 0.74 * s)))
        f, _p, _v = _font(size_px, WORDMARK_FONT, bold=False)
        fi, _p, _v = _font(size_px, WORDMARK_FONT, italic=True, bold=False)
        chrom = probe.textlength("Chrom", font=f) / s
        iq = probe.textlength("IQ", font=fi) / s
        kern = WORDMARK_KERN * size_px / s
        return {"size_mm": size_mm, "size_px": size_px, "font": f,
                "chrom_len": chrom, "kern": kern,
                "length": chrom + kern + iq}

    def fit(t: str, length: float) -> str:
        keep = len(t)
        label = t
        while label and text_len(label) > length + 1e-9:
            keep -= 1
            label = t[:keep] + "…" if keep > 0 else ""
        return label

    def short_min(t: str) -> float:
        return text_len(t if len(t) <= TEXT_MIN_CHARS
                        else t[:TEXT_MIN_CHARS] + "…")

    full = str(full or "")
    chosen, label = None, full
    size = F.WORDMARK_MM.value
    while size >= F.WORDMARK_MIN_MM.value - 1e-9:
        wm = wordmark(size)
        left = room - wm["length"] - (WORDMARK_GAP_MM if full else 0.0)
        if left >= (short_min(full) if full else 0.0) - 1e-9:
            chosen, label = wm, fit(full, max(0.0, left))
            break
        size -= 0.5
    if chosen is None:
        label = fit(full, room)
    total = ((chosen["length"] if chosen else 0.0)
             + (WORDMARK_GAP_MM if chosen and label else 0.0)
             + text_len(label))
    start = mid_y + total / 2.0                 # the text runs UP the page
    out = {"line_x": line_x, "group": (start - total, start), "text": label,
           "text_size_px": text_px, "wordmark": None}
    y = start
    if chosen is not None:
        cap = _cap_mm(chosen["font"], s)
        out["wordmark"] = {
            "size_mm": chosen["size_mm"], "size_px": chosen["size_px"],
            "baseline_x": line_x + cap / 2.0, "chrom_y": y,
            "iq_y": y - chosen["chrom_len"] - chosen["kern"],
            "box": (line_x - cap / 2.0, y - chosen["length"],
                    line_x + cap / 2.0, y)}
        y -= chosen["length"] + (WORDMARK_GAP_MM if label else 0.0)
    out["text_baseline_x"] = line_x + _cap_mm(text_font, s) / 2.0
    out["text_y"] = y
    return out


# ---- without the crosses: the text line only where it costs nothing --------

def free_spots(geom, layout, w: float, h: float, page: int,
               labels: "Labels | None" = None) -> "list[dict]":
    """The paper a text line may use on a chart WITHOUT the crosses, page
    *page*: only what no patch, run or label needs, inside the printer's
    edge. In order of preference:

    * "bottom edge": beside the last strip (on the table the sheet's bottom
      edge, where the line is with the crosses), centred between the
      bottom-left and bottom-right corner patches;
    * "top edge": between the paper's edge and the patch numbers (on the
      table along the top), centred between the top corner patches.

    Each ``{"spot", "x0", "x1", "y0", "y1", "mid_y"}`` in mm on the page;
    a spot narrower than nothing is left out. Never nearer the paper's edge
    than `table_facts.TEXT_EDGE_MM` (10 mm, as the patch numbers), so no
    printer's unprinted edge cuts the line; the "top edge" spot, between
    the edge and the patch numbers, is therefore empty while the numbers
    are printed."""
    cells = page_patches(geom, layout, w, h, page)
    if not cells:
        return []
    edge = F.TEXT_EDGE_MM.value
    clear = F.LABEL_CLEAR_MM.value
    first = min(c[1] for c in cells)
    last = max(c[1] for c in cells)
    out = []

    def mid(strip):
        col = [c for c in cells if c[1] == strip]
        return (min(c[4] for c in col) + max(c[6] for c in col)) / 2.0

    x0 = max(c[5] for c in cells) + clear
    out.append({"spot": "bottom edge", "x0": x0, "x1": w - edge,
                "y0": edge, "y1": h - edge, "mid_y": mid(last)})
    numbers = labels is None or labels.columns
    x1 = (F.NUMBERS_EDGE_MM.value if numbers
          else min(c[3] for c in cells)) - clear
    x0 = edge
    band = clip_band_mm(geom)
    if band is not None:
        # a clip border holds that edge: only the paper past it is free,
        # and with the patch numbers on there is none (they follow it)
        x0 = max(edge, band[1] + clear)
        if numbers:
            x1 = x0
    out.append({"spot": "top edge", "x0": x0, "x1": x1,
                "y0": edge, "y1": h - edge, "mid_y": mid(first)})
    return [o for o in out if o["x1"] - o["x0"] > 0.0]


def _across(probe, font, txt: str, s: float) -> "tuple[float, float]":
    """``(up, down)`` in mm: how far *txt*'s ink reaches from its visual
    middle (half the capital height above the baseline) towards the glyph
    tops and towards the descenders."""
    ascent = font.getmetrics()[0]
    bb = probe.textbbox((0, 0), txt or "H", font=font)
    cap = _cap_mm(font, s)
    up = (ascent - bb[1]) / s - cap / 2.0
    down = (bb[3] - ascent) / s + cap / 2.0
    return max(up, cap / 2.0), max(down, 0.0)


def free_text_plan(spot: dict, head: str, extra: str, dpi: int) -> dict:
    """The text line in one free *spot* (`free_spots`) of a chart without the
    crosses: as much of it as costs nothing, by the owner's priorities
    (2026-11-13): 1. the chart name with the page N/M, 2. (the strip letters
    and patch numbers keep their own places), 3. the sheet text, 4. the
    logo. Each is shrunk first and only then left off; a long sheet text is
    shortened before the logo shrinks, as with the crosses.

    Returns the dict `text_line_plan` returns, plus ``"spot"``, ``"kept"``
    (a subset of ``("name", "sheet text", "logo")``), ``"name_whole"`` and
    ``"name_small"``; ``"text"`` is empty and ``"wordmark"`` None when even
    the page number does not fit."""
    from PIL import Image, ImageDraw
    s = dpi / 25.4
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    width = spot["x1"] - spot["x0"]
    mid_y = spot["mid_y"]
    room = 2.0 * max(0.0, min(mid_y - spot["y0"], spot["y1"] - mid_y))
    probe_font, _p, _v = _font(200, "Inter")
    cap200 = _cap_mm(probe_font, 1.0)
    every = (head + extra + "Hgy…").strip()

    def text_font(cap_mm: float):
        px_ = max(1, int(round(200 * (cap_mm * s) / cap200)))
        return px_, _font(px_, "Inter")[0]

    caps = []
    c = TEXT_CAP_MM
    while c >= F.TEXT_MIN_CAP_MM.value - 1e-9:
        px_, f = text_font(c)
        up, down = _across(probe, f, every, s)
        if up + down <= width + 1e-9:
            caps.append((c, px_, f))
        c = round(c - 0.25, 4)
    empty = {"line_x": (spot["x0"] + spot["x1"]) / 2.0,
             "group": (mid_y, mid_y), "text": "", "text_size_px": 1,
             "wordmark": None, "spot": spot["spot"], "kept": (),
             "name_whole": False, "name_small": False,
             "text_baseline_x": spot["x0"], "text_y": mid_y}
    if not caps:
        return empty

    def wm_at(size_mm: float):
        size_px = max(1, int(round(size_mm / 0.74 * s)))
        f, _p, _v = _font(size_px, WORDMARK_FONT, bold=False)
        fi, _p, _v = _font(size_px, WORDMARK_FONT, italic=True, bold=False)
        chrom = probe.textlength("Chrom", font=f) / s
        iq = probe.textlength("IQ", font=fi) / s
        kern = WORDMARK_KERN * size_px / s
        u1, d1 = _across(probe, f, "Chrom", s)
        u2, d2 = _across(probe, fi, "IQ", s)
        return {"size_mm": size_mm, "size_px": size_px, "font": f,
                "chrom_len": chrom, "kern": kern, "length": chrom + kern + iq,
                "up": max(u1, u2), "down": max(d1, d2)}

    wms = []
    size = F.WORDMARK_MM.value
    while size >= F.WORDMARK_MIN_MM.value - 1e-9:
        wm = wm_at(size)
        if wm["up"] + wm["down"] <= width + 1e-9:
            wms.append(wm)
        size -= 0.5

    def tlen(f, t: str) -> float:
        return probe.textlength(t, font=f) / s if t else 0.0

    def fit(f, t: str, length: float, least: int) -> "str | None":
        """*t*, shortened with "…" to *length*, never below *least*
        characters; None when even that is too long."""
        if tlen(f, t) <= length + 1e-9:
            return t
        keep = len(t) - 1
        while keep >= least:
            label = t[:keep].rstrip() + "…"
            if tlen(f, label) <= length + 1e-9:
                return label
            keep -= 1
        return None

    def join(a: str, b: str) -> str:
        return f"{a}{TEXT_SEP}{b}" if a and b else (a or b)

    def attempt(cap, wm, extra_least, name_least=None):
        """One arrangement: the text at *cap* (``(mm, px, font)``), the
        wordmark *wm* (or None), the sheet text kept down to *extra_least*
        characters (None: left off), the name shortened down to
        *name_least* characters (None: whole). Returns (label, wm) or None."""
        _c, _px, f = cap
        left = room - (wm["length"] + WORDMARK_GAP_MM if wm else 0.0)
        if left < 0:
            return None
        if name_least is None:
            if tlen(f, head) > left + 1e-9:
                return None
            name = head
        else:
            name = fit(f, head, left, name_least)
            if name is None:
                return None
        if extra and extra_least is not None:
            rest = left - tlen(f, name) - tlen(f, TEXT_SEP)
            ex = fit(f, extra, rest, min(extra_least, len(extra)))
            if ex is None:
                return None
            return join(name, ex), wm
        return name, wm

    big = caps[0]
    tries = []
    top_wm = wms[0] if wms else None
    if top_wm is not None:
        tries.append((big, top_wm, len(extra) if extra else None, None))
        tries.append((big, top_wm, TEXT_MIN_CHARS if extra else None, None))
        for wm in wms[1:]:
            tries.append((big, wm, TEXT_MIN_CHARS if extra else None, None))
    if extra:
        tries.append((big, None, len(extra), None))
        tries.append((big, None, TEXT_MIN_CHARS, None))
    for cap in caps:
        tries.append((cap, None, None, None))
    # the page number stays whole: only the name after it is shortened
    page_part = head.split(TEXT_SEP)[0] if TEXT_SEP in head else ""
    least = max(len(page_part) + len(TEXT_SEP) + 4, 4) if head else 0
    tries.append((caps[-1], None, None, least))
    for cap, wm, ex_least, name_least in tries:
        got = attempt(cap, wm, ex_least, name_least)
        if got is None:
            continue
        label, wm = got
        if not label and not wm:
            continue
        _c, px_, f = cap
        total = ((wm["length"] if wm else 0.0)
                 + (WORDMARK_GAP_MM if wm and label else 0.0)
                 + tlen(f, label))
        up, down = _across(probe, f, label, s)
        if wm:
            up, down = max(up, wm["up"]), max(down, wm["down"])
        # every part's visual middle on one line, the ink inside the spot
        lo, hi = spot["x0"] + up, spot["x1"] - down
        line_x = (lo + hi) / 2.0
        start = mid_y + total / 2.0
        out = {"line_x": line_x, "group": (start - total, start),
               "text": label, "text_size_px": px_, "wordmark": None,
               "spot": spot["spot"],
               "name_whole": label.startswith(head) if head else True,
               "name_small": (cap[0] < TEXT_CAP_MM - 1e-9
                              or name_least is not None)}
        y = start
        kept = ["name"] if head else []
        if extra and label != head and len(label) > len(head):
            kept.append("sheet text")
        if wm:
            capw = _cap_mm(wm["font"], s)
            out["wordmark"] = {
                "size_mm": wm["size_mm"], "size_px": wm["size_px"],
                "baseline_x": line_x + capw / 2.0, "chrom_y": y,
                "iq_y": y - wm["chrom_len"] - wm["kern"],
                "box": (line_x - capw / 2.0, y - wm["length"],
                        line_x + capw / 2.0, y)}
            kept.append("logo")
            y -= wm["length"] + (WORDMARK_GAP_MM if label else 0.0)
        out["kept"] = tuple(kept)
        out["text_baseline_x"] = line_x + _cap_mm(f, s) / 2.0
        out["text_y"] = y
        return out
    return empty


def _rank(plan: dict) -> tuple:
    """How good a free text plan is, by the owner's priorities."""
    kept = plan.get("kept", ())
    return ("name" in kept, bool(plan.get("name_whole")),
            "sheet text" in kept, "logo" in kept,
            not plan.get("name_small"))


def crosses_off_plan(geom, layout, w: float, h: float, page: int, head: str,
                     extra: str, dpi: int,
                     labels: "Labels | None" = None) -> dict:
    """The text line of page *page* of a chart without the crosses: the best
    of the free spots (`free_spots`, `free_text_plan`), the bottom edge
    when it keeps as much."""
    best = None
    for spot in free_spots(geom, layout, w, h, page, labels):
        plan = free_text_plan(spot, head, extra, dpi)
        if best is None or _rank(plan) > _rank(best):
            best = plan
    if best is None:
        best = {"line_x": 0.0, "group": (0.0, 0.0), "text": "",
                "text_size_px": 1, "wordmark": None, "spot": None,
                "kept": (), "name_whole": False, "name_small": False,
                "text_baseline_x": 0.0, "text_y": 0.0}
    return best


def line_plan(geom, layout, w: float, h: float, page: int, *, name: str,
              sheet_text: str = "", text_ctx: "dict | None" = None,
              dpi: int = 300, labels: "Labels | None" = None,
              crosses: bool = True) -> dict:
    """The text line of page *page*, with the crosses (`text_line_plan`,
    between crosses 2 and 3) or without them (`crosses_off_plan`)."""
    pages = layout.pages
    if crosses:
        plan = text_line_plan(w, h, page_line_text(name, page, pages,
                                                   sheet_text, text_ctx), dpi)
        plan.setdefault("spot", "between crosses 2 and 3")
        return plan
    head, extra = page_line_parts(name, page, pages, sheet_text, text_ctx)
    return crosses_off_plan(geom, layout, w, h, page, head, extra, dpi,
                            labels)


def crosses_off_effects(kw: dict, name: str = "", sheet_text: str = "",
                        pages: int = 1, dpi: int = 300) -> dict:
    """What happens to the text line of page 1 when the crosses of the i1iO
    chart *kw* (build kwargs) are switched off, for the help of "Aiming
    crosses": ``{"name": "whole" | "small" | "shortened" | "none",
    "spot": "bottom edge" | "top edge" | None, "sheet_text": None | "kept" |
    "shortened" | "dropped", "logo": bool}``."""
    from workflow.layout_engine import geometry, instruments, papers
    k = {**kw, "instrument": "IO2", CROSSES_KEY: False}
    w, h = papers.dimensions_mm(k.get("paper") or "A4")
    geom = instruments.geom_from_build_kwargs(k)
    per = geometry.patches_per_sheet(geom, w, h)
    pages = max(1, int(pages or 1))
    layout = geometry.compute(geom, w, h, max(1, per) * pages)
    labels = label_wishes(fixed_build_kwargs(k))
    plan = line_plan(geom, layout, w, h, 0, name=name, sheet_text=sheet_text,
                     dpi=dpi, labels=labels, crosses=False)
    head, extra = page_line_parts(name, 0, layout.pages, sheet_text, None)
    kept = plan.get("kept", ())
    names = [p["patch"] for p in aim_points(geom, layout, w, h, 0, False)]
    if "name" not in kept:
        state = "none"
    elif not plan.get("name_whole"):
        state = "shortened"
    elif plan.get("name_small"):
        state = "small"
    else:
        state = "whole"
    if not extra:
        sheet = None
    elif "sheet text" not in kept:
        sheet = "dropped"
    elif not plan.get("text", "").endswith(extra):
        sheet = "shortened"
    else:
        sheet = "kept"
    return {"name": state, "spot": plan.get("spot") if kept else None,
            "sheet_text": sheet, "logo": "logo" in kept,
            # page 1's three aiming patches, as printed (when labelled)
            "aim_patches": names,
            "labels": bool(labels.rows and labels.columns)}


#: The face of the strip letters: the engine's own label face, as the patch
#: numbers beside them.
LETTER_FONT = "JetBrains Mono"


def letter_size_mm(geom, dpi: int, labels: "Labels | None") -> float:
    """The strip letters' size: Manual's, or the engine's automatic label
    size (the patch numbers' own), never above LABEL_MAX_MM."""
    from workflow.layout_engine import raster
    asked = float(labels.size) if labels is not None and labels.size else 0.0
    if not asked:
        asked = raster.effective_indicator_size_mm(geom, dpi, LETTER_FONT, 0.0)
    return min(asked, F.LETTER_AUTO_MM.value if not (
        labels is not None and labels.size) else F.LABEL_MAX_MM.value)


def strip_letters(geom, layout, w: float, h: float, page: int, dpi: int,
                  labels: "Labels | None" = None, draw=None):
    """``[(text, start (x, y) in mm, size px)]`` for the strip letters of
    *page*: one per strip, its START (the turned text runs up the page from
    there, so it reads left to right on the table) placed so its END is
    LABEL_CLEAR_MM below the strip's run-out."""
    from PIL import ImageDraw, Image
    from workflow.layout_engine import permutation
    s = dpi / 25.4
    size_px = max(1, int(round(letter_size_mm(geom, dpi, labels) * s)))
    font, _p, _v = _font(size_px, LETTER_FONT, bold=False)
    if draw is None:
        draw = ImageDraw.Draw(Image.new("L", (1, 1)))
    name = permutation.make_labeller(permutation.DEFAULT_STRIP_PATTERN)
    steps = max(1, layout.steps_in_pass)
    out = []
    for x, _y0, y1, col in scan_strips(page_patches(geom, layout, w, h, page)):
        text = str(name(col[0][0] // steps + 1)).strip()
        bb = draw.textbbox((0, 0), text, font=font)
        length = (bb[2] - bb[0]) / s
        out.append((text, (x, y1 + F.LABEL_CLEAR_MM.value + length), size_px))
    return out


def wordmark_box(geom, layout, w: float, h: float, page: int,
                 labels: "Labels | None" = None, full: str = "",
                 dpi: int = 300, plan: "dict | None" = None):
    """Where the ChromIQ wordmark goes on page *page* with the text line
    *full*, ``(x0, y0, x1, y1, height)`` in mm on the page, or None when it
    is left off (`text_line_plan`).

    THE LOGO NEVER COSTS A PATCH (Basti, 2026-11-13): it is no layout input,
    it is drawn only between crosses 2 and 3 in the margin no strip and no
    run ever is, shrunk to the smallest legible size, and left off only when
    even that does not fit."""
    wm = (plan if plan is not None else text_line_plan(w, h, full, dpi)
          )["wordmark"]
    if wm is None:
        return None
    return (*wm["box"], wm["size_mm"])


# ---- the side file -----------------------------------------------------------

def _clip_record(geom, w: float, h: float, content: str) -> "dict | None":
    """The side file's "clip_border": None without one."""
    area = clip_area(geom, w, h)
    band = clip_band_mm(geom)
    if area is None or band is None:
        return None
    return {"side": "left", "width_mm": round(band[1], 4),
            "content": str(content or "off"),
            "area_mm": [round(v, 4) for v in area]}


def write_side_file(path: Path, *, geom, layout, w: float, h: float,
                    paper: str, dpi: int, seed: int, randomize: bool,
                    strip_pattern: str, patch_pattern: str, label_rule: str,
                    designed: int, labels: "Labels | None" = None,
                    name: str = "", sheet_text: str = "",
                    text_ctx: "dict | None" = None,
                    crosses: "bool | list" = True,
                    slots: "list[int] | None" = None,
                    clip_content: str = "off") -> Path:
    """Write ``<stem>.i1io.json``: every mark, strip and patch in mm on the
    portrait page, what to aim at and where, for the measuring step.
    *slots* is the chart's own patch order (`sheet_slots`)."""
    from workflow.layout_engine import permutation
    from .support import HEAD_MODEL, TABLE_MODEL, TARGET_INSTRUMENT
    if slots is None:
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
        here = on_page(crosses, page)
        plan = line_plan(geom, layout, w, h, page, name=name,
                         sheet_text=sheet_text, text_ctx=text_ctx, dpi=dpi,
                         labels=labels, crosses=here)
        wm = wordmark_box(geom, layout, w, h, page, labels, dpi=dpi,
                          plan=plan)
        points = aim_points(geom, layout, w, h, page, here,
                            (strip_pattern, patch_pattern, label_rule))
        entry = {"page": page + 1, "strips": strips,
                 # EVERY PAGE IS ALIGNED ON ITS OWN (X-Rite: each sheet is
                 # laid down by hand): its own three points, in aiming order
                 "aim": aim_of(here),
                 # the numbers 1, 2, 3 printed beside this page's crosses
                 "digits_printed": bool(here),
                 "aim_patches": [p["patch"] for p in points] if not here
                 else [],
                 "aim_points": points,
                 "wordmark_mm": list(wm) if wm else None,
                 "text_line": {"text": plan.get("text", ""),
                               "spot": plan.get("spot")}}
        if here:
            entry["text_column_mm"] = list(text_column(w, h))
        else:
            entry["corner_patches"] = {
                corner: {"loc": permutation.location_label(
                             c[0], layout.steps_in_pass, strip_pattern,
                             patch_pattern, label_rule),
                         "sample_id": sample_of[c[0]]}
                for corner, c in corner_cells(geom, layout, w, h,
                                              page).items()}
        pages.append(entry)
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
        # WHAT TO AIM AT (`.ti2` keyword CHROMIQ_I1IO_AIM): "crosses" or
        # "corner patches"; every page's "aim_points" says where, in aiming
        # order, on the page and on the table (the sheet's top left there).
        "aim": aim_of(on_page(crosses, 0) if not isinstance(
            crosses, (list, tuple)) else all(crosses)),
        "aim_rule": "every page is aligned on its own, at its own three "
                    "points (pages[].aim, aim_points, aim_patches); without "
                    "the crosses a page keeps them only when its corner "
                    "patches cannot be aimed at (one strip, or no visible "
                    "patch in a corner)",
        "labels_printed": bool(labels is None or (labels.rows
                                                  and labels.columns)),
        "table_mm_note": "table_mm: from the sheet's top left corner as it "
                         "lies on the table, x to the right, y down",
        "marks_mm": ([{"number": m.number, "corner_on_table": m.corner,
                       "centre_mm": list(m.centre_mm)} for m in marks(w, h)]
                     if any(on_page(crosses, p) for p in range(layout.pages))
                     else []),
        "page_count": layout.pages,
        "pages": pages,
        "generation": {"seed": seed, "randomize": bool(randomize), "dpi": dpi,
                       "designed_patches": designed,
                       "padding_patches": layout.padding},
        "table_facts": F.as_record(),
    }
    # THE CLIP BORDER (an option, off by default): its band on the page's
    # left edge (the table's top edge), mm on the page, and what it holds.
    # Written only when there is one, so a chart without it records exactly
    # what it recorded before the option.
    clip = _clip_record(geom, w, h, clip_content)
    if clip is not None:
        doc["clip_border"] = clip
    path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    return path
