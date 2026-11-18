# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The i1iO 2 table, as far as the session test program talks to it.

Standard library only. pyusb is imported only when the REAL table is opened.

THE ONE RULE OF THIS FILE: the program can put exactly FORTY-SIX different lines on
the wire, listed in :data:`WIRE` (with where each was recorded in :data:`RECORDED_AT`
and in BYTES.md beside this file). Every one is a line X-Rite's i1Profiler sent to the
tester's own i1iO 2, byte for byte. Part A (0.3.1's steps, unchanged on the wire) uses
sixteen: eleven from opening, homing and closing the table, four moves (m0) whose
targets and speed are recorded, and f1 (the hand-alignment mode that lets the arm go).
Part B (new in 0.4.0) adds twenty-nine: m1 (i1Profiler's move to the alignment start,
the same bytes in every recorded session) and the 28 m0 lines of the recorded spot row
of S2 session 3, each with its recorded target and speed. There is no function that
builds a command from numbers: the lines are fixed at import and :func:`check_outgoing`
refuses every other byte string.

The lines are sent only inside STEPS (:data:`STEPS` for part A, :data:`B_STEPS` and the
optional :data:`OPTIONAL_NEAR_STEPS` for part B): fixed sequences, each a list of
operations, chosen and confirmed one by one by the person beside the table. A step is
removed by deleting its entry; the caps follow from the lists. 0.6.0 adds the forty-sixth
line, i0, the start-up of a table that has just been switched on, byte for byte as
i1Profiler sent it in the one recording of a cold start (S1 1.517): it is sent only by
:data:`COLD_STEP`, at most once per sitting, only on a table whose a0 answered 111800, and
only after the person's typed yes. Never in this package: memory or configuration writes,
any line never seen in a recording (m2, p1, c3, c4, d1, a3 outside part C, every u8 other
than the two reads), any target the arm was not driven to in
a recording, any speed not recorded, and every line that occurs only between "arm at
a patch" and "reading" in a scan.

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
TOOL_VERSION = "0.6.0"

VID, PID = 0x0971, 0x2004


class ForbiddenLine(Exception):
    """A line that is not one of the allowed lines (a bug; it is never written)."""


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
    """The real table cannot be opened on this computer. In the app the message is a proposed
    message id (``M-I1IO-DRIVE-...``), also in :attr:`problem`'s company: *problem* names the
    case for the diagnostics (build step 6)."""

    def __init__(self, message: str = "", problem: str = ""):
        super().__init__(message)
        self.message_id = message
        self.problem = problem


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
    # ---- 0.4.0, part B: the recorded spot row of S2 session 3 (empty table) ----
    "m1":        _frame("m1", "0b10055b012c"),     # ;m10b10055b012c42  to the alignment start
    "spot01": _frame("m0", "fb63067a012c"),  # ;m0fb63067a012c03  to (-1181, 1658)
    "spot02": _frame("m0", "fbba067b012c"),  # ;m0fbba067b012ca8  to (-1094, 1659)
    "spot03": _frame("m0", "fc11067b012c"),  # ;m0fc11067b012c08  to (-1007, 1659)
    "spot04": _frame("m0", "fc68067b012c"),  # ;m0fc68067b012cfc  to (-920, 1659)
    "spot05": _frame("m0", "fcbf067b012c"),  # ;m0fcbf067b012ca2  to (-833, 1659)
    "spot06": _frame("m0", "fd17067b012c"),  # ;m0fd17067b012c01  to (-745, 1659)
    "spot07": _frame("m0", "fd6e067c012c"),  # ;m0fd6e067c012ccd  to (-658, 1660)
    "spot08": _frame("m0", "fdc5067c012c"),  # ;m0fdc5067c012cd0  to (-571, 1660)
    "spot09": _frame("m0", "fe1c067c012c"),  # ;m0fe1c067c012cd3  to (-484, 1660)
    "spot10": _frame("m0", "fe74067c012c"),  # ;m0fe74067c012cfc  to (-396, 1660)
    "spot11": _frame("m0", "fecb067c012c"),  # ;m0fecb067c012ca2  to (-309, 1660)
    "spot12": _frame("m0", "ff22067d012c"),  # ;m0ff22067d012c01  to (-222, 1661)
    "spot13": _frame("m0", "ff79067d012c"),  # ;m0ff79067d012cf5  to (-135, 1661)
    "spot14": _frame("m0", "ffd0067d012c"),  # ;m0ffd0067d012cd1  to (-48, 1661)
    "spot15": _frame("m0", "0027067d012c"),  # ;m00027067d012c68  to (39, 1661)
    "spot16": _frame("m0", "007e067d012c"),  # ;m0007e067d012c35  to (126, 1661)
    "spot17": _frame("m0", "00d5067d012c"),  # ;m000d5067d012c38  to (213, 1661)
    "spot18": _frame("m0", "012c067e012c"),  # ;m0012c067e012c3a  to (300, 1662)
    "spot19": _frame("m0", "0184067e012c"),  # ;m00184067e012c63  to (388, 1662)
    "spot20": _frame("m0", "01db067e012c"),  # ;m001db067e012c09  to (475, 1662)
    "spot21": _frame("m0", "0232067e012c"),  # ;m00232067e012c69  to (562, 1662)
    "spot22": _frame("m0", "0289067e012c"),  # ;m00289067e012c5d  to (649, 1662)
    "spot23": _frame("m0", "02e0067f012c"),  # ;m002e0067f012c38  to (736, 1663)
    "spot24": _frame("m0", "0338067f012c"),  # ;m00338067f012c61  to (824, 1663)
    "spot25": _frame("m0", "038f067f012c"),  # ;m0038f067f012c2e  to (911, 1663)
    "spot26": _frame("m0", "03e6067f012c"),  # ;m003e6067f012c31  to (998, 1663)
    "spot27": _frame("m0", "043d067f012c"),  # ;m0043d067f012c34  to (1085, 1663)
    "spot28": _frame("m0", "0495067f012c"),  # ;m00495067f012c5d  to (1173, 1663)
    # ---- 0.6.0: the start-up of a table that has just been switched on (S1 1.517, once) ----
    "start_up": _frame("i0"),                      # ;i02c  only in COLD_STEP, at most once
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
    "m1":       "after m0 (2507, 1498) in every measuring session that began without a calibration: S2 3.488, 270.753, 383.348, 526.841, 683.957 (0.399-0.400 s), then s0 f4 f4 f3 f4 f4 f1; R1, R2 after (1000, 1500): 1.759 s; the volunteer's table, 17 Nov 2026: from (2507, 1498) and (2505, 1498) 0.400 s, then p0 read (2507, 1429), twice (`:!m107`, `:$m10D4`, `:$p0009CB059511`); i1Profiler's own from (999, 1503) 1.759 s (a plain move to (2507, 1429) of that length: 1.75 s predicted). m1 brings the measuring opening to X 2507, Y 1429",
    "spot01":   "S2 session 3, S2 454.218, from (-1297, 2681), 1.456 s to (-1181, 1658) at 300; context p0 p0 m0 p0 (the first spot move, from the free arm after s0 f4 f4 f4 f4)",
    "spot02":   "S2 session 3, S2 456.128, from (-1180, 1658), 0.431 s to (-1094, 1659) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot03":   "S2 session 3, S2 457.625, from (-1093, 1660), 0.432 s to (-1007, 1659) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot04":   "S2 session 3, S2 459.137, from (-1006, 1659), 0.432 s to (-920, 1659) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot05":   "S2 session 3, S2 460.644, from (-920, 1659), 0.431 s to (-833, 1659) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot06":   "S2 session 3, S2 462.327, from (-833, 1659), 0.431 s to (-745, 1659) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot07":   "S2 session 3, S2 463.598, from (-744, 1659), 0.432 s to (-658, 1660) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot08":   "S2 session 3, S2 465.087, from (-657, 1660), 0.431 s to (-571, 1660) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot09":   "S2 session 3, S2 466.554, from (-570, 1660), 0.432 s to (-484, 1660) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot10":   "S2 session 3, S2 468.030, from (-484, 1660), 0.432 s to (-396, 1660) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot11":   "S2 session 3, S2 469.539, from (-395, 1661), 0.431 s to (-309, 1660) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot12":   "S2 session 3, S2 471.049, from (-309, 1661), 0.431 s to (-222, 1661) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot13":   "S2 session 3, S2 472.697, from (-222, 1661), 0.432 s to (-135, 1661) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot14":   "S2 session 3, S2 474.037, from (-134, 1661), 0.431 s to (-48, 1661) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot15":   "S2 session 3, S2 475.517, from (-47, 1662), 0.431 s to (39, 1661) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot16":   "S2 session 3, S2 477.011, from (39, 1662), 0.432 s to (126, 1661) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot17":   "S2 session 3, S2 478.511, from (126, 1661), 0.431 s to (213, 1661) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot18":   "S2 session 3, S2 480.010, from (213, 1661), 0.432 s to (300, 1662) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot19":   "S2 session 3, S2 481.519, from (300, 1663), 0.432 s to (388, 1662) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot20":   "S2 session 3, S2 483.231, from (388, 1662), 0.431 s to (475, 1662) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot21":   "S2 session 3, S2 484.529, from (475, 1662), 0.432 s to (562, 1662) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot22":   "S2 session 3, S2 486.041, from (562, 1662), 0.432 s to (649, 1662) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot23":   "S2 session 3, S2 487.541, from (649, 1662), 0.431 s to (736, 1663) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot24":   "S2 session 3, S2 489.019, from (736, 1663), 0.431 s to (824, 1663) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot25":   "S2 session 3, S2 490.514, from (823, 1663), 0.432 s to (911, 1663) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot26":   "S2 session 3, S2 492.024, from (911, 1663), 0.431 s to (998, 1663) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot27":   "S2 session 3, S2 493.757, from (997, 1663), 0.432 s to (1085, 1663) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "spot28":   "S2 session 3, S2 495.037, from (1085, 1663), 0.432 s to (1173, 1663) at 300; context p0 m0 p0 (spot pass, one patch on)",
    "start_up": "once, on a table that answered a0 = 111800 (just switched on), right after that "
                "answer: S1 1.517 (accepted 1.533, done 4.684, 3.167 s; what the arm did is not "
                "recorded); then s0 f4 f4 f4 f4 (00) s0 p0 (1102, 14) i1 (0.224 s) s0, S1 "
                "4.693-5.036; and once sent by ChromIQ's tester 0.6.0 on the volunteer's table "
                "(17 Nov 2026, S1 l.58-92): `:!i00C`, `:$i00D9` after 3.088 s, the same nine "
                "lines after it, p0 (1102, 29), i1 0.288 s; the arm travelled and came back, "
                "nothing wrong reported",
}

