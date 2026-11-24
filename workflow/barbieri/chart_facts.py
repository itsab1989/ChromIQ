"""EVERY NUMBER ABOUT A BARBIERI SPECTRO 100xy CHART, IN ONE PLACE, WITH ITS SOURCE.

The chart layout (`workflow.barbieri.chart`) reads its numbers from here and
from nowhere else. Each entry says how sure we are:

* ``VERIFIED``: read in a source we can show: Barbieri's own 100xy datasheets
  of 2002 to 2004 ("D"), the Profile-Xpert Gateway 3 manual and the job files
  Gateway 3.26 writes when it is used ("G"), or an owner's real Spectro32 files
  and template ("O-files": his 32 x 28 test chart at 6.5 mm, read in one run of
  896 patches).
* ``OWNER``: what an owner of the device said on issue #215, not checked here.
* ``OURS``: a design choice of ours, with the reason.

Nobody on the project owns the instrument; nothing here was measured on one.

All lengths are millimetres on the sheet. Columns run across the page (left
to right), rows down it. A column is a strip of the layout engine, so its
letter is the strip letter (A, B, ... AF), and a row is the patch number
down it (1, 2, ...): patch "AF1" is the top patch of column AF.
"""
from __future__ import annotations

from dataclasses import dataclass

VERIFIED = "VERIFIED"
OWNER = "OWNER"
OURS = "OURS"


@dataclass(frozen=True)
class Fact:
    value: "float | int | tuple | dict | str"
    source: str
    confidence: str


@dataclass(frozen=True)
class Head:
    """One measuring opening the entry offers (the "Measuring opening" choice)."""
    key: str                 # the recipe value
    aperture_mm: float
    mode: str                # "reflection" or "transmission"
    spectro32: str           # Spectro32's template command, "" when unknown
    model: str               # which 100xy model has it (datasheets)
    default_patch_mm: float  # the patch size this opening starts with
    tested: bool             # read on a real device by an owner
    source: str


# ---- the measuring openings (datasheets: model 1 reflection 3 mm,
# transmission 0.5 and 3 mm; model 2 reflection 3 and 6 mm, transmission 3 mm)

HEAD_REFLECTION_3 = "reflection-3"
HEAD_TRANSMISSION_3 = "transmission-3"
HEAD_TRANSMISSION_05 = "transmission-0.5"
HEAD_REFLECTION_6 = "reflection-6"

HEADS: "dict[str, Head]" = {
    HEAD_REFLECTION_3: Head(
        HEAD_REFLECTION_3, 3.0, "reflection", "MR", "1 and 2", 6.5, True,
        "D (both models); O-files: 896 patches of 6.5 mm read in one run"),
    HEAD_TRANSMISSION_3: Head(
        HEAD_TRANSMISSION_3, 3.0, "transmission", "MT", "1 and 2", 6.5, False,
        "D; OWNER (template command MT); OURS: the 3 mm reflection size"),
    HEAD_TRANSMISSION_05: Head(
        HEAD_TRANSMISSION_05, 0.5, "transmission", "M5", "1", 1.0, False,
        "D (model 1); OWNER (template command M5, 'I would trust 1 mm "
        "patches more'); OURS: 0.25 mm each side for aiming and travel"),
    HEAD_REFLECTION_6: Head(
        HEAD_REFLECTION_6, 6.0, "reflection", "", "2", 10.0, False,
        "D (model 2 only; its Spectro32 command was never seen); OURS: the "
        "3 mm ratio of patch to opening, rounded up"),
}

#: The opening a new chart starts with: the only one read on a real device.
DEFAULT_HEAD = HEAD_REFLECTION_3

#: The order the choice lists them in.
HEAD_ORDER = (HEAD_REFLECTION_3, HEAD_TRANSMISSION_3, HEAD_TRANSMISSION_05,
              HEAD_REFLECTION_6)

