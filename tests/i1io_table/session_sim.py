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

0.4.0 adds part B (the recorded spot row): its own copy of the 29 new lines, a prefix
automaton of the whole part B session (:data:`B_GRAMMAR`), m1 as a 0.40 s move that ends
where the REAL table put the opening, (2507, 1429) (read twice on the volunteer's i1iO 2 on
17 Nov 2026; tests set `m1_lands_at` to any other place to see the program stop), f1 at the
alignment start, a scripted HAND (:meth:`SimTable.hand_to`) that may
only move a free arm, the first patch move re-engaging the motors (f4 keeps 01 until f0),
and the 28 recorded targets with their recorded times.
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field

from workflow.i1io.table.session_table import TransportError, checksum, checksum_ok


class SimViolation(AssertionError):
    """The program sent the simulated table something it must never send."""


A1, K2L, UA, UB, A0 = ";a133", ";k228", ";u8000060000100d1", ";u8000061000068c3", ";a034"
S0, F4, P0, I1, F0, F3, F1 = ";s022", ";f42b", ";p025", ";i12b", ";f02f", ";f32c", ";f12e"
M250, M1000 = ";m0044e00fa012c0e", ";m003e805dc012c06"
M1498, M2507 = ";m0044e05da012c0b", ";m009cb05da012cda"
M1L = ";m10b10055b012c42"
#: 0.6.0: the start-up of a table just switched on (the simulator's own copy, S1 1.517)
I0 = ";i02c"
#: S1 1.517 to 4.684: the one recorded start-up took 3.167 s; the arm read (1102, 14) after it
I0_RECORDED_S = 3.167
I0_RECORDED_AFTER = (1102.0, 14.0)
#: the simulator's own copy of the 28 spot lines of S2 session 3 (S2 454.218-495.037)
SPOTS = (";m0fb63067a012c03 ;m0fbba067b012ca8 ;m0fc11067b012c08 ;m0fc68067b012cfc "
         ";m0fcbf067b012ca2 ;m0fd17067b012c01 ;m0fd6e067c012ccd ;m0fdc5067c012cd0 "
         ";m0fe1c067c012cd3 ;m0fe74067c012cfc ;m0fecb067c012ca2 ;m0ff22067d012c01 "
         ";m0ff79067d012cf5 ;m0ffd0067d012cd1 ;m00027067d012c68 ;m0007e067d012c35 "
         ";m000d5067d012c38 ;m0012c067e012c3a ;m00184067e012c63 ;m001db067e012c09 "
         ";m00232067e012c69 ;m00289067e012c5d ;m002e0067f012c38 ;m00338067f012c61 "
         ";m0038f067f012c2e ;m003e6067f012c31 ;m0043d067f012c34 ;m00495067f012c5d").split()

REC_OPEN6 = [A1, A1, K2L, UA, UB, A0]
REC_OPEN = REC_OPEN6 + [S0, F4, F4, F4, F4]
_HF = [S0, P0, I1, S0]
#: 0.6.0: S1 as recorded, the opening of a cold table through the start-up's homing
REC_COLD_OPEN = REC_OPEN6 + [I0] + REC_OPEN[6:] + _HF
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

#: Part B, as a sequence of (lines-of-one-repetition, min, max) items; every prefix of a
#: sentence of this grammar may be sent, nothing else.
_B_END = [S0, P0, I1, S0, F0, F4, F4, P0]
B_GRAMMAR = (
    (lambda r: REC_OPEN, 1, 1),
    (lambda r: _HF, 1, 1),
    (lambda r: [F4, F4, P0, M1498, P0, M2507, P0, M1L, P0, S0, F4, F4, F3, F4, F4, F1, F4,
                F4, P0], 1, 1),
    (lambda r: [S0, F4, F4, F4, F4, P0], 1, 1),
    (lambda r: [P0], 0, 5),
    (lambda r: [P0, P0, SPOTS[0], P0], 1, 1),
    (lambda r: [P0, SPOTS[r + 1]], 0, 27),
    (lambda r: _B_END, 1, 1),
    (lambda r: [S0, F0, F3], 0, 1),
)


