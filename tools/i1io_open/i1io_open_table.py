# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The i1iO 2 table, as far as this test program talks to it.

Standard library only. pyusb is imported only when the REAL table is opened.

THE ONE RULE OF THIS FILE: the program can put exactly ELEVEN different lines
on the wire, listed in :data:`WIRE` (and, with where each was recorded, in
BYTES.md beside this file). Every one of them is a line that X-Rite's
i1Profiler sent to the tester's own i1iO 2, byte for byte, in the place where
i1Profiler sent it when it opened an already started ("warm") table and when it
closed the table. There is no command in this package that moves the arm
anywhere but its own resting place, and no function that builds a command from
numbers: the eleven lines are fixed at import and :func:`check_outgoing`
refuses every other byte string.

ONE line makes the arm move: ``;i12b`` (i1, run to the resting place), sent
ONCE, right after a ``p0`` that read a place i1Profiler itself sent i1 from at
rest (:data:`HOME_CLUSTER`: X 1102, Y 0..47 in the recordings, one reading step
around it). Version 0.2.2 (after the tester's 0.2.1 runs of 15 Nov 2026, where
the arm read Y 55 and the run stopped) no longer derives that box from the
positions seen at rest, which drift the longer the arm stands: it uses only the
recorded starting points of i1Profiler's own homings. From anywhere else it
sends no homing at all. Version 0.2.1 (after the tester's real
run of 0.2.0 and the safety review that followed it, M3) ends exactly as
i1Profiler ended two recorded sessions: ``s0 p0 i1 s0``, a pause, ``s0 f0 f3``
(S1 4.766-22.951, R2 268.621-361.611). No position is read after the homing,
because in every recording ``p0`` is followed only by a movement, ``c4`` or
another ``p0``, never by ``s0``, ``f4`` or ``f0``; the homing's own time is the
check on the wire (it must answer within :data:`SLOW_AFTER`), and the person's
look is the check by eye. Every run of up to ten neighbouring lines of the whole
run occurs in the recordings. i1Profiler's start-up line for a table that has just been
switched on (i0) is NOT in this program (safety review 2026-11-14, B1): on such
a table the program sends only the six reading lines of the opening and stops.
Two lines read the table's memory (``u8``): their answers hold the table's
serial number, so they are checked for their form and length only and are never
logged, shown or kept.

Line format (held on every recorded line): host to table ``;`` + command id +
arguments (lower-case hex) + checksum + CR; the table answers every command
with two lines, ``:!`` id checksum (accepted) at once and ``:$`` id status data
checksum (done) when it has finished, or with ``:#`` id code checksum when it
refuses (seen on the tester's table, never in the recordings). The checksum is
the two's complement of the 8-bit sum of every character before it.

Table positions are in the table's own units (0.1 mm). The resting place, where
the arm stands over the table's white tile, is X 1102, Y 0.
"""
from __future__ import annotations

import re
import signal
import sys
import time
from dataclasses import dataclass

TOOL_NAME = "chromiq-i1io-open"
TOOL_VERSION = "0.2.2"

VID, PID = 0x0971, 0x2004


class ForbiddenLine(Exception):
    """A line that is not one of the eleven (a bug; it is never written)."""


class ProtocolError(Exception):
    """A reply that is not what the recordings show."""


class TableRefused(ProtocolError):
    """The table answered ``:#`` + id + code: it refused the command. Seen on
    the tester's table (0.1.0, run 1: ``:#s01CF`` to ``;s022`` on a table that had
    been switched on and not yet started; whether k2, u8 or a0 would have
    changed that is not known); never in the recordings."""

    def __init__(self, cid: str, code: int, line: str):
        super().__init__(f"the table refused {cid} with code {code} ({line!r})")
        self.cid, self.code = cid, code


class TransportError(Exception):
    """The USB link itself failed."""


class NotAvailable(Exception):
    """The real table cannot be opened on this computer (with the reason)."""


class TableBusy(TransportError):
    """macOS did not let the program open the table: another program holds it (libusb
    ACCESS or BUSY while opening or claiming it; seen twice on the tester's Mac, 15 Nov
    2026). Nothing was sent. *step* is the call that failed, *code* libusb's number."""

    def __init__(self, message: str, step: str, code):
        super().__init__(message)
        self.step, self.code = step, code


# ---- checksum and framing ------------------------------------------------------

def _short(raw: bytes) -> str:
    """Unexpected bytes are described, never copied whole into a message or the
    log: a memory answer holds the table's serial number."""
    return f"{len(raw)} bytes, starting {bytes(raw[:4])!r}"


#: Replies longer than this are never echoed, only described (no recorded
#: reply to a non-memory line is longer: ":$k20" + 14 + checksum = 21).
ECHO_MAX = 24


def show(line: str) -> str:
    """A received line as it may appear in a message or the log."""
    if len(line) <= ECHO_MAX and line.isprintable() and not line.startswith(":$u8"):
        return repr(line)
    return _short(line.encode("ascii", "replace"))


def checksum(body: str) -> str:
    """Two lower-case hex digits that make the byte sum of *body* + them 0."""
    return f"{(-sum(body.encode('ascii'))) & 0xFF:02x}"


def checksum_ok(line: str) -> bool:
    """True when the last two characters are the line's valid checksum."""
    if len(line) < 3 or not re.fullmatch(r"[0-9A-Fa-f]{2}", line[-2:]):
        return False
    return (sum(line[:-2].encode("ascii", "replace")) + int(line[-2:], 16)) & 0xFF == 0


def _frame(cid: str, args: str = "") -> bytes:
    body = ";" + cid + args
    return (body + checksum(body) + "\r").encode("ascii")


# ---- THE ELEVEN LINES -------------------------------------------------------------

