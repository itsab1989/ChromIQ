"""An i1iSis chart: the layout engine's own grid, plus what the instrument needs.

THE GRID IS i1PROFILER'S. i1Profiler does not read a layout from a file; it
COMPUTES the i1iSis grid from the page, the margins, the patch size, the
header, tight margins, the barcode and the patch count (REQUIREMENTS §1, 38 of
38 measured layouts predicted). ChromIQ lays its chart out with the very same
rule (:func:`split`, :func:`grid_for`), and its i1Profiler test-chart file
(`workflow.isis.export`) makes i1Profiler compute exactly that grid, so a
ChromIQ print can be measured in i1Profiler.

THE FURNITURE IS i1PROFILER'S (all numbers in `workflow.isis.chart_facts`):
the black bar at the leading edge across every column, a black diamond at
both ends of EVERY row (also the empty rows of a last page), the clear spaces,
the trailer, the two feed arrows, the dashed outline, the name and page line
and the corner labels. The optional barcode follows X-Rite's rules with the
decimal checksum i1Profiler writes.

THE COLUMNS ARE THE ENGINE'S STRIPS and the rows are the patches down a
strip: the engine places patch slot ``s`` at column ``s // R``, row ``s % R``
of page ``s // (C x R)``, which is i1Profiler's own placement (column-major,
rows shared evenly over the pages, unused cells at the end left white). This
module computes the margins that make the engine put the grid exactly where
the chart needs it (:func:`fixed_build_kwargs`), and draws everything else
after the engine has drawn the patches (:func:`draw_furniture`).

WHERE THE CHART SITS: top-left inside the page margins, as i1Profiler puts it
(measured on 30 of its page previews, REQUIREMENTS §10); Manual's patch area
alignment and the chart offset move the whole chart.

THE CUT RULE (ChromIQ's own, PROPOSAL §3): a sheet may be fed as printed when
X-Rite's limits hold measured from the PAPER edges; otherwise the chart is
still made and every instruction says to cut along the dashed outline. Only
what cannot be read even when cut is refused (:class:`IsisSheetRefused`).

Nothing here talks to an instrument.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import chart_facts as F
from .support import MODEL_STANDARD, MODEL_XL, model_of, device_name

#: Schema of the side file ``<stem>.isis.json`` (also in the ``.ti2``
#: keyword CHROMIQ_ISIS_LAYOUT).
SCHEMA = 1

#: The ``.ti2`` keyword naming the side file's schema.
LAYOUT_KEYWORD = "CHROMIQ_ISIS_LAYOUT"
#: The ``.ti2`` keyword recording the model width the chart was made for.
MODEL_KEYWORD = "CHROMIQ_ISIS_MODEL"

#: The build-kwargs keys (and `LayoutRecipe` fields) of an i1iSis chart.
MODEL_KEY = "isis_model"
HEADER_KEY = "isis_header_mm"
TIGHT_KEY = "isis_tight"
BARCODE_KEY = "isis_barcode"
TRAILER_KEY = "isis_trailer_mm"
ARROWS_KEY = "isis_arrows"
OUTLINE_KEY = "isis_outline"
CORNERS_KEY = "isis_corner_labels"
LETTERS_KEY = "isis_strip_letters"
BAND_KEY = "isis_notes_band"
BAND_PLACE_KEY = "isis_notes_place"
BAND_HEIGHT_KEY = "isis_notes_height_mm"
ALIGN_KEY = "isis_align"
#: The build-kwargs key with the run's chart-note lines for the trailer.
NOTES_LINES_KEY = "_isis_trailer_lines"
#: The build-kwargs key that carries the parsed options past
#: :func:`fixed_build_kwargs`.
OPTIONS_KEY = "_isis_options"

#: Every i1iSis-only build-kwargs key (the engine ignores them all).
OWN_KEYS = (MODEL_KEY, HEADER_KEY, TIGHT_KEY, BARCODE_KEY, TRAILER_KEY,
            ARROWS_KEY, OUTLINE_KEY, CORNERS_KEY, LETTERS_KEY,
            BAND_KEY, BAND_PLACE_KEY, BAND_HEIGHT_KEY, ALIGN_KEY)

#: The notes band's default height (header 56 mm, PROPOSAL §4.5).
BAND_HEIGHT_DEFAULT_MM = 24.0
#: Where strip letters may go.
LETTERS_PLACES = ("off", "top", "bottom")
BAND_PLACES = ("header", "trailer")
#: The patch area alignment an i1iSis chart takes when none was chosen.
DEFAULT_ALIGN = "top-left"
#: Extra trailer the bottom strip letters and the layout summary each take.
TRAILER_LINE_MM = 4.5

#: The papers Guided offers (PROPOSAL §6): A4, Letter, A5, 5 x 7 in,
#: 8 x 10 in; with the XL models also A3, 11 x 17 in and A3+ (329 x 483).
GUIDED_PAPERS = ("A4", "Letter", "148x210", "127x178", "203x254")
GUIDED_PAPERS_XL = GUIDED_PAPERS + ("A3", "279x432", "329x483")


def guided_margins(paper: str) -> "tuple | None":
    """Guided's page margins (top, right, bottom, left) for *paper* when the
    usual 5 mm would leave less than the 171 mm an i1iSis chart needs along
    the feed; None otherwise (the usual margins)."""
    from workflow.layout_engine import papers
    try:
        _w, h = papers.dimensions_mm(paper)
    except Exception:  # noqa: BLE001 - an unknown paper: the usual margins
        return None
    need = F.CHART_MIN_LENGTH_MM.value
    if h - 10.0 >= need - 1e-9:
        return None
    v = max(0.0, math.floor((h - need) / 2.0 * 10.0) / 10.0)
    return (v, 5.0, v, 5.0)


class IsisSheetRefused(ValueError):
    """A layout no i1iSis can read even when the sheet is cut along its
    outline. ``kind`` names the reason (M-ISIS-SHEET-CHECK)."""

    def __init__(self, kind: str, message: str) -> None:
        self.kind = kind
        super().__init__(message)


# ---------------------------------------------------------------------------
# options
# ---------------------------------------------------------------------------

def _num(value, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float(default)
    return v if math.isfinite(v) else float(default)


def _flag(value, default: bool) -> bool:
    return default if value is None else bool(value)


@dataclass(frozen=True)
class Options:
    """Everything that shapes an i1iSis chart, read safely from build kwargs."""
    model: str = MODEL_STANDARD
    pw: float = 6.0
    ph: float = 6.0
    header: float = 32.0
    tight: bool = False
    barcode: bool = False
    trailer: float = 25.5
    arrows: bool = True
    outline: bool = True
    corner_labels: bool = True
    strip_letters: str = "off"
    row_numbers: bool = False
    notes_band: bool = False
    notes_place: str = "header"
    notes_height: float = BAND_HEIGHT_DEFAULT_MM
    #: page margins (top, right, bottom, left)
    margins: tuple = (5.0, 5.0, 5.0, 5.0)
    offset: tuple = (0.0, 0.0)
    align: str = DEFAULT_ALIGN
    #: rows per page asked for (Manual's "Max strip length"); None = auto
    max_rows: "int | None" = None
    stamp: bool = False
    #: The strip letters and row numbers, with the engine's OWN label
    #: controls (owner, 2026-11-14: one control, no duplicates): on/off from
    #: "Show strip indicators" / "Show row indicators", the face, size,
    #: bold, italic, rotation, alignment, underline and offsets from the
    #: label style; only the PLACE of the letters is the i1iSis's own.
    letter_font: str = "Inter"
    letter_size: float = 0.0
    letter_bold: bool = False
    letter_italic: bool = False
    letter_rotation: int = 0
    number_rotation: int = 0
    letter_align: str = "center"
    underline: str = "off"
    underline_mm: float = 0.5
    underline_gap: float = 0.5
    label_offset_y: float = 0.0
    label_offset_x: float = 0.0
    #: The run's chart notes (and the settings line) printed in the trailer
    #: when no notes band holds them, one line each.
    trailer_lines: tuple = ()
    #: How the patch size was chosen ("patch_first" or "area_first").
    layout_mode: str = "patch_first"

    @property
    def xl(self) -> bool:
        return self.model == MODEL_XL

    @property
    def d1(self) -> float:
        return (F.DIST1_TIGHT_MM if self.tight else F.DIST1_MM).value

    @property
    def d2(self) -> float:
        return (F.DIST2_TIGHT_MM if self.tight else F.DIST2_MM).value

    @property
    def side(self) -> float:
        return self.d1 + F.DIAMOND_W_MM.value + self.d2

    @property
    def header_mm(self) -> float:
        """The header length drawn: the option, or long enough for the notes
        band in the header, never outside 32 .. 80."""
        h = self.header
        if self.notes_band and self.notes_place == "header":
            h = max(h, F.HEADER_MIN_MM.value + self.notes_height)
        return min(max(h, F.HEADER_MIN_MM.value), F.HEADER_MAX_MM.value)

    @property
    def trailer_mm(self) -> float:
        """The trailer asked for: the option, plus the room the notes band in
        the trailer, the bottom strip letters and the layout summary take."""
        t = max(self.trailer, F.TRAILER_MIN_MM.value)
        need = F.TRAILER_MIN_MM.value
        if self.notes_band and self.notes_place == "trailer":
            need += self.notes_height
        if self.strip_letters == "bottom":
            need += TRAILER_LINE_MM
        if self.stamp:
            need += TRAILER_LINE_MM
        need += TRAILER_LINE_MM * len(self.trailer_lines)
        return max(t, need)

    @property
    def under_bar(self) -> float:
        """Bar bottom to the first row: 6 mm, or 20 mm with the barcode."""
        return (F.CLEAR_UNDER_BAR_BARCODE_MM if self.barcode
                else F.CLEAR_UNDER_BAR_MM).value

    @property
    def grid_top(self) -> float:
        """The first row's top, from the chart's leading edge."""
        return (self.header_mm + F.BAR_TOP_EXTRA_MM.value
                + F.BAR_HEIGHT_MM.value + self.under_bar)

    @property
    def cap(self) -> float:
        return F.CAP_MM.value[self.model]


def clamp_patch_mm(value) -> float:
    """A patch size inside X-Rite's 6 .. 20 mm (0 / unset = 6, the default)."""
    v = _num(value, 0.0)
    if v <= 0:
        return F.PATCH_DEFAULT_MM.value
    return min(max(v, F.PATCH_MIN_MM.value), F.PATCH_MAX_MM.value)


