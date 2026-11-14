# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The i1iO 2 table, as far as this test program talks to it.

Standard library only. pyusb is imported only when the REAL table is opened.

THE ONE RULE OF THIS FILE: the program can put exactly TWELVE different lines
on the wire, listed in :data:`WIRE` (and, with where each was recorded, in
BYTES.md beside this file). Every one of them is a line that X-Rite's
i1Profiler sent to the tester's own i1iO 2, byte for byte, in the same place
of the same sequence: the opening of the table, cold (right after the table
was switched on) and warm, and the closing. There is no command in this
package that moves the arm anywhere but its own resting place, and no function
that builds a command from numbers: the twelve lines are fixed at import and
:func:`check_outgoing` refuses every other byte string.

Two of the twelve make the arm move: ``;i02c`` (i0, the start-up of a table
that has just been switched on: i1Profiler sent it once, 3.2 s, the arm at its
resting place before and after) and ``;i12b`` (i1, run to the resting place,
sent only while the arm is already there). Two read the table's memory
(``u8``): their answers hold the table's serial number, so they are checked for
their form and length only and are never logged, shown or kept.

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
import sys
import time
from dataclasses import dataclass

TOOL_NAME = "chromiq-i1io-open"
TOOL_VERSION = "0.2.0"

VID, PID = 0x0971, 0x2004


class ForbiddenLine(Exception):
    """A line that is not one of the twelve (a bug; it is never written)."""


class ProtocolError(Exception):
    """A reply that is not what the recordings show."""


class TableRefused(ProtocolError):
    """The table answered ``:#`` + id + code: it refused the command. Seen on
    the tester's table (0.1.0, run 1: ``:#s01CF`` to ``;s022`` on a table that had
    been switched on and not yet started); never in the recordings."""

    def __init__(self, cid: str, code: int, line: str):
        super().__init__(f"the table refused {cid} with code {code} ({line!r})")
        self.cid, self.code = cid, code


class TransportError(Exception):
    """The USB link itself failed."""


class NotAvailable(Exception):
    """The real table cannot be opened on this computer (with the reason)."""


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


# ---- THE TWELVE LINES -------------------------------------------------------------

#: Everything this program can send. Each line is verbatim from the recordings
#: (where: :data:`RECORDED_AT` and BYTES.md); the tests pin the bytes and check
#: that BYTES.md lists exactly these.
WIRE = {
    "identity":  _frame("a1"),                     # ;a133
    "k2":        _frame("k2"),                     # ;k228
    "memory_a":  _frame("u8", "000060000100"),     # ;u8000060000100d1
    "memory_b":  _frame("u8", "000061000068"),     # ;u8000061000068c3
    "a0":        _frame("a0"),                     # ;a034
    "start":     _frame("i0"),                     # ;i02c
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
    "start":    "S1 1.517, the one i0: right after a0 = 111800, done after 3.167 s, "
                "arm at X 1102, Y 14 afterwards",
    "status":   "S1 4.693/4.766/5.020/22.919; R2 34.932/378.530/378.602/378.905/361.579",
    "arm_mode": "four times after the first s0 at every open: S1 4.706-4.748, R2 378.539-378.585",
    "position": "S1 4.780 and R2 378.617, just before the homing at the opening",
    "home":     "S1 4.796 from (1102, 14), 0.224 s; R2 378.632 from (1102, 24), 0.272 s; "
                "R2 35.033 from (1102, 47), 0.35 s",
    "f0":       "S1 22.935 (closing, after s0, arm at rest); R2 361.594",
    "f3":       "S1 22.951 (closing, right after f0); R2 361.611",
}

ALLOWED_LINES = frozenset(WIRE.values())
MOTION_KEYS = frozenset({"start", "home"})
MOTION_LINES = frozenset(WIRE[k] for k in MOTION_KEYS)
#: Replies that hold the table's serial number: checked, never logged or kept.
SECRET_KEYS = frozenset({"memory_a", "memory_b"})

