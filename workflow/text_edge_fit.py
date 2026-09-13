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

#: The gap as a distance on PAPER, which is what it always meant: the 2 px
#: above were measured at 200 dpi.
NOTE_PATCH_GAP_MM = round(NOTE_PATCH_GAP_PX * 25.4 / 200.0, 3)   # 0.254 mm

#: **SHRINKING HAS A FLOOR, AND IT IS 7 POINT.** Knut, 2026-09-11, after
#: running his own two-run `test` project against the 8 pt floor that shipped
#: that morning: *"Run 2 has a right side Chart Text, set in Sheet Text frame
#: as size 7. (The auto setting shrunk the text to size 8, but that cause the
#: long text to overflow the height of the page, so I changed to size 7). This
#: showed me that the threshold of 8pt font size as the limit for when
#: shrinking stops, when size is set to Auto, is too high. Please set the
#: stop-shrinking threshold to 7, applicable for all the places font size is
#: set and has Auto as a choice."*
#:
#: Measured on that run's own sheet, driven on screen: his 147-character note
#: on a 130 x 180 mm card takes 1530 px of line at 8 pt against the 1347 px the
#: sheet has for it, so its tail was cut; at 7 pt it takes 1269 px and the
#: whole sentence is printed. One point of type is the difference between his
#: colour-management instruction being on the paper and not.
#:
#: He asked for it *"at 8pt"* the day before, on a different fault, and this
#: supersedes that: it is the same constant, moved once, and everything that
#: shrinks automatically reads it from here.
#:
#: The 9 px legibility floor the 8 pt one replaced was a floor on the RASTER,
#: not on paper: 9 px is 3.24 pt at 200 dpi and 1.08 pt at 600. Measured on
#: Knut's `testHex` project at his own numbers, the note printed 2.29 mm of ink
#: across the sheet, which is 6.5 pt of line including its gap. It fits, so
#: nothing warned.
#:
#: **The floor applies only to AUTOMATIC shrinking.** His rule, 2026-09-11:
#: *"It makes sense that only the Auto size setting allows automatic shrinking
#: of the text."* A size the user typed is used exactly as typed, 6 pt
#: included, and the warning takes the place of the shrink.
AUTO_SHRINK_FLOOR_PT = 7.0


def pt_to_mm(size_pt: float) -> float:
    """Points (1/72 inch) to millimetres."""
    return float(size_pt or 0.0) * 25.4 / 72.0


def pt_to_px(size_pt: float, dpi: float) -> int:
    """Points to whole pixels at *dpi*, never less than one."""
    try:
        d = float(dpi)
        if d <= 0:
            raise ValueError
    except (TypeError, ValueError):
        d = 300.0
    return max(1, int(round(float(size_pt or 0.0) * d / 72.0)))


def px_to_pt(size_px: float, dpi: float) -> float:
    """Pixels at *dpi* back to points."""
    try:
        d = float(dpi)
        if d <= 0:
            raise ValueError
    except (TypeError, ValueError):
        d = 300.0
    return float(size_px or 0.0) * 72.0 / d


def text_floor_pt(size_pt: float = 0.0) -> float:
    """The smallest line this text may be drawn at, in points.

    A typed size is its own floor (nothing shrinks it, and a size below the
    floor is honoured); "auto" — 0, which is what the Size spin box's *auto*
    special value stores — stops at :data:`AUTO_SHRINK_FLOOR_PT`.
    """
    try:
        s = float(size_pt or 0.0)
    except (TypeError, ValueError):
        s = 0.0
    return s if s > 0 else AUTO_SHRINK_FLOOR_PT


def note_min_strip_px(dpi: float, size_pt: float = 0.0) -> int:
    """The floor in pixels at *dpi*, derived from the paper floor.

    More pixels at a finer raster, because it is the same paper.
    """
    try:
        d = float(dpi)
        if d <= 0:
            raise ValueError
    except (TypeError, ValueError):
        d = 300.0
    return max(1, int(round(note_min_width_mm(d, size_pt) * d / 25.4)))

#: Line PITCH of the bottom-of-sheet text, in mm. The renderer's own
#: ``line_h`` floor (`workflow/layout_engine/raster.py`).
SHEET_TEXT_LINE_MM = 4.2

#: The size the Sheet text frame's "auto" prints the BOTTOM line at. It does
#: not shrink and it does not grow: `raster.render_page` reads
#: ``px(chart_text_size_mm or 3.2)``, so "auto" here means this number and not
#: :data:`AUTO_SHRINK_FLOOR_PT`, which is the floor of the two boxes that DO
#: shrink (the side note and the clip band).
SHEET_TEXT_DEFAULT_MM = 3.2


def note_min_width_mm(_dpi: float = 0.0, size_pt: float = 0.0) -> float:
    """The narrowest strip the chart note may be printed into, on PAPER.

    One line at its floor (:data:`AUTO_SHRINK_FLOOR_PT` when the Sheet text
    frame's Size is "auto", otherwise the size that was typed), plus the white
    gap Knut asked for between the note and the patch block.

    THIS USED TO DEPEND ON THE RESOLUTION AND ITS OWN DOCSTRING SAID SO:
    "a pixel floor is not a paper floor: the same sheet gives the note 1.40 mm
    at 200 dpi and 0.47 mm at 600". It noticed the fault and then returned the
    pixel floor anyway, so the warning followed the raster instead of the sheet.
    The *dpi* argument is kept so every caller keeps working and is
    deliberately ignored.
    """
    return round(pt_to_mm(text_floor_pt(size_pt)) + NOTE_PATCH_GAP_MM, 3)


#: What the module used to call the floor, kept for the one thing it still
#: means: the narrowest strip anything is ever drawn into.
NOTE_MIN_STRIP_MM = note_min_width_mm()
NOTE_MIN_STRIP_PX = NOTE_PATCH_GAP_PX + int(round(AUTO_SHRINK_FLOOR_PT * 200.0 / 72.0))


