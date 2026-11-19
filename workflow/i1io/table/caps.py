# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The table job's caps, DERIVED FROM THE CHART (build step 6; the owner's requirement of
2026-11-17: every chart ChromIQ's i1iO layout can make for an i1iO 2 with an i1Pro 2 must be
measurable, and a session may never send more than its chart needs plus a stated allowance).

The tester program 0.6.0 used fixed caps per sitting (8,680 lines / 3,060 movements, part C's
``session_caps()``), which would refuse the third or fourth 990-patch page. The job replaces them
with caps worked out from the chart's own rows, patches and pages:

    lines = OPEN + PARK + CAL + TILE + sum over pages of (page_need + page_allowance)
    page_need = ALIGN_CYCLE + sum over rows of ROW(n)
    page_allowance = ALIGN_CYCLE                (one more alignment: a new white, a re-aim)
                     + 2 x the page's longest ROW  (two rows read again)
                     + CAL + TILE                (step 7: a new white and a tile reading)
                     + ceil(10 % of page_need)
                     + (rows + 2) x 2 x (3, 1)   (4.3.48: each row attempt's two automatic
                                                  second moves after an arrival beside)

and the same for movements. Every per-step number below is the tester's own (its stage caps and
the recorded steps' list lengths), so a session can never send more than the tester's stages
would for the same chart, plus the allowance. RUNAWAY PROTECTION, NOT A CHART LIMIT: a chart is
refused here only when it lies beyond what ChromIQ's i1iO layout can make at all
(:data:`LAYOUT_MAXIMA`), which no chart the app made can.

The start-up of a just-switched-on table keeps its own ten lines on top
(``Table.cold_allowance``), exactly as in 0.6.0.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import geometry as geo
from . import session_table as tbl

#: The true maxima of ChromIQ's i1iO layout for an i1iO 2 (computed from the layout engine,
#: ``maxima.json`` of 2026-11-17): patches per row, rows per page, patches per page, pages.
LAYOUT_MAXIMA = {"per_row": 33, "rows": 30, "per_page": 990, "pages": 667}

#: How often a creep (the feel-forward step) may run per page, and its own lines / movements
#: (part C's stage DZ: 2 x CREEP_STEPS_MAX + 8 lines, CREEP_STEPS_MAX + 1 movements).
#: 4.3.49 (Basti's ruling: targets up to what the person aimed at): 19, from 10, so that an
#: aimed area up to geometry's absolute backstop (FRONT_CAP_Y 3650) can be felt to from the proven
#: front (2723): 927 units in steps of at most 50. The step rule itself is unchanged.
CREEP_STEPS_MAX = 19
CREEP_PAUSE_S = 0.5
#: S-7 (owner-results round): +1 line, the arrival of the move to the front edge read once more
#: 4.3.47 MUST-1 (safety review): +1 line, the arm read again after the creep's first-visit
#: question, before its first move
CREEP = (2 * CREEP_STEPS_MAX + 8 + 1 + 1, CREEP_STEPS_MAX + 1)

#: Part C's own per-stage numbers (0.6.0), each pinned by a test.
OPEN = (len(tbl.OPEN_KEYS), 0)                                           # 11 / 0
PARK = (tbl.STEP_MAX_LINES["b_home"], tbl.STEP_MAX_MOTIONS["b_home"])    # the homing at rest
APPROACH = (sum(tbl.STEP_MAX_LINES[k] for k in ("b_home", "b_align")),
            sum(tbl.STEP_MAX_MOTIONS[k] for k in ("b_home", "b_align")))
