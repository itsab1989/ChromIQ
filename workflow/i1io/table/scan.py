# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""ONE ROW SCAN (a strip reading) with the i1iO 2 and its i1Pro 2, for part C (0.5.0).

Merged from the scan-stage study (branch study/i1io-scan, ed70c69f6, tools/i1io_scan/
i1io_scan_stage.py): the same sequence and the same rule, now written through the session
program's ONE writer (Table._write, part C's gate and caps) and its shared guard (i1io_geometry).

One row, in the order i1Profiler 3.8.6 did it on every one of the 44 recorded passes::

    table  p0                         where the arm is
    instr  lights off                 (the recorded 18 bytes)
    table  c4                         answer one byte, recorded B7..BC
    table  p0
    table  m0 row start @300          travel
    table  d1 365                     echo 016D
    table  p0                         arrival at the row start within 5 units
    instr  ARM: ready to fire at once -- if not ready, the scan move is NEVER sent
    table  m2 row end @V              accepted at once; the table now waits
    table  a3, c3
    instr  FIRE: dark 5 x 5.004 ms, then N x 5.004 ms with the lamp: the lamp starts the move
    table  done answer of m2, then p0 at the row end

THE RULE: from the moment the scan move is written there is ONE code path to the FIRE, with no
stop point, no question and no exception that skips it (a stop asked for meanwhile is honoured
after the move has ended). A scan move that never gets its lamp is the one state nothing sent can
end; the person is then told to SWITCH THE TABLE OFF, and a marker file says so too.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

from . import geometry as geo
from . import lines as cl
from . import session_table as tbl

TRAVEL_SPEED = 300
DEFAULT_SPEED = 54                      # recorded (R1, R2); 15-16 readings per 10 mm patch
#: c4's one-byte answer: B7..BB in the 44 passes of R1, R2 and S2; BC and BA in the volunteer's
#: recording of 17 Nov 2026 (REC 231.431 `:$c40BC56`, the row then scanned normally; 236.2
#: `:$c40BA58`). What the byte means is not known; anything outside stops the row cleanly.
C4_RANGE = (0xB7, 0xBC)
READING_S = 0.005004
FIRST_READING_AFTER_LAMP_S = 0.370
DONE_EXTRA_S = (0.42, 0.50)
DONE_EXTRA_ACCEPT_S = (0.25, 1.20)
#: motion start after the lamp trigger, for cutting by position. MEASURED (value replay of
#: 2026-11-16, ChromIQ-work 2026-11-16_i1io_app_prep/values; study/i1io-scan 9f01e8acd): every
#: patch of 20 recorded passes located in the reading stream by its own spot or i1Profiler
#: value, R1 R2 S2 at 40-138 mm/s: lamp + 0.3718 s, sd 0.0027 s (half a reading), min 0.363,
#: max 0.376. The move starts with the FIRST READING (0.370), not d1's 365 ms after it. The
#: 0.43 used before (0.5.0) was 12 readings late; the uniformity refinement did not rescue it
#: on the R1/R2 rows (dE00 mean 21 against the spots; 2.1 with 0.372 and no refinement, 0.2-0.3
#: on the patches that are uniform in the stream). Confirmed again on the volunteer's table
#: (17 Nov 2026, i1Profiler's two rows at 168 mm/s against its own saved file): the best motion
#: start is lamp + 0.372 s on both rows (0.09 dE00 mean; 0.43 s gives 25-36). Note: i1Profiler's
#: calibration on the table's tile makes no wavelength-LED reading (none in three recordings).
MOTION_START_AFTER_LAMP_S = 0.372
#: readings the cut may move the motion start by, by default: none. A refinement that picks
#: the most uniform windows was MEASURED to wander on real rows (R1 R2: lamp + 0.305..0.500
#: for +-25 readings, 0.352..0.392 for +-4) and to make the values worse.
CUT_REFINE_READINGS = 0
ARRIVAL_UNITS = 5
ACK_TIMEOUT_S = 0.5
PENDING_EXTRA_S = 10.0
HELPER_NMAX = 2000
PENDING_MARKER = "SCAN_MOVE_MAY_BE_PENDING.txt"


@dataclass
class Patch:
    sample_id: str
    loc: str
    xy: "tuple[float, float]"
    along_mm: float = 0.0
    half_mm: float = 4.0


