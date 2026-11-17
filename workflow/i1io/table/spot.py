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
#: what a spot patch takes at most, for the calibration check before a row (tester: "about
#: 1.5 s per patch as i1Profiler did it")
PATCH_S_ESTIMATE = 1.5
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
    """One row of one page: its patches in the order the arm visits them (serpentine)."""
    page: int                 # 0-based
    index: int                # 0-based row of the page (the side file's strip)
    kind: str                 # "spot" (step 7); "strip" is step 10's
    patches: "tuple[PatchTarget, ...]"

    @property
    def name(self) -> str:
        """The reader's chart name for this row (``-p <name>``): page and row, 1-based."""
        return f"p{self.page + 1}_row{self.index + 1}"

    def as_dict(self) -> dict:
        return {"page": self.page + 1, "row": self.index + 1, "kind": self.kind,
                "patches": [[p.sample_id, p.loc, list(p.target)] for p in self.patches]}


def plan_row(sheet: dict, page: int, index: int, alignment, front_y=None, kind: str = "spot",
             only_locs=None) -> RowPlan:
    """The row's plan. Spot (step 7): part C's ``sheet_spot_rows`` for this row: every patch's
    centre through the alignment (``Alignment.target``: on the aimed sheet, inside the area,
    not beyond the confirmed front), sorted along X, serpentine (every second row from the
    other end, as i1Profiler drives rows). *only_locs* keeps only those patches (resume and
    refinement: the order stays the serpentine one). A target outside raises geometry's
    AreaRefused (the caller turns it into its id); nothing is sent either way.

    Strip rows are step 10: ``kind="strip"`` is refused here, so a strip row can never reach
    the table through this planner until it is built and reviewed (the seam: a strip planner
    returns a RowPlan of kind "strip" built by ``scan.sheet_rows``)."""
    if kind not in ROW_KINDS:
        raise RowRefused("row_kind_unknown", row_kind=kind)
    if kind == "strip":
        raise RowRefused("strip_rows_not_built")
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
    pts.sort(key=lambda t: t.target[0], reverse=(index % 2 == 1))
    if only_locs is not None:
        keep = set(only_locs)
        pts = [p for p in pts if p.loc in keep]
    return RowPlan(page, index, kind, tuple(pts))


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
    "-p": "spot_is_the_table_s_only_reading_for_now",
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
    "strip_mode": ("not_built", "strip_rows_not_built"),
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
        no_meaning["strip"] = "strip_rows_not_built_spot_is_used"
    return OptionsReport(ReadOptions(**kw), tuple(used), no_meaning, refused)
