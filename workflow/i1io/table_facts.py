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

#: THE TESTER'S SCANS WERE i1Profiler'S FALLBACK, NOT ITS SUCCESS
#: (2026-11-13_i1profiler_io_facts RESULTS 2.1 and the summary): i1Profiler's
#: help says a row that fails is read again more slowly and then patch by
#: patch, which is exactly what every row of his chart (9.54 x 8.2 mm, no
#: gaps) did. The data held every patch (14 to 36 readings each, RESULTS 6.2
#: of the i1Pro 2 side), but i1Profiler's own recognition gave up. So
#: nothing here is taken as proof that a scan of that layout works, and the
#: design leaves more room than it had:
#:
#: * OURS: the speed we design for is i1Profiler's middle one, not its
#:   fastest; the measuring step chooses the speed, and a slower scan is
#:   still far quicker than patch by patch;
SCAN_DESIGN_SPEED_MM_S = Fact(88.0, "ours: i1Profiler's middle speed", OURS)
#: * OURS: at least this many readings on every patch at that speed, half
#:   again what the fastest recorded pass gave (about 14);
SCAN_SAFE_READINGS = Fact(20, "ours: about 1.5 x the fastest recorded pass",
                          OURS)
#: * OURS: a thin white gap between neighbouring patches of a row, so every
#:   patch boundary is an edge a stream patch finder can see, also between
#:   two similar colours (X-Rite asks scanning charts for "gaps or a minimum
#:   deltaE between the patches"; i1Profiler's driver refuses a gap of more
#:   than 20 % of the patch length; 1 mm is 10 % of a 10 mm patch). On top,
#:   the patches are scrambled as on every ChromIQ chart, which X-Rite's help
#:   recommends for the i1iO too. UNPROVEN until a tester has scanned it.
SCAN_GAP_MM = Fact(1.0, "ours: X-Rite's supported-targets note; i1Profiler's "
                   "20 % gap limit", OURS)
#: Between ROWS (across the scan) there is no gap by default: the 4.5 mm
#: aperture keeps 1.75 mm inside an 8 mm row on each side, and the arm's
#: positioning error is not published (the recordings show the encoder
#: drifting a few tenths of a millimetre at rest, PROTOCOL 3.1), so a row gap
#: buys nothing measured and costs whole rows. Manual may add one, up to this.
ROW_GAP_MM = Fact(0.0, "ours: aperture 4.5 mm in an 8 mm row; arm accuracy "
                  "unpublished", OURS)
ROW_GAP_MAX_MM = Fact(3.0, "ours", OURS)
GAP_MAX_FRACTION = Fact(0.2, "i1Profiler driver: 'gaps size too large (more "
                        "than 20% of the patch length)'", VERIFIED)


def readings_per_patch(length_mm: float, speed_mm_s: float) -> float:
    """Readings the i1Pro 2 takes over *length_mm* of a row at *speed*."""
    return length_mm / (speed_mm_s * SCAN_READING_INTERVAL_S.value)


def min_patch_length_mm(speed_mm_s: "float | None" = None,
                        readings: "float | None" = None) -> float:
    """The shortest patch along the row that still gets *readings* readings
    (default :data:`SCAN_SAFE_READINGS`) at *speed*."""
    n = SCAN_SAFE_READINGS.value if readings is None else readings
    v = SCAN_DESIGN_SPEED_MM_S.value if speed_mm_s is None else speed_mm_s
    return n * v * SCAN_READING_INTERVAL_S.value


def run_in_mm(speed_mm_s: "float | None" = None) -> float:
    """Blank paper needed before the first patch of a row at *speed* (the
    design speed by default): the arm may travel for the shortest trigger
    delay seen before the first reading arrives."""
    v = SCAN_DESIGN_SPEED_MM_S.value if speed_mm_s is None else speed_mm_s
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

#: Patch length along the row (the scan direction). The shortest that gets
#: SCAN_SAFE_READINGS at the design speed is `min_patch_length_mm()` =
#: 20 x 88 x 0.005004 = 8.81 mm; 10 mm gives 22.7 readings at 88 mm/s and
#: still 14.5 at the fastest recorded 138 mm/s. Patch by patch it leaves
#: 2.75 mm on each side of the aperture.
PATCH_ALONG_MM = Fact(10.0, "ours: above min_patch_length_mm() = 8.81",
                      OURS)