#: Every line except the start-up (0.6.0): the start-up passes only through COLD_STEP
#: (Table._write and the wire's own one-shot check), never through check_outgoing.
ALLOWED_LINES = frozenset(v for k, v in WIRE.items() if k != "start_up")
#: The 28 spot lines in the recorded order (patch 1 at the chart's right, patch 28 at its
#: left, as the person sees it).
SPOT_KEYS = tuple(f"spot{k:02d}" for k in range(1, 29))
#: Their recorded targets, read from the lines themselves (never typed twice).


def _target(key: str) -> "tuple[int, int]":
    b = WIRE[key].decode("ascii")
    x, y = int(b[3:7], 16), int(b[7:11], 16)
    return (x - 0x10000 if x & 0x8000 else x, y - 0x10000 if y & 0x8000 else y)


SPOT_TARGETS = tuple(_target(k) for k in SPOT_KEYS)
#: Part A's lines (0.3.1): part A may send nothing else, part B adds m1 and the spots.
PART_A_KEYS = ("identity", "k2", "memory_a", "memory_b", "a0", "status", "arm_mode",
               "position", "home", "f0", "f3", "to_250", "to_1000", "to_1498", "to_2507",
               "free")
PART_A_LINES = frozenset(WIRE[k] for k in PART_A_KEYS)
MOTION_KEYS = frozenset({"home", "to_250", "to_1000", "to_1498", "to_2507", "m1",
                         "start_up"} | set(SPOT_KEYS))
MOTION_LINES = frozenset(WIRE[k] for k in MOTION_KEYS)
SECRET_KEYS = frozenset({"memory_a", "memory_b"})

DATA_LEN = {"identity": 10, "k2": 14, "memory_a": 512, "memory_b": 208, "a0": 6,
            "status": 0, "arm_mode": 2, "position": 8, "home": 0, "f0": 2, "f3": 2,
            "to_250": 0, "to_1000": 0, "to_1498": 0, "to_2507": 0, "free": 2, "m1": 0,
            "start_up": 0, **{k: 0 for k in SPOT_KEYS}}
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
    """THE GATE. The command id if *line* is exactly one of the allowed lines;
    ForbiddenLine otherwise. The start-up line (0.6.0) is not among them: it has its own
    gate, armed only inside COLD_STEP."""
    if not isinstance(line, (bytes, bytearray)) or bytes(line) not in ALLOWED_LINES:
        raise ForbiddenLine(f"not one of the allowed lines: {line!r}")
    return bytes(line)[1:3].decode("ascii")


# ---- replies -----------------------------------------------------------------------

@dataclass(frozen=True)
class Reply:
    cid: str
    status: int
    data: str
    #: only for the memory block u8 0x6000: the 36 numbers at its bytes 88-231 (D-4b, the
    #: table's stored white tile values), or None. Nothing else of the block is kept.
    tile: "tuple | None" = None

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
    tile = stored_tile_values(data) if key == "memory_a" else None
    if key in SECRET_KEYS:
        data = ""
    return Reply(cid, status, data, tile)


#: D-4b: where the table's memory block u8 0x6000 keeps its white tile's values, as the analysis
#: of the volunteer's recording of 17 Nov 2026 found them (i1Profiler's values are reproduced with
#: them): 36 little-endian 32-bit floats at bytes 88-231 of the block's 256 bytes, after the
#: serial field. ONLY these bytes are read; no earlier byte is read, logged or stored.
STORED_TILE_FIRST_BYTE = 88
STORED_TILE_BANDS = 36


def stored_tile_values(data_hex: str) -> "tuple | None":
    """The 36 numbers at bytes 88-231 of the memory block (as given in its answer, hex), or None
    when the block is not that long or not hex. Not validated here (spot.stored_white_factors
    does that); nothing is logged."""
    import struct
    a = 2 * STORED_TILE_FIRST_BYTE
    b = a + 8 * STORED_TILE_BANDS
    try:
        raw = bytes.fromhex(str(data_hex)[a:b])
    except ValueError:
        return None
    if len(raw) != 4 * STORED_TILE_BANDS:
        return None
    return struct.unpack(f"<{STORED_TILE_BANDS}f", raw)


def parse_done_c(line: str, cid: str, data_len: int) -> Reply:
    """Part C (0.5.0): the done answer of any line its gate allows: status 0 and exactly the
    recorded number of data characters for that line."""
    _check_refused(line, cid)
    if not line.startswith(":$") or not checksum_ok(line):
        raise ProtocolError(f"expected the table's answer to {cid}, got {show(line)}")
    m = _DONE_RE.fullmatch(line)
    if not m or m.group(1) != cid:
        raise ProtocolError(f"malformed answer to {cid}: {show(line)}")
    status, data = int(m.group(2), 16), m.group(3)
    if status != 0:
        raise ProtocolError(f"the table answered {cid} with status {status}, which it did not "
                            "do in the recordings for this line")
    if len(data) != data_len:
        raise ProtocolError(f"answer to {cid} has {len(data)} data characters, expected "
                            f"{data_len}")
    return Reply(cid, status, data)


class MoveOutside(Exception):
    """Part C: a movement finished (status 0) outside its time window. The session is NOT
    closed by this: the stage reads where the arm is before it decides."""

    def __init__(self, took: float, lo: float, hi: float):
        super().__init__(f"the movement took {took:.3f} s, outside {lo:.2f}-{hi:.2f} s")
        self.took, self.lo, self.hi = took, lo, hi


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

