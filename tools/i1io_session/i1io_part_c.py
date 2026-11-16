# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""Part C of the session test program (0.5.0): READING with the instrument on the table.

Stages, each explained first in plain words, confirmed with a typed yes, skippable, repeatable
within its own cap, and each with a result block in the log and a folder in the results:

  C1  open the instrument with the bundled reader and calibrate it (spot and strip readings)
  C2  one spot reading of the table's white tile, the arm at its resting place (nothing moves)
  E1  the recorded row scan of 14 November replayed exactly (a strip reading, a first try)
  C3  one spot reading at the first patch of the recorded spot row (the recorded way there)
  C4  the recorded spot row, a reading at every one of its 28 patches
  D1  your ChromIQ i1iO sheet: you aim the sight at its three marks, the program checks them
  D2  the first computed move: a short one to the mark you aimed at last
  D3  one row of your sheet, a spot reading at every patch (computed targets)
  E2  one row of your sheet as a strip reading (computed start and end, a recorded speed)
  E3  your whole page as strip readings, row by row
  D4  your whole page in spot readings, row by row (the longest stage)
  F   home and end: the recorded end of a job from wherever the arm stands

THE RULES, the same for every stage (they cannot be switched off by a stage):
* every line goes through Table._write with part C's gate (i1io_c_lines) and caps;
* computed targets lie inside the measuring area (i1io_geometry) and inside the sheet as aimed;
  the whole swept rectangle is checked; a first move into a part of the table no recording drove
  the arm to is its own confirmed step;
* the instrument is never read while the arm moves; a scan move is sent only after the reader
  has answered that it can fire at once, and then always gets its fire;
* a stage that fails CLEANLY (nothing pending, the arm read where it should be, held, or still at
  its resting place) says what failed, keeps everything, offers the recorded homing when the arm is
  out, and then the next stage that does not depend on it; anything else (a movement whose end is
  not known, a scan move that may be pending, a reading in the wrong place, Ctrl-C) ends the
  sitting for good, with the true state and the way out.
