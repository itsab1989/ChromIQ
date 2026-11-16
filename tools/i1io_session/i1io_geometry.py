# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""Where the arm may be sent in part C (0.5.0): the shared guard for spot and scan stages.

Standard library only. Positions are table units of 0.1 mm. X falls from the left to the right of
a chart as the person sees it from the front of the table; Y grows towards the front. Home is
X 1102, Y 0.

THE MEASURING AREA. X-Rite gives the measuring area of the i1iO as 320 x 230 mm (ChromIQ's
`workflow/i1io/table_facts.py` REACH_MM; the figure ChromIQ's i1iO layout is built on: a sheet laid
across the table, at most 320 mm along X and 230 mm along Y). Where that rectangle lies in the
table's own units is not published. The derivation (SAFETY_BRIEF_0.5.md, section 3, with every
number's source):

* X: the arm was at X -1434 (the smallest X ever read, the free arm beside a bottom-right corner,
  R1) and at X 2832 (the alignment start, every session); the aimed corners of ten alignments span
  X -1315 to 1321. The 320 mm rectangle is put with its right edge (smallest X) ON the smallest X
  ever reached, -1434, so it never reaches further right than the arm has been: X -1434 to 1766.
  Every X in it lies between two positions the arm has physically been at.
* Y: the arm was read at Y 3109 (by hand, a bottom-left corner, R1) and at Y 0 (home); the aimed
  corners span Y 1543 to 3109. The 230 mm rectangle is put with its front edge ON the frontmost
  position ever reached, 3109: Y 809 to 3109.
* The table moves its two axes independently (an X carriage on an arm that travels along Y), so a
  point whose X and Y were each reached lies in the travel of the mechanism. This is a belief
  supported by the hand alignments (the four corners of X -1315..1321 by Y 1543..3109 were each
  reached within 4 mm); it is not proved for the strip X -1434..-1315 behind Y 1543, where no
  sheet of a recording lay.
* MARGIN: 5 mm kept inside on every side, so the guard is X -1384 to 1716, Y 859 to 3059.

What this leaves uncertain is stated in the brief: the true area may extend further to the right or
the front than these figures (then the guard is merely conservative), and nothing in the
recordings fixes its back and left edges (the guard then relies on the travel the recordings show).

THE SHEET. Inside that, every computed target must also lie inside the sheet as the person aimed
at it: the parallelogram of his three aimed marks (top-left, bottom-left, bottom-right and the
fourth corner TL + BR - BL), widened by RUN_OUT_MM along the rows (the run-in and run-out of a
strip read) and ACROSS_MM across them. The aims were reached by hand, the sight on each mark, so
the mechanism has been there in this very sitting.