#: Everything this program can send. Each line is verbatim from the recordings
#: (where: :data:`RECORDED_AT` and BYTES.md); the tests pin the bytes and check
#: that BYTES.md lists exactly these.
WIRE = {
    "identity":  _frame("a1"),                     # ;a133
    "k2":        _frame("k2"),                     # ;k228
    "memory_a":  _frame("u8", "000060000100"),     # ;u8000060000100d1
    "memory_b":  _frame("u8", "000061000068"),     # ;u8000061000068c3
    "a0":        _frame("a0"),                     # ;a034
    "status":    _frame("s0"),                     # ;s022
    "arm_mode":  _frame("f4"),                     # ;f42b
    "position":  _frame("p0"),                     # ;p025
    "home":      _frame("i1"),                     # ;i12b
    "f0":        _frame("f0"),                     # ;f02f
    "f3":        _frame("f3"),                     # ;f32c
}

#: Where each line was recorded. S1 = the cold-start recording of 14 Nov 2026,
#: R2 = the second recording of 12/13 Nov 2026 (seconds from its start).
RECORDED_AT = {
    "identity": "S1 1.141 and 1.311 (cold); R2 34.546/34.715 and 378.147/378.314 (warm)",
    "k2":       "S1 1.327 (cold); R2 34.731 and 378.331 (warm)",
    "memory_a": "S1 1.343 (cold); R2 34.747 and 378.347 (warm)",
    "memory_b": "S1 1.450 (cold); R2 34.853 and 378.453 (warm)",
    "a0":       "S1 1.502 answered 111800 (cold); R2 34.906 and 378.505 answered 130000 (warm)",
    "status":   "R2 34.932 (after a0), 378.602 (right before p0, i1), 378.905 (after i1), "
                "361.579 and S1 22.919 (right before f0)",
    "arm_mode": "four times after the first s0 at every open: R2 34.940-34.985, 378.539-378.585",
    "position": "R2 35.017 and 378.617, right before the homing at the opening; S1 4.780 and "
                "R2 268.637, right before the homing that the close followed",
    "home":     "S1 4.796 from (1102, 14), 0.224 s, and R2 268.653 from (1102, 24), 0.256 s, "
                "each followed by s0, a pause and the close; R2 378.632 from (1102, 24), "
                "0.272 s; R2 35.033 from (1102, 47), 0.35 s",
    "f0":       "S1 22.935 (closing, after s0, arm at rest); R2 361.594",
    "f3":       "S1 22.951 (closing, right after f0); R2 361.611",
}

ALLOWED_LINES = frozenset(WIRE.values())
MOTION_KEYS = frozenset({"home"})
MOTION_LINES = frozenset(WIRE[k] for k in MOTION_KEYS)
#: Replies that hold the table's serial number: checked, never logged or kept.
SECRET_KEYS = frozenset({"memory_a", "memory_b"})

#: Data characters in the ':$' reply to each line (as recorded).
DATA_LEN = {"identity": 10, "k2": 14, "memory_a": 512, "memory_b": 208, "a0": 6,
            "status": 0, "arm_mode": 2, "position": 8, "home": 0,
            "f0": 2, "f3": 2}
#: The recorded constant answers (identical at every recorded open and close).
EXACT_DATA = {"identity": "005D010702", "k2": "0B600000000013", "f0": "00", "f3": "00",
              "arm_mode": "00"}
#: f4's recorded answer wherever this program reads it (98 of 98 reads outside an alignment;
#: 01 was only ever read after f1, the hand-alignment mode, which is never sent here).
#: f4 is a mode flag, NOT a reading of the motors: R1's opening read 00 with the arm found
#: 3 cm from its resting place, and on 15 Nov 2026 the tester's table read 00 four times
#: while he found the arm free at rest (0.2.1, run 5).
F4_RECORDED = "00"
#: The first 8 bytes of the memory block, the same at every recorded open:
#: the block length 360 and the text "V1.1" (no serial number in them).
MEMORY_A_START = "6801000056312E31"
#: a0's two recorded answers.
A0_COLD = "111800"
A0_WARM = "130000"


def check_outgoing(line: bytes) -> str:
    """THE GATE. Return the command id if *line* is exactly one of the eleven
    lines; raise ForbiddenLine otherwise."""
    if not isinstance(line, (bytes, bytearray)) or bytes(line) not in ALLOWED_LINES:
        raise ForbiddenLine(f"not one of the eleven allowed lines: {line!r}")
    return bytes(line)[1:3].decode("ascii")


# ---- replies -----------------------------------------------------------------------

@dataclass(frozen=True)
class Reply:
    cid: str
    status: int
    data: str          # upper-case hex as received ("" for a memory answer)

    def xy(self) -> "tuple[int, int]":
        x, y = int(self.data[:4], 16), int(self.data[4:8], 16)
        return (x - 0x10000 if x & 0x8000 else x, y - 0x10000 if y & 0x8000 else y)


_ACK_RE = re.compile(r":!([a-z][0-9])([0-9A-F]{2})")
_REFUSED_RE = re.compile(r":#([a-z][0-9])([0-9A-F])([0-9A-F]{2})")
_DONE_RE = re.compile(r":\$([a-z][0-9])([0-9A-F])([0-9A-F]*)([0-9A-F]{2})")
#: The longest acceptance or refusal line (":#s01CF").
ACK_MAX = 7


def _check_refused(line: str, cid: str) -> None:
    if not line.startswith(":#"):
        return
    m = _REFUSED_RE.fullmatch(line)
    if m and checksum_ok(line) and m.group(1) == cid:
        raise TableRefused(cid, int(m.group(2), 16), line)
    raise ProtocolError(f"a malformed refusal while waiting for {cid} ({show(line)})")