@dataclass
class RowPlan:
    name: str
    start: "tuple[int, int]"
    end: "tuple[int, int]"
    speed: int
    patches: "list[Patch]" = field(default_factory=list)
    aperture_mm: float = 4.5
    dist: float = 0.0
    T: int = 0
    A: int = 0
    N: int = 0

    @property
    def m0(self) -> bytes:
        return geo.m0_line(self.start[0], self.start[1], TRAVEL_SPEED)

    @property
    def m2(self) -> bytes:
        return geo.m2_line(self.end[0], self.end[1], self.speed)

    @property
    def move_s(self) -> float:
        return (self.T + self.A) / 1000.0

    def as_dict(self) -> dict:
        return {"name": self.name, "start": self.start, "end": self.end, "speed": self.speed,
                "dist_units": round(self.dist, 1), "T_ms": self.T, "A_ms": self.A,
                "readings": self.N, "m0": self.m0.decode().rstrip("\r"),
                "m2": self.m2.decode().rstrip("\r"),
                "patches": [{"id": q.sample_id, "loc": q.loc, "xy": [round(v, 1) for v in q.xy],
                             "along_mm": round(q.along_mm, 2)} for q in self.patches]}


def reading_count(T: int, A: int) -> int:
    """i1Profiler's count on all 44 recorded passes: (T + A) / 5.004 ms, up to a multiple of 10."""
    return int(math.ceil((T + A) / (READING_S * 1000.0) / 10.0) * 10)


def plan_row(name, start, end, speed, patches=None, aperture_mm=4.5) -> RowPlan:
    start = (int(round(start[0])), int(round(start[1])))
    end = (int(round(end[0])), int(round(end[1])))
    p = RowPlan(name, start, end, int(speed), list(patches or []), aperture_mm)
    p.dist = math.hypot(end[0] - start[0], end[1] - start[1])
    p.T = int(p.dist * 100 / p.speed)
    p.A = 5 * p.speed
    p.N = reading_count(p.T, p.A)
    ux, uy = (end[0] - start[0]) / (p.dist or 1), (end[1] - start[1]) / (p.dist or 1)
    for q in p.patches:
        q.along_mm = ((q.xy[0] - start[0]) * ux + (q.xy[1] - start[1]) * uy) / 10.0
    return p


class PlanRefused(Exception):
    pass


def check_plan(p: RowPlan, at=None, front_y=None) -> None:
    if p.speed not in geo.RECORDED_M2_SPEEDS:
        raise PlanRefused(f"speed {p.speed} is not a recorded scan speed")
    try:
        geo.check_target(p.start, "the row start", front_y)
        geo.check_target(p.end, "the row end", front_y)
        geo.check_path(p.start, p.end, "the row", front_y)
        if at is not None:
            geo.check_path(at, p.start, "the way to the row start", front_y)
    except geo.AreaRefused as exc:
        raise PlanRefused(str(exc)) from None
    if p.dist < 100:
        raise PlanRefused("a row shorter than 10 mm")
    if not 10 <= p.N <= HELPER_NMAX:
        raise PlanRefused(f"{p.N} readings: outside what the reader takes (10..{HELPER_NMAX})")
    for q in p.patches:
        if not -1.0 <= q.along_mm <= p.dist / 10.0 + 1.0:
            raise PlanRefused(f"patch {q.loc} does not lie on the row")


#: S2 session 1 row 1, i1Profiler's own iO chart (28 patches), exactly as recorded (S2 114.662-
#: 120.649): m0 to (-1196, 1645) at 300, m2 to (1175, 1661) at 118.
RECORDED_ROW = {"start": (-1196, 1645), "end": (1175, 1661), "speed": 118,
                "m0_line": b";m0fb54066d012c01\r", "m2_line": b";m20497067d007684\r",
                "first_col_x": 1171, "last_col_x": -1199, "patches": 28, "patch_mm": 8.0}


