# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The i1iO 2 table, as far as the session test program talks to it.

Standard library only. pyusb is imported only when the REAL table is opened.

THE ONE RULE OF THIS FILE: the program can put exactly SIXTEEN different lines on
the wire, listed in :data:`WIRE` (with where each was recorded in :data:`RECORDED_AT`
and in BYTES.md beside this file). Every one is a line X-Rite's i1Profiler sent to the
tester's own i1iO 2, byte for byte: eleven from opening, homing and closing the table,
four moves (m0) whose targets and speed are recorded, and f1 (the hand-alignment mode
that lets the arm go). There is no function that builds a command from numbers: the
lines are fixed at import and :func:`check_outgoing` refuses every other byte string.

The lines are sent only inside STEPS (:data:`STEPS`): fixed sequences, each a list of
operations, chosen and confirmed one by one by the person beside the table. A step is
removed by deleting its entry; the caps follow from the list. Never in this package:
memory or configuration writes, any line never seen in a recording (i0, m1, m2, p1,
c3, c4, d1, a3, every u8 other than the two reads), any target the arm was not driven
to in a recording, any speed not recorded, and every line that occurs only between
"arm at a patch" and "reading" in the recordings.

Line format (held on every recorded line): host to table ``;`` + command id + arguments
(lower-case hex) + checksum + CR; the table answers ``:!`` id checksum (accepted) at
once and ``:$`` id status data checksum when done, or ``:#`` id code checksum when it
refuses. The checksum is the two's complement of the 8-bit sum of the characters
before it. Positions are table units of 0.1 mm; the resting place is X 1102, Y 0.
"""
from __future__ import annotations

import re
import signal
import sys
import time
from dataclasses import dataclass

TOOL_NAME = "chromiq-i1io-session"
TOOL_VERSION = "0.3.1"

VID, PID = 0x0971, 0x2004


class ForbiddenLine(Exception):
    """A line that is not one of the sixteen (a bug; it is never written)."""


class ProtocolError(Exception):
    """A reply that is not what the recordings show."""


class TableRefused(ProtocolError):
    """The table answered ``:#`` + id + code: it refused the command (seen once on the
    tester's table, never in the recordings)."""

    def __init__(self, cid: str, code: int, line: str):
        super().__init__(f"the table refused {cid} with code {code} ({line!r})")
        self.cid, self.code = cid, code


class TransportError(Exception):
    """The USB link itself failed."""


class NotAvailable(Exception):
    """The real table cannot be opened on this computer (with the reason)."""


class TableBusy(TransportError):
    """macOS did not let the program open the table: another program holds it (libusb
    ACCESS or BUSY while opening or claiming it). Nothing was sent."""

    def __init__(self, message: str, step: str, code):
        super().__init__(message)
        self.step, self.code = step, code


# ---- checksum and framing ------------------------------------------------------

def _short(raw: bytes) -> str:
    """Unexpected bytes are described, never copied whole (a memory answer holds the
    table's serial number)."""
    return f"{len(raw)} bytes, starting {bytes(raw[:4])!r}"


ECHO_MAX = 24


def show(line: str) -> str:
    if len(line) <= ECHO_MAX and line.isprintable() and not line.startswith(":$u8"):
        return repr(line)
    return _short(line.encode("ascii", "replace"))


def checksum(body: str) -> str:
    return f"{(-sum(body.encode('ascii'))) & 0xFF:02x}"


def checksum_ok(line: str) -> bool:
    if len(line) < 3 or not re.fullmatch(r"[0-9A-Fa-f]{2}", line[-2:]):
        return False
    return (sum(line[:-2].encode("ascii", "replace")) + int(line[-2:], 16)) & 0xFF == 0


def _frame(cid: str, args: str = "") -> bytes:
    body = ";" + cid + args
    return (body + checksum(body) + "\r").encode("ascii")


# ---- THE SIXTEEN LINES -----------------------------------------------------------

WIRE = {
    "identity":  _frame("a1"),                     # ;a133
    "k2":        _frame("k2"),                     # ;k228
    "memory_a":  _frame("u8", "000060000100"),     # ;u8000060000100d1   (a READ)
    "memory_b":  _frame("u8", "000061000068"),     # ;u8000061000068c3   (a READ)
    "a0":        _frame("a0"),                     # ;a034
    "status":    _frame("s0"),                     # ;s022
    "arm_mode":  _frame("f4"),                     # ;f42b
    "position":  _frame("p0"),                     # ;p025
    "home":      _frame("i1"),                     # ;i12b
    "f0":        _frame("f0"),                     # ;f02f
    "f3":        _frame("f3"),                     # ;f32c
    "to_250":    _frame("m0", "044e00fa012c"),     # ;m0044e00fa012c0e  to (1102, 250) at 300
    "to_1000":   _frame("m0", "03e805dc012c"),     # ;m003e805dc012c06  to (1000, 1500) at 300
    "to_1498":   _frame("m0", "044e05da012c"),     # ;m0044e05da012c0b  to (1102, 1498) at 300
    "to_2507":   _frame("m0", "09cb05da012c"),     # ;m009cb05da012cda  to (2507, 1498) at 300
    "free":      _frame("f1"),                     # ;f12e  hand-alignment mode (arm free)
}

