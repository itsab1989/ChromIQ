"""AN i1iO CHART ON A SHEET LARGER THAN THE TABLE: which pieces it is cut into.

A sheet that lies inside the arm's reach is one piece, always, as before this
existed. A larger one is divided: the pieces are the chart's pages (each is
laid on the table by itself), the sheet is what is printed. Two sizes, and
which one a reader of a paper size gets, are in the design's table of readers
(`tests/data/i1io_readers.json` names every one):

* the SHEET: ``paper`` everywhere (recipe, kwargs, params, side file), with its
  millimetres from `layout_engine.papers.dimensions_mm`;
* the PIECE, what lies on the table: `layout_engine.papers.piece_mm_of`, which
  comes here for an i1iO layout only.

THE DIVISION IS RESOLVED ONCE, AT GENERATE, AND STORED (`token` in the chart's
recipe, its ``.ti2`` and its side file). Everything stored is read from that
record, never worked out again by the rule of a later version; a stored chart
without the record is one piece (ONE). Qt free; imports the layout engine
only inside functions.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from core.logger import get_logger

from . import table_facts as F

log = get_logger(__name__)

#: The recipe field / build-kwargs key: "" = automatic, ONE = one piece
#: (a stored chart without a division), else a resolved plan's `token`.
PIECES_KEY = "i1io_pieces"
ONE = "one"
#: The build-kwargs key under which a build hands on the piece it resolved.
PIECE_MM_KEY = "_i1io_piece_mm"
#: The `.ti2` keyword of a chart of several pieces (the token).
KEYWORD = "CHROMIQ_I1IO_PIECES"
#: About the time one more laying and aiming costs, in patches.
LAYING_COSTS = 100
#: No piece is narrower than this (three crosses and a few strips).
NARROWEST_MM = 60.0
#: No sheet is longer than this (a whole roll).
LONGEST_MM = 20000.0
_EPS = 0.01


class PieceRecordError(ValueError):
    """The recorded division of a chart is damaged, of another sheet, or a
    newer ChromIQ's: it is never used, and nothing is built or read by it."""


class NewerChartError(PieceRecordError):
    """A chart of a newer ChromIQ (its side file says so): it is not read."""


@dataclass(frozen=True)
class Plan:
    """A sheet divided into pieces. The sheet as it is printed, x to the right,
    y down; *places* the top left of every piece on it, in page order (as a
    person holding the sheet the way its pieces read reads them: left to
    right, then down). *turn*: quarter turns clockwise a piece page (portrait)
    is turned by on the sheet, 0 or 1."""
    sheet_mm: "tuple[float, float]"
    piece_mm: "tuple[float, float]"                  # the portrait page
    turn: int
    places: "tuple[tuple[float, float], ...]"
    cut_x: "tuple[float, ...]"
    cut_y: "tuple[float, ...]"

    @property
    def count(self) -> int:
        return len(self.places)

    @property
    def cell_mm(self) -> "tuple[float, float]":
        """A piece's width and height as it lies on the sheet."""
        w, h = self.piece_mm
        return (h, w) if self.turn else (w, h)

    def sheet_of(self, page: int) -> "tuple[int, int]":
        """``(sheet, place)``, 0-based, of piece page *page*."""
        return divmod(int(page), self.count)

    def to_sheet(self, page: int, x: float, y: float) -> "tuple[float, float]":
        """A point of piece page *page* (mm on the portrait page) on its sheet."""
        px, py = self.places[self.sheet_of(page)[1]]
        if self.turn:
            return px + self.piece_mm[1] - y, py + x
        return px + x, py + y

    def from_sheet(self, place: int, x: float, y: float
                   ) -> "tuple[float, float]":
        """A point of the sheet on the piece at *place*: `to_sheet`'s inverse."""
        px, py = self.places[place]
        if self.turn:
            return y - py, self.piece_mm[1] - (x - px)
        return x - px, y - py

    @property
    def token(self) -> str:
        def n(v):
            return f"{round(float(v), 3):g}"
        return (f"v1;sheet={n(self.sheet_mm[0])}x{n(self.sheet_mm[1])}"
                f";piece={n(self.piece_mm[0])}x{n(self.piece_mm[1])}"
                f";turn={self.turn};at="
                + "/".join(f"{n(x)},{n(y)}" for x, y in self.places)
                + ";cut_x=" + ",".join(map(n, self.cut_x))
                + ";cut_y=" + ",".join(map(n, self.cut_y)))

    def as_record(self) -> dict:
        """The side file's ``sheet`` block."""
        return {"sheet_mm": list(self.sheet_mm), "piece_mm": list(self.piece_mm),
                "turn": self.turn, "places_mm": [list(p) for p in self.places],
                "cut_x_mm": list(self.cut_x), "cut_y_mm": list(self.cut_y),
                "pieces": self.count, "token": self.token}


