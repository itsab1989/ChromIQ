"""EVERY NUMBER ABOUT AN i1iSis CHART, IN ONE PLACE, WITH WHERE IT COMES FROM.

The chart layout (`workflow.isis.chart`) and the i1Profiler export
(`workflow.isis.export`) read their numbers from here and from nowhere else.
Each entry says how sure we are:

* ``VERIFIED``: read in a primary source we can show: X-Rite's *i1iSis Chart
  Design Guidelines*, Edition 2g ("G"), Kodak's MPI 10 page ("K"), or
  measured in a chart i1Profiler 3.8.8 drew ("I", the study of 2026-11-14,
  ``ChromIQ-work/2026-11-14_isis_chart_study``, REQUIREMENTS v2, "R§").
* ``LIKELY``: one reading fits every source, not proved.
* ``OURS``: a design choice of ours, with the reason.

Nothing here was read by a real i1iSis: nobody on the project owns one.

All lengths are millimetres on the sheet. x runs ACROSS the feed from the
chart's left edge, y ALONG the feed from its leading (top) edge, where the
black bar is. The sheet is fed bar end first.
"""
from __future__ import annotations

from dataclasses import dataclass

VERIFIED = "VERIFIED"
LIKELY = "LIKELY"
OURS = "OURS"


@dataclass(frozen=True)
class Fact:
    value: "float | int | tuple"
    source: str
    confidence: str


# ---- patches --------------------------------------------------------------

PATCH_MIN_MM = Fact(6.0, "G §2; I (slider minimum, R§1)", VERIFIED)
PATCH_MAX_MM = Fact(20.0, "G §2; I (slider maximum, R§1)", VERIFIED)
PATCH_DEFAULT_MM = Fact(6.0, "I: 'Use default' gives 6 x 6 mm (R§2)", VERIFIED)
#: The barcode states patch sizes in steps of 0.25 mm above 6 mm.
BARCODE_STEP_MM = Fact(0.25, "G §4; I barcodes decoded (R§0)", VERIFIED)
#: Patches per chart (per page).
PATCHES_PER_PAGE_MAX = Fact(3000, "G §2", VERIFIED)

# ---- the leading edge -----------------------------------------------------

#: The header length ("leader"): from the chart's leading edge to the bar.
HEADER_MIN_MM = Fact(32.0, "G (32 to 80 mm); I slider 0 % (R§2)", VERIFIED)
HEADER_MAX_MM = Fact(80.0, "G; I slider 100 % (R§2)", VERIFIED)
HEADER_DEFAULT_MM = Fact(32.0, "I default (R§2)", VERIFIED)
#: i1Profiler draws the bar's top half a millimetre below the header length:
#: 32.5 at 32, 56.5 at 56, 80.5 at 80 (V02, V17, V08).
BAR_TOP_EXTRA_MM = Fact(0.5, "I V02, V17, V08 (R§2, R§4)", VERIFIED)
BAR_HEIGHT_MM = Fact(6.0, "G allows 5 to 8; I always 6.0 (R§4)", VERIFIED)
#: Bar to the first patch row: at least 6 mm; 20 mm with a barcode.
CLEAR_UNDER_BAR_MM = Fact(6.0, "G >= 6; I 6.0 (R§4)", VERIFIED)
CLEAR_UNDER_BAR_BARCODE_MM = Fact(20.0, "G 20 mm with a barcode; I 20.0 "
                                  "(R§4, V06)", VERIFIED)
#: Nothing may be printed in the 20 mm above the bar across its width.
CLEAR_ABOVE_BAR_MM = Fact(20.0, "G 'some clear space without any mark or "
                          "writing'; I writes only in the first 10.25 mm",
                          VERIFIED)
#: The text band at the leading edge (name, page line, corner labels).
TEXT_BAND_MM = Fact(12.0, "K 'You can write in the first 1.2 cm'; I writes "
                    "at y 3.25 to 10.25 (R§4 Z1)", VERIFIED)
NAME_LINE_TOP_MM = Fact(3.25, "I (R§4)", VERIFIED)
NAME_LINE_BOTTOM_MM = Fact(10.25, "I (R§4)", VERIFIED)
CORNER_LABEL_TOP_MM = Fact((3.0, 6.0), "I corner labels y 3 to 6 (R§4)",
                           VERIFIED)
#: The feed arrows, in the diamond columns, y 10 to 30, pointing to the
#: leading edge.
ARROW_Y_MM = Fact((10.0, 30.0), "I (R§4)", VERIFIED)

# ---- the side geometry ----------------------------------------------------