def parse_ack(line: str, cid: str) -> None:
    _check_refused(line, cid)
    m = _ACK_RE.fullmatch(line)
    if not m or not checksum_ok(line):
        raise ProtocolError(f"expected the table's acceptance of {cid}, got {show(line)}")
    if m.group(1) != cid:
        raise ProtocolError(f"acceptance for {m.group(1)} while waiting for {cid}: {show(line)}")


def parse_done(line: str, key: str) -> Reply:
    """The ':$' answer to WIRE[key], checked against the recorded form: status
    0, the recorded number of data characters, the recorded constant where
    there is one. A memory answer is checked and then dropped (data "")."""
    cid = WIRE[key][1:3].decode("ascii")
    _check_refused(line, cid)
    if not line.startswith(":$") or not checksum_ok(line):
        raise ProtocolError(f"expected the table's answer to {cid}, got {show(line)}")
    m = _DONE_RE.fullmatch(line)
    if not m:
        raise ProtocolError(f"malformed answer to {cid}: {show(line)}")
    if m.group(1) != cid:
        raise ProtocolError(f"answer for {m.group(1)} while waiting for {cid}: {show(line)}")
    status, data = int(m.group(2), 16), m.group(3)
    if status != 0:
        raise ProtocolError(f"the table answered {cid} with status {status}, which it never "
                            "did in the recordings for this line")
    if len(data) != DATA_LEN[key]:
        raise ProtocolError(f"answer to {cid} has {len(data)} data characters, expected "
                            f"{DATA_LEN[key]}")
    if key in EXACT_DATA and data != EXACT_DATA[key]:
        raise ProtocolError(f"the table answered {cid} with {data}, not with the recorded "
                            f"{EXACT_DATA[key]}")
    if key == "memory_a" and not data.startswith(MEMORY_A_START):
        raise ProtocolError("the table's memory block does not start as recorded")
    if key == "a0" and data not in (A0_COLD, A0_WARM):
        raise ProtocolError(f"the table answered a0 with {data}; the recordings only show "
                            f"{A0_COLD} (just switched on) and {A0_WARM} (started)")
    if key in SECRET_KEYS:
        data = ""
    return Reply(cid, status, data)


def done_max_len(key: str) -> int:
    """The length of the recorded ':$' answer to WIRE[key]."""
    return 2 + 2 + 1 + DATA_LEN[key] + 2


# ---- places, times and caps ------------------------------------------------------------

@dataclass(frozen=True)
class Box:
    xmin: int
    xmax: int
    ymin: int
    ymax: int

    def contains(self, p) -> bool:
        return self.xmin <= p[0] <= self.xmax and self.ymin <= p[1] <= self.ymax


#: Where i1Profiler itself sent i1 from, at rest, in the recordings: X 1102 and
#: Y 14, 22, 24, 24, 32, 36, 47 (first homings: S1 4.796, R2 417.181, 268.653, 378.632, R1
#: 190.093, R2 134.274, 35.033) and Y 0, 2, 2 (second homings of a double homing: R2 134.610,
#: R1 190.412, R2 417.453). (seconds, position read right before)
RECORDED_DIRECT_STARTS = ((1102, 14), (1102, 22), (1102, 24), (1102, 24), (1102, 32),
                          (1102, 36), (1102, 47), (1102, 0), (1102, 2), (1102, 2))
#: The ONE homing is sent only from here, checked on the p0 right before it: the recorded
#: starting points above, with one unit (0.1 mm, the table's reading step) around them.
#: Not a range of "positions seen at rest": those drift the longer the arm stands (Y 0..5
#: right after a homing, 22..37 within minutes, 41, 46, 47 and, on the tester's table on
#: 15 Nov 2026, 55 after a long idle), so any limit drawn from them fails on some later day
#: (0.2.0's Y -3..8 failed at Y 19, 0.2.1's Y -5..50 at Y 55). Between Y 47 and the far
#: positions i1 is recorded from (Y 1492 and more) i1Profiler was recorded once making the
#: other choice: from (1058, 317) it drove out with two m0 before it homed (R1 83.6). Where its
#: rule changes is not known, so this program does not guess: from outside this box it sends
#: no homing (a planned stop; nothing moves).
HOME_CLUSTER = Box(1101, 1103, -1, 48)

#: How long the program waits for an answer before it counts as missing.
#: Recorded: quick lines 0.005-0.022 s, u8 0.051-0.106 s,
#: i1 0.048-0.352 s at the resting place (4.02 s from far out).
QUICK_TIMEOUT = 1.0
HOME_TIMEOUT = 12.0
#: A homing that finished, but took longer than this, is a doubt (safety review M1): the
#: arm may have done something no recording shows (a travel, a search like i0's 3.17 s),
#: so nothing more is sent, not even the close. Every recorded homing from the resting
#: place took 0.047-0.352 s (from Y 0..2 0.047-0.048 s; from Y 14..47 0.224-0.352 s); the
#: tester's own table took 0.352 s from Y 46 (0.2.0's log: line 7879.843, acceptance 7879.859,
#: answer 7880.195; like the recordings, measured from the line to the answer). 0.6 s is 1.7
#: times the slowest.
#: There is NO lower bound: the arm can rest at Y 0..2 (read there after a homing), where a
#: homing answered in 0.047 s, and no recording shows a time a real homing cannot beat.
SLOW_AFTER = {"home": 0.6}
#: The slowest recorded homing from the resting place, for the texts.
SLOWEST_RECORDED_HOME_S = 0.352
SLOW_HOME_TEXT = (
    "The table reported that the homing had finished, but it took {took:.2f} seconds. On "
    "your table it took 0.35 seconds (version 0.2.0), and in every recording a homing from "
    "the resting place took at most 0.35 seconds. Because it took longer than anything we "
    "know, the arm may have done something no recording shows, so the program does not "
    "close the table and sends nothing more.")