def _sound(plan: Plan) -> bool:
    """Whether *plan* is a division ChromIQ makes: every number finite and in
    range, a sheet larger than the table, upright pieces within the reach,
    standing in a full grid from the sheet's corner, in the order they are
    read, cut where they end. (A stored plan is believed only then; which of
    the possible grids it is, is its own business, not today's rule's.)"""
    flat = (*plan.sheet_mm, *plan.piece_mm, *plan.cut_x, *plan.cut_y,
            *(v for p in plan.places for v in p))
    if not plan.places or not all(
            0.0 <= v <= LONGEST_MM for v in flat):      # (nan is neither)
        return False
    pw, ph = plan.piece_mm
    if pw > ph + _EPS or pw < NARROWEST_MM - _EPS or min(plan.sheet_mm) < 1.0:
        return False
    short, long = _most(True)
    if one_piece(plan.sheet_mm) or not (one_piece(plan.piece_mm) or (
            F.LARGE_PIECES and pw <= short + _EPS and ph <= long + _EPS)):
        return False
    cw, ch = (ph, pw) if plan.turn else (pw, ph)
    c, r = len({x for x, _y in plan.places}), len({y for _x, y in plan.places})
    if cw * c > plan.sheet_mm[0] + 0.05 or ch * r > plan.sheet_mm[1] + 0.05:
        return False
    want = _grid(*plan.sheet_mm, c, r, cw, ch, plan.turn)

    def same(a, b):
        return len(a) == len(b) and all(
            abs(x - y) <= 0.05 for x, y in zip(a, b))
    return (same(plan.cut_x, want.cut_x) and same(plan.cut_y, want.cut_y)
            and len(plan.places) == len(want.places)
            and all(same(p, q) for p, q in zip(plan.places, want.places)))


def from_token(token) -> "Plan | None":
    """The plan a `Plan.token` names; None for "", ONE, and what is no token
    of a division ChromIQ makes (`_sound`)."""
    text = str(token or "")
    if not text.startswith("v1;"):
        return None
    try:
        f = dict(part.split("=", 1) for part in text.split(";")[1:])

        def pair(s, sep="x"):
            a, b = s.split(sep)
            return float(a), float(b)

        def nums(s):
            return tuple(float(v) for v in s.split(",") if v)
        plan = Plan(pair(f["sheet"]), pair(f["piece"]), int(f["turn"]),
                    tuple(pair(p, ",") for p in f["at"].split("/")),
                    nums(f["cut_x"]), nums(f["cut_y"]))
    except (KeyError, ValueError, AttributeError):
        return None
    return plan if plan.turn in (0, 1) and _sound(plan) else None


def one_piece(sheet_mm) -> bool:
    """Whether the sheet lies inside the arm's reach, either way round: then
    it is one piece, as before (whatever `chart.sheet_size` says about how it
    is laid)."""
    s, l_ = sorted(float(v) for v in sheet_mm)
    rx, ry = F.REACH_MM.value
    return s <= ry + 1e-3 and l_ <= rx + 1e-3


