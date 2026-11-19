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
  calibrate   (step 7) part C's C1, spot white only: the arm read at rest before and after, the
              reader consent before the first reader of the session, the place (the instrument's
              own tile or the table's tile), the instrument's own calibration
  read_tile   (step 7) part C's C2: one spot reading of the table's tile at the resting place
  read_row    (step 7) part C's D3/D4 for one row: the arm to every patch (computed targets,
              arrival- and time-checked), one spot reading per patch, the plausibility check; a
              failed reading read again once from a fresh position reading; a failed row offers
              again / skip / stop (at most two rows read again per page)
  close       sends nothing: lets go of the USB connection, writes the results
  measurement / save / discard   (step 7) the readings as the run's measurement (spot.py,
              measurement.py): nothing reaches ``Run.measurement_ti3`` except by save()

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

import copy
import json
import math
import os
import re
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import caps as cp
from . import dual_rows as dl
from . import geometry as geo
from . import lines as cl
from . import measurement as ms
from . import reach as rc
from . import reader as rd
from . import scan as sc
from . import session_table as tbl
from . import session_end as se
from . import spot as sp
from . import strip as stp
from . import usb_system as us
from .diagnostics import Diagnostics
from .session_table import Doubt, Stopped

JOB_VERSION = "step8-1"


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
    READY_TO_OPEN = "ready_to_open"  # tester PRE_QUESTIONS: the arm at rest, the bed clear
    REPORT_AFTER_STEP = "report_after_step"   # asking mode: did it do what was described?
    # step 7, reading
    READER_CONSENT = "reader_consent"         # tester ASK_READER_CONSENT, once per session
    CAL_PLACE = "calibration_place"           # tester CAL_WHERE: which white tile (D-4 open)
    CAL_OWN_TILE = "calibration_own_tile"     # tester CAL_OWN: the i1Pro 2 on its own tile
    CAL_RESEAT = "calibration_reseated"       # tester CAL_RESEAT: seated back in the arm
    ROW_FAILED = "row_failed"                 # APP_DESIGN 9: read it again / skip / stop
    #: round B: a STRIP row failed: read it again as a strip / patch by patch / skip / stop
    ROW_FAILED_STRIP = "row_failed_strip"
    # step 8: the end of a session (M-END's three buttons; M-END-EMPTY asks nothing)
    END = "end_of_session"                    # save (and stop) / keep measuring / discard
    #: 4.3.49 ("learn this table's reach once"): the plan needs more front reach than this
    #: table has shown: the person pushes the free arm gently to the front and presses the
    #: instrument's button (or "pushed" on screen); or lays the sheet further back instead
    REACH_PUSH = "reach_push"
    #: 4.3.49: the push showed enough reach; the person pulls the arm back a little, away from
    #: the end, and lets go before anything moves (the next move still asks the hands-off GO)
    REACH_DONE = "reach_done"


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
    # 4.3.48: "arm out": the person says the arm is NOT at its resting place (an earlier stop
    # left it out); ChromIQ connects, reads where it is and moves nothing before it asks
    Confirm.READY_TO_OPEN: ("yes", "arm out", "stop"),
    Confirm.REPORT_AFTER_STEP: ("as described", "something wrong", "not sure"),
    Confirm.READER_CONSENT: ("yes", "no"),
    Confirm.CAL_PLACE: ("own tile", "table tile", "stop"),
    Confirm.CAL_OWN_TILE: ("ready", "stop"),
    Confirm.CAL_RESEAT: ("seated", "stop"),
    Confirm.ROW_FAILED: ("again", "skip", "stop"),
    Confirm.ROW_FAILED_STRIP: ("again", "patch by patch", "skip", "stop"),
    Confirm.END: ("save", "keep measuring", "discard"),
    Confirm.REACH_PUSH: ("pushed", "lay back"),
    Confirm.REACH_DONE: ("go on", "stop"),
}
#: 4.3.49: the guided step's lines: two p0 readings 0.3 s apart (the stillness check) and one p1
#: on the same press, each in its recorded read-only form; nothing moves (REACH_CAPS lines, 0
#: movements), at most REACH_TRIES presses per alignment
REACH_CAPS = cp.REACH_PRESS
REACH_TRIES = cp.REACH_PRESSES
REACH_STILL_WAIT_S = 0.3
#: what the reader consent stands for (tester 0.5.1's READER_CONSENT, as facts; the window words
#: them). The Mac-only facts are listed only on a Mac.
READER_CONSENT_FACTS = ("the_reader_opens_the_i1pro2_with_the_argyllcms_library",
                        "as_when_measuring_by_hand")
READER_CONSENT_FACTS_MAC = ("on_a_mac_it_closes_xrites_i1prodeviceservice_if_the_instrument_is_"
                            "in_use_for_up_to_two_seconds",
                            "macos_normally_starts_that_service_again_by_itself",
                            "xrites_xrdd_is_not_touched",
                            "i1profiler_worked_normally_afterwards_on_one_mac",
                            "the_calibration_is_kept_where_a_later_hand_reading_finds_it")
#: D-4 (where to calibrate), answered by the volunteer's table on 17 Nov 2026: a white made on
#: the table's tile with the instrument in the arm and one made on the instrument's own tile gave
#: patch values 0.13 dE00 apart on average (at most 0.22) from the same raw readings, and
#: i1Profiler itself calibrates on the table's tile. So the table's tile is the recommended (and
#: the window's default) place; the own tile stays a choice. What is still open is D-4b: which
#: white REFERENCE the table's tile is given (the instrument's own, as by hand, or the values
#: stored in the table, as i1Profiler does). The job never answers the question itself.
CAL_PLACE_RECOMMENDED = "table tile"
#: what the calibration question's data says about it (the log and the analysis read it)
CAL_PLACE_MEASURED = "own_tile_and_table_tile_0.13_dE00_apart_on_one_real_table_2026-11-17"
#: final fix round, S-1 (review 13: a white taken partly off the tile spoils every patch): the
#: level of the white, checked on a reading of the TABLE's tile taken with it (Y, the reading's
#: own scale, 100 = the instrument's perfect white). Derived from the volunteer's table on
#: 17 Nov 2026 (test data, nothing private): the table's tile read with a white made on the
#: instrument's own tile gave Y 89.78; the values stored in the table give about 87.6; the
#: i1Pro 2's own reference lies within 0.3-1.0 % of that reading. About 7 % either side: a
#: white made partly off its tile (darker) makes the tile read brighter than 97, a white made
#: on something brighter than a white tile, or a tile not under the opening, below 82.
WHITE_TILE_Y = (82.0, 97.0)

#: NEXT_STEPS 4d: at most this many rows of a page are read again, whatever the session total
ROWS_READ_AGAIN_PER_PAGE = 2
#: round B (the owner, 2026-11-17: "can you confirm the device being on each crosshair point by
#: pressing the button on the device instead of the button in the app?"): while an aiming
#: question waits, ONE press of the i1Pro 2's own button is the same answer as Aimed. The helper
#: (--i1io-press-wait) reports a press only while the job armed it, and never one sooner than
#: BUTTON_MIN_MS after the arm (a press meant for the question before is not an answer); after
#: BUTTON_WAIT_MS without a press it stops waiting (the panel's Aimed still works). Review 14,
#: S-1: the same minimum as the window's hands-off answers (``HANDS_OFF_READY_MS``, 0.6 s).
BUTTON_MIN_MS = 600
BUTTON_WAIT_MS = 600000
#: how long the job waits, before it opens a reader, for the button wait to have let go of the
#: i1Pro 2 (the helper's own close plus the kill that follows a close that blocks)
BUTTON_CLOSE_WAIT_S = 12.0
BUTTON_IGNORED = "button_press_ignored"
#: final fix round, S-2: the button wait has not let go of the i1Pro 2 within
#: BUTTON_CLOSE_WAIT_S: no reader is opened (refused truthfully, nothing moves)
BUTTON_WAIT_HOLDS = "button_wait_still_holds_the_instrument"
#: review 8, S-1: the steps that move the arm (the homing is the way back and never refused
#: for a stop); a stop pressed between steps or at a question ends them before their next move
MOVING_STEPS = ("park", "align", "creep", "check_move", "read_row", "start_up")
STOPPED_BEFORE_THE_NEXT_MOVE = "stopped_before_the_next_move"
#: review 8, B-1: the refusal of every step but the homing once the session has ended (saved,
#: discarded, or "nothing read"); the detail names how it ended
SESSION_ENDED = "session_ended"
#: the facts READY_TO_OPEN stands for (the later window may ask them as separate ticks; the
#: answer "yes" means every one of them is confirmed)
READY_TO_OPEN_ITEMS = ("arm_at_its_resting_place", "nothing_on_the_bed_but_the_sheet")

#: B' (the owner's ruling on the review of step 6): no question after every step; the person
#: can report a problem AT ANY TIME instead (the window's always-visible Stop / "Something is
#: wrong" control): report_problem(kind) with one of these
PROBLEM_STOP_NOW = "stop now"
PROBLEM_SOMETHING_WRONG = "something looked or sounded wrong"
PROBLEM_KINDS = (PROBLEM_STOP_NOW, PROBLEM_SOMETHING_WRONG)
#: the person's own words (the owner: "the window could offer to enter what went wrong"):
#: at most this many characters; longer is cut with NOTE_CUT_MARK
NOTE_MAX_CHARS = 2000
NOTE_CUT_MARK = " [cut: the note was longer]"


def clean_note(note) -> str:
    """A person's free text, made safe for the log and the JSON: control characters (newlines,
    tabs, escapes) become spaces, runs of spaces one, at most NOTE_MAX_CHARS kept. The scrub of
    paths, names and hex runs follows in the diagnostics, as for every line."""
    if note is None:
        return ""
    text = "".join(ch if ch.isprintable() else " " for ch in str(note))
    text = " ".join(text.split())
    if len(text) > NOTE_MAX_CHARS:
        text = text[:NOTE_MAX_CHARS] + NOTE_CUT_MARK
    return text


#: the named state close() returns after a clean measurement in the asking mode: the window may
#: offer "do not ask after each step from now on" (the job stores nothing about the mode)
MAY_OFFER_DO_NOT_ASK_AGAIN = "may_offer_do_not_ask_again"


#: final fix round, M-1 (review 13: "a hand can be on the bed or the arm at EVERY question"): after
#: ANY answered question the next motor move waits for the hands-off confirmation. These
#: answers ARE that confirmation, because the page that asks them says "take your hands away
#: from the table and the arm" and names the move that follows (the window's texts); every
#: other answer, the job's and the window's own questions alike, makes the next move ask GO
#: first. The table module refuses a movement line while one is owed (a bug guard).
HANDS_OFF_ANSWERS = frozenset({(Confirm.GO, "yes"), (Confirm.SHEET_LAID, "yes"),
                               (Confirm.FIRST_VISIT, "yes"), (Confirm.START_UP, "yes"),
                               (Confirm.REPORT_AFTER_STEP, "as described")})
#: the window's own questions whose answer is the hands-off confirmation (same rule)
HANDS_OFF_WINDOW_ANSWERS = frozenset({("check_mark", "centred")})
#: every movement the guard refused (a bug in the job: the tests fail on any entry)
HANDS_OFF_BREACHES: "list[str]" = []

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
    #: 4.3.48: this job stopped sending, but at a place check the table answered cleanly, with
    #: the arm held where recorded homings start: ChromIQ may bring it home itself after a
    #: hands-off GO (``home_after_stop``), once; otherwise the old way (open i1Profiler once)
    HOME_AFTER_STOP = "home_after_stop"
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
    stopped_by_person: bool = False


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


class _ArrivedBeside(StageFailed):
    """4.3.47 fix2 (safety review, suspect 4): a finished computed move whose arm read, twice,
    0.3 s apart, beside its target by more than the arrival tolerance (5 units) but within
    ARRIVAL_BESIDE_UNITS (1 mm). Nothing is pending (the move ended with status 0 inside its
    time window) and nothing more is sent in the step: a clean failure the person can answer
    (read the row again), never a reading taken there."""


class PersonStopped(Exception):
    """The person chose not to go on (a clean stop; the sitting goes on)."""

    def __init__(self, reason: str, **detail):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


#: part C's per-stage runs, per page (the tester's max_runs per sitting, now per sheet laid)
MAX_RUNS = {"park": 8, "d1": 5, "dz": 3, "d2": 3, "f": 8, "c1": 3, "c2": 3}
#: the steps and the tester's stage key each writes its result block under
STAGE_KEY = {"park": "park", "align": "d1", "creep": "dz", "check_move": "d2", "home": "f",
             "home_after_stop": "f",
             "calibrate": "c1", "read_tile": "c2", "read_row": "row"}
#: the step caps the tester used for its own stages (lines, movements)
DZ_CAPS = cp.CREEP
D1_CAPS = (8, 0)
D2_CAPS = (6, 1)       # 4.3.47 MUST-1: +1, the arm read again after a first-visit question

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
    # 4.3.47: the freed arm shifted further than settling explains (RELEASE_SETTLE_UNITS)
    ("the free arm at the alignment start", "free_arm_moved_at_the_alignment_start"),
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


_MODE_FLAG_RE = re.compile(r"f4 answered (\S*) where the recordings show (\S+) here")


_A0_RE = re.compile(r"the table answered a0 with ([0-9A-Fa-f]+)")


def mode_flag_detail(reason: str, step: str) -> dict:
    """Safety review 448, SHOULD-2: what the table answered about its hand-alignment mode (f4),
    what the recordings show at that point, and whether it was the opening, so the window can
    say the one sentence that is true for this case (mode on at an opening, mode on where the
    motors should hold the arm, mode off where they should have let it go, an answer no
    recording shows)."""
    m = _MODE_FLAG_RE.search(reason)
    if not m:
        return {}
    return {"mode_answer": m.group(1), "mode_expected": m.group(2),
            "at_opening": step == "open"}


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
    if geo.AT_AN_END in reason:
        return "move_start_at_an_end"
    if "beyond this table's known reach" in reason:
        return "target_beyond_the_reach"
    if "front part of the table further than this sitting has confirmed" in reason:
        return "target_beyond_confirmed_front"
    if "swept" in reason or "rectangle" in reason:
        return "path_leaves_area"
    if "outside the aimed marks" in reason:
        return "target_off_sheet"
    return "target_outside_area"


#: S-7: the wait before an arrival that read outside the tolerance is read once more
ARRIVAL_RECHECK_S = 0.3
#: 4.3.47 fix2 (safety review, suspect 4): i1Profiler's own arrivals on the volunteer's table
#: reach 5 units (dy -5 of 48, 17 Nov), the edge of the tolerance. An arrival read twice beside
#: the target by 6..10 units (at most 1 mm) after a move that ended normally stops the step
#: CLEANLY (the row is read again by the person's choice, from a fresh reading), instead of
#: ending the measurement; beyond 1 mm it stays a doubt (nothing more is sent), as before.
ARRIVAL_BESIDE_UNITS = 10


def _near(p, q, d=5) -> bool:
    return p is not None and abs(p[0] - q[0]) <= d and abs(p[1] - q[1]) <= d


def homing_starts_here(p, arm_free, cap_y=None) -> bool:
    """Where ChromIQ sends its homing from (4.3.47's rule in ``_end_of_job``, one place for it
    since 4.3.48): inside the measuring area's raw box (14 of i1Profiler's 16 recorded homings
    from a held arm out on the volunteer's table, in 9 recordings, and its 2 clean ones from a
    free arm start there; the other two lie 3-4 units beyond its X -1434), on the
    stretch of the home line near the resting place (START_GUARD), or, held, in the front zone up
    to its cap. Nowhere else: no recording starts a homing at the alignment start (X 2507).

    4.3.49 (FOR THE SAFETY REVIEW; the regions themselves are open decision 1 and unchanged):
    "the front zone up to its cap" was the frontmost recorded aim (Y 3109) plus the arrival
    tolerance, i.e. wherever a held arm could stand after a computed move. Targets may now go to
    THIS table's learned front minus the margin (*cap_y*), so a held arm may be homed up to that
    plus the arrival tolerance, never less far than before. The no-homing-at-an-end rule
    (reach.Reach.near_end) is checked separately, in ``_end_of_job``."""
    if p is None:
        return False
    if geo.AREA_RAW.contains(p) or tbl.START_GUARD.contains(p):
        return True
    if arm_free is not False:
        return False
    front = geo.FRONTMOST_AIM_Y if cap_y is None else max(geo.FRONTMOST_AIM_Y,
                                                         geo.table_cap(cap_y))
    return geo.Area(geo.AREA_RAW.xmin, geo.AREA_RAW.xmax, geo.AREA_RAW.ymin,
                    front + geo.ARRIVAL_SLACK).contains(p)


#: 4.3.48 (safety review 448, NOTE 1): the homing AFTER A STOP is offered only inside the
#: envelope of the recorded homings from a HELD arm out on the table, narrower than
#: ``homing_starts_here`` (4.3.47's rule for the usual homing, unchanged). 16 homings in 9 of
#: the volunteer's recordings, all status 0: 15 at the end of a job (R1 338.379 (-1314, 1643),
#: 546.843 (-1285, 1757); R2 706.049 (-1263, 1785); S2 179.201 (1169, 2560), 371.169
#: (-1088, 1636), 497.615 (1172, 1663), 586.887 (1176, 2120), 769.808 (1179, 1665); 17 Nov
#: 240.899 (-1352, 1646), 122.470 (-1311, 2181), 148.689 (-1307, 2182); 18 Nov 249.679
#: (-1437, 1794), 80.377 (-1438, 1868), 292.945 (-1343, 1864)) and i1Profiler's own at-open
#: recovery, R1 85.848, from (1102, 1202). X -1438..1179, Y 1202..2560; nothing beyond: not the
#: front zone, not X 1180..1766, not the alignment start. The two starts at X -1437 and -1438
#: lie 3-4 units beyond the measuring area's raw box (X from -1434), where 4.3.47's homing
#: refuses anyway (``homing_starts_here``), so the box begins at X -1434.
HOME_AFTER_STOP_AREA = geo.Area(geo.AREA_RAW.xmin, 1179, 1202, 2560)


#: 4.3.48: the stops after which ChromIQ may offer its own homing (``home_after_stop``): the
#: first reason the table module closed the sending with must start with one of these. Each is
#: a PLACE check whose answer the table gave in its recorded form (status 0, the position), with
#: nothing moving and nothing pending, where the arm was simply not where the step expected it:
#: the position read right before the homing a step starts with (HOME_FIRST: START_GUARD),
#: i.e. the arm found out on the table (an earlier stop left it there). NOT on this list, on
#: purpose: a move that did not arrive, a slow move, a homing that failed (a mechanical doubt);
#: any answer not understood, a refusal, no answer, a lost link, the caps (the table's state is
#: not known); the person's own "Send nothing more" (their word stands for this measurement);
#: i1Profiler started meanwhile.
HOME_AFTER_STOP_REASONS = ("right before the homing: the arm reports ",)


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


def shape_of_options(opts: "sp.ReadOptions") -> dict:
    """What the reader will save with these options (review 9, S-2): chartread's -l saves
    L*a*b* instead of XYZ, -L both, -n no spectral values, -H more spectral bands."""
    return {"xyz": not opts.save_lab, "lab": bool(opts.save_lab or opts.save_lab_and_xyz),
            "spectral": not opts.no_spectral,
            "high_res": bool(opts.high_res and not opts.no_spectral)}


#: review 9, S-2: the options that decide what a reading file holds
FIELD_OPTIONS = ("-l", "-L", "-n", "-H")


CHART_TABLE = "i1iO 2"
CHART_HEAD = "i1Pro 2"