#: How much paper a patch should keep beyond the opening on each side, for
#: the hand aim and the table's travel. Below it ChromIQ warns, never refuses.
EDGE_ALLOWANCE_MM = Fact(0.25, "OURS: the 0.5 mm opening on a 1 mm patch "
                         "(the owner's suggestion) leaves this much", OURS)

# ---- the grid ----------------------------------------------------------------

#: The smallest step of the table and Spectro32's unit for offsets and spans.
STEP_MM = Fact(0.1, "D 'smallest step 0.1 mm'; O-files (template R line in "
               "0.1 mm)", VERIFIED)
#: Patches across and down that Gateway accepts (1 to 99 each). Spectro32's
#: own limit is not known; the cap keeps a chart readable by both.
MAX_PER_SIDE = Fact(99, "G manual: patches x, y 1 to 99", VERIFIED)
#: Gateway names its rows A to Z, then a to z: 52 rows before the names run
#: out (its horizontal format, where the letter is the ROW).
GATEWAY_ROW_NAMES = Fact(52, "G demo files: row 27 = a1, row 40 = n47",
                         VERIFIED)
#: The owner's 32 x 28 chart at 6.5 mm and the R line his template held.
OWNER_TEMPLATE = Fact((32, 28, 6.5, "R0,0,2015,1755,32,28"),
                      "O-files (template line) and his README", VERIFIED)

# ---- the instrument ---------------------------------------------------------

#: The largest area the datasheets say the table reads automatically. NOT a
#: limit ChromIQ applies: an owner may read bigger charts; it is named only in
#: the help, with its source (Basti, 2026-11-24).
READING_AREA_MM = Fact((235.0, 200.0), "D 2002 to 2004: 'max automatic area "
                       "235 x 200 mm'", VERIFIED)
#: The paper a reflective sheet needs to the LEFT of the patches. The
#: datasheets disagree: 15 mm (2003 web page, Italian and French sheets) and
#: 35 mm (English and German sheet of 2004). ChromIQ starts at 15 mm and says
#: so in the help.
LEFT_BORDER_MM = Fact((15.0, 35.0), "D: 15 mm (2003 web, IT/FR) vs 35 mm "
                      "(EN/DE 2004)", VERIFIED)
#: Reading pace: about 7 minutes for 220 patches.
SECONDS_PER_PATCH = Fact(1.9, "D '~7 min / 220 patches'", VERIFIED)

# ---- the chart's own defaults ------------------------------------------------

#: Margins of a new reflective chart (top, right, bottom, left): the left
#: border of the datasheets, 10 mm elsewhere, raised on the right and the
#: bottom so the patch area stays inside the datasheet reading area
#: (:func:`workflow.barbieri.chart.default_margins`).
DEFAULT_MARGIN_MM = Fact(10.0, "OURS: room for the corner marks and the "
                         "aim ticks", OURS)

# ---- the marks (all in the margins, outside the patch grid) -----------------

#: Thin line of a corner mark and an aim tick.
MARK_LINE_MM = Fact(0.25, "OURS: visible under a laser spot and on film "
                    "against a lit cross", OURS)
#: The aim corner (upper right) is drawn this many times bolder, so a sheet
#: or film laid mirrored or turned shows it at once.
MARK_BOLD_FACTOR = Fact(3.0, "OURS", OURS)
#: White between the patch grid and the start of a mark.
MARK_GAP_MM = Fact(0.8, "OURS: never touches a patch", OURS)
#: Length of a corner arm or tick, shortened to what the margin holds.
MARK_ARM_MM = Fact(5.0, "OURS", OURS)
#: The shortest mark still drawn; a margin with less room draws none and
#: the build says so.
MARK_ARM_MIN_MM = Fact(0.3, "OURS", OURS)
#: Side of the small solid square left of patch A1 (the first patch read).
START_MARK_MM = Fact(1.5, "OURS", OURS)
