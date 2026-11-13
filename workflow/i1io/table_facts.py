"""EVERY NUMBER ABOUT THE i1iO TABLE, IN ONE PLACE, WITH WHERE IT COMES FROM.

The chart layout (`workflow.i1io.chart`) reads its numbers from here and from
nowhere else, so the tester's next recording can correct a number without
anybody touching layout logic. Each entry says how sure we are:

* ``VERIFIED``: read from a source we can show (X-Rite's own page or files,
  or arithmetic that holds on every case in the recordings).
* ``PUBLISHED``: a published figure that nobody on the project has checked on
  a real table yet.
* ``LIKELY``: one reading fits all the evidence of the recordings, not proved.
* ``OURS``: a design choice of ours, with the reason.

"PROTOCOL" is the decode of the tester's two i1Profiler recordings (GitHub
issue #129, i1Profiler 3.8.6, an i1iO 2 with an i1Pro 2), kept privately;
"STUDY" is the integration study of 2026-11-13. Neither recording is in the
repository and no number here was copied from a vendor file.

All lengths are millimetres on the sheet. X runs along the sheet's long side
(the direction the arm scans a row), Y down the sheet.
"""
from __future__ import annotations

from dataclasses import dataclass

VERIFIED = "VERIFIED"
PUBLISHED = "PUBLISHED"
LIKELY = "LIKELY"
OURS = "OURS"


@dataclass(frozen=True)
class Fact:
    value: "float | tuple"
    source: str
    confidence: str


#: The area the arm can reach, X by Y. X-Rite publishes 32 x 23 cm for the
#: i1iO 3; Northlight's review gives the same for the first i1iO. The tester's
#: recordings drove the arm over 427 mm in X, but that includes parking
#: positions off the chart (PROTOCOL 3.1), so it does not widen this.
REACH_MM = Fact((320.0, 230.0),
                "X-Rite i1iO 3 product page; Northlight Images review of the "
                "first i1iO. Not published for the i1iO 2, and the recordings "
                "only spanned 263 x 154 mm between aimed corners: the tester "
                "must confirm the arm reaches all three marks",
                PUBLISHED)

#: The i1Pro 2's measuring opening.
APERTURE_MM = Fact(4.5, "X-Rite i1Pro 2 specification "
                   "(workflow.layout_engine.instruments.STRIP_READ_APERTURE_MM)",
                   VERIFIED)

#: i1Profiler's own patch-size range for the i1iO 2: width (along the row) and
#: height (across it).
PATCH_RANGE_ALONG_MM = Fact((6.0, 20.0),
                            "i1Profiler workflow files (docs/dev_pxwf_format.md)",
                            VERIFIED)
PATCH_RANGE_ACROSS_MM = Fact((7.0, 20.0),
                             "i1Profiler workflow files (docs/dev_pxwf_format.md)",
                             VERIFIED)

# ---- scanning a row (ALL FROM ONE RECORDING: issue #129, R1 and R2, an
#      i1iO 2 with an i1Pro 2 Rev E; to be confirmed by the tester) ---------

#: How often the i1Pro 2 reads while i1Profiler drags it along a row: a fixed
#: burst of N readings of 5.004 ms each, lamp on, no gap between them
#: (i1pro2_side RESULTS 6.1: 139 integration clocks of 36 us, all 494
#: triggers; the table's own memory stores 0.005004).
SCAN_READING_INTERVAL_S = Fact(0.005004, "i1pro2_side RESULTS 6.1 (every "
                               "trigger of both recordings)", VERIFIED)

#: The three arm speeds i1Profiler used on every row, mm/s (the m2 speeds
#: 137-138, 87-88, 53-54 in table units per 0.1 s; the unit 0.1 mm is LIKELY).
#: The fastest pass alone already held every patch with about 14 readings
#: each (RESULTS 6.2, a fit to the spot readings, LIKELY strong).
SCAN_SPEEDS_MM_S = Fact((138.0, 88.0, 54.0), "PROTOCOL 4.4; i1pro2_side "
                        "RESULTS 6.1-6.2", LIKELY)

#: Delay between the move command and the instrument's first reading:
#: 0.10 s at the fastest speed, up to 0.8 s at the slower ones (RESULTS 6.1).
#: The recordings show the table finishing later by exactly as much as the
#: trigger came later, so it seems to start moving in step with the
#: instrument (observation CERTAIN, mechanism a GUESS).
SCAN_TRIGGER_DELAY_S = Fact((0.10, 0.80), "i1pro2_side RESULTS 6.1", LIKELY)

#: ArgyllCMS's patch finder in the i1Pro driver keeps the middle two thirds
#: of every patch it finds in a stream and drops a patch with 3 readings or
#: fewer after that (native/instlib/i1pro_imp.c: MIN_SAMPLES 3, the 66 % trim
#: in i1pro_extract_patches_multimeas).
ARGYLL_MIN_SAMPLES = Fact(3, "native/instlib/i1pro_imp.c MIN_SAMPLES",
                          VERIFIED)

#: OURS: the readings a patch should get at the fastest speed. i1Profiler's
#: own fastest pass gave 13.8 (the only case seen to work); 14 keeps us at or
#: above it. After the 4.5 mm aperture's own smear (about 6.5 readings at
#: that speed) and Argyll's two-thirds trim, a 14-reading patch still has
#: about 5 clean readings, above Argyll's minimum of 3.
SCAN_SAFE_READINGS = Fact(14, "ours: at least what i1Profiler's fastest "
                          "pass gave", OURS)