# ---- part B places (0.4.0) ------------------------------------------------------------
#: Where the measuring opening reads after m1: MEASURED on the volunteer's i1iO 2 on 17 Nov
#: 2026, twice, with and without a chart: m1 from (2507, 1498) and (2505, 1498) took 0.400 s
#: and p0 then read (2507, 1429) (`;p025` -> `:$p0009CB059511`). i1Profiler's own m1 from
#: (999, 1503) took 1.759 s in the recording of that night, which is the time a plain move of
#: that length to (2507, 1429) takes (the m0 time fit predicts 1.75 s). So m1 is a move of the
#: opening to (2507, 1429); its target field (2832, 1371) is not where anything lands. The box
#: is the arrival tolerance every recorded move uses (plus or minus 5 units). Until then two
#: places were accepted here, (2832, 1371) and a "sight frame" box around (2716, 1057); both
#: were wrong, and every alignment start stopped at this check on the real table.
AT_M1 = near(2507, 1429)
#: Where the free arm may stand before the first patch move (sensor reading): the box of the
#: recorded starts of i1Profiler's first move from the free arm after an alignment:
#: (-1297, 2681) S2 454.186 (this very line), (-1303, 2689) S2 726.363, (-1283, 2677) S2
#: 114.662, (-1210, 2668) and (-1349, 2616) (the other sessions, NEXT_PROGRAMS 0.4 step 4).
START_BOX = Box(-1360, -1200, 2600, 2700)
RECORDED_FIRST_STARTS = ((-1297, 2681), (-1303, 2689), (-1283, 2677), (-1210, 2668),
                         (-1349, 2616))
#: The two readings right before the first patch move must agree this closely (the arm is
#: free: a hand still on it would show as a difference).
STILL_UNITS = 2
#: 4.3.47: how far the arm may shift when f1 lets it go at the alignment start (b_align), from
#: the reading after m1 (held) to the one read after f1 (free). MEASURED on the volunteer's
#: i1iO 2 on 18 Nov 2026 (ChromIQ 4.3.46): (2506, 1429) held, (2501, 1441) free 0.8 s later,
#: nothing sent in between but the recorded s0 f4 f4 f3 f4 f4 f1 f4 f4, nobody asked to touch
#: it: the freed arm SETTLES by about (-5, +12) units (against the direction m1 and the move
#: before it had driven it). i1Profiler never reads the arm between f1 and the person's first
#: aim, so the recordings hold no such pair; until then this check allowed 5 units, a held
#: arm's arrival tolerance, written against a simulated table whose freed arm never moved,
#: and it stopped the first real run here. What the check is for: a table that DRIVES the arm
#: after f1 (the motors running on although every movement has reported its end) must not be
#: followed by the question that asks the person to touch the arm. At the slowest speed this
#: table ever moved under m0 or m1 (m1: 69 units in 0.40 s) a motor covers more than 100 units
#: in the 0.8 s between the two reads; a settling arm moves a few. 50 units (5 mm, four times
#: the measured settling) separates the two. Nothing that is sent later depends on this
#: reading: the person then moves the free arm by hand to the marks, and every later motor
#: move reads the arm afresh (twice, within STILL_UNITS, while it is free).
RELEASE_SETTLE_UNITS = 50
#: How many times the person may place the free arm by hand in step B3 (each try: he
#: pushes, presses Enter, one position read). Reads only; nothing moves under motor.
PLACE_TRIES = 6
#: Arrival boxes at the 28 patches (plus or minus 5 units, as every arrival in 0.3.1).
AT_SPOT = tuple(near(x, y) for x, y in SPOT_TARGETS)
#: The pause after each patch move before the next position read (i1Profiler's p0 followed
#: each done answer by 0.44 s at the first patch and 1.02-1.07 s at the others, the time of
#: its two instrument readings; S2 456.112-495.037). No line is sent during it.
PATCH_PAUSE_S = 1.0

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
#: Part B (0.4.0):
#:   m1           recorded 0.399-0.400 s from (2507, 1498) (S2, five sessions)
#:   first_patch  spot01 from the free arm in START_BOX: recorded 1.456 s from (-1297, 2681)
#:                (S2 454.218; session 5's own first line 1.455 s); predicted 1.37-1.46 s
#:                over the box (about 2000 units/s^2)
#:   patch        spot02..spot28 from the previous patch: recorded 0.431-0.432 s (27 of 27)
#:   end_home     i1 from (1173, 1663) at the row end: recorded 2.559 s (S2 497.615)
#:   home_patch   i1 from another patch of row 1 (the optional homing after a stop by the
#:                person): recorded on this row 2.559 s from (1172, 1663) and 3.711 s from
#:                (-1088, 1636) (S2 371.169); as home_table
#:   m1 is a plain move of the opening to (2507, 1429) from wherever the arm is (17 Nov 2026:
#:                0.400 s from (2507, 1498), 1.759 s from (999, 1503), 2.751 s for 3,717 units
#:                from (-1210, 1870), each the m0 profile's time). This program sends it ONLY
#:                from the far side: b_align reads AT_2507 right before it, so the short
#:                window below always applies; from anywhere else nothing is sent.
TIME_WINDOW.update({"m1": (0.25, 0.80), "first_patch": (1.0, 2.4), "patch": (0.35, 0.70),
                    "end_home": (1.6, 4.5), "home_patch": (1.0, 6.0)})
MOVE_TIMEOUT.update({"m1": 4.0, "first_patch": 6.0, "patch": 3.0, "end_home": 12.0,
                     "home_patch": 15.0})
#: 0.6.0, the start-up (i0) of a table just switched on: recorded ONCE, 3.167 s (S1 1.517 to
#: 4.684), the arm believed at rest, what it did during it not recorded. Accepted 1.0 to 8.0 s:
#:   lower 1.0 s: under a third of the one recorded time; a much shorter start-up would not be
#:                the start-up that was recorded (every recorded homing at rest, the nearest
#:                movement, took 0.05-0.35 s, so a 1 s floor still leaves room for a start
#:                position nearer to wherever i0 drives);
#:   upper 8.0 s: 2.5 times the recorded time, longer than the longest movement ever recorded
#:                (a strip move, 7.215 s), room for a travel to end positions from a slightly
#:                different start.
#: The program waits up to 15 s for the done answer (as for a homing from the table); none by
#: then: the movement may be unfinished, and the way out is the power switch.
TIME_WINDOW["start_up"] = (1.0, 8.0)
MOVE_TIMEOUT["start_up"] = 15.0
START_UP_LINE = WIRE["start_up"]
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
         "AT_1000": AT_1000, "AT_1498": AT_1498, "AT_2507": AT_2507, "START_BOX": START_BOX}

# ---- PART B (0.4.0): the recorded spot row over the empty table -----------------------------
#
# S2 session 3 (S2 379.860-500.238) without the chart and without the instrument: the way to
# the alignment start, the hand-alignment mode, the arm placed by hand where the recorded first
# patch move started, the 28 recorded patch moves, the homing from the row end and
# i1Profiler's end-of-job lines. Each step needs the one before it (the "needs" state); no
# step can be skipped and a later one run.