# ---------------------------------------------------------------------------
# THE RULER HELPER MARKERS ARE A SECOND RESERVE, AND THE TEXT KEEPS OFF BOTH.
# ---------------------------------------------------------------------------
#: The clear millimetre Knut puts between a helper marker's inner tip and the
#: nearest text, on every edge that carries markers. #182, 2026-09-12:
#:
#:     *"IF "Print helper markers" and "Sides" checkboxes are both ON, under
#:     "Ruler helper markers" frame: "Distance from page edge" + "Marker
#:     length" + 1.0mm."*
#:
#: He writes the same sum four times, once per edge, and his own worked A4
#: example (4.0 + 2.0 + 1.0 = 7.0 mm) is the arithmetic below. The width and
#: height allowances in the same post are the same number doubled: his
#: ``"Distance from page edge" x2 + "Marker length" x2 + 2.0mm`` is
#: ``2 * (edge + length + 1.0)``, so there is one constant here and not two.


def helper_marker_reserve_mm(markers_on: bool, edge_mm: float,
                             length_mm: float,
                             this_edge_marked: bool = True) -> float:
    """How far in from a page edge that carries markers the text must start.

    0 when the markers are off, or when this edge is not one of the two sets
    the "Top/bottom" and "Sides" checkboxes switch on: the reserve exists
    because a dash is drawn there, so an edge with no dash on it costs nothing.

    **THIS IS A DIFFERENT QUESTION FROM WHETHER OVERLAP IS ALLOWED, AND THE
    OLDER ANSWER WAS THE OTHER ONE.** `geometry.helper_marker_lines_mm` still
    records Knut's #152 ruling that *"overlapping is acceptable. User must
    adapt settings for the markers, margins and clip-border text etc. to look
    as desired."* That was about the MARKERS: a dash is never suppressed to
    protect something the user placed, because a hole in the rhythm is worse
    than a crossing. #182 changes the other half of it: the TEXT now gets out
    of the dashes' way by itself, so the two no longer collide in the ordinary
    case and the user is not asked to adapt anything. Nothing here suppresses a
    dash.
    """
    if not (markers_on and this_edge_marked):
        return 0.0
    # ONE COPY OF THE ARITHMETIC, AND ONE CONSTANT. This added the
    # distance, the length and a gap of its own, beside a second function
    # doing the identical sum with a second constant of the same value.
    # That is how the two came to share a name and break the merge. The
    # fact lives in one place; this function's whole job is the gate.
    return helper_marker_ink_reach_mm(edge_mm, length_mm)


def edge_reserve_mm(text_edge_mm: float, markers_on: bool = False,
                    marker_edge_mm: float = 0.0, marker_len_mm: float = 0.0,
                    this_edge_marked: bool = True) -> float:
    """The distance from ONE page edge that the text on it must respect.

    *"whichever go furthest in from the page edge"* (Knut, four times in the
    same post): the "Text distance from edge" box for this side, or the helper
    markers' own reserve, and it is a MAX and not a sum. His A4 example: with
    "Clip" at 4.0 mm and markers at 4.0 + 2.0, the answer is 7.0 mm.
    """
    return max(max(0.0, float(text_edge_mm or 0.0)),
               helper_marker_reserve_mm(markers_on, marker_edge_mm,
                                        marker_len_mm, this_edge_marked))


def strip_label_top_mm(text_edge_top_mm: float, label_offset_mm: float = 0.0,
                       markers_on: bool = False, marker_edge_mm: float = 0.0,
                       marker_len_mm: float = 0.0,
                       markers_top_bottom: bool = True) -> float:
    """Where the TOP side of the strip letters belongs, from the page's top.

    Knut, #182, 2026-09-12, "Top page edge":

        *"When helper markers OFF: The top-side of the strip labels should be
        placed the following distance from the page top edge: The defined "T"
        in "Text distance from edge" + "Label offset" under "Strip letters
        only" frame. When helper markers ON: […] or the defined "Distance from
        page edge" + "Marker length" + 1.0mm + "Label offset" […], whichever is
        largest of the two."*

    So the offset rides on TOP of whichever reserve wins; it is not one of the
    two candidates. A negative offset is honoured as typed, because it is the
    user asking for it, and it is the only way the letters ever come closer to
    the paper edge than the reserve.
    """
    return (edge_reserve_mm(text_edge_top_mm, markers_on, marker_edge_mm,
                            marker_len_mm, markers_top_bottom)
            + float(label_offset_mm or 0.0))


def sheet_text_bottom_mm(text_edge_mm: float, markers_on: bool = False,
                         marker_edge_mm: float = 0.0,
                         marker_len_mm: float = 0.0,
                         markers_top_bottom: bool = True) -> float:
    """Where the BOTTOM side of the sheet text belongs, from the page's bottom.

    Knut's "Bottom page edge" section, the same two-way rule as the top with no
    offset control on this edge. There is no "Label offset" for the sheet text,
    so this is the reserve alone.
    """
    return edge_reserve_mm(text_edge_mm, markers_on, marker_edge_mm,
                           marker_len_mm, markers_top_bottom)