AIMS = (8, 0)              # three p1, s0, f4 x 4 (stage D1)
CHECK_MOVE = (6, 1)        # stage D2: p0 (twice if free), m0, p0 (+1: S-7, the arrival read again)
#                            (+1: 4.3.47 MUST-1, read again after a first-visit question)
HOME = (8, 1)              # stage F: s0 p0 i1 s0 f0 f4 f4 p0
#: One alignment cycle: the way out, the aims, the creep, the check move and the homing.
ALIGN_CYCLE = tuple(sum(v) for v in zip(APPROACH, AIMS, CREEP, CHECK_MOVE, HOME))
#: A strip row (stage E2's row step 12 / 2, and its front-row ends 7 / 2).
STRIP_ROW = (12 + 7, 2 + 2)
#: THE DUAL ROW (2026-11-18): a strip row plus its UV pass straight back (the recorded zero-length
#: m0, c4, d1 210, p0, m2, a3, c3, and the p0 at its end: 8 lines, 2 movements), plus two lines of
#: room for ONE more reading: either the job's reading of the arm after a question answered
#: since the lamp pass's last reading (4.3.47 MUST-1, job._read_again_if_asked, only when a
#: reading is kept: table.position_now set) or scan._run_uv_pass's own reading (only when no
#: reading is kept, or the last motion is unconfirmed). The two never both happen (4.3.48
#: re-review NOTE-A, tightened from 10): the UV pass starts only after the lamp pass ended
#: "done", and every motion line either gets its done-answer (motion_unconfirmed False) or
#: raises before the job goes on, so the last motion is confirmed there; and every motion
#: clears position_now, so a kept reading is never older than the last motion. A tenth line
#: would be refused by the step's cap (a doubt, nothing more moves). 8 + 1 = 9 lines, 2
#: movements. (The arrival beside the UV start, 4.3.47 fix2, sends nothing more: one reading,
#: as run_row's.)
DUAL_UV_PASS = (9, 2)
DUAL_ROW = (STRIP_ROW[0] + DUAL_UV_PASS[0], STRIP_ROW[1] + DUAL_UV_PASS[1])
#: The allowance, stated: 10 % of a page's need, two rows read again, one more alignment.
ALLOWANCE_FRACTION = 0.10
ALLOWANCE_ROWS = 2
ALLOWANCE_ALIGNMENTS = 1
#: Step 7, reading: a calibration reads where the arm rests before and after it (tester C1: 2
#: lines, no movement); the white-tile reading three (C2). Each page carries one of each (a new
#: white is due every hour, between rows or pages), and the session one more of each.
CALIBRATION = (2, 0)
TILE_READING = (3, 0)


#: 4.3.48 (release review 4.3.47, SHOULD-1): an arrival read twice beside its target by 6..10
#: units in a patch row is moved to once more, automatically, from the fresh reading (the same
#: m0 line, as i1Profiler sends it on this table). One such retry costs at most BESIDE_RETRY:
#: the m0, its arrival p0 and that p0 read once more after 0.3 s (the first arrival's two
#: readings are the row's own S-7 slots). At most BESIDE_RETRIES_PER_ROW per row attempt.
BESIDE_RETRY = (3, 1)
BESIDE_RETRIES_PER_ROW = 2


def spot_row(n: int) -> "tuple[int, int]":
    """A spot row of *n* patches: stage D3's caps (2 n + 4 lines, n movements)."""
    return (2 * n + 4, n)


def spot_row_step(n: int) -> "tuple[int, int]":
    """Step 7: one attempt at a spot row of *n* patches, the job step's own cap: D3's 2 n + 4
    plus one fresh position reading per patch (a failed reading is read again once, from a
    fresh reading of where the arm stands, the owner's rule), plus one more per patch since the
    owner-results round (S-7: an arrival outside the tolerance is read once more before any
    doubt). The session caps keep D3's numbers; such re-reads come out of the page's
    allowance. 4.3.48: plus BESIDE_RETRIES_PER_ROW automatic second moves (BESIDE_RETRY each)."""
    return (4 * n + 4 + BESIDE_RETRIES_PER_ROW * BESIDE_RETRY[0],
            n + BESIDE_RETRIES_PER_ROW * BESIDE_RETRY[1])


def row_cost(n: int, dual: bool = False) -> "tuple[int, int]":
    """The larger of reading the row patch by patch or as a strip (*dual*: a dual row)."""
    s = spot_row(n)
    r = DUAL_ROW if dual else STRIP_ROW
    return (max(s[0], r[0]), max(s[1], r[1]))


class CapsRefused(Exception):
    """A chart beyond what ChromIQ's i1iO layout can make (the reason id in .reason)."""

    def __init__(self, reason: str, **detail):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


@dataclass(frozen=True)
class ChartShape:
    """The counts a chart's caps come from: patches per row, per page."""
    pages: "tuple[tuple[int, ...], ...]"

    @property
    def patches(self) -> int:
        return sum(sum(p) for p in self.pages)


def shape_of(sheet: dict) -> ChartShape:
    """The shape of an i1iO side file (``<stem>.i1io.json``): rows and patches per page."""
    try:
        pages = tuple(tuple(len(st["patches"]) for st in pg["strips"]) for pg in sheet["pages"])
    except (KeyError, TypeError) as exc:
        raise CapsRefused("chart_record_unreadable", what=type(exc).__name__) from None
    return ChartShape(pages)