B_STEPS = (
    Step("b_home", "Send the arm to its resting place once",
         ("warm",), "homed", HOME_FIRST, "low",
         "The same homing as step 1 of part A: the arm is sent to its resting place, where it "
         "already is or nearly is (usually a few millimetres, about a third of a second).",
         "As in part A: i1Profiler sent this homing only from X 1102, Y 0 to 47; this "
         "program also sends it from X 1090 to 1115 and Y up to 250, and stops if it takes "
         "longer than 2 s. If the arm stands farther out, nothing moves."),
    Step("b_align", "Drive to the place where i1Profiler starts every alignment, and let the arm go there",
         ("homed",), "free_out",
         (("f4", "00"), ("f4", "00"), ("p0", "OUT_START", "before driving out"),
          ("move", "to_1498", "to_1498"), ("p0", "AT_1498", "after the first move"),
          ("move", "to_2507", "to_2507"), ("p0", "AT_2507", "at the far side"),
          ("move", "m1", "m1"), ("p0m1",),
          ("x", "status"), ("f4", "00"), ("f4", "00"), ("x", "f3"), ("f4", "00"),
          ("f4", "00"), ("x", "free"), ("f4", "01"), ("f4", "01"),
          ("p0freed", RELEASE_SETTLE_UNITS, "the free arm at the alignment start"),
          ("touch_out",)),
         "medium",
         "The arm drives straight out from its resting place by 150 mm (about 1.7 s), then "
         "140 mm sideways to the far side, towards the left as you see the table when you lay "
         "a chart on it (about 1.7 s), then makes one short move of 7 mm towards the back "
         "(about 0.4 s) to the place where i1Profiler starts every chart alignment. These are exactly "
         "i1Profiler's three moves at the start of the five measuring sessions of 14 November. "
         "Then the program sends i1Profiler's lines that switch on the hand-alignment mode "
         "(f3, then f1): the motors should let the arm go. The program reads where the arm is "
         "and asks you to touch it gently once.",
         "The short move (m1) is sent exactly as i1Profiler sent it, from the same place. "
         "It brings the measuring opening to X 2507, Y 1429 (measured twice on a real i1iO 2 "
         "on 17 November 2026, 0.4 s each time). i1Profiler never read the position right "
         "after it; this program does, between the moves and after m1, and stops if the arm "
         "is not there. In the recordings these moves followed i1Profiler's end of the "
         "previous job; here they follow this program's homing."),
    Step("b_place", "You push the free arm by hand to the front right of the table",
         ("free_out",), "free_placed", (("place",),), "low",
         "Nothing moves under motor in this step. You push the free arm gently by the "
         "instrument holder, as you do in i1Profiler's alignment, to the place where the first "
         "patch move of your recorded spot measurement started: in the front right part of "
         "the table, about 24 cm to the right of the resting place and about 27 cm towards "
         "the front (where the alignment sight was over the bottom-right corner patch of your "
         "chart on 14 November). Then you take your hands off and type placed, and the "
         "program reads where the arm is. The place is a small box, 16 mm wide and 10 mm "
         "deep, so the program tells you how far to push it if it is not there yet; you have "
         f"{PLACE_TRIES} tries.",
         "i1Profiler sent these lines (s0, f4 four times) after you had aimed at the third "
         "corner patch with the instrument's button and the position under the sight had been "
         "read (p1); here nothing is aimed, there is no p1, and typing placed takes the place of "
         "the button. The position reads between your tries are not in the recordings (reads "
         "only; i1Profiler read the free arm twice right before its first patch move)."),
    Step("b_first", "The motors take the arm and drive it to the first patch",
         ("free_placed",), "row",
         (("p0", "START_BOX", "the free arm before the first patch move"),
          ("p0still", STILL_UNITS, "the free arm, read a second time"),
          ("move", "spot01", "first_patch"), ("pause", False), ("p0spot", 0)),
         "medium",
         "With your hands off the arm, the program reads its position twice, exactly as "
         "i1Profiler does, and only if it is inside the box and has not moved, sends "
         "i1Profiler's first patch move: the motors take the free arm and drive it about "
         "10 cm towards the back of the table (about 1.5 s) to the first patch of row 1 "
         "(table position X -1181, Y 1658). The program then checks that it arrived.",
         "The line, its target and speed are exactly as recorded. Your recordings hold 10 "
         "chart alignments: in 2 of them, i1Profiler's next movement was a first patch move "
         "like this one, straight from the free arm; in 5, it first sent the line c4 and then "
         "a move (the scan measurements); in 3, it sent a homing. The start is where your hand "
         "left the arm, inside the box of the recorded starts but not "
         "exactly the recorded start (X -1297, Y 2681). After it, the arm is held by the "
         "motors again, but the table stays in the hand-alignment mode until step 6."),
    Step("b_row", "Row 1, patch by patch, as i1Profiler measured it (without measuring)",
         ("row",), "row_end",
         tuple(op for k in range(1, 28)
               for op in (("pause", True), ("p0spot", k - 1), ("move", SPOT_KEYS[k], "patch")))
         + (("pause", False),),
         "low-medium",
         "The arm steps along row 1 to the left, 27 steps of about 8.7 mm, one step about "
         "every 1.4 seconds (each move takes about 0.43 s, then the program waits 1 s), about "
         "40 seconds in all, 23.5 cm altogether, exactly the 27 moves of your recorded spot "
         "measurement. Before each step it reads where the arm is and stops if it is not "
         "within half a millimetre of the patch it was sent to. While it runs you can press "
         "Enter to stop at the next patch, or Ctrl-C (then it sends nothing more at all). Please watch the round measuring opening "
         "and the glider ring under it.",
         "The moves are exactly as recorded. In the recording the instrument took two readings "
         "in each 1 s pause; here the instrument is not used, and the program only waits."),
    Step("b_end", "Home from the row end and end the job the way i1Profiler does",
         ("row_end",), "b_done",
         (("x", "status"), ("p0spot", 27), ("move", "home", "end_home"), ("x", "status"),
          ("x", "f0"), ("f4", "00"), ("f4", "00"),
          ("p0", "REST_GUARD", "back home after the row")),
         "low",
         "The arm is sent home from the end of row 1 (about 2.6 s), then the program sends "
         "i1Profiler's end-of-job lines: f0 switches the hand-alignment mode off, f4 should "
         "then answer 00. Last, it reads that the arm is at its resting place.",
         "Nothing in the lines or their order: this is i1Profiler's end of your recorded spot "
         "measurement, from the same place. The last position read is added (i1Profiler read "
         "it at the start of the next job)."),
)

#: The two [near] steps of part B, defined here; only those named in OPTIONAL_NEAR_STEPS are
#: ever offered. A reviewer strikes one by deleting its name from that list.
NEAR_STEP_DEFS = {
    "home_from_patch": Step(
        "home_from_patch", "Send the arm home from the patch where you stopped, and end the job",
        ("row", "row_stopped"), "b_done",
        (("x", "status"), ("p0last",), ("move", "home", "home_patch"), ("x", "status"),
         ("x", "f0"), ("f4", "00"), ("f4", "00"), ("p0", "REST_GUARD", "back home")),
        "medium",
        "The arm is held by the motors at the patch of row 1 it reached last. "
        "This step sends it home from there (2.5 to 4 s) and then sends i1Profiler's "
        "end-of-job lines, which switch the hand-alignment mode off, exactly as at the end of "
        "the row. If you say no, nothing more is sent and the arm stays where it is.",
        "i1Profiler sent this homing from two places on this same row with the arm held "
        "(X 1172, Y 1663 at the row end, 2.6 s; X -1088, Y 1636 near the row's other end, "
        "3.7 s, after the previous job); every patch of row 1 lies on the line between them. "
        "From this very patch it was never sent."),
    "close_after_end": Step(
        "close_after_end", "Close the table the way i1Profiler closes it when you quit",
        ("b_done",), "closed", (("x", "status"), ("x", "f0"), ("x", "f3")), "low",
        "The two lines with which i1Profiler closes the table when you quit it. Nothing moves.",
        "i1Profiler sent this close only after a homing (i1, s0); here it would follow the "
        "end-of-job lines, which already contain f0, so f0 would come twice. That is not "
        "recorded."),
}
#: Both are offered (the owner's ruling of 16 Nov 2026: the bar is physical harm or a memory
#: write, and neither can do either; SAFETY_BRIEF.md, "The two optional steps"). The homing
#: from a patch is offered only after a stop by the person on row 1: it replaces an arm left
#: held out on the table in the hand-alignment mode by the recorded end of job, sent from a
#: point on the same recorded homing line. The close after the end of job is offered after
#: step 6 (or after the homing from a patch); it is not recommended, because the end of job
#: already leaves the table as i1Profiler leaves it between jobs, and f0 twice is not
#: recorded. A reviewer strikes either by deleting its name here.
OPTIONAL_NEAR_STEPS = ("home_from_patch", "close_after_end")


# ---- 0.6.0: the start-up of a table that has just been switched on ------------------------
#
# S1 (14 Nov 2026, i1Profiler 3.8.6, the volunteer's table, recorded ONCE), right after a0 had
# answered 111800: i0 (3.167 s), then s0, f4 x4 (00), s0, p0 (1102, 14), i1 (0.224 s), s0. The
# step sends exactly these ten lines in this order; the p0 must read START_GUARD (the box every
# first homing of this program already uses) and the homing must finish inside its usual window.
# After it the table is treated as started ("warm"), and the part the person chose goes on.

