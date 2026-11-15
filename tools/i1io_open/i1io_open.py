#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""ChromIQ i1iO test program 0.2.3: open an X-Rite i1iO 2 table that is already
started, the way i1Profiler opens it, send the arm to its resting place where it
already is (only from a place i1Profiler itself sent that line from), and close
the table again. It never measures. It asks you to feel gently whether the arm is
held three times: before it opens anything, and before and after it lets go of the
table's USB connection.

    python3 i1io_open.py              practice run on a SIMULATED table (nothing is opened)
    python3 i1io_open.py --sim cold   the same, for a table that has just been switched on
    python3 i1io_open.py --plan       print every line it could send, in order, and stop
    python3 i1io_open.py --dry-run    the same as --plan, with every byte in hex
    python3 i1io_open.py --real       the real table (asks you to type a sentence first)

With --real it sends i1Profiler's own opening lines. If the table has just been
switched on, it stops there (this version does not start a table; i1Profiler
does). On a started table it sends the line that sends the arm to its resting
place, where it already is, and closes the table as i1Profiler does. The one
movement is shown, with what you should see, before you type yes. Everything
sent and received goes into a log file without the table's serial number.
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

# the program's own folder, also when started with "python3 -I"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import i1io_open_table as tbl  # noqa: E402
from i1io_open_table import Doubt, Stopped  # noqa: E402

TITLE = (f"ChromIQ i1iO test program {tbl.TOOL_VERSION} (opens and closes a started table "
         "the way i1Profiler does; never measures)")
CONFIRM_SENTENCE = "i understand that this moves my table"
HANDS = "Keep your hands and everything else away from the arm while it moves."
PLUG = ("If anything looks or sounds wrong while the arm moves, switch the table off at its "
        "power switch or pull its power plug. That is always allowed. Pulling the USB cable "
        "is not a way to stop a movement: the table has its own power supply.")
PLUG_SHORT = "If it sounds or looks wrong, switch the table off at its power switch."
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
ASK_TOUCH = ("Please put one finger on the instrument holder and push it very gently towards "
             "the front of the table (the way the arm travels over the table), as if to move it "
             "by about a millimetre, then let go at once. Push sideways only, level with the "
             "table, and do not press down: the measuring opening rests on the white tile. Do "
             "not force it. Does the arm hold its "
             "place, or does it move freely? \"holds\": it resists your finger, or springs back "
             "when you let go. \"free\": it gives way with almost no effort, as when the table "
             "is switched off.")
TOUCH_CHOICES = ("holds", "free", "not sure", "skip")
TOUCH_BEFORE_INTRO = (
    "One check before the program opens anything (nothing has been sent to the table yet, and "
    "i1Profiler is not running). It answers the question we most want to know: is the arm "
    "held or free when i1Profiler has finished with the table? Touch it the same way as the "
    "program will ask you to at the end. If the arm moves a little, leave it where it is.")
WATCH_HEAD = ("If you can, watch the round measuring opening on the white tile while the arm "
              "moves: does it lift off the tile and come down again? You will be asked "
              "afterwards.")
ASK_HEAD = ("During the homing, did the measuring opening lift off the white tile and come down "
            "again?")
HEAD_CHOICES = ("lifted", "did not lift", "did not see")
ASK_LIGHTS = ("Which lights are on right now, on the table and on the i1Pro 2? (a few words, "
              "for example 'table power light green, i1Pro 2 dark'; press Enter to skip)")
ASK_MOVED = ("Since you quit i1Profiler, has anyone touched or moved the arm, apart from the "
             "touch just now?")
ASK_COLD_START = ("If you have seen it: when i1Profiler starts the table after it was switched "
                  "on, what do the arm and the measuring opening do (does the arm travel, how "
                  "far, does the opening lift)? Press Enter to skip.")
ASK_MINUTES = ("About how many minutes ago did you quit i1Profiler? (a rough number is fine; "
               "press Enter if you do not know)")
