# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""A SIMULATED i1iO 2 table. It never touches hardware.

It answers like the tester's table did in his recordings (two lines per
command, correct checksums, the recorded identity, positions in table units,
move times from the measured acceleration), on a VIRTUAL clock, so a run takes
no real time. Its values are invented where the recordings say nothing.

It is STRICT: it raises :class:`SimViolation` (and a test fails) the moment
it receives anything the real program must never send:

* any command other than a1, s0, f4, p0, i1 (it knows no move command at all),
  or a line with a bad checksum or without its CR;
* anything at all while the arm is still moving;
* an i1 while the arm is free, or from anywhere but the resting place (the
  recorded start-up homing, R2 35.033 from (1102, 47));
* a second i1 in one run.

These rules are written from the recordings, on purpose not imported from
`i1io_table`, so that a mistake in one is caught by the other.

Faults can be injected for the tests (:meth:`SimTable.inject`).
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field

from i1io_table import TransportError, checksum, checksum_ok


class SimViolation(AssertionError):
    """The program sent the simulated table something it must never send."""


IDENTITY = "005D010702"       # the recorded constant identity reply (no serial number)
HOME = (1102, 0)
ACCEL = 2000.0                # units/s^2, fitted on the recorded travel-move times
_HOST_RE = re.compile(r";([a-z][0-9])([0-9a-f]*)([0-9a-f]{2})")
KNOWN_IDS = {"s0": "", "a1": "", "f4": "", "p0": "", "i1": ""}


def _at_home(p) -> bool:
    return abs(p[0] - 1102) <= 5 and -5 <= p[1] <= 50


def move_time(distance: float, speed: int) -> float:
    vmax = 10.0 * speed
    ramp = vmax * vmax / ACCEL
    if distance <= ramp:
        t = 2.0 * math.sqrt(distance / ACCEL)
    else:
        t = 2.0 * vmax / ACCEL + (distance - ramp) / vmax
    return 0.012 + t


@dataclass
class Fault:
    kind: str
    cid: "str | None" = None
    value: float = 0.0


FAULT_KINDS = ("no_answer", "no_done", "late", "bad_checksum", "garbled", "status",
               "wrong_cid", "stray", "blocked", "drift", "unplug", "free", "identity",
               "extra_line", "refuse")