#: No read is shorter than this (macOS cancels a timed-out USB read).
MIN_READ_S = 0.05
#: Before every command the program listens this long for anything unasked.
QUIET_CHECK_S = 0.05
#: After opening, the table must be silent this long before the first command.
DRAIN_QUIET_S = 1.0
DRAIN_SETTLE_S = 15.0
DRAIN_MAX_S = 60.0

#: Hard caps, checked on every write. A complete (warm) run sends exactly 18
#: lines with 1 movement (the homing at the resting place); a cold table gets
#: the six reading lines of the opening only.
MAX_LINES = 18
MAX_MOTIONS = 1


# ---- the session ------------------------------------------------------------------------

class Doubt(Exception):
    """Something was not as expected. From now on NOTHING more is sent.
    *plain*: a whole sentence for the tester, said as it is."""

    def __init__(self, reason: str, plain: "str | None" = None):
        super().__init__(reason)
        self.plain = plain


class Stopped(Exception):
    """The tester stopped the run. From now on NOTHING more is sent."""


#: The signals that ask the program to stop (Ctrl-C and the like).
_STOP_SIGNALS = tuple(getattr(signal, n) for n in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT")
                      if hasattr(signal, n))


def hold_stop_signals():
    """Hold the stop signals back (they stay pending, nothing is lost).
    Returns what to restore; None where the system cannot do it."""
    try:
        return signal.pthread_sigmask(signal.SIG_BLOCK, _STOP_SIGNALS)
    except (AttributeError, ValueError, OSError):
        return None


def release_stop_signals(held) -> None:
    if held is None:
        return
    try:
        signal.pthread_sigmask(signal.SIG_SETMASK, held)
    except (AttributeError, ValueError, OSError):
        pass


OUTSIDE_TEXT = (
    "{what} the arm reports table position X {x}, Y {y} (in tenths of a millimetre). "
    "i1Profiler has been recorded sending its homing from the resting place only when the arm "
    "read X 1102 and Y 0 to 47, and this program sends it only from there (X 1101 to 1103, "
    "Y -1 to 48). From further out, nobody knows whether i1Profiler would send the same line: "
    "once, when the arm was further away, it drove the arm out first. So the program does not "
    "send the homing, and nothing more is sent. This is one of the planned "
    "endings, not a fault of your table: the arm creeps slowly away from Y 0 the longer it "
    "stands.")

REFUSED_TEXT = ("The table answered, but refused the line {line} (code {code}). The recordings "
                "never showed this. Nothing more is sent to the table.")