#: Marker (diamond) size, one left and one right of every row.
DIAMOND_W_MM = Fact(5.0, "G >= 5 x 2.5; I exactly 5.0 x 2.5 (R§4)", VERIFIED)
DIAMOND_H_MM = Fact(2.5, "G; I (R§4)", VERIFIED)
#: Chart edge to marker (Dist 1) and marker to patches (Dist 2): normal 5/5,
#: tight margins 4/3 (side 15 / 12 mm).
DIST1_MM = Fact(5.0, "G >= 3; I 5.0 (R§4)", VERIFIED)
DIST2_MM = Fact(5.0, "G >= 3, 5 with a barcode; I 5.0 (R§4)", VERIFIED)
DIST1_TIGHT_MM = Fact(4.0, "I V07, V16 (R§2)", VERIFIED)
DIST2_TIGHT_MM = Fact(3.0, "I V07, V16 (R§2; i1Profiler uses 3 even with a "
                      "barcode, V16)", VERIFIED)
#: White kept around each diamond: nothing else printed there.
DIAMOND_CLEAR_MM = Fact(3.0, "K 'only 3 mm is supported'; G 'white around "
                        "them'", VERIFIED)
#: The fit tolerance i1Profiler's column count uses (0.43 <= t < 1.0).
COLUMN_FIT_TOLERANCE_MM = Fact(0.5, "I W04, V16 (R§1; challenge S1)",
                               VERIFIED)

# ---- the trailing edge ----------------------------------------------------

TRAILER_MIN_MM = Fact(25.5, "G >= 25; I 25.5 (R§4)", VERIFIED)
#: The inner trailer, last row to +22 mm: nothing printed (keep-out).
TRAILER_INNER_KEEP_OUT_MM = Fact(22.0, "I leaves it empty (R§4 Z7); OURS "
                                 "to keep it white", OURS)
#: The last 3.5 mm of the trailer carry the bottom corner labels.
TRAILER_TEXT_MM = Fact(3.5, "I (R§4)", VERIFIED)
CHART_MIN_LENGTH_MM = Fact(171.0, "I 171.0 in every padded case (R§9, R§13)",
                           VERIFIED)
CHART_MAX_LENGTH_MM = Fact(660.0, "G chart length 170 to 660", VERIFIED)
#: X-Rite's smallest chart width; i1Profiler does not widen (X08: 54 mm),
#: ChromIQ draws the outline at 60 mm with white beyond the right markers.
CHART_MIN_WIDTH_MM = Fact(60.0, "G; X08 (R§12); OURS to widen", OURS)

# ---- the outline ----------------------------------------------------------

OUTLINE_LINE_MM = Fact(0.5, "I (R§4)", VERIFIED)
OUTLINE_DASH_MM = Fact(2.5, "I 2.5 mm dashes every 5 mm (R§4)", VERIFIED)

# ---- the barcode ----------------------------------------------------------

BARCODE_GAP_MM = Fact(3.0, "I bar bottom 38.5, barcode 41.5 (R§4)", VERIFIED)
BARCODE_HEIGHT_MM = Fact(13.0, "G; I 41.5 to 54.5 (R§4)", VERIFIED)
BARCODE_ELEMENT_MM = Fact(4.0, "I elements 4 mm, 1 mm apart (R§4)", VERIFIED)
BARCODE_PITCH_MM = Fact(5.0, "I (R§4)", VERIFIED)
BARCODE_NARROW_MM = Fact(0.5, "I (R§4)", VERIFIED)
BARCODE_WIDE_MM = Fact(1.0, "I (R§4)", VERIFIED)
#: Two characters per element, 6 mm each, 1 mm apart, read bottom to top.
BARCODE_CHAR_MM = Fact(6.0, "I (R§4)", VERIFIED)
BARCODE_CHAR_GAP_MM = Fact(1.0, "I (R§4)", VERIFIED)

# ---- the instrument -------------------------------------------------------

#: The right marker's right edge from the LEFT paper edge, and the paper
#: width the slot takes.
CAP_MM = Fact({"standard": 218.0, "xl": 318.0}, "G §3; I W12, X06 (R§12)",
              VERIFIED)
PAPER_W_MM = Fact({"standard": (60.0, 230.0), "xl": (60.0, 330.0)},
                  "G; X-Rite support 'Basic iSis information'", VERIFIED)
PAPER_LEN_MM = Fact((170.0, 660.0), "G; X-Rite support", VERIFIED)
#: Leading paper edge to the bar's top, when the sheet is fed as printed.
LEADER_MAX_FROM_PAPER_MM = Fact(80.0, "G (32 to 80 mm, from the paper)",
                                VERIFIED)
#: Paper edge to the marker, at least.
DIST1_MIN_FROM_PAPER_MM = Fact(3.0, "G Dist 1 >= 3", VERIFIED)

# ---- i1Profiler's defaults (what the factory defaults equal) -------------

MARGIN_DEFAULT_MM = Fact(5.0, "I default chart margins 5 mm (R§2)", VERIFIED)