def bottom_text_bounds_mm(paper_w_mm: float, text_edge_clip_mm: float,
                          markers_on: bool = False, marker_edge_mm: float = 0.0,
                          marker_len_mm: float = 0.0,
                          markers_sides: bool = True, *,
                          clip_border_mm: float = 0.0,
                          clip_side: str = "left") -> tuple[float, float]:
    """The two page-edge distances the bottom line is centred BETWEEN, in mm.

    Knut, #182, comment 5651269930 (an edit of 5649955254, and the edit is the
    one that counts: his first wording said only "centred according to page
    width" and he came back to give the case table). Returned as
    ``(left_mm, right_mm)`` measured from the LEFT page edge, so the centre of
    the line is ``(left + right) / 2``.

    His table, in his own units, for A4 Portrait::

        Helper markers off, Clip-border off:
            (0+Clip)                and (210 - Clip)
        Clip-border ON (side=left)  [also markers on when Clip is the larger]:
            (0+Clip-border width)   and (210 - Clip)
        Clip-border ON (side=right) [same proviso]:
            (0+Clip)                and (210 - Clip-border width)
        Markers on for sides, Clip smaller than the marker reserve, no border:
            (0+R)                   and (210 - R)
        Markers on for sides, border on the left, Clip smaller:
            (0+Clip-border width)   and (210 - R)
        Markers on for sides, border on the right, Clip smaller:
            (0+R)                   and (210 - Clip-border width)

    where ``R`` is *"Distance from page edge" + "Marker length" + 1.0mm*. Two
    rules cover all six rows, which is why they are written once here:

    * the side with NO clip border on it keeps ``max(Clip, R)``, which is
      :func:`edge_reserve_mm` and is what his "whichever is larger" proviso
      says in every row;
    * the side WITH the clip border keeps the border's own width, because the
      band and the line share this strip of paper: the band now runs from the
      "T" bound to the "B" bound (:func:`side_text_band_mm`), so it reaches
      down past the bottom line's own row and the line has to start clear of
      it.

    **ONE CLAUSE HE DID NOT TABULATE, AND IT IS RESOLVED CONSERVATIVELY.**
    Every row of his table has the border wider than the reserve, so the two
    readings agree; a border NARROWER than the reserve is a case he does not
    cover, and taking his words literally there would let the line into a
    reserve that is a limit on all four sides everywhere else in this module.
    The bound is therefore ``max(border, reserve)`` on the border's side, which
    is exactly his table wherever his table speaks. Reported for his ruling.
    """
    reserve = edge_reserve_mm(text_edge_clip_mm, markers_on, marker_edge_mm,
                              marker_len_mm, markers_sides)
    w = max(0.0, float(paper_w_mm or 0.0))
    border = max(0.0, float(clip_border_mm or 0.0))
    left = right_in = reserve
    if border > 0.0:
        if str(clip_side or "left").strip().lower() == "right":
            right_in = max(reserve, border)
        else:
            left = max(reserve, border)
    right = w - right_in
    if right < left:                      # a pathological sheet: no room at all
        left = right = w / 2.0
    return (left, right)


def bottom_text_room_mm(paper_w_mm: float, text_edge_clip_mm: float,
                        markers_on: bool = False, marker_edge_mm: float = 0.0,
                        marker_len_mm: float = 0.0,
                        markers_sides: bool = True, *,
                        clip_border_mm: float = 0.0,
                        clip_side: str = "left") -> float:
    """How wide the bottom-of-sheet text may be before it crosses a reserve.

    Knut's worked A4 example, from the "Bottom page edge" section:

        *"1. Helper markers ON: 210mm (A4) - ("Distance from page edge" x2 +
        "Marker length" x2 + 2.0mm) = 210 - (4x2 + 2x2 +2) = 210mm - 14mm =
        196mm. 2. Helper markers OFF: 210mm (A4) - "Clip"x2 = 210 - 4x2 =
        210mm - 8mm = 202mm."*

    Both are the paper less TWICE the side reserve, because the line runs from
    one side of the sheet to the other and each end has a reserve to keep off.
    Written that way there is one rule and the two cases are the two values
    :func:`edge_reserve_mm` can take. **His two examples are not a choice
    between the numbers: 196 is smaller than 202, and with the markers on both
    reserves apply**, so the wider of the two per side is the one that binds,
    exactly as it does on the other three edges.

    **AND THE CLIP BORDER IS THE THIRD THING THAT CAN BIND IT** (comment
    5651269930): the room is the distance between the two bounds the line is
    centred between, so a clip border on one side takes its width out of the
    line's room rather than the reserve. With no border described this is his
    two-reserve figure exactly, which is what every caller got before.
    """
    left, right = bottom_text_bounds_mm(paper_w_mm, text_edge_clip_mm,
                                        markers_on, marker_edge_mm,
                                        marker_len_mm, markers_sides,
                                        clip_border_mm=clip_border_mm,
                                        clip_side=clip_side)
    return max(0.0, right - left)


def bottom_text_overflow(paper_w_mm: float, text_edge_clip_mm: float,
                         needed_w_mm: float, markers_on: bool = False,
                         marker_edge_mm: float = 0.0,
                         marker_len_mm: float = 0.0,
                         markers_sides: bool = True, *,
                         clip_border_mm: float = 0.0,
                         clip_side: str = "left") -> "Overlap | None":
    """The bottom line's WIDTH against the paper it has, or None when it fits.

    The fourth side's version of the check the other three already make. Named
    an :class:`Overlap` on side ``"bottom"`` like the height one, because the
    panel reports both the same way and the remedy differs only in wording.

    *clip_border_mm* and *clip_side* describe a clip border, which bounds the
    line on its own side (comment 5651269930). Keyword-only, so every call
    written before it still asks the question it asked.
    """
    return _overlap("bottom",
                    bottom_text_room_mm(paper_w_mm, text_edge_clip_mm,
                                        markers_on, marker_edge_mm,
                                        marker_len_mm, markers_sides,
                                        clip_border_mm=clip_border_mm,
                                        clip_side=clip_side),
                    max(0.0, float(needed_w_mm or 0.0)))


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


