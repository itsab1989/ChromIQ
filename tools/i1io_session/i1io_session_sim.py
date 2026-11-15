# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""A SIMULATED i1iO 2 table for the session program. It never touches hardware.

It answers like the tester's table did in the recordings (two lines per command, correct
checksums, the recorded constant answers, a0 111800 when just switched on and 130000 once
started, movements taking about their recorded times) on a VIRTUAL clock. Where the
recordings say nothing, its values are invented; its memory block is SYNTHETIC (a made-up
serial number).

It is STRICT and holds its OWN copy (written here, on purpose NOT imported from the program)
of the opening and of every step's line sequence, and of where each movement may start. It
raises :class:`SimViolation` the moment the program sends a line that is not the next line
of the opening or of a step not yet run, a movement from a place this copy does not allow,
any line while the arm moves, or anything after the close.
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field

from i1io_session_table import TransportError, checksum, checksum_ok


class SimViolation(AssertionError):
    """The program sent the simulated table something it must never send."""


A1, K2L, UA, UB, A0 = ";a133", ";k228", ";u8000060000100d1", ";u8000061000068c3", ";a034"
S0, F4, P0, I1, F0, F3, F1 = ";s022", ";f42b", ";p025", ";i12b", ";f02f", ";f32c", ";f12e"
M250, M1000 = ";m0044e00fa012c0e", ";m003e805dc012c06"
M1498, M2507 = ";m0044e05da012c0b", ";m009cb05da012cda"

REC_OPEN6 = [A1, A1, K2L, UA, UB, A0]
REC_OPEN = REC_OPEN6 + [S0, F4, F4, F4, F4]
_HF = [S0, P0, I1, S0]
_HC = [S0, S0, P0, I1, S0]
_AR = [S0, S0, F4, F4]
REC_STEPS = {
    "home": _HF,
    "near": _HF + [F4, F4, P0, M250, P0, M1000] + _AR + [P0, I1] + _HC,
    "straight": _HF + [F4, F4, P0, M1498] + _AR + [P0, I1] + _HC,
    "across": _HF + [F4, F4, P0, M1498, P0, M2507] + _AR + [P0, M1498] + _AR + [P0, I1]
    + _HC,
    "free": _HF + [F4, F4, F3, F4, F4, F1, F4, F4, S0, F4, F4, F4, F4, S0, P0, I1] + _HC,
    "close": [S0, F0, F3],
}

IDENTITY = "005D010702"
K2 = "0B600000000013"
HOME = (1102, 0)
_HOST_RE = re.compile(r";([a-z][0-9])([0-9a-f]*)([0-9a-f]{2})")
FAKE_SERIAL = "SIM0000TEST"
#: recorded durations of the moves (seconds from the line to the done-answer)
DURATION = {M250: 0.719, M1000: 1.599, M1498: 1.727, M2507: 1.695}
TARGET = {M250: (1102, 250), M1000: (1000, 1500), M1498: (1102, 1498), M2507: (2507, 1498)}


