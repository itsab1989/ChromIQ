#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""ChromIQ i1iO test program: a first, very small test of talking to an
X-Rite i1iO 2 table. It never measures.

    python3 i1io_trace.py            practice run on a SIMULATED table (nothing is opened)
    python3 i1io_trace.py --plan     print every line it could send, in order, and stop
    python3 i1io_trace.py --real     the real table (asks you to type a sentence first)

With --real it reads the table's identity, status and position and then asks
the table ONCE to run to its resting place, where the arm already is, so the
arm should barely move. That is the only line that can make anything move,
and it is shown, with what you should see, before you type yes. Everything
sent and received goes into a log file. See README.md.
"""
from __future__ import annotations

import argparse
import datetime
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

TITLE = (f"ChromIQ i1iO test program {tbl.TOOL_VERSION} (a first sign of life: one homing "
         "at the resting place, never measures)")
CONFIRM_SENTENCE = "i understand that this moves my table"
HANDS = "Keep your hands and everything else away from the arm while it moves."
PLUG = ("If anything looks or sounds wrong while the arm moves, switch the table off at its "
        "power switch or pull its power plug. That is always allowed, and it is the way to "
        "stop a movement that has begun. Pulling the USB cable alone does not do that: the "
        "table has its own power supply, so a movement it has started most likely goes on.")
PLUG_SHORT = "If it sounds or looks wrong, switch the table off at its power switch."
STOP_PROMISE = ("Ctrl-C works at any time: after Ctrl-C has been noticed, the program never "
                "starts a movement. A movement that has already begun is not stopped by "
                "Ctrl-C; only the power switch or plug stops it.")
#: X-Rite programs that may talk to the table or to its instrument. The names
#: are those installed on a Mac with i1Profiler 3.8: the app, its menu-bar
#: helper (/Library/LaunchAgents/com.xrite.i1Profiler.tray.plist) and X-Rite
#: Device Services (/Library/LaunchDaemons/com.xrite.device.xrdd.plist).
XRITE_NAMES = ("i1Profiler", "i1ProfilerTray", "xrdd")
XRITE_HOWTO = (
    "How to quit them, only for this test:\n"
    "  i1Profiler: quit the app (i1Profiler menu, Quit).\n"
    "  i1ProfilerTray (the menu-bar helper): in the Terminal,\n"
    "    launchctl bootout gui/$(id -u) /Library/LaunchAgents/com.xrite.i1Profiler.tray.plist\n"
    "  xrdd (X-Rite Device Services): in the Terminal (asks for your password),\n"
    "    sudo launchctl bootout system /Library/LaunchDaemons/com.xrite.device.xrdd.plist\n"
    "Afterwards, restart your Mac: that starts all of them again as before. (These commands "
    "were written from the files i1Profiler installs; they were not tried on a Mac with a "
    "table. If one does not work, restarting the Mac still undoes everything.)")
RECOVERY = ("To bring the arm back to its resting place, start i1Profiler once and let it "
            "connect to the table: it sends the arm home by itself. Then quit i1Profiler. "
            "Please do not start this program again until i1Profiler has brought the arm home.")
RECOVERY_UNFINISHED = (
    "The table never reported that its last movement had finished, so it may still be "
    "moving, or it may start that movement later. Please keep your hands away from the arm, "
    "switch the table off, wait ten seconds and switch it on again before you open "
    "i1Profiler; keep your hands away from the arm when you switch it on again too, because "
    "nobody knows yet whether the table moves by itself then. ")

RISKS = (
    "Please read this before you go on.\n"
    "This is a test program written by ChromIQ, not by X-Rite, and it has never run on a "
    "real table before: you would be the first, and nobody on the ChromIQ project owns a "
    "table. It can send only five different lines to the table, and each of them is a line "
    "that i1Profiler itself sent to your table in the recordings you made: four that only "
    "ask (identity, status, position, whether the motors hold the arm), and one that asks "
    "the table to run to its resting place. The arm is already there, so it should barely "
    "move. The program has no command for any other movement, sends no command of its own "
    "to lower or lift the measuring head, never measures, never talks to the i1Pro 2, and "
    "never reads or writes the table's memory. It cannot see the measuring head.\n"
    "What could still go wrong, in plain words: the table could do something the recordings "
    "never showed. That is why the table should be empty, why the one movement waits for "
    "you, and why you should keep the power switch or plug within reach.\n"
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
        self.log("SAY", text.replace("\n", " / "))
        try:              # a closed terminal must not stop the program from finishing
            for para in text.split("\n"):
                print(textwrap.fill(para, 78) if para else "")
        except OSError:
            pass

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
    meaning = "i1: go to the resting place"          # the only movement line there is
    return (f"Step {step.number} of {len(tbl.PLAN)}. The program will send the line "
            f"{line} ({meaning}).\n"
            f"What you should see: {step.what} When i1Profiler sent this line, it took "
            f"about {step.seconds}.\n"
            f"About this line: {step.recorded}.")


def _bare(key: str) -> str:
    return tbl.WIRE[key].decode("ascii").rstrip("\r")


def plan_text() -> str:
    """Every line the program can send, in the order it sends them."""
    out = [f"Every line this program can send, in order (nothing else can be sent; "
           f"{len(tbl.WIRE)} different lines):", "", "Opening (only reads, nothing moves):"]
    for key in ("identity", "identity", "status", "arm_mode", "position"):
        out.append(f"  {_bare(key):20} {key}")
    out.append("  checks: identity 005D010702 both times, motors holding the arm (00), "
               "arm at its resting place (X 1097..1107, Y -5..50)")
    for step in tbl.PLAN:
        s, e = step.start, step.end
        out += ["", f"Step {step.number} (only after you type yes):",
                f"  {_bare('arm_mode'):20} arm_mode, must be 00",
                f"  {_bare('position'):20} position, must be in X {s.xmin}..{s.xmax}, "
                f"Y {s.ymin}..{s.ymax}",
                f"  {_bare(step.key):20} {step.key}: {step.what}",
                f"  {_bare('position'):20} position, must be in X {e.xmin}..{e.xmax}, "
                f"Y {e.ymin}..{e.ymax}",
                f"  {_bare('arm_mode'):20} arm_mode, must still be 00"]
    out += ["", f"At most {tbl.MAX_LINES} lines and {tbl.MAX_MOTIONS} movements per run. "
            "After any stop or any doubt, nothing more is sent at all."]
    return "\n".join(out)


class Run:
    def __init__(self, table: tbl.Table, ui: Console, simulated: bool, sim=None,
                 other_program=None):
        self.d, self.ui, self.simulated, self.sim = table, ui, simulated, sim
        #: called before every step (real run: is i1Profiler running now?)
        self.other_program = other_program or (lambda: False)
        self.done_steps = 0
        self.answers: "list[tuple[str, str]]" = []

    def note(self, question: str, answer: str) -> None:
        self.answers.append((question, answer))

    def look(self, question: str, choices, key: str) -> str:
        ans = self.ui.ask(question, choices)
        self.note(key, ans)
        if ans == "stop":
            raise Stopped("You stopped the run.")
        return ans

    def go(self) -> int:
        """The whole run. Returns 0 (complete), 1 (stopped by you) or 2 (a doubt)."""
        try:
            self.ui.say("Talking to the table. Nothing moves yet.")
            pos = self.d.open_checks()
            self.ui.say(f"The table answered as expected. It is the table model this program "
                        f"was made from, its motors hold the arm, and the arm reports table "
                        f"position X {pos[0]}, Y {pos[1]}, which is its resting place.")
            ans = self.look("Please look at the table now. Is the arm at its resting place "
                            "(where i1Profiler leaves it, over the white tile)?",
                            ("yes", "no", "stop"), "arm at its resting place")
            if ans != "yes":
                raise Stopped("Then the program does not move anything. Please use "
                              "i1Profiler once to bring the arm to its resting place, quit "
                              "i1Profiler, then start again.")
            ans = self.look("And is the table completely empty (no paper, no chart, nothing "
                            "lying on it)?", ("yes", "no", "stop"), "table empty")
            if ans != "yes":
                raise Stopped("Then the program does not move anything. Please clear the "
                              "table, then start again.")
            for step in tbl.PLAN:
                self.ui.say("")
                self.ui.say(describe(step))
                if step.number == 1:
                    self.ui.say(PLUG)
                    self.ui.say(STOP_PROMISE)
                self.ui.say(PLUG_SHORT)
                go = self.ui.ask(f"{HANDS} Send step {step.number} now?", ("yes", "no", "stop"))
                if go != "yes":
                    raise Stopped(f"You stopped before step {step.number}.")
                if self.other_program():
                    self.d.close_for_sending("an X-Rite program was started during the run")
                    raise Stopped("An X-Rite program has started, so the program stops here: "
                                  "two programs must never talk to the table at the same "
                                  "time.")
                got = self.d.motion(step)
                self.done_steps = step.number
                self.ui.say(f"The table reports that it has finished step {step.number}; "
                            f"the arm reports table position X {got[0]}, Y {got[1]}.")
                seen = self.look(f"Did the arm do what was described for step "
                                 f"{step.number}?", ("yes", "no", "not sure", "stop"),
                                 f"step {step.number} as described")
                if seen != "yes":
                    self.note(f"step {step.number} instead", self.ui.text(
                        "What did you see instead? (type a few words, then Enter)"))
                    raise Stopped("Thank you, that is exactly what we need to know. The "
                                  "program stops here.")
                if step.number == 1:
                    self.look("Now please look at the bottom of the instrument holder, where "
                              "the round measuring opening is. Does it rest on the white "
                              "tile, or is there a gap between it and the tile?",
                              ("rests", "gap", "not sure", "stop"), "opening at home")
            self.ui.say("")
            self.ui.say("That was all: the table answered, and the arm is at its resting "
                        "place. Thank you.")
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
        except Exception as exc:      # a bug or a library surprise: say so, never a traceback
            self.d.close_for_sending(f"an unexpected error ({type(exc).__name__})")
            self.ui.say(f"The program stopped because of an unexpected error "
                        f"({type(exc).__name__}). Nothing more is sent to the table.")
            return 2
        finally:
            # whatever happened: from here on nothing is sent to the table
            self.d.close_for_sending("the run is over")

    def ending(self, code: int) -> None:
        """Say where the arm is and what to do. Sends nothing; nothing (not
        even Ctrl-C) may keep the advice from being shown."""
        try:
            d = self.d
            pos = None if d.arrival_unknown else d.position_now
            if d.motions_sent == 0:
                self.ui.say("Nothing was moved.")
            elif code == 0:
                pass
            elif pos is not None and tbl.HOME_CLUSTER.contains(pos):
                self.ui.say("The arm was last reported at its resting place.")
            else:
                if d.arrival_unknown and d.heading_to:
                    where = (f" Its last movement was towards table position X "
                             f"{d.heading_to[0]}, Y {d.heading_to[1]}, and where it stopped "
                             "is not known.")
                elif pos is not None:
                    where = f" It was last reported at table position X {pos[0]}, Y {pos[1]}."
                else:
                    where = ""
                self.ui.say("The arm stays where it is now; the program does not move it "
                            "again." + where + " "
                            + (RECOVERY_UNFINISHED if d.motion_unconfirmed else "")
                            + RECOVERY)
        except BaseException:
            pass

    def questions(self) -> None:
        if self.d.lines_sent == 0:
            return
        try:
            self.ui.say("")
            self.ui.say("A few questions for the report (just press Enter to skip one).")
            for q in ("Did you hear anything unusual (grinding, knocking, clicking, a long "
                      "buzz)? If yes, during which step?",
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


def xrite_running() -> "list[str]":
    """Which of X-Rite's programs (by exact name) are running now. Any of them
    could have the table or its instrument open, and the outcome of two
    programs talking to the table at once is unknown, so the real run refuses."""
    return [name for name in XRITE_NAMES if _pgrep("-x", "-i", name)]


def i1profiler_running() -> bool:
    """Kept for the step check: any X-Rite program counts."""
    return bool(xrite_running())


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
        # the (empty) file is left in the temporary folder: deleting it could
        # let two later copies lock two different files
        if self.fh is not None:
            self.fh.close()
            self.fh = None


def install_signals(table: tbl.Table) -> dict:
    """Ctrl-C (and the other stop signals) never cut an exchange or a step in
    half: while one runs they only ask for a stop at the next safe point; at
    a question they stop the run at once. Ctrl-Z (and the other job-control
    stops) are ignored, so the program is never frozen in the middle of a
    step. Returns the previous handlers."""
    old = {}

    def handler(signum, frame):
        if table.busy:
            first = not table.stop_requested
            table.request_stop()
            if first:
                try:      # a closed terminal must not raise in the middle of a step
                    print("\nThe program stops at the next safe point; if the arm is "
                          "moving, the table finishes that movement first.", flush=True)
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
    try:
        fh = log_path.open("w", encoding="utf-8")
    except OSError as exc:
        print(f"The log file {log_path.name} cannot be written here ({type(exc).__name__}). "
              "Please start the program from a folder you can write to. Nothing was sent.")
        return 2

    def log(kind, text):
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

    log("INFO", f"{TITLE}; {'REAL table' if args.real else 'SIMULATED table'}; "
                f"{datetime.datetime.now().isoformat(timespec='seconds')}")
    log("INFO", environment(args.real))
    log("INFO", "allowed lines: " + " ".join(_bare(k) for k in tbl.WIRE)
        + f"; at most {tbl.MAX_LINES} lines and {tbl.MAX_MOTIONS} movements")
    log("INFO", "the table's serial number is never read by this program")
    ui = console or Console(log)
    if console is not None:
        console.log = log
    lock, transport, sim = Lock(), None, None
    code = 2
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
            try:
                usb_info = tbl.check_usb_available()
            except tbl.NotAvailable as exc:
                ui.say(str(exc) + " Nothing was sent.")
                return 2
            log("INFO", usb_info)
            ui.say(RISKS)
            running = xrite_running()
            if running:
                log("INFO", f"X-Rite programs running: {running}")
                ui.say("These X-Rite programs are running: " + ", ".join(running) + ". "
                       "Please quit them first: if X-Rite's software has the table open "
                       "while this program talks to it, nobody knows what happens. "
                       "Nothing was sent.\n" + XRITE_HOWTO)
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
                if ui.ask(q, ("yes", "no", "stop")) != "yes":
                    ui.say("Please make it so, then start the program again. Nothing was sent.")
                    return 1
            if not ui.sentence("To go on with the REAL table, type this sentence and press "
                               "Enter:\n    I understand that this moves my table",
                               CONFIRM_SENTENCE):
                ui.say("That was not the sentence, so nothing was sent to the table.")
                return 1
            running = xrite_running()       # one may have started while he read
            if running:
                ui.say("These X-Rite programs are running now: " + ", ".join(running) + ". "
                       "Please quit them first. Nothing was sent.\n" + XRITE_HOWTO)
                return 2
            log("INFO", "X-Rite programs running: none")
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
            r = Run(table, ui, simulated=not args.real, sim=sim,
                    other_program=i1profiler_running if args.real else None)
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
        # before the table was opened, or after the run
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
        previous_int = None
        try:                    # the tidy-up itself is never cut short by Ctrl-C
            previous_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
        except (ValueError, OSError):
            pass
        if transport is not None:
            transport.close()
        lock.release()
        try:
            print(f"The log is in: {args.log or log_path.name}")
            if args.real:
                print("Please read the log before you post it anywhere, and post the log, "
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
