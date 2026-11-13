#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""ChromIQ i1iO test program: a first, very small test of talking to an
X-Rite i1iO 2 table. It never measures.

    python3 i1io_trace.py            practice run on a SIMULATED table (nothing is opened)
    python3 i1io_trace.py --plan     print every line it could send, in order, and stop
    python3 i1io_trace.py --real     the real table (asks you to type a sentence first)

With --real it reads the table's identity and position, sends the arm to its
resting place, moves it twice in a straight line towards the front of the
table (about 25 mm, then about 95 mm more) and sends it back. Before every
movement it shows the exact line it will send and what you should see, and
waits until you type yes. Everything sent and received goes into a log file.
See README.md.
"""
from __future__ import annotations

import argparse
import datetime
import os
import platform
import signal
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

# the program's own folder, also when started with "python3 -I"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import i1io_table as tbl  # noqa: E402
from i1io_table import Doubt, Stopped  # noqa: E402

TITLE = f"ChromIQ i1iO test program {tbl.TOOL_VERSION} (moves the arm a little, never measures)"
CONFIRM_SENTENCE = "i understand that this moves my table"
HANDS = "Keep your hands and everything else away from the arm while it moves."
PLUG = ("If anything looks or sounds wrong while the arm moves, switch the table off at its "
        "power switch or pull its power plug: that is always allowed and stops the motors. "
        "Pulling the USB cable alone does not stop a movement that has already started.")
RECOVERY = ("To bring the arm back to its resting place, start i1Profiler once and let it "
            "connect to the table: it sends the arm home by itself. Then quit i1Profiler.")
RECOVERY_NO_ANSWER = ("Because the table did not answer as expected, please switch the table "
                      "off, wait ten seconds and switch it on again before you open "
                      "i1Profiler, so that nothing the table may still be waiting to do is "
                      "left over. ")

RISKS = (
    "Please read this before you go on.\n"
    "This is a test program written by ChromIQ, not by X-Rite, and it has never run on a "
    "real table before: you would be the first. It sends only seven different lines to "
    "the table, and each of them is a line that i1Profiler itself sent to your table in "
    "the recordings you made: three that only read (identity, position, whether the "
    "motors hold the arm), one status query, the command that sends the arm to its "
    "resting place, and two moves. It never sends anything that lowers the measuring "
    "head, never measures, and never reads or writes the table's memory.\n"
    "What could still go wrong, in plain words: the arm could bump into something left "
    "on the table, or a hand; the table could do something the recordings never showed. "
    "In the worst case the mechanism could be strained. That is why the table must be "
    "empty, why every movement waits for you, and why you should keep the power switch "
    "or plug within reach.\n"
    "Nothing leaves your computer unless you send the log file yourself.")


# ---- talking to the tester -------------------------------------------------------------

def _flush_typed_ahead() -> None:
    """Keys typed before a question was shown never answer it."""
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
        for para in text.split("\n"):
            print(textwrap.fill(para, 78) if para else "")
        self.log("SAY", text.replace("\n", " / "))

    def ask(self, question: str, choices=("yes", "no")) -> str:
        """One of *choices*, typed out in full; an empty Enter or a single
        letter never answers. The end of input counts as the last choice
        (no / stop / not sure)."""
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
        """Free text; an empty Enter means 'nothing to add'."""
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
    """Answers for the practice run with --auto (and the tests): yes to every
    question, the first choice otherwise, nothing as free text. *script* may
    override answers by a word in the question."""

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


# ---- the run ---------------------------------------------------------------------------

def describe(step: tbl.Motion) -> str:
    line = tbl.WIRE[step.key].decode("ascii").rstrip("\r")
    if step.key == "home":
        meaning = "i1: go to the resting place"
    else:
        x, y, v = (int(line[3:7], 16), int(line[7:11], 16), int(line[11:15], 16))
        meaning = f"m0: move to table position X {x}, Y {y} at speed {v}"
    return (f"Step {step.number} of {len(tbl.PLAN)}. The program will send the line "
            f"{line} ({meaning}).\n"
            f"What you should see: {step.what} In the recordings this took about "
            f"{step.seconds}.\n"
            f"Where i1Profiler did the same on your table: {step.recorded}.")


def plan_text() -> str:
    """Every line the program can send, in the order it sends them."""
    out = ["Every line this program can send, in order (nothing else can be sent):", "",
           "Opening (only reads, nothing moves):"]
    for key in ("status", "identity", "identity", "arm_mode", "position"):
        out.append(f"  {tbl.WIRE[key].decode().rstrip(chr(13)):20} {key}")
    out.append("  checks: identity 005D010702 both times, motors holding the arm (00), "
               "arm at its resting place (X 1097..1107, Y -5..50)")
    for step in tbl.PLAN:
        out += ["", f"Step {step.number} (only after you type yes):",
                f"  {tbl.WIRE['arm_mode'].decode().rstrip(chr(13)):20} arm_mode, must be 00",
                f"  {tbl.WIRE['position'].decode().rstrip(chr(13)):20} position, must be in "
                f"X {step.start.xmin}..{step.start.xmax}, Y {step.start.ymin}..{step.start.ymax}",
                f"  {tbl.WIRE[step.key].decode().rstrip(chr(13)):20} {step.key}: {step.what}",
                f"  {tbl.WIRE['position'].decode().rstrip(chr(13)):20} position, must be in "
                f"X {step.end.xmin}..{step.end.xmax}, Y {step.end.ymin}..{step.end.ymax}",
                f"  {tbl.WIRE['arm_mode'].decode().rstrip(chr(13)):20} arm_mode, must still be 00"]
    out += ["", f"At most {tbl.MAX_LINES} lines and {tbl.MAX_MOTIONS} movements per run. "
            "After any stop or any doubt, nothing more is sent at all."]
    return "\n".join(out)


class Run:
    def __init__(self, table: tbl.Table, ui: Console, simulated: bool, sim=None):
        self.d, self.ui, self.simulated, self.sim = table, ui, simulated, sim
        self.done_steps = 0
        self.answers: "list[tuple[str, str]]" = []

    def note(self, question: str, answer: str) -> None:
        self.answers.append((question, answer))

    def go(self) -> int:
        """The whole run. Returns 0 (complete), 1 (stopped by you) or 2 (a doubt)."""
        try:
            self.ui.say("Talking to the table. Nothing moves yet.")
            pos = self.d.open_checks()
            self.ui.say(f"The table answered as expected. It is the table model this program "
                        f"was made from, its motors hold the arm, and the arm reports table "
                        f"position X {pos[0]}, Y {pos[1]}, which is its resting place.")
            ans = self.ui.ask("Please look at the table now. Is the arm at its resting place "
                              "at the back of the table, and is the table completely empty "
                              "(no paper, nothing lying on it)?")
            self.note("arm at rest and table empty", ans)
            if ans != "yes":
                raise Stopped("Then the program does not move anything. Please clear the "
                              "table, or if the arm is not at its resting place, use "
                              "i1Profiler once to bring it there, then start again.")
            for step in tbl.PLAN:
                self.ui.say("")
                self.ui.say(describe(step))
                if step.number == 1:
                    self.ui.say(PLUG)
                go = self.ui.ask(f"{HANDS} Send step {step.number} now?", ("yes", "stop"))
                if go != "yes":
                    raise Stopped(f"You stopped before step {step.number}.")
                got = self.d.motion(step)
                self.done_steps = step.number
                self.ui.say(f"The table reports that it has finished step {step.number}; "
                            f"the arm reports table position X {got[0]}, Y {got[1]}.")
                seen = self.ui.ask(f"Did the arm do what was described for step "
                                   f"{step.number}?", ("yes", "no", "not sure"))
                self.note(f"step {step.number} as described", seen)
                if seen != "yes":
                    detail = self.ui.text("What did you see instead? (type a few words, "
                                          "then Enter)")
                    self.note(f"step {step.number} instead", detail)
                    raise Stopped("Thank you, that is exactly what we need to know. The "
                                  "program stops here.")
                if step.key == "out":
                    ring = self.ui.ask("Now look at the bottom of the instrument holder, "
                                       "where the round measuring opening is. Does it touch "
                                       "the table, or is there a gap between it and the table?",
                                       ("gap", "touches", "not sure"))
                    self.note("measuring opening at step 2", ring)
                    if ring != "gap":
                        raise Stopped("Thank you, that is important to know. Because the "
                                      "head may rest on the table, the program does not "
                                      "move the arm any further.")
            self.ui.say("")
            self.ui.say("All four steps are done, and the arm is back at its resting place.")
            return 0
        except Stopped as exc:
            self.ui.say(str(exc))
            return 1
        except KeyboardInterrupt:
            self.d.close_for_sending("stopped with Ctrl-C")
            self.ui.say("Stopped with Ctrl-C.")
            return 1
        except Doubt as exc:
            self.ui.say(f"The program stopped because {exc}.")
            return 2
        except tbl.ForbiddenLine as exc:      # a bug: nothing was written
            self.d.close_for_sending("an internal check refused a line")
            self.ui.say(f"The program stopped because of an internal error ({exc}).")
            return 2
        finally:
            # whatever happened: from here on nothing is sent to the table
            self.d.close_for_sending("the run is over")

    def ending(self, code: int) -> None:
        """Say where the arm is. Sends nothing (the session is closed)."""
        pos = self.d.position_now
        if self.d.motions_sent == 0:
            self.ui.say("Nothing was moved.")
        elif code == 0:
            pass
        elif pos is not None and tbl.HOME_CLUSTER.contains(pos) and not self.d.busy:
            self.ui.say("The arm was last reported at its resting place.")
        else:
            where = f" (last reported at table position X {pos[0]}, Y {pos[1]})" if pos else ""
            self.ui.say(f"The arm stays where it is now{where}; the program does not move it "
                        "again. If it was moving, the table finishes that movement by itself. "
                        + (RECOVERY_NO_ANSWER if code == 2 else "") + RECOVERY)

    def questions(self) -> None:
        if self.d.lines_sent == 0:
            return
        self.ui.say("")
        self.ui.say("A few questions for the report (just press Enter to skip one).")
        try:
            for q in ("Did you hear anything unusual (grinding, knocking, clicking, a long "
                      "buzz)? If yes, during which step?",
                      "Did anything else surprise you, or is there anything you want to add?"):
                self.note(q, self.ui.text(q))
        except KeyboardInterrupt:
            self.ui.say("Questions skipped.")


# ---- the environment -------------------------------------------------------------------

def i1profiler_running() -> bool:
    """i1Profiler talking to the table at the same time would be two masters."""
    try:
        out = subprocess.run(["pgrep", "-x", "-i", "i1Profiler"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(out.stdout.strip())


class Lock:
    """Only one copy of this program at a time (per user)."""

    def __init__(self):
        self.path = Path(tempfile.gettempdir()) / "chromiq-i1io-trace.lock"
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
            try:
                self.path.unlink()
            except OSError:
                pass
            self.fh.close()
            self.fh = None


def install_signals(table: tbl.Table) -> dict:
    """Ctrl-C (and the other stop signals) never cut an exchange or a step in
    half: while one runs they only ask for a stop after it; at a question
    they stop the run at once. Returns the previous handlers."""
    old = {}

    def handler(signum, frame):
        if table.busy:
            first = not table.stop_requested
            table.request_stop()
            if first:
                try:      # a closed terminal must not raise in the middle of a step
                    print("\nThe program stops after the current step; if the arm is "
                          "moving, the table finishes that movement first.", flush=True)
                except Exception:
                    pass
            return
        raise KeyboardInterrupt
    for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT"):
        if hasattr(signal, name):
            sig = getattr(signal, name)
            old[sig] = signal.signal(sig, handler)
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


# ---- main ------------------------------------------------------------------------------

def main(argv=None, sim_table=None, console=None) -> int:
    ap = argparse.ArgumentParser(description=TITLE)
    ap.add_argument("--real", action="store_true",
                    help="use the REAL table (without it: a simulated table)")
    ap.add_argument("--plan", action="store_true",
                    help="print every line the program can send, and stop")
    ap.add_argument("--auto", action="store_true",
                    help="simulated run only: answer every question automatically")
    ap.add_argument("--log", help="where to write the log file (default: this folder)")
    ap.add_argument("--version", action="version", version=TITLE)
    args = ap.parse_args(argv)

    if args.plan:
        print(plan_text())
        return 0
    if args.real and args.auto:
        ap.error("--auto is only for the simulated table")
    if sys.version_info < (3, 8):
        print("This program needs Python 3.8 or newer.")
        return 2

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = Path(args.log or f"i1io-trace-{stamp}{'' if args.real else '-simulated'}.txt")
    fh = log_path.open("w", encoding="utf-8")

    def log(kind, text):
        fh.write(f"{kind:6} {text}\n")
        fh.flush()
        if not args.real and kind in ("SEND", "RECV"):
            print(f"    {kind} {text.split(None, 1)[-1]}")

    log("INFO", f"{TITLE}; {'REAL table' if args.real else 'SIMULATED table'}; "
                f"{datetime.datetime.now().isoformat(timespec='seconds')}")
    log("INFO", environment(args.real))
    log("INFO", "allowed lines: " + " ".join(v.decode().rstrip("\r") for v in tbl.WIRE.values())
        + f"; at most {tbl.MAX_LINES} lines and {tbl.MAX_MOTIONS} movements")
    log("INFO", "the table's serial number is never read by this program")
    ui = console or Console(log)
    if console is not None:
        console.log = log
    lock, transport, sim = Lock(), None, None
    try:
        ui.say(TITLE + ".")
        if args.real:
            if not sys.stdin.isatty():
                ui.say("With --real, every answer must be typed by a person at the keyboard, "
                       "so the program does not run with piped or redirected input.")
                return 2
            if sys.platform != "darwin":
                ui.say("The real table can only be used from a Mac with this program "
                       "(it was never tried on Windows or Linux). Nothing was sent.")
                return 2
            ui.say(RISKS)
            if i1profiler_running():
                ui.say("i1Profiler is running. Please quit it first: two programs must never "
                       "talk to the table at the same time. Nothing was sent.")
                return 2
            if not lock.acquire():
                ui.say("Another copy of this program is running. Please let it finish first. "
                       "Nothing was sent.")
                return 2
            for q in ("Is the table's power switch or power plug within reach of your hand, "
                      "so you can switch it off at once if needed?",
                      "Is the i1Pro 2 seated in the arm's holder and connected, exactly as "
                      "when you use it with i1Profiler?",
                      "Is the table completely empty: no paper, no chart, nothing lying on it?"):
                if ui.ask(q) != "yes":
                    ui.say("Please make it so, then start the program again. Nothing was sent.")
                    return 1
            if not ui.sentence("To go on with the REAL table, type this sentence and press "
                               "Enter:\n    I understand that this moves my table",
                               CONFIRM_SENTENCE):
                ui.say("That was not the sentence, so nothing was sent to the table.")
                return 1
            try:
                transport = tbl.open_table()
            except (tbl.NotAvailable, tbl.TransportError) as exc:
                ui.say(str(exc))
                return 2
        else:
            from i1io_sim import SimTable, SimTransport
            sim = sim_table or SimTable()
            transport = SimTransport(sim)
            if console is None and (args.auto or not sys.stdin.isatty()):
                ui = AutoConsole(log)
            ui.say("SIMULATED TABLE: nothing is opened and nothing is sent to any device. "
                   "Every line the real run would send and receive is printed, so you can "
                   "see what it will do. Add --real for the real table.")
        log("INFO", tbl.usb_summary(transport))
        table = tbl.Table(transport, log=log)
        previous = install_signals(table)
        try:
            r = Run(table, ui, simulated=not args.real, sim=sim)
            code = r.go()
            r.ending(code)
            r.questions()
            log("INFO", f"result {code}; {table.lines_sent} lines sent, "
                        f"{table.motions_sent} movements; answers {r.answers}")
        finally:
            for sig, h in previous.items():
                signal.signal(sig, h)
        return code
    except KeyboardInterrupt:
        # before the table was opened, or between the end of the run and here
        print("\nStopped." + ("" if transport is None else
                              " Nothing more is sent to the table."))
        return 1
    finally:
        if transport is not None:
            transport.close()
        lock.release()
        print(f"The log is in {log_path.resolve()}")
        if args.real:
            print("Please read the log before you post it anywhere. It holds every line sent "
                  "and received and your answers, and no serial number.")
        fh.close()


if __name__ == "__main__":
    sys.exit(main())