#: Where the one homing may start (shown before the go-ahead; the numbers are the box in
#: i1io_open_table.HOME_CLUSTER, and a test keeps the two together).
HOMING_PLACES = ("X 1101 to 1103, Y -1 to 48 (in tenths of a millimetre: the recorded "
                 "places X 1102, Y 0 to 47, and one tenth of a millimetre around them)")
AGAIN_TEXT = (
    "If you would like to try again: open i1Profiler, let it start the table as usual, quit "
    "it, and start this program again straight away. In the recordings, in the first three "
    "minutes after i1Profiler's own homing the arm read Y 22 to 37, inside that range. We "
    "cannot promise it, because how fast the arm creeps once i1Profiler has quit has never "
    "been measured.")
#: The optional wait before the second reading or the last touch.
LATER_WAIT_S = 600.0
LATER_REREAD = (
    "One more step, optional, if you have ten minutes: the program waits ten minutes with "
    "nothing connected to the table, then opens it once more with i1Profiler's own opening "
    "lines and asks where the arm is: 13 lines, every one of them only reading, nothing moves "
    "(i1Profiler re-opened your table exactly this way after closing it, in one of your "
    "recordings). That shows how far the arm's reading creeps in ten minutes after a homing, "
    "which is what stopped versions 0.2.0 and 0.2.1. After that reading the program sends "
    "nothing more, so the table is left without the closing lines, as after any stop. Then it "
    "asks you to touch the holder once more.")
LATER_TOUCH = (
    "One more step, optional, if you have ten minutes: you felt the arm held. The program waits "
    "ten minutes (nothing is sent, nothing is connected), then asks you to touch the holder "
    "once more. That shows whether the table lets the arm go after a while by itself.")
REREAD_NOT_CLOSED = (
    "After the second reading the table was left without i1Profiler's closing lines (they are "
    "recorded only right after a homing). That is the same as after any stop of this program: "
    "the next time, i1Profiler opens the table as usual.")
NOT_CLOSED = (
    "The table was not closed with i1Profiler's two closing lines: i1Profiler has only ever "
    "been recorded sending them right after its homing, so after a stop this program sends "
    "nothing at all. Ending without them is what also happens when i1Profiler is force-quit or "
    "its USB cable is pulled. Four earlier runs on your table ended this way: two of version "
    "0.1.0, one of 0.2.0 and one of 0.2.1. After each of the first three, the next opening "
    "worked normally; how the next opening after the 0.2.1 run went, we do not know yet.")
#: How long the program waits after letting go of the USB connection before the second touch.
RELEASE_WAIT_S = 10.0
NO_LIGHT = ("The instrument's own light will not come on, because this program never talks "
            "to the i1Pro 2 (when i1Profiler starts the table, that light does come on).")
LOOSE_ADVICE = (
    "If the arm is loose (it moves freely when you touch it gently), that is, as far as we "
    "know, the same harmless state as a table that is switched off. Please do not push it "
    "around. Leave the arm where it is, at its resting place. Then open i1Profiler once, let "
    "it start the table as usual, and quit it.")
RECOVERY = ("To bring the arm back to its resting place, start i1Profiler once and let it "
            "connect to the table: it sends the arm home by itself. Then quit i1Profiler. "
            "Please do not start this program again until i1Profiler has done that.")
RECOVERY_UNFINISHED = (
    "The table never reported that its last movement had finished, so it may still be "
    "moving, or it may start that movement later. Please keep your hands away from the arm, "
    "switch the table off, wait ten seconds and switch it on again before you open "
    "i1Profiler. ")
REST_PLACE = ("its resting place, where i1Profiler leaves it when you quit it: the instrument "
              "holder over the table's small white tile, with the round measuring opening "
              "resting on that tile")

COLD_TEXT = ("Your table has just been switched on and needs its start-up, which this "
             "version does not send. Please open i1Profiler, wait until it shows the table, "
             "quit i1Profiler, and run this program again. Nothing was moved.")

