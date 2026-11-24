"""A Barbieri Spectro 100xy chart: the layout engine's own grid, read by coordinates.

WHAT THE INSTRUMENT NEEDS, AND NOTHING ELSE. The 100xy's table moves the head
to every patch; it never sweeps a strip and never looks for an edge, so the
chart is a plain grid of patches with no run-up, no spacers and no strip
furniture. The margins are exactly what the person types (the engine's
"margins are the law" mode): nothing hidden is added at the top, unlike the
SpectroScan entry, which keeps the band printtarg gave it.

What this module adds to the engine's grid:

* **one pitch in 0.1 mm steps.** Spectro32 is told the span from the centre of
  the first patch to the centre of the last, across and down, in 0.1 mm
  (template line ``R xoff,yoff,xspan,yspan,cols,rows``). A patch size and gap
  in whole 0.1 mm steps make every span exact; a value with more decimals is
  rounded to the nearest 0.1 mm and the build says so;
* **at most 99 patches across and down** (Gateway's limit): a wider page
  leaves the rest of its width empty and the build says so;
* **marks at the four outer corners of the patch grid, on every page**: thin
  corner marks whose arms continue the grid's outer edges into the margin, so
  the corners can be aimed at (Gateway aims at three of them). The UPPER RIGHT
  one is bold: Spectro32 is aimed at the centre of the upper-right patch, and
  two thin ticks continue that patch's row and column into the margin so they
  cross at its centre. A small solid square left of patch A1 shows where the
  reading starts. A sheet or film laid mirrored or turned shows its bold corner
  in the wrong place;
* **check patches at the corners** (an option, on by default): the darkest
  patch of each page at A1, its most colourful at the upper-right patch (the
  one Spectro32 is aimed at: a clear colour shows its edges and a laser spot
  on it), its lightest at the lower-left patch, and two clearly different
  colours right of and below A1. ONLY POSITIONS MOVE: the patch set and its count stay the
  same. A measurement read from a sheet that lay mirrored, upside down, turned
  or one patch off then shows a colour mismatch at those places, which the
  import (a later step) checks against the side file;
* **the reading order**, row by row from the top: A1, B1, ... to the last
  column, then the next row, never back and forth (an owner's real 896-patch
  run). The patch names are the engine's own (column letter, row number), so
  the order names the patches exactly as the ``.ti2`` does;
* **the side file** ``<stem>.barbieri.json``: the grid of every page, the
  numbers Spectro32 and Gateway ask for, the aim patch, the reading order, the
  check patches and the ``.ti2``'s checksum.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from core.i18n import tr
from workflow.barbieri import chart_facts as F

#: The schema of the side file.
SCHEMA = 1

#: The ``.ti2`` keywords of a Barbieri chart.
LAYOUT_KEYWORD = "CHROMIQ_BARBIERI_LAYOUT"
HEAD_KEYWORD = "CHROMIQ_BARBIERI_HEAD"

#: The recipe / build-kwargs keys of the chart's own options.
HEAD_KEY = "barbieri_head"
CHECK_KEY = "barbieri_check_patches"
MARKS_KEY = "barbieri_marks"
SIZE_KEY = "barbieri_size"

#: The chart's own options and their defaults (`LayoutRecipe.barbieri_*`).
FIELD_DEFAULTS: dict = {
    HEAD_KEY: F.DEFAULT_HEAD,
    CHECK_KEY: True,
    MARKS_KEY: True,
    SIZE_KEY: "",
}

#: Set on build kwargs this module has already fixed (idempotence marker).
FIXED_KEY = "_barbieri_fixed"
#: What the fixing left for the build to say (rounding, the column cap).
NOTES_KEY = "_barbieri_notes"


class BarbieriSheetRefused(ValueError):
    """A Barbieri layout that cannot be built, said in words."""


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def head_of(value) -> F.Head:
    """The measuring opening a stored value names (the default for anything
    unknown)."""
    return F.HEADS.get(str(value or ""), F.HEADS[F.DEFAULT_HEAD])


def step_round(mm) -> float:
    """*mm* rounded to the table's 0.1 mm step."""
    try:
        v = float(mm)
    except (TypeError, ValueError):
        return 0.0
    return round(round(v / F.STEP_MM.value) * F.STEP_MM.value, 4)