def recorded_row_plan() -> RowPlan:
    r = RECORDED_ROW
    n = r["patches"]
    pts = []
    for k in range(n):
        x = r["last_col_x"] + (r["first_col_x"] - r["last_col_x"]) * k / (n - 1)
        y = r["start"][1] + (r["end"][1] - r["start"][1]) * k / (n - 1)
        col = n - k
        pts.append(Patch(str(col), f"A{col}", (x, y), half_mm=r["patch_mm"] / 2))
    p = plan_row("recorded_row1", r["start"], r["end"], r["speed"], pts)
    if p.m0 != r["m0_line"] or p.m2 != r["m2_line"]:
        raise PlanRefused("the recorded row's bytes are not reproduced (a bug)")
    return p


def sheet_table_mm(i1io: dict, page_mm) -> "tuple[float, float]":
    """chart.py to_table_mm: a page point (x, y) as the sheet lies on the table."""
    h = float(i1io["paper_mm"][1])
    return (h - float(page_mm[1]), float(page_mm[0]))


def aims_of(i1io: dict, page: int):
    pts = sorted(i1io["pages"][page]["aim_points"], key=lambda a: a["number"])
    if len(pts) != 3:
        raise PlanRefused(f"page {page + 1} of this sheet has {len(pts)} aim points, not three")
    return pts


def sheet_rows(i1io: dict, page: int, al: geo.Alignment, speed: int = DEFAULT_SPEED,
               front_y=None):
    """Every strip of one page as a RowPlan, serpentine, the first from the right end (as
    recorded: the arm comes from the third mark, bottom right)."""
    along = float(i1io["patch_mm"][1])
    plans = []
    for k, st in enumerate(i1io["pages"][page]["strips"]):
        r0, r1 = st["run_mm"]
        ua = sheet_table_mm(i1io, (st["x_mm"], r0))
        ub = sheet_table_mm(i1io, (st["x_mm"], r1))
        a = al.target(ua, f"row {k + 1}'s run end", front_y=front_y)
        b = al.target(ub, f"row {k + 1}'s run end", front_y=front_y)
        if (a[0] > b[0]) != (k % 2 == 1):
            a, b = b, a
        patches = []
        for q in st["patches"]:
            u = sheet_table_mm(i1io, q["centre_mm"])
            patches.append(Patch(str(q["sample_id"]), q["loc"],
                                 al.target(u, f"patch {q['loc']}", run_out_mm=0.5,
                                           front_y=front_y),
                                 half_mm=along / 2))
        plans.append(plan_row(f"p{page + 1}_row{k + 1}", a, b, speed, patches))
    return plans


# ---- one row --------------------------------------------------------------------------

@dataclass
class RowResult:
    kind: str                 # done / failed_clean / after_doubt / pending / stopped
    why: str
    plan: RowPlan
    fired: "dict | None" = None
    armed: "dict | None" = None
    t_m2: "float | None" = None
    t_fire_sent: "float | None" = None
    t_done: "float | None" = None
    a3: "tuple[int, int, int] | None" = None
    c4: "int | None" = None
    start_read: "tuple[int, int] | None" = None
    at_start: "tuple[int, int] | None" = None
    end_xy: "tuple[int, int] | None" = None
    notes: "list[str]" = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"kind": self.kind, "why": self.why, "plan": self.plan.as_dict(),
                "fired": self.fired, "armed": self.armed, "t_m2": self.t_m2,
                "t_fire_sent": self.t_fire_sent, "t_done": self.t_done, "a3": self.a3,
                "c4": self.c4, "start_read": self.start_read, "at_start": self.at_start,
                "end_xy": self.end_xy, "notes": self.notes}


class CleanFail(Exception):
    """Before the scan move: something failed, nothing is pending, the arm is where last read."""


def _near(p, q, d=ARRIVAL_UNITS) -> bool:
    return p is not None and abs(p[0] - q[0]) <= d and abs(p[1] - q[1]) <= d


