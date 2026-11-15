"""Bringing back an i1Profiler "Measure Chart" measurement of ChromIQ's own
i1iO sheet (the i1iO table Beta, one page).

WHAT IT IS. i1Profiler can measure a sheet it did not lay out on the i1iO
table: the person types the grid (columns and rows), aims the arm at three
corner patches and the table scans every cell of that grid. The file it saves
(``.cmxf``, CxF3 XML) carries placeholders for the device values (RGB
150/150/150 on every patch) and, for every reading, its place on i1Profiler's
grid: a ``Location`` tag collection with ``Page``, ``Row`` and ``Column``.
Proved on a real ChromIQ sheet (the tester's 24 x 22 A4 chart, 2026-11-14):
i1Profiler's **Row r is the r-th strip from the table's top** (the strip
beside aim 1) and **Column c the (c+1)-th patch from the table's left**
(beside aims 1 and 2); the file lists the readings column by column.

HOW A READING FINDS ITS PATCH. By its OWN Row/Column tag, through the chart's
side file ``<stem>.i1io.json`` (strips and patches in mm), never by colour
(§I.9) and never by the list position. Each reading's tag must agree with
the tag of the Target at the same position in the file (they are two parallel
lists the converter pairs by index). The side file is tied to the chart by
its content: every cell must name a ``.ti2`` patch with the same
``SAMPLE_ID`` and ``SAMPLE_LOC``, every ``.ti2`` patch must be a cell, and the
grid must be the ``.ti2``'s ``STEPS_IN_PASS`` x ``PASSES_IN_STRIPS2``.

THE SAFETY NET. The colours only decide whether the file is filed, never where
a reading goes. Nothing is ever corrected: a sheet that looks turned,
mirrored, shifted or aimed off is REFUSED with the reason and the way to
measure again (about two minutes on the table). The alternatives are ranked
only to word that reason. In order (the design of 2026-11-14 with its
challenge, M1 to M4 and S1 to S7):

1. exact: one page, i1Profiler's grid == the chart's grid, every cell once,
   readings == cells, Target and reading tags agree; the side file tie;
2. the colour judge of 4.3.32 (`turned_colour_check.judge`), unchanged, with
   the entries in i1Profiler's own column-major order;
3. a chart the colours CAN judge: agree -> the neighbour-strip check (a corner
   aimed a few mm across the strips blends the next strip into the readings,
   which the judge cannot see); anything else (disagree, or unsure) refuses;
4. a chart the colours CANNOT judge (sorted, ramps, few or similar patches):
   the arrangements compared by fit (one affine map expected -> measured), the
   exact count of readings that look like blank paper, the neighbour-strip
   check; only then the person is asked.

Off = unchanged: this module is imported only when the i1iO Beta is on, the
run's chart is an i1iO chart with its side file, and the picked file is a CxF
(`measurement_import.assess`, ``source=``). The converter is not changed; the
tags are read from the picked file here.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from core.logger import get_logger

log = get_logger(__name__)

#: The picked files this route reads (a CxF3 measurement).
SUFFIXES = (".cmxf", ".cxf", ".mxf")
#: Header keyword of a filed copy: which side file and grid paired it.
PAIRED_KEYWORD = "CHROMIQ_PAIRED_BY_I1IO_GRID"
#: Header keyword of a filed copy: what the colours said.
COLOUR_KEYWORD = "CHROMIQ_I1IO_GRID_COLOURS"

#: M2a: an arrangement whose fit residual is below this share of the recorded
#: order's fits clearly better (challenge sim2: wrong arrangements fit 2 dE
#: against 36 to 46 for the recorded order; right readings the other way).
FIT_RATIO = 0.6
#: M2a: an arrangement that moves the chart's expected colours by less than
#: this (median dE76 over the moved entries) cannot be told from the recorded
#: order and is not compared.
SELF_MAP_DE = 3.0
#: M2a: a recorded order that one affine map cannot bring within this many
#: dE76 (median) of the chart's colours is not explained by the chart at all
#: (another sheet, or the corners aimed in an order no whole-chart
#: arrangement describes: aimed top left, top right, bottom right). The
#: build's sweep: right readings at most 10.4 at noise 5 on every chart
#: kind; the transposed aim on a sorted chart at least 34.7.
FIT_ABSURD = 20.0
#: M2a: the lightness slope rule needs expected L* to spread this much.
SLOPE_MIN_L_SPREAD = 3.0
#: M2b: readings within this dE76 of the brightest reading look like it (the
#: paper, when the table read blank paper); the chart's patches within
#: PAPER_EXPECTED_DE of the expected colour at that reading's place are the
#: ones that should. More of the first than the second + PAPER_SLACK: the
#: table read paper where patches are (aimed at the crosses).
PAPER_DE = 6.0
PAPER_EXPECTED_DE = 10.0
PAPER_SLACK = 2
#: M4: the share of the neighbouring strip's colour in a strip's readings, at
#: its lower bound (`blend_share`). The false-alarm sweep of the build
#: (2026-11-15, 25 seeds x random / small / sorted / ramps / near-identical
#: charts x noise 0.8 / 2.5 / 5): right readings at most 0.031; a corner
#: aimed 3.5 mm across the strips 0.11 to 0.29 on every randomised or sorted
#: chart at noise up to 2.5 (the challenge's start value was 0.15).
BLEND_LIMIT = 0.10
#: M4: strips whose fitted colours differ from the neighbour's by less than
#: this (median dE76) cannot show a blend and are not asked.
BLEND_MIN_DIFF = 8.0
#: M4: the share is taken this many standard errors below its estimate.
BLEND_SIGMAS = 3.0
#: S1: an arrangement scoring at least this names the mistake.
NAME_FROM = 0.75

#: The judge's "the chart cannot tell" reasons (M1: only these may be asked).
CANNOT_TELL = frozenset(("few-patches", "similar", "neighbours",
                         "short-strips", "no-colours"))
#: The arrangements that mean the sheet lay turned half round.
TURNED = frozenset(("half-turn",))


# ---------------------------------------------------------------------------
# The file
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class McFile:
    """What a CxF measurement says about its grid and places."""
    columns: "int | None"
    rows: "int | None"
    pages: "int | None"
    target_cells: tuple
    target_rgbs: tuple
    readings: dict             # condition ("M0") -> tuple of cells

    @property
    def placeholders(self) -> bool:
        """Every Target carries the same device value (i1Profiler's
        placeholders for a chart whose colours it does not know)."""
        return bool(self.target_rgbs) and len(set(self.target_rgbs)) == 1


def is_cxf_name(path) -> bool:
    return Path(str(path)).suffix.lower() in SUFFIXES


def convert(path, out_dir, condition: "str | None" = None) -> Path:
    """The converted copy of a CxF *path* in *out_dir*, by the converter's own
    CxF reader (`reference_convert.cxf_measurement_to_ti3`, unchanged).

    WHY THIS EXISTS: i1Profiler saves a Measure Chart measurement as
    ``.cmxf`` ("Measurement only"), and the converter's `is_cxf` knows only
    ``.mxf`` and ``.cxf``, so it hands a ``.cmxf`` to txt2ti3, which stops
    with "No patches". Only the gated Measure Chart route (Beta on, an i1iO
    chart with its side file) converts a ``.cmxf`` here; everywhere else it
    is converted exactly as before."""
    from workflow.reference_convert import cxf_measurement_to_ti3
    p = Path(str(path))
    out = Path(str(out_dir))
    out.mkdir(parents=True, exist_ok=True)
    # the converter's own name for a CxF's copy (`convert_i1profiler_
    # measurement`): `cxf_measurement_to_ti3` mends a stem with a dot itself
    return Path(cxf_measurement_to_ti3(p, out / f"{p.stem}.ti3",
                                       condition=condition))


def _loc_of(obj, ns) -> "tuple | None":
    tags = {}
    for tc in obj.findall("cc:TagCollection", ns):
        if tc.get("Name") != "Location":
            continue
        for t in tc.findall("cc:Tag", ns):
            tags[t.get("Name")] = t.get("Value")
    try:
        return (int(str(tags["Page"]).strip()), int(str(tags["Row"]).strip()),
                int(str(tags["Column"]).strip()))
    except (KeyError, TypeError, ValueError):
        return None


def read_file(path) -> "McFile | None":
    """The grid and the places of the CxF at *path*, or None when it is not
    readable CxF XML. Read only; nothing is paired here."""
    import xml.etree.ElementTree as ET
    from workflow.reference_convert import _CXF_NS as ns
    try:
        root = ET.parse(str(path)).getroot()
    except (ET.ParseError, OSError):
        return None
    attrs = None
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] == "CustomAttributes" and (
                el.get("NumberPatchColumns") is not None):
            attrs = el
            break

    def _int(name):
        try:
            return int(str(attrs.get(name)).strip()) if attrs is not None \
                else None
        except (TypeError, ValueError):
            return None
    targets, rgbs, readings = [], [], {}
    for o in root.findall(".//cc:Object", ns):
        kind = o.get("ObjectType") or ""
        if kind == "Target":
            targets.append(_loc_of(o, ns))
            c = o.find("cc:DeviceColorValues/cc:ColorRGB", ns)
            k = o.find("cc:DeviceColorValues/cc:ColorCMYK", ns)
            el = c if c is not None else k
            rgbs.append(tuple((ch.text or "").strip() for ch in el)
                        if el is not None else ())
        elif re.fullmatch(r"M[0-2]_Measurement", kind):
            readings.setdefault(kind[:2], []).append(_loc_of(o, ns))
    return McFile(_int("NumberPatchColumns"), _int("NumberPatchRows"),
                  _int("NumberPatchPages"), tuple(targets), tuple(rgbs),
                  {k: tuple(v) for k, v in readings.items()})


# ---------------------------------------------------------------------------
# The chart's grid, from its side file
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Grid:
    """i1Profiler's Measure Chart grid of one page of an i1iO chart.

    ``sample_id[r][c]`` / ``loc[r][c]``: the patch at i1Profiler's Row r
    (the r-th strip from the table's top) and Column c (the (c+1)-th patch
    from the table's left), None where the cell holds no patch. *aim*: the
    printed names of the three corner patches to aim at, in aiming order
    (top left, bottom left, bottom right on the table)."""
    rows: int
    columns: int
    sample_id: tuple
    loc: tuple
    page: int = 1

    @property
    def full(self) -> bool:
        return all(s is not None for row in self.sample_id for s in row)

    @property
    def aim(self) -> "tuple[str, str, str]":
        return (self.loc[0][0], self.loc[self.rows - 1][0],
                self.loc[self.rows - 1][self.columns - 1])


def side_file_for(chart_ti2) -> Path:
    p = Path(str(chart_ti2))
    stem = str(p)[:-4] if str(p).lower().endswith(".ti2") else str(p)
    return Path(stem + ".i1io.json")


def read_side(chart_ti2) -> "dict | None":
    try:
        return json.loads(side_file_for(chart_ti2).read_text(
            encoding="utf-8"))
    except (OSError, ValueError):
        return None


def measure_chart_grid(side_doc: dict, page: int = 1) -> "Grid | None":
    """The grid of page *page* derived from the side file's COORDINATES, not
    from how its lists are sorted: strips by their x on the page (the table's
    y: `chart.to_table_mm`), patches by their y on the page DESCENDING (the
    table's x is the page's height minus its y)."""
    try:
        strips = side_doc["pages"][page - 1]["strips"]
    except (KeyError, IndexError, TypeError):
        return None
    if not strips:
        return None
    try:
        ordered = sorted(strips, key=lambda s: float(s["x_mm"]))
        cells = [sorted(s["patches"], key=lambda q: -float(q["centre_mm"][1]))
                 for s in ordered]
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    cols = max(len(c) for c in cells)
    sid = tuple(tuple(int(q["sample_id"]) for q in c) + (None,) * (cols - len(c))
                for c in cells)
    loc = tuple(tuple(str(q["loc"]) for q in c) + (None,) * (cols - len(c))
                for c in cells)
    return Grid(len(cells), cols, sid, loc, page)


def grid_record(grid: Grid) -> dict:
    """What a NEW chart's side file records for the Measure Chart route
    (written by `chart.write_side_file`, read back for the instructions)."""
    return {"columns": grid.columns, "rows": grid.rows,
            "aim_patches": list(grid.aim),
            "rule": "i1Profiler Measure Chart: Row r = the r-th strip from "
                    "the table's top (the strip beside aim 1), Column c = "
                    "the (c+1)-th patch from the table's left (beside aims 1 "
                    "and 2); type columns = patches per strip, rows = strips"}


def _ti2_facts(chart_ti2) -> "tuple[dict, dict, int, int]":
    """({sample_id: loc}, {sample_id: device strings}, steps, passes)."""
    from core.text_io import read_text
    from workflow.measurement_pairing import _first_table
    text = read_text(Path(str(chart_ti2)), lenient=True)
    m = re.search(r'^\s*STEPS_IN_PASS\s+"?(\d+)', text, re.M)
    steps = int(m.group(1)) if m else 0
    m = re.search(r'^\s*PASSES_IN_STRIPS2\s+"?(\d+)', text, re.M)
    passes = int(m.group(1)) if m else 0
    t = _first_table(text)
    locs, dev = {}, {}
    if t is None:
        return locs, dev, steps, passes
    fields, rows = t
    if "SAMPLE_ID" not in fields or "SAMPLE_LOC" not in fields:
        return locs, dev, steps, passes
    si, li = fields.index("SAMPLE_ID"), fields.index("SAMPLE_LOC")
    di = [i for i, f in enumerate(fields)
          if f not in ("SAMPLE_ID", "SAMPLE_LOC", "SAMPLE_NAME", "INDEX")
          and not f.startswith(("XYZ_", "LAB_", "SPEC_", "STDEV_", "D_"))]
    for ln in rows:
        p = ln.split()
        try:
            s = int(p[si].strip('"'))
        except (ValueError, IndexError):
            continue
        locs[s] = p[li].strip('"')
        dev[s] = tuple(p[i] for i in di if i < len(p))
    return locs, dev, steps, passes


def tie_ok(grid: Grid, chart_ti2) -> bool:
    """Does the side file's grid belong to this exact chart? By content (S6):
    every cell names a ``.ti2`` patch with the same id and name, every patch
    is a cell, and the grid is the ``.ti2``'s strips x patches."""
    try:
        locs, _dev, steps, passes = _ti2_facts(chart_ti2)
    except OSError:
        return False
    cells = [(s, l) for rs, rl in zip(grid.sample_id, grid.loc)
             for s, l in zip(rs, rl) if s is not None]
    if not locs or len(cells) != len(locs):
        return False
    if len({s for s, _ in cells}) != len(cells):
        return False
    if any(locs.get(s) != l for s, l in cells):
        return False
    if steps and grid.columns != steps:
        return False
    if passes and grid.rows != passes:
        return False
    return True


# ---------------------------------------------------------------------------
# The safety net (pure: expected and measured L*a*b* in judge order)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NetResult:
    """What the net decided. *action*: "file", "refuse" or "ask". *code*
    names the reason: "agree" (filed on the colours' word), "cannot-tell"
    (asked, *why* the judge's reason), "turned", "aimed" (*how* the best
    arrangement's name), "strip" (*strip* 0-based), "other-chart", "paper",
    "beside" (*strip*)."""
    action: str
    code: str
    why: str = ""
    how: str = ""
    strip: "int | None" = None
    score: float = float("nan")
    detail: str = ""
    judgement: object = None


def _fit(E: np.ndarray, M: np.ndarray):
    X = np.hstack([E, np.ones((len(E), 1))])
    B, *_ = np.linalg.lstsq(X, M, rcond=None)
    return np.linalg.norm(M - X @ B, axis=1), B


def fit_ranking(E, M, rows: int, cols: int):
    """M2a. (recorded residual, recorded L* slope, [(residual, name)] of the
    wrong arrangements that move the chart's colours and fit with a positive
    L* slope, best first)."""
    from workflow.turned_colour_check import wrong_arrangements
    E = np.asarray(E, float)
    M = np.asarray(M, float)
    n = len(E)
    res, B = _fit(E, M)
    rec = float(np.median(res))
    out = []
    for name, p in wrong_arrangements(n, rows, cols).items():
        keep = p >= 0
        if keep.sum() < 0.8 * n:
            continue
        moved = keep & (p != np.arange(n))
        if not moved.any() or float(np.median(np.linalg.norm(
                E[moved] - E[p[moved]], axis=1))) < SELF_MAP_DE:
            continue
        r, Bp = _fit(E[p[keep]], M[keep])
        if Bp[0, 0] <= 0:
            continue                       # an inverted fit explains nothing
        out.append((float(np.median(r)), name))
    out.sort()
    return rec, float(B[0, 0]), out


def paper_excess(E, M) -> "tuple[int, int]":
    """M2b. (readings that look like the brightest reading, the paper on a
    sheet read off its patches; patches the chart expects to look like the
    patch at that brightest reading's place). *M* is against the brightest
    reading, *E* against the chart's white; each side is compared within its
    own scale, so a chart of light, similar colours (whose brightest reading
    is a patch) counts its own similar patches on both sides."""
    E = np.asarray(E, float)
    M = np.asarray(M, float)
    k = int(np.argmax(M[:, 0]))
    m = int((np.linalg.norm(M - M[k], axis=1) <= PAPER_DE).sum())
    e = int((np.linalg.norm(E - E[k], axis=1) <= PAPER_EXPECTED_DE).sum())
    return m, e


def blend_share(E, M, rows: int, cols: int) -> "tuple[float, int | None]":
    """M4. The largest share of a neighbouring strip's fitted colour in a
    strip's readings (least squares, one affine map expected -> measured over
    the whole chart), and that strip (0-based).

    Taken at its LOWER bound, the share minus BLEND_SIGMAS standard errors,
    the noise read from the fit's own residuals: on a chart whose
    neighbouring strips differ little the share is mostly noise (the
    false-alarm sweep: a near-identical chart at noise 5 measured 0.33 with
    every reading right), while a real blend across strips that differ is
    many standard errors clear."""
    E = np.asarray(E, float)
    M = np.asarray(M, float)
    res, B = _fit(E, M)
    sigma = float(np.median(res)) / math.sqrt(3.0)

    def f(e):
        return np.hstack([e, np.ones((len(e), 1))]) @ B
    worst, at = 0.0, None
    for r in range(rows):
        js = [c * rows + r for c in range(cols) if c * rows + r < len(E)]
        own = f(E[js])
        for nb in (r - 1, r + 1):
            if not 0 <= nb < rows:
                continue
            ks = [c * rows + nb for c in range(cols) if c * rows + nb < len(E)]
            if len(ks) != len(js):
                continue
            d = f(E[ks]) - own
            if float(np.median(np.linalg.norm(d, axis=1))) < BLEND_MIN_DIFF:
                continue
            den = float((d * d).sum())
            if den <= 0:
                continue
            w = float(((M[js] - own) * d).sum() / den)
            w -= BLEND_SIGMAS * sigma / math.sqrt(den)
            if w > worst:
                worst, at = w, r
    return worst, at


def _name_from_alternatives(E, M, rows, cols) -> str:
    """S1: the arrangement that explains the readings, for the WORDS of a
    refusal only, or ""."""
    from workflow.turned_colour_check import _score, wrong_arrangements
    E = np.asarray(E, float)
    M = np.asarray(M, float)
    best, name = -2.0, ""
    for nm, p in wrong_arrangements(len(E), rows, cols).items():
        v = _score(E, M, p)
        if math.isfinite(v) and v > best:
            best, name = v, nm
    if best >= NAME_FROM:
        return name
    rec, _slope, ranked = fit_ranking(E, M, rows, cols)
    if ranked and ranked[0][0] < FIT_RATIO * rec:
        return ranked[0][1]
    return ""


def _refuse_named(name: str, **kw) -> NetResult:
    if name in TURNED:
        return NetResult("refuse", "turned", how=name, **kw)
    return NetResult("refuse", "aimed", how=name, **kw)


def judge_readings(E, M, rows: int, cols: int) -> NetResult:
    """The net for readings *M* against the chart's expected colours *E*,
    both in i1Profiler's column-major order (entry j = Row j % rows, Column
    j // rows). Never pairs; only decides."""
    from workflow.turned_colour_check import AGREE, DISAGREE, judge
    E = np.asarray(E, float)
    M = np.asarray(M, float)
    j = judge(E, M, rows, cols)
    kw = dict(score=j.score, judgement=j)
    if j.verdict == AGREE:
        w, at = blend_share(E, M, rows, cols)
        if w > BLEND_LIMIT:
            return NetResult("refuse", "beside", strip=at,
                             detail=f"{j.log_text()}; neighbour-strip share "
                                    f"{w:.2f} in strip {at}", **kw)
        return NetResult("file", "agree",
                         detail=f"{j.log_text()}; neighbour-strip share "
                                f"{w:.2f}", **kw)
    if j.why not in CANNOT_TELL:
        # M1: the chart CAN tell, and it did not say yes: refused.
        detail = j.log_text()
        if j.why in ("strip-wrong", "strip-unclear"):
            return NetResult("refuse", "strip", strip=j.strip,
                             detail=detail, **kw)
        name = _name_from_alternatives(E, M, rows, cols)
        if name:
            return _refuse_named(name, detail=detail)
        m_paper, e_paper = paper_excess(E, M)
        if m_paper > e_paper + PAPER_SLACK:
            return NetResult("refuse", "paper",
                             detail=f"{detail}; {m_paper} paper readings, "
                                    f"{e_paper} near-white patches", **kw)
        if j.verdict == DISAGREE and j.why == "low-score":
            return NetResult("refuse", "other-chart", detail=detail, **kw)
        return NetResult("refuse", "aimed", how="", detail=detail, **kw)
    # M2: the chart cannot tell by rank. By fit, by paper, by blend; then ask.
    detail = j.log_text()
    if j.why == "no-colours":
        return NetResult("ask", "cannot-tell", why=j.why, detail=detail,
                         **kw)
    rec, slope, ranked = fit_ranking(E, M, rows, cols)
    if ranked and ranked[0][0] < FIT_RATIO * rec:
        return _refuse_named(ranked[0][1], detail=(
            f"{detail}; by fit {ranked[0][1]} {ranked[0][0]:.1f} vs recorded "
            f"{rec:.1f}"))
    m_paper, e_paper = paper_excess(E, M)
    if m_paper > e_paper + PAPER_SLACK:
        return NetResult("refuse", "paper", detail=(
            f"{detail}; {m_paper} paper readings, {e_paper} near-white "
            f"patches"), **kw)
    if rec > FIT_ABSURD:
        return NetResult("refuse", "other-chart", detail=(
            f"{detail}; recorded fit {rec:.1f} dE, not explained by the "
            f"chart"), **kw)
    if slope <= 0 and float(E[:, 0].std()) >= SLOPE_MIN_L_SPREAD:
        name = ranked[0][1] if ranked else "half-turn"
        return _refuse_named(name, detail=(
            f"{detail}; recorded order runs against the lightness "
            f"(slope {slope:.2f})"))
    w, at = blend_share(E, M, rows, cols)
    if w > BLEND_LIMIT:
        return NetResult("refuse", "beside", strip=at, detail=(
            f"{detail}; neighbour-strip share {w:.2f} in strip {at}"), **kw)
    return NetResult("ask", "cannot-tell", why=j.why, detail=(
        f"{detail}; recorded fit {rec:.1f}"
        + (f", next {ranked[0][1]} {ranked[0][0]:.1f}" if ranked else "")),
        **kw)


# ---------------------------------------------------------------------------
# The route: from the picked file and its converted copy to a verdict
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class McVerdict:
    """The route's answer. *ok* False: refuse with *reason*. *ask_why*
    non-empty: file only after the person confirms (the chart cannot tell).
    *sample_of_row*: converted row i (0-based) -> the chart's sample id."""
    ok: bool
    reason: str = ""
    code: str = ""
    ask_why: str = ""
    grid: "Grid | None" = None
    sample_of_row: tuple = ()
    net: "NetResult | None" = None
    side_name: str = ""


def _condition_of(ti3) -> str:
    try:
        with open(ti3, "r", encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh):
                s = line.strip()
                if s == "BEGIN_DATA" or n > 400:
                    break
                m = re.match(r'^MEASUREMENT_CONDITION\s+"([^"]*)"', s)
                if m:
                    return m.group(1).strip().upper()
    except OSError:
        return ""
    return ""


def _expected(grid: Grid, chart_ti2, sids: list) -> "np.ndarray | None":
    """The colours the chart expects for *sids* (L*a*b* against its white):
    targen's estimate of the device values for an RGB chart, else the
    chart's own XYZ columns."""
    from workflow.turned_colour_check import _lab, expected_lab_rgb
    from workflow.ti3_analysis import Ti3ParseError, device_space_of, parse_ti3
    try:
        space = device_space_of(Path(str(chart_ti2)))
    except Exception:          # noqa: BLE001 - cannot say: no colours
        return None
    _locs, dev, _s, _p = _ti2_facts(chart_ti2)
    if space == "RGB":
        try:
            return expected_lab_rgb([[float(v) for v in dev[s][:3]]
                                     for s in sids])
        except (KeyError, ValueError, IndexError):
            return None
    try:
        design = parse_ti3(Path(str(chart_ti2)))
    except (Ti3ParseError, OSError):
        return None
    xyz = np.asarray(design.xyz, float)
    if xyz.size == 0 or not np.all(np.isfinite(xyz)) \
            or float(xyz[:, 1].max()) <= 0:
        return None
    by_id = {int(str(s).strip('"')): i for i, s in
             enumerate(design.sample_ids)}
    try:
        rows = [by_id[s] for s in sids]
    except KeyError:
        return None
    return _lab(xyz[rows], xyz[int(np.argmax(xyz[:, 1]))])


def assess_file(source, converted_ti3, chart_ti2) -> "McVerdict | None":
    """Judge the picked CxF *source* (its converted copy *converted_ti3*)
    against the i1iO chart *chart_ti2*. None when the file is not a Measure
    Chart measurement (it carries real device values): the ordinary import
    then judges it, unchanged. Call only when the Beta is on and the chart is
    an i1iO chart with its side file (`measurement_import.assess`)."""
    from workflow import measurement_messages as MM
    from workflow.ti3_analysis import Ti3ParseError, parse_ti3
    f = read_file(source)
    if f is None or not f.target_cells:
        return None
    side = read_side(chart_ti2)
    if side is None:
        return None
    _locs, dev, _s, _p = _ti2_facts(chart_ti2)
    chart_devs = {tuple(round(float(v), 1) for v in d) for d in dev.values()
                  if d}
    if not f.placeholders:
        return None
    try:
        shared = tuple(round(float(v) * 100.0 / 255.0, 1)
                       for v in f.target_rgbs[0])
    except ValueError:
        shared = ()
    if chart_devs == {shared}:
        # every patch of the chart has the file's one device value (an
        # evenness sheet measured with real values): not placeholders
        return None
    side_name = side_file_for(chart_ti2).name
    pages = int(side.get("page_count") or len(side.get("pages") or []) or 1)
    if pages > 1:
        return McVerdict(False, MM.i1io_import_reason("pages", pages=pages),
                         "pages", side_name=side_name)
    grid = measure_chart_grid(side, 1)
    if grid is None or not tie_ok(grid, chart_ti2):
        return McVerdict(False, MM.i1io_import_reason("side", side=side_name),
                         "side", side_name=side_name)
    if not grid.full:
        # S4: cannot occur on one page (the engine pads every strip); a grid
        # that is not full is refused rather than guessed.
        return McVerdict(False, MM.i1io_import_reason("side", side=side_name),
                         "side", grid=grid, side_name=side_name)
    R, C = grid.rows, grid.columns
    if (f.pages or 0) > 1:
        return McVerdict(False, MM.i1io_import_reason("pages", pages=f.pages),
                         "pages", grid=grid, side_name=side_name)
    if (f.columns, f.rows) != (C, R):
        return McVerdict(False, MM.i1io_import_reason(
            "grid", got_cols=f.columns or 0, got_rows=f.rows or 0, cols=C,
            rows=R), "grid", grid=grid, side_name=side_name)
    cond = _condition_of(converted_ti3)
    readings = f.readings.get(cond) if cond else None
    n = R * C
    if readings is None or len(readings) != len(f.target_cells) \
            or len(readings) != n:
        got = len(readings) if readings is not None else 0
        return McVerdict(False, MM.i1io_import_reason(
            "count", got=got, total=n), "count", grid=grid,
            side_name=side_name)
    seen = set()
    for t, r in zip(f.target_cells, readings):
        if r is None or t != r:
            return McVerdict(False, MM.i1io_import_reason("places"),
                             "places", grid=grid, side_name=side_name)
        pg, row, col = r
        if pg != 1 or not (0 <= row < R and 0 <= col < C) or r in seen:
            return McVerdict(False, MM.i1io_import_reason(
                "count", got=len(readings), total=n), "count", grid=grid,
                side_name=side_name)
        seen.add(r)
    try:
        measured = parse_ti3(Path(str(converted_ti3)))
    except (Ti3ParseError, OSError):
        return McVerdict(False, MM.i1io_import_reason(
            "count", got=0, total=n), "count", grid=grid, side_name=side_name)
    xyz = np.asarray(measured.xyz, float)
    if len(xyz) != n:
        return McVerdict(False, MM.i1io_import_reason(
            "count", got=len(xyz), total=n), "count", grid=grid,
            side_name=side_name)
    sample_of_row = tuple(grid.sample_id[r[1]][r[2]] for r in readings)
    # judge order: entry j = Row j % R, Column j // R
    row_of_cell = {(r[1], r[2]): i for i, r in enumerate(readings)}
    order = [row_of_cell[(j % R, j // R)] for j in range(n)]
    sids = [grid.sample_id[j % R][j // R] for j in range(n)]
    E = _expected(grid, chart_ti2, sids)
    from workflow.turned_colour_check import measured_lab
    if E is None or float(xyz[:, 1].max()) <= 0:
        net = NetResult("ask", "cannot-tell", why="no-colours",
                        detail="no expected colours")
    else:
        net = judge_readings(E, measured_lab(xyz[order]), R, C)
    log.info("i1iO Measure Chart import: %s, grid %d x %d, condition %s: "
             "%s (%s)", Path(str(source)).name, C, R, cond, net.code,
             net.detail)
    if net.action == "refuse":
        letter = (grid.loc[net.strip][0] if net.strip is not None else "")
        return McVerdict(False, MM.i1io_import_reason(
            net.code, how=net.how, strip=_strip_name(letter),
            number=(net.strip + 1) if net.strip is not None else "",
            p1=grid.aim[0], p2=grid.aim[1], p3=grid.aim[2],
            labelled=bool(side.get("labels_printed", True))), net.code,
            grid=grid, net=net, side_name=side_name)
    return McVerdict(True, "", net.code,
                     ask_why=(net.why or "cannot-tell")
                     if net.action == "ask" else "",
                     grid=grid, sample_of_row=sample_of_row, net=net,
                     side_name=side_name)


def _strip_name(loc: "str | None") -> str:
    """The strip letters of a printed patch name ("AB12" -> "AB")."""
    m = re.match(r"^([^0-9]+)", str(loc or ""))
    return m.group(1) if m else str(loc or "")


def complete(converted_ti3, chart_ti2, verdict: McVerdict) -> int:
    """File the converted COPY *converted_ti3* by the verdict's pairing: each
    row takes the chart's ``SAMPLE_LOC`` of its own cell, the placeholder
    device values are dropped and the chart's written in their place, in the
    chart's order (`measurement_pairing.attach_device_values_from_chart`),
    and the header says which grid paired it and what the colours said.
    Rewrites the file in place; returns the rows written, 0 when nothing was
    done (the caller refuses then)."""
    from core.text_io import read_text
    from workflow.measurement_pairing import (_first_table,
                                              attach_device_values_from_chart)
    if not verdict.ok or verdict.grid is None or not verdict.sample_of_row:
        return 0
    path = Path(str(converted_ti3))
    locs, _dev, _s, _p = _ti2_facts(chart_ti2)
    text = read_text(path, lenient=True)
    t = _first_table(text)
    if t is None:
        return 0
    fields, rows = t
    if len(rows) != len(verdict.sample_of_row) or "SAMPLE_LOC" not in fields:
        return 0
    from workflow.ti3_analysis import _has_device_columns
    drop = {i for i, f in enumerate(fields)
            if _has_device_columns([f]) or f.startswith(
                ("RGB_", "CMYK_"))}
    li = fields.index("SAMPLE_LOC")
    keep = [i for i in range(len(fields)) if i not in drop]
    new_fields = [fields[i] for i in keep]
    new_rows = []
    for ln, sid in zip(rows, verdict.sample_of_row):
        p = ln.split()
        p[li] = f'"{locs[sid]}"'
        new_rows.append(" ".join(p[i] for i in keep))
    out, state = [], "head"
    for ln in text.splitlines():
        s = ln.strip()
        if state == "head":
            if s.startswith("NUMBER_OF_FIELDS"):
                out.append(f"NUMBER_OF_FIELDS {len(new_fields)}")
                continue
            if s == "BEGIN_DATA_FORMAT":
                out += [ln, " ".join(new_fields) + " "]
                state = "fmt"
                continue
            out.append(ln)
        elif state == "fmt":
            if s == "END_DATA_FORMAT":
                out.append(ln)
                state = "mid"
        elif state == "mid":
            out.append(ln)
            if s == "BEGIN_DATA":
                out += new_rows
                state = "data"
        elif state == "data":
            if s == "END_DATA":
                out.append(ln)
                state = "tail"
        else:
            out.append(ln)
    g, net = verdict.grid, verdict.net
    at = 1 if out and out[0].strip().startswith("CTI3") else 0
    colour = ("asked=yes why=" + verdict.ask_why) if verdict.ask_why else (
        f"score={net.score:.3f}" if net is not None and net.score == net.score
        else "score=n/a")
    out[at:at] = [f'KEYWORD "{PAIRED_KEYWORD}"',
                  f'{PAIRED_KEYWORD} "{verdict.side_name} page {g.page}, '
                  f'{g.columns} x {g.rows}"',
                  f'KEYWORD "{COLOUR_KEYWORD}"', f'{COLOUR_KEYWORD} "{colour}"']
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return attach_device_values_from_chart(path, chart_ti2)


# ---------------------------------------------------------------------------
# The numbers the instructions show
# ---------------------------------------------------------------------------

def instruction_numbers(chart_ti2) -> "dict | None":
    """{"cols", "rows", "p1", "p2", "p3", "pages", "labelled", "crosses"} for
    the Measure Chart steps of the Start window, from the side file (its
    "measure_chart" record when a new chart has one, else derived from its
    strips), or None when the side file cannot say."""
    side = read_side(chart_ti2)
    if side is None:
        return None
    pages = int(side.get("page_count") or len(side.get("pages") or []) or 1)
    grid = measure_chart_grid(side, 1)
    if grid is None:
        return None
    rec = (side.get("pages") or [{}])[0].get("measure_chart") or {}
    aim = rec.get("aim_patches") or list(grid.aim)
    return {"cols": int(rec.get("columns") or grid.columns),
            "rows": int(rec.get("rows") or grid.rows),
            "p1": aim[0], "p2": aim[1], "p3": aim[2], "pages": pages,
            "labelled": bool(side.get("labels_printed", True)),
            "crosses": bool(side.get("marks_mm"))}