#: Data characters in the ':$' reply to each line (as recorded).
DATA_LEN = {"identity": 10, "k2": 14, "memory_a": 512, "memory_b": 208, "a0": 6,
            "start": 0, "status": 0, "arm_mode": 2, "position": 8, "home": 0,
            "f0": 2, "f3": 2}
#: The recorded constant answers (identical at every recorded open and close).
EXACT_DATA = {"identity": "005D010702", "k2": "0B600000000013", "f0": "00", "f3": "00",
              "arm_mode": "00"}
#: The first 8 bytes of the memory block, the same at every recorded open:
#: the block length 360 and the text "V1.1" (no serial number in them).
MEMORY_A_START = "6801000056312E31"
#: a0's two recorded answers.
A0_COLD = "111800"
A0_WARM = "130000"


def check_outgoing(line: bytes) -> str:
    """THE GATE. Return the command id if *line* is exactly one of the twelve
    lines; raise ForbiddenLine otherwise."""
    if not isinstance(line, (bytes, bytearray)) or bytes(line) not in ALLOWED_LINES:
        raise ForbiddenLine(f"not one of the twelve allowed lines: {line!r}")
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


#: Where the arm rests. Every recorded start read X 1101 or 1102 and Y between
#: 0 and 47 (R1, R2, S1 14, S2 31..41; the reading creeps while the arm
#: stands); 5 units of margin on each side. i1 is sent only from here.
HOME_CLUSTER = Box(1097, 1107, -5, 50)
#: Where the arm must report itself right after the homing: recorded Y 0 and 2
#: (R1 190.412, R2 134.610), the tester's run of 0.1.1 read Y 5 64 ms after the
#: answer; the reading creeps (Y 0 -> 6 in 7 s, R2 134.6-142.1). X 3 units.
HOMED = Box(1099, 1105, -3, 8)

#: How long the program waits for an answer before it counts as missing.
#: Recorded: quick lines 0.005-0.022 s, u8 0.051-0.106 s, i0 3.167 s (once),
#: i1 0.048-0.352 s at the resting place (4.02 s from far out).
QUICK_TIMEOUT = 1.0
START_TIMEOUT = 15.0
HOME_TIMEOUT = 12.0
#: A movement that finished, but took far longer than recorded, is a doubt:
#: the arm may not have done what the recordings show (nothing more is sent).
SLOW_AFTER = {"start": 9.0, "home": 2.0}
#: No read is shorter than this (macOS cancels a timed-out USB read).
MIN_READ_S = 0.05
#: Before every command the program listens this long for anything unasked.
QUIET_CHECK_S = 0.05
#: After opening, the table must be silent this long before the first command.
DRAIN_QUIET_S = 1.0
DRAIN_SETTLE_S = 15.0
DRAIN_MAX_S = 60.0

#: Hard caps, checked on every write. A cold run sends exactly 20 lines, a warm one 19.
MAX_LINES = 20
MAX_MOTIONS = 2


# ---- the session ------------------------------------------------------------------------

class Doubt(Exception):
    """Something was not as expected. From now on NOTHING more is sent.
    *plain*: a whole sentence for the tester, said as it is."""

    def __init__(self, reason: str, plain: "str | None" = None):
        super().__init__(reason)
        self.plain = plain


