"""EVERY NUMBER ABOUT THE i1iO TABLE, IN ONE PLACE, WITH WHERE IT COMES FROM.

The chart layout (`workflow.i1io.chart`) reads its numbers from here and from
nowhere else, so a table owner's next result can correct a number without
anybody touching layout logic. Each entry says how sure we are:

* ``VERIFIED``: it holds on every case of the recordings, or a maker's or a
  program's published figure that was checked in use (the instrument's
  opening, ArgyllCMS's spacer), or a number of ChromIQ's own code that a test
  pins to its place.
* ``PUBLISHED``: a published figure that nobody on the project has checked on
  a real table yet.
* ``LIKELY``: one reading fits all the evidence of the recordings, not proved.
* ``OURS``: a design choice of ours, with the reason.

WHERE THE NUMBERS COME FROM. X-Rite's public product and specification pages;
a published review of the table (Northlight Images); ArgyllCMS's printtarg;
the defaults of ChromIQ's own layout engine; recordings that table owners made
of their own table; the output and the shipped user help of the maker's
program, used as a user; and our own choices. An older limit on the space
between two patches (20 percent of the patch) did not come from our
recordings; it is replaced by what our own measurements and charts show.

"RECORDINGS" is the decode of the table owner's two recordings of 2026
(GitHub issue #129, an i1iO 2 with an i1Pro 2), kept privately. No recording
is in the repository.

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
#: i1iO 3; Northlight's review gives the same for the first i1iO. The owner's
#: recordings drove the arm over 427 mm in X, but that includes parking
#: positions off the chart, so it does not widen this. Everything the arm does
#: on a chart (the aims, every patch, both ends of every run) stays inside it.
REACH_MM = Fact((320.0, 230.0),
                "X-Rite i1iO 3 product page; Northlight Images review of the "
                "first i1iO. Not published for the i1iO 2",
                PUBLISHED)

#: The i1Pro 2's measuring opening.
APERTURE_MM = Fact(4.5, "X-Rite i1Pro 2 specification "
                   "(workflow.layout_engine.instruments.STRIP_READ_APERTURE_MM)",
                   VERIFIED)

# ---- what a patch must be to be read -------------------------------------

#: How often the i1Pro 2 reads while it is drawn along a row: a fixed burst of
#: readings of 5.004 ms each, lamp on, no gap between them (every trigger of
#: both recordings; the table's own memory stores 0.005004). The table
#: package's own copy is `table.scan.READING_S` (a test holds them together).
SCAN_READING_INTERVAL_S = Fact(0.005004, "RECORDINGS: every trigger", VERIFIED)

#: The row speeds the recordings show, mm/s; `table.geometry.RECORDED_M2_SPEEDS`
#: is the list the job may send (a test holds the chart's speeds inside it).
SCAN_SPEEDS_MM_S = Fact((138.0, 88.0, 54.0), "RECORDINGS", LIKELY)

#: The clean border at each edge of a patch that no reading is used from: at
#: least this much, or what the arm travels in the spread of its start
#: (`table.scan.strip_edge_mm`; a test holds the copies equal).
READER_EDGE_MM = Fact(0.5, "table.scan.STRIP_EDGE_MIN_MM", VERIFIED)
READER_START_SPREAD_S = Fact(0.018, "table.scan.MOTION_START_SPREAD_S",
                             VERIFIED)
#: A patch read in a row needs this many clean readings
#: (`table.spot.STRIP_MIN_READINGS`; a test holds the copies equal).
READER_MIN_READINGS = Fact(3, "table.spot.STRIP_MIN_READINGS", VERIFIED)

#: How far from a patch's centre the arm may have landed and still count as
#: arrived (`table` refuses more than 5 units of 0.1 mm), and how far off an
#: ordinary aim at a cross may be.
LANDING_MM = Fact(0.5, "the job's arrival tolerance, 5 units", VERIFIED)
AIM_ERROR_MM = Fact(0.7, "an ordinary aim at a cross", LIKELY)

#: The smallest patch, both ways: the opening plus the landing error on each
#: side. Below it no reading lies inside one patch.
PATCH_MIN_MM = Fact(5.5, "ours: opening 4.5 plus 0.5 landing each side", OURS)
#: The largest: only the page and the arm's reach; nothing else limits it.
PATCH_MAX_ALONG_MM = Fact(REACH_MM.value[0], "ours: the reach", OURS)
PATCH_MAX_ACROSS_MM = Fact(REACH_MM.value[1], "ours: the reach", OURS)

#: How far a run may end beyond the corner patches a person aims at (safety
#: review of the new layout, B2): what 4.3.65's longest patch (20 mm) had, half
#: the patch and the 10 mm run. Further, and the arm would be sent past ground
#: nobody's aim has shown to exist; such a page keeps its crosses.
PAST_THE_AIMS_MM = Fact(20.0, "ours: 4.3.65's longest patch", OURS)
#: Under this size the instrument can see the patch beside it when an ordinary
#: aim and the arm's landing error come together (`neighbour_share`): said.
SMALL_PATCH_NOTE_MM = Fact(7.0, "ours: 4.5 + 2 x (0.7 + 0.5) = 6.9", OURS)
#: Under this length a row read in one movement is untried on a table: said.
SHORT_PATCH_NOTE_MM = Fact(10.0, "ours: the proven patch length", OURS)
#: From this length the table can read a row in one movement (some recorded
#: speed leaves every patch READER_MIN_READINGS clean readings; below, patch
#: by patch): a copy for the chart side, held to the reader's own planning by
#: a test.
STRIP_FROM_MM = Fact(7.6, "table.spot.plan_strip_row", VERIFIED)
#: From this length the dual scan reads a row in one movement (below, patch by
#: patch with both conditions), and the Row speed factor may speed a row up.
DUAL_ROW_FROM_MM = Fact(9.5, "ours: three clean readings in both passes", OURS)
ROW_SPEED_FROM_MM = Fact(9.5, "ours: as the dual row", OURS)

#: THE STRIPS RUN ALONG THE ARM (the coordinator and Basti, 2026-11-13): the
#: engine's strips are the lines the arm scans in one move, so ChromIQ's own
#: CONTRAST SPACERS lie between the patches of a scan line, exactly where the
#: row placement check looks for an edge. ArgyllCMS lays every i1Pro strip out
#: with 1 mm spacers (printtarg; `instruments._build_base`, the i1 branch), so
#: the default is what ChromIQ prints for handheld strips. Read on a real table.
SPACER_MM = Fact(1.0, "printtarg's i1Pro spacer (instruments.py, i1 branch)",
                 VERIFIED)
SPACER_MODE = Fact("colored", "ours: the contrast-maximising spacers ChromIQ "
                   "prints for handheld strips", OURS)
#: The narrowest spacer a person may set (0 = none): half a millimetre still
#: covers 14 % of what the opening sees. Under SPACER_MM nobody has read one.
SPACER_MIN_MM = Fact(0.5, "ours: still 14 % of the opening's view", OURS)

#: Between ROWS (across the scan) there is no gap by default: the 4.5 mm
#: aperture keeps 1.75 mm inside an 8 mm row on each side, and a row gap buys
#: nothing measured and costs whole rows. Manual may set any gap the page
#: holds: a wider gap only costs patches.
ROW_GAP_MM = Fact(0.0, "ours: aperture 4.5 mm in an 8 mm row", OURS)

# ---- one sheet on the table ------------------------------------------------

#: LARGER PIECES THAN ANY EVER TRIED (up to half an A3+ sheet) wait for their
#: own safety sign-off. False: a piece of a larger sheet is at most A4 or
#: Letter (`PIECE_MAX_MM`), and the maxima below are theirs.
#: `table.caps.LARGE_PIECES` is the table package's own copy (a test holds the
#: two equal: they change together or not at all).
LARGE_PIECES = False
#: The largest piece of a divided sheet, across and along the strips.
PIECE_MAX_MM = Fact((215.9, 297.0), "ours: the sizes tried on a table", OURS)
PIECE_MAX_LARGE_MM = Fact((242.0, 331.0), "ours: half of A3+ / 13 x 19 in, "
                          "untried on a table", OURS)
#: The most a page may hold: patches in a strip, strips, patches. Generate
#: refuses more (`chart.check_sheet`), START refuses the same numbers
#: (`table.caps.LAYOUT_MAXIMA`, its own copy: chart code never imports the
#: table package; a test holds them equal and works them out again from the
#: layout engine: 5.5 mm patches, no spacers, no crosses, no labels, on the
#: largest piece, the run held inside the reach).
LAYOUT_MAXIMA_SMALL = {"per_row": 49, "rows": 37, "per_page": 1813}
LAYOUT_MAXIMA_LARGE = {"per_row": 54, "rows": 42, "per_page": 2268}
MAX_PAGES = 667


def layout_maxima() -> dict:
    """The most one page of an i1iO chart may hold (and the most pages)."""
    m = LAYOUT_MAXIMA_LARGE if LARGE_PIECES else LAYOUT_MAXIMA_SMALL
    return {**m, "pages": MAX_PAGES}


def neighbour_share(size_mm: float, off_mm: "float | None" = None) -> float:
    """The part (0..1) of what the instrument sees that belongs to the patch
    beside, for a patch *size_mm* wide read *off_mm* from its middle (default:
    an ordinary aim and the arm's landing error together, 1.2 mm): the segment
    of the round opening beyond the patch's edge."""
    import math
    if off_mm is None:
        off_mm = AIM_ERROR_MM.value + LANDING_MM.value
    r = APERTURE_MM.value / 2.0
    d = float(size_mm) / 2.0 - float(off_mm)
    if d >= r:
        return 0.0
    a = math.acos(max(-r, d) / r)
    return (a - math.sin(a) * math.cos(a)) / math.pi


def readings_per_patch(length_mm: float, speed_mm_s: float) -> float:
    """Readings the i1Pro 2 takes over *length_mm* of a row at *speed*."""
    return length_mm / (speed_mm_s * SCAN_READING_INTERVAL_S.value)


def row_edge_mm(speed_mm_s: float) -> float:
    """The clean border the reader leaves at each patch edge at *speed*."""
    return max(READER_EDGE_MM.value, speed_mm_s * READER_START_SPREAD_S.value)


def clean_length_mm(length_mm: float, speed_mm_s: float) -> float:
    """The part of a patch *length_mm* long that a row read at *speed* uses:
    the patch less half the opening and the border at each end (may be
    negative)."""
    return length_mm - APERTURE_MM.value - 2.0 * row_edge_mm(speed_mm_s)


#: The table's position unit (for the measuring step; the chart does not use it).
TABLE_UNIT_MM = Fact(0.1, "RECORDINGS", LIKELY)

#: Which way the sheet lies: the arm parks at Y 0 and Y grows from the chart's
#: top edge to its bottom edge (RECORDINGS), so the chart's top edge faces
#: the back of the table, where the arm parks. Rows lie along X.
TOP_EDGE_TOWARDS_PARKING = Fact(True, "RECORDINGS (axes of the aligned "
                                "corners)", VERIFIED)

#: The order the maker's program asks its user for the three corners.
AIMING_ORDER = Fact(("top-left", "bottom-left", "bottom-right"),
                    "RECORDINGS", VERIFIED)

# ---- our design choices -------------------------------------------------

#: Patch length along the row (the scan direction): at 88 mm/s, the speed the
#: job chooses for it, four clean readings on every patch, and a row that lies
#: up to 1.8 mm off is still read (at 2.2 mm it is refused). Read on a
#: real table. Patch by patch it leaves 2.75 mm on each side of the opening.
PATCH_ALONG_MM = Fact(10.0, "ours: four clean readings at 88 mm/s; read on a "
                      "table", OURS)

#: Patch height across the row: 1.75 mm each side of the 4.5 mm aperture for
#: alignment and arm error, which also suits a spot reading.
PATCH_ACROSS_MM = Fact(8.0, "ours: aperture plus 1.75 mm each side", OURS)

#: "Compact", the second chart layout offered (25 November 2026): patches as
#: long as they are wide, read in one movement at 61 mm/s with three clean
#: readings each, the proven 1 mm spacer kept (one thing changed at a time).
#: Not tried on a table. Patch by patch it leaves 1.75 mm each side.
COMPACT_ALONG_MM = Fact(8.0, "ours: three clean readings at 61 mm/s", OURS)
COMPACT_ACROSS_MM = Fact(8.0, "ours: as the standard layout", OURS)

#: Blank paper before the first and after the last patch of every row, so the
#: first and the last patch are read whole, even when the sheet lies a little
#: off: half the opening (2.25 mm), the row lying off (2.8 mm, recorded rows
#: of a real table, kept privately) and the arm's creep at its ends (1.3 mm) are
#: 6.4 mm. 7 mm would gain a patch only on Letter and 4 x 6 in, so the proven
#: 10 mm stay. The dual scan needs no more.
RUN_MM = Fact(10.0, "ours: 6.4 mm needed, 10 mm proven", OURS)

#: NOTHING IS PRINTED ON A SCAN LINE OUTSIDE THE PATCHES (Basti, 2026-11-13):
#: the instrument reads all through the run-in and the run-out, and ink there
#: would move the edges the row placement check looks for. So the runs are blank paper, and a label sits only where the
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
#: The largest label size an i1iO chart prints (review r3 M1): the letters
#: stand side by side at the strip pitch, so a label keeps this much less than
#: it (`label_max_mm`); the numbers stand at the patch pitch, two characters
#: side by side along the strip. A larger size asked for is printed at the
#: largest.
LABEL_AIR_MM = Fact(1.0, "ours: 1 mm of paper between two letters", OURS)
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
#: How far in from the page's left edge the patch numbers start (Manual's
#: "Clip" text distance, which an i1iO chart fixes): beside the strips, inside
#: the marks' 20 mm side band, so they cost no patch and stay well inside the
#: edge a printer leaves unprinted (6.4 mm on a Canon PRO-300's Letter sheet,
#: where 4 mm cut them: review r3 m3).
NUMBERS_EDGE_MM = Fact(10.0, "ours: past every printer edge ChromIQ knows, "
                       "inside the 20 mm side band", OURS)

#: The engine's strip letters and patch numbers are turned this far on the
#: page so they read the right way up on the sheet laid across the table.
LABEL_TURN_DEG = Fact(90, "ours: the sheet lies a quarter turn clockwise",
                      OURS)

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
#: unprintable edge (the engine's default margin). What the table's hold and
#: the arm's glider ring need beyond that is not published, so nothing is added.
PRINTER_EDGE_MM = Fact(5.0, "the engine's default page margin for text "
                       "(text_edge)", OURS)

#: The ChromIQ wordmark's height in the top band (beside mark 1), and the
#: smallest it is shrunk to before it is left off: 2 mm, the same as the
#: smallest label size, still legible in print (Basti, 2026-11-13: "or very
#: small in a place where it takes up no space for patches").
WORDMARK_MM = Fact(4.0, "ours", OURS)
WORDMARK_MIN_MM = Fact(2.0, "ours: the smallest label size", OURS)

#: Clear paper kept round every mark (no patch, run or text inside it).
MARK_CLEAR_MM = Fact(1.0, "ours", OURS)

#: THE AIMING CROSSES ARE AN OPTION (the owner, 2026-11-13: "add an option to
#: turn on the crosses (or not in turn) and then make even more patches fit a
#: single sheet"). On by default: a cross is easier and safer to put the
#: sight on than the middle of a patch. Off, the person aims at the centres
#: of three corner patches (table top left, bottom left, bottom right), as
#: X-Rite's own software does; the table needs three points either way.
#: 4.3.57 (item 29): switching them off moves no patch (the same margins,
#: alignment and patch order as with them; until 4.3.56 `chart.corner_order`
#: swapped visible patches into the corners and the freed side band took
#: patches); a page whose corner patches cannot be aimed at keeps its crosses
#: (`chart.page_crosses`).
AIM_CROSSES = Fact(True, "ours: easier and safer to aim at than a patch",
                   OURS)
#: A corner patch for aiming is mid to dark: CIELAB L* at most this (on the
#: display colours of the set), so it stands out from the paper ...
CORNER_MAX_L = Fact(60.0, "ours: clearly darker than paper (L* about 95)",
                    OURS)
#: ... and either this saturated (C*ab) or, if greyish, at most CORNER_DARK_L.
CORNER_MIN_C = Fact(25.0, "ours", OURS)
CORNER_DARK_L = Fact(45.0, "ours", OURS)
#: Never near white, whatever is left in a small set.
CORNER_NEVER_L = Fact(85.0, "ours: near white is not aimed at", OURS)
#: THE ANGLE THAT TELLS ONE STRIP FROM THE NEXT. Mark 3 aimed one strip too
#: far in turns the corner at mark 2 by atan(strip pitch / row length); the
#: alignment refuses more than ALIGN_ANGLE_TOL_DEG, and honest alignments were
#: recorded up to half a degree off, which can hide as much of it. So corner
#: patches are aimed at only where one strip turns the corner by at least the
#: two together (`chart.corners_tell_a_strip`).
ALIGN_HONEST_DEG = Fact(0.5, "RECORDINGS: alignments of 89.9 to 90.5 degrees",
                        LIKELY)
#: ...and the alignment's angle limit at mark 2, a copy for the chart side
#: (the chart code never imports the table package): equal to
#: `table.geometry.ANGLE_TOL_DEG` (a test holds the two together).
ALIGN_ANGLE_TOL_DEG = Fact(1.0, "table.geometry.ANGLE_TOL_DEG", OURS)
#: 4.3.57 (item 30): how far off the centre of a corner PATCH an ordinary aim
#: by eye lands, sideways. An ordinary aim at a CROSS is up to
#: `AIM_ERROR_MM` off; the row placement study measured aim plus print errors
#: of 1 to 2.5 mm on patches. A patch has no cross hair to meet, so 1.5 mm.
CORNER_AIM_ERROR_MM = Fact(1.5, "ours: ordinary aims at crosses, the "
                           "row placement study's patches 1-2.5 mm", OURS)

#: Without the crosses the text line (chart name, page N/M, sheet text, logo)
#: is printed only where it costs no patch (the owner, 2026-11-13): it is
#: shrunk, down to capitals this high, before a part is left off.
TEXT_MIN_CAP_MM = Fact(1.5, "ours: 6 pt type, still legible in print", OURS)
#: ... and never nearer the paper's edge than this, whichever printer prints
#: it: the patch numbers' own distance. Until 2026-11-13 it could sit 5 to
#: 9 mm from the edge, and a Canon PRO-300 leaves 6.4 mm of a Letter sheet
#: unprinted. Where no free paper is left that far in, the line is left off
#: by the no-cost rule and the help asks for the name by hand.
TEXT_EDGE_MM = Fact(NUMBERS_EDGE_MM.value, "ours: = NUMBERS_EDGE_MM, past "
                    "every printer edge ChromIQ knows", OURS)


def label_max_mm(strip_pitch_mm: float, patch_pitch_mm: float) -> float:
    """The largest label size on a chart of that strip pitch (letters side by
    side, LABEL_AIR_MM apart) and patch pitch (two-digit numbers, half as far
    apart), never below the smallest size that reads well."""
    numbers = (float(patch_pitch_mm) - LABEL_AIR_MM.value / 2.0) / (
        2.0 * LETTER_ADVANCE)
    return max(LABEL_SIZE_RANGE_MM.value[0],
               min(float(strip_pitch_mm) - LABEL_AIR_MM.value, numbers))


def run_ends_mm(page_h: float, top: float, bottom: float
                ) -> "tuple[float, float]":
    """*top* and *bottom* (the patch block's margins along the strips) raised,
    both alike, until a strip's run spans at most the arm's reach: the block
    and its two runs. Only a piece over 324 mm with its letters off notices."""
    over = (float(page_h) - top - bottom + 2 * RUN_MM.value
            - REACH_MM.value[0])
    if over <= 1e-9:
        return top, bottom
    return top + over / 2.0, bottom + over / 2.0


def as_record() -> dict:
    """Every fact as ``{name: value}``, for the side file, so a later version
    knows which numbers made a sheet."""
    out = {}
    for name, fact in globals().items():
        if isinstance(fact, Fact):
            value = fact.value
            out[name] = list(value) if isinstance(value, tuple) else value
    return out


def row_label_band_mm(size_mm: "float | None" = None) -> float:
    """Paper a column of row numbers (up to two digits) takes beside the
    runs, its gap included."""
    size = LABEL_SIZE_MM.value if not size_mm else float(size_mm)
    return round(2 * LABEL_CHAR_WIDTH * size + ROW_LABEL_GAP_MM.value
                 + ROW_LABEL_EDGE_MM.value - RUN_EDGE_MM.value, 3)


#: THE STRIP LETTERS SIT AT THE BOTTOM OF THE PAGE, beyond every strip's
#: run-out: on the table (the sheet a quarter turn clockwise) that is the LEFT
#: end of every strip, and the patches run from there, 1 at the left (the
#: owner, 2026-11-13: "strip labels on the other side so the numbers can be
#: read from left to right"). ChromIQ draws them itself
#: (`chart.draw_furniture`), turned to read upright on the table, in the
#: engine's label face, JetBrains Mono, whose advance is 0.6 of the size.
LETTER_EDGE_MM = Fact(4.0, "ours: the engine's own text edge", OURS)
LETTER_ADVANCE = 0.6
#: The letters' size when Manual leaves it on "auto": the engine's own
#: automatic label size for an i1iO chart (4.9 mm, the patch numbers'),
#: rounded up.
LETTER_AUTO_MM = Fact(5.0, "ours: the engine's automatic label size, 4.9 mm",
                      OURS)


def letter_band_mm(size_mm: "float | None" = None) -> float:
    """Paper the strip letters take below the run-outs, from the page edge:
    the text edge, two letters at *size_mm* (a chart of more than 26 strips
    needs two) and LABEL_CLEAR_MM before the run-out."""
    size = float(size_mm or 0.0) or LETTER_AUTO_MM.value
    return round(LETTER_EDGE_MM.value + 2 * LETTER_ADVANCE * size
                 + LABEL_CLEAR_MM.value, 3)


#: THE MARKS COST AS LITTLE AS THEY CAN (the owner, 2026-11-13: "do they
#: use space that could be used for printing more patches?"). A cross sits
#: in its corner, MARK_INSET_MM in from both edges (its arms 8 mm from the
#: paper edge, clear of the widest unprintable edge seen); its DIGIT sits
#: beside it along the strips, towards the middle of the page, in paper the
#: strips' runs and labels never use, so it widens nothing. What a side band
#: needs is then only the cross and MARK_CLEAR_MM: 15 mm. Until 2026-11-13
#: the digit sat beside the cross ACROSS the strips and every side band was
#: 20 mm, which cost one strip on A4 (504 instead of 528) and two on Letter
#: (462 instead of 506).
MARK_SIDE_MM = Fact(15.0, "ours: mark inset 11 + half the cross 3 + 1 clear",
                    OURS)


def numbers_band_mm(size_mm: "float | None" = None,
                    start_mm: "float | None" = None) -> float:
    """Paper the patch numbers take at the page's left (the table's top), from
    the page edge to the strips: NUMBERS_EDGE_MM (or *start_mm*, where a clip
    border ends), the numbers turned (as wide on the page as their size) and
    ROW_LABEL_GAP_MM before the first strip."""
    size = float(size_mm or 0.0) or LETTER_AUTO_MM.value
    start = NUMBERS_EDGE_MM.value if start_mm is None else float(start_mm)
    return round(start + size + ROW_LABEL_GAP_MM.value, 3)


#: THE CLIP BORDER IS AN OPTION, OFF BY DEFAULT (the owner, 2026-11-13: "the
#: clip border should be possible to enable if a user wants it as an option.
#: just off by default"). The table holds the sheet itself, so the band holds
#: no clip: it is the engine's notes band (Notes box, custom text, branding or
#: an image), as on a ColorMunki, SpectroScan or CR30 chart, always along the
#: page's LEFT edge (the table's top edge): the other long edge holds crosses
#: 2 and 3 and the name line.
CLIP_BORDER = Fact(False, "ours: the owner's ruling, off by default", OURS)
#: The narrowest band: its content starts NUMBERS_EDGE_MM (10 mm) in from the
#: paper edge, past every unprinted edge ChromIQ knows, so a narrower band
#: would hold next to nothing.
CLIP_MIN_MM = Fact(20.0, "ours: 10 mm of content past the 10 mm text edge",
                   OURS)
#: The band's content keeps this far from the page's top and bottom edges
#: (the table's right and left edges), as the name line does.
CLIP_EDGE_MM = Fact(10.0, "ours: = TEXT_EDGE_MM, past every printer edge "
                    "ChromIQ knows", OURS)


def margins_mm(strip_letters: bool = True,
               label_size_mm: "float | None" = None, numbers: bool = True,
               crosses: bool = True, clip_mm: float = 0.0,
               letter_band: "float | None" = None,
               numbers_edge: "float | None" = None,
               ) -> "tuple[float, float, float, float]":
    """The patch block's smallest margins ``(top, right, bottom, left)`` on
    the PORTRAIT page: at the top a run, at the bottom a run and the strip
    letters (if on, at *label_size_mm*), at the sides the marks' zones (the
    patch numbers live in the left one, beside the first strip, clear of
    the marks and of every scan line).

    Without the aiming crosses (*crosses* False, :data:`AIM_CROSSES`) a side
    needs only the printer's edge, and the patch numbers' band on the left:
    the paper the crosses held goes to patches, and the text line takes only
    what is left over (`chart.free_text_plan`).

    With a clip border of *clip_mm* (its width from the paper edge, 0 = none)
    on the left, the left margin is at least the band, the numbers' band and
    LABEL_CLEAR_MM (without numbers: the band and LABEL_CLEAR_MM). This is a
    floor for the margin only: the engine places the patch numbers itself
    (`raster.apply_row_label_geometry`), and they may stand in the part of
    the band its content leaves free, 1 mm clear of that content. *letter_band* is the strip
    letters' band when the caller has measured it (`chart.letter_band_for`:
    another pattern, face or an underline), else `letter_band_mm`."""
    top = RUN_EDGE_MM.value + RUN_MM.value
    band = (letter_band_mm(label_size_mm) if letter_band is None
            else float(letter_band))
    bottom = RUN_MM.value + (band if strip_letters else RUN_EDGE_MM.value)
    side = MARK_SIDE_MM.value if crosses else PRINTER_EDGE_MM.value
    right = side
    clip = float(clip_mm or 0.0)
    if clip > 0:
        left = max(side, numbers_band_mm(label_size_mm, start_mm=clip)
                   if numbers else clip + LABEL_CLEAR_MM.value)
    else:
        left = max(side, numbers_band_mm(label_size_mm, start_mm=numbers_edge)
                   if numbers else 0.0)
    return top, right, bottom, left


def patch_limits_mm() -> "tuple[tuple[float, float], tuple[float, float]]":
    """``((along_min, along_max), (across_min, across_max))``: what Manual
    may set. No smaller than a patch the opening fits into with the arm's
    landing error (PATCH_MIN_MM); upwards only the arm's reach, and the page
    itself says what it holds."""
    lo = PATCH_MIN_MM.value
    return ((lo, PATCH_MAX_ALONG_MM.value), (lo, PATCH_MAX_ACROSS_MM.value))


def gaps_mm(strip_gap: "float | None" = None,
            inter_patch: "float | None" = None) -> "tuple[float, float]":
    """``(gap between strips, extra white gap between the patches of a
    strip)`` an i1iO chart is laid out with: Manual's "Strip gap" and
    "Inter-patch gap" (default none, upwards only what the page holds)."""
    g = ROW_GAP_MM.value if strip_gap is None else float(strip_gap)
    i = 0.0 if inter_patch is None else float(inter_patch)
    return max(g, 0.0), max(i, 0.0)


def spacer_width_mm(asked: "float | None" = None) -> float:
    """The width of the spacer between two patches of a strip on an i1iO
    chart: Manual's "Spacer width" (0 or None = SPACER_MM), never narrower
    than SPACER_MIN_MM; upwards only what the page holds."""
    return max(float(asked), SPACER_MIN_MM.value) if asked else SPACER_MM.value


#: Where the patch block sits in the space the margins leave, when nobody
#: chose ("" in Manual's "Patch area alignment" for the i1iO): centred
#: between the crosses; without them at the patch numbers, so what is left
#: over goes to the table's bottom edge, where the text line is
#: (`chart.free_text_plan`). Any of the nine places keeps every run, mark
#: and label inside the margins, which are what keep them clear.
ALIGN_WITH_CROSSES = Fact("center", "ours", OURS)
#: 4.3.57 (item 29): THE CROSSES NEVER MOVE A PATCH. Without them the block
#: sits where it sits with them (until 4.3.56 "center-left", which moved it):
#: switching the crosses off changes only what is aimed at.
ALIGN_WITHOUT_CROSSES = Fact("center", "ours: the same place as with the "
                             "crosses (4.3.57, item 29)", OURS)
ALIGNMENTS = ("top-left", "top-center", "top-right", "center-left", "center",
              "center-right", "bottom-left", "bottom-center", "bottom-right")


def patch_size_mm(along: "float | None" = None,
                  across: "float | None" = None) -> "tuple[float, float]":
    """The patch size an i1iO chart is laid out with: *along* x *across* when
    given (Manual's patch size), held inside :func:`patch_limits_mm`, else the
    defaults."""
    (alo, ahi), (clo, chi) = patch_limits_mm()
    a = float(along) if along else PATCH_ALONG_MM.value
    c = float(across) if across else PATCH_ACROSS_MM.value
    return min(max(a, alo), ahi), min(max(c, clo), chi)
