# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""Patch-by-patch (spot) reading for the table job (build step 7, no UI).

What the job needs besides the table: the row planner (tester 0.6.0 part C's
``sheet_spot_rows``, one row at a time, with the clean seam for strip rows of step 10), the
plausibility check on a reading (part C's ``spot_read``), the reader's failures as ids, the
Measure tab's options mapped to what the table can honour, and the constants of a reading
session (pace, calibration validity, timeouts). Numbers only and ids: NO TEXT FOR A PERSON.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import scan as sc

# ---- constants (each pinned by a test) -------------------------------------------------------

#: part C's plausibility of a spot reading: the reading carries X, Y, Z and its Y (in percent,
#: as ArgyllCMS's .ti3 and the helper's patch_read event give it) lies within this range
PLAUSIBLE_Y = (0.2, 130.0)
#: part C (and APP_DESIGN 6.1): at least this long between the end of a reading and the next
#: move of the arm, so the table is never driven faster than i1Profiler did (1.07 s recorded)
PACE_FLOOR_S = 1.0
#: what a spot patch takes at most, for the calibration check before a row. Was 1.5 s (the
#: tester: "as i1Profiler did it", an M0-only row of S2). i1Profiler's DUAL spot row on the
#: volunteer's table (17 Nov 2026) took 2.01 s a patch (1.94-2.04): I1PROFILER_DUAL_PATCH_S.
#: ChromIQ reads ONE (M0) reading per patch but waits PACE_FLOOR_S after it: the 0.48 s move,
#: the arrival reading, the reading itself (not yet recorded on a table; 0.9 s in the
#: simulator) and the 1.0 s pace come to about 2.4 s, so its own estimate is 2.5 s.
I1PROFILER_DUAL_PATCH_S = 2.0
PATCH_S_ESTIMATE = 2.5
#: S-8: spot rows run from column 0 (the end of marks 1 and 2) on EVERY row, as i1Profiler's spot
#: rows do on the volunteer's table (17 Nov 2026: both rows column 0 -> 23, the move back to
#: column 0 of the next row 2.239 s); only its scan rows are serpentine. True only for the
#: wire-identity tests against tester 0.6.0, whose spot stages were serpentine.
SPOT_ROWS_SERPENTINE = False
#: ArgyllCMS's calibrations last one hour (APP_DESIGN 7); a row is started only with its own
#: estimated time plus this margin left (the helper's rule for a strip row: 2 minutes)
CAL_VALID_S = 3600.0
CAL_MARGIN_S = 120.0
#: the reader's own waits (reader.SpotReader's defaults, named here so the job passes them)
OPEN_TIMEOUT_S = 45.0
READ_TIMEOUT_S = 15.0
#: the model name the helper reports for an i1Pro 2 (ArgyllCMS's inst_name(instI1Pro2),
#: native/instlib/insttypes.c)
I1PRO2_MODEL = "X-Rite i1 Pro 2"
#: one reader chart of one patch for a calibration and the tile reading (tester C1, C2)
CAL_PATCHES = (("1", "A1"),)

ROW_KINDS = ("spot", "strip")

# ---- strip rows (build step 10, round B: a FIRST TRY, off by default) ------------------------
#: NEXT_STEPS 4b / D-7: the most readings one strip row may take until a longer lamp pass is
#: confirmed on a real table: the longest recorded pass (1,190 readings). A row that needs more
#: at 54 mm/s goes faster (a recorded speed), and when no recorded speed keeps it inside, the
#: row is read patch by patch (M-I1IO-DRIVE-STRIP-TOO-LONG). The helper's own cap (2,000) and
#: the allow-list are unchanged.
STRIP_N_MAX = 1190
#: the scan speeds a strip row may use, slowest first (all recorded, scan.py's default 54 first:
#: NEXT_STEPS 4b "the job picks the speed from the chart's patch length (default 54)"). 168 was
#: recorded on the volunteer's table on 17 Nov 2026 (i1Profiler's two rows); it is used only
#: when no slower speed keeps the row within STRIP_N_MAX, and only where every patch window
#: still holds STRIP_MIN_READINGS readings (patches of about 9.7 mm and longer).
STRIP_SPEEDS = (54, 61, 87, 88, 110, 118, 137, 138, 168)
# ---- D-4b: the table's stored white tile values (an option, off by default) ---------------
#: a white tile's reflectance, as a fraction, must lie in this range in every band (the analysis
#: of 17 Nov 2026 found the run of 36 values by this range); anything else is not used
STORED_TILE_RANGE = (0.30, 1.20)
#: the per-band factor (stored value / the table's tile as the instrument read it after its
#: white) must lie in this range: on the real table they differed by 1.3 to 5.2 %; a factor
#: beyond 15 % means the values or the reading are not what this option assumes
STORED_FACTOR_RANGE = (0.85, 1.15)
#: the wavelengths of the stored values (ArgyllCMS's 380-730 nm at 10 nm, the i1Pro 2's grid)
STORED_TILE_WL = tuple(range(380, 731, 10))


def stored_white_factors(stored, tile_percent) -> "tuple[tuple | None, str]":
    """((factor per 10 nm band from 380 to 730 nm), "") or (None, the reason id). *stored*: the
    table's 36 values (fractions); *tile_percent*: the table's tile read by the instrument right
    after its white, 36 values in percent as a .ti3 holds them."""
    import math
    if stored is None or len(stored) != len(STORED_TILE_WL):
        return None, "stored_white_not_readable"
    lo, hi = STORED_TILE_RANGE
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and lo <= v <= hi
               for v in stored):
        return None, "stored_white_not_a_white_tile"
    if tile_percent is None or len(tile_percent) != len(STORED_TILE_WL):
        return None, "stored_white_no_tile_reading"
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 1.0
               for v in tile_percent):
        return None, "stored_white_no_tile_reading"
    f = tuple(s / (t / 100.0) for s, t in zip(stored, tile_percent))
    if not all(STORED_FACTOR_RANGE[0] <= v <= STORED_FACTOR_RANGE[1] for v in f):
        return None, "stored_white_too_far_from_the_reading"
    return f, ""