def _num(value, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def default_margins(paper_w: float, paper_h: float
                    ) -> "tuple[float, float, float, float]":
    """``(top, right, bottom, left)`` for a new reflective chart: the left
    border the datasheets ask for (15 mm, the smaller of their two numbers),
    10 mm elsewhere, and the right and bottom margins raised so the patch area
    stays inside the datasheet reading area (235 x 200 mm). A default only:
    every margin stays the person's to change, and a bigger patch area is not
    refused or warned about (an owner may read bigger charts)."""
    m = F.DEFAULT_MARGIN_MM.value
    left = F.LEFT_BORDER_MM.value[0]
    aw, ah = F.READING_AREA_MM.value
    right = max(m, round(paper_w - left - aw, 2))
    bottom = max(m, round(paper_h - m - ah, 2))
    return (m, right, bottom, left)


# ---------------------------------------------------------------------------
# the ready-made sizes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SizePreset:
    """One ready-made size of the "Ready-made size" choice. Applying it fills
    the ordinary controls (paper, margins, patch size, opening, resolution);
    every value stays editable and is saved like any typed value."""
    key: str
    label: str               # English; shown through tr()
    head: str
    patch_mm: float
    margins: "tuple[float, float, float, float]"   # top, right, bottom, left
    paper: str = ""          # a paper code (mm); "" with page_size
    page_size: "dict | None" = None   # the page-output Beta's typed sides
    dpi: int = 0             # 0 = leave the resolution as it is
    needs_page_beta: bool = False


#: Each with the patch area it gives at its own patch size, worked out in
#: `tests/test_barbieri_chart.py::test_every_size_preset_gives_its_patch_area`.
SIZE_PRESETS: "tuple[SizePreset, ...]" = (
    # A4 landscape with the patch area inside one pass of the table, the
    # 15 mm left border included: 36 x 29 patches of 6.5 mm, 234 x 188.5 mm.
    SizePreset("a4", "A4 landscape, one pass (3 mm, 6.5 mm patches)",
               F.HEAD_REFLECTION_3, 6.5, (10.0, 47.0, 10.0, 15.0),
               paper="A4R"),
    # Letter landscape, the same way: 36 x 30 patches, 234 x 195 mm.
    SizePreset("letter", "Letter landscape, one pass (3 mm, 6.5 mm patches)",
               F.HEAD_REFLECTION_3, 6.5, (7.9, 29.4, 7.9, 15.0),
               paper="LetterR"),
    # Barbieri's own common patch area, 225 x 180 mm (the jobs Gateway ships
    # with): 30 x 24 patches of 7.5 mm on A4 landscape.
    SizePreset("standard", "Barbieri standard area 225 x 180 mm (7.5 mm "
               "patches)", F.HEAD_REFLECTION_3, 7.5,
               (15.0, 56.9, 14.9, 15.0), paper="A4R"),
    # The datasheet reading area, 235 x 200 mm: 36 x 30 patches of 6.5 mm
    # (234 x 195 mm) on A4 landscape with 5 mm top and bottom.
    SizePreset("full", "Full reading area 235 x 200 mm (6.5 mm patches)",
               F.HEAD_REFLECTION_3, 6.5, (5.0, 47.0, 5.0, 15.0),
               paper="A4R"),
    # An owner's large film frame, 9.25 x 7.75 in, read with the 3 mm opening
    # in transmission, at his film recorder's 2032 pixels per inch.
    SizePreset("film_large", "Film frame 9.25 x 7.75 in (3 mm transmission, "
               "6.5 mm patches)", F.HEAD_TRANSMISSION_3, 6.5,
               (3.0, 3.0, 3.0, 3.0),
               page_size={"w": [9.25, "in"], "h": [7.75, "in"], "ppi": 2032},
               dpi=2032, needs_page_beta=True),
    # The 35 mm frame, 4096 x 2730 pixels at 2731 pixels per inch (1.5 x 1
    # in), read with the 0.5 mm opening: 36 x 23 patches of 1 mm.
    SizePreset("film_35", "35 mm film frame, 4096 x 2730 px at 2731 ppi "
               "(0.5 mm, 1 mm patches)", F.HEAD_TRANSMISSION_05, 1.0,
               (1.0, 1.0, 1.0, 1.0),
               page_size={"w": [4096, "px"], "h": [2730, "px"], "ppi": 2731},
               dpi=2731, needs_page_beta=True),
)


def size_preset(key) -> "SizePreset | None":
    for p in SIZE_PRESETS:
        if p.key == key:
            return p
    return None


# ---------------------------------------------------------------------------
# the fixed settings (one chokepoint for the estimate and the build)
# ---------------------------------------------------------------------------

def fixed_build_kwargs(kw: dict) -> dict:
    """*kw* (layout-engine build kwargs) with what a Barbieri chart fixes:
    patch-first, the margins as the law (no hidden run-up), no spacers, no
    edge spacers, no honeycomb or stagger, no ruler helper markers, the patch
    size and gaps in 0.1 mm steps, and at most 99 columns (the right margin
    grows by what is left over). What a person may set is kept: the patch
    size, the gaps, the margins, the alignment, the offsets, the labels, the
    clip border and its content. Used by the capacity estimate and by the
    build alike, so the two cannot disagree. Idempotent."""
    if kw.get(FIXED_KEY):
        return kw
    out = dict(kw)
    notes: list = []
    head = head_of(kw.get(HEAD_KEY))
    pw_in = kw.get("patch_w")
    ph_in = kw.get("patch_h")
    pw = step_round(pw_in) if pw_in else head.default_patch_mm
    ph = step_round(ph_in) if ph_in else pw
    if pw <= 0:
        pw = head.default_patch_mm
    if ph <= 0:
        ph = pw
    for asked, got in ((pw_in, pw), (ph_in, ph)):
        if asked and abs(_num(asked, got) - got) > 1e-6:
            notes.append(("rounded", _num(asked, got), got))
    gaps = []
    for key in ("inter_patch", "strip_gap"):
        asked = kw.get(key)
        got = max(0.0, step_round(asked)) if asked else 0.0
        if asked and abs(_num(asked, got) - got) > 1e-6:
            notes.append(("rounded", _num(asked, got), got))
        gaps.append(got)
    out.update(
        patch_w=pw, patch_h=ph, pscale=1.0, sscale=1.0,
        spacer_on=False, spacer_mode="none", spacer_width=None,
        inter_patch=gaps[0] or None, strip_gap=gaps[1] or None,
        edge_spacers=False, nolimit=True,
        helper_markers=False, use_instrument_margins=True,
        layout_mode="patch_first", density=1, cm_stagger=False,
        hflag=False, hex_flat_top=False, nolpcbord=True)
    out[FIXED_KEY] = True
    out = _cap_columns(out, notes)
    out[NOTES_KEY] = tuple(notes)
    return out


def _cap_columns(kw: dict, notes: list) -> dict:
    """Raise the right margin so no page has more than 99 columns."""
    from workflow.layout_engine import geometry, instruments, papers
    try:
        w, h = papers.dimensions_mm(kw.get("paper") or "A4")
        if kw.get("page_size"):
            from workflow.page_output import support as _po
            ps = _po.clean_page_size(kw.get("page_size"))
            if ps is not None:
                w, h = _po.page_mm(ps, kw.get("dpi") or ps.get("ppi") or 300)
        g = instruments.geom_from_build_kwargs(kw)
        lay = geometry.compute(g, w, h, 1_000_000)
    except Exception:   # noqa: BLE001 - the build says what is wrong
        return kw
    cols = (lay.patches_per_page // lay.steps_in_pass
            if lay.steps_in_pass else 0)
    cap = int(F.MAX_PER_SIDE.value)
    if cols <= cap:
        return kw
    extra = (cols - cap) * g.rrsp
    m = kw.get("margins") or (g.margin_t, g.margin_r, g.margin_b, g.margin_l)
    t, r, b, l_ = (float(v) for v in m)
    out = dict(kw, margins=(t, r + extra, b, l_))
    notes.append(("columns", cols, cap))
    return out


def option_notes(kw: dict, widest: "int | None" = None) -> "list[str]":
    """What the fixed settings changed or what the options risk, in words:
    a size rounded to 0.1 mm, columns beyond 99 (only when the chart really
    reaches the cap: *widest* is its widest page's column count), a patch
    too small for the opening. Translated."""
    from workflow import measurement_messages as _mm
    out: list = []
    fixed = fixed_build_kwargs(kw)
    for note in fixed.get(NOTES_KEY, ()):
        if note[0] == "rounded":
            text = tr(_mm._BARBIERI_ROUNDED).format(
                asked=_mm_text(note[1], 3), got=_mm_text(note[2], 1))
        else:
            if widest is not None and widest < note[2]:
                continue
            text = tr(_mm._BARBIERI_COLUMN_CAP).format(cols=note[1],
                                                       cap=note[2])
        if text not in out:
            out.append(text)
    head = head_of(kw.get(HEAD_KEY))
    smallest = min(float(fixed["patch_w"]), float(fixed["patch_h"]))
    need = head.aperture_mm + 2 * F.EDGE_ALLOWANCE_MM.value
    if smallest + 1e-9 < need:
        out.append(tr(_mm._BARBIERI_PATCH_SMALL).format(
            patch=_mm_text(smallest, 1), opening=_mm_text(head.aperture_mm, 1),
            need=_mm_text(need, 2)))
    return out


def _mm_text(v: float, places: int) -> str:
    """A length for a sentence, in the UI language's decimal style."""
    from core.i18n import decimal_text
    text = f"{float(v):.{places}f}".rstrip("0").rstrip(".") if places else \
        f"{float(v):.0f}"
    try:
        return decimal_text(text)
    except Exception:   # noqa: BLE001
        return text


# ---------------------------------------------------------------------------
# the grid of every page
# ---------------------------------------------------------------------------

@dataclass
class PageGrid:
    """One page's patch grid, as the engine laid it out."""
    page: int
    cols: int
    rows: int
    first_slot: int
    steps: int
    pitch_x: float
    pitch_y: float
    patch_w: float
    patch_h: float
    left: float      # grid's outer edges on the page, mm
    top: float
    right: float
    bottom: float
    paper_w: float
    paper_h: float

    def slot(self, col: int, row: int) -> int:
        return self.first_slot + col * self.steps + row

    def centre(self, col: int, row: int) -> "tuple[float, float]":
        return (self.left + col * self.pitch_x + self.patch_w / 2.0,
                self.top + row * self.pitch_y + self.patch_h / 2.0)

    @property
    def x_span_mm(self) -> float:
        return (self.cols - 1) * self.pitch_x

    @property
    def y_span_mm(self) -> float:
        return (self.rows - 1) * self.pitch_y

    @property
    def area_mm(self) -> "tuple[float, float]":
        return (self.right - self.left, self.bottom - self.top)


def page_grids(geom, layout, w: float, h: float) -> "list[PageGrid]":
    """Every page's grid. Each page is a full rectangle (the last pass is
    filled up with paper patches, ``padlrow``), so Spectro32 and Gateway can
    read it as one grid."""
    from workflow.layout_engine import geometry
    place = geometry.placement(geom, w, h, layout)
    steps = layout.steps_in_pass
    out = []
    for page in range(layout.pages):
        first = page * layout.patches_per_page
        last = min(layout.total_patches, first + layout.patches_per_page)
        n = last - first
        cols = (n + steps - 1) // steps if steps else 0
        rows = steps
        pitch_x = place.rrsp
        pitch_y = place.plen + place.pspa
        left, top = place.x_of(0), place.y_of(0)
        out.append(PageGrid(
            page=page, cols=cols, rows=rows, first_slot=first, steps=steps,
            pitch_x=pitch_x, pitch_y=pitch_y, patch_w=place.pwid,
            patch_h=place.plen, left=left, top=top,
            right=place.x_of(cols - 1) + place.pwid,
            bottom=place.y_of(rows - 1) + place.plen,
            paper_w=w, paper_h=h))
    return out


def tenths(mm: float) -> int:
    """A length in Spectro32's 0.1 mm units."""
    return int(round(float(mm) / F.STEP_MM.value))


def spectro32_line(cols: int, rows: int, pitch_x: float, pitch_y: float
                   ) -> str:
    """Spectro32's grid line for a grid of *cols* x *rows* at the pitches
    given (mm): ``R0,0,xspan,yspan,cols,rows``, the spans from the centre of
    the first patch to the centre of the last, in 0.1 mm. The offsets stay 0:
    Spectro32 is aimed at the upper-right patch by hand."""
    return (f"R0,0,{tenths((cols - 1) * pitch_x)},"
            f"{tenths((rows - 1) * pitch_y)},{int(cols)},{int(rows)}")


def gateway_numbers(cols: int, rows: int, pitch_x: float, pitch_y: float
                    ) -> dict:
    """What Barbieri Gateway asks for: the patches across and down and the
    "target size", the patch area from edge to edge as Gateway works it out
    (count x pitch), in whole millimetres. ``exact`` is False when a size is
    not a whole millimetre (Gateway would then place the far patches a little
    off)."""
    sx, sy = cols * pitch_x, rows * pitch_y
    return {"patches_x": int(cols), "patches_y": int(rows),
            "size_x_mm": int(round(sx)), "size_y_mm": int(round(sy)),
            "size_x_exact_mm": round(sx, 4), "size_y_exact_mm": round(sy, 4),
            "exact": abs(sx - round(sx)) < 1e-6 and abs(sy - round(sy)) < 1e-6}


def reading_minutes(cells: int) -> int:
    """Estimated reading time, whole minutes (at least 1), from the
    datasheet's pace."""
    return max(1, int(round(cells * F.SECONDS_PER_PATCH.value / 60.0)))


def patch_name(slot: int, steps: int, patterns: "tuple | None" = None) -> str:
    """The name the chart prints and the ``.ti2`` holds for *slot*."""
    from workflow.layout_engine import permutation
    sp, pp, rule = patterns or (permutation.DEFAULT_STRIP_PATTERN,
                                permutation.DEFAULT_PATCH_PATTERN,
                                permutation.ARGYLL)
    return permutation.location_label(slot, steps, sp, pp, rule)


def reading_order(grid: PageGrid, patterns: "tuple | None" = None
                  ) -> "list[str]":
    """The patch names of one page in the order the table reads them: row by
    row from the top, each row from the left (A1, B1, ... AF1, A2, ...)."""
    return [patch_name(grid.slot(c, r), grid.steps, patterns)
            for r in range(grid.rows) for c in range(grid.cols)]


# ---------------------------------------------------------------------------
# the check patches
# ---------------------------------------------------------------------------

#: Each check place: (role, column, row); a negative index counts from the
#: grid's far side (-1 = the last column or row).
CHECK_PLACES = (("first", 0, 0), ("aim", -1, 0), ("lower_left", 0, -1),
                ("right_of_first", 1, 0), ("below_first", 0, 1))


def _lab(xyz, white) -> "tuple[float, float, float]":
    def f(t):
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0
    fx, fy, fz = (f(max(0.0, float(v)) / max(1e-9, float(wv)))
                  for v, wv in zip(xyz, white))
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def _lab_of_rgb(rgb) -> "tuple[float, float, float]":
    def lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(float(v)) for v in rgb[:3])
    xyz = (100 * (0.4124 * r + 0.3576 * g + 0.1805 * b),
           100 * (0.2126 * r + 0.7152 * g + 0.0722 * b),
           100 * (0.0193 * r + 0.1192 * g + 0.9505 * b))
    return _lab(xyz, (95.047, 100.0, 108.883))