def readings_per_patch(length_mm: float, speed_mm_s: float) -> float:
    """Readings the i1Pro 2 takes over *length_mm* of a row at *speed*."""
    return length_mm / (speed_mm_s * SCAN_READING_INTERVAL_S.value)


def min_patch_length_mm(speed_mm_s: float,
                        readings: "float | None" = None) -> float:
    """The shortest patch along the row that still gets *readings* readings
    (default :data:`SCAN_SAFE_READINGS`) at *speed*."""
    n = SCAN_SAFE_READINGS.value if readings is None else readings
    return n * speed_mm_s * SCAN_READING_INTERVAL_S.value


def run_in_mm(speed_mm_s: "float | None" = None) -> float:
    """Blank paper needed before the first patch of a row at *speed* (the
    fastest by default): the arm may travel for the shortest trigger delay
    seen before the first reading arrives."""
    v = max(SCAN_SPEEDS_MM_S.value) if speed_mm_s is None else speed_mm_s
    return v * SCAN_TRIGGER_DELAY_S.value[0]


#: The tester's own i1Profiler chart: 28 patches 9.54 mm apart along each row,
#: 18 rows 8.2 mm apart (PROTOCOL 3.1, the unit LIKELY 0.1 mm).
TESTER_CHART_PITCH_MM = Fact((9.54, 8.2), "PROTOCOL 3.1", LIKELY)

#: The table's position unit (for the measuring step; the chart does not use it).
TABLE_UNIT_MM = Fact(0.1, "PROTOCOL 3.1", LIKELY)

#: Which way the sheet lies: the arm parks at Y 0 and Y grows from the chart's
#: top edge to its bottom edge (PROTOCOL 3.1), so the chart's top edge faces
#: the back of the table, where the arm parks. Rows lie along X.
TOP_EDGE_TOWARDS_PARKING = Fact(True, "PROTOCOL 3.1 (axes of the aligned "
                                "corners)", VERIFIED)

#: The order i1Profiler asks for the three corners (PROTOCOL 4.3).
AIMING_ORDER = Fact(("top-left", "bottom-left", "bottom-right"),
                    "PROTOCOL 4.3", VERIFIED)

# ---- our design choices -------------------------------------------------

#: Patch length along the row (the scan direction): the shortest length
#: that gets SCAN_SAFE_READINGS at the fastest speed seen
#: (`min_patch_length_mm`: 14 x 138 x 0.005004 = 9.67 mm), rounded up to
#: 10 mm. Patch by patch it leaves 2.75 mm on each side of the aperture.
PATCH_ALONG_MM = Fact(10.0, "ours: min_patch_length_mm(138) = 9.67, "
                      "rounded up", OURS)

#: Patch height across the row: 1.75 mm each side of the 4.5 mm aperture for
#: alignment and arm error, which also suits a spot reading.
PATCH_ACROSS_MM = Fact(8.0, "ours: aperture plus 1.75 mm each side", OURS)

#: Blank paper before the first and after the last patch of every row:
#: `run_in_mm()` at the fastest speed (138 x 0.10 = 13.8 mm), rounded up, so
#: a reading that starts late at full speed still finds paper before the
#: first patch. The slower passes' longer delays (to 0.8 s) do not fit on any
#: sheet; the recordings suggest the table waits for the instrument, which
#: the tester must confirm.
RUN_MM = Fact(15.0, "ours: run_in_mm(138) = 13.8, rounded up", OURS)

#: A solid black bar across every row inside the run-in and the run-out, at
#: this distance before the first and after the last patch and this wide: a
#: dark-to-white edge at a known place, so a scan can be lined up by position
#: even when the first or last patch is pale. The challenge of 2026-11-13
#: asked for a timing aid that a printed sheet can no longer get later.
ANCHOR_BAR_GAP_MM = Fact(5.0, "ours", OURS)
ANCHOR_BAR_MM = Fact(2.0, "ours", OURS)

#: Blank paper outside each run, to the sheet's left and right edges.
RUN_EDGE_MM = Fact(2.0, "ours: so a run never starts on the paper edge", OURS)

#: The aiming marks: centre this far in from both sheet edges at its corner,
#: a cross of this span and line width inside a square outline of this size,
#: and the digit this high beside it.
MARK_INSET_MM = Fact(10.0, "ours: clear of most printers' unprintable edge",
                     OURS)
MARK_CROSS_MM = Fact(8.0, "ours", OURS)
MARK_LINE_MM = Fact(0.3, "ours: thin enough to put the sight's cross hair on",
                    OURS)
MARK_FRAME_MM = Fact(5.0, "ours: makes the cross easy to find", OURS)
MARK_DIGIT_MM = Fact(4.0, "ours", OURS)

#: The bands above and below the patches that hold the marks, the arrow, the
#: page number and the chart name.
BAND_MM = Fact(18.0, "ours: mark inset + half the cross + 4 mm clear", OURS)

#: Clear paper kept round every mark (no patch, run or text inside it).
MARK_CLEAR_MM = Fact(1.0, "ours", OURS)


def as_record() -> dict:
    """Every fact as ``{name: {value, source, confidence}}``, for the side
    file, so a later version knows which numbers made a sheet."""
    out = {}
    for name, fact in globals().items():
        if isinstance(fact, Fact):
            value = fact.value
            out[name] = {"value": list(value) if isinstance(value, tuple) else value,
                         "source": fact.source, "confidence": fact.confidence}
    return out


def margins_mm() -> "tuple[float, float, float, float]":
    """The patch block's margins ``(top, right, bottom, left)``."""
    side = RUN_MM.value + RUN_EDGE_MM.value
    return BAND_MM.value, side, BAND_MM.value, side