#: Patch height across the row: 1.75 mm each side of the 4.5 mm aperture for
#: alignment and arm error, which also suits a spot reading.
PATCH_ACROSS_MM = Fact(8.0, "ours: aperture plus 1.75 mm each side", OURS)

#: Blank paper before the first and after the last patch of every row:
#: `run_in_mm()` at the design speed (88 x 0.10 = 8.8 mm), rounded up, so a
#: reading that starts late still finds paper before the first patch, as
#: little as possible of the sheet going to it (Basti, 2026-11-13: "use as
#: much space on the paper as possible for patches"). The fastest recorded
#: speed would need 13.8 mm; the recordings suggest the table waits for the
#: instrument anyway, which the tester must confirm.
RUN_MM = Fact(10.0, "ours: run_in_mm(88) = 8.8, rounded up", OURS)

#: NOTHING IS PRINTED ON A SCAN LINE OUTSIDE THE PATCHES (Basti, 2026-11-13):
#: the instrument reads all through the run-in and the run-out, and a patch
#: finder working on the stream of readings would take any ink there for a
#: patch. So the runs are blank paper, and a label sits only where the
#: aperture never passes during a scan: a row label beyond the end of its
#: run, a column label above the first row, at least LABEL_CLEAR_MM from the
#: patch edge across the scan. (An earlier draft put a black timing bar in
#: every run-in; it was taken out for exactly this reason.)
#:
#: The labels themselves are only for the person: the table needs none, the
#: positions come from the three marks. Column letters above the patches,
#: row numbers beside the rows, as SAMPLE_LOC names a patch ("C7" = column C,
#: row 7), so a warning and the sheet use the same name.
LABEL_SIZE_MM = Fact(2.5, "ours: the smallest size that still reads well "
                     "in print", OURS)
LABEL_SIZE_RANGE_MM = Fact((2.0, 4.0), "ours", OURS)
#: Clear paper between a label and the nearest patch edge across the scan.
#: The aperture is 4.5 mm on an 8 mm row, so it keeps 1.75 mm inside the
#: row's edges; with an alignment or arm error of that size it reaches the
#: edge, and 1 mm more keeps a label out of its sight.
LABEL_CLEAR_MM = Fact(1.0, "ours: aperture 4.5 mm in an 8 mm row, plus 1 mm",
                      OURS)
#: The label font's capital height and digit width as fractions of its size
#: (Inter Bold, the engine's label face), so a box in mm holds its text.
LABEL_CAP_HEIGHT = 0.73
LABEL_CHAR_WIDTH = 0.85

#: The row numbers start at least this far from the paper's left edge, so a
#: printer that leaves an edge unprinted does not cut them (same reason as
#: MARK_INSET_MM); on A4 and Letter it costs no column.
ROW_LABEL_EDGE_MM = Fact(5.0, "ours", OURS)

#: Clear paper between a row label and the end of the row's run.
ROW_LABEL_GAP_MM = Fact(1.0, "ours", OURS)

#: Blank paper outside each run, to the sheet's left and right edges.
RUN_EDGE_MM = Fact(2.0, "ours: so a run never starts on the paper edge", OURS)

#: The aiming marks: centre this far in from both sheet edges at its corner,
#: a cross of this span and line width inside a square outline of this size,
#: and the digit this high beside it.
MARK_INSET_MM = Fact(11.0, "ours: the cross stays 8 mm from the paper edge, "
                     "clear of the widest unprintable edge seen (6.4 mm, a "
                     "Canon PRO-300 description, on screen 2026-11-13)", OURS)
MARK_CROSS_MM = Fact(6.0, "ours", OURS)
MARK_LINE_MM = Fact(0.3, "ours: thin enough to put the sight's cross hair on",
                    OURS)
MARK_FRAME_MM = Fact(5.0, "ours: makes the cross easy to find", OURS)
MARK_DIGIT_MM = Fact(4.0, "ours", OURS)