class Table:
    """One command at a time over a transport; every reply checked against the
    recorded form.

    After the first doubt or stop, :attr:`closed_reason` is set and every
    further write is refused before it reaches the transport: the program
    never sends anything to "tidy up" (no homing, no stop, no closing)."""

    def __init__(self, transport, log=None):
        self.t = transport
        self._log = log or (lambda kind, text: None)
        self._buf = b""
        self.closed_reason: "str | None" = None
        self.lines_sent = 0
        self.motions_sent = 0
        self.busy = 0
        self.stop_requested = False
        self.position_now: "tuple[int, int] | None" = None
        #: a movement line was written and its completion never arrived
        self.motion_unconfirmed = False
        #: a movement was sent and where the arm is now has not been read yet
        self.arrival_unknown = False
        self.heading_to: "tuple[int, int] | None" = None
        self.state: "str | None" = None      # "cold" / "warm" after a0
        self.homed = False                   # i1 answered done
        self.homing_times: "list[float]" = []
        self.homings_done = 0
        self.closed_table = False            # f0, f3 answered
        #: the position read right before the homing, when it was outside HOME_CLUSTER
        self.outside_at: "tuple[int, int] | None" = None

    # ---- logging and stopping ------------------------------------------------------
    def log(self, kind: str, text: str) -> None:
        self._log(kind, f"{self.t.now():10.3f}  {text}")

    def request_stop(self) -> None:
        self.stop_requested = True

    def close_for_sending(self, reason: str) -> None:
        if self.closed_reason is None:
            self.closed_reason = reason
            self.log("STOP", f"nothing more is sent: {reason}")

    def _doubt(self, reason: str, plain: "str | None" = None) -> Doubt:
        self.close_for_sending(reason)
        return Doubt(reason, plain)

    def _stop_if_requested(self) -> None:
        if self.stop_requested:
            self.close_for_sending("stopped by you")
            raise Stopped("You stopped the program. Nothing more is sent to the table.")

    # ---- the wire ---------------------------------------------------------------------
    def _write(self, line: bytes) -> str:
        """The ONLY place that writes to the transport.

        The stop signals are held back from the last stop check until the line
        has been handed to the transport (safety review M1): a Ctrl-C is then
        either handled before that check, and the line is never written, or
        after the write, when the line was already on its way before the stop
        was noticed."""
        if self.closed_reason is not None:
            raise Doubt(f"not sending: {self.closed_reason}")
        cid = check_outgoing(line)
        if self.lines_sent >= MAX_LINES:
            raise self._doubt("the program reached its limit of lines for one run")
        is_motion = line in MOTION_LINES
        if is_motion and self.motions_sent >= MAX_MOTIONS:
            raise self._doubt("the program reached its limit of movements for one run")
        held = hold_stop_signals()
        try:
            self._stop_if_requested()          # the last check, with the signals held
            if self.closed_reason is not None:
                raise Doubt(f"not sending: {self.closed_reason}")
            self.lines_sent += 1
            if is_motion:
                self.motions_sent += 1
                self.motion_unconfirmed = True
            self.log("SEND", line.decode("ascii").rstrip("\r"))
            self.t.write(bytes(line))
        finally:
            release_stop_signals(held)
        return cid

    def _read_line(self, deadline: float, max_len: int, secret: bool = False) -> str:
        """One line of at most *max_len* characters. Bytes already waiting are
        always read before a timeout is declared."""
        last_try = False
        while b"\r" not in self._buf:
            if len(self._buf) > max_len:
                raise ProtocolError(f"a reply longer than the recorded one "
                                    f"({_short(self._buf)})")
            left = deadline - self.t.now()
            if left <= 0:
                if last_try:
                    raise TimeoutError
                last_try = True
            self._buf += self.t.read(max(MIN_READ_S, min(left, 0.25)))
        raw, self._buf = self._buf.split(b"\r", 1)
        if len(raw) > max_len:
            raise ProtocolError(f"a reply longer than the recorded one ({_short(raw)})")
        try:
            line = raw.decode("ascii")
        except UnicodeDecodeError:
            raise ProtocolError(f"non-text bytes from the table ({_short(raw)})") from None
        if not line.isprintable():
            raise ProtocolError(f"unexpected characters from the table ({_short(raw)})")
        if secret and line.startswith(":$"):
            self.log("RECV", f"{line[:5]}... ({len(line)} characters of the table's memory; "
                             "not written down, because they hold its serial number)")
        else:
            self.log("RECV", line if len(line) <= ECHO_MAX else show(line))
        return line

    def _quiet_check(self) -> None:
        """Before every command the table must have nothing more to say."""
        end = self.t.now() + QUIET_CHECK_S
        try:
            while not self._buf:
                left = end - self.t.now()
                if left <= 0:
                    break
                self._buf += self.t.read(max(MIN_READ_S, left))
        except TransportError as exc:
            raise self._doubt(f"the USB link failed: {exc}") from None
        if self._buf:
            raise self._doubt(f"the table sent something nobody asked for ({_short(self._buf)})")

    def exchange(self, key: str, timeout: float = QUICK_TIMEOUT) -> Reply:
        """Send WIRE[key], read its two answers, check them against the
        recorded form. Any fault closes the session. A stop asked for earlier
        is ALWAYS honoured before the line is written: after a stop nothing
        more is sent, not even a question about where the arm arrived."""
        line = WIRE[key]
        if self.closed_reason is not None:
            raise Doubt(f"not sending: {self.closed_reason}")
        self._stop_if_requested()
        self.busy += 1
        cid = line[1:3].decode("ascii")
        try:
            self._quiet_check()
            self._stop_if_requested()
            self._write(line)
            start = self.t.now()
            parse_ack(self._read_line(start + QUICK_TIMEOUT, ACK_MAX), cid)
            reply = parse_done(self._read_line(start + timeout, done_max_len(key),
                                               secret=key in SECRET_KEYS), key)
            took = self.t.now() - start
        except TimeoutError:
            raise self._doubt(f"no answer to {cid} within the expected time") from None
        except TableRefused as exc:
            if line in MOTION_LINES:
                # the table answered and refused: it did not start the movement
                self.motion_unconfirmed = False
                self.arrival_unknown = False
            raise self._doubt(str(exc), REFUSED_TEXT.format(
                line=line.decode("ascii").rstrip("\r"), code=exc.code)) from None
        except ProtocolError as exc:
            raise self._doubt(str(exc)) from None
        except TransportError as exc:
            raise self._doubt(f"the USB link failed: {exc}") from None
        except Stopped:
            raise
        except (Doubt, ForbiddenLine):
            self.close_for_sending("an internal check refused a line")
            raise
        except BaseException as exc:
            self.close_for_sending(f"an unexpected error ({type(exc).__name__})")
            raise
        finally:
            self.busy -= 1
        if line in MOTION_LINES:
            self.motion_unconfirmed = False
            self.homing_times.append(took)
            if took > SLOW_AFTER[key]:
                raise self._doubt(f"{cid} took {took:.3f} s, more than the {SLOW_AFTER[key]} s "
                                  f"allowed; the recordings show at most "
                                  f"{SLOWEST_RECORDED_HOME_S} s from the resting place",
                                  SLOW_HOME_TEXT.format(took=took))
        return reply

    def drain(self) -> None:
        """Before the first command the table must be silent. Bytes that arrive
        unasked are counted, never printed in full."""
        start = last = self.t.now()
        quiet = DRAIN_QUIET_S
        while True:
            self._stop_if_requested()
            try:
                chunk = self.t.read(0.25)
            except TransportError as exc:
                raise self._doubt(f"the USB link failed: {exc}") from None
            now = self.t.now()
            if chunk:
                self.log("DRAIN", f"{len(chunk)} unasked bytes after opening")
                last, quiet = now, DRAIN_SETTLE_S
            elif now - last >= quiet:
                return
            if now - start > DRAIN_MAX_S:
                raise self._doubt("the table keeps sending without being asked")

    # ---- the recorded sequences ----------------------------------------------------
    def position(self) -> "tuple[int, int]":
        p = self.exchange("position").xy()
        self.position_now = p
        self.arrival_unknown = False
        return p

    def opening(self) -> str:
        """i1Profiler's opening up to a0, as recorded at every open (cold and
        warm): a1, a1, k2, u8 6000/0100, u8 6100/0068, a0. Returns "cold"
        (a0 111800) or "warm" (a0 130000); anything else is a doubt. Moves
        nothing."""
        self.busy += 1
        try:
            self.drain()
            self.exchange("identity")
            self.exchange("identity")
            self.exchange("k2")
            self.exchange("memory_a")
            self.exchange("memory_b")
            a0 = self.exchange("a0").data
        finally:
            self.busy -= 1
        self.state = "cold" if a0 == A0_COLD else "warm"
        self.log("DATA", f"a0 = {a0}: the table is {self.state}")
        return self.state

    def _arm(self) -> str:
        got = self.exchange("arm_mode").data
        if got != F4_RECORDED:
            raise self._doubt(f"f4 answered {got} where the recordings show {F4_RECORDED}")
        return got

    def follow_up(self) -> None:
        """s0, f4 x4 (each 00): recorded right after a0 on a warm table (R2
        34.932-34.985, 378.530-378.585). The person's yes comes next: f4 then s0
        after a pause is recorded 13 times (up to 162 s, R1 550.730-713.337)."""
        if self.state != "warm":
            raise self._doubt("the follow-up asked for on a table that is not started (a bug)")
        self.busy += 1
        try:
            self.exchange("status")
            for _ in range(4):
                self._arm()
        finally:
            self.busy -= 1
        self._stop_if_requested()

    def _at_rest(self, what: str) -> "tuple[int, int]":
        pos = self.position()
        self.log("DATA", f"{what} the arm reports {pos}")
        if not HOME_CLUSTER.contains(pos):
            self.outside_at = pos
            raise self._doubt(
                f"{what} the arm reports {pos}, outside the places i1Profiler sent the "
                "homing from",
                OUTSIDE_TEXT.format(what=f"{what[0].upper()}{what[1:]}", x=pos[0], y=pos[1]))
        return pos

    def _homing(self) -> None:
        self.arrival_unknown = True
        self.heading_to = (1102, 0)
        self.position_now = None
        self.exchange("home", HOME_TIMEOUT)
        self.homings_done += 1

    def home(self) -> None:
        """After the person's yes, ONE homing, as i1Profiler sent it right before it
        closed the table: s0 p0 i1 s0 (S1 4.766-5.020, R2 268.621-268.909; the
        recorded pause and close follow). The i1 is sent right after a p0 that read
        the resting place. After the homing no position is read: no recording
        follows a p0 with s0, f4 or f0. The homing must answer within
        :data:`SLOW_AFTER` (safety review M1), or nothing more is sent."""
        if self.homed or self.state != "warm":
            raise self._doubt("i1 asked for while the arm is not known to be at rest (a bug)")
        self.busy += 1
        try:
            self.exchange("status")
            self._at_rest("right before the homing")
            self._homing()
            self.homed = True
            self.exchange("status")
        finally:
            self.busy -= 1
        self.log("DATA", f"the homing took {self.homing_times[-1]:.3f} s")
        self._stop_if_requested()

    def closing(self) -> None:
        """s0, f0, f3: i1Profiler's closing, recorded with the arm at rest right after
        its homing and a pause (S1 22.919-22.951, R2 361.579-361.611)."""
        if not self.homed:
            raise self._doubt("the closing asked for before the homing (a bug)")
        self.busy += 1
        try:
            self.exchange("status")
            self.exchange("f0")
            self.exchange("f3")
        finally:
            self.busy -= 1
        self.closed_table = True