class TableJob:
    """One START on the table. Steps are methods; each returns a StepResult. A step that needs
    a person's confirmation returns ``needs_confirmation``; :meth:`answer` continues it."""

    def __init__(self, sheet: dict, page: int = 0, *, run=None, stamp: "str | None" = None,
                 folder: "Path | None" = None, open_transport=None, preflight=None,
                 other_program=None, ask_after_each_step: bool = True, reader_factory=None,
                 helper_check=None, instrument_check=None, chart_ti2=None,
                 app_marker_place: "tuple[Path, str] | None" = None, press_factory=None,
                 scan_factory=None, latency_guard=None, stored_tile_white: bool = False,
                 reach_store=None):
        #: D-4b (an option, off until the owner decides): the white of this measurement scaled
        #: per band to the white tile values stored in the table's memory, as i1Profiler does.
        #: Off: the i1Pro 2's own white reference, as in a measurement by hand.
        self.stored_tile_white = bool(stored_tile_white)
        #: THE i1Pro 2 DUAL SCAN ON THE TABLE (2026-11-18, a first try): what START decided
        #: (dual_rows.DualSetup), set by the window before the job opens; None = the released
        #: job, line for line (no dual argument, no dual line, no dual file)
        self.dual: "dl.DualSetup | None" = None
        #: the dual calibrations of this session: {"spot": event, "strip": event}
        self.dual_calibrations: "dict[str, dict]" = {}
        #: why M1 / M2 could not be written for the measurement (None: written, or no dual)
        self.dual_conditions_refused: "str | None" = None
        #: the per-band factors in use (None: off, or refused), and why they were refused
        self.white_scale: "tuple | None" = None
        self.white_scale_refused: "str | None" = None
        #: 4.3.49 ("learn this table's reach once"): where the reaches of the tables this computer
        #: has driven are kept (the window passes the app's settings; None: memory only), this
        #: table's reach once the opening has read its memory block, and what the diagnostics
        #: of this session say about it (reach.json in the session folder)
        self._reach_store = reach_store if reach_store is not None else rc.MemoryReachStore()
        self.reach: "rc.Reach | None" = None
        self.reach_diag: dict = {"guided_step": {"ran": False}, "free_readings": [],
                                 "motor_arrivals": 0, "aims": [], "p0_after_aims": [],
                                 "pairs": [], "statuses": [], "refusals": [], "events": []}
        # the job's OWN copy (review of step 6): the caps are derived from it, and a caller
        # changing its chart afterwards changes nothing here
        self.sheet = copy.deepcopy(sheet)
        self.page = int(page)
        #: review 9, NOTE: where the app-level pending marker lives ((folder, name prefix), see
        #: session_end.app_marker_dir_and_prefix); the window passes it, None = none (tests)
        self.app_marker_place = app_marker_place
        #: step 9 (display only): called with a small dict when a row starts, before the arm
        #: moves to a patch, after a patch is read and when a row ends, so the Measure tab's
        #: preview can follow the job (the current row / patch, what was read). It runs in the
        #: job's thread; it is never asked anything and its errors are swallowed: it can
        #: neither send a line nor stop the job.
        self.on_progress = None
        self.run, self.stamp = run, stamp
        if run is not None and stamp is not None:
            folder = run.i1io_table_session_dir(stamp)
            self.diag = Diagnostics(folder, run.i1io_table_log(stamp))
        else:
            self.diag = Diagnostics(folder)
        self._open_transport = open_transport or tbl.open_table
        self._preflight = preflight or us.preflight
        self._other_program = other_program
        #: the table: PRIVATE (review of step 6): a window drives the job's steps, never the
        #: table itself, so GO, stillness, first visit and the arrival checks cannot be skipped
        self._table: "tbl.Table | None" = None
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
        #: B': every problem the person reported, never lost (kind, the step it came in, the
        #: lines sent by then)
        self.problems: "list[tuple[str, str | None, int]]" = []
        #: the person's notes that belong to no step (before the first one)
        self.session_notes: "list[dict]" = []
        #: the owner's ruling: True = the "first measurement" mode (after every step that
        #: moved, and after the start-up, REPORT_AFTER_STEP; the safety review's change B);
        #: False = no question, report_problem() and the automatic checks (B'). The window
        #: passes it; the job stores nothing about it.
        self.ask_after_each_step = bool(ask_after_each_step)
        #: asking mode: the step whose report is due (None: none due); every moving step but
        #: the homing is refused until it is answered
        self.report_due: "str | None" = None
        #: asking mode: every report given (step, answer)
        self.reports: "list[tuple[str, str]]" = []
        #: "stop now" was reported: nothing more is ever sent, nothing more is opened
        self.stopped_by_person = False
        #: GO is asked once per page (the owner's ruling: no question after every step)
        self._go_page: "int | None" = None
        #: final fix round, M-1: a question was answered since the last hands-off
        #: confirmation; the next movement asks GO first (True from the start: the first
        #: question, READY_TO_OPEN, is answered before anything can move)
        self._hands_off_due = True
        #: 4.3.47 MUST-1: the table's line count when the person last answered a question (the
        #: job's, a report, or the window's own): a computed move is never sent from a reading
        #: taken before it (``_read_again_if_asked``)
        self._answered_at_line: "int | None" = None
        #: the 0-based line numbers of those extra readings in this sitting
        self.reads_after_question: "list[int]" = []
        self.notes: "list[tuple[str, str]]" = []
        self._gen = None
        self._gen_step: "str | None" = None
        self._pending: "Ask | None" = None
        self._block: "dict | None" = None
        self._pause_stop = False
        #: fix round 10 (NEXT_STEPS 4d, open point e): the person pressed Stop at least once in
        #: this session; the "don't ask after each step" offer is then never made
        self.stop_pressed = False
        #: fix round 10 (B-1): the write-ahead "the table is in use" markers of this session
        #: (the session folder's and the app-level one), written when the USB is opened and
        #: acknowledged by close(); a session the app never closed leaves them, and the next
        #: START asks "switched off and on" first
        self._in_use_markers: "list[Path]" = []
        self.preflight_seen: "us.Preflight | None" = None
        # ---- step 7, reading -------------------------------------------------------------------
        #: starts ChromIQ's helper for spot readings (reader.SpotReader through the app's
        #: helper path, as the tester's Readers.spot did); tests pass a simulated one
        self._reader_factory = reader_factory or _default_reader
        # ---- round B: the instrument's button as "Aimed" ---------------------------------------
        #: builds the helper's button wait (folder, log) -> reader.PressWaiter-like; False or
        #: None = not offered. By default the real helper's, only with the real readers (the
        #: same helper) and only when its build string carries the button wait
        if press_factory is None and reader_factory is None:
            press_factory = _default_press_factory
        # ---- round B: strip rows (a first try) ----------------------------------------------
        #: builds the helper's table-scan reader (folder, log) -> reader.ScanReader-like; by
        #: default the real helper's, only with the real readers (the same helper)
        if scan_factory is None and reader_factory is None:
            scan_factory = _default_scan_reader
        self._scan_factory = scan_factory
        #: a context manager held around each strip move (the app passes macOS's "latency
        #: critical" activity, so App Nap cannot slow the one path to the fire); None: none
        self._latency_guard = latency_guard
        #: the strip white (tester C1's strip calibration): {"place", "t"} or None
        self.strip_calibration: "dict | None" = None
        #: per page, the rows read patch by patch because the strip could not be used, and why
        self.strip_fallbacks: "dict[int, dict[int, str]]" = {}
        self._press_factory = press_factory or None
        self._press = None
        self._press_lock = threading.Lock()
        self._press_closing: "threading.Thread | None" = None
        #: the token of the aiming question the button may answer now (None: none)
        self._press_token: "str | None" = None
        self._press_seq = 0
        self._press_used: "set[str]" = set()
        self._by_button = False
        #: why the button is not offered at this alignment (None: offered or not asked yet)
        self.button_unavailable: "str | None" = None
        #: the marks answered by the instrument's button, (page, mark)
        self.button_aims: "list[tuple[int, int]]" = []
        #: 4.3.49 (the volunteer's run of 19 Nov 2026): refused alignments in a row, so the
        #: page can say more from the second one on (reset by an alignment that fits)
        self.align_refusals_in_a_row = 0
        self._helper_check = helper_check or _default_helper_check
        self._instrument_check = instrument_check or us.instrument_now
        self._chart_ti2 = Path(chart_ti2) if chart_ti2 is not None else (
            Path(run.chart_ti2) if run is not None else None)
        if run is not None and stamp is not None:
            # review 12, M-2 / M-3: which chart (and which dated verification) this session
            # reads, recorded before anything is read; never completed into another
            try:
                se.write_identity(run.i1io_table_session_dir(stamp), self._chart_ti2, run)
            except OSError:
                self.diag.log("INFO", "the chart's checksum could not be recorded; this "
                                      "session can never be completed by a later one")
        #: the reader consent, given once in this session (never stored by the job)
        self.reader_consent = False
        self.readers_started = 0
        self._open_readers: list = []
        #: the white: {"place", "t" (the table's clock), "kind": "spot"} or None
        self.calibration: "dict | None" = None
        self.cal_place: "str | None" = None
        self.calibration_due = False
        #: the person lifted the i1Pro 2 out of the arm's holder for its own tile, and has not
        #: said "seated" since: nothing moves (its cable could catch), nothing but a calibration
        #: (which asks for "seated" again) runs
        self.instrument_out = False
        self._cal_refused: "str | None" = None
        self.options_report = sp.OptionsReport(sp.ReadOptions())
        #: resume / refinement: only these patches are read (None: every patch)
        self.only_locs: "set[str] | None" = None
        self._resume_base: "Path | None" = None
        #: review 8, S-3: what set_options asked for, and what the adoptions still lack (each
        #: (locations or None, base)); only_locs and the base are made from both
        self._requested: "tuple[set[str] | None, Path | None]" = (None, None)
        self._adopted: "tuple[set[str], Path | None]" = (set(), None)
        #: rows per page: {page: {row index: status}} (read, failed, skipped, stopped, ...)
        self.row_status: "dict[int, dict[int, str]]" = {}
        #: per page, how many rows were read again (NEXT_STEPS 4d)
        self.rows_again: "dict[int, int]" = {}
        #: 4.3.48: the automatic second moves after an arrival beside the target (for the
        #: diagnostics), and how many the running row attempt may still send
        self.beside_retries: "list[dict]" = []
        self._beside_retries_left = 0
        self._beside_at_block = 0
        #: 4.3.48: the person answered "arm out" at the ready question
        self.opened_with_arm_out = False
        #: 4.3.48: the homing after a stop was tried in this session (it is offered once)
        self._home_after_stop_tried = False
        self._row_seq = 0
        self.tile_readings: "list[dict]" = []
        self._tile_spectrum: "list[float] | None" = None
        self.ended: "str | None" = None          # "saved" / "discarded" / "nothing_read"
        #: step 8: interrupted earlier sessions adopted by this one (their readings count)
        self._earlier_dirs: "list[Path]" = []
        #: review 9, S-1: True only while _end() itself saves or discards
        self._inside_end = False
        #: review 9, S-2: what the adopted readings hold (XYZ, L*a*b*, spectral)
        self._adopted_shape: "dict | None" = None
        #: review 14, M-2: the white reference the adopted readings were made with
        self._adopted_white: "str | None" = None
        #: review 14, M-2: THE SESSION'S WHITE REFERENCE, decided ONCE, at its first calibration
        #: (or its first row, read without one under -N), and kept for every later calibration:
        #: "stored" (the table's stored white tile values) or "own" (the i1Pro 2's own). A later
        #: calibration that cannot give it is refused like a failed white (calibrate again, or
        #: end and save what was read with it); a session never switches reference silently, so
        #: its readings always go into one file
        self.session_white: "str | None" = None
        #: fix round 10, S-2: an adoption made with the replace agreed (the run's measurement
        #: is replaced at Save, by the window's archive, and never built on)
        self._replacing = False
        self.diag.log("INFO", f"ChromIQ table job {JOB_VERSION} (table module "
                              f"{tbl.TOOL_NAME} {tbl.TOOL_VERSION}); page {self.page + 1}")

    # ---- the state, from the table's answers only ------------------------------------------
    def at_rest(self) -> bool:
        d = self._table
        if d is None:
            return False
        p = d.position_now
        return (p is not None and not d.motion_unconfirmed and d.arm_free is False
                and tbl.REST_GUARD.contains(p) and not d.mode_on)

    def unread_rest(self) -> bool:
        d = self._table
        return d is not None and d.motions_sent == d.cold_motions and d.state == "warm"

    def parked(self) -> bool:
        """Right after the job's own park (the recorded s0 p0 i1 s0 from rest, finished in its
        window): at rest by the reading before the homing; the next step's own homing reads it
        again before anything moves (HOME_FIRST's p0 in START_GUARD)."""
        d = self._table
        return (d is not None and d.state == "homed" and not d.motion_unconfirmed
                and d.last_move == ("home", True) and d.position_now is None
                and d.before_move is not None and tbl.START_GUARD.contains(d.before_move)
                and d.arm_free is False and not d.mode_on)

    def out_known(self) -> bool:
        d = self._table
        if d is None:
            return False
        p = d.position_now
        return p is not None and not d.motion_unconfirmed and not self.at_rest()

    def front_reached(self) -> int:
        return geo.areas(self._table.front_y if self._table is not None else None,
                         self._cap())[0].ymax

    def _cap(self) -> int:
        """4.3.49: the front of THIS table's target area (its learned reach minus the margin;
        the proven measuring area while nothing is known)."""
        r = self.reach
        return geo.table_cap(r.front_bound() if r is not None else None)

    def state(self) -> TableState:
        d = self._table
        if d is None:
            return TableState(None, None, None, None, False, False, False, False, False, False,
                              self.phase == "closed", 0, 0, None, self.only_home)
        pending = (d.closed_reason == "a scan move may be pending" or (
            d.motion_unconfirmed and bool(d.last_move) and d.last_move[0] == "scan move"))
        return TableState(d.state, d.last_read, d.last_read_t, d.position_now, self.at_rest(),
                          d.arm_free, d.mode_on, bool(d.motion_unconfirmed), pending,
                          d.link_lost_at is not None, d.closed_reason is not None,
                          d.lines_sent, d.motions_sent, getattr(d, "front_y", None),
                          self.only_home, self.stopped_by_person)

    def way_back(self) -> str:
        """Part C's where_text, as ids, from the table's answers only."""
        d = self._table
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
        if self._home_after_stop_why() is None:
            return WayBack.HOME_AFTER_STOP
        return WayBack.OPEN_I1PROFILER_ONCE

    def _progress(self, **event) -> None:
        cb = self.on_progress
        if cb is None:
            return
        try:
            cb(dict(event, page=self.page + 1))
        except Exception:      # noqa: BLE001 - display only, never the job's concern
            pass

    # ---- results ---------------------------------------------------------------------------
    def _result(self, step: str, kind: str, reason: str = "", **detail) -> StepResult:
        if reason == SESSION_ENDED:
            detail.setdefault("ended", self.ended)
        if kind in (Kind.REFUSED, Kind.STOPPED):
            # the safety review of step 7 (REQUIRED): a step that ended refused or stopped (the
            # person's stop inside a row, a declined move, a failed row, any named refusal) may
            # have the person's hands on the bed; the next moving step waits for a hands-off GO
            self._go_page = None
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
        self._moves_at_begin = self._table.motions_sent if self._table is not None else 0
        return self._drive(None)

    def answer(self, kind: str, value: str) -> StepResult:
        """The person's answer to the confirmation the job is waiting for."""
        return self._answer(kind, value)

    def _answer(self, kind: str, value: str, by: str = "") -> StepResult:
        if kind == Confirm.REPORT_AFTER_STEP and self.report_due is not None:
            return self._report(value)
        step = self._gen_step or "none"
        if self._gen is None or self._pending is None:
            return self._result(step, Kind.REFUSED, "nothing_waits_for_a_confirmation")
        if kind != self._pending.kind:
            return self._result(step, Kind.REFUSED, "not_the_confirmation_asked_for",
                                asked=self._pending.kind, given=kind)
        if value not in CHOICES[kind]:
            return self._result(step, Kind.REFUSED, "not_one_of_the_choices",
                                asked=self._pending.kind, choices=list(CHOICES[kind]))
        if kind in (Confirm.ROW_FAILED, Confirm.ROW_FAILED_STRIP) and value in (
                "again", "patch by patch"):
            # NEXT_STEPS 4d, enforced per page: a third row read again on this page is refused
            # (nothing sent); the question stays open for skip or stop
            why = self._again_refused()
            if why:
                self.diag.log("ANSWER", f"{step}: {kind} -> again refused ({why})")
                return self._result(step, Kind.REFUSED, why, asked=kind,
                                    rows_read_again=self.rows_again.get(self.page, 0),
                                    choices=["skip", "stop"])
        self.notes.append((f"{step}: {kind}", value))
        self.diag.log("ANSWER", f"{step}: {kind} -> {value}{by}")
        if self._block is not None:
            self._block["answers"].append((BLOCK_LABEL.get(kind, kind), value))
        self._pending = None
        self._mark_answered()
        # final fix round, M-1: the person was at the screen, and maybe at the table, for this
        # question; unless the answer is itself the hands-off confirmation, the next movement
        # asks GO first
        self._hands_off_due = (kind, value) not in HANDS_OFF_ANSWERS
        # review 8, S-1: Stop was pressed while this question was shown: the step ends here,
        # before the move the answer would allow (the reader, if open, is finished by the
        # step's own way out)
        stop = PersonStopped(STOPPED_BEFORE_THE_NEXT_MOVE) if self._stale_stop(step) else None
        return self._drive(value, throw=stop)

    def cancel(self) -> StepResult:
        """The Ctrl-C equivalent: nothing more is ever sent. While a line is on its way, it is
        written to the end and its answers read (the table module never cuts a line in half);
        at a confirmation, the job ends at once."""
        step = self._gen_step or "cancel"
        self.stopped_by_person = True
        self._press_cancel("cancelled")
        if self._table is not None:
            self._table.request_stop()
        if self._gen is not None and self._pending is not None:
            gen, self._gen, self._pending = self._gen, None, None
            try:
                gen.close()
            except BaseException:         # noqa: BLE001
                pass
            if self._table is not None:
                self._table.close_for_sending("stopped by you")
            res = self._result(step, Kind.STOPPED, "cancelled_by_person")
            self._end_block(res)
            self._gen_step = None
            return res
        if self._table is not None and self._gen is None:
            self._table.close_for_sending("stopped by you")
        return self._result(step, Kind.STOPPED, "cancelled_by_person")

    def stop_at_next_pause(self) -> None:
        """Part C's Enter between two creep steps: a clean stop at the next pause. Pressed while
        no line is on its way (between steps, or while a question is shown), it takes effect
        BEFORE the next move (review 8, S-1): the next moving step, or the answer that would
        let a waiting step move on, ends there (``stopped_before_the_next_move``), and the
        hands-off GO is asked again; the homing is never refused for it."""
        self._pause_stop = True
        self.stop_pressed = True
        # round B: Stop cancels the wait for the instrument's button (the question on screen
        # may still be answered in the panel; a press is no longer taken)
        self._press_cancel("stop pressed")
        # review 9, M-1: in EVERY case, also while a step runs (a check move has no pause of
        # its own): the next movement after a stop, the homing included, asks the hands-off
        # GO again. A running step has passed its GO already; the rows set or clear it
        # themselves.
        self._go_page = None

    def stop_honoured_between_steps(self) -> None:
        """Final fix round: the window showed the person's Stop at once, because no step was
        running or waiting (the mark-3 check, the next page's question): the stop has taken
        effect there, so it does not stop the next step a second time. The next movement still
        asks the hands-off GO (stop_at_next_pause cleared it)."""
        if self._gen is None and self._pause_stop:
            self._pause_stop = False
            self.diag.log("ANSWER", "the stop pressed between steps is honoured: nothing moved; "
                                    "the next movement asks the hands-off GO first")

    def _stale_stop(self, step: "str | None") -> bool:
        """A stop pressed between steps or at a question, still waiting (consumed here)."""
        if self._pause_stop and step in MOVING_STEPS and not self.only_home:
            self._pause_stop = False
            self.diag.log("ANSWER", f"{step}: the stop pressed before it is honoured before "
                                    f"the next move")
            return True
        return False

    def _drive(self, value, throw: "BaseException | None" = None) -> StepResult:
        step = self._gen_step
        moves_before = getattr(self, "_moves_at_begin", 0)
        res = self._drive_inner(value, step, throw)
        t = self._table
        if (self.ask_after_each_step and self._gen is None and t is not None
                and t.closed_reason is None and step not in ("home", None) and (
                    t.motions_sent > moves_before or (step == "start_up" and t.start_up_sent))):
            # tester 0.6.0 asked after every stage that moved (and after the start-up)
            self.report_due = step
            res = replace(res, state=self.state(), confirm=Confirm.REPORT_AFTER_STEP,
                          choices=CHOICES[Confirm.REPORT_AFTER_STEP])
        return res

    def _drive_inner(self, value, step, throw=None) -> StepResult:
        try:
            ask = self._gen.throw(throw) if throw is not None else self._gen.send(value)
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
        d = self._table
        if isinstance(exc, StageFailed):
            res = self._result(step, Kind.REFUSED, exc.reason, **exc.detail)
        elif isinstance(exc, PersonStopped):
            res = self._result(step, Kind.REFUSED, exc.reason, by_person=True, **exc.detail)
        elif isinstance(exc, geo.AlignmentRefused):
            res = self._result(step, Kind.REFUSED, alignment_id(str(exc)), log_reason=str(exc))
        elif isinstance(exc, (geo.AreaRefused, sc.PlanRefused)):
            res = self._result(step, Kind.REFUSED, area_id(str(exc)), log_reason=str(exc))
        elif isinstance(exc, sp.RowRefused):
            res = self._result(step, Kind.REFUSED, exc.reason, **exc.detail)
        elif isinstance(exc, tbl.MoveOutside):
            d.close_for_sending(str(exc))
            res = self._result(step, Kind.STOPPED, "movement_outside_time_window",
                               took=round(exc.took, 3), window=(exc.lo, exc.hi))
        elif isinstance(exc, Doubt):
            rid = doubt_id(str(exc))
            if d is not None and d.link_lost_at is not None:
                rid = "link_lost"
            extra = mode_flag_detail(str(exc), step) if rid == "mode_flag_unexpected" else {}
            if rid == "table_state_unknown":
                m = _A0_RE.search(str(exc))
                extra = {"a0": m.group(1)} if m else {}
            if extra and d is not None:
                # fix2 (found on screen): the table contradicted what ChromIQ believed about the
                # hand-alignment mode, so whether the motors hold the arm is NOT known; no page
                # may then say "the arm is still free" (or that it is held)
                d.arm_free = None
            if rid in ("table_answered_a_status", "table_refused_a_line"):
                # 4.3.49: every non-zero status and every refusal, with where the arm was read
                # before it (the data a later model-wide reach would be learned from)
                self._reach_note("status" if rid == "table_answered_a_status" else "refused",
                                 step=step, reason=str(exc)[:200],
                                 position_before=list(d.last_read) if d is not None and
                                 d.last_read is not None else None,
                                 arm_free=d.arm_free if d is not None else None)
            res = self._result(step, Kind.STOPPED, rid, log_reason=str(exc), **extra)
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
        d = self._table
        self._block = {"stage": key, "run": n, "page": self.page + 1, "verdict": "", "why": "",
                       "folder": f"{key}-{n}", "lines_before": d.lines_sent,
                       "moves_before": d.motions_sent, "position_before": d.position_now,
                       "t_start": round(d.t.now(), 3), "answers": [], "data": {}}
        self._beside_at_block = len(self.beside_retries)
        self.diag.stage_dir(key, n)
        d.log("STAGE", f"start {key} run {n}")

    def _end_block(self, res: StepResult) -> None:
        b, self._block = self._block, None
        if b is None or self._table is None:
            return
        d = self._table
        verdict = {Kind.OK: "worked", Kind.STOPPED: "stopped"}.get(res.kind, "failed cleanly")
        if res.kind == Kind.REFUSED and res.detail.get("by_person"):
            verdict = "stopped by you (clean)"
        b.update({"verdict": verdict, "why": res.reason, "lines_after": d.lines_sent,
                  "moves_after": d.motions_sent, "position_after": d.position_now,
                  "last_read": d.last_read, "arm_free": d.arm_free, "mode_on": d.mode_on,
                  "movement_unconfirmed": d.motion_unconfirmed, "t_end": round(d.t.now(), 3),
                  "front_zone_reached_y": d.front_y, "way_back": res.way_back,
                  "state": {k: v for k, v in res.state.__dict__.items()}})
        second = self.beside_retries[self._beside_at_block:]
        if second:
            # safety review 448, SHOULD-3: every automatic second move of this step, with its
            # readings and whether it cured the miss (diagnostics.py, "second_moves")
            b["data"]["second_moves"] = copy.deepcopy(second)
        if res.kind == Kind.OK and b["stage"] in ("d1", "dz", "d2", "f", "park"):
            self.worked.add(b["stage"])
        b.setdefault("notes", [])
        self._last_block = b
        self.diag.block(b)
        if self.reach is not None:
            self._reach_save()
            self._write_reach_diag()

    # ---- the opening -------------------------------------------------------------------------
    def open(self) -> StepResult:
        if self.stopped_by_person:
            return self._result("open", Kind.REFUSED, "stopped_by_person")
        if self.ended is not None:
            return self._result("open", Kind.REFUSED, SESSION_ENDED)
        if self.phase != "new":
            return self._result("open", Kind.REFUSED, "already_opened")
        if self._gen is None and not self.options_report.ok:
            # review 9, NOTE: options cannot change after the opening, so a session opened with
            # a refused option could never read; it is refused here, before anything is asked
            return self._result("open", Kind.REFUSED, "option_refused",
                                refused=dict(self.options_report.refused))
        first = self.pages_to_read()
        if (self._gen is None and first and 0 <= self.page < self.pages_in_chart()
                and not self.page_has_something_to_read() and self.page + 1 > first[0]):
            # review 9, NOTE: next_page() only goes forward; a job built on a page with nothing
            # to read, after a page that has something, would never reach that one (the window
            # builds the job on pages_to_read()[0])
            return self._result("open", Kind.REFUSED, "an_earlier_page_is_to_be_read_first",
                                page=self.page + 1, first_page=first[0])
        return self._begin("open", self._open())

    def _unacknowledged_markers(self) -> "list[Path]":
        """Review 9, NOTE: a strip move that may still wait is a state of the physical table:
        the markers of EVERY run of this project, and the app-level ones (any project, any run,
        a job without a run), not acknowledged yet."""
        found = se.project_markers(self.run) if self.run is not None else []
        if self.app_marker_place is not None:
            found += se.app_markers(*self.app_marker_place)
        return found

    def _open(self):
        sheet = self.sheet
        # 1. a strip move that may still wait (a marker from an earlier START): the person
        #    says the table was switched off and on since; the marker is kept, acknowledged
        markers = self._unacknowledged_markers()
        if markers:
            ans = yield Ask(Confirm.MARKER, {
                "markers": len(markers),
                # fix round 10 (B-1): markers left by a session the app never closed (a
                # crash, a kill, a power cut) rather than by a strip move
                "app_ended": sum(1 for m in markers if se.is_in_use_marker(m))})
            if ans != "switched off and on":
                raise PersonStopped("pending_marker_not_cleared", markers=len(markers))
            for m in markers:
                try:
                    se.acknowledged_path(m).write_text(
                        json.dumps({"acknowledged_by_person": "switched off and on"}),
                        encoding="utf-8")
                except OSError:
                    raise StageFailed("pending_marker_not_writable") from None
        # 2. the chart: an i1iO 2 with an i1Pro 2 (its own record; nothing is opened yet)
        if sheet.get("table_model") != CHART_TABLE or sheet.get("head_model") != CHART_HEAD:
            raise StageFailed("chart_not_for_i1io2_with_i1pro2",
                              table=sheet.get("table_model"), head=sheet.get("head_model"))
        # final fix round (crosses off): every page must name its three points to aim at
        # (three crosses, or three corner patches); checked here, before anything is opened,
        # never at the aims (the chart module gives a page whose corner patches cannot be
        # aimed at its crosses, so a chart ChromIQ made never fails this)
        for k, pg in enumerate(sheet.get("pages") or []):
            pts = pg.get("aim_points") or []
            if len(pts) != 3 or any(len(a.get("page_mm") or ()) != 2 for a in pts) or \
                    sorted(int(a.get("number", 0)) for a in pts) != [1, 2, 3]:
                raise StageFailed("chart_page_without_three_aim_points", page=k + 1)
        try:
            dual = self.dual is not None
            self.caps = cp.caps_for_sheet(sheet, dual) if dual else cp.caps_for_sheet(sheet)
            if self.only_locs is not None:
                # step 8, resume: the caps come from what is MISSING, not from the whole chart
                self.caps = (cp.caps_for_missing(sheet, self.only_locs, dual) if dual
                             else cp.caps_for_missing(sheet, self.only_locs))
        except cp.CapsRefused as exc:
            raise StageFailed(exc.reason, **exc.detail) from None
        # review 8, M-3: the CHART's pages (a resume's caps leave out the pages with nothing
        # missing, so their count is not the chart's)
        if not 0 <= self.page < self.pages_in_chart():
            raise StageFailed("page_not_in_chart", page=self.page + 1)
        self.diag.log("INFO", "caps derived from the chart: " + json.dumps(self.caps.as_dict()))
        # 3. the system's own lists (read only): the instrument, who holds the table, i1Profiler
        pf = self._preflight()
        self.preflight_seen = pf
        self.diag.log("INFO", "before opening: " + json.dumps(pf.as_dict(), default=str))
        if pf.system == "windows" and pf.x64_on_arm64:
            # review WIN2, F-S1: an x64 ChromIQ on a Windows for ARM computer can never drive the
            # table (it cannot load the ARM64 libusb0.dll), whatever the drivers' states: the
            # truthful message (use the ARM64 version) here, BEFORE the READY_TO_OPEN question,
            # never after the person has prepared the table for an opening that cannot come
            raise StageFailed("usb_open_refused",
                              message_id="M-I1IO-DRIVE-USB-NOT-ON-THIS-SYSTEM",
                              problem="windows-x64-on-arm64")
        if pf.system == "windows" and pf.table_driver.state == "none" and (
                pf.table_driver.detail.get("seen") is False
                or pf.table_driver.detail.get("present") is False):
            # review WIN2, F-M2: no table attached (never seen, or only remembered by Windows)
            # is "ChromIQ did not find the table", the same words as the opening's; an install
            # offer would lead into a window that lists no table
            raise StageFailed("usb_open_refused", message_id=tbl.NO_TABLE,
                              problem="windows-table-not-connected")
        if pf.system == "windows" and pf.table_driver.state != "libusb0":
            # the owner's ruling: on Windows the table is reached like ArgyllCMS's instruments,
            # through libusb-win32, which only the person's explicit choice installs for it.
            # 4.3.46 (owner, 2026-11-18): the window then offers that install (the ARM64 build
            # like x64; the x64 build on an ARM PC was refused above)
            raise StageFailed("driver_not_installed_for_table",
                              driver_state=pf.table_driver.state, **pf.table_driver.detail)
        if pf.system == "windows" and pf.instrument_driver.state == "none":
            # 4.3.46: the i1Pro 2 in the arm is its own USB device and needs the same driver
            # (ArgyllCMS reads it through libusb-win32); the window offers that install too
            raise StageFailed("driver_not_installed_for_instrument")
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
        # 4. the tester's PRE_QUESTIONS (review of step 6, REQUIRED A): the person confirms the
        #    arm at its resting place and nothing on the bed but the sheet; else nothing opens
        ready = yield Ask(Confirm.READY_TO_OPEN, {"items": list(READY_TO_OPEN_ITEMS)})
        if ready not in ("yes", "arm out"):
            raise PersonStopped("not_ready_to_open")
        #: 4.3.48: the person said the arm is out over the table: after the opening the window
        #: asks where_is_the_arm() (one reading) before anything else, and nothing moves
        #: without its own hands-off GO
        self.opened_with_arm_out = ready == "arm out"
        # 5. the USB opening: ChromIQ's own library only; nothing sent before the descriptors
        try:
            self.transport = self._open_transport()
        except tbl.NotAvailable as exc:
            mid, problem = getattr(exc, "message_id", ""), getattr(exc, "problem", "")
            if pf.system == "windows" and pf.x64_on_arm64 and mid == tbl.DRIVER_NOT_INSTALLED:
                # review 446, W-M1, as revised 2026-11-18: the opening found the table without its
                # driver (or its libusb0.dll missing) in an x64 ChromIQ on a Windows for ARM
                # computer. An install cannot help that process: the truthful message instead
                raise StageFailed("usb_open_refused",
                                  message_id="M-I1IO-DRIVE-USB-NOT-ON-THIS-SYSTEM",
                                  problem="windows-x64-on-arm64-" + str(problem)) from None
            if pf.system == "windows" and mid == tbl.DRIVER_NOT_INSTALLED \
                    and problem == "no-libusb0-dll":
                # review 446, W-S3: Windows lists the table with libusb-win32 (the check before
                # the opening said so), but the driver's libusb0.dll is missing or gives no
                # backend: not "no driver", and the window says which
                raise StageFailed("driver_file_missing_for_table", problem=problem) from None
            raise StageFailed("usb_open_refused", message_id=mid, problem=problem) from None
        except tbl.TransportError as exc:
            raise StageFailed("usb_open_failed", error=type(exc).__name__) from None
        self.diag.log("INFO", tbl.usb_summary(self.transport))
        self._write_in_use_markers()
        d = tbl.Table(self.transport, log=self.diag.log)
        self._table = d
        self.phase = "open"
        # part C's gate and caps are in place before the first line of the opening
        d.part = "C"
        d.front_y = None
        d.creep = False
        d.c_gate = cl.make_gate(d)
        #: the dual row's phase ("lamp" / "uv") while it reads that pass; None otherwise
        d.dual_phase = None
        d.c_caps = (self.caps.lines, self.caps.moves)
        # final fix round, M-1: no movement line while a hands-off confirmation is owed
        d.motion_guard = self._motion_guard
        if hasattr(self.transport, "gate"):
            # the dual scan: the same classify, with the table's dual phase at the write
            self.transport.gate = cl.wire_gate if self.dual is None else cl.make_wire_gate(d)
        d._touch_out = lambda: "asked after the step"
        state = d.opening()
        self._load_reach(d)
        out = {"table": state, "system": pf.system}
        if self.opened_with_arm_out:
            out["arm_out"] = True
        if pf.system == "windows":
            out["table_driver"] = "driver_installed"
        return out

    # ---- the start-up of a just-switched-on table ----------------------------------------------
    def start_up(self) -> StepResult:
        why = SESSION_ENDED if self.ended is not None else self._sending_ready()
        if why:
            return self._result("start_up", Kind.REFUSED, why)
        if self._table.state != "cold" or self._table.start_up_sent:
            return self._result("start_up", Kind.REFUSED, "table_not_just_switched_on")
        if self.instrument_out:
            return self._result("start_up", Kind.REFUSED, "instrument_not_in_the_arm")
        if self.stopped_by_person:
            return self._result("start_up", Kind.REFUSED, "stopped_by_person")
        if self.opened_with_arm_out:
            # safety review 448, SHOULD-1: the start-up (i0, then its homing) is recorded only
            # with the arm at its resting place, never with the arm out over the table; the
            # person said it is out, so the job itself refuses it (not only the window)
            return self._result("start_up", Kind.REFUSED, "arm_out_start_up_not_recorded")
        if self._gen is None and self._stale_stop("start_up"):
            return self._result("start_up", Kind.REFUSED, STOPPED_BEFORE_THE_NEXT_MOVE,
                                by_person=True)
        return self._begin("start_up", self._start_up())

    def _start_up(self):
        d = self._table
        ans = yield Ask(Confirm.START_UP)
        if ans != "yes":
            d.close_for_sending("the table has just been switched on; you chose i1Profiler for "
                                "the start-up")
            raise PersonStopped("start_up_left_to_i1profiler")
        self._check_other_program()
        yield from self._hands_off("start_up")
        try:
            d.run_cold_start()
        except Doubt as exc:
            d.cold_failure = _cold_failure_kind(d, exc)
            raise
        return {"start_up_took_s": round(d.start_up_took, 3), "read_before_homing": d.cold_read}

    # ---- readiness (part C's ready(), as ids) ------------------------------------------------
    def _sending_ready(self) -> "str | None":
        if self.stopped_by_person:
            return "stopped_by_person"
        if self.phase != "open" or self._table is None:
            return "table_not_open"
        if self._table.closed_reason is not None:
            return "sending_closed"
        if self._table.motion_unconfirmed:
            return "movement_may_be_unfinished"
        return None

    def _ready(self, step: str) -> "str | None":
        if self.ended is not None and step != "home":
            # review 8, B-1: the session has ended (saved, discarded, nothing read): the person
            # believes it is over and may reach for the sheet; only the offered homing is left,
            # and it asks its own hands-off GO
            return SESSION_ENDED
        why = self._sending_ready()
        if why:
            return why
        d = self._table
        if d.state == "cold":
            return "table_not_started"
        key = STAGE_KEY[step]
        if self.instrument_out and step != "calibrate":
            return "instrument_not_in_the_arm"
        if self.report_due is not None and step != "home":
            return "report_due"
        if self.only_home and step != "home":
            return "only_the_homing_now"
        if key in ("d1", "dz", "d2", "row") and not self.page_has_something_to_read():
            # review 8, M-3: resume / refinement: a page with nothing missing is never aligned
            # or read (the caps from the missing patches hold nothing for it); next_page()
            # goes past it
            return "nothing_missing_on_this_page"
        if key in ("c1", "c2", "row"):
            return self._reading_ready(step)
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
        if step == "home" and d.arm_free is False and d.position_now is not None and \
                not homing_starts_here(d.position_now, d.arm_free, self._cap()):
            # 4.3.48: a HELD arm (the motors keep it where it was read) is never offered the
            # homing where the homing itself would refuse (``_end_of_job``): no recorded homing
            # starts there (the alignment start, say). A free arm may have been moved by hand
            # since its last reading; its homing reads it afresh and decides then, as before.
            return "homing_not_from_here"
        return None

    def _check_other_program(self) -> None:
        if self._other_program is not None and self._other_program() is True:
            self._table.close_for_sending("i1Profiler was started during the session")
            raise Stopped("other_program_started")

    def _stage(self, step: str, body, go: bool = True) -> StepResult:
        """*go*: the step moves the arm, so the page's hands-off GO applies (a calibration and
        the tile reading move nothing, as the tester's C1 and C2)."""
        if self._gen is not None:
            return self._begin(step, None)
        why = self._ready(step)
        if why:
            return self._result(step, Kind.REFUSED, why)
        if self._stale_stop(step):
            return self._result(step, Kind.REFUSED, STOPPED_BEFORE_THE_NEXT_MOVE, by_person=True)

        def gen():
            ask_go = go() if callable(go) else go
            if ask_go and (self._go_page != self.page or self._hands_off_due):
                # once per page (the owner's ruling: no question after every step); the first
                # moving step of a page asks it, with the hands-off reminder the window shows
                ans = yield Ask(Confirm.GO, {"step": step, "page": self.page + 1})
                if ans != "yes":
                    raise PersonStopped("person_chose_back")
                self._go_page = self.page
                if step == "home":
                    # review 8, S-1: the homing is the way back a stop leads to; its fresh GO
                    # is the stop's effect, so a stop pressed before it is used up here
                    self._pause_stop = False
            self._check_other_program()
            key = STAGE_KEY[step]
            self.runs[(self.page, key)] = self.runs.get((self.page, key), 0) + 1
            self._start_block(step)
            try:
                out = yield from body()
            finally:
                self._table.current_step = None
                if step == "home":
                    # review 9, NOTE: a stop pressed while the homing ran is answered by the
                    # homing itself (the way back a stop leads to); it does not outlive it
                    # (the next movement asks GO anyway: the stop cleared it)
                    self._pause_stop = False
            return out
        return self._begin(step, gen())

    # ---- the steps ---------------------------------------------------------------------------
    def park(self) -> StepResult:
        return self._stage("park", self._park)

    def align(self) -> StepResult:
        # final fix round, M-1: when the sheet is to be laid, its question IS the hands-off
        # confirmation (the person lays the sheet, takes the hands away and says so; the arm
        # moves right after it), so no GO is asked before it: a GO first, then "lay the
        # sheet", then a move, was the order review 13 found unsafe
        return self._stage("align", self._align, go=self._align_asks_go)

    def _align_asks_go(self) -> bool:
        d = self._table
        return d is not None and d.arm_free is True and d.mode_on

    def creep(self) -> StepResult:
        return self._stage("creep", self._creep)

    def check_move(self) -> StepResult:
        return self._stage("check_move", self._check_move)

    def home(self) -> StepResult:
        return self._stage("home", self._home)

    # ---- 4.3.48: where the arm is at a START, and the homing after a stop ----------------------
    def where_is_the_arm(self) -> StepResult:
        """After an opening the person answered "arm out": ONE position reading (``;p025``, the
        line a calibration's own rest check sends first), nothing moves. At its resting place:
        ok, and the measurement goes on as usual. Elsewhere: refused ``arm_not_at_rest`` with the
        true state; the way back then says whether ChromIQ may bring it home (HOME_OFFERED, the
        usual homing with its own hands-off GO) or not."""
        step = "where_is_the_arm"
        if self._gen is not None:
            return self._begin(step, None)
        why = SESSION_ENDED if self.ended is not None else self._sending_ready()
        if why:
            return self._result(step, Kind.REFUSED, why)
        if self._table.state == "cold":
            return self._result(step, Kind.REFUSED, "table_not_started")
        return self._begin(step, self._where_is_the_arm())

    def _where_is_the_arm(self):
        d = self._table
        self._step("locate", 1, 0)
        try:
            p = d.position()
        finally:
            d.current_step = None
        d.log("DATA", f"where the arm is at the start: {p}")
        if not (tbl.REST_GUARD.contains(p) and d.arm_free is False and not d.mode_on):
            raise StageFailed("arm_not_at_rest", read=p, at_start=True)
        return {"read": p, "at_rest": True}
        yield  # pragma: no cover  (a generator)

    def _home_after_stop_why(self) -> "str | None":
        """None when ChromIQ may offer to bring the arm home after this stop; else why not. From
        the table's answers only (HOME_AFTER_STOP_REASONS)."""
        d = self._table
        if d is None or self.phase != "open":
            return "table_not_open"
        if self._home_after_stop_tried:
            return "tried_already"
        if d.link_lost_at is not None:
            return "link_lost"
        if d.motion_unconfirmed or d.closed_reason == "a scan move may be pending" or (
                d.last_move and d.last_move[0] == "scan move" and d.last_move[1] is None):
            return "movement_may_be_unfinished"
        if d.state == "cold" or (d.start_up_sent and not d.cold_done):
            return "table_not_started"
        reason = d.closed_reason
        if reason is None:
            return "not_stopped"
        if not reason.startswith(HOME_AFTER_STOP_REASONS):
            return "stop_not_at_a_place_check"
        if d.motions_sent != 0 or d.start_up_sent:
            # safety review 448, MUST-1: the place check "right before the homing" also takes
            # the first reading after ChromIQ's OWN homings of this sitting (the park, the
            # start-up of a just-switched-on table). An arm out there means a homing reported
            # done and did not reach rest: a mechanical doubt, never an offer. The offer is
            # only for an arm FOUND out at a START, before anything moved in this sitting.
            # (The hand-alignment mode, the only way a hand moves the arm, is switched on only
            # at the alignment start, after the drive there: always after a movement.)
            return "moved_in_this_sitting"
        if self.stopped_by_person:
            return "stopped_by_person"
        if self.instrument_out:
            return "instrument_not_in_the_arm"
        p = d.position_now
        if p is None or getattr(d, "read_at_line", None) != d.lines_sent:
            # the reading the stop came with must be the last line the table answered
            return "no_fresh_position_reading"
        if d.arm_free is not False or d.mode_on:
            return "arm_not_held"
        if not homing_starts_here(p, d.arm_free, self._cap()) or \
                not HOME_AFTER_STOP_AREA.contains(p):
            return "homing_not_from_here"
        return None

    def home_after_stop(self) -> StepResult:
        """4.3.48 (the owner: "is there something we could do so this [i1Profiler] would not be
        needed anymore?"): after a stop this job made at a place check (the way back
        HOME_AFTER_STOP), the arm is brought home by ChromIQ's usual homing (``_end_of_job``,
        4.3.47's lines: s0 p0 i1 s0 f0 f4 f4 p0, i1Profiler's own recorded end of a job from a
        held arm plus the reading at rest), after its own hands-off GO, ONCE per session. The
        table module lets exactly these lines through (``Table.reopen_for_homing``), and nothing
        more is sent afterwards, whether the arm got home or not."""
        step = "home_after_stop"
        if self._gen is not None:
            return self._begin(step, None)
        why = self._home_after_stop_why()
        if why:
            return self._result(step, Kind.REFUSED, why)
        return self._begin(step, self._home_after_stop())

    def _home_after_stop(self):
        ans = yield Ask(Confirm.GO, {"step": "home_after_stop", "page": self.page + 1,
                                     "after_a_stop": True})
        if ans != "yes":
            raise PersonStopped("person_chose_back")
        why = self._home_after_stop_why()       # nothing may have changed while it was asked
        if why:
            raise StageFailed(why)
        if self._other_program is not None and self._other_program() is True:
            raise StageFailed("i1profiler_running")
        d = self._table
        self._home_after_stop_tried = True
        stopped_because = d.closed_reason
        d.reopen_for_homing(stopped_because, cp.HOME)
        self.runs[(self.page, "f")] = self.runs.get((self.page, "f"), 0) + 1
        self._start_block("home_after_stop")
        try:
            self._end_of_job(where=HOME_AFTER_STOP_AREA.contains)
        finally:
            d.current_step = None
            d.close_for_sending("the homing after the stop has ended; nothing more is sent in "
                                "this measurement")
        d.log("DATA", f"brought home after the stop ({stopped_because})")
        return {"read": d.position_now, "after": stopped_because}

    def _note(self, note, step: "str | None", about: str) -> "dict | None":
        """The person's own words, into the log (a NOTE line) and into the result block of the
        step they belong to (rewritten), with the time and the step id. An empty note changes
        nothing; a note is never required."""
        text = clean_note(note)
        if not text:
            return None
        d = self._table
        entry = {"words": text, "by": "the person, in their own words", "about": about,
                 "step": step, "t": round(d.t.now(), 3) if d is not None else None}
        self.diag.log("NOTE", f"the person's own words ({about}, step {step or '-'}): {text}")
        b = self._block if self._block is not None else getattr(self, "_last_block", None)
        if b is not None:
            b.setdefault("notes", []).append(entry)
            if b is not self._block:
                self.diag.write_json(f"{b['folder']}/result.json", b)
        else:
            self.session_notes.append(entry)
        return entry

    def add_note(self, note) -> StepResult:
        """The person's words at the end of a session that stopped or failed (or any time)."""
        entry = self._note(note, getattr(self, "_last_block", {}) and
                           self._last_block.get("stage"), "added")
        return self._result("note", Kind.OK, "" if entry else "empty_note")

    def report_after_step(self, answer: str, note=None) -> StepResult:
        """The asking mode's report (the same as answer(REPORT_AFTER_STEP, answer)), with an
        optional note in the person's own words."""
        if self.report_due is None:
            return self._result("report", Kind.REFUSED, "no_report_due")
        step = self.report_due
        res = self._report(answer)
        if res.ok:
            self._note(note, step, f"report: {answer}")
        return res

    def _report(self, value: str) -> StepResult:
        step = self.report_due
        if value not in CHOICES[Confirm.REPORT_AFTER_STEP]:
            return self._result("report", Kind.REFUSED, "not_one_of_the_choices",
                                choices=list(CHOICES[Confirm.REPORT_AFTER_STEP]))
        self.report_due = None
        # final fix round, M-1: "As described" is the hands-off confirmation (its page says so
        # and names the move that follows); any other answer makes the next movement ask GO
        self._hands_off_due = (Confirm.REPORT_AFTER_STEP, value) not in HANDS_OFF_ANSWERS
        self._mark_answered()
        self.reports.append((step, value))
        self.notes.append((f"{step}: report", value))
        self.diag.log("ANSWER", f"{step}: report_after_step -> {value}")
        if value != "as described":
            # review 8, M-1: the person who saw something wrong is the one most likely to reach
            # onto the bed: the homing that is left asks the hands-off GO again
            self._go_page = None
            if step == "start_up":
                self.report_start_up_wrong()
            else:
                self.restrict_to_homing(f"the person's report after {step}: {value}")
        return self._result("report", Kind.OK, "", after=step, answer=value)

    def report_problem(self, kind: str, note=None) -> StepResult:
        res = self._report_problem(kind)
        if kind in PROBLEM_KINDS:
            self._note(note, self.problems[-1][1] if self.problems else None,
                       f"problem: {kind}")
        return res

    def _report_problem(self, kind: str) -> StepResult:
        """B' (the owner's ruling): the person reports a problem, AT ANY TIME and in every state:
        while a step waits for a confirmation, while a line is on its way (from another thread),
        between steps, before the opening and after it. Never lost: it is kept in
        :attr:`problems` and logged, and it acts at once.

        * "stop now": nothing more is ever sent (the line on its way is finished, as the table
          module never cuts one in half); the true state and the way back are returned
          (switch off first when a movement may be waiting). Nothing more is opened either.
        * "something looked or sounded wrong": nothing more moves except the homing (after the
          start-up, with nothing moved since: nothing more is sent at all, as tester 0.6.0);
          a step waiting for a confirmation ends there; a running creep stops at its next
          pause."""
        d = self._table
        step = self._gen_step
        if kind not in PROBLEM_KINDS:
            return self._result("problem", Kind.REFUSED, "not_one_of_the_choices",
                                choices=list(PROBLEM_KINDS))
        self.problems.append((kind, step, d.lines_sent if d is not None else 0))
        self.diag.log("ANSWER", f"problem reported{f' during {step}' if step else ''}: {kind}")
        self._press_cancel("a problem was reported")
        waiting = self._gen is not None and self._pending is not None
        start_up_wrong = (d is not None and d.cold_done and d.motions_sent == d.cold_motions)
        if kind == PROBLEM_STOP_NOW or d is None or start_up_wrong:
            self.stopped_by_person = True
            if kind != PROBLEM_STOP_NOW and start_up_wrong:
                self.report_start_up_wrong()
            if d is not None:
                d.request_stop()
            if waiting:
                self._close_waiting(step)
            if d is not None and (self._gen is None or waiting):
                d.close_for_sending("stopped by you")
            return self._result("problem", Kind.STOPPED, "stopped_by_person", problem=kind,
                                during=step)
        self.restrict_to_homing(f"the person reported: {kind}")
        self._pause_stop = True
        if waiting:
            self._close_waiting(step, kind=Kind.REFUSED, reason="problem_reported")
        return self._result("problem", Kind.OK, "only_the_homing_now", problem=kind,
                            during=step)

    def _close_waiting(self, step, kind=Kind.STOPPED, reason="cancelled_by_person") -> None:
        gen, self._gen, self._pending = self._gen, None, None
        try:
            gen.close()
        except BaseException:         # noqa: BLE001
            pass
        if kind == Kind.STOPPED and self._table is not None:
            self._table.close_for_sending("stopped by you")
        self._end_block(self._result(step, kind, reason))
        self._gen_step = None

    def restrict_to_homing(self, why: str) -> None:
        """The person reported that the table or the arm did something wrong (part C's
        ASK_ARM_WRONG): nothing more moves in this sitting except the homing, and that homing
        asks the hands-off GO again (review 8, M-1: also when no step was waiting)."""
        self.only_home = True
        self._go_page = None
        if self._table is not None:
            self._table.log("DATA", f"only the homing from now on: {why}")

    def report_start_up_wrong(self) -> None:
        """The person saw or heard something wrong during the start-up: nothing more is sent."""
        if self._table is not None:
            self._table.close_for_sending("you saw or heard something wrong during the start-up")

    def note(self, question_id: str, answer: str) -> None:
        """An answer kept for the diagnostics only (it gates nothing)."""
        self.notes.append((question_id, answer))
        self.diag.log("ANSWER", f"{question_id} -> {answer}")

    def person_answered(self, question_id: str, answer: str = "") -> None:
        """Final fix round, M-1: the person answered one of the WINDOW's own questions (the
        mark-3 check, a "Go on", "Carry on", the problem page...). As after any of the job's
        questions, the next movement asks the hands-off GO first, unless the answer is itself
        that confirmation (``HANDS_OFF_WINDOW_ANSWERS``). Ignored while a step runs (its GO was
        given before it started; a page answered then is not a question at the table)."""
        self.notes.append((question_id, answer))
        if self._gen is not None and self._pending is None:
            self.diag.log("ANSWER", f"{question_id} -> {answer} (while a step runs)")
            return
        self._hands_off_due = (question_id, answer) not in HANDS_OFF_WINDOW_ANSWERS
        self._mark_answered()
        self.diag.log("ANSWER", f"{question_id} -> {answer}"
                      + ("" if self._hands_off_due else " (the hands-off confirmation)"))

    def _hands_off(self, step: str, **detail):
        """Final fix round, M-1: before a movement inside a step, the hands-off GO when a
        question was answered since the last one (a generator; asks nothing otherwise)."""
        if not self._hands_off_due:
            return
        ans = yield Ask(Confirm.GO, {"step": step, "page": self.page + 1,
                                     "after_a_question": True, **detail})
        if ans != "yes":
            raise PersonStopped("person_chose_back")
        self._go_page = self.page

    def _motion_guard(self) -> "str | None":
        """The table module's last check before any movement line (a bug guard: the steps ask
        GO themselves)."""
        if self._hands_off_due:
            why = "a movement before the hands-off confirmation that follows a question"
            HANDS_OFF_BREACHES.append(f"{self._gen_step}: {why}")
            del HANDS_OFF_BREACHES[:-50]
            return why
        return None

    def next_page(self) -> StepResult:
        """The next sheet of the chart (only with the arm at rest: every page is aligned on its
        own)."""
        why = SESSION_ENDED if self.ended is not None else self._sending_ready()
        if why:
            return self._result("next_page", Kind.REFUSED, why)
        if self.report_due is not None:
            return self._result("next_page", Kind.REFUSED, "report_due")
        if not (self.at_rest() or self.unread_rest() or self.parked()):
            return self._result("next_page", Kind.REFUSED, "arm_not_at_rest")
        # review 8, M-3: the chart's pages, numbered as the chart numbers them; in a resume or
        # a refinement the pages with nothing missing are passed over (never aligned, so the
        # caps derived from the missing patches stay right)
        later = [pg for pg in range(self.page + 1, self.pages_in_chart())
                 if self.page_has_something_to_read(pg)]
        if not later:
            return self._result("next_page", Kind.REFUSED, "no_more_pages")
        skipped = [pg + 1 for pg in range(self.page + 1, later[0])]
        self.page = later[0]
        self.alignment = self.fit = None
        self.front_need = None
        return self._result("next_page", Kind.OK, page=self.page + 1, passed_over=skipped)

    def pages_in_chart(self) -> int:
        return len(self.sheet.get("pages", []))

    def page_has_something_to_read(self, page: "int | None" = None) -> bool:
        """Whether a page (0-based; None: this one) has a patch this session reads: every page
        when the whole chart is read; in a resume or a refinement only a page with a missing
        patch."""
        pg = self.page if page is None else page
        if self.only_locs is None:
            return True
        try:
            strips = self.sheet["pages"][pg]["strips"]
        except (KeyError, IndexError, TypeError):
            return False
        return any(q.get("loc") in self.only_locs for st in strips for q in st["patches"])

    def pages_to_read(self) -> "list[int]":
        """The pages (1-based, the chart's numbers) with something to read in this session."""
        return [pg + 1 for pg in range(self.pages_in_chart())
                if self.page_has_something_to_read(pg)]

    # ---- helpers (part C's, the questions turned into confirmations) --------------------------
    def _step(self, key: str, lines: int, moves: int) -> None:
        st = _CStep(key, lines, moves)
        self._table.current_step = st
        self._table.step_lines = self._table.step_motions = 0

    def _soft_stop(self) -> None:
        """B': a problem reported while a step runs ends it at the next point the job controls
        (between two recorded steps, before a computed move); the recorded step on its way is
        never cut (the table module runs it whole), and the homing stays possible."""
        if self._pause_stop and self.only_home and self._gen_step not in ("home", None):
            self._pause_stop = False
            raise PersonStopped("problem_reported")

    def _run_b(self, step) -> None:
        self._soft_stop()
        d = self._table
        if step.key == "b_home" and d.state not in C_HOME.needs:
            d.state = "homed"
        d.run_step(C_HOME if step.key == "b_home" else step)

    def _check_rest(self, what: str):
        self._step(f"{self._block['stage']}_rest", 1, 0)
        p = self._table.position()
        self._table.log("DATA", f"{what}: the arm reports {p}")
        if not tbl.REST_GUARD.contains(p):
            self._table.outside_at = p
            raise StageFailed("arm_not_at_rest", read=p)
        return p

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
        """4.3.49 (Basti's ruling of 19 Nov 2026, FOR THE SAFETY REVIEW): a free arm is no
        longer refused for standing outside AREA_RAW (where recordings happened to read it):
        the person's hand put it there, so the mechanism reaches that place, and the move from
        it is judged by its target alone (geo.check_move_from_reading). Only a reading that is
        not a pair of finite numbers is refused."""
        try:
            ok = a is not None and all(math.isfinite(float(v)) for v in a) and len(a) == 2
        except (TypeError, ValueError):
            ok = False
        if not ok:
            raise StageFailed("free_arm_outside_area", read=a)

    def _still(self, a):
        """The stillness check before moving a free arm: two readings within STILL_UNITS."""
        b = self._table.position()
        if abs(a[0] - b[0]) > tbl.STILL_UNITS or abs(a[1] - b[1]) > tbl.STILL_UNITS:
            raise StageFailed("free_arm_moved_between_two_readings", first=a, second=b)
        # 4.3.49: a stable reading of a free arm is a place the opening has been
        due = getattr(self, "_p0_after_aims_due", None)
        if due is not None:
            self._p0_after_aims_due = None
            self.reach_diag["p0_after_aims"].append({
                "p0": list(b), "third_aim_p1": list(due),
                "p0_minus_p1": [b[0] - due[0], b[1] - due[1]],
                "note": "the first free-arm reading after the third aim; the person may have "
                        "moved the arm since"})
        self._learn(b, "free")
        return b

    def _not_at_an_end(self, a, what: str) -> None:
        """4.3.49: no computed move starts within the margin of a known end of this table (the
        analysis, section i; geo.check_start_not_at_an_end is the same rule in geometry, the
        table gate the third). A clean refusal: nothing was sent, a free arm can be moved."""
        side = self.reach.near_end(a) if self.reach is not None else None
        if side:
            d = self._table
            self._reach_note("refused_at_an_end", step=self._gen_step, at=list(a), side=side,
                             what=what)
            raise StageFailed("move_start_at_an_end", read=a, side=side,
                              arm_free=bool(d.arm_free) if d is not None else None,
                              away_mm=self.reach.away_from_end_mm(a, side))

    # ---- 4.3.49: this table's reach (reach.py, FOR THE SAFETY REVIEW) ------------------------
    def _load_reach(self, d) -> None:
        """At the opening, right after the table's memory block was read (before anything can
        move): this table's remembered reach, by its salted key. No key (the block could not be
        hashed): the model's defaults, learned for this sitting only, never stored."""
        key = None
        try:
            key = rc.table_key(getattr(d, "memory_ident", None), self._reach_store.salt())
        except Exception:      # noqa: BLE001 - not remembered, never a guess
            key = None
        try:
            self.reach = self._reach_store.get(key) if key else rc.Reach()
        except Exception:      # noqa: BLE001
            self.reach = rc.Reach()
        self._apply_reach()
        r = self.reach
        self.reach_diag.update({
            "key": key, "remembered": bool(key),
            "model": {"a1": tbl.EXACT_DATA["identity"], "k2": tbl.EXACT_DATA["k2"]},
            "at_open": r.as_dict(), "target_front_at_open_y": self._cap(),
            "defaults": {"front_y": rc.DEFAULT_FRONT_Y, "right_end_x": rc.DEFAULT_RIGHT_END_X,
                         "margin": rc.MARGIN, "end_margin": rc.END_MARGIN,
                         "ceiling_y": geo.FRONT_CAP_Y}})
        self.diag.log("INFO", f"this table's reach: {'key ' + key if key else 'no key, kept for this sitting only'}; "
                              f"front Y {r.front_y} ({r.front_how}), right end X {r.right_end_x} "
                              f"({r.right_how}), guided step {'done' if r.pushed else 'not done'}; "
                              f"targets up to Y {self._cap()}")
        self._write_reach_diag()

    def _apply_reach(self) -> None:
        """The table module's gate checks every computed line against the same bound."""
        d = self._table
        if d is None or self.reach is None:
            return
        d.reach_cap_y = self._cap()
        d.reach_ends = self.reach

    def _learn(self, p, how: str) -> None:
        """Passive growth: a stable free-arm reading, or the reading after a computed move that
        arrived within the tolerance, extends the remembered extremes (stored at once)."""
        r = self.reach
        if r is None:
            return
        t = round(self._table.t.now(), 3) if self._table is not None else None
        if how == "free":
            if len(self.reach_diag["free_readings"]) < 400:
                self.reach_diag["free_readings"].append({"t": t, "at": list(p)})
        elif how == "motor":
            self.reach_diag["motor_arrivals"] += 1
        try:
            grew = r.learn(p, how)
        except ValueError:
            return
        if grew:
            before = self._table.reach_cap_y if self._table is not None else None
            self._apply_reach()
            self.reach_diag["events"].append({"t": t, "learned": how, "at": list(p),
                                              "grew": grew, "target_front_y": self._cap()})
            if self._table is not None and before != self._table.reach_cap_y:
                self.diag.log("DATA", f"this table's reach grew ({how}, at {tuple(p)}): targets "
                                      f"now up to Y {self._cap()}")
            self._reach_save()

    def _reach_save(self) -> None:
        r = self.reach
        if r is None or not r.dirty or not r.key:
            return
        try:
            ok = self._reach_store.put(r)
        except Exception:      # noqa: BLE001 - never in the way of the measurement
            ok = False
        if not ok:
            self.diag.log("INFO", "this table's reach could not be stored this time")

    def _reach_note(self, kind: str, **detail) -> None:
        d = self._table
        entry = dict(detail, kind=kind, t=round(d.t.now(), 3) if d is not None else None)
        bucket = "statuses" if kind == "status" else "refusals"
        if len(self.reach_diag[bucket]) < 200:
            self.reach_diag[bucket].append(entry)

    def _write_reach_diag(self) -> None:
        """reach.json in the session folder (every diagnostics zip): no serial, no unsalted
        hash; the salted key, the extremes and how each was learned, the readings."""
        out = dict(self.reach_diag)
        if self.reach is not None:
            out["now"] = self.reach.as_dict()
            out["target_front_now_y"] = self._cap()
        self.diag.write_json("reach.json", out)

    def _reach_needed(self, need) -> "int | None":
        """The plan's frontmost target beyond this table's target area (None: it fits)."""
        if need is None:
            return None
        return int(need) if int(need) > self._cap() else None

    def _guided_reach(self, need: int):
        """4.3.49, THE GUIDED STEP (a generator; nothing moves): the plan needs targets up to
        *need* and this table's target area ends before it. Shown once per table: the person
        pushes the free arm gently towards the front, as far as it goes, and presses the
        instrument's button (or "pushed" on screen). ChromIQ reads p0 twice, 0.3 s apart, and
        p1 once, each in its recorded read-only form; the reading is taken only when the two p0
        agree within STILL_UNITS. Stored at once. Afterwards: enough (REACH_DONE: pull the arm
        back a little and let go), or refused with how far to lay the sheet back. A table whose
        guided step ran before is never asked again: a plan beyond its end is refused."""
        d, r = self._table, self.reach
        g = self.reach_diag["guided_step"]
        cap0 = self._cap()
        if r.pushed:
            self._reach_note("plan_beyond_the_learned_end", need_y=need, target_front_y=cap0)
            raise StageFailed("aims_beyond_the_reach", need_y=need, target_front_y=cap0,
                              back_mm=geo.reach_advice_mm(need, cap0), pushed_before=True)
        g.update({"ran": True, "need_y": need, "target_front_before_y": cap0, "presses": []})
        moving = False
        for attempt in range(1, REACH_TRIES + 1):
            self._press_start()
            token = self._press_arm(0)
            self._by_button = False
            ans = yield Ask(Confirm.REACH_PUSH, {
                "need_y": need, "target_front_y": cap0,
                "short_mm": geo.reach_advice_mm(need, cap0), "attempt": attempt,
                "moving": moving, "button": token is not None, "button_token": token,
                "button_unavailable": self.button_unavailable,
                "page": self.page + 1})
            by_button, self._by_button = self._by_button, False
            self._press_stop()
            if ans != "pushed":
                g["outcome"] = "lay_back_chosen"
                raise StageFailed("aims_reach_lay_back", need_y=need, target_front_y=cap0,
                                  back_mm=geo.reach_advice_mm(need, cap0), by_person=True)
            self._step("reach", *REACH_CAPS)
            try:
                a = d.position()
                d.c_wait(REACH_STILL_WAIT_S)
                b = d.position()
                sight = d.c_exchange(cl.C_FIXED["aim"], cl.C_DATA_LEN["aim"]).xy()
            finally:
                d.current_step = None
            press = {"attempt": attempt, "p0": [list(a), list(b)], "p1": list(sight),
                     "by_button": by_button}
            g["presses"].append(press)
            self.reach_diag["pairs"].append({"p0": list(b), "p1": list(sight),
                                             "p0_minus_p1": [b[0] - sight[0], b[1] - sight[1]],
                                             "at": "the guided step"})
            d.log("DATA", f"the guided step: p0 reads {a}, {REACH_STILL_WAIT_S:.1f} s later {b}; "
                          f"p1 reads {sight}" + (" (pressed by the instrument's button)"
                                                  if by_button else ""))
            if abs(a[0] - b[0]) > rc.STILL_UNITS or abs(a[1] - b[1]) > rc.STILL_UNITS:
                moving = True
                press["taken"] = False
                continue
            press["taken"] = True
            grew = r.learn_push(b, sight)
            self._apply_reach()
            self._reach_save()
            cap1 = self._cap()
            g.update({"outcome": None, "read_y": b[1], "grew": grew,
                      "target_front_after_y": cap1})
            self.reach_diag["events"].append({"learned": "push", "at": list(b), "grew": grew,
                                              "target_front_y": cap1})
            self._write_reach_diag()
            if need > cap1:
                g["outcome"] = "short"
                raise StageFailed("aims_beyond_the_reach", need_y=need, target_front_y=cap1,
                                  back_mm=geo.reach_advice_mm(need, cap1), pushed_now=True,
                                  gained_mm=max(0, (cap1 - cap0) // 10))
            g["outcome"] = "enough"
            done = yield Ask(Confirm.REACH_DONE, {"gained_mm": max(0, (cap1 - cap0) // 10),
                                                  "need_y": need, "target_front_y": cap1,
                                                  "page": self.page + 1})
            if done != "go on":
                raise PersonStopped("stopped_after_the_reach_step")
            return cap1
        g["outcome"] = "arm_kept_moving"
        raise StageFailed("aims_reach_arm_kept_moving", need_y=need, presses=REACH_TRIES)

    def _mark_answered(self) -> None:
        d = self._table
        self._answered_at_line = d.lines_sent if d is not None else 0

    def _reading_is_stale(self) -> bool:
        """4.3.47 MUST-1: True when ``position_now`` was read before the person's last answer
        or before the motors last let the arm go (f1), so it cannot say where the arm is now."""
        d = self._table
        r = getattr(d, "read_at_line", None)
        if d.position_now is None or r is None:
            return True
        q = self._answered_at_line
        f = getattr(d, "freed_at_line", None)
        return (q is not None and r <= q) or (f is not None and r <= f)

    def _read_again_if_asked(self, a, what: str):
        """4.3.47 MUST-1 (safety review): the reading *a* a computed move is judged from was
        taken before the last question (or the last release of the arm): the arm is read once
        more (the recorded ``;p025``). Moved by more than STILL_UNITS (free arm) or by more than
        the arrival tolerance (held arm) since *a*: the step stops before the move (nothing
        moves; trying the step again reads the arm afresh). Otherwise the move is judged from
        the new reading. Returns the reading to use."""
        if not self._reading_is_stale():
            return a
        d = self._table
        free = bool(d.arm_free)
        b = d.position()
        # the line's number in this sitting (0-based), for the diagnostics and the wire tests
        self.reads_after_question.append(d.lines_sent - 1)
        d.log("DATA", f"{what}: read again after the last question: {b} (before it: {a}; "
                      f"arm {'free' if free else 'held'})")
        tol = tbl.STILL_UNITS if free else 5
        if abs(a[0] - b[0]) > tol or abs(a[1] - b[1]) > tol:
            raise StageFailed("free_arm_moved_while_asked" if free else "arm_moved_while_asked",
                              first=a, second=b)
        if free:
            self._learn(b, "free")
        # a problem reported while this line was on its way is honoured before the move
        self._soft_stop()
        return b

    def _move_to(self, target, what: str, retry_beside: bool = False):
        """One computed m0 from the position just read, checked, timed and arrival-checked (a
        generator: the first-visit confirmation may be asked). 4.3.47 MUST-1: never from a
        reading taken before the last question or the last release of the arm. 4.3.48
        (*retry_beside*, patch rows only): an arrival read twice beside the target by 6..10
        units is moved to once more, see :meth:`_move_again_beside`."""
        self._soft_stop()
        d = self._table
        a = d.position_now
        if a is None:
            raise StageFailed("no_fresh_position_reading")
        self._free_arm_inside(a)
        self._not_at_an_end(a, what)
        geo.check_move_from_reading(a, target, what, d.front_y, self._cap(), self.reach)
        ok = yield from self._confirm_new_part(a, target, what=what)
        if not ok:
            raise PersonStopped("first_visit_declined")
        yield from self._hands_off(self._gen_step or "move")
        b = self._read_again_if_asked(a, what)
        if b is not a:
            # judged again, in full, from where the arm stands now (no question can follow:
            # the new reading lies within 5 units of a part just confirmed, widened by 10)
            self._free_arm_inside(b)
            self._not_at_an_end(b, what)
            geo.check_move_from_reading(b, target, what, d.front_y, self._cap(), self.reach)
            if not self._seg_visited(b, target):
                raise StageFailed("free_arm_moved_while_asked" if d.arm_free
                                  else "arm_moved_while_asked", first=a, second=b)
            a = b
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
            # S-7 (the volunteer's table, 17 Nov 2026: i1Profiler's own arrivals on 48 patches
            # were dx -2..+3, dy -5..+1, one at exactly 5): one reading outside the tolerance is
            # read once more after a short wait, sending nothing in between; the tolerance itself
            # is NOT widened. A second reading outside stops as before.
            first = got
            d.c_wait(ARRIVAL_RECHECK_S)
            got = d.position()
            d.log("DATA", f"{what}: the arm read {first}, {ARRIVAL_RECHECK_S:.1f} s later {got} "
                          f"(target {target}); read again once")
            if not _near(got, target):
                d.outside_at = got
                if _near(got, target, ARRIVAL_BESIDE_UNITS) and _near(first, target,
                                                                       ARRIVAL_BESIDE_UNITS):
                    if retry_beside and self._beside_retry_allowed(got, target):
                        # 4.3.48: once, the same move again from this fresh reading
                        return (yield from self._move_again_beside(a, got, target, what,
                                                                   first=first))
                    d.log("DATA", f"{what}: the arm stands beside the target by "
                                  f"({got[0] - target[0]:+d}, {got[1] - target[1]:+d}) units "
                                  f"(within {ARRIVAL_BESIDE_UNITS}): the step ends cleanly, "
                                  "nothing is read there")
                    raise _ArrivedBeside("arrived_beside_the_target", target=target, read=got)
                raise d._doubt(f"{what}: the arm reads {got}, not {target} (twice)")
        self.driven.append((a, target))
        self._learn(got, "motor")
        return got

    # ---- 4.3.48: one automatic retry of an arrival beside its target ---------------------------
    def _beside_retry_allowed(self, got, target) -> bool:
        """The retry is sent only while this row attempt has one left (cp.BESIDE_RETRIES_PER_ROW),
        the arm is held, the new way lies on the part of the table just confirmed for this row,
        and nothing (a stop, a reported problem) waits."""
        d = self._table
        left = self._beside_retries_left > 0
        ok = (left and d.arm_free is False and not d.motion_unconfirmed
              and self._seg_visited(got, target) and not self._pause_stop)
        if not ok:
            d.log("DATA", f"no automatic second move to {target}: "
                          + ("this row's retries are used up" if not left else
                             "the arm is not held, the way is not confirmed, or a stop waits"))
        return ok

    def _move_again_beside(self, a, got, target, what: str, first=None):
        """4.3.48 (release review 4.3.47, SHOULD-1): the arm read twice beside its target by
        6..10 units after a move that ended normally. The SAME m0 line (the same absolute
        target) is sent once more from the fresh reading *got*, as i1Profiler does on this table
        (23 recorded m0 lines to the previous move's own target, from a fresh p0 0..3 units off:
        R1 285.068, R2 480.292, 18 Nov A 161.408, B 49.904 ...). Its arrival is checked exactly as
        the first one's (read again once after 0.3 s); a second arrival beside fails the row as
        before (``_ArrivedBeside``), beyond 1 mm it is a doubt. Lines: m0, p0 (and the p0 read
        again), at most 3, 1 movement (cp.BESIDE_RETRY).

        Safety review 448, SHOULD-3: every such move is written into the session's diagnostics
        (the row's result block, ``data["second_moves"]``, see diagnostics.py): the target, the
        two readings before it, the reading(s) after it, and whether it cured the miss."""
        d = self._table
        self._beside_retries_left -= 1
        entry = {"what": what, "target": list(target), "read": list(got),
                 "readings_before": [list(first) if first is not None else None, list(got)],
                 "readings_after": [], "cured": None, "result": "not sent",
                 "line": d.lines_sent}
        self.beside_retries.append(entry)
        d.log("DATA", f"{what}: the arm stands beside the target by ({got[0] - target[0]:+d}, "
                      f"{got[1] - target[1]:+d}) units; the same move is sent once more from "
                      "this reading")
        # a stop or a problem reported meanwhile is honoured before the move
        self._between_patches()
        entry["result"] = "sent"
        # no lower bound: a move of a few units may finish at once (i1Profiler's recorded moves
        # to the previous target, 0..3 units, took 0.016 s); its arrival is read in any case
        win = (0.0, geo.move_window(got, target)[1])
        try:
            d.c_exchange(geo.m0_line(target[0], target[1]), 0, window=win,
                         timeout=win[1] + 4.0, late_is_doubt=False)
        except tbl.MoveOutside as exc:
            again = d.position()
            entry["readings_after"].append(list(again))
            entry["took_s"] = round(exc.took, 3)
            if _near(again, target):
                self.driven.append((a, target))
                entry.update(cured=True, result="arrived, but slower than recorded")
                raise StageFailed("movement_late_but_arrived", took=round(exc.took, 3),
                                  window=(round(exc.lo, 2), round(exc.hi, 2))) from None
            entry.update(cured=False, result="slower than recorded and not arrived")
            raise d._doubt(f"{what}: after a slow move the arm reads {again}, not {target}")
        again = d.position()
        entry["readings_after"].append(list(again))
        if not _near(again, target):
            first = again
            d.c_wait(ARRIVAL_RECHECK_S)
            again = d.position()
            entry["readings_after"].append(list(again))
            d.log("DATA", f"{what}: after the second move the arm read {first}, "
                          f"{ARRIVAL_RECHECK_S:.1f} s later {again} (target {target})")
            if not _near(again, target):
                d.outside_at = again
                if _near(again, target, ARRIVAL_BESIDE_UNITS) and _near(first, target,
                                                                         ARRIVAL_BESIDE_UNITS):
                    entry.update(cured=False, result="beside the target again")
                    d.log("DATA", f"{what}: beside the target again, by "
                                  f"({again[0] - target[0]:+d}, {again[1] - target[1]:+d}) "
                                  "units: the row ends cleanly, nothing is read there")
                    raise _ArrivedBeside("arrived_beside_the_target_again", target=target,
                                         read=again)
                entry.update(cured=False, result="more than 1 mm off after the second move")
                raise d._doubt(f"{what}: the arm reads {again}, not {target} (twice, after the "
                               "second move)")
        entry.update(cured=True, result="arrived")
        d.log("DATA", f"{what}: the second move arrived at {again}")
        self.driven.append((a, target))
        self._learn(again, "motor")
        return again
        yield  # pragma: no cover  (a generator)

    def _alignment_homed(self) -> None:
        self.alignment = None
        self.front_need = None
        self.fit = None
        self.worked.discard("d1")
        self.worked.discard("d2")

    # ---- park: the recorded homing at rest -----------------------------------------------------
    def _park(self):
        self._run_b(C_HOME)
        return {"read": self._table.position_now}
        yield  # pragma: no cover  (a generator)

    # ---- align: part C's D1 --------------------------------------------------------------------
    def _align(self):
        d = self._table
        sheet = self.sheet
        aims = sc.aims_of(sheet, self.page)
        if not (d.arm_free is True and d.mode_on):
            ans = yield Ask(Confirm.SHEET_LAID, {"orientation": sheet.get("orientation", ""),
                                                 "hands_off": True})
            if ans != "yes":
                raise PersonStopped("sheet_not_laid")
            # its "yes" is the page's hands-off GO (the page says so, and that the arm moves)
            self._go_page = self.page
            self._check_other_program()
            yield from self._hands_off("align")
            # part B's recorded way out to the alignment start, the arm let go there
            self._run_b(C_HOME)
            self._run_b(C_ALIGN)
            felt = yield Ask(Confirm.ARM_FELT)
            d.out_touch = felt
            if felt != "free":
                raise StageFailed("arm_did_not_give_way_at_the_alignment_start", felt=felt)
        self._step("d1_aims", *D1_CAPS)
        readings = []
        self._soft_stop()
        # round B: the instrument's button may answer each aiming question (never a GO: the
        # hand is on the arm). Started here, ended before anything after the aims runs
        self._press_start()
        try:
            for a in aims:
                token = self._press_arm(a["number"])
                self._by_button = False
                ans = yield Ask(Confirm.AIMED, {"mark": a["number"],
                                                "corner": a.get("corner_on_table", ""),
                                                "target": a.get("target"),
                                                "patch": a.get("patch"),
                                                "button": token is not None,
                                                "button_token": token,
                                                "button_unavailable": self.button_unavailable})
                by_button, self._by_button = self._by_button, False
                self._press_disarm()
                if ans != "aimed":
                    raise PersonStopped("stopped_during_the_aims")
                rep = d.c_exchange(cl.C_FIXED["aim"], cl.C_DATA_LEN["aim"])
                p = rep.xy()
                d.log("DATA", f"aim {a['number']}: p1 reports {p}"
                              + (f" (the centre of corner patch {a.get('patch')})"
                                 if a.get("target") == "patch" else "")
                              + (" (aimed by the instrument's button)" if by_button else ""))
                if by_button:
                    self.button_aims.append((self.page + 1, int(a["number"])))
                    self._block["data"].setdefault("aimed_by_button", []).append(a["number"])
                readings.append(p)
        finally:
            self._press_stop()
        # the safety review's confirmation of step 6 (required): the person's hands were on the
        # free arm for the aims, so the first motor move after them (the creep, the check move
        # or the homing) waits for a hands-off GO again, in both modes (one more question a page)
        self._go_page = None
        d.exchange("status")
        for _ in range(4):
            d._f4("01")
        self._block["data"]["aims"] = readings
        self.reach_diag["aims"].append({"page": self.page + 1, "p1": [list(p) for p in readings]})
        self._p0_after_aims_due = tuple(readings[-1]) if readings else None
        aims_mm = [tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in aims]
        try:
            al = geo.fit_alignment(aims_mm, readings)
        except geo.AlignmentRefused as exc:
            self.align_refusals_in_a_row += 1
            raise StageFailed(alignment_id(str(exc)), log_reason=str(exc),
                              **_rows_beyond(sheet, self.page, aims_mm, readings),
                              **_aims_detail(sheet, self.page, aims, aims_mm, readings,
                                             str(exc)),
                              refusals_in_a_row=self.align_refusals_in_a_row) from None
        self.align_refusals_in_a_row = 0
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
        beyond = self._reach_needed(need)
        if beyond is not None:
            # 4.3.49 ("learn this table's reach once"): the sheet needs more front reach than
            # this table has shown ChromIQ; nothing has moved since the aims
            kept = False
            try:
                yield from self._guided_reach(beyond)
                kept = True
            finally:
                if not kept:
                    self.alignment = None
                    self.fit = None
            out["reach_learned_y"] = self.reach.front_y
            self._block["data"]["reach_target_front_y"] = self._cap()
        if need is not None and need > self.front_reached():
            # review 9, NOTE: ANY way out of the front questions but "go on" + "yes" (a "back",
            # a "no", a stop thrown at the question) leaves the state "back" leaves: no
            # alignment, never an alignment without its front-zone need
            kept = False
            try:
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
                        kept = True
                        return out
            finally:
                if not kept:
                    self.alignment = None
                    self.fit = None
            raise PersonStopped("sheet_to_be_laid_further_back",
                                back_mm=int((need - geo.MEASURING_AREA.ymax) / 10.0) + 1)
        return out

    # ---- creep: part C's DZ ---------------------------------------------------------------------
    def _creep(self):
        d, al = self._table, self.alignment
        need = min(int(self.front_need), self._cap())
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
            yield from self._hands_off("creep")
            here = self._read_again_if_asked(d.position_now, "creep")
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
            self._learn(got, "motor")
            d.log("DATA", f"front zone reached: Y {d.front_y}")
            self._block["data"]["front_zone_reached_y"] = d.front_y
            d.c_wait(cp.CREEP_PAUSE_S)
            if self._pause_stop:
                self._pause_stop = False
                raise PersonStopped("stopped_at_a_creep_pause", front_y=d.front_y)
        return {"front_y": d.front_y}

    def _creep_failed(self, target, got, why: str, **more) -> None:
        self._table.outside_at = got
        self.only_home = True
        self._block["data"]["creep_stopped_at"] = {"target": target, "read": got, "why": why}
        raise StageFailed(f"creep_{why}", target=target, read=got,
                          front_y=self.front_reached(), **more)

    # ---- check_move: part C's D2 -----------------------------------------------------------------
    def _check_move(self):
        d = self._table
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
        return {"read": self._table.position_now}
        yield  # pragma: no cover

    def _end_of_job(self, where=None) -> None:
        """*where* (the homing after a stop only): a further check of the fresh reading, on top of
        ``homing_starts_here`` (HOME_AFTER_STOP_AREA)."""
        d = self._table
        self._step(f"{self._block['stage']}_end", *cp.HOME)
        d.exchange("status")
        last = d.position_now
        got = d.position()
        if last is not None and not _near(got, last) and d.arm_free is False:
            raise d._doubt(f"before the homing the arm reads {got}, not {last}")
        if not homing_starts_here(got, d.arm_free, self._cap()) or (
                where is not None and not where(got)):
            raise StageFailed("homing_only_from_inside_the_area", read=got,
                              arm_free=bool(d.arm_free),
                              **({"push": geo.free_arm_push_advice(got)} if d.arm_free
                                 else {}))
        side = (self.reach.near_end(got) if self.reach is not None and d.arm_free is not False
                else None)
        if side:
            # 4.3.49 (the analysis, section i: the one recorded non-zero status, R1 272.124,
            # was a homing of a FREE arm started at the right stop): never a homing of a free
            # arm from the margin of an end. A HELD arm is left to the homing regions (open
            # decision 1, unchanged): i1Profiler's own held homings from X -1437 and -1438 were
            # clean, and the motors only put the arm where targets may lie (5 mm inside)
            self._reach_note("refused_at_an_end", step="home", at=list(got), side=side)
            raise StageFailed("homing_at_an_end", read=got, side=side,
                              arm_free=bool(d.arm_free),
                              away_mm=self.reach.away_from_end_mm(got, side))
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

    # ==== step 7: READING ========================================================================
    # ---- options, resume ---------------------------------------------------------------------
    def set_options(self, chartread_args=None, options: "sp.ReadOptions | None" = None,
                    only_locs=None, fields_as_built_on: bool = False) -> StepResult:
        """The Measure tab's options for this session (its chartread arguments, or a ReadOptions),
        and optionally the patches to read (a refinement strips file's patches). Sends nothing.
        An option the table cannot honour without changing what is measured is REFUSED (the
        reading steps refuse "option_refused" until it is taken out); one with no meaning on
        the table is dropped with its reason. Resume (-r) reads only what the run's partial
        measurement lacks.

        Fix round 10 (review 10, M-4): *fields_as_built_on* is the person's "Measure the rest
        that way" after ``options_change_the_fields``: the field options (-l -L -n -H) are
        taken from the readings this session builds on instead of the tab's, and everything
        else stays as asked (the resume, its base, the patches to read, -S, -N, -A ...).

        Fix round 10 (open point a): with -r and *only_locs* on a COMPLETE run measurement this
        is a REFINEMENT: only those patches are read again, and the Save replaces exactly their
        readings in the run's measurement (the hand path's guided re-measurement)."""
        if self._gen is not None:
            return self._result("options", Kind.REFUSED, "another_step_waits_for_a_confirmation")
        if self.ended is not None:
            return self._result("options", Kind.REFUSED, SESSION_ENDED)
        if any(self.row_status.values()):
            return self._result("options", Kind.REFUSED, "rows_read_already")
        if self.phase != "new":
            # review 8, S-3: the caps are derived at open() from what is to be read; what is to
            # be read cannot change after it
            return self._result("options", Kind.REFUSED, "already_opened")
        before = (self.options_report, self._requested)
        if chartread_args is not None:
            rep = sp.options_from_chartread_args(chartread_args)
        else:
            rep = sp.OptionsReport(options or sp.ReadOptions())
        if fields_as_built_on:
            rep = self._report_with_fields_built_on(rep)
            if rep is None:
                self.options_report, self._requested = before
                self._apply_locs()
                return self._result("options", Kind.REFUSED, "options_change_the_fields",
                                    field_options=list(FIELD_OPTIONS), as_built_on=False)
        self.options_report = rep
        self._requested = (set(only_locs) if only_locs is not None else None, None)
        self._apply_locs()
        detail = {"used": list(rep.used), "no_meaning": dict(rep.no_meaning),
                  "refused": dict(rep.refused)}
        self.diag.log("INFO", "reading options: " + json.dumps(detail))
        if rep.options.resume and self._earlier_dirs:
            # review 8, S-3: an adoption already reads only what the run's partial measurement
            # and the adopted readings lack (and keeps the partial as its base)
            detail["resume_by_adoption"] = True
        elif rep.options.resume:
            from workflow.measurement_state import Ti3State, classify, unread_locations
            base = Path(self.run.measurement_ti3) if self.run is not None else None
            if base is None or self._chart_ti2 is None or not base.is_file():
                return self._result("options", Kind.REFUSED, "nothing_to_resume", **detail)
            facts = classify(base, self._chart_ti2)
            unread = unread_locations(base, self._chart_ti2)
            asked = self._requested[0]
            if facts.state is Ti3State.COMPLETE and asked:
                # open point a: a refinement re-reads the patches asked for (the strips the
                # quality check named) on the complete measurement, which stays the base
                self._requested = (set(asked), base)
                self._apply_locs()
                detail["refine"] = len(self.only_locs)
            elif facts.state is not Ti3State.PARTIAL or not unread:
                return self._result("options", Kind.REFUSED, "nothing_to_resume",
                                    state=facts.state.value, **detail)
            else:
                self._requested = (set(unread) if asked is None else asked & set(unread),
                                   base)
                self._apply_locs()
                detail["resume_unread"] = len(self.only_locs)
        clash = self._fields_clash(rep.options)
        if clash is not None:
            # review 9, S-2: the readings this session builds on (adopted ones, or the run's
            # partial measurement for a resume) define the fields; an option that would make
            # the new readings unlike them is refused, nothing else changes, so the session can
            # never become impossible to save
            self.options_report, self._requested = before
            self._apply_locs()
            return self._result("options", Kind.REFUSED, "options_change_the_fields",
                                builds_on=clash, asked=shape_of_options(rep.options),
                                field_options=list(FIELD_OPTIONS), **detail)
        built_on = self.built_on_white()
        if built_on is not None and built_on != self.white_asked():
            # review 14, M-2: the readings this session completes (a resume's or refinement's
            # base, or adopted readings) were made with the other white reference; readings of
            # both kinds cannot go into one file, so this is refused BEFORE anything is opened,
            # with what the person can do (the option, or a new measurement)
            self.options_report, self._requested = before
            self._apply_locs()
            return self._result("options", Kind.REFUSED, "built_on_another_white_reference",
                                built_on=built_on, asked=self.white_asked(), **detail)
        if self._earlier_dirs:
            # review 8, S-3: options set after an adoption keep it (never silently undone)
            detail["adopted_still_missing"] = len(self.only_locs or ())
        why = self._dual_refusal(rep.options)
        if why:
            self.options_report, self._requested = before
            self._apply_locs()
            return self._result("options", Kind.REFUSED, why, **detail)
        if not rep.ok:
            return self._result("options", Kind.REFUSED, "option_refused", **detail)
        return self._result("options", Kind.OK, "", **detail)

    def _dual_refusal(self, opts: "sp.ReadOptions") -> "str | None":
        """The dual scan on the table (2026-11-18): an option or a measurement it cannot go on
        with, as the hand dual scan refuses them (reason ids of workflow/dual_scan/reasons.py).
        Never anything without the dual scan."""
        import workflow.dual_scan.storage as S
        base = self._resume_base
        if self.dual is None:
            # a single-scan session never writes into a dual measurement (and the other way)
            if base is not None and S.read_dual_record(base).dual:
                return "mixed_scan_kind"
            return None
        if opts.skip_initial_calibration:
            return "dual_needs_a_calibration"
        if opts.high_res:
            return "dual_high_resolution"
        if base is not None:
            rec = S.read_dual_record(base)
            if not rec.dual and S._has_readings(Path(base)):
                return "mixed_scan_kind"
            if rec.dual and rec.scale is not None and round(rec.scale, 4) != round(
                    self.dual.scale, 4):
                return "mixed_factor"
        return None

    def _report_with_fields_built_on(self, rep: "sp.OptionsReport") -> "sp.OptionsReport | None":
        """*rep* with its field options replaced by those that save what the readings this
        session builds on hold (M-4). Needs the resume's base (or the adoption) to be known:
        it is worked out from the run's measurement as set_options would. None when no
        option set gives that shape."""
        shape = self._adopted_shape if self._earlier_dirs else None
        if shape is None and rep.options.resume and self.run is not None:
            base = Path(self.run.measurement_ti3)
            shape = ms.fields_shape(base) if base.is_file() else None
        if shape is None:
            return rep
        o = replace(rep.options, save_lab=bool(shape.get("lab") and not shape.get("xyz")),
                    save_lab_and_xyz=bool(shape.get("lab") and shape.get("xyz")),
                    no_spectral=not shape.get("spectral"),
                    high_res=bool(shape.get("high_res")))
        if shape_of_options(o) != shape:
            return None
        used = tuple(u for u in rep.used if u not in FIELD_OPTIONS) + o.reader_args_fields()
        return replace(rep, options=o, used=used)

    def _fields_clash(self, opts: "sp.ReadOptions") -> "dict | None":
        """The fields of the readings this session builds on (the adopted sessions' readings,
        else the run's partial measurement a resume completes) when *opts* would save other
        ones; None when they agree or nothing is built on."""
        shape = self._adopted_shape if self._earlier_dirs else None
        if shape is None and self._resume_base is not None:
            shape = ms.fields_shape(self._resume_base)
        if shape is None or shape == shape_of_options(opts):
            return None
        return shape

    def white_asked(self) -> str:
        """The white reference the option asks for: "stored" or "own" (review 14, M-2)."""
        return "stored" if self.stored_tile_white else "own"

    def built_on_white(self) -> "str | None":
        """Review 14, M-2: the white reference of the readings this session builds on (adopted
        readings, else the run's measurement a resume or refinement completes); None when it
        builds on nothing."""
        if self._earlier_dirs and self._adopted_white is not None:
            return self._adopted_white
        if self._resume_base is not None:
            return ms.white_of(self._resume_base)
        return None

    def white_needed(self) -> str:
        """The white reference this session's next calibration must give: the one decided at
        its first calibration, else the one of the readings it builds on, else the option's."""
        return self.session_white or self.built_on_white() or self.white_asked()

    # ---- readiness -----------------------------------------------------------------------------
    def _apply_locs(self) -> None:
        """What this session reads: the patches the options asked for (a refinement's, or a
        resume's), cut to what an adoption still lacks; the base is the run's partial
        measurement either way (review 8, S-3: neither undoes the other)."""
        locs, base = self._requested
        if self._earlier_dirs:
            alocs, abase = self._adopted
            locs = set(alocs) if locs is None else locs & set(alocs)
            base = abase
        self.only_locs, self._resume_base = locs, base

    def _reading_ready(self, step: str) -> "str | None":
        d = self._table
        key = STAGE_KEY[step]
        if self.diag.folder is None:
            return "no_session_folder"
        if not self.options_report.ok:
            return "option_refused"
        rest = self.at_rest() or self.unread_rest() or self.parked()
        if key in ("c1", "c2"):
            if self.runs.get((self.page, key), 0) >= MAX_RUNS[key]:
                return "ran_as_often_as_allowed"
            if not rest:
                return "arm_not_at_rest"
            if key == "c2" and not self._has_white():
                return "needs_calibration"
            return None
        # a row
        if self.alignment is None:
            return "needs_alignment"
        if not self.out_known() and d.arm_free is not True:
            return "arm_not_out_on_the_sheet"
        if not self._has_white():
            return "needs_calibration"
        return None

    def _has_white(self) -> bool:
        return self.calibration is not None or self.options_report.options.skip_initial_calibration

    def calibration_left_s(self) -> "float | None":
        """Seconds the job's own white has left (None: no timed white, e.g. -N)."""
        if self.calibration is None or self.calibration.get("t") is None or self._table is None:
            return None
        return sp.CAL_VALID_S - (self._table.t.now() - self.calibration["t"])

    def _calibration_due_for(self, n: int) -> bool:
        if self.calibration_due:
            return True
        left = self.calibration_left_s()
        return left is not None and left < sp.row_seconds(n) + sp.CAL_MARGIN_S

    def _again_refused(self) -> "str | None":
        if self.rows_again.get(self.page, 0) >= ROWS_READ_AGAIN_PER_PAGE:
            return "rows_read_again_limit"
        return None

    # ---- the reader ------------------------------------------------------------------------
    def _consent_facts(self) -> "list[str]":
        system = self.preflight_seen.system if self.preflight_seen is not None else ""
        return list(READER_CONSENT_FACTS) + (list(READER_CONSENT_FACTS_MAC)
                                             if system == "macos" else [])

    def _start_reader(self, folder: Path, name: str, patches, calibrate: bool,
                      moves_next: bool = False, dual_args=()):
        """Part C's instrument_ready() and spot_reader(): the helper can run, exactly one
        i1Pro 2 and no other instrument, the consent (once in the session, before the FIRST
        reader starts), then the reader. A generator (the consent is a confirmation).
        *moves_next*: the arm moves once the reader is open (a row): a consent answered here
        is followed by the hands-off GO before the reader starts (final fix round, M-1)."""
        if not self._press_join():
            raise StageFailed(BUTTON_WAIT_HOLDS)
        why = self._helper_check()
        if why:
            raise StageFailed(why)
        chk = self._instrument_check()
        self.diag.log("INST", f"instrument check before the reader: {chk.state} "
                              + json.dumps(chk.detail))
        if chk.state != "ok":
            raise StageFailed(f"instrument_{chk.state}", **chk.detail)
        if not self.reader_consent:
            ans = yield Ask(Confirm.READER_CONSENT, {"facts": self._consent_facts()})
            if ans != "yes":
                raise PersonStopped("reader_not_started")
            self.reader_consent = True
        if moves_next:
            yield from self._hands_off(self._gen_step or "read_row")
        self._check_other_program()
        try:
            args = self.options_report.options.reader_args()
            if dual_args:
                args = tuple(args) + tuple(dual_args)
            r = self._reader_factory(folder, name, list(patches), calibrate, args, self.diag.log)
        except (OSError, ValueError, rd.ReaderFailed) as exc:
            raise StageFailed("reader_could_not_start", error=type(exc).__name__) from None
        self.readers_started += 1
        self._open_readers.append(r)
        return r

    @staticmethod
    def _events(r) -> "list[dict]":
        proc = getattr(r, "proc", None)
        return list(getattr(proc, "events", []) or [])

    @staticmethod
    def _alive(r) -> bool:
        proc = getattr(r, "proc", None)
        try:
            return bool(proc.alive()) if proc is not None else True
        except Exception:      # noqa: BLE001
            return False

    def _open_reader(self, r, place) -> None:
        """Until the reader sits on its first patch; then the model it reports must be an
        i1Pro 2 (NEXT_STEPS 3: the helper's own report before the first move)."""
        try:
            r.open(place, timeout=sp.OPEN_TIMEOUT_S)
        except rd.ReaderFailed as exc:
            rid, det = sp.failure_id(str(exc), self._events(r), self._alive(r))
            if self._cal_refused:
                rid, det = self._cal_refused, {}
            self._close_reader(r)
            if rid == "instrument_asks_for_calibration":
                self.calibration_due = True
            raise StageFailed(rid, **det) from None
        model = sp.reported_model(self._events(r))
        if model != sp.I1PRO2_MODEL:
            self._close_reader(r)
            raise StageFailed("wrong_instrument" if model else "instrument_not_reported",
                              model=model)

    def _close_reader(self, r) -> None:
        try:
            r.close()
        except Exception:      # noqa: BLE001 - closing never raises
            pass
        if r in self._open_readers:
            self._open_readers.remove(r)

    def _finish_reader(self, r) -> "Path | None":
        try:
            ti3 = r.finish()
        except Exception:      # noqa: BLE001 - what it saved is kept, the rest is said
            ti3 = None
        if r in self._open_readers:
            self._open_readers.remove(r)
        return Path(ti3) if ti3 is not None else None

    def _close_readers(self) -> None:
        for r in list(self._open_readers):
            self._close_reader(r)

    # ---- round B: the instrument's button as "Aimed" ----------------------------------------
    def _press_start(self) -> None:
        """Start the helper's button wait for this alignment, when it is offered. Never fails
        the step: when it cannot start, the panel's Aimed is the only way (said in the log)."""
        self.button_unavailable = None
        if self._press_factory is None:
            self.button_unavailable = "not_offered"
            return
        if not self.reader_consent:
            # the button wait opens the i1Pro 2 with the ArgyllCMS library, which is what the
            # reader consent is about; before it, the instrument is not opened for a button
            self.button_unavailable = "no_reader_consent"
            self.diag.log("BUTTON", "the instrument's button is not offered for these aims: "
                                    "the reading program has not been agreed to yet")
            return
        if not self._press_join():
            self.button_unavailable = BUTTON_WAIT_HOLDS
            self.diag.log("BUTTON", "the instrument's button is not offered: the last wait "
                                    "still holds the instrument")
            return
        why = self._helper_check()
        if why:
            self.button_unavailable = why
            self.diag.log("BUTTON", f"the instrument's button is not offered: {why}")
            return
        chk = self._instrument_check()
        self.diag.log("INST", f"instrument check before the button wait: {chk.state} "
                              + json.dumps(chk.detail))
        if chk.state != "ok":
            self.button_unavailable = f"instrument_{chk.state}"
            return
        if self.diag.folder is None:
            self.button_unavailable = "no_session_folder"
            return
        try:
            waiter = self._press_factory(self.diag.folder / "button", self.diag.log)
        except HelperWithoutButtonWait:
            self.button_unavailable = "helper_without_button_wait"
            self.diag.log("BUTTON", "the instrument's button is not offered: this helper has no "
                                    "button wait (an older build); the panel's Aimed is the way")
            return
        except Exception as exc:       # noqa: BLE001 - not offered, nothing breaks
            self.button_unavailable = "button_wait_could_not_start"
            self.diag.log("BUTTON", f"the button wait could not start ({type(exc).__name__})")
            return
        with self._press_lock:
            self._press = waiter
        self.diag.log("BUTTON", "the instrument's button may answer the aiming questions "
                                "(a first try: not confirmed on a real table yet; a press "
                                "received is logged as 'button press received')")

    def _press_arm(self, mark) -> "str | None":
        with self._press_lock:
            w = self._press
            if w is None:
                self._press_token = None
                return None
            self._press_seq += 1
            token = f"p{self.page + 1}-m{int(mark)}-{self._press_seq}"
            ok = w.arm(token, BUTTON_WAIT_MS, BUTTON_MIN_MS)
            self._press_token = token if ok else None
        if not ok:
            self.button_unavailable = "button_wait_stopped"
            self.diag.log("BUTTON", "the button wait has stopped; the panel's Aimed is the way")
            return None
        return token

    def _press_disarm(self) -> None:
        with self._press_lock:
            self._press_token = None
            w = self._press
        if w is not None:
            w.disarm()

    def _press_cancel(self, why: str) -> None:
        """Stop, Report a problem, a cancel: the press is no longer taken (from any thread)."""
        with self._press_lock:
            had = self._press_token is not None
            self._press_token = None
            w = self._press
        if w is not None:
            w.disarm()
        if had:
            self.diag.log("BUTTON", f"the wait for the instrument's button was cancelled ({why})")

    def _press_stop(self) -> None:
        """Let go of the button wait. The helper's close runs in the background; a reader (or a
        new wait) first waits for it (``_press_join``)."""
        with self._press_lock:
            w, self._press, self._press_token = self._press, None, None
        if w is None:
            return
        t = threading.Thread(target=_close_quietly, args=(w,), daemon=True)
        self._press_closing = t
        t.start()

    def _press_join(self) -> bool:
        """Final fix round, S-2: wait (at most BUTTON_CLOSE_WAIT_S) until the button wait has
        let go of the i1Pro 2. False: it still holds it; the caller opens nothing (the wait is
        asked again next time, never forgotten)."""
        t = self._press_closing
        if t is None:
            return True
        t.join(BUTTON_CLOSE_WAIT_S)
        if t.is_alive():
            self.diag.log("BUTTON", "the button wait did not let go of the instrument in "
                                    f"{BUTTON_CLOSE_WAIT_S:.0f} s; no reader is opened")
            return False
        self._press_closing = None
        return True

    def press_events(self) -> "list[dict]":
        """What the button wait has reported so far (display only; never acted on here)."""
        with self._press_lock:
            w = self._press
        try:
            return w.events() if w is not None else []
        except Exception:      # noqa: BLE001
            return []

    def button_token(self) -> "str | None":
        """The token a press must carry to answer the aiming question now (None: none)."""
        return self._press_token

    def _press_seen(self, token: str) -> bool:
        return any(ev.get("event") == "press" and ev.get("id") == token
                   for ev in self.press_events())

    def answer_by_button(self, token: str) -> StepResult:
        """A press of the instrument's button, reported by the helper for *token*: the same
        answer as the panel's Aimed, and only that. Ignored (logged, nothing sent, the question
        stays) unless an aiming question waits whose token it is, the helper itself reported a
        press for it, and it was not used before."""
        step = self._gen_step or "none"
        pending = self._pending
        why = None
        if self._gen is None or pending is None or pending.kind not in (Confirm.AIMED,
                                                                        Confirm.REACH_PUSH):
            why = "no_aiming_question"
        elif token in self._press_used:
            why = "used_already"
        elif not token or pending.detail.get("button_token") != token \
                or self._press_token != token:
            why = "not_this_question"
        elif not self._press_seen(token):
            why = "not_reported_by_the_helper"
        if why:
            self.diag.log("BUTTON", f"a press of the instrument's button was ignored ({why})")
            return StepResult(step, Kind.REFUSED, BUTTON_IGNORED, self.state(), self.way_back(),
                              detail={"why": why})
        self._press_used.add(token)
        self._by_button = True
        if pending.kind == Confirm.REACH_PUSH:
            self.diag.log("BUTTON", "button press received: the arm pushed to the front (the "
                                    "guided step)")
            return self._answer(Confirm.REACH_PUSH, "pushed", by=" (by the instrument's button)")
        self.diag.log("BUTTON", f"button press received: mark {pending.detail.get('mark')} "
                                f"aimed by the instrument's button")
        return self._answer(Confirm.AIMED, "aimed", by=" (by the instrument's button)")

    def note_button_ignored(self, why: str) -> None:
        """The window saw a press it did not pass on (nothing waits for it): logged only."""
        self.diag.log("BUTTON", f"a press of the instrument's button was ignored ({why})")

    # ---- calibration (part C's C1, spot white) ----------------------------------------------
    def calibrate(self) -> StepResult:
        """With the arm at its resting place: the reader consent (once), the place, the
        instrument's own calibration. Nothing moves; the arm is read before and after."""
        return self._stage("calibrate", self._calibrate, go=False)

    def _cal_place_ok(self, ev) -> bool:
        """The reader's calibration request (its own prompt, an event): only a reflective white
        is a calibration this job does; the person placed the instrument before the reader
        started (the place confirmation)."""
        cond = str(ev.get("cond", ""))
        if cond and "ref_white" not in cond:
            self._cal_refused = "calibration_kind_unknown"
            self.diag.log("INST", f"the reader asks for a calibration of another kind ({cond})")
            return False
        return True

    def _cal_in_a_row(self, ev) -> bool:
        """The instrument asks for a calibration while a row starts: never done there (the arm
        stands over the sheet); the row ends cleanly and a new white is due."""
        self.calibration_due = True
        self.diag.log("INST", "the instrument asks for a calibration: a new white is due "
                              f"({ev.get('cond', '')}); the row is not read")
        return False

    def _calibrate(self):
        d = self._table
        p = self._check_rest("before opening the instrument")
        if not tbl.REST_RECORDED.contains(p):
            # final fix round, S-1: the white is made only with the arm in the recorded resting
            # box over the tile (Y up to 48, where every recorded calibration was made); from
            # the wider guard (Y 49..80) the recorded homing at rest comes first, after the
            # hands-off GO as before any move
            if self._go_page != self.page or self._hands_off_due:
                ans = yield Ask(Confirm.GO, {"step": "calibrate", "page": self.page + 1,
                                             "homing_before_the_white": True})
                if ans != "yes":
                    raise PersonStopped("person_chose_back")
                self._go_page = self.page
            self._check_other_program()
            self._run_b(C_HOME)
            p = self._check_rest("after the homing before the white")
            if not tbl.REST_RECORDED.contains(p):
                self._table.outside_at = p
                raise StageFailed("arm_not_over_the_tile", read=p)
        folder = self.diag.folder / self._block["folder"]
        # tester C1: the reader first (its checks and the consent), then the place, asked once
        # in the session (the tester asked it at the reader's calibration request)
        reader = yield from self._start_reader(
            folder, "c1_spot", sp.CAL_PATCHES, True,
            dual_args=self._dual_spot_args(folder, self.cal_place) if self.dual else ())
        if self.instrument_out:
            # S-1 (the volunteer's table, 17 Nov 2026: an own-tile calibration failed and the
            # session went on): the instrument may still lie on its own tile, out of the arm.
            # A calibration now is made on the own tile again, never "in the arm" with the
            # instrument outside it; the place is not asked (an answer "table tile" would
            # calibrate on whatever the instrument lies on and leave it out of the arm). The
            # person is asked for "ready" on the own tile and "seated" afterwards, as always.
            self.diag.log("STEP", "the instrument is still out of the arm after a calibration "
                                  "on its own tile that did not finish: calibrating on its own "
                                  "tile again")
            place = "own tile"
        elif self.cal_place is None:
            ans = yield Ask(Confirm.CAL_PLACE, {"recommended": CAL_PLACE_RECOMMENDED,
                                                "measured": CAL_PLACE_MEASURED,
                                                "decision_open": "D-4b"})
            if ans == "stop":
                self._close_reader(reader)
                raise PersonStopped("calibration_not_started")
            place = ans
        else:
            place = self.cal_place
        if place == "own tile":
            ok = yield Ask(Confirm.CAL_OWN_TILE)
            if ok != "ready":
                self._close_reader(reader)
                raise PersonStopped("calibration_not_started")
            # the instrument is out of the arm from here: no white counts (and so no row is
            # read) until a calibration ends with the person's "seated", and nothing moves
            self.calibration = None
            self.instrument_out = True
            # review 8, M-2: the person's hands lift the i1Pro 2 out and seat it back on the
            # arm, as for the aims: the next movement waits for a hands-off GO again
            self._go_page = None
        self._cal_refused = None
        self._open_reader(reader, self._cal_place_ok)
        cal_ok = bool(getattr(reader, "calibrated", False))
        dual_ev = self._dual_event(reader, "dual_calibration") if self.dual is not None else None
        self._close_reader(reader)
        if not cal_ok:
            raise StageFailed("calibration_not_confirmed")
        if self.dual is not None:
            # the dual scan (2026-11-18): the helper read the tile with the UV LED right after
            # the white (10 dark + 5 UV-LED readings, the volts) and kept it for the rows'
            # readers; without it no row could have M1 / M2
            self.dual_calibrations.pop("spot", None)
            if not dual_ev or not dual_ev.get("ok"):
                self.calibration = None
                raise StageFailed("dual_calibration_failed",
                                  why=str((dual_ev or {}).get("why") or "no_dual_calibration"))
            self.dual_calibrations["spot"] = dual_ev
            self.diag.log("STEP", "the dual calibration (the tile with the UV LED) is made and "
                                  "kept for the rows: " + json.dumps(dual_ev))
        strip_white = False
        if self.options_report.options.strip:
            # round B (tester C1): the strip white as well, on the same tile, while the
            # instrument is where it is; the helper's table-scan mode needs its own
            self._strip_white(folder)
            strip_white = True
        self.cal_place = place
        made = d.t.now()
        if place == "own tile":
            # the white counts only once the instrument is back in the arm: no row is read
            # with an instrument the person has not seated again
            self.calibration = None
            ans = yield Ask(Confirm.CAL_RESEAT)
            if ans != "seated":
                raise StageFailed("instrument_not_seated_again")
            self.instrument_out = False
        self._check_rest("after the calibration")
        self._block["data"]["calibration"] = {"place": place}
        out = {"place": place, "valid_s": sp.CAL_VALID_S}
        self._tile_spectrum = None
        tile_read = False
        if place == "own tile" or self.stored_tile_white:
            # final fix round, S-1: the white's LEVEL, on a reading of the table's tile made with
            # it (ArgyllCMS checks only the white's spectral shape). Nothing is read with a white
            # that fails it; the calibration can be made again. After a white on the
            # instrument's own tile this reading is independent of the white; after a white on
            # the table's tile it is taken at the same place, so it can only catch a white far
            # off (there the recorded resting box above is what keeps the opening on the tile),
            # and it is made only when the stored-white option reads the tile anyway.
            out["white_level_y"] = yield from self._white_level_check()
            tile_read = True
        self.calibration = {"place": place, "t": made, "kind": "spot"}
        if strip_white:
            self.strip_calibration = {"place": place, "t": made}
        self.calibration_due = False
        need = self.white_needed()
        decided = self.session_white is not None or self.built_on_white() is not None
        if need == "stored":
            sw = yield from self._stored_white(tile_read=tile_read)
            if not sw.get("used") and decided:
                # review 14, M-2: this session's readings (or the readings it completes) were
                # made with the table's stored values; a white without them would make the
                # session unsaveable. No row is read with this white; calibrate again, or end
                # and save what was read with the first reference
                self.calibration = None
                self.strip_calibration = None
                self.diag.log("STEP", "this calibration is not used: the session's white "
                                      "reference is the table's stored white tile values, and "
                                      f"they could not be used this time ({sw.get('why')}); "
                                      "no row is read with it")
                raise StageFailed("stored_white_refused_later", why=str(sw.get("why", "")),
                                  rows_read=bool(self.session_white is not None))
            out["stored_white"] = sw
        else:
            # D-4b: the log always says which white reference this session uses
            self.white_scale = None
            if self.stored_tile_white:
                self.diag.log("STEP", "white reference: the i1Pro 2's own, kept for the whole "
                                      "session (decided at its first calibration, or by the "
                                      "readings it completes)")
            else:
                self.diag.log("STEP", "white reference: the i1Pro 2's own (the table's stored "
                                      "white tile values are switched off in Preferences > Beta)")
        if self.session_white is None:
            self.session_white = "stored" if self.white_scale else "own"
            self.diag.log("STEP", f"the session's white reference is decided: {self.session_white} "
                                  "(kept for every later calibration of this session)")
        return out

    def _decide_white_by_a_row(self) -> None:
        """Review 14, M-2: a row read before any calibration (-N) decides the session's white
        reference as a first calibration would: the one its readings are made with."""
        if self.session_white is None:
            self.session_white = "stored" if self.white_scale else "own"
            self.diag.log("STEP", f"the session's white reference is decided by its first row: "
                                  f"{self.session_white}")

    def _white_level_check(self):
        """Final fix round, S-1: one reading of the table's white tile at rest with the white
        just made (nothing moves); its Y must be a white tile's (``WHITE_TILE_Y``). Refused:
        no white counts (no row is read), the reason is said, the calibration can be made
        again."""
        try:
            yield from self._read_tile()
        except StageFailed as exc:
            self.calibration = None
            self.strip_calibration = None
            raise StageFailed("white_level_not_checked", why=exc.reason) from None
        y = float(self.tile_readings[-1]["xyz"][1])
        lo, hi = WHITE_TILE_Y
        self.diag.log("STEP", f"the white's level: the table's tile reads Y {y:.2f} with it "
                              f"(a white tile reads {lo:.0f} to {hi:.0f})")
        self._block["data"]["white_level_y"] = round(y, 2)
        if not lo <= y <= hi:
            self.calibration = None
            self.strip_calibration = None
            raise StageFailed("white_level_implausible", tile_y=round(y, 2),
                              lowest=lo, highest=hi)
        return round(y, 2)

    def _stored_white(self, tile_read: bool = False):
        """D-4b: read the table's tile once (at rest, nothing moves) and scale this session's
        white per band to the tile values stored in the table. Any doubt: said, and the session
        measures with the i1Pro 2's own reference (the option's off behaviour). *tile_read*:
        the white's level check has read the tile already (that reading is used)."""
        d = self._table
        self.white_scale = None
        why = ""
        if self.options_report.options.no_spectral:
            why = "stored_white_needs_spectral_values"
        elif d.stored_tile is None:
            why = "stored_white_not_readable"
        else:
            if not tile_read:
                self._tile_spectrum = None
                try:
                    yield from self._read_tile()
                except StageFailed as exc:
                    self.diag.log("STEP", f"the tile reading for the stored white failed "
                                          f"({exc.reason})")
                    why = "stored_white_no_tile_reading"
            if not why:
                factors, why = sp.stored_white_factors(d.stored_tile, self._tile_spectrum)
                if factors is not None:
                    self.white_scale = tuple(round(f, 6) for f in factors)
        if self.white_scale is None:
            self.white_scale_refused = why
            self.diag.log("STEP", f"white reference: the i1Pro 2's own (the table's stored "
                                  f"white tile values not used: {why})")
            self.diag.write_json("white_scale.json", {"used": False, "why": why})
            return {"used": False, "why": why}
        self.white_scale_refused = None
        lo, hi = min(self.white_scale), max(self.white_scale)
        self.diag.log("STEP", f"white reference: the table's stored white tile values (as "
                              f"i1Profiler does); per-band factors from {lo:.3f} to {hi:.3f}")
        self.diag.write_json("white_scale.json", {"used": True, "wavelengths":
                                                  list(sp.STORED_TILE_WL),
                                                  "factors": list(self.white_scale)})
        return {"used": True, "factor_range": [round(lo, 4), round(hi, 4)]}

    # ---- the table's white tile (part C's C2) -------------------------------------------------
    def read_tile(self) -> StepResult:
        return self._stage("read_tile", self._read_tile, go=False)

    def _read_tile(self):
        d = self._table
        self._check_rest("before the reading")
        folder = self.diag.folder / self._block["folder"]
        reader = yield from self._start_reader(folder, "c2_tile", sp.CAL_PATCHES, False)
        rows = []
        try:
            self._cal_refused = None
            self._open_reader(reader, self._cal_in_a_row)
            self._check_rest("right before the reading")
            p = sp.PatchTarget("1", "A1", d.position_now)
            try:
                rec = self._read_patch(reader, p, at=d.position_now)
            except _PatchFailed as f:
                rows.append({"sample_id": "1", "loc": "A1", "why": f.reason})
                raise StageFailed(f.reason, **f.detail) from None
            rows.append(rec)
        finally:
            self._finish_reader(reader)
            self._write_readings(folder, "c2_tile", rows)
        try:
            got = reader.readings.get("A1")
            self._tile_spectrum = list(got.spectrum) if got and got.spectrum else None
        except Exception:      # noqa: BLE001 - no spectrum: the stored white is refused
            self._tile_spectrum = None
        self._check_rest("after the reading")
        self.tile_readings.append({"xyz": rows[0]["xyz"]})
        return {"xyz": rows[0]["xyz"]}

    # ---- a spot row ----------------------------------------------------------------------------
    def rows_left(self) -> "list[int]":
        """The rows of this page not tried yet (1-based), in reading order."""
        done = self.row_status.get(self.page, {})
        return [k + 1 for k in range(sp.rows_on_page(self.sheet, self.page)) if k not in done]

    @property
    def row_kind(self) -> str:
        """How this session reads its rows: "spot" (patch by patch, the default), or "strip"
        (round B: "Patch-by-patch mode (-p)" off, a first try)."""
        return "strip" if self.options_report.options.strip else "spot"

    def read_row(self, row: "int | None" = None, kind: "str | None" = None) -> StepResult:
        """One row of this page (1-based *row*; None: the next row not tried yet). A row tried
        before on this page counts as a row read again (at most two per page). *kind*: the
        session's (:attr:`row_kind`) unless given. A strip row that cannot be read in one strip
        move (too long, or only part of it wanted) is read patch by patch, and said so."""
        kind = kind or self.row_kind
        step = "read_row"
        if self._gen is not None:
            return self._begin(step, None)
        why = self._ready(step)
        if why:
            return self._result(step, Kind.REFUSED, why)
        done = self.row_status.get(self.page, {})
        if row is None:
            left = self.rows_left()
            if not left:
                return self._result(step, Kind.REFUSED, "page_read")
            row = left[0]
        k = int(row) - 1
        if not 0 <= k < sp.rows_on_page(self.sheet, self.page):
            return self._result(step, Kind.REFUSED, "row_not_in_chart", row=row)
        again = k in done
        if again:
            why = self._again_refused()
            if why:
                return self._result(step, Kind.REFUSED, why, row=row,
                                    rows_read_again=self.rows_again.get(self.page, 0))
        fallback = None
        try:
            try:
                plan = (sp.plan_row(self.sheet, self.page, k, self.alignment,
                                    self._table.front_y, cap_y=self._cap(), kind=kind, only_locs=self.only_locs,
                                    dual=True) if self.dual is not None else
                        sp.plan_row(self.sheet, self.page, k, self.alignment,
                                    self._table.front_y, cap_y=self._cap(), kind=kind, only_locs=self.only_locs))
            except sp.RowRefused as exc:
                if kind != "strip" or exc.reason not in ("strip_row_too_long",
                                                         "strip_only_some_patches",
                                                         "dual_row_patches_too_short"):
                    raise
                fallback = exc.reason
                self.diag.log("DATA", f"row {row} is read patch by patch: {exc.reason} "
                                      + json.dumps(exc.detail, default=str))
                plan = sp.plan_row(self.sheet, self.page, k, self.alignment,
                                   self._table.front_y, cap_y=self._cap(), kind="spot", only_locs=self.only_locs)
        except sp.RowRefused as exc:
            return self._result(step, Kind.REFUSED, exc.reason, row=row, **exc.detail)
        except geo.AreaRefused as exc:
            return self._result(step, Kind.REFUSED, area_id(str(exc)), row=row,
                                log_reason=str(exc))
        if not plan.patches:
            self.row_status.setdefault(self.page, {})[k] = "nothing_to_read"
            return self._result(step, Kind.OK, "", row=row, status="nothing_to_read")
        if self._calibration_due_for(len(plan.patches)):
            return self._result(step, Kind.REFUSED, "calibration_due", row=row,
                                left_s=self.calibration_left_s())
        if plan.kind == "strip" and self.strip_calibration is None and \
                not self.options_report.options.skip_initial_calibration:
            return self._result(step, Kind.REFUSED, "needs_strip_calibration", row=row)
        return self._stage(step, lambda: self._read_row(plan, again, fallback))

    def _read_row(self, plan: "sp.RowPlan", again: bool = False, fallback: "str | None" = None):
        if again:
            # counted when the row really starts (after GO), never for a refused request
            self.rows_again[self.page] = self.rows_again.get(self.page, 0) + 1
        if fallback:
            self.strip_fallbacks.setdefault(self.page, {})[plan.index] = fallback
            self._progress(event="strip_fallback", row=plan.index + 1, why=fallback)
        attempt = 1
        while True:
            if plan.kind == "strip" and self.dual is not None:
                rec = yield from self._dual_strip_attempt(plan, attempt)
            elif plan.kind == "strip":
                rec = yield from self._strip_attempt(plan, attempt)
            else:
                rec = yield from self._row_attempt(plan, attempt)
            if rec["status"] == "read":
                self.row_status.setdefault(self.page, {})[plan.index] = "read"
                break
            self.row_status.setdefault(self.page, {})[plan.index] = "failed"
            self._go_page = None          # a failed row: hands may reach in; GO before any move
            ask = Confirm.ROW_FAILED_STRIP if plan.kind == "strip" else Confirm.ROW_FAILED
            ans = yield Ask(ask, {
                "row": plan.index + 1, "page": self.page + 1, "why": rec["why"],
                "loc": rec.get("failed_loc"), "read": len(rec["accepted"]),
                "patches": len(plan.patches), "kind": plan.kind,
                "again_allowed": self._again_refused() is None
                and not self._calibration_due_for(len(plan.patches)),
                "rows_read_again": self.rows_again.get(self.page, 0),
                "calibration_due": self._calibration_due_for(len(plan.patches))})
            if ans == "patch by patch":
                if self._calibration_due_for(len(plan.patches)):
                    raise StageFailed("calibration_due", row=plan.index + 1)
                go = yield Ask(Confirm.GO, {"step": "read_row", "page": self.page + 1,
                                            "row": plan.index + 1, "again": True})
                if go != "yes":
                    raise PersonStopped("person_chose_back", row=plan.index + 1)
                self._go_page = self.page
                self.rows_again[self.page] = self.rows_again.get(self.page, 0) + 1
                plan = sp.plan_row(self.sheet, self.page, plan.index, self.alignment,
                                   self._table.front_y, cap_y=self._cap(), kind="spot", only_locs=self.only_locs)
                self.strip_fallbacks.setdefault(self.page, {})[plan.index] = "chosen_by_you"
                attempt += 1
                continue
            if ans == "again":
                if self._calibration_due_for(len(plan.patches)):
                    raise StageFailed("calibration_due", row=plan.index + 1)
                # the reviewer's recommended variant: the arm moves right after "again", so
                # the hands-off GO is asked first, in both modes
                go = yield Ask(Confirm.GO, {"step": "read_row", "page": self.page + 1,
                                            "row": plan.index + 1, "again": True})
                if go != "yes":
                    raise PersonStopped("person_chose_back", row=plan.index + 1)
                self._go_page = self.page
                self.rows_again[self.page] = self.rows_again.get(self.page, 0) + 1
                attempt += 1
                continue
            if ans == "skip":
                self.row_status[self.page][plan.index] = "skipped"
                rec["status"] = "skipped"
                break
            self.row_status[self.page][plan.index] = "failed"
            raise PersonStopped("stopped_after_a_failed_row", row=plan.index + 1)
        out = {"row": plan.index + 1, "page": self.page + 1, "status": rec["status"],
               "read": len(rec["accepted"]), "patches": len(plan.patches),
               "attempts": attempt, "row_kind": plan.kind}
        if self.strip_fallbacks.get(self.page, {}).get(plan.index):
            out["read_patch_by_patch_because"] = self.strip_fallbacks[self.page][plan.index]
        if self._pause_stop:
            # a stop asked for during the row's last patch: the row has ended, so it is
            # honoured (nothing follows without a new step) and does not reach the next row
            self._pause_stop = False
            out["stop_asked_during_the_last_patch"] = True
            self._go_page = None          # the person pressed stop: GO before the next move
        n_next = len(plan.patches)
        if self._calibration_due_for(n_next):
            out["calibration_due_before_next_row"] = True
        return out

    def _row_attempt(self, plan: "sp.RowPlan", attempt: int):
        """Part C's spot_row, for one row of the page (byte for byte the tester's table lines
        when nothing fails): where the arm is, the first-visit rule for the whole row, the
        reader, then per patch the pace, the move (arrival- and time-checked) and the reading."""
        d = self._table
        n = len(plan.patches)
        self._step("row", *cp.spot_row_step(n))
        self._beside_retries_left = cp.BESIDE_RETRIES_PER_ROW
        self._row_seq += 1
        name = plan.name if attempt == 1 else f"{plan.name}_again{attempt - 1}"
        folder = self.diag.folder / self._block["folder"]
        rec = {"seq": self._row_seq, "page": plan.page + 1, "row": plan.index + 1,
               "attempt": attempt, "kind": plan.kind, "name": name, "status": "started",
               "why": "", "reader_ti3": None, "accepted": [], "failed": [],
               "patches": len(plan.patches),
               "white_scale": list(self.white_scale) if self.white_scale else None}
        self._decide_white_by_a_row()
        readings: "list[dict]" = []
        reader = None
        opened = False
        self._progress(event="row_start", row=plan.index + 1, kind=plan.kind,
                       locs=[p.loc for p in plan.patches])
        try:
            here = d.position()
            self._free_arm_inside(here)
            first = plan.patches[0]
            self._not_at_an_end(here, f"the way to patch {first.loc}")
            geo.check_move_from_reading(here, first.target, f"the way to patch {first.loc}",
                                        d.front_y, self._cap(), self.reach)
            ok = yield from self._confirm_new_part(here, *[p.target for p in plan.patches],
                                                   what=f"row {plan.index + 1}")
            if not ok:
                raise PersonStopped("first_visit_declined")
            reader = yield from self._start_reader(
                folder, name, [(p.sample_id, p.loc) for p in plan.patches], False,
                moves_next=True,
                dual_args=self._dual_spot_args(folder, self.cal_place) if self.dual else ())
            self._cal_refused = None
            self._open_reader(reader, self._cal_in_a_row)
            opened = True
            if self.dual is not None:
                # the dual scan, patch by patch: this row's reader must have taken up the dual
                # tile kept for THIS white (else no patch could have M1 / M2): checked before
                # the arm moves
                dev = self._dual_event(reader, "dual_calibration")
                rec["dual_calibration"] = dev
                if not dev or not dev.get("ok"):
                    self.calibration_due = True
                    raise _RowFailed("dual_calibration_not_kept", "")
            last_t = 0.0
            for i, p in enumerate(plan.patches):
                if i:
                    # held by the motors at the patch just read; a problem or a stop asked for
                    # during that patch is honoured here, before the next move
                    self._between_patches()
                    d.c_wait(max(0.0, sp.PACE_FLOOR_S - last_t))
                elif d.arm_free:
                    self._still(here)
                # fix round 10 (review 10, S-4): announced when the arm really goes there,
                # after the stop check and the pause, never while it still waits at the last one
                self._progress(event="patch_next", row=plan.index + 1, loc=p.loc, index=i)
                try:
                    yield from self._move_to(p.target, f"the move to patch {p.loc}",
                                             retry_beside=True)
                except _ArrivedBeside as exc:
                    # fix2: the row fails cleanly; the person may read it again (fresh reading)
                    raise _RowFailed(exc.reason, p.loc) from None
                self._arrival = (d.lines_sent, d.position_now)
                got = self._patch(reader, p, rec, readings)
                if got.get("plausible"):
                    self._progress(event="patch_read", row=plan.index + 1, loc=p.loc,
                                   xyz=list(got.get("xyz") or []))
                last_t = got["t"]
            rec["status"] = "read"
            self._progress(event="row_end", row=plan.index + 1, status="read")
        except _RowFailed as f:
            self._progress(event="row_end", row=plan.index + 1, status="failed", loc=f.loc)
            rec.update(status="failed", why=f.reason, failed_loc=f.loc)
        except PersonStopped as exc:
            rec.update(status="stopped", why=exc.reason)
            raise
        except BaseException as exc:      # noqa: BLE001 - recorded, then the step ends
            rec.update(status="stopped" if not isinstance(exc, StageFailed) else "failed",
                       why=getattr(exc, "reason", type(exc).__name__))
            raise
        finally:
            if reader is not None:
                if opened:
                    ti3 = self._finish_reader(reader)
                    rec["reader_ti3"] = ti3.name if ti3 is not None and ti3.is_file() else None
                else:
                    self._close_reader(reader)
            rec["accepted"] = [{"sample_id": r["sample_id"], "loc": r["loc"], "xyz": r["xyz"]}
                               for r in readings if r.get("plausible")]
            if self.dual is not None and opened:
                # the dual scan: the row's M1 / M2 files, in step with its readings
                rec["conditions"] = self._dual_row_conditions(
                    folder, folder / rec["reader_ti3"] if rec["reader_ti3"] else None)
                rec["dual_spot_results"] = [
                    {k: ev.get(k) for k in ("ok", "why", "uv_triggers", "volts")}
                    for ev in self._events(reader) if ev.get("event") == "dual_pass_result"]
                if rec["accepted"] and rec["conditions"] is None and rec["status"] == "read":
                    rec.update(status="failed", why="dual_conditions_missing")
                    self._progress(event="row_end", row=plan.index + 1, status="failed",
                                   loc=None)
            self.diag.write_json(f"{self._block['folder']}/{name}{ms.ROW_RECORD_SUFFIX}", rec)
            self._write_readings(folder, name, readings + rec["failed"])
            self._block["data"].setdefault("rows", []).append(
                {k: rec[k] for k in ("page", "row", "attempt", "status", "why", "reader_ti3")}
                | {"read": len(rec["accepted"]), "failed": len(rec["failed"]),
                   # the analysis script's row keys (analyse_session_050.py)
                   "kind": plan.kind, "notes": []})
            self._block["data"]["spot_readings"] = (
                self._block["data"].get("spot_readings", 0) + len(readings))
        return rec

    # ---- round B: a strip row (tester 0.6.0 part C's E2/E3 row, scan.run_row) --------------
    def _strip_white(self, folder: Path) -> None:
        """The strip white (tester C1's first half): the helper's table-scan mode calibrates on
        the tile the instrument is on; nothing is sent to the table."""
        if self._scan_factory is None:
            raise StageFailed("strip_reading_not_available")
        try:
            scan = self._new_scan(folder / "strip")
        except (OSError, ValueError, rd.ReaderFailed) as exc:
            raise StageFailed("reader_could_not_start", error=type(exc).__name__) from None
        self.readers_started += 1
        self._open_readers.append(scan)
        try:
            ev = scan.opened(timeout=sp.OPEN_TIMEOUT_S)
            if not _is_i1pro2(ev.get("model")):
                raise StageFailed("wrong_instrument", model=ev.get("model"))
            scan.calibrate(self._cal_place_ok)
            if self.dual is not None:
                # the dual row: the strip white's tile read with the UV LED as well (recorded:
                # 10 dark + 5 UV-LED readings at the strip integration, the volts), kept
                dev = getattr(scan, "dual_calibration", None)
                self.dual_calibrations.pop("strip", None)
                if not dev or not dev.get("ok"):
                    raise StageFailed("dual_calibration_failed",
                                      why=str((dev or {}).get("why") or "no_dual_calibration"))
                self.dual_calibrations["strip"] = dev
                self.diag.log("STEP", "the strip white's dual calibration is made and kept: "
                                      + json.dumps(dev))
        except rd.ReaderFailed as exc:
            raise StageFailed("strip_calibration_failed", log_reason=str(exc)) from None
        finally:
            self._close_reader(scan)

    def _start_scan(self, folder: Path):
        """The checks of every reader (helper, exactly one i1Pro 2, the consent), then the
        helper's table-scan reader. A generator."""
        if not self._press_join():
            raise StageFailed(BUTTON_WAIT_HOLDS)
        why = self._helper_check()
        if why:
            raise StageFailed(why)
        chk = self._instrument_check()
        self.diag.log("INST", f"instrument check before the strip reader: {chk.state} "
                              + json.dumps(chk.detail))
        if chk.state != "ok":
            raise StageFailed(f"instrument_{chk.state}", **chk.detail)
        if not self.reader_consent:
            ans = yield Ask(Confirm.READER_CONSENT, {"facts": self._consent_facts()})
            if ans != "yes":
                raise PersonStopped("reader_not_started")
            self.reader_consent = True
        # final fix round, M-1: the strip moves once the reader is open
        yield from self._hands_off(self._gen_step or "read_row")
        self._check_other_program()
        if self._scan_factory is None:
            raise StageFailed("strip_reading_not_available")
        try:
            scan = self._new_scan(folder)
        except (OSError, ValueError, rd.ReaderFailed) as exc:
            raise StageFailed("reader_could_not_start", error=type(exc).__name__) from None
        self.readers_started += 1
        self._open_readers.append(scan)
        return scan

    # ---- the i1Pro 2 dual scan on the table (2026-11-18, a first try) ----------------------
    def _new_scan(self, folder: Path):
        """A table-scan reader; with the dual scan its helper is told --i1io-table-dual."""
        if self.dual is None:
            return self._scan_factory(folder, self.diag.log)
        return self._scan_factory(folder, self.diag.log, extra_args=self.dual.scan_args)

    def _dual_spot_args(self, folder: Path, place: "str | None") -> "list[str]":
        """A patch-by-patch reader's dual arguments: the hand dual scan's, the white of the
        tile the calibration is made on, --dual-table, and the row folder's conditions."""
        return self.dual.spot_args(Path(folder) / "conditions", dl.white_for_place(place))

    @staticmethod
    def _dual_event(reader, name: str) -> "dict | None":
        """The reader's LAST event of that name (its helper's own words), or None."""
        for ev in reversed(TableJob._events(reader)):
            if ev.get("event") == name:
                return ev
        return None

    def _dual_row_conditions(self, folder: Path, ti3: "Path | None") -> "dict | None":
        """The M1 / M2 files the patch-by-patch reader wrote for its row file (in step with
        its readings), as names relative to the row folder; None when either is missing."""
        if ti3 is None or not Path(ti3).is_file():
            return None
        import workflow.i1pro3_conditions as ic
        out = {}
        for cond in dl.CONDITIONS:
            f = ic.condition_file(ti3, cond)
            if f is None or not Path(f).is_file() or Path(f) == Path(ti3):
                return None
            out[cond] = Path(f).relative_to(Path(folder)).as_posix()
        return out

    def _strip_attempt(self, plan: "sp.RowPlan", attempt: int):
        """One strip row: the first-visit rule for the way to its start and the run, the front
        rows' two spot moves to the row's ends (tester fix 2), the table-scan reader, then
        tester 0.6.0's scan.run_row (byte for byte its lines), the stream cut by position.
        A pending scan move or a doubt ends the table part (nothing more is sent); a clean
        failure (before the scan move, or a stream that cannot be cut) fails the row."""
        d = self._table
        scan_plan = plan.scan
        self._row_seq += 1
        name = plan.name if attempt == 1 else f"{plan.name}_again{attempt - 1}"
        folder = self.diag.folder / self._block["folder"]
        folder.mkdir(parents=True, exist_ok=True)
        rec = {"seq": self._row_seq, "page": plan.page + 1, "row": plan.index + 1,
               "attempt": attempt, "kind": "strip", "name": name, "status": "started",
               "why": "", "reader_ti3": None, "accepted": [], "failed": [],
               "patches": len(plan.patches), "speed": scan_plan.speed,
               "readings_planned": scan_plan.N, "first_try": True,
               "white_scale": list(self.white_scale) if self.white_scale else None}
        self._decide_white_by_a_row()
        if attempt > 1:
            scan_plan = sc.plan_row(name, scan_plan.start, scan_plan.end, scan_plan.speed,
                                    [sc.Patch(q.sample_id, q.loc, q.xy, q.along_mm, q.half_mm)
                                     for q in scan_plan.patches])
        else:
            scan_plan.name = name
        scan = None
        self._progress(event="row_start", row=plan.index + 1, kind="strip",
                       locs=[p.loc for p in plan.patches])
        try:
            if d.arm_free or d.position_now is None:
                # the free arm (right after the aims) has no fresh reading of where it stands:
                # read it first, so the first-visit rule judges the real way to the row start
                # (scan.run_row then reads it again, twice while free: its stillness check)
                self._step("row_where", 1, 0)
                d.position()
            a0 = d.position_now
            ok = yield from self._confirm_new_part(a0, scan_plan.start, scan_plan.end,
                                                   what=f"row {plan.index + 1}")
            if not ok:
                raise PersonStopped("first_visit_declined")
            scan = yield from self._start_scan(folder)
            try:
                ev = scan.opened(timeout=sp.OPEN_TIMEOUT_S)
            except rd.ReaderFailed as exc:
                raise _RowFailed("strip_reader_did_not_open", "") from exc
            if not _is_i1pro2(ev.get("model")):
                raise _RowFailed("wrong_instrument", "")
            self._soft_stop()
            if self._pause_stop:
                self._pause_stop = False
                raise PersonStopped("stopped_before_the_strip")
            if geo.in_front_zone(scan_plan.start) or geo.in_front_zone(scan_plan.end):
                # tester fix 2: the creep confirmed the front Y at one X only; the strip runs
                # along X, so both ends of the row are first reached by a spot move each
                self._step("row_ends", 9, 2)     # +2: S-7, each arrival read again once
                a = d.position()
                if d.arm_free:
                    self._still(a)
                try:
                    yield from self._move_to(scan_plan.start, f"row {plan.index + 1}'s start")
                    yield from self._move_to(scan_plan.end, f"row {plan.index + 1}'s end")
                except _ArrivedBeside as exc:
                    raise _RowFailed(exc.reason, "") from None
                rec["front_row_ends_confirmed"] = True
            if self._hands_off_due:
                # final fix round, M-1 (never expected: every question of this row is asked
                # before the reader opens, and GO follows it there); no GO is asked with the
                # strip reader open, the row fails cleanly before anything moves
                raise _RowFailed("strip_move_refused_here", "")
            self._step("row", 12, 2)
            self._progress(event="strip_move", row=plan.index + 1, speed=scan_plan.speed)
            guard = self._latency_guard() if self._latency_guard is not None else None
            if guard is not None:
                guard.__enter__()
            try:
                res = sc.run_row(d, scan, scan_plan, d.log, str(folder),
                                 confirm_move=lambda a, b, e=scan_plan.end: (
                                     self._seg_visited(a, b) and self._seg_visited(b, e)))
            finally:
                if guard is not None:
                    try:
                        guard.__exit__(None, None, None)
                    except Exception:      # noqa: BLE001 - never the job's concern
                        pass
            files = sc.save_row(str(folder), res)
            rec["scan"] = {"kind": res.kind, "why": res.why, "notes": res.notes,
                           "files": files, "c4": res.c4, "a3": res.a3}
            if res.kind == "pending":
                raise Doubt("a scan move may be pending", sc.PENDING_TEXT)
            if res.kind == "after_doubt":
                raise Doubt(res.why)
            if res.kind != "done":
                raise _RowFailed(_strip_clean_id(res.why), "")
            self.driven.append((scan_plan.start, scan_plan.end))
            cut = stp.cut_row(scan_plan, str(folder), res.fired)
            stp.save_cut_info(str(folder), name, cut)
            rec["cut"] = {"ok": cut.ok, "reason": cut.reason,
                          "readings_per_patch": cut.info.get("readings_per_patch"),
                          "recogniser": cut.info.get("recogniser")}
            if not cut.ok:
                raise _RowFailed(cut.reason, str(cut.info.get("loc") or ""))
            row_file = f"{name}.strip{stp.ROW_FILE_SUFFIX}"
            stp.write_row_file(str(folder / row_file), cut, self.options_report.options)
            rec["reader_ti3"] = row_file
            rec["accepted"] = stp.accepted_entries(cut, row_file)
            for a in rec["accepted"]:
                self._progress(event="patch_read", row=plan.index + 1, loc=a["loc"],
                               xyz=list(a["xyz"]))
            rec["status"] = "read"
            self._progress(event="row_end", row=plan.index + 1, status="read")
        except _RowFailed as f:
            self._progress(event="row_end", row=plan.index + 1, status="failed", loc=f.loc)
            rec.update(status="failed", why=f.reason, failed_loc=f.loc or None)
        except PersonStopped as exc:
            rec.update(status="stopped", why=exc.reason)
            raise
        except BaseException as exc:      # noqa: BLE001 - recorded, then the step ends
            rec.update(status="stopped" if not isinstance(exc, StageFailed) else "failed",
                       why=getattr(exc, "reason", type(exc).__name__))
            raise
        finally:
            if scan is not None:
                self._close_reader(scan)
            self.diag.write_json(f"{self._block['folder']}/{name}{ms.ROW_RECORD_SUFFIX}", rec)
            self._block["data"].setdefault("rows", []).append(
                {k: rec[k] for k in ("page", "row", "attempt", "status", "why", "reader_ti3")}
                | {"read": len(rec["accepted"]), "failed": 0, "kind": "strip",
                   "notes": (rec.get("scan") or {}).get("notes", [])})
        return rec

    def _dual_strip_attempt(self, plan: "sp.RowPlan", attempt: int):
        """One DUAL row (the i1Pro 2 dual scan on the table, 2026-11-18, a first try): the
        strip row's own checks and lamp pass at 132 (scan.run_row, byte for byte its lines but
        the speed), then straight back with the UV LED (scan.run_row(uv_pass=True): the zero
        m0, c4, d1 210, p0, the same one path to the fire), both passes cut by position, M1 / M2
        worked out by the helper (which proves the UV pass belongs to this row). A pending move
        or a doubt in either pass ends the table part as for a strip row; a clean failure, a cut
        that cannot be made or a UV pass that does not belong fails the row (offered again as
        a row or patch by patch). Every reading of both passes stays in the session folder."""
        d = self._table
        lamp = plan.scan
        self._row_seq += 1
        name = plan.name if attempt == 1 else f"{plan.name}_again{attempt - 1}"
        folder = self.diag.folder / self._block["folder"]
        folder.mkdir(parents=True, exist_ok=True)
        rec = {"seq": self._row_seq, "page": plan.page + 1, "row": plan.index + 1,
               "attempt": attempt, "kind": "strip", "dual": True, "name": name,
               "status": "started", "why": "", "reader_ti3": None, "accepted": [],
               "failed": [], "patches": len(plan.patches), "speed": lamp.speed,
               "readings_planned": lamp.N, "first_try": True, "not_tried_on_a_real_table": True,
               "white_scale": list(self.white_scale) if self.white_scale else None}
        self._decide_white_by_a_row()
        lamp = sc.plan_row(name, lamp.start, lamp.end, lamp.speed,
                           [sc.Patch(q.sample_id, q.loc, q.xy, q.along_mm, q.half_mm)
                            for q in lamp.patches], lamp.aperture_mm, dual=True)
        uv = sp.uv_pass_of(lamp)
        scan = None
        self._progress(event="row_start", row=plan.index + 1, kind="strip",
                       locs=[p.loc for p in plan.patches], dual=True)
        try:
            if d.arm_free or d.position_now is None:
                self._step("row_where", 1, 0)
                d.position()
            a0 = d.position_now
            ok = yield from self._confirm_new_part(a0, lamp.start, lamp.end,
                                                   what=f"row {plan.index + 1}")
            if not ok:
                raise PersonStopped("first_visit_declined")
            scan = yield from self._start_scan(folder)
            try:
                ev = scan.opened(timeout=sp.OPEN_TIMEOUT_S)
            except rd.ReaderFailed as exc:
                raise _RowFailed("strip_reader_did_not_open", "") from exc
            if not _is_i1pro2(ev.get("model")):
                raise _RowFailed("wrong_instrument", "")
            state = scan.dual_state()
            rec["dual_state"] = state
            if not state.get("on"):
                # this instrument cannot do the dual scan (no UV LED, no factory tables)
                raise _RowFailed(str(state.get("why") or "dual_not_available"), "")
            if state.get("tile") != "kept":
                # no dual tile kept for this white: nothing is moved; a new calibration first
                self.calibration_due = True
                raise _RowFailed("dual_calibration_not_kept", "")
            self._soft_stop()
            if self._pause_stop:
                self._pause_stop = False
                raise PersonStopped("stopped_before_the_strip")
            if geo.in_front_zone(lamp.start) or geo.in_front_zone(lamp.end):
                self._step("row_ends", 9, 2)
                a = d.position()
                if d.arm_free:
                    self._still(a)
                try:
                    yield from self._move_to(lamp.start, f"row {plan.index + 1}'s start")
                    yield from self._move_to(lamp.end, f"row {plan.index + 1}'s end")
                except _ArrivedBeside as exc:
                    # 4.3.47 fix2, as for a strip row: beside the target by at most 1 mm, read
                    # twice: the row fails cleanly and may be read again
                    raise _RowFailed(exc.reason, "") from None
                rec["front_row_ends_confirmed"] = True
            if self._hands_off_due:
                raise _RowFailed("strip_move_refused_here", "")
            results = {}
            for which, pplan in (("lamp", lamp), ("uv", uv)):
                if which == "uv":
                    # between the two passes: a stop or a problem reported during the lamp
                    # pass is honoured here, before the UV pass's first line
                    self._soft_stop()
                    if self._pause_stop:
                        self._pause_stop = False
                        raise PersonStopped("stopped_before_the_uv_pass")
                    self._step("row_uv", *cp.DUAL_UV_PASS)
                    # 4.3.47 MUST-1: the UV pass's zero-length m0 and its scan move are judged
                    # from the lamp pass's last reading only when no question was answered
                    # (and the arm not let go) since it; otherwise the arm is read once more
                    # first (the recorded ;p025), and a held arm that moved by more than the
                    # arrival tolerance stops the step before anything moves
                    if d.position_now is not None:
                        self._read_again_if_asked(d.position_now, f"row {plan.index + 1}'s "
                                                  "UV pass")
                else:
                    self._step("row", 12, 2)
                self._progress(event="strip_move", row=plan.index + 1, speed=pplan.speed,
                               dual_pass=which)
                guard = self._latency_guard() if self._latency_guard is not None else None
                if guard is not None:
                    guard.__enter__()
                d.dual_phase = which
                try:
                    res = sc.run_row(
                        d, dl.DualPass(scan, which), pplan, d.log, str(folder),
                        confirm_move=(lambda a, b, e=lamp.end: (self._seg_visited(a, b)
                                                                and self._seg_visited(b, e))),
                        uv_pass=(which == "uv"))
                finally:
                    d.dual_phase = None
                    if guard is not None:
                        try:
                            guard.__exit__(None, None, None)
                        except Exception:      # noqa: BLE001 - never the job's concern
                            pass
                files = sc.save_row(str(folder), res) if which == "lamp" else \
                    _save_pass(str(folder), res)
                results[which] = res
                rec.setdefault("scan", {})[which] = {
                    "kind": res.kind, "why": res.why, "notes": res.notes, "files": files,
                    "c4": res.c4, "a3": res.a3, "start_read": res.start_read,
                    "at_start": res.at_start, "end_xy": res.end_xy,
                    "fired": {k: (res.fired or {}).get(k) for k in
                              ("ok", "got", "lit_sent", "dark_sent", "ms_lit_trig", "pass",
                               "volts")}}
                if res.kind == "pending":
                    raise Doubt("a scan move may be pending", sc.PENDING_TEXT)
                if res.kind == "after_doubt":
                    raise Doubt(res.why)
                if res.kind != "done":
                    cid = _strip_clean_id(res.why)
                    if which == "uv" and cid != "arrived_beside_the_target":
                        cid = "uv_pass_failed_clean"
                    raise _RowFailed(cid, "")
                self.driven.append((pplan.start, pplan.end))
            # both passes ran: cut both by position, then the helper's M1 / M2
            try:
                wl, lrows = sc.read_spec_csv(str(folder / f"{lamp.name}.spec.csv"))
                _wl2, urows = sc.read_spec_csv(str(folder / f"{uv.name}.spec.csv"))
            except (OSError, ValueError):
                raise _RowFailed("strip_readings_unreadable", "") from None
            cut = dl.cut_dual(lamp, uv, lrows, urows)
            cut.wavelengths = list(wl)
            # SHOULD-2 (table safety review, 2026-11-19): the UV pass's timing against the
            # chart's patches; both passes' best-fitting motion starts go into the record so
            # that a real run tells the true values
            timing = dl.uv_timing_fit(lamp, uv, lrows, urows, wl)
            cut.info["uv_timing"] = timing
            _write_json(folder / f"{name}.dual_cut.json",
                        {"ok": cut.ok, "reason": cut.reason, "info": cut.info})
            rec["cut"] = {"ok": cut.ok, "reason": cut.reason,
                          "lamp_readings_per_patch": cut.info.get("lamp_readings_per_patch"),
                          "uv_readings_per_patch": cut.info.get("uv_readings_per_patch")}
            rec["uv_timing"] = timing
            self.diag.log("DATA", f"{name}: best-fitting motion starts: UV "
                          f"{(timing.get('uv') or {}).get('best_motion_start_s')} s (assumed "
                          f"{sc.UV_MOTION_START_AFTER_TRIGGER_S} s), lamp "
                          f"{(timing.get('lamp') or {}).get('best_motion_start_s')} s (assumed "
                          f"{sc.MOTION_START_AFTER_LAMP_S} s); judged {timing.get('checked')}, "
                          f"refused {timing.get('refuse')}; lamp judged "
                          f"{timing.get('lamp_checked')}, refused {timing.get('lamp_refuse')}")
            if not cut.ok:
                raise _RowFailed(cut.reason, str(cut.info.get("loc") or ""))
            if timing.get("lamp_refuse"):
                # SHOULD-A (4.3.48 re-review): the lamp pass judged as the UV pass is
                raise _RowFailed("lamp_pass_timing_off", "")
            if timing.get("refuse"):
                raise _RowFailed("uv_pass_timing_off", "")
            xyz0 = stp._xyz(cut.lamp, cut.wavelengths)
            for q, xyz in zip(plan.patches, xyz0):
                why = sp.plausible(xyz)
                if why or not all(math.isfinite(v) for v in xyz):
                    raise _RowFailed("strip_patch_implausible", q.loc)
            dl.write_dual_in(str(folder / f"{name}.dual_in.txt"), cut)
            comp = scan.dual_compute(name, self.dual.scale)
            rec["dual_compute"] = {k: comp.get(k) for k in ("ok", "why", "pairing", "n",
                                                            "usable")}
            if not comp.get("ok"):
                raise _RowFailed(str(comp.get("why") or "uv_pass_missing"), "")
            try:
                m1, m2 = dl.read_dual_out(str(folder / f"{name}.dual_out.txt"),
                                          len(plan.patches), len(cut.wavelengths))
            except (OSError, ValueError):
                raise _RowFailed("record", "") from None
            white = dl.white_for_place(self.cal_place)
            kws = dl.dual_keywords(self.dual, white)
            row_file = f"{name}.strip{stp.ROW_FILE_SUFFIX}"
            c0 = dl.condition_cut(lamp, cut, cut.lamp)
            stp.write_row_file(str(folder / row_file), c0, self.options_report.options)
            dl.add_keywords(str(folder / row_file), kws)
            conds = {}
            for cond, vals in (("M1", m1), ("M2", m2)):
                f = f"{name}.strip.{cond}{stp.ROW_FILE_SUFFIX}"
                stp.write_row_file(str(folder / f), dl.condition_cut(lamp, cut, vals),
                                   self.options_report.options)
                dl.add_keywords(str(folder / f), kws + [("MEASUREMENT_CONDITION", cond)])
                conds[cond] = f
            rec["reader_ti3"] = row_file
            rec["conditions"] = conds
            rec["accepted"] = stp.accepted_entries(c0, row_file)
            for a in rec["accepted"]:
                self._progress(event="patch_read", row=plan.index + 1, loc=a["loc"],
                               xyz=list(a["xyz"]))
            rec["status"] = "read"
            self._progress(event="row_end", row=plan.index + 1, status="read")
        except _RowFailed as f:
            self._progress(event="row_end", row=plan.index + 1, status="failed", loc=f.loc)
            rec.update(status="failed", why=f.reason, failed_loc=f.loc or None)
        except PersonStopped as exc:
            rec.update(status="stopped", why=exc.reason)
            raise
        except BaseException as exc:      # noqa: BLE001 - recorded, then the step ends
            rec.update(status="stopped" if not isinstance(exc, StageFailed) else "failed",
                       why=getattr(exc, "reason", type(exc).__name__))
            raise
        finally:
            if scan is not None:
                self._close_reader(scan)
            self.diag.write_json(f"{self._block['folder']}/{name}{ms.ROW_RECORD_SUFFIX}", rec)
            self._block["data"].setdefault("rows", []).append(
                {k: rec[k] for k in ("page", "row", "attempt", "status", "why", "reader_ti3")}
                | {"read": len(rec["accepted"]), "failed": 0, "kind": "strip", "dual": True,
                   "notes": [n for v in (rec.get("scan") or {}).values()
                             for n in v.get("notes", [])]})
        return rec

    def _between_patches(self) -> None:
        self._soft_stop()
        if self._pause_stop:
            self._pause_stop = False
            raise PersonStopped("stopped_between_patches")

    def _reading_place_ok(self, p) -> bool:
        """The reading is taken where the patch is: the arm was read on the target after its
        move (or after the fresh reading of a repeat), and nothing was sent since."""
        d = self._table
        lines, at = getattr(self, "_arrival", (None, None))
        return (at is not None and d.position_now == at and lines == d.lines_sent
                and not d.motion_unconfirmed and _near(at, p.target))

    def _read_patch(self, reader, p, at=None) -> dict:
        d = self._table
        if at is None and not self._reading_place_ok(p):
            raise _PatchFailed("reading_off_target", retry=True)
        try:
            r = reader.read(p.loc, timeout=sp.READ_TIMEOUT_S)
        except rd.ReaderFailed as exc:
            alive = self._alive(reader)
            rid, det = sp.failure_id(str(exc), self._events(reader), alive)
            if rid == "instrument_asks_for_calibration":
                self.calibration_due = True
            if self.dual is not None and rid == "reading_failed":
                # the dual scan: the UV half of this patch failed (the helper reads the patch
                # again as one unit): said as such
                last = self._dual_event(reader, "dual_pass_result")
                if last is not None and last.get("ok") is False:
                    det = dict(det, dual_why=str(last.get("why") or ""))
                    raise _PatchFailed("uv_spot_failed", retry=alive, **det) from None
            raise _PatchFailed(rid, retry=alive and rid in sp.RETRYABLE, **det) from None
        why = sp.plausible(r.xyz)
        rec = {"sample_id": p.sample_id, "loc": p.loc, "target": list(p.target),
               "read_at": list(d.position_now) if d.position_now else None,
               "xyz": [float(v) for v in r.xyz] if r.xyz is not None and why !=
               "reading_without_values" else None,
               "t": round(float(getattr(r, "t", 0.0) or 0.0), 3), "plausible": why is None}
        if why:
            raise _PatchFailed(why, retry=True, rec=rec)
        return rec

    def _patch(self, reader, p, rec, readings) -> dict:
        """One patch, read again once from a fresh position reading if the reading failed
        (reader alive and on the patch); a second failure fails the row."""
        d = self._table
        for attempt in (1, 2):
            try:
                got = self._read_patch(reader, p)
                readings.append(got)
                return got
            except _PatchFailed as f:
                rec["failed"].append({"sample_id": p.sample_id, "loc": p.loc, "why": f.reason,
                                      "xyz": (f.detail.get("rec") or {}).get("xyz")})
                if attempt == 2 or not f.retry:
                    raise _RowFailed(f.reason, p.loc) from None
            # the fresh reading of where the arm stands: it must still be on the patch; the
            # reader is sent to the patch again (never trusted to sit on it after a failure)
            if hasattr(reader, "ready_loc"):
                reader.ready_loc = None
            self._drain(reader)
            got = d.position()
            if not _near(got, p.target):
                d.outside_at = got
                raise d._doubt(f"before reading {p.loc} again the arm reads {got}, "
                               f"not {p.target}")
            self._arrival = (d.lines_sent, d.position_now)
        raise _RowFailed("reading_failed", p.loc)      # pragma: no cover

    @staticmethod
    def _drain(reader) -> None:
        """Before a patch is read again: the reader's events still waiting from the failed
        reading (a spot_ready for the next patch, say) are taken off, so that the answer to the
        new "goto" is the one that is read."""
        proc = getattr(reader, "proc", None)
        if proc is None or not hasattr(proc, "poll"):
            return
        for _ in range(200):
            if proc.poll("\x00 none") is None:
                return

    def _write_readings(self, folder: Path, name: str, rows) -> None:
        """The raw readings of a row (tester's <name>.readings.csv; numbers only)."""
        import csv
        import io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["sample_id", "loc", "target_x", "target_y", "read_x", "read_y", "X", "Y",
                    "Z", "seconds", "plausible", "why"])
        for r in rows:
            t = r.get("target") or ("", "")
            at = r.get("read_at") or ("", "")
            x = r.get("xyz") or ("", "", "")
            w.writerow([r.get("sample_id", ""), r.get("loc", ""), *t, *at, *x, r.get("t", ""),
                        r.get("plausible", False), r.get("why", "")])
        try:
            (folder / f"{name}.readings.csv").write_text(buf.getvalue(), encoding="utf-8")
        except OSError:
            pass

    # ---- the measurement (step 7) and the end of a session (step 8) -------------------------
    def _session_dirs(self) -> "list[Path]":
        return list(self._earlier_dirs) + [self.run.i1io_table_session_dir(self.stamp)]

    def _base(self) -> "Path | None":
        """The run's partial measurement this session completes (resume, or an adopted
        interrupted session on top of one), else None."""
        return self._resume_base

    def measurement(self) -> StepResult:
        """This session's readings as one measurement, in the session folder
        (``Run.i1io_table_measurement``): complete or partial, never written into the run."""
        if self.run is None or self.stamp is None or self._chart_ti2 is None:
            return self._result("measurement", Kind.REFUSED, "no_run")
        if self.ended == "discarded":
            return self._result("measurement", Kind.REFUSED, "discarded")
        try:
            a = ms.assemble(self._session_dirs(), self._chart_ti2,
                            self.run.i1io_table_measurement(self.stamp), base_ti3=self._base())
        except OSError as exc:
            # review 8, S-5: a disk error is a named refusal, never an exception that closes
            # the table for sending
            return self._result("measurement", Kind.REFUSED, "measurement_not_written",
                                error=type(exc).__name__)
        self._assembly = a
        extra = {}
        if self.dual is not None and a.state in ("complete", "partial"):
            extra["dual"] = self._dual_measurement(a)
        self.diag.write_json("measurement.json", dict(a.as_dict(), **extra))
        kind = Kind.OK if a.state in ("complete", "partial") else Kind.REFUSED
        return self._result("measurement", kind, a.reason, measurement=a.as_dict(), **extra)

    def _dual_measurement(self, a) -> dict:
        """The dual scan (2026-11-18): M1 and M2 of the assembled measurement, assembled from
        the same row records (each patch from its M0 row) and named by the main file's readings
        as the i1Pro 3 Beta's files are (``conditions/<hash>-M1.ti3``, CHROMIQ_CONDITION_OF,
        MEASUREMENT_CONDITION). Refused (said, logged, M0 stays) when any patch lacks them."""
        from core.file_manager import Run
        import workflow.i1pro3_conditions as ic
        from workflow.measurement_condition import record_condition
        main = Path(a.path)
        self.dual_conditions_refused = None
        self._dual_files = {}
        made = {}
        for cond in dl.CONDITIONS:
            tmp = main.with_name(f"{main.stem}.{cond}.assembled.ti3")
            c = ms.assemble(self._session_dirs(), self._chart_ti2, tmp, base_ti3=self._base(),
                            cond=cond)
            if c.state != a.state or c.read != a.read or set(c.unread) != set(a.unread):
                self.dual_conditions_refused = c.reason or "dual_rows_without_m1_m2"
                self.diag.log("DATA", f"M1 and M2 are not written for this measurement: "
                                      f"{cond} {c.state} {c.reason} " + json.dumps(c.detail))
                return {"conditions": None, "why": self.dual_conditions_refused}
            made[cond] = tmp
        record_condition(main, "M0")
        key = ic.data_block_hash(main)
        for cond, tmp in made.items():
            dest = Run.for_dir(main.parent).condition_ti3(cond, measurement=main)
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(tmp, dest)
            record_condition(dest, cond)
            ic._set_condition_of(dest, key)
            self._dual_files[cond] = dest
        self.diag.log("DATA", "M1 and M2 written beside the measurement (dual scan, a first "
                              f"try): {', '.join(p.name for p in self._dual_files.values())}")
        return {"conditions": {k: v.name for k, v in self._dual_files.items()}, "why": ""}

    def _file_dual_conditions(self, dest: Path) -> dict:
        """After the person's Save: M1 / M2 into the run beside its measurement (named by the
        same readings), and the dual scan's pass record (``Run.dual_pass_record``) with the
        person's choice, so Build Profile starts at it exactly as after a hand dual scan."""
        import shutil
        import workflow.i1pro3_conditions as ic
        from workflow.dual_scan.record import PassRecord
        out = {"conditions": None, "why": self.dual_conditions_refused or ""}
        files = getattr(self, "_dual_files", {}) or {}
        filed = {}
        if not self.dual_conditions_refused and len(files) == len(dl.CONDITIONS):
            for cond, src in files.items():
                to = self.run.condition_ti3(cond)
                if to is None:
                    break
                to.parent.mkdir(parents=True, exist_ok=True)
                tmp = to.with_name(to.name + ".table-part")
                shutil.copyfile(str(src), str(tmp))
                os.replace(tmp, to)
                filed[cond] = to
            if not all(ic.condition_file(dest, c) is not None for c in dl.CONDITIONS):
                filed = {}
                out["why"] = "conditions_not_in_step"
        strips = [f"p{pg + 1}_row{k + 1}" for pg, page in enumerate(self.sheet["pages"])
                  for k in range(len(page["strips"]))]
        rec = PassRecord(strips, chosen=self.dual.chosen)
        have = set(self._assembly.unread)
        if filed:
            for pg, page in enumerate(self.sheet["pages"]):
                for k, st in enumerate(page["strips"]):
                    locs = {q["loc"] for q in st["patches"]}
                    if not (locs & have):
                        rec.helper_strip(f"p{pg + 1}_row{k + 1}", True)
        else:
            for pg, page in enumerate(self.sheet["pages"]):
                for k, st in enumerate(page["strips"]):
                    locs = {q["loc"] for q in st["patches"]}
                    if not (locs & have):
                        rec.helper_lamp_only(f"p{pg + 1}_row{k + 1}",
                                             "uv_pass_missing")
        from core.file_manager import Run
        rec.save(Run.dual_pass_record(dest))
        out["conditions"] = {k: v.name for k, v in filed.items()} if filed else None
        self.diag.log("DATA", "dual scan filed: " + json.dumps(out))
        return out

    def accepted_in_this_session(self) -> int:
        if self.run is None or self.stamp is None:
            return 0
        return sum(len(rec.get("accepted") or []) for _f, rec in
                   ms.row_records([self.run.i1io_table_session_dir(self.stamp)]))

    def end_state(self) -> dict:
        """What the session would leave if it ended now (nothing is sent, nothing filed), in
        the binding specs' terms: ``complete`` (every patch of every page, §3a by location),
        ``partial`` (which pages, rows and patches are missing), or ``nothing_read`` (this
        session accepted no reading: M-END-EMPTY); with the arm's true state and way back."""
        new = self.accepted_in_this_session() + sum(
            len(rec.get("accepted") or []) for _f, rec in ms.row_records(self._earlier_dirs))
        out = {"state": se.EMPTY, "read_in_this_session": self.accepted_in_this_session(),
               "pages": len(self.sheet.get("pages", [])), "way_back": self.way_back(),
               "arm_out": self.out_known() or bool(self._table is not None
                                                   and self._table.arm_free),
               "at_rest": self.at_rest() or self.parked() or self.unread_rest(),
               "measurement_before": self._before_state()}
        if new == 0:
            return out
        res = self.measurement()
        a = getattr(self, "_assembly", None)
        if not res.ok and res.reason == "nothing_read":
            # fix round 10 (found on screen): readings were taken, but none can be filed (the
            # only row they belong to failed before its reader saved them): the session ends
            # as one that read nothing, saying so, instead of an ending that can never end
            out["unfiled"] = new
            return out
        if not res.ok or a is None:
            out.update(state="refused", reason=res.reason)
            return out
        out.update(state=a.state, read=a.read, expected=a.expected,
                   missing=se.missing_by_page(self.sheet, a.unread),
                   rejected=[list(r) for r in a.rejected])
        return out

    def _before_state(self) -> str:
        from workflow.measurement_state import classify
        if self.run is None:
            return "none"
        try:
            return classify(self.run.measurement_ti3, self._chart_ti2).state.value
        except Exception:      # noqa: BLE001 - a question, never a blocker
            return "unreadable"

    def end(self) -> StepResult:
        """The end of the session (M-END), asked only between steps: the session's end state,
        then the person's choice ``save`` (Save and stop), ``keep measuring``, ``discard``
        (Discard and stop); no default. Nothing read in this session: no question, nothing
        saved (M-END-EMPTY). NOTHING MOVES HERE: after save or discard the arm goes home only
        by ``home()`` (its own GO); keep measuring reads on only by ``read_row()`` (its own GO).
        The page's GO is cleared: the person's hands may have been on the bed. Once the session
        has ended (saved, discarded, nothing read), every step but the homing is refused
        ``session_ended`` (review 8, B-1)."""
        if self._gen is not None:
            return self._result("end", Kind.REFUSED, "another_step_waits_for_a_confirmation")
        if self.ended is not None:
            return self._result("end", Kind.REFUSED, f"ended_already_{self.ended}")
        if self.run is None or self.stamp is None:
            # review 8, NOTE: without a run nothing could be counted or saved; "nothing read"
            # would not be true over real readings
            return self._result("end", Kind.REFUSED, "no_run")
        self._go_page = None
        st = self.end_state()
        self.diag.log("INFO", "end of the session asked: " + json.dumps(
            {k: v for k, v in st.items() if k != "missing"}, default=str))
        if st["state"] == se.EMPTY:
            self.ended = "nothing_read"
            self._end_detail = {"ending": "nothing_read", **self._after_end()}
            return self._result("end", Kind.OK, "", **self._end_detail, end_state=st)
        if st["state"] == "refused":
            return self._result("end", Kind.REFUSED, st.get("reason", "measurement_refused"),
                                end_state=st)
        return self._begin("end", self._end(st))

    def _after_end(self) -> dict:
        """What may follow an ending: the homing when it can run (its own GO). Review 8, NOTE:
        the same test the way back uses for HOME_OFFERED (``_ready("home")``), so ``next``
        never names a homing that would be refused (the instrument out of the arm, say).
        4.3.48: after a stop, the homing after the stop when it is offered."""
        ok = self._table is not None and self._ready("home") is None
        if ok:
            return {"next": ["home"]}
        if self._table is not None and self._home_after_stop_why() is None:
            return {"next": ["home_after_stop"]}
        return {"next": []}

    def _end(self, st):
        ans = yield Ask(Confirm.END, {"end_state": st})
        if ans == "keep measuring":
            rows = [{"page": pg["page"], "row": r["row"], "patches": r["patches"]}
                    for pg in st.get("missing", []) for r in pg["rows"]]
            # review 8, NOTE: the missing rows of EVERY page are listed; read_row() reaches
            # only the current page's (``current_page``), the others need next_page()
            return {"ending": "keep_measuring", "missing_rows": rows,
                    "current_page": self.page + 1,
                    "rows_read_again": self.rows_again.get(self.page, 0)}
        # review 9, S-1: only these two calls may save or discard while the ending is shown
        # (the public save()/discard() are refused then), and each one's own result counts
        self._inside_end = True
        try:
            res = self.discard() if ans == "discard" else self.save()
        finally:
            self._inside_end = False
        if ans == "discard":
            if not res.ok:
                raise StageFailed(res.reason, **{**res.detail, **self._after_end()})
            return {"ending": "discarded", **self._after_end(), **res.detail}
        if not res.ok:
            # review 8, S-5: the refusal names what was not done and what may follow (the homing)
            raise StageFailed(res.reason, **{**res.detail, **self._after_end()})
        return {"ending": "saved", **self._after_end(), **res.detail}

    def dismiss_end(self) -> StepResult:
        """The later window's Esc or X on the ending: a withdrawal (measurement_exit_strategy
        note 8b). It takes the option that changes nothing: nothing is saved or discarded and
        NOTHING MOVES; the readings stay where they are and the ending can be asked again."""
        if self._gen is None or self._pending is None or self._pending.kind != Confirm.END:
            return self._result("end", Kind.REFUSED, "no_ending_open")
        gen, self._gen, self._pending = self._gen, None, None
        try:
            gen.close()
        except BaseException:         # noqa: BLE001
            pass
        self._gen_step = None
        self._go_page = None
        self.diag.log("ANSWER", "end: the ending was dismissed (nothing saved, nothing moved)")
        return StepResult("end", Kind.OK, "", self.state(), self.way_back(),
                          detail={"ending": "dismissed"})

    def save(self) -> StepResult:
        """The person's Save: the measurement becomes ``Run.measurement_ti3``, guarded as every
        measurement is (``MeasurementSession``: the run's earlier file copied to ``old/`` and
        C0 recorded first; the verdict of §3b after). A partial one is filed as partial; a later
        START with resume completes it. Never over a measurement the run already has, unless it
        is the partial this session completes. Sends nothing. The window then announces the
        file as after a hand measurement (``detail["announce"]``, the run's measurement)."""
        from workflow.measurement_session import MeasurementSession
        from workflow.measurement_state import can_resume
        # review 8, B-1: Save ends the session in the person's mind; whatever follows (only the
        # homing) asks the hands-off GO again, also when save() is called without end()
        self._go_page = None
        if self._gen is not None and not (self._gen_step == "end" and self._inside_end):
            # review 9, S-1: while the ending (M-END) is shown, only the person's answer to it
            # saves; a direct save() then would make the ending's own answer untrue
            return self._result("save", Kind.REFUSED, "another_step_waits_for_a_confirmation",
                                waiting_step=self._gen_step)
        if self.ended in ("saved", "discarded"):
            return self._result("save", Kind.REFUSED, self.ended)
        res = self.measurement()
        if not res.ok:
            return replace(res, step="save")
        dest = Path(self.run.measurement_ti3)
        if dest.exists() and (self._base() is None
                              or Path(self._base()).resolve() != dest.resolve()):
            return self._result("save", Kind.REFUSED, "run_has_a_measurement_already")
        # review 8, S-4: earlier sessions whose filing was cut off before their result was
        # recorded are settled first (their filing note against the run's file AS IT IS NOW,
        # before this Save changes it)
        se.settle_filed_sessions(self.run, exclude=self.stamp)
        guard = MeasurementSession(dest, self._chart_ti2,
                                   getattr(self.run, "measurement_old_dir", self.run.old_dir))
        try:
            # review 8, S-4: a filing note (the measurement's checksum) in every session folder
            # that goes into this file BEFORE the run's file changes: a crash between the run's
            # .ti3 and session_result.json is then recognised at the next START as saved
            note = se.filing_note(self._assembly.path, self.stamp)
            for sdir in self._session_dirs():
                se.write_json_now(Path(sdir) / ms.FILING, note)
            guard.begin()
            why = ms.file_into_run(self._assembly, self.run, may_replace=self._base())
        except OSError as exc:
            # review 8, S-5: a disk error never closes the table for sending: nothing reached
            # the run (one atomic replace), the readings stay in the session folder, the
            # homing stays offered (its own GO), Save may be asked again
            self.diag.log("INFO", f"the measurement could not be written into the run "
                                  f"({type(exc).__name__}); the readings stay in the session")
            return self._result("save", Kind.REFUSED, "measurement_not_written",
                                error=type(exc).__name__, readings_kept=True,
                                **self._after_end())
        if why:
            return self._result("save", Kind.REFUSED, why)
        try:
            outcome = guard.finish(resumed=self._base() is not None)
        except OSError as exc:
            # filed already (the run holds it); only the verdict could not be judged
            outcome = None
            self.diag.log("INFO", f"the saved measurement could not be judged "
                                  f"({type(exc).__name__})")
        self.ended = "saved"
        restored = bool(outcome is not None and outcome.restored)
        dual_filed = None
        if self.dual is not None and not restored:
            try:
                dual_filed = self._file_dual_conditions(dest)
            except (OSError, ValueError) as exc:
                dual_filed = {"conditions": None, "why": f"not_written_{type(exc).__name__}"}
                self.diag.log("INFO", f"M1 / M2 could not be filed ({type(exc).__name__}); "
                                      "the measurement (M0) is filed")
        detail = {"measurement": self._assembly.as_dict(), "announce": dest.name,
                  "verdict": outcome.verdict.value if outcome else None,
                  "before": outcome.before if outcome else None,
                  "after": outcome.after if outcome else None,
                  "added": outcome.added if outcome else None,
                  "restored": restored,
                  "message_id": outcome.message_id if outcome else None,
                  "archive": outcome.archive.parent.name if outcome and outcome.archive
                  else None,
                  "resume_next": (self._assembly.state == "partial"
                                  and can_resume(dest, self._chart_ti2))}
        if outcome is None:
            detail["verdict_not_judged"] = True
        if dual_filed is not None:
            detail["dual"] = dual_filed
        # review 8, NOTE: "filed" is true only when the run keeps this measurement (a §3b
        # restore, M-TI3-SHRANK / M-TI3-EMPTY, put the earlier file back)
        result = {"filed": not restored, "state": self._assembly.state,
                  "verdict": detail["verdict"], "added": detail["added"],
                  "restored": restored}
        self.diag.write_json(ms.SESSION_RESULT, result)
        # review 8, M-4: the adopted earlier sessions ended in this measurement too; recorded
        # in their own folders, so the next START does not offer them as interrupted
        marked, not_marked = [], []
        for sdir in self._earlier_dirs:
            try:
                se.mark_saved_by(sdir, self.stamp, result)
                marked.append(sdir.name)
            except OSError as exc:
                not_marked.append(sdir.name)
                self.diag.log("INFO", f"an adopted session ({sdir.name}) could not be marked "
                                      f"saved ({type(exc).__name__})")
        if self._earlier_dirs:
            detail["adopted_marked_saved"] = marked
        if not_marked:
            detail["adopted_not_marked"] = not_marked
        self.diag.log("INFO", f"the measurement was saved into the run "
                              f"({self._assembly.state}, {self._assembly.read} readings, "
                              f"verdict {detail['verdict']})")
        return self._result("save", Kind.OK, "", **detail)

    def discard(self) -> StepResult:
        """The person's Discard: nothing goes into the run's measurement, and these readings
        are never used by a later assembly. The session folder (its log and raw readings)
        STAYS in the run, marked (the coordinator's decision of 2026-11-17: diagnostics are
        worth keeping; the owner may change it); ``session_end.set_aside`` moves such folders
        into ``old/`` later, never deletes them."""
        self._go_page = None              # review 8, B-1: as for save()
        if self._gen is not None and not (self._gen_step == "end" and self._inside_end):
            # a step waiting for a confirmation (a GO, say) would read on into a discarded
            # session once answered; review 9, S-1: the ending's own question included (only
            # the person's answer to it discards then)
            return self._result("discard", Kind.REFUSED, "another_step_waits_for_a_confirmation",
                                waiting_step=self._gen_step)
        if self.ended == "saved":
            return self._result("discard", Kind.REFUSED, "saved_already")
        self.ended = "discarded"
        # review 8, S-2 (the coordinator's decision): the person dropped the measurement M-END
        # showed, which held the ADOPTED sessions' readings too: those are discarded with it
        # (folders kept, nothing deleted), and the result names every session set to discarded
        marked, not_marked = [], []
        folders = ([(self.diag.folder, "the person discarded the session", None)]
                   if self.diag.folder is not None else [])
        folders += [(sdir, "discarded with the session that had adopted it", self.stamp)
                    for sdir in self._earlier_dirs]
        for sdir, why, by in folders:
            try:
                se.mark_discarded(sdir, why, by=by)
                marked.append(Path(sdir).name)
            except OSError as exc:
                not_marked.append(Path(sdir).name)
                self.diag.log("INFO", f"a session ({Path(sdir).name}) could not be marked "
                                      f"discarded ({type(exc).__name__})")
        self.diag.log("INFO", "the readings were discarded: nothing was written into the "
                              "run's measurement")
        detail = {"session_folder_kept": True, "discarded_sessions": marked}
        if not_marked:
            detail["not_marked"] = not_marked
        return self._result("discard", Kind.OK, "", **detail)

    # ---- what the next START finds (step 8) -------------------------------------------------
    def earlier_sessions(self) -> "list[dict]":
        """The run's earlier table sessions as this START finds them (saved, discarded,
        interrupted by a crash, a logout or a power cut, with or without a pending marker)."""
        if self.run is None:
            return []
        return [e.as_dict() for e in se.earlier_sessions(self.run, exclude=self.stamp,
                                                         chart_ti2=self._chart_ti2)]

    def adopt_earlier(self, stamp: str, replacing: bool = False) -> StepResult:
        """Complete an INTERRUPTED earlier session: its accepted readings become part of this
        session's measurement, and only the patches still missing (with the run's own partial
        measurement, if any) are read. Before any row is read; sends nothing.

        Fix round 10 (review 10, S-2): *replacing* = the person agreed at START to replace the
        run's measurement (M-REPLACE-*). That measurement then stays where it is, untouched,
        and is not built on; the Save refuses ``run_has_a_measurement_already`` and the window
        archives it only then, at the moment the new one is written. A Discard, an ending
        before anything is read, a crash or a quit leave the run as it was."""
        from workflow.measurement_state import Ti3State, classify
        if self.run is None or self._chart_ti2 is None:
            return self._result("adopt", Kind.REFUSED, "no_run")
        if self.ended is not None:
            return self._result("adopt", Kind.REFUSED, SESSION_ENDED)
        if any(self.row_status.values()):
            return self._result("adopt", Kind.REFUSED, "rows_read_already")
        if self.phase != "new":
            # review 8, S-3: the caps are derived at open() from what is to be read
            return self._result("adopt", Kind.REFUSED, "already_opened")
        try:
            sdir = self.run.i1io_table_session_dir(stamp)
        except ValueError:
            return self._result("adopt", Kind.REFUSED, "not_a_session")
        state = se.session_state(sdir, self.run.measurement_ti3) if sdir.is_dir() else None
        if stamp == self.stamp or state != se.INTERRUPTED:
            return self._result("adopt", Kind.REFUSED, "not_an_interrupted_session",
                                state=state)
        # review 12, M-2 / M-3: only a session read from this very chart, for this place (a
        # verification's date), is ever completed into it
        elsewhere = se.belongs_elsewhere(self.run, sdir, self._chart_ti2)
        if elsewhere:
            return self._result("adopt", Kind.REFUSED, elsewhere)
        live = Path(self.run.measurement_ti3)
        facts = classify(live, self._chart_ti2)
        if replacing and live.exists():
            base = None                    # replaced at Save, never built on
            self._replacing = True
        else:
            if facts.state is Ti3State.COMPLETE:
                return self._result("adopt", Kind.REFUSED, "run_has_a_complete_measurement")
            if live.exists() and facts.state is not Ti3State.PARTIAL:
                return self._result("adopt", Kind.REFUSED, "run_has_a_measurement_already",
                                    state=facts.state.value)
            base = live if facts.state is Ti3State.PARTIAL else None
        probe = self.run.i1io_table_session_dir(self.stamp) / f"adopted-{stamp}.ti3"
        a = ms.assemble(list(self._earlier_dirs) + [sdir], self._chart_ti2, probe,
                        base_ti3=base)
        if a.state not in ("complete", "partial"):
            return self._result("adopt", Kind.REFUSED, a.reason or "nothing_to_adopt")
        shape = ms.fields_shape(a.path) if a.path is not None else None
        if shape is not None and shape != shape_of_options(self.options_report.options):
            # review 9, S-2: the options already set would save other fields than these
            # readings hold; adopting them would make the session impossible to save
            return self._result("adopt", Kind.REFUSED, "options_change_the_fields",
                                builds_on=shape,
                                asked=shape_of_options(self.options_report.options),
                                field_options=list(FIELD_OPTIONS))
        self._earlier_dirs.append(sdir)
        self._adopted_shape = shape
        self._adopted_white = ms.white_of(a.path) if a.path is not None else None
        self._adopted = (set(a.unread), base)
        self._apply_locs()
        self.diag.log("INFO", f"an interrupted session ({stamp}) adopted: {a.read} readings, "
                              f"{len(a.unread)} patches still to read")
        return self._result("adopt", Kind.OK, "", read=a.read,
                            still_missing=len(self.only_locs or ()), state=a.state)

    def discard_earlier(self, stamp: str) -> StepResult:
        """An interrupted earlier session the person does not want: marked discarded (its
        folder stays, never used again). Sends nothing."""
        if self.run is None:
            return self._result("discard_earlier", Kind.REFUSED, "no_run")
        if self.ended is not None:
            return self._result("discard_earlier", Kind.REFUSED, SESSION_ENDED)
        try:
            sdir = self.run.i1io_table_session_dir(stamp)
        except ValueError:
            return self._result("discard_earlier", Kind.REFUSED, "not_a_session")
        if stamp == self.stamp or not sdir.is_dir() or se.session_state(
                sdir, self.run.measurement_ti3) in (se.SAVED, se.DISCARDED):
            return self._result("discard_earlier", Kind.REFUSED, "not_an_interrupted_session")
        if sdir in self._earlier_dirs:
            return self._result("discard_earlier", Kind.REFUSED, "adopted_already")
        se.mark_discarded(sdir, "discarded at a later START")
        return self._result("discard_earlier", Kind.OK, "")

    # ---- the write-ahead "table in use" markers (fix round 10, B-1) -------------------------
    def _write_in_use_markers(self) -> None:
        """Written when the USB is opened, before the first line: if the app is killed, the
        markers stay and the next START asks "switched off and on" before anything is sent.
        A marker holds the stamp only. A marker that cannot be written is logged; nothing
        else changes (close() of a running app acknowledges what it wrote)."""
        places = []
        if self.run is not None and self.stamp is not None:
            places.append(se.in_use_marker(self.run, self.stamp))
        if self.app_marker_place is not None and self.stamp is not None:
            folder, prefix = self.app_marker_place
            places.append(Path(folder) / se.app_in_use_name(prefix, self.stamp))
        for m in places:
            try:
                m.parent.mkdir(parents=True, exist_ok=True)
                m.write_text(json.dumps({"stamp": self.stamp, "what": se.IN_USE_WHAT}),
                             encoding="utf-8")
                self._in_use_markers.append(m)
            except OSError as exc:
                self.diag.log("INFO", f"the 'table in use' marker could not be written "
                                      f"({type(exc).__name__})")

    def _acknowledge_in_use_markers(self) -> None:
        for m in self._in_use_markers:
            try:
                se.acknowledged_path(m).write_text(
                    json.dumps({"acknowledged_by": "the job's close()"}), encoding="utf-8")
            except OSError:
                pass

    def _a_row_failed(self) -> bool:
        """A row failed, was skipped or was read again in this session."""
        return (any(v in ("failed", "skipped") for rows in self.row_status.values()
                    for v in rows.values())
                or any(self.rows_again.values()))

    # ---- close: sends nothing ----------------------------------------------------------------
    def close(self) -> StepResult:
        if self._gen is not None:
            self.cancel()
        self._press_stop()
        self._press_join()
        self._close_readers()
        d = self._table
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
        if st.strip_move_may_be_pending and self.app_marker_place is not None:
            # review 9, NOTE: and one app-level marker, so a START on another run or project
            # asks too (the stamp only; no path, no name)
            folder, prefix = self.app_marker_place
            stamp = self.stamp or time.strftime("%Y%m%d-%H%M%S")
            try:
                Path(folder).mkdir(parents=True, exist_ok=True)
                (Path(folder) / f"{prefix}{stamp}.json").write_text(
                    json.dumps({"stamp": stamp, "what": "a strip move may still wait"}),
                    encoding="utf-8")
            except OSError:
                pass
        if self.transport is not None:
            try:
                self.transport.close()
            except Exception:      # noqa: BLE001 - closing never raises
                pass
        # fix round 10 (B-1): the session ended through close(): its write-ahead markers are
        # acknowledged (a strip move that may still wait has its own marker above)
        self._acknowledge_in_use_markers()
        if d is not None:
            self.diag.log("INFO", f"result: table {d.state or 'not asked'}; "
                                  f"{d.lines_sent} lines sent, {d.motions_sent} movements; "
                                  f"move times {[(k, round(t, 3)) for k, t in d.timings]}; "
                                  f"way back {wb}")
            self.diag.log("INFO", "the job has let go of the table's USB connection (nothing is "
                                  "sent when it does)")
        clean = (self.ask_after_each_step and d is not None and d.motions_sent > 0
                 and not self.problems and not self.stopped_by_person and not self.only_home
                 # fix round 10 (open point e): never after a Stop or a failed / skipped row
                 and not self.stop_pressed and not self._a_row_failed()
                 and self.report_due is None
                 and all(a == "as described" for _s, a in self.reports)
                 and d.closed_reason == "the session is over" and wb == WayBack.NONE
                 and not st.movement_may_be_unfinished and not st.link_lost)
        detail = {"offer": MAY_OFFER_DO_NOT_ASK_AGAIN} if clean else {}
        if clean:
            self.diag.log("INFO", "a clean measurement in the asking mode: the window may offer "
                                  "not to ask after each step")
        if self.session_notes:
            self.diag.write_json("notes.json", self.session_notes)
        # step 8: the session's summary (beside summary.json, which the analysis script and
        # the log's RESULT blocks already carry): how it ended, and what it read
        self.diag.write_json("session_summary.json", {
            "job": JOB_VERSION, "ending": self.ended or "no_ending",
            "pages": len(self.sheet.get("pages", [])),
            "rows": {str(pg + 1): {str(r + 1): v for r, v in rows.items()}
                     for pg, rows in self.row_status.items()},
            "rows_read_again": {str(k + 1): v for k, v in self.rows_again.items()},
            "accepted_readings": self.accepted_in_this_session(),
            "calibration_place": self.cal_place, "problems": [p[0] for p in self.problems],
            "reports": self.reports, "way_back": wb,
            "adopted": [d.name for d in self._earlier_dirs]})
        self.phase = "closed"
        if self.reach is not None:
            self._reach_save()
            self._write_reach_diag()
        self.diag.finish()
        return StepResult("close", Kind.OK, "", st, wb, detail=detail)


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


def _corner_patches_mm(sheet: dict, page: int, aims_mm) -> "list[tuple[float, float]]":
    """The patch nearest each mark, as the sheet lies on the table (mm): on a chart with
    crosses, the coloured corner patch beside each cross (i1Profiler's charts are aimed at
    those)."""
    cells = [tuple(sc.sheet_table_mm(sheet, q["centre_mm"]))
             for st in sheet["pages"][page]["strips"] for q in st["patches"]]
    if not cells:
        return []
    return [min(cells, key=lambda c: math.dist(c, m)) for m in aims_mm]


def _aims_detail(sheet: dict, page: int, aims, aims_mm, readings, reason: str) -> dict:
    """4.3.49 (the volunteer's run of 19 Nov 2026): what the refusal page needs to say WHY and
    WHAT TO DO, as numbers and ids only: the mark that lay outside and by how much, the two
    lengths that did not match, how far the sheet would have to lie elsewhere, and whether the
    aims fit the corner patches beside the crosses instead (the usual mix-up for someone who
    knows i1Profiler's charts). Nothing here changes what is refused."""
    out: dict = {}
    try:
        out["sheet_move"] = geo.sheet_move_advice(readings)
    except (TypeError, ValueError, IndexError):
        pass
    m = re.match(r"mark (\d) was aimed at X (-?\d+), Y (-?\d+)", reason)
    if m:
        out["outside_mark"] = int(m.group(1))
    m = re.match(r"marks (\d) and (\d) are ([0-9.]+) mm apart on the table but ([0-9.]+) mm "
                 r"on the sheet \(at most ([0-9.]+) mm", reason)
    if m:
        out["lengths"] = {"marks": [int(m.group(1)), int(m.group(2))],
                          "table_mm": float(m.group(3)), "sheet_mm": float(m.group(4)),
                          "allowed_mm": float(m.group(5))}
    m = re.match(r"the corner at mark 2 measures ([0-9.]+) degrees", reason)
    if m:
        out["corner_deg"] = float(m.group(1))
    if aims and all(a.get("target") == "cross" for a in aims):
        try:
            corners = _corner_patches_mm(sheet, page, aims_mm)
            if (len(corners) == 3 and not geo.lengths_fit(aims_mm, readings)
                    and geo.lengths_fit(corners, readings)):
                out["aimed_at"] = "corner_patches"
        except (KeyError, IndexError, TypeError, ValueError):
            pass
    return out


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


class _PatchFailed(Exception):
    """A reading that failed (``retry``: the reader is alive and on the patch)."""

    def __init__(self, reason: str, retry: bool = False, **detail):
        super().__init__(reason)
        self.reason, self.retry, self.detail = reason, retry, detail


class _RowFailed(Exception):
    def __init__(self, reason: str, loc: str):
        super().__init__(reason)
        self.reason, self.loc = reason, loc


def _default_reader(folder, name, patches, calibrate, extra_args, log):
    """ChromIQ's own helper for the i1Pro 2, through the app's helper path (reader.py's
    helper_path: core.resource_path), reading patch by patch: ``--json [options] -v -c 1 [-N]
    -p <row chart>``, as tester 0.6.0's Readers.spot started it."""
    return rd.SpotReader(rd.helper_path(), folder, name, patches, log, calibrate,
                         extra_args=tuple(extra_args))


class HelperWithoutButtonWait(Exception):
    """The helper's build string has no button wait (2026-11-17a and older)."""


def _default_press_factory(folder, log):
    """The real helper's button wait (round B), only when its build carries it: an older
    helper is never started for it (``reader.press_wait_supported``)."""
    if not rd.press_wait_supported():
        raise HelperWithoutButtonWait()
    return rd.PressWaiter(rd.helper_path(), folder, log)


def _close_quietly(w) -> None:
    try:
        w.close()
    except Exception:      # noqa: BLE001 - closing never raises
        pass


def _default_scan_reader(folder, log):
    """ChromIQ's own helper in its table-scan mode (round B, strip rows)."""
    return rd.ScanReader(rd.helper_path(), folder, log)


def _is_i1pro2(model) -> bool:
    m = str(model or "")
    return "i1 Pro 2" in m or "i1Pro 2" in m


#: scan.run_row's clean failures (before the scan move, or after it with the arm at the row's
#: end) as ids (the first match wins)
_STRIP_CLEAN_IDS = (
    ("the free arm moved", "free_arm_moved_between_two_readings"),
    ("the plan was refused", "strip_plan_refused"),
    ("you did not confirm the first move", "first_visit_declined"),
    ("the instrument reader is not running", "strip_reader_not_running"),
    ("the instrument's lights-off failed", "strip_lights_off_failed"),
    ("c4 answered", "strip_c4_not_recorded"),
    ("the move to the row start took", "movement_late_but_arrived"),
    ("the arm stands beside the row start", "arrived_beside_the_target"),
    ("the instrument is not ready to fire", "strip_instrument_not_ready"),
    ("the scan move was refused by the program's own checks", "strip_move_refused_here"),
    ("scan move refused", "strip_move_refused_by_the_table"),
    ("the scan move ran and the arm is at the row end, but the instrument did not deliver",
     "strip_instrument_delivered_nothing"),
)


def _save_pass(outdir: str, res) -> "list[str]":
    """A dual row's UV pass: its plan and result (its readings are the helper's own files)."""
    p = Path(outdir) / (res.plan.name + ".plan_and_result.json")
    try:
        p.write_text(json.dumps(res.as_dict(), indent=1, default=str), encoding="utf-8")
    except OSError:
        return []
    return [p.name]


def _write_json(path: Path, data) -> None:
    try:
        Path(path).write_text(json.dumps(data, default=str), encoding="utf-8")
    except OSError:
        pass


def _strip_clean_id(why: str) -> str:
    for prefix, rid in _STRIP_CLEAN_IDS:
        if why.startswith(prefix):
            return rid
    return "strip_failed"


def _default_helper_check() -> "str | None":
    """The helper can be started (read only): it exists and may be run."""
    import os
    path = rd.helper_path()
    if not path.exists():
        return "helper_missing"
    if not os.access(path, os.X_OK):
        return "helper_not_runnable"
    return None