RECORDED_AT = {
    "identity": "every open: S1 1.141/1.311; R2 34.546/34.715, 378.147/378.314; R1 83.666",
    "k2":       "every open, right after the second a1: S1 1.327; R2 34.731, 378.331",
    "memory_a": "every open, right after k2: S1 1.343; R2 34.747, 378.347",
    "memory_b": "every open, right after the first u8: S1 1.450; R2 34.853, 378.453",
    "a0":       "every open: S1 1.502 (111800, cold); R2 34.906, 378.505 (130000, warm)",
    "status":   "R2 34.932, 378.530 after a0; S1 4.766, R2 35.003, 268.621 before the p0 of a "
                "homing; R2 265.659, 268.909 after a homing; R2 427.359/427.389 after a move; "
                "S1 22.919, R2 361.579 before f0",
    "arm_mode": "R2 34.940-34.985 and 378.539-378.585 (00); R2 424.993/425.006 before the "
                "way out (00); S2 3.909-3.999 around f3 (00); S2 4.033/4.048 after f1 (01); "
                "R2 256.592-256.638 before the cancel (01)",
    "position": "R2 35.017, 378.617 before the homing; R2 425.026 before the way out; R2 "
                "427.445 at (1000, 1500); R2 261.628 on the free arm before the cancel",
    "home":     "at rest from Y 14..47 (S1 4.796; R2 35.033, 134.274, 268.653, 378.632, "
                "417.181; R1 190.093) and Y 0..2 (R1 190.412; R2 134.610, 417.453); from held "
                "positions on the table (S2 179.201, 371.169, 497.615, 586.887, 769.808; R1 "
                "338.379, 546.843, 740.993; R2 706.049; from (1102, 1202) R1 85.848); from the "
                "free arm after f1 (R2 261.644 status 0, 4.01 s; R1 272.124 status 3)",
    "f0":       "the close, after s0: S1 22.935, R2 361.594; R1 0.017",
    "f3":       "right after f0 in the close: S1 22.951, R2 361.611; before f1 at every "
                "alignment: S2 3.957, R1 202.158, R2 146.302",
    "to_250":   "from rest right after p0: R2 425.038 from (1102, 4), R2 142.056, R1 197.917; "
                "0.719-0.720 s",
    "to_1000":  "right after to_250: R2 425.758, R2 142.775, R1 198.637; 1.599 s",
    "to_1498":  "from rest right after p0: R1 398.217, 713.401; S2 267.330, 379.924, 523.418, "
                "680.534 (from Y 29..37), 1.727-1.728 s",
    "to_2507":  "right after to_1498: R1 399.945, 715.129; S2 1.792, 269.057, 381.652, "
                "525.146, 682.262; 1.695 s",
    "free":     "at every alignment, after s0 f4 f4 f3 f4 f4: S2 4.018 (answer 01; f4 then "
                "reads 01), R1 202.217, 402.173, 717.356, R2 146.366, 429.355; 10 in all",
}

ALLOWED_LINES = frozenset(WIRE.values())
MOTION_KEYS = frozenset({"home", "to_250", "to_1000", "to_1498", "to_2507"})
MOTION_LINES = frozenset(WIRE[k] for k in MOTION_KEYS)
SECRET_KEYS = frozenset({"memory_a", "memory_b"})

DATA_LEN = {"identity": 10, "k2": 14, "memory_a": 512, "memory_b": 208, "a0": 6,
            "status": 0, "arm_mode": 2, "position": 8, "home": 0, "f0": 2, "f3": 2,
            "to_250": 0, "to_1000": 0, "to_1498": 0, "to_2507": 0, "free": 2}
EXACT_DATA = {"identity": "005D010702", "k2": "0B600000000013", "f0": "00", "f3": "00",
              "free": "01"}
#: f4's recorded answers: 00, and 01 only after f1 (each step says which it expects).
F4_VALUES = ("00", "01")
MEMORY_A_START = "6801000056312E31"
A0_COLD = "111800"
A0_WARM = "130000"


def _key_of(line: bytes) -> str:
    return next(k for k, v in WIRE.items() if v == bytes(line))