def _b_closure(states):
    out, todo = set(), list(states)
    while todo:
        st = todo.pop()
        if st in out:
            continue
        out.add(st)
        i, r, o = st
        if i < len(B_GRAMMAR) and o == 0 and r >= B_GRAMMAR[i][1]:
            todo.append((i + 1, 0, 0))
    return out


def _b_step(states, line):
    nxt = set()
    for i, r, o in states:
        if i >= len(B_GRAMMAR):
            continue
        fn, lo, hi = B_GRAMMAR[i]
        if o == 0 and r >= hi:
            continue
        seq = fn(r)
        if seq[o] == line:
            nxt.add((i, r + 1, 0) if o + 1 == len(seq) else (i, r, o + 1))
    return _b_closure(nxt)


IDENTITY = "005D010702"
K2 = "0B600000000013"
HOME = (1102, 0)
_HOST_RE = re.compile(r";([a-z][0-9])([0-9a-f]*)([0-9a-f]{2})")
FAKE_SERIAL = "SIM0000TEST"
#: recorded durations of the moves (seconds from the line to the done-answer)
DURATION = {M250: 0.719, M1000: 1.599, M1498: 1.727, M2507: 1.695, M1L: 0.400}
TARGET = {M250: (1102, 250), M1000: (1000, 1500), M1498: (1102, 1498), M2507: (2507, 1498)}
#: the simulator's own reading of the spot targets (from its own copy of the lines)


def _xy_of(line):
    x, y = int(line[3:7], 16), int(line[7:11], 16)
    return (x - 0x10000 if x & 0x8000 else x, y - 0x10000 if y & 0x8000 else y)


SPOT_XY = {ln: _xy_of(ln) for ln in SPOTS}
#: MEASURED on the volunteer's i1iO 2 on 17 Nov 2026: m1 from (2507, 1498) and (2505, 1498) took
#: 0.400 s and p0 then read (2507, 1429), twice, with and without a chart. (Until then this was a
#: labelled belief, (2716, 1057), "the sight on (2832, 1371)": wrong, and because the simulator
#: carried the program's own wrong belief no test could catch it.) Tests set `m1_lands_at` to any
#: other place to see the program stop truthfully.
M1_LANDS = (2507.0, 1429.0)
#: i1Profiler's own m1 from (999, 1503), the recording of 17 Nov 2026 (and R1, R2): 1.759 s
M1_FROM_1000_S = 1.759
#: MEASURED on the volunteer's i1iO 2 on 18 Nov 2026 (ChromIQ 4.3.46, stage d1): when f1 let the
#: arm go at the alignment start, the next p0 (0.8 s after the one that read the m1 landing,
#: nobody asked to touch it) read (2501, 1441) where the held arm had read (2506, 1429): the
#: freed arm SETTLES by about (-5, +12) units. Until then this simulator's free arm stood
#: exactly where the motors had left it, so the program's "the free arm must not have moved
#: more than 5 units" check passed every test and stopped the first real run. Tests set
#: `release_settle` to (0, 0) for the old belief, or to a larger shift for a person's touch.
RELEASE_SETTLE_REAL = (-5.0, 12.0)
#: 4.3.50: every settle MEASURED on a real table: 18 Nov 2026 (above), and 19 Nov 2026, the first
#: complete page (ChromIQ 4.3.49: (2506, 1429) held, then free (2505, 1433)). The default stays
#: the larger one; tests drive the other too.
RELEASE_SETTLES_MEASURED = (RELEASE_SETTLE_REAL, (-1.0, 4.0))


def _first_start(p) -> bool:         # the simulator's own copy of where spot 1 may start
    return -1360 <= p[0] <= -1200 and 2600 <= p[1] <= 2700