@dataclass(frozen=True)
class LabelOverlap:
    """The strip letters and the patch area want the same paper at the top.

    *reserve_mm* is the distance from the page's top edge the letters' band
    starts at, *from_markers* says which of the two candidates won it (so the
    message can name the control that is actually binding), *offset_mm* is the
    user's "Label offset", *band_mm* how tall the band is and *margin_mm* the
    top margin.
    """

    reserve_mm: float
    from_markers: bool
    offset_mm: float
    band_mm: float
    margin_mm: float
    gap_mm: float = 0.0

    @property
    def reaches_mm(self) -> float:
        """How far down the page the letters' band ends."""
        return self.reserve_mm + self.gap_mm + self.offset_mm + self.band_mm

    @property
    def overlap_mm(self) -> float:
        return max(0.0, self.reaches_mm - self.margin_mm)


def strip_label_overlap(margin_top_mm: float, text_edge_top_mm: float,
                        band_mm: float, label_offset_mm: float = 0.0,
                        markers_on: bool = False, marker_edge_mm: float = 0.0,
                        marker_len_mm: float = 0.0,
                        markers_top_bottom: bool = True, *,
                        gap_mm: float = 0.0,
                        ) -> "LabelOverlap | None":
    """The strip letters against the patch area's top edge, or None if clear.

    Knut, #182, 2026-09-12, "Top page edge", names three ways this happens:

        *"1. If helper markers OFF: defined "T" … + "Label offset" … is so
        large that strip labels are placed overlapping with top margin. 2. If
        helper markers ON: a. … or b. … Whichever is the largest value of the
        two … 3. defined top margin is so small that patch area top edge
        overlaps with placed strip labels."*

    All three are the one inequality ``reserve + offset + band > top margin``,
    reached by moving a different term, so what a message can honestly do is
    name **which term is binding** and offer the lever for each. That is what
    *from_markers* is for: it separates his case 1 from his case 2, and case 3
    is the top margin, which the caller offers as the alternative remedy in
    both. Nothing here guesses which of the three the user "meant".

    **THE CLAMP IS GONE AND THIS IS NOW THE LIVE PREDICATE.** It was written,
    tested and parked for a day, because removing the clamp collided with an
    earlier ruling of his that came from a real printed sheet, and
    `CLAUDE.md` is explicit that a collision like that is his call. He made it
    in comment 5649810914: *"the strip labels do not cross the "Text distance
    from edge" value […] and then the text overlaps on top of the patch area
    top edge (according to top margin)."*

    What it costs is not a surprise to anyone. Measured on the SHIPPED CR30 A4
    default (top margin 6.0 mm, a 7.0 mm label band): the label band's bottom
    moves from 83 px to 130 px at 300 dpi while the first patch box starts at
    91 px, so every strip letter is printed over the first row of hexagons,
    14 px of ink where a roomy sheet draws 61. That is the sheet he ruled on,
    and this function is what puts the warning on the panel for it.

    **AND THE ARITHMETIC WAS SHORT BY ONE TERM WHILE IT WAS PARKED.** The
    renderer's band bottom is ``leader_top + label_ink_bottom_mm``, and
    `geometry.placement` builds ``leader_top`` as *reserve + the layout's own
    ``strip_indicator_gap``*. That gap was not in this sum, so on any recipe
    that sets one, this said the letters clear the patches by exactly the gap
    when they do not. *gap_mm* is keyword-only so the calls written against the
    parked signature still mean what they meant.
    """
    band = float(band_mm or 0.0)
    if band <= 0.0:
        return None
    reserve = edge_reserve_mm(text_edge_top_mm, markers_on, marker_edge_mm,
                              marker_len_mm, markers_top_bottom)
    marker_reserve = helper_marker_reserve_mm(markers_on, marker_edge_mm,
                                              marker_len_mm,
                                              markers_top_bottom)
    hit = LabelOverlap(reserve,
                       marker_reserve > float(text_edge_top_mm or 0.0),
                       float(label_offset_mm or 0.0), band,
                       float(margin_top_mm or 0.0),
                       max(0.0, float(gap_mm or 0.0)))
    return hit if hit.overlap_mm > EPS_MM else None


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
                       lines: int,
                       line_mm: float = SHEET_TEXT_LINE_MM) -> "Overlap | None":
    """The sheet text along the bottom against the bottom margin.

    *lines* counts the custom sheet text and the settings stamp separately,
    because the renderer draws one line for each.

    **4.2 mm IS A PITCH, NOT A TYPE HEIGHT, AND THIS USED TO BE THE ONLY
    NUMBER IT KNEW.** `raster.render_page` stacked the lines at a fixed
    ``px(4.2)`` whatever Size the Sheet text frame was set to, and anchored
    each line by its ASCENDER, so the ink went on down as far as the face
    takes it. Measured on screen, A4 at 200 dpi, bottom margin 12 mm with "B"
    at 4 mm and one line of sheet text, the ink's own distance from the bottom
    of the paper:

    | Size | ink to the paper edge | what the panel said |
    |---|---|---|
    | auto | 4.32 mm | nothing |
    | 12 pt | 3.17 mm | nothing |
    | 18 pt | 0.64 mm | nothing |
    | 28 pt | **0.00 mm, cut by the paper edge** | nothing |

    So the "B" reserve was crossed from about 12 pt up and the line fell off
    the sheet at 28, on a chart the panel called fine; and with the settings
    stamp switched on as well, the second line was printed on top of the
    first. *line_mm* is the line's real box now (`raster.sheet_text_line_mm`,
    the larger of the pitch and the face's own ascent plus descent), so the
    reserve is a limit on this edge as it is on the other three, the overflow
    goes inward over the patches where Knut's ruling of 2026-09-12 puts it,
    and this sentence's ``need`` is what the block really takes.
    """
    n = max(0, int(lines or 0))
    line = max(0.0, float(line_mm or 0.0)) or SHEET_TEXT_LINE_MM
    return _overlap("bottom",
                    float(margin_bottom_mm or 0.0) - float(text_edge_mm or 0.0),
                    n * line)