def check_outgoing(line: bytes) -> str:
    """THE GATE. The command id if *line* is exactly one of the sixteen lines;
    ForbiddenLine otherwise."""
    if not isinstance(line, (bytes, bytearray)) or bytes(line) not in ALLOWED_LINES:
        raise ForbiddenLine(f"not one of the sixteen allowed lines: {line!r}")
    return bytes(line)[1:3].decode("ascii")


# ---- replies -----------------------------------------------------------------------

@dataclass(frozen=True)
class Reply:
    cid: str
    status: int
    data: str

    def xy(self) -> "tuple[int, int]":
        x, y = int(self.data[:4], 16), int(self.data[4:8], 16)
        return (x - 0x10000 if x & 0x8000 else x, y - 0x10000 if y & 0x8000 else y)


_ACK_RE = re.compile(r":!([a-z][0-9])([0-9A-F]{2})")
_REFUSED_RE = re.compile(r":#([a-z][0-9])([0-9A-F])([0-9A-F]{2})")
_DONE_RE = re.compile(r":\$([a-z][0-9])([0-9A-F])([0-9A-F]*)([0-9A-F]{2})")
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
        raise ProtocolError(f"the table answered {cid} with status {status}, which it did not "
                            "do in the recordings for this line in this place")
    if len(data) != DATA_LEN[key]:
        raise ProtocolError(f"answer to {cid} has {len(data)} data characters, expected "
                            f"{DATA_LEN[key]}")
    if key in EXACT_DATA and data != EXACT_DATA[key]:
        raise ProtocolError(f"the table answered {cid} with {data}, not with the recorded "
                            f"{EXACT_DATA[key]}")
    if key == "arm_mode" and data not in F4_VALUES:
        raise ProtocolError(f"the table answered f4 with {data}; recorded are only 00 and 01")
    if key == "memory_a" and not data.startswith(MEMORY_A_START):
        raise ProtocolError("the table's memory block does not start as recorded")
    if key == "a0" and data not in (A0_COLD, A0_WARM):
        raise ProtocolError(f"the table answered a0 with {data}; the recordings only show "
                            f"{A0_COLD} (just switched on) and {A0_WARM} (started)")
    if key in SECRET_KEYS:
        data = ""
    return Reply(cid, status, data)


def done_max_len(key: str) -> int:
    return 2 + 2 + 1 + DATA_LEN[key] + 2


# ---- places, times ------------------------------------------------------------------

@dataclass(frozen=True)
class Box:
    xmin: int
    xmax: int
    ymin: int
    ymax: int

    def contains(self, p) -> bool:
        return self.xmin <= p[0] <= self.xmax and self.ymin <= p[1] <= self.ymax

    def text(self) -> str:
        return f"X {self.xmin} to {self.xmax}, Y {self.ymin} to {self.ymax}"


#: Where i1Profiler sent i1 from at rest (X 1102; Y 14..47 first homings, 0..2 second).
RECORDED_REST_STARTS = ((1102, 14), (1102, 22), (1102, 24), (1102, 24), (1102, 32),
                        (1102, 36), (1102, 47), (1102, 0), (1102, 2), (1102, 2))
#: The recorded starts plus one unit: a homing from here is as recorded.
REST_RECORDED = Box(1101, 1103, -1, 48)
#: The session's homing guard (the owner's ruling of 15 Nov 2026 allows a start close to
#: a recorded one): up to Y 80 (8 mm), on the home line X 1101..1103. It was Y 120 in the
#: reviewed eb38ba20b; the independent safety review (S1) asked for 80, because the largest
#: reading of an arm at rest ever seen is Y 55 (0.2.1). Why a step beyond 47 at all: the line
#: X 1102, Y 0..250 is driven by the recorded move to (1102, 250) and Y 0..1498 by the
#: recorded move to (1102, 1498), so the arm travels it under motor in the recordings; i1 is
#: recorded from Y 47 (at rest) and from Y 1202 on X 1102 (R1 85.848, after a move); the
#: only near-home start i1Profiler did NOT home from directly was (1058, 317), 44 units off
#: the line and 317 out. The same box is the check at rest before every homing from rest
#: (every step's first homing, the second homing, the free-arm homing).
REST_GUARD = Box(1101, 1103, -1, 80)
#: 0.3.1: the guard for the FIRST homing of a step (HOME_FIRST), from wherever the arm stands
#: after i1Profiler was quit. In 0.3.0 the tester's arm read (1104, 110) and (1101, 97) there,
#: twice, after our own touch question had pushed the free arm outwards; nothing moved. This
#: box is a step beyond the recordings, chosen from them: i1Profiler homed directly from rest
#: at X 1102, Y 0..47, and drove the arm under motor along X 1102 from rest to Y 250 (the
#: recorded m0 to (1102, 250)); it homed from held positions farther out ((1102, 1202),
#: (1172, 1663)) and from a free arm ((1050, 1492)). Y stops at 250, the recorded target on that
#: line, so the one place where i1Profiler drove out first, (1058, 317), stays outside: 67
#: units (6.7 mm) beyond Y 250 and 32 units (3.2 mm) left of X 1090. X 1090..1115 is about
#: 1.2 mm either side of 1102. The checks at rest after a homing (HOME_AND_CHECK, the free arm)
#: keep REST_GUARD.
START_GUARD = Box(1090, 1115, -1, 250)
#: Where a recorded move out from rest started (Y 4..6 after a double homing, 29..41 at a
#: session start), plus one unit: the moves out are sent only from here.
OUT_START = Box(1101, 1103, -1, 48)