COLD_STEP = Step(
    "cold_start", "Start the table the way i1Profiler started it after it was switched on",
    ("cold",), "warm",
    (("start_up",), ("x", "status"), ("f4", "00"), ("f4", "00"), ("f4", "00"), ("f4", "00"))
    + HOME_FIRST, "medium",
    "The table has just been switched on. i1Profiler starts such a table with one command, "
    "i0, and the program sends it exactly as i1Profiler sent it (the same six bytes). In the one "
    "recording, the table took about 3 seconds to report it finished. Then come the lines "
    "i1Profiler sent right after it: a status line, four reads of the mode flag, a status "
    "line, a position read (it must read the resting place) and the usual homing.",
    "This start-up command was recorded ONCE from i1Profiler, and it has run ONCE from this "
    "program on a real table (17 November 2026: 3.1 s, the arm travelled and came back to its "
    "resting place, nothing wrong). In the recording it followed the table's answer at once; "
    "here it follows your typed yes.")


def near_steps() -> "tuple[Step, ...]":
    return tuple(NEAR_STEP_DEFS[k] for k in OPTIONAL_NEAR_STEPS)


def step_lines(step: Step) -> "list[str]":
    """The host lines of a step, in order, at their most (for the plan, the caps and the
    tests). The placement in step b_place counts all its tries."""
    out = []
    for op in step.ops:
        if op[0] == "x":
            out.append(op[1])
        elif op[0] == "f4":
            out.append("arm_mode")
        elif op[0] in ("p0", "p0m1", "p0still", "p0freed", "p0spot", "p0last"):
            out.append("position")
        elif op[0] == "home_rest":
            out.append("home")
        elif op[0] == "move":
            out.append(op[1])
        elif op[0] == "place":
            out += ["status"] + ["arm_mode"] * 4 + ["position"] * PLACE_TRIES
        elif op[0] == "start_up":
            out.append("start_up")
    return out


OPEN_KEYS = ("identity", "identity", "k2", "memory_a", "memory_b", "a0",
             "status", "arm_mode", "arm_mode", "arm_mode", "arm_mode")

ALL_STEP_DEFS = STEPS + B_STEPS + tuple(NEAR_STEP_DEFS.values())
#: Hard caps. Per step: exactly its own lines and movements. Per session: the opening plus
#: every step of the chosen part once (each step can be run at most once).
STEP_MAX_LINES = {s.key: len(step_lines(s)) for s in ALL_STEP_DEFS}
STEP_MAX_MOTIONS = {s.key: sum(1 for k in step_lines(s) if k in MOTION_KEYS)
                    for s in ALL_STEP_DEFS}
#: Part A (0.3.1, unchanged): 110 lines, 19 movements.
MAX_LINES = len(OPEN_KEYS) + sum(STEP_MAX_LINES[s.key] for s in STEPS)
MAX_MOTIONS = sum(STEP_MAX_MOTIONS[s.key] for s in STEPS)
#: 0.6.0: the start-up (10 lines, 2 movements: i0 and the homing), at most once per sitting.
#: It is NOT part of any part's caps: a sitting in which it ran may send these ten lines more
#: than the part's own cap (Table.cold_allowance); a sitting on a started table has exactly
#: 0.5.1's caps.
STEP_MAX_LINES["cold_start"] = len(step_lines(COLD_STEP))
STEP_MAX_MOTIONS["cold_start"] = sum(1 for k in step_lines(COLD_STEP) if k in MOTION_KEYS)
COLD_MAX_LINES = STEP_MAX_LINES["cold_start"]
COLD_MAX_MOTIONS = STEP_MAX_MOTIONS["cold_start"]


def _b_session_steps() -> "tuple[Step, ...]":
    """The longest part B session: every B step, then the optional steps that may follow the
    end of job (the homing from a patch replaces the rest of the row and the end of job, so
    it never adds to the longest session)."""
    return B_STEPS + tuple(s for s in near_steps() if "b_done" in s.needs)


B_MAX_LINES = len(OPEN_KEYS) + sum(STEP_MAX_LINES[s.key] for s in _b_session_steps())
B_MAX_MOTIONS = sum(STEP_MAX_MOTIONS[s.key] for s in _b_session_steps())
#: The lines each part may send at all.
PART_B_KEYS = ("identity", "k2", "memory_a", "memory_b", "a0", "status", "arm_mode",
               "position", "home", "f0", "f3", "to_1498", "to_2507", "free", "m1") + SPOT_KEYS
PART_LINES = {"A": PART_A_LINES, "B": frozenset(WIRE[k] for k in PART_B_KEYS)}
PART_CAPS = {"A": (MAX_LINES, MAX_MOTIONS), "B": (B_MAX_LINES, B_MAX_MOTIONS)}


# ---- the session ------------------------------------------------------------------------

#: how every lost USB link is reported (the reason of the Doubt starts with it)
LINK_FAILED = "the USB link failed"
#: 0.5.1, part C: what a lost USB link means, on screen
LINK_LOST = (
    "The table's USB connection was lost ({detail}). That happens when a USB cable is unplugged, when the table is switched off, or when the USB "
    "connection drops by itself. This program cannot reach the table any more and sends nothing "
    "more to it, and it offers no more stages.")


class Doubt(Exception):
    """Something was not as expected. From now on NOTHING more is sent."""

    def __init__(self, reason: str, plain: "str | None" = None):
        super().__init__(reason)
        self.plain = plain


class Stopped(Exception):
    """The person stopped. From now on NOTHING more is sent."""


