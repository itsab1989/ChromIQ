# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""Part C (0.5.0) on a SIMULATED table and a FAKE instrument. Never touches hardware.

The table is 0.4.0's simulator (i1io_session_sim.SimTable) extended in a clearly marked part C
mode, with its OWN copies of part C's rules (written here, on purpose not imported from the
program): the five further fixed lines, the computed-move form, the recorded speeds, the
measuring area and the swept rectangle from the arm's real position, p1 only with the arm free,
a3 and c3 only right after a scan move, no line while the arm moves or a scan move waits, and a
scan move that starts only on the instrument's lamp after c3. It raises SimViolation the moment
any of these is broken. Its timings are the recorded ones (SEQUENCE.md section 10); where the
recordings say nothing (where p1 reads relative to the arm, how a sheet looks) its values are
labelled beliefs or invented.

The fake instruments answer like ChromIQ's helper: a spot reader (patch by patch) and a strip
reader (the table-scan mode), on the simulator's clock, with faults on both sides.
"""
from __future__ import annotations

import math
import os
import random

from tests.i1io_table.session_sim import (F1, I1, SPOT_XY, SPOTS, M1L, M1498, M2507, SimTable, SimViolation,
                              _near, _first_start, _out_start, short_homing_stop)
from workflow.i1io.table.session_table import checksum, checksum_ok

#: When the simulated table starts a scan move, after the lamp trigger. The simulator's OWN
#: number, deliberately not the stage's: until 0.5.1 the simulator used the same 0.43 as the
#: stage, so a wrong constant could never show in a test. Measured on the recordings (value
#: replay, 20 passes; study/i1io-scan 9f01e8acd): lamp + 0.3718 s, sd 0.0027 s.
TABLE_MOTION_START_AFTER_LAMP_S = 0.372
#: THE DUAL ROW (the volunteer's recordings of 18 Nov 2026, the simulator's own copies): the UV
#: pass's move starts 0.233-0.240 s after its trigger, its first reading comes at +0.231 s; the
#: done answers came at lamp trigger + T + A + 0.653 s and UV trigger + T + A + 0.345 s (B 48.097,
#: 53.265), the lamp pass's data 3.12 s and the UV pass's 2.98 s after their triggers (N 550)
TABLE_MOTION_START_AFTER_UV_S = 0.236
UV_FIRST_READING_S = 0.231
DUAL_DONE_EXTRA = {"lamp": (0.62, 0.68), "uv": (0.33, 0.36)}

# ---- the simulator's own copy of part C's rules ---------------------------------------------
C_P1, C_C4, C_D1, C_A3, C_C3 = ";p124", ";c42e", ";d1016d35", ";a331", ";c32f"
C_SPEEDS_M2 = (40, 53, 54, 61, 87, 88, 110, 118, 137, 138, 168)
#: the dual row's two recorded forms (the simulator's own copy): d1 210 and m2 at 132; d1 210 only
#: right after c4 that came right after a zero-length m0 from where a scan move ended; 132 only
#: in a sitting the simulator was told reads dual rows (``CSimTable.dual``)
C_D1_UV = ";d100d23a"
C_SPEEDS_DUAL = (132,)
#: targets: the sides (the simulator's own copy): right = the protocol's signed 16-bit range
#: since the 4.3.53 fix round (-1800 in the rows branch, the recorded extent -1384 until 4.3.52),
#: left = 2507 (where the table's m1 stops the arm); the front is physical since 4.3.49
#: (FRONT_END_Y below; the 3109 is kept for the record only)
C_TARGET_BOX = (-32768, 2507, 483, 3109)
#: 2026-11-21, the vendor's way home (the simulator's own copy of R1 and N3): speed 200, the two
#: points on the home line it drives to, and the line out of the back strip
C_DETOUR_SPEED = 200
C_DETOUR_TARGETS = ((1102, 1498), (1102, 1202))
C_BACK_STRIP_OUT_Y = 1202
C_SWEEP_BOX = (-1434, 1766, 473, 3114)         # the swept rectangle from where the arm is
#                                                (the cap plus the 5-unit arrival tolerance)
#: fix 2, the simulator's own copy of the front-zone rule: in front of the proven zone (targets
#: Y 2723, sweep 2773) a computed move may reach at most 50 units (5 mm) beyond the frontmost Y
#: the motors have already brought the arm to, an m0 there moves at most 50 units per axis, and a
#: scan move never goes beyond where the arm has been under motor.
C_PROVEN_Y = (2723, 2773)
C_CREEP = 50
#: BELIEF (LIKELY in the recordings): p1 reads the place the SENSOR must go to stand over what
#: the sight shows; the arm itself then stands this far from it (S2 383.3: (-106, -323)).
SIGHT_OFFSET = (-106, -323)
READING_S = 0.005004
#: 4.3.49 ("learn this table's reach once"): the simulated table's PHYSICAL front end: the
#: opening cannot be pushed by hand nor driven by its motors beyond this Y. The simulator's own
#: rule for targets is then physical: a computed target within 5 mm of this end (or beyond it)
#: is booked in ``end_targets`` (the program only ever learns an end the opening has reached).
#: 4.3.50: ASSUMED, and moved from 3400 (invented in 4.3.49) to 3450. On 19 Nov 2026 a real
#: i1iO 2 took the opening to Y 3370 under motor (13 steps of 5 mm from 2723, every one arrived
#: within 3 units, no status, no sign of an end): with 3400 that real target would have been
#: booked as one 5 mm from the end. Where the real end lies is still NOT known (beyond 3371);
#: 3450 puts it past the real arrival and its 5 mm margin. Tests that want an end met pass
#: ``front_end=`` (3400, 3230, 3180 ...) themselves.
FRONT_END_Y = 3450
FRONT_END_MARGIN = 50
FRONT_END_WHY = ("ASSUMED: the real arm reached Y 3370 under motor without meeting an end "
                 "(19 Nov 2026); the real end is somewhere beyond, not known")
#: 4.3.50: the real table answers a computed move of 0 to 3 units (its larger axis) at once:
#: 0.015-0.016 s from the line to the done answer, in 24 of 24 real and recorded cases
#: (tests/i1io_table/data/real_table_moves.json); 4 units and more take their travel time.
REAL_AT_ONCE_UNITS = 3
REAL_AT_ONCE_S = 0.016
#: 4.3.50: where the real arm rests after a homing: Y 28 (11 s after the start-up's homing), 30
#: (after the homing before the alignment), 32 (after the start-up) on 19 Nov 2026; 35 on
#: 18 Nov. The simulated homing ends at one of these (it then relaxes as REAL_REST_RELAX says).
REAL_REST_AFTER_HOMING_Y = (28, 29, 30, 31, 32)

#: 4.3.47 fix2: the volunteer's real table, where real data exists (``real_table=True``, the
#: default). i1Profiler's arrivals after its 48 spot moves on his table (17 Nov, REC3, next p0
#: minus target): dx -2..+3, dy -5..+1, as counts. Every computed m0 lands off by one draw.
REAL_ARRIVAL_DX = ((-2, 1), (-1, 4), (0, 16), (1, 19), (2, 6), (3, 2))
REAL_ARRIVAL_DY = ((-5, 1), (-1, 7), (0, 32), (1, 8))
#: His arm at rest after a homing, when nothing drives it (18 Nov, ChromIQ 4.3.46's log: after
#: the c1 homing (1102, 35), 17 s later with nothing sent (1101, 48); i1Profiler's own rests read
#: Y 1..48): it relaxes by about (-1, +13). The simulated arm does so once, at the first reading
#: at least REAL_RELAX_AFTER_S after a homing ended, until the next movement.
REAL_REST_RELAX = (-1, 13)
REAL_RELAX_AFTER_S = 1.0


#: 4.3.51: the homings of a held arm on the home line that the recordings time (the simulator's
#: own copy): (1102, 48) 0.352 s (the owner's start-up capture, 19 Nov 2026, at rest), (1098, 810)
#: 1.312 s (the same capture, the arm pushed out by hand), (1102, 1202) 1.599 s (12 Nov, R1
#: 85.848). Between them the simulated homing takes the straight-line time.
HOME_LINE_RECORDED_S = ((48.0, 0.352), (810.0, 1.312), (1202.0, 1.599))


def _homing_s(start, free) -> float:
    """How long the simulated i1 takes from *start* (the simulator's own model)."""
    on_line = 1090 <= start[0] <= 1115
    if on_line and start[1] <= 250:
        return 0.17 + abs(start[1]) * 0.0038
    if on_line and start[1] <= HOME_LINE_RECORDED_S[-1][0] and not free:
        pts = HOME_LINE_RECORDED_S
        for (y0, t0), (y1, t1) in zip(pts, pts[1:]):
            if start[1] <= y1:
                return t0 + (t1 - t0) * (start[1] - y0) / (y1 - y0)
    return 2.0 + max(abs(start[0] - 1102), abs(start[1])) * 0.0006 + (0.4 if free else 0.0)


def _draw(rng, counts):
    n = rng.randrange(sum(c for _v, c in counts))
    for v, c in counts:
        if n < c:
            return v
        n -= c
    return counts[-1][0]      # pragma: no cover


def _s16(h):
    v = int(h, 16)
    return v - 0x10000 if v & 0x8000 else v


def _inside(box, p):
    return box[0] <= p[0] <= box[1] and box[2] <= p[1] <= box[3]


class CSimTable(SimTable):
    """0.4.0's simulated table with part C's mode switched on (`part_c=True`)."""

    def __init__(self, *a, part_c=True, aims=None, real_table=True, front_end=FRONT_END_Y,
                 right_end=None, sight_offset=SIGHT_OFFSET, serial=None,
                 motors_have_been_to=None, **kw):
        super().__init__(*a, **kw)
        self.part_c = part_c
        #: 4.3.49: the physical ends of the opening's travel (right_end None: no right stop,
        #: the simulator before 4.3.49), where the person's sight sits relative to the opening
        #: (p1 = opening - sight_offset), and the serial in the memory block (another table)
        self.front_end = None if front_end is None else float(front_end)
        self.right_end = None if right_end is None else float(right_end)
        self.sight_offset = tuple(sight_offset)
        if serial is not None:
            self.serial = str(serial)
        #: every time a hand or a move reached an end: (what, x, y)
        self.at_end_events: "list[tuple[str, float, float]]" = []
        #: computed targets within 5 mm of the front end or beyond it: (cid, x, y)
        self.end_targets: "list[tuple[str, int, int]]" = []
        #: 4.3.47 fix2: arrivals a few units off and the resting arm relaxing (see REAL_*);
        #: False: the ideal table the frozen tester 0.6.0 captures were made on
        self.real_table = real_table
        self._real_rng = random.Random(self.seed * 7919 + 17)
        self._relax_due: "float | None" = None
        self.arrivals_off: "list[tuple[int, int]]" = []
        #: where the person's sight is put on marks 1, 2, 3 (sensor targets, table units)
        self.aims = list(aims or [])
        self.m2_pending = None
        self.instrument = None             # the fake strip reader (for the armed check)
        self.c_faults = {}
        self.violations = []
        self.read_spots: "list[tuple[float, float]]" = []
        self.p1_count = 0
        self.lamp_rng = random.Random(5)
        self.scan_moves = []
        #: the frontmost Y the motors have brought the arm to (4.3.49: on this simulated TABLE,
        #: earlier sittings included: *motors_have_been_to*)
        self.front_seen = float(max(C_PROVEN_Y[0], motors_have_been_to or 0))
        #: the dual row: this sitting may read dual rows (m2 at 132, d1 210 in its place)
        self.dual = False
        #: 2026-11-21: every move of the vendor's way home: (from, to)
        self.detour_moves: "list[tuple]" = []
        self.last_scan_end = None          # where the last scan move ended (the UV pass's start)
        self.zero_m0_at = None             # the received index of the last zero-length m0

    # -- the person's hand at an aim
    def aim(self, n: int) -> None:
        mark = self.aims[n - 1]
        self.hand_to(mark[0] + self.sight_offset[0], mark[1] + self.sight_offset[1])

    def _clamp(self, x: float, y: float, what: str) -> "tuple[float, float]":
        """The physical ends: a hand or a motor cannot take the opening beyond them."""
        if self.front_end is not None and y > self.front_end:
            self.at_end_events.append((what + " at the front end", x, self.front_end))
            y = self.front_end
        if self.right_end is not None and x < self.right_end:
            self.at_end_events.append((what + " at the right end", self.right_end, y))
            x = self.right_end
        return x, y

    def push_to_front(self, x: "float | None" = None) -> None:
        """4.3.49, the guided step: the person pushes the free arm gently towards the front, as
        far as it goes (at its X, or at *x*): it stops at the front end."""
        self.hand_to(self.pos[0] if x is None else x, (self.front_end or self.pos[1]) + 500.0)

    def pull_back(self, dy: float = 200.0, dx: float = 150.0) -> None:
        """The person pulls the arm back a little and away from the right side, and lets go."""
        self.hand_to(self.pos[0] + dx, self.pos[1] - dy)

    # -- part C's own checks, before anything happens
    def _check_sequence(self, line: str) -> None:
        if not self.part_c:
            return super()._check_sequence(line)
        if self._closed:
            raise SimViolation(f"{line!r} after the close")

    def _c_physics(self, line: str, cid: str, args: str) -> None:
        if self.m2_pending is not None and cid not in ("a3", "c3"):
            raise SimViolation(f"{cid} sent while a scan move waits or runs")
        if self.moving:
            raise SimViolation(f"{line[1:3]} sent while the arm is still moving")
        here = (self.pos[0], self.pos[1])
        if line == C_P1 and not self.free_arm:
            raise SimViolation("p1 with the arm held (recorded only with the arm free)")
        before = self.received[-2][1:3] if len(self.received) >= 2 else ""
        if cid == "a3" and before != "m2":
            raise SimViolation("a3 not right after a scan move")
        if cid == "c3" and before != "a3":
            raise SimViolation("c3 not right after a3")
        if cid in ("a3", "c3") and self.m2_pending is not None and self.m2_pending.get("lamp"):
            raise SimViolation(f"{cid} after the scan move had started")
        if line == C_D1_UV:
            n = len(self.received)
            if not self.dual or self.zero_m0_at is None or self.zero_m0_at != n - 3 \
                    or self.received[-2] != C_C4:
                raise SimViolation("d1 210 not right after c4 after the zero-length m0 at the "
                                   "end of a scan move")
        if cid in ("m0", "m2") and line not in SPOT_XY and line not in (M1498, M2507):
            x, y, v = _s16(args[0:4]), _s16(args[4:8]), int(args[8:12], 16)
            # 2026-11-21, the simulator's own copy of the vendor's way home: m0 at 200 only as
            # recorded (R1: from the back strip straight ahead to Y 1202, then to (1102, 1202);
            # N3: to (1102, 1498)), never from the back strip but straight ahead
            detour = cid == "m0" and v == C_DETOUR_SPEED
            if detour:
                in_strip = here[1] < C_SWEEP_BOX[2] and not 1090 <= here[0] <= 1115
                ok = ((in_strip and abs(x - here[0]) <= 1 and y == C_BACK_STRIP_OUT_Y) or
                      (not in_strip and (x, y) in C_DETOUR_TARGETS))
                if not ok:
                    raise SimViolation(f"a move at 200 from {here} to ({x}, {y}): not the "
                                       "vendor's way home")
                self.detour_moves.append((tuple(here), (x, y)))
            if cid == "m0" and v != 300 and not detour:
                raise SimViolation(f"m0 at {v}")
            # 4.3.54 ("Row speed"): a single row may run at any whole speed inside the frame of
            # the recorded ones (40..168), never at the dual row's 132
            in_frame = C_SPEEDS_M2[0] <= v <= C_SPEEDS_M2[-1] and v not in C_SPEEDS_DUAL
            if cid == "m2" and v not in C_SPEEDS_M2 and not in_frame \
                    and not (self.dual and v in C_SPEEDS_DUAL):
                raise SimViolation(f"m2 at {v}")
            if cid == "m2" and v in C_SPEEDS_DUAL and self.received[-3:-1] and \
                    self.received[-3] not in (C_D1, C_D1_UV):
                raise SimViolation("a scan move at 132 not after d1 and p0")
            if cid == "m0" and self.last_scan_end is not None and \
                    _near(here, self.last_scan_end) and _near(here, (x, y)):
                # the recorded zero-length m0 goes to the position p0 just reported, which may
                # differ by a unit or two from where the simulated arm "really" stands
                self.zero_m0_at = len(self.received) - 1
            # 4.3.49 (Basti's ruling): the sides and the back as before (a violation); the front
            # is PHYSICAL: a target within 5 mm of the simulated front end, or beyond it, is
            # what the real table may meet when a person aims further than its arm can take the
            # opening. What the real table then does is NOT KNOWN (no recording); the simulator
            # records it (``end_targets``) and its arm stalls at the end (``_clamp``)
            if not _inside((C_TARGET_BOX[0], C_TARGET_BOX[1], C_TARGET_BOX[2], math.inf),
                           (x, y)):
                raise SimViolation(f"{cid} to ({x}, {y}) outside the area")
            if self.front_end is not None and y > self.front_end - FRONT_END_MARGIN:
                self.end_targets.append((cid, x, y))
            if self.right_end is not None and x < self.right_end:
                # 4.3.53: a target beyond the simulated right end (the arm stalls there)
                self.end_targets.append((cid, x, y))
            # 4.3.49 (Basti's ruling of 19 Nov 2026): the arm stands where the simulated table
            # has it, so the way from there is not judged against where recordings happened to
            # read it; a computed move from the back strip at the resting place stays a violation
            if here[1] < C_SWEEP_BOX[2] and not detour:
                raise SimViolation(f"{cid} from {here} to ({x}, {y}): from the back strip")
            known = max(C_PROVEN_Y[0], self.front_seen)
            # 4.3.49: the front-zone oracle judges the target (the start is where the arm is)
            if y > known:
                if cid == "m2":
                    raise SimViolation(f"a scan move to Y {y} beyond where the motors have been "
                                       f"(Y {known:.0f})")
                if y > known + C_CREEP:
                    raise SimViolation(f"m0 to Y {y} more than 5 mm beyond the confirmed front "
                                       f"(Y {known:.0f})")
                if abs(x - here[0]) > C_CREEP or abs(y - here[1]) > C_CREEP:
                    raise SimViolation(f"a step into the front zone longer than 5 mm: {here} to "
                                       f"({x}, {y})")
            if cid == "m2":
                if self.free_arm:
                    raise SimViolation("a scan move with the arm free")
                inst = self.instrument
                if inst is None or not inst.ready_now():
                    raise SimViolation("a scan move while the instrument was not ready to fire")
        # 4.3.52 (the owner's ruling of 2026-11-20, the simulator's own copy): a HELD arm is
        # homed from wherever it stands, the ends of travel included; the one place that stays
        # a violation is physical: the back strip beside the white tile's holder (Y below 473,
        # off the home line X 1090..1115). 4.3.53 fix round 2 (the re-review's ruling): a FREE
        # arm the same (the homing is one line the table carries out by itself; the one recorded
        # refusal, R1 272.124, was inside 4.3.51's region)
        on_line = 1090 <= here[0] <= 1115
        if line == I1 and here[1] < C_SWEEP_BOX[2] and not on_line:
            raise SimViolation(f"i1 from {here}: from the back strip"
                               + (" with the arm free" if self.free_arm else ""))
        if line == M1L and (self.free_arm or not (_near(here, (2507, 1498))
                                                  or _near(here, (1000, 1500)))):
            raise SimViolation(f"m1 from {here}")
        if line == F1 and not _near(here, self.m1_lands_at):
            raise SimViolation("f1 away from the alignment start")
        if line in SPOT_XY:
            k = SPOTS.index(line)
            if k == 0 and not (self.free_arm and _first_start(here)):
                raise SimViolation(f"the first recorded patch move from {here}")
            if k > 0 and (self.free_arm or not _near(here, SPOT_XY[SPOTS[k - 1]])):
                raise SimViolation(f"recorded patch move {k + 1} from {here}")
        if line in (M1498, M2507):
            ok = _out_start(here) if line == M1498 else _near(here, (1102, 1498))
            if self.free_arm or not ok:
                raise SimViolation(f"{line} from {here}")

    def _command(self, line: str) -> None:
        """Every violation is also KEPT (the program turns a raised one into a stop, and a test
        must still see it)."""
        try:
            self._command_c(line)
        except SimViolation as exc:
            self.violations.append(str(exc))
            raise

    def hand_to(self, x: float, y: float) -> None:
        if self.part_c:
            x, y = self._clamp(float(x), float(y), "the hand")
        try:
            super().hand_to(x, y)
        except SimViolation as exc:
            self.violations.append(str(exc))
            raise

    def _command_c(self, line: str) -> None:
        if not self.part_c:
            return super()._command(line)
        self.received.append(line)
        self.received_at.append(self.clock)
        if not checksum_ok(line) or not line.startswith(";"):
            raise SimViolation(f"malformed line or bad checksum: {line!r}")
        cid, args = line[1:3], line[3:-2]
        self._cold_rules(line)
        self._check_sequence(line)
        self._c_physics(line, cid, args)
        if getattr(self, "silent", False):
            return
        index = len(self.received) - 1
        if self.on_command is not None:
            self.on_command(index)
        t0 = max(self.clock, self._busy_until)
        fault = self._faults_at.pop(index, None) or self._fault_for(cid)
        kind = fault.kind if fault else None
        if kind == "unplug":
            self.unplugged = True
            return
        if kind == "no_answer":
            return
        if kind == "refuse":
            self._reply(t0 + 0.016, f":#{cid}{int(fault.value or 1):X}")
            return
        if kind == "garbled":
            self._out.append((t0 + 0.01, b":!\xff\xfe\r"))
            return
        self._reply(t0 + 0.01, f":!{cid}")
        if cid == "m2":
            x, y, v = _s16(args[0:4]), _s16(args[4:8]), int(args[8:12], 16)
            d = math.hypot(x - self.pos[0], y - self.pos[1])
            self.m2_pending = {"to": (x, y), "v": v, "T": int(d * 100 / v), "A": 5 * v,
                               "c3": False, "from": tuple(self.pos), "lamp": False,
                               "ignore": kind == "no_done"}
            self.motions += 1
            return
        if kind == "no_done":
            if cid in ("m0", "m1", "i1", "i0"):
                self._busy_until = math.inf     # a movement that never reports its end
            else:
                self.silent = True              # the table answers nothing more
            return
        if kind == "status":
            status, data, duration = int(fault.value or 3), "", 0.02
        else:
            status, data, duration = self._c_execute(line, cid, args, fault)
        if kind == "late":
            duration += fault.value or 30.0
        if kind == "slow_motion":
            duration += 8.0
        done = f":${cid}{status:X}{data}"
        t_done = t0 + max(duration, 0.014)
        if kind == "bad_checksum":
            bad = (int(checksum(done), 16) + 1) & 0xFF
            self._out.append((t_done, (done + f"{bad:02X}\r").encode("ascii")))
        else:
            self._reply(t_done, done)
        if kind == "stray":
            self._reply(t0 + 0.01, ":$s00")
        if cid in ("m0", "m1", "i1", "i0"):
            self._busy_until = t_done

    def _c_execute(self, line, cid, a, fault):
        kind = fault.kind if fault else None
        if cid == "p0" and self.real_table and self._relax_due is not None \
                and self.clock >= self._relax_due:
            self._relax_due = None
            self.pos = [self.pos[0] + REAL_REST_RELAX[0], self.pos[1] + REAL_REST_RELAX[1]]
        if cid != "p0" and cid in ("m0", "m1", "m2", "i1", "i0"):
            self._relax_due = None
            self._scan_settle = None
        settle = getattr(self, "_scan_settle", None)
        if cid == "p0" and settle is not None:
            if settle[2] > 0:                      # the first reading still sees the offset
                self._scan_settle = (settle[0], settle[1], settle[2] - 1)
            else:
                self.pos = [settle[0], settle[1]]
                self._scan_settle = None
        if cid == "p1":
            self.p1_count += 1
            return 0, self._xy(self.pos[0] - self.sight_offset[0],
                               self.pos[1] - self.sight_offset[1]), 0.0
        if cid == "c4":
            v = self.c_faults.get("c4_byte", 0xBA)       # or a callable: the next answer
            v = v() if callable(v) else v
            return 0, v if isinstance(v, str) else f"{int(v):02X}", 0.20
        if cid == "d1":
            if line == C_D1_UV:
                return 0, self.c_faults.get("d1_uv_echo", "00D2"), 0.016
            return 0, self.c_faults.get("d1_echo", "016D"), 0.016
        if cid in ("a3", "c3") and self.m2_pending is None:
            return 3, "", 0.016             # INVENTED: no scan move waiting (it was lost)
        if cid == "a3":
            p = self.m2_pending
            # 4.3.54 (review M1): 'a3_v' makes the table answer another speed than was sent
            # (an int: that speed; a callable: the answer for the speed sent), as a table that
            # snapped an unrecorded speed to one of its own might
            v_ans = self.c_faults.get("a3_v")
            v = v_ans(p["v"]) if callable(v_ans) else (int(v_ans) if v_ans else p["v"])
            return 0, f"{p['A']:08X}{p['T'] + int(self.c_faults.get('a3_off', 0)):08X}" \
                      f"{v:04X}", 0.016
        if cid == "c3":
            self.m2_pending["c3"] = True
            return 0, "", 0.016
        if cid == "m0" and line not in SPOT_XY and line not in (M1498, M2507):
            x, y = _s16(a[0:4]), _s16(a[4:8])
            # 4.3.50: the straight line (the real table, 19 Nov 2026: a diagonal of 2598 x 1778
            # units took 2.528 s; the larger axis alone predicts 0.25 s less), and a move of up
            # to 3 units answered at once (REAL_AT_ONCE_S)
            if max(abs(x - self.pos[0]), abs(y - self.pos[1])) <= REAL_AT_ONCE_UNITS:
                t = REAL_AT_ONCE_S
            else:
                d = math.hypot(x - self.pos[0], y - self.pos[1])
                t = max(0.015, 2 * math.sqrt(d / 2000.0)) + 0.012
            self.motions += 1
            target_y = y
            off = self.c_faults.get("arrival_off", 0)
            if kind == "blocked":
                x, y = x + 300, y
            if "front_wall" in self.c_faults:      # a mechanical front end: the arm stalls there
                y = min(y, int(self.c_faults["front_wall"]))
            if self.real_table:
                ox, oy = _draw(self._real_rng, REAL_ARRIVAL_DX), _draw(self._real_rng,
                                                                     REAL_ARRIVAL_DY)
                self.arrivals_off.append((ox, oy))
                x, y = x + ox, y + oy
            cx, cy = self._clamp(float(x + off), float(y), "a computed move")
            self.pos = [cx, cy]
            x, y = cx - off, cy
            self.free_arm = False
            # 4.3.50: the frontmost place the motors brought the arm to is the TARGET it arrived
            # at within the arrival tolerance (as the job counts it), not the arrival drawn a
            # few units short: the job's next 5 mm step goes from that target (found by the
            # replay of the real page, whose steps a short draw would have refused)
            self.front_seen = max(self.front_seen, float(y),
                                  float(target_y) if abs(cy - target_y) <= 5 else float(y))
            return 0, "", t
        if cid == "i1":
            self.motions += 1
            start = (self.pos[0], self.pos[1])
            free = self.free_arm
            self.pos = [1102.0, float(self._rng.choice(REAL_REST_AFTER_HOMING_Y)
                                      if self.real_table else self._rng.choice((0, 1, 2)))]
            self.free_arm = False
            took = _homing_s(start, free)
            if kind == "fast_motion":
                took = 0.02
            if kind == "short_homing":
                # done in its usual time, the arm short of rest (session_sim.FAULT_KINDS)
                self.pos = short_homing_stop(start, self.pos, fault.value)
            if self.real_table:
                # the arm at rest, not driven, relaxes a little later (REAL_REST_RELAX; the same
                # estimate of the homing's time as before 4.3.51)
                est = (0.17 + abs(start[1]) * 0.0038 if 1090 <= start[0] <= 1115
                       and start[1] <= 250 else 2.0)
                self._relax_due = self.clock + est + REAL_RELAX_AFTER_S
            return 0, "", took
        return self._execute(line, cid, a, fault)

    # -- the instrument's lamp starts a waiting scan move
    def lamp(self, t_lamp: float, dual_pass: "str | None" = None) -> None:
        """*dual_pass* ("lamp" / "uv"): the trigger of a dual row's pass (the UV LED starts the
        move too, sooner after its trigger: the recordings' own timings)."""
        p = self.m2_pending
        if p is None or not p["c3"] or p["lamp"] or p.get("ignore") \
                or self.c_faults.get("lamp_ignored"):
            return
        p["lamp"] = True
        if dual_pass is None:
            extra = 0.42 + 0.08 * self.lamp_rng.random()
            p["motion_start"] = t_lamp + TABLE_MOTION_START_AFTER_LAMP_S
        else:
            lo, hi = DUAL_DONE_EXTRA[dual_pass]
            extra = lo + (hi - lo) * self.lamp_rng.random()
            p["motion_start"] = t_lamp + (TABLE_MOTION_START_AFTER_UV_S if dual_pass == "uv"
                                          else TABLE_MOTION_START_AFTER_LAMP_S)
        done_at = t_lamp + (p["T"] + p["A"]) / 1000.0 + extra
        self._busy_until = done_at
        self.scan_moves.append((tuple(self.pos), p["to"], p["v"]))
        self.pos = [float(p["to"][0]), float(p["to"][1])]
        # 4.3.57 (item 21): the arm ends a scan move "scan_end_off" units short along X (the
        # owner's row 2: 6 units at 168 mm/s); "scan_end_settle" = where it reads from the
        # second reading on (an arm still settling), relative to the target
        off = self.c_faults.get("scan_end_off")
        if off:
            self.pos[0] += float(off)
            settle = self.c_faults.get("scan_end_settle")
            self._scan_settle = None if settle is None else (
                float(p["to"][0]) + float(settle), float(p["to"][1]), 1)
        self.last_scan_end = (float(p["to"][0]), float(p["to"][1]))
        self._reply(done_at, ":$m20")

    def pending(self, until: float) -> bytes:
        out = super().pending(until)
        if self.m2_pending is not None and self.m2_pending.get("lamp") and self.clock >= \
                self._busy_until:
            self.m2_pending = None
        return out


class _Clock:
    def __init__(self, sim):
        self.sim = sim

    def now(self):
        return self.sim.clock

    def advance(self, dt):
        self.sim.clock += dt


def _through_aperture(a, b, L: float, s: float, ap: float) -> "list[float]":
    """What a round opening of *ap* mm sees at *s* mm along the row a -> b (L mm long): the
    sheet's spectrum averaged over 9 slices across the opening, each weighted by its chord
    (4.3.54, the row placement check's tests: the recorded readings are such averages)."""
    r = ap / 2.0
    acc, wsum = [0.0] * 36, 0.0
    for k in range(9):
        u = -r + (k + 0.5) * ap / 9
        w = math.sqrt(max(0.0, r * r - u * u))
        f = (s + u) / L if L else 0
        x, y = a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])
        sp_ = _spectrum_at(x, y)
        acc = [c + w * v for c, v in zip(acc, sp_)]
        wsum += w
    return [c / wsum for c in acc]