def chart_note_overlap(side: str, margin_mm: float, text_edge_clip_mm: float,
                       dpi: float, clip_band_mm: float = 0.0,
                       size_pt: float = 0.0) -> "Overlap | None":
    """The run chart notes / stamped settings down the side margin.

    The note is stamped onto a finished raster, so it can move nothing: it is
    anchored at *text_edge_clip_mm* from the paper edge and grows inward. When
    a clip border sits on the same edge the note keeps off it too, so
    *clip_band_mm* comes out of the paper available to it.

    *size_pt* is the Sheet text frame's Size: 0 for "auto" (the note may shrink
    to :data:`AUTO_SHRINK_FLOOR_PT` and no further), or the size the user typed
    (which nothing shrinks).

    **THE TWO RESERVES ARE ONE RESERVE, AND ADDING THEM UP WAS THE FAULT KNUT
    REPORTED ON 2026-09-11.** This read
    ``margin - text_edge_clip - clip_band - SAFETY_PAD``, so on his own sheet
    (right margin 32.0 mm, a 24.0 mm clip border on that edge, "Clip" 4.0 mm)
    it reported 3.6 mm of paper and warned, while the note needed 3.8. He
    measured his own TIFF and found the ink 4.95 mm to 7.49 mm in from the
    patch area's right edge, with white paper either side of it.

    Both numbers are right about their own question and only one of them is the
    question the warning asks:

    * *"how much paper is between the patch area and a reserve made of the clip
      band with another 'Text distance from edge' strip stacked on top of it"* —
      what the subtraction answered, about a strip that is not on the sheet;
    * *"how much paper is between the patch area and the nearest ink on the
      other side"* — what the sheet answers, and what the stamper computes:
      ``_right_limit = W - max(_pad, clip_band)`` in
      `workflow/tiff_metadata.py::_stamp_one`. A MAX, because the 4 mm the
      "Clip" box asks for lies INSIDE the band's own 24 mm; the band already
      keeps the note that far from the paper edge and further.

    Measured on the sheet the app itself wrote from his run 1 recipe at 200 dpi:
    the note's ink lands 25.15 mm to 27.56 mm in from the paper edge whichever
    of his two right margins is set, the patch block ends at 32.0 mm, and
    ``32.0 - max(4.0, 24.0) - 0.34`` is the 7.66 mm that are really there.
    """
    avail = (float(margin_mm or 0.0)
             - max(float(text_edge_clip_mm or 0.0), float(clip_band_mm or 0.0))
             - SAFETY_PAD_MM)
    return _overlap(side, avail, note_min_width_mm(dpi, size_pt))


#: Clear paper between a ruler helper marker's inner tip and any text on that
#: edge. Knut, #182, 2026-09-12: the text-box sits at *"'Distance from page
#: edge' + 'Marker length' + 1.0mm"* when the markers are on for that edge.
#: The clear paper Knut asks for between a marker's inner tip and any
#: text. There were briefly two constants of this value under two names.
HELPER_MARKER_TEXT_GAP_MM = 1.0

#: The renderer's own line spacing for clip text (`raster._vtext`: ``size *
#: 1.2``).
CLIP_LINE_SPACING = 1.2


def helper_marker_ink_reach_mm(marker_edge_mm: float,
                               marker_len_mm: float) -> float:
    """How far in from a page edge a helper marker's ink reaches, plus the gap.

    **TWO QUESTIONS, AND FOR ONE MERGE THEY SHARED A NAME.** The two halves of
    this round each wrote a `helper_marker_reserve_mm`, one taking the marker
    sizes and one taking the switches as well, in the same module. Python keeps
    the last definition, so every four-argument caller raised TypeError and
    twenty-two geometry tests failed on the merge while both halves were green
    alone. They are different questions and now have different names: this one
    is the unconditional GEOMETRIC FACT about where the ink reaches, and
    :func:`helper_marker_reserve_mm` is what a given edge must actually keep
    clear, which is zero when the markers are off or that edge carries none.

    ``"Distance from page edge" + "Marker length" + 1.0 mm`` (Knut, #182). The
    dashes start *marker_edge_mm* in from the paper and point inward for
    *marker_len_mm*, so their inner tip is the sum of the two; the last
    millimetre is the clear paper he asks for between that tip and any text.
    """
    return (max(0.0, float(marker_edge_mm or 0.0))
            + max(0.0, float(marker_len_mm or 0.0))
            + HELPER_MARKER_TEXT_GAP_MM)


def side_text_edge_mm(text_edge_clip_mm: float, *,
                      helper_markers: bool = False,
                      marker_edge_mm: float = 0.0,
                      marker_len_mm: float = 0.0,
                      marker_sides: bool = True) -> float:
    """How far in from the LEFT or RIGHT page edge that side's text-box starts.

    Knut's rule, #182, 2026-09-12, worded for both side edges at once:

        "The defined text-box-edge […] must be placed with its right
        text-box-edge against the right page edge, in a distance from the page
        edge defined by one of the following settings, whichever go furthest in
        from the page edge: 1. "Clip" in "Text distance from edge" parameter
        […] OR, 2. IF "Print helper markers" and "Sides" checkboxes are both
        ON […]: "Distance from page edge" + "Marker length" + 1.0mm."

    **THE HELPER MARKERS WERE NOT PART OF THIS CALCULATION AT ALL**, which is
    the collision he reports as a consequence of the change that aligned the
    text to the paper edge rather than to the patch area. Measured on his own
    "ColorMunki-A4-306p-1page-Portrait" preset, whose markers are ON at 4.0 mm
    with a 2.0 mm dash: the side dashes' ink runs from 4.01 mm to 6.0 mm in
    from the right page edge, and the clip-border text was placed at 4.13 mm,
    straight through them. This rule puts it at 7.0 mm instead.

    Both halves are consulted only when the markers are drawn on THIS pair of
    edges: *marker_sides* is the "Sides" checkbox, and with it off the dashes
    are not on the left or right edges at all, so they reserve nothing there.
    """
    base = max(0.0, float(text_edge_clip_mm or 0.0))
    if not (helper_markers and marker_sides):
        return base
    return max(base, helper_marker_ink_reach_mm(marker_edge_mm, marker_len_mm))


