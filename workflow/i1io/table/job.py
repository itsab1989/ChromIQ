# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The table JOB: the steps of one START on an i1iO 2 with an i1Pro 2 (build step 6, no UI).

A state machine a later window drives step by step, and that runs headless against the
simulator. It is the tester program's part C (chromiq-i1io-session 0.6.0, ``i1io_part_c.py``)
rewritten for the app, with every reviewed safety setting carried over:

  open        identity (the chart names an i1iO 2 with an i1Pro 2; USB 0971:2004, exactly one,
              the recorded descriptors; exactly one 0971:2000 instrument and no other), the
              opening, the table's state: warm / cold / other
  start_up    the recorded start-up of a just-switched-on table (``;i02c``, COLD_STEP: its
              three gates and its one-shot are the table module's, unchanged)
  park        the recorded homing at rest (part B's b_home, needs-conditions as part C)
  align       part C's D1: the recorded way out to the alignment start, the arm let go (f3, f1),
              the person's three aims read with p1, ``fit_alignment`` (order, mirror, turn,
              distances, corner, area), which rows fit (``page_fit``), the front-zone decision
  creep       part C's DZ: feel forward into the front zone in steps of at most 5 mm; the
              furthest clean arrival is the confirmed-Y limit for the rest of the sitting
  check_move  part C's D2: the one computed move to mark 3
  home        part C's F: the recorded end of a job from where the arm stands
  close       sends nothing: lets go of the USB connection, writes the results

Every step answers a :class:`StepResult`: ``ok``, a named refusal (nothing unsafe happened, the
sitting goes on), a named stop (nothing more is ever sent), or ``needs_confirmation`` with what
the person must confirm. A confirmation is NEVER given by the job itself: the caller passes the
person's answer to :meth:`TableJob.answer`, one of the listed choices, for the confirmation the
job is waiting for; nothing has a default. Every result carries the TRUE last-read state (only the
table's answers count), whether a movement may be unfinished, whether a strip move may be
pending, and which way back applies (:class:`WayBack`), so the later window can say the right
thing. NO TEXT FOR A PERSON IS MADE HERE: reasons and ways back are ids.

The wire: every line still goes through ``Table._write`` with part C's gate (lines.py) and the
caps, now DERIVED FROM THE CHART (caps.py). For the stages the tester has, the job sends byte for
byte what tester 0.6.0 sends in the same situation (tests/i1io_table/test_job_wire_identity.py).

Nothing in the app imports this yet (tests/test_i1io_table_not_reached_by_the_app.py).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import caps as cp
from . import geometry as geo
from . import lines as cl
from . import scan as sc
from . import session_table as tbl
from . import usb_system as us
from .diagnostics import Diagnostics
from .session_table import Doubt, Stopped

JOB_VERSION = "step6-1"


class Kind:
    OK = "ok"
    REFUSED = "refused"
    STOPPED = "stopped"
    NEEDS = "needs_confirmation"


class Confirm:
    """What a person must confirm; each with its own choices (never a default)."""
    START_UP = "start_up"            # tester ASK_COLD: send the recorded start-up now?
    GO = "go"                        # the stage offer: run this step now (hands off the arm)?
    SHEET_LAID = "sheet_laid"        # ASK_SHEET_LAID: the sheet lies as described, nothing else
    ARM_FELT = "arm_felt"            # ASK_OUT_TOUCH: the free arm at the alignment start
    AIMED = "aimed"                  # the sight sits on mark n (one per mark)
    FRONT_CHOICE = "front_choice"    # back (lay it further back) or go on (feel forward)
    FRONT_YES = "front_yes"          # FRONT_YES: go on needs its own yes
    FIRST_VISIT = "first_visit"      # a move into a part no recording drove the arm to
    MARKER = "pending_marker"        # a strip move may still wait: the table was switched off?


CHOICES = {
    Confirm.START_UP: ("yes", "i1profiler"),
    Confirm.GO: ("yes", "back"),
    Confirm.SHEET_LAID: ("yes", "stop"),
    Confirm.ARM_FELT: ("free", "holds", "not sure", "skip"),
    Confirm.AIMED: ("aimed", "stop"),
    Confirm.FRONT_CHOICE: ("back", "go on"),
    Confirm.FRONT_YES: ("yes", "no"),
    Confirm.FIRST_VISIT: ("yes", "no"),
    Confirm.MARKER: ("switched off and on", "stop"),
}


#: the tester's names for the answers in a result block (the analysis script reads them)
BLOCK_LABEL = {Confirm.FRONT_CHOICE: "front part", Confirm.FRONT_YES: "front part, yes",
               Confirm.FIRST_VISIT: "first visit", Confirm.SHEET_LAID: "on the table"}


class WayBack:
    """Which way back applies (the later window words each; part C's where_text order)."""
    NONE = "none"                                   # nothing was moved, or at rest and held
    HOME_OFFERED = "home_offered"                   # out on the table, known: the homing step
    OPEN_I1PROFILER_ONCE = "open_i1profiler_once"   # where the arm stands is known or not, but
                                                    # this job sends nothing more
    SWITCH_OFF_UNFINISHED = "switch_off_unfinished"     # a movement never reported finished
    SWITCH_OFF_PENDING = "switch_off_pending"       # a strip move may still wait for the lamp
    LINK_LOST_REPLUG = "link_lost_replug"           # lost link, nothing waiting
    LINK_LOST_SWITCH_OFF_FIRST = "link_lost_switch_off_first"   # lost link, something may wait
    COLD_NOT_STARTED = "cold_not_started"           # a just-switched-on table, start-up not sent
    COLD_WAY_OUT = "cold_way_out"                   # the start-up was sent and did not finish


@dataclass(frozen=True)
class TableState:
    """The TRUE state, from what the table last answered."""
    table: "str | None"                     # cold / warm / homed / free_out / b_done / ...
    last_read: "tuple[int, int] | None"
    last_read_t: "float | None"
    position_now: "tuple[int, int] | None"  # read after the last movement (None: not read)
    at_rest: bool
    arm_free: "bool | None"
    mode_on: bool
    movement_may_be_unfinished: bool
    strip_move_may_be_pending: bool
    link_lost: bool
    sending_closed: bool
    lines_sent: int
    moves_sent: int
    front_y: "int | None"
    only_homing: bool


@dataclass(frozen=True)
class StepResult:
    step: str
    kind: str
    reason: str = ""
    state: "TableState | None" = None
    way_back: str = WayBack.NONE
    confirm: "str | None" = None
    choices: "tuple[str, ...]" = ()
    detail: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.kind == Kind.OK


@dataclass(frozen=True)
class Ask:
    kind: str
    detail: dict = field(default_factory=dict)


class StageFailed(Exception):
    """A clean failure: nothing pending, the arm read where it stands (or never moved)."""

    def __init__(self, reason: str, **detail):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


class PersonStopped(Exception):
    """The person chose not to go on (a clean stop; the sitting goes on)."""

    def __init__(self, reason: str, **detail):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


#: part C's per-stage runs, per page (the tester's max_runs per sitting, now per sheet laid)
MAX_RUNS = {"park": 8, "d1": 5, "dz": 3, "d2": 3, "f": 8}
#: the steps and the tester's stage key each writes its result block under
STAGE_KEY = {"park": "park", "align": "d1", "creep": "dz", "check_move": "d2", "home": "f"}
#: the step caps the tester used for its own stages (lines, movements)
DZ_CAPS = cp.CREEP
D1_CAPS = (8, 0)
D2_CAPS = (4, 1)

# The recorded part B steps part C uses, each allowed from the states part C leaves (C_HOME:
# the homing only from "warm", "homed", "b_done": the needs-conditions before homing).
_B = {s.key: s for s in tbl.B_STEPS}
C_HOME = replace(_B["b_home"], needs=("warm", "homed", "b_done"))
C_ALIGN = _B["b_align"]

#: which Doubt reasons (the table module's words) get which stop id; the first match wins
_DOUBT_IDS = (
    (tbl.LINK_FAILED, "link_lost"),
    ("no answer to", "table_did_not_answer"),
    ("the table refused", "table_refused_a_line"),
    ("the program reached its limit of lines", "session_line_cap"),
    ("the program reached its limit of movements", "session_movement_cap"),
    ("the step '", "step_cap"),
    ("not sending: ", "sending_closed"),
    ("the table answered a0 with", "table_state_unknown"),
    ("the table answered a1 with", "not_the_recorded_table"),
    ("the table answered k2 with", "not_the_recorded_table"),
    ("f4 answered", "mode_flag_unexpected"),
    ("the table sent something nobody asked for", "table_sent_unasked"),
    ("the table keeps sending", "table_sent_unasked"),
    ("the start-up", "start_up_out_of_order"),
    ("the free arm was not inside", "free_arm_not_in_box"),
    ("after m1", "arm_not_where_m1_puts_it"),
    ("a scan move may be pending", "strip_move_may_be_pending"),
)


def doubt_id(reason: str) -> str:
    for prefix, rid in _DOUBT_IDS:
        if reason.startswith(prefix) or (prefix in ("the step '",) and prefix in reason):
            return rid
    if " took " in reason and "outside" in reason:
        return "movement_outside_time_window"
    if "the arm reports" in reason or "the arm reads" in reason:
        return "arm_not_where_expected"
    if "status" in reason:
        return "table_answered_a_status"
    return "table_answer_unexpected"


#: AlignmentRefused reasons (geometry's words) -> ids; detail keeps the numbers
_ALIGN_IDS = (
    ("a mark or a position reading is not a finite number", "aims_not_numbers"),
    ("the sheet's three marks lie on one line", "sheet_marks_on_one_line"),
    ("two of the aimed positions are less than 1 cm apart", "aims_not_moved"),
    ("the marks were aimed in another order", "aims_order_or_mirrored"),
    ("the sheet seems to be turned", "sheet_turned"),
    ("marks 1 and 2 are", "aims_distance_1_2"),
    ("marks 2 and 3 are", "aims_distance_2_3"),
    ("the corner at mark 2", "aims_corner_not_square"),
    ("mark 1 must be", "aims_mark_1_not_top_left"),
    ("mark ", "aims_outside_area"),
)


def alignment_id(reason: str) -> str:
    for prefix, rid in _ALIGN_IDS:
        if reason.startswith(prefix):
            return rid
    return "alignment_refused"


def area_id(reason: str) -> str:
    if "front part of the table further than this sitting has confirmed" in reason:
        return "target_beyond_confirmed_front"
    if "swept" in reason or "rectangle" in reason:
        return "path_leaves_area"
    if "outside the aimed marks" in reason:
        return "target_off_sheet"
    return "target_outside_area"


def _near(p, q, d=5) -> bool:
    return p is not None and abs(p[0] - q[0]) <= d and abs(p[1] - q[1]) <= d


def _rect_contains(r, p) -> bool:
    (a, b) = r
    return (min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def _beyond_mm(a, b) -> float:
    worst = 0.0
    for p in ((a[0], a[1]), (b[0], b[1]), (a[0], b[1]), (b[0], a[1])):
        if any(box.contains(p) for box in geo.DRIVEN):
            continue
        dmin = min(max(box.xmin - p[0], 0, p[0] - box.xmax) + max(box.ymin - p[1], 0,
                                                                   p[1] - box.ymax)
                   for box in geo.DRIVEN)
        worst = max(worst, dmin / 10.0)
    return worst


def page_fit(sheet: dict, page: int, al: geo.Alignment) -> dict:
    """Part C's page check after the aims (nothing moves): which spot targets and which strip
    rows of the page lie inside the area, and how far the sheet reaches into the front zone.
    Numbers only (the tester's words are the later window's)."""
    area = geo.CAP_AREA
    strips = sheet["pages"][page]["strips"]
    spot_pts, run_pts = [], []
    spot_out_rows, rows_out_list = [], []
    spot_out = rows_out = 0
    for k, st in enumerate(strips, 1):
        for q in st["patches"]:
            u = sc.sheet_table_mm(sheet, q["centre_mm"])
            p = al.to_table(u)
            spot_pts.append(p)
            if not (area.contains(p) and al.on_sheet(u, 0.5)):
                spot_out += 1
                if k not in spot_out_rows:
                    spot_out_rows.append(k)
        ends = []
        for r in st["run_mm"]:
            p = al.to_table(sc.sheet_table_mm(sheet, (st["x_mm"], r)))
            ends.append(p)
            run_pts.append(p)
        if not all(area.contains(p) for p in ends):
            rows_out += 1
            rows_out_list.append(k)

    def over(pts):
        return {"left": max(p[0] for p in pts) - area.xmax,
                "right": area.xmin - min(p[0] for p in pts),
                "back": area.ymin - min(p[1] for p in pts),
                "front": max(p[1] for p in pts) - area.ymax}
    inside = [p for p in spot_pts + run_pts + [tuple(r) for r in al.readings] if area.contains(p)]
    front_need = max((p[1] for p in inside), default=geo.MEASURING_AREA.ymax)
    front_need = front_need if front_need > geo.MEASURING_AREA.ymax else None
    front_spot = sum(1 for p in spot_pts if area.contains(p) and geo.in_front_zone(p))
    front_rows = sum(1 for st in strips
                     if any(geo.in_front_zone(al.to_table(sc.sheet_table_mm(sheet, (st["x_mm"],
                                                                                    r))))
                            for r in st["run_mm"]))
    return {"spot_outside": spot_out, "spot_total": len(spot_pts), "rows_outside": rows_out,
            "rows_total": len(strips), "over_spot": over(spot_pts), "over_rows": over(run_pts),
            "front_need": front_need, "front_spot": front_spot, "front_rows": front_rows,
            "spot_outside_rows": spot_out_rows, "rows_outside_list": rows_out_list}


CHART_TABLE = "i1iO 2"
CHART_HEAD = "i1Pro 2"


class TableJob:
    """One START on the table. Steps are methods; each returns a StepResult. A step that needs
    a person's confirmation returns ``needs_confirmation``; :meth:`answer` continues it."""

    def __init__(self, sheet: dict, page: int = 0, *, run=None, stamp: "str | None" = None,
                 folder: "Path | None" = None, open_transport=None, preflight=None,
                 other_program=None):
        self.sheet = sheet
        self.page = int(page)
        self.run, self.stamp = run, stamp
        if run is not None and stamp is not None:
            folder = run.i1io_table_session_dir(stamp)
            self.diag = Diagnostics(folder, run.i1io_table_log(stamp))
        else:
            self.diag = Diagnostics(folder)
        self._open_transport = open_transport or tbl.open_table
        self._preflight = preflight or us.preflight
        self._other_program = other_program
        self.d: "tbl.Table | None" = None
        self.transport = None
        self.caps: "cp.Caps | None" = None
        self.phase = "new"            # new, open, closed
        self.alignment: "geo.Alignment | None" = None
        self.front_need: "int | None" = None
        self.fit: "dict | None" = None
        self.driven: "list[tuple]" = []
        self.worked: "set[str]" = set()
        self.runs: "dict[tuple[int, str], int]" = {}
        self.only_home = False
        self.notes: "list[tuple[str, str]]" = []
        self._gen = None
        self._gen_step: "str | None" = None
        self._pending: "Ask | None" = None
        self._block: "dict | None" = None
        self._pause_stop = False
        self.preflight_seen: "us.Preflight | None" = None
        self.diag.log("INFO", f"ChromIQ table job {JOB_VERSION} (table module "
                              f"{tbl.TOOL_NAME} {tbl.TOOL_VERSION}); page {self.page + 1}")

    # ---- the state, from the table's answers only ------------------------------------------
    def at_rest(self) -> bool:
        d = self.d
        if d is None:
            return False
        p = d.position_now
        return (p is not None and not d.motion_unconfirmed and d.arm_free is False
                and tbl.REST_GUARD.contains(p) and not d.mode_on)

    def unread_rest(self) -> bool:
        d = self.d
        return d is not None and d.motions_sent == d.cold_motions and d.state == "warm"

    def parked(self) -> bool:
        """Right after the job's own park (the recorded s0 p0 i1 s0 from rest, finished in its
        window): at rest by the reading before the homing; the next step's own homing reads it
        again before anything moves (HOME_FIRST's p0 in START_GUARD)."""
        d = self.d
        return (d is not None and d.state == "homed" and not d.motion_unconfirmed
                and d.last_move == ("home", True) and d.position_now is None
                and d.before_move is not None and tbl.START_GUARD.contains(d.before_move)
                and d.arm_free is False and not d.mode_on)

    def out_known(self) -> bool:
        d = self.d
        if d is None:
            return False
        p = d.position_now
        return p is not None and not d.motion_unconfirmed and not self.at_rest()

    def front_reached(self) -> int:
        return geo.areas(self.d.front_y if self.d is not None else None)[0].ymax

    def state(self) -> TableState:
        d = self.d
        if d is None:
            return TableState(None, None, None, None, False, False, False, False, False, False,
                              self.phase == "closed", 0, 0, None, self.only_home)
        pending = (d.closed_reason == "a scan move may be pending" or (
            d.motion_unconfirmed and bool(d.last_move) and d.last_move[0] == "scan move"))
        return TableState(d.state, d.last_read, d.last_read_t, d.position_now, self.at_rest(),
                          d.arm_free, d.mode_on, bool(d.motion_unconfirmed), pending,
                          d.link_lost_at is not None, d.closed_reason is not None,
                          d.lines_sent, d.motions_sent, getattr(d, "front_y", None),
                          self.only_home)

    def way_back(self) -> str:
        """Part C's where_text, as ids, from the table's answers only."""
        d = self.d
        if d is None:
            return WayBack.NONE
        st = self.state()
        lost = st.link_lost
        if d.state == "cold" or (d.start_up_sent and not d.cold_done):
            return WayBack.COLD_NOT_STARTED if not d.start_up_sent else (
                WayBack.LINK_LOST_SWITCH_OFF_FIRST if lost else WayBack.COLD_WAY_OUT)
        if st.strip_move_may_be_pending:
            return WayBack.LINK_LOST_SWITCH_OFF_FIRST if lost else WayBack.SWITCH_OFF_PENDING
        if st.movement_may_be_unfinished:
            return WayBack.LINK_LOST_SWITCH_OFF_FIRST if lost else WayBack.SWITCH_OFF_UNFINISHED
        if lost:
            return WayBack.LINK_LOST_REPLUG
        p = d.position_now
        if d.motions_sent == 0 and p is None:
            return WayBack.NONE
        if self.parked():
            return WayBack.NONE
        if p is None:
            return WayBack.OPEN_I1PROFILER_ONCE
        if tbl.REST_GUARD.contains(p) and d.arm_free is False:
            return WayBack.OPEN_I1PROFILER_ONCE if d.mode_on else WayBack.NONE
        if d.closed_reason is None and self.phase == "open" and self._ready("home") is None:
            return WayBack.HOME_OFFERED
        return WayBack.OPEN_I1PROFILER_ONCE

    # ---- results ---------------------------------------------------------------------------
    def _result(self, step: str, kind: str, reason: str = "", **detail) -> StepResult:
        return StepResult(step, kind, reason, self.state(), self.way_back(), detail=detail)

    def _needs(self, step: str, ask: Ask) -> StepResult:
        return StepResult(step, Kind.NEEDS, "", self.state(), self.way_back(), ask.kind,
                          CHOICES[ask.kind], dict(ask.detail))

    # ---- driving a step ----------------------------------------------------------------------
    def _begin(self, step: str, gen) -> StepResult:
        if self._gen is not None:
            return self._result(step, Kind.REFUSED, "another_step_waits_for_a_confirmation",
                                waiting_step=self._gen_step,
                                waiting_for=self._pending.kind if self._pending else None)
        self._gen, self._gen_step, self._pending = gen, step, None
        return self._drive(None)

    def answer(self, kind: str, value: str) -> StepResult:
        """The person's answer to the confirmation the job is waiting for."""
        step = self._gen_step or "none"
        if self._gen is None or self._pending is None:
            return self._result(step, Kind.REFUSED, "nothing_waits_for_a_confirmation")
        if kind != self._pending.kind:
            return self._result(step, Kind.REFUSED, "not_the_confirmation_asked_for",
                                asked=self._pending.kind, given=kind)
        if value not in CHOICES[kind]:
            return self._result(step, Kind.REFUSED, "not_one_of_the_choices",
                                asked=self._pending.kind, choices=list(CHOICES[kind]))
        self.notes.append((f"{step}: {kind}", value))
        self.diag.log("ANSWER", f"{step}: {kind} -> {value}")
        if self._block is not None:
            self._block["answers"].append((BLOCK_LABEL.get(kind, kind), value))
        self._pending = None
        return self._drive(value)

    def cancel(self) -> StepResult:
        """The Ctrl-C equivalent: nothing more is ever sent. While a line is on its way, it is
        written to the end and its answers read (the table module never cuts a line in half);
        at a confirmation, the job ends at once."""
        step = self._gen_step or "cancel"
        if self.d is not None:
            self.d.request_stop()
        if self._gen is not None and self._pending is not None:
            gen, self._gen, self._pending = self._gen, None, None
            try:
                gen.close()
            except BaseException:         # noqa: BLE001
                pass
            if self.d is not None:
                self.d.close_for_sending("stopped by you")
            res = self._result(step, Kind.STOPPED, "cancelled_by_person")
            self._end_block(res)
            self._gen_step = None
            return res
        if self.d is not None and self._gen is None:
            self.d.close_for_sending("stopped by you")
        return self._result(step, Kind.STOPPED, "cancelled_by_person")

    def stop_at_next_pause(self) -> None:
        """Part C's Enter between two creep steps: a clean stop at the next pause."""
        self._pause_stop = True

    def _drive(self, value) -> StepResult:
        step = self._gen_step
        try:
            ask = self._gen.send(value)
        except StopIteration as done:
            self._gen = self._gen_step = None
            res = self._result(step, Kind.OK, "", **(done.value or {}))
            self._end_block(res)
            return res
        except BaseException as exc:      # noqa: BLE001 - every way a step can end
            self._gen = self._gen_step = None
            res = self._from_exception(step, exc)
            self._end_block(res)
            if isinstance(exc, KeyboardInterrupt):
                raise
            return res
        self._pending = ask
        return self._needs(step, ask)

    def _from_exception(self, step: str, exc: BaseException) -> StepResult:
        d = self.d
        if isinstance(exc, StageFailed):
            res = self._result(step, Kind.REFUSED, exc.reason, **exc.detail)
        elif isinstance(exc, PersonStopped):
            res = self._result(step, Kind.REFUSED, exc.reason, by_person=True, **exc.detail)
        elif isinstance(exc, geo.AlignmentRefused):
            res = self._result(step, Kind.REFUSED, alignment_id(str(exc)), log_reason=str(exc))
        elif isinstance(exc, (geo.AreaRefused, sc.PlanRefused)):
            res = self._result(step, Kind.REFUSED, area_id(str(exc)), log_reason=str(exc))
        elif isinstance(exc, tbl.MoveOutside):
            d.close_for_sending(str(exc))
            res = self._result(step, Kind.STOPPED, "movement_outside_time_window",
                               took=round(exc.took, 3), window=(exc.lo, exc.hi))
        elif isinstance(exc, Doubt):
            rid = doubt_id(str(exc))
            if d is not None and d.link_lost_at is not None:
                rid = "link_lost"
            res = self._result(step, Kind.STOPPED, rid, log_reason=str(exc))
        elif isinstance(exc, (Stopped, KeyboardInterrupt)):
            if d is not None:
                d.close_for_sending("stopped by you")
            res = self._result(step, Kind.STOPPED, "cancelled_by_person")
        else:
            if d is not None:
                d.close_for_sending(f"an unexpected error ({type(exc).__name__})")
            res = self._result(step, Kind.STOPPED, "unexpected_error",
                               error=type(exc).__name__)
        if res.kind == Kind.REFUSED and d is not None and (d.motion_unconfirmed
                                                           or d.closed_reason):
            res = replace(res, kind=Kind.STOPPED)
        return res

    # ---- result blocks (the tester's RESULT blocks, same keys) -------------------------------
    def _start_block(self, step: str) -> None:
        key = STAGE_KEY.get(step)
        if key is None:
            self._block = None
            return
        n = sum(v for (pg, k), v in self.runs.items() if k == key)   # this run counted already
        d = self.d
        self._block = {"stage": key, "run": n, "page": self.page + 1, "verdict": "", "why": "",
                       "folder": f"{key}-{n}", "lines_before": d.lines_sent,
                       "moves_before": d.motions_sent, "position_before": d.position_now,
                       "t_start": round(d.t.now(), 3), "answers": [], "data": {}}
        self.diag.stage_dir(key, n)
        d.log("STAGE", f"start {key} run {n}")

    def _end_block(self, res: StepResult) -> None:
        b, self._block = self._block, None
        if b is None or self.d is None:
            return
        d = self.d
        verdict = {Kind.OK: "worked", Kind.STOPPED: "stopped"}.get(res.kind, "failed cleanly")
        if res.kind == Kind.REFUSED and res.detail.get("by_person"):
            verdict = "stopped by you (clean)"
        b.update({"verdict": verdict, "why": res.reason, "lines_after": d.lines_sent,
                  "moves_after": d.motions_sent, "position_after": d.position_now,
                  "last_read": d.last_read, "arm_free": d.arm_free, "mode_on": d.mode_on,
                  "movement_unconfirmed": d.motion_unconfirmed, "t_end": round(d.t.now(), 3),
                  "front_zone_reached_y": d.front_y, "way_back": res.way_back,
                  "state": {k: v for k, v in res.state.__dict__.items()}})
        if res.kind == Kind.OK and b["stage"] in ("d1", "dz", "d2", "f", "park"):
            self.worked.add(b["stage"])
        self.diag.block(b)

    # ---- the opening -------------------------------------------------------------------------
    def open(self) -> StepResult:
        if self.phase != "new":
            return self._result("open", Kind.REFUSED, "already_opened")
        return self._begin("open", self._open())

    def _unacknowledged_markers(self) -> "list[Path]":
        if self.run is None:
            return []
        return [m for m in self.run.i1io_table_pending_markers()
                if not m.with_suffix(".acknowledged.json").exists()]

    def _open(self):
        sheet = self.sheet
        # 1. a strip move that may still wait (a marker from an earlier START): the person
        #    says the table was switched off and on since; the marker is kept, acknowledged
        markers = self._unacknowledged_markers()
        if markers:
            ans = yield Ask(Confirm.MARKER, {"markers": len(markers)})
            if ans != "switched off and on":
                raise PersonStopped("pending_marker_not_cleared", markers=len(markers))
            for m in markers:
                try:
                    m.with_suffix(".acknowledged.json").write_text(
                        json.dumps({"acknowledged_by_person": "switched off and on"}),
                        encoding="utf-8")
                except OSError:
                    raise StageFailed("pending_marker_not_writable") from None
        # 2. the chart: an i1iO 2 with an i1Pro 2 (its own record; nothing is opened yet)
        if sheet.get("table_model") != CHART_TABLE or sheet.get("head_model") != CHART_HEAD:
            raise StageFailed("chart_not_for_i1io2_with_i1pro2",
                              table=sheet.get("table_model"), head=sheet.get("head_model"))
        try:
            self.caps = cp.caps_for_sheet(sheet)
        except cp.CapsRefused as exc:
            raise StageFailed(exc.reason, **exc.detail) from None
        if not 0 <= self.page < len(self.caps.shape.pages):
            raise StageFailed("page_not_in_chart", page=self.page + 1)
        self.diag.log("INFO", "caps derived from the chart: " + json.dumps(self.caps.as_dict()))
        # 3. the system's own lists (read only): the instrument, who holds the table, i1Profiler
        pf = self._preflight()
        self.preflight_seen = pf
        self.diag.log("INFO", "before opening: " + json.dumps(pf.as_dict(), default=str))
        if pf.system == "windows" and pf.table_driver.state != "libusb0":
            # the owner's ruling: on Windows the table is reached like ArgyllCMS's instruments,
            # through libusb-win32, which only the person's explicit choice installs for it
            raise StageFailed("driver_not_installed_for_table",
                              driver_state=pf.table_driver.state, **pf.table_driver.detail)
        if pf.instrument.state != "ok":
            raise StageFailed(f"instrument_{pf.instrument.state}", **pf.instrument.detail)
        if pf.i1profiler is True:
            raise StageFailed("i1profiler_running")
        if pf.holders.state == "held":
            raise StageFailed("table_held_by_another_program", **pf.holders.detail)
        if pf.holders.state == "kernel_driver_bound":
            raise StageFailed("table_held_by_a_kernel_driver", **pf.holders.detail)
        if self._other_program is None:
            self._other_program = lambda system=pf.system: us.i1profiler_running(system)
        # 4. the USB opening: ChromIQ's own library only; nothing sent before the descriptors
        try:
            self.transport = self._open_transport()
        except tbl.NotAvailable as exc:
            raise StageFailed("usb_open_refused", message_id=getattr(exc, "message_id", ""),
                              problem=getattr(exc, "problem", "")) from None
        except tbl.TransportError as exc:
            raise StageFailed("usb_open_failed", error=type(exc).__name__) from None
        self.diag.log("INFO", tbl.usb_summary(self.transport))
        d = tbl.Table(self.transport, log=self.diag.log)
        self.d = d
        self.phase = "open"
        # part C's gate and caps are in place before the first line of the opening
        d.part = "C"
        d.front_y = None
        d.creep = False
        d.c_gate = cl.make_gate(d)
        d.c_caps = (self.caps.lines, self.caps.moves)
        if hasattr(self.transport, "gate"):
            self.transport.gate = cl.wire_gate
        d._touch_out = lambda: "asked after the step"
        state = d.opening()
        out = {"table": state, "system": pf.system}
        if pf.system == "windows":
            out["table_driver"] = "driver_installed"
        return out

    # ---- the start-up of a just-switched-on table ----------------------------------------------
    def start_up(self) -> StepResult:
        why = self._sending_ready()
        if why:
            return self._result("start_up", Kind.REFUSED, why)
        if self.d.state != "cold" or self.d.start_up_sent:
            return self._result("start_up", Kind.REFUSED, "table_not_just_switched_on")
        return self._begin("start_up", self._start_up())

    def _start_up(self):
        d = self.d
        ans = yield Ask(Confirm.START_UP)
        if ans != "yes":
            d.close_for_sending("the table has just been switched on; you chose i1Profiler for "
                                "the start-up")
            raise PersonStopped("start_up_left_to_i1profiler")
        self._check_other_program()
        try:
            d.run_cold_start()
        except Doubt as exc:
            d.cold_failure = _cold_failure_kind(d, exc)
            raise
        return {"start_up_took_s": round(d.start_up_took, 3), "read_before_homing": d.cold_read}

    # ---- readiness (part C's ready(), as ids) ------------------------------------------------
    def _sending_ready(self) -> "str | None":
        if self.phase != "open" or self.d is None:
            return "table_not_open"
        if self.d.closed_reason is not None:
            return "sending_closed"
        if self.d.motion_unconfirmed:
            return "movement_may_be_unfinished"
        return None

    def _ready(self, step: str) -> "str | None":
        why = self._sending_ready()
        if why:
            return why
        d = self.d
        if d.state == "cold":
            return "table_not_started"
        key = STAGE_KEY[step]
        if self.only_home and step != "home":
            return "only_the_homing_now"
        if self.runs.get((self.page, key), 0) >= MAX_RUNS[key]:
            return "ran_as_often_as_allowed"
        rest = self.at_rest() or self.unread_rest() or self.parked()
        if step == "park" and not rest:
            return "arm_not_at_rest"
        if step == "align" and not (rest or (d.arm_free is True and d.mode_on)):
            return "arm_not_at_rest_or_free_after_alignment"
        if step in ("creep", "check_move"):
            if self.alignment is None:
                return "needs_alignment"
            if not self.out_known() and d.arm_free is not True:
                return "arm_not_out_on_the_sheet"
        if step == "creep":
            if self.front_need is None:
                return "sheet_does_not_reach_the_front_zone"
            if self.front_reached() >= self.front_need:
                return "front_zone_confirmed_already"
        if step == "check_move" and self.front_need is not None and \
                self.front_reached() < self.alignment.readings[2][1]:
            return "needs_creep_first"
        if step == "home" and not (self.out_known() or d.arm_free is True):
            return "arm_not_out_on_the_table"
        return None

    def _check_other_program(self) -> None:
        if self._other_program is not None and self._other_program() is True:
            self.d.close_for_sending("i1Profiler was started during the session")
            raise Stopped("other_program_started")

    def _stage(self, step: str, body) -> StepResult:
        if self._gen is not None:
            return self._begin(step, None)
        why = self._ready(step)
        if why:
            return self._result(step, Kind.REFUSED, why)

        def gen():
            ans = yield Ask(Confirm.GO, {"step": step})
            if ans != "yes":
                raise PersonStopped("person_chose_back")
            self._check_other_program()
            key = STAGE_KEY[step]
            self.runs[(self.page, key)] = self.runs.get((self.page, key), 0) + 1
            self._start_block(step)
            try:
                out = yield from body()
            finally:
                self.d.current_step = None
            return out
        return self._begin(step, gen())

    # ---- the steps ---------------------------------------------------------------------------
    def park(self) -> StepResult:
        return self._stage("park", self._park)

    def align(self) -> StepResult:
        return self._stage("align", self._align)

    def creep(self) -> StepResult:
        return self._stage("creep", self._creep)

    def check_move(self) -> StepResult:
        return self._stage("check_move", self._check_move)

    def home(self) -> StepResult:
        return self._stage("home", self._home)

    def restrict_to_homing(self, why: str) -> None:
        """The person reported that the table or the arm did something wrong (part C's
        ASK_ARM_WRONG): nothing more moves in this sitting except the homing."""
        self.only_home = True
        if self.d is not None:
            self.d.log("DATA", f"only the homing from now on: {why}")

    def report_start_up_wrong(self) -> None:
        """The person saw or heard something wrong during the start-up: nothing more is sent."""
        if self.d is not None:
            self.d.close_for_sending("you saw or heard something wrong during the start-up")

    def note(self, question_id: str, answer: str) -> None:
        """An answer kept for the diagnostics only (it gates nothing)."""
        self.notes.append((question_id, answer))
        self.diag.log("ANSWER", f"{question_id} -> {answer}")

    def next_page(self) -> StepResult:
        """The next sheet of the chart (only with the arm at rest: every page is aligned on its
        own)."""
        why = self._sending_ready()
        if why:
            return self._result("next_page", Kind.REFUSED, why)
        if not (self.at_rest() or self.unread_rest() or self.parked()):
            return self._result("next_page", Kind.REFUSED, "arm_not_at_rest")
        if self.page + 1 >= len(self.caps.shape.pages):
            return self._result("next_page", Kind.REFUSED, "no_more_pages")
        self.page += 1
        self.alignment = self.fit = None
        self.front_need = None
        return self._result("next_page", Kind.OK, page=self.page + 1)

    # ---- helpers (part C's, the questions turned into confirmations) --------------------------
    def _step(self, key: str, lines: int, moves: int) -> None:
        st = _CStep(key, lines, moves)
        self.d.current_step = st
        self.d.step_lines = self.d.step_motions = 0

    def _run_b(self, step) -> None:
        d = self.d
        if step.key == "b_home" and d.state not in C_HOME.needs:
            d.state = "homed"
        d.run_step(C_HOME if step.key == "b_home" else step)

    def _check_rest(self, what: str) -> None:
        self._step(f"{self._block['stage']}_rest", 1, 0)
        p = self.d.position()
        self.d.log("DATA", f"{what}: the arm reports {p}")
        if not tbl.REST_GUARD.contains(p):
            self.d.outside_at = p
            raise StageFailed("arm_not_at_rest", read=p)

    def _visited(self, p) -> bool:
        return (any(box.contains(p) for box in geo.DRIVEN)
                or any(_rect_contains(r, p) for r in self.driven))

    def _seg_visited(self, a, b) -> bool:
        x0, x1 = sorted((int(a[0]), int(b[0])))
        y0, y1 = sorted((int(a[1]), int(b[1])))
        xs = sorted(set(list(range(x0, x1 + 1, 10)) + [x1]))
        ys = sorted(set(list(range(y0, y1 + 1, 10)) + [y1]))
        return all(self._visited((x, y)) for x in xs for y in ys)

    def _confirm_new_part(self, a, b, *more, what: str):
        """The first-visit rule (part C): a move whose swept rectangles leave every place the arm
        was driven to (recordings, and this sitting) is confirmed first, ONCE; its rectangles
        (widened by 1 mm) then count as driven. A generator: True when the move may be sent."""
        pts = [tuple(a), tuple(b)] + [tuple(p) for p in more]
        segs = [(pts[k], pts[k + 1]) for k in range(len(pts) - 1)]
        new = [sg for sg in segs if not self._seg_visited(*sg)]
        if not new:
            return True
        region = {"what": what,
                  "x": [min(min(p[0], q[0]) for p, q in new), max(max(p[0], q[0]) for p, q in new)],
                  "y": [min(min(p[1], q[1]) for p, q in new), max(max(p[1], q[1]) for p, q in new)],
                  "beyond_mm": round(max(_beyond_mm(*sg) for sg in new), 1)}
        ans = yield Ask(Confirm.FIRST_VISIT, region)
        if ans == "yes":
            for p, q in segs:
                self.driven.append(((min(p[0], q[0]) - 10, min(p[1], q[1]) - 10),
                                    (max(p[0], q[0]) + 10, max(p[1], q[1]) + 10)))
        return ans == "yes"

    def _free_arm_inside(self, a) -> None:
        if self.d.arm_free and not geo.AREA_RAW.contains(a):
            raise StageFailed("free_arm_outside_area", read=a)

    def _still(self, a):
        """The stillness check before moving a free arm: two readings within STILL_UNITS."""
        b = self.d.position()
        if abs(a[0] - b[0]) > tbl.STILL_UNITS or abs(a[1] - b[1]) > tbl.STILL_UNITS:
            raise StageFailed("free_arm_moved_between_two_readings", first=a, second=b)
        return b

    def _move_to(self, target, what: str):
        """One computed m0 from the position just read, checked, timed and arrival-checked (a
        generator: the first-visit confirmation may be asked)."""
        d = self.d
        a = d.position_now
        if a is None:
            raise StageFailed("no_fresh_position_reading")
        self._free_arm_inside(a)
        geo.check_path(a, target, what, d.front_y)
        ok = yield from self._confirm_new_part(a, target, what=what)
        if not ok:
            raise PersonStopped("first_visit_declined")
        win = geo.move_window(a, target)
        try:
            d.c_exchange(geo.m0_line(target[0], target[1]), 0, window=win,
                         timeout=win[1] + 4.0, late_is_doubt=False)
        except tbl.MoveOutside as exc:
            got = d.position()
            if _near(got, target):
                self.driven.append((a, target))
                raise StageFailed("movement_late_but_arrived", took=round(exc.took, 3),
                                  window=(round(exc.lo, 2), round(exc.hi, 2))) from None
            raise d._doubt(f"{what}: after a slow move the arm reads {got}, not {target}")
        got = d.position()
        if not _near(got, target):
            d.outside_at = got
            raise d._doubt(f"{what}: the arm reads {got}, not {target}")
        self.driven.append((a, target))
        return got

    def _alignment_homed(self) -> None:
        self.alignment = None
        self.front_need = None
        self.fit = None
        self.worked.discard("d1")
        self.worked.discard("d2")

    # ---- park: the recorded homing at rest -----------------------------------------------------
    def _park(self):
        self._run_b(C_HOME)
        return {"read": self.d.position_now}
        yield  # pragma: no cover  (a generator)

    # ---- align: part C's D1 --------------------------------------------------------------------
    def _align(self):
        d = self.d
        sheet = self.sheet
        aims = sc.aims_of(sheet, self.page)
        if not (d.arm_free is True and d.mode_on):
            ans = yield Ask(Confirm.SHEET_LAID, {"orientation": sheet.get("orientation", "")})
            if ans != "yes":
                raise PersonStopped("sheet_not_laid")
            # part B's recorded way out to the alignment start, the arm let go there
            self._run_b(C_HOME)
            self._run_b(C_ALIGN)
            felt = yield Ask(Confirm.ARM_FELT)
            d.out_touch = felt
            if felt != "free":
                raise StageFailed("arm_did_not_give_way_at_the_alignment_start", felt=felt)
        self._step("d1_aims", *D1_CAPS)
        readings = []
        for a in aims:
            ans = yield Ask(Confirm.AIMED, {"mark": a["number"],
                                            "corner": a.get("corner_on_table", ""),
                                            "target": a.get("target"), "patch": a.get("patch")})
            if ans != "aimed":
                raise PersonStopped("stopped_during_the_aims")
            rep = d.c_exchange(cl.C_FIXED["aim"], cl.C_DATA_LEN["aim"])
            p = rep.xy()
            d.log("DATA", f"aim {a['number']}: p1 reports {p}")
            readings.append(p)
        d.exchange("status")
        for _ in range(4):
            d._f4("01")
        self._block["data"]["aims"] = readings
        aims_mm = [tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in aims]
        try:
            al = geo.fit_alignment(aims_mm, readings)
        except geo.AlignmentRefused as exc:
            raise StageFailed(alignment_id(str(exc)), log_reason=str(exc),
                              **_rows_beyond(sheet, self.page, aims_mm, readings)) from None
        self._block["data"]["checks"] = al.checks
        self.diag.write_json(f"{self._block['folder']}/alignment.json",
                             {"aims_mm": al.aims_mm, "readings": al.readings, "M": al.M,
                              "checks": al.checks})
        self.alignment = al
        fit = page_fit(sheet, self.page, al)
        self.fit = fit
        self._block["data"]["fit"] = fit
        self.front_need = None
        need = fit["front_need"]
        out = {"checks": al.checks, "fit": fit}
        if need is not None and need > self.front_reached():
            choice = yield Ask(Confirm.FRONT_CHOICE, {
                "front_need_y": int(need), "front_spot": fit["front_spot"],
                "front_rows": fit["front_rows"],
                "back_mm": int((need - geo.MEASURING_AREA.ymax) / 10.0) + 1})
            if choice == "go on":
                yes = yield Ask(Confirm.FRONT_YES)
                if yes == "yes":
                    self.front_need = int(need)
                    self._block["data"]["front_need_y"] = self.front_need
                    out["front_need_y"] = self.front_need
                    return out
            self.alignment = None
            raise PersonStopped("sheet_to_be_laid_further_back",
                                back_mm=int((need - geo.MEASURING_AREA.ymax) / 10.0) + 1)
        return out

    # ---- creep: part C's DZ ---------------------------------------------------------------------
    def _creep(self):
        d, al = self.d, self.alignment
        need = min(int(self.front_need), geo.FRONT_CAP_Y)
        self._block["data"]["front_need_y"] = need
        mark = max(al.readings, key=lambda p: p[1])
        x = min(max(int(mark[0]), geo.MEASURING_AREA.xmin), geo.MEASURING_AREA.xmax)
        self._step("dz", *DZ_CAPS)
        a = d.position()
        if d.arm_free:
            a = self._still(a)
        y0 = self.front_reached()
        start = (x, min(y0, need))
        ok = yield from self._confirm_new_part(a, start, (x, need), what="creep")
        if not ok:
            raise PersonStopped("first_visit_declined")
        yield from self._move_to(start, "the move to the front edge of the confirmed part")
        n = 0
        while self.front_reached() < need:
            n += 1
            if n > cp.CREEP_STEPS_MAX:
                raise StageFailed("more_creep_steps_than_allowed")
            here = d.position_now
            target = (x, min(here[1] + geo.CREEP_STEP, self.front_reached() + geo.CREEP_STEP,
                             need))
            win = geo.move_window(here, target)
            d.creep = True
            try:
                d.c_exchange(geo.m0_line(*target), 0, window=win, timeout=win[1] + 4.0,
                             late_is_doubt=False)
            except tbl.MoveOutside as exc:
                d.creep = False
                got = d.position()
                self._creep_failed(target, got, "step_outside_time_window",
                                   took=round(exc.took, 3))
            finally:
                d.creep = False
            got = d.position()
            if not _near(got, target):
                self._creep_failed(target, got, "step_did_not_arrive")
            d.front_y = max(d.front_y or 0, target[1])
            self.driven.append((here, target))
            d.log("DATA", f"front zone reached: Y {d.front_y}")
            self._block["data"]["front_zone_reached_y"] = d.front_y
            d.c_wait(cp.CREEP_PAUSE_S)
            if self._pause_stop:
                self._pause_stop = False
                raise PersonStopped("stopped_at_a_creep_pause", front_y=d.front_y)
        return {"front_y": d.front_y}

    def _creep_failed(self, target, got, why: str, **more) -> None:
        self.d.outside_at = got
        self.only_home = True
        self._block["data"]["creep_stopped_at"] = {"target": target, "read": got, "why": why}
        raise StageFailed(f"creep_{why}", target=target, read=got,
                          front_y=self.front_reached(), **more)

    # ---- check_move: part C's D2 -----------------------------------------------------------------
    def _check_move(self):
        d = self.d
        al = self.alignment
        self._step("d2", *D2_CAPS)
        target = al.readings[2]
        a = d.position()
        if d.arm_free:
            self._still(a)
        got = yield from self._move_to(target, "the move to mark 3")
        return {"target": target, "read": got}

    # ---- home: part C's F ----------------------------------------------------------------------
    def _home(self):
        self._end_of_job()
        return {"read": self.d.position_now}
        yield  # pragma: no cover

    def _end_of_job(self) -> None:
        d = self.d
        self._step(f"{self._block['stage']}_end", *cp.HOME)
        d.exchange("status")
        last = d.position_now
        got = d.position()
        if last is not None and not _near(got, last) and d.arm_free is False:
            raise d._doubt(f"before the homing the arm reads {got}, not {last}")
        held_front = d.arm_free is False and geo.CAP_RAW.contains(got)
        if not (geo.AREA_RAW.contains(got) or tbl.START_GUARD.contains(got) or held_front):
            raise StageFailed("homing_only_from_inside_the_area", read=got,
                              arm_free=bool(d.arm_free))
        try:
            d.c_exchange(tbl.WIRE["home"], 0, window=(0.8, 8.0), timeout=15.0,
                         late_is_doubt=False)
        except tbl.MoveOutside as exc:
            p = d.position()
            if not tbl.REST_GUARD.contains(p):
                raise d._doubt(f"after a slow homing the arm reads {p}")
            raise StageFailed("homing_late_but_at_rest", took=round(exc.took, 3)) from None
        d.exchange("status")
        d.exchange("f0")
        d.mode_on = False
        for _ in range(2):
            d._f4("00")
        p = d.position()
        self._alignment_homed()
        if not tbl.REST_GUARD.contains(p):
            d.outside_at = p
            raise d._doubt(f"after the homing the arm reads {p}, not at its resting place")
        d.state = "b_done"

    # ---- close: sends nothing ----------------------------------------------------------------
    def close(self) -> StepResult:
        if self._gen is not None:
            self.cancel()
        d = self.d
        if d is not None:
            d.close_for_sending("the session is over")
        st = self.state()
        wb = self.way_back()
        if st.strip_move_may_be_pending and self.run is not None and self.stamp is not None:
            try:
                marker = self.run.i1io_table_pending_marker(self.stamp)
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(sc.PENDING_TEXT + "\n", encoding="utf-8")
            except OSError:
                pass
        if self.transport is not None:
            try:
                self.transport.close()
            except Exception:      # noqa: BLE001 - closing never raises
                pass
        if d is not None:
            self.diag.log("INFO", f"result: table {d.state or 'not asked'}; "
                                  f"{d.lines_sent} lines sent, {d.motions_sent} movements; "
                                  f"move times {[(k, round(t, 3)) for k, t in d.timings]}; "
                                  f"way back {wb}")
            self.diag.log("INFO", "the job has let go of the table's USB connection (nothing is "
                                  "sent when it does)")
        self.phase = "closed"
        self.diag.finish()
        return StepResult("close", Kind.OK, "", st, wb)


@dataclass(frozen=True)
class _CStep:
    """What Table._write checks while a job step writes its own lines (part C's CStep)."""
    key: str
    max_lines: int
    max_moves: int


def _cold_failure_kind(d: tbl.Table, exc: Doubt) -> str:
    """Tester 0.6.0's cold_failure_kind: link, not_sent, outside, refused, no_answer,
    bad_answer, after."""
    reason = str(exc)
    if reason.startswith(tbl.LINK_FAILED):
        return "link"
    if not d.start_up_sent:
        return "not_sent"
    if d.lines_sent == d.start_up_line_no:
        if d.start_up_took is not None and d.last_move == ("start_up", False):
            return "outside"
        if reason.startswith("the table refused i0"):
            return "refused"
        if reason.startswith("no answer to i0"):
            return "no_answer"
        return "bad_answer"
    return "after"


def _rows_beyond(sheet: dict, page: int, aims_mm, readings) -> dict:
    """For refused aims (nothing moves): which rows could not be reached as the sheet lies."""
    try:
        al = geo.fit_model(aims_mm, readings)
        fit = page_fit(sheet, page, al)
    except (geo.AlignmentRefused, geo.AreaRefused, ValueError, KeyError, IndexError,
            ZeroDivisionError):
        return {}
    return {"spot_outside_rows": fit["spot_outside_rows"],
            "rows_outside_list": fit["rows_outside_list"]}
