#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""ChromIQ i1iO test program 0.2.0: open an X-Rite i1iO 2 table that is already
started, the way i1Profiler opens it, send the arm to its resting place where it
already is, and close the table again. It never measures.

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
import signal
import subprocess
import sys
import tempfile
import textwrap
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
    "your table twice (the first time the table refused it, the second time it worked). This "
    "version sends a few more lines. Each of them is a line that i1Profiler itself sent to your "
    "table in your recordings, byte for byte, and in the order i1Profiler sent them, except for "
    "one extra 'where is the arm' question after the homing: the lines with which i1Profiler "
    "opens the table, the line that sends the arm to its resting place, and the two lines with "
    "which it closes the table. Only the homing makes the arm move, and the arm is already at its "
    "resting place, so it should barely move. If the table has just been switched on, the "
    "program stops after the opening and asks you to let i1Profiler start the table first. The "
    "program has no command for any other movement, never measures and never talks to the "
    "i1Pro 2. It sends no line of its own for the measuring head. Whether the table lifts and "
    "lowers the head by itself as part of the homing is not known; with the first program the "
    "arm moved very little and nothing unusual was seen.\n"
    "It also asks for the table's memory block, as i1Profiler does when it opens the table. "
    "That block holds the table's serial number. The program checks only its length and its "
    "first eight bytes, and never writes it down or shows it.\n"
    "What could still go wrong, in plain words: the table could do something the recordings "
    "never showed. That is why the table should be empty, why the movement waits for your yes, "
    "why you should keep your hands and everything else away from the arm, and why you should "
    "keep the power switch or plug within reach.\n"
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
FOLLOW = ("status", "arm_mode", "arm_mode", "arm_mode", "arm_mode", "status", "position")
HOMING = ("status", "position", "home", "status", "position")
CLOSING = ("status", "f0", "f3")
MEANING = {
    "identity": "identity (must be 005D010702)",
    "k2": "k2, a fixed answer (must be 0B600000000013)",
    "memory_a": "the table's memory, part 1 (256 bytes; not written down)",
    "memory_b": "the table's memory, part 2 (104 bytes; not written down)",
    "a0": "a0: we believe 111800 = just switched on (cold: stop here), 130000 = started",
    "status": "status (must be accepted)",
    "arm_mode": "we believe: do the motors hold the arm? (must be 00)",
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
           f"{tbl.MAX_MOTIONS} movement in one run. After any stop or any doubt, nothing "
           "more is sent at all.", "",
           "Before anything: the USB set-up i1Profiler uses (FTDI reset, purge, purge, "
           "57600 baud, 8 data bits, no parity, 1 stop bit), then 1 s of listening.", "",
           "1. Opening (only reads; nothing moves):"]
    out += [row(k) for k in OPENING]
    out += ["", "2. If a0 answered 111800 (just switched on): STOP here, nothing more is sent;",
            "   you are asked to let i1Profiler start the table and to run the program again.",
            "   Any answer other than 111800 or 130000: stop, nothing more is sent.", "",
            "3. Follow-up on a started table (only reads):"]
    out += [row(k) for k in FOLLOW]
    out += ["  checks: every arm answer 00; the arm at its resting place (X 1097..1107, "
            "Y -5..50); otherwise stop.", "",
            "4. Homing, only after you type yes (status and position asked again, the place "
            "checked again, then the homing at once, as i1Profiler does):"]
    out += [row(k) for k in HOMING]
    out += ["  checks: the arm at X 1099..1105, Y -3..8 afterwards; otherwise stop.", "",
            "5. Closing, after you have looked at the arm:"]
    out += [row(k) for k in CLOSING]
    return "\n".join(out)


# ---- the run ---------------------------------------------------------------------------