def _de(a, b) -> float:
    return math.dist(a, b)


def patch_labs(target) -> "list[tuple[float, float, float]]":
    """The expected CIELAB of every patch of *target* (its ``.ti1`` XYZ where
    it has them, else its display colour)."""
    from workflow.layout_engine import raster
    media = target.media_patch()
    white = media[1] if any(media[1]) else (96.42, 100.0, 82.49)
    out = []
    for dev, xyz in target.patches:
        if xyz and any(float(v) for v in xyz):
            out.append(_lab(xyz, white))
        else:
            out.append(_lab_of_rgb(raster.to_display_rgb(dev, target.color_rep)))
    return out


def check_cells(grid: PageGrid) -> "list[tuple[str, int, int]]":
    """The check places that exist on *grid*, as (role, column, row), each
    cell once (a one-column or one-row page has fewer)."""
    out, seen = [], set()
    for role, c, r in CHECK_PLACES:
        col = c if c >= 0 else grid.cols + c
        row = r if r >= 0 else grid.rows + r
        if not (0 <= col < grid.cols and 0 <= row < grid.rows):
            continue
        if (col, row) in seen:
            continue
        seen.add((col, row))
        out.append((role, col, row))
    return out


def check_order(slots: "list[int]", labs: "list", real: int,
                grids: "list[PageGrid]") -> "list[int]":
    """*slots* (patch index -> slot, the engine's order) with the check
    patches moved into their places on every page. ONLY POSITIONS MOVE, and
    only within a page: a chosen patch and the one in the check place change
    places, so the set, its count and every page's patch set stay as they
    were. Paper patches that fill up the last pass are never chosen."""
    out = list(slots)
    patch_at = {s: i for i, s in enumerate(out)}
    for grid in grids:
        cells = check_cells(grid)
        if not cells:
            continue
        lo = grid.first_slot
        hi = grid.first_slot + grid.cols * grid.steps
        chosen: dict = {}

        def candidates():
            return [i for i in range(real)
                    if lo <= out[i] < hi and i not in chosen.values()]

        for role, c, r in cells:
            pool = candidates()
            if not pool:
                break
            if role == "first":
                pick = min(pool, key=lambda i: (labs[i][0], i))
            elif role == "aim":
                pick = max(pool, key=lambda i: (math.hypot(labs[i][1],
                                                           labs[i][2]), -i))
            elif role == "lower_left":
                pick = max(pool, key=lambda i: (labs[i][0], -i))
            else:
                taken = [labs[i] for i in chosen.values()]
                pick = max(pool, key=lambda i: (
                    min(_de(labs[i], t) for t in taken) if taken else 0.0, -i))
            chosen[role] = pick
            target_slot = grid.slot(c, r)
            here = patch_at.get(target_slot)
            if here == pick:
                continue
            a = out[pick]
            out[pick] = target_slot
            patch_at[target_slot] = pick
            if here is not None:
                out[here] = a
                patch_at[a] = here
            else:
                patch_at.pop(a, None)
    return out