class Stopped(Exception):
    """The tester stopped the run. From now on NOTHING more is sent."""


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
        self.started = False                 # i0 answered done
        self.homed = False                   # i1 answered done
        self.closed_table = False            # f0, f3 answered

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
        """The ONLY place that writes to the transport."""
        if self.closed_reason is not None:
            raise Doubt(f"not sending: {self.closed_reason}")
        cid = check_outgoing(line)
        if self.lines_sent >= MAX_LINES:
            raise self._doubt("the program reached its limit of lines for one run")
        is_motion = line in MOTION_LINES
        if is_motion and self.motions_sent >= MAX_MOTIONS:
            raise self._doubt("the program reached its limit of movements for one run")
        self.lines_sent += 1
        if is_motion:
            self.motions_sent += 1
            self.motion_unconfirmed = True
        self.log("SEND", line.decode("ascii").rstrip("\r"))
        self.t.write(bytes(line))
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
            if took > SLOW_AFTER[key]:
                raise self._doubt(f"{cid} took {took:.1f} s; the recordings show at most "
                                  f"{'3.2' if key == 'start' else '0.4'} s from the resting "
                                  "place")
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

    def start(self) -> None:
        """i0, only on a cold table, right after the opening (S1 1.517)."""
        if self.state != "cold" or self.started or self.lines_sent != 6:
            raise self._doubt("i0 asked for outside its recorded place (a bug)")
        self.arrival_unknown = True
        self.heading_to = (1102, 0)
        self.position_now = None
        self.exchange("start", START_TIMEOUT)
        self.started = True

    def after_start(self) -> "tuple[int, int]":
        """s0, f4 x4 (each 00), s0, p0: recorded right after a0 on a warm table
        and right after i0 on a cold one. The arm must report its resting place."""
        if self.state is None or (self.state == "cold" and not self.started):
            raise self._doubt("the follow-up asked for outside its recorded place (a bug)")
        self.busy += 1
        try:
            self.exchange("status")
            for _ in range(4):
                self.exchange("arm_mode")
            self.exchange("status")
            pos = self.position()
        finally:
            self.busy -= 1
        self.log("DATA", f"the arm reports {pos}")
        if not HOME_CLUSTER.contains(pos):
            raise self._doubt(
                f"the arm reports table position {pos}, not its resting place",
                f"The arm reports table position X {pos[0]}, Y {pos[1]}, which is not its "
                "resting place (X 1097 to 1107, Y -5 to 50). This program only goes on from "
                "there, so nothing more is sent.")
        self._stop_if_requested()
        return pos

    def home(self) -> "tuple[int, int]":
        """i1 right after the p0 that read the resting place (as recorded),
        then s0 and p0: the arm must report the homed position."""
        if self.homed or self.position_now is None or not HOME_CLUSTER.contains(self.position_now):
            raise self._doubt("i1 asked for while the arm is not known to be at rest (a bug)")
        self.busy += 1
        try:
            self.arrival_unknown = True
            self.heading_to = (1102, 0)
            self.position_now = None
            self.exchange("home", HOME_TIMEOUT)
            self.homed = True
            self.exchange("status")
            got = self.position()
        finally:
            self.busy -= 1
        self.log("DATA", f"after the homing the arm reports {got}")
        if not HOMED.contains(got):
            raise self._doubt(
                f"after the homing the arm reports {got}",
                f"After the homing the arm reports X {got[0]}, Y {got[1]}, a little different "
                "from what i1Profiler's table reported right after homing (Y 0 to 5). "
                + ("The arm is at its resting place. " if HOME_CLUSTER.contains(got) else "")
                + "Nothing more is sent.")
        self._stop_if_requested()
        return got

    def closing(self) -> None:
        """s0, f0, f3: i1Profiler's closing, recorded with the arm at rest and
        the motors holding it (S1 22.919-22.951, R2 361.579-361.611)."""
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
        try:
            try:
                self.dev.get_active_configuration()
            except USBError as exc:
                if "Configuration not set" not in str(exc):
                    raise
                self.dev.set_configuration()
            self._util.claim_interface(self.dev, 0)
            self._claimed = True
        except USBError as exc:
            raise TransportError(
                "The table could not be opened. Another program may be using it: "
                "i1Profiler, another copy of this program, or one of X-Rite's background "
                "services (for example X-Rite Device Services). Please quit i1Profiler and "
                "try again; if it still fails, send the log. Nothing was sent to the table. "
                f"({getattr(exc, 'strerror', None) or type(exc).__name__})") from None
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
NO_PYUSB = ("The real table needs the Python package pyusb and the libusb library: see "
            "'What to install' in the README, and start the program with venv/bin/python3 "
            "as shown there.")
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
                           "into the computer.")
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