def page_text_height_mm(paper_h_mm: float, text_edge_top_mm: float,
                        text_edge_bottom_mm: float, *,
                        helper_markers: bool = False,
                        marker_edge_mm: float = 0.0,
                        marker_len_mm: float = 0.0,
                        marker_top_bottom: bool = True) -> float:
    """The height a side text-box is judged against, in mm. Knut, #182:

        "1. Page hight (defined by selected paper) minus T and minus B
        parameters in "Text distance from edge" […] OR, 2. IF "Print helper
        markers" and "Top/bottom" checkboxs are both ON […]: Page hight minus
        ("Distance from page edge" x 2 + "Marker length" x 2 + 2.0mm) […]
        whichever is smallest".

    His own worked example, which this reproduces exactly: A4 at T = B = 4.0
    gives 289 mm, and the markers at 4.0 + 2.0 give 297 - 14 = 283 mm, so 283
    is the height to judge against.
    """
    return side_text_band_mm(
        paper_h_mm, text_edge_top_mm, text_edge_bottom_mm,
        helper_markers=helper_markers, marker_edge_mm=marker_edge_mm,
        marker_len_mm=marker_len_mm, marker_top_bottom=marker_top_bottom)[1]


def side_text_band_mm(paper_h_mm: float, text_edge_top_mm: float,
                      text_edge_bottom_mm: float, *,
                      helper_markers: bool = False,
                      marker_edge_mm: float = 0.0,
                      marker_len_mm: float = 0.0,
                      marker_top_bottom: bool = True) -> tuple[float, float]:
    """``(top_mm, height_mm)`` of the band a side text is centred in.

    Knut, #182, comment 5649955254, giving the bounds one case at a time for an
    A4 sheet at T = 12 and B = 4::

        helper markers off:
            (0+T)  and  (297 - B)
        helper markers on for top/bottom:
            T smaller than the marker reserve:  (0+R)  and  (297 - B)
            B smaller:                          (0+T)  and  (297 - R)
            both smaller:                       (0+R)  and  (297 - R)

    where ``R`` is *"Distance from page edge" + "Marker length" + 1.0mm*. All
    four rows are ONE rule per edge: the bound is ``max(that edge's box, R)``,
    which is :func:`edge_reserve_mm`, the same function the other elements on
    the same edges already use. He asks for the band to be *"vertically
    centred"* between them, and a band that spans them exactly is centred in
    them, so the rectangle is returned rather than a rule for sliding a shorter
    one about.

    **THIS CORRECTS THE HEIGHT AS WELL AS THE PLACEMENT, AND THE CORRECTION IS
    HIS.** The rule this replaces came from his earlier post and read *"page
    height minus T and minus B, OR page height minus (distance x2 + length x2 +
    2.0mm), whichever is smallest"* -- one symmetric figure for both ends. That
    is right whenever T and B fall on the same side of R, and wrong in the two
    mixed rows he has now written out. On his own example, A4 at T = 12, B = 4
    with the markers at 4.0 + 2.0 (R = 7.0), the old rule gives
    ``min(281, 283) = 281`` mm starting 8.0 mm down; his rows give 12.0 mm down
    to 290.0 mm, a 278.0 mm band. Three millimetres and a different anchor, and
    the anchor is the half that showed: the band was symmetric about the middle
    of the sheet whatever T and B said.

    ``height_mm`` is floored at zero, and the top bound is pulled back with it
    on a sheet whose two reserves overlap, so the rectangle is never inverted.
    """
    h = max(0.0, float(paper_h_mm or 0.0))
    top = edge_reserve_mm(text_edge_top_mm, helper_markers, marker_edge_mm,
                          marker_len_mm, marker_top_bottom)
    bot = edge_reserve_mm(text_edge_bottom_mm, helper_markers, marker_edge_mm,
                          marker_len_mm, marker_top_bottom)
    if top + bot >= h:                    # a pathological pair on a small sheet
        return (min(top, h) if h > 0 else 0.0, 0.0)
    return (top, h - top - bot)


def geom_side_text_edge_mm(geom) -> float:
    """:func:`side_text_edge_mm` for a built :class:`Geom`.

    The geometry carries the helper-marker settings (`instruments.Geom`) so
    that every place which already has a geometry, and there are several,
    asks this one question rather than re-assembling the four fields and
    drifting apart. Duck-typed on purpose: this module is imported BY the
    layout engine and must not import it back.
    """
    return side_text_edge_mm(
        float(getattr(geom, "text_edge_clip_mm", 0.0) or 0.0),
        helper_markers=bool(getattr(geom, "helper_markers", False)),
        marker_edge_mm=float(getattr(geom, "helper_marker_edge_mm", 0.0) or 0.0),
        marker_len_mm=float(getattr(geom, "helper_marker_len_mm", 0.0) or 0.0),
        marker_sides=bool(getattr(geom, "helper_markers_sides", True)),
    )


def clip_text_needed_mm(lines: int, size_pt: float = 0.0) -> float:
    """What *lines* of clip-border text take ACROSS the band, at their floor."""
    n = max(0, int(lines or 0))
    if n <= 0:
        return 0.0
    return n * CLIP_LINE_SPACING * pt_to_mm(text_floor_pt(size_pt))