def options_from(kw: dict) -> Options:
    """The :class:`Options` of a build-kwargs dict (or a dict of recipe-like
    keys). Never raises; every value is held inside its range."""
    pre = kw.get(OPTIONS_KEY)
    if isinstance(pre, Options):
        return pre
    margins = kw.get("margins")
    try:
        margins = tuple(max(0.0, float(v)) for v in margins) \
            if margins and len(margins) == 4 else None
    except (TypeError, ValueError):
        margins = None
    if margins is None:
        m = F.MARGIN_DEFAULT_MM.value
        margins = (m, m, m, m)
    # where the letters go (the i1iSis's own: the text band at the top or
    # the trailer); whether they are drawn is the engine's own "Show strip
    # indicators" (draw_indicators, default off on an i1iSis recipe)
    letters = str(kw.get(LETTERS_KEY) or "top")
    if letters not in ("top", "bottom"):
        letters = "top"
    if not kw.get("draw_indicators", False):
        letters = "off"
    place = str(kw.get(BAND_PLACE_KEY) or "header")
    ph = clamp_patch_mm(kw.get("patch_h"))
    max_rows = None
    ms = _num(kw.get("max_strip"), 0.0)
    if ms > 0:
        max_rows = max(1, int(math.floor(ms / ph + 1e-9)))
    opts = Options(
        model=model_of(kw.get(MODEL_KEY)),
        pw=clamp_patch_mm(kw.get("patch_w")),
        ph=ph,
        header=min(max(_num(kw.get(HEADER_KEY), F.HEADER_DEFAULT_MM.value),
                       F.HEADER_MIN_MM.value), F.HEADER_MAX_MM.value),
        tight=_flag(kw.get(TIGHT_KEY), False),
        barcode=_flag(kw.get(BARCODE_KEY), False),
        trailer=max(_num(kw.get(TRAILER_KEY), F.TRAILER_MIN_MM.value),
                    F.TRAILER_MIN_MM.value),
        arrows=_flag(kw.get(ARROWS_KEY), True),
        outline=_flag(kw.get(OUTLINE_KEY), True),
        corner_labels=_flag(kw.get(CORNERS_KEY), True),
        strip_letters=letters,
        # "Show row indicators": None (the instrument's own) is off here
        row_numbers=bool(kw.get("row_indicators")),
        notes_band=_flag(kw.get(BAND_KEY), False),
        notes_place=place if place in BAND_PLACES else "header",
        notes_height=min(max(_num(kw.get(BAND_HEIGHT_KEY),
                                  BAND_HEIGHT_DEFAULT_MM), 4.0),
                         F.HEADER_MAX_MM.value - F.HEADER_MIN_MM.value),
        margins=margins,
        offset=(max(0.0, _num(kw.get("offset_x"), 0.0)),
                max(0.0, _num(kw.get("offset_y"), 0.0))),
        align=str(kw.get(ALIGN_KEY) or DEFAULT_ALIGN),
        max_rows=max_rows,
        stamp=bool(kw.get("stamp_command")),
        letter_font=str(kw.get("indicator_font") or "Inter"),
        letter_size=max(0.0, _num(kw.get("indicator_size_mm"), 0.0)),
        letter_bold=bool(kw.get("indicator_bold")),
        letter_italic=bool(kw.get("indicator_italic")),
        letter_rotation=_quarter(kw.get("indicator_rotation")),
        number_rotation=_quarter(kw.get("row_indicator_rotation")),
        letter_align=(str(kw.get("indicator_align") or "center")
                      if kw.get("indicator_align") in ("left", "center",
                                                       "right") else "center"),
        underline=str(kw.get("underline_mode") or "off"),
        underline_mm=min(max(_num(kw.get("underline_thickness_mm"), 0.5),
                             0.1), 2.0),
        underline_gap=min(max(_num(kw.get("underline_gap_mm"), 0.5), 0.0),
                          3.0),
        label_offset_y=_num(kw.get("strip_label_offset_mm"), 0.0),
        label_offset_x=_num(kw.get("strip_label_offset_x_mm"), 0.0),
        trailer_lines=tuple(str(x) for x in (kw.get(NOTES_LINES_KEY) or ())
                            if str(x).strip()),
        layout_mode=("area_first" if kw.get("layout_mode") == "area_first"
                     else "patch_first"),
    )
    if opts.layout_mode == "area_first":
        opts = _area_first(opts, kw)
    return opts


def _quarter(v) -> int:
    try:
        d = int(v or 0) % 360
    except (TypeError, ValueError):
        return 0
    return d if d in (0, 90, 180, 270) else 0


def _area_first(opts: Options, kw: dict) -> Options:
    """"Prioritise chart area" for an i1iSis chart: the patch size that
    fills the page, then the grid follows i1Profiler's rule. By columns and
    rows when both are set; otherwise the LARGEST patch (in X-Rite's 6 to
    20 mm, in 0.25 mm steps so the barcode can state it, at the chosen
    height-to-width ratio, never below the minimum patch) at which the
    chart's patches fit on one page; with no patch count known, the
    minimum. Any size it picks is clamped to 6 .. 20 mm."""
    from dataclasses import replace as _rep
    from workflow.layout_engine import papers
    try:
        w, h = papers.dimensions_mm(kw.get("paper") or "A4")
    except (ValueError, TypeError):
        return opts
    step = F.BARCODE_STEP_MM.value
    lo, hi = F.PATCH_MIN_MM.value, F.PATCH_MAX_MM.value

    def q(v):
        return min(max(math.floor(v / step + 1e-9) * step, lo), hi)
    mt, mr, mb, ml = opts.margins
    ox, oy = opts.offset
    cols = int(_num(kw.get("area_cols"), 0))
    rows = int(_num(kw.get("area_rows"), 0))
    if str(kw.get("area_method") or "") == "by_grid" and cols > 0 and rows > 0:
        pw = q((w - ml - mr - ox - 2 * opts.side) / cols)
        ph = q((h - mt - mb - oy - opts.grid_top - opts.trailer_mm) / rows)
        return _rep(opts, pw=pw, ph=ph)
    ratio = _num(kw.get("area_ratio"), 0.0) or 1.0
    floor = max(lo, _num(kw.get("area_min_patch"), 0.0))
    try:
        n = int(kw.get(COUNT_KEY) or 0)
    except (TypeError, ValueError):
        n = 0
    if n < 1:
        return _rep(opts, pw=q(floor), ph=q(floor * ratio))
    s_ = hi
    while s_ >= floor - 1e-9:
        cand = _rep(opts, pw=q(s_), ph=q(s_ * ratio))
        c, r = limits(cand, w, h)
        if c >= 1 and r >= 1 and c * r >= n:
            return cand
        s_ -= step
    return _rep(opts, pw=q(floor), ph=q(floor * ratio))

# ---------------------------------------------------------------------------
# the grid
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Grid:
    """Columns and rows per page, pages, and the limits they came from."""
    C: int
    R: int
    P: int
    cmax: int
    rmax: int
    N: int

    @property
    def cells(self) -> int:
        return self.C * self.R * self.P