def check_shape(shape: ChartShape) -> None:
    m = LAYOUT_MAXIMA
    if not shape.pages:
        raise CapsRefused("chart_has_no_pages")
    if len(shape.pages) > m["pages"]:
        raise CapsRefused("chart_beyond_layout_maxima", what="pages", value=len(shape.pages),
                          maximum=m["pages"])
    for k, rows in enumerate(shape.pages, 1):
        if not rows or any(n <= 0 for n in rows):
            raise CapsRefused("chart_page_without_patches", page=k)
        if len(rows) > m["rows"]:
            raise CapsRefused("chart_beyond_layout_maxima", what="rows", page=k,
                              value=len(rows), maximum=m["rows"])
        if max(rows) > m["per_row"]:
            raise CapsRefused("chart_beyond_layout_maxima", what="per_row", page=k,
                              value=max(rows), maximum=m["per_row"])
        if sum(rows) > m["per_page"]:
            raise CapsRefused("chart_beyond_layout_maxima", what="per_page", page=k,
                              value=sum(rows), maximum=m["per_page"])


def page_caps(rows: "tuple[int, ...]", dual: bool = False) -> "tuple[int, int]":
    """(lines, movements) for one page: its need plus its allowance."""
    need = [ALIGN_CYCLE[i] + sum(row_cost(n, dual)[i] for n in rows) for i in (0, 1)]
    longest = max(row_cost(n, dual) for n in rows)
    out = []
    # 4.3.48: every row attempt of the page (its rows, and the two rows read again) may send its
    # BESIDE_RETRIES_PER_ROW automatic second moves
    attempts = len(rows) + ALLOWANCE_ROWS
    for i in (0, 1):
        allow = (ALLOWANCE_ALIGNMENTS * ALIGN_CYCLE[i] + ALLOWANCE_ROWS * longest[i]
                 + CALIBRATION[i] + TILE_READING[i]
                 + math.ceil(ALLOWANCE_FRACTION * need[i])
                 + attempts * BESIDE_RETRIES_PER_ROW * BESIDE_RETRY[i])
        out.append(need[i] + allow)
    return out[0], out[1]


@dataclass(frozen=True)
class Caps:
    lines: int
    moves: int
    shape: ChartShape

    def as_dict(self) -> dict:
        return {"lines": self.lines, "moves": self.moves, "pages": len(self.shape.pages),
                "patches": self.shape.patches,
                "formula": "open + park + calibration + tile + sum(pages: align_cycle + rows "
                           "+ allowance)",
                "allowance": {"fraction": ALLOWANCE_FRACTION, "rows": ALLOWANCE_ROWS,
                              "alignments": ALLOWANCE_ALIGNMENTS,
                              "beside_retries_per_row_attempt": BESIDE_RETRIES_PER_ROW,
                              "calibrations": 1, "tile_readings": 1}}


def caps_for(shape: ChartShape, dual: bool = False) -> Caps:
    """The session caps for a chart of *shape* (CapsRefused only beyond the layout maxima).
    *dual*: the session may read dual rows (each row's UV pass counted, :data:`DUAL_ROW`)."""
    check_shape(shape)
    lines = OPEN[0] + PARK[0] + CALIBRATION[0] + TILE_READING[0]
    moves = OPEN[1] + PARK[1] + CALIBRATION[1] + TILE_READING[1]
    for rows in shape.pages:
        pl, pm = page_caps(rows, dual)
        lines += pl
        moves += pm
    return Caps(lines, moves, shape)


def caps_for_sheet(sheet: dict, dual: bool = False) -> Caps:
    return caps_for(shape_of(sheet), dual)


#: The creep's own step (5 mm), kept with the geometry module's value (a test pins both).
CREEP_STEP = geo.CREEP_STEP


def caps_for_missing(sheet: dict, locs, dual: bool = False) -> Caps:
    """Step 8, resume: the caps of a session that reads only *locs* (the patches a partial
    measurement lacks): the chart's shape with every row cut to its missing patches (rows and
    pages with none left out). A page with nothing missing needs no alignment, so it adds
    nothing. Falls back to the whole chart's caps when nothing is missing (nothing will be
    read anyway)."""
    keep = set(locs)
    try:
        pages = tuple(t for t in (tuple(n for n in (sum(1 for q in st["patches"]
                                                         if q["loc"] in keep)
                                                     for st in pg["strips"]) if n)
                                  for pg in sheet["pages"]) if t)
    except (KeyError, TypeError) as exc:
        raise CapsRefused("chart_record_unreadable", what=type(exc).__name__) from None
    if not pages:
        return caps_for_sheet(sheet, dual)
    return caps_for(ChartShape(pages), dual)
