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
                "X-Rite i1iO 3 product page; Northlight Images i1iO review",
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

#: How often the i1Pro 2 reads while i1Profiler drags it along a row, and the
#: fastest of the three speeds i1Profiler used (PROTOCOL 4.4: 520 readings of
#: 5.00 ms during a 138 units/0.1 s move).
SCAN_READING_INTERVAL_S = Fact(0.005, "PROTOCOL 4.4 (i1Pro trigger, 5.00 ms)",
                               VERIFIED)
SCAN_FASTEST_MM_S = Fact(138.0, "PROTOCOL 4.4 (m2 speed 138; unit 0.1 mm "
                         "LIKELY, PROTOCOL 3.1)", LIKELY)

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

#: Patch length along the row (the scan direction). At the fastest speed one
#: reading covers 138 x 0.005 = 0.69 mm; a 9.5 mm patch less the 4.5 mm
#: aperture leaves 5 mm of clean patch, about 7 readings at 138 mm/s and 18 at
#: 54 mm/s, and is close to the tester's own 9.54 mm pitch.
PATCH_ALONG_MM = Fact(9.5, "ours: scan readings per patch, see comment", OURS)

#: Patch height across the row: 1.75 mm each side of the 4.5 mm aperture for
#: alignment and arm error, which also suits a spot reading.
PATCH_ACROSS_MM = Fact(8.0, "ours: aperture plus 1.75 mm each side", OURS)

#: Blank paper before the first and after the last patch of every row, for the
#: arm to reach speed and to stop, and for a clean paper-to-patch edge.
RUN_MM = Fact(10.0, "ours: nothing is known about the arm's acceleration",
              OURS)

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