def clip_content_inset_mm(band_mm: float, text_edge_clip_mm: float) -> float:
    """How far in from the PAGE EDGE the clip content starts, and it is a LIMIT.

    It is applied to the page-edge side ONLY: the band's inner edge is where
    the first patch column begins and needs no reserve of its own.

    **"CLIP" USED TO BE CAPPED AT A FIFTH OF THE BAND, AND THAT CAP IS THE
    FAULT KNUT REPORTED ON 2026-09-12.** It read
    ``min(text_edge_clip, band * 0.2)``, so on the
    "ColorMunki-A4-306p-1page-Portrait" preset, whose band is 24.0 mm, the
    reserve stopped growing at 4.8 mm and every "Clip" above 5 mm was
    discarded:

        "Changing from 4 to 5mm moves the text 1 mm more away from the right
        border, but any higher settings than 5.0mm does not move the text at
        all, even though there is free space between the patch area right side
        and the clip-border text."

    Measured in ink on the rendered sheet before the change, with the markers
    off so the ink measured is the text: Clip 4.0 put it 4.13 mm from the
    paper's right edge, Clip 5.0 put it at 4.90, and 5.5, 6, 7, 8, 10 and 15
    all put it at 4.90 as well. His "1 mm" is the 0.77 mm step from 4.13 to
    4.90 and the cap is the wall after it.

    The cap existed so a narrow band would not be eaten whole by a large
    "Clip", but that is no longer a thing to protect against: text which does
    not fit inside the reserve keeps the reserve and grows INWARD over the
    patch area, with a warning (:func:`clip_text_overhang_mm`, Knut's ruling of
    the same day). So the reserve is simply what was asked for.

    *band_mm* is kept in the signature although it no longer decides anything,
    because every caller has it and passing it says which band this reserve
    belongs to. `tests/test_the_sheet_text_fits_the_sheet.py` pins the
    signature for a different reason, below.

    THE FIRST VERSION OF THIS TOOK IT OFF BOTH SIDES AND USED THE TYPED VALUE.
    On Knut's 16 mm band with Clip at 4 mm that predicted 8.0 mm of room where
    the renderer gives 12.8, so the warning fired about 4.8 mm that exist. A
    prediction is only worth something while it reads its numbers from the same
    place as the thing it predicts.

    **AND FOR ONE EVENING THIS SURRENDERED THE RESERVE TO TEXT THAT WOULD NOT
    FIT. It does not, and it never should have.** The question put to Knut on
    2026-09-11 was worded so that he read it as being about something else, and
    he corrected it the next morning:

        "I was confused about the question, when you already know the
        text-edge distance is a limit on every side. The text on each of the 4
        sides shall NOT cross the text-edge distance limit on every side. If
        the patch area with its margins are pushing against these limits, the
        text shall overlap in the other direction, inward and over the edges
        of the patch area instead. When this happens the warning texts shall
        appear, informing the user, as described and defined earlier."

    So rule 1 of section 2c of `docs/design/issue_182_answers.md` was never
    wrong, and the direction of the overflow is what was in question:
    :func:`clip_text_overhang_mm` is where it goes instead.
    """
    return max(0.0, float(text_edge_clip_mm or 0.0))


def clip_text_overhang_mm(band_mm: float, text_edge_clip_mm: float, lines: int,
                          size_pt: float = 0.0) -> float:
    """How far the clip text reaches INWARD, past the band and over the patches.

    0 when it fits the band inside the page-edge reserve, which is the ordinary
    case. Otherwise it is the shortfall exactly: the text keeps the distance
    from the paper edge that "Clip" asks for, stops shrinking at
    :data:`AUTO_SHRINK_FLOOR_PT`, and what will not fit goes over the patch
    area, where the panel says so in red (Knut, 2026-09-12).

    **This is where the text used to be CUT.** `raster._vtext` draws into a
    canvas the width of the band's content rectangle and stacks the lines from
    one end at their natural spacing, so a block taller than that rectangle
    simply had its last lines fall outside the canvas and vanish. Measured on
    Knut's own run 1 at a 12 mm band: four lines need 11.9 mm, the rectangle
    gave them 9.6, and the fourth line was not printed anywhere, with nothing
    in the log and nothing on screen.
    """
    needed = clip_text_needed_mm(lines, size_pt)
    if needed <= 0.0:
        return 0.0
    room = max(0.0, float(band_mm or 0.0)
               - clip_content_inset_mm(band_mm, text_edge_clip_mm))
    return max(0.0, needed - room)


def clip_text_reach_mm(band_mm: float, text_edge_clip_mm: float, lines: int,
                       size_pt: float = 0.0) -> float:
    """How far in from the PAGE EDGE the clip band's text ends up, in mm.

    It starts at the page-edge reserve, which is a limit
    (:func:`clip_content_inset_mm`), and grows inward, so this is simply the
    reserve plus what the lines take. Equal to ``band + overhang`` by
    construction, and stated as its own function because what the text COLLIDES
    with is measured from the page edge too.
    """
    if int(lines or 0) <= 0:
        return 0.0
    return (clip_content_inset_mm(band_mm, text_edge_clip_mm)
            + clip_text_needed_mm(lines, size_pt))


@dataclass(frozen=True)
class ClipCollision:
    """What the clip band's text is printed on top of, and by how much.

    All four distances are measured from the page edge on the band's own side,
    which is the only frame in which they can be compared.

    *label_start_mm* is where the leftmost row-label ink begins, or ``None``
    when there are no row labels on this edge. *patch_start_mm* is the patch
    area's edge, which is the clip-side margin.
    """

    reach_mm: float
    label_start_mm: "float | None"
    patch_start_mm: float

    @property
    def over_labels_mm(self) -> float:
        if self.label_start_mm is None:
            return 0.0
        return max(0.0, self.reach_mm - float(self.label_start_mm))

    @property
    def over_patches_mm(self) -> float:
        return max(0.0, self.reach_mm - float(self.patch_start_mm))

    @property
    def hits_anything(self) -> bool:
        return (self.over_labels_mm > EPS_MM
                or self.over_patches_mm > EPS_MM)