@dataclass
class SimTable:
    pos: "list[float]" = field(default_factory=lambda: [1102.0, 30.0])
    arm: str = "00"                   # f4: 00 held by the motors, 01 free
    clock: float = 0.0
    seed: int = 1
    unplugged: bool = False

    def __post_init__(self):
        self._rng = random.Random(self.seed)
        self._out: "list[tuple[float, bytes]]" = []
        self._busy_until = 0.0
        self._faults: "list[Fault]" = []
        self._faults_at: "dict[int, Fault]" = {}
        self.on_command = None           # test hook: called with the command's index
        self.received: "list[str]" = []
        self.motions = 0

    def inject(self, kind: str, cid: "str | None" = None, value: float = 0.0) -> None:
        """Arm one fault for the next command with id *cid* (or any).

        no_answer: nothing comes back; no_done: accepted, never finished (a move
        that never ends); late: the answer comes *value* s late; bad_checksum;
        garbled: non-text bytes; status: status *value* (default 3); wrong_cid:
        the answer names another command; stray: an unasked line before the
        answer; extra_line: an unasked line after it; blocked: a move stops at
        fraction *value* of the way but reports done; drift: p0 reads *value*
        units off; unplug: the cable goes after this command is written; free:
        f4 answers 01; identity: a1 answers another identity."""
        if kind not in FAULT_KINDS:
            raise ValueError(kind)
        self._faults.append(Fault(kind, cid, value))

    def inject_at(self, index: int, kind: str, value: float = 0.0) -> None:
        """The same faults, for the command with this index (0 = the first)."""
        if kind not in FAULT_KINDS:
            raise ValueError(kind)
        self._faults_at[index] = Fault(kind, None, value)

    @property
    def moving(self) -> bool:
        return self.clock < self._busy_until

    # ---- the wire -----------------------------------------------------------
    def receive(self, data: bytes) -> None:
        if self.unplugged:
            raise TransportError("simulated cable pulled")
        if not data.endswith(b"\r") or data.count(b"\r") != 1:
            raise SimViolation(f"one command line with its CR per write: {data!r}")
        self._command(data[:-1].decode("ascii", "replace"))

    def pending(self, until: float) -> bytes:
        out = b"".join(b for t, b in sorted(self._out, key=lambda e: e[0]) if t <= until)
        self._out = [(t, b) for t, b in self._out if t > until]
        return out

    def next_time(self) -> "float | None":
        return min((t for t, _ in self._out), default=None)

    # ---- commands -------------------------------------------------------------
    def _fault_for(self, cid: str) -> "Fault | None":
        for f in self._faults:
            if f.cid in (None, cid):
                self._faults.remove(f)
                return f
        return None

    def _reply(self, t: float, line: str) -> None:
        self._out.append((t, (line + checksum(line).upper() + "\r").encode("ascii")))

    def _check(self, cid: str, args: str) -> None:
        here = (self.pos[0], self.pos[1])
        if cid == "i1":
            if self.arm != "00":
                raise SimViolation("i1 while the arm is free")
            if not _at_home(here):
                raise SimViolation(f"i1 from {here}: only the start-up homing at the resting "
                                   "place may be sent")
            if self.motions:
                raise SimViolation("a second i1 in one run")

    def _command(self, line: str) -> None:
        self.received.append(line)
        m = _HOST_RE.fullmatch(line)
        if not m or not checksum_ok(line):
            raise SimViolation(f"malformed line or bad checksum: {line!r}")
        cid, args = m.group(1), m.group(2)
        if cid not in KNOWN_IDS or not re.fullmatch(KNOWN_IDS[cid], args):
            raise SimViolation(f"command {cid!r} must never be sent: {line!r}")
        if self.moving:
            raise SimViolation(f"{cid} sent while the arm is still moving: {line!r}")
        self._check(cid, args)
        t0 = max(self.clock, self._busy_until)
        index = len(self.received) - 1
        if self.on_command is not None:
            self.on_command(index)
        fault = self._faults_at.pop(index, None) or self._fault_for(cid)
        kind = fault.kind if fault else None
        if kind == "unplug":
            self.unplugged = True
            return
        if kind == "no_answer":
            return
        if kind == "garbled":
            self._out.append((t0 + 0.01, b":!\xff\xfe\r"))
            return
        if kind == "refuse":       # ':#' + id + code, as the tester's table answered s0
            self._reply(t0 + 0.016, f":#{cid}{int(fault.value or 1):X}")
            return
        if kind == "wrong_cid":
            other = "s0" if cid != "s0" else "p0"
            self._reply(t0 + 0.01, f":!{other}")
            return
        self._reply(t0 + 0.01, f":!{cid}")
        if kind == "stray":
            self._reply(t0 + 0.01, ":$s00")
        if kind == "status":
            status, data, duration = int(fault.value or 3), "", 0.02
        else:
            status, data, duration = self._execute(cid, args, fault)
        if kind == "no_done":
            self._busy_until = math.inf
            return
        if kind == "late":
            duration += fault.value or 30.0
        done = f":${cid}{status:X}{data}"
        t_done = t0 + max(duration, 0.014)
        if kind == "bad_checksum":
            bad = (int(checksum(done), 16) + 1) & 0xFF
            self._out.append((t_done, (done + f"{bad:02X}\r").encode("ascii")))
        else:
            self._reply(t_done, done)
        if kind == "extra_line":
            self._reply(t_done, ":$p00")
        if duration > 0.014:
            self._busy_until = t_done

    def _xy(self, x: float, y: float) -> str:
        return f"{int(round(x)) & 0xFFFF:04X}{int(round(y)) & 0xFFFF:04X}"

    def _execute(self, cid: str, a: str, fault: "Fault | None"):
        kind = fault.kind if fault else None
        if cid == "s0":
            return 0, "", 0.0
        if cid == "a1":
            return 0, ("005D010800" if kind == "identity" else IDENTITY), 0.0
        if cid == "f4":
            return 0, ("01" if kind == "free" else self.arm), 0.0
        if cid == "p0":
            drift = fault.value if kind == "drift" else 0.0
            jx, jy = self._rng.choice((-1, 0, 0, 1)), self._rng.choice((-1, 0, 0, 1))
            return 0, self._xy(self.pos[0] + drift + jx, self.pos[1] + drift + jy), 0.0
        self.motions += 1
        # i1 (the only movement it knows)
        dist = math.hypot(self.pos[0] - HOME[0], self.pos[1] - HOME[1])
        t = 0.05 + (0.3 if dist > 20 else 0.25) + move_time(dist, 300)
        target = (float(HOME[0]), float(self._rng.choice((0, 1, 2))))
        if kind == "blocked":
            f = max(0.0, min(1.0, fault.value))
            target = (self.pos[0] + f * (target[0] - self.pos[0]),
                      self.pos[1] + f * (target[1] - self.pos[1]))
        self.pos = [target[0], target[1]]
        return 0, "", t


class SimTransport:
    """A transport to a :class:`SimTable` on its virtual clock."""

    def __init__(self, table: "SimTable | None" = None):
        self.table = table or SimTable()
        self.closed = False
        self.writes: "list[bytes]" = []

    def write(self, data: bytes) -> None:
        if self.closed:
            raise TransportError("closed")
        self.writes.append(bytes(data))
        self.table.receive(bytes(data))

    def read(self, timeout: float) -> bytes:
        t = self.table
        if t.unplugged:
            raise TransportError("simulated cable pulled")
        deadline = t.clock + max(0.0, timeout)
        nxt = t.next_time()
        t.clock = min(deadline, nxt) if nxt is not None and nxt <= deadline else deadline
        return t.pending(t.clock)

    def now(self) -> float:
        return self.table.clock

    def close(self) -> None:
        self.closed = True
