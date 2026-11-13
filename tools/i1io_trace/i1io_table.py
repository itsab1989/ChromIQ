# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The i1iO 2 table, as far as this test program talks to it.

Standard library only. pyusb is imported only when the REAL table is opened.

THE ONE RULE OF THIS FILE: the program can put exactly SEVEN different lines
on the wire, listed in :data:`WIRE`, and every one of them is a line that
X-Rite's i1Profiler sent to the tester's own table in his two recordings,
byte for byte (GitHub issue #129, recordings R1 and R2, decoded 2026-11-13).
There is no function that builds a command from numbers: the seven lines are
fixed at import and :func:`check_outgoing` refuses every other byte string.

Line format (the decode, held on all 2,475 recorded lines): host to table
``;`` + command id + arguments (lower-case hex) + checksum + CR; the table
answers every command with two lines, ``:!`` id checksum (accepted) at once and
``:$`` id status data checksum (done) when it has finished. The checksum is the
two's complement of the 8-bit sum of every character before it.

Table positions are in the table's own units (most likely 0.1 mm). Home, where
the arm rests over the white tile at the back of the table, is X 1102, Y 0;
Y grows towards the front of the table.
"""
from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass

TOOL_VERSION = "0.1.0"

VID, PID = 0x0971, 0x2004


class ForbiddenLine(Exception):
    """A line that is not one of the seven (a bug; it is never written)."""


class ProtocolError(Exception):
    """A reply that is not what the protocol says."""


class TransportError(Exception):
    """The USB link itself failed."""


class NotAvailable(Exception):
    """The real table cannot be opened on this computer (with the reason)."""


# ---- checksum and framing ------------------------------------------------------

def _short(raw: bytes) -> str:
    """Unexpected bytes are described, never copied whole into a message or the
    log: an unasked memory answer could hold the table's serial number."""
    return f"{len(raw)} bytes, starting {bytes(raw[:4])!r}"


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


# ---- THE SEVEN LINES ---------------------------------------------------------------

#: Everything this program can send. Each line is verbatim from the recordings
#: (where, in :data:`RECORDED_AT`); `tests/test_i1io_trace_tool.py` pins the bytes.
WIRE = {
    "status":   _frame("s0"),                    # ;s022
    "identity": _frame("a1"),                    # ;a133
    "arm_mode": _frame("f4"),                    # ;f42b
    "position": _frame("p0"),                    # ;p025
    "home":     _frame("i1"),                    # ;i12b
    # m0 X Y speed: X 0x044e = 1102, Y 0x00fa = 250, speed 0x012c = 300
    "out":      _frame("m0", "044e00fa012c"),    # ;m0044e00fa012c0e
    # m0 X Y speed: X 0x044e = 1102, Y 0x04b2 = 1202, speed 0x00c8 = 200
    "approach": _frame("m0", "044e04b200c8"),    # ;m0044e04b200c838
}

#: Where each line was recorded (seconds from the start of the recording).
RECORDED_AT = {
    "status":   "R1 84.051, R2 34.932 (at every open)",
    "identity": "R1 and R2, twice at every open (R2 34.546, 34.715)",
    "arm_mode": "R1 84.062, R2 34.940 (four times at every open)",
    "position": "R2 35.017 (just before the start-up homing), before nearly every move",
    "home":     "R2 35.033 from (1102, 47) at start-up; R1 85.848 from (1102, 1202)",
    "out":      "R1 197.917 from home (1102, 5), the first move out after a calibration",
    "approach": "R1 85.529, i1Profiler's start-up approach, right before its homing",
}

ALLOWED_LINES = frozenset(WIRE.values())

#: Data characters in the ':$' reply of each command id.
DATA_LEN = {"s0": 0, "a1": 10, "f4": 2, "p0": 8, "i1": 0, "m0": 0}


def check_outgoing(line: bytes) -> str:
    """THE GATE. Return the command id if *line* is exactly one of the seven
    lines; raise ForbiddenLine otherwise."""
    if not isinstance(line, (bytes, bytearray)) or bytes(line) not in ALLOWED_LINES:
        raise ForbiddenLine(f"not one of the seven allowed lines: {line!r}")
    return bytes(line)[1:3].decode("ascii")


# ---- replies -----------------------------------------------------------------------

@dataclass(frozen=True)
class Reply:
    cid: str
    status: int
    data: str          # upper-case hex as received

    def xy(self) -> "tuple[int, int]":
        x, y = int(self.data[:4], 16), int(self.data[4:8], 16)
        return (x - 0x10000 if x & 0x8000 else x, y - 0x10000 if y & 0x8000 else y)


_ACK_RE = re.compile(r":!([a-z][0-9])([0-9A-F]{2})")
_DONE_RE = re.compile(r":\$([a-z][0-9])([0-9A-F])([0-9A-F]*)([0-9A-F]{2})")


def parse_ack(line: str, cid: str) -> None:
    m = _ACK_RE.fullmatch(line)
    if not m or not checksum_ok(line):
        raise ProtocolError(f"expected the table's acceptance of {cid}, got {line!r}")
    if m.group(1) != cid:
        raise ProtocolError(f"acceptance for {m.group(1)} while waiting for {cid}: {line!r}")


def parse_done(line: str, cid: str) -> Reply:
    if not line.startswith(":$") or not checksum_ok(line):
        raise ProtocolError(f"expected the table's answer to {cid}, got {line!r}")
    m = _DONE_RE.fullmatch(line)
    if not m:
        raise ProtocolError(f"malformed answer to {cid}: {line!r}")
    if m.group(1) != cid:
        raise ProtocolError(f"answer for {m.group(1)} while waiting for {cid}: {line!r}")
    status, data = int(m.group(2), 16), m.group(3)
    if status == 0 and len(data) != DATA_LEN[cid]:
        raise ProtocolError(f"answer to {cid} has {len(data)} data characters, "
                            f"expected {DATA_LEN[cid]}: {line!r}")
    return Reply(cid, status, data)


# ---- places and the plan ---------------------------------------------------------------

@dataclass(frozen=True)
class Box:
    xmin: int
    xmax: int
    ymin: int
    ymax: int

    def contains(self, p) -> bool:
        return self.xmin <= p[0] <= self.xmax and self.ymin <= p[1] <= self.ymax


def around(x: int, y: int, tol: int = 10) -> Box:
    return Box(x - tol, x + tol, y - tol, y + tol)


#: The identity reply of the one table we know (constant at all four recorded
#: opens). It carries no serial number. Any other answer: nothing moves.
KNOWN_IDENTITY = "005D010702"

#: Where the arm rests: every recorded start and calibration found it at
#: X 1102, Y 0 to 47 (the reading creeps while it stands), plus 5 units of
#: jitter. The program starts only from here.
HOME_CLUSTER = Box(1097, 1107, -5, 50)

#: After a completed move the position must be this close to the target, per
#: axis (220 recorded moves: worst 4, median 1).
TOLERANCE = 10

#: Longest recorded: quick commands 0.21 s, m0 1.76 s, i1 4.02 s. These are
#: how long the program waits before it treats a missing answer as a fault.
QUICK_TIMEOUT = 1.0
MOVE_TIMEOUT = 8.0
HOME_TIMEOUT = 12.0

#: Before every command the program listens this long for anything unasked.
QUIET_CHECK_S = 0.05
#: The longest answer line to any of the seven lines (":$a1" + 10 + checksum).
LONGEST_REPLY = 17

#: After opening, the table must be silent this long before the first command.
DRAIN_QUIET_S = 1.0
DRAIN_SETTLE_S = 15.0
DRAIN_MAX_S = 60.0


@dataclass(frozen=True)
class Motion:
    """One step of the plan: a fixed line, where the arm must be before it
    (position and motors holding), and where it must be afterwards."""
    number: int
    key: str
    start: Box
    end: Box
    timeout: float
    what: str          # what the tester will see, in plain words
    seconds: str       # how long it took in the recordings
    recorded: str      # where i1Profiler made this same movement


#: THE PLAN. The whole of what the program can make the arm do, in this order,
#: each step only after the tester typed yes. Nothing else moves the arm.
PLAN = (
    Motion(1, "home", HOME_CLUSTER, HOME_CLUSTER, HOME_TIMEOUT,
           "The arm finds its exact resting place. It is already there, so it moves "
           "very little or not at all; you may hear the motors for a moment.",
           "0.3 s", "R2 35.033: the line ;i12b sent from (1102, 47), right after "
           "i1Profiler opened the table (also R2 378.632, R1 190.093)"),
    Motion(2, "out", HOME_CLUSTER, around(1102, 250), MOVE_TIMEOUT,
           "The arm moves about 25 mm (1 inch) straight towards the front of the "
           "table, away from its resting place, and stops.",
           "0.7 s", "R1 197.917: this same line sent from (1102, 5), the first move "
           "out from the resting place"),
    Motion(3, "approach", around(1102, 250), around(1102, 1202), MOVE_TIMEOUT,
           "The arm moves about 95 mm (3.7 inches) further towards the front of the "
           "table, in a straight line, and stops about 12 cm from its resting place.",
           "1.4 s", "R1 84.153 to 85.529: i1Profiler's start-up approach sent the arm "
           "from Y 317 to Y 1202 and then to exactly this place with this same line; "
           "this step starts 7 mm nearer the resting place and 4 mm to the side"),
    Motion(4, "home", around(1102, 1202), HOME_CLUSTER, HOME_TIMEOUT,
           "The arm goes back to its resting place at the back of the table by itself.",
           "1.6 s", "R1 85.848: the line ;i12b sent from (1102, 1202), right after "
           "this same approach"),
)

#: A hard cap, checked on every write: no run can make more motions than the plan has.
MAX_MOTIONS = len(PLAN)
#: A hard cap on lines of any kind (the full plan sends 25).
MAX_LINES = 40

MOTION_KEYS = frozenset({"home", "out", "approach"})


# ---- the session ------------------------------------------------------------------------

class Doubt(Exception):
    """Something was not as expected. From now on NOTHING more is sent."""


class Stopped(Exception):
    """The tester stopped the run. From now on NOTHING more is sent."""


class Table:
    """One command at a time over a transport; every reply checked.

    After the first doubt or stop, :attr:`closed_reason` is set and every
    further write is refused before it reaches the transport: the program
    never sends anything to "tidy up" (no homing, no stop, no reset)."""

    def __init__(self, transport, log=None):
        self.t = transport
        self._log = log or (lambda kind, text: None)
        self._buf = b""
        self.closed_reason: "str | None" = None
        self.lines_sent = 0
        self.motions_sent = 0
        self.busy = 0                 # >0 while an exchange or a motion step runs
        self.stop_requested = False
        self.position_now: "tuple[int, int] | None" = None

    # ---- logging and stopping ------------------------------------------------------
    def log(self, kind: str, text: str) -> None:
        self._log(kind, f"{self.t.now():10.3f}  {text}")

    def request_stop(self) -> None:
        """From a signal handler while busy: stop once the current step is done."""
        self.stop_requested = True

    def close_for_sending(self, reason: str) -> None:
        if self.closed_reason is None:
            self.closed_reason = reason
            self.log("STOP", f"nothing more is sent: {reason}")

    def _doubt(self, reason: str) -> Doubt:
        self.close_for_sending(reason)
        return Doubt(reason)

    # ---- the wire ---------------------------------------------------------------------
    def _write(self, line: bytes) -> str:
        """The ONLY place that writes to the transport."""
        if self.closed_reason is not None:
            raise Doubt(f"not sending: {self.closed_reason}")
        cid = check_outgoing(line)
        if self.lines_sent >= MAX_LINES:
            raise self._doubt("the program reached its limit of lines for one run")
        is_motion = line in (WIRE["home"], WIRE["out"], WIRE["approach"])
        if is_motion and self.motions_sent >= MAX_MOTIONS:
            raise self._doubt("the program reached its limit of motions for one run")
        self.lines_sent += 1
        if is_motion:
            self.motions_sent += 1
        self.log("SEND", line.decode("ascii").rstrip("\r"))
        self.t.write(bytes(line))
        return cid

    def _read_line(self, deadline: float) -> str:
        while b"\r" not in self._buf:
            left = deadline - self.t.now()
            if left <= 0:
                raise TimeoutError
            self._buf += self.t.read(min(left, 0.25))
        raw, self._buf = self._buf.split(b"\r", 1)
        try:
            line = raw.decode("ascii")
        except UnicodeDecodeError:
            raise ProtocolError(f"non-text bytes from the table ({_short(raw)})") from None
        if not line.isprintable():
            raise ProtocolError(f"unexpected characters from the table ({_short(raw)})")
        if len(raw) > LONGEST_REPLY:
            raise ProtocolError(f"a reply longer than any the program asks for ({_short(raw)})")
        self.log("RECV", line)
        return line

    def _quiet_check(self) -> None:
        """Before every command the table must have nothing more to say: an
        extra or late line means the conversation is out of step."""
        try:
            self._buf += self.t.read(QUIET_CHECK_S)
        except TransportError as exc:
            raise self._doubt(f"the USB link failed: {exc}") from None
        if self._buf:
            raise self._doubt(f"the table sent something nobody asked for ({_short(self._buf)})")

    def exchange(self, key: str, timeout: float) -> Reply:
        """Send WIRE[key], read its two answers. Any fault closes the session."""
        line = WIRE[key]
        if self.closed_reason is not None:
            raise Doubt(f"not sending: {self.closed_reason}")
        self.busy += 1
        try:
            self._quiet_check()
            cid = self._write(line)
            start = self.t.now()
            parse_ack(self._read_line(start + QUICK_TIMEOUT), cid)
            reply = parse_done(self._read_line(start + timeout), cid)
        except TimeoutError:
            raise self._doubt(f"no answer to {cid} within the expected time") from None
        except ProtocolError as exc:
            raise self._doubt(str(exc)) from None
        except TransportError as exc:
            raise self._doubt(f"the USB link failed: {exc}") from None
        except (Doubt, ForbiddenLine):
            self.close_for_sending("an internal check refused a line")
            raise
        except BaseException as exc:
            # anything else after the write (a bug, an interrupt that got
            # through): the answer may still be on its way, so nothing more
            self.close_for_sending(f"an unexpected error: {exc!r}")
            raise
        finally:
            self.busy -= 1
        if reply.status != 0:
            raise self._doubt(f"the table answered {cid} with status {reply.status}, which "
                              "it never did in the recordings")
        return reply

    def drain(self) -> None:
        """Before the first command the table must be silent. Bytes that arrive
        unasked (an old answer after a crash) are counted, never printed in
        full, and the program waits for DRAIN_SETTLE_S of silence."""
        start = last = self.t.now()
        quiet = DRAIN_QUIET_S
        while True:
            try:
                chunk = self.t.read(0.25)
            except TransportError as exc:
                raise self._doubt(f"the USB link failed: {exc}") from None
            now = self.t.now()
            if chunk:
                ids = sorted(set(re.findall(rb":[!$]([a-z][0-9])", chunk)))
                self.log("DRAIN", f"{len(chunk)} unasked bytes after opening, answers to "
                                  f"{[i.decode() for i in ids]}")
                last, quiet = now, DRAIN_SETTLE_S
            elif now - last >= quiet:
                return
            if now - start > DRAIN_MAX_S:
                raise self._doubt("the table keeps sending without being asked")

    # ---- reads ------------------------------------------------------------------------
    def status(self) -> None:
        self.exchange("status", QUICK_TIMEOUT)

    def identity(self) -> str:
        return self.exchange("identity", QUICK_TIMEOUT).data

    def arm_mode(self) -> str:
        return self.exchange("arm_mode", QUICK_TIMEOUT).data

    def position(self) -> "tuple[int, int]":
        p = self.exchange("position", QUICK_TIMEOUT).xy()
        self.position_now = p
        return p

    def _stop_if_requested(self) -> None:
        if self.stop_requested:
            self.close_for_sending("stopped by you")
            raise Stopped("stopped by you")

    # ---- the opening checks -------------------------------------------------------
    def open_checks(self) -> "tuple[int, int]":
        """The read-only opening, as i1Profiler's: s0, a1 twice, f4, p0. Raises
        Doubt (nothing moves, nothing more is sent) unless it is the table we
        know, its motors hold the arm and the arm is at its resting place."""
        self.busy += 1
        try:
            self.drain()
            self.status()
            for _ in range(2):
                ident = self.identity()
                if ident != KNOWN_IDENTITY:
                    raise self._doubt(
                        f"the table identified itself as {ident}, not as the one table this "
                        f"program was made from ({KNOWN_IDENTITY})")
            mode = self.arm_mode()
            if mode != "00":
                raise self._doubt(f"the arm is not held by its motors (mode {mode}); "
                                  "i1Profiler never started like that")
            pos = self.position()
            if not HOME_CLUSTER.contains(pos):
                raise self._doubt(f"the arm reports table position {pos}, not its resting "
                                  "place; this program only starts from there")
        finally:
            self.busy -= 1
        self._stop_if_requested()
        return pos

    # ---- one motion -----------------------------------------------------------------
    def motion(self, step: Motion) -> "tuple[int, int]":
        """f4 and p0 first (motors holding, arm where the step starts), then the
        step's fixed line, then p0 and f4 again (arrived, still held). A stop
        asked for during the step is honoured after it, never in the middle."""
        if step.key not in MOTION_KEYS or step not in PLAN:
            raise self._doubt(f"not a step of the plan: {step!r}")
        self.busy += 1
        try:
            mode = self.arm_mode()
            if mode != "00":
                raise self._doubt(f"the arm is not held by its motors (mode {mode})")
            here = self.position()
            if not step.start.contains(here):
                raise self._doubt(f"step {step.number} starts only from its own place, and "
                                  f"the arm reports {here}")
            if self.stop_requested:
                self._stop_if_requested()
            self.exchange(step.key, step.timeout)
            got = self.position()
            if not step.end.contains(got):
                raise self._doubt(f"after step {step.number} the arm reports {got}, not where "
                                  "it was sent: something may be in its way")
            mode = self.arm_mode()
            if mode != "00":
                raise self._doubt(f"after step {step.number} the motors no longer hold the "
                                  f"arm (mode {mode})")
        finally:
            self.busy -= 1
        self._stop_if_requested()
        return got


# ---- the real table: FTDI over USB ------------------------------------------------------

def strip_ftdi(packet: bytes) -> bytes:
    """FTDI puts two status bytes before every 64-byte packet's payload."""
    return b"".join(packet[i + 2:i + 64] for i in range(0, len(packet), 64))


#: FTDI line-status bits that mean bytes were lost or damaged on the serial
#: side: overrun 0x02, parity 0x04, framing 0x08, break 0x10, RX FIFO 0x80.
#: The recordings only ever showed 0x60 and 0x00.
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


class FtdiUsb(Transport):
    """The real table through pyusb + libusb, set up exactly as i1Profiler
    does it (recorded at every open): FTDI reset, purge RX, purge TX, 57600
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
        # pyusb before 1.2: a USBError with ETIMEDOUT (60 on macOS, 110 on Linux)
        return getattr(exc, "errno", None) in (60, 110)

    def setup(self) -> None:
        USBError = self._core.USBError
        try:
            try:
                self.dev.get_active_configuration()
            except USBError:
                self.dev.set_configuration()      # only if not configured yet
            self._util.claim_interface(self.dev, 0)
            self._claimed = True
        except USBError as exc:
            raise TransportError(
                "The table could not be opened. Another program may be using it "
                "(i1Profiler, or another copy of this program); please quit it and try "
                f"again. ({getattr(exc, 'strerror', None) or type(exc).__name__})") from None
        try:
            for req, val, idx in self.SETUP:
                self.dev.ctrl_transfer(0x40, req, val, idx, None, 1000)
        except USBError as exc:
            raise TransportError(f"could not set up the table's USB link "
                                 f"({getattr(exc, 'strerror', None) or type(exc).__name__})") from None

    def write(self, data: bytes) -> None:
        check_outgoing(data)                       # the gate, once more, at the wire
        try:
            n = self.dev.write(self.EP_OUT, data, 1000)
        except self._core.USBError as exc:
            raise TransportError(f"USB write failed ({getattr(exc, 'strerror', None) or exc})") from None
        if n != len(data):
            raise TransportError(f"USB write sent {n} of {len(data)} bytes")

    def read(self, timeout: float) -> bytes:
        try:
            raw = bytes(self.dev.read(self.EP_IN, 64, max(1, int(timeout * 1000))))
        except self._core.USBError as exc:
            if self._is_timeout(exc):
                return b""
            raise TransportError(f"USB read failed ({getattr(exc, 'strerror', None) or exc})") from None
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
    sent to it (not even the FTDI set-up): FTDI chip revision 0x0400, one
    interface of class ff/ff/ff with bulk IN 0x81 and bulk OUT 0x02 of 64
    bytes. Reads cached descriptors only; never the serial-number string."""
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
    except Exception as exc:          # a descriptor we cannot read is a mismatch
        problems.append(f"could not read its descriptors ({type(exc).__name__})")
    if problems:
        raise NotAvailable("The device with the i1iO's USB id does not look like the i1iO 2 "
                           "this program was made from (" + "; ".join(problems) + "). "
                           "Nothing was sent to it.")


#: Where Homebrew puts libusb (Apple silicon, then Intel). macOS's own Python
#: does not look there by itself.
LIBUSB_PATHS = ("/opt/homebrew/lib/libusb-1.0.dylib", "/usr/local/lib/libusb-1.0.dylib")


def libusb_backend(libusb1):
    """pyusb's libusb 1.0 backend: the library pyusb finds by itself, else
    Homebrew's. Loading the library touches no device."""
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


def open_table() -> FtdiUsb:
    """Find and open the table, or raise NotAvailable. Sends no table command;
    only the FTDI set-up after the descriptor check."""
    if sys.platform == "win32":
        raise NotAvailable(
            "On Windows, X-Rite's own driver owns the i1iO, and this test program cannot "
            "open it next to that driver. Please run it on a Mac instead.")
    try:
        import usb.backend.libusb1
        import usb.core
        import usb.util
    except ImportError:
        raise NotAvailable(
            "The real table needs the Python package pyusb and the libusb library: "
            "see 'What to install' in the README. (Without --real nothing is needed.)") from None
    backend = libusb_backend(usb.backend.libusb1)
    if backend is None:
        raise NotAvailable("pyusb is installed but finds no libusb library. "
                           "On a Mac: 'brew install libusb'.")
    try:
        found = list(usb.core.find(find_all=True, idVendor=VID, idProduct=PID, backend=backend))
    except usb.core.NoBackendError:
        raise NotAvailable("pyusb is installed but finds no libusb library. "
                           "On a Mac: 'brew install libusb'.") from None
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
    except TransportError:
        t.close()
        raise
    return t


def usb_summary(t) -> str:
    """For the log: USB id and chip revision. Never the serial number."""
    dev = getattr(t, "dev", None)
    if dev is None:
        return "simulated table"
    return f"USB {VID:04x}:{PID:04x}, bcdDevice {getattr(dev, 'bcdDevice', 0):04x}"