# ---- the real table: FTDI over USB ------------------------------------------------------

def strip_ftdi(packet: bytes) -> bytes:
    """FTDI puts two status bytes before every 64-byte packet's payload."""
    return b"".join(packet[i + 2:i + 64] for i in range(0, len(packet), 64))


#: FTDI line-status bits that mean bytes were lost or damaged on the serial
#: side: overrun 0x02, parity 0x04, framing 0x08, break 0x10, RX FIFO 0x80.
LINE_ERROR_BITS = 0x9E


def check_line_status(packet: bytes) -> None:
    for i in range(0, len(packet), 64):
        if len(packet) > i + 1 and packet[i + 1] & LINE_ERROR_BITS:
            raise TransportError(f"the table's USB chip reports a line error "
                                 f"(status 0x{packet[i + 1]:02x})")


class Transport:
    def write(self, data: bytes) -> None:
        raise NotImplementedError

    def read(self, timeout: float) -> bytes:
        raise NotImplementedError

    def now(self) -> float:
        return time.monotonic()

    def close(self) -> None:
        pass


#: i1Profiler's five set-up requests were 0 to 5 ms apart (S1 1.124-1.141,
#: R2 34.534-34.546, 378.128-378.147).
SETUP_GAP_S = 0.004


class FtdiUsb(Transport):
    """The real table through pyusb + libusb, set up exactly as i1Profiler
    does it at every recorded open: FTDI reset, purge RX, purge TX, 57600
    baud, 8 data bits, no parity, 1 stop bit, no flow control."""

    EP_OUT, EP_IN = 0x02, 0x81
    SETUP = ((0x00, 0x0000, 0),   # SIO_RESET
             (0x00, 0x0001, 0),   # purge RX
             (0x00, 0x0002, 0),   # purge TX
             (0x03, 0x0034, 0),   # baud divisor 52: 57 600
             (0x04, 0x0008, 0))   # 8 data bits, no parity, 1 stop

    def __init__(self, dev, usb_core, usb_util):
        self.dev, self._core, self._util = dev, usb_core, usb_util
        self._timeout_error = getattr(usb_core, "USBTimeoutError", None)
        self._claimed = False
        self._closed = False

    def _is_timeout(self, exc) -> bool:
        if self._timeout_error is not None and isinstance(exc, self._timeout_error):
            return True
        return getattr(exc, "errno", None) in (60, 110)

    def setup(self) -> None:
        USBError = self._core.USBError
        step = "get_active_configuration"
        try:
            try:
                self.dev.get_active_configuration()
            except USBError as exc:
                if "Configuration not set" not in str(exc):
                    raise
                step = "set_configuration"
                self.dev.set_configuration()
            step = "claim_interface"
            self._util.claim_interface(self.dev, 0)
            self._claimed = True
        except USBError as exc:
            raise open_error(exc, step) from None
        try:
            for n, (req, val, idx) in enumerate(self.SETUP):
                if n:
                    time.sleep(SETUP_GAP_S)
                self.dev.ctrl_transfer(0x40, req, val, idx, None, 1000)
        except USBError as exc:
            raise TransportError(f"could not set up the table's USB link "
                                 f"({getattr(exc, 'strerror', None) or type(exc).__name__})") from None

    def write(self, data: bytes) -> None:
        check_outgoing(data)                       # the gate, once more, at the wire
        try:
            n = self.dev.write(self.EP_OUT, data, 1000)
        except self._core.USBError as exc:
            raise TransportError(f"USB write failed ({getattr(exc, 'strerror', None) or type(exc).__name__})") from None
        if n != len(data):
            raise TransportError(f"USB write sent {n} of {len(data)} bytes")

    def read(self, timeout: float) -> bytes:
        try:
            raw = bytes(self.dev.read(self.EP_IN, 64, max(1, int(timeout * 1000))))
        except self._core.USBError as exc:
            if self._is_timeout(exc):
                return b""
            raise TransportError(f"USB read failed ({getattr(exc, 'strerror', None) or type(exc).__name__})") from None
        check_line_status(raw)
        return strip_ftdi(raw)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        steps = [lambda: self._util.dispose_resources(self.dev)]
        if self._claimed:
            steps.insert(0, lambda: self._util.release_interface(self.dev, 0))
        for step in steps:
            try:
                step()
            except Exception:      # closing never raises
                pass


