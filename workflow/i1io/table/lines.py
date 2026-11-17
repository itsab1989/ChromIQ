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
   speed 300 and m2 at one of the ten recorded scan speeds, never beyond the front zone's cap
   (classify), and only right after a position was read. The gate checks the target and the
   whole swept rectangle from that reading against what THIS SITTING allows: the proven zone,
   plus the front zone up to the Y a creep step has confirmed (`Table.front_y`); during the creep
   (`Table.creep`) one m0 of at most 5 mm per axis, at most 5 mm beyond that Y (fix 2). They are
   built by i1io_geometry.m0_line / m2_line only.

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
               "the press, arm free (R1 263.517 ... S2 710.005); answer 8 data characters",
    "scan_c4": "at the start of all 44 recorded row scans, 1 ms after the i1Pro 2's lights-off "
               "(R1 9, R2 12, S2 23); answer one byte B7..BB, 0.171-0.218 s; and both passes of the "
               "volunteer's recording of 17 Nov 2026: BC (0.189 s, `:$c40BC56`) and BA (0.217 s, "
               "`:$c40BA58`), so B7..BC",
    "scan_d1": "before all 44 recorded row scans, always 016d (365); answer the echo 016D",
    "scan_a3": "0.016 s after all 44 recorded m2 lines, while the scan move waits; answer A, T, V",
    "scan_c3": "right after a3 in all 44 recorded row scans; answer no data",
}
#: data characters in each done answer (recorded)
C_DATA_LEN = {"aim": 8, "scan_c4": 2, "scan_d1": 4, "scan_a3": 20, "scan_c3": 0}

_ALLOWED_WIRE = {tbl.WIRE[k]: k for k in PART_C_WIRE_KEYS}
_FIXED = {v: k for k, v in C_FIXED.items()}
_COMPUTED_RE = re.compile(rb";(m[02])([0-9a-f]{4})([0-9a-f]{4})([0-9a-f]{4})([0-9a-f]{2})\r")


def classify(line: bytes) -> "tuple[str, bool, str]":
    """(command id, is it a movement, label) for an allowed line; ForbiddenLine otherwise.
    Computed lines are checked for form, checksum, recorded speed and the area."""
    line = bytes(line)
    if line in _ALLOWED_WIRE:
        key = _ALLOWED_WIRE[line]
        return line[1:3].decode("ascii"), line in tbl.MOTION_LINES, key
    if line in _FIXED:
        return line[1:3].decode("ascii"), False, _FIXED[line]
    m = _COMPUTED_RE.fullmatch(line)
    if not m or not tbl.checksum_ok(line.decode("ascii").rstrip("\r")):
        raise tbl.ForbiddenLine(f"not one of part C's lines: {line!r}")
    cid, x, y, v = geo.decode_xyv(line)
    if cid == "m0" and v not in geo.RECORDED_M0_SPEEDS:
        raise tbl.ForbiddenLine(f"m0 at speed {v}: not recorded on a chart")
    if cid == "m2" and v not in geo.RECORDED_M2_SPEEDS:
        raise tbl.ForbiddenLine(f"m2 at speed {v}: not a recorded scan speed")
    if not geo.CAP_AREA.contains((x, y)):
        raise tbl.ForbiddenLine(f"{cid} to ({x}, {y}): outside the measuring area (beyond the "
                                "front zone's cap or the sides)")
    return cid, True, ("computed m0" if cid == "m0" else "scan move")


def make_gate(table):
    """The gate Table._write calls in part C: classify, and for a computed move also the whole
    swept rectangle from the position read right before it (no fresh reading: refused)."""
    def gate(line: bytes):
        cid, motion, label = classify(line)
        if label in ("computed m0", "scan move"):
            start = table.position_now
            if start is None:
                raise tbl.ForbiddenLine(f"a computed {cid} without a fresh position reading")
            _c, x, y, _v = geo.decode_xyv(line)
            tgt, sweep = geo.areas(getattr(table, "front_y", None))
            if getattr(table, "creep", False) and cid == "m0":
                # one creep step: at most CREEP_STEP per axis from the fresh reading, at most
                # CREEP_STEP beyond what this sitting has confirmed, never beyond the cap
                lim = min(tgt.ymax + geo.CREEP_STEP, geo.FRONT_CAP_Y)
                tgt = geo.Area(tgt.xmin, tgt.xmax, tgt.ymin, lim)
                sweep = geo.Area(sweep.xmin, sweep.xmax, sweep.ymin, max(sweep.ymax, lim))
                if abs(x - start[0]) > geo.CREEP_STEP or abs(y - start[1]) > geo.CREEP_STEP:
                    raise tbl.ForbiddenLine(f"a creep step from {start} to ({x}, {y}): more than "
                                            f"{geo.CREEP_STEP} units")
            if not tgt.contains((x, y)):
                raise tbl.ForbiddenLine(f"{cid} to ({x}, {y}): beyond what this sitting allows "
                                        f"({tgt.text()})")
            if not sweep.contains_path(start, (x, y)):
                raise tbl.ForbiddenLine(f"{cid} from {start} to ({x}, {y}): the swept rectangle "
                                        "leaves the measuring area")
        return cid, motion, label
    return gate


def wire_gate(line: bytes) -> str:
    """The second check at the USB write itself (FtdiUsb.gate in part C)."""
    return classify(line)[0]