def _memory_a() -> str:
    head = "6801000056312E31"
    body = head + "0102030405060708090A0B0C" + FAKE_SERIAL.encode("ascii").hex().upper()
    return body + "AB" * ((512 - len(body)) // 2)


def _memory_b() -> str:
    return "FF" * 96 + "0102030405060708"


def _near(p, q, d=10) -> bool:
    return abs(p[0] - q[0]) <= d and abs(p[1] - q[1]) <= d


def _rest_guard(p) -> bool:          # the simulator's own copy of where i1 may start at rest
    return 1101 <= p[0] <= 1103 and -1 <= p[1] <= 120


def _out_start(p) -> bool:           # where a move out from rest may start
    return 1101 <= p[0] <= 1103 and -1 <= p[1] <= 48


@dataclass
class Fault:
    kind: str
    cid: "str | None" = None
    value: float = 0.0


FAULT_KINDS = ("no_answer", "no_done", "late", "bad_checksum", "garbled", "status",
               "wrong_cid", "stray", "extra_line", "blocked", "drift", "unplug", "free",
               "identity", "refuse", "a0_other", "k2_other", "memory_short",
               "memory_bad_start", "long_line", "slow_motion", "fast_motion")


@dataclass
class SimTable:
    cold: bool = False
    pos: "list[float]" = field(default_factory=lambda: [1102.0, 30.0])
    clock: float = 0.0
    seed: int = 1
    unplugged: bool = False
    chunk: int = 62
    jitter: bool = True
    #: the arm's "mode" as f4 reports it: 00, or 01 after f1 (until f0)
    mode: str = "00"
    #: True while the hand-alignment mode lets the arm go
    free_arm: bool = False

    def __post_init__(self):
        self._rng = random.Random(self.seed)
        self._out: "list[tuple[float, bytes]]" = []
        self._busy_until = 0.0
        self._faults: "list[Fault]" = []
        self._faults_at: "dict[int, Fault]" = {}
        self.on_command = None
        self.received: "list[str]" = []
        self.motions = 0
        self.steps_run: "list[str]" = []
        self._cur: "str | None" = "open"
        self._cur_i = 0
        self._closed = False

    def inject(self, kind: str, cid: "str | None" = None, value: float = 0.0) -> None:
        if kind not in FAULT_KINDS:
            raise ValueError(kind)
        self._faults.append(Fault(kind, cid, value))

    def inject_at(self, index: int, kind: str, value: float = 0.0) -> None:
        if kind not in FAULT_KINDS:
            raise ValueError(kind)
        self._faults_at[index] = Fault(kind, None, value)

    @property
    def moving(self) -> bool:
        return self.clock < self._busy_until

    def receive(self, data: bytes) -> None:
        if self.unplugged:
            raise TransportError("simulated cable pulled")
        if not data.endswith(b"\r") or data.count(b"\r") != 1:
            raise SimViolation(f"one command line with its CR per write: {data!r}")
        self._command(data[:-1].decode("ascii", "replace"))

    def pending(self, until: float) -> bytes:
        ready = sorted((e for e in self._out if e[0] <= until), key=lambda e: e[0])
        data = b"".join(b for _, b in ready)
        rest = [(t, b) for t, b in self._out if t > until]
        if len(data) > self.chunk:
            rest.insert(0, (until, data[self.chunk:]))
            data = data[:self.chunk]
        self._out = rest
        return data

    def next_time(self) -> "float | None":
        return min((t for t, _ in self._out), default=None)

    # ---- the sequence check (own copy) ------------------------------------------------
    def _sequence(self, line: str) -> None:
        if self._closed:
            raise SimViolation(f"{line!r} after the close")
        if self._cur == "open":
            seq = REC_OPEN6 if self.cold else REC_OPEN
            if self._cur_i < len(seq) and seq[self._cur_i] == line:
                self._cur_i += 1
                if self._cur_i == len(seq):
                    self._cur, self._cur_i = None, 0
                return
            raise SimViolation(f"{line!r} is not the next line of the recorded opening")
        if self._cur is not None:
            seq = REC_STEPS[self._cur]
            if self._cur_i < len(seq) and seq[self._cur_i] == line:
                self._cur_i += 1
                if self._cur_i == len(seq):
                    self.steps_run.append(self._cur)
                    if self._cur == "close":
                        self._closed = True
                    self._cur, self._cur_i = None, 0
                return
            raise SimViolation(f"{line!r} breaks the step {self._cur!r} at line {self._cur_i + 1}")
        if self.cold:
            raise SimViolation("nothing may follow the opening of a table just switched on")
        # a new step: the candidates are the steps not run yet whose first line matches
        cands = [k for k, s in REC_STEPS.items() if k not in self.steps_run and s[0] == line]
        if "free" in self.steps_run:
            cands = [k for k in cands if k == "close"]
        if not self.steps_run or self.steps_run == []:
            cands = [k for k in cands if k != "close"]
        if not cands:
            raise SimViolation(f"{line!r} starts no step that may come now")
        self._cands = cands
        self._cur, self._cur_i = "_choose", 1
        self._prefix = [line]

    def _sequence_choose(self, line: str) -> bool:
        if self._cur != "_choose":
            return False
        self._prefix.append(line)
        cands = [k for k in self._cands if REC_STEPS[k][:len(self._prefix)] == self._prefix]
        # a finished short step ("home") followed by the start of another one
        done = [k for k in self._cands if REC_STEPS[k] == self._prefix[:-1]]
        if not cands and done:
            self.steps_run.append(done[0])
            self._cur, self._cur_i = None, 0
            self._sequence(line)
            return True
        if not cands:
            raise SimViolation(f"{self._prefix} matches no step that may come now")
        self._cands = cands
        full = [k for k in cands if REC_STEPS[k] == self._prefix]
        if full and len(cands) == 1:
            self.steps_run.append(full[0])
            if full[0] == "close":
                self._closed = True
            self._cur, self._cur_i = None, 0
        return True

    def finish(self) -> None:
        """At the end of a run: a step that was complete but still ambiguous counts."""
        if self._cur == "_choose":
            done = [k for k in self._cands if REC_STEPS[k] == self._prefix]
            if done:
                self.steps_run.append(done[0])
                self._cur = None

    # ---- physics (own beliefs) --------------------------------------------------------
    def _physics(self, line: str) -> None:
        if self.moving:
            raise SimViolation(f"{line[1:3]} sent while the arm is still moving")
        here = (self.pos[0], self.pos[1])
        if line == I1:
            ok = (_rest_guard(here) or (not self.free_arm and (_near(here, (1000, 1500))
                                                              or _near(here, (1102, 1498)))))
            if not ok:
                raise SimViolation(f"i1 from {here}: not a place this copy allows")
        if line in TARGET:
            if self.free_arm:
                raise SimViolation("a move while the arm is free")
            start_ok = {M250: _out_start(here), M1000: _near(here, (1102, 250)),
                        M1498: _out_start(here) or _near(here, (2507, 1498)),
                        M2507: _near(here, (1102, 1498))}[line]
            if not start_ok:
                raise SimViolation(f"{line} from {here}: not a recorded start")
        if line == F1 and not _rest_guard(here):
            raise SimViolation("f1 away from the resting place")

    def _fault_for(self, cid: str) -> "Fault | None":
        for f in self._faults:
            if f.cid in (None, cid):
                self._faults.remove(f)
                return f
        return None

    def _reply(self, t: float, line: str) -> None:
        self._out.append((t, (line + checksum(line).upper() + "\r").encode("ascii")))

    def _command(self, line: str) -> None:
        self.received.append(line)
        m = _HOST_RE.fullmatch(line)
        if not m or not checksum_ok(line):
            raise SimViolation(f"malformed line or bad checksum: {line!r}")
        cid, args = m.group(1), m.group(2)
        if not self._sequence_choose(line):
            self._sequence(line)
        self._physics(line)
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
        if kind == "long_line":
            self._out.append((t0 + 0.01, b":!" + b"A" * 40 + b"\r"))
            return
        if kind == "refuse":
            self._reply(t0 + 0.016, f":#{cid}{int(fault.value or 1):X}")
            return
        if kind == "wrong_cid":
            self._reply(t0 + 0.01, f":!{'s0' if cid != 's0' else 'p0'}")
            return
        self._reply(t0 + 0.01, f":!{cid}")
        if kind == "stray":
            self._reply(t0 + 0.01, ":$s00")
        if kind == "status":
            status, data, duration = int(fault.value or 3), "", 0.02
        else:
            status, data, duration = self._execute(line, cid, args, fault)
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
        if line == I1 or line in TARGET:
            self._busy_until = t_done

    def _xy(self, x: float, y: float) -> str:
        return f"{int(round(x)) & 0xFFFF:04X}{int(round(y)) & 0xFFFF:04X}"

    def _execute(self, line: str, cid: str, a: str, fault: "Fault | None"):
        kind = fault.kind if fault else None
        if cid == "s0":
            return 0, "", 0.0
        if cid == "a1":
            return 0, ("005D010800" if kind == "identity" else IDENTITY), 0.0
        if cid == "k2":
            return 0, ("0B600000000014" if kind == "k2_other" else K2), 0.0
        if cid == "u8":
            data = _memory_a() if a == "000060000100" else _memory_b()
            if kind == "memory_short":
                data = data[:-2]
            if kind == "memory_bad_start":
                data = "00" + data[2:]
            return 0, data, 0.106 if a == "000060000100" else 0.051
        if cid == "a0":
            if kind == "a0_other":
                return 0, "120000", 0.0
            return 0, ("111800" if self.cold else "130000"), 0.0
        if cid == "f4":
            if kind == "free":
                return 0, ("01" if self.mode == "00" else "00"), 0.0
            return 0, self.mode, 0.0
        if cid == "f1":
            self.mode, self.free_arm = "01", True
            return 0, "01", 0.0
        if cid == "f3":
            return 0, "00", 0.0
        if cid == "f0":
            self.mode = "00"
            return 0, "00", 0.0
        if cid == "p0":
            drift = fault.value if kind == "drift" else 0.0
            jx, jy = ((self._rng.choice((0, 0, 1)) * 0, self._rng.choice((-1, 0, 0, 1)))
                      if self.jitter else (0, 0))
            return 0, self._xy(self.pos[0] + drift + jx, self.pos[1] + drift + jy), 0.0
        # movements
        self.motions += 1
        if line == I1:
            start = (self.pos[0], self.pos[1])
            target = (1102.0, float(self._rng.choice((0, 1, 2))))
            if _rest_guard(start):
                t = 0.048 if abs(start[1]) <= 3 else 0.17 + abs(start[1]) * 0.0038
            else:
                t = 2.4
            self.free_arm = False          # the homing takes the arm again
        else:
            target = (float(TARGET[line][0]), float(TARGET[line][1]))
            t = DURATION[line]
        if kind == "slow_motion":
            t += 8.0
        if kind == "fast_motion":
            t = 0.02
        if kind == "blocked":
            f = max(0.0, min(1.0, fault.value))
            target = (self.pos[0] + f * (target[0] - self.pos[0]) + 300,
                      self.pos[1] + f * (target[1] - self.pos[1]) + 300)
        self.pos = [target[0], target[1]]
        return 0, "", t


def todays_table(**kw) -> SimTable:
    """The tester's table as it answered 0.2.1 on 15 Nov 2026 (run 5): started, f4 00 x4,
    the arm at (1101, 55)."""
    return SimTable(cold=False, pos=[1101.0, 55.0], jitter=False, **kw)


class SimTransport:
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