def near(x: int, y: int, d: int = 5) -> Box:
    return Box(x - d, x + d, y - d, y + d)


AT_250 = near(1102, 250)
AT_1000 = near(1000, 1500)
AT_1498 = near(1102, 1498)
AT_2507 = near(2507, 1498)

QUICK_TIMEOUT = 1.0
#: Time windows (seconds from the line to its done-answer) for every movement, from the
#: recorded times, widened; outside: nothing more is sent.
#:   home_rest    i1 from REST_RECORDED: recorded 0.047-0.352 s; limit 0.6 (as 0.2.x)
#:   home_wide    i1 from REST_GUARD outside REST_RECORDED (Y 49..80): predicted 0.36-0.48 s
#:                (0.17 + 0.0039 s per unit, fitted to the recorded at-rest homings); limit 1.1
#:   home_far     0.3.1: i1 from START_GUARD outside REST_GUARD (up to Y 250): predicted up
#:                to 1.15 s; limit 2.0 (1.7 times the longest prediction)
#:   home_table   i1 from a held position out on the table: recorded 1.60-4.01 s
#:   home_free    i1 from the free arm at rest (after f1): from rest never recorded; from
#:                the free arm far out 2.36 and 4.01 s; 0.3.1 (re-check C1): the check before it
#:                uses START_GUARD (a sideways wiggle may move the free arm a little), limit 2.0
#:   to_250       recorded 0.719-0.720 s
#:   to_1000      recorded 1.599 s
#:   to_1498      recorded 1.727-1.728 s from Y 29..37 (here from Y -1..48)
#:   to_2507      recorded 1.695 s
#:   back_1498    to_1498 sent from (2507, 1498): the recorded to_2507 path backwards, same
#:                distance: 1.695 s expected
TIME_WINDOW = {"home_rest": (0.0, 0.6), "home_wide": (0.0, 1.1), "home_far": (0.0, 2.0), "home_table": (1.0, 6.0),
               "home_free": (0.0, 2.0), "to_250": (0.55, 1.2), "to_1000": (1.35, 2.4),
               "to_1498": (1.40, 2.4), "to_2507": (1.40, 2.4), "back_1498": (1.40, 2.4)}
MOVE_TIMEOUT = {"home_rest": 12.0, "home_wide": 12.0, "home_far": 12.0, "home_table": 15.0, "home_free": 12.0,
                "to_250": 4.0, "to_1000": 6.0, "to_1498": 6.0, "to_2507": 6.0,
                "back_1498": 6.0}
MIN_READ_S = 0.05
QUIET_CHECK_S = 0.05
DRAIN_QUIET_S = 1.0
DRAIN_SETTLE_S = 15.0
DRAIN_MAX_S = 60.0


# ---- THE STEPS ------------------------------------------------------------------------

#: The homing every step starts with: i1Profiler's own "s0 p0 i1 s0" (after the opening:
#: R2 35.003-35.385; after a previous homing: R2 265.659-268.909 "s0 s0 p0 i1 s0").
HOME_FIRST = (("x", "status"), ("p0", "START_GUARD", "right before the homing"),
              ("home_rest",), ("x", "status"))
#: Back home from out on the table, then the recorded check at home and the second
#: homing (R2 265.659-268.909 after a homing from the table).
HOME_AND_CHECK = (("x", "status"), ("x", "status"), ("p0", "REST_GUARD", "back home"),
                  ("home_rest",), ("x", "status"))
ARRIVE = (("x", "status"), ("x", "status"), ("f4", "00"), ("f4", "00"))


@dataclass(frozen=True)
class Step:
    key: str            # short name typed nowhere; used in the log and the tests
    title: str
    needs: "tuple[str, ...]"   # the session states it may start from
    leaves: str         # the state it leaves when it completes
    ops: tuple
    risk: str           # "low" or "medium"
    explain: str
    beyond: str         # what is not exactly as recorded