# ---------------------------------------------------------------------------
# the marks
# ---------------------------------------------------------------------------

@dataclass
class MarkPlan:
    """The rectangles (mm) of one page's marks, and the sides left out."""
    rects: "list[tuple[float, float, float, float]]" = field(
        default_factory=list)
    left_out: "list[str]" = field(default_factory=list)
    arm_mm: "dict[str, float]" = field(default_factory=dict)


def plan_marks(grid: PageGrid, *, letters_on_top: bool = False,
               numbers_on_left: bool = False) -> MarkPlan:
    """Where one page's marks go: the four corner marks, the bold upper-right
    one, the two aim ticks that cross at the upper-right patch's centre, and
    the start square left of A1. Everything lies in the margins, never on a
    patch; a margin too narrow for a mark leaves that side's marks out (said
    by the build)."""
    plan = MarkPlan()
    rooms = {"left": grid.left, "top": grid.top,
             "right": grid.paper_w - grid.right,
             "bottom": grid.paper_h - grid.bottom}
    # THE MARKS SHRINK WITH THE MARGINS: a film frame with 1 mm margins
    # still gets them, thinner (the bold corner never more than a quarter of
    # the narrowest margin)
    least = max(0.0, min(rooms.values()))
    t = min(F.MARK_LINE_MM.value, max(0.05, least * 0.15))
    tb = min(t * F.MARK_BOLD_FACTOR.value, max(t, least * 0.25))
    gap: dict = {}
    arm: dict = {}
    for side, room in rooms.items():
        g = min(F.MARK_GAP_MM.value, max(0.0, room) / 3.0)
        a = min(F.MARK_ARM_MM.value, room - g - tb)
        gap[side] = g
        if a >= F.MARK_ARM_MIN_MM.value:
            arm[side] = a
        else:
            plan.left_out.append(side)
    plan.arm_mm = dict(arm)
    x0, y0, x1, y1 = grid.left, grid.top, grid.right, grid.bottom

    def add(a, b, c, d):
        plan.rects.append((min(a, c), min(b, d), max(a, c), max(b, d)))

    corners = (("top", "left", x0, y0, -1, -1), ("top", "right", x1, y0, 1, -1),
               ("bottom", "left", x0, y1, -1, 1),
               ("bottom", "right", x1, y1, 1, 1))
    for vside, hside, cx, cy, sx, sy in corners:
        w_ = tb if (vside, hside) == ("top", "right") else t
        if vside in arm:          # the arm continuing the grid's side edge
            g, a = gap[vside], arm[vside]
            add(cx, cy + sy * g, cx + sx * w_, cy + sy * (g + a))
        if hside in arm:          # the arm continuing the top / bottom edge
            g, a = gap[hside], arm[hside]
            add(cx + sx * g, cy, cx + sx * (g + a), cy + sy * w_)
    xc, yc = grid.centre(grid.cols - 1, 0)
    if "top" in arm and not letters_on_top:
        g, a = gap["top"], arm["top"]
        add(xc - t / 2.0, y0 - g, xc + t / 2.0, y0 - g - a)
    if "right" in arm:
        g, a = gap["right"], arm["right"]
        add(x1 + g, yc - t / 2.0, x1 + g + a, yc + t / 2.0)
    if "left" in arm and not numbers_on_left:
        g = gap["left"]
        s = min(F.START_MARK_MM.value, arm["left"], grid.patch_h * 0.8)
        _x, ya = grid.centre(0, 0)
        add(x0 - g - s, ya - s / 2.0, x0 - g, ya + s / 2.0)
    return plan