def run_row(table: tbl.Table, inst, plan: RowPlan, log, outdir: str,
            confirm_move=None) -> RowResult:
    """Scan one row. Before the scan move every failure is clean (nothing pending, the arm last
    read where it stands); after it, the ONE path to the fire. *confirm_move(a, b)* is asked
    before the travel to the row start (the first-visit rule); False ends the row cleanly."""
    res = RowResult("failed_clean", "", plan)
    try:
        at = table.position()
        if table.arm_free:
            # the same two-reading stillness check as D2/D3 and part B's step B4: a hand still
            # on the free arm shows as a difference, and then no motor takes it
            again = table.position()
            if abs(at[0] - again[0]) > tbl.STILL_UNITS or abs(at[1] - again[1]) > tbl.STILL_UNITS:
                raise CleanFail(f"the free arm moved between two readings ({at} then {again}): "
                                "please take your hands off it")
            at = again
        res.start_read = at
        try:
            check_plan(plan, at, getattr(table, "front_y", None))
        except PlanRefused as exc:
            raise CleanFail(f"the plan was refused: {exc}") from None
        if confirm_move is not None and not confirm_move(at, plan.start):
            raise CleanFail("you did not confirm the first move into a new part of the table")
        if not inst.alive():
            raise CleanFail("the instrument reader is not running")
        lo = inst.lights_off()
        if lo.get("event") != "tscan_lights_off" or lo.get("err") != 0:
            raise CleanFail(f"the instrument's lights-off failed ({lo})")
        d = table.c_exchange(cl.C_FIXED["scan_c4"], cl.C_DATA_LEN["scan_c4"], timeout=1.0)
        res.c4 = int(d.data, 16)
        if not C4_RANGE[0] <= res.c4 <= C4_RANGE[1]:
            raise CleanFail(f"c4 answered {res.c4:02X}, never seen (recorded B7..BC)")
        at = table.position()
        try:
            table.c_exchange(plan.m0, 0, window=geo.move_window(at, plan.start),
                             timeout=geo.move_window(at, plan.start)[1] + 4.0,
                             late_is_doubt=False)
        except tbl.MoveOutside as exc:
            res.notes.append(str(exc))
            got = table.position()
            if not _near(got, plan.start):
                raise table._doubt(f"after a slow move the arm reads {got}, not {plan.start}")
            raise CleanFail(f"the move to the row start took {exc.took:.2f} s, outside "
                            f"{exc.lo:.2f}-{exc.hi:.2f} s, although the arm arrived") from None
        d = table.c_exchange(cl.C_FIXED["scan_d1"], cl.C_DATA_LEN["scan_d1"], timeout=1.0)
        if d.data.upper() != "016D":
            raise table._doubt(f"d1 answered {d.data}, not the recorded echo 016D")
        got = table.position()
        res.at_start = got
        if not _near(got, plan.start):
            raise table._doubt(f"the arm arrived at {got}, not at the row start {plan.start}")
        armed = inst.arm(plan.N, 3000)
        res.armed = armed
        if armed.get("event") != "tscan_armed" or armed.get("ready") is not True:
            raise CleanFail(f"the instrument is not ready to fire at once ({armed})")
    except CleanFail as exc:
        res.kind, res.why = "failed_clean", str(exc)
        log("SCAN", f"{plan.name}: {res.why}")
        return res

    # ======== FROM HERE: ONE PATH TO THE FIRE ==========================================
    refused = False
    never_written = False
    fire_sent = None                # False: the trigger could not even be handed to the reader
    before_m2 = None                # why the scan move was never written (a stop, a check)
    table.busy += 1                 # Ctrl-C now only asks for a stop after the move has ended
    try:
        table.defer_stop = True
        try:
            res.t_m2 = table.t.now()
            sent_before = table.lines_sent
            try:
                table.c_send(plan.m2)
            except BaseException as exc:
                if table.lines_sent == sent_before:      # refused or stopped before the wire:
                    never_written = True                 # nothing is waiting for a lamp
                    before_m2 = exc
                raise
            try:
                ack = table.c_read(res.t_m2 + ACK_TIMEOUT_S, tbl.ACK_MAX)
            except Exception as exc:              # noqa: BLE001 - a3, c3 and the fire follow
                ack = f"unreadable: {exc}"
            if ack is not None and ack.startswith(":#"):
                refused = True
                res.notes.append(f"scan move refused: {ack}")
            elif ack is None or not ack.startswith(":!m2"):
                res.notes.append(f"scan move: no or unexpected acceptance ({ack!r}); firing anyway")
            if not refused:
                try:
                    t = table.t.now()
                    table.c_send(cl.C_FIXED["scan_a3"])
                    table.c_read(t + ACK_TIMEOUT_S, tbl.ACK_MAX)
                    d = table.c_read(t + 1.0, 30) or ""
                    if len(d) == 27 and d.startswith(":$a30"):
                        res.a3 = (int(d[5:13], 16), int(d[13:21], 16), int(d[21:25], 16))
                        if res.a3 != (plan.A, plan.T, plan.speed):
                            res.notes.append(f"a3 {res.a3} differs from the plan "
                                             f"{(plan.A, plan.T, plan.speed)} (logged only)")
                    else:
                        res.notes.append(f"a3 answered {d!r}")
                    t = table.t.now()
                    table.c_send(cl.C_FIXED["scan_c3"])
                    table.c_read(t + ACK_TIMEOUT_S, tbl.ACK_MAX)
                    d = table.c_read(t + 1.0, 12) or ""
                    if not d.startswith(":$c30"):
                        res.notes.append(f"c3 answered {d!r}")
                except Exception as exc:              # noqa: BLE001 - logged; the fire follows
                    res.notes.append(f"a3/c3: {exc}")
        except Exception as exc:                      # noqa: BLE001 - the fire follows
            res.notes.append(f"scan move: {exc}")
        finally:
            if not refused and not never_written:
                res.t_fire_sent = table.t.now()
                fire_sent = inst.fire(plan.N, len(plan.patches), plan.name)
        # ==============================================================================

        if fire_sent is False:
            # the lamp trigger never reached the reader: nothing can start the waiting move,
            # so the person is told to switch the table off NOW, not after the wait
            res.kind = "pending"
            res.why = ("no done answer can come: the lamp trigger could not be sent to the "
                       "instrument (its reader had stopped)")
            _mark_pending(outdir)
            table.close_for_sending("a scan move may be pending")
            return res
        if never_written:
            if isinstance(before_m2, tbl.Stopped):
                raise before_m2
            res.kind = "failed_clean" if table.closed_reason is None else "after_doubt"
            res.why = "the scan move was refused by the program's own checks before it was sent"
            return res
        if refused:
            table.motion_unconfirmed = False
            res.kind, res.why = "failed_clean", res.notes[-1]
            return res

        deadline = res.t_fire_sent + plan.move_s + DONE_EXTRA_S[1] + PENDING_EXTRA_S
        done = None
        while table.t.now() < deadline and done is None:
            try:
                line = table.c_read(min(deadline, table.t.now() + 0.05), 12)
            except Exception as exc:                  # noqa: BLE001
                res.notes.append(f"reading the table: {exc}")
                break
            if line is not None:
                if line.startswith(":$m2"):
                    done = line
                else:
                    res.notes.append(f"while the scan move ran: {line!r}")
            if res.fired is None:
                res.fired = inst.poll("tscan_fired")
        if res.fired is None:
            res.fired = inst.wait(("tscan_fired",), 2.0)
        if done is None:
            res.kind = "pending"
            res.why = "no done answer to the scan move"
            if res.fired is None or res.fired.get("lit_sent") != 1:
                res.why += "; the instrument did not report its lamp trigger"
            _mark_pending(outdir)
            table.close_for_sending("a scan move may be pending")
            return res
        table.motion_unconfirmed = False
        res.t_done = table.t.now()
        table.timings.append(("m2/scan", res.t_done - res.t_m2))
        doubts = []
        # a3, c3 or the acceptance not answered as recorded: logged during the path (the fire
        # had to follow), and now, with the move over, a doubt: nothing more is sent
        odd = [n for n in res.notes if n.startswith(("a3 answered", "c3 answered", "a3/c3:",
                                                     "scan move: no or unexpected",
                                                     "while the scan move ran"))]
        doubts += odd
        if done[4:5] != "0" or not tbl.checksum_ok(done):
            doubts.append(f"its done answer was {done!r}")
        if res.fired and isinstance(res.fired.get("ms_lit_trig"), (int, float)) \
                and res.fired.get("ms_lit_trig", -1) >= 0:
            t_lamp = res.t_fire_sent + res.fired["ms_lit_trig"] / 1000.0
            extra = res.t_done - t_lamp - plan.move_s
            res.notes.append(f"done = lamp + T + A + {extra:.3f} s (recorded 0.42-0.50)")
            if not DONE_EXTRA_ACCEPT_S[0] <= extra <= DONE_EXTRA_ACCEPT_S[1]:
                doubts.append(f"it ended {extra:.2f} s after lamp + T + A, outside the "
                              "recorded range")
    finally:
        table.defer_stop = False
        table.busy -= 1
    try:
        res.end_xy = table.position()
        table.arm_free = False
        if not _near(res.end_xy, plan.end):
            doubts.append(f"the arm stands at {res.end_xy}, not at the row end {plan.end}")
    except tbl.Doubt as exc:
        doubts.append(str(exc))
    if doubts:
        res.kind, res.why = "after_doubt", "; ".join(doubts)
        table.close_for_sending(doubts[0])
    else:
        res.kind = "done"
        res.why = ""
        if not res.fired or not res.fired.get("ok"):
            res.kind, res.why = "failed_clean", ("the scan move ran and the arm is at the row "
                                                 "end, but the instrument did not deliver its "
                                                 "readings (see its .json)")
    return res