def _spectrum_at(x: float, y: float) -> "list[float]":
    """The simulated sheet: a different, smooth spectrum per 8.7 mm cell; the bare table where
    nothing is (0.80 everywhere) is used only by tests that say so."""
    cx, cy = round(x / 87.0), round(y / 87.0)
    r = random.Random(cx * 10007 + cy)
    base = [r.uniform(0.05, 0.9) for _ in range(4)]
    out = []
    for w in range(36):
        t = w / 35 * 3
        i = min(int(t), 2)
        f = t - i
        out.append(base[i] * (1 - f) + base[i + 1] * f)
    return out


class FakeSpotReader:
    """Answers like the helper reading patch by patch. Each reading takes 0.9 s of the
    simulator's clock and is of whatever stands under the sensor; a reading while the arm moves
    or a scan move waits is a violation."""

    calibrations = 0

    def __init__(self, sim: CSimTable, workdir, name, patches, log, calibrate, faults=None):
        self.sim, self.log = sim, log
        self.workdir = workdir
        os.makedirs(workdir, exist_ok=True)
        self.base = os.path.join(workdir, name)
        self.patches = list(patches)
        self.faults = dict(faults or {})
        self.calibrate_asked = calibrate
        self.readings = {}
        self.calibrated = False
        self.closed = False

    def open(self, place, timeout=45.0):
        from workflow.i1io.table.reader import ReaderFailed
        if self.faults.get("no_instrument"):
            raise ReaderFailed("the reader did not get ready (no instrument)")
        if self.calibrate_asked or self.faults.get("needs_cal"):
            if not place({"event": "cal_required", "cond": "man_ref_white"}):
                raise ReaderFailed("the calibration was not done")
            if self.faults.get("cal_fails"):
                raise ReaderFailed("the calibration ended with 'failed'")
            self.calibrated = True
            FakeSpotReader.calibrations += 1

    def read(self, loc, timeout=15.0):
        from workflow.i1io.table.reader import Reading, ReaderFailed
        if self.sim.moving or self.sim.m2_pending is not None:
            self.sim.violations.append(f"a spot reading of {loc} while the arm moves")
            raise SimViolation(f"a spot reading of {loc} while the arm moves")
        if self.faults.get("read_fails_at") == loc:
            raise ReaderFailed(f"no reading of {loc} within 15 s")
        self.sim.clock += 0.9
        x, y = self.sim.pos
        self.sim.read_spots.append((x, y))
        spec = _spectrum_at(x, y)
        if self.faults.get("empty"):
            spec = [0.0] * 36
        Y = 100 * sum(spec) / len(spec)
        # percent, as in ArgyllCMS's .ti3 (the real reader's spectra come from there)
        r = Reading(loc, (Y * 0.96, Y, Y * 0.82), spectrum=[100 * v for v in spec], t=0.9,
                    event={"event": "patch_read", "loc": loc, "sim": True})
        self.readings[loc] = r
        return r

    def finish(self, timeout=20.0):
        self.closed = True
        path = self.base + ".ti3"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("CTI3\n\nORIGINATOR \"simulated reader\"\n")
            fh.write("NUMBER_OF_FIELDS 2\nBEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC\n"
                     "END_DATA_FORMAT\n")
            fh.write(f"NUMBER_OF_SETS {len(self.readings)}\nBEGIN_DATA\n")
            for sid, loc in self.patches:
                if loc in self.readings:
                    fh.write(f'{sid} "{loc}"\n')
            fh.write("END_DATA\n")
        from pathlib import Path
        return Path(path)

    def close(self):
        self.closed = True