def split(N: int, cmax: int, rmax: int) -> "tuple[int, int, int]":
    """i1Profiler's own split (REQUIREMENTS §1, VERIFIED on 38 layouts):
    total rows T = ceil(N / Cmax); pages P = ceil(T / Rmax); rows per page
    R = ceil(T / P), shared evenly; columns C = ceil(N / (R x P))."""
    N, cmax, rmax = int(N), int(cmax), int(rmax)
    if N < 1 or cmax < 1 or rmax < 1:
        raise ValueError("split needs N, Cmax and Rmax of at least 1")
    T = -(-N // cmax)
    P = -(-T // rmax)
    R = -(-T // P)
    C = -(-N // (R * P))
    return C, R, P


def column_cap(opts: Options) -> int:
    """The most columns the instrument reads (REQUIREMENTS §12): with normal
    side geometry the whole chart within 218 / 318 mm, with tight margins
    the right marker's right edge (chart width - Dist 1) within it."""
    room = opts.cap - 2.0 * opts.side + (opts.d1 if opts.tight else 0.0)
    return int(math.floor(room / opts.pw + 1e-9))


def overhead_mm(opts: Options, trailer: "float | None" = None) -> float:
    """Leading edge to the first row plus the trailer."""
    t = opts.trailer_mm if trailer is None else trailer
    return opts.grid_top + t


def limits(opts: Options, paper_w: float, paper_h: float
           ) -> "tuple[int, int]":
    """(Cmax, Rmax) for ChromIQ's own chart on this page: i1Profiler's rule
    (with its 0.5 mm fit tolerance, never past the paper edge), the device's
    column cap, the trailer ChromIQ draws, at most 660 mm of chart and 3000
    patches a page, and the rows a person asked for."""
    mt, mr, mb, ml = opts.margins
    ox, oy = opts.offset
    t = F.COLUMN_FIT_TOLERANCE_MM.value
    pw, ph = opts.pw, opts.ph
    cmax = int(math.floor((paper_w - ml - mr - ox - 2 * opts.side + t) / pw
                          + 1e-9))
    # the fit tolerance may use the right margin, never paper beyond the edge
    cmax = min(cmax, int(math.floor((paper_w - ml - ox - 2 * opts.side) / pw
                                    + 1e-9)))
    cmax = min(cmax, column_cap(opts))
    over = overhead_mm(opts)
    rmax = int(math.floor((paper_h - mt - mb - oy - over) / ph + 1e-9))
    rmax = min(rmax, int(math.floor((F.CHART_MAX_LENGTH_MM.value - over) / ph
                                    + 1e-9)))
    if cmax >= 1:
        rmax = min(rmax, F.PATCHES_PER_PAGE_MAX.value // cmax)
    if opts.max_rows:
        rmax = min(rmax, opts.max_rows)
    return cmax, rmax


def extra_page_reasons(N: int, paper_w: float, paper_h: float,
                       opts: Options) -> "list[str]":
    """Why the chart takes more pages than its paper alone would need:
    "patches" (no more than 3000 patches on one page, X-Rite's limit) and
    "length" (no chart longer than 660 mm). Empty when neither binds."""
    mt, mr, mb, ml = opts.margins
    oy = opts.offset[1]
    cmax, rmax = limits(opts, paper_w, paper_h)
    if cmax < 1:
        return []
    page_rows = int(math.floor((paper_h - mt - mb - oy - overhead_mm(opts))
                               / opts.ph + 1e-9))
    if opts.max_rows:
        page_rows = min(page_rows, opts.max_rows)
    if page_rows <= rmax or page_rows < 1:
        return []
    free = split(max(1, int(N)), cmax, page_rows)[2]
    used = split(max(1, int(N)), cmax, rmax)[2]
    if used <= free:
        return []
    out = []
    if cmax * page_rows > F.PATCHES_PER_PAGE_MAX.value:
        out.append("patches")
    if overhead_mm(opts) + page_rows * opts.ph > F.CHART_MAX_LENGTH_MM.value:
        out.append("length")
    return out


def extra_page_message(reasons: "list[str]", pages: int) -> str:
    """The Create Chart log line for :func:`extra_page_reasons`."""
    from core.i18n import tr
    if not reasons:
        return ""
    why = []
    if "patches" in reasons:
        why.append(tr("an i1iSis reads at most 3000 patches on one page"))
    if "length" in reasons:
        why.append(tr("an i1iSis takes no chart longer than 660 mm"))
    return tr("This chart was spread over {pages} pages because {why}. Each "
              "page is measured on its own in i1Profiler.").format(
                  pages=pages, why=tr(" and ").join(why))


def grid_for(N: int, paper_w: float, paper_h: float, opts: Options) -> Grid:
    """The grid of an N-patch chart on this page, or IsisSheetRefused when
    no i1iSis could read a chart on it even when cut."""
    from core.i18n import tr
    cmax, rmax = limits(opts, paper_w, paper_h)
    mt, mr, mb, ml = opts.margins
    oy = opts.offset[1]
    if cmax < 1:
        raise IsisSheetRefused("narrow", tr(
            "the page is too narrow for even one column of patches with the "
            "markers on both sides"))
    need = F.CHART_MIN_LENGTH_MM.value
    if paper_h - mt - mb - oy < need - 1e-6 and paper_h - oy >= need - 1e-6:
        # THE MARGINS, NOT THE PAPER: say how small they must be (5 x 7 in
        # with 5 mm margins, 2026-11-14)
        m = math.floor((paper_h - oy - need) / 2.0 * 10.0) / 10.0
        raise IsisSheetRefused("short", tr(
            "the page margins leave {room} mm along the feed and an i1iSis "
            "chart needs {need} mm. It fits with top and bottom margins of "
            "{m} mm or less").format(room=f"{paper_h - mt - mb - oy:.1f}",
                                     need=f"{need:g}", m=f"{m:.1f}"))
    if paper_h - mt - mb - oy < need - 1e-6:
        raise IsisSheetRefused("short", tr(
            "the chart would be shorter than 170 mm along the feed, and the "
            "i1iSis does not take sheets that short"))
    if rmax < 1:
        raise IsisSheetRefused("short", tr(
            "the page is too short for even one row of patches between the "
            "bar and the trailer"))
    C, R, P = split(max(1, int(N)), cmax, rmax)
    return Grid(C=C, R=R, P=P, cmax=cmax, rmax=rmax, N=max(1, int(N)))


def page_capacity(paper_w: float, paper_h: float, opts: Options) -> int:
    """Patches one page holds (Cmax x Rmax), 0 when none."""
    try:
        cmax, rmax = limits(opts, paper_w, paper_h)
    except Exception:  # noqa: BLE001
        return 0
    return max(0, cmax) * max(0, rmax)


# ---------------------------------------------------------------------------
# where everything is
# ---------------------------------------------------------------------------

_VFRAC = {"top": 0.0, "center": 0.5, "bottom": 1.0}
_HFRAC = {"left": 0.0, "center": 0.5, "right": 1.0}


def _align_fractions(align: str) -> "tuple[float, float]":
    a = (align or DEFAULT_ALIGN).strip().lower()
    if a == "center":
        return 0.5, 0.5
    if "-" in a:
        v, h = a.split("-", 1)
    else:
        v, h = "center", a
    return _VFRAC.get(v, 0.0), _HFRAC.get(h, 0.0)


@dataclass(frozen=True)
class Sheet:
    """Every element of the chart in millimetres on the PAGE (x from the
    paper's left edge, y from its leading edge)."""
    opts: Options
    grid: Grid
    paper_w: float
    paper_h: float
    #: the chart's outline: left, top, width, height
    x0: float
    y0: float
    width: float
    height: float
    #: 2 x side + C x pw (the outline may be wider, never narrower)
    nominal_width: float
    grid_x: float
    grid_y: float
    bar_y: float
    trailer: float
    fed_as_printed: bool
    #: why the sheet must be cut (empty when it may be fed as printed)
    cut_reasons: tuple = ()
    notes: tuple = field(default=())

    @property
    def header(self) -> float:
        return self.opts.header_mm

    @property
    def grid_w(self) -> float:
        return self.grid.C * self.opts.pw

    @property
    def grid_h(self) -> float:
        return self.grid.R * self.opts.ph

    @property
    def bar(self) -> "tuple[float, float, float, float]":
        return (self.grid_x, self.bar_y, self.grid_w, F.BAR_HEIGHT_MM.value)

    @property
    def left_diamond_x(self) -> float:
        return self.x0 + self.opts.d1

    @property
    def right_diamond_x(self) -> float:
        return self.grid_x + self.grid_w + self.opts.d2

    @property
    def right_marker_edge(self) -> float:
        """The right marker's right edge from the paper's left edge."""
        return self.right_diamond_x + F.DIAMOND_W_MM.value

    def row_centre(self, r: int) -> float:
        return self.grid_y + (r + 0.5) * self.opts.ph

    def diamonds(self) -> "list[tuple[float, float, float, float]]":
        """Every diamond's bounding box (x, y, w, h), left and right of every
        row, the empty rows of a last page included."""
        w, h = F.DIAMOND_W_MM.value, F.DIAMOND_H_MM.value
        out = []
        for r in range(self.grid.R):
            cy = self.row_centre(r)
            for x in (self.left_diamond_x, self.right_diamond_x):
                out.append((x, cy - h / 2.0, w, h))
        return out

    @property
    def barcode_y(self) -> float:
        return self.bar_y + F.BAR_HEIGHT_MM.value + F.BARCODE_GAP_MM.value

    @property
    def last_row_bottom(self) -> float:
        return self.grid_y + self.grid_h

    def header_band(self) -> "tuple[float, float, float, float] | None":
        """The notes band in the header (PROPOSAL §5): across the grid's
        width, from the end of the text band to 20 mm above the bar."""
        if not (self.opts.notes_band and self.opts.notes_place == "header"):
            return None
        top = self.y0 + F.TEXT_BAND_MM.value
        bottom = self.y0 + self.header - F.CLEAR_ABOVE_BAR_MM.value
        if bottom - top < 1.0:
            return None
        return (self.grid_x, top, self.grid_w, bottom - top)

    def trailer_band(self) -> "tuple[float, float, float, float] | None":
        """The notes band in the trailer: from 22 mm after the last row to
        the trailing text line."""
        if not (self.opts.notes_band and self.opts.notes_place == "trailer"):
            return None
        top = self.last_row_bottom + F.TRAILER_INNER_KEEP_OUT_MM.value
        bottom = self.y0 + self.height - F.TRAILER_TEXT_MM.value
        if self.opts.strip_letters == "bottom":
            bottom -= TRAILER_LINE_MM
        if self.opts.stamp:
            bottom -= TRAILER_LINE_MM
        if bottom - top < 1.0:
            return None
        return (self.grid_x, top, self.grid_w, bottom - top)

    def keep_out(self) -> "list[tuple[str, tuple]]":
        """The zones nothing but the instrument's own marks may enter:
        the 20 mm above the bar (Z3) across the chart, the bar itself, the
        space under it (the barcode only), the grid, 3 mm around every
        diamond, and the first 22 mm after the last row."""
        o = self.opts
        zones = []
        top3 = self.bar_y - F.CLEAR_ABOVE_BAR_MM.value
        zones.append(("above_bar", (self.x0, top3, self.width,
                                    F.CLEAR_ABOVE_BAR_MM.value)))
        zones.append(("bar", self.bar))
        zones.append(("under_bar", (self.x0, self.bar_y + F.BAR_HEIGHT_MM.value,
                                    self.width, o.under_bar)))
        zones.append(("grid", (self.grid_x, self.grid_y, self.grid_w,
                               self.grid_h)))
        c = F.DIAMOND_CLEAR_MM.value
        for (x, y, w, h) in self.diamonds():
            zones.append(("diamond", (x - c, y - c, w + 2 * c, h + 2 * c)))
        zones.append(("trailer_inner", (self.x0, self.last_row_bottom,
                                        self.width,
                                        F.TRAILER_INNER_KEEP_OUT_MM.value)))
        return zones


def _cut_reasons(opts: Options, x0: float, y0: float, nominal_w: float,
                 paper_w: float, paper_h: float) -> "list[str]":
    """Why this sheet cannot be fed as printed (PROPOSAL §3): the paper
    width and length, the right marker from the paper's left edge, the
    leading paper edge to the bar, and Dist 1 from the paper edge."""
    lo, hi = F.PAPER_W_MM.value[opts.model]
    llo, lhi = F.PAPER_LEN_MM.value
    out = []
    if not (lo - 1e-6 <= paper_w <= hi + 1e-6):
        out.append("paper_width")
    if not (llo - 1e-6 <= paper_h <= lhi + 1e-6):
        out.append("paper_length")
    if x0 + nominal_w - opts.d1 > opts.cap + 1e-6:
        out.append("marker_reach")
    if y0 + opts.header_mm + F.BAR_TOP_EXTRA_MM.value \
            > F.LEADER_MAX_FROM_PAPER_MM.value + 1e-6:
        out.append("leader")
    if x0 + opts.d1 < F.DIST1_MIN_FROM_PAPER_MM.value - 1e-6:
        out.append("marker_edge")
    return out


def sheet_for(grid: Grid, paper_w: float, paper_h: float,
              opts: Options) -> Sheet:
    """Place the chart of *grid* on the page."""
    nominal_w = 2.0 * opts.side + grid.C * opts.pw
    width = max(nominal_w, F.CHART_MIN_WIDTH_MM.value)
    if opts.row_numbers:
        # ROOM FOR THE ROW NUMBERS INSIDE THE OUTLINE (so a cut sheet keeps
        # them): 3 mm of white after the right marker, then the widest
        # number, when the page has that paper inside its right margin
        size = opts.letter_size or min(3.0, max(1.2, opts.ph * 0.5))
        # the widest digit, not "9": in Inter a "4" is wider, so a chart
        # widened for "99" set its "14" smaller than the room allowed
        digits = len(str(grid.R))
        room = paper_w - opts.margins[1] - opts.margins[3] - opts.offset[0]
        # and never wider than the sheet the model takes, so a sheet cut
        # along the outline still feeds (review of a7ca1489e, m2); without
        # the room the row numbers are left off and said
        widest = F.PAPER_W_MM.value[opts.model][1]

        def _need(sz: float) -> float:
            nw = max(_label_box(0, 0, sz, ch * digits, opts.number_rotation,
                                opts.letter_font, opts.letter_bold,
                                opts.letter_italic)[2]
                     for ch in "0123456789")
            return (nominal_w - opts.d1 + F.DIAMOND_CLEAR_MM.value
                    + max(0.0, opts.label_offset_x) + nw + 0.5)
        # SET SMALLER BEFORE LEFT OFF, as `_plan_numbers` sets them. The
        # owner, 2026-11-15, on 4.3.38: "Show row indicators" ticked had no
        # effect. On every default A4 chart (28 columns of 6 mm) the numbers
        # at their full 3 mm needed 200.4 mm of the 200 inside the margins,
        # so the width never grew, and `_plan_numbers` then had 2 mm left
        # for them and dropped them, however small it set them. The width
        # now grows for the largest size down to LABEL_MIN_MM that fits; a
        # chart whose numbers fitted at full size is unchanged.
        need = _need(size)
        while (need > min(room, widest) + 1e-6
               and size - 0.1 >= LABEL_MIN_MM - 1e-9):
            size -= 0.1
            need = _need(size)
        if need <= room + 1e-6 and need <= widest + 1e-6:
            width = max(width, need)
    natural_h = opts.grid_top + grid.R * opts.ph + opts.trailer_mm
    height = max(natural_h, F.CHART_MIN_LENGTH_MM.value)
    trailer = height - opts.grid_top - grid.R * opts.ph
    mt, mr, mb, ml = opts.margins
    ox, oy = opts.offset
    fv, fh = _align_fractions(opts.align)
    slack_x = max(0.0, paper_w - mr - ml - ox - width)
    slack_y = max(0.0, paper_h - mb - mt - oy - height)
    x0 = ml + ox + fh * slack_x
    y0 = mt + oy + fv * slack_y
    reasons = _cut_reasons(opts, x0, y0, nominal_w, paper_w, paper_h)
    return Sheet(opts=opts, grid=grid, paper_w=paper_w, paper_h=paper_h,
                 x0=x0, y0=y0, width=width, height=height,
                 nominal_width=nominal_w,
                 grid_x=x0 + opts.side, grid_y=y0 + opts.grid_top,
                 bar_y=y0 + opts.header_mm + F.BAR_TOP_EXTRA_MM.value,
                 trailer=trailer, fed_as_printed=not reasons,
                 cut_reasons=tuple(reasons))


def check_sheet(sheet: Sheet) -> None:
    """Refuse (IsisSheetRefused) what no i1iSis can read even when the sheet
    is cut along its outline: a chart wider than the instrument reads,
    longer than 660 mm, more than 3000 patches on a page, a chart off its
    page, a barcode with a patch size it cannot state or a title it cannot
    hold."""
    from core.i18n import tr
    o, g = sheet.opts, sheet.grid
    if sheet.nominal_width - (o.d1 if o.tight else 0.0) > o.cap + 1e-6:
        raise IsisSheetRefused("wide", tr(
            "wider than the instrument reads ({w} mm, at most {cap} mm)"
        ).format(w=f"{sheet.nominal_width:.1f}", cap=f"{o.cap:g}"))
    if sheet.height > F.CHART_MAX_LENGTH_MM.value + 1e-6:
        raise IsisSheetRefused("long", tr(
            "longer than 660 mm along the feed"))
    if g.C * g.R > F.PATCHES_PER_PAGE_MAX.value:
        raise IsisSheetRefused("many", tr(
            "more than 3000 patches on one page"))
    if sheet.x0 + sheet.width > sheet.paper_w + 1e-6 and \
            sheet.width <= sheet.paper_w - o.offset[0] + 1e-6:
        # the side margins, not the paper (a 60 mm sheet with 5 mm margins
        # cannot hold the 60 mm the narrowest chart is wide)
        m = math.floor((sheet.paper_w - o.offset[0] - sheet.width)
                       / 2.0 * 10.0) / 10.0
        room = sheet.paper_w - o.margins[1] - o.margins[3] - o.offset[0]
        if m <= 0:
            raise IsisSheetRefused("off_page", tr(
                "the page margins leave {room} mm across and this chart is "
                "{need} mm wide. It fits only with no left and right "
                "margins").format(room=f"{room:.1f}",
                                  need=f"{sheet.width:.1f}"))
        raise IsisSheetRefused("off_page", tr(
            "the page margins leave {room} mm across and this chart is "
            "{need} mm wide. It fits with left and right margins of {m} mm "
            "or less").format(
                room=f"{sheet.paper_w - o.margins[1] - o.margins[3] - o.offset[0]:.1f}",
                need=f"{sheet.width:.1f}", m=f"{max(m, 0.0):.1f}"))
    if (sheet.x0 + sheet.width > sheet.paper_w + 1e-6
            or sheet.y0 + sheet.height > sheet.paper_h + 1e-6):
        raise IsisSheetRefused("off_page", tr(
            "the chart does not fit on the page with these margins and this "
            "offset"))
    if o.barcode:
        for v in (o.pw, o.ph):
            steps = (v - F.PATCH_MIN_MM.value) / F.BARCODE_STEP_MM.value
            if abs(steps - round(steps)) > 1e-6:
                raise IsisSheetRefused("barcode_size", tr(
                    "a barcode with a patch size the barcode cannot state "
                    "(it counts in steps of 0.25 mm)"))
        if barcode_elements(barcode_text(g, 1, "")) * F.BARCODE_PITCH_MM.value \
                - 1.0 > sheet.grid_w + 1e-6:
            raise IsisSheetRefused("barcode_width", tr(
                "a barcode longer than the chart is wide"))


def layout_for(N: int, paper_w: float, paper_h: float, kw: dict
               ) -> "tuple[Options, Grid, Sheet]":
    """Options, grid and sheet of an N-patch chart, checked."""
    opts = options_from(kw)
    grid = grid_for(N, paper_w, paper_h, opts)
    sheet = sheet_for(grid, paper_w, paper_h, opts)
    check_sheet(sheet)
    return opts, grid, sheet


# ---------------------------------------------------------------------------
# the engine's part
# ---------------------------------------------------------------------------

#: The build-kwargs key a caller sets with the chart's patch count, so the
#: margins make the engine lay out exactly this chart's grid. Without it (a
#: capacity estimate) the margins hold one full page, Cmax x Rmax.
COUNT_KEY = "area_target_count"


def engine_margins(sheet: Sheet) -> "tuple[float, float, float, float]":
    """The (top, right, bottom, left) margins that make the engine put
    exactly C columns and R rows at the grid's place: the grid's own left
    and top, and half a patch of room beyond its right and bottom edges."""
    o, g = sheet.opts, sheet.grid
    left = sheet.grid_x
    top = sheet.grid_y
    right = sheet.paper_w - left - (g.C + 0.5) * o.pw
    bottom = sheet.paper_h - top - (g.R + 0.5) * o.ph
    return (top, right, bottom, left)


def fixed_build_kwargs(kw: dict) -> dict:
    """*kw* (layout-engine build kwargs) with what an i1iSis chart fixes:
    patch-first, no spacers or gaps, no edge spacers, no engine labels, text,
    stamp, clip band or helper markers (this module draws the chart's own),
    no honeycomb or stagger, and margins that put the engine's grid exactly
    where the chart needs it (:func:`engine_margins`). The person's own
    margins, offsets and alignment place the CHART (:func:`sheet_for`).

    Used by the capacity estimate and by the build alike, so the two
    cannot disagree. Raises IsisSheetRefused for an unreadable layout."""
    from workflow.layout_engine import papers
    out = dict(kw)
    opts = options_from(kw)
    paper = kw.get("paper") or "A4"
    w, h = papers.dimensions_mm(paper)
    try:
        n = int(kw.get(COUNT_KEY) or 0)
    except (TypeError, ValueError):
        n = 0
    if n < 1:
        cmax, rmax = limits(opts, w, h)
        n = max(1, cmax) * max(1, rmax)
    grid = grid_for(n, w, h, opts)
    sheet = sheet_for(grid, w, h, opts)
    out.update(
        patch_w=opts.pw, patch_h=opts.ph, pscale=1.0, sscale=1.0,
        spacer_on=False, spacer_mode="none", spacer_width=None,
        inter_patch=0.0, strip_gap=0.0, edge_spacers=False,
        max_strip=None, nolimit=True, offset_x=0.0, offset_y=0.0,
        helper_markers=False, margins=engine_margins(sheet),
        use_instrument_margins=True, layout_mode="patch_first",
        patch_area_align="top-left", density=1, cm_stagger=False,
        hflag=False, nolpcbord=True, clip_band=0.0,
        clip_content_mode="off", chart_text="", stamp_command=False,
        side_stamp=False, strip_indicator_gap=0.0, draw_indicators=False,
        row_indicators=False, underline_mode="off", text_edge_top=4.0,
        strip_label_offset_mm=0.0, strip_label_offset_x_mm=0.0,
        indicator_rotation=0, row_indicator_rotation=0)
    out[OPTIONS_KEY] = opts
    return out


def with_guided_values(recipe):
    """*recipe* (rebuilt from Guided's build kwargs, which carry no margins
    or patch size) with what Guided's i1iSis chart really used: i1Profiler's
    6 x 6 mm patches, 5 mm margins, the chart top-left, no spacers. So Manual
    opens on the chart Guided made, and the chart's record says so."""
    if getattr(recipe, "instrument", None) != "XRISIS":
        return recipe
    if not (recipe.patch_w_mm and recipe.patch_h_mm):
        recipe.patch_w_mm = recipe.patch_h_mm = F.PATCH_DEFAULT_MM.value
    m = F.MARGIN_DEFAULT_MM.value
    recipe.margin_top = recipe.margin_right = m
    recipe.margin_bottom = recipe.margin_left = m
    recipe.use_instrument_margins = False
    recipe.patch_area_align = DEFAULT_ALIGN
    recipe.spacer_mode, recipe.spacer_on = "none", False
    recipe.inter_patch_mm = recipe.strip_gap_mm = 0.0
    recipe.edge_spacers = False
    recipe.layout_mode = "patch_first"
    return recipe


def capacity(kw: dict) -> int:
    """Patches one page of the chart *kw* holds (Guided's count)."""
    from workflow.layout_engine import papers
    try:
        w, h = papers.dimensions_mm(kw.get("paper") or "A4")
    except (ValueError, TypeError):
        return 0
    return page_capacity(w, h, options_from(kw))


# ---------------------------------------------------------------------------
# the barcode (X-Rite chart rules §4, decoded in i1Profiler's charts)
# ---------------------------------------------------------------------------

CODE39 = {
    "0": "nnnwwnwnn", "1": "wnnwnnnnw", "2": "nnwwnnnnw", "3": "wnwwnnnnn",
    "4": "nnnwwnnnw", "5": "wnnwwnnnn", "6": "nnwwwnnnn", "7": "nnnwnnwnw",
    "8": "wnnwnnwnn", "9": "nnwwnnwnn", "A": "wnnnnwnnw", "B": "nnwnnwnnw",
    "C": "wnwnnwnnn", "D": "nnnnwwnnw", "E": "wnnnwwnnn", "F": "nnwnwwnnn",
    "G": "nnnnnwwnw", "H": "wnnnnwwnn", "I": "nnwnnwwnn", "J": "nnnnwwwnn",
    "K": "wnnnnnnww", "L": "nnwnnnnww", "M": "wnwnnnnwn", "N": "nnnnwnnww",
    "O": "wnnnwnnwn", "P": "nnwnwnnwn", "Q": "nnnnnnwww", "R": "wnnnnnwwn",
    "S": "nnwnnnwwn", "T": "nnnnwnwwn", "U": "wwnnnnnnw", "V": "nwwnnnnnw",
    "W": "wwwnnnnnn", "X": "nwnnwnnnw", "Y": "wwnnwnnnn", "Z": "nwwnwnnnn",
    "-": "nwnnnnwnw", ".": "wwnnnnwnn", " ": "nwwnnnwnn", "*": "nwnnwnwnn",
    "$": "nwnwnwnnn", "/": "nwnwnnnwn", "+": "nwnnnwnwn", "%": "nnnwnwnwn",
}


def barcode_title(title: str) -> str:
    """The chart's title as i1Profiler writes it into the barcode: upper
    case, and ``_`` and every character Code 39 lacks as ``*`` (V16:
    "V16_isisXL_A3_bc_tight" became "V16*ISISXL*A3*BC*TIGHT")."""
    return "".join(c if (c in CODE39 and c != "*") else "*"
                   for c in str(title or "").upper())


def barcode_text(grid: Grid, page: int, title: str,
                 pw: float = 6.0, ph: float = 6.0) -> str:
    """The barcode's content for *page* (1-based): ``RRCCXXYY`` (two hex
    digits each: rows, columns, (patch width - 6) / 0.25, (patch height -
    6) / 0.25), the page number, a space, the title, ``*`` and the checksum,
    the DECIMAL sum of the ASCII codes of everything before it, that ``*``
    included (all three of i1Profiler's barcodes decoded: 1405, 1406, 2000)."""
    step = F.BARCODE_STEP_MM.value
    xx = int(round((pw - F.PATCH_MIN_MM.value) / step))
    yy = int(round((ph - F.PATCH_MIN_MM.value) / step))
    body = (f"{grid.R:02X}{grid.C:02X}{xx:02X}{yy:02X}{int(page)} "
            f"{barcode_title(title)}*")
    return body + str(sum(ord(c) for c in body))


def barcode_elements(text: str) -> int:
    """Elements (4 mm wide, every 5 mm) the text takes, two characters each."""
    return (len(text) + 1) // 2


def fitting_title(grid: Grid, sheet_w: float, title: str,
                  pw: float = 6.0, ph: float = 6.0) -> str:
    """The longest start of *title* whose barcode fits *sheet_w* (the grid's
    width) on the chart's longest page number."""
    t = str(title or "")
    while t:
        txt = barcode_text(grid, grid.P, t, pw, ph)
        if barcode_elements(txt) * F.BARCODE_PITCH_MM.value - 1.0 \
                <= sheet_w + 1e-6:
            return t
        t = t[:-1]
    return ""


def barcode_bars(text: str, x0: float, y0: float
                 ) -> "list[tuple[float, float, float, float]]":
    """The black bars (x, y, w, h) of *text* as i1Profiler draws it: two
    characters per element, the first one at the BOTTOM, each read bottom to
    top as narrow (0.5) and wide (1.0) modules across the element's 4 mm."""
    out = []
    elw = F.BARCODE_ELEMENT_MM.value
    char_h = F.BARCODE_CHAR_MM.value
    gap = F.BARCODE_CHAR_GAP_MM.value
    narrow, wide = F.BARCODE_NARROW_MM.value, F.BARCODE_WIDE_MM.value
    total = F.BARCODE_HEIGHT_MM.value
    for i, ch in enumerate(text):
        el, second = divmod(i, 2)
        x = x0 + el * F.BARCODE_PITCH_MM.value
        # the first character of an element sits at its bottom
        bottom = y0 + total - (char_h + gap) * second
        y = bottom
        for k, mod in enumerate(CODE39.get(ch, CODE39["*"])):
            size = wide if mod == "w" else narrow
            if k % 2 == 0:          # a bar
                out.append((x, y - size, elw, size))
            y -= size
    return out


# ---------------------------------------------------------------------------
# labels
# ---------------------------------------------------------------------------

def cell_name(sheet: Sheet, page: int, col: int, row: int,
              patterns: "tuple | None" = None) -> str:
    """The chart's own name of a cell (the ``.ti2``'s SAMPLE_LOC rule), so
    the sheet, the chart file and i1Profiler's SampleName agree."""
    from workflow.layout_engine import permutation
    g = sheet.grid
    slot = page * g.C * g.R + col * g.R + row
    sp, pp, rule = patterns or (permutation.DEFAULT_STRIP_PATTERN,
                                permutation.DEFAULT_PATCH_PATTERN,
                                permutation.ARGYLL)
    return permutation.location_label(slot, g.R, sp, pp, rule)


def _patterns(patterns: "tuple | None"):
    from workflow.layout_engine import permutation
    return patterns or (permutation.DEFAULT_STRIP_PATTERN,
                        permutation.DEFAULT_PATCH_PATTERN, permutation.ARGYLL)


def strip_name(sheet: Sheet, page: int, col: int,
               patterns: "tuple | None" = None) -> str:
    """The column's own letters (the strip half of its cells' names); the
    columns continue over the pages."""
    from workflow.layout_engine import permutation
    sp, _pp, rule = _patterns(patterns)
    return permutation.make_labeller(sp, rule)(
        page * sheet.grid.C + col + 1)


def row_name(row: int, patterns: "tuple | None" = None) -> str:
    """The row's own label (the patch half of its cells' names)."""
    from workflow.layout_engine import permutation
    _sp, pp, rule = _patterns(patterns)
    return permutation.make_labeller(pp, rule)(row + 1)


# ---------------------------------------------------------------------------
# what is drawn, and where (planned in mm, so it can be checked)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Item:
    """One drawn element: ``kind`` ("rect", "diamond", "arrow", "dash",
    "text", "band"), its box (x, y, w, h) in mm on the page, and for text
    its string, size (cap height, mm) and anchor ("centre", "left",
    "right")."""
    kind: str
    box: tuple
    text: str = ""
    size: float = 0.0
    anchor: str = "centre"
    role: str = ""
    family: str = "Inter"
    bold: bool = False
    italic: bool = False
    rotation: int = 0
    rgb: tuple = (0, 0, 0)
    #: (x, baseline) in mm: a text run with a pen is set on that baseline
    #: from that left edge; the wordmark's pen is where the engine's routine
    #: starts "Chrom"
    pen: tuple = ()


def _text_box(x: float, y_top: float, size: float, text: str,
              anchor: str = "centre") -> tuple:
    """A conservative box for a text run: 0.62 em per character."""
    w = max(size, 0.62 * size * 1.45 * max(1, len(text)))
    if anchor == "left":
        return (x, y_top, w, size)
    if anchor == "right":
        return (x - w, y_top, w, size)
    return (x - w / 2.0, y_top, w, size)


def page_line(name: str, page: int, pages: int, sheet_text: str = "") -> str:
    """The name and page line (i1Profiler: the name, then the page). The
    ChromIQ wordmark follows it, drawn by the engine's own routine
    (`wordmark_metrics`), never as text."""
    parts = [str(name or "").strip(), f"page {page}/{pages}"]
    if sheet_text and sheet_text.strip():
        parts.append(sheet_text.strip())
    return "  ·  ".join(p for p in parts if p)


#: THE ChromIQ WORDMARK on the name line is the one every other chart
#: carries: `raster._draw_wordmark_h` draws it (Instrument Serif "Chrom",
#: the magenta italic "IQ" on the same baseline after "Chrom"'s advance and
#: a kern of 0.02 of the size) in a band this many times the name line's
#: cap height: "Chrom"'s capital C then stands as tall as the line's
#: capitals (measured: the routine's C is 0.47 of its band).
WORDMARK_BAND_PER_CAP = 2.15
#: The smallest band it is drawn in, when the line is short of room (the
#: text is shortened first).
WORDMARK_BAND_MIN_MM = 3.0
#: Paper between the name line's text and the wordmark.
WORDMARK_GAP_MM = 3.0
#: The resolution the plan measures text and wordmark at (mm come out).
_MEASURE_DPI = 1200


_WM_CACHE: dict = {}


def wordmark_tile(band_px: float):
    """The wordmark as `raster._draw_wordmark_h` draws it for a band of
    *band_px*: ``(RGB tile cropped to its ink, pen x in the tile, baseline
    y in the tile, width the routine consumed)``, all in px. Drawn on white
    paper exactly as the clip border's branding is (a transparent canvas
    would thin the anti-aliased edges twice over)."""
    key = round(float(band_px), 3)
    hit = _WM_CACHE.get(key)
    if hit is not None:
        return hit
    from PIL import Image, ImageChops, ImageDraw
    from workflow.layout_engine import raster
    h = float(band_px)
    x = int(round(h * 0.5))
    size = (int(h * 8) + 2 * x, int(h * 3))
    canvas = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    used = raster._draw_wordmark_h(canvas, draw, x, h, h, max_w=1e9)
    base = raster.wordmark_h_baseline(h, h)
    box = ImageChops.difference(
        canvas, Image.new("RGB", size, (255, 255, 255))).getbbox() \
        or (0, 0, 1, 1)
    out = (canvas.crop(box), x - box[0], base - box[1], used)
    if len(_WM_CACHE) > 64:
        _WM_CACHE.clear()
    _WM_CACHE[key] = out
    return out


def wordmark_metrics(band_mm: float) -> dict:
    """The wordmark in mm, measured from the routine's own drawing: its
    ``width`` (pen to the end of "IQ"'s ink, as the routine counts it) and
    its ink box from the pen and the baseline (``left``, ``up`` above the
    baseline, ``right``, ``down`` below it, for the italic Q's tail)."""
    s = _MEASURE_DPI / 25.4
    tile, pen_x, base_y, used = wordmark_tile(band_mm * s)
    return {"width": used / s, "left": -pen_x / s,
            "up": base_y / s, "right": (tile.width - pen_x) / s,
            "down": (tile.height - base_y) / s}


def text_ink_mm(text: str, size: float, bold: bool = False,
                family: str = "Inter", italic: bool = False) -> tuple:
    """The ink of *text* at cap height *size*, from its pen on the
    baseline, in mm: ``(left, up, right, down)`` (``up`` above the baseline,
    ``down`` below it). Accents, descenders and other scripts' glyphs reach
    beyond the cap height, so a box from the cap height alone is not where
    the ink is."""
    s = _MEASURE_DPI / 25.4
    font = _font(max(6, int(round(size / 0.73 * s))), bold=bold,
                 family=family, italic=italic)[0]
    if not text:
        return (0.0, 0.0, 0.0, 0.0)
    l, t, r, b = font.getbbox(text, anchor="ls")
    return (l / s, -t / s, r / s, b / s)


def text_width_mm(text: str, size: float, bold: bool = False,
                  family: str = "Inter") -> float:
    """The real advance of *text* at cap height *size* (mm), as `draw_page`
    sets it."""
    from PIL import Image, ImageDraw
    s = _MEASURE_DPI / 25.4
    font = _font(max(6, int(round(size / 0.73 * s))), bold=bold,
                 family=family)[0]
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    return d.textlength(text, font=font) / s


def plan_page(sheet: Sheet, page: int, *, name: str = "",
              sheet_text: str = "", patterns: "tuple | None" = None,
              title: str = "", stamp_text: str = "",
              band_shows: "frozenset | set" = frozenset()
              ) -> "tuple[list[Item], list[str]]":
    """Everything drawn on *page* (0-based) besides the patches, and the
    reasons a label was left off (M-ISIS-KEEP-OUT). Pure: no pixels.

    *band_shows* names what the notes band on this page already prints
    legibly ("wordmark", "name", "page", `band_shows`): the name line leaves
    those out rather than print them twice."""
    o, g = sheet.opts, sheet.grid
    items: "list[Item]" = []
    left_off: "list[str]" = []
    # the bar, across every column of a full page (R§11)
    items.append(Item("rect", sheet.bar, role="bar"))
    # a diamond pair on every row
    for box in sheet.diamonds():
        items.append(Item("diamond", box, role="diamond"))
    # the barcode
    if o.barcode:
        txt = barcode_text(g, page + 1, fitting_title(
            g, sheet.grid_w, title, o.pw, o.ph), o.pw, o.ph)
        for b in barcode_bars(txt, sheet.grid_x, sheet.barcode_y):
            items.append(Item("rect", b, role="barcode"))
    # the feed arrows, in the diamond columns, pointing to the leading edge
    if o.arrows:
        a0, a1 = F.ARROW_Y_MM.value
        for x in (sheet.left_diamond_x, sheet.right_diamond_x):
            items.append(Item("arrow", (x, sheet.y0 + a0,
                                        F.DIAMOND_W_MM.value, a1 - a0),
                              role="arrow"))
    # the dashed outline
    if o.outline:
        items.append(Item("dash", (sheet.x0, sheet.y0, sheet.width,
                                   sheet.height), role="outline"))
    # the name and page line and the wordmark, in the text band (Z1),
    # never touching the corner labels (`_plan_name_line`)
    letters_top = o.strip_letters == "top"
    cl_size = 2.2
    items_n, off = _plan_name_line(sheet, page, name, sheet_text, patterns,
                                   band_shows)
    items += items_n
    left_off += off
    # corner labels: the first and last column and row of THIS page, the
    # columns continuing over the pages (R§3)
    if o.corner_labels:
        lx, rx = sheet.grid_x, sheet.grid_x + sheet.grid_w
        ty = sheet.y0 + F.CORNER_LABEL_TOP_MM.value[0]
        # inside the last 3.5 mm, clear of the dashed outline's 0.5 mm
        by = sheet.y0 + sheet.height - F.TRAILER_TEXT_MM.value + 0.3
        corners = [((lx, "left", 0), (ty, 0)), ((lx, "left", 0), (by, g.R - 1))]
        if _right_corner_drawn(sheet, page, patterns):
            corners += [((rx, "right", g.C - 1), (ty, 0)),
                        ((rx, "right", g.C - 1), (by, g.R - 1))]
        for (x, anchor, col), (y, row) in corners:
            t = cell_name(sheet, page, col, row, patterns)
            tw_ = text_width_mm(t, cl_size)
            items.append(Item("text", (x if anchor == "left" else x - tw_, y,
                                       tw_, cl_size),
                              text=t, size=cl_size, anchor=anchor,
                              role="corner"))
    # strip letters, one per column, in Z1 or Z8 only, in the engine's own
    # label style (face, size, bold, italic, rotation, alignment, offsets,
    # underline), held inside their zone (clamped, or left off and said)
    if o.strip_letters in ("top", "bottom"):
        if o.strip_letters == "top":
            z0, z1 = sheet.y0 + LETTER_ZONE_TOP_MM[0], \
                sheet.y0 + LETTER_ZONE_TOP_MM[1]
        else:
            z1 = sheet.y0 + sheet.height - F.TRAILER_TEXT_MM.value - 0.25
            z0 = z1 - TRAILER_LINE_MM + 0.5
        items_l, off = _plan_letters(sheet, page, patterns, z0, z1)
        items += items_l
        left_off += off
    # row numbers right of the right diamonds, 3 mm clear, in the same style
    if o.row_numbers:
        items_n, off = _plan_numbers(sheet, patterns)
        items += items_n
        left_off += off
    # the layout summary and the run's chart notes, one line each, in the
    # trailer's text room above the bottom corner labels (and above the
    # bottom strip letters); the trailer grew to hold them
    lines = list(o.trailer_lines) + ([stamp_text] if o.stamp and stamp_text
                                     else [])
    base = (sheet.y0 + sheet.height - F.TRAILER_TEXT_MM.value
            - (TRAILER_LINE_MM if o.strip_letters == "bottom" else 0.0))
    for i, line in enumerate(reversed(lines)):
        y = base - TRAILER_LINE_MM * (i + 1) + 0.75
        size = 2.4
        while size > 1.2 and _text_box(0, 0, size, line)[2] > sheet.grid_w:
            size -= 0.1
        if _text_box(0, 0, size, line)[2] > sheet.grid_w:
            # too long even small: shortened, never past the chart
            while len(line) > 4 and \
                    _text_box(0, 0, size, line + "…")[2] > sheet.grid_w:
                line = line[:-1]
            line = line.rstrip() + "…"
            if "trailer_text" not in left_off:
                left_off.append("trailer_text")
        role = "stamp" if (o.stamp and stamp_text and i == 0) else "notes"
        items.append(Item("text", _text_box(sheet.x0 + sheet.width / 2.0, y,
                                            size, line),
                          text=line, size=size, role=role))
    for band in (sheet.header_band(), sheet.trailer_band()):
        if band is not None:
            items.append(Item("band", band, role="notes_band"))
    return items, left_off


#: THE NAME LINE (the text band's first 12 mm). Its type is measured, never
#: estimated, and it keeps NAME_GAP_MM of paper to each top corner label.
NAME_GAP_MM = 1.5
#: The smallest cap height the name line is set at (legible on paper).
NAME_MIN_MM = 1.8
#: The fewest characters a shortened chart name keeps (with "…" inside).
NAME_MIN_CHARS = 8
#: Where the second line starts when the line moves under the corner labels.
NAME_LINE2_TOP_MM = 7.0
NAME_LINE2_MAX_MM = 3.0


def mid_ellipsis(text: str, keep: int) -> str:
    """*text* shortened to *keep* characters with "…" in the middle (the
    start and the end of a chart name are what tell charts apart)."""
    text = str(text or "")
    if len(text) <= keep:
        return text
    keep = max(2, keep)
    a = (keep - 1 + 1) // 2
    b = keep - 1 - a
    return text[:a] + "…" + (text[-b:] if b > 0 else "")


def _right_corner_drawn(sheet: "Sheet", page: int, patterns) -> bool:
    """Whether the right-hand corner labels are drawn: not on a one-column
    chart (they would name the same cell on top of the left ones), and not
    where the two labels of a row would come closer than NAME_GAP_MM (a
    two-column chart of small patches); the left ones always are."""
    g = sheet.grid
    if g.C < 2:
        return False
    cl = 2.2
    widths = [text_width_mm(cell_name(sheet, page, c, r, patterns), cl)
              for c in (0, g.C - 1) for r in (0, g.R - 1)]
    left = max(widths[0], widths[1])
    right = max(widths[2], widths[3])
    return left + right + NAME_GAP_MM <= sheet.grid_w + 1e-9


def _plan_name_line(sheet: "Sheet", page: int, name: str, sheet_text: str,
                    patterns, band_shows=frozenset()
                    ) -> "tuple[list[Item], list[str]]":
    """The chart's name, the page and the ChromIQ wordmark in the text band.

    One line between the top corner labels, at the full size; when it does
    not fit: the sheet text goes, then the chart name is shortened with "…"
    in its middle (the full name is in the chart's files), then the line is
    set smaller, down to NAME_MIN_MM. Still too wide, and with the strip
    letters elsewhere: two lines, the wordmark between the corner labels and
    the name and page under them, between the feed arrows. Last, the least
    needed element is left off and said: the wordmark, then on a one-page
    chart the page, then the name; never the page of a multi-page chart,
    never the corner labels.

    NOTHING TWICE (the owner, 2026-11-15: *"when the clipborder is turned
    on the information included in it don't need to double on the
    chart"*): what the notes band on this page prints legibly
    (*band_shows*) is left out here; with nothing left (no sheet text
    either) the line is not drawn at all. Nothing else moves: the line
    only ever sat in the text band's free paper."""
    o, g = sheet.opts, sheet.grid
    items: "list[Item]" = []
    left_off: "list[str]" = []
    want_wm = "wordmark" not in band_shows
    if (not want_wm and "name" in band_shows and "page" in band_shows
            and not (sheet_text and sheet_text.strip())):
        return items, left_off
    letters_top = o.strip_letters == "top"
    cl_size = 2.2
    if letters_top:
        line_top, line_h = sheet.y0 + 1.25, 3.0
    else:
        line_top, line_h = sheet.y0 + F.NAME_LINE_TOP_MM.value, 3.5
    cx = sheet.x0 + sheet.width / 2.0
    # the room between the top corner labels (or the diamond columns)
    lo = sheet.x0 + o.d1 + F.DIAMOND_W_MM.value + NAME_GAP_MM
    hi = sheet.x0 + sheet.width - o.d1 - F.DIAMOND_W_MM.value - NAME_GAP_MM
    lo2, hi2 = lo, hi
    if o.corner_labels:
        tl = cell_name(sheet, page, 0, 0, patterns)
        lo = max(lo, sheet.grid_x + text_width_mm(tl, cl_size) + NAME_GAP_MM)
        if _right_corner_drawn(sheet, page, patterns):
            tr_ = cell_name(sheet, page, g.C - 1, 0, patterns)
            hi = min(hi, sheet.grid_x + sheet.grid_w
                     - text_width_mm(tr_, cl_size) - NAME_GAP_MM)
    # centred on the chart, so the room is twice the nearer side
    room1 = max(0.0, 2.0 * min(cx - lo, hi - cx))
    room2 = max(0.0, 2.0 * min(cx - lo2, hi2 - cx))
    page_txt = "" if "page" in band_shows else f"page {page + 1}/{g.P}"
    full = "" if "name" in band_shows else str(name or "").strip()

    def band_for(sz: float) -> float:
        return round(sz * WORDMARK_BAND_PER_CAP, 2) if want_wm else 0.0

    def wm_width(b: float) -> float:
        return wordmark_metrics(b)["width"] if b else 0.0

    def tw(t: str, sz: float) -> float:
        # the advance or the ink, whichever reaches further
        if not t:
            return 0.0
        il, _u, ir, _d = text_ink_mm(t, sz, bold=True)
        return max(text_width_mm(t, sz, bold=True), ir) - min(0.0, il)

    def ink(t: str, sz: float) -> "tuple[float, float, float]":
        """(left of the pen, up, down) of the line's real ink."""
        il, iu, _ir, idn = text_ink_mm(t, sz, bold=True)
        return min(0.0, il), max(iu, sz), max(idn, 0.0)

    def line(nm: str, with_page: bool, extra: str = "") -> str:
        parts = [nm, page_txt if with_page else "", extra]
        return "  ·  ".join(p for p in parts if p)

    def fit_name(sz: float, room: float, with_page: bool, wm_w: float,
                 extra: str = "") -> "str | None":
        """The name (whole, or shortened in its middle) that fits *room*
        at *sz* beside the page and the wordmark; None when none does."""
        gap = WORDMARK_GAP_MM if wm_w > 0 else 0.0
        if tw(line(full, with_page, extra), sz) + gap + wm_w <= room:
            return full
        if not full or extra:
            return None
        lo_k, hi_k, best = NAME_MIN_CHARS, len(full) - 1, None
        while lo_k <= hi_k:
            k = (lo_k + hi_k) // 2
            if tw(line(mid_ellipsis(full, k), with_page), sz) + gap \
                    + wm_w <= room:
                best, lo_k = mid_ellipsis(full, k), k + 1
            else:
                hi_k = k - 1
        return best

    sizes = []
    v = line_h
    while v >= NAME_MIN_MM - 1e-9:
        sizes.append(round(v, 2))
        v -= 0.1

    plan = None             # (mode, size, text, wordmark band or 0)
    # 1. one line: the sheet text too, at the full size only
    if sheet_text and sheet_text.strip():
        b = band_for(line_h)
        if fit_name(line_h, room1, True, wm_width(b),
                    sheet_text.strip()) is not None:
            plan = ("one", line_h, line(full, True, sheet_text.strip()), b)
    # 2. one line: the name shortened, then smaller
    if plan is None:
        for sz in sizes:
            b = band_for(sz)
            nm = fit_name(sz, room1, True, wm_width(b))
            if nm is not None:
                plan = ("one", sz, line(nm, True), b)
                break
    # 3. two lines (the strip letters' zone must be free): the wordmark
    #    between the corner labels, the name and page under them
    if plan is None and not letters_top:
        b1 = None
        for sz in sizes:
            if want_wm and wm_width(band_for(sz)) <= room1:
                b1 = band_for(sz)
                break
        for sz in [x for x in sizes if x <= NAME_LINE2_MAX_MM + 1e-9]:
            nm = fit_name(sz, room2, True, 0.0)
            if nm is not None:
                plan = ("two", sz, line(nm, True), b1 or 0.0)
                if b1 is None and want_wm:
                    left_off.append("name_wordmark")
                break
    # 4. the least needed left off: the wordmark, then on a one-page chart
    #    the page, then the name; each tried between the corner labels and,
    #    with the strip letters elsewhere, under them (a 1- or 2-column
    #    chart has almost no room between its corner labels)
    if plan is None:
        sz = NAME_MIN_MM
        if want_wm:
            left_off.append("name_wordmark")
        places = [("one", room1)] + ([("two", room2)] if not letters_top
                                     else [])
        tries = [((lambda r: fit_name(sz, r, True, 0.0)), True, [])]
        if g.P == 1:
            tries.append(((lambda r: fit_name(sz, r, False, 0.0)), False,
                          ["name_page"]))
        for find, with_page, extra in tries:
            for mode_, room in places:
                nm = find(room)
                if nm is not None:
                    plan = (mode_, sz, line(nm, with_page), 0.0)
                    left_off += extra
                    break
            if plan is not None:
                break
        if plan is None:
            if full:
                left_off.append("name_text")
            mode_, room = places[-1]
            t = page_txt if (not page_txt or tw(page_txt, sz) <= room) \
                else f"{page + 1}/{g.P}"
            # the page alone, set smaller still until it fits (never off
            # a multi-page chart)
            while sz > 1.0 + 1e-9 and tw(t, sz) > room:
                sz = round(sz - 0.1, 2)
            plan = (mode_, sz, t, 0.0)

    mode, size, text, band = plan
    ink_top = sheet.y0 + F.OUTLINE_LINE_MM.value + 0.75
    zone_bottom = (sheet.y0 + LETTER_ZONE_TOP_MM[0] - 0.25 if letters_top
                   else sheet.bar_y - F.CLEAR_ABOVE_BAR_MM.value - 0.25)

    def place_wordmark(band_mm: float, x_pen: float, baseline: float):
        wm = wordmark_metrics(band_mm)
        items.append(Item("wordmark",
                          (x_pen + wm["left"], baseline - wm["up"],
                           wm["right"] - wm["left"], wm["up"] + wm["down"]),
                          text="ChromIQ", size=band_mm, role="wordmark",
                          pen=(x_pen, baseline)))

    if mode == "one":
        wm = wordmark_metrics(band) if band else None
        ink_bottom = zone_bottom
        while wm is not None:
            baseline = max(line_top + size, ink_top + wm["up"])
            if (baseline + wm["down"] <= ink_bottom + 1e-9
                    or band <= WORDMARK_BAND_MIN_MM + 1e-9):
                break
            band = round(band - 0.25, 3)
            wm = wordmark_metrics(band)
        il, iu, idn = ink(text, size) if text else (0.0, size, 0.0)
        baseline = max(line_top + size, ink_top + iu,
                       ink_top + (wm["up"] if wm else 0.0))
        w_text = tw(text, size)
        gap_wm = WORDMARK_GAP_MM if (wm and text) else 0.0
        w_all = w_text + ((gap_wm + wm["width"]) if wm else 0.0)
        gx = cx - w_all / 2.0
        if text:
            items.append(Item("text", (gx, baseline - iu, w_text, iu + idn),
                              text=text, size=size, anchor="left",
                              role="name_line", pen=(gx - il, baseline)))
        if wm is not None:
            place_wordmark(band, gx + w_text + gap_wm, baseline)
    else:
        # line 1: the wordmark alone, its ink inside the corner labels' rows
        top2 = sheet.y0 + NAME_LINE2_TOP_MM
        wm_bottom = ink_top
        if band:
            wm = wordmark_metrics(band)
            while band > WORDMARK_BAND_MIN_MM + 1e-9 and \
                    ink_top + wm["up"] + wm["down"] > top2 - 0.5:
                band = round(band - 0.25, 3)
                wm = wordmark_metrics(band)
            place_wordmark(band, cx - wm["width"] / 2.0,
                           ink_top + wm["up"])
            wm_bottom = ink_top + wm["up"] + wm["down"]
        # line 2: the name and the page, under the corner labels and the
        # wordmark (its accents and tall glyphs too), between the arrows
        if not text:
            return items, left_off
        il, iu, idn = ink(text, size)
        baseline = max(top2 + size, wm_bottom + 0.5 + iu)
        w_text = tw(text, size)
        gx = cx - w_text / 2.0
        items.append(Item("text", (gx, baseline - iu, w_text, iu + idn),
                          text=text, size=size, anchor="left",
                          role="name_line", pen=(gx - il, baseline)))
    return items, left_off


#: The smallest label ChromIQ prints on an i1iSis chart (cap height, mm):
#: below it a label is left off and the log says so (M-ISIS-KEEP-OUT).
LABEL_MIN_MM = 1.5
#: Where the top strip letters may go inside the text band (Z1), from the
#: chart's leading edge: below the name line, above the band's end.
LETTER_ZONE_TOP_MM = (6.75, 11.75)
#: The colours "Coloured (per strip)" underlines cycle through.
UNDERLINE_CYCLE = ((230, 25, 75), (60, 180, 75), (0, 130, 200),
                   (245, 130, 48), (145, 30, 180), (70, 70, 70))


def _label_box(cx: float, cy: float, size: float, text: str,
               rotation: int, family: str = "JetBrains Mono",
               bold: bool = False, italic: bool = False) -> tuple:
    """The box of a label of cap height *size* centred on (cx, cy), turned
    by *rotation* (90 / 270 run along y): its real ink, measured in its
    own face, with 0.1 mm to spare on each side."""
    il, _iu, ir, _id = text_ink_mm(text, size, bold, family or "Inter",
                                   italic)
    w = max(ir - il, 0.0) + 0.2
    h = size + 0.2
    if rotation in (90, 270):
        w, h = h, w
    return (cx - w / 2.0, cy - h / 2.0, w, h)


def _plan_letters(sheet: Sheet, page: int, patterns, z0: float, z1: float):
    o, g = sheet.opts, sheet.grid
    items, off = [], []
    room_h = z1 - z0
    ul = o.underline not in ("off", "", None)
    ul_room = (o.underline_gap + o.underline_mm) if ul else 0.0
    size = o.letter_size or min(3.0, max(1.2, o.pw * 0.5))
    texts = [strip_name(sheet, page, c, patterns) for c in range(g.C)]

    def fits(sz):
        for t in texts:
            x, y, w, h = _label_box(0, 0, sz, t, o.letter_rotation,
                                     o.letter_font, o.letter_bold,
                                     o.letter_italic)
            if w > o.pw + 1e-6 or h + ul_room > room_h + 1e-6:
                return False
        return True
    while size > LABEL_MIN_MM and not fits(size):
        size -= 0.1
    if not fits(size):
        return [], ["strip_letters"]
    for c, t in enumerate(texts):
        x, y, w, h = _label_box(0, 0, size, t, o.letter_rotation,
                                 o.letter_font, o.letter_bold,
                                 o.letter_italic)
        col0 = sheet.grid_x + c * o.pw
        if o.letter_align == "left":
            lx = col0
        elif o.letter_align == "right":
            lx = col0 + o.pw - w
        else:
            lx = col0 + (o.pw - w) / 2.0
        # the offsets move the letters, held inside their column and zone
        lx = min(max(lx + o.label_offset_x, col0), col0 + o.pw - w)
        ly = z0 + (room_h - h - ul_room) / 2.0 + o.label_offset_y
        ly = min(max(ly, z0), z1 - h - ul_room)
        items.append(Item("text", (lx, ly, w, h), text=t, size=size,
                          role="strip_letter", family=o.letter_font,
                          bold=o.letter_bold, italic=o.letter_italic,
                          rotation=o.letter_rotation))
        if ul:
            rgb = (UNDERLINE_CYCLE[(page * g.C + c) % len(UNDERLINE_CYCLE)]
                   if o.underline == "cycle" else (0, 0, 0))
            uw = o.pw if o.underline == "segments" else w
            ux = col0 if o.underline == "segments" else lx
            items.append(Item("rect", (ux, ly + h + o.underline_gap, uw,
                                       o.underline_mm), role="underline",
                              rgb=rgb))
    return items, off


def _plan_numbers(sheet: Sheet, patterns):
    o, g = sheet.opts, sheet.grid
    x0 = sheet.right_marker_edge + F.DIAMOND_CLEAR_MM.value \
        + max(0.0, o.label_offset_x)
    # INSIDE THE OUTLINE'S OWN LINE, which `sheet_for` leaves room for (the
    # 0.5 in its "need"): measured on screen 2026-11-15, numbers set against
    # the outline's outer edge printed "10" to "35" across the dashes
    limit = sheet.x0 + sheet.width - F.OUTLINE_LINE_MM.value
    texts = [row_name(r, patterns) for r in range(g.R)]
    size = o.letter_size or min(3.0, max(1.2, o.ph * 0.5))

    def fits(sz):
        for t in texts:
            _x, _y, w, h = _label_box(0, 0, sz, t, o.number_rotation,
                                        o.letter_font, o.letter_bold,
                                        o.letter_italic)
            if h > o.ph + 1e-6 or x0 + w > limit + 1e-6:
                return False
        return True
    while size > LABEL_MIN_MM and not fits(size):
        size -= 0.1
    if not fits(size):
        return [], ["row_numbers"]
    items = []
    for r, t in enumerate(texts):
        _x, _y, w, h = _label_box(0, 0, size, t, o.number_rotation,
                                        o.letter_font, o.letter_bold,
                                        o.letter_italic)
        items.append(Item("text", (x0, sheet.row_centre(r) - h / 2.0, w, h),
                          text=t, size=size, anchor="left",
                          role="row_number", family=o.letter_font,
                          bold=o.letter_bold, italic=o.letter_italic,
                          rotation=o.number_rotation))
    return items, []


def _intersects(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax < bx + bw - 1e-6 and bx < ax + aw - 1e-6
            and ay < by + bh - 1e-6 and by < ay + ah - 1e-6)


#: Which drawn roles may sit inside which keep-out zone (the instrument's
#: own marks only).
ALLOWED_IN = {
    "bar": {"bar"},
    "under_bar": {"barcode"},
    "grid": set(),
    "diamond": {"diamond"},
    "above_bar": {"arrow", "outline"},
    "trailer_inner": {"outline", "diamond"},
}


def keep_out_violations(sheet: Sheet, items: "list[Item]") -> "list[str]":
    """Every drawn element that enters a zone it may not (empty = clean).
    The outline sits on the chart's edge and crosses every zone's end: it
    is checked as its four edges, each a 0.5 mm line."""
    bad = []
    zones = sheet.keep_out()
    for it in items:
        boxes = [it.box]
        if it.kind == "dash":
            x, y, w, h = it.box
            t = F.OUTLINE_LINE_MM.value
            boxes = [(x, y, w, t), (x, y + h - t, w, t), (x, y, t, h),
                     (x + w - t, y, t, h)]
        for name, zone in zones:
            if it.role in ALLOWED_IN.get(name, set()):
                continue
            if name == "diamond" and it.role == "diamond":
                continue
            for b in boxes:
                if _intersects(b, zone):
                    # the outline's side edges run beside every zone; the
                    # zones span the chart's full width only where X-Rite
                    # asks for clear paper across it
                    if it.kind == "dash" and name in ("under_bar",
                                                       "above_bar",
                                                       "trailer_inner"):
                        continue
                    bad.append(f"{it.role} in {name}")
                    break
    return bad


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------

def _font(px: int, bold: bool = False, family: str = "Inter",
          italic: bool = False):
    from workflow.layout_engine import raster
    try:
        path, variation = raster._font_file_and_variation(family, bold,
                                                          italic)
        return (raster._font(px, family, bold=bold, italic=italic), path,
                variation)
    except Exception:  # noqa: BLE001 - an unknown face: the house face
        path, variation = raster._font_file_and_variation("Inter", bold,
                                                          False)
        return raster._font(px, "Inter", bold=bold, italic=False), path, \
            variation


def draw_page(img, page_geom: "list | None", sheet: Sheet, items, dpi: int,
              *, band_images: "dict | None" = None,
              ink_boxes: "list | None" = None) -> None:
    """Draw *items* (mm) onto one page image (PIL, RGB) and, when a display
    list is collected (PDF, separated TIFF), as vector rectangles and text
    runs. Diamonds and arrows are drawn as rows of thin rectangles, exact to
    the pixel, so the vector PDF needs no new shape."""
    from PIL import Image, ImageDraw
    s = dpi / 25.4
    draw = ImageDraw.Draw(img)
    black = (0, 0, 0)

    def px(mm: float) -> int:
        return int(round(mm * s))

    def rect(x0: int, y0: int, x1: int, y1: int, rgb=black) -> None:
        if x1 <= x0 or y1 <= y0:
            return
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=rgb)
        if page_geom is not None:
            page_geom.append(("vrect", (x0, y0, x1, y1), rgb))

    def rhombus(x: float, y: float, w: float, h: float,
                arrow: bool = False) -> None:
        """A diamond (or, *arrow*, an up-pointing arrow) in the box, row by
        row of pixels."""
        X0, Y0, X1, Y1 = px(x), px(y), px(x + w), px(y + h)
        H = max(1, Y1 - Y0)
        cx = (X0 + X1) / 2.0
        half = (X1 - X0) / 2.0
        if not arrow:
            for r in range(H):
                t = (r + 0.5) / H
                k = 1.0 - abs(2.0 * t - 1.0)
                a = int(round(cx - half * k))
                b = int(round(cx + half * k))
                rect(a, Y0 + r, b, Y0 + r + 1)
            return
        head = min(H, int(round(px(w) * 1.0)))
        shaft = max(1, int(round((X1 - X0) * 0.36)))
        for r in range(H):
            if r < head:
                k = (r + 0.5) / head
                a = int(round(cx - half * k))
                b = int(round(cx + half * k))
            else:
                a = int(round(cx - shaft / 2.0))
                b = a + shaft
            rect(a, Y0 + r, b, Y0 + r + 1)

    def dashed(x: float, y: float, w: float, h: float) -> None:
        t = F.OUTLINE_LINE_MM.value
        d = F.OUTLINE_DASH_MM.value

        def run(a: float, b: float, horiz: bool, at: float) -> None:
            pos = a
            while pos < b - 1e-9:
                e = min(b, pos + d)
                if horiz:
                    rect(px(pos), px(at), px(e), px(at + t))
                else:
                    rect(px(at), px(pos), px(at + t), px(e))
                pos += 2.0 * d
        run(x, x + w, True, y)
        run(x, x + w, True, y + h - t)
        run(y, y + h, False, x)
        run(y, y + h, False, x + w - t)

    def text(it: Item) -> None:
        size_px = max(6, int(round(it.size / 0.73 * s)))
        if it.rotation:
            return turned(it, size_px)
        font, path, var = _font(size_px, bold=(it.bold or
                                               it.role == "name_line"),
                                family=it.family, italic=it.italic)
        bb = draw.textbbox((0, 0), it.text, font=font)
        tw = bb[2] - bb[0]
        x, y, w, h = it.box
        if it.anchor == "left":
            left = px(x)
        elif it.anchor == "right":
            left = px(x + w) - tw
        else:
            left = px(x + w / 2.0) - tw // 2
        cap_top = px(y)
        # the cap height starts where the ink of a capital starts
        cbb = draw.textbbox((0, 0), "H", font=font)
        top = cap_top - cbb[1]
        if it.pen:
            # set on its baseline, the pixel row the wordmark beside it
            # sits on too
            top = int(round(it.pen[1] * s)) - font.getmetrics()[0]
        draw.text((left - bb[0], top), it.text, font=font, fill=it.rgb)
        if ink_boxes is not None:
            ink_boxes.append((it.role, draw.textbbox((left - bb[0], top),
                                                     it.text, font=font)))
        if page_geom is not None and path:
            ascent = font.getmetrics()[0]
            page_geom.append(("text", left - bb[0], top + ascent, it.text,
                              path, size_px, 0, 0, it.rgb, var))

    def turned(it: Item, size_px: int) -> None:
        """A label turned by 90, 180 or 270 degrees, centred in its box;
        carried into the PDF and the separated TIFF as artwork."""
        import numpy as np
        font, _path, _var = _font(size_px, bold=it.bold, family=it.family,
                                  italic=it.italic)
        bb = draw.textbbox((0, 0), it.text, font=font)
        tw, th = max(1, bb[2] - bb[0]), max(1, bb[3] - bb[1])
        tile = Image.new("L", (tw, th), 0)
        ImageDraw.Draw(tile).text((-bb[0], -bb[1]), it.text, font=font,
                                  fill=255)
        tile = tile.rotate(it.rotation, expand=True)
        x, y, w, h = it.box
        cx, cy = px(x + w / 2.0), px(y + h / 2.0)
        x0, y0 = cx - tile.width // 2, cy - tile.height // 2
        ink = Image.new("RGB", tile.size, it.rgb)
        img.paste(ink, (x0, y0), tile)
        if ink_boxes is not None:
            ib = tile.getbbox() or (0, 0, 0, 0)
            ink_boxes.append((it.role, (x0 + ib[0], y0 + ib[1],
                                        x0 + ib[2], y0 + ib[3])))
        if page_geom is not None:
            art = Image.new("RGB", tile.size, (255, 255, 255))
            art.paste(ink, (0, 0), tile)
            page_geom.append(("clip", (x0, y0), np.asarray(art)))

    def wordmark(it: Item) -> None:
        """The ChromIQ wordmark, drawn by the engine's own routine at this
        resolution and set with its pen and baseline on the item's; carried
        into the PDF and the separated TIFF as artwork, like the clip
        border's branding."""
        tile, pen_x, base_y, _used = wordmark_tile(it.size * s)
        x0 = int(round(it.pen[0] * s - pen_x))
        y0 = int(round(it.pen[1] * s)) - int(round(base_y))
        # its ink box holds nothing else (planned clear of the outline, the
        # name line and every zone), so the white tile lies on white paper
        img.paste(tile, (x0, y0))
        if ink_boxes is not None:
            ink_boxes.append((it.role, (x0, y0, x0 + tile.width,
                                        y0 + tile.height)))
        if page_geom is not None:
            import numpy as np
            page_geom.append(("clip", (x0, y0), np.asarray(tile)))

    for it in items:
        if it.kind == "rect":
            x, y, w, h = it.box
            rect(px(x), px(y), px(x + w), px(y + h), it.rgb)
        elif it.kind == "wordmark":
            wordmark(it)
        elif it.kind == "diamond":
            rhombus(*it.box)
        elif it.kind == "arrow":
            rhombus(*it.box, arrow=True)
        elif it.kind == "dash":
            dashed(*it.box)
        elif it.kind == "text":
            text(it)
        elif it.kind == "band" and band_images:
            band = band_images.get(it.box)
            if band is not None:
                x, y = px(it.box[0]), px(it.box[1])
                img.paste(band, (x, y))
                if page_geom is not None:
                    import numpy as np
                    page_geom.append(("clip", (x, y), np.asarray(band)))


def band_image(box, dpi: int, *, mode: str, text: str = "",
               font_family: str = "Inter", ctx: "dict | None" = None,
               text_size_mm: float = 0.0, image_path: str = "",
               image_rotation: int = 0, image_scale: float = 100.0,
               image_offset_x_mm: float = 0.0,
               image_offset_y_mm: float = 0.0, flip: bool = False):
    """The notes band's content, drawn by the engine's clip-content renderer
    on a strip as tall as the band is wide and turned upright, so it reads
    across the chart."""
    from workflow.layout_engine import raster
    s = dpi / 25.4
    w_px = max(1, int(round(box[2] * s)))
    h_px = max(1, int(round(box[3] * s)))
    strip = raster.render_clip_strip(
        mode if mode not in ("", "off", None) else "notes",
        width_px=h_px, height_px=w_px, dpi=dpi, text=text,
        font_family=font_family, ctx=ctx, image_path=image_path,
        image_rotation=image_rotation, image_scale=image_scale,
        image_offset_x_mm=image_offset_x_mm,
        image_offset_y_mm=image_offset_y_mm, text_size_mm=text_size_mm)
    img = strip.rotate(-90, expand=True)
    if flip:
        img = img.rotate(180)
    return img.convert("RGB").resize((w_px, h_px))


def band_numbers(sheet: Sheet, index: int, layout=None) -> dict:
    """The numbers the notes band prints on page *index*, from the FINAL
    layout, in the Create Chart panel's own terms.

    Up to 4.3.38 the band was given no patch count, so it printed the notes
    design's SAMPLE ("560 patches"), and it printed the ROWS (32 on A4
    portrait) as "strips on page", where the panel, the .ti2 and the strip
    letters on the sheet count the COLUMNS (28) as strips of 32 patches. The
    panel reads the .ti2 the engine writes from *layout* (NUMBER_OF_SETS,
    STEPS_IN_PASS, the passes on each page), so these are taken from it too.
    Without a layout the sheet's own grid gives the same values."""
    if layout is not None:
        total = int(layout.total_patches)
        steps = max(1, int(layout.steps_in_pass))
        per_page = max(1, int(layout.patches_per_page))
    else:
        total = int(sheet.grid.N)
        steps = max(1, int(sheet.grid.R))
        per_page = max(1, int(sheet.grid.C * sheet.grid.R))
    first = index * per_page
    on_page = max(0, min(total, first + per_page) - first)
    return {"count": str(total),
            "page": f"page {index + 1}/{sheet.grid.P}",
            "strips": str(-(-on_page // steps)),
            "per_strip": str(steps)}


#: The smallest cap height (mm) at which the notes band's own name and page
#: count as printed, so the name line may leave them out (LABEL_MIN_MM, the
#: chart's legibility floor). The default 24 mm band sets 1.69 mm; a band of
#: 16 mm or less sets 1.2 mm or smaller, and the name line keeps them.
BAND_TEXT_MIN_MM = 1.5


def band_shows(band: "dict | None", ctx: dict, box, dpi: int,
               name: str) -> frozenset:
    """What the notes band in *box* prints that the name line also would
    ("wordmark", "name", "page"), from its content:

    * the notes design: its wordmark always (it is the band's largest
      element); the chart's name and "page x/y" only when its text is set
      at BAND_TEXT_MIN_MM or more and its name is the name line's;
    * "branding": the wordmark, when it fills the band as it does by default
      (not shrunk, not moved);
    * plain text or an image: nothing (what they say is the person's own).
    """
    if not band:
        return frozenset()
    mode = str(band.get("mode") or "notes")
    if mode in ("", "off"):
        mode = "notes"
    if mode == "branding":
        scaled = float(band.get("image_scale") or 100.0) >= 100.0 - 1e-9
        moved = (abs(float(band.get("image_offset_x_mm") or 0.0)) > 1e-9
                 or abs(float(band.get("image_offset_y_mm") or 0.0)) > 1e-9)
        return frozenset({"wordmark"}) if scaled and not moved \
            else frozenset()
    if mode != "notes":
        return frozenset()
    out = {"wordmark"}
    from workflow.layout_engine import raster
    # MEASURED AT 300 dpi WHATEVER THE BUILD'S, so the same chart drops
    # the same things in a preview and in its print file (the design's
    # 8 px floor would make a low-dpi band's text look larger than it is)
    ref = 300
    s = ref / 25.4
    w_px = max(1, int(round(box[2] * s)))
    h_px = max(1, int(round(box[3] * s)))
    try:
        cap = raster.notes_text_cap_mm(h_px, w_px, ref, ctx,
                                       band.get("font_family") or "Inter")
    except Exception:  # noqa: BLE001 - not measured: keep the name line
        cap = 0.0
    if cap >= BAND_TEXT_MIN_MM - 1e-9:
        out.add("page")
        if str(ctx.get("project") or "").strip() == str(name or "").strip():
            out.add("name")
    return frozenset(out)


def draw_furniture(render, sheet: Sheet, dpi: int, *, name: str,
                   sheet_text: str = "", patterns: "tuple | None" = None,
                   title: str = "", stamp_text: str = "",
                   band: "dict | None" = None,
                   layout=None) -> "list[str]":
    """Draw the chart's furniture onto every page of *render* (in place) and
    return what was left off (`keep_out` reasons, for M-ISIS-KEEP-OUT).

    *layout* is the engine's final layout (the one its .ti2 and the Create
    Chart panel read); the notes band takes its numbers from it."""
    left_off: "list[str]" = []
    band_cache: dict = {}
    for index, img in enumerate(render.images):
        # THE BAND FIRST, so the name line knows what it already prints
        shows: frozenset = frozenset()
        images = {}
        for box in (sheet.header_band(), sheet.trailer_band()):
            if box is None:
                continue
            # one per page: it carries the page number
            key = (box, index)
            if key not in band_cache:
                ctx = dict((band or {}).get("ctx") or {})
                ctx.update(band_numbers(sheet, index, layout))
                ctx["instrument"] = device_name(sheet.opts.model)
                try:
                    img_b = band_image(
                        box, dpi, **{k: v for k, v in (band or {}).items()
                                     if k != "ctx"}, ctx=ctx)
                except Exception:  # noqa: BLE001 - a blank band
                    img_b = None
                band_cache[key] = (img_b, band_shows(
                    band, ctx, box, dpi, name) if img_b is not None
                    else frozenset())
            images[box], s_ = band_cache[key]
            shows = shows | s_
        items, off = plan_page(sheet, index, name=name, sheet_text=sheet_text,
                               patterns=patterns, title=title,
                               stamp_text=stamp_text, band_shows=shows)
        for why in off:
            if why not in left_off:
                left_off.append(why)
        geom_list = (render.patch_geom[index]
                     if getattr(render, "patch_geom", None) is not None
                     else None)
        draw_page(img, geom_list, sheet, items, dpi, band_images=images)
    return left_off


# ---------------------------------------------------------------------------
# the side file
# ---------------------------------------------------------------------------

def side_doc(sheet: Sheet, *, paper: str, name: str, title: str,
             patterns: "tuple | None" = None, designed: int = 0) -> dict:
    """The side file's content (PROPOSAL §8): page, margins, offsets,
    placement, every element in mm, the grid, the barcode text of every
    page, the model width and whether the sheet may be fed as printed."""
    o, g = sheet.opts, sheet.grid

    def r(v):
        return round(float(v), 4)

    pages = []
    for p in range(g.P):
        first = p * g.C * g.R
        pages.append({
            "page": p + 1,
            "first_slot": first,
            "patches": max(0, min(g.C * g.R, g.N - first)),
            "barcode": (barcode_text(g, p + 1, fitting_title(
                g, sheet.grid_w, title, o.pw, o.ph), o.pw, o.ph)
                if o.barcode else None),
            "corners": {
                "top_left": cell_name(sheet, p, 0, 0, patterns),
                "top_right": cell_name(sheet, p, g.C - 1, 0, patterns),
                "bottom_left": cell_name(sheet, p, 0, g.R - 1, patterns),
                "bottom_right": cell_name(sheet, p, g.C - 1, g.R - 1,
                                          patterns),
            },
        })
    return {
        "schema": SCHEMA,
        "what": "ChromIQ i1iSis chart: every element in mm on the page "
                "(x from the paper's left edge, y from its leading edge)",
        "name": name, "title": title,
        "model": o.model, "device": device_name(o.model),
        "paper": paper, "paper_mm": [r(sheet.paper_w), r(sheet.paper_h)],
        "margins_mm": {"top": r(o.margins[0]), "right": r(o.margins[1]),
                       "bottom": r(o.margins[2]), "left": r(o.margins[3])},
        "offset_mm": [r(o.offset[0]), r(o.offset[1])],
        "align": o.align,
        "patch_mm": [r(o.pw), r(o.ph)],
        "header_mm": r(o.header_mm), "trailer_mm": r(sheet.trailer),
        "tight_margins": o.tight, "barcode": o.barcode,
        "columns": g.C, "rows": g.R, "pages": g.P,
        "cmax": g.cmax, "rmax": g.rmax, "patches": g.N,
        "designed_patches": int(designed or g.N),
        "outline_mm": [r(sheet.x0), r(sheet.y0), r(sheet.width),
                       r(sheet.height)],
        "grid_mm": [r(sheet.grid_x), r(sheet.grid_y), r(sheet.grid_w),
                    r(sheet.grid_h)],
        "bar_mm": [r(v) for v in sheet.bar],
        "diamond_x_mm": [r(sheet.left_diamond_x), r(sheet.right_diamond_x)],
        "diamond_size_mm": [F.DIAMOND_W_MM.value, F.DIAMOND_H_MM.value],
        "right_marker_edge_mm": r(sheet.right_marker_edge),
        "fed_as_printed": sheet.fed_as_printed,
        "cut_reasons": list(sheet.cut_reasons),
        "notes_band": ({"place": o.notes_place,
                        "box_mm": [r(v) for v in (sheet.header_band()
                                                   or sheet.trailer_band()
                                                   or ())]}
                       if o.notes_band else None),
        "pages_detail": pages,
        # whether "Show row indicators" could be honoured (the panel's note,
        # M-ISIS-ROW-NUMBERS-NO-ROOM); absent while it is off
        **({"row_numbers": ("printed" if not _plan_numbers(sheet, patterns)[1]
                            else "left_off")} if o.row_numbers else {}),
    }


def write_side_file(path, sheet: Sheet, **kw) -> Path:
    path = Path(path)
    path.write_text(json.dumps(side_doc(sheet, **kw), indent=1),
                    encoding="utf-8")
    return path


def placement_order(ti2_path, grid: "Grid | dict", patterns=None
                    ) -> "list[str]":
    """The chart's patch names in placement order (slot 0, 1, ...: column
    by column, page by page), one per PRINTED cell."""
    from workflow.layout_engine import permutation
    if isinstance(grid, dict):
        C, R, P, N = (int(grid["columns"]), int(grid["rows"]),
                      int(grid["pages"]), int(grid["patches"]))
    else:
        C, R, P, N = grid.C, grid.R, grid.P, grid.N
    sp, pp, rule = patterns or (permutation.DEFAULT_STRIP_PATTERN,
                                permutation.DEFAULT_PATCH_PATTERN,
                                permutation.ARGYLL)
    return [permutation.location_label(s, R, sp, pp, rule)
            for s in range(min(N, C * R * P))]


def cut_instruction(fed_as_printed: bool) -> str:
    """{cut_or_not} of M-ISIS-NOT-YET and the Print tab note."""
    from core.i18n import tr
    if fed_as_printed:
        return tr("Feed the sheet as printed (cutting it along the dashed "
                  "outline also works).")
    return tr("Cut the sheet along the dashed outline before feeding it: "
              "printed on this sheet, the chart would not sit where the "
              "i1iSis looks for it.")


def keep_out_message(what: str) -> str:
    """M-ISIS-KEEP-OUT for a label left off."""
    from core.i18n import tr
    if what == "trailer_text":
        return tr("The chart notes are longer than the chart is wide, so "
                  "their end was left off in the trailer.")
    parts = {"name_wordmark": tr("the ChromIQ logo"),
             "name_page": tr("the page number"),
             "name_text": tr("the chart's name")}
    if what in parts:
        return tr("This chart is too narrow for its whole name line between "
                  "the corner labels, even with the name shortened and the "
                  "text set small, so {what} was left off the top of the "
                  "sheet. The chart's files keep its full name.").format(
                      what=parts[what])
    if what == "row_numbers":
        # left off for lack of room beside the chart, not for a marker
        # zone: what makes room is said (M-ISIS-ROW-NUMBERS-NO-ROOM, also
        # the note on the panel)
        from workflow.measurement_messages import \
            isis_row_numbers_no_room_text
        return isis_row_numbers_no_room_text()
    names = {"row_numbers": tr("The row numbers"),
             "strip_letters": tr("The strip letters")}
    return tr("{what} would print where the i1iSis looks for its markers, so "
              "they were left off. Room for text: the first 12 mm of the "
              "chart, the notes band, or a longer trailer.").format(
                  what=names.get(what, what))


def with_options(sheet: Sheet, **changes) -> Sheet:
    """A copy of *sheet* placed again with changed options (tests)."""
    opts = replace(sheet.opts, **changes)
    return sheet_for(sheet.grid, sheet.paper_w, sheet.paper_h, opts)