def _code(v: float) -> str:
    return f"{round(v, 3):g}"


@lru_cache(maxsize=512)
def _patches(short: float, long: float) -> int:
    """The patches of the standard layout on a piece of this size (0: none)."""
    from workflow.layout_engine import geometry, instruments
    from .chart import LIMITS_KEY, LIMITS_NOW
    try:
        g = instruments.geom_from_build_kwargs({
            "instrument": "IO2", "paper": f"{_code(short)}x{_code(long)}",
            LIMITS_KEY: LIMITS_NOW, PIECES_KEY: ONE})
        return int(geometry.patches_per_sheet(g, short, long))
    except Exception:            # noqa: BLE001 - no layout, no piece
        return 0


def _most(large: bool) -> "tuple[float, float]":
    """The largest piece, short and long side."""
    w, h = (F.PIECE_MAX_LARGE_MM if large else F.PIECE_MAX_MM).value
    return min(w, h), max(w, h)


def _candidates(w: float, h: float, large: bool):
    """``(score, -pieces, cols, rows, cell w, cell h)`` of every division:
    equal shares, and pieces cut down to exactly A4 or Letter (or the largest
    piece, once allowed)."""
    short_max, long_max = _most(large)
    for c in range(1, 10):
        for r in range(1, 10):
            cw, ch = round(w / c, 3), round(h / r, 3)
            s, l_ = min(cw, ch), max(cw, ch)
            if l_ <= long_max + _EPS and s <= short_max + _EPS \
                    and s >= NARROWEST_MM:
                yield (_patches(s, l_) * c * r - LAYING_COSTS * c * r,
                       -(c * r), c, r, cw, ch)
    trims = [(210.0, 297.0), (215.9, 279.4)]
    if large:
        trims.append((short_max, long_max))
    for s, l_ in trims:
        for cw, ch in ((s, l_), (l_, s)):
            for c in range(1, int(w / cw + 1e-9) + 1):
                for r in range(1, int(h / ch + 1e-9) + 1):
                    yield (_patches(s, l_) * c * r - LAYING_COSTS * c * r,
                           -(c * r), c, r, cw, ch)


@lru_cache(maxsize=128)
def _plan(w: float, h: float, large: bool) -> "Plan | None":
    if one_piece((w, h)):
        return None
    best = max(_candidates(w, h, large), default=None, key=lambda b: b[:2])
    if best is None or best[0] + LAYING_COSTS * -best[1] <= 0:
        return None
    _s, _n, c, r, cw, ch = best
    return _grid(w, h, c, r, cw, ch, 1 if cw > ch else 0)


def _grid(w, h, c: int, r: int, cw, ch, turn: int) -> Plan:
    """The plan of *c* by *r* cells of *cw* x *ch* mm on a sheet."""
    if turn:
        order = [(i, j) for j in range(r) for i in range(c)]
    else:
        # the sheet is read turned a quarter clockwise, as its pieces are
        order = [(i, j) for i in range(c) for j in reversed(range(r))]
    cut_x = [round(cw * i, 3) for i in range(1, c + 1)
             if cw * i < w - _EPS]
    cut_y = [round(ch * j, 3) for j in range(1, r + 1)
             if ch * j < h - _EPS]
    return Plan((w, h), (min(cw, ch), max(cw, ch)), turn,
                tuple((round(cw * i, 3), round(ch * j, 3)) for i, j in order),
                tuple(cut_x), tuple(cut_y))


def plan_for(sheet_mm, choice: str = "") -> "Plan | None":
    """The pieces of a sheet (None: one piece, or none that fits): the rule of
    today for *choice* "", else the stored division. `PieceRecordError` for
    one that is damaged or of another sheet: nothing is described by it, and
    what asks for a build refuses it in words (`refuse_bad_record`)."""
    w, h = (round(float(v), 3) for v in sheet_mm)
    text = str(choice or "")
    if not text:
        return _plan(w, h, bool(F.LARGE_PIECES))
    if text == ONE:
        return None
    return stored_plan(text, (w, h))