def factor_at(factors, wl: float) -> float:
    """The factor at any wavelength (linear between the 10 nm bands, the end values beyond)."""
    grid = STORED_TILE_WL
    if wl <= grid[0]:
        return factors[0]
    if wl >= grid[-1]:
        return factors[-1]
    i = int((wl - grid[0]) // 10)
    t = (wl - grid[i]) / 10.0
    return factors[i] * (1 - t) + factors[i + 1] * t


#: readings a patch's window must hold for the patch to be cut (a FIRST TRY value: an 8.9 mm
#: patch at 54 mm/s gets about 12 in its clean middle; fewer means the move ran differently)
STRIP_MIN_READINGS = 5
#: the largest difference of one reading from its window's mean, in any band (reflectance
#: 0..1), for the window to count as one colour (a FIRST TRY value, not from a recording: a
#: window across two printed patches differs by far more)
STRIP_UNIFORMITY_MAX = 0.10


class RowRefused(Exception):
    """A row that cannot be planned (nothing was sent). ``.reason`` is an id."""

    def __init__(self, reason: str, **detail):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


@dataclass(frozen=True)
class PatchTarget:
    sample_id: str
    loc: str
    target: "tuple[int, int]"


@dataclass(frozen=True)
class RowPlan:
    """One row of one page: its patches in the order the arm visits them (spot rows from column
    0 on every row; strip rows serpentine)."""
    page: int                 # 0-based
    index: int                # 0-based row of the page (the side file's strip)
    kind: str                 # "spot" (step 7); "strip" (step 10, round B)
    patches: "tuple[PatchTarget, ...]"
    #: a strip row's scan plan (scan.RowPlan: start, end, speed, readings); None for spot
    scan: "object | None" = None

    @property
    def name(self) -> str:
        """The reader's chart name for this row (``-p <name>``): page and row, 1-based."""
        return f"p{self.page + 1}_row{self.index + 1}"

    def as_dict(self) -> dict:
        return {"page": self.page + 1, "row": self.index + 1, "kind": self.kind,
                "patches": [[p.sample_id, p.loc, list(p.target)] for p in self.patches]}


def plan_row(sheet: dict, page: int, index: int, alignment, front_y=None, kind: str = "spot",
             only_locs=None, dual: bool = False) -> RowPlan:
    """The row's plan. Spot (step 7): part C's ``sheet_spot_rows`` for this row: every patch's
    centre through the alignment (``Alignment.target``: on the aimed sheet, inside the area,
    not beyond the confirmed front), every row from column 0 (the end of marks 1 and 2, the
    largest X) to its last column, as i1Profiler's spot rows run (S-8: not serpentine; only
    scan rows are). *only_locs* keeps only those patches (resume and refinement: the order
    stays the same). A target outside raises geometry's AreaRefused (the caller turns it into
    its id); nothing is sent either way.

    Strip rows (round B): :func:`plan_strip_row`."""
    if kind not in ROW_KINDS:
        raise RowRefused("row_kind_unknown", row_kind=kind)
    if kind == "strip":
        if dual:
            return plan_dual_row(sheet, page, index, alignment, front_y, only_locs)
        return plan_strip_row(sheet, page, index, alignment, front_y, only_locs)
    try:
        st = sheet["pages"][page]["strips"][index]
    except (KeyError, IndexError, TypeError):
        raise RowRefused("row_not_in_chart", page=page + 1, row=index + 1) from None
    pts = []
    for q in st["patches"]:
        u = sc.sheet_table_mm(sheet, q["centre_mm"])
        pts.append(PatchTarget(str(q["sample_id"]), q["loc"],
                               alignment.target(u, f"patch {q['loc']}", run_out_mm=0.5,
                                                front_y=front_y)))
    if SPOT_ROWS_SERPENTINE:            # tester 0.6.0's order (its wire-identity tests only)
        pts.sort(key=lambda t: t.target[0], reverse=(index % 2 == 1))
    else:
        pts.sort(key=lambda t: t.target[0], reverse=True)
    if only_locs is not None:
        keep = set(only_locs)
        pts = [p for p in pts if p.loc in keep]
    return RowPlan(page, index, kind, tuple(pts))


def strip_windows_ok(plan) -> "int | None":
    """The fewest readings any patch of a scan plan gets in its clean middle, or None when a
    window lies outside the reading stream (scan.windows on the plan's own profile)."""
    w = sc.windows(plan, sc.MOTION_START_AFTER_LAMP_S, plan.N)
    if any(i1 - i0 < 1 for i0, i1 in w):
        return None
    return min(i1 - i0 for i0, i1 in w) if w else None


def plan_strip_row(sheet: dict, page: int, index: int, alignment, front_y=None,
                   only_locs=None) -> RowPlan:
    """One row as a STRIP (tester 0.6.0 part C's E2/E3, ``scan.sheet_rows`` for this row): the
    run from just beyond one end of the row to just beyond the other, serpentine as the spot
    rows, at the slowest speed of :data:`STRIP_SPEEDS` that keeps the row within
    :data:`STRIP_N_MAX` readings with :data:`STRIP_MIN_READINGS` in every patch. Refused (the
    caller reads the row patch by patch, and says why):

    * ``strip_only_some_patches``: a resume or a refinement wants only part of the row;
    * ``strip_row_too_long``: no recorded speed keeps it within the readings, or the run with
      its run-in and run-out leaves the measuring area (geometry's own check: the 230 x 320 mm
      sheet's longest row, NEXT_STEPS 4b)."""
    try:
        st = sheet["pages"][page]["strips"][index]
    except (KeyError, IndexError, TypeError):
        raise RowRefused("row_not_in_chart", page=page + 1, row=index + 1) from None
    if only_locs is not None and not {q["loc"] for q in st["patches"]} <= set(only_locs):
        raise RowRefused("strip_only_some_patches", page=page + 1, row=index + 1)
    from . import geometry as geo
    last = None
    for speed in STRIP_SPEEDS:
        try:
            plans = _one_strip(sheet, page, index, alignment, speed, front_y)
        except (geo.AreaRefused, sc.PlanRefused) as exc:
            raise RowRefused("strip_row_too_long", page=page + 1, row=index + 1,
                             log_reason=str(exc)) from None
        last = plans
        fewest = strip_windows_ok(plans)
        if plans.N <= STRIP_N_MAX and fewest is not None and fewest >= STRIP_MIN_READINGS:
            try:
                sc.check_plan(plans, None, front_y)
            except sc.PlanRefused as exc:
                raise RowRefused("strip_row_too_long", page=page + 1, row=index + 1,
                                 log_reason=str(exc)) from None
            pts = tuple(PatchTarget(q.sample_id, q.loc, (int(round(q.xy[0])),
                                                         int(round(q.xy[1]))))
                        for q in plans.patches)
            return RowPlan(page, index, "strip", pts, scan=plans)
    raise RowRefused("strip_row_too_long", page=page + 1, row=index + 1,
                     readings=last.N if last is not None else None, readings_max=STRIP_N_MAX)


# ---- THE DUAL ROW (the i1Pro 2 dual scan on the table, 2026-11-18; A FIRST TRY) ---------------

def dual_windows_ok(lamp, uv) -> "int | None":
    """The fewest readings any patch gets in EITHER pass of a dual row with the dual row's cut
    (``scan.DUAL_EDGE_MM``, each pass's own motion start and first reading), or None when a
    window lies outside a pass's readings."""
    w = sc.windows(lamp, sc.MOTION_START_AFTER_LAMP_S, lamp.N, edge_mm=sc.DUAL_EDGE_MM)
    w += sc.windows(uv, sc.UV_MOTION_START_AFTER_TRIGGER_S, uv.N, edge_mm=sc.DUAL_EDGE_MM,
                    first_reading_s=sc.UV_FIRST_READING_AFTER_TRIGGER_S)
    if any(i1 - i0 < 1 for i0, i1 in w):
        return None
    return min(i1 - i0 for i0, i1 in w) if w else None


def uv_pass_of(lamp) -> "sc.RowPlan":
    """The UV pass of a dual row: the same row, straight back at the same speed (recorded)."""
    pts = [sc.Patch(q.sample_id, q.loc, q.xy, half_mm=q.half_mm) for q in lamp.patches]
    return sc.plan_row(lamp.name + "_uv", lamp.end, lamp.start, lamp.speed, pts,
                       lamp.aperture_mm, dual=True)


def plan_dual_row(sheet: dict, page: int, index: int, alignment, front_y=None,
                  only_locs=None) -> RowPlan:
    """One row as a DUAL row: the lamp pass from just beyond the row's -X end to just beyond its
    +X end and the UV pass straight back, BOTH at the recorded 132 (``scan.DUAL_SPEED``), every
    row in the same direction (as recorded: the UV pass brings the arm back to the row's start).
    Refused, so that the caller reads the row patch by patch with the dual scan and says why:

    * ``strip_only_some_patches``: a resume or a refinement wants only part of the row;
    * ``strip_row_too_long``: the run leaves the measuring area, or it needs more readings than
      the longest UV-LED pass ever recorded (``scan.DUAL_N_MAX``);
    * ``dual_row_patches_too_short``: a patch gets fewer than ``scan.DUAL_MIN_READINGS``
      readings in one of the two passes with the dual row's clean edge."""
    try:
        st = sheet["pages"][page]["strips"][index]
    except (KeyError, IndexError, TypeError):
        raise RowRefused("row_not_in_chart", page=page + 1, row=index + 1) from None
    if only_locs is not None and not {q["loc"] for q in st["patches"]} <= set(only_locs):
        raise RowRefused("strip_only_some_patches", page=page + 1, row=index + 1)
    from . import geometry as geo
    try:
        lamp = _one_strip(sheet, page, index, alignment, sc.DUAL_SPEED, front_y, dual=True)
        sc.check_plan(lamp, None, front_y)
        uv = uv_pass_of(lamp)
        sc.check_plan(uv, None, front_y)
    except (geo.AreaRefused, sc.PlanRefused) as exc:
        raise RowRefused("strip_row_too_long", page=page + 1, row=index + 1,
                         log_reason=str(exc)) from None
    fewest = dual_windows_ok(lamp, uv)
    if fewest is None or fewest < sc.DUAL_MIN_READINGS:
        raise RowRefused("dual_row_patches_too_short", page=page + 1, row=index + 1,
                         fewest=fewest, needed=sc.DUAL_MIN_READINGS)
    pts = tuple(PatchTarget(q.sample_id, q.loc, (int(round(q.xy[0])), int(round(q.xy[1]))))
                for q in lamp.patches)
    return RowPlan(page, index, "strip", pts, scan=lamp)


def _one_strip(sheet, page, index, alignment, speed, front_y, dual: bool = False):
    """scan.sheet_rows for one row (the same targets, ends and serpentine order). *dual*: every
    row from its -X end (a dual row's UV pass brings the arm back there), at the dual speed."""
    along = float(sheet["patch_mm"][1])
    st = sheet["pages"][page]["strips"][index]
    r0, r1 = st["run_mm"]
    ua = sc.sheet_table_mm(sheet, (st["x_mm"], r0))
    ub = sc.sheet_table_mm(sheet, (st["x_mm"], r1))
    a = alignment.target(ua, f"row {index + 1}'s run end", front_y=front_y)
    b = alignment.target(ub, f"row {index + 1}'s run end", front_y=front_y)
    if (a[0] > b[0]) != (False if dual else index % 2 == 1):
        a, b = b, a
    patches = []
    for q in st["patches"]:
        u = sc.sheet_table_mm(sheet, q["centre_mm"])
        patches.append(sc.Patch(str(q["sample_id"]), q["loc"],
                                alignment.target(u, f"patch {q['loc']}", run_out_mm=0.5,
                                                 front_y=front_y),
                                half_mm=along / 2))
    return sc.plan_row(f"p{page + 1}_row{index + 1}", a, b, speed, patches, dual=dual)


def rows_on_page(sheet: dict, page: int) -> int:
    return len(sheet["pages"][page]["strips"])


def plausible(xyz) -> "str | None":
    """None when a spot reading is plausible (part C's rule), else the reason id."""
    if xyz is None:
        return "reading_without_values"
    try:
        vals = [float(v) for v in xyz]
    except (TypeError, ValueError):
        return "reading_without_values"
    if len(vals) != 3:
        return "reading_without_values"
    if not all(math.isfinite(v) for v in vals):
        return "reading_implausible"
    if not PLAUSIBLE_Y[0] <= vals[1] <= PLAUSIBLE_Y[1]:
        return "reading_implausible"
    return None


def row_seconds(n: int) -> float:
    return n * PATCH_S_ESTIMATE + 10.0


# ---- the reader's failures as ids ------------------------------------------------------------

#: the helper's error kinds (native/chartread_helper: cq_emit_error) -> the job's ids
ERROR_KIND_IDS = {
    "no_instrument": "instrument_not_found",
    "read_error": "reading_failed",
    "misread": "reading_failed",
    "coms": "reading_failed",
    "needs_cal": "instrument_asks_for_calibration",
    "cal_failed": "calibration_failed",
    "patch_not_found": "reader_did_not_go_to_patch",
    "chart_unreadable": "reader_chart_refused",
    "chart_refused": "reader_chart_refused",
}
#: words in a no_instrument detail that mean another program has it
BUSY_WORDS = ("busy", "in use", "access", "claim")

#: failures after which the same reader may read the same patch again (it is alive and sits on
#: the patch); every other failure ends the reader, and the row
RETRYABLE = ("reading_failed", "reading_implausible", "reading_without_values",
             "reading_off_target")


def failure_id(message: str, events: "list[dict]", alive: bool) -> "tuple[str, dict]":
    """A ReaderFailed (its plain words, the reader's events so far, whether its process still
    runs) -> (id, detail). The events decide where they can; the words only where the reader
    module says nothing else (a wait that ran out, a call the reader refused)."""
    last = events[-1] if events else {}
    kind = last.get("event")
    # the helper's own last word first: a helper that names its failure and then ends (no
    # instrument, the instrument busy) did not simply die
    if kind != "error" and (not alive or "stopped listening" in message
                            or kind == "helper_gone"):
        return "reader_died", {}
    if kind == "error":
        ek = str(last.get("kind", ""))
        rid = ERROR_KIND_IDS.get(ek, "reader_error")
        detail = str(last.get("detail", ""))
        if ek == "no_instrument" and any(w in detail.lower() for w in BUSY_WORDS):
            rid = "instrument_busy"
        return rid, {"helper_error": ek}
    if kind == "cal_required" and ("instead of a reading" in message
                                   or "calibration was not done" in message):
        return "instrument_asks_for_calibration", {"cond": str(last.get("cond", ""))}
    if kind == "patch_read" and "instead of a reading" in message:
        return "reading_of_another_patch", {"loc": str(last.get("loc", ""))}
    if "did not get ready" in message:
        return "reader_did_not_get_ready", {}
    if message.startswith("no reading of"):
        return "reading_timed_out", {}
    if "without values" in message:
        return "reading_without_values", {}
    if "did not go to patch" in message:
        return "reader_did_not_go_to_patch", {}
    if "calibration was not done" in message:
        return "calibration_not_done", {}
    if "calibration ended with" in message:
        return "calibration_failed", {}
    return "reader_error", {}


def reported_model(events: "list[dict]") -> "str | None":
    for ev in events:
        if ev.get("event") == "instrument" and ev.get("model"):
            return str(ev.get("model"))
    return None


# ---- the Measure tab's options, as far as the table honours them -----------------------------

@dataclass(frozen=True)
class ReadOptions:
    """What the job passes to the reader for spot rows (the helper's own chartread flags, the
    same as when measuring by hand), and what it does itself."""
    suppress_warnings: bool = False      # -S
    high_res: bool = False               # -H
    xrga: str = ""                       # -A <N|A|X|G>; "" = not passed
    save_lab: bool = False               # -l
    save_lab_and_xyz: bool = False       # -L
    no_spectral: bool = False            # -n
    #: -N: the person says a calibration made earlier (by hand, ArgyllCMS keeps it) is good;
    #: the job then starts rows without its own white and the instrument's own request for a
    #: calibration ends the row (instrument_asks_for_calibration)
    skip_initial_calibration: bool = False
    #: -r: read only what the run's partial measurement lacks
    resume: bool = False
    #: round B: "Patch-by-patch mode (-p)" off for a table chart = the rows are read as STRIPS
    #: (a first try, not confirmed on a real table yet; the Measure tab ticks -p for a table
    #: chart by default)
    strip: bool = False

    def reader_args_fields(self) -> "tuple[str, ...]":
        """The field options among :meth:`reader_args` (-H -l -L -n), in that order."""
        return tuple(a for a in self.reader_args() if a in ("-H", "-l", "-L", "-n"))

    def reader_args(self) -> "tuple[str, ...]":
        out = []
        if self.suppress_warnings:
            out.append("-S")
        if self.high_res:
            out.append("-H")
        if self.xrga:
            out += ["-A", self.xrga]
        if self.save_lab:
            out.append("-l")
        if self.save_lab_and_xyz:
            out.append("-L")
        if self.no_spectral:
            out.append("-n")
        return tuple(out)


XRGA_CODES = ("N", "A", "X", "G")

#: options with no meaning on the table: dropped, with the reason (the window greys them)
NO_MEANING = {
    "-c": "the_table_check_picks_its_own_i1pro2",
    "-T": "the_table_knows_where_each_patch_is",
    "-B": "no_meaning_for_spot_readings",
    "-b": "no_meaning_for_spot_readings",
    "-v": "the_reader_always_reports_the_instrument",
}
#: round B: in strip mode these have no meaning for the strip rows (the table-scan mode reads in
#: standard resolution and does its own conversion); dropped for the whole session, so the rows
#: a strip session reads patch by patch match the strip rows' fields
NO_MEANING_STRIP = {
    "-H": "the_strip_reading_has_no_high_resolution",
}
#: round B: refused in strip mode (it would change WHAT is measured and the strip reading cannot
#: honour it): the table-scan conversion applies no XRGA
REFUSED_STRIP = {
    "-A": "xrga_not_with_strip_rows",
}
#: options that would change WHAT is measured and that the table cannot honour: the job does
#: not read with them (a refusal, never silently dropped)
REFUSED = {
    "-F": "i1pro2_refuses_every_filter",
    "-x": "external_values_not_with_the_table",
}
#: options that take a value (the next token)
TAKES_VALUE = ("-c", "-T", "-F", "-A")
#: the Measure tab's other settings and Betas, by name, with what the table does with them
SETTINGS = {
    "aiming_help": ("no_meaning", "the_table_moves_the_instrument"),
    "strip_recognition": ("no_meaning", "no_recogniser_the_table_reads_by_position"),
    "i1pro2_ruler_check": ("no_meaning", "no_ruler_is_read_in_the_arm"),
    "i1pro2_margin_tolerance": ("no_meaning", "no_ruler_is_read_in_the_arm"),
    "i1pro2_lights": ("no_meaning", "the_spot_reader_does_not_use_the_lights"),
    "button_gestures": ("no_meaning", "the_button_is_not_used_on_the_table"),
    "i1pro3_conditions": ("no_meaning", "only_an_i1pro2_is_driven"),
    "i1pro3_lights": ("no_meaning", "only_an_i1pro2_is_driven"),
    "averaging_pass": ("not_built", "a_second_pass_is_filed_by_step_8"),
    "strip_mode": ("first_try", "strip_rows_a_first_try_not_confirmed_on_a_real_table"),
}


@dataclass(frozen=True)
class OptionsReport:
    options: ReadOptions
    used: "tuple[str, ...]" = ()
    no_meaning: "dict" = field(default_factory=dict)      # flag -> reason id
    refused: "dict" = field(default_factory=dict)         # flag -> reason id

    @property
    def ok(self) -> bool:
        return not self.refused


def options_from_chartread_args(tokens) -> OptionsReport:
    """The chartread arguments the Measure tab builds (``MeasureManager._build_args`` and its
    extra options) -> what the table job honours. The base name (the last token without a
    dash) is ignored: the job names its own reader charts. An unknown flag is refused (never
    passed to the helper unseen)."""
    toks = [str(t) for t in tokens]
    kw: dict = {}
    used, no_meaning, refused = [], {}, {}
    patch_by_patch = False
    i = 0
    while i < len(toks):
        t = toks[i]
        val = None
        if t in TAKES_VALUE and i + 1 < len(toks):
            val = toks[i + 1]
            i += 1
        i += 1
        if not t.startswith("-"):
            continue                       # the chart's base name
        if t == "-p":
            patch_by_patch = True
            continue
        if t.startswith("-x"):
            refused[t] = REFUSED["-x"]
        elif t in REFUSED:
            refused[t] = REFUSED[t]
        elif t in NO_MEANING:
            no_meaning[t] = NO_MEANING[t]
        elif t == "-S":
            kw["suppress_warnings"] = True
            used.append(t)
        elif t == "-H":
            kw["high_res"] = True
            used.append(t)
        elif t == "-A":
            if val in XRGA_CODES:
                kw["xrga"] = val
                used.append(f"-A {val}")
            else:
                refused[t] = "xrga_value_unknown"
        elif t == "-l":
            kw["save_lab"] = True
            used.append(t)
        elif t == "-L":
            kw["save_lab_and_xyz"] = True
            used.append(t)
        elif t == "-n":
            kw["no_spectral"] = True
            used.append(t)
        elif t == "-N":
            kw["skip_initial_calibration"] = True
            used.append(t)
        elif t == "-r":
            kw["resume"] = True
            used.append(t)
        else:
            refused[t] = "option_unknown_to_the_table_job"
    if not patch_by_patch:
        # round B: strip rows (a first try); what the strip reading cannot honour is said
        kw["strip"] = True
        used.append("strip")
        for flag, why in NO_MEANING_STRIP.items():
            if flag == "-H" and kw.pop("high_res", False):
                used.remove("-H")
                no_meaning["-H"] = why
        if kw.get("xrga"):
            used[:] = [u for u in used if not u.startswith("-A ")]
            kw.pop("xrga")
            refused["-A"] = REFUSED_STRIP["-A"]
    return OptionsReport(ReadOptions(**kw), tuple(used), no_meaning, refused)
