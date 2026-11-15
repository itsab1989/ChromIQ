# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""A SIMULATED i1iO 2 table. It never touches hardware.

It answers like the tester's table did in the recordings (two lines per
command, correct checksums, the recorded constant answers, a0 111800 when it
has just been switched on and 130000 once started, i1 at the resting place in
about 0.25 s), on a VIRTUAL clock, so a run takes no real
time. Where the recordings say nothing, its values are invented; its memory
block is SYNTHETIC (a made-up serial number, never the tester's).

It is STRICT. It holds its own copy of the two recorded sequences (written
here from the recordings, on purpose NOT imported from `i1io_open_table`, so that a
mistake in one is caught by the other) and raises :class:`SimViolation` (and a
test fails) the moment the program sends anything that is not the next line of
the sequence for the table's state (on a table just switched on: the six
reading lines of the opening and nothing else), or sends a line while the arm
moves, or i1 from anywhere but the resting place, or i0 at all.

Faults can be injected for the tests (:meth:`SimTable.inject`, :meth:`inject_at`).
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field

from i1io_open_table import TransportError, checksum, checksum_ok


class SimViolation(AssertionError):
    """The program sent the simulated table something it must never send."""


#: The recorded opening, the same cold (S1 1.141-1.502) and warm (R2 34.546-34.906).
REC_OPEN = [";a133", ";a133", ";k228", ";u8000060000100d1", ";u8000061000068c3", ";a034"]
#: After a0 on a warm table (R2 34.932-34.985, 378.530-378.585): s0, f4 x4; after the
#: person's yes ONE homing as i1Profiler sent it right before a close: s0 p0 i1 s0, then,
#: after the look, s0 f0 f3 (S1 4.766-22.951, R2 268.621-361.611). No p0 after the
#: homing: no recording follows p0 with s0.
REC_FOLLOW = [";s022", ";f42b", ";f42b", ";f42b", ";f42b",
              ";s022", ";p025", ";i12b", ";s022",
              ";s022", ";f02f", ";f32c"]
#: A table just switched on gets the opening's six reading lines and nothing more.
REC_COLD = list(REC_OPEN)
REC_WARM = REC_OPEN + REC_FOLLOW
#: Optionally, after the close: i1Profiler's re-opening up to its position read (R2 378.147-
#: 378.617, after its close at 361.611), and nothing more (the i1 that followed is not sent).
REC_REREAD = REC_OPEN + [";s022", ";f42b", ";f42b", ";f42b", ";f42b", ";s022", ";p025"]

IDENTITY = "005D010702"
K2 = "0B600000000013"
HOME = (1102, 0)
ACCEL = 2000.0
_HOST_RE = re.compile(r";([a-z][0-9])([0-9a-f]*)([0-9a-f]{2})")
#: A made-up serial number in the synthetic memory block (the tests check it
#: never reaches the log or the screen).
FAKE_SERIAL = "SIM0000TEST"