#: The bands above and below the patches that hold the marks, the arrow, the
#: page number and the chart name.
#: No band of their own for the marks: the top and bottom rows start right
#: below (above) a mark's zone (inset + half the cross + MARK_CLEAR_MM), so a
#: row's run never crosses a mark, and the labels and text lines share the
#: paper beside the marks, which can never hold a row anyway.
BAND_MM = Fact(15.0, "ours: mark inset 11 + half the cross 3 + 1 mm clear",
               OURS)

#: Where the top text line (the ChromIQ wordmark and the page "N/M") sits,
#: its middle this far from the top edge: above the column letters.
TEXT_LINE_MM = Fact(8.5, "ours", OURS)

#: Paper ChromIQ's other charts leave at an edge by default, for the printer's
#: unprintable edge (the engine's default margin), and what the table needs
#: beyond that at the sheet's edges: the electrostatic hold and the arm's
#: glider ring are not documented with a number (i1Profiler facts RESULTS,
#: [TESTER]), so nothing is added for them yet.
PRINTER_EDGE_MM = Fact(5.0, "the engine's default page margin for text "
                       "(text_edge); the hold and the ring: unknown", OURS)

#: The ChromIQ wordmark's height in the top band (beside mark 1).
WORDMARK_MM = Fact(4.0, "ours", OURS)

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


def row_label_band_mm(size_mm: "float | None" = None) -> float:
    """Paper a column of row numbers (up to two digits) takes beside the
    runs, its gap included."""
    size = LABEL_SIZE_MM.value if not size_mm else float(size_mm)
    return round(2 * LABEL_CHAR_WIDTH * size + ROW_LABEL_GAP_MM.value
                 + ROW_LABEL_EDGE_MM.value - RUN_EDGE_MM.value, 3)


def margins_mm(row_labels: bool = False,
               label_size_mm: "float | None" = None
               ) -> "tuple[float, float, float, float]":
    """The patch block's margins ``(top, right, bottom, left)``: the mark
    bands above and below, the runs at the sides, and with *row_labels* a
    band for the row numbers beyond the left run."""
    side = RUN_MM.value + RUN_EDGE_MM.value
    left = side + (row_label_band_mm(label_size_mm) if row_labels else 0.0)
    return BAND_MM.value, side, BAND_MM.value, left


def patch_limits_mm() -> "tuple[tuple[float, float], tuple[float, float]]":
    """``((along_min, along_max), (across_min, across_max))``: what Manual
    may set. Along the row, no shorter than a patch that still gets
    SCAN_SAFE_READINGS at the design speed (rounded UP to 0.1 mm, so 8.9 mm)
    and no longer than i1Profiler's own maximum; across it, i1Profiler's own
    range for the i1iO 2 (its minimum, 7 mm, is X-Rite's)."""
    import math
    lo = math.ceil(min_patch_length_mm() * 10) / 10
    along = (max(lo, PATCH_RANGE_ALONG_MM.value[0]), PATCH_RANGE_ALONG_MM.value[1])
    return along, tuple(PATCH_RANGE_ACROSS_MM.value)


def gaps_mm(along_gap: "float | None" = None,
            row_gap: "float | None" = None,
            patch_along: "float | None" = None) -> "tuple[float, float]":
    """``(gap along the row, gap between rows)`` an i1iO chart is laid out
    with: the given values (Manual's "Strip gap" and "Inter-patch gap"),
    held to 0 .. 20 % of the patch length along the row and 0 ..
    ROW_GAP_MAX_MM between rows; None takes the defaults."""
    length = patch_along or PATCH_ALONG_MM.value
    a = SCAN_GAP_MM.value if along_gap is None else float(along_gap)
    r = ROW_GAP_MM.value if row_gap is None else float(row_gap)
    return (min(max(a, 0.0), GAP_MAX_FRACTION.value * length),
            min(max(r, 0.0), ROW_GAP_MAX_MM.value))


def patch_size_mm(along: "float | None" = None,
                  across: "float | None" = None) -> "tuple[float, float]":
    """The patch size an i1iO chart is laid out with: *along* x *across* when
    given (Manual's patch size), held inside :func:`patch_limits_mm`, else the
    defaults."""
    (alo, ahi), (clo, chi) = patch_limits_mm()
    a = float(along) if along else PATCH_ALONG_MM.value
    c = float(across) if across else PATCH_ACROSS_MM.value
    return min(max(a, alo), ahi), min(max(c, clo), chi)