"""
from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass, replace
from pathlib import Path

import i1io_c_lines as cl
import i1io_geometry as geo
import i1io_reader as rd
import i1io_scan as sc
import i1io_session_table as tbl
from i1io_session_table import Doubt, Stopped


# ---- stages ------------------------------------------------------------------------------

@dataclass(frozen=True)
class CStep:
    """What Table._write checks while a part C stage writes its own lines."""
    key: str
    max_lines: int
    max_moves: int


@dataclass(frozen=True)
class Stage:
    key: str
    title: str
    minutes: str
    needs: "tuple[str, ...]"        # what must have WORKED in this sitting (see NEEDS_TEXT)
    where: str                      # "rest": starts with the arm at its resting place;
                                    # "sheet": the arm out on the sheet you aimed at; "any"
    risk: str
    first_try: bool
    max_runs: int
    max_lines: int                  # this stage's own lines, besides the recorded steps it uses
    max_moves: int
    explain: str
    beyond: str


SPOT_ROW_PATCHES_MAX = 40
PAGE_PATCHES_MAX = 1100
PAGE_ROWS_MAX = 40

STAGES = (
    Stage("c1", "Open the instrument with ChromIQ's reader and calibrate it", "about 3 min",
          (), "rest", "low", False, 3, 2, 0,
          "Nothing moves. The program checks that the arm is at its resting place, then starts "
          "ChromIQ's own reader (in the bin folder of this package). The reader opens the i1Pro 2 "
          "while this program keeps the table. On a Mac, the ArgyllCMS instrument library inside "
          "the reader closes X-Rite's background service i1ProDeviceService when it opens the "
          "instrument (that is how ArgyllCMS always opens an i1Pro; its own note says the service "
          "starts again by itself). Then the instrument is calibrated twice, once for spot "
          "readings and once for strip readings, on a white tile you choose: the i1Pro 2's own "
          "calibration tile, or the table's tile under the arm at its resting place.",
          "The table hears nothing new: one position reading. The calibration is ArgyllCMS's own "
          "(the one ChromIQ uses when you measure by hand), not i1Profiler's; it writes nothing "
          "into the instrument's memory."),
    Stage("c2", "One spot reading of the table's white tile, at the resting place", "about 1 min",
          (), "rest", "low", False, 3, 2, 0,
          "Nothing moves. With the arm at its resting place the instrument's measuring opening "
          "rests on the table's small white tile. The reader takes one spot reading of it, the "
          "same kind of reading ChromIQ takes patch by patch by hand. The program reads the arm's "
          "position before and after.",
          "No table line is new. The reading is ArgyllCMS's spot reading, not i1Profiler's."),
    Stage("e1", "The recorded row scan of 14 November, replayed exactly (a strip reading)",
          "about 4 min", (), "rest", "medium", True, 3, 12, 2,
          "This is the first strip reading: the arm drives one row while the instrument reads "
          "continuously. First the recorded way to the alignment start as in part B (out 15 cm, "
          "across 14 cm, the short move, the arm let go); you push the free arm by hand to the "
          "front right (the same box as part B). Then exactly i1Profiler's scan of row 1 of your "
          "14 November session 1: the reader darkens the instrument's lights, the table is asked "
          "c4, the arm drives about 10 cm towards the back to the row start (X -1196, Y 1645), d1, "
          "and only when the reader has answered that it can fire at once, the scan move to "
          "X 1175, Y 1661 at 118 mm/s (24 cm in about 2.6 s, started by the instrument's lamp). "
          "Then the recorded end of the job brings the arm home. You can lay your i1Profiler iO "
          "chart where it lay on 14 November (then the readings mean something) or leave the "
          "table empty (then the reader reads the mat); the moves are the same.",
          "A FIRST TRY. Every table line and its target and speed are exactly i1Profiler's; what "
          "is new is ChromIQ's reader triggering the instrument (its requests to the i1Pro 2 are "
          "i1Profiler's byte for byte, the timing is ours). If the lamp did not start the move, the "
          "table could be left waiting with no command known to cancel it: then the program tells "
          "you to SWITCH THE TABLE OFF. It never sends the scan move unless the reader is ready."),
    Stage("c3", "One spot reading at the first patch of the recorded spot row", "about 3 min",
          (), "rest", "medium", False, 3, 2, 0,
          "Part B's recorded way: out to the alignment start, the arm let go, you push it to the "
          "front right, the motors take it and drive it to the first patch of row 1 (X -1181, "
          "Y 1658). There the reader takes one spot reading. You can lay your i1Profiler iO chart "
          "where it lay on 14 November, or leave the table empty.",
          "The table lines are exactly part B's steps 1 to 4. The reading is ArgyllCMS's."),
    Stage("c4", "The recorded spot row, a reading at every patch", "about 2 min (5 from rest)",
          (), "any", "low-medium", False, 3, 63, 28,
          "From the first patch of row 1 (if the arm is not there yet, C3's way there first), "
          "the 27 recorded moves of 8.7 mm along row 1, with a spot reading at every patch, about "
          "1.5 s per patch as i1Profiler did it, then the recorded end of the job brings the arm "
          "home. Enter between two patches stops at the next patch.",
          "The moves are exactly the recorded ones; the readings are ArgyllCMS's."),
    Stage("d1", "Your ChromIQ i1iO sheet: aim the sight at its three marks", "about 5 min",
          (), "rest_or_free", "medium", True, 5, 8, 0,
          "You lay your printed ChromIQ i1iO sheet on the table as ChromIQ printed it for the "
          "table (its top edge to the right). The arm takes part B's "
          "recorded way to the alignment start and is let go. You push it so that the cross hairs "
          "of the sight sit on mark 1, then 2, then 3, typing aimed at each; the program asks the "
          "table where the sight is (p1, the line i1Profiler sends at each aim). Then it checks "
          "the three positions against the sheet before anything moves: the order, a mirrored or "
          "turned sheet, both distances within 2 mm of the sheet's, the corner within 1 degree of "
          "a right angle, and that all three lie inside the measuring area.",
          "p1 is i1Profiler's own line; here it follows your typed word instead of the "
          "instrument's button. If the check refuses your aims, nothing has moved and you can aim "
          "again."),
    Stage("d2", "The first computed move: a short one to mark 3", "about 1 min",
          ("d1",), "sheet", "medium", True, 3, 4, 1,
          "With your hands off, the program reads where the free arm is (twice) and drives it the "
          "few centimetres to the position the table reported for mark 3, so the measuring opening "
          "should then sit on mark 3. You tell us whether it does.",
          "A FIRST TRY: the first move to a computed target (inside the measuring area, at the "
          "recorded speed 300). Near the front of the table it may also be the first motor move "
          "into a part no recording drove the arm to: then the program says so first."),
    Stage("d3", "One row of your sheet, a spot reading at every patch", "about 2 min",
          ("d1",), "sheet", "medium", True, 3, 2 * SPOT_ROW_PATCHES_MAX + 4, SPOT_ROW_PATCHES_MAX,
          "Row 1 of your sheet, patch by patch, as i1Profiler measures in spot mode: the arm goes "
          "to the patch at the right end of the row and steps to the left, a spot reading at each "
          "patch, at least 1 s between moves. Enter between two patches stops at the next patch.",
          "A FIRST TRY: every target is computed from your three aims (i1Profiler's own model)."),
    Stage("e2", "One row of your sheet as a strip reading", "about 1 min",
          ("d1",), "sheet", "medium", True, 4, 12, 2,
          "Row 1 of your sheet read as a strip: the arm drives to the row's start just beyond its "
          "right end, the reader is armed, and the scan move runs the whole row at a recorded "
          "speed (54 mm/s unless you choose another recorded one), started by the instrument's "
          "lamp. The readings are cut into patches by position afterwards.",
          "A FIRST TRY: the start and end are computed; the row is longer than any recorded scan "
          "move but inside the measuring area, at a recorded speed. If a scan move might still be "
          "waiting afterwards, the program tells you to switch the table off."),
    Stage("e3", "Your whole page as strip readings, row by row", "about 1 min per 5 rows",
          ("d1",), "sheet", "medium", True, 2, 12 * PAGE_ROWS_MAX, 2 * PAGE_ROWS_MAX,
          "Every row of the page as in E2, serpentine as i1Profiler drives rows, with a question "
          "after each row whether to go on.",
          "A FIRST TRY, as E2. The front rows of an A4 sheet lie where no recording drove the "
          "arm: the first move there is its own confirmed step."),
    Stage("d4", "Your whole page in spot readings, row by row", "about 1 min per row",
          ("d1",), "sheet", "medium", True, 2, 2 * PAGE_PATCHES_MAX + 2 * PAGE_ROWS_MAX,
          PAGE_PATCHES_MAX,
          "Every row of the page as in D3, serpentine, with a question after each row whether to "
          "go on.",
          "A FIRST TRY, as D3. The front rows lie where no recording drove the arm: the first "
          "move there is its own confirmed step."),
    Stage("f", "Home and end the job", "under 1 min", (), "out", "low", False, 8, 8, 1,
          "The recorded end of a job: s0, a position reading (the arm must be where it was last "
          "read), the homing i1, then f0 (the hand-alignment mode off), f4 twice (00), and a last "
          "position reading at the resting place.",
          "i1Profiler sent this homing from row ends and points on its charts (2.6 to 3.8 s), and "
          "from a free arm twice (it worked once in 4.0 s; once the table answered status 3 and "
          "the arm stayed). From exactly this point it was never sent."),
)
STAGE_BY_KEY = {s.key: s for s in STAGES}
#: Offered in this order: the most informative and quickest first.
ORDER = ("c1", "c2", "e1", "c3", "c4", "d1", "d2", "d3", "e2", "e3", "d4", "f")
NEEDS_TEXT = {
    "c1": "nothing", "c2": "a spot calibration in this sitting (C1, or it calibrates itself)",
    "e1": "nothing (it calibrates for strip readings itself if C1 did not)",
    "c3": "nothing (calibrates itself if needed)", "c4": "nothing (C3's way there if needed)",
    "d1": "nothing (the instrument is not used)",
    "d2": "D1 accepted in this sitting, the arm not homed since",
    "d3": "D1, and a spot calibration in this sitting (C1, C2, C3 or C4)",
    "e2": "D1, and a strip calibration in this sitting (C1 or E1)",
    "e3": "D1, and a strip calibration in this sitting (C1 or E1)",
    "d4": "D1, and a spot calibration in this sitting",
    "f": "the arm out on the table, last read where it stands",
}

# The recorded part B steps part C uses, each allowed from the states part C leaves.
B = {s.key: s for s in tbl.B_STEPS}
C_HOME = replace(B["b_home"], needs=("warm", "homed", "b_done"))
C_ALIGN = B["b_align"]
C_PLACE = B["b_place"]
C_FIRST = B["b_first"]
APPROACH_LINES = sum(tbl.STEP_MAX_LINES[k] for k in ("b_home", "b_align", "b_place", "b_first"))
APPROACH_MOVES = sum(tbl.STEP_MAX_MOTIONS[k] for k in ("b_home", "b_align", "b_place", "b_first"))


def session_caps() -> "tuple[int, int]":
    """Part C's caps per sitting: the opening, then every stage as often as it may run, each run
    with the recorded approach it may use, and a homing after each run."""
    lines = len(tbl.OPEN_KEYS)
    moves = 0
    f = STAGE_BY_KEY["f"]
    for s in STAGES:
        lines += s.max_runs * (s.max_lines + APPROACH_LINES + f.max_lines)
        moves += s.max_runs * (s.max_moves + APPROACH_MOVES + f.max_moves)
    return lines, moves


C_MAX_LINES, C_MAX_MOVES = session_caps()

# ---- texts -----------------------------------------------------------------------------

RISK_WORDS = {
    "low": "Risk, as we judge it: low (nothing new for the table, or nothing moves).",
    "low-medium": "Risk, as we judge it: low to medium (recorded moves in the recorded order).",
    "medium": ("Risk, as we judge it: medium (a first try or a computed target inside the "
               "measuring area; the worst we expect is a reading that does not work)."),
}
FIRST_TRY = ("This is a first try: it may simply fail. If it does, the program says what failed, "
             "keeps everything about it for us, and offers the next stage.")
HANDS = "Keep your hands and everything else away from the arm while it moves."
PLUG = ("If anything looks or sounds wrong while the arm moves, switch the table off at its power "
        "switch. That is always allowed.")
PENDING = sc.PENDING_TEXT
UNFINISHED = (
    "The table never reported that its last movement had finished, so it may still be moving, "
    "or start it later. Please keep your hands away from the arm, switch the table off, wait ten "
    "seconds and switch it on again, then open i1Profiler once, let it start the table, and quit "
    "it.")
OPEN_ONCE = ("Please open i1Profiler once, let it start the table as usual, and quit it. If it "
             "does not bring the arm home or shows a problem, switch the table off, wait ten "
             "seconds, switch it on again and open i1Profiler once more (a recovery, not a routine "
             "step).")
MODE_ON = ("The table is still in the hand-alignment mode (f0, which switches it off, was not "
           "answered). Nobody has recorded what i1Profiler does when it opens a table in this "
           "mode.")


def where_text(d: tbl.Table) -> "list[str]":
    """The TRUE state from what the table last answered: the last READ position decides."""
    if d.closed_reason == "a scan move may be pending" or (
            d.motion_unconfirmed and d.last_move and d.last_move[0] == "scan move"):
        return [PENDING]
    if d.motion_unconfirmed:
        return [UNFINISHED] + ([MODE_ON] if d.mode_on else [])
    p = d.position_now
    if d.motions_sent == 0 and p is None:
        return ["Nothing was moved."]
    if p is None:
        last = d.last_read
        at = (f" (it last read X {last[0]}, Y {last[1]}, before its last movement)"
              if last else "")
        return ["Where the arm stands now was not read after its last movement" + at + ". "
                "The program does not move it again. Please do not push it around. " + OPEN_ONCE]
    if tbl.REST_GUARD.contains(p) and d.arm_free is False:
        out = [f"The arm last read X {p[0]}, Y {p[1]}: at its resting place, held when last "
               "checked."]
        if d.mode_on:
            out.append(MODE_ON + " " + OPEN_ONCE)
        return out
    hold = {True: "free (the motors let it go)", False: "held when last checked",
            None: "held or free: not known"}[d.arm_free]
    out = [f"The arm last read X {p[0]}, Y {p[1]}, out on the table, {hold}. The program does "
           "not move it again. Please do not push it around."]
    if d.mode_on:
        out.append(MODE_ON)
    out.append(OPEN_ONCE)
    return out


# ---- results -----------------------------------------------------------------------------

class Results:
    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.blocks: "list[dict]" = []
        self.spot_rows: "list[tuple]" = []      # (sample_id, loc, spectrum, stage)
        self.strip_rows: "list[tuple]" = []
        self.wl = [380.0 + 10 * i for i in range(36)]

    def stage_dir(self, key: str, n: int) -> Path:
        p = self.folder / f"{key}-{n}"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def write_combined(self) -> None:
        if self.spot_rows:
            sc.write_ti3(str(self.folder / "spot_readings.ti3"),
                         [(a, b, [v / 100.0 if max(c) > 1.5 else v for v in c])
                          for a, b, c, _s in self.spot_rows], self.wl,
                         "i1iO spot readings (all stages)", "spot readings (first try)")
        if self.strip_rows:
            sc.write_ti3(str(self.folder / "strip_readings.ti3"),
                         [(a, b, c) for a, b, c, _s in self.strip_rows], self.wl,
                         "i1iO strip readings (all stages)", "position (first try)")
        with open(self.folder / "summary.json", "w", encoding="utf-8") as fh:
            json.dump(self.blocks, fh, indent=1, default=str)


class StageFailed(Exception):
    """A clean failure: nothing pending, the arm read where it stands (or never moved)."""


class PersonStopped(Exception):
    """Enter between two patches or rows: a clean stop by the person."""


# ---- the runner ----------------------------------------------------------------------------

class PartC:
    def __init__(self, session, readers, sheet=None, page: int = 0, results: Results = None):
        self.s = session
        self.d: tbl.Table = session.d
        self.ui = session.ui
        self.readers = readers
        self.sheet = sheet
        self.page = page
        self.results = results
        self.worked: "set[str]" = set()
        self.runs: "dict[str, int]" = {}
        self.spot_cal = False
        self.strip_cal = False
        self.alignment: "geo.Alignment | None" = None
        self.driven: "list[tuple]" = []          # swept rectangles driven in this sitting
        self.spot_index: "int | None" = None     # at a recorded spot patch (C3/C4)
        self.cal_place: "str | None" = None
        self.stage_notes: "list[tuple[str, str]]" = []
        d = self.d
        d.part = "C"
        d.c_gate = cl.make_gate(d)
        d.c_caps = (C_MAX_LINES, C_MAX_MOVES)
        if hasattr(d.t, "gate"):
            d.t.gate = cl.wire_gate

    # ---- the state, from the table's answers only ----------------------------------------
    def at_rest(self) -> bool:
        d, p = self.d, self.d.position_now
        return (p is not None and not d.motion_unconfirmed and d.arm_free is False
                and tbl.REST_GUARD.contains(p) and not d.mode_on)

    def unread_rest(self) -> bool:
        """Just opened (warm, nothing moved yet): the first homing reads it first."""
        return self.d.motions_sent == 0 and self.d.state == "warm"

    def out_known(self) -> bool:
        d, p = self.d, self.d.position_now
        return p is not None and not d.motion_unconfirmed and not self.at_rest()

    def ok_to_go_on(self) -> bool:
        d = self.d
        return d.closed_reason is None and not d.motion_unconfirmed

    def ready(self, s: Stage) -> "str | None":
        """None when stage *s* may be offered now, else why not (plain words)."""
        if self.runs.get(s.key, 0) >= s.max_runs:
            return "it has run as often as this program allows in one sitting"
        for k in s.needs:
            if k not in self.worked:
                return f"it needs {k.upper()} first"
        rest = self.at_rest() or self.unread_rest()
        if s.where == "rest" and not rest:
            return "it starts with the arm at its resting place"
        if s.key == "c4" and not (rest or (self.spot_index == 0 and self.out_known())):
            return "it starts at the resting place or at patch 1 of the recorded row"
        if s.where == "rest_or_free" and not (rest or (self.d.arm_free is True
                                                       and self.d.mode_on)):
            return "it starts at the resting place, or with the arm free after an alignment"
        if s.where == "sheet":
            if self.alignment is None:
                return "it needs your three aims (D1) in this sitting"
            if not self.out_known() and self.d.arm_free is not True:
                return "it needs the arm out on your sheet"
        if s.key in ("d3", "d4") and not self.spot_cal:
            return "it needs a spot calibration in this sitting (C1)"
        if s.key in ("e2", "e3") and not self.strip_cal:
            return "it needs a strip calibration in this sitting (C1 or E1)"
        if s.where in ("sheet", "rest_or_free", "rest") or s.key == "c4":
            pass
        if s.key in ("d1", "d2", "d3", "d4", "e2", "e3") and self.sheet is None and \
                s.key != "d1":
            return "it needs your sheet's file"
        if s.where == "out" and not (self.out_known() or self.d.arm_free is True):
            return "the arm is not out on the table"
        return None

    def finish(self) -> None:
        """At the end of the sitting (nothing is sent): the combined readings and summary."""
        self._close_readers()
        if self.results is not None:
            try:
                self.results.write_combined()
            except Exception as exc:          # noqa: BLE001 - the zip still carries the rest
                self.d.log("INFO", f"the combined results could not be written ({exc!r})")

    def available(self) -> "list[Stage]":
        if self.only_home:
            # after "the arm did something wrong": nothing more moves, except the homing
            f = STAGE_BY_KEY["f"]
            return [f] if self.ready(f) is None else []
        return [STAGE_BY_KEY[k] for k in ORDER if self.ready(STAGE_BY_KEY[k]) is None]

    # ---- the menu ---------------------------------------------------------------------
    def run(self) -> int:
        ui = self.ui
        ui.say("")
        ui.say(C_INTRO)
        while True:
            if not self.ok_to_go_on():
                return 2 if self.d.closed_reason != "stopped by you" else 1
            avail = self.available()
            fresh = [s for s in avail if s.key not in self.worked and s.key != "f"]
            if self.out_known() or self.d.arm_free is True:
                fresh = [s for s in avail if s.key not in self.worked]
                if not [s for s in fresh if s.key != "f"]:
                    fresh = [STAGE_BY_KEY["f"]] if STAGE_BY_KEY["f"] in avail else fresh
            others = [s for s in avail if s not in fresh]
            choices = [s.key for s in fresh] + [s.key for s in others] + ["end"]
            ui.say("")
            ui.say("What can run now (with about how long it takes):")
            for s in fresh + others:
                done = " (worked already; you can repeat it)" if s.key in self.worked else ""
                ui.say(f"  {s.key.upper():3} {s.title} ({s.minutes}){done}")
            ui.say("  END stop here" + ("" if not (self.out_known() or self.d.arm_free) else
                                        " (F is recommended first: the arm is out on the table)"))
            not_now = [(k, self.ready(STAGE_BY_KEY[k])) for k in ORDER
                       if STAGE_BY_KEY[k] not in avail]
            if not_now:
                ui.say("Not offered now: " + "; ".join(
                    f"{k.upper()} ({why or 'only the homing is offered after what you saw'})"
                    for k, why in not_now) + ".")
            if len(choices) == 1 or (self.s.auto_end_when_done and not fresh):
                return 0
            ans = ui.ask("Which stage now? (the first one listed is our suggestion)", choices)
            self.s.note("part C: stage chosen", ans)
            if ans == "end":
                return 0
            stage = STAGE_BY_KEY[ans]
            if self.offer(stage) != "yes":
                continue
            if self.s.other_program():
                self.d.close_for_sending("i1Profiler was started during the session")
                raise Stopped("i1Profiler has started, so the program stops here: two programs "
                              "must never talk to the table at the same time. Nothing more is "
                              "sent to the table.")
            self.run_stage(stage)

    def offer(self, s: Stage) -> str:
        ui = self.ui
        n = self.runs.get(s.key, 0) + 1
        ui.say("")
        ui.say(f"Stage {s.key.upper()}{'' if n == 1 else f' (run {n})'}: {s.title}. "
               f"It takes {s.minutes}.")
        ui.say(s.explain)
        ui.say("What is not exactly as recorded: " + s.beyond)
        if s.first_try:
            ui.say(FIRST_TRY)
        ui.say(RISK_WORDS[s.risk] + f" It depends on: {NEEDS_TEXT[s.key]}.")
        moves = s.max_moves or s.where in ("rest",) and s.key in ("e1", "c3")
        if moves or s.key in ("c3", "c4", "e1", "d1", "f"):
            ui.say(PLUG)
            q = f"{HANDS} Run stage {s.key.upper()} now?"
        else:
            q = f"Run stage {s.key.upper()} now?"
        ans = ui.ask(q, ("yes", "back"))
        self.s.note(f"part C: offer {s.key}", ans)
        return ans

    def run_stage(self, s: Stage) -> None:
        n = self.runs.get(s.key, 0) + 1
        self.runs[s.key] = n
        folder = self.results.stage_dir(s.key, n)
        d = self.d
        block = {"stage": s.key, "run": n, "verdict": "", "why": "", "folder": folder.name,
                 "lines_before": d.lines_sent, "moves_before": d.motions_sent,
                 "position_before": d.position_now, "t_start": round(d.t.now(), 3),
                 "answers": [], "data": {}}
        self.block = block
        d.log("STAGE", f"start {s.key} run {n}")
        verdict, why = "worked", ""
        try:
            getattr(self, "stage_" + s.key)(s, folder)
            self.worked.add(s.key)
        except StageFailed as exc:
            verdict, why = "failed cleanly", str(exc)
        except PersonStopped as exc:
            verdict, why = "stopped by you (clean)", str(exc)
        except (geo.AreaRefused, geo.AlignmentRefused, sc.PlanRefused) as exc:
            verdict, why = "failed cleanly", str(exc)
        except rd.ReaderFailed as exc:
            verdict, why = "failed cleanly (instrument)", str(exc)
        except tbl.MoveOutside as exc:
            verdict, why = "stopped", str(exc)
            d.close_for_sending(why)
        except (Doubt, Stopped, KeyboardInterrupt) as exc:
            verdict, why = "stopped", str(exc) or type(exc).__name__
            block.update(self._end_block(verdict, why))
            self._write_block(block)
            raise
        except Exception as exc:              # noqa: BLE001 - logged, then the sitting ends
            verdict, why = "stopped", f"an unexpected error ({type(exc).__name__}: {exc})"
            d.close_for_sending(why)
        finally:
            self._close_readers()
            d.current_step = None
        if verdict != "worked" and (d.motion_unconfirmed or d.closed_reason):
            verdict = "stopped"
        block.update(self._end_block(verdict, why))
        self._write_block(block)
        self.ui.say("")
        if verdict == "worked":
            self.ui.say(f"Stage {s.key.upper()} worked.")
        else:
            self.ui.say(f"Stage {s.key.upper()}: {verdict}: {why}")
            if verdict.startswith("failed") or verdict.startswith("stopped by you"):
                self.ui.say("Everything about it is kept in the results. " + " ".join(
                    where_text(d)[:1]))
        if verdict != "worked" or s.key in ("f",):
            pass
        if s.key != "f" and self.ok_to_go_on():
            self.after_stage(s)

    def _end_block(self, verdict, why) -> dict:
        d = self.d
        return {"verdict": verdict, "why": why, "lines_after": d.lines_sent,
                "moves_after": d.motions_sent, "position_after": d.position_now,
                "last_read": d.last_read, "arm_free": d.arm_free, "mode_on": d.mode_on,
                "movement_unconfirmed": d.motion_unconfirmed, "t_end": round(d.t.now(), 3),
                "state_text": where_text(d)}

    def _write_block(self, block) -> None:
        self.results.blocks.append(block)
        self.d.log("RESULT", json.dumps(block, default=str))
        try:
            with open(self.results.folder / block["folder"] / "result.json", "w",
                      encoding="utf-8") as fh:
                json.dump(block, fh, indent=1, default=str)
        except OSError:
            pass

    def after_stage(self, s: Stage) -> None:
        """Questions after a stage (nothing moves). A 'no' is noted; the sitting goes on only
        when the table is in a known state."""
        did = self.ui.ask("Did the table and the instrument do what was described?",
                          ("yes", "no", "not sure", "stop"))
        self.s.note(f"part C {s.key}: as described?", did)
        self.block["answers"].append(("as described", did))
        seen = self.ui.text("What did you see, hear or feel? (a few words; press Enter to skip)")
        self.s.note(f"part C {s.key}: seen", seen)
        self.block["answers"].append(("seen", seen))
        self.d.log("RESULT", json.dumps({"stage": s.key, "run": self.runs[s.key],
                                         "answers": self.block["answers"]}, default=str))
        if did == "stop":
            self.s.stopped_by_person = True
            self.d.close_for_sending("stopped by you")
            raise Stopped("You stopped the program. Nothing more is sent to the table.")
        if did != "yes":
            self.worked.discard(s.key)
            arm = self.ui.ask(ASK_ARM_WRONG, ("yes", "no", "not sure"))
            self.s.note(f"part C {s.key}: the arm or table wrong?", arm)
            self.block["answers"].append(("arm or table wrong", arm))
            if arm != "no":
                self.ui.say("Thank you, that is exactly what we need to know. Nothing more moves "
                            "in this sitting except, if you want it, the recorded homing.")
                self.only_home = True
            else:
                self.ui.say("Thank you, that is noted. The table behaved as described, so the "
                            "sitting can go on.")

    only_home = False

    def _close_readers(self) -> None:
        for r in list(getattr(self, "_open_readers", [])):
            try:
                r.close()
            except Exception:
                pass
        self._open_readers = []

    def _keep(self, reader):
        self._open_readers = getattr(self, "_open_readers", []) + [reader]
        return reader

    # ---- helpers for the stages ---------------------------------------------------------
    def step(self, key: str, lines: int, moves: int) -> CStep:
        st = CStep(key, lines, moves)
        self.d.current_step = st
        self.d.step_lines = self.d.step_motions = 0
        return st

    def run_b(self, step) -> None:
        """One recorded part B step (its own caps)."""
        d = self.d
        if step.key == "b_home" and d.state not in C_HOME.needs:
            d.state = "homed"
        d.run_step(C_HOME if step.key == "b_home" else step)

    def approach(self, to: str) -> None:
        """Part B's recorded steps from the resting place: 'free_out' (the arm free at the
        alignment start), 'placed' (pushed into the box by hand), 'patch1' (the motors took it
        to patch 1 of the recorded row)."""
        d = self.d
        self.run_b(C_HOME)
        self.run_b(C_ALIGN)
        if d.out_touch != "free":
            raise StageFailed("the arm did not give way at the alignment start, so nobody "
                              "should push it")
        if to == "free_out":
            return
        self.run_b(C_PLACE)
        if to == "placed":
            return
        self.run_b(C_FIRST)
        self.spot_index = 0

    def place_for_calibration(self, kind: str):
        """The calibration placement question, once per sitting (then remembered)."""
        def place(ev) -> bool:
            cond = str(ev.get("cond", ""))
            if cond and "white" not in cond:
                self.ui.say(f"The reader asks for a calibration of a kind this program does not "
                            f"know ({cond}). The calibration is not done.")
                return False
            if self.unread_rest() and self.d.position_now is None:
                # just opened: read where the arm is before anyone handles the instrument
                self.check_rest("before the calibration")
            if not self.at_rest():
                self.ui.say("The reader asks for a calibration, but the arm is out on the table. "
                            "A calibration needs the instrument on a white tile, so this stage "
                            "stops here (nothing more moves). Home the arm with F, then run C1.")
                return False
            if self.cal_place is None:
                ans = self.ui.ask(CAL_WHERE, ("arm", "own", "stop"))
                self.s.note("calibration place", ans)
                if ans == "stop":
                    return False
                self.cal_place = ans
                if ans == "own":
                    if self.ui.ask(CAL_OWN, ("ready", "stop")) != "ready":
                        return False
            else:
                self.ui.say(f"Calibration for {kind} readings, on the same tile as before "
                            "(please leave the instrument where it is).")
            return True
        return place

    def reseat_after_own_tile(self) -> None:
        if self.cal_place == "own":
            ans = self.ui.ask(CAL_RESEAT, ("seated", "stop"))
            self.s.note("instrument seated again", ans)
            if ans != "seated":
                raise StageFailed("the instrument was not seated in the arm again")

    def check_rest(self, what: str) -> None:
        st = self.step(f"{self.block['stage']}_rest", 1, 0)
        p = self.d.position()
        self.d.log("DATA", f"{what}: the arm reports {p}")
        if not tbl.REST_GUARD.contains(p):
            self.d.outside_at = p
            raise StageFailed(f"{what}: the arm reads X {p[0]}, Y {p[1]}, not at its resting "
                              f"place ({tbl.REST_GUARD.text()})")
        del st

    def confirm_new_part(self, a, b) -> bool:
        """The first-visit rule: a move whose swept rectangle leaves every place the arm was
        driven to (recordings, and this sitting so far) is announced and confirmed first."""
        if not geo.first_visit(a, b) or any(_inside_rect(r, a, b) for r in self.driven):
            return True
        far = _beyond_mm(a, b)
        self.ui.say(f"The next move (from X {a[0]}, Y {a[1]} to X {b[0]}, Y {b[1]}) takes the arm "
                    f"up to about {far:.0f} mm beyond any place a recording drove it to, inside the "
                    "measuring area. It is a first visit there under motor: please watch it.")
        ans = self.ui.ask(f"{HANDS} Make this move now?", ("yes", "no"))
        self.s.note("first visit move", ans)
        self.block["answers"].append(("first visit", ans))
        return ans == "yes"

    def move_to(self, target, what: str, first_from_free: bool = False) -> "tuple[int, int]":
        """One computed m0 from the position just read, checked, timed and arrival-checked.
        A move that ends late but where it should is a clean failure."""
        d = self.d
        a = d.position_now
        if a is None:
            raise StageFailed(f"{what}: no fresh position reading (a bug)")
        if d.arm_free and not geo.AREA_RAW.contains(a):
            raise StageFailed(
                f"the free arm stands at X {a[0]}, Y {a[1]}, outside the measuring area "
                f"({geo.AREA_RAW.text()}), and this program starts no move from there. Nothing "
                "moved. Please push the free arm gently a few centimetres towards the middle "
                "of your sheet, take your hands off, and run the stage again.")
        geo.check_path(a, target, what)
        if not self.confirm_new_part(a, target):
            raise StageFailed("you did not confirm the first move into a new part of the table")
        win = geo.move_window(a, target)
        try:
            d.c_exchange(geo.m0_line(target[0], target[1]), 0, window=win,
                         timeout=win[1] + 4.0, late_is_doubt=False)
        except tbl.MoveOutside as exc:
            got = d.position()
            if _near(got, target):
                self.driven.append((a, target))
                raise StageFailed(f"{what}: the move took {exc.took:.2f} s, outside "
                                  f"{exc.lo:.2f}-{exc.hi:.2f} s, but the arm read where it should "
                                  "be") from None
            raise d._doubt(f"{what}: after a slow move the arm reads {got}, not {target}")
        got = d.position()
        if not _near(got, target):
            d.outside_at = got
            raise d._doubt(f"{what}: the arm reads {got}, not {target}",
                           f"The arm reports X {got[0]}, Y {got[1]} after the move, not the "
                           f"target X {target[0]}, Y {target[1]}. So nothing more is sent.")
        self.driven.append((a, target))
        return got

    def poll_person(self) -> None:
        if self.s.poll_enter():
            raise PersonStopped("you pressed Enter")

    def instrument_ready(self) -> None:
        """Before a reader is started: the bundled reader can run, and exactly one i1Pro 2 and
        no other instrument is connected (reads only; a problem is a clean failure)."""
        why = self.readers.check()
        if why:
            raise rd.ReaderFailed(why)
        if not self.notice_said:
            self.ui.say(C1_SAY)
            self.notice_said = True

    notice_said = False

    def spot_reader(self, folder: Path, name: str, patches, calibrate: bool):
        self.instrument_ready()
        r = self.readers.spot(folder, name, patches, calibrate)
        return self._keep(r)

    def scan_reader(self, folder: Path):
        self.instrument_ready()
        return self._keep(self.readers.scan(folder))

    def spot_read(self, reader, loc: str, sid: str, target, rows: list) -> None:
        r = reader.read(loc)
        spec = r.spectrum or []
        ok = r.xyz is not None and 0.2 <= r.xyz[1] <= 130
        rows.append({"sample_id": sid, "loc": loc, "target": target,
                     "read_at": self.d.position_now, "xyz": r.xyz, "t": round(r.t, 3),
                     "plausible": ok, "spectrum": spec})
        if not ok:
            raise StageFailed(f"the reading of {loc} came back implausible ({r.xyz})")

    def save_spot(self, folder: Path, name: str, reader, rows: list) -> None:
        ti3 = None
        try:
            ti3 = reader.finish()
        except Exception as exc:      # noqa: BLE001
            self.d.log("INST", f"finish: {exc!r}")
        for row in rows:
            rr = reader.readings.get(row["loc"])
            if rr is not None and rr.spectrum:
                row["spectrum"] = rr.spectrum
        with open(folder / f"{name}.readings.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["sample_id", "loc", "target_x", "target_y", "read_x", "read_y", "X", "Y",
                        "Z", "seconds", "plausible", "spectrum"])
            for row in rows:
                t, p, x = row["target"] or ("", ""), row["read_at"] or ("", ""), row["xyz"] or \
                    ("", "", "")
                w.writerow([row["sample_id"], row["loc"], *t, *p, *x, row["t"],
                            row["plausible"], " ".join(f"{v:.5f}" for v in row["spectrum"])])
        for row in rows:
            if row["spectrum"]:
                self.results.spot_rows.append((row["sample_id"], row["loc"], row["spectrum"],
                                               self.block["stage"]))
        self.block["data"]["spot_readings"] = len(rows)
        self.block["data"]["reader_ti3"] = ti3.name if ti3 else None

    # ---- the stages ---------------------------------------------------------------------
    def stage_c1(self, s: Stage, folder: Path) -> None:
        self.check_rest("before opening the instrument")
        scan = self.scan_reader(folder / "strip")
        ev = scan.opened()
        self.block["data"]["instrument"] = ev.get("model")
        scan.calibrate(self.place_for_calibration("strip"))
        self.strip_cal = True
        scan.close()
        spot = self.spot_reader(folder, "c1_spot", [("1", "A1")], calibrate=True)
        spot.open(self.place_for_calibration("spot"))
        self.spot_cal = True
        spot.close()
        self.reseat_after_own_tile()
        self.check_rest("after the calibration")

    def _spot_ready(self, folder, name, patches):
        cal = not self.spot_cal
        r = self.spot_reader(folder, name, patches, calibrate=cal)
        r.open(self.place_for_calibration("spot"))
        if cal:
            self.spot_cal = True
            self.reseat_after_own_tile()
        return r

    def stage_c2(self, s: Stage, folder: Path) -> None:
        self.check_rest("before the reading")
        r = self._spot_ready(folder, "c2_tile", [("1", "A1")])
        self.check_rest("right before the reading")
        rows = []
        try:
            self.spot_read(r, "A1", "1", self.d.position_now, rows)
        finally:
            self.save_spot(folder, "c2_tile", r, rows)
        self.check_rest("after the reading")
        if rows and rows[0]["xyz"]:
            self.ui.say(f"The white tile read X {rows[0]['xyz'][0]:.2f}, Y {rows[0]['xyz'][1]:.2f}, "
                        f"Z {rows[0]['xyz'][2]:.2f}.")

    def _recorded_patches(self, n: int):
        return [(str(k + 1), f"A{k + 1}") for k in range(n)]

    def stage_c3(self, s: Stage, folder: Path) -> None:
        self.check_rest("before the way out") if not self.unread_rest() else None
        r = self._spot_ready(folder, "c3_patch1", self._recorded_patches(1))
        self.ask_chart("recorded")
        self.approach("patch1")
        rows = []
        try:
            self.spot_read(r, "A1", "1", tbl.SPOT_TARGETS[0], rows)
        finally:
            self.save_spot(folder, "c3_patch1", r, rows)

    def stage_c4(self, s: Stage, folder: Path) -> None:
        d = self.d
        r = self._spot_ready(folder, "c4_row", self._recorded_patches(28))
        rows = []
        try:
            if self.spot_index != 0:
                self.ask_chart("recorded")
                self.approach("patch1")
            self.step("c4", s.max_lines, s.max_moves)
            got = d.position()
            if not tbl.AT_SPOT[0].contains(got):
                raise d._doubt(f"the arm reads {got}, not at patch 1 of the recorded row")
            self.spot_read(r, "A1", "1", tbl.SPOT_TARGETS[0], rows)
            for k in range(1, 28):
                self.poll_person()
                d.c_wait(max(0.0, 1.0 - rows[-1]["t"]))
                d._move(tbl.SPOT_KEYS[k], "patch")
                self.spot_index = k
                got = d.position()
                if not tbl.AT_SPOT[k].contains(got):
                    d.outside_at = got
                    raise d._doubt(f"at patch {k + 1}: the arm reads {got}")
                self.spot_read(r, f"A{k + 1}", str(k + 1), tbl.SPOT_TARGETS[k], rows)
        finally:
            self.save_spot(folder, "c4_row", r, rows)
        self.end_of_job("the end of the recorded row")

    def ask_chart(self, which: str) -> None:
        if which == "recorded":
            ans = self.ui.ask(ASK_REC_CHART, ("empty", "chart", "stop"))
        else:
            ans = self.ui.ask(ASK_SHEET_LAID, ("yes", "stop"))
        self.s.note(f"what lies on the table ({which})", ans)
        self.block["answers"].append(("on the table", ans))
        if ans == "stop":
            raise PersonStopped("you chose to stop before the arm moved")

    def stage_e1(self, s: Stage, folder: Path) -> None:
        scan = self.scan_reader(folder)
        scan.opened()
        if not self.strip_cal:
            scan.calibrate(self.place_for_calibration("strip"))
            self.strip_cal = True
            self.reseat_after_own_tile()
        plan = sc.recorded_row_plan()
        self.ask_chart("recorded")
        self.approach("placed")
        self.scan_rows(scan, [plan], folder, ask_between=False)
        self.end_of_job("the end of the recorded row")

    def scan_rows(self, scan, plans, folder: Path, ask_between: bool) -> None:
        d = self.d
        for k, plan in enumerate(plans):
            self.step(f"{self.block['stage']}_row{k + 1}", 12, 2)
            res = sc.run_row(d, scan, plan, d.log, str(folder),
                             confirm_move=self.confirm_new_part)
            files = sc.save_row(str(folder), res)
            self.block["data"].setdefault("rows", []).append(
                {"row": plan.name, "kind": res.kind, "why": res.why, "notes": res.notes,
                 "files": files})
            if res.kind == "pending":
                self.ui.say(PENDING)
                raise Doubt("a scan move may be pending", PENDING)
            if res.kind == "after_doubt":
                raise Doubt(res.why)
            cut = os.path.join(str(folder), plan.name + ".cut.ti3")
            if os.path.exists(cut):
                try:
                    wl, data = rd.read_ti3_spectra(Path(cut))
                    for loc, (sid, _x, spec) in data.items():
                        self.results.strip_rows.append((sid, loc, [v / 100 for v in spec],
                                                        self.block["stage"]))
                except Exception:
                    pass
            if res.kind != "done":
                raise StageFailed(f"{plan.name}: {res.why}")
            self.driven.append((plan.start, plan.end))
            if ask_between and k + 1 < len(plans):
                ans = self.ui.ask(f"Row {k + 1} of {len(plans)} is done. Go on with row {k + 2}?",
                                  ("yes", "stop"))
                self.s.note(f"strip row {k + 1}: go on?", ans)
                if ans != "yes":
                    raise PersonStopped(f"you stopped after row {k + 1}")

    def end_of_job(self, where: str) -> None:
        """The recorded end of a job (S2 497.583-500.238 and the other job ends): s0 p0 i1 s0 f0
        f4 f4, and a last position reading at rest."""
        d = self.d
        self.step(f"{self.block['stage']}_end", 8, 1)
        d.exchange("status")
        last = d.position_now
        got = d.position()
        if last is not None and not _near(got, last) and d.arm_free is False:
            raise d._doubt(f"before the homing the arm reads {got}, not {last}")
        if not (geo.AREA_RAW.contains(got) or tbl.START_GUARD.contains(got)):
            # i1Profiler sent its homing from its charts and from the alignment; never from
            # outside the measuring area: this program does not either
            free = (" The arm is free: you can push it gently back over the middle of the table "
                    "and run F again, or end here.") if d.arm_free else ""
            raise StageFailed(f"the arm reads X {got[0]}, Y {got[1]}, outside the measuring area "
                              f"({geo.AREA_RAW.text()}), and this program sends its homing only "
                              "from inside it. Nothing moved." + free)
        try:
            d.c_exchange(tbl.WIRE["home"], 0, window=(0.8, 8.0), timeout=15.0,
                         late_is_doubt=False)
        except tbl.MoveOutside as exc:
            p = d.position()
            if not tbl.REST_GUARD.contains(p):
                raise d._doubt(f"after a slow homing the arm reads {p}")
            raise StageFailed(f"the homing from {where} took {exc.took:.2f} s, outside "
                              f"{exc.lo:.1f}-{exc.hi:.1f} s, but the arm is at rest") from None
        d.exchange("status")
        d.exchange("f0")
        d.mode_on = False
        for _ in range(2):
            d._f4("00")
        p = d.position()
        self.alignment_homed()
        if not tbl.REST_GUARD.contains(p):
            d.outside_at = p
            raise d._doubt(f"after the homing the arm reads {p}, not at its resting place")
        d.state = "b_done"
        self.spot_index = None

    def alignment_homed(self) -> None:
        if self.alignment is not None:
            self.ui.say("The arm has left your sheet: for D2 to E3 the three marks are aimed "
                        "again (D1).")
        self.alignment = None
        self.worked.discard("d1")
        self.worked.discard("d2")

    def stage_f(self, s: Stage, folder: Path) -> None:
        self.end_of_job("where the arm stood")

    # ---- D: your sheet ------------------------------------------------------------------
    def need_sheet(self) -> dict:
        if self.sheet is None:
            path = self.ui.text("Please drag your sheet's file (ending .i1io.json, beside the "
                                ".ti2 in the run folder) into this window and press Enter:")
            path = path.strip().strip("'\"")
            try:
                self.sheet = load_sheet(Path(path).expanduser())
            except Exception as exc:
                raise StageFailed(f"the sheet's file could not be read ({type(exc).__name__})")
        return self.sheet

    def stage_d1(self, s: Stage, folder: Path) -> None:
        d = self.d
        sheet = self.need_sheet()
        aims = sc.aims_of(sheet, self.page)
        if not (d.arm_free is True and d.mode_on):
            self.ui.say(SHEET_LAY.format(orient=sheet.get("orientation", "")))
            self.ask_chart("sheet")
            self.approach("free_out")
        self.step("d1_aims", s.max_lines, 0)
        readings = []
        for a in aims:
            corner = a.get("corner_on_table", "")
            target = "the cross" if a.get("target") == "cross" else f"patch {a.get('patch')}"
            ans = self.ui.ask(
                f"Mark {a['number']}: please push the free arm so that the cross hairs of the sight "
                f"sit exactly on mark {a['number']} ({target} at the {corner} of the sheet as it "
                "lies). Keep it there, then type aimed. (stop ends here)", ("aimed", "stop"))
            self.s.note(f"aim {a['number']}", ans)
            if ans != "aimed":
                raise PersonStopped("you stopped during the aims")
            if self.s.sim_aim is not None:
                self.s.sim_aim(a["number"])
            rep = d.c_exchange(cl.C_FIXED["aim"], cl.C_DATA_LEN["aim"])
            p = rep.xy()
            d.log("DATA", f"aim {a['number']}: p1 reports {p}")
            readings.append(p)
        d.exchange("status")
        for _ in range(4):
            d._f4("01")
        self.block["data"]["aims"] = readings
        try:
            al = geo.fit_alignment([tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in aims],
                                   readings)
        except geo.AlignmentRefused as exc:
            raise StageFailed(f"{exc}. Nothing has moved since your aims. " + REAIM) from None
        self.block["data"]["checks"] = al.checks
        with open(folder / "alignment.json", "w", encoding="utf-8") as fh:
            json.dump({"aims_mm": al.aims_mm, "readings": al.readings, "M": al.M,
                       "checks": al.checks}, fh, indent=1)
        self.alignment = al
        L = al.checks["lengths_units"]
        self.ui.say(f"Your aims fit the sheet: marks 1 to 2 {L[0][1] / 10:.1f} mm (sheet "
                    f"{L[0][0] / 10:.1f}), marks 2 to 3 {L[1][1] / 10:.1f} mm (sheet "
                    f"{L[1][0] / 10:.1f}), corner {al.checks['angle_deg']:.1f} degrees, turned "
                    f"{al.checks['rotation_deg']:.1f} degrees.")
        fit = page_fit(sheet, self.page, al)
        self.block["data"]["fit"] = fit
        for line in fit["say"]:
            self.ui.say(line)

    def stage_d2(self, s: Stage, folder: Path) -> None:
        d = self.d
        al = self.alignment
        self.step("d2", s.max_lines, s.max_moves)
        target = al.readings[2]
        a = d.position()
        if d.arm_free:
            b = d.position()
            if abs(a[0] - b[0]) > tbl.STILL_UNITS or abs(a[1] - b[1]) > tbl.STILL_UNITS:
                raise StageFailed(f"the free arm moved between two readings ({a} then {b}): "
                                  "please take your hands off it")
        self.move_to(target, "the move to mark 3")
        ans = self.ui.ask("Is the round measuring opening now centred on mark 3?",
                          ("yes", "a little off", "clearly off", "cannot see"))
        self.s.note("d2: opening on mark 3?", ans)
        self.block["answers"].append(("opening on mark 3", ans))

    def sheet_spot_rows(self):
        sheet, al = self.sheet, self.alignment
        rows = []
        for k, st in enumerate(sheet["pages"][self.page]["strips"]):
            pts = []
            for q in st["patches"]:
                u = sc.sheet_table_mm(sheet, q["centre_mm"])
                pts.append((str(q["sample_id"]), q["loc"], al.target(u, f"patch {q['loc']}",
                                                                     run_out_mm=0.5)))
            pts.sort(key=lambda t: t[2][0], reverse=(k % 2 == 1))
            rows.append(pts)
        return rows

    def spot_row(self, folder: Path, name: str, pts, first: bool) -> None:
        d = self.d
        r = self.spot_reader(folder, name, [(sid, loc) for sid, loc, _t in pts], calibrate=False)
        r.open(self.place_for_calibration("spot"))
        rows = []
        try:
            for i, (sid, loc, target) in enumerate(pts):
                if i:
                    self.poll_person()
                    d.c_wait(max(0.0, 1.0 - rows[-1]["t"]))
                a = d.position()
                if d.arm_free:
                    b = d.position()
                    if abs(a[0] - b[0]) > tbl.STILL_UNITS or abs(a[1] - b[1]) > tbl.STILL_UNITS:
                        raise StageFailed("the free arm moved between two readings: please take "
                                          "your hands off it")
                self.move_to(target, f"the move to patch {loc}")
                self.spot_read(r, loc, sid, target, rows)
        finally:
            self.save_spot(folder, name, r, rows)

    def stage_d3(self, s: Stage, folder: Path) -> None:
        pts = self.sheet_spot_rows()[0]
        if len(pts) > SPOT_ROW_PATCHES_MAX:
            raise StageFailed(f"row 1 has {len(pts)} patches, more than this stage reads")
        self.step("d3", s.max_lines, s.max_moves)
        self.spot_row(folder, "d3_row1", pts, True)

    def stage_d4(self, s: Stage, folder: Path) -> None:
        rows = self.sheet_spot_rows()
        if sum(len(r) for r in rows) > PAGE_PATCHES_MAX or len(rows) > PAGE_ROWS_MAX:
            raise StageFailed("the page has more patches than this stage reads")
        self.step("d4", s.max_lines, s.max_moves)
        for k, pts in enumerate(rows):
            self.spot_row(folder, f"d4_row{k + 1}", pts, k == 0)
            if k + 1 < len(rows):
                ans = self.ui.ask(f"Row {k + 1} of {len(rows)} is done. Go on with row {k + 2}?",
                                  ("yes", "stop"))
                self.s.note(f"spot row {k + 1}: go on?", ans)
                if ans != "yes":
                    raise PersonStopped(f"you stopped after row {k + 1}")

    def scan_speed(self) -> int:
        ans = self.ui.ask("At which recorded speed (mm/s)? 54 is our suggestion (about 16 "
                          "readings per patch)", tuple(str(v) for v in SPEED_CHOICES))
        self.s.note("strip speed", ans)
        return int(ans)

    def sheet_plans(self, speed: int):
        return sc.sheet_rows(self.sheet, self.page, self.alignment, speed)

    def _scan_reader_ready(self, folder: Path):
        scan = self.scan_reader(folder)
        scan.opened()
        return scan

    def stage_e2(self, s: Stage, folder: Path) -> None:
        speed = self.scan_speed()
        plans = self.sheet_plans(speed)
        with open(folder / "plans.json", "w", encoding="utf-8") as fh:
            json.dump([p.as_dict() for p in plans[:1]], fh, indent=1)
        scan = self._scan_reader_ready(folder)
        self.scan_rows(scan, plans[:1], folder, ask_between=False)

    def stage_e3(self, s: Stage, folder: Path) -> None:
        speed = self.scan_speed()
        plans = self.sheet_plans(speed)
        if len(plans) > PAGE_ROWS_MAX:
            raise StageFailed("the page has more rows than this stage reads")
        with open(folder / "plans.json", "w", encoding="utf-8") as fh:
            json.dump([p.as_dict() for p in plans], fh, indent=1)
        scan = self._scan_reader_ready(folder)
        self.scan_rows(scan, plans, folder, ask_between=True)


SPEED_CHOICES = (54, 118, 88, 61, 40, 53, 87, 110, 137, 138)


def _near(p, q, d=5) -> bool:
    return p is not None and abs(p[0] - q[0]) <= d and abs(p[1] - q[1]) <= d


def _inside_rect(r, a, b) -> bool:
    (p, q) = r
    x0, x1 = sorted((p[0], q[0]))
    y0, y1 = sorted((p[1], q[1]))
    return (x0 <= min(a[0], b[0]) and max(a[0], b[0]) <= x1
            and y0 <= min(a[1], b[1]) and max(a[1], b[1]) <= y1)


def _beyond_mm(a, b) -> float:
    """How far (mm) the swept rectangle reaches beyond the driven boxes, roughly."""
    worst = 0.0
    for p in ((a[0], a[1]), (b[0], b[1]), (a[0], b[1]), (b[0], a[1])):
        if any(box.contains(p) for box in geo.DRIVEN):
            continue
        dmin = min(max(box.xmin - p[0], 0, p[0] - box.xmax) + max(box.ymin - p[1], 0,
                                                                   p[1] - box.ymax)
                   for box in geo.DRIVEN)
        worst = max(worst, dmin / 10.0)
    return worst


class Readers:
    """The real instrument side: ChromIQ's reader in this package's bin folder."""

    def __init__(self, log, helper: "Path | None" = None):
        self.log = log
        self.helper = helper or rd.helper_path()

    def check(self) -> "str | None":
        problems = rd.helper_problems(self.helper)
        if problems:
            return " ".join(problems)
        return rd.instrument_check()

    def spot(self, folder, name, patches, calibrate):
        return rd.SpotReader(self.helper, folder, name, patches, self.log, calibrate)

    def scan(self, folder):
        return rd.ScanReader(self.helper, folder, self.log)


#: the practice run's sheet (a ChromIQ 4.3.33 A4 i1iO chart's side file, ours)
DEMO_SHEET = "demo-sheet.i1io.json"
#: where the practice run lays it (table units of its mark 1 corner, sheet mm (0, 0)): chosen so
#: that every row of the demo sheet lies inside the measuring area this program uses
DEMO_ORIGIN = (1650, 950)


def demo_aims(sheet: "dict | None" = None, origin=DEMO_ORIGIN, page: int = 0):
    """The three marks of the demo sheet in table units, as the practice run lays it (the
    simulated sight is put on these)."""
    if sheet is None:
        sheet = load_sheet(Path(__file__).resolve().parent / "demo" / DEMO_SHEET)
    out = []
    for a in sc.aims_of(sheet, page):
        u = sc.sheet_table_mm(sheet, a["page_mm"])
        out.append((int(round(origin[0] - 10 * u[0])), int(round(origin[1] + 10 * u[1]))))
    return out


REAIM = ("You can lay the sheet again (first push the free arm gently aside, off the sheet) and "
         "run D1 again.")


def _shift_words(over: dict) -> str:
    """Which way the sheet would have to lie, in plain words (X falls to the right, Y grows
    towards the front, as the person sees the table)."""
    parts = []
    if over["left"] > 0 and over["right"] <= 0:
        parts.append(f"about {over['left'] / 10 + 1:.0f} mm further to the right")
    if over["right"] > 0 and over["left"] <= 0:
        parts.append(f"about {over['right'] / 10 + 1:.0f} mm further to the left")
    if over["back"] > 0 and over["front"] <= 0:
        parts.append(f"about {over['back'] / 10 + 1:.0f} mm further towards the front")
    if over["front"] > 0 and over["back"] <= 0:
        parts.append(f"about {over['front'] / 10 + 1:.0f} mm further towards the back")
    if (over["left"] > 0 and over["right"] > 0) or (over["back"] > 0 and over["front"] > 0):
        return "it is longer than the measuring area this program uses, wherever it lies"
    return " and ".join(parts)


def page_fit(sheet: dict, page: int, al: "geo.Alignment") -> dict:
    """After D1 (nothing moves): which spot targets and which strip rows of the page lie inside
    the measuring area this program uses, and which way the sheet would have to lie for the
    rest. Plain words in 'say'."""
    area = geo.MEASURING_AREA
    strips = sheet["pages"][page]["strips"]
    spot_pts, run_pts = [], []
    spot_out = rows_out = 0
    for st in strips:
        for q in st["patches"]:
            u = sc.sheet_table_mm(sheet, q["centre_mm"])
            p = al.to_table(u)
            spot_pts.append(p)
            if not (area.contains(p) and al.on_sheet(u, 0.5)):
                spot_out += 1
        ends = []
        for r in st["run_mm"]:
            u = sc.sheet_table_mm(sheet, (st["x_mm"], r))
            p = al.to_table(u)
            ends.append(p)
            run_pts.append(p)
        if not all(area.contains(p) for p in ends):
            rows_out += 1

    def over(pts):
        return {"left": max(p[0] for p in pts) - area.xmax,
                "right": area.xmin - min(p[0] for p in pts),
                "back": area.ymin - min(p[1] for p in pts),
                "front": max(p[1] for p in pts) - area.ymax}
    say = []
    n_spot, n_rows = len(spot_pts), len(strips)
    if spot_out == 0:
        say.append(f"All {n_spot} patches of this page lie inside the measuring area this program "
                   "uses: the spot stages (D3, D4) can reach every one.")
    else:
        say.append(f"{spot_out} of the {n_spot} patches of this page lie outside the measuring area "
                   f"this program uses, so D3 or D4 stop cleanly before the first of them. For "
                   f"all of them the sheet would have to lie {_shift_words(over(spot_pts))}.")
    if rows_out == 0:
        say.append(f"All {n_rows} rows of this page, with their run-in and run-out, lie inside it "
                   "too: the strip stages (E2, E3) can read every row.")
    else:
        say.append(f"{rows_out} of the {n_rows} rows, with their run-in and run-out, reach outside "
                   f"it, so E2 or E3 stop cleanly before such a row. For all rows the sheet would "
                   f"have to lie {_shift_words(over(run_pts))}. " + REAIM)
    return {"spot_outside": spot_out, "spot_total": n_spot, "rows_outside": rows_out,
            "rows_total": n_rows, "over_spot": over(spot_pts), "over_rows": over(run_pts),
            "say": say}


def demo_aims_point(sheet: dict, page_mm, origin=DEMO_ORIGIN) -> "tuple[int, int]":
    """Where a page point of the demo sheet lies in table units, as the practice run lays it."""
    u = sc.sheet_table_mm(sheet, page_mm)
    return (int(round(origin[0] - 10 * u[0])), int(round(origin[1] + 10 * u[1])))


def load_sheet(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "pages" not in data or "paper_mm" not in data:
        raise ValueError("not a ChromIQ i1iO sheet file")
    return data


C_INTRO = (
    "Part C: READING with the instrument. Stages you choose one at a time; each is explained "
    "first and needs your yes. If a stage fails without leaving anything uncertain, the program "
    "says what failed, keeps everything about it, and offers the next stage; you can also repeat "
    "a stage. Everything goes into the log and a results folder, and at the end into one zip "
    "file to send back. Some stages are first tries: they may simply fail, and that is useful "
    "too.")
C1_SAY = ("Opening the instrument with ChromIQ's reader now (on a Mac this closes X-Rite's "
          "i1ProDeviceService, as ArgyllCMS always does when it opens an i1Pro).")
CAL_WHERE = (
    "Where should the instrument be calibrated? arm: it stays seated in the arm at the resting "
    "place, its opening on the table's white tile (nothing to handle; ArgyllCMS then compares the "
    "table's tile with the i1Pro 2's own white reference, which may give a small white error: "
    "one of the things this run tells us). own: you lift the i1Pro 2 out of the arm's holder and "
    "set it on its own white calibration tile (the plate it came with), cable still plugged in; "
    "afterwards you seat it back exactly as before. Choose own only if its cable reaches.")
CAL_OWN = ("Please lift the i1Pro 2 out of the holder gently, set it on its own white calibration "
           "tile with the opening on the tile, and type ready. (The arm stays where it is; "
           "nothing moves.)")
CAL_RESEAT = ("Please seat the i1Pro 2 back in the arm's holder exactly as it was, and type "
              "seated.")
ASK_REC_CHART = (
    "What lies on the table now? empty: nothing (the reader then reads the mat). chart: your "
    "i1Profiler iO chart from 14 November, laid where it lay then (only then do the readings "
    "mean something). Nothing else may lie on the table.")
SHEET_LAY = (
    "Please lay your printed ChromIQ i1iO sheet on the table now, while the arm is at rest, the "
    "way ChromIQ printed it for the table ({orient}). All three marks must lie where the arm can "
    "reach them; ChromIQ's layout keeps the sheet inside the measuring area of 320 x 230 mm.")
ASK_ARM_WRONG = (
    "Did anything about the TABLE or the ARM look, sound or feel wrong (a move that was not "
    "described, a noise, a bump, the arm in an unexpected place)? Answer no if only the "
    "instrument or its readings were not as described.")
ASK_SHEET_LAID = "Is your sheet lying on the table as described, and nothing else on it?"