STEPS = (
    Step("home", "Send the arm to its resting place once",
         ("warm", "homed"), "homed", HOME_FIRST, "low",
         "The arm is sent to its resting place, where it already is or nearly is: usually it "
         "moves a few millimetres, for about a third of a second, and at most 25 mm, for "
         "about a second. This is what i1Profiler does right after it opens the table.",
         "i1Profiler sent this homing only from X 1102, Y 0 to 47; this program also sends it "
         "from X 1090 to 1115 and Y up to 250 (up to 25 mm out, about 1 mm to either side of "
         "the home line), the stretch i1Profiler drove the arm along under motor in your "
         "recordings. From 25 mm out it should take about 1.2 s; it is stopped if it takes "
         "longer than 2 s. If the arm stands even farther out, nothing moves."),
    Step("near", "Drive out about 15 cm along i1Profiler's way to an alignment, and back home",
         ("warm", "homed"), "homed",
         HOME_FIRST + (("f4", "00"), ("f4", "00"), ("p0", "OUT_START", "before driving out"),
                       ("move", "to_250", "to_250"),
                       ("p0", "AT_250", "after the first move"),
                       ("move", "to_1000", "to_1000")) + ARRIVE
         + (("p0", "AT_1000", "after driving out"), ("move", "home", "home_table"))
         + HOME_AND_CHECK, "medium",
         "After a homing, the arm drives out from its resting place 25 mm straight ahead, then "
         "on to a point 10 mm to the side and 150 mm out (table position X 1000, Y 1500), in "
         "about 0.7 s and 1.6 s, exactly the two moves i1Profiler makes before it asks you to "
         "align a chart. The program checks that the arm arrived, then sends it home (about "
         "2 to 4 seconds), checks that it is at rest and sends it home once more, as "
         "i1Profiler does.",
         "In the recordings these two moves always came 7.5 s after an i1Pro 2 calibration on "
         "the tile; here they come right after the homing, and the program asks where the "
         "arm is between them (i1Profiler sent them back to back) so that it stops if the "
         "first did not arrive. i1Profiler never sent the arm home from exactly this point. "
         "With the motors holding the arm, the closest recorded homing nearer home started at "
         "X 1102, Y 1202 (about 3 cm from this point); the nearest one of all started at "
         "X 1172, Y 1663 (about 2.4 cm away, farther out). The other recorded homings with the "
         "arm held started farther out."),
    Step("straight", "Drive straight out about 15 cm and back home",
         ("warm", "homed"), "homed",
         HOME_FIRST + (("f4", "00"), ("f4", "00"), ("p0", "OUT_START", "before driving out"),
                       ("move", "to_1498", "to_1498")) + ARRIVE
         + (("p0", "AT_1498", "after driving out"), ("move", "home", "home_table"))
         + HOME_AND_CHECK, "medium",
         "After a homing, the arm drives straight out from its resting place by 150 mm "
         "(table position X 1102, Y 1498) in about 1.7 s: the first move i1Profiler made at "
         "the start of the seven measuring sessions in your recordings that began without a "
         "calibration (after a calibration it used the way out of step 2). The program checks "
         "that it arrived and sends it home (about 2 to 3 seconds), then checks it at rest and "
         "sends it home once more.",
         "i1Profiler followed this move with a second move, never with a homing. With the "
         "motors holding the arm, the closest recorded homing nearer home started at X 1102, "
         "Y 1202, on this same line about 3 cm nearer home; the nearest one of all started at "
         "X 1172, Y 1663 (about 1.8 cm away, farther out)."),
    Step("across", "Drive out 15 cm, across 14 cm to the far side, back, and home",
         ("warm", "homed"), "homed",
         HOME_FIRST + (("f4", "00"), ("f4", "00"), ("p0", "OUT_START", "before driving out"),
                       ("move", "to_1498", "to_1498"),
                       ("p0", "AT_1498", "after the first move"),
                       ("move", "to_2507", "to_2507")) + ARRIVE
         + (("p0", "AT_2507", "at the far side"), ("move", "to_1498", "back_1498"))
         + ARRIVE + (("p0", "AT_1498", "back on the home line"),
                     ("move", "home", "home_table")) + HOME_AND_CHECK, "medium",
         "After a homing, the arm drives straight out by 150 mm (about 1.7 s), then sideways "
         "by 140 mm to table position X 2507, Y 1498 (about 1.7 s), exactly the two moves "
         "i1Profiler made at the start of the seven measuring sessions in your recordings that "
         "began without a calibration. The program checks that "
         "it arrived, drives it back the same way to X 1102, Y 1498, checks again, and sends "
         "it home (about 2 to 3 seconds), then checks it at rest and homes once more.",
         "The way back to X 1102, Y 1498 is the recorded sideways move driven backwards (its "
         "target is recorded, its start is not); i1Profiler went on from the far side to "
         "the alignment instead. The program also asks where the arm is between the first "
         "two moves (i1Profiler sent them back to back), so that it stops if the first did "
         "not arrive."),
    Step("free", "Let the arm go (the mode i1Profiler uses for aligning a chart) and take it back",
         ("warm", "homed"), "free_homed",
         HOME_FIRST + (("f4", "00"), ("f4", "00"), ("x", "f3"), ("f4", "00"), ("f4", "00"),
                       ("x", "free"), ("f4", "01"), ("f4", "01"), ("touch",),
                       ("x", "status"), ("f4", "01"), ("f4", "01"), ("f4", "01"),
                       ("f4", "01"), ("x", "status"),
                       ("p0", "START_GUARD", "the free arm before the homing"),
                       ("move", "home", "home_free"))
         + HOME_AND_CHECK, "medium",
         "With the arm at its resting place, the program switches on the hand-alignment mode, "
         "exactly the lines i1Profiler sends before it asks you to push the arm over your "
         "chart (f3, then f1). The arm should then move freely. You touch it gently once, "
         "without moving it away from the tile. Then the program takes it back the way "
         "i1Profiler does when you cancel an alignment: it sends the arm home (the motors "
         "take it again) and homes once more. Afterwards only the close may follow, and we "
         "recommend it: the close is what switches the hand-alignment mode off again.",
         "i1Profiler switched this mode on only out on the table, after a move to the "
         "alignment start; here it is switched on at the resting place. Taking the free arm "
         "back with a homing is recorded three times: twice it worked, from far out on the "
         "table (2.4 s and 4.0 s); once, when the homing was sent two milliseconds after a "
         "button on the instrument had been pressed, the table answered with status 3 "
         "instead. What status 3 means is not known. If the table answers that here, the "
         "program stops and sends nothing more; the table is then still in the "
         "hand-alignment mode, and the program tells you what to do."),
    Step("close", "Close the table the way i1Profiler does",
         ("homed", "free_homed"), "closed", (("x", "status"), ("x", "f0"), ("x", "f3")), "low",
         "The two lines with which i1Profiler closes the table. Nothing moves.",
         "Nothing: this is i1Profiler's close after a homing and a pause, as recorded."),
)

