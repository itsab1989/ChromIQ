# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""Part C's allow-list (0.5.0): every line part C may put on the wire, and its gate.

Three kinds, nothing else:

1. Lines of 0.4.0's own list (`i1io_session_table.WIRE`), byte for byte: the opening, the homing,
   the hand-alignment mode, the way to the alignment start and the 28 recorded spot moves of S2
   session 3 (PART_C_WIRE_KEYS). Part A's moves to (1102, 250) and (1000, 1500) are not used.
2. FIVE further fixed lines, each recorded byte for byte from i1Profiler on the volunteer's table
   (C_FIXED, with where in C_RECORDED_AT): the position under the sight at an aim (p1), and the
   four lines around every recorded row scan (c4, d1 with its only recorded value 365, a3, c3).
3. COMPUTED moves, in exactly the recorded form apart from the numbers: m0 at the recorded chart
   speed 300 and m2 at one of the eleven recorded scan speeds, never beyond the front zone's cap
   (classify), and only right after a position was read. The gate checks the target and the
   whole swept rectangle from that reading against what THIS SITTING allows: the proven zone,
   plus the front zone up to the Y a creep step has confirmed (`Table.front_y`); during the creep
   (`Table.creep`) one m0 of at most 5 mm per axis, at most 5 mm beyond that Y (fix 2). They are
   built by i1io_geometry.m0_line / m2_line only.

4. THE DUAL ROW (2026-11-18, the i1Pro 2 dual scan on the table): d1 210 (C_DUAL_FIXED) and the
   scan move at 132 (geometry.DUAL_M2_SPEEDS), each recorded byte for byte in i1Profiler's dual
   rows on the volunteer's table, and allowed ONLY while the job's dual row reads the pass they
   belong to (``Table.dual_phase``); with no dual phase the list above is unchanged.