class PersonStop(Exception):
    """Part B, step b_row: the person pressed Enter during a pause between two patches. The
    session is NOT closed by this: the arm is held at the patch it reached, and the session
    may offer the optional homing from there (OPTIONAL_NEAR_STEPS) or end."""


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
        #: D-4b: the table's stored white tile values (Reply.tile of the memory block), or None
        self.stored_tile: "tuple | None" = None
        self.closed_reason: "str | None" = None
        self.lines_sent = 0
        self.motions_sent = 0
        self.step_lines = 0
        self.step_motions = 0
        self.current_step: "Step | None" = None
        self.busy = 0
        self.stop_requested = False
        self.position_now: "tuple[int, int] | None" = None
        self.last_read: "tuple[int, int] | None" = None
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
        # ---- 0.4.0 ----
        #: "A" (0.3.1's steps, the default) or "B" (the recorded spot row)
        self.part = "A"
        #: the hand-alignment mode as the table should have it: on after f1 answered 01, off
        #: after f0 answered 00 (part B; part A keeps 0.3.1's own logic with `freed`)
        self.mode_on = False
        #: True after f1 was answered (the motors let go), False after a movement from the
        #: free arm finished with status 0 (the motors hold it again), None when unknown
        self.arm_free: "bool | None" = False
        #: the answer to the touch at the alignment start (b_align)
        self.out_touch: "str | None" = None
        #: the patch (0..27) whose arrival was last read, and the last patch sent to
        self.last_spot_read: "int | None" = None
        self.last_spot_sent: "int | None" = None
        #: the person's placement tries in b_place and what each read
        self.place_reads: "list[tuple[int, int]]" = []
        #: asked between patches whether the person pressed Enter (part B, b_row)
        self._poll_stop = lambda: False
        #: asked in b_place: the person pushes the free arm; returns "placed" or "stop"
        self._hand = lambda n, last: "placed"
        #: asked at the end of b_align with the arm free at the alignment start
        self._touch_out = lambda: "skip"
        # ---- 0.5.0, part C ----
        #: part C's gate: line -> (command id, is it a movement, label); set by i1io_part_c
        self.c_gate = None
        #: final fix round, M-1: the job's last check before a movement line (None: none);
        #: returns why the movement may not be sent, or None
        self.motion_guard = None
        #: part C's caps per session (lines, movements)
        self.c_caps = (0, 0)
        #: True only on the one path from a scan move to the instrument's fire (i1io_scan):
        #: a stop asked for there is honoured after the scan move has ended, never between the
        #: scan move and the two lines (a3, c3) that belong to it
        self.defer_stop = False
        # ---- 0.5.1 ----
        #: the table's clock time when its USB link was lost (part C), None while it works
        self.link_lost_at: "float | None" = None
        #: what the person is told about it (said once, whichever way the stage ends)
        self.link_lost_text: "str | None" = None
        #: the table's clock time of the last position reading (last_read)
        self.last_read_t: "float | None" = None
        # ---- 0.6.0 ----
        #: the start-up line was written (at most once per sitting)
        self.start_up_sent = False
        #: True only while COLD_STEP writes its start-up line (the gate's own condition)
        self._start_up_armed = False
        #: the start-up step ran to its end (the table is started)
        self.cold_done = False
        #: (lines, movements) the start-up adds to the part's caps once it has begun
        self.cold_allowance = (0, 0)
        #: how long the start-up took (s), and where the arm read after it
        self.start_up_took: "float | None" = None
        self.cold_read: "tuple[int, int] | None" = None
        #: movements of the start-up (part C counts "nothing moved yet" after them)
        self.cold_motions = 0
        #: the number of the start-up line among the lines sent (to tell whether a later doubt
        #: came on it or on a line after it)
        self.start_up_line_no: "int | None" = None
        #: how the start-up failed (set by the session; None while nothing failed)
        self.cold_failure: "str | None" = None

    # ---- logging and stopping ------------------------------------------------------
    def log(self, kind: str, text: str) -> None:
        self._log(kind, f"{self.t.now():10.3f}  {text}")

    def request_stop(self) -> None:
        self.stop_requested = True

    def close_for_sending(self, reason: str) -> None:
        if self.closed_reason is None:
            self.closed_reason = reason
            self.log("STOP", f"nothing more is sent: {reason}")

    def _note_link_lost(self, detail: str) -> "str | None":
        """0.5.1, part C only: remember that the USB link was lost, and what to tell the
        person (once). Sends nothing and closes nothing by itself."""
        if self.part != "C":
            return None
        if self.link_lost_at is None:
            self.link_lost_at = self.t.now()
            self.link_lost_text = LINK_LOST.format(detail=detail)
            self.log("DATA", f"the USB link was lost: {detail}")
        return self.link_lost_text

    def _doubt(self, reason: str, plain: "str | None" = None) -> Doubt:
        if reason.startswith(LINK_FAILED):
            # 0.5.1: part C says plainly what a lost link means (parts A and B unchanged)
            lost = self._note_link_lost(reason[len(LINK_FAILED):].lstrip(": "))
            if lost:
                plain = lost if not plain else lost + " " + plain
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
        if bytes(line) == START_UP_LINE:
            # 0.6.0: the start-up line passes only inside COLD_STEP, on a table that answered
            # a0 = 111800, once per sitting; in every part, before the part's own gate
            if (not self._start_up_armed or self.start_up_sent or self.state != "cold"
                    or self.current_step is None or self.current_step.key != "cold_start"):
                raise self._doubt("the start-up line outside the start-up step (a bug)")
            cid, is_motion, label = "i0", True, "start_up"
            max_lines, max_motions = (self.c_caps if self.part == "C"
                                      else PART_CAPS[self.part])
        elif self.part == "C":
            # 0.5.0, part C: its own gate (i1io_part_c.c_gate: the fixed lines it may send, and
            # computed m0/m2 lines checked against the measuring area and the recorded speeds)
            # and its own caps; parts A and B keep exactly the checks below.
            if self.c_gate is None:
                raise self._doubt("part C without its gate (a bug)")
            cid, is_motion, label = self.c_gate(bytes(line))
            max_lines, max_motions = self.c_caps
        else:
            cid = check_outgoing(line)
            if bytes(line) not in PART_LINES[self.part]:
                raise self._doubt(f"a line that part {self.part} never sends (a bug)")
            max_lines, max_motions = PART_CAPS[self.part]
            is_motion = line in MOTION_LINES
            label = None
        max_lines += self.cold_allowance[0]
        max_motions += self.cold_allowance[1]
        if self.lines_sent >= max_lines:
            raise self._doubt("the program reached its limit of lines for one session")
        if is_motion and self.motions_sent >= max_motions:
            raise self._doubt("the program reached its limit of movements for one session")
        if self.current_step is not None:
            key = self.current_step.key
            own = getattr(self.current_step, "max_lines", None)
            lim_l = own if own is not None else STEP_MAX_LINES[key]
            lim_m = (self.current_step.max_moves if own is not None
                     else STEP_MAX_MOTIONS[key])
            if self.step_lines >= lim_l:
                raise self._doubt(f"the step '{key}' reached its limit of lines")
            if is_motion and self.step_motions >= lim_m:
                raise self._doubt(f"the step '{key}' reached its limit of movements")
        elif is_motion:
            raise self._doubt("a movement outside a step (a bug)")
        if is_motion and self.motion_guard is not None:
            why = self.motion_guard()
            if why:
                raise self._doubt(f"{why} (a bug)")
        held = hold_stop_signals()
        try:
            # part C: on the scan path a stop is deferred until the scan move has ended, but the
            # scan move itself is never written after a stop was asked for
            if not self.defer_stop or label == "scan move":
                self._stop_if_requested()
            if self.closed_reason is not None:
                raise Doubt(f"not sending: {self.closed_reason}")
            self.lines_sent += 1
            self.step_lines += 1
            if is_motion:
                self.motions_sent += 1
                self.step_motions += 1
                self.motion_unconfirmed = True
                self.last_move = (label or _key_of(line), None)
            self.log("SEND", line.decode("ascii").rstrip("\r"))
            if label == "start_up":
                self.start_up_sent = True
                self.start_up_line_no = self.lines_sent
                self.t.start_up_armed = True     # the wire's own one-shot check (FtdiUsb)
            self.t.write(bytes(line))
        finally:
            if label == "start_up":
                self.t.start_up_armed = False
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
            if key == "memory_a":
                self.stored_tile = reply.tile
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
                if self.arm_free:
                    self.arm_free = None    # held again or not: not known
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
            self.arm_free = False           # a finished movement: the motors hold the arm
            if key in SPOT_KEYS:
                self.last_spot_sent = SPOT_KEYS.index(key)
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

    # ---- 0.5.0, part C primitives (every line still goes through _write) ---------------
    def c_exchange(self, line: bytes, data_len: int, window=None, timeout: float = QUICK_TIMEOUT,
                   late_is_doubt: bool = True) -> Reply:
        """Part C: send *line* (any line its gate allows), read the acceptance and the done
        answer, check their form (status 0, *data_len* data characters). A movement must finish
        inside *window* (lo, hi); outside it, with late_is_doubt False, :class:`MoveOutside` is
        raised WITHOUT closing the session (the stage then reads the position: if the arm is
        where it was sent and held, the stage has failed cleanly)."""
        if self.closed_reason is not None:
            raise Doubt(f"not sending: {self.closed_reason}")
        cid = bytes(line)[1:3].decode("ascii")
        self.busy += 1
        is_motion = False
        try:
            self._quiet_check()
            if not self.defer_stop:
                self._stop_if_requested()
            before = self.motions_sent
            self._write(line)
            is_motion = self.motions_sent > before
            if is_motion:
                self.before_move = self.position_now
                self.position_now = None        # the next computed move needs a new reading
                self.arrival_unknown = True
            start = self.t.now()
            parse_ack(self._read_line(start + QUICK_TIMEOUT, ACK_MAX), cid)
            reply = parse_done_c(self._read_line(start + timeout, 2 + 2 + 1 + data_len + 2),
                                 cid, data_len)
            took = self.t.now() - start
        except TimeoutError:
            raise self._doubt(f"no answer to {cid} within the expected time") from None
        except TableRefused as exc:
            if is_motion:
                self.motion_unconfirmed = False
                self.arrival_unknown = False
            raise self._doubt(str(exc), REFUSED_TEXT.format(
                line=bytes(line).decode("ascii").rstrip("\r"), code=exc.code)) from None
        except ProtocolError as exc:
            if is_motion:
                self.motion_unconfirmed = False
                if self.arm_free:
                    self.arm_free = None
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
            self.arm_free = False
            self.timings.append((f"{cid}/computed", took))
            self.log("DATA", f"{cid} took {took:.3f} s")
            if window is not None:
                lo, hi = window
                self.last_move = (self.last_move[0] if self.last_move else cid, lo <= took <= hi)
                if not lo <= took <= hi:
                    if late_is_doubt:
                        raise self._doubt(f"{cid} took {took:.3f} s, outside {lo:.2f}-{hi:.2f} s",
                                          SLOW_TEXT.format(took=took, lo=lo, hi=hi))
                    raise MoveOutside(took, lo, hi)
            else:
                self.last_move = (self.last_move[0] if self.last_move else cid, True)
        return reply

    def c_wait(self, seconds: float) -> None:
        """Part C: wait, sending nothing, listening for anything the table sends unasked (a
        stop). The pacing between spot moves (at least 1.0 s, as recorded) uses it."""
        end = self.t.now() + seconds
        while True:
            self._stop_if_requested()
            left = end - self.t.now()
            if left <= 0:
                return
            try:
                chunk = self.t.read(max(MIN_READ_S, min(left, 0.25)))
            except TransportError as exc:
                raise self._doubt(f"the USB link failed: {exc}") from None
            if chunk:
                self._buf += chunk
                raise self._doubt(f"the table sent something nobody asked for "
                                  f"({_short(self._buf)})")

    def c_send(self, line: bytes) -> None:
        """Part C, the scan path only: write one line (through _write) and return at once."""
        self.busy += 1
        try:
            before = self.motions_sent
            self._write(line)
            if self.motions_sent > before:
                self.before_move = self.position_now
                self.position_now = None
                self.arrival_unknown = True
        except (TransportError, OSError) as exc:
            raise self._doubt(f"the USB link failed: {exc}") from None
        finally:
            self.busy -= 1

    def c_read(self, deadline: float, max_len: int = 48) -> "str | None":
        """Part C, the scan path only: one reply line, or None at the deadline."""
        try:
            return self._read_line(deadline, max_len)
        except TimeoutError:
            return None
        except TransportError as exc:
            # 0.5.1: the scan path decides what follows (as in 0.5.0); the loss is remembered
            # so that the person is told about it
            self._note_link_lost(str(exc))
            raise

    # ---- the opening and the steps --------------------------------------------------
    def position(self) -> "tuple[int, int]":
        p = self.exchange("position").xy()
        self.position_now = p
        self.last_read = p
        self.last_read_t = self.t.now()
        self.arrival_unknown = False
        return p

    def opening(self) -> str:
        """i1Profiler's opening (a1 a1 k2 u8 u8 a0) and, on a started table, its follow-up
        s0 f4 f4 f4 f4 (all 00), as recorded at every warm open. Returns "cold" (after six
        lines: nothing more is sent unless the person chooses the start-up, run_cold_start)
        or "warm". Moves nothing."""
        self.busy += 1
        try:
            self.drain()
            for key in OPEN_KEYS[:5]:
                self.exchange(key)
            a0 = self.exchange("a0").data
            if a0 == A0_COLD:
                # 0.6.0: nothing more is sent unless the person chooses the start-up
                # (run_cold_start); the session closes the table for sending otherwise
                self.state = "cold"
                self.log("DATA", "a0 = 111800: the table has just been switched on")
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

    def _start_up(self) -> None:
        """0.6.0: i0, the only place that may write it (armed for this one write)."""
        if self.state != "cold" or self.start_up_sent:
            raise self._doubt("the start-up asked for on a table that is not just switched on, "
                              "or a second time (a bug)")
        self._start_up_armed = True
        try:
            self._move("start_up", "start_up")
        finally:
            self._start_up_armed = False
            if self.timings and self.timings[-1][0] == "start_up/start_up":
                self.start_up_took = self.timings[-1][1]

    def run_cold_start(self) -> None:
        """0.6.0: COLD_STEP, at most once per sitting, only on a table that answered a0 =
        111800. Its ten lines come on top of the part's caps (cold_allowance)."""
        if self.state != "cold" or self.start_up_sent or self.cold_done:
            raise self._doubt("the start-up asked for out of order (a bug)")
        self.cold_allowance = (COLD_MAX_LINES, COLD_MAX_MOTIONS)
        try:
            self.run_step(COLD_STEP)
        finally:
            if self.start_up_took is None:
                for k, took in self.timings:
                    if k == "start_up/start_up":
                        self.start_up_took = took
        self.cold_done = True
        self.cold_motions = self.motions_sent
        self.cold_read = self.before_move
        self.log("DATA", f"the start-up is done: i0 took {self.start_up_took:.3f} s; the arm "
                         f"read {self.cold_read} before the homing")

    def can_run(self, step: Step) -> bool:
        if step.key == "b_place" and self.out_touch != "free":
            return False            # never ask anyone to push an arm that may be held
        return (self.closed_reason is None and self.state in step.needs
                and (self.part == "C" or step.key not in self.done_steps))

    # ---- part B operations (0.4.0) ------------------------------------------------------
    def _check_box(self, box: Box, what: str) -> "tuple[int, int]":
        pos = self.position()
        self.log("DATA", f"{what}: the arm reports {pos}")
        if not box.contains(pos):
            self.outside_at = pos
            raise self._doubt(f"{what}: the arm reports {pos}, outside {box}",
                              OFF_PLACE_TEXT.format(x=pos[0], y=pos[1], what=what,
                                                    box=box.text()))
        return pos

    def _p0_after_m1(self) -> None:
        """The arm must read where m1 brought it on the real table, (2507, 1429) within the
        usual arrival tolerance; anywhere else nothing more is sent."""
        pos = self.position()
        self.log("DATA", f"after m1: the arm reports {pos}")
        if not AT_M1.contains(pos):
            self.outside_at = pos
            raise self._doubt(
                f"after m1: the arm reports {pos}, not at {AT_M1}",
                OFF_PLACE_TEXT.format(x=pos[0], y=pos[1], what="after the short move m1",
                                      box=AT_M1.text()))

    def _p0_freed(self, units: int, what: str) -> None:
        """b_align after f1: the free arm read once more (the same single p0 as before 4.3.47).
        It may have settled when the motors let it go (RELEASE_SETTLE_UNITS); a larger shift
        stops as before: nothing more is sent."""
        before = self.position_now
        if before is None:
            raise self._doubt(f"{what}: no reading to compare with (a bug)")
        pos = self.position()
        dx, dy = pos[0] - before[0], pos[1] - before[1]
        self.log("DATA", f"{what}: the arm reports {pos} (held before f1: {before}; "
                         f"settled by ({dx:+d}, {dy:+d}) units, at most {units} allowed)")
        if abs(dx) > units or abs(dy) > units:
            self.outside_at = pos
            raise self._doubt(
                f"{what}: the arm moved from {before} to {pos} (more than {units} units)",
                f"The arm reports table position X {pos[0]}, Y {pos[1]}, but right before the "
                f"motors let it go it reported X {before[0]}, Y {before[1]}: it moved further "
                f"than a freed arm settles by itself ({what}). So nothing more is sent.")

    def _p0_still(self, units: int, what: str) -> None:
        before = self.position_now
        if before is None:
            raise self._doubt(f"{what}: no reading to compare with (a bug)")
        pos = self.position()
        self.log("DATA", f"{what}: the arm reports {pos} (before: {before})")
        if abs(pos[0] - before[0]) > units or abs(pos[1] - before[1]) > units:
            self.outside_at = pos
            raise self._doubt(
                f"{what}: the arm moved from {before} to {pos} (more than {units} units)",
                f"The arm reports table position X {pos[0]}, Y {pos[1]}, but a moment ago it "
                f"reported X {before[0]}, Y {before[1]}: it moved while nothing was sent "
                "({what}). So nothing more is sent.".replace("{what}", what))

    def _place(self) -> None:
        """b_place: the person pushes the free arm; after each try one position read. The
        lines s0 f4 f4 f4 f4 (01) come once, after the first try, as i1Profiler sent them
        after the third corner aim (S2 419.021-419.094)."""
        for n in range(1, PLACE_TRIES + 1):
            last = self.place_reads[-1] if self.place_reads else None
            self.busy -= 1              # Ctrl-C at the question stops at once
            try:
                ans = self._hand(n, last)
            finally:
                self.busy += 1
            self._stop_if_requested()
            if ans != "placed":
                self.close_for_sending("you ended the placement")
                raise Stopped("You ended the placement. Nothing more is sent to the table.")
            if n == 1:
                self.exchange("status")
                for _ in range(4):
                    self._f4("01")
            pos = self.position()
            self.place_reads.append(pos)
            self.log("DATA", f"placement try {n}: the free arm reports {pos}")
            if START_BOX.contains(pos):
                return
        self.outside_at = self.place_reads[-1]
        raise self._doubt(f"the free arm was not inside {START_BOX} after {PLACE_TRIES} tries",
                          f"After {PLACE_TRIES} tries the arm is still not inside the box "
                          "the first patch move may start from. Nothing more is sent, and "
                          "nothing moved under motor.")

    def _pause(self, poll: bool) -> None:
        """Wait PATCH_PAUSE_S between two patches, sending nothing, listening for anything
        the table sends unasked (a stop), and (poll) for the person's Enter."""
        end = self.t.now() + PATCH_PAUSE_S
        while True:
            self._stop_if_requested()
            left = end - self.t.now()
            if left <= 0:
                break
            try:
                chunk = self.t.read(max(MIN_READ_S, min(left, 0.25)))
            except TransportError as exc:
                raise self._doubt(f"the USB link failed: {exc}") from None
            if chunk:
                self._buf += chunk
                raise self._doubt(f"the table sent something nobody asked for "
                                  f"({_short(self._buf)})")
        self._stop_if_requested()
        # once per pause: an Enter typed at any time during the row waits in the input
        if poll and self._poll_stop():
            self.log("STEP", "you pressed Enter: stop at this patch")
            raise PersonStop()

    def _p0_spot(self, i: int) -> None:
        self._check_box(AT_SPOT[i], f"at patch {i + 1} of row 1")
        self.last_spot_read = i

    def _p0_last(self) -> None:
        i = self.last_spot_sent
        if i is None:
            raise self._doubt("the homing from a patch without a patch reached (a bug)")
        self._p0_spot(i)

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
                        self.mode_on = True
                        self.arm_free = True
                    elif op[1] == "f0":
                        self.mode_on = False
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
                elif kind == "p0m1":
                    self._p0_after_m1()
                elif kind == "p0still":
                    self._p0_still(op[1], op[2])
                elif kind == "p0freed":
                    self._p0_freed(op[1], op[2])
                elif kind == "touch_out":
                    self.busy -= 1
                    try:
                        self.out_touch = self._touch_out()
                    finally:
                        self.busy += 1
                    self._stop_if_requested()
                elif kind == "place":
                    self._place()
                elif kind == "pause":
                    self._pause(op[1])
                elif kind == "p0spot":
                    self._p0_spot(op[1])
                elif kind == "p0last":
                    self._p0_last()
                elif kind == "start_up":
                    self._start_up()
                else:
                    raise self._doubt(f"unknown operation {kind} (a bug)")
            self._quiet_check()             # listens once more; sends nothing
        except PersonStop:
            self.state = "row_stopped"
            self.log("STEP", f"stopped by you in {step.key} at patch "
                             f"{(self.last_spot_sent or 0) + 1}")
            raise
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

    def __init__(self, dev, usb_core, usb_util, timeout_codes=()):
        self.dev, self._core, self._util = dev, usb_core, usb_util
        self._timeout_error = getattr(usb_core, "USBTimeoutError", None)
        #: build step 6, Windows: libusb-win32 reports a read timeout as its own errno (116)
        #: through pyusb's libusb0 backend, which pyusb does not always call a timeout
        self._timeout_codes = tuple(timeout_codes)
        self._claimed = False
        self._closed = False

    def _is_timeout(self, exc) -> bool:
        if self._timeout_error is not None and isinstance(exc, self._timeout_error):
            return True
        if getattr(exc, "errno", None) in (60, 110):
            return True
        return bool(self._timeout_codes) and \
            getattr(exc, "backend_error_code", None) in self._timeout_codes

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
            err = TransportError(f"could not set up the table's USB link "
                                 f"({getattr(exc, 'strerror', None) or type(exc).__name__})")
            err.usb_error = exc
            raise err from None

    #: the gate at the wire: check_outgoing, or part C's own gate (0.5.0) once part C is chosen
    gate = None

    #: 0.6.0: set by Table._write for exactly the one write of the start-up line
    start_up_armed = False

    def write(self, data: bytes) -> None:
        if bytes(data) == START_UP_LINE:
            # the start-up line: only when the table armed this very write, once
            if not self.start_up_armed:
                raise ForbiddenLine("the start-up line without the start-up step")
            self.start_up_armed = False
        elif self.gate is not None:
            self.gate(data)                        # part C's gate, once more, at the wire
        else:
            check_outgoing(data)                   # the gate, once more, at the wire
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
        err = TableBusy(f"{BUSY_TEXT} ({detail})", step, code)
    elif kind == "NO_DEVICE":
        err = TransportError(f"{GONE_TEXT} ({detail})")
    else:
        err = TransportError(
            "The table could not be opened. Please quit i1Profiler if it is open and try again; "
            f"if it still fails, send the log. Nothing was sent to the table. ({detail})")
    err.usb_error = exc          # build step 6: open_table names it by core.usb_library's id
    return err


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
        raise NotAvailable("M-I1IO-DRIVE-NOT-I1IO2", problem="; ".join(problems))