class FakeScanReader:
    """Answers like the helper in its table-scan mode, on the simulator's clock; the lamp
    starts the simulator's waiting scan move."""

    def __init__(self, sim: CSimTable, outdir, log, faults=None, chart=None, dual=False):
        self.sim, self.outdir, self.log = sim, str(outdir), log
        self.faults = dict(faults or {})
        #: the dual row (--i1io-table-dual): the pass armed, the last lamp pass delivered,
        #: a dual tile kept (faults["dual_kept"]: a strip white with its dual tile was made)
        self.dual = bool(dual)
        self.armed_pass = None
        self.lamp_done = False
        self.dual_calibration = None
        self.dual_kept = bool(self.faults.get("dual_kept"))
        if self.dual:
            sim.dual = True
        os.makedirs(self.outdir, exist_ok=True)
        self.last_lamp_off = sim.clock - 10.0
        self.lights_at = None
        self.fired_event = None
        self.fired_due = None
        self.fires = 0
        self.armed_n = None
        self.calibrated = False
        self.rng = random.Random(2)
        sim.instrument = self

    def opened(self, timeout=45.0):
        from workflow.i1io.table.reader import ReaderFailed
        if self.faults.get("no_instrument"):
            raise ReaderFailed("the reader did not open the i1Pro 2 for strip readings")
        return {"event": "tscan_instrument", "model": "i1Pro 2 (simulated)"}

    def calibrate(self, place, timeout=120.0):
        from workflow.i1io.table.reader import ReaderFailed
        if not place({"event": "cal_required", "cond": "man_ref_white"}):
            raise ReaderFailed("the strip calibration was not done")
        if self.faults.get("cal_fails"):
            raise ReaderFailed("the strip calibration failed")
        self.calibrated = True
        if self.dual:
            # the recorded dual calibration: 10 dark + 5 UV-LED readings of the tile, the volts
            self.sim.clock += 0.33
            ok = not self.faults.get("dual_cal_fails")
            self.dual_calibration = {"event": "tdual_calibration", "ok": ok,
                                     "why": "" if ok else "uv_tile_dark", "mode": "scan",
                                     "lamp_clocks": 139, "uv_clocks": 139,
                                     "volts": [660, 655], "kept": ok}
            self.dual_kept = ok

    def dual_state(self, timeout=5.0):
        if not self.dual:
            return {"event": "timeout"}
        if self.faults.get("no_uv_led"):
            return {"event": "tdual_state", "on": False, "tile": "none",
                    "why": "dual_no_uv_tables"}
        return {"event": "tdual_state", "on": True,
                "tile": "kept" if self.dual_kept else "none", "why": ""}

    def alive(self):
        return not self.faults.get("dead")

    def ready_now(self) -> bool:
        t = self.sim.clock
        if self.armed_pass == "uv":
            return (self.armed_n is not None and self.lamp_done
                    and t >= self.last_lamp_off + 1.07)
        return (self.armed_n is not None and self.lights_at is not None
                and t >= self.last_lamp_off + 1.07 and t >= self.lights_at + 0.68)

    def lights_off(self):
        self.lights_at = self.sim.clock
        return {"event": "tscan_lights_off", "err": 1 if self.faults.get("lights_err") else 0}

    def arm(self, n, wait_ms=3000, pass_=None):
        self.armed_pass = None
        if self.dual and pass_ not in ("lamp", "uv"):
            return {"event": "tscan_armed", "ready": False, "why": "no such pass"}
        if not self.dual and pass_ is not None:
            raise SimViolation("a pass armed without --i1io-table-dual")
        if self.faults.get("not_ready") or not (self.calibrated or self.faults.get("restored")):
            return {"event": "tscan_armed", "ready": False, "why": "not calibrated"}
        if self.dual and not self.dual_kept:
            return {"event": "tscan_armed", "ready": False, "why": "no dual calibration"}
        if self.dual and n > 1150:
            return {"event": "tscan_armed", "ready": False, "why": "reading count out of range"}
        if pass_ == "uv":
            if not self.lamp_done or self.faults.get("uv_not_ready"):
                return {"event": "tscan_armed", "ready": False,
                        "why": "the lamp pass of this row did not deliver"}
            need = self.last_lamp_off + 1.07
            t = self.sim.clock
            if need > t:
                self.sim.clock = need
            self.armed_n, self.armed_pass = n, "uv"
            return {"event": "tscan_armed", "ready": True, "waited_ms": int(max(0, need - t) * 1000)}
        if self.lights_at is None:
            return {"event": "tscan_armed", "ready": False, "why": "no lights-off"}
        need = max(self.last_lamp_off + 1.07, self.lights_at + 0.68)
        t = self.sim.clock
        if need > t:
            if need - t > wait_ms / 1000.0:
                return {"event": "tscan_armed", "ready": False, "why": "timing"}
            self.sim.clock = need
        self.armed_n = n
        self.armed_pass = pass_
        return {"event": "tscan_armed", "ready": True, "waited_ms": int(max(0, need - t) * 1000)}

    def fire(self, n, patches, name):
        """True when the trigger reached the reader (the real ScanReader's contract)."""
        if self.dual:
            return self._fire_dual(n, patches, name)
        self.fires += 1
        self.armed_n = None
        self.lights_at = None
        t = self.sim.clock
        if self.faults.get("fire_unsent"):
            # the reader had stopped before the trigger could be handed to it
            self.faults["dead"] = True
            return False
        if self.faults.get("dies_at_fire"):
            self.faults["dead"] = True
            return True
        t_lamp = t + 0.047
        lit = not self.faults.get("no_lamp")
        p = self.sim.m2_pending
        if lit:
            self.sim.lamp(t_lamp)
        t_end = t_lamp + 0.370 + n * READING_S
        self.last_lamp_off = t_end
        files = []
        if lit and p is not None and p.get("lamp"):
            files = self._stream(name, n, p)
        self.fired_event = {"event": "tscan_fired", "name": name,
                            "ok": lit and not self.faults.get("dark_fail"), "n": n,
                            "got": n if lit else 0, "lit_sent": 1 if lit else 0, "dark_sent": 1,
                            "ms_dark_trig": 1, "ms_lit_trig": 47, "files": files}
        self.fired_due = t_end + 0.006
        return True

    def _fire_dual(self, n, patches, name):
        """The dual row's armed pass (the helper fires exactly that): the lit trigger first
        (lamp, or the UV LED), its data, then the 5 dark readings (and the volts after UV)."""
        which = self.armed_pass
        self.fires += 1
        self.armed_n = None
        self.armed_pass = None
        self.lights_at = None
        t = self.sim.clock
        if which not in ("lamp", "uv"):
            self.fired_event = {"event": "tscan_fired", "name": name, "ok": False, "rc": -1,
                                "refused": "no pass was armed", "lit_sent": 0}
            self.fired_due = t
            return True
        if which == "uv":
            self.lamp_done = False
        if self.faults.get("fire_unsent"):
            self.faults["dead"] = True
            return False
        t_trig = t + 0.006
        lit = not (self.faults.get("no_lamp") or (which == "uv" and self.faults.get("no_uv")))
        p = self.sim.m2_pending
        if lit:
            self.sim.lamp(t_trig, dual_pass=which)
        first = UV_FIRST_READING_S if which == "uv" else 0.370
        t_end = t_trig + first + n * READING_S
        if which == "lamp":
            self.last_lamp_off = t_end
        files = []
        if lit and p is not None and p.get("lamp"):
            files = self._stream(name, n, p, which)
        ok = lit and not self.faults.get("dark_fail")
        if which == "lamp" and ok:
            self.lamp_done = True
        self.fired_event = {"event": "tscan_fired", "name": name, "ok": ok, "n": n,
                            "got": n if lit else 0, "lit_sent": 1 if lit else 0,
                            "dark_sent": 1, "ms_lit_trig": 6, "ms_dark_trig": int(
                                (t_end - t) * 1000) + 5, "files": files, "pass": which,
                            "volts": [661, 657] if which == "uv" else [-1, -1]}
        self.fired_due = t_end + 0.045
        return True

    def dual_compute(self, name, scale, timeout=10.0):
        """The helper's M1 / M2 of a cut row (the simulator's own invented glow: a brightened
        paper glows at 420-500 nm). Faults: uv_wrong_strip (the pairing check refuses)."""
        path = os.path.join(self.outdir, name + ".dual_in.txt")
        try:
            with open(path, encoding="ascii") as fh:
                rows = fh.read().split("\n")
            n = int(rows[0])
            vals = [[float(x) for x in r.split()] for r in rows[1:1 + n]]
        except (OSError, ValueError, IndexError):
            return {"event": "tscan_dual_computed", "ok": False, "why": "record", "n": 0}
        if self.faults.get("uv_wrong_strip"):
            return {"event": "tscan_dual_computed", "ok": False, "why": "uv_pass_wrong_strip",
                    "n": n, "pairing": ""}
        out = []
        for v in vals:
            L = v[:36]
            g = [0.02 * math.exp(-((380 + 10 * w - 450) / 30.0) ** 2) * float(scale) for w in
                 range(36)]
            m1 = [a + 0.6 * b for a, b in zip(L, g)]
            m2 = [a - b for a, b in zip(L, g)]
            out.append(" ".join(f"{x:.8f}" for x in m1 + m2))
        with open(os.path.join(self.outdir, name + ".dual_out.txt"), "w",
                  encoding="ascii") as fh:
            fh.write("\n".join(out) + "\n")
        self.sim.clock += 0.02
        return {"event": "tscan_dual_computed", "ok": True, "why": "", "n": n,
                "pairing": "checked", "usable": n}

    def _stream(self, name, n, p, which=None):
        """The reading stream of the simulated sheet along the move (aperture 4.5 mm)."""
        a, b = p["from"], p["to"]
        L = math.hypot(b[0] - a[0], b[1] - a[1]) / 10.0
        V, ta = float(p["v"]), p["A"] / 1000.0
        acc = V / ta

        def s_at(t):
            if t <= 0:
                return 0.0
            d_acc = 0.5 * acc * ta * ta
            if L < 2 * d_acc:
                tm = math.sqrt(L / acc)
                return 0.5 * acc * t * t if t < tm else min(L, L - 0.5 * acc * max(0, 2 * tm - t) ** 2)
            tt = (p["T"] + p["A"]) / 1000.0
            if t < ta:
                return 0.5 * acc * t * t
            if t < tt - ta:
                return d_acc + V * (t - ta)
            return L - 0.5 * acc * max(0.0, tt - t) ** 2
        rows = []
        first, start = ((UV_FIRST_READING_S, TABLE_MOTION_START_AFTER_UV_S) if which == "uv"
                        else (0.370, TABLE_MOTION_START_AFTER_LAMP_S))
        # 4.3.54 (the row placement check's tests): "sheet_offset_mm": the printed sheet lies that
        # far further along the row than the aims put it (the opening sees the sheet that much
        # behind where it stands)
        off = float(self.faults.get("sheet_offset_mm", 0.0) or 0.0)
        # ... and "aperture_mm": each reading sees the sheet through the i1Pro 2's round opening
        # (each slice along the row weighted by its chord), not as one point
        ap = float(self.faults.get("aperture_mm", 0.0) or 0.0)
        for i in range(n):
            t = first + (i + 0.5) * READING_S - start
            s = s_at(t) - off
            f = s / L if L else 0
            x, y = a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])
            spec = _spectrum_at(x, y) if not ap else _through_aperture(a, b, L, s, ap)
            if which == "uv":
                # the UV pass in lamp-white units: the LED light the patch reflects (strong at
                # 380-400 nm, none beyond 450) and a little glow; small numbers, as recorded
                spec = [v * max(0.0, 1.6 - 0.04 * w) * (0.25 if w < 7 else 0.02) +
                        0.004 * math.exp(-((380 + 10 * w - 450) / 30.0) ** 2)
                        for w, v in enumerate(spec)]
                rows.append([v + self.rng.gauss(0, 0.0002) for v in spec])
                continue
            rows.append([v + self.rng.gauss(0, 0.001) for v in spec])
        path = os.path.join(self.outdir, name + ".spec.csv")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("reading," + ",".join(str(380 + 10 * w) for w in range(36)) + "\n")
            for i, r in enumerate(rows):
                fh.write(f"{i}," + ",".join(f"{v:.6f}" for v in r) + "\n")
        with open(os.path.join(self.outdir, name + ".raw"), "wb") as fh:
            fh.write(b"\x00" * 16)
        return [name + ".spec.csv", name + ".raw"]

    def poll(self, name):
        if self.fired_event is not None and self.sim.clock >= self.fired_due:
            ev, self.fired_event = self.fired_event, None
            return ev
        return None

    def wait(self, names, timeout):
        if self.fired_event is not None and self.fired_due <= self.sim.clock + timeout:
            self.sim.clock = max(self.sim.clock, self.fired_due)
            return self.poll("tscan_fired")
        self.sim.clock += timeout
        return None

    def close(self):
        pass