RISKS = (
    "Please read this before you go on.\n"
    "This is an unofficial test program written by ChromIQ. It is not from X-Rite, and X-Rite "
    "has nothing to do with it. Running it is entirely your choice. Its first version ran on "
    "your table twice (the first time the table refused it, the second time it worked). "
    "Version 0.2.0 opened the table, sent the arm home and stopped before the closing lines, "
    "because the position it read after the homing was outside a range we had guessed too "
    "narrowly. Version 0.2.1 opened the table and stopped before the homing, because the arm "
    "read Y 55 and 0.2.1 allowed only up to Y 50: our second wrong guess. Your table did "
    "nothing wrong either time. The arm's reading at rest creeps slowly away from Y 0 the "
    "longer it stands, so a range taken from the readings seen so far will always be beaten "
    "one day. This version therefore sends the homing only from the places i1Profiler itself "
    "was recorded sending it from (X 1102, Y 0 to 47, with 0.1 mm around them). If your arm "
    "reads anything else, it stops before the homing and moves nothing: a planned ending, not "
    "a fault. It reads no position after the homing, because i1Profiler never does right "
    "before the closing lines. Each line it sends is a line that i1Profiler itself sent to "
    "your table in your recordings, byte for byte, and every stretch of up to ten lines that "
    "follow each other here also follows in the same order in your recordings: the lines with "
    "which i1Profiler opens the table, its homing, and the two lines with which it closes the "
    "table. Only the homing makes the arm move, and the arm is already at its resting place, "
    "so it should barely move. If the table has just been switched on, the program stops after "
    "the opening and asks you to let i1Profiler start the table first. The program has no "
    "command for any other movement, never measures and never talks to the i1Pro 2. It sends "
    "no line of its own for the measuring head. Whether the table lifts and lowers the head by "
    "itself as part of the homing is not known; with the first program the arm moved very "
    "little and nothing unusual was seen.\n"
    "It also asks for the table's memory block, as i1Profiler does when it opens the table. "
    "That block holds the table's serial number. The program checks only its length and its "
    "first eight bytes, and never writes it down or shows it.\n"
    "What could still go wrong, in plain words: the table could do something the recordings "
    "never showed. That is why the table should be empty, why the movement waits for your yes, "
    "why you should keep your hands and everything else away from the arm, and why you should "
    "keep the power switch or plug within reach.\n"
    "With version 0.2.1 you found the arm free at rest, although the table had answered the "
    "question we used to read as \"the motors hold the arm\" with 00. So that answer does not "
    "mean what we thought. This version asks you to feel gently whether the arm is held three "
    "times: before it opens anything (right after you quit i1Profiler is best), and before and "
    "after it lets go of the table's USB connection. The first one tells us whether a free arm "
    "is simply how i1Profiler leaves the table.\n"
    "Nothing leaves your computer unless you send the log file yourself.")


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

    def __init__(self, log, script=None, interrupt_at=None):
        super().__init__(log)
        self.script = dict(script or {})
        self.asked = 0
        self.interrupt_at = interrupt_at

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


OPENING = ("identity", "identity", "k2", "memory_a", "memory_b", "a0")
FOLLOW = ("status", "arm_mode", "arm_mode", "arm_mode", "arm_mode")
HOMING = ("status", "position", "home", "status")
CLOSING = ("status", "f0", "f3")
MEANING = {
    "identity": "identity (must be 005D010702)",
    "k2": "k2, a fixed answer (must be 0B600000000013)",
    "memory_a": "the table's memory, part 1 (256 bytes; not written down)",
    "memory_b": "the table's memory, part 2 (104 bytes; not written down)",
    "a0": "a0: we believe 111800 = just switched on (cold: stop here), 130000 = started",
    "status": "status (must be accepted)",
    "arm_mode": "f4, asked four times at every opening (must be 00; 01 was only seen in the "
                "hand-alignment mode; it does not tell whether the motors hold the arm)",
    "position": "where the arm is",
    "home": "i1: GO TO THE RESTING PLACE. MOVES very little (it is already there)",
    "f0": "f0, first closing line (must answer 00)",
    "f3": "f3, second closing line (must answer 00)",
}