WHERE THE ARM WAS DRIVEN. :data:`DRIVEN` is where motors moved it in a recording. A computed move
whose swept rectangle leaves it is a FIRST VISIT: the stage runner makes it a step of its own,
explained, confirmed, and checked on arrival (:func:`first_visit`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


class AreaRefused(Exception):
    """A position or path outside the guard. Nothing was sent."""


class AlignmentRefused(Exception):
    """The three aims do not describe the sheet as it must lie. Nothing was moved."""


@dataclass(frozen=True)
class Area:
    xmin: int
    xmax: int
    ymin: int
    ymax: int

    def contains(self, p) -> bool:
        return self.xmin <= p[0] <= self.xmax and self.ymin <= p[1] <= self.ymax

    def contains_path(self, a, b) -> bool:
        """The whole SWEPT RECTANGLE of a move from a to b (the table may move axis by axis)."""
        return (self.contains((min(a[0], b[0]), min(a[1], b[1])))
                and self.contains((max(a[0], b[0]), max(a[1], b[1]))))

    def text(self) -> str:
        return f"X {self.xmin} to {self.xmax}, Y {self.ymin} to {self.ymax}"


#: The manufacturer's 320 x 230 mm, placed as derived above (before the margin).
AREA_MM = (320.0, 230.0)
SMALLEST_X_REACHED = -1434          # R1, the free arm beside a bottom-right corner (p0)
FRONTMOST_Y_REACHED = 3109          # R1 401.6, the bottom-left aim (p1)
AREA_RAW = Area(SMALLEST_X_REACHED, SMALLEST_X_REACHED + int(AREA_MM[0] * 10),
                FRONTMOST_Y_REACHED - int(AREA_MM[1] * 10), FRONTMOST_Y_REACHED)
MARGIN = 50
MEASURING_AREA = Area(AREA_RAW.xmin + MARGIN, AREA_RAW.xmax - MARGIN,
                      AREA_RAW.ymin + MARGIN, AREA_RAW.ymax - MARGIN)

#: Where motors drove the arm in the recordings (R1, R2, S2), as boxes; a path is "visited" when
#: every point of its swept rectangle lies in one of them.
#:   chart   every m0 and m2 target after an alignment: X -1320..1316, Y 1537..2559
#:   first   the recorded first moves from the free arm: from (-1297, 2681), (-1303, 2689),
#:           (-1283, 2677), (-1210, 2668), (-1349, 2616) to the top-right of the chart
#:   way     home line X 1102 Y 0..1498, and Y 1498 X 1000..2507 (the approach), m1's place
DRIVEN = (Area(-1320, 1316, 1537, 2559), Area(-1349, -1181, 1645, 2689),
          Area(1000, 1104, 0, 1500), Area(1000, 2507, 1371, 1500), Area(2507, 2832, 1371, 1498))

#: The recorded speeds: m0 on a chart only at 300; m2 at these (mm/s).
RECORDED_M0_SPEEDS = (300,)
RECORDED_M2_SPEEDS = (40, 53, 54, 61, 87, 88, 110, 118, 137, 138)

#: Run-in / run-out allowed beyond the aimed marks along a row, and across the rows.
RUN_OUT_MM = 10.0
ACROSS_MM = 2.0


def check_target(p, what: str) -> None:
    if not MEASURING_AREA.contains(p):
        raise AreaRefused(f"{what}: table position X {p[0]}, Y {p[1]} lies outside the measuring "
                          f"area this program uses ({MEASURING_AREA.text()})")


def check_path(a, b, what: str) -> None:
    """A move from the READ position *a* to the target *b*: the target inside MEASURING_AREA
    (with its margin), the whole swept rectangle inside AREA_RAW (the start is where the arm
    physically is, so it may lie in the margin, e.g. a free arm left beside a corner)."""
    check_target(b, what + " (its end)")
    if not AREA_RAW.contains_path(a, b):
        raise AreaRefused(f"{what}: the rectangle the arm may sweep from {tuple(a)} to {tuple(b)} "
                          f"leaves the measuring area ({AREA_RAW.text()})")


def _visited(p) -> bool:
    return any(box.contains(p) for box in DRIVEN)


def first_visit(a, b, step: int = 10) -> bool:
    """True when any point of the swept rectangle of a -> b lies outside every DRIVEN box (checked
    on a grid of *step* units, corners included)."""
    x0, x1 = sorted((int(a[0]), int(b[0])))
    y0, y1 = sorted((int(a[1]), int(b[1])))
    xs = sorted(set(list(range(x0, x1 + 1, step)) + [x1]))
    ys = sorted(set(list(range(y0, y1 + 1, step)) + [y1]))
    return not all(_visited((x, y)) for x in xs for y in ys)


# ---- times ---------------------------------------------------------------------------------

ACCEL = 2000.0          # units/s^2 (every recorded m0: SEQUENCE.md section 10)


def predicted_move_time(a, b, speed: int = 300) -> float:
    """Per axis, the slower axis wins: a triangle at 2000 units/s^2 up to 10 x V units/s.
    Checked against the recordings: 87 units 0.417 (0.431), 1023 units 1.43 (1.456), 1498 units
    1.73 (1.727), 1250 units 1.58 (1.599)."""
    d = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
    vmax = 10.0 * speed
    ta = vmax / ACCEL
    if d <= vmax * ta:
        t = 2.0 * math.sqrt(d / ACCEL)
    else:
        t = d / vmax + ta
    return max(t, 0.015)


def move_window(a, b, speed: int = 300) -> "tuple[float, float]":
    """The time window a computed m0 must finish in (recorded moves fit the prediction within 3 %)."""
    t = predicted_move_time(a, b, speed)
    return (max(0.0, 0.75 * t - 0.05), max(0.7, 1.35 * t + 0.35))


# ---- the lines -------------------------------------------------------------------------------

def _cks(body: str) -> str:
    return f"{(-sum(body.encode('ascii'))) & 0xFF:02x}"


def _s16(h: str) -> int:
    v = int(h, 16)
    return v - 0x10000 if v & 0x8000 else v


def _line(cid: str, x: int, y: int, v: int) -> bytes:
    body = ";" + cid + f"{int(x) & 0xFFFF:04x}{int(y) & 0xFFFF:04x}{int(v):04x}"
    return (body + _cks(body) + "\r").encode("ascii")


def m0_line(x: int, y: int, speed: int = 300) -> bytes:
    """The ONLY builder of a computed m0: the recorded form apart from X and Y."""
    if speed not in RECORDED_M0_SPEEDS:
        raise AreaRefused(f"m0 at speed {speed}: only {RECORDED_M0_SPEEDS} is recorded on a chart")
    check_target((x, y), "a computed move")
    return _line("m0", x, y, speed)


def m2_line(x: int, y: int, speed: int) -> bytes:
    """The ONLY builder of a computed scan move (m2): the recorded form apart from X, Y and a
    recorded speed."""
    if speed not in RECORDED_M2_SPEEDS:
        raise AreaRefused(f"a scan move at speed {speed}: not a recorded speed")
    check_target((x, y), "a scan move's end")
    return _line("m2", x, y, speed)


def decode_xyv(line: bytes) -> "tuple[str, int, int, int]":
    s = bytes(line).decode("ascii").rstrip("\r")
    return s[1:3], _s16(s[3:7]), _s16(s[7:11]), int(s[11:15], 16)


# ---- the three aims -------------------------------------------------------------------------

#: The ten recorded alignments (p1 readings, aiming order TL, BL, BR; ALIGNMENT.md, align_fit.txt).
#: Two are degenerate (R1 716.8, R2 144.5) and no move followed them.
RECORDED_ALIGNMENTS = {
    "R1 200.3": ((1249, 1678), (1250, 3108), (-1315, 3073)),
    "R1 401.6": ((1286, 1705), (1268, 3109), (-1304, 3079)),
    "R1 716.8": ((1290, 1717), (1291, 1787), (1219, 1777)),
    "R2 144.5": ((1321, 1624), (1313, 2942), (1311, 2955)),
    "R2 427.5": ((1312, 1543), (1311, 2939), (-1266, 2934)),
    "S2 3.5":   ((1171, 1661), (1164, 3008), (-1199, 2993)),
    "S2 270.8": ((1188, 1658), (1169, 3005), (-1110, 2984)),
    "S2 383.3": ((1173, 1664), (1164, 3009), (-1191, 3004)),
    "S2 526.8": ((1176, 1674), (1164, 3013), (-1199, 2993)),
    "S2 684.0": ((1180, 1665), (1164, 3009), (-1198, 3001)),
}

LENGTH_TOL_UNITS = 20       # 2 mm: the recorded aims of one chart agree within 1 mm
ANGLE_TOL_DEG = 1.0         # recorded 89.9 to 90.5 degrees
ROTATION_TOL_DEG = 3.0      # recorded within 0.8 degrees; a turned sheet is 90 or 180 off


@dataclass(frozen=True)
class Alignment:
    aims_mm: tuple          # the sheet's three marks, sheet mm (x right, y down as it lies)
    readings: tuple         # the three p1 readings, table units
    M: tuple                # 2x2: table units per sheet mm
    checks: dict

    def to_table(self, u) -> "tuple[int, int]":
        dx, dy = u[0] - self.aims_mm[0][0], u[1] - self.aims_mm[0][1]
        P = self.readings[0]
        return (int(round(P[0] + self.M[0][0] * dx + self.M[0][1] * dy)),
                int(round(P[1] + self.M[1][0] * dx + self.M[1][1] * dy)))

    def on_sheet(self, u, run_out_mm: float = RUN_OUT_MM, across_mm: float = ACROSS_MM) -> bool:
        """Inside the parallelogram of the three aims (sheet x between TL and BR, y between TL and
        BL), widened by run_out_mm along x and across_mm along y."""
        xs = [a[0] for a in self.aims_mm]
        ys = [a[1] for a in self.aims_mm]
        return (min(xs) - run_out_mm <= u[0] <= max(xs) + run_out_mm
                and min(ys) - across_mm <= u[1] <= max(ys) + across_mm)

    def target(self, u, what: str, run_out_mm: float = RUN_OUT_MM) -> "tuple[int, int]":
        if not self.on_sheet(u, run_out_mm):
            raise AreaRefused(f"{what}: sheet position {u} lies outside the aimed marks")
        p = self.to_table(u)
        check_target(p, what)
        return p


def fit_alignment(aims_mm, readings) -> Alignment:
    """i1Profiler's own model: the affine map through the three aims (its recorded spot targets
    fit it within 1 unit). Every check from the challenge, before anything moves."""
    (a1, a2, a3), (P1, P2, P3) = [tuple(map(float, a)) for a in aims_mm], \
        [tuple(map(float, p)) for p in readings]
    ux, uy = a2[0] - a1[0], a2[1] - a1[1]
    vx, vy = a3[0] - a2[0], a3[1] - a2[1]
    det = ux * vy - uy * vx
    if abs(det) < 1e-9:
        raise AlignmentRefused("the sheet's three marks lie on one line (a bad side file)")
    px, py = P2[0] - P1[0], P2[1] - P1[1]
    qx, qy = P3[0] - P2[0], P3[1] - P2[1]
    if math.hypot(px, py) < 100 or math.hypot(qx, qy) < 100:
        raise AlignmentRefused("two of the aimed positions are less than 1 cm apart: the arm was "
                               "not moved from one mark to the next")
    inv = ((vy / det, -vx / det), (-uy / det, ux / det))
    M = ((px * inv[0][0] + qx * inv[1][0], px * inv[0][1] + qx * inv[1][1]),
         (py * inv[0][0] + qy * inv[1][0], py * inv[0][1] + qy * inv[1][1]))
    detM = M[0][0] * M[1][1] - M[0][1] * M[1][0]
    lens = []
    for (a, b), (A, B) in (((a1, a2), (P1, P2)), ((a2, a3), (P2, P3))):
        lens.append((10 * math.dist(a, b), math.dist(A, B)))
    e1 = (P1[0] - P2[0], P1[1] - P2[1])
    e2 = (P3[0] - P2[0], P3[1] - P2[1])
    cosang = (e1[0] * e2[0] + e1[1] * e2[1]) / (math.hypot(*e1) * math.hypot(*e2))
    ang = math.degrees(math.acos(max(-1.0, min(1.0, cosang))))
    rot = math.degrees(math.atan2(M[1][0], -M[0][0]))        # 0 = the recorded way round
    checks = {"det": round(detM, 4), "lengths_units": [(round(w), round(g, 1)) for w, g in lens],
              "angle_deg": round(ang, 2), "rotation_deg": round(rot, 2)}
    if detM >= 0:
        raise AlignmentRefused("the marks were aimed in another order than 1, 2, 3, or the sheet "
                               "is mirrored")
    if abs(rot) > ROTATION_TOL_DEG:
        raise AlignmentRefused(f"the sheet seems to be turned by about {abs(rot):.0f} degrees from "
                               f"the way it must lie (at most {ROTATION_TOL_DEG:.0f} is accepted)")
    for (want, got), name in zip(lens, ("marks 1 and 2", "marks 2 and 3")):
        if abs(want - got) > LENGTH_TOL_UNITS:
            raise AlignmentRefused(f"{name} are {got / 10:.1f} mm apart on the table but "
                                   f"{want / 10:.1f} mm on the sheet (at most "
                                   f"{LENGTH_TOL_UNITS / 10:.0f} mm difference is accepted): one "
                                   "aim was probably on another point")
    if abs(ang - 90) > ANGLE_TOL_DEG:
        raise AlignmentRefused(f"the corner at mark 2 measures {ang:.1f} degrees on the table "
                               f"(90 within {ANGLE_TOL_DEG:.0f} is accepted): one aim was "
                               "probably off")
    if not (P1[0] >= max(P2[0], P3[0]) - 30 and P1[1] <= min(P2[1], P3[1])):
        raise AlignmentRefused("mark 1 must be the one furthest to the left and furthest back")
    for n, p in enumerate((P1, P2, P3), 1):
        if not MEASURING_AREA.contains(p):
            raise AlignmentRefused(f"mark {n} was aimed at X {p[0]:.0f}, Y {p[1]:.0f}, outside the "
                                   f"measuring area this program uses ({MEASURING_AREA.text()})")
    return Alignment(tuple(tuple(a) for a in aims_mm),
                     tuple(tuple(int(v) for v in p) for p in readings), M, checks)