Never: any memory or configuration write, i0, any other u8 than the two reads, any line form not
seen in a recording, any other speed, any target outside the area.
"""
from __future__ import annotations

import re

from . import geometry as geo
from . import session_table as tbl


def _frame(cid: str, args: str = "") -> bytes:
    body = ";" + cid + args
    return (body + tbl.checksum(body) + "\r").encode("ascii")


PART_C_WIRE_KEYS = ("identity", "k2", "memory_a", "memory_b", "a0", "status", "arm_mode",
                    "position", "home", "f0", "f3", "to_1498", "to_2507", "free", "m1") \
    + tbl.SPOT_KEYS

C_FIXED = {
    "aim":       _frame("p1"),            # position under the alignment sight
    "scan_c4":   _frame("c4"),            # before every recorded row scan
    "scan_d1":   _frame("d1", "016d"),    # 365, before every recorded row scan
    "scan_a3":   _frame("a3"),            # right after every recorded m2
    "scan_c3":   _frame("c3"),            # right after a3
}
C_RECORDED_AT = {
    "aim":     "after each of the 30 button presses of the ten recorded alignments, 3-5 ms after "
               "the press, arm free (R1 263.517 ... S2 710.005); and the three presses of the "
               "volunteer's recording of 17 Nov 2026 (i1Pro 2 0x84, one byte 0x06, then `;p124` "
               "after 5 / 3 / 4 ms), and the 12 of the two further recordings of that night (2-5 "
               "ms); 45 in all; answer 8 data characters",
    "scan_c4": "at the start of all 44 recorded row scans, 1 ms after the i1Pro 2's lights-off "
               "(R1 9, R2 12, S2 23); answer one byte B7..BB, 0.171-0.218 s; and both passes of the "
               "volunteer's recording of 17 Nov 2026: BC (0.189 s, `:$c40BC56`) and BA (0.217 s, "
               "`:$c40BA58`), so B7..BC; the further recording of that night: BB (0.170 s) and B8 "
               "(0.202 s), inside",
    "scan_d1": "before all 44 recorded row scans, always 016d (365); answer the echo 016D",
    "scan_a3": "0.016 s after all 44 recorded m2 lines, while the scan move waits; answer A, T, V",
    "scan_c3": "right after a3 in all 44 recorded row scans; answer no data",
}
#: data characters in each done answer (recorded)
C_DATA_LEN = {"aim": 8, "scan_c4": 2, "scan_d1": 4, "scan_a3": 20, "scan_c3": 0}

#: THE DUAL ROW (the i1Pro 2 dual scan on the table, 2026-11-18): ONE further fixed line, recorded
#: byte for byte only in i1Profiler's dual rows, and allowed ONLY while the job's dual row reads
#: its second (UV) pass (``Table.dual_phase == "uv"``): never in any other place.
C_DUAL_FIXED = {
    "scan_d1_uv": _frame("d1", "00d2"),   # 210, before the UV pass straight back
}
C_DUAL_RECORDED_AT = {
    "scan_d1_uv": "before the UV pass of all five accepted dual rows of the volunteer's recording "
                  "of 18 Nov 2026 (B 50.112 `;d100d23a` -> `:$d1000D207`, 62.255, 74.350; A 231.5, "
                  "243.7), after the zero-length m0 and c4, before p0 and the m2 straight back at "
                  "132; answer the echo 00D2. The lamp pass before it keeps d1 016d (365)",
}
C_DUAL_DATA_LEN = {"scan_d1_uv": 4}
#: the table's dual phase in which each line of the dual row may be sent
DUAL_PHASES = ("lamp", "uv")

_ALLOWED_WIRE = {tbl.WIRE[k]: k for k in PART_C_WIRE_KEYS}
_FIXED = {v: k for k, v in C_FIXED.items()}
_DUAL_FIXED = {v: k for k, v in C_DUAL_FIXED.items()}
_COMPUTED_RE = re.compile(rb";(m[02])([0-9a-f]{4})([0-9a-f]{4})([0-9a-f]{4})([0-9a-f]{2})\r")


def classify(line: bytes, dual_phase: "str | None" = None) -> "tuple[str, bool, str]":
    """(command id, is it a movement, label) for an allowed line; ForbiddenLine otherwise.
    Computed lines are checked for form, checksum, recorded speed and the area.

    *dual_phase* (the dual row, 2026-11-18; None everywhere else): "lamp" or "uv" while the
    job's dual row reads that pass. Only then is a scan move at the dual row's recorded speed
    (132) allowed, and then ONLY that speed; d1 210 only in the "uv" pass, and d1 365 never
    there. With *dual_phase* None this is the released allow-list, unchanged."""
    line = bytes(line)
    if dual_phase is not None and dual_phase not in DUAL_PHASES:
        raise tbl.ForbiddenLine(f"an unknown dual phase {dual_phase!r}")
    if line in _ALLOWED_WIRE:
        key = _ALLOWED_WIRE[line]
        return line[1:3].decode("ascii"), line in tbl.MOTION_LINES, key
    if line in _FIXED:
        if _FIXED[line] == "scan_d1" and dual_phase == "uv":
            raise tbl.ForbiddenLine("d1 365 before a dual row's UV pass (recorded: d1 210)")
        return line[1:3].decode("ascii"), False, _FIXED[line]
    if line in _DUAL_FIXED:
        if dual_phase != "uv":
            raise tbl.ForbiddenLine(f"{line!r} outside a dual row's UV pass")
        return line[1:3].decode("ascii"), False, _DUAL_FIXED[line]
    m = _COMPUTED_RE.fullmatch(line)
    if not m or not tbl.checksum_ok(line.decode("ascii").rstrip("\r")):
        raise tbl.ForbiddenLine(f"not one of part C's lines: {line!r}")
    cid, x, y, v = geo.decode_xyv(line)
    if cid == "m0" and v not in geo.RECORDED_M0_SPEEDS:
        raise tbl.ForbiddenLine(f"m0 at speed {v}: not recorded on a chart")
    if cid == "m2" and dual_phase is not None and v not in geo.DUAL_M2_SPEEDS:
        raise tbl.ForbiddenLine(f"m2 at speed {v} in a dual row (recorded: "
                                f"{geo.DUAL_M2_SPEEDS[0]} only)")
    if cid == "m2" and dual_phase is None and not geo.row_speed_ok(v):
        raise tbl.ForbiddenLine(f"m2 at speed {v}: not a recorded scan speed, nor inside the "
                                f"recorded frame {geo.ROW_SPEED_FRAME}")
    if not geo.CAP_AREA.contains((x, y)):
        raise tbl.ForbiddenLine(f"{cid} to ({x}, {y}): outside the measuring area (beyond the "
                                "front zone's cap or the sides)")
    return cid, True, ("computed m0" if cid == "m0" else "scan move")


def make_gate(table):
    """The gate Table._write calls in part C: classify, and for a computed move also the whole
    swept rectangle from the position read right before it (no fresh reading: refused)."""
    def gate(line: bytes):
        phase = getattr(table, "dual_phase", None)
        cid, motion, label = classify(line) if phase is None else classify(line, phase)
        # 4.3.54 (review S3): a speed inside the frame that was never recorded only in a sitting
        # whose person set "Row speed" to something other than 1.00 (the job sets
        # ``row_speed_frame``); otherwise only the recorded speeds, as up to 4.3.53
        if cid == "m2" and phase is None and not getattr(table, "row_speed_frame", False):
            _c2, _x2, _y2, v2 = geo.decode_xyv(line)
            if v2 not in geo.RECORDED_M2_SPEEDS:
                raise tbl.ForbiddenLine(f"m2 at speed {v2}: not a recorded scan speed, and "
                                        "this sitting reads at ChromIQ's own speeds")
        if label in ("computed m0", "scan move"):
            start = table.position_now
            if start is None:
                raise tbl.ForbiddenLine(f"a computed {cid} without a fresh position reading")
            _c, x, y, _v = geo.decode_xyv(line)
            # 4.3.49 (Basti's ruling, FOR THE SAFETY REVIEW): the front of what this sitting
            # allows is the area the person AIMED AT (the job sets ``aimed_cap_y`` from the
            # alignment, None without one: the proven measuring area only)
            cap_y = getattr(table, "aimed_cap_y", None)
            tgt, sweep = geo.areas(getattr(table, "front_y", None), cap_y)
            if getattr(table, "creep", False) and cid == "m0":
                # one creep step: at most CREEP_STEP per axis from the fresh reading, at most
                # CREEP_STEP beyond what this sitting has confirmed, never beyond the cap
                lim = min(tgt.ymax + geo.CREEP_STEP, geo.table_cap(cap_y))
                tgt = geo.Area(tgt.xmin, tgt.xmax, tgt.ymin, lim)
                sweep = geo.Area(sweep.xmin, sweep.xmax, sweep.ymin, max(sweep.ymax, lim))
                if abs(x - start[0]) > geo.CREEP_STEP or abs(y - start[1]) > geo.CREEP_STEP:
                    raise tbl.ForbiddenLine(f"a creep step from {start} to ({x}, {y}): more than "
                                            f"{geo.CREEP_STEP} units")
            if not tgt.contains((x, y)):
                raise tbl.ForbiddenLine(f"{cid} to ({x}, {y}): beyond what this sitting allows "
                                        f"({tgt.text()})")
            # 4.3.49 (Basti's ruling of 19 Nov 2026, FOR THE SAFETY REVIEW): the swept
            # rectangle is no longer compared with a box of where recordings happened to read
            # the arm. Its start is the fresh reading of where the arm physically stands, its
            # end passed the target check above, and the table moves each axis over one
            # interval, so every point of the rectangle is reachable
            # (geo.check_move_from_reading). The creep's per-step limit above stays, and no
            # computed move starts in the back strip at the resting place (the physical reason
            # is in geo.check_move_from_reading).
            del sweep
            if start[1] < geo.AREA_RAW.ymin:
                raise tbl.ForbiddenLine(f"{cid} from {start}: a computed move from the back strip "
                                        "at the resting place")

        return cid, motion, label
    return gate


def wire_gate(line: bytes) -> str:
    """The second check at the USB write itself (FtdiUsb.gate in part C)."""
    return classify(line)[0]


def make_wire_gate(table):
    """The second check at the USB write for a session that may read DUAL rows: the same
    classify, with the table's dual phase at the moment of the write. A session without the
    dual scan uses :func:`wire_gate` itself (the job sets exactly that object)."""
    def gate(line: bytes) -> str:
        phase = getattr(table, "dual_phase", None)
        return (classify(line) if phase is None else classify(line, phase))[0]
    return gate