def _mark_pending(outdir: str) -> None:
    try:
        with open(os.path.join(outdir, PENDING_MARKER), "w", encoding="utf-8") as fh:
            fh.write(PENDING_TEXT + "\n")
    except OSError:
        pass


PENDING_TEXT = (
    "SWITCH THE TABLE OFF NOW with its power switch. A scan move may still be waiting for the "
    "instrument's lamp. Do not open i1Profiler while the table is on: its lamp could start that "
    "move. After switching off, wait ten seconds, switch on, then open i1Profiler once to bring "
    "the arm home.")


# ---- readings into patches --------------------------------------------------------------

def read_spec_csv(path: str):
    with open(path, encoding="utf-8") as fh:
        head = fh.readline().strip().split(",")
        wl = [float(x) for x in head[1:]]
        rows = [[float(x) for x in ln.strip().split(",")[1:]] for ln in fh if ln.strip()]
    return wl, rows


def time_at(plan: RowPlan, along_mm: float) -> float:
    V = float(plan.speed)
    ta = plan.A / 1000.0
    L = plan.dist / 10.0
    a = V / ta
    d_acc = 0.5 * a * ta * ta
    s = min(max(along_mm, 0.0), L)
    if L < 2 * d_acc:
        if s <= L / 2:
            return math.sqrt(2 * s / a)
        return 2 * math.sqrt(L / a) - math.sqrt(2 * (L - s) / a)
    if s <= d_acc:
        return math.sqrt(2 * s / a)
    if s <= L - d_acc:
        return ta + (s - d_acc) / V
    return plan.move_s - math.sqrt(2 * (L - s) / a)