#: libusb's error numbers that matter while opening (libusb.h).
LIBUSB_ERRORS = {-1: "IO", -3: "ACCESS", -4: "NO_DEVICE", -5: "NOT_FOUND", -6: "BUSY",
                 -7: "TIMEOUT", -12: "NOT_SUPPORTED", -99: "OTHER"}
#: The same as POSIX errno, which pyusb also carries (EACCES, EBUSY, ENODEV).
_ERRNO_KIND = {13: "ACCESS", 16: "BUSY", 19: "NO_DEVICE"}

BUSY_TEXT = (
    "Your Mac did not let this program open the table, because another program is using it "
    "right now. Nothing was sent to the table.")
BUSY_STEPS = (
    "What usually helps, one step at a time: (1) If i1Profiler is open, quit it (i1Profiler "
    "menu, Quit i1Profiler). (2) Wait a minute and start this program again. (3) If the table "
    "is still in use: open i1Profiler, wait until it shows the table, quit it, and start this "
    "program again straight away. (4) If it is still in use after that, restarting the Mac "
    "frees it. Please do not try to stop X-Rite's background helpers by hand; this program "
    "never touches them either.")
GONE_TEXT = ("The table disappeared while the program was opening it (its USB cable or its "
             "power). Nothing was sent to the table. Please check both and try again.")


def error_kind(exc) -> "tuple[str, object]":
    """('ACCESS' / 'BUSY' / 'NO_DEVICE' / other name, the number) from a pyusb USBError."""
    code = getattr(exc, "backend_error_code", None)
    if isinstance(code, int) and code in LIBUSB_ERRORS:
        return LIBUSB_ERRORS[code], code
    errno = getattr(exc, "errno", None)
    if isinstance(errno, int) and errno in _ERRNO_KIND:
        return _ERRNO_KIND[errno], errno
    return "OTHER", code if code is not None else errno


def open_error(exc, step: str) -> TransportError:
    """The exception for a failure while opening the table (nothing was sent yet)."""
    kind, code = error_kind(exc)
    detail = (f"{step} failed: libusb {kind} ({code}); "
              f"{getattr(exc, 'strerror', None) or type(exc).__name__}")
    if kind in ("ACCESS", "BUSY"):
        return TableBusy(f"{BUSY_TEXT} ({detail})", step, code)
    if kind == "NO_DEVICE":
        return TransportError(f"{GONE_TEXT} ({detail})")
    return TransportError(
        "The table could not be opened. Please quit i1Profiler if it is open and try again; "
        f"if it still fails, send the log. Nothing was sent to the table. ({detail})")


# ---- who holds the table: macOS's own record, read only ------------------------------

#: The two IORegistry fields that name a process ("pid 123, name"). Nothing else from the
#: registry is ever kept: the table's entry also holds its serial number.
HOLDER_KEYS = ("UsbExclusiveOwner", "IOUserClientCreator")
_HOLDER_RE = re.compile(r"pid (\d{1,7}), ([A-Za-z0-9 ._+-]{1,40})")


def holders_from_plist(data: bytes, own_pid: "int | None" = None) -> "list[str]":
    """Read ioreg's plist output (bytes) and return, for the table's entry (0971:2004) and
    everything below it, the processes macOS names in :data:`HOLDER_KEYS`, as
    "exclusive owner: name (pid N)" or "connected: name (pid N)". Only text matching
    "pid N, name" is ever returned; every other field is dropped unread."""
    import plistlib
    if not data.strip():
        return []
    try:
        roots = plistlib.loads(data)
    except Exception:
        return ["(macOS's list could not be read)"]
    if isinstance(roots, dict):
        roots = [roots]
    found: "list[str]" = []

    def collect(node) -> None:
        for key in HOLDER_KEYS:
            value = node.get(key)
            if isinstance(value, str):
                m = _HOLDER_RE.fullmatch(value.strip())
                if m:
                    pid, name = int(m.group(1)), m.group(2).strip()
                    label = "exclusive owner" if key == "UsbExclusiveOwner" else "connected"
                    who = "this program" if own_pid is not None and pid == own_pid else name
                    entry = f"{label}: {who} (pid {pid})"
                else:
                    entry = f"{key}: (not in the expected form)"
                if entry not in found:
                    found.append(entry)
        for child in node.get("IORegistryEntryChildren", []) or []:
            if isinstance(child, dict):
                collect(child)

    def walk(node) -> None:
        if not isinstance(node, dict):
            return
        if node.get("idVendor") == VID and node.get("idProduct") == PID:
            collect(node)
            return
        for child in node.get("IORegistryEntryChildren", []) or []:
            walk(child)

    for root in roots:
        walk(root)
    return found[:12]