class FakeReaders:
    """The instrument side of a simulated sitting: fake spot and strip readers on the
    simulator's clock. Like ArgyllCMS (ENABLE_NONVCAL: the calibration is kept in a file on the
    Mac between two runs of the reader), a calibration done by one reader is found by the next.
    *problem*: what the check before a reader reports (instrument not found and the like)."""

    def __init__(self, sim: CSimTable, log, spot_faults=None, scan_faults=None, problem=None):
        self.sim, self.log = sim, log
        self.spot_faults = dict(spot_faults or {})
        self.scan_faults = dict(scan_faults or {})
        self.problem = problem
        self.spot_calibrated = False
        self.strip_calibrated = False
        self.started: "list[tuple[str, str]]" = []

    def check(self):
        return self.problem

    def spot(self, folder, name, patches, calibrate):
        self.started.append(("spot", name))
        faults = dict(self.spot_faults)
        if not calibrate and not self.spot_calibrated:
            faults["needs_cal"] = True
        r = FakeSpotReader(self.sim, str(folder), name, patches, self.log, calibrate, faults)
        owner = self
        real_open = r.open

        def open_(place, timeout=45.0):
            real_open(place, timeout)
            if r.calibrated:
                owner.spot_calibrated = True
        r.open = open_
        return r

    def scan(self, folder, extra_args=()):
        self.started.append(("scan", str(folder)))
        faults = dict(self.scan_faults)
        if self.strip_calibrated:
            faults["restored"] = True
        dual = "--i1io-table-dual" in tuple(extra_args)
        if getattr(self, "strip_dual_kept", False):
            faults["dual_kept"] = True
        r = FakeScanReader(self.sim, str(folder), self.log, faults, dual=dual)
        owner = self
        real_cal = r.calibrate

        def calibrate(place, timeout=120.0):
            real_cal(place, timeout)
            owner.strip_calibrated = True
            owner.strip_dual_kept = bool(r.dual_kept) and dual
        r.calibrate = calibrate
        return r