def _memory_a(tile=None, serial: "str | None" = None) -> str:
    """The SYNTHETIC memory block: a made-up serial (*serial*, 4.3.49: another simulated table;
    at most 11 characters, so it stays in bytes 20-30); at bytes 88-231 filler, or *tile*: 36
    made-up white tile values (D-4b tests; never a real table's)."""
    import struct
    head = "6801000056312E31"
    serial = (serial or FAKE_SERIAL)[:11].ljust(11, "0")
    body = head + "0102030405060708090A0B0C" + serial.encode("ascii").hex().upper()
    out = body + "AB" * ((512 - len(body)) // 2)
    if tile is not None:
        vals = struct.pack("<36f", *tile).hex().upper()
        out = out[:176] + vals + out[176 + len(vals):]
    return out


def _memory_b() -> str:
    return "FF" * 96 + "0102030405060708"


def _near(p, q, d=10) -> bool:
    return abs(p[0] - q[0]) <= d and abs(p[1] - q[1]) <= d


def _rest_guard(p) -> bool:          # the simulator's own copy of where i1 may start at rest
    return 1101 <= p[0] <= 1103 and -1 <= p[1] <= 80


def _start_guard(p) -> bool:         # the simulator's own copy of the first homing's box (0.3.1)
    return 1090 <= p[0] <= 1115 and -1 <= p[1] <= 250


def _out_start(p) -> bool:           # where a move out from rest may start
    return 1101 <= p[0] <= 1103 and -1 <= p[1] <= 48


@dataclass
class Fault:
    kind: str
    cid: "str | None" = None
    value: float = 0.0


FAULT_KINDS = ("no_answer", "no_done", "late", "bad_checksum", "garbled", "status",
               "wrong_cid", "stray", "extra_line", "blocked", "drift", "unplug", "free",
               "identity", "refuse", "a0_other", "a0_after_hand", "k2_other", "memory_short",
               "memory_bad_start", "long_line", "slow_motion", "fast_motion", "short_homing")
#: "short_homing" (4.3.51 fix round, review MUST-1): the homing (i1) answers done with status 0 in
#: its usual time, but the arm stops short of its resting place, on the way it came: *value* is
#: the share of the way still left (0 < value < 1, default 0.5; from (1098, 810) it stops at
#: (1100, 405)). INVENTED: no recording shows it; it is the case the reading after every homing
#: is there to catch (a homing that reports done and does not arrive).
SHORT_HOMING_LEFT = 0.5


def short_homing_stop(start, rest, value) -> "list[float]":
    """Where the arm of a "short_homing" fault stops: *value* of the way from *rest* back to
    *start* (the simulator's own model)."""
    f = value if 0.0 < (value or 0.0) < 1.0 else SHORT_HOMING_LEFT
    return [rest[0] + f * (start[0] - rest[0]), rest[1] + f * (start[1] - rest[1])]


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
    #: where the opening reads after m1 (default: where the real table put it)
    m1_lands_at: "tuple[float, float]" = M1_LANDS
    #: how far the arm shifts when f1 lets it go (default: what the real table did, 18 Nov)
    release_settle: "tuple[float, float]" = RELEASE_SETTLE_REAL
    #: 0.6.0, a cold table: how long its start-up takes, and where the arm stands after it
    #: (default: as recorded in S1; the tests set other values for the late and the away models)
    i0_s: float = I0_RECORDED_S
    i0_after: "tuple[float, float]" = I0_RECORDED_AFTER
    #: True once the start-up has finished (a cold table then behaves like a started one)
    started: bool = False
    #: D-4b tests: 36 MADE-UP white tile values at bytes 88-231 of the memory block (None:
    #: filler there, which is no white tile)
    stored_tile: "tuple | None" = None

    def __post_init__(self):
        self._rng = random.Random(self.seed)
        self._out: "list[tuple[float, bytes]]" = []
        self._busy_until = 0.0
        self._faults: "list[Fault]" = []
        self._faults_at: "dict[int, Fault]" = {}
        self.on_command = None
        self.received: "list[str]" = []
        self.received_at: "list[float]" = []
        self.motions = 0
        self.steps_run: "list[str]" = []
        self._cur: "str | None" = "open"
        self._cur_i = 0
        self._closed = False
        # part B: the prefix automaton runs beside part A's own sequence check
        self._a_alive = True
        self._b_states = _b_closure({(0, 0, 0)}) if not self.cold else set()
        self.hand_moves: "list[tuple[float, float]]" = []
        self._b_arm = False

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
            seq = REC_COLD_OPEN if self.cold else REC_OPEN
            if self._cur_i < len(seq) and seq[self._cur_i] == line:
                self._cur_i += 1
                if self._cur_i == len(seq):
                    self._cur, self._cur_i = None, 0
                    if self.cold:
                        self._b_arm = True      # part B may start now, after the opening
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
        if self.cold and not self.started:
            raise SimViolation("nothing but the start-up may follow the opening of a table just "
                               "switched on")
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

    def _check_sequence(self, line: str) -> None:
        """Part A's own step check and part B's automaton side by side: a line is allowed if
        it continues either of them (they share the opening and the first homing)."""
        a_err = None
        if self._a_alive:
            try:
                if not self._sequence_choose(line):
                    self._sequence(line)
            except SimViolation as exc:
                self._a_alive, a_err = False, exc
        self._b_states = _b_step(self._b_states, line) if self._b_states else set()
        if self._b_arm:
            self._b_states, self._b_arm = _b_closure({(1, 0, 0)}), False
        if not self._a_alive and not self._b_states:
            raise a_err or SimViolation(f"{line!r} continues neither part A nor part B")

    @property
    def part_b_line_count(self) -> int:
        return len(self.received) if self._b_states else 0

    #: where the scripted hand puts the free arm at each placement try (the last one repeats)
    hand_script = ((-1290.0, 2660.0),)

    def hand(self, n: int) -> None:
        """The scripted hand of a simulated run: placement try *n* (1 = the first)."""
        x, y = self.hand_script[min(n, len(self.hand_script)) - 1]
        self.hand_to(x, y)

    def hand_to(self, x: float, y: float) -> None:
        """The person's hand moves the arm. Only a FREE arm, and never while it moves."""
        if self.moving:
            raise SimViolation("the hand moved the arm while it was moving")
        if not self.free_arm:
            raise SimViolation("the hand pushed an arm that the motors hold")
        self.pos = [float(x), float(y)]
        self.hand_moves.append((float(x), float(y)))

    # ---- physics (own beliefs) --------------------------------------------------------
    def _cold_rules(self, line: str) -> None:
        """0.6.0, the simulator's own rules for a table just switched on (both modes): until
        its start-up has finished it takes only the reading lines of the opening and then i0,
        once, right after a0; a started table never gets i0."""
        if line == I0:
            if not self.cold or self.started or self.i0_sent:
                raise SimViolation("i0 on a table that is not just switched on, or a second time")
            if len(self.received) < 2 or self.received[-2] != A0:
                raise SimViolation("i0 not right after a0")
            if self.moving:
                raise SimViolation("i0 while the arm moves")
            self.i0_sent = True
            return
        if self.cold and not self.started and line not in REC_OPEN6:
            raise SimViolation(f"{line!r} before the start-up of a table just switched on")

    i0_sent = False

    def _physics(self, line: str) -> None:
        if self.moving:
            raise SimViolation(f"{line[1:3]} sent while the arm is still moving")
        here = (self.pos[0], self.pos[1])
        if line == I1:
            ok = (_start_guard(here) or (not self.free_arm and (
                _near(here, (1000, 1500)) or _near(here, (1102, 1498))
                or any(_near(here, t) for t in SPOT_XY.values()))))
            if not ok:
                raise SimViolation(f"i1 from {here}: not a place this copy allows")
        if line == M1L:
            if self.free_arm or not (_near(here, (2507, 1498)) or _near(here, (1000, 1500))):
                raise SimViolation(f"m1 from {here}: not a recorded start")
        if line in SPOT_XY:
            k = SPOTS.index(line)
            if k == 0:
                if not self.free_arm or not _first_start(here):
                    raise SimViolation(f"the first patch move from {here} (free "
                                       f"{self.free_arm}): not a recorded start")
            elif self.free_arm or not _near(here, SPOT_XY[SPOTS[k - 1]]):
                raise SimViolation(f"patch move {k + 1} from {here}: not the previous patch")
        if line in TARGET:
            if self.free_arm:
                raise SimViolation("a move while the arm is free")
            start_ok = {M250: _out_start(here), M1000: _near(here, (1102, 250)),
                        M1498: _out_start(here) or _near(here, (2507, 1498)),
                        M2507: _near(here, (1102, 1498))}[line]
            if not start_ok:
                raise SimViolation(f"{line} from {here}: not a recorded start")
        if line == F1 and not (_rest_guard(here) or _near(here, self.m1_lands_at)):
            raise SimViolation("f1 away from the resting place and the alignment start")

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
        self.received_at.append(self.clock)
        m = _HOST_RE.fullmatch(line)
        if not m or not checksum_ok(line):
            raise SimViolation(f"malformed line or bad checksum: {line!r}")
        cid, args = m.group(1), m.group(2)
        self._cold_rules(line)
        self._check_sequence(line)
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
        if line in (I1, I0) or line in TARGET or line == M1L or line in SPOT_XY:
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
            data = (_memory_a(self.stored_tile, getattr(self, "serial", None))
                    if a == "000060000100" else _memory_b())
            if kind == "memory_short":
                data = data[:-2]
            if kind == "memory_bad_start":
                data = "00" + data[2:]
            return 0, data, 0.106 if a == "000060000100" else 0.051
        if cid == "a0":
            if kind == "a0_other":
                return 0, "120000", 0.0
            if kind == "a0_after_hand":
                # the volunteer's real table, 19 Nov 2026 (two openings, 12:37 and 12:38):
                # `:$a00530000B9` after the arm had been moved by hand and put back
                return 0, "530000", 0.0
            return 0, ("111800" if self.cold else "130000"), 0.0
        if cid == "f4":
            if kind == "free":
                return 0, ("01" if self.mode == "00" else "00"), 0.0
            return 0, self.mode, 0.0
        if cid == "f1":
            if not self.free_arm:
                # the motors let go: the arm settles (RELEASE_SETTLE_REAL, measured)
                self.pos = [self.pos[0] + float(self.release_settle[0]),
                            self.pos[1] + float(self.release_settle[1])]
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
        if line == I0:
            # the simulator's own model of the start-up (what the arm does is not recorded): it
            # ends at i0_after, and the table is started from then on
            self.started = True
            self.pos = [float(self.i0_after[0]), float(self.i0_after[1])]
            self.free_arm = False
            t = self.i0_s
            if kind == "slow_motion":
                t += 8.0
            if kind == "fast_motion":
                t = 0.02
            return 0, "", t
        if line == I1:
            start = (self.pos[0], self.pos[1])
            target = (1102.0, float(self._rng.choice((0, 1, 2))))
            if _start_guard(start):
                t = 0.048 if abs(start[1]) <= 3 else 0.17 + abs(start[1]) * 0.0038
            elif any(_near(start, p) for p in SPOT_XY.values()):
                t = 2.5 + abs(start[0] - 1102) * 0.0005     # 2.54 s from (1173, 1663)
            else:
                t = 2.4
            self.free_arm = False          # the homing takes the arm again
        elif line == M1L:
            # as the real table: 0.400 s from (2507, 1498), 1.759 s from i1Profiler's (999, 1503)
            target = self.m1_lands_at
            t = DURATION[M1L] if _near(self.pos, (2507, 1498)) else M1_FROM_1000_S
        elif line in SPOT_XY:
            target = SPOT_XY[line]
            if SPOTS.index(line) == 0:
                d = max(abs(target[0] - self.pos[0]), abs(target[1] - self.pos[1]))
                t = 2 * math.sqrt(d / 2000.0) + 0.02         # 1.45 s from (-1297, 2681)
            else:
                t = 0.431
            self.free_arm = False          # the motors take the arm again; f4 stays 01
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
        if kind == "short_homing" and line == I1:
            target = tuple(short_homing_stop(self.pos, target, fault.value))
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