def windows(plan: RowPlan, motion_start_s: float, nread: int, edge_mm: float = 0.5):
    out = []
    for q in plan.patches:
        half_clean = q.half_mm - plan.aperture_mm / 2 - edge_mm
        if half_clean <= 0:
            out.append((0, 0))
            continue
        t0 = motion_start_s + time_at(plan, q.along_mm - half_clean) - FIRST_READING_AFTER_LAMP_S
        t1 = motion_start_s + time_at(plan, q.along_mm + half_clean) - FIRST_READING_AFTER_LAMP_S
        i0 = int(math.ceil(t0 / READING_S))
        i1 = int(math.floor(t1 / READING_S))
        out.append((max(0, i0), min(nread, max(i0, i1))))
    return out


def _mean(rows):
    n = len(rows)
    return [sum(r[j] for r in rows) / n for j in range(len(rows[0]))]


def cut_by_position(plan: RowPlan, spec_rows, refine_readings: int = CUT_REFINE_READINGS):
    """Patches from the reading stream by POSITION: the move's own profile (V, A), the
    recorded first-reading delay and the measured motion start MOTION_START_AFTER_LAMP_S.
    refine_readings > 0 also tries shifts of up to that many readings and keeps the one
    that makes every patch window most uniform (off by default: measured to mislead).
    Returns (patch spectra, info); info["uniformity"] is, per patch, the largest
    difference of one reading in its window from the window's mean (any band), so a
    window that is not on one colour can be seen."""
    n = len(spec_rows)
    best = None
    for k in range(-refine_readings, refine_readings + 1):
        ms = MOTION_START_AFTER_LAMP_S + k * READING_S
        w = windows(plan, ms, n)
        if any(i1 - i0 < 1 for i0, i1 in w):
            continue
        cost, cnt = 0.0, 0
        for i0, i1 in w:
            m = _mean(spec_rows[i0:i1])
            for r in spec_rows[i0:i1]:
                cost += sum((a - b) ** 2 for a, b in zip(r, m))
                cnt += 1
        cost /= max(cnt, 1)
        if best is None or cost < best[0]:
            best = (cost, ms, w)
    if best is None:
        raise ValueError("no motion start puts every patch inside the reading stream")
    cost, ms, w = best
    vals = [_mean(spec_rows[i0:i1]) for i0, i1 in w]
    uni = [max((abs(a - b) for r in spec_rows[i0:i1] for a, b in zip(r, v)), default=0.0)
           for (i0, i1), v in zip(w, vals)]
    info = {"motion_start_after_lamp_s": round(ms, 4), "windows": w,
            "readings_per_patch": [i1 - i0 for i0, i1 in w], "residual": cost,
            "uniformity": [round(u, 5) for u in uni]}
    return vals, info