BOXES = {"REST_GUARD": REST_GUARD, "START_GUARD": START_GUARD, "OUT_START": OUT_START, "AT_250": AT_250,
         "AT_1000": AT_1000, "AT_1498": AT_1498, "AT_2507": AT_2507}


def step_lines(step: Step) -> "list[str]":
    """The host lines of a step, in order (for the plan, the caps and the tests)."""
    out = []
    for op in step.ops:
        if op[0] == "x":
            out.append(op[1])
        elif op[0] == "f4":
            out.append("arm_mode")
        elif op[0] == "p0":
            out.append("position")
        elif op[0] == "home_rest":
            out.append("home")
        elif op[0] == "move":
            out.append(op[1])
    return out


OPEN_KEYS = ("identity", "identity", "k2", "memory_a", "memory_b", "a0",
             "status", "arm_mode", "arm_mode", "arm_mode", "arm_mode")

#: Hard caps. Per step: exactly its own lines and movements. Per session: the opening plus
#: every step once (each step can be run at most once).
STEP_MAX_LINES = {s.key: len(step_lines(s)) for s in STEPS}
STEP_MAX_MOTIONS = {s.key: sum(1 for k in step_lines(s) if k in MOTION_KEYS) for s in STEPS}
MAX_LINES = len(OPEN_KEYS) + sum(STEP_MAX_LINES.values())
MAX_MOTIONS = sum(STEP_MAX_MOTIONS.values())


# ---- the session ------------------------------------------------------------------------

class Doubt(Exception):
    """Something was not as expected. From now on NOTHING more is sent."""

    def __init__(self, reason: str, plain: "str | None" = None):
        super().__init__(reason)
        self.plain = plain


class Stopped(Exception):
    """The person stopped. From now on NOTHING more is sent."""


_STOP_SIGNALS = tuple(getattr(signal, n) for n in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT")
                      if hasattr(signal, n))


def hold_stop_signals():
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


REFUSED_TEXT = ("The table answered, but refused the line {line} (code {code}). Nothing more is "
                "sent to the table.")
SLOW_TEXT = ("The table reported the movement finished after {took:.2f} seconds; i1Profiler's "
             "movements of this kind took {lo:.2f} to {hi:.2f} seconds (widened). Because it is "
             "outside that, nothing more is sent.")
OFF_PLACE_TEXT = ("The arm reports table position X {x}, Y {y} ({what}); this step needs it "
                  "at {box}. So nothing more is sent, and nothing more moves.")


