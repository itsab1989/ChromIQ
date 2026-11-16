#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""ChromIQ i1iO session test program 0.4.0: open an X-Rite i1iO 2 table that is already
started, the way i1Profiler opens it, and then offer one of two parts, one step at a time.
Part A is version 0.3.1's steps, unchanged: the homing, three recorded drives out and back
home, the hand-alignment mode at rest, and the close. Part B (new) drives i1Profiler's
recorded spot measurement of row 1 over the EMPTY table, without measuring: the way to the
alignment start, the arm let go and placed by hand, the 28 recorded patch moves, and
i1Profiler's end of the job. Each step is explained first, needs your yes, and is followed
by questions about what you saw, heard and felt. It never measures.

    python3 i1io_session.py              practice run on a SIMULATED table (nothing is opened)
    python3 i1io_session.py --sim cold   the same, for a table that has just been switched on
    python3 i1io_session.py --plan       print every step and every line it could send, and stop
    python3 i1io_session.py --dry-run    the same as --plan, with every byte in hex
    python3 i1io_session.py --real       the real table (asks you to type a sentence first)

Everything sent and received goes into a log file without the table's serial number.
See README.md.
"""
from __future__ import annotations

import argparse
import datetime
import platform
import re
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import i1io_session_table as tbl  # noqa: E402
from i1io_session_table import Doubt, Stopped  # noqa: E402

TITLE = (f"ChromIQ i1iO session test program {tbl.TOOL_VERSION} (recorded steps, one at "
         "a time, each with your yes; never measures)")
CONFIRM_SENTENCE = "i understand that this moves my table"
HANDS = "Keep your hands and everything else away from the arm while it moves."
PLUG = ("If anything looks or sounds wrong while the arm moves, switch the table off at its "
        "power switch or pull its power plug. That is always allowed. Pulling the USB cable "
        "is not a way to stop a movement: the table has its own power supply.")
STOP_PROMISE = ("Ctrl-C works at any time: after Ctrl-C has been noticed, the program sends "
                "nothing more to the table at all. A movement that has already begun is not "
                "stopped by Ctrl-C; only the power switch or plug stops it.")
I1PROFILER = "i1Profiler"
XRITE_HELPERS = ("i1ProfilerTray", "xrdd")
I1PROFILER_RUNNING = (
    "i1Profiler is running. Please quit it (i1Profiler menu, Quit i1Profiler) and start "
    "this program again. Nothing was sent. X-Rite's background helpers (i1ProfilerTray, "
    "X-Rite Device Services) can keep running; you do not need to stop them, and please do "
    "not try to stop them by hand.")
STOPPED = "You stopped the program. Nothing more is sent to the table."
#: 0.3.1: asked only after a homing has finished at the resting place, never after an early
#: stop, and never as a push towards the front of the table (in 0.3.0 that push, asked before
#: the opening, moved the free arm out of the homing guard twice).
WIGGLE = ("Please put one finger on the instrument holder and wiggle it very gently from side "
          "to side, by about a millimetre, then let go at once. Do not push it towards the "
          "front of the table or back, do not press down (the measuring opening rests on the "
          "white tile), and do not force it.")
ASK_TOUCH = (WIGGLE + " Is the arm held, or is it free? \"holds\": it resists your finger, "
             "or springs back when you let go. \"free\": it gives way with almost no effort, "
             "as when the table is switched off.")
TOUCH_CHOICES = ("holds", "free", "not sure", "skip")
TOUCH_BEFORE_INTRO = (
    "Three short questions before the program opens anything (nothing has been sent to the "
    "table yet). Please do not touch the arm now: even a gentle push can move a free arm "
    "out of the range where this program may send it home.")
ASK_MINUTES = ("About how many minutes ago did you quit i1Profiler? (a rough number is fine; "
               "press Enter if you do not know)")
ASK_MOVED = "Since you quit i1Profiler, has anyone touched or moved the arm?"
ASK_LIGHTS = ("Which lights are on right now, on the table and on the i1Pro 2? (a few words, "
              "for example 'table power light green, i1Pro 2 dark'; press Enter to skip)")
ASK_COLD_START = ("If you have seen it: when i1Profiler starts the table after it was switched "
                  "on, what do the arm and the measuring opening do (does the arm travel, how "
                  "far, does the opening lift)? Press Enter to skip.")
ASK_FREE_TOUCH = (
    "The arm should now be free. " + WIGGLE + " Do not move it away from the white tile. "
    "Then take your hand off the arm BEFORE you answer: "
    "right after your answer, the program sends the arm home at once. Does it move freely "
    "now, or does it still hold?")
FREE_CHOICES = ("free", "holds", "not sure", "skip")
ASK_DID = "Did the arm do what was described?"
DID_CHOICES = ("yes", "no", "not sure", "stop")
ASK_SEEN = ("What did you see, hear and feel during this step? (a few words, for example "
            "'quiet, smooth, the opening lifted off the tile'; press Enter to skip)")
RELEASE_WAIT_S = 10.0
NO_LIGHT = ("The instrument's own light will not come on, because this program never talks "
            "to the i1Pro 2.")
REST_PLACE = ("its resting place, where i1Profiler leaves it when you quit it: the instrument "
              "holder over the table's small white tile, with the round measuring opening "
              "resting on that tile")
COLD_TEXT = ("Your table has just been switched on and needs its start-up, which this "
             "program does not send. Please open i1Profiler, wait until it shows the table, "
             "quit i1Profiler, and run this program again. Nothing was moved.")
NOT_CLOSED = (
    "The table was not closed with i1Profiler's two closing lines (they are recorded only "
    "right after a homing at the resting place). Ending without them is what also happens "
    "when i1Profiler is force-quit or its USB cable is pulled. Four earlier runs on your "
    "table ended this way: two of version 0.1.0, one of 0.2.0 and one of 0.2.1. After each "
    "of the first three, the next opening worked normally; how the next opening after the "
    "0.2.1 run went, we do not know yet.")
OPEN_I1PROFILER = "Please open i1Profiler once, let it start the table as usual, and quit it."
#: What to do if i1Profiler does not put things right (a recovery, not a routine step).
RECOVERY = (
    "If i1Profiler does not bring the arm to its resting place, or shows a problem with the "
    "table, switch the table off at its power switch, wait ten seconds, switch it on again, "
    "and open i1Profiler once more. That is a recovery for this case, not a routine step.")
EXPECT_HOME = (
    "We expect i1Profiler to bring the arm home: it did so once in your recordings, from "
    "3 cm out.")
OUT_STATE = ("The arm may have stopped out on the table. The program does not move it again. "
             "Please do not push it around.")
OUT_ON_TABLE = OUT_STATE + " " + OPEN_I1PROFILER + " " + EXPECT_HOME + " " + RECOVERY
#: After f1 was answered and the close (whose f0 switches the mode off) was not sent: a stop
#: inside step 5 (Ctrl-C at the touch question, status 3 when the arm is taken back, any
#: other doubt) or a session that ended after step 5 without the close. f4 reads 01 then;
#: i1Profiler opening a table in this mode has never been recorded (safety review M1).
FREE_MODE_LEFT = (
    "The table is still in the hand-alignment mode: the line that switches this mode off "
    "again is part of the close, and the close was not sent. Nobody has recorded yet what "
    "i1Profiler does when it opens a table in this mode. " + OPEN_I1PROFILER + " " + RECOVERY)
FREE_MAYBE = "The arm may still be free: please do not push it away from its resting place."
CLOSE_AFTER_FREE = (
    "After the hand-alignment step, this close is what switches that mode off again. We "
    "recommend running it now.")
UNFINISHED = (
    "The table never reported that its last movement had finished, so it may still be "
    "moving, or it may start that movement later. Please keep your hands away from the arm, "
    "switch the table off, wait ten seconds and switch it on again, then " + OPEN_I1PROFILER[7:])
#: 0.3.1: the arm stood outside even START_GUARD before the first homing (nothing moved).
OUTSIDE_START = (
    "The arm stands at X {x}, Y {y}, outside the range from which this program may send it "
    "home ({box}). That is a stop, not a fault of your table, and nothing moved. What is known "
    "to bring the arm back: open i1Profiler once, let it start the table, quit i1Profiler, and "
    "then run this program again without touching the arm in between.")
UNFINISHED_FREE = ("The table was also left in the hand-alignment mode (the close, which "
                   "switches it off, was not sent).")

RISKS = (
    "Please read this before you go on.\n"
    "This is an unofficial test program written by ChromIQ. It is not from X-Rite, and X-Rite "
    "has nothing to do with it. Running it is entirely your choice, at every step. It goes "
    "further than the earlier versions: besides opening, homing and closing the table, it "
    "offers drives out over the empty table and back home, and i1Profiler's hand-alignment "
    "mode, in which the arm is free. Every line it can send is a line i1Profiler sent to your "
    "table in your recordings, byte for byte, with the same targets and the same speed. What "
    "is new is the order and the place where some of them are sent: each step says exactly "
    "what is as recorded and what goes one step beyond a recording.\n"
    "It never measures, never talks to the i1Pro 2, never writes anything into the table's "
    "memory, and has no line of its own for the measuring head. Whether the table lifts and "
    "lowers the head by itself during a move is not known; please watch the round opening "
    "and tell us.\n"
    "It also asks for the table's memory block, as i1Profiler does when it opens the table. "
    "That block holds the table's serial number. The program checks only its length and its "
    "first eight bytes, and never writes it down or shows it.\n"
    "What could go wrong, in plain words: the table could do something the recordings never "
    "showed, for example a move that ends somewhere else or makes a noise. That is why the "
    "table must be empty, why every step waits for your yes, why you keep your hands and "
    "everything else away from the arm while it moves, and why you keep the power switch or "
    "plug within reach: switching the table off is always allowed and is the emergency stop. "
    "If anything is not as expected (an answer late, wrong, or a move much slower or faster "
    "than recorded), the program sends nothing more at all.\n"
    "Nothing leaves your computer unless you send the log file yourself.")

RISK_WORDS = {
    "low": ("Risk, as we judge it: low (as recorded, or a small step beside a recording on "
            "the same line, at the resting place)."),
    "medium": ("Risk, as we judge it: medium (recorded lines, but at least one of them in a "
               "place or order the recordings do not show exactly)."),
}
#: Part B's ratings say what they rest on (a part B step is never rated by part A's words).
B_RISK_WORDS = {
    "low": ("Risk, as we judge it: low (nothing moves under motor, exactly the recorded "
            "lines from the recorded place, or part A's homing at the resting place)."),
    "low-medium": ("Risk, as we judge it: low to medium (exactly the recorded moves in the "
                   "recorded order; the pauses between them are a little different, and the "
                   "instrument is not used)."),
    "medium": ("Risk, as we judge it: medium (recorded lines, but at least one of them from a "
               "place or in an order the recordings do not show exactly)."),
}

# ---- 0.4.0: choosing a part, and part B's texts ---------------------------------------------
PART_INTRO = (
    "This program has two parts. You choose one for this run; to run the other one, start "
    "the program again.\n"
    "Part A: the steps of version 0.3.1, exactly as they were (the homing, three drives out "
    "over the empty table and back, the hand-alignment mode at the resting place, the close). "
    "If you have not run 0.3.1 yet, please run part A first.\n"
    "Part B (new): i1Profiler's recorded spot measurement of row 1 from 14 November, over the "
    "EMPTY table and without measuring: the drive to the place where i1Profiler starts an "
    "alignment, the arm let go there, you push it by hand to the front right, then the motors "
    "take it and step it along row 1 (28 recorded moves), and it is sent home. Six steps, "
    "about five minutes. Part B is offered only after part A (or 0.3.1) went well.")
ASK_PART = "Which part do you want to run now? (a, b, or end to stop here)"
PART_CHOICES = ("a", "b", "end")
GATE_QUESTIONS = (
    ("Have you already run part A of this program, or version 0.3.1, on this table, and did "
     "its step 4 (out 15 cm, across to the far side, back, and home) run to its end and do "
     "what was described?", ("yes", "no", "not sure"), "yes"),
    ("In that run, did its step 5 (the hand-alignment mode at the resting place) end with the "
     "arm taken back home by the program, without a stop?", ("yes", "no", "not sure"), "yes"),
    ("In that step 5, when the arm was let go, did anything move or make a sound?",
     ("no", "yes", "not sure"), "no"),
)
GATE_REFUSED = (
    "Then part B is not offered yet: it builds on exactly those steps (the drive across to the "
    "far side, and the hand-alignment mode). Please run part A first and send us the log. "
    "Nothing was sent to the table.")
B_DEPENDS = (
    "Each step of part B needs the one before it, so there is no skipping inside part B: "
    "\"end\" ends part B here, and nothing more is sent.")
ASK_OUT_TOUCH = (
    "The arm should now be free, out at the alignment start. Please put one finger on the "
    "instrument holder and nudge it very gently sideways, by about a millimetre, then let go "
    "at once. Do not press down, do not lift it, and do not force it. Does it give way?")
OUT_TOUCH_CHOICES = ("free", "holds", "not sure", "skip")
OUT_NOT_FREE = (
    "Thank you. Then the next step (pushing the arm by hand) is not offered: nobody should "
    "push an arm that may be held. Nothing more is sent.")
B_BOX_CENTRE = (-1280, 2650)
ASK_PLACE_FIRST = (
    "Now please push the arm gently by the instrument holder, sideways only, nothing pressed "
    "down, to the front right part of the table: about 24 cm to the right of the resting "
    "place and about 27 cm towards the front (right and front as you see the table when you "
    "lay a chart on it). If it resists anywhere, stop pushing. When it is there, take both "
    "hands off the arm and type placed. Type stop to end here instead.")
PLACE_CHOICES = ("placed", "stop")
ASK_HAND_FEEL = ("How did the arm move under your hand: easily and evenly, or did it catch "
                 "or resist anywhere? (a few words; press Enter to skip)")
ASK_FIRST_FEEL = ("How did it feel and sound when the motors took the arm? (a few words; "
                  "press Enter to skip)")
ASK_RING = ("Did the instrument's glider ring (the ring around the round measuring opening) "
            "stay on the mat all the time while the arm stepped along the row?")
RING_CHOICES = ("yes", "no", "not sure", "did not see")
ASK_LIFT = ("Did anything lift or lower at any point during the row: the instrument, its "
            "holder, or the measuring opening?")
LIFT_CHOICES = ("no", "yes", "not sure", "did not see")
ASK_ROW_SEEN = ("What else did you see, hear or feel during the row: an even stepping, any "
                "noise, anything that changed along the way? (a few words; press Enter to skip)")
ROW_RUNNING = ("The arm is stepping along row 1 now (about 40 seconds). Press Enter to stop "
               "at the next patch, or Ctrl-C to send nothing more at all.")
PERSON_STOP_TEXT = ("You stopped on row 1. The arm is held by the motors at patch {n}, and the "
                    "table is still in the hand-alignment mode.")


B_DONE_TEXT = ("The arm is at its resting place, and the hand-alignment mode is off (f4 answered "
               "00): the table is in the state i1Profiler leaves it in after a measurement.")
B_MODE_LEFT = (
    "The table is still in the hand-alignment mode: the line that switches it off (f0) is "
    "part of the end of the job, which was not sent. Nobody has recorded yet what i1Profiler "
    "does when it opens a table in this mode. Please do not push the arm around; it can stay "
    "where it is. " + OPEN_I1PROFILER + " " + RECOVERY)
B_HOME_MODE_LEFT = (
    "The arm is at its resting place, but the table is still in the hand-alignment mode (the "
    "end-of-job line f0 did not answer as recorded, or was not sent). " + OPEN_I1PROFILER + " "
    + RECOVERY)


def b_state_texts(d: tbl.Table) -> "list[str]":
    """Part B: a TRUE statement of the table's state after the session (held or free, in the
    hand-alignment mode or not, out on the table or at rest) and the recovery known to be
    safe for that state. Built only from what the table answered."""
    out = []
    if d.motion_unconfirmed:
        out.append(UNFINISHED)
        if d.mode_on:
            out.append(UNFINISHED_FREE)
        return out
    if d.motions_sent == 0:
        out.append("Nothing was moved.")
        if d.outside_at is not None:
            x, y = d.outside_at
            out.append(OUTSIDE_START.format(x=x, y=y, box=tbl.START_GUARD.text()))
        elif d.state in ("warm", "homed"):
            out.append(NOT_CLOSED)
        return out
    if d.last_move == ("home", True):
        if d.mode_on:
            out.append(B_HOME_MODE_LEFT)
        elif d.state == "closed":
            out.append("The arm is at its resting place, and the table was closed the way "
                       "i1Profiler closes it.")
        elif d.state == "b_done":
            out.append(B_DONE_TEXT)
        else:
            out.append("The arm is at its resting place.")
            out.append(NOT_CLOSED)
        return out
    if (d.last_move == ("home", None) and d.before_move is not None
            and tbl.START_GUARD.contains(d.before_move) and not d.mode_on):
        out.append("The table refused the last homing, which started at the resting place, "
                   "so the arm should still be there.")
        return out
    where = d.outside_at or d.last_read
    at = (f" (it last reported table position X {where[0]}, Y {where[1]})"
          if where is not None else "")
    if not d.mode_on:
        out.append("The arm is out on the table, held by the motors" + at + ".")
        out.append(OUT_ON_TABLE)
        return out
    free = d.arm_free
    if free is True and d.out_touch in ("holds", "not sure"):
        free = None             # f1 answered 01, but the person felt it hold: not known
    hold = {True: "The arm is free (the motors do not hold it)",
            False: "The arm is held by the motors",
            None: "Whether the motors hold the arm is not known"}[free]
    out.append(hold + ", out on the table" + at + ".")
    out.append(B_MODE_LEFT)
    return out


def place_hint(p) -> str:
    """Which way the free arm still has to go, in plain words (right and front as the person
    sees the table when laying a chart: X falls to the right, Y grows towards the front)."""
    b, (cx, cy) = tbl.START_BOX, B_BOX_CENTRE
    parts = []
    if p[0] > b.xmax:
        parts.append(f"about {(p[0] - cx) / 100:.1f} cm further to the right")
    elif p[0] < b.xmin:
        parts.append(f"about {(cx - p[0]) / 100:.1f} cm further to the left")
    if p[1] < b.ymin:
        parts.append(f"about {(cy - p[1]) / 100:.1f} cm further towards the front")
    elif p[1] > b.ymax:
        parts.append(f"about {(p[1] - cy) / 100:.1f} cm further towards the back")
    return ("It needs to go " + " and ".join(parts) + ".") if parts else ""


# ---- talking to the tester -------------------------------------------------------------

def _flush_typed_ahead() -> None:
    try:
        import termios
        if sys.stdin.isatty():
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except (ImportError, OSError, ValueError):
        pass


class Console:
    def __init__(self, log):
        self.log = log

    def say(self, text: str = "") -> None:
        self.log("SAY", text.replace("\n", " / "))
        try:
            for para in text.split("\n"):
                print(textwrap.fill(para, 78) if para else "")
        except OSError:
            pass

    def ask(self, question: str, choices=("yes", "no")) -> str:
        """One of *choices*, typed out in full. The end of input counts as the
        last choice (no / stop / not sure)."""
        while True:
            _flush_typed_ahead()
            try:
                ans = " ".join(input(f"{question} [{'/'.join(choices)}] ").lower().split())
            except (EOFError, OSError):
                self.log("ASK", f"{question} -> input ended, counted as {choices[-1]}")
                return choices[-1]
            if ans in choices:
                self.log("ASK", f"{question} -> {ans}")
                return ans
            print(f"Please type one of these words in full: {', '.join(choices)}")

    def text(self, question: str) -> str:
        _flush_typed_ahead()
        try:
            ans = input(question + " ").strip()
        except (EOFError, OSError):
            ans = ""
        self.log("ANSWER", f"{question} -> {ans!r}")
        return ans

    def poll_enter(self) -> bool:
        """Part B, between two patches: has the person pressed Enter? Never waits."""
        try:
            import select
            if not sys.stdin.isatty():
                return False
            ready, _, _ = select.select([sys.stdin], [], [], 0)
            if ready:
                sys.stdin.readline()
                return True
        except (ImportError, OSError, ValueError):
            pass
        return False

    def sentence(self, prompt: str, wanted: str) -> bool:
        _flush_typed_ahead()
        try:
            ans = input(prompt + "\n> ")
        except (EOFError, OSError):
            return False
        ok = " ".join(ans.lower().replace(".", " ").split()) == wanted
        self.log("ENTER", f"confirmation sentence typed {'correctly' if ok else 'differently'}")
        return ok


class AutoConsole(Console):
    """Answers for the practice run with --auto (and the tests): the first
    choice to every question, nothing as free text. *script* may override
    answers by a word in the question."""

    def __init__(self, log, script=None, interrupt_at=None, stop_at_poll=None):
        super().__init__(log)
        self.script = dict(script or {})
        self.asked = 0
        self.interrupt_at = interrupt_at
        #: part B: "press Enter" at this pause between patches (1 = the first)
        self.stop_at_poll = stop_at_poll
        self.polls = 0

    def poll_enter(self) -> bool:
        self.polls += 1
        return self.stop_at_poll is not None and self.polls == self.stop_at_poll

    def _maybe_interrupt(self):
        self.asked += 1
        if self.interrupt_at is not None and self.asked == self.interrupt_at:
            raise KeyboardInterrupt

    def ask(self, question: str, choices=("yes", "no")) -> str:
        self._maybe_interrupt()
        ans = next((a for k, a in self.script.items() if k in question), choices[0])
        print(f"{question} [{'/'.join(choices)}] {ans}   (automatic answer)")
        self.log("ASK", f"{question} -> {ans} (automatic)")
        return ans

    def text(self, question: str) -> str:
        self._maybe_interrupt()
        print(f"{question}    (automatic answer: nothing)")
        self.log("ANSWER", f"{question} -> '' (automatic)")
        return ""

    def sentence(self, prompt: str, wanted: str) -> bool:
        self._maybe_interrupt()
        return True




# ---- what the program will send ----------------------------------------------------------

def _bare(key: str) -> str:
    return tbl.WIRE[key].decode("ascii").rstrip("\r")


def plan_text(hex_bytes: bool = False) -> str:
    def row(key):
        b = tbl.WIRE[key]
        extra = f"   bytes {b.hex(' ')}" if hex_bytes else ""
        return f"      {_bare(key):20}{extra}"
    out = [f"Every line this program can send. Nothing else can be sent: {len(tbl.WIRE)} "
           f"different lines; in part A at most {tbl.MAX_LINES} lines and {tbl.MAX_MOTIONS} "
           "movements in one session, and each step at most its own lines and movements "
           "(below). After any "
           "stop or any doubt, nothing more is sent at all.", "",
           "PART A (choose a at the start) uses lines 1 to 16; part B uses the others "
           "and the reading, homing and mode lines.", "",
           f"The {len(tbl.WIRE)} lines and where i1Profiler sent them in your recordings:"]
    for key in tbl.WIRE:
        out.append(row(key))
        out.append(f"         recorded: {tbl.RECORDED_AT[key]}")
    out += ["", "Before anything: the USB set-up i1Profiler uses (FTDI reset, purge, purge, "
            "57600 baud, 8N1), then 1 s of listening.", "",
            f"Opening (only reads; {len(tbl.OPEN_KEYS)} lines). If a0 answers 111800 (just "
            "switched on), it stops after the sixth line:"]
    out += [row(k) for k in tbl.OPEN_KEYS]
    for n, step in enumerate(tbl.STEPS, 1):
        out += ["", f"Step {n}: {step.title} ({tbl.STEP_MAX_LINES[step.key]} lines, "
                    f"{tbl.STEP_MAX_MOTIONS[step.key]} movements; risk {step.risk}). Only "
                    "after your yes; you may skip it:"]
        for op in step.ops:
            if op[0] == "x":
                out.append(row(op[1]))
            elif op[0] == "f4":
                out.append(row("arm_mode") + f"   (must answer {op[1]})")
            elif op[0] == "p0":
                out.append(row("position") + f"   (must read {tbl.BOXES[op[1]].text()})")
            elif op[0] == "home_rest":
                out.append(row("home") + "   (MOVES home; within 0.6 s, "
                           f"{tbl.TIME_WINDOW['home_wide'][1]:.1f} s from Y "
                           f"{tbl.REST_RECORDED.ymax + 1}..{tbl.REST_GUARD.ymax}, or "
                           f"{tbl.TIME_WINDOW['home_far'][1]:.1f} s from farther out, up to Y "
                           f"{tbl.START_GUARD.ymax})")
            elif op[0] == "move":
                lo, hi = tbl.TIME_WINDOW[op[2]]
                out.append(row(op[1]) + f"   (MOVES; must finish within {lo:.2f}..{hi:.2f} s)")
            elif op[0] == "touch":
                out.append("      ... you touch the free arm gently (nothing is sent) ...")
    out += ["", f"PART B (choose b at the start): at most {tbl.B_MAX_LINES} lines and "
                f"{tbl.B_MAX_MOTIONS} movements in one session; each step needs the one "
                "before it. The opening as above, then:"]
    for n, step in enumerate(tbl.B_STEPS, 1):
        out += ["", f"B{n}: {step.title} ({tbl.STEP_MAX_LINES[step.key]} lines at most, "
                    f"{tbl.STEP_MAX_MOTIONS[step.key]} movements; risk {step.risk}):"]
        out += _plan_ops(step, row)
    for step in tbl.near_steps():
        out += ["", f"Optional: {step.title} ({tbl.STEP_MAX_LINES[step.key]} lines, "
                    f"{tbl.STEP_MAX_MOTIONS[step.key]} movements; risk {step.risk}):"]
        out += _plan_ops(step, row)
    return "\n".join(out)


def _plan_ops(step: tbl.Step, row) -> "list[str]":
    out = []
    for op in step.ops:
        k = op[0]
        if k == "x":
            out.append(row(op[1]))
        elif k == "f4":
            out.append(row("arm_mode") + f"   (must answer {op[1]})")
        elif k == "p0":
            out.append(row("position") + f"   (must read {tbl.BOXES[op[1]].text()})")
        elif k == "home_rest":
            out.append(row("home") + "   (MOVES home, from rest, as part A)")
        elif k == "move":
            lo, hi = tbl.TIME_WINDOW[op[2]]
            out.append(row(op[1]) + f"   (MOVES; must finish within {lo:.2f}..{hi:.2f} s)")
        elif k == "p0m1":
            out.append(row("position") + f"   (must read {tbl.AT_M1_SENSOR.text()} or "
                       f"{tbl.AT_M1_SIGHT.text()})")
        elif k == "p0still":
            out.append(row("position") + f"   (must read within {op[1]} units of the reading "
                       "before)")
        elif k == "touch_out":
            out.append("      ... you touch the free arm gently (nothing is sent) ...")
        elif k == "place":
            out.append("      ... you push the free arm by hand and type placed ...")
            out.append(row("status"))
            out += [row("arm_mode") + "   (must answer 01)"] * 4
            out.append(row("position") + f"   (once per try, at most {tbl.PLACE_TRIES} "
                       f"tries, until it reads {tbl.START_BOX.text()})")
        elif k == "pause":
            pass
        elif k == "p0spot":
            out.append(row("position") + f"   (must read {tbl.AT_SPOT[op[1]].text()})")
        elif k == "p0last":
            out.append(row("position") + "   (must read the patch reached, plus or minus 5)")
    if step.key == "b_row":
        out.insert(0, "      27 times: 1 s pause (Enter stops here), then position and the "
                      "next patch move:")
    return out


# ---- the session ------------------------------------------------------------------------

class Session:
    def __init__(self, table: tbl.Table, ui, simulated: bool, other_program=None,
                 answers=None, sim_hand=None):
        self.d, self.ui, self.simulated = table, ui, simulated
        self.other_program = other_program or (lambda: False)
        self.answers: "list[tuple[str, str]]" = list(answers or [])
        self.stopped_by_person = False
        self.touch_asked = False
        self.seen_ok = True
        #: simulated runs only: the simulator's scripted hand (moves the simulated free arm)
        self.sim_hand = sim_hand
        self.part = None
        table._touch = self._free_touch
        table._touch_out = self._out_touch
        table._hand = self._hand
        table._poll_stop = lambda: bool(getattr(self.ui, "poll_enter", lambda: False)())

    def note(self, question: str, answer: str) -> None:
        self.answers.append((question, answer))

    def _free_touch(self) -> str:
        ans = self.ui.ask(ASK_FREE_TOUCH, FREE_CHOICES)
        self.note("free arm at home (step 'free')", ans)
        return ans

    # ---- part B (0.4.0) ---------------------------------------------------------------------
    def _out_touch(self) -> str:
        ans = self.ui.ask(ASK_OUT_TOUCH, OUT_TOUCH_CHOICES)
        self.note("free arm at the alignment start (part B step 2)", ans)
        return ans

    def _hand(self, n: int, last) -> str:
        if n == 1:
            q = ASK_PLACE_FIRST
        else:
            q = (f"The arm reports table position X {last[0]}, Y {last[1]}; the box it must be "
                 f"in is {tbl.START_BOX.text()}. " + place_hint(last) + " Please push it "
                 "there gently, take both hands off the arm, and type placed (try "
                 f"{n} of {tbl.PLACE_TRIES}). Type stop to end here instead.")
        ans = self.ui.ask(q, PLACE_CHOICES)
        self.note(f"placement try {n}", ans)
        if ans == "placed" and self.sim_hand is not None:
            self.sim_hand(n)
        return ans

    def choose_part(self) -> str:
        self.ui.say("")
        self.ui.say(PART_INTRO)
        part = self.ui.ask(ASK_PART, PART_CHOICES)
        self.note("part", part)
        if part != "b":
            return part
        for q, choices, good in GATE_QUESTIONS:
            ans = self.ui.ask(q, choices)
            self.note(q, ans)
            if ans != good:
                self.ui.say(GATE_REFUSED)
                return "refused"
        return "b"

    def offer_b(self, n: int, step: tbl.Step) -> str:
        self.ui.say("")
        self.ui.say(f"Part B, step {n}: {step.title}.")
        self.ui.say(step.explain)
        if step.key == "b_row" and "home_from_patch" in tbl.OPTIONAL_NEAR_STEPS:
            self.ui.say("If you press Enter during the row, the program stops at the next "
                        "patch and then offers to send the arm home from there.")
        self.ui.say("What is not exactly as recorded: " + step.beyond)
        m = tbl.STEP_MAX_MOTIONS[step.key]
        lines = tbl.STEP_MAX_LINES[step.key]
        self.ui.say(B_RISK_WORDS[step.risk] + f" It sends at most {lines} lines; "
                    + ("none of them moves the arm." if m == 0 else
                       "1 of them moves the arm." if m == 1 else f"{m} of them move the arm."))
        if step.key in ("b_align", "b_place", "b_first", "b_row"):
            self.ui.say(B_DEPENDS)
        if m:
            self.ui.say(PLUG)
            self.ui.say(STOP_PROMISE)
            question = f"{HANDS} Run this step now?"
        else:
            question = "Run this step now?"
        ans = self.ui.ask(question, ("yes", "end"))
        self.note(f"step {step.key}", ans)
        return ans

    def offer_near(self, step: tbl.Step, why: str) -> str:
        self.ui.say("")
        self.ui.say(f"Offered: {step.title}.")
        self.ui.say(why)
        self.ui.say(step.explain)
        self.ui.say("What is not exactly as recorded: " + step.beyond)
        m = tbl.STEP_MAX_MOTIONS[step.key]
        self.ui.say(B_RISK_WORDS[step.risk] + f" It sends {tbl.STEP_MAX_LINES[step.key]} "
                    "lines; " + ("none of them moves the arm." if m == 0 else
                                 "1 of them moves the arm."))
        if m:
            self.ui.say(PLUG)
            q = f"{HANDS} Run it now?"
        else:
            q = "Run it now?"
        ans = self.ui.ask(q, ("yes", "no"))
        self.note(f"optional {step.key}", ans)
        return ans

    def _after_b_step(self, step: tbl.Step) -> None:
        """The questions after a part B step (nothing moves while they are asked)."""
        if step.key == "b_place":
            self.note("b_place: how the arm moved under the hand", self.ui.text(ASK_HAND_FEEL))
            return
        did = self.ui.ask(ASK_DID, DID_CHOICES)
        self.note(f"step {step.key}: as described?", did)
        if step.key == "b_first":
            self.note("b_first: the motors taking the arm", self.ui.text(ASK_FIRST_FEEL))
        if step.key == "b_row":
            self.note("b_row: glider ring on the mat all the time?",
                      self.ui.ask(ASK_RING, RING_CHOICES))
            self.note("b_row: anything lifted or lowered?", self.ui.ask(ASK_LIFT, LIFT_CHOICES))
            self.note("b_row: seen, heard, felt", self.ui.text(ASK_ROW_SEEN))
        else:
            self.note(f"step {step.key}: seen, heard, felt", self.ui.text(ASK_SEEN))
        if did == "stop":
            self.stopped_by_person = True
            raise Stopped(STOPPED)
        if did != "yes":
            self.seen_ok = False
            raise Stopped("Thank you, that is exactly what we need to know. The program stops "
                          "here; nothing more is sent.")

    def _run_near(self, key: str, why: str) -> bool:
        if key not in tbl.OPTIONAL_NEAR_STEPS:
            return False
        step = tbl.NEAR_STEP_DEFS[key]
        if not self.d.can_run(step):
            return False
        if self.offer_near(step, why) != "yes":
            return False
        if self.other_program():
            self.d.close_for_sending("i1Profiler was started during the session")
            raise Stopped("i1Profiler has started, so the program stops here. Nothing more "
                          "is sent to the table.")
        self.d.run_step(step)
        if tbl.STEP_MAX_MOTIONS[step.key]:
            self._after_b_step(step)
        return True

    def go_b(self) -> int:
        d = self.d
        for n, step in enumerate(tbl.B_STEPS, 1):
            if not d.can_run(step):
                if step.key == "b_place" and d.out_touch != "free":
                    self.ui.say(OUT_NOT_FREE)
                    d.close_for_sending("the arm did not give way at the alignment start")
                    return 1
                break
            ans = self.offer_b(n, step)
            if ans != "yes":
                if d.state == "row":
                    self._run_near("home_from_patch", "You ended part B with the arm on row 1.")
                break
            if self.other_program():
                d.close_for_sending("i1Profiler was started during the session")
                raise Stopped("i1Profiler has started, so the program stops here: two "
                              "programs must never talk to the table at the same time. "
                              "Nothing more is sent to the table.")
            if step.key == "b_row":
                self.ui.say(ROW_RUNNING)
            try:
                d.run_step(step)
            except tbl.PersonStop:
                self.ui.say(PERSON_STOP_TEXT.format(n=(d.last_spot_sent or 0) + 1))
                if not self._run_near("home_from_patch", "You stopped on row 1."):
                    self.stopped_by_person = True
                    d.close_for_sending("stopped by you on row 1")
                    return 1
                break
            self.ui.say(f"Part B, step {n} is done.")
            self._after_b_step(step)
        if d.state == "b_done":
            self._run_near("close_after_end", "Part B is done. We do not recommend this close: "
                           "the end of job has already left the table as i1Profiler leaves "
                           "it between jobs. It is offered so you can try it if you like.")
        return 0

    def offer(self, n: int, step: tbl.Step) -> str:
        self.ui.say("")
        self.ui.say(f"Step {n}: {step.title}.")
        self.ui.say(step.explain)
        self.ui.say("What is not exactly as recorded: " + step.beyond)
        if step.leaves == "closed" and self.d.freed:
            self.ui.say(CLOSE_AFTER_FREE)
        m = tbl.STEP_MAX_MOTIONS[step.key]
        self.ui.say(RISK_WORDS[step.risk] + f" It sends {tbl.STEP_MAX_LINES[step.key]} lines; "
                    + ("none of them moves the arm." if m == 0 else
                       "1 of them moves the arm." if m == 1 else f"{m} of them move the arm."))
        if tbl.STEP_MAX_MOTIONS[step.key]:
            self.ui.say(PLUG)
            self.ui.say(STOP_PROMISE)
            question = f"{HANDS} Run this step now?"
        else:
            question = "Run this step now?"
        ans = self.ui.ask(question, ("yes", "skip", "end"))
        self.note(f"step {step.key}", ans)
        return ans

    def go(self) -> int:
        """The whole session. 0: ended as chosen; 1: stopped by you or cold table; 2: a doubt."""
        try:
            part = self.choose_part()
            if part not in ("a", "b"):
                self.d.close_for_sending("no part was chosen")
                return 0 if part == "end" else 1
            self.part = part.upper()
            self.d.part = self.part
            self.ui.log("INFO", f"part {self.part} chosen")
            self.ui.say("Talking to the table. Nothing moves yet.")
            if self.d.opening() == "cold":
                self.ui.say("The table answered as expected, and we believe it says it has just "
                            "been switched on (a0 = 111800).")
                raise Stopped(COLD_TEXT)
            self.ui.say("The table answered as expected: it is started (a0 = 130000), and f4 "
                        "answered 00 as at every recorded opening (f4 is a mode flag; it does "
                        "not tell whether the motors hold the arm).")
            if self.part == "B":
                return self.go_b()
            for n, step in enumerate(tbl.STEPS, 1):
                if not self.d.can_run(step):
                    continue
                ans = self.offer(n, step)
                if ans == "end":
                    break
                if ans != "yes":
                    continue
                if self.other_program():
                    self.d.close_for_sending("i1Profiler was started during the session")
                    raise Stopped("i1Profiler has started, so the program stops here: two "
                                  "programs must never talk to the table at the same time. "
                                  "Nothing more is sent to the table.")
                self.d.run_step(step)
                self.ui.say(f"Step {n} is done. "
                            + ("" if not tbl.STEP_MAX_MOTIONS[step.key] else
                               "The table reports the arm back at its resting place."))
                if tbl.STEP_MAX_MOTIONS[step.key]:
                    did = self.ui.ask(ASK_DID, DID_CHOICES)
                    self.note(f"step {step.key}: as described?", did)
                    self.note(f"step {step.key}: seen, heard, felt", self.ui.text(ASK_SEEN))
                    if did == "stop":
                        self.stopped_by_person = True
                        raise Stopped(STOPPED)
                    if did != "yes":
                        self.seen_ok = False
                        raise Stopped("Thank you, that is exactly what we need to know. The "
                                      "program stops here; nothing more is sent.")
            return 0
        except Stopped as exc:
            if self.d.stop_requested:
                self.stopped_by_person = True
            self.ui.say(str(exc))
            return 1
        except KeyboardInterrupt:
            self.stopped_by_person = True
            self.d.close_for_sending("stopped with Ctrl-C")
            self.ui.say(STOPPED)
            return 1
        except Doubt as exc:
            self.ui.say(exc.plain or f"The program stopped because {exc}. Nothing more is "
                        "sent to the table.")
            return 2
        except Exception as exc:
            self.d.close_for_sending(f"an unexpected error ({type(exc).__name__})")
            self.ui.say(f"The program stopped because of an unexpected error "
                        f"({type(exc).__name__}). Nothing more is sent to the table.")
            return 2
        finally:
            self.d.close_for_sending("the session is over")

    def where(self) -> str:
        """Where the arm is at the end, as far as the program knows."""
        d = self.d
        if d.motion_unconfirmed:
            return "unfinished"
        if d.motions_sent == 0:
            return "not moved"
        if d.outside_at is not None:
            return "outside"
        if d.last_move == ("home", True):
            return "home"
        if (d.last_move == ("home", None) and d.before_move is not None
                and tbl.START_GUARD.contains(d.before_move)):
            return "home, homing refused"      # answered with an error: it had not left rest
        return "maybe out"

    def ending(self, code: int) -> None:
        if self.part == "B":
            try:
                self.ui.say("")
                for text in b_state_texts(self.d):
                    self.ui.say(text)
            except BaseException:
                pass
            return
        try:
            d, w = self.d, self.where()
            #: f1 was answered and the close never followed: the hand-alignment mode is on
            free_mode = d.freed and d.state != "closed"
            self.ui.say("")
            if w == "unfinished":
                self.ui.say(UNFINISHED)
            elif w == "maybe out":
                self.ui.say(OUT_STATE if free_mode else OUT_ON_TABLE)
            elif w == "not moved":
                self.ui.say("Nothing was moved.")
                if d.outside_at is not None:
                    x, y = d.outside_at
                    self.ui.say(OUTSIDE_START.format(x=x, y=y, box=tbl.START_GUARD.text()))
            elif w == "outside":
                x, y = d.outside_at
                self.ui.say(f"The arm last read X {x}, Y {y}, not where the step needed it. "
                            "The program does not move it again; please do not push it "
                            "around." + ("" if free_mode else
                                         " " + OPEN_I1PROFILER + " " + EXPECT_HOME + " "
                                         + RECOVERY))
            elif w == "home, homing refused":
                self.ui.say("The table refused the last homing, which started at the resting "
                            "place, so the arm should still be there.")
            else:
                self.ui.say("The arm is at its resting place.")
            if d.state == "closed":
                self.ui.say("The table was closed the way i1Profiler closes it.")
            elif free_mode:
                self.ui.log("INFO", "the hand-alignment mode was left on: f1 answered 01, the "
                                    "close (s0 f0 f3) was not sent; f4 reads 01")
                if w == "unfinished":
                    self.ui.say(UNFINISHED_FREE)
                else:
                    if d.state != "free_homed":
                        self.ui.say(FREE_MAYBE)
                    self.ui.say(FREE_MODE_LEFT)
            elif d.state in ("warm", "homed", "free_homed"):
                self.ui.say(NOT_CLOSED)
        except BaseException:
            pass

    def may_touch(self, code: int = 0) -> bool:
        """0.3.1: only after a session that ended as chosen (no early stop) with a homing
        finished at the resting place as the last movement."""
        return (code == 0 and self.d.lines_sent > 0 and not self.d.motion_unconfirmed
                and not self.stopped_by_person
                and self.where() == "home"
                and self.seen_ok)

    def touch(self, when: str) -> bool:
        self.touch_asked = True
        try:
            ans = self.ui.ask(ASK_TOUCH, TOUCH_CHOICES)
        except KeyboardInterrupt:
            self.stopped_by_person = True
            self.note(f"arm held? ({when})", "stopped with Ctrl-C")
            return False
        except BaseException:
            ans = "skipped"
        self.note(f"arm held? ({when})", ans)
        return True

    def after(self, transport, real: bool, code: int = 0) -> None:
        """After go(): touches (USB held, then released), questions, closing advice. Sends
        nothing (go() has closed the table for sending)."""
        log = self.ui.log
        touch = self.may_touch(code)
        if touch:
            self.ui.say("")
            self.ui.say("The program still holds the table's USB connection, and it sends "
                        "nothing more.")
            touch = self.touch("while the program still held the USB connection")
        transport.close()
        log("INFO", "the program has let go of the table's USB connection (nothing is sent "
                    "when it does)")
        if touch:
            self.ui.say("The program has now let go of the table's USB connection. It waits "
                        "ten seconds; then please touch the holder gently once more, the same "
                        "way.")
            if real:
                try:
                    time.sleep(RELEASE_WAIT_S)
                except KeyboardInterrupt:
                    self.stopped_by_person = True
                    self.note("arm held? (ten seconds after the release)",
                              "stopped with Ctrl-C during the wait")
                    touch = False
            if touch:
                self.touch("about ten seconds after the program let go of the USB connection")
        if self.stopped_by_person:
            log("INFO", "stopped by you: no more questions")
        else:
            self.questions()

    def questions(self) -> None:
        if self.d.lines_sent == 0:
            return
        try:
            self.ui.say("")
            self.ui.say("A few questions for the report (just press Enter to skip one).")
            for q in ("Did you hear anything unusual (grinding, knocking, clicking, a long "
                      "buzz)? If yes, during which step?",
                      "Had the table been switched off and on before this run? If yes, how "
                      "long before?",
                      ASK_LIGHTS.replace("right now", "now"), ASK_COLD_START,
                      "Did anything else surprise you, or is there anything you want to add?"):
                self.note(q, self.ui.text(q))
        except BaseException:
            try:
                self.ui.say("Questions skipped.")
            except BaseException:
                pass

# ---- the environment -------------------------------------------------------------------

def _pgrep(*args) -> "list[str]":
    try:
        out = subprocess.run(["pgrep", *args], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []
    return [line for line in out.stdout.splitlines() if line.strip()]


#: i1Profiler's program inside its app bundle (the second, independent check).
I1PROFILER_PATH = "i1Profiler.app/Contents/MacOS"


def i1profiler_running() -> bool:
    """By its process name, and by its path inside the app bundle (the real
    process name was never checked on the tester's Mac). The hard guard stays
    libusb's exclusive claim of the table's interface."""
    return bool(i1profiler_matches())


def i1profiler_matches() -> "list[str]":
    """What was found: 'name' and/or 'app path' (the app-path check could also match a helper
    inside i1Profiler's bundle; the log then names it, so a refusal is never a mystery)."""
    found = []
    if _pgrep("-x", "-i", I1PROFILER):
        found.append("a process named i1Profiler")
    if _pgrep("-f", I1PROFILER_PATH):
        found.append("a process inside i1Profiler.app (i1Profiler itself or one of its helpers)")
    return found


def xrite_helpers_running() -> "list[str]":
    return [name for name in XRITE_HELPERS if _pgrep("-x", "-i", name)]


class Lock:
    """Only one copy of this program at a time (per user)."""

    def __init__(self):
        self.path = Path(tempfile.gettempdir()) / "chromiq-i1io-session.lock"
        self.fh = None

    def acquire(self) -> bool:
        try:
            import fcntl
        except ImportError:
            return True
        self.fh = self.path.open("w", encoding="utf-8")
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.fh.close()
            self.fh = None
            return False
        return True

    def release(self) -> None:
        if self.fh is not None:
            self.fh.close()
            self.fh = None


def install_signals(table: tbl.Table) -> dict:
    """Ctrl-C (and the other stop signals) never cut an exchange in half:
    while one runs they only ask for a stop before the next line; at a
    question they stop the run at once. Ctrl-Z is ignored."""
    old = {}

    def handler(signum, frame):
        if table.busy:
            first = not table.stop_requested
            table.request_stop()
            if first:
                try:
                    print("\nThe program sends nothing more; if the arm is moving, the table "
                          "finishes that movement first.", flush=True)
                except Exception:
                    pass
            return
        raise KeyboardInterrupt
    for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT"):
        if hasattr(signal, name):
            sig = getattr(signal, name)
            old[sig] = signal.signal(sig, handler)
    for name in ("SIGTSTP", "SIGTTIN", "SIGTTOU"):
        if hasattr(signal, name):
            sig = getattr(signal, name)
            old[sig] = signal.signal(sig, signal.SIG_IGN)
    return old


def environment(real: bool) -> str:
    mac = platform.mac_ver()[0]
    pyusb = "not used (simulated table)"
    if real:
        try:
            import usb
            pyusb = getattr(usb, "__version__", "unknown version")
        except ImportError:
            pyusb = "not installed"
    return (f"{platform.system()} {mac or platform.release()} {platform.machine()}; "
            f"Python {platform.python_version()}; pyusb {pyusb}")


def holder_names_for_screen(holders) -> str:
    """The holders as the person sees them: program names only. The process numbers stay in
    the log (safety review of 0.2.2, N1: a number on screen invites ending the process)."""
    def name(entry):
        return re.sub(r" \(pid \d+\)$", "", entry.split(": ", 1)[-1])
    owners = [name(h) for h in holders if h.startswith("exclusive owner: ")]
    others = [name(h) for h in holders if h.startswith("connected: ")
              and name(h) != "this program"]
    if owners:
        return "macOS names the program holding it: " + ", ".join(owners) + "."
    if others:
        return ("macOS did not name a single holder; these programs are connected to it: "
                + ", ".join(others) + ".")
    return "macOS did not say which program it is."


def touch_before_opening(ui, notes) -> None:
    """Before anything is opened or sent: how long ago i1Profiler was quit, whether the arm was
    moved, the lights. 0.3.1: NO touch here (in 0.3.0 the touch asked here pushed the free arm
    out of the homing guard, twice). Sends nothing; the table is not even opened yet."""
    ui.say("")
    ui.say(TOUCH_BEFORE_INTRO)
    notes.append(("minutes since i1Profiler was quit", ui.text(ASK_MINUTES)))
    notes.append(("arm touched or moved since i1Profiler was quit",
                  ui.ask(ASK_MOVED, ("no", "yes", "not sure"))))
    notes.append(("lights before opening", ui.text(ASK_LIGHTS)))


PRE_QUESTIONS = (
    "Is the table's power switch or power plug within reach of your hand, so you can switch "
    "it off at once if needed?",
    "Is the i1Pro 2 seated in the arm's holder and connected, exactly as when you use it "
    "with i1Profiler?",
    "Is the table completely empty: no paper, no chart, nothing lying on it, and nothing in "
    "the way of the arm over the whole table?",
    f"Is the arm at {REST_PLACE}?",
    "Since the table was last switched on, has i1Profiler connected to it and been quit "
    "again?",
)


# ---- main ------------------------------------------------------------------------------

def main(argv=None, sim_table=None, console=None) -> int:
    ap = argparse.ArgumentParser(description=TITLE)
    ap.add_argument("--real", action="store_true",
                    help="use the REAL table (without it: a simulated table)")
    ap.add_argument("--sim", choices=("cold", "warm"), default="warm",
                    help="simulated table: started (warm, the default) or just switched on")
    ap.add_argument("--plan", action="store_true",
                    help="print every step and line the program can send, and stop")
    ap.add_argument("--dry-run", action="store_true",
                    help="like --plan, with every byte in hex; opens nothing, sends nothing")
    ap.add_argument("--auto", action="store_true",
                    help="simulated run only: answer every question automatically")
    ap.add_argument("--log", help="where to write the log file (default: this folder)")
    ap.add_argument("--version", action="version", version=TITLE)
    args = ap.parse_args(argv)

    if args.plan or args.dry_run:
        print(plan_text(hex_bytes=args.dry_run))
        return 0
    if args.real and args.auto:
        ap.error("--auto is only for the simulated table")
    if sys.version_info < (3, 8):
        print("This program needs Python 3.8 or newer.")
        return 2

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "" if args.real else f"-simulated-{args.sim}"
    log_path = Path(f"i1io-session-{stamp}{suffix}.txt")
    try:
        if args.log:
            log_path = Path(args.log)
            fh = log_path.open("w", encoding="utf-8")
        else:
            for n in range(1, 1000):
                log_path = Path(f"i1io-session-{stamp}{'' if n == 1 else f'-{n}'}{suffix}.txt")
                try:
                    fh = log_path.open("x", encoding="utf-8")
                    break
                except FileExistsError:
                    continue
            else:
                raise FileExistsError(log_path.name)
    except OSError as exc:
        print(f"The log file {log_path.name} cannot be written here ({type(exc).__name__}). "
              "Please start the program from a folder you can write to. Nothing was sent.")
        return 2

    started = time.monotonic()

    def log(kind, text):
        if kind in ("ASK", "ANSWER", "ENTER"):
            text = f"{text}   [program time {time.monotonic():.1f} s, " \
                   f"{time.monotonic() - started:.0f} s after the start]"
        try:
            fh.write(f"{kind:6} {text}\n")
            fh.flush()
        except (OSError, ValueError):
            pass
        if not args.real and kind in ("SEND", "RECV"):
            try:
                print(f"    {kind} {text.split(None, 1)[-1]}")
            except OSError:
                pass

    log("INFO", f"{TITLE}; {'REAL table' if args.real else 'SIMULATED table, ' + args.sim}; "
                f"{datetime.datetime.now().isoformat(timespec='seconds')}")
    log("INFO", environment(args.real))
    log("INFO", "allowed lines: " + " ".join(_bare(k) for k in tbl.WIRE)
        + f"; at most {tbl.MAX_LINES} lines and {tbl.MAX_MOTIONS} movements per session; "
        + "per step " + ", ".join(f"{s.key} {tbl.STEP_MAX_LINES[s.key]}/"
                                  f"{tbl.STEP_MAX_MOTIONS[s.key]}" for s in tbl.STEPS))
    log("INFO", "the table's memory answers (they hold its serial number) are checked for "
                "length and their first 8 bytes and never written down")
    ui = console or Console(log)
    if console is not None:
        console.log = log
    lock, transport = Lock(), None
    code = 2
    pre_notes: "list[tuple[str, str]]" = []
    early = {}

    def early_stop(signum, frame):
        raise KeyboardInterrupt
    for name in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            try:
                early[getattr(signal, name)] = signal.signal(getattr(signal, name), early_stop)
            except (ValueError, OSError):
                pass
    try:
        ui.say(TITLE + ".")
        if args.real:
            if not sys.stdin.isatty():
                ui.say("With --real, every answer must be typed by a person at the keyboard, "
                       "so the program does not run with piped or redirected input.")
                return 2
            try:
                usb_info = tbl.check_usb_available()
            except tbl.NotAvailable as exc:
                ui.say(str(exc) + " Nothing was sent.")
                return 2
            log("INFO", usb_info)
            ui.say(RISKS)
            if i1profiler_running():
                log("INFO", "i1Profiler is running: refused; found " + "; ".join(i1profiler_matches()))
                ui.say(I1PROFILER_RUNNING + " (Found: " + "; ".join(i1profiler_matches()) + ".)")
                return 2
            if not lock.acquire():
                ui.say("Another copy of this program is running. Please let it finish first. "
                       "Nothing was sent.")
                return 2
            for q in PRE_QUESTIONS:
                if ui.ask(q, ("yes", "no", "not sure", "stop")) != "yes":
                    ui.say("Then this program does not start. " + OPEN_I1PROFILER
                           + " Nothing was sent.")
                    return 1
            if i1profiler_running():
                log("INFO", "i1Profiler is running: refused before the first touch; found "
                    + "; ".join(i1profiler_matches()))
                ui.say(I1PROFILER_RUNNING + " (Found: " + "; ".join(i1profiler_matches()) + ".)")
                return 2
            touch_before_opening(ui, pre_notes)
            if not ui.sentence("To go on with the REAL table, type this sentence and press "
                               "Enter:\n    I understand that this moves my table",
                               CONFIRM_SENTENCE):
                ui.say("That was not the sentence, so nothing was sent to the table.")
                return 1
            if i1profiler_running():
                log("INFO", "i1Profiler is running: refused; found " + "; ".join(i1profiler_matches()))
                ui.say(I1PROFILER_RUNNING + " (Found: " + "; ".join(i1profiler_matches()) + ".)")
                return 2
            helpers = xrite_helpers_running()
            log("INFO", f"X-Rite background helpers running: {helpers or 'none'}")
            log("INFO", "macOS lists for the table before opening: "
                        + ("; ".join(tbl.usb_holders()) or "nobody"))
            try:
                transport = tbl.open_table()
            except tbl.TableBusy as exc:
                holders = tbl.usb_holders()
                log("INFO", f"opening refused by macOS at {exc.step} (libusb {exc.code}); "
                            "macOS lists for the table: " + ("; ".join(holders) or "nobody"))
                ui.say(tbl.BUSY_TEXT + " " + holder_names_for_screen(holders))
                ui.say(tbl.BUSY_STEPS)
                return 2
            except (tbl.NotAvailable, tbl.TransportError) as exc:
                ui.say(str(exc))
                return 2
        else:
            from i1io_session_sim import SimTable, SimTransport
            sim = sim_table or SimTable(cold=(args.sim == "cold"))
            transport = SimTransport(sim)
            if console is None and (args.auto or not sys.stdin.isatty()):
                ui = AutoConsole(log)
            ui.say(f"SIMULATED TABLE ({'just switched on' if sim.cold else 'already started'}"
                   "): nothing is opened and nothing is sent to any device. Every line the "
                   "real run would send and receive is printed, so you can see what it will "
                   "do. Add --real for the real table.")
            if console is None and not isinstance(ui, AutoConsole):
                for q in PRE_QUESTIONS:
                    if ui.ask(q, ("yes", "no", "not sure", "stop")) != "yes":
                        ui.say("Then this program does not start (practice run).")
                        return 1
                touch_before_opening(ui, pre_notes)
        log("INFO", tbl.usb_summary(transport))
        table = tbl.Table(transport, log=log)
        previous = install_signals(table)
        try:
            r = Session(table, ui, simulated=not args.real,
                        other_program=i1profiler_running if args.real else None,
                        answers=pre_notes,
                        sim_hand=None if args.real else getattr(transport.table, "hand", None))
            code = r.go()
            r.ending(code)
            r.after(transport, real=args.real, code=code)
            if r.part == "B":
                log("INFO", f"part B: after m1 the reading fitted the {table.m1_frame or '-'} "
                            f"explanation; touch at the alignment start "
                            f"{table.out_touch or '-'}; placement reads {table.place_reads}; "
                            f"last patch sent {(table.last_spot_sent or -1) + 1}, last read "
                            f"{(table.last_spot_read if table.last_spot_read is not None else -1) + 1}; "
                            f"hand-alignment mode {'on' if table.mode_on else 'off'}; arm "
                            f"{ {True: 'free', False: 'held', None: 'unknown'}[table.arm_free] }")
            log("INFO", f"result {code}; table {table.state or 'not asked'}; steps done "
                        f"{table.done_steps or 'none'}; {table.lines_sent} lines sent, "
                        f"{table.motions_sent} movements; arm {r.where()}; move times "
                        f"{[(k, round(t, 3)) for k, t in table.timings]}; answers {r.answers}")
        finally:
            for sig, h in previous.items():
                signal.signal(sig, h)
        return code
    except KeyboardInterrupt:
        log("INFO", "stopped with Ctrl-C (or the Terminal window was closed) "
                    + ("before the table was opened; nothing was sent" if transport is None
                       else "; nothing more is sent")
                    + (f"; answers so far {pre_notes}" if pre_notes else ""))
        try:
            print("\nStopped." + ("" if transport is None else
                                  " Nothing more is sent to the table."))
        except OSError:
            pass
        return 1
    except Exception as exc:
        log("INFO", f"unexpected error {type(exc).__name__}")
        try:
            print(f"The program stopped because of an unexpected error ({type(exc).__name__}). "
                  "Nothing more is sent to the table.")
        except OSError:
            pass
        return 2
    finally:
        for sig, h in early.items():
            try:
                signal.signal(sig, h)
            except (ValueError, OSError):
                pass
        previous_int = None
        try:
            previous_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
        except (ValueError, OSError):
            pass
        if transport is not None:
            transport.close()
        lock.release()
        try:
            print(f"The log is in: {args.log or log_path.name}")
            if args.real:
                print("The log file is in the folder you started the program from. Please "
                      "read the log before you post it anywhere, and post the log, not a copy "
                      "of this Terminal window. It holds every line sent and received and your "
                      "answers, and no serial number.")
        except OSError:
            pass
        fh.close()
        if previous_int is not None:
            try:
                signal.signal(signal.SIGINT, previous_int)
            except (ValueError, OSError):
                pass


if __name__ == "__main__":
    sys.exit(main())