def usb_holders() -> "list[str]":
    """Ask macOS which processes hold the table (``ioreg``, read only: it opens no device,
    sends nothing, and touches no process). [] when nothing is found or ioreg fails."""
    import os
    import subprocess
    if sys.platform != "darwin":
        return []
    try:
        out = subprocess.run(["/usr/sbin/ioreg", "-a", "-r", "-c", "IOUSBHostDevice", "-l"],
                             capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ["(macOS's list could not be read)"]
    return holders_from_plist(out.stdout, own_pid=os.getpid())


def check_descriptors(dev) -> None:
    """The device must look exactly like the recorded table BEFORE anything is
    sent to it (not even the FTDI set-up). Reads cached descriptors only;
    never the serial-number string."""
    problems = []
    if getattr(dev, "bcdDevice", None) != 0x0400:
        problems.append(f"device release {getattr(dev, 'bcdDevice', None)!r}, expected 0x0400")
    try:
        cfg = dev[0]
        intfs = list(cfg)
        if len(intfs) != 1:
            problems.append(f"{len(intfs)} interfaces, expected 1")
        intf = intfs[0]
        cls = (intf.bInterfaceClass, intf.bInterfaceSubClass, intf.bInterfaceProtocol)
        if cls != (0xFF, 0xFF, 0xFF):
            problems.append(f"interface class {cls}, expected (255, 255, 255)")
        eps = sorted((e.bEndpointAddress, e.bmAttributes & 3, e.wMaxPacketSize)
                     for e in intf.endpoints())
        if eps != [(0x02, 2, 64), (0x81, 2, 64)]:
            problems.append(f"endpoints {eps}, expected bulk 0x02 and 0x81 of 64 bytes")
    except Exception as exc:
        problems.append(f"could not read its descriptors ({type(exc).__name__})")
    if problems:
        raise NotAvailable("The device with the i1iO's USB id does not look like the i1iO 2 "
                           "this program was made from (" + "; ".join(problems) + "). "
                           "Nothing was sent to it.")


#: Where Homebrew puts libusb (Apple silicon, then Intel).
LIBUSB_PATHS = ("/opt/homebrew/lib/libusb-1.0.dylib", "/usr/local/lib/libusb-1.0.dylib")


def libusb_backend(libusb1):
    import os
    backend = libusb1.get_backend()
    if backend is not None:
        return backend
    for path in LIBUSB_PATHS:
        if os.path.exists(path):
            backend = libusb1.get_backend(find_library=lambda name, path=path: path)
            if backend is not None:
                return backend
    return None


def libusb_version(backend) -> str:
    try:
        import ctypes

        class _V(ctypes.Structure):
            _fields_ = [("major", ctypes.c_uint16), ("minor", ctypes.c_uint16),
                        ("micro", ctypes.c_uint16), ("nano", ctypes.c_uint16),
                        ("rc", ctypes.c_char_p), ("describe", ctypes.c_char_p)]
        fn = backend.lib.libusb_get_version
        fn.restype = ctypes.POINTER(_V)
        v = fn().contents
        return f"{v.major}.{v.minor}.{v.micro}"
    except Exception:
        return "version unknown"


NOT_A_MAC = ("This test program opens the real table only on a Mac (it was never tried "
             "anywhere else). On Windows, X-Rite's own driver owns the i1iO.")
NO_PYUSB = ("The real table needs the Python package pyusb and the libusb library. If you "
            "have set them up as in 'What to install' in the README, start the program like "
            "this, from its folder: venv/bin/python3 i1io_open.py --real (plain 'python3' "
            "does not see the venv folder).")
NO_LIBUSB = ("pyusb is installed but finds no libusb library. On a Mac: "
             "'HOMEBREW_NO_AUTO_UPDATE=1 brew install libusb'.")


def check_usb_available() -> str:
    """Before any question of the real run: a Mac, pyusb and libusb. Opens no device."""
    if sys.platform != "darwin":
        raise NotAvailable(NOT_A_MAC)
    try:
        import usb
        import usb.backend.libusb1
    except ImportError:
        raise NotAvailable(NO_PYUSB) from None
    backend = libusb_backend(usb.backend.libusb1)
    if backend is None:
        raise NotAvailable(NO_LIBUSB)
    return (f"pyusb {getattr(usb, '__version__', 'version unknown')}; "
            f"libusb {libusb_version(backend)}")


def open_table() -> FtdiUsb:
    """Find and open the table, or raise NotAvailable. Sends no table command;
    only the FTDI set-up after the descriptor check."""
    if sys.platform != "darwin":
        raise NotAvailable(NOT_A_MAC)
    try:
        import usb.backend.libusb1
        import usb.core
        import usb.util
    except ImportError:
        raise NotAvailable(NO_PYUSB) from None
    backend = libusb_backend(usb.backend.libusb1)
    if backend is None:
        raise NotAvailable(NO_LIBUSB)
    try:
        found = list(usb.core.find(find_all=True, idVendor=VID, idProduct=PID, backend=backend))
    except usb.core.NoBackendError:
        raise NotAvailable(NO_LIBUSB) from None
    if not found:
        raise NotAvailable("No i1iO table (USB 0971:2004) was found. Please check that its "
                           "power supply is switched on and that its USB cable goes straight "
                           "into the computer. Nothing was sent.")
    if len(found) > 1:
        raise NotAvailable(f"{len(found)} devices with the i1iO's USB id are connected. "
                           "Please connect only one table. Nothing was sent.")
    dev = found[0]
    check_descriptors(dev)
    t = FtdiUsb(dev, usb.core, usb.util)
    try:
        t.setup()
    except BaseException:
        t.close()
        raise
    return t


def usb_summary(t) -> str:
    """For the log: USB id and chip revision. Never the serial number."""
    dev = getattr(t, "dev", None)
    if dev is None:
        return "simulated table"
    return f"USB {VID:04x}:{PID:04x}, bcdDevice {getattr(dev, 'bcdDevice', 0):04x}"