def draw_marks(render, grids: "list[PageGrid]", dpi: int, *,
               letters_on_top: bool = False,
               numbers_on_left: bool = False) -> "list[MarkPlan]":
    """Draw every page's marks onto *render* (the page images, and the
    display list a separated TIFF or a PDF is made from). In place."""
    from PIL import ImageDraw
    s = dpi / 25.4
    black = (0, 0, 0)
    plans = []
    for grid, img in zip(grids, render.images):
        plan = plan_marks(grid, letters_on_top=letters_on_top,
                          numbers_on_left=numbers_on_left)
        plans.append(plan)
        draw = ImageDraw.Draw(img)
        geom_list = (render.patch_geom[grid.page]
                     if getattr(render, "patch_geom", None) is not None
                     else None)
        for (a, b, c, d) in plan.rects:
            x0, y0 = int(round(a * s)), int(round(b * s))
            x1 = max(x0 + 1, int(round(c * s)))
            y1 = max(y0 + 1, int(round(d * s)))
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=black)
            if geom_list is not None:
                geom_list.append(("vrect", (x0, y0, x1, y1), black))
    return plans


def marks_left_out_message(plans: "list[MarkPlan]") -> "str | None":
    """One sentence for the sides whose margin held no mark, or None."""
    from workflow import measurement_messages as _mm
    sides = []
    for plan in plans:
        for side in plan.left_out:
            if side not in sides:
                sides.append(side)
    if not sides:
        return None
    names = {"left": tr("Left"), "top": tr("Top"), "right": tr("Right"),
             "bottom": tr("Bottom")}
    return tr(_mm._BARBIERI_MARKS_LEFT_OUT).format(
        sides=", ".join(names[s] for s in sides))