# ---- opening the real table: ChromIQ's own USB library, on every system (build step 6) -----
#
# The tester (0.6.0) asked pyusb's DEFAULT search and then Homebrew's paths for libusb, and refused
# every system but a Mac. In the app the table is opened ONLY through core.usb_library.backend():
# the libusb ChromIQ bundles, found by path, never the system's (pyusb keeps the FIRST library it
# loads for the whole process, so no other search may ever run first). No text for a person is
# made here: every refusal carries the proposed message id (core.usb_library.MESSAGE_FOR_PROBLEM,
# open_failure) in NotAvailable.problem.

#: refusals of the opening that core.usb_library does not name (proposed ids, STEP4_PROPOSAL)
NO_TABLE = "M-I1IO-DRIVE-TABLE-NOT-FOUND"
SEVERAL_TABLES = "M-I1IO-DRIVE-SEVERAL-TABLES"
NOT_I1IO2 = "M-I1IO-DRIVE-NOT-I1IO2"


def check_usb_available() -> str:
    """The bundled USB library loads (core.usb_library.status). Opens no device, lists none."""
    import core.usb_library as usb_library
    st = usb_library.status()
    if not st.ok:
        raise NotAvailable(usb_library.MESSAGE_FOR_PROBLEM.get(st.problem,
                                                               "M-I1IO-DRIVE-USB-MISSING"),
                           problem=st.problem)
    return f"pyusb {st.pyusb}; libusb {st.libusb}"