def stored_plan(token, sheet_mm=None) -> Plan:
    """The division *token* names, of this very sheet when *sheet_mm* is
    given; `PieceRecordError` for anything else."""
    plan = from_token(token)
    if plan is None or sheet_mm is not None and not all(
            abs(a - float(b)) < 0.02
            for a, b in zip(plan.sheet_mm, sheet_mm)):
        raise PieceRecordError(str(token))
    return plan


def refuse_bad_record(source) -> None:
    """`PieceRecordError` when build kwargs or a recipe carry a division that
    is damaged, of another sheet or a newer ChromIQ's."""
    text = str(_of(source, PIECES_KEY, "i1io_pieces") or "")
    if text and text != ONE:
        from workflow.layout_engine.papers import dimensions_mm
        stored_plan(text, dimensions_mm(str(_of(source, "paper", "paper")
                                            or "A4")))


def record_of(chart_ti2) -> "Plan | None":
    """The division recorded with a chart (its side file and its ``.ti2``'s
    keyword, which must say the same), None for a chart of one piece;
    `PieceRecordError` when what is recorded cannot be trusted, whatever is
    wrong with it."""
    try:
        return _record_of(chart_ti2)
    except PieceRecordError:
        raise
    except Exception as exc:      # noqa: BLE001 - any damage is the one answer
        raise PieceRecordError(f"damaged: {type(exc).__name__}: {exc}") from exc


def _record_of(chart_ti2) -> "Plan | None":
    from core.stem_paths import without_ext
    ti2 = Path(chart_ti2)
    stem = without_ext(ti2, ".ti2")
    side = stem.with_name(stem.name + ".i1io.json")
    doc, in_side = None, None
    try:
        doc = json.loads(side.read_text(encoding="utf-8"))
    except OSError:
        pass
    except ValueError as exc:
        raise PieceRecordError("the side file cannot be read") from exc
    in_ti2, head = None, ""
    try:
        with open(ti2, encoding="utf-8", errors="replace") as fh:
            head = fh.read(12000)
        m = re.search(r'^%s\s+"([^"]*)"' % KEYWORD, head, re.M)
        in_ti2 = m.group(1) if m else None
    except OSError:
        pass
    if side.is_file() and not isinstance(doc, dict):
        raise PieceRecordError("the side file is no record")
    if isinstance(doc, dict):
        from .chart import SCHEMA, SCHEMA_PIECES
        schema = doc.get("schema")
        if isinstance(schema, (int, float)) and schema > SCHEMA_PIECES:
            raise NewerChartError(f"schema {schema!r}")
        if schema not in (None, SCHEMA, SCHEMA_PIECES):
            raise PieceRecordError(f"schema {schema!r}")
        if schema == SCHEMA_PIECES:
            in_side = doc.get("sheet")
            in_side = str(in_side.get("token") or "?") \
                if isinstance(in_side, dict) else "?"
        elif doc.get("sheet") is not None:
            in_side = "?"
    if in_side is None and in_ti2 is None:
        return None
    if None not in (in_side, in_ti2) and in_side != in_ti2 \
            or isinstance(doc, dict) and in_side is None:
        raise PieceRecordError("the side file and the .ti2 disagree")
    plan = stored_plan(in_side if in_side is not None else in_ti2)
    if isinstance(doc, dict):
        def near(a, b) -> bool:              # (nan is near nothing)
            return len(a) == len(b) and all(
                abs(x - float(y)) <= 0.05 for x, y in zip(a, b))
        if not near(plan.piece_mm, doc["paper_mm"]):
            raise PieceRecordError("the pages are not the pieces' size")
        pages = doc["pages"]
        if not pages:
            raise PieceRecordError("no page is recorded")
        m = re.search(r'^PASSES_IN_STRIPS2?\s+"([^"]*)"', head, re.M)
        if m and len([v for v in re.split(r"[,\s]+", m.group(1)) if v]) != \
                len(pages):
            raise PieceRecordError("the .ti2 has another number of pages")
        for n, page in enumerate(pages):
            at, place = plan.sheet_of(n)
            p = page["piece"]
            if (p["sheet"], p["piece"], p["turn"]) != (
                    at + 1, place + 1, plan.turn) or not near(
                        plan.places[place], p["place_mm"]):
                raise PieceRecordError("a page is another piece's")
    return plan


