# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""Where the arm may be sent in part C (0.5.0): the shared guard for spot and scan stages.

Standard library only. Positions are table units of 0.1 mm. X falls from the left to the right of
a chart as the person sees it from the front of the table; Y grows towards the front. Home is
X 1102, Y 0.

THE MEASURING AREA. X-Rite gives the measuring area of the i1iO as 320 x 230 mm (ChromIQ's
`workflow/i1io/table_facts.py` REACH_MM: the i1iO 3 product page and a review of the first i1iO;
NOT published for the i1iO 2, so for this table the size is our assumption). Where that rectangle
lies in the table's own units is not published either: WHERE IT LIES ON HIS TABLE IS OUR ESTIMATE,
taken from where the measuring opening has actually been in his recordings.

TWO FRAMES, ONE OF THEM FOR PLACES. The table answers two position questions:

* p0 reads where the MEASURING OPENING (the sensor) is. Every m0/m2 target is a sensor position
  too: after a move, p0 reads the target (every arrival in every recording, within 5 units).
* p1 (sent at each aim) reads the point under the alignment SIGHT, in the same units as a move
  target: i1Profiler drives its spot targets to the affine map of its three p1 readings within
  1 unit (S2 383.3 and 684.0, 56 targets), so a p1 value IS the target that puts the opening on
  the aimed mark. The arm itself (the opening) stands elsewhere at that moment: p0 read right after
  the third aim is (-83..-119, -306..-323) from it (eight sessions; the person may also have moved
  the arm a little after the press). The sight sits about 31 mm in front of the opening.
  Confirmed on 17 Nov 2026 on the volunteer's table for both of i1Profiler's paths (D-5,
  settled for i1Profiler's own path): its scans run straight along the line through the p1
  readings, starting and ending 0.4 mm beyond the end patches' centres, and its spot targets are
  the grid through the three p1 readings within 1 unit; the values computed from its raw readings
  at those places agree with its own saved files to 0.09 dE00 on average (scan) and 0.07 (spot)
  with the table's stored tile values. No offset between a p1 reading and a target exists
  anywhere in this package. (4.3.50: a page driven by ChromIQ HAS run on a real table, 19 Nov
  2026: 528 patches read patch by patch, every arrival within 4 units, no sign of a reading off
  its patch; the check move to mark 3 and its question, the safeguard until then, are gone.)

So a p1 reading says where a mark lies; it is NOT a place the opening has been. Turning aims into
targets needs no conversion (i1Profiler's own model, checked against its recorded moves:
:func:`fit_alignment`); deciding where the opening may go uses p0 readings and motor targets only.

The derivation (SAFETY_BRIEF_0.5.md, section 4, with every number's source):

* X: the opening was read at X -1434 (p0, the free arm beside a bottom-right corner, R1 272.108,
  the smallest X ever read) and was driven to X 2507 (m0, done, every approach of R1, R2, S2; and
  m1, which ends at (2507, 1429): read twice on the volunteer's table on 17 Nov 2026); p0 read X
  up to 1318 (R2). The 320 mm rectangle is put with its right edge (smallest X)
  ON the smallest X ever read, -1434, so it never reaches further right than the opening has been:
  X -1434 to 1766. Every X in it lies between two places the opening has been.
* Y: the opening was read at Y 2773 (p0 twice, R1 431.410 and 431.635: the free arm after the
  R1 401.6 aims, from where the motors then took it to the chart), the frontmost p0 in every
  recording and log; and at Y 0 (home). Under motor it went to Y 2559 at most (m2, S2; read 2560
  after it). The 230 mm rectangle is put with its front edge ON the frontmost position the opening
  was ever READ at, 2773: Y 473 to 2773. (Until the safety review of 7382e56f2 the front edge was
  the p1 reading 3109, a SIGHT position: the opening was then about 31 mm further back, so that
  area let computed moves go about 3 cm further to the front than the opening had ever been.)
* The table moves its two axes independently (an X carriage on an arm that travels along Y), so a
  point whose X and Y were each reached lies in the travel of the mechanism. This is a belief: the
  opening was READ at the front right (-1434, 2755) and (-1413, 2773), at the back left only on
  the chart rows and the approach (X up to 1318 at Y 1543..1790; X 2507 at Y 1498), and never at
  the front left (the sight was there, at the bottom-left aims, with the opening about 31 mm
  behind it, which is LIKELY but not read).
* MARGIN: 5 mm kept inside on every side, so the guard is X -1384 to 1716, Y 523 to 2723.

What this leaves uncertain is stated in the brief: the true area may extend further to the right or
the front than these figures (then the guard is merely conservative), and nothing in the
recordings fixes its back and left edges (the guard then relies on the travel the recordings show).
A sheet must therefore lie a few centimetres further back than in his i1Profiler sessions (their
bottom marks were aimed at sight Y 2934 to 3109); D1 says by how much before anything moves.

THE FRONT ZONE (fix 2, the owner's ruling after fix 1 had refused all ten recorded sheet
positions). In front of that PROVEN area lies a FRONT ZONE up to an absolute cap, FRONT_CAP_Y =
3109: the frontmost mark any recorded alignment put (p1 Y 3109, R1 412.443, mark 2 of R1 401.6),
with nothing added (fix 3, the safety review of fix 2). A mark is a corner patch of a chart that i1Profiler then measures, so in normal use
i1Profiler sends the measuring opening to the marks' positions; that this table reaches them is
very likely (the tester has measured full charts laid like this in i1Profiler), but no reading in
our recordings shows the opening there. So:

* nothing is ever a target beyond FRONT_CAP_Y (CAP_AREA; classify and the builders check it on
  every computed line), and no swept rectangle reaches beyond FRONT_SWEEP_CAP_Y = 3114 (CAP_RAW:
  a move may start where the arm reads after a clean arrival at the cap, within 5 units);
* inside the front zone, a target is allowed only up to the Y that this sitting has CONFIRMED
  (`Table.front_y`): the furthest Y a creep step reached with a clean arrival (:func:`areas`);
* the creep itself (stage DZ) drives forward in m0 steps of at most CREEP_STEP (5 mm) along Y,
  each one at most CREEP_STEP beyond what is confirmed, from a fresh reading (the gate checks
  this whole rule on the bytes it is given).

THE SHEET. Until 4.3.52 every computed target also had to lie inside the parallelogram of the three
aimed marks, widened by RUN_OUT_MM along the rows and ACROSS_MM across them. 4.3.53 (the owner,
2026-11-20: the aimed points are not the edge, "a little wider than where he aimed is safe as
well ... for both patch by patch and rows"): that is no longer a refusal. The targets are the
side file's own patch centres and row run ends through the alignment; the target area (sides:
the backstop below; front: the aimed area or the plan's frontmost target, felt for with the
creep) is the only bound, the same for both ways of reading.

THE SIDES (4.3.53). The X sides of MEASURING_AREA / AREA_RAW below were the recorded extent and
kept the owner's sheet out of strip rows (its run-out needs X -1443). They are replaced by an
absolute backstop (TARGET_X_RIGHT / TARGET_X_LEFT, not an end of travel) and by KNOWN GROUND
(:func:`known_x`): the vendor's own motor targets and what this table's opening has been read at.

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


#: The manufacturer's 320 x 230 mm (published for the i1iO and i1iO 3; our assumption for the
#: i1iO 2), placed as derived above (before the margin). Both edges are SENSOR positions (p0).
AREA_MM = (320.0, 230.0)
SMALLEST_X_REACHED = -1434          # p0, R1 272.108: the free arm beside a bottom-right corner
FRONTMOST_Y_REACHED = 2773          # p0, R1 431.410 / 431.635: the free arm after the R1 401.6 aims
#: Where the opening stood, relative to the p1 reading of the third aim, when p0 was read next
#: (R1 200.3, 401.6; R2 427.5; S2 3.5, 270.8, 383.3, 526.8, 684.0). Documentation and the
#: simulator only: no target is ever computed with it (a p1 value is already the target).
SIGHT_TO_SENSOR_SEEN = ((-119, -318), (-109, -306), (-83, -318), (-84, -316), (-100, -316),
                        (-106, -323), (-98, -316), (-105, -312))
AREA_RAW = Area(SMALLEST_X_REACHED, SMALLEST_X_REACHED + int(AREA_MM[0] * 10),
                FRONTMOST_Y_REACHED - int(AREA_MM[1] * 10), FRONTMOST_Y_REACHED)
MARGIN = 50
MEASURING_AREA = Area(AREA_RAW.xmin + MARGIN, AREA_RAW.xmax - MARGIN,
                      AREA_RAW.ymin + MARGIN, AREA_RAW.ymax - MARGIN)
#: The PROVEN zone is AREA_RAW / MEASURING_AREA above (the names kept). 4.3.53: their X sides
#: (-1384 / -1434 and 1716 / 1766) no longer bound a target: they came from where recordings
#: happened to read the opening, which the owner's rulings of 19 and 20 Nov 2026 say is not a
#: fence. MEASURING_AREA stays the PROVEN zone for the FRONT (its Y) and the back strip.
PROVEN_RAW, PROVEN = AREA_RAW, MEASURING_AREA

#: 4.3.53 (the owner, 2026-11-20: "there is no physical reason he should not be able to do it",
#: and: "for patch by patch you allowed this position because we considered the position where
#: he aimed the device as safe. so why not rows? ... for both patch by patch and rows"). THE SIDES
#: OF THE TARGET AREA, the same for both ways of reading:
#:
#: * VENDOR_ROW_START_X: the furthest right X i1Profiler ITSELF drove the opening to under motor
#:   on a real i1iO 2: the starts of its own scan rows on the owner's table, -1432 to -1439
#:   (18 Nov 2026, decode_full_124449 / _125226, rows at lines 90, 170, 250). Known ground for
#:   ANY table of this model: the vendor's software sends it there.
#: * VENDOR_APPROACH_X: the left end of every recorded way out (m0 to (2507, 1498) at 300, done,
#:   every session; m1 then lands at (2507, 1429)). Known ground on the left for any table.
#: * Beyond those, what THIS table's opening has been read at (free or under motor: the reach
#:   record's right_end_x / left_x, learned and stored per table) is known ground too: the arm
#:   stood there, so the mechanism reaches it (the X carriage on the Y arm: every X reached at
#:   one Y is reached at every Y of the travel, the belief AREA_RAW's derivation states).
#: * TARGET_X_RIGHT / TARGET_X_LEFT: the right one was -1800 in the 4.3.53 rows branch (the
#:   furthest-left mark ever aimed minus 320 mm); since the 4.3.53 fix round it is only the
#:   protocol's number range (COORD_MIN, below). Left: VENDOR_APPROACH_X (physical). Both are
#:   checked by the line builders and the USB gate on every computed line.
#: Ground between the known ground and the backstop is NOT refused: a strip row that reaches
#: into it is driven to first by two ordinary arrival-checked moves (its row start and end, the
#: careful mechanism the front-zone rows already used), ONCE per table: the arrivals are learned
#: and stored, and later rows and sittings run at full speed (job.TableJob._row_ends_known).
#:
#: 4.3.53 FIX ROUND (rows review SHOULD-4, inventory A1 / A3 / A9; the owner: "a place the user
#: reached with the free arm by hand is a place the arm can be"): the right backstop of -1800
#: (and the front one of 365 mm, below) refused real aims and rows on a table whose travel
#: reaches that far, for a reason the owner rejected ("no recording shows the arm that far
#: out"). Both are GONE AS REFUSALS. What stays is only a guard against PLAINLY CORRUPTED
#: NUMBERS: a value no table of this kind can report or be sent at all. The table's X and Y
#: travel in a signed 16-bit field of 0.1 mm units (four hex digits, two's complement:
#: :func:`_s16`, :func:`_line`), so COORD_MIN / COORD_MAX are the protocol's own number range,
#: not anything a recording happened to show. A computed target outside it cannot even be
#: written into a line. The left side (2507, where the table's own m1 stops the arm) and the
#: back strip stay: those have their physical reasons.
COORD_MIN = -0x8000
COORD_MAX = 0x7FFF
VENDOR_ROW_START_X = -1439
VENDOR_APPROACH_X = 2507
TARGET_X_RIGHT = COORD_MIN
TARGET_X_LEFT = VENDOR_APPROACH_X

#: the arrival tolerance (units) every move is checked with
ARRIVAL_SLACK = 5
#: fix 2/3: the FRONT ZONE's absolute cap for TARGETS: the frontmost aimed mark of any recorded
#: alignment (p1, R1 412.443), with no margin added (the safety review of fix 2: i1Profiler
#: sends the opening to an aim with no offset, and no recorded alignment or i1Profiler target
#: goes beyond it). Never a target beyond it.
FRONTMOST_AIM_Y = 3109
#: 4.3.49 (Basti's ruling of 19 Nov 2026, FOR THE SAFETY REVIEW): the front of the target area
#: is no longer the frontmost RECORDED aim (FRONTMOST_AIM_Y). It is what the person AIMED AT on
#: this sheet (Alignment.aimed_front_y, the aimed area with the plan's run-out, passed to every
#: check below as *cap_y*), on the evidence that i1Profiler drives the opening to the very points
#: the person aimed the sight at (17 Nov 2026, three sessions, all three marks, within 1-5 units).
#: Without an alignment, the proven MEASURING_AREA only (DEFAULT_TARGET_FRONT_Y).
#: FRONT_CAP_Y was then an absolute backstop of 365 mm from home; since the 4.3.53 fix round it
#: is only the protocol's number range (below); the line builders and the USB gate check it.
#: 4.3.53 fix round (SHOULD-4 / A3): no longer 365 mm. Only the protocol's own number range
#: (COORD_MAX), with room for the swept rectangle's arrival tolerance inside it. The real care
#: at the front is the creep (5 mm steps, once per table: FIRST-TIME CARE), not a cap.
REACH_CEILING_Y = COORD_MAX
FRONT_CAP_Y = COORD_MAX - 2 * MARGIN
DEFAULT_TARGET_FRONT_Y = MEASURING_AREA.ymax
#: A swept rectangle may START where the arm reads after a clean arrival at the cap, within the
#: arrival tolerance; never beyond this.
FRONT_SWEEP_CAP_Y = FRONT_CAP_Y + ARRIVAL_SLACK
#: 4.3.53: the back of the target area is the edge of the back strip (AREA_RAW.ymin, the one
#: physical exception kept: the head parks there beside the white tile's holder, and no computed
#: move starts in it) plus 1 mm, not the 5 mm margin of 4.3.52. The 1 mm is a STATE reason, not
#: a fence: an arrival the job accepts may lie up to 1 mm off its target (ARRIVAL_BESIDE_UNITS
#: in the job), and the arm must never come to stand inside the back strip, from where the next
#: computed move would be refused.
TARGET_Y_BACK = AREA_RAW.ymin + 2 * ARRIVAL_SLACK
CAP_AREA = Area(TARGET_X_RIGHT, TARGET_X_LEFT, TARGET_Y_BACK, FRONT_CAP_Y)
CAP_RAW = Area(TARGET_X_RIGHT, TARGET_X_LEFT, AREA_RAW.ymin, FRONT_SWEEP_CAP_Y)
#: One creep step: at most 5 mm, and at most 5 mm beyond what the sitting has confirmed.
CREEP_STEP = 50


def table_cap(cap_y=None) -> int:
    """The front of the target area for a sitting whose aimed area reaches *cap_y* (None: no
    alignment): never beyond FRONT_CAP_Y, never behind the proven measuring area."""
    if cap_y is None or not isinstance(cap_y, (int, float)) or cap_y != cap_y:
        return DEFAULT_TARGET_FRONT_Y
    return int(max(DEFAULT_TARGET_FRONT_Y, min(cap_y, FRONT_CAP_Y)))


def table_area(cap_y=None) -> Area:
    """The whole target area of a sitting (its sides as MEASURING_AREA, its front at
    :func:`table_cap`), whatever this sitting has confirmed with the creep."""
    return Area(TARGET_X_RIGHT, TARGET_X_LEFT, TARGET_Y_BACK, table_cap(cap_y))


#: 4.3.53: the proven zone with the target area's sides (the backstop above): its front is
#: MEASURING_AREA's, its sides are no longer the recorded extent
PROVEN_TARGETS = Area(TARGET_X_RIGHT, TARGET_X_LEFT, TARGET_Y_BACK, MEASURING_AREA.ymax)
PROVEN_SWEEP = Area(TARGET_X_RIGHT, TARGET_X_LEFT, AREA_RAW.ymin, AREA_RAW.ymax)


def areas(front_y=None, cap_y=None) -> "tuple[Area, Area]":
    """(targets, swept rectangles) for a sitting that has confirmed the front zone up to
    *front_y* (None: nothing confirmed, the proven zone only), whose target area ends at *cap_y*
    (:func:`table_cap`). Targets never beyond the cap, swept rectangles never beyond it plus the
    arrival tolerance. (4.3.49: the job starts a sitting with *front_y* at the frontmost place
    THIS table's motors already brought the opening to, minus the arrival tolerance.) 4.3.53:
    the sides are the backstop (TARGET_X_RIGHT / TARGET_X_LEFT), the same for every row kind."""
    if front_y is None or not isinstance(front_y, (int, float)) or front_y != front_y \
            or front_y <= MEASURING_AREA.ymax:
        return PROVEN_TARGETS, PROVEN_SWEEP
    cap = table_cap(cap_y)
    fy = int(min(front_y, cap))
    # a swept rectangle may start where the arm READS after a clean arrival at fy (within the
    # 5-unit arrival tolerance), never beyond the cap plus that tolerance
    sy = min(fy + ARRIVAL_SLACK, cap + ARRIVAL_SLACK)
    return (Area(TARGET_X_RIGHT, TARGET_X_LEFT, TARGET_Y_BACK, fy),
            Area(TARGET_X_RIGHT, TARGET_X_LEFT, AREA_RAW.ymin, max(AREA_RAW.ymax, sy)))


def known_x(right_end_x=None, left_x=None) -> "tuple[int, int]":
    """4.3.53: (right, left) X of the ground a table's opening is KNOWN to reach: the vendor's
    own motor targets, widened by what this table's opening has been read at (free or under
    motor, the reach record). Never beyond the backstop. Nothing here refuses anything: the job
    drives a strip row beyond it with its careful row-end moves first, once per table."""
    right = VENDOR_ROW_START_X
    if isinstance(right_end_x, (int, float)) and right_end_x == right_end_x:
        right = min(right, int(right_end_x))
    left = VENDOR_APPROACH_X
    if isinstance(left_x, (int, float)) and left_x == left_x:
        left = max(left, int(left_x))
    return max(right, TARGET_X_RIGHT), min(left, TARGET_X_LEFT)


def in_front_zone(p) -> bool:
    return p[1] > MEASURING_AREA.ymax

#: Where motors drove the arm in the recordings (R1, R2, S2), as boxes; a path is "visited" when
#: every point of its swept rectangle lies in one of them.
#:   chart   every m0 and m2 target after an alignment: X -1320..1316, Y 1537..2559
#:   first   the recorded first moves from the free arm: from (-1297, 2681), (-1303, 2689),
#:           (-1283, 2677), (-1210, 2668), (-1349, 2616) to the top-right of the chart
#:   way     home line X 1102 Y 0..1498, and the approach: Y 1498 X 1000..2507, and m1, which
#:           brings the opening to (2507, 1429) (MEASURED twice, 17 Nov 2026; from (999, 1503) in
#:           the recording of that night). Until then this box reached Y 1371 and a further box
#:           X 2507..2832 stood here, both from the target field of m1 (2832, 1371), where the arm
#:           never was.
DRIVEN = (Area(-1320, 1316, 1537, 2559), Area(-1349, -1181, 1645, 2689),
          Area(1000, 1104, 0, 1500), Area(1000, 2507, 1429, 1500))

#: The recorded speeds: m0 on a chart only at 300; m2 at these (mm/s).
RECORDED_M0_SPEEDS = (300,)
#: 168 since the owner-results round: i1Profiler scanned both rows of the volunteer's recording of
#: 17 Nov 2026 at 168 (`;m2047a061c00a837`, `;m2fab7066f00a8cb`; a3 answered A 840, T 1474,
#: V 168, N 470 readings by the app's own rule; each move done 0.456 / 0.448 s after lamp + T + A).
RECORDED_M2_SPEEDS = (40, 53, 54, 61, 87, 88, 110, 118, 137, 138, 168)
#: THE DUAL ROW (the i1Pro 2 dual scan on the table, 2026-11-18): the ONLY speed i1Profiler used
#: for both passes of every accepted dual row in the volunteer's recordings of 18 Nov 2026 (B
#: 43.6-80.3: `;m204f306a0008466` forward, `;m2fa6706ad0084fb` straight back; a3 answered A 660,
#: T 2045, V 132). Never a speed of a single strip, and never allowed outside a dual row
#: (lines.classify, the table's dual phase); 82 and 51, i1Profiler's slow repeats of a failed
#: row, are NOT used (a failed dual row is offered again, or patch by patch).
DUAL_M2_SPEEDS = (132,)
#: 4.3.54 (the owner, 2026-11-21: "an option in the beta section that allows to increase or
#: decrease the speed within a certain frame by a factor"): THE FRAME of a single strip row's
#: speed. Its two ends are the slowest and the fastest speed i1Profiler was recorded sending in
#: a single row's scan move (RECORDED_M2_SPEEDS): 40 mm/s (one of its slow repeats of a failed
#: row in the 16 Nov 2026 recordings, passes.json of 2026-11-16_i1io_scan_mode) and 168 mm/s
#: (both rows of the volunteer's table, 17 Nov 2026). The table's motor was seen driven at every
#: speed in between that is listed there, in the same recorded m2 FORM; with "Row speed" not at
#: 1.00 ChromIQ may send any whole number inside the frame in that same form. 132 stays the
#: dual row's own (the gate and the simulator know a dual row by it): a single row never uses it.
ROW_SPEED_FRAME = (min(RECORDED_M2_SPEEDS), max(RECORDED_M2_SPEEDS))


def row_speed_ok(speed, dual: bool = False) -> bool:
    """The scan move's speed may be sent: a dual row only at DUAL_M2_SPEEDS; a single row at a
    recorded speed or (4.3.54, "Row speed") a whole number inside ROW_SPEED_FRAME, never the
    dual row's 132."""
    if dual:
        return speed in DUAL_M2_SPEEDS
    if speed in RECORDED_M2_SPEEDS:
        return True
    return (isinstance(speed, int) and ROW_SPEED_FRAME[0] <= speed <= ROW_SPEED_FRAME[1]
            and speed not in DUAL_M2_SPEEDS)

#: Run-in / run-out allowed beyond the aimed marks along a row, and across the rows.
RUN_OUT_MM = 10.0
ACROSS_MM = 2.0


def check_target(p, what: str, front_y=None, cap_y=None) -> None:
    tgt, _sweep = areas(front_y, cap_y)
    if not tgt.contains(p):
        whole = table_area(cap_y)
        if whole.contains(p) and in_front_zone(p):
            raise AreaRefused(f"{what}: table position X {p[0]}, Y {p[1]} lies in the front part "
                              f"of the table further than this sitting has confirmed (Y "
                              f"{tgt.ymax}); stage DZ feels its way there first")
        if CAP_AREA.contains(p) and p[1] > whole.ymax:
            raise AreaRefused(f"{what}: table position X {p[0]}, Y {p[1]} lies in front of the "
                              f"area that was aimed at (targets up to Y {whole.ymax})")
        raise AreaRefused(f"{what}: table position X {p[0]}, Y {p[1]} lies outside the measuring "
                          f"area this program uses ({tgt.text()})")


def check_path(a, b, what: str, front_y=None, cap_y=None) -> None:
    """A move from the READ position *a* to the target *b*: the target inside MEASURING_AREA
    (with its margin), the whole swept rectangle inside AREA_RAW (the start is where the arm
    physically is, so it may lie in the margin, e.g. a free arm left beside a corner)."""
    check_target(b, what + " (its end)", front_y, cap_y)
    sweep = areas(front_y, cap_y)[1]
    if not sweep.contains_path(a, b):
        raise AreaRefused(f"{what}: the rectangle the arm may sweep from {tuple(a)} to {tuple(b)} "
                          f"leaves the measuring area ({sweep.text()})")


def check_move_from_reading(a, b, what: str, front_y=None, cap_y=None) -> None:
    """4.3.49 (Basti's ruling of 19 Nov 2026, FOR THE SAFETY REVIEW): a move from *a*, a FRESH
    POSITION READING of where the arm physically stands (held or free, put there by the motors
    or by the person's hand), to the target *b*. Only the target is judged (inside the target
    area, as every computed target). The start is not compared with any recorded extent: the
    arm IS there. The way between needs no box of its own: the table moves an X carriage on an
    arm that travels along Y, each axis over one interval, so every point of the rectangle
    spanned by a point the arm stands on and a point it may be driven to has an X and a Y each
    of which the mechanism reaches (the same belief AREA_RAW's derivation states).

    One place is kept out on PHYSICAL grounds, not historical ones: a start in the BACK STRIP
    (Y below AREA_RAW's back edge, the home line and the resting place over the table's white
    tile). There the head parks over the tile holder; every recording leaves it straight along
    Y on the home line first (to_250, to_1498), and ChromIQ's own way out is those recorded
    lines. A computed move never starts there."""
    if not (a is not None and len(a) == 2 and all(math.isfinite(float(v)) for v in a)):
        raise AreaRefused(f"{what}: no usable reading of where the arm stands ({a!r})")
    if a[1] < AREA_RAW.ymin:
        raise AreaRefused(f"{what}: a computed move from {tuple(a)}, in the back strip at the "
                          f"resting place (Y below {AREA_RAW.ymin}): only the recorded ways out "
                          "start there")
    check_target(b, what + " (its end)", front_y, cap_y)


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
    """A triangle at 2000 units/s^2 up to 10 x V units/s along the STRAIGHT LINE from a to b.
    Checked against the recordings: 87 units 0.417 (0.431), 1023 units 1.43 (1.456), 1498 units
    1.73 (1.727), 1250 units 1.58 (1.599).

    4.3.50 (the first complete page on a real i1iO 2, 19 Nov 2026): the straight line, not the
    larger axis as until 4.3.49. Over the 985 real and recorded moves longer than 60 units
    (tests/i1io_table/data/real_table_moves.json) took / predicted is 1.006-1.068 on the straight
    line and 1.006-1.186 on the larger axis; the real page's diagonal to its first row (2598 x
    1778 units) took 2.528 s, 2.509 s on the straight line, 2.279 s on the larger axis."""
    d = math.hypot(b[0] - a[0], b[1] - a[1])
    vmax = 10.0 * speed
    ta = vmax / ACCEL
    if d <= vmax * ta:
        t = 2.0 * math.sqrt(d / ACCEL)
    else:
        t = d / vmax + ta
    return max(t, 0.015)


#: 4.3.50: a computed move this short (on its larger axis, table units) has NO lower time limit.
#: The real table answers a move of 0 to 3 units at once (0.015-0.016 s, 24 of 24 real and
#: recorded cases, among them the real page's 3-unit move of 19 Nov 2026), and whether it does so
#: for the same target sent again from a few units short is not recorded. 10 units = every
#: arrival miss the job tolerates or moves to once more (ARRIVAL_BESIDE_UNITS): a move this short
#: that did not happen leaves the arm at most 1 mm off, which the arrival check reads anyway.
SMALL_MOVE_UNITS = 10


def move_window(a, b, speed: int = 300) -> "tuple[float, float]":
    """The time window a computed m0 must finish in. Upper limit 1.35 t + 0.35 s, at least 0.7 s
    (catches a move that does not finish). Lower limit 0.75 t - 0.05 s (catches a done answer far
    sooner than any movement takes), none for a move of up to SMALL_MOVE_UNITS. Every one of the
    1102 real and recorded moves of real_table_moves.json lies inside its window."""
    t = predicted_move_time(a, b, speed)
    small = max(abs(b[0] - a[0]), abs(b[1] - a[1])) <= SMALL_MOVE_UNITS
    lo = 0.0 if small else max(0.0, 0.75 * t - 0.05)
    return (lo, max(0.7, 1.35 * t + 0.35))


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
    if not CAP_AREA.contains((x, y)):
        raise AreaRefused(f"a computed move to X {x}, Y {y}: outside {CAP_AREA.text()}")
    return _line("m0", x, y, speed)


def m2_line(x: int, y: int, speed: int, dual: bool = False) -> bytes:
    """The ONLY builder of a computed scan move (m2): the recorded form apart from X, Y and a
    recorded speed. *dual*: a pass of the dual row, whose only recorded speed is
    :data:`DUAL_M2_SPEEDS` (and no other)."""
    if not row_speed_ok(speed, dual):
        raise AreaRefused(f"a scan move at speed {speed}: not a recorded speed"
                          + (" for a dual row" if dual else ""))
    if not CAP_AREA.contains((x, y)):
        raise AreaRefused(f"a scan move's end X {x}, Y {y}: outside {CAP_AREA.text()}")
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
#: 4.3.49 (FOR THE SAFETY REVIEW): the allowed difference between a side of the aimed triangle
#: on the table and on the sheet grows with the side, by LENGTH_TOL_FRACTION of it. The table
#: reads long sides 0.4-0.5 % long on the volunteer's real table (19 Nov 2026, crosses of an A4
#: chart: 2764 and 2761 units for 2750, corner patches 2539 for 2530) and his eight earlier real
#: alignments passed the flat 2 mm only by 1.6 mm at worst; one round of 19 Nov by 1.9 mm. A
#: wrong point (a corner patch for a cross, a patch one row off) is 9 to 22 mm and stays refused.
LENGTH_TOL_FRACTION = 0.004


def length_tolerance(sheet_units: float) -> float:
    """Units by which a side of the aimed triangle may differ from the sheet's: 2 mm plus 0.4 %
    of the side (2.75 mm on 188 mm, 3.1 mm on 275 mm)."""
    return LENGTH_TOL_UNITS + LENGTH_TOL_FRACTION * abs(float(sheet_units))


ANGLE_TOL_DEG = 1.0         # recorded 89.9 to 90.5 degrees
ROTATION_TOL_DEG = 3.0      # recorded within 0.8 degrees; a turned sheet is 90 or 180 off
#: 4.3.53 fix round (inventory A11): a sheet read PATCH BY PATCH may lie turned by up to this
#: much: every patch is its own m0 to a computed target (the recorded form), whatever the
#: turn, and an arrival is checked; the limit only keeps a sheet turned by 90 or 180 degrees
#: (marks aimed on the wrong sides) refused. Rows keep ROTATION_TOL_DEG: a strip's scan move
#: across a turned sheet runs diagonally, and how the table moves a long diagonal m2 has not
#: been recorded (next_release.txt).
ROTATION_TOL_SPOT_DEG = 30.0


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
        BL), widened by run_out_mm along x and across_mm along y. 4.3.53: words only, never a
        refusal (see :meth:`target`)."""
        xs = [a[0] for a in self.aims_mm]
        ys = [a[1] for a in self.aims_mm]
        return (min(xs) - run_out_mm <= u[0] <= max(xs) + run_out_mm
                and min(ys) - across_mm <= u[1] <= max(ys) + across_mm)

    def target(self, u, what: str, run_out_mm: float = RUN_OUT_MM,
               front_y=None, cap_y=None) -> "tuple[int, int]":
        """The table target of the sheet point *u* (a patch centre or a row's run end from the
        side file). 4.3.53 (the owner, 2026-11-20: "probably even a little wider than where he
        aimed is safe as well. so if there are no crosshairs for aiming but patches only will
        be safe as well. for both patch by patch and rows"): the aimed marks are NOT the edge
        of the usable ground, so a point outside their rectangle is not refused (a chart aimed
        on its corner patches has its row run-outs and half of every edge patch outside it).
        Only the target area decides (:func:`check_target`: the backstop, the front). *run_out_mm*
        is kept for the callers; it no longer refuses anything (:meth:`on_sheet` stays, words
        and diagnostics only)."""
        del run_out_mm
        p = self.to_table(u)
        # 4.3.49: an alignment's targets are bounded by the area it was aimed at
        check_target(p, what, front_y, self.aimed_front_y() if cap_y is None else cap_y)
        return p

    def aimed_front_y(self) -> int:
        """4.3.49 (Basti's ruling): the frontmost table Y of the area the person aimed at, with
        the plan's run-out along the rows and ACROSS_MM across them (:meth:`on_sheet`'s area,
        mapped onto the table). Every target the plan may compute lies inside it."""
        xs = [a[0] for a in self.aims_mm]
        ys = [a[1] for a in self.aims_mm]
        corners = [(x, y) for x in (min(xs) - RUN_OUT_MM, max(xs) + RUN_OUT_MM)
                   for y in (min(ys) - ACROSS_MM, max(ys) + ACROSS_MM)]
        return max(self.to_table(c)[1] for c in corners)


def _shift_back(points, area: Area) -> str:
    """Which way the sheet would have to lie for *points* to come inside *area* (plain words; X
    falls to the right, Y grows towards the front, as the person sees the table)."""
    over = {"left": max(p[0] for p in points) - area.xmax,
            "right": area.xmin - min(p[0] for p in points),
            "back": area.ymin - min(p[1] for p in points),
            "front": max(p[1] for p in points) - area.ymax}
    parts = []
    for side, way in (("left", "to the right"), ("right", "to the left"),
                      ("back", "towards the front"), ("front", "towards the back")):
        if over[side] > 0:
            parts.append(f"about {over[side] / 10 + 1:.0f} mm further {way}")
    return " and ".join(parts)


def fit_model(aims_mm, readings, rotation_tol: float = ROTATION_TOL_DEG) -> Alignment:
    """i1Profiler's own model: the affine map through the three aims, p1 readings used AS
    TARGETS with no sight-to-opening conversion (its recorded spot targets fit it within 1 unit;
    tests/test_i1io_part_c.py checks it against every recorded alignment). The shape checks, but
    NOT the area: :func:`fit_alignment` is what the stages use."""
    (a1, a2, a3), (P1, P2, P3) = [tuple(map(float, a)) for a in aims_mm], \
        [tuple(map(float, p)) for p in readings]
    if not all(math.isfinite(v) for p in (a1, a2, a3, P1, P2, P3) for v in p):
        raise AlignmentRefused("a mark or a position reading is not a finite number")
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
    if abs(rot) > rotation_tol:
        raise AlignmentRefused(f"the sheet seems to be turned by about {abs(rot):.0f} degrees from "
                               f"the way it must lie (at most {rotation_tol:.0f} is accepted)")
    for (want, got), name in zip(lens, ("marks 1 and 2", "marks 2 and 3")):
        tol = length_tolerance(want)
        if abs(want - got) > tol:
            raise AlignmentRefused(f"{name} are {got / 10:.1f} mm apart on the table but "
                                   f"{want / 10:.1f} mm on the sheet (at most "
                                   f"{tol / 10:.1f} mm difference is accepted): one "
                                   "aim was probably on another point")
    if abs(ang - 90) > ANGLE_TOL_DEG:
        raise AlignmentRefused(f"the corner at mark 2 measures {ang:.1f} degrees on the table "
                               f"(90 within {ANGLE_TOL_DEG:.0f} is accepted): one aim was "
                               "probably off")
    # 4.3.53 fix round (A11): for a sheet allowed to lie turned further (patch by patch), the
    # order check leaves room for that turn (the side times sin of the allowed turn); a sheet
    # turned by 90 or 180 degrees still fails it, and rows keep the check as it was
    slack = (max(math.dist(P1, P2), math.dist(P2, P3)) * math.sin(math.radians(rotation_tol))
             if rotation_tol > ROTATION_TOL_DEG else 0.0)
    if not (P1[0] >= max(P2[0], P3[0]) - 30 - slack and P1[1] <= min(P2[1], P3[1]) + slack):
        raise AlignmentRefused("mark 1 must be the one furthest to the left and furthest back")
    return Alignment(tuple(tuple(a) for a in aims_mm),
                     tuple(tuple(int(v) for v in p) for p in readings), M, checks)


def fit_alignment(aims_mm, readings, rotation_tol: float = ROTATION_TOL_DEG) -> Alignment:
    """:func:`fit_model`, then all three marks inside CAP_AREA (the proven zone and the front
    zone up to its cap; whether the front zone is used is D1's question to the person). The
    marks are compared as TARGETS (the opening is put on a mark by moving to its p1 value), the
    same frame as every patch target and :func:`check_target`."""
    al = fit_model(aims_mm, readings, rotation_tol)
    pts = [tuple(map(float, p)) for p in readings]
    outside = [(n, p) for n, p in enumerate(pts, 1) if not CAP_AREA.contains(p)]
    if outside:
        n, p = outside[0]
        front = (" (further to the front than ChromIQ ever lets the arm go, whatever a table "
                 "has shown it)" if p[1] > CAP_AREA.ymax else "")
        raise AlignmentRefused(
            f"mark {n} was aimed at X {p[0]:.0f}, Y {p[1]:.0f}, outside the measuring area this "
            f"program uses ({CAP_AREA.text()}{front}; where it lies on your table is our "
            "estimate, from where the measuring opening has been in your recordings and where "
            "your recorded alignments put their marks). For all three marks the sheet would have "
            f"to lie {_shift_back(pts, CAP_AREA)}")
    return al


# ---- 4.3.49: what to tell the person (words only: nothing here allows or refuses a move) ------

def _mm_up(units: float) -> int:
    """Units to whole millimetres, rounded up, with one more millimetre to spare."""
    return int(math.ceil(max(0.0, units) / 10.0)) + 1 if units > 0 else 0


def sheet_move_advice(readings) -> dict:
    """How far the sheet would have to lie further back / front / left / right (whole mm, 0 =
    not that way) so that all three aims lie inside CAP_AREA, the target area (the corner patches lie just
    inside the marks; the aims are kept inside it although no move goes to them since 4.3.50). Words for the
    person only; :func:`fit_alignment` and the job's checks decide."""
    pts = [tuple(map(float, p)) for p in readings]
    return {"back_mm": _mm_up(max(p[1] for p in pts) - CAP_AREA.ymax),
            "front_mm": _mm_up(CAP_AREA.ymin - min(p[1] for p in pts)),
            "left_mm": _mm_up(CAP_AREA.xmin - min(p[0] for p in pts)),
            "right_mm": _mm_up(max(p[0] for p in pts) - CAP_AREA.xmax)}


def free_arm_push_advice(p) -> dict:
    """How far a FREE arm read at *p* would have to be pushed by hand (whole mm; back = away
    from the person, left / right as the person sees the table) to stand inside AREA_RAW, where
    ChromIQ may start a move or its homing from a free arm. Words only."""
    x, y = float(p[0]), float(p[1])
    return {"back_mm": _mm_up(y - AREA_RAW.ymax), "front_mm": _mm_up(AREA_RAW.ymin - y),
            "left_mm": _mm_up(AREA_RAW.xmin - x), "right_mm": _mm_up(x - AREA_RAW.xmax)}


def reach_advice_mm(need_y, cap_y) -> int:
    """4.3.49: whole mm (rounded up, one to spare) by which a sheet whose frontmost target is
    at *need_y* must lie further back to fit a table whose targets end at *cap_y*. Words for
    the person only."""
    return _mm_up(float(need_y) - float(cap_y))


def lengths_fit(aims_mm, readings) -> bool:
    """Whether *readings* have the shape of *aims_mm* (the length, corner and turn checks of
    :func:`fit_model`). Used to tell the person which points they aimed at."""
    try:
        fit_model(aims_mm, readings)
    except AlignmentRefused:
        return False
    return True