class Table:
    """One command at a time over a transport; every reply checked against the recorded
    form; every step run as its fixed list of operations.

    After the first doubt or stop, :attr:`closed_reason` is set and every further write
    is refused before it reaches the transport: the program never sends anything to
    "tidy up"."""

    def __init__(self, transport, log=None, touch=None):
        self.t = transport
        self._log = log or (lambda kind, text: None)
        #: asked by the step "free" with the arm free at home; returns the answer
        self._touch = touch or (lambda: "skip")
        self._buf = b""
        self.closed_reason: "str | None" = None
        self.lines_sent = 0
        self.motions_sent = 0
        self.step_lines = 0
        self.step_motions = 0
        self.current_step: "Step | None" = None
        self.busy = 0
        self.stop_requested = False
        self.position_now: "tuple[int, int] | None" = None
        self.motion_unconfirmed = False
        self.arrival_unknown = False
        self.state: "str | None" = None      # cold, warm, homed, free_homed, closed
        self.done_steps: "list[str]" = []
        self.timings: "list[tuple[str, float]]" = []
        self.touch_answers: "list[str]" = []
        self.outside_at: "tuple[int, int] | None" = None
        #: the last movement and whether it finished inside its time window (None: pending)
        self.last_move: "tuple[str, bool | None] | None" = None
        #: where the arm was read right before the last movement was sent
        self.before_move: "tuple[int, int] | None" = None
        #: f1 answered: the hand-alignment mode was switched on (the arm may be free)
        self.freed = False

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

    @property
    def at_home_held(self) -> bool:
        return self.state in ("homed",) and not self.motion_unconfirmed

    # ---- the wire ---------------------------------------------------------------------
    def _write(self, line: bytes) -> str:
        """The ONLY place that writes to the transport. Caps per step and per session are
        checked here; the stop signals are held from the last stop check until the line is
        on its way."""
        if self.closed_reason is not None:
            raise Doubt(f"not sending: {self.closed_reason}")
        cid = check_outgoing(line)
        if self.lines_sent >= MAX_LINES:
            raise self._doubt("the program reached its limit of lines for one session")
        is_motion = line in MOTION_LINES
        if is_motion and self.motions_sent >= MAX_MOTIONS:
            raise self._doubt("the program reached its limit of movements for one session")
        if self.current_step is not None:
            key = self.current_step.key
            if self.step_lines >= STEP_MAX_LINES[key]:
                raise self._doubt(f"the step '{key}' reached its limit of lines")
            if is_motion and self.step_motions >= STEP_MAX_MOTIONS[key]:
                raise self._doubt(f"the step '{key}' reached its limit of movements")
        elif is_motion:
            raise self._doubt("a movement outside a step (a bug)")
        held = hold_stop_signals()
        try:
            self._stop_if_requested()
            if self.closed_reason is not None:
                raise Doubt(f"not sending: {self.closed_reason}")
            self.lines_sent += 1
            self.step_lines += 1
            if is_motion:
                self.motions_sent += 1
                self.step_motions += 1
                self.motion_unconfirmed = True
                self.last_move = (_key_of(line), None)
            self.log("SEND", line.decode("ascii").rstrip("\r"))
            self.t.write(bytes(line))
        finally:
            release_stop_signals(held)
        return cid

    def _read_line(self, deadline: float, max_len: int, secret: bool = False) -> str:
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

    def exchange(self, key: str, window: "str | None" = None) -> Reply:
        """Send WIRE[key], read its two answers, check them against the recorded form; a
        movement must finish inside TIME_WINDOW[window]. Any fault closes the session. A
        stop asked for earlier is always honoured before the line is written."""
        line = WIRE[key]
        if self.closed_reason is not None:
            raise Doubt(f"not sending: {self.closed_reason}")
        is_motion = line in MOTION_LINES
        if is_motion and window not in TIME_WINDOW:
            raise self._doubt(f"a movement without its time window (a bug): {key}")
        timeout = MOVE_TIMEOUT[window] if is_motion else QUICK_TIMEOUT
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
            if is_motion:
                self.motion_unconfirmed = False
                self.arrival_unknown = False
            raise self._doubt(str(exc), REFUSED_TEXT.format(
                line=line.decode("ascii").rstrip("\r"), code=exc.code)) from None
        except ProtocolError as exc:
            if is_motion:            # a done-answer came (with a wrong form): it ended
                self.motion_unconfirmed = False
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
        if is_motion:
            self.motion_unconfirmed = False
            self.timings.append((f"{key}/{window}", took))
            self.log("DATA", f"{cid} ({key}) took {took:.3f} s")
            lo, hi = TIME_WINDOW[window]
            self.last_move = (key, lo <= took <= hi)
            if not lo <= took <= hi:
                raise self._doubt(f"{cid} took {took:.3f} s, outside {lo}-{hi} s ({window})",
                                  SLOW_TEXT.format(took=took, lo=lo, hi=hi))
        return reply

    def drain(self) -> None:
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

    # ---- the opening and the steps --------------------------------------------------
    def position(self) -> "tuple[int, int]":
        p = self.exchange("position").xy()
        self.position_now = p
        self.arrival_unknown = False
        return p

    def opening(self) -> str:
        """i1Profiler's opening (a1 a1 k2 u8 u8 a0) and, on a started table, its follow-up
        s0 f4 f4 f4 f4 (all 00), as recorded at every warm open. Returns "cold" (after six
        lines: nothing more is sent) or "warm". Moves nothing."""
        self.busy += 1
        try:
            self.drain()
            for key in OPEN_KEYS[:5]:
                self.exchange(key)
            a0 = self.exchange("a0").data
            if a0 == A0_COLD:
                self.state = "cold"
                self.log("DATA", "a0 = 111800: the table has just been switched on")
                self.close_for_sending("the table has just been switched on (no start-up is "
                                       "sent by this program)")
                return "cold"
            self.exchange("status")
            for _ in range(4):
                self._f4("00")
        finally:
            self.busy -= 1
        self.state = "warm"
        self.log("DATA", "a0 = 130000: the table is started; f4 00 x4")
        self._stop_if_requested()
        return "warm"

    def _f4(self, want: str) -> None:
        got = self.exchange("arm_mode").data
        if got != want:
            raise self._doubt(f"f4 answered {got} where the recordings show {want} here")

    def _check(self, box_name: str, what: str) -> "tuple[int, int]":
        box = BOXES[box_name]
        pos = self.position()
        self.log("DATA", f"{what}: the arm reports {pos}")
        if not box.contains(pos):
            if box_name in ("REST_GUARD", "START_GUARD", "OUT_START"):
                self.outside_at = pos
            raise self._doubt(f"{what}: the arm reports {pos}, outside {box_name} {box}",
                              OFF_PLACE_TEXT.format(x=pos[0], y=pos[1], what=what,
                                                    box=box.text()))
        return pos

    def _home_from_rest(self) -> None:
        """i1 right after the p0 that read the resting place (checked just before)."""
        pos = self.position_now
        if pos is None or not START_GUARD.contains(pos):
            raise self._doubt("a homing from rest without a fresh reading at rest (a bug)")
        window = ("home_rest" if REST_RECORDED.contains(pos) else
                  "home_wide" if REST_GUARD.contains(pos) else "home_far")
        self._move("home", window)

    def _move(self, key: str, window: str) -> None:
        self.before_move = self.position_now
        self.arrival_unknown = True
        self.position_now = None
        self.exchange(key, window)

    def can_run(self, step: Step) -> bool:
        return (self.closed_reason is None and self.state in step.needs
                and step.key not in self.done_steps)

    def run_step(self, step: Step) -> None:
        """Run one step's fixed operations. Any doubt or stop ends everything; nothing is
        sent after it."""
        if not self.can_run(step):
            raise self._doubt(f"the step '{step.key}' asked for out of order (a bug)")
        self.current_step = step
        self.step_lines = self.step_motions = 0
        self.busy += 1
        self.log("STEP", f"start: {step.key}")
        try:
            for op in step.ops:
                kind = op[0]
                if kind == "x":
                    self.exchange(op[1])
                    if op[1] == "free":
                        self.freed = True
                elif kind == "f4":
                    self._f4(op[1])
                elif kind == "p0":
                    self._check(op[1], op[2])
                elif kind == "home_rest":
                    self._home_from_rest()
                elif kind == "move":
                    if op[1] == "home" and op[2] == "home_free" and \
                            not START_GUARD.contains(self.position_now or (0, 9999)):
                        raise self._doubt("the free-arm homing without a reading at rest")
                    self._move(op[1], op[2])
                elif kind == "touch":
                    self.busy -= 1          # Ctrl-C at the question stops at once
                    try:
                        self.touch_answers.append(self._touch())
                    finally:
                        self.busy += 1
                    self._stop_if_requested()
                else:
                    raise self._doubt(f"unknown operation {kind} (a bug)")
            self._quiet_check()             # listens once more; sends nothing
        finally:
            self.busy -= 1
            self.current_step = None
        self.done_steps.append(step.key)
        self.state = step.leaves
        if step.leaves == "closed":
            self.close_for_sending("the table is closed")
        self.log("STEP", f"done: {step.key}; {self.lines_sent} lines, {self.motions_sent} "
                         "movements so far")
        self._stop_if_requested()
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
            "this, from its folder: venv/bin/python3 i1io_session.py --real (plain 'python3' "
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