#: How far a stored place may lie beyond its page, or a page beyond the table,
#: for rounding (no chart ChromIQ ever wrote needs it).
PLACE_TOL_MM = 0.5


def check_places(chart_ti2) -> None:
    """START's look at where a chart's own side file sends the arm (safety
    review of the new layout, S3 and B2; charts of one piece too): the page is
    no larger than a piece may be, every aim, patch and run end lies on the
    page, and no run ends more than `F.PAST_THE_AIMS_MM` beyond a page's corner
    patches. `PieceRecordError` otherwise; a chart without a side file, or one
    without places, is not this function's business."""
    ti2 = Path(chart_ti2)
    from core.stem_paths import without_ext
    stem = without_ext(ti2, ".ti2")
    side = stem.with_name(stem.name + ".i1io.json")
    if not side.is_file():
        return
    try:
        doc = json.loads(side.read_text(encoding="utf-8"))
        _check_places(doc)
    except PieceRecordError:
        raise
    except Exception as exc:      # noqa: BLE001 - any damage is the one answer
        raise PieceRecordError(f"damaged: {type(exc).__name__}: {exc}") from exc


def _check_places(doc: dict) -> None:
    w, h = (float(v) for v in doc["paper_mm"])
    short, long = _most(F.LARGE_PIECES)
    short, long = max(short, F.REACH_MM.value[1]), max(long, F.REACH_MM.value[0])
    tol = PLACE_TOL_MM
    # (every comparison is written so that nan is refused)
    if not (0.0 < w <= short + tol and 0.0 < h <= long + tol):
        raise PieceRecordError(f"a page of {w} x {h} mm is larger than the table")

    def inside(what: str, x: float, y: float) -> None:
        if not (-tol <= x <= w + tol and -tol <= y <= h + tol):
            raise PieceRecordError(f"{what} lies at {x}, {y}, off its page")
    for page in doc["pages"]:
        aims = page.get("aim_points") or []
        for a in aims:
            inside("an aim", float(a["page_mm"][0]), float(a["page_mm"][1]))
        ends: "list[float]" = []
        for st in page.get("strips") or []:
            for q in st.get("patches") or []:
                inside(f"patch {q.get('loc')}", float(q["centre_mm"][0]),
                       float(q["centre_mm"][1]))
            r0, r1 = (float(v) for v in st["run_mm"])
            for r in (r0, r1):
                inside("the end of a run", float(st.get("x_mm", 0.0)), r)
            ends += [r0, r1]
        ys = [float(a["page_mm"][1]) for a in aims if a.get("target") == "patch"]
        if ys and ends:
            most = F.PAST_THE_AIMS_MM.value + 0.02
            if not (min(ys) - min(ends) <= most and max(ends) - max(ys) <= most):
                raise PieceRecordError(
                    "a run ends too far beyond the corner patches aimed at")


def made_by_a_newer_chromiq(chart_ti2) -> bool:
    """Whether the chart's side file is of a version this one does not know."""
    try:
        record_of(chart_ti2)
    except NewerChartError:
        return True
    except PieceRecordError:
        pass
    return False


#: What a stored recipe carries when the chart's own files contradict its
#: division (`recipe_token`): never a division, refused wherever one is asked.
NOT_TRUSTED = "not-trusted"