#: Windows: the table's driver is not libusb-win32's (proposed id)
DRIVER_NOT_INSTALLED = "M-I1IO-DRIVE-TABLE-DRIVER-NOT-INSTALLED"


def open_table(system: "str | None" = None) -> FtdiUsb:
    """Find and open the table through ChromIQ's own USB route, or raise NotAvailable (with
    the message id in .problem). Sends no table command; only the FTDI set-up after the
    descriptor check. macOS / Linux: the bundled libusb-1.0. Windows: libusb-win32's driver,
    which ChromIQ's installer gives the table only on the person's explicit choice, through
    pyusb's libusb0 backend (core.usb_library.table_backend; UNTESTED ON REAL WINDOWS). *system*
    is sys.platform (tests)."""
    import core.usb_library as usb_library
    system = system or sys.platform
    if system == "win32":
        import core.usb_driver_installer as inst
        state, _detail = inst.table_driver_state_now()
        if state != inst.TABLE_DRIVER_LIBUSB0:
            raise NotAvailable(DRIVER_NOT_INSTALLED, problem=f"table driver {state}")
    else:
        check_usb_available()
    tb = usb_library.table_backend(system)
    if tb.backend is None:
        raise NotAvailable(usb_library.MESSAGE_FOR_PROBLEM.get(tb.problem,
                                                               "M-I1IO-DRIVE-USB-MISSING"),
                           problem=tb.problem or "no-backend")
    import usb.core
    import usb.util
    try:
        found = list(usb.core.find(find_all=True, idVendor=VID, idProduct=PID,
                                   backend=tb.backend))
    except Exception as exc:          # NoBackendError, USBError, OSError: said by its id
        raise NotAvailable(usb_library.open_failure(exc, system, tb.kind),
                           problem="find") from None
    if not found:
        raise NotAvailable(NO_TABLE, problem="none")
    if len(found) > 1:
        raise NotAvailable(SEVERAL_TABLES, problem=f"{len(found)} tables")
    dev = found[0]
    check_descriptors(dev)
    t = FtdiUsb(dev, usb.core, usb.util,
                timeout_codes=usb_library.LIBUSB0_TIMEOUT_CODES if tb.kind == "libusb0" else ())
    t.backend_kind = tb.kind
    try:
        t.setup()
    except TransportError as exc:
        t.close()
        cause = getattr(exc, "usb_error", None)
        raise NotAvailable(usb_library.open_failure(cause, system, tb.kind)
                           if cause is not None else "M-I1IO-DRIVE-USB-UNEXPECTED",
                           problem="claim") from None
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