def plan_text(hex_bytes: bool = False) -> str:
    def row(key, note=""):
        b = tbl.WIRE[key]
        extra = f"   bytes {b.hex(' ')}" if hex_bytes else ""
        return f"  {_bare(key):20} {MEANING[key]}{note}{extra}"
    out = [f"Every line this program can send, in order. Nothing else can be sent: "
           f"{len(tbl.WIRE)} different lines, at most {tbl.MAX_LINES} lines and "
           f"{tbl.MAX_MOTIONS} movements in one run. After any stop or any doubt, nothing "
           "more is sent at all.", "",
           "Before anything: the USB set-up i1Profiler uses (FTDI reset, purge, purge, "
           "57600 baud, 8 data bits, no parity, 1 stop bit), then 1 s of listening.",
           "Before that, nothing is sent while you answer the start questions and touch the "
           "arm once.", "",
           "1. Opening (only reads; nothing moves):"]
    out += [row(k) for k in OPENING]
    out += ["", "2. If a0 answered 111800 (just switched on): STOP here, nothing more is sent;",
            "   you are asked to let i1Profiler start the table and to run the program again.",
            "   Any answer other than 111800 or 130000: stop, nothing more is sent.", "",
            "3. Follow-up on a started table (only reads):"]
    out += [row(k) for k in FOLLOW]
    out += ["  checks: every arm answer 00; otherwise stop.", "",
            "4. Homing, only after you type yes: one homing, as i1Profiler sent it right "
            "before it closed the table (status, position, homing, status):"]
    out += [row(k) for k in HOMING]
    out += ["  checks: right before the homing the arm must be where i1Profiler itself sent "
            "the homing from (X 1101..1103, Y -1..48); the homing answered within 0.6 s (every "
            "recorded one took at most 0.35 s); otherwise stop, without the closing lines and "
            "without any movement. No position is read after the homing (i1Profiler never "
            "follows a position question with the closing lines).", "",
            "5. Closing, after you have looked at the arm:"]
    out += [row(k) for k in CLOSING]
    out += ["", "6. Nothing more is sent. You are asked to feel gently whether the arm is held, "
            "once before and once after the program lets go of the USB connection. After any "
            "stop, the closing lines are NOT sent (they are recorded only after the homing)."]
    return "\n".join(out)


# ---- the run ---------------------------------------------------------------------------