def recipe_token(stored: str, chart_ti2=None) -> str:
    """The division of a recipe STORED WITH A CHART (``channels.json``), held
    against the chart's own record, the one truth (its side file and
    ``.ti2``, `record_of`): the record's; ONE for a chart of one piece;
    NOT_TRUSTED when they contradict each other or the record is damaged. A
    recipe without one takes the record's (a chart of the patch set editor
    before it was stored there). Without *chart_ti2*, or with neither file
    there, as stored."""
    stored = str(stored or "")
    if chart_ti2 is None:
        return stored or ONE
    from core.stem_paths import without_ext
    stem = without_ext(chart_ti2, ".ti2")
    if not Path(chart_ti2).is_file() and not stem.with_name(
            stem.name + ".i1io.json").is_file():
        return stored or ONE
    try:
        plan = record_of(chart_ti2)
    except PieceRecordError as exc:
        log.warning("i1iO: %s: the pieces' record is not trusted: %s",
                    Path(chart_ti2).name, exc)
        return NOT_TRUSTED
    own = plan.token if plan is not None else ONE
    if stored in ("", own):
        return own
    log.warning("i1iO: %s: the stored recipe and the chart's record disagree",
                Path(chart_ti2).name)
    return NOT_TRUSTED


# ---- the one door ---------------------------------------------------------------

def _of(source, kw_key: str, attr: str, default=None):
    if isinstance(source, dict):
        return source.get(kw_key, default)
    return getattr(source, attr, default)


def plan_of(source) -> "Plan | None":
    """The plan of build kwargs or of a `LayoutRecipe` (None: one piece): only
    an i1iO layout with the limits' marker is ever divided."""
    from .chart import LIMITS_KEY, LIMITS_NOW
    if _of(source, "instrument", "instrument") != "IO2":
        return None
    try:
        if int(_of(source, LIMITS_KEY, "i1io_limits") or 0) < LIMITS_NOW:
            return None
    except (TypeError, ValueError):
        return None
    from workflow.layout_engine.papers import dimensions_mm
    try:
        sheet = dimensions_mm(str(_of(source, "paper", "paper") or ""))
    except (ValueError, TypeError):
        return None
    return plan_for(sheet, _of(source, PIECES_KEY, "i1io_pieces") or "")


def piece_mm_of(source) -> "tuple[float, float]":
    """What lies on the table: the piece of a divided sheet, else the sheet."""
    if isinstance(source, dict) and source.get(PIECE_MM_KEY):
        w, h = source[PIECE_MM_KEY]
        return float(w), float(h)
    plan = plan_of(source)
    if plan is not None:
        return plan.piece_mm
    from workflow.layout_engine.papers import dimensions_mm
    return dimensions_mm(str(_of(source, "paper", "paper") or "A4"))


def info_text(plan: Plan, sheets: int, patches: int) -> str:
    """M-I1IO-PIECES-INFO, translated: what is printed, cut and measured."""
    from core.i18n import count_phrase, tr
    from workflow import measurement_messages as _mm
    return tr(_mm._I1IO_PIECES_INFO).format(
        sheets=count_phrase(sheets, tr("1 sheet"), tr("{n} sheets")),
        pieces=count_phrase(sheets * plan.count, tr("1 piece"),
                            tr("{n} pieces")), patches=patches)


# ---- the three counts --------------------------------------------------------------

def pieces_on(source) -> int:
    """The pieces of one printed sheet (1 for every other chart)."""
    plan = plan_of(source)
    return plan.count if plan is not None else 1


def sheets_of(pieces: int, source) -> int:
    """The printed sheets that *pieces* piece pages take."""
    n = pieces_on(source)
    return -(-int(pieces) // n)


def patches_on_a_sheet(per_piece: int, source) -> int:
    """The patches of one printed sheet, *per_piece* of them on each piece."""
    return int(per_piece) * pieces_on(source)