# ---------------------------------------------------------------------------
# the side file and the numbers
# ---------------------------------------------------------------------------

def page_record(grid: PageGrid, patterns, checks: "list[dict]") -> dict:
    names = reading_order(grid, patterns)
    aim = patch_name(grid.slot(grid.cols - 1, 0), grid.steps, patterns)
    gw = gateway_numbers(grid.cols, grid.rows, grid.pitch_x, grid.pitch_y)
    return {
        "page": grid.page + 1,
        "columns": grid.cols, "rows": grid.rows,
        "spectro32": spectro32_line(grid.cols, grid.rows, grid.pitch_x,
                                    grid.pitch_y),
        "gateway": gw,
        "grid_mm": [round(grid.left, 4), round(grid.top, 4),
                    round(grid.right, 4), round(grid.bottom, 4)],
        "patch_area_mm": [round(v, 4) for v in grid.area_mm],
        "aim_patch": aim,
        "aim_centre_mm": [round(v, 4) for v in grid.centre(grid.cols - 1, 0)],
        "first_patch": names[0] if names else "",
        "reading_order": names,
        "check_patches": checks,
    }


def write_side_file(path: Path, *, geom, layout, w: float, h: float,
                    grids: "list[PageGrid]", head: F.Head, patterns,
                    checks_by_page: "list[list[dict]]", check_on: bool,
                    marks_on: bool, designed: int, ti2_path: Path,
                    paper: str, dpi: int, size_key: str = "") -> dict:
    """Write ``<stem>.barbieri.json`` and return what it holds."""
    try:
        digest = hashlib.sha256(Path(ti2_path).read_bytes()).hexdigest()
    except OSError:
        digest = ""
    cells = sum(g.cols * g.rows for g in grids)
    doc = {
        "schema": SCHEMA,
        "instrument": "Barbieri Spectro 100xy",
        "head": head.key, "aperture_mm": head.aperture_mm,
        "mode": head.mode, "spectro32_mode": head.spectro32,
        "head_tested": head.tested,
        "paper": paper, "paper_mm": [round(w, 4), round(h, 4)], "dpi": dpi,
        "size_preset": size_key,
        "pitch_mm": [round(grids[0].pitch_x, 4) if grids else 0.0,
                     round(grids[0].pitch_y, 4) if grids else 0.0],
        "patch_mm": [round(geom.pwid, 4), round(geom.plen, 4)],
        "pages": len(grids), "designed_patches": int(designed),
        "cells": cells, "padding": int(layout.padding),
        "reading_minutes": reading_minutes(cells),
        "reading_order_rule": "rows from the top, each row from the left "
                              "(never back and forth)",
        "check_patches_on": bool(check_on), "marks_on": bool(marks_on),
        "ti2_sha256": digest,
        "pages_detail": [page_record(g, patterns,
                                     checks_by_page[i] if i < len(
                                         checks_by_page) else [])
                         for i, g in enumerate(grids)],
    }
    Path(path).write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return doc


