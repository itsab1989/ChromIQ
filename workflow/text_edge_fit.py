"""Where a sheet's text lands against the patch area, on all four sides.

**Text on any of the four sides is never dropped.** Knut's ruling, 2026-09-10,
correcting what shipped in 4.2.3:

    "For the right margin, the text must still be visible, even if the patch
    area overlaps on the right Run Chart Notes text. Else the user will not
    notice that it is silently dropped, like you now do. The user must be given
    the chance to see that something is wrong, and then adjust the margins to
    place the patch area further in on the paper, so that the chart notes can be
    visible. […] For the Strip labels, we previously designed a warning message
    that should come (in the message field in Measured from Preview frame) if
    the text is overlapping with the patch area due to the margins. This should
    also be implemented for text defined for the right margin, when Run Chart
    Notes are defined or "Stamp settings used on the chart" is selected, or when
    Clip border content is defined (for either left or right side) and also for
    the bottom margin, when sheet text (custom text field) is defined. They
    should all behave the same way."

So there is one law and it is written here once, rather than four times in four
layers:

* the text is drawn at the distance "Text distance from edge" asks for, and the
  patch area is allowed to overlap it;
* the overlap is measured and reported, in red, in the "Measured from Preview"
  frame's message field.

**Why the predicate lives in its own module.** The four sides are decided in
three different places — the strip labels and the sheet text by the renderer
(`workflow/layout_engine/raster.py`), the clip band by the geometry
(`workflow/layout_engine/geometry.py`), and the chart note by a stamper that
runs over a finished raster (`workflow/tiff_metadata.py`) — while the warning
has to be raised by a Qt panel that is a layer above all three. Nothing can
travel up from the stamper: it runs once, at build time, on a chart the user has
already committed to, and the panel has to say "this will overlap" while they
are still moving the spin boxes. So the panel PREDICTS, and the only way a
prediction stays true is if the thing being predicted reads its floor from the
same place. :data:`NOTE_MIN_STRIP_PX` is that place: `tiff_metadata` imports it
to decide how wide a note strip it needs, and
:func:`chart_note_overlap` uses it to decide whether to warn.

Every function here is pure arithmetic in millimetres, with no Qt and no image
library, so the law can be tested on its own.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Millimetres of slop before a touch counts as an overlap. Two floats that
#: describe the same edge of the same sheet differ in the third decimal; a
#: warning that fires on that is a warning nobody reads.
EPS_MM = 0.05

#: The patch-side guard the note keeps between its ink and the patch block, as a
#: distance on paper. Mirrors ``tiff_metadata._PATCH_SAFETY_PAD_MM``; it is
#: repeated as a number rather than imported because importing `tiff_metadata`
#: drags in `numpy` and `tifffile`, and this module is asked its question from a
#: Qt panel on every keystroke.
SAFETY_PAD_MM = 0.34

#: Narrowest note strip that still renders a legible line: the 2 px white gap
#: Knut asked for between the note and the patch block, plus one line at the 9 px
#: legibility floor. Measured, not guessed: DejaVuSans at 9 px renders a note
#: with descenders 9 px across (10 px also gives 9, 12 gives 12, 15 gives 14,
#: 28 gives 27). `workflow/tiff_metadata.py` imports this and never keeps its
#: own copy, so what the panel warns about and what the stamper does cannot
#: drift apart.
NOTE_PATCH_GAP_PX = 2
NOTE_MIN_STRIP_PX = NOTE_PATCH_GAP_PX + 9

#: THE SAME FLOOR AS A DISTANCE ON PAPER, WHICH IS WHAT IT ALWAYS MEANT.
#: The measurement above was taken at 200 dpi, where 11 px is 1.397 mm, and
#: "legible" is a property of ink on paper rather than of a raster. Left as a
#: pixel count it shrank as the resolution rose: a challenge round built the
#: same card at 200, 300 and 600 dpi and found the panel warning at 200 and
#: printing a cheerful "Margins: OK" at 600, where the note was a quarter of the
#: width on the same sheet. A user who saw the red line and raised the
#: resolution to "fix" it silenced the warning and made the note less readable.
NOTE_MIN_STRIP_MM = round(NOTE_MIN_STRIP_PX * 25.4 / 200.0, 3)   # 1.397 mm


def note_min_strip_px(dpi: float) -> int:
    """The floor in pixels at *dpi*, derived from the paper floor.

    More pixels at a finer raster, because it is the same paper.
    """
    try:
        d = float(dpi)
        if d <= 0:
            raise ValueError
    except (TypeError, ValueError):
        d = 300.0
    return max(1, int(round(NOTE_MIN_STRIP_MM * d / 25.4)))

#: Height of one line of bottom-of-sheet text, in mm. The renderer's own
#: ``line_h = px(4.2)`` (`workflow/layout_engine/raster.py`).
SHEET_TEXT_LINE_MM = 4.2


def note_min_width_mm(_dpi: float = 0.0) -> float:
    """The narrowest strip that still renders a legible line, on PAPER.

    THIS USED TO DEPEND ON THE RESOLUTION AND ITS OWN DOCSTRING SAID SO:
    "a pixel floor is not a paper floor: the same sheet gives the note 1.40 mm
    at 200 dpi and 0.47 mm at 600". It noticed the fault and then returned the
    pixel floor anyway, so the warning followed the raster instead of the sheet.
    The argument is kept so every caller keeps working and is deliberately
    ignored.
    """
    return NOTE_MIN_STRIP_MM


@dataclass(frozen=True)
class Overlap:
    """One side's text and the patch area want the same paper.

    *side* is "top" / "right" / "bottom" / "left" — the page edge, not the
    reading direction. *available_mm* is the paper the text has between the
    distance-from-edge reserve and the patch area (negative when the reserve
    itself is already inside the patch area); *needed_mm* is what the text
    takes. *overlap_mm* is the difference, and is always positive here.
    """

    side: str
    available_mm: float
    needed_mm: float

    @property
    def overlap_mm(self) -> float:
        return self.needed_mm - self.available_mm


def _overlap(side: str, available_mm: float, needed_mm: float) -> "Overlap | None":
    if needed_mm <= 0.0:
        return None
    if available_mm + EPS_MM >= needed_mm:
        return None
    return Overlap(side, float(available_mm), float(needed_mm))


@dataclass(frozen=True)
class Squeeze:
    """The strip letters could not keep the distance the user asked for.

    They do NOT run into the patches, and this type exists because a message
    saying they do was shipped and was false in every state in which it fired.

    *asked_mm* is the distance from the page edge the setting asks for,
    *actual_mm* is where the renderer puts them instead, *band_mm* is how tall
    they are, and *margin_mm* is the top margin. ``off_the_sheet`` is the worse
    case: the band is taller than the whole margin, so anchoring its bottom at
    the patch area would start it above the paper and it is clamped at the
    edge, losing the top of every letter.
    """

    asked_mm: float
    actual_mm: float
    band_mm: float
    margin_mm: float

    @property
    def short_mm(self) -> float:
        """How much more top margin would let the setting be kept."""
        return max(0.0, self.band_mm + self.asked_mm - self.margin_mm)

    @property
    def off_the_sheet(self) -> bool:
        return self.band_mm > self.margin_mm + EPS_MM


def strip_label_squeeze(margin_top_mm: float, text_edge_top_mm: float,
                        band_mm: float, label_offset_mm: float = 0.0,
                        ) -> "Squeeze | None":
    """What the strip letters actually do when the top margin is tight.

    THEY NEVER MOVE DOWN INTO THE PATCHES, and the first version of this law
    said they did. It computed `margin_top - reserve` against the band and
    called the shortfall an overlap, which is the arithmetic the right edge
    needs and the wrong question for this one. A challenge round measured five
    sheets: at every top margin from 1 mm to 8 mm the letters were printed
    ABOVE the patch block with clear paper between, and the message said they
    ran into it. The remedy it offered, lowering "T", silenced the warning
    without moving a single pixel.

    What the renderer does is at `workflow/layout_engine/geometry.py`, and it
    says so in its own comment: the label's BOTTOM is anchored at the top of
    the patch area, so when the margin is too small the label slides UP toward
    the page edge, clamped there.

        _leader_top = max(0.0, min(text_edge_top + gap, margin_t - band))

    So the thing to report is not an overlap. It is that the distance from the
    paper edge the user asked for is not the distance they get, which is what
    the app's own help for "Show strip letters" has always said would happen.
    """
    asked = float(text_edge_top_mm or 0.0) + max(0.0, float(label_offset_mm or 0.0))
    band = float(band_mm or 0.0)
    margin = float(margin_top_mm or 0.0)
    if band <= 0.0:
        return None
    actual = max(0.0, min(asked, margin - band))
    if actual + EPS_MM >= asked:
        return None
    return Squeeze(asked, actual, band, margin)


def sheet_text_overlap(margin_bottom_mm: float, text_edge_mm: float,
                       lines: int) -> "Overlap | None":
    """The sheet text along the bottom against the bottom margin.

    *lines* counts the custom sheet text and the settings stamp separately,
    because the renderer draws one line for each.
    """
    n = max(0, int(lines or 0))
    return _overlap("bottom",
                    float(margin_bottom_mm or 0.0) - float(text_edge_mm or 0.0),
                    n * SHEET_TEXT_LINE_MM)


def chart_note_overlap(side: str, margin_mm: float, text_edge_clip_mm: float,
                       dpi: float, clip_band_mm: float = 0.0,
                       ) -> "Overlap | None":
    """The run chart notes / stamped settings down the side margin.

    The note is stamped onto a finished raster, so it can move nothing: it is
    anchored at *text_edge_clip_mm* from the paper edge and grows inward. When
    a clip border sits on the same edge the note keeps off it too, so
    *clip_band_mm* comes out of the paper available to it.
    """
    avail = (float(margin_mm or 0.0) - float(text_edge_clip_mm or 0.0)
             - float(clip_band_mm or 0.0) - SAFETY_PAD_MM)
    return _overlap(side, avail, note_min_width_mm(dpi))


def clip_content_overlap(side: str, margin_mm: float, clip_zone_mm: float,
                         text_edge_clip_mm: float = 0.0) -> "Overlap | None":
    """The clip border's content against the margin on its own edge.

    The band runs from *text_edge_clip_mm* in from the page edge out to
    *clip_zone_mm*, which is where the first patch column is meant to begin;
    the patch area starts at *margin_mm*. `workflow/layout_engine/instruments.py`
    raises that margin to the clip zone, so on every chart the app builds today
    the two are equal and this returns None. It is asked anyway, because a
    geometry that stops raising it is exactly the day the user needs to be told.
    """
    inset = max(0.0, float(text_edge_clip_mm or 0.0))
    return _overlap(side, float(margin_mm or 0.0) - inset,
                    max(0.0, float(clip_zone_mm or 0.0) - inset))