class Run:
    def __init__(self, table: tbl.Table, ui: Console, simulated: bool,
                 other_program=None, answers=None, reopen=None):
        self.d, self.ui, self.simulated = table, ui, simulated
        #: opens a new connection for the optional second reading (None: not offered)
        self.reopen = reopen
        #: the read-only table of the second reading, once made
        self.second: "tbl.Table | None" = None
        self.other_program = other_program or (lambda: False)
        self.answers: "list[tuple[str, str]]" = list(answers or [])
        #: False when the person said the arm is not at its resting place
        self.seen_at_rest: "bool | None" = None
        #: True after Ctrl-C (anywhere) or a typed "stop": from then on nothing is sent AND
        #: nothing more is asked; only the closing text is shown (safety review S2)
        self.stopped_by_person = False
        #: True once a touch question has been put to the person
        self.touch_asked = False

    def note(self, question: str, answer: str) -> None:
        self.answers.append((question, answer))

    def look(self, question: str, choices, key: str) -> str:
        ans = self.ui.ask(question, choices)
        self.note(key, ans)
        if ans == "stop":
            self.stopped_by_person = True
            raise Stopped(STOPPED)
        return ans

    def _go_ahead(self, what: str) -> None:
        self.ui.say("")
        self.ui.say(what)
        self.ui.say(PLUG)
        self.ui.say(STOP_PROMISE)
        go = self.ui.ask(f"{HANDS} Send it now?", ("yes", "no", "stop"))
        self.note("go ahead", go)
        if go == "stop":
            self.stopped_by_person = True
        if go != "yes":
            raise Stopped("You chose not to go on. Nothing more is sent to the table.")
        if self.other_program():
            self.d.close_for_sending("i1Profiler was started during the run")
            raise Stopped("i1Profiler has started, so the program stops here: two programs "
                          "must never talk to the table at the same time. Nothing more is "
                          "sent to the table.")

    def go(self) -> int:
        """The whole run. Returns 0 (complete), 1 (stopped by you) or 2 (a doubt)."""
        try:
            self.ui.say("Talking to the table. Nothing moves yet.")
            state = self.d.opening()
            if state == "cold":
                # listen once more (sends nothing): a late line is reported like any surprise
                self.d.busy += 1
                try:
                    self.d._quiet_check()
                finally:
                    self.d.busy -= 1
                self.ui.say("The table answered as expected, and we believe it says it has just "
                            "been switched on (a0 = 111800).")
                raise Stopped(COLD_TEXT)
            self.d.follow_up()
            self.ui.say("The table answered as expected: it is started (a0 = 130000), and f4 "
                        "answered 00 as at every recorded opening. (Earlier versions said this "
                        "meant the motors hold the arm. It does not: on your table f4 said 00 "
                        "while you found the arm free.)")
            self._go_ahead(
                f"Next the program sends the arm to its resting place once, exactly as "
                f"i1Profiler did right before it closed the table: it asks where the arm is and "
                f"sends {_bare('home')} (i1, go to the resting place) if the arm is there. The "
                "arm is already at its resting place, so it should move very little or not at "
                "all; you may hear the motors for a moment. With version 0.2.0 on your table "
                "the homing took about a third of a second. " + NO_LIGHT + " Right before the "
                "homing the program reads where the arm is, and it sends the homing only if "
                f"the arm is where i1Profiler itself sent it from: {HOMING_PLACES}. Otherwise "
                "it stops there and moves nothing. On your table the arm has read Y 46 once and "
                "Y 55 once, so this check may well stop the run; that is one of the planned "
                "endings. " + WATCH_HEAD)
            self.d.home()
            self.ui.say(f"The table reports that the homing has finished (after "
                        f"{self.d.homing_times[-1]:.2f} s).")
            seen = self.look(f"Please look at the table now. Is the arm at {REST_PLACE}?",
                             ("yes", "no", "not sure", "stop"), "arm at its resting place")
            self.seen_at_rest = seen == "yes"
            if seen != "yes":
                self.note("arm instead", self.ui.text(
                    "What do you see instead? (type a few words, then Enter)"))
                raise Stopped("Thank you, that is exactly what we need to know. The program "
                              "stops here without closing the table; nothing more is sent.")
            self.ui.say("Now the program closes the table the way i1Profiler does (two lines; "
                        "nothing moves).")
            self.d.closing()
            # listen once more (sends nothing): a late line is reported like any surprise
            self.d.busy += 1
            try:
                self.d._quiet_check()
            finally:
                self.d.busy -= 1
            self.ui.say("")
            self.ui.say("The table was opened and closed the way i1Profiler does it, and the arm "
                        "is at its resting place. Nothing more is sent to the table.")
            return 0
        except Stopped as exc:
            if self.d.stop_requested:          # Ctrl-C noticed during an exchange
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
        except Exception as exc:      # a bug or a library surprise: say so, never a traceback
            self.d.close_for_sending(f"an unexpected error ({type(exc).__name__})")
            self.ui.say(f"The program stopped because of an unexpected error "
                        f"({type(exc).__name__}). Nothing more is sent to the table.")
            return 2
        finally:
            self.d.close_for_sending("the run is over")

    def ending(self, code: int) -> None:
        """Say where the arm is and what to do. Sends nothing."""
        try:
            d = self.d
            if d.outside_at is not None:
                self.ui.say(AGAIN_TEXT)
            if code != 0 and d.state == "warm" and not d.closed_table:
                self.ui.say(NOT_CLOSED)
            if d.motions_sent == 0:
                self.ui.say("Nothing was moved.")
            elif code == 0:
                pass
            elif d.homed and not d.motion_unconfirmed:
                self.ui.say("The table reported that the homing had finished, so the arm "
                            "should be at its resting place (its position is not read after the "
                            "homing). The table was not closed; i1Profiler opens it "
                            "normally the next time.")
            elif (not d.arrival_unknown and d.position_now is not None
                  and tbl.HOME_CLUSTER.contains(d.position_now)):
                self.ui.say("The arm was last reported at its resting place.")
            else:
                if d.arrival_unknown and d.heading_to:
                    where = (" Its last movement was towards its resting place, and where it "
                             "stopped has not been read.")
                elif d.position_now is not None:
                    where = (f" It was last reported at table position X {d.position_now[0]}, "
                             f"Y {d.position_now[1]}.")
                else:
                    where = ""
                self.ui.say("The arm stays where it is now; the program does not move it "
                            "again." + where + " "
                            + (RECOVERY_UNFINISHED if d.motion_unconfirmed else "")
                            + RECOVERY)
        except BaseException:
            pass

    def may_touch(self) -> bool:
        """The touch questions are asked only when the arm is known to be still and at
        rest (safety review S2): something was sent, no movement whose end the table never
        reported, no stop by the person (Ctrl-C or "stop"), and either nothing moved or
        the person's last word about the arm was "yes, at its resting place"."""
        return (self.d.lines_sent > 0 and not self.d.motion_unconfirmed
                and not self.stopped_by_person
                and (self.d.motions_sent == 0 or self.seen_at_rest is True))

    def touch(self, when: str) -> bool:
        """One gentle touch, as the person reports it. Sends nothing. Returns False when
        the person stopped (Ctrl-C): then nothing more is asked."""
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

    def after_the_run(self, transport, real: bool) -> None:
        """Everything after go(): the touch question while the USB connection is still
        held, the release, ten seconds (real table only), the second touch, the report
        questions, the closing text. Sends nothing (go() has closed the table for
        sending). After a stop by the person nothing more is ASKED either."""
        log = self.ui.log
        touch = self.may_touch()
        if touch:
            self.ui.say("")
            self.ui.say("The program still holds the table's USB connection, and it sends "
                        "nothing more.")
            touch = self.touch("while the program still held the USB connection")
        transport.close()
        log("INFO", "the program has let go of the table's USB connection (nothing is "
                    "sent when it does)")
        if touch:
            self.ui.say("The program has now let go of the table's USB connection, as it does "
                        "when it ends. It waits ten seconds; then please touch the holder "
                        "gently once more, the same way.")
            if real:
                try:
                    time.sleep(RELEASE_WAIT_S)
                except KeyboardInterrupt:      # a stop: no second touch, no more questions
                    self.stopped_by_person = True
                    self.note("arm held? (about ten seconds after the program let go of the "
                              "USB connection)", "stopped with Ctrl-C during the wait")
                    touch = False
            if touch:
                touch = self.touch("about ten seconds after the program let go of the USB "
                                   "connection")
        if touch and not self.stopped_by_person:
            self.later(real)
        if self.stopped_by_person:
            log("INFO", "stopped by you: no more questions")
        else:
            self.questions()
        if self.touch_asked:
            self.advice()

    def complete(self) -> bool:
        """The run went all the way: one homing, the person saw the arm at rest, closed."""
        return (self.d.closed_table and self.d.motions_sent == 1 and self.seen_at_rest is True
                and not self.d.motion_unconfirmed)

    def later(self, real: bool) -> None:
        """Optional, ten minutes later (0.2.3). After a complete run: the second reading
        (i1Profiler's re-opening after its close up to its position read, 13 reading lines,
        nothing moves) and one more touch. After an incomplete run, only if the last touch
        said "holds": one more touch (nothing is sent). Nothing at all without the person's
        yes; a Ctrl-C during the wait ends it with nothing sent."""
        last = self.answers[-1][1] if self.answers else ""
        reread = self.complete() and self.reopen is not None
        if not reread and last != "holds":
            return
        self.ui.say("")
        self.ui.say(LATER_REREAD if reread else LATER_TOUCH)
        try:
            ans = self.ui.ask("Would you like to do this?", ("no", "yes"))
        except KeyboardInterrupt:
            self.stopped_by_person = True
            self.note("ten more minutes", "stopped with Ctrl-C")
            return
        self.note("ten more minutes", ans)
        if ans != "yes":
            return
        self.ui.say(f"Waiting {LATER_WAIT_S // 60:.0f} minutes. Nothing is connected to the "
                    "table meanwhile. Ctrl-C ends the wait; then nothing more is sent.")
        started = time.monotonic()
        if real:
            try:
                left = LATER_WAIT_S
                while left > 0:
                    step = min(60.0, left)
                    time.sleep(step)
                    left -= step
                    if left > 0:
                        print(f"  {left / 60:.0f} minutes to go", flush=True)
            except KeyboardInterrupt:
                self.stopped_by_person = True
                self.note("ten more minutes", "stopped with Ctrl-C during the wait")
                return
        self.ui.log("INFO", f"waited {time.monotonic() - started:.0f} s"
                            + ("" if real else " (practice run: no real wait)"))
        if reread:
            self.second_reading()
        if not self.stopped_by_person:
            self.touch("about ten minutes after the run" + (", after the second reading"
                                                             if reread else ""))

    def second_reading(self) -> None:
        """Re-open the table and read, as i1Profiler re-opened it after its own close (R2
        378.128-378.617). A read-only table: it cannot send i1, f0 or f3, nor more than 13
        lines, and the shared budget keeps the whole run within its caps."""
        log = self.ui.log
        if self.other_program():
            self.ui.say("i1Profiler is running now, so the second reading is not made. "
                        "Nothing was sent.")
            return
        try:
            t2 = self.reopen()
        except (tbl.NotAvailable, tbl.TransportError) as exc:
            self.ui.say(f"The table could not be opened for the second reading, so it is not "
                        f"made. Nothing was sent. ({exc})")
            return
        table2 = tbl.Table(t2, log=log, budget=self.d.budget, read_only=True)
        previous = install_signals(table2)
        self.second = table2
        try:
            self.ui.say("Second reading: opening the table and asking where the arm is. "
                        "Nothing moves.")
            pos = table2.reread()
            self.ui.say(f"The arm reports X {pos[0]}, Y {pos[1]}. Thank you. Nothing more is "
                        "sent to the table.")
            if table2.stop_requested:            # Ctrl-C during the last line: honoured too
                self.stopped_by_person = True
        except (Doubt, Stopped) as exc:
            self.ui.say(getattr(exc, "plain", None) or f"The second reading stopped: {exc}. "
                        "Nothing more is sent to the table.")
            if isinstance(exc, Stopped):
                self.stopped_by_person = True
        except KeyboardInterrupt:
            self.stopped_by_person = True
            table2.close_for_sending("stopped with Ctrl-C")
            self.ui.say(STOPPED)
        except Exception as exc:
            table2.close_for_sending(f"an unexpected error ({type(exc).__name__})")
            self.ui.say(f"The second reading stopped because of an unexpected error "
                        f"({type(exc).__name__}). Nothing more is sent to the table.")
        finally:
            table2.close_for_sending("the second reading is over")
            for sig, h in previous.items():
                signal.signal(sig, h)
            t2.close()
            log("INFO", "the program has let go of the table's USB connection again "
                        "(nothing is sent when it does)")
        if table2.lines_sent:
            self.ui.say(REREAD_NOT_CLOSED)

    def advice(self) -> None:
        try:
            self.ui.say("")
            self.ui.say(LOOSE_ADVICE)
            self.ui.say("If you have a moment, please touch the holder gently once more in "
                        "about ten minutes and add one line to the log about what you felt.")
        except BaseException:
            pass

    def questions(self) -> None:
        if self.d.lines_sent == 0:
            return
        try:
            self.ui.say("")
            self.ui.say("A few questions for the report (just press Enter to skip one).")
            if self.d.motions_sent:
                self.note("measuring opening during the homing",
                          self.ui.ask(ASK_HEAD, HEAD_CHOICES))
            for q in ("Did you hear anything unusual (grinding, knocking, clicking, a long "
                      "buzz)? If yes, when?",
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
        self.path = Path(tempfile.gettempdir()) / "chromiq-i1io-open.lock"
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
    """Before anything is opened or sent: one gentle touch, and how long ago i1Profiler was
    quit (the observation that settles whether a free arm at rest is the table's normal state
    after i1Profiler). Sends nothing; the table is not even opened yet."""
    ui.say("")
    ui.say(TOUCH_BEFORE_INTRO)
    notes.append(("arm held? (before the program opened anything)",
                  ui.ask(ASK_TOUCH, TOUCH_CHOICES)))
    notes.append(("minutes since i1Profiler was quit", ui.text(ASK_MINUTES)))
    notes.append(("arm touched or moved since i1Profiler was quit",
                  ui.ask(ASK_MOVED, ("no", "yes", "not sure"))))
    notes.append(("lights before opening", ui.text(ASK_LIGHTS)))


PRE_QUESTIONS = (
    "Is the table's power switch or power plug within reach of your hand, so you can switch "
    "it off at once if needed?",
    "Is the i1Pro 2 seated in the arm's holder and connected, exactly as when you use it "
    "with i1Profiler?",
    "Is the table completely empty: no paper, no chart, nothing lying on it?",
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
                    help="print every line the program can send, and stop")
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
    log_path = Path(f"i1io-open-{stamp}{suffix}.txt")
    try:
        if args.log:
            log_path = Path(args.log)
            fh = log_path.open("w", encoding="utf-8")
        else:
            for n in range(1, 1000):
                log_path = Path(f"i1io-open-{stamp}{'' if n == 1 else f'-{n}'}{suffix}.txt")
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
        if kind in ("ASK", "ANSWER", "ENTER"):          # when the person answered (0.2.3)
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
        + f"; at most {tbl.MAX_LINES} lines and {tbl.MAX_MOTIONS} movements")
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
    for name in ("SIGTERM", "SIGHUP"):          # a closed window: logged, not silent
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
                    ui.say("Then this program does not start. If the arm is not at its "
                           "resting place, or may have been pushed while the table was off, "
                           "please let i1Profiler bring it home first (open i1Profiler, wait "
                           "until it shows the table, quit it). Nothing was sent.")
                    return 1
            if i1profiler_running():           # the touch text says it is not running
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
            from i1io_open_sim import SimTable, SimTransport
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
            if args.real:
                def reopen():
                    log("INFO", "macOS lists for the table before the second opening: "
                                + ("; ".join(tbl.usb_holders()) or "nobody"))
                    t = tbl.open_table()
                    log("INFO", "second opening: " + tbl.usb_summary(t))
                    return t
            else:
                def reopen():
                    return SimTransport(sim)
            r = Run(table, ui, simulated=not args.real,
                    other_program=i1profiler_running if args.real else None,
                    answers=pre_notes, reopen=reopen)
            code = r.go()
            r.ending(code)
            r.after_the_run(transport, real=args.real)
            second = ""
            if r.second is not None:
                second = (f"; second reading: {r.second.lines_sent} lines, arm "
                          f"{r.second.position_now}, table left without the closing lines")
            log("INFO", f"result {code}; table {table.state or 'not asked'}; "
                        f"{table.lines_sent} lines sent, {table.motions_sent} movements; "
                        f"closed {'yes' if table.closed_table else 'no'}{second}; "
                        f"in all {table.budget.lines} lines, {table.budget.motions} movements; "
                        f"answers {r.answers}")
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
    except Exception as exc:       # never a traceback (it would show folder names)
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
                print("The log file is in the folder you started the program from. "
                  "Please read the log before you post it anywhere, and post the log, "
                      "not a copy of this Terminal window. It holds every line sent and "
                      "received and your answers, and no serial number.")
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