def check_records(grids: "list[PageGrid]", slots: "list[int]", target,
                  labs: "list", patterns) -> "list[list[dict]]":
    """The check patches of every page, for the side file: role, name,
    device values and the expected CIELAB."""
    at = {s: i for i, s in enumerate(slots)}
    out = []
    for grid in grids:
        page = []
        for role, c, r in check_cells(grid):
            slot = grid.slot(c, r)
            i = at.get(slot)
            if i is None or i >= len(target.patches):
                continue
            dev = target.patches[i][0]
            page.append({"role": role,
                         "patch": patch_name(slot, grid.steps, patterns),
                         "device": [round(float(v), 4) for v in dev],
                         "lab": [round(v, 2) for v in labs[i]]})
        out.append(page)
    return out


def summary_lines(doc: dict) -> "list[str]":
    """The app log's lines for a Barbieri chart (translated): the opening,
    the pitch, and for every page the grid, Spectro32's and Gateway's
    numbers and the aim patch; then the reading time."""
    from workflow import measurement_messages as _mm
    head = head_of(doc.get("head"))
    pitch = doc.get("pitch_mm") or [0, 0]
    lines = [tr(_mm._BARBIERI_LOG_CHART).format(
        opening=head_label(head), code=head.spectro32 or "?",
        px=_mm_text(pitch[0], 2), py=_mm_text(pitch[1], 2),
        pages=int(doc.get("pages") or 0))]
    for pg in doc.get("pages_detail") or []:
        gw = pg.get("gateway") or {}
        lines.append(tr(_mm._BARBIERI_LOG_PAGE).format(
            page=pg.get("page"), cols=pg.get("columns"), rows=pg.get("rows"),
            r=pg.get("spectro32"), gx=gw.get("size_x_mm"),
            gy=gw.get("size_y_mm"), aim=pg.get("aim_patch"),
            first=pg.get("first_patch")))
    lines.append(tr(_mm._BARBIERI_LOG_TIME).format(
        minutes=int(doc.get("reading_minutes") or 0),
        cells=int(doc.get("cells") or 0)))
    return lines