def _memory_a() -> str:
    head = "6801000056312E31"
    filler = "0102030405060708090A0B0C"                  # invented, not the table's
    serial = FAKE_SERIAL.encode("ascii").hex().upper()
    body = head + filler + serial
    return body + "AB" * ((512 - len(body)) // 2)


def _memory_b() -> str:
    return "FF" * 96 + "0102030405060708"           # invented, not the table's


def _at_home(p) -> bool:
    """The simulator's own copy (not imported) of where i1Profiler sent i1 from at rest in the
    recordings: X 1102, Y 0..47, plus one unit."""
    return 1101 <= p[0] <= 1103 and -1 <= p[1] <= 48


@dataclass
class Fault:
    kind: str
    cid: "str | None" = None
    value: float = 0.0


FAULT_KINDS = ("no_answer", "no_done", "late", "bad_checksum", "garbled", "status",
               "wrong_cid", "stray", "extra_line", "blocked", "drift", "unplug", "free",
               "identity", "refuse", "a0_other", "k2_other", "memory_short",
               "memory_bad_start", "long_line", "slow_motion", "bad_checksum_memory")


@dataclass
class SimTable:
    cold: bool = False                # True: switched on and not yet started (a0 111800)
    pos: "list[float]" = field(default_factory=lambda: [1102.0, 30.0])
    arm: str = "00"
    clock: float = 0.0
    seed: int = 1
    unplugged: bool = False
    #: at most this many bytes per read (the FTDI chip: 62 per packet)
    chunk: int = 62
    #: replay of a real run: where the homing leaves the arm and how long it takes
    #: (None: invented values), and no +-1 jitter on the position reads
    home_y: "float | None" = None
    home_s: "float | None" = None
    home_x: "float | None" = None
    jitter: bool = True

    def __post_init__(self):
        self._rng = random.Random(self.seed)
        self._out: "list[tuple[float, bytes]]" = []
        self._busy_until = 0.0
        self._faults: "list[Fault]" = []
        self._faults_at: "dict[int, Fault]" = {}
        self.on_command = None
        self.received: "list[str]" = []
        self.motions = 0
        self._expect = list(REC_COLD if self.cold else REC_WARM + REC_REREAD)

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

    # ---- the wire -----------------------------------------------------------
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

    # ---- commands -------------------------------------------------------------
    def _fault_for(self, cid: str) -> "Fault | None":
        for f in self._faults:
            if f.cid in (None, cid):
                self._faults.remove(f)
                return f
        return None

    def _reply(self, t: float, line: str) -> None:
        self._out.append((t, (line + checksum(line).upper() + "\r").encode("ascii")))

    def _check(self, line: str, cid: str) -> None:
        index = len(self.received) - 1
        if index >= len(self._expect) or self._expect[index] != line:
            want = self._expect[index] if index < len(self._expect) else "nothing more"
            raise SimViolation(f"line {index + 1} is {line!r}; the recorded sequence for a "
                               f"{'cold' if self.cold else 'warm'} table has {want!r} there")
        if self.moving:
            raise SimViolation(f"{cid} sent while the arm is still moving")
        here = (self.pos[0], self.pos[1])
        if cid == "i0":
            raise SimViolation("i0 is not in this program")
        if cid == "i1":
            if self.arm != "00":
                raise SimViolation("i1 while the arm is free")
            if not _at_home(here):
                raise SimViolation(f"i1 from {here}: only from the resting place")

    def _command(self, line: str) -> None:
        self.received.append(line)
        m = _HOST_RE.fullmatch(line)
        if not m or not checksum_ok(line):
            raise SimViolation(f"malformed line or bad checksum: {line!r}")
        cid, args = m.group(1), m.group(2)
        self._check(line, cid)
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
            other = "s0" if cid != "s0" else "p0"
            self._reply(t0 + 0.01, f":!{other}")
            return
        # A BELIEF, not a recording: a table just switched on refuses everything
        # but the opening. Observed only once: ':#s01' to s0 after a1, a1 (the
        # tester's run 1 of 0.1.0, without k2, u8, a0). The sequence check above
        # stops the program's lines before this matters.
        if self.cold and cid not in ("a1", "k2", "u8", "a0"):
            self._reply(t0 + 0.016, f":#{cid}1")
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
        if kind in ("bad_checksum", "bad_checksum_memory"):
            bad = (int(checksum(done), 16) + 1) & 0xFF
            self._out.append((t_done, (done + f"{bad:02X}\r").encode("ascii")))
        else:
            self._reply(t_done, done)
        if kind == "extra_line":
            self._reply(t_done, ":$p00")
        if cid == "i1":
            self._busy_until = t_done

    def _xy(self, x: float, y: float) -> str:
        return f"{int(round(x)) & 0xFFFF:04X}{int(round(y)) & 0xFFFF:04X}"

    def _execute(self, cid: str, a: str, fault: "Fault | None"):
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
            return 0, ("01" if kind == "free" else self.arm), 0.0
        if cid in ("f0", "f3"):
            return 0, "00", 0.0
        if cid == "p0":
            drift = fault.value if kind == "drift" else 0.0
            jx, jy = ((self._rng.choice((-1, 0, 0, 1)), self._rng.choice((-1, 0, 0, 1)))
                      if self.jitter else (0, 0))
            return 0, self._xy(self.pos[0] + drift + jx, self.pos[1] + drift + jy), 0.0
        self.motions += 1
        slow = 8.0 if kind == "slow_motion" else 0.0
        # i1 at the resting place: recorded 0.224-0.352 s
        # a replayed homing ends where the real one ended, after the real one's time
        replay = self.home_y is not None and self.motions == 1
        target = (float(self.home_x if (replay and self.home_x is not None) else HOME[0]),
                  float(self.home_y if replay else self._rng.choice((0, 1, 2))))
        # recorded at rest: 0.047-0.048 s from Y 0..2, 0.224-0.352 s from Y 14..47
        t = (self.home_s if (replay and self.home_s is not None)
             else 0.048 if abs(self.pos[1]) <= 3 else 0.17 + abs(self.pos[1]) * 0.0038)
        if kind == "blocked":
            f = max(0.0, min(1.0, fault.value))
            target = (self.pos[0] + f * (target[0] - self.pos[0]) + 300,
                      self.pos[1] + f * (target[1] - self.pos[1]) + 300)
        self.pos = [target[0], target[1]]
        return 0, "", t + slow


def tonights_table(**kw) -> SimTable:
    """The tester's real table as it answered version 0.2.0 on 14 Nov 2026 (his log; no
    serial in it): started (a0 130000), every arm answer 00, the arm at (1101, 46) before
    the homing, the homing answered 0.352 s after the line was sent (0.336 s after its
    acceptance; the recordings' times, like this program's, run from the line to the answer),
    the arm at (1102, 19) after it (0.2.1 reads no position after the homing; the value is
    kept for the replay of 0.2.0)."""
    return SimTable(cold=False, pos=[1101.0, 46.0], home_y=19.0, home_s=0.352, jitter=False,
                    **kw)


def todays_table(**kw) -> SimTable:
    """The tester's real table as it answered version 0.2.1 on 15 Nov 2026 (run 5; his log, no
    serial in it): started (a0 130000), every f4 answer 00, the arm at (1101, 55) right before
    the homing. 0.2.1 stopped there (its box ended at Y 50); 0.2.2 stops there too, as planned
    (i1Profiler sent the homing only from Y 0..47)."""
    return SimTable(cold=False, pos=[1101.0, 55.0], jitter=False, **kw)


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