class Run:
    def __init__(self, table: tbl.Table, ui: Console, simulated: bool,
                 other_program=None):
        self.d, self.ui, self.simulated = table, ui, simulated
        self.other_program = other_program or (lambda: False)
        self.answers: "list[tuple[str, str]]" = []

    def note(self, question: str, answer: str) -> None:
        self.answers.append((question, answer))

    def look(self, question: str, choices, key: str) -> str:
        ans = self.ui.ask(question, choices)
        self.note(key, ans)
        if ans == "stop":
            raise Stopped(STOPPED)
        return ans

    def _go_ahead(self, what: str) -> None:
        self.ui.say("")
        self.ui.say(what)
        self.ui.say(PLUG)
        self.ui.say(STOP_PROMISE)
        go = self.ui.ask(f"{HANDS} Send it now?", ("yes", "no", "stop"))
        self.note("go ahead", go)
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
            pos = self.d.follow_up()
            self.ui.say(f"The table answered as expected. It is started (a0 = 130000), its "
                        f"motors hold the arm, and the arm reports table position X {pos[0]}, "
                        f"Y {pos[1]}, which is its resting place.")
            self._go_ahead(
                f"Next the program asks once more for the status and where the arm is, and if "
                f"the arm is still at its resting place it sends {_bare('home')} (i1, go to the "
                "resting place) at once, as i1Profiler does. The arm is already there, so it "
                "should move very little or not at all; you may hear the motors for a moment. "
                "With i1Profiler it took about a quarter of a second.")
            got = self.d.home()
            self.ui.say(f"The table reports that the homing has finished; the arm reports "
                        f"table position X {got[0]}, Y {got[1]}.")
            seen = self.look(f"Please look at the table now. Is the arm at {REST_PLACE}?",
                             ("yes", "no", "not sure", "stop"), "arm at its resting place")
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
            self.ui.say("That was all: the table was opened and closed the way i1Profiler does "
                        "it, and the arm is at its resting place. Thank you.")
            return 0
        except Stopped as exc:
            self.ui.say(str(exc))
            return 1
        except KeyboardInterrupt:
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
            pos = None if d.arrival_unknown else d.position_now
            if d.motions_sent == 0:
                self.ui.say("Nothing was moved.")
            elif code == 0:
                pass
            elif pos is not None and tbl.HOME_CLUSTER.contains(pos):
                self.ui.say("The arm was last reported at its resting place.")
            else:
                if d.arrival_unknown and d.heading_to:
                    where = (" Its last movement was towards its resting place, and where it "
                             "stopped has not been read.")
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
                      "buzz)? If yes, when?",
                      "Had the table been switched off and on before this run? If yes, how "
                      "long before?",
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
    return bool(_pgrep("-x", "-i", I1PROFILER)) or bool(_pgrep("-f", I1PROFILER_PATH))


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
                log("INFO", "i1Profiler is running: refused")
                ui.say(I1PROFILER_RUNNING)
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
            if not ui.sentence("To go on with the REAL table, type this sentence and press "
                               "Enter:\n    I understand that this moves my table",
                               CONFIRM_SENTENCE):
                ui.say("That was not the sentence, so nothing was sent to the table.")
                return 1
            if i1profiler_running():
                log("INFO", "i1Profiler is running: refused")
                ui.say(I1PROFILER_RUNNING)
                return 2
            helpers = xrite_helpers_running()
            log("INFO", f"X-Rite background helpers running: {helpers or 'none'}")
            try:
                transport = tbl.open_table()
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
        log("INFO", tbl.usb_summary(transport))
        table = tbl.Table(transport, log=log)
        previous = install_signals(table)
        try:
            r = Run(table, ui, simulated=not args.real,
                    other_program=i1profiler_running if args.real else None)
            code = r.go()
            r.ending(code)
            r.questions()
            log("INFO", f"result {code}; table {table.state or 'not asked'}; "
                        f"{table.lines_sent} lines sent, {table.motions_sent} movements; "
                        f"closed {'yes' if table.closed_table else 'no'}; answers {r.answers}")
        finally:
            for sig, h in previous.items():
                signal.signal(sig, h)
        return code
    except KeyboardInterrupt:
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