def head_label(head: F.Head) -> str:
    """The opening as the choice lists it (translated)."""
    return {
        F.HEAD_REFLECTION_3: tr("3 mm, reflection"),
        F.HEAD_TRANSMISSION_3: tr("3 mm, transmission"),
        F.HEAD_TRANSMISSION_05: tr("0.5 mm, transmission"),
        F.HEAD_REFLECTION_6: tr("6 mm, reflection (model 2, untested)"),
    }.get(head.key, head.key)


def capacity(kw: dict) -> int:
    """Patches one page of the chart *kw* holds (Guided's count)."""
    from workflow.layout_engine import geometry, instruments, papers
    try:
        w, h = papers.dimensions_mm(kw.get("paper") or "A4")
        g = instruments.geom_from_build_kwargs(kw)
        return int(geometry.compute(g, w, h, 1_000_000).patches_per_page)
    except Exception:   # noqa: BLE001
        return 0


#: Guided's papers for the Barbieri: landscape sheets, whose patch area fits
#: one pass of the table with the default margins.
GUIDED_PAPERS = ("A4R", "LetterR", "A4", "Letter")


def guided_kwargs(paper: str, head_key: str) -> dict:
    """What Guided's Barbieri chart uses: the opening's own patch size, no
    gaps, and the default margins (`default_margins`)."""
    from workflow.layout_engine import papers
    head = head_of(head_key)
    w, h = papers.dimensions_mm(paper or "A4R")
    out = {"patch_w": head.default_patch_mm, "patch_h": head.default_patch_mm,
           "margins": default_margins(w, h), "layout_mode": "patch_first",
           "spacer_on": False, "spacer_mode": "none", "draw_indicators": False,
           "row_indicators": False, "patch_area_align": "top-left"}
    if head.key != F.DEFAULT_HEAD:
        out[HEAD_KEY] = head.key
    return out