def clip_text_collision(band_mm: float, text_edge_clip_mm: float, lines: int,
                        size_pt: float = 0.0,
                        label_start_mm: "float | None" = None,
                        patch_start_mm: float = 0.0) -> "ClipCollision":
    """What the clip band's text runs into on its way inward.

    **THE ROW LABELS ARE THE FIRST THING IT MEETS, NOT THE PATCHES.** Knut,
    #182, 2026-09-12, in the edited post:

        "If clip-border text starts overlapping with the row labels (if
        enabled), the warning shall occur too, because the row labels are left
        of the patch area edges and any clip-border text that does not have
        space enough to fit between the clip text-edge distance setting and the
        patch area left edge or the row labels to its left, will overflow and
        overlap towards the row label or the left edge of the patch area (left
        margin). This situation must be caught."

    Measured on his own run 2 through the real window: with the labels on, they
    begin ONE MILLIMETRE inside the clip band, because
    `raster.apply_row_label_geometry` floors them at the band's own width and
    `docs/design/row_label_geometry.md` §R2 then puts the band's 1 mm gap on
    the page-edge side of the number. So a 12 mm band whose text overhangs by
    2.25 mm crosses 1.25 mm of label while the patch area, at 20.25 mm, is
    still six millimetres away.

    Both distances are reported, because a deep overflow crosses the labels AND
    reaches the patches, and the two do different damage.
    """
    reach = clip_text_reach_mm(band_mm, text_edge_clip_mm, lines, size_pt)
    return ClipCollision(reach, label_start_mm, float(patch_start_mm or 0.0))


def clip_edge_that_clears_labels_mm(band_mm: float, needed_mm: float,
                                    label_offset_mm: float = 1.0,
                                    ) -> "float | None":
    """The LARGEST "Clip" that keeps the clip text off the row labels, or None.

    **RAISING "Clip" USED TO BE THE REMEDY HERE, AND AFTER THE CAP WAS REMOVED
    IT CANNOT BE.** The function this replaces answered "raise Clip to X and
    the labels move out of the way", which was true only because
    :func:`clip_content_inset_mm` capped the text's reserve at a fifth of the
    band while `raster.apply_row_label_geometry` floors the LABELS at
    ``max(band, Clip)`` uncapped. The text stopped moving at the cap and the
    labels kept going, so the gap opened. With the cap gone (Knut's fault
    report of 2026-09-12) both are anchored to the same line and move together
    one for one, so above the band's width raising "Clip" changes the gap by
    exactly nothing, and the old sentence would have been false on every chart.

    What is left is a ceiling, not a floor. The labels' leftmost ink is at
    ``max(band, clip) + offset`` and the text reaches ``clip + needed``, so
    they are clear while::

        clip <= band + offset - needed

    which is only reachable below the band's own width. None when even a
    "Clip" of zero cannot buy the room, and the caller must then name the band
    width or the text size instead, which are the levers Knut names.
    """
    band = max(0.0, float(band_mm or 0.0))
    needed = max(0.0, float(needed_mm or 0.0))
    offset = max(0.0, float(label_offset_mm or 0.0))
    out = band + offset - needed
    return out if out > 0.0 else None


def clip_band_needed_mm(text_edge_clip_mm: float, lines: int,
                        size_pt: float = 0.0) -> float:
    """The narrowest "Clip border width" that holds *lines* clear of the patches.

    The band holds the text once it is the reserve plus what the lines take,
    so this is simply ``needed + clip``.

    **IT USED TO BE A TWO-CASE ANSWER, AND THAT WAS THE CAP'S DOING.** While
    the page-edge reserve was capped at a fifth of the band, widening the band
    widened the reserve too and ate part of what had just been bought, so the
    honest answer was sometimes ``needed / (1 - frac)`` instead. The cap is
    gone (:func:`clip_content_inset_mm`, Knut's fault report of 2026-09-12),
    the reserve no longer moves when the band does, and one case is left.

    *text_edge_clip_mm* is the effective page-edge reserve, so a caller whose
    helper markers push it further in passes THAT (:func:`side_text_edge_mm`)
    and gets a band wide enough for where the text really starts.
    """
    needed = clip_text_needed_mm(lines, size_pt)
    if needed <= 0.0:
        return 0.0
    return needed + max(0.0, float(text_edge_clip_mm or 0.0))


def clip_text_squeeze(band_mm: float, text_edge_clip_mm: float, lines: int,
                      size_pt: float = 0.0, side: str = "left",
                      ) -> "Overlap | None":
    """The clip border's own TEXT against the band it is drawn in.

    Different question from :func:`clip_content_overlap`, which asks whether
    the BAND fits inside the margin. This one asks whether the LINES fit
    inside the band once the fitter has stopped shrinking them, which is what
    Knut reported on 2026-09-11: *"If I reduce the clip-border width to f.ex.
    16mm … then the clip border text is shrunk as normal. But here too there
    should be a font size minimum limit before the clip-border text stops
    shrinking."*

    **It is asked of the band INSIDE the page-edge reserve**, because that
    reserve is a limit and is not spent on text (Knut, 2026-09-12). So this
    fires exactly when :func:`clip_text_overhang_mm` is non-zero: the two are
    the same fact, one as a predicate and one as a distance, and the warning
    the panel raises names both.
    """
    n = max(0, int(lines or 0))
    if n <= 0:
        return None
    avail = (float(band_mm or 0.0)
             - clip_content_inset_mm(band_mm, text_edge_clip_mm))
    return _overlap(side, avail, clip_text_needed_mm(n, size_pt))


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