def write_ti3(path: str, rows, wl, title: str, cut_by: str) -> None:
    """A .ti3-style CGATS file: SAMPLE_ID, SAMPLE_LOC and the spectra in percent. rows:
    [(sample_id, loc, spectrum 0..1)]."""
    fields = ["SAMPLE_ID", "SAMPLE_LOC"] + [f"SPEC_{int(w)}" for w in wl]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("CTI3\n\n")
        fh.write(f'DESCRIPTOR "{title}"\n')
        fh.write(f'ORIGINATOR "chromiq-i1io-session {tbl.TOOL_VERSION}"\n')
        fh.write('KEYWORD "DEVICE_CLASS"\nDEVICE_CLASS "OUTPUT"\n')
        fh.write('KEYWORD "SPECTRAL_BANDS"\n' f'SPECTRAL_BANDS "{len(wl)}"\n')
        if wl:
            fh.write('KEYWORD "SPECTRAL_START_NM"\n' f'SPECTRAL_START_NM "{wl[0]:.6f}"\n')
            fh.write('KEYWORD "SPECTRAL_END_NM"\n' f'SPECTRAL_END_NM "{wl[-1]:.6f}"\n')
        fh.write('KEYWORD "SPECTRAL_NORM"\nSPECTRAL_NORM "100.000000"\n')
        fh.write('KEYWORD "CUT_BY"\n' f'CUT_BY "{cut_by}"\n\n')
        fh.write(f"NUMBER_OF_FIELDS {len(fields)}\nBEGIN_DATA_FORMAT\n{' '.join(fields)}\n"
                 "END_DATA_FORMAT\n\n")
        fh.write(f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n")
        for sid, loc, v in rows:
            fh.write(f'{sid} "{loc}" ' + " ".join(f"{100 * x:.5f}" for x in v) + "\n")
        fh.write("END_DATA\n")


def save_row(outdir: str, res: RowResult) -> "list[str]":
    """Plan, result and (when the stream is there) the readings cut by position."""
    files = []
    p = os.path.join(outdir, res.plan.name + ".plan_and_result.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(res.as_dict(), fh, indent=1, default=str)
    files.append(os.path.basename(p))
    spec = os.path.join(outdir, res.plan.name + ".spec.csv")
    if res.kind in ("done", "failed_clean") and os.path.exists(spec) and res.plan.patches:
        try:
            wl, rows = read_spec_csv(spec)
            vals, info = cut_by_position(res.plan, rows)
            write_ti3(os.path.join(outdir, res.plan.name + ".cut.ti3"),
                      [(q.sample_id, q.loc, v) for q, v in zip(res.plan.patches, vals)],
                      wl, "i1iO strip reading, first try", "position (first try)")
            with open(os.path.join(outdir, res.plan.name + ".cut.json"), "w",
                      encoding="utf-8") as fh:
                json.dump(info, fh, default=str)
            files += [res.plan.name + ".cut.ti3", res.plan.name + ".cut.json"]
            res.notes.append(f"cut by position: {info['readings_per_patch']} readings per "
                             f"patch, motion start {info['motion_start_after_lamp_s']} s")
        except Exception as exc:                       # noqa: BLE001 - a first try
            res.notes.append(f"the stream could not be cut by position: {exc}")
    return files
