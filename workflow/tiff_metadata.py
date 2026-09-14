"""Byte-safe stamping of caption text onto a chart TIFF.

Two entry points share the same TIFF re-write machinery:

- `stamp_chart_metadata()` — appends user notes / commands as a single rotated
  text line in the right margin (between Argyll's own vertical ID column and
  the page edge).
- `stamp_left_clip_info()` — fills the left clip strip (reserved by `printtarg`
  when `-L` is not set on an i1Pro / i1Pro 3+ chart) with two rotated text
  sub-columns: an outer column with chart context + archival form fields, and
  an inner column with i1Pro jig orientation instructions.

Color-integrity guarantees (apply to both stampers):
- Every pixel column outside the targeted band(s) is byte-identical
  before/after stamping. Argyll's existing text column and the patch area are
  never touched.
- Pixel dimensions, bit depth (uint8/uint16), photometric, compression, ICC
  profile tag, and XResolution/YResolution/ResolutionUnit are preserved.
- If a target band has no usable white run of at least _MIN_STRIP_WIDTH_PX,
  that stamper logs an info line and leaves the TIFF unchanged.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import tifffile
from PIL import Image, ImageDraw, ImageFont

from core.logger import get_logger
from workflow import text_edge_fit

log = get_logger(__name__)

# Per-column ink threshold (fraction of rows) above which a column belongs
# to the patch area, not the margin.
_PATCH_COL_DENSITY_THRESHOLD = 0.30
_PATCH_SAFETY_PAD_PX = 4
#: The same guard as a distance on PAPER, so a sheet behaves the same however
#: finely it is rastered. A pixel guard does not: measured on one physical A4
#: sheet, the two pads plus the legibility floor cost 3.21 mm of margin at
#: 150 dpi and 0.81 mm at 600, so the note printed at 300 dpi and was dropped at
#: 200 dpi, which is the resolution of the reporter's own files. 0.34 mm is what
#: the 4 px guard has always meant at 300 dpi, where the note prints today; the
#: 2 px floor keeps it a real guard on a coarse raster.
_PATCH_SAFETY_PAD_MM = 0.34


def _safety_pad_px(dpi: float) -> int:
    """The patch-side guard in pixels for a sheet at *dpi*."""
    try:
        return max(2, int(round(_PATCH_SAFETY_PAD_MM * float(dpi) / 25.4)))
    except (TypeError, ValueError, ZeroDivisionError):
        return _PATCH_SAFETY_PAD_PX
_MIN_STRIP_WIDTH_PX = 24
#: How much of a column may be inked and still count as somewhere the note can
#: go. A ruler dash covers a few percent of the height; a patch column or a clip
#: band covers most of it. Measured on real sheets: side-marker columns come out
#: at 0.02 to 0.08, a clip band at 0.9 and up, patches at 1.0.
_BAND_INK_TOLERANCE = 0.25
#: White gap left between the note's ink and the patch-block side of its strip.
#: Knut, 2026-09-10, asked for exactly this: *"should the text move closer to
#: the patch area edge but still leave 2 pixels space/gap, so that it is not
#: going towards the edge?"*
#: Narrowest strip the note is rendered into: `_NOTE_PATCH_GAP_PX` plus one line
#: at the 9 px legibility floor. Measured, not guessed -- DejaVuSans at 9 px
#: renders a note with descenders 9 px across (10 px also gives 9, 12 gives 12,
#: 15 gives 14, 28 gives 27).
#:
#: BOTH LIVE IN `workflow/text_edge_fit.py` AND ARE ONLY BORROWED HERE. The
#: "Measured from Preview" panel warns about an overlap this stamper is about to
#: draw, and it has to be able to say so while the user is still moving the spin
#: boxes -- long before any raster exists for the fact to travel up from. A
#: prediction only stays true while both sides read the same floor.
_NOTE_PATCH_GAP_PX = text_edge_fit.NOTE_PATCH_GAP_PX
#: The floor at the RASTER'S OWN RESOLUTION, from the paper floor the panel
#: warns about. A constant number of pixels was the same ink at 200 dpi and a
#: quarter of it at 600, so the two disagreed about the same sheet.
_MIN_NOTE_STRIP_PX = text_edge_fit.NOTE_MIN_STRIP_PX     # 200 dpi, for callers
# Gap between the three left-clip text sub-columns.
_LEFT_CLIP_GAP_PX = 8
# White padding on each side of the spectrum accent bar placed at the
# page-edge side of the outermost text column.
_SPECTRUM_BAR_PAD_PX = 6

# Joiner between concatenated metadata pieces in a single stamped line.
_JOIN = "    |    "

# Paper keys for which the left-clip info stamp is enabled. Smaller sheets are
# excluded because the rotated text becomes too cramped to be useful.
ALLOWED_LEFT_CLIP_PAPERS: frozenset[str] = frozenset({
    "A2", "594x420", "A3", "11x17", "Legal", "A4", "A4R", "Letter", "LetterR",
    "329x483", "420x297", "483x329", "custom",
})

# ChromIQ spectrum (matches ui.styles.TAB_COLORS). Drawn as a thin 5-segment
# vertical stripe between the text sub-columns of the left clip stamp — a
# small branded accent that doesn't interfere with text readability.
_SPECTRUM_COLORS_RGB: tuple[tuple[int, int, int], ...] = (
    (0xFF, 0x45, 0x73),  # magenta
    (0xFF, 0xB4, 0x2D),  # amber
    (0x56, 0xD6, 0xA5),  # green
    (0x37, 0xBC, 0xD6),  # cyan
    (0x9F, 0x82, 0xFF),  # violet
)
_SPECTRUM_BAR_WIDTH_PX = 6


def stamp_chart_metadata(
    tiff_paths: Iterable[Path],
    lines: Sequence[str],
    text_edge_mm: float = 0.0,
    clip_band_mm: float = 0.0,
    font_family: str = "",
    size_pt: float = 0.0,
    clip_reach_mm: float = -1.0,
    gap_mm: float = 0.0,
    text_edge_top_mm: float = -1.0,
    text_edge_bottom_mm: float = -1.0,
) -> None:
    """Stamp `lines` joined into a single rotated text line on each TIFF's right margin.

    *text_edge_mm* is the user's "Text distance from edge" setting. It was not
    passed at all, so the note started 0.5 mm from the paper edge whatever the
    box said. Zero keeps the old floor, which is what an unset value means.

    **THE NOTE HAS THREE EDGES, NOT ONE, AND ALL THREE READ THE SIDE BOX.**
    *text_edge_top_mm* and *text_edge_bottom_mm* are the reserves for the edges
    the note's two ENDS approach: "T", "B", or the ruler helper markers' own
    room on those edges, whichever goes furthest in. See :func:`_stamp_one`.
    Negative means "not supplied", and *text_edge_mm* is then used for all
    three, which is what every caller did before.

    *font_family* and *size_pt* are the **Sheet text frame's** Font and Size.
    Knut, 2026-09-11: *"The Sheet text frame Font and Size should be used for
    the Run Chart Notes text and the 'Stamp settings used on the chart'
    checkbox, so that the text is controllable."* A size of 0 is the box's
    "auto", which lets the line shrink to fit, down to
    :data:`text_edge_fit.AUTO_SHRINK_FLOOR_PT` and no further.

    *clip_reach_mm* is how far in from the page edge the clip border's OWN
    content text actually reaches, which is not the same as the band's width
    and is the distance this note has to keep off. Negative means "not
    supplied", and the band's width is used, which is what every caller did
    before #182. See :func:`_stamp_one` for why the difference matters.
    """
    pieces = [s.strip() for s in lines if s and s.strip()]
    if not pieces:
        return
    text = _JOIN.join(pieces)
    for path in tiff_paths:
        try:
            _stamp_one(Path(path), text, text_edge_mm, clip_band_mm,
                       font_family, size_pt, clip_reach_mm, gap_mm,
                       text_edge_top_mm, text_edge_bottom_mm)
        except Exception as exc:
            log.warning("Right-edge stamp failed for %s: %s", path, exc)


# Target width of the manufactured left clip strip, and the safety margin to
# keep between the rightmost patch and the page edge after the shift.
_LEFT_CLIP_TARGET_MM = 28.0
_RIGHT_SAFETY_MM = 3.0
# Minimum strip width worth stamping into; below this the shift is skipped.
_LEFT_CLIP_MIN_MM = 14.0


def shift_patches_for_chromiq_clip(
    tiff_paths: Iterable[Path],
    target_strip_mm: float = _LEFT_CLIP_TARGET_MM,
) -> None:
    """Shift the patch block right to open a ChromIQ left clip strip.

    Used with the ChromIQ-style clipping border feature: `printtarg` runs with
    `-L` (no native clip strip), packing patches near the left edge; this then
    shifts the whole image right so the total left white strip reaches
    `target_strip_mm` — BUT never far enough to push any patch off the page.
    Patch survival takes priority: if the right gap can't accommodate the full
    target, the strip is made narrower instead (capped at
    `right_gap − _RIGHT_SAFETY_MM`).

    Argyll's vertical ID text on the right is dropped (shifted off-page and/or
    blanked by the right-edge cleanup). All metadata tags are preserved via
    the shared `_capture_page_state` / `_write_preserving` helpers.
    """
    for path in tiff_paths:
        try:
            _shift_patches_one(Path(path), target_strip_mm)
        except Exception as exc:
            log.warning("Patch shift failed for %s: %s", path, exc)


def _shift_patches_one(path: Path, target_strip_mm: float) -> None:
    with tifffile.TiffFile(str(path)) as tf:
        page = tf.pages[0]
        state = _capture_page_state(page)
        arr = np.array(page.asarray(), copy=True)

    if arr.ndim != 3 or arr.shape[2] not in (1, 3, 4):
        log.warning("Patch shift: unexpected array shape %s for %s", arr.shape, path)
        return
    dtype = arr.dtype
    if dtype not in (np.uint8, np.uint16):
        log.warning("Patch shift: unsupported dtype %s for %s", dtype, path)
        return

    H, W = arr.shape[:2]
    dpi = _dpi_from_state(state)
    px_per_mm = dpi / 25.4
    max_val = np.iinfo(dtype).max

    # Locate the patch block by column ink density (low-density glyph columns
    # like Argyll's right-edge text are excluded by the threshold).
    ink_cutoff = int(max_val * 240 / 255)
    if arr.shape[2] == 1:
        ink_mask = arr[..., 0] < ink_cutoff
    else:
        ink_mask = (arr < ink_cutoff).any(axis=2)
    col_density = ink_mask.sum(axis=0) / max(1, H)
    patch_cols = np.where(col_density >= _PATCH_COL_DENSITY_THRESHOLD)[0]
    if len(patch_cols) == 0:
        log.info("Patch shift skipped (no patch block detected) for %s", path)
        return
    patch_left = int(patch_cols[0])
    patch_right = int(patch_cols[-1])

    # Shift to reach the target total strip width, but never far enough to push
    # the rightmost patch past (W − safety). Patch survival wins over strip width.
    target_px = int(round(target_strip_mm * px_per_mm))
    safety_px = int(round(_RIGHT_SAFETY_MM * px_per_mm))
    shift_needed = target_px - patch_left
    max_safe_shift = (W - patch_right) - safety_px
    shift_px = max(0, min(shift_needed, max_safe_shift))

    strip_mm = (patch_left + shift_px) / px_per_mm
    if shift_px <= 0 or strip_mm < _LEFT_CLIP_MIN_MM:
        log.info(
            "Patch shift skipped (no room: left margin %.1fmm, right gap %.1fmm, "
            "would-be strip %.1fmm) for %s",
            patch_left / px_per_mm, (W - patch_right) / px_per_mm, strip_mm, path,
        )
        return

    log.info(
        "Patch shift: %dpx (%.1fmm) → left strip %.1fmm; rightmost patch %d/%d for %s",
        shift_px, shift_px / px_per_mm, strip_mm, patch_right + shift_px, W, path,
    )

    shifted = np.full_like(arr, max_val)   # white background
    shifted[:, shift_px:, :] = arr[:, :-shift_px, :]

    # Right-edge cleanup: blank any content past the rightmost patch column
    # with white. Catches Argyll's vertical ID text the shift didn't fully
    # push off the page so the chart always ends with a clean right edge.
    if shifted.shape[2] == 1:
        ink_mask2 = shifted[..., 0] < ink_cutoff
    else:
        ink_mask2 = (shifted < ink_cutoff).any(axis=2)
    col_density2 = ink_mask2.sum(axis=0) / max(1, H)
    patch_cols2 = np.where(col_density2 >= _PATCH_COL_DENSITY_THRESHOLD)[0]
    if len(patch_cols2):
        blank_start = int(patch_cols2[-1]) + _PATCH_SAFETY_PAD_PX
        if blank_start < W:
            shifted[:, blank_start:, :] = max_val

    _write_preserving(path, shifted, state)


def _dpi_from_state(state: dict) -> float:
    """Return horizontal DPI from captured page state, defaulting to 300.

    Handles TIFF ResolutionUnit: 2 = inches (native dpi), 3 = centimeters
    (convert dots/cm → dots/inch by ×2.54), other values fall back to inches.
    """
    xres = state.get("xres_val")
    if not xres or xres[1] == 0:
        return 300.0
    dpi = xres[0] / xres[1]
    if state.get("runit_val") == 3:
        dpi *= 2.54
    return dpi


def stamp_left_clip_info(
    tiff_paths: Iterable[Path],
    outer_header_lines: Sequence[str],
    form_fields: Sequence[str],
    inner_lines: Sequence[str],
    command_lines: Sequence[str] | None = None,
) -> None:
    """Stamp the left clip strip with rotated text sub-columns.

    The detected left clip band is divided into equal-width sub-columns
    separated by `_LEFT_CLIP_GAP_PX` gaps, with a ChromIQ spectrum accent bar
    at the page-edge side. Columns, page-edge → patch-side:

      - Header: `outer_header_lines` joined with `_JOIN` (chart context +
        print reminder).
      - Commands: `command_lines` joined with `_JOIN` (targen / printtarg
        commands + chart notes) — only when supplied; this is the ChromIQ-
        style replacement for the right-margin command stamp.
      - Form: a fill-in-the-blank form line built from `form_fields` with
        underscore writing space sized to the paper.
      - Inner (patch side): `inner_lines` joined with `_JOIN` (jig
        orientation note).

    Empty inputs are skipped (their column simply isn't created); the
    remaining columns share the band evenly.
    """
    header_text = _JOIN.join(s.strip() for s in outer_header_lines if s and s.strip())
    inner_text = _JOIN.join(s.strip() for s in inner_lines if s and s.strip())
    command_text = _JOIN.join(s.strip() for s in (command_lines or []) if s and s.strip())
    form_fields_clean = [s.strip() for s in form_fields if s and s.strip()]
    if not (header_text or form_fields_clean or inner_text or command_text):
        return
    for path in tiff_paths:
        try:
            _stamp_left_clip_one(
                Path(path), header_text, command_text, form_fields_clean, inner_text
            )
        except Exception as exc:
            log.warning("Left-clip stamp failed for %s: %s", path, exc)


def _stamp_one(path: Path, text: str, text_edge_mm: float = 0.0,
               clip_band_mm: float = 0.0, font_family: str = "",
               size_pt: float = 0.0, clip_reach_mm: float = -1.0,
               gap_mm: float = 0.0, text_edge_top_mm: float = -1.0,
               text_edge_bottom_mm: float = -1.0) -> None:
    with tifffile.TiffFile(str(path)) as tf:
        page = tf.pages[0]
        # Device-native (separated) CMYK / CMYK+N charts: skip the post-render
        # ID stamp. It renders in RGB and rewriting would drop the InkNames /
        # InkSet / ExtraSamples tags (and invert the ink convention). The chart
        # identity is already baked into the raster's on-sheet stamp text, so
        # nothing is lost. (#72 Tier D)
        if int(page.photometric) == 5:                # SEPARATED
            log.debug("Right-edge stamp skipped for %s (separated device TIFF)", path)
            return
        state = _capture_page_state(page)
        arr = np.array(page.asarray(), copy=True)

    if arr.ndim != 3 or arr.shape[2] not in (1, 3, 4):
        log.warning("Right-edge stamp: unexpected array shape %s for %s", arr.shape, path)
        return

    dtype = arr.dtype
    if dtype not in (np.uint8, np.uint16):
        log.warning("Right-edge stamp: unsupported dtype %s for %s", dtype, path)
        return

    H, W, C = arr.shape
    _dpi = _dpi_from_state(state)
    # THE NOTE BELONGS BESIDE THE CLIP TEXT, NOT OUTSIDE THE WHOLE BAND. Knut,
    # #182, 2026-09-12:
    #
    #   "Currently, when Run's Chart Notes and/or "Stamp settings used on the
    #    chart" are used, the text is always placed outside (to the left of)
    #    the Clip-border width, even if that width is large enough to show free
    #    space between the patch area right margin and the defined
    #    "Clip-border content" Text. This is wrong, and the text must be placed
    #    as described above, to the left of the defined "Clip-border content"
    #    Text itself."
    #
    # Measured on his own "ColorMunki-A4-306p-1page-Portrait" preset before the
    # change: the band is 24.0 mm, its four lines of text reach only 18.99 mm
    # in from the paper's right edge, so 5.01 mm of the band is blank paper,
    # and the note was stamped at 24.20 mm to 26.36 mm, entirely outside the
    # band and hard against the patch block, with that 5 mm never used.
    #
    # So what the note keeps off is the clip content's REACH, and the band's
    # width is only the fallback for a caller that cannot measure the reach.
    _keep_out_mm = (float(clip_reach_mm) if clip_reach_mm is not None
                    and float(clip_reach_mm) >= 0.0
                    else float(clip_band_mm or 0.0))
    band = _detect_writable_band(
        arr, keep_out_px=int(round(_keep_out_mm * _dpi / 25.4)),
        pad_px=_safety_pad_px(_dpi))
    if band is None:
        # NO WHITE BAND IS NOT A REASON TO DROP THE NOTE EITHER. This was the
        # second silent drop on this edge, and the ruling covers both: an empty
        # band at the paper's right edge sends the note down the overlap path
        # below, which prints it at the distance the setting asks for and warns.
        log.info("Right-edge stamp: no usable right margin on %s, the note is "
                 "printed over the patch block instead", path)
        band_left = band_right = W
    else:
        band_left, band_right = band
    # THE USER'S OWN "TEXT DISTANCE FROM EDGE" DECIDES EVERY SIDE THE NOTE
    # TOUCHES, and it decided only two of them. It was turned into `_pad` and
    # applied to the TOP and the BOTTOM; horizontally nothing applied it, so the
    # note ran to `W - _PATCH_SAFETY_PAD_PX`, a 4 px constant which is 0.5 mm at
    # 200 dpi. Measured on Knut's own 130x180 sheet with the box reading 4.0 mm:
    # the note ended 1.98 mm from the paper edge. The pad stays as the floor,
    # because a note must never be pushed into the patch area, and it is what an
    # unset value falls back to.
    # NO FLOOR UNDER THE USER'S OWN NUMBER. Knut, 2026-09-10: *"there shall not
    # be any hard-coded values in the code"*. This read
    # `max(_PATCH_SAFETY_PAD_PX, …)`, so a 4 px constant, 0.5 mm at 200 dpi,
    # quietly won whenever the box asked for less. The setting decides; every
    # caller now supplies one, and a path with no control of its own passes the
    # SETTING'S DEFAULT rather than nothing (`chart_creator._stamp_tiff_metadata`).
    #
    # `_PATCH_SAFETY_PAD_PX` KEEPS ITS OTHER JOB, which is not this one.
    # `_detect_writable_band` uses it as an ink-detection tolerance: how much
    # white paper to require around the ink it finds. That is a different
    # measurement with a different meaning, and it is not a distance from an
    # edge, so the ruling does not reach it.
    _pad = int(round((text_edge_mm or 0.0) * _dpi / 25.4))
    # THE TWO ENDS OF THE NOTE ARE NOT ON THE EDGE THE SIDE BOX IS ABOUT, AND
    # THEY WERE MEASURED WITH IT ANYWAY. `_pad` is the reserve for the RIGHT
    # page edge, which is the edge the line's thickness runs into; its two ENDS
    # run into the TOP and the BOTTOM, whose reserves are "T", "B", and the
    # ruler helper markers' room on THOSE edges. Taking the side figure for all
    # three made the note the only text on the sheet whose vertical placement
    # is decided by a box about the other axis, and it put the note's ink
    # inside the top and bottom dash bands.
    #
    # Measured on screen at 200 dpi, an A4 ColorMunki sheet driven through the
    # real panel, the note isolated against a control sheet with it switched
    # off:
    #
    # * "T" and "B" moved it by NOTHING. At T = B = 4.0 and at T = B = 20.0 the
    #   same 10,917 pixels of note ink ran from 5.46 mm to 5.08 mm of the two
    #   ends, so at 20.0 the note crossed the reserve by 14.54 mm;
    # * with the markers ON, "Top/bottom" on and "Sides" OFF, the reserve fell
    #   back to "Clip" at 4.0 and the ink landed at 5.46 mm, INSIDE the 4.0 to
    #   6.0 mm dash band, 9 pixels of it in the top comb and 41 in the bottom.
    #   Turning "Sides" back on moved it to 8.00 mm, so a checkbox about the
    #   left and right dashes was what kept the note off the top ones;
    # * and on one A4 sheet at T 20 / B 4 with both marker sets on, the strip
    #   letters kept 20.0 mm, the bottom line kept 7.0 mm, the clip band's
    #   rectangle sat at 12.0 mm and the note kept 7.0 mm. Four elements, three
    #   answers, one page.
    #
    # `text_edge_fit.edge_reserve_mm` is the one function that answers this for
    # an edge, and the caller passes what it says. Negative means a caller that
    # does not know, and then the old behaviour stands rather than a guess.
    def _end_pad(v: float) -> int:
        if v is None or float(v) < 0.0:
            return _pad
        return int(round(max(0.0, float(v)) * _dpi / 25.4))
    _pad_t = _end_pad(text_edge_top_mm)
    _pad_b = _end_pad(text_edge_bottom_mm)
    if _pad_t + _pad_b >= H:                # a pathological setting on a tiny sheet
        _pad_t = _pad_b = 0
    if 2 * _pad >= H:
        _pad = 0
    strip_h = H - _pad_t - _pad_b
    if strip_h < 100:
        log.info("Right-edge stamp skipped (image too short) for %s", path)
        return

    # THE DISTANCE FROM THE PAGE EDGE IS A LIMIT, NOT A PREFERENCE, so nothing
    # is traded against it: no ink may land at or past `W - _pad`. Knut,
    # 2026-09-10, on the same rule for the labels: *"the text needs to stay
    # within the default 'Text distance from edge' settings … For all sides, for
    # Guided mode. Not a hardwired margin."*
    #
    # This is the LEFT edge's rule (`docs/design/row_label_geometry.md` R1.3,
    # "the labels can never be closer to the edge than the floor"), not the
    # top's, which gives the distance up when the margin is too small. The left
    # buys its guarantee by RAISING the margin; the note is stamped onto a
    # finished raster and can move nothing, so when the paper between the patch
    # block and the reserve is too thin for a legible line, the note is printed
    # ACROSS THE PATCH BLOCK rather than not printed at all -- see below.
    # `_LINE_GAP_PX` USED TO STAND HERE AND IS NOW PAID TWICE OVER. It pushed
    # the strip 6 px off the band's patch-side edge back when the renderer
    # CENTRED the line inside that strip; the gap the eye saw was that 6 px plus
    # half the strip's slack. The line is anchored now, so the gap is explicit
    # (`_NOTE_PATCH_GAP_PX`, on top of the 4 px safety pad `_detect_writable_
    # band` already adds), and keeping the old push as well would spend 0.5 mm
    # of a 6.1 mm margin on nothing. Measured on the stock i1/A4 sheet: it is
    # the difference between a 15 px note and a 9 px one.
    # THE USER'S OWN CLIP BAND IS STILL NOT A PLACE FOR THE NOTE, and this is
    # the one collision Knut's ruling does not settle. It sanctions the note
    # against the PATCH AREA -- *"even if the patch area overlaps on the right
    # Run Chart Notes text"* -- and says nothing about the note against the
    # user's own clip-border content, which is text they wrote. With a clip band
    # on this edge the two cannot both have the sliver at the paper's edge, so
    # the band keeps it (it is already the keep-out `_detect_writable_band` is
    # given) and the note moves INWARD, over the patches, where the ruling
    # allows it to go and where the panel then says so in red.
    _right_limit = W - max(_pad, int(round(_keep_out_mm * _dpi / 25.4)))
    strip_w = min(40, band_right - band_left, _right_limit - band_left)
    # ONE BOX, PACKED TOWARD THE PAGE EDGE. Knut's #182 text-box: everything on
    # this edge is one box whose RIGHT edge sits at the page-edge reserve, so
    # the note is anchored against the clip content's text (or the reserve when
    # there is no clip content) and grows inward from there, rather than being
    # left-anchored against the patch block with the freed paper stranded
    # between the two. *"The distance between "Run's Chart Notes" / "Stamp
    # settings used on the chart" and the text in "Clip-border content" Text
    # shall be equal to the normal distance between two lines of text for the
    # largest font size specified among the text fields that are part of the
    # text-box content."* -- that distance is `gap_mm`, computed by the caller
    # because only it knows both font sizes.
    #
    # **AND IT IS DONE ONLY WHERE THERE IS CLIP CONTENT TO PACK AGAINST,
    # BECAUSE THE TWO RULINGS CONFLICT AND THIS ONE IS NOT OURS TO SETTLE.**
    # Knut, 2026-09-10, on a chart with no clip band, asked for the opposite
    # arrangement by name: *"should the text move closer to the patch area edge
    # but still leave 2 pixels space/gap, so that it is not going towards the
    # edge?"* His #182 text-box rule reads the other way for that same chart:
    # the box's right edge goes at the page-edge reserve, which is where the
    # note sat when he objected. So the note packs against the clip content
    # when there IS clip content -- the case his fault report is about, and
    # where the freed paper is his whole point -- and a chart with none keeps
    # the placement he asked for. `clip_reach_mm` is supplied only when the
    # caller found clip text on this edge, so it is exactly that switch.
    # Reported for his ruling rather than decided here.
    _pack = (clip_reach_mm is not None and float(clip_reach_mm) >= 0.0)
    _gap_px = max(0, int(round(max(0.0, float(gap_mm or 0.0)) * _dpi / 25.4)))
    x0 = max(band_left, _right_limit - _gap_px - strip_w) if _pack else band_left
    strip_w = min(strip_w, _right_limit - x0)
    # TEXT ON ANY SIDE IS NEVER DROPPED. Knut's ruling, 2026-09-10, reversing
    # what 4.2.3 shipped:
    #
    #   "For the right margin, the text must still be visible, even if the
    #    patch area overlaps on the right Run Chart Notes text. Else the user
    #    will not notice that it is silently dropped, like you now do. The user
    #    must be given the chance to see that something is wrong, and then
    #    adjust the margins to place the patch area further in on the paper, so
    #    that the chart notes can be visible."
    #
    # 4.2.3 returned here, and it cost the 10 x 15 cm photo card its
    # identification line on every sheet: a 5.0 mm right margin less the 4.0 mm
    # reserve and the 0.34 mm patch guard leaves 0.66 mm, and a line at the
    # legibility floor needs 0.93 mm at 300 dpi. The user was told nothing they
    # could see. So the note now grows LEFT, over the patches if it must, while
    # the page-edge reserve stays exactly where it was -- that reserve is still
    # a limit, and it is the only thing here that is. The overlap is warned
    # about in red in the "Measured from Preview" frame
    # (`ui/tabs/tab_chart.py::_engine_text_overflow_warnings`), which is the
    # part of the ruling the user actually sees.
    _floor_px = text_edge_fit.note_min_strip_px(_dpi, size_pt)
    _overlaps = strip_w < _floor_px
    if _overlaps:
        strip_w = min(_floor_px, _right_limit)
        x0 = max(0, _right_limit - strip_w)
        if strip_w < 1:
            log.info(
                "Right-edge stamp skipped for %s: the %.1f mm "
                "text-distance-from-edge reserve leaves no paper at all.",
                path, _pad * 25.4 / _dpi)
            return
        log.info(
            "Right-edge stamp overlaps the patch block on %s: %.2f mm of paper "
            "between the patch block and the %.1f mm text-distance-from-edge "
            "reserve, and a legible line needs %.2f mm. The note is printed "
            "anyway. Widen the right margin or lower "
            "“Text distance from edge” → Clip.",
            path, max(0, _right_limit - band_left) * 25.4 / _dpi,
            _pad * 25.4 / _dpi, _floor_px * 25.4 / _dpi,
        )

    # SHRINK TO FIT, DO NOT CROP.
    #
    # This picked a font from the strip WIDTH alone and then centred the line,
    # so a note longer than the sheet lost its TAIL: `max(0, (strip_h - text_w)
    # // 2 - bbox[0])` clamps to zero and the end falls off the paper. Measured
    # on Knut's own 141-character note at 200 dpi: 4.2 mm lost on a 130x180
    # sheet and 34.2 mm on a 100x150 one, and what went missing was the end,
    # which is where he had put the colour-management setting. The fitting
    # renderer that does exactly this already lived in this file and was called
    # only by the left-clip stamp.
    #
    # ANCHOR THE LINE AGAINST THE PATCH SIDE, DO NOT CENTRE IT IN THE STRIP.
    # The strip was already anchored to the patch side of the band, but the
    # renderer centred the line INSIDE it, so a narrow line in a 40 px strip
    # kept about 1.4 mm of empty strip on each side. Measured on Knut's sheet:
    # a 3.05 mm gap on the patch side while the note lay against the paper
    # edge. He asked for the other arrangement by name -- *"should the text
    # move closer to the patch area edge but still leave 2 pixels space/gap,
    # so that it is not going towards the edge?"* -- and it is also what makes
    # the page-edge reserve above cheap: the blank part of the strip now falls
    # on the reserve's side, where it costs nothing.
    strip = _render_fitted_rotated_line(text, strip_h, strip_w, dtype, C,
                                        anchor_px=_NOTE_PATCH_GAP_PX,
                                        font_family=font_family,
                                        size_pt=size_pt, dpi=_dpi)
    # The strip itself stays anchored to the patch-side (left) edge of the
    # band. The band is the widest white column run right of the patches; when
    # the chart doesn't fill the sheet that run is a large empty area, so
    # centering would strand the text mid-void. Left-anchoring keeps it snug
    # against Argyll's vertical ID column / the patch block regardless of how
    # much blank space follows.
    # ...INSIDE THE WHITE BAND, unless the band is too narrow to hold a legible
    # line, in which case `x0` has deliberately been put left of it and these
    # two would put it straight back and drop the note again by another name.
    if not _overlaps:
        if x0 < band_left:
            x0 = band_left
        if x0 + strip_w > band_right:
            x0 = band_right - strip_w
    y0 = _pad_t
    # WRITE THE INK, NOT THE PAPER. This pasted an opaque white strip over the
    # whole band, AFTER the renderer had drawn the page, so every ruler dash the
    # band crossed was deleted. Measured against a control with the note off:
    # 100 pixels of existing dash removed on one sheet, 0 with the markers off.
    # Compositing keeps whatever was already there and only darkens.
    _under = arr[y0 : y0 + strip_h, x0 : x0 + strip_w, :]
    arr[y0 : y0 + strip_h, x0 : x0 + strip_w, :] = np.minimum(_under, strip)

    _write_preserving(path, arr, state)


def _stamp_left_clip_one(
    path: Path,
    header_text: str,
    command_text: str,
    form_fields: Sequence[str],
    inner_text: str,
) -> None:
    with tifffile.TiffFile(str(path)) as tf:
        page = tf.pages[0]
        if int(page.photometric) == 5:                # SEPARATED device TIFF (#72)
            log.debug("Left-clip stamp skipped for %s (separated device TIFF)", path)
            return
        state = _capture_page_state(page)
        arr = np.array(page.asarray(), copy=True)

    if arr.ndim != 3 or arr.shape[2] not in (1, 3, 4):
        log.warning("Left-clip stamp: unexpected array shape %s for %s", arr.shape, path)
        return

    dtype = arr.dtype
    if dtype not in (np.uint8, np.uint16):
        log.warning("Left-clip stamp: unsupported dtype %s for %s", dtype, path)
        return

    H, W, C = arr.shape
    band = _detect_writable_band(arr, side="left")
    if band is None:
        log.info("Left-clip stamp skipped (no usable left margin) for %s", path)
        return
    band_left, band_right = band
    band_w = band_right - band_left

    strip_h = H - 2 * _PATCH_SAFETY_PAD_PX
    if strip_h < 100:
        log.info("Left-clip stamp skipped (image too short) for %s", path)
        return

    # Build the ordered list of columns (page-edge → patch-side). Each entry is
    # (kind, content, weight): "text" for a joined rotated line, "form" for the
    # fill-in-the-blank line. The form column carries extra weight so it gets
    # more width for handwriting. Empty pieces are omitted.
    columns: list[tuple[str, object, float]] = []
    if header_text:
        columns.append(("text", header_text, 1.0))
    if command_text:
        columns.append(("text", command_text, 1.0))
    if form_fields:
        columns.append(("form", form_fields, _FORM_COL_WEIGHT))
    if inner_text:
        columns.append(("text", inner_text, 1.0))
    if not columns:
        return

    # Layout (page-edge → patch-side):
    #   [pad] bar [pad]  col0  [gap]  col1 ...  [gap]  colN
    # A ChromIQ spectrum bar sits at the page-edge side; the remaining width is
    # distributed across columns proportional to their weight.
    n = len(columns)
    bar_overhead = _SPECTRUM_BAR_WIDTH_PX + 2 * _SPECTRUM_BAR_PAD_PX
    avail = band_w - bar_overhead - (n - 1) * _LEFT_CLIP_GAP_PX
    total_weight = sum(w for _, _, w in columns)
    widths = [int(avail * w / total_weight) for _, _, w in columns]
    widths[-1] += avail - sum(widths)   # last column absorbs rounding remainder
    if min(widths) < _MIN_STRIP_WIDTH_PX:
        log.info(
            "Left-clip stamp skipped (band %d px too narrow for %d columns) for %s",
            band_w, n, path,
        )
        return

    y0 = _PATCH_SAFETY_PAD_PX

    # ChromIQ spectrum accent, framing the first text line from the page-edge side.
    bar_x0 = band_left + _SPECTRUM_BAR_PAD_PX
    bar = _render_spectrum_bar(strip_h, _SPECTRUM_BAR_WIDTH_PX, dtype, C)
    arr[y0 : y0 + strip_h, bar_x0 : bar_x0 + _SPECTRUM_BAR_WIDTH_PX, :] = bar

    x = bar_x0 + _SPECTRUM_BAR_WIDTH_PX + _SPECTRUM_BAR_PAD_PX
    for (kind, content, _), w in zip(columns, widths):
        if kind == "form":
            text = _build_form_line(
                content,  # type: ignore[arg-type]
                available_text_px=strip_h - 2 * _PATCH_SAFETY_PAD_PX,
                font_px=max(_FORM_FONT_FLOOR, min(_FORM_FONT_CEIL, w - 8)),
            )
        else:
            text = content  # type: ignore[assignment]
        if text:
            strip = _render_fitted_rotated_line(text, strip_h, w, dtype, C)
            arr[y0 : y0 + strip_h, x : x + w, :] = strip
        x += w + _LEFT_CLIP_GAP_PX

    _write_preserving(path, arr, state)


def _render_spectrum_bar(
    strip_h: int,
    strip_w: int,
    dtype,
    channels: int,
) -> np.ndarray:
    """Vertical 5-segment spectrum stripe matching `ui.styles.TAB_COLORS`.

    Returns an (strip_h, strip_w, channels) array. Each of the 5 spectrum
    colors fills `strip_h // 5` rows; the bottom segment absorbs any
    integer-division remainder so the bar fills the full strip height.
    """
    rgb = np.zeros((strip_h, strip_w, 3), dtype=np.uint8)
    n = len(_SPECTRUM_COLORS_RGB)
    seg_h = strip_h // n
    for i, (r, g, b) in enumerate(_SPECTRUM_COLORS_RGB):
        s = i * seg_h
        e = strip_h if i == n - 1 else (i + 1) * seg_h
        rgb[s:e, :, 0] = r
        rgb[s:e, :, 1] = g
        rgb[s:e, :, 2] = b

    if dtype == np.uint16:
        rgb = (rgb.astype(np.uint32) * 257).astype(np.uint16)

    if channels == 3:
        return rgb
    if channels == 1:
        gray = (0.299 * rgb[..., 0]
                + 0.587 * rgb[..., 1]
                + 0.114 * rgb[..., 2]).astype(rgb.dtype)
        return gray[..., None]
    if channels == 4:
        out = np.zeros((strip_h, strip_w, 4), dtype=rgb.dtype)
        out[..., :3] = rgb
        out[..., 3] = np.iinfo(rgb.dtype).max
        return out
    return rgb


# Form-line font sizing bounds. The actual font used is clamped to the
# form sub-column width so the rotated text doesn't overflow horizontally;
# these bounds limit how big or small the rendered glyphs can get on very
# wide / very narrow clip strips. The form (handwriting) line is the most
# important column, so it runs a little larger than the reference columns.
_FORM_FONT_FLOOR = 16
_FORM_FONT_CEIL = 30
# Width weighting: the form column is rendered wider than the plain text
# columns to leave more room for handwriting.
_FORM_COL_WEIGHT = 1.6


def _build_form_line(
    fields: Sequence[str],
    available_text_px: int,
    font_px: int,
) -> str:
    """Build a fill-in-the-blank form line sized to `available_text_px`.

    Each entry in `fields` becomes `"label: ____...____"` with the underscore
    count picked so the joined line — all fields separated by three spaces —
    fills the available rotated-text length. Bigger paper → wider available
    range → more underscores per field. Minimum 8 underscores per field;
    maximum 80 (above that the line becomes silly-long).
    """
    if not fields:
        return ""

    font = _pick_font(font_px)
    probe = Image.new("L", (10, 10), 255)
    draw = ImageDraw.Draw(probe)

    def text_w(s: str) -> int:
        bbox = _text_bbox(draw, s, font)
        return bbox[2] - bbox[0]

    sep = "   "
    sep_w = text_w(sep)
    underscore_w = max(1, text_w("_"))
    label_widths = [text_w(f"{f}: ") for f in fields]

    total_label_w = sum(label_widths)
    total_sep_w = sep_w * (len(fields) - 1)
    remaining_px = available_text_px - total_label_w - total_sep_w
    if remaining_px <= 0:
        underscores = 8
    else:
        underscores = remaining_px // (underscore_w * len(fields))
    underscores = max(8, min(80, int(underscores)))

    return sep.join(f"{label}: {'_' * underscores}" for label in fields)


def _capture_page_state(page) -> dict:
    """Capture every TIFF tag we need to reproduce in the rewritten file."""
    xres_tag = page.tags.get("XResolution")
    yres_tag = page.tags.get("YResolution")
    runit_tag = page.tags.get("ResolutionUnit")
    icc_tag = page.tags.get(34675)

    # tifffile owns 270 (ImageDescription) and 305 (Software) natively — pass
    # them through dedicated kwargs. All other ancillary tags ride along in
    # extratags.
    description_val = _str_tag_value(page.tags.get(270))
    software_val = _str_tag_value(page.tags.get(305))
    orientation_val = page.tags.get(274).value if page.tags.get(274) else None
    xpos_val = (tuple(page.tags.get(286).value)
                if page.tags.get(286) else None)
    ypos_val = (tuple(page.tags.get(287).value)
                if page.tags.get(287) else None)
    artist_val = _str_tag_value(page.tags.get(315))
    copyright_val = _str_tag_value(page.tags.get(33432))

    preserved_tags: list[tuple] = []
    if orientation_val is not None:
        preserved_tags.append((274, 3, 1, int(orientation_val), True))
    if xpos_val:
        preserved_tags.append((286, 5, 1, (int(xpos_val[0]), int(xpos_val[1])), True))
    if ypos_val:
        preserved_tags.append((287, 5, 1, (int(ypos_val[0]), int(ypos_val[1])), True))
    if artist_val:
        preserved_tags.append((315, 2, len(artist_val) + 1, artist_val + "\x00", True))
    if copyright_val:
        preserved_tags.append((33432, 2, len(copyright_val) + 1, copyright_val + "\x00", True))

    return {
        "photometric": page.photometric,
        "compression": page.compression,
        "xres_val": tuple(xres_tag.value) if xres_tag else None,
        "yres_val": tuple(yres_tag.value) if yres_tag else None,
        "runit_val": int(runit_tag.value) if runit_tag else None,
        "icc_bytes": bytes(icc_tag.value) if icc_tag else None,
        "description_val": description_val,
        "software_val": software_val,
        "preserved_tags": preserved_tags,
    }


def _write_preserving(path: Path, arr: np.ndarray, state: dict) -> None:
    """Rewrite `path` with `arr` while preserving every tag captured in `state`."""
    # Preserve resolution and unit. tifffile owns tags 282/283/296 (extratags
    # for them are silently dropped), so we use the resolution kwargs with the
    # exact unit string that matches the original ResolutionUnit value. The
    # rational form may differ by ulps but the unit and effective DPI are
    # preserved, so the image's physical print dimensions are unchanged.
    res_unit_str = _resunit_str(state["runit_val"])
    res_pair = _rational_to_float_pair(state["xres_val"], state["yres_val"])
    extratags: list[tuple] = list(state["preserved_tags"])

    write_kwargs: dict = {
        "photometric": state["photometric"],
        "compression": state["compression"],
        "extratags": extratags or None,
        "metadata": None,
        "description": state["description_val"] or None,
        "software": state["software_val"] if state["software_val"] is not None else False,
    }
    if state["icc_bytes"]:
        write_kwargs["iccprofile"] = state["icc_bytes"]
    if res_pair is not None and res_unit_str is not None:
        write_kwargs["resolution"] = res_pair
        write_kwargs["resolutionunit"] = res_unit_str

    tifffile.imwrite(str(path), arr, **write_kwargs)


def _str_tag_value(tag) -> str | None:
    """Decode a TIFF ASCII tag (bytes or str), stripping trailing NULs."""
    if tag is None:
        return None
    v = tag.value
    if isinstance(v, bytes):
        return v.rstrip(b"\x00").decode("ascii", errors="ignore") or None
    if isinstance(v, str):
        return v.rstrip("\x00") or None
    return None


def _resunit_str(unit: int | None) -> str | None:
    """Map TIFF ResolutionUnit code → tifffile.imwrite resolutionunit string."""
    if unit == 1:
        return "NONE"
    if unit == 2:
        return "INCH"
    if unit == 3:
        return "CENTIMETER"
    return None


def _rational_to_float_pair(
    xres: tuple[int, int] | None,
    yres: tuple[int, int] | None,
) -> tuple[float, float] | None:
    """Convert a pair of TIFF rationals to (float, float). None if either missing/zero."""
    if not xres or not yres or xres[1] == 0 or yres[1] == 0:
        return None
    return (xres[0] / xres[1], yres[0] / yres[1])


def _detect_writable_band(
    arr: np.ndarray,
    side: str = "right",
    keep_out_px: int = 0,
    pad_px: int | None = None,
) -> tuple[int, int] | None:
    """Return (left_x, right_x) of the widest white column run in the requested margin.

    `side="right"` scans the column band to the right of the patch area (the
    page's right edge). `side="left"` scans the column band to the left of the
    patch area (the page's left clip strip).

    A column counts as usable when it is inked over no more than
    `_BAND_INK_TOLERANCE` of the rows sampled, NOT only when it is blank paper.

    Demanding blank paper is what made the note vanish. A ruler dash is a short
    mark: it inks a handful of rows in a column and leaves the rest white, and
    that was enough for no run of `_MIN_STRIP_WIDTH_PX` clear columns to survive,
    so this returned None and the caller gave up. Measured on one chart with
    only the side markers switched on, and again with the clip band moved to the
    right: the notes were not printed on ANY page, with one line in the log and
    nothing on screen.

    An earlier attempt reserved the strip those marks own and moved the search
    inward. It did not work, and a reviewer proved why over a 6 to 26 mm sweep
    of the right margin: it never once rescued a note, because the run-finder
    already picks the widest clear run, and where the margin was narrow it
    removed the only space there was. Tolerating the mark is the mechanism that
    matches what is actually on the paper -- and the stamp composites now, so
    sharing the margin with a dash costs the dash nothing.

    *keep_out_px* IS WHERE THE TOLERANCE IS WITHDRAWN, NOT WHERE THE SEARCH
    STOPS, and the difference is the whole of two failed attempts.

    Tolerating a thin mark means the white gutters BETWEEN the user's own clip
    lines also read as usable paper. The band is wider than the clean strip
    outside it, so "the widest run wins" preferred it and the note was stamped
    straight through their text: measured on two builds differing only in the
    Notes field, the note moved onto 2424 pixels of the user's own lines, and
    nine of thirteen clip configurations came out worse.

    The first repair EXCLUDED the band's footprint from the search, and that was
    worse still, because the note's home has always been the last few
    millimetres at the paper edge -- the same edge the band is measured from. So
    excluding the band excluded the note, and twenty of twenty configurations
    printed nothing at all.

    What both measurements agree on: inside the band's footprint the rule that
    worked demanded BLANK paper, and outside it a thin mark must be tolerated or
    a ruler dash defeats the search. So the tolerance is applied by COLUMN: zero
    where the band reaches, `_BAND_INK_TOLERANCE` beyond it. A dash is a mark
    the note may share; a band the user has filled with words is not.
    """
    if arr.size == 0:
        return None
    H, W = arr.shape[:2]
    max_val = np.iinfo(arr.dtype).max
    ink_cutoff = int(max_val * 240 / 255)
    if arr.shape[2] == 1:
        mask = arr[..., 0] < ink_cutoff
    else:
        mask = (arr < ink_cutoff).any(axis=2)

    col_density = mask.sum(axis=0) / max(1, H)
    patch_cols = np.where(col_density >= _PATCH_COL_DENSITY_THRESHOLD)[0]
    _pad = _PATCH_SAFETY_PAD_PX if pad_px is None else max(0, int(pad_px))

    if side == "left":
        patch_left = (int(patch_cols[0]) - _pad
                      if len(patch_cols) else W // 2)
        if patch_left <= _MIN_STRIP_WIDTH_PX:
            return None
        scan_lo, scan_hi = 0, patch_left
    else:
        patch_right = (int(patch_cols[-1]) + _pad
                       if len(patch_cols) else W // 2)
        if patch_right >= W - _MIN_STRIP_WIDTH_PX:
            return None
        scan_lo, scan_hi = patch_right, W

    mid_top, mid_bottom = H // 6, 5 * H // 6
    _sampled = mask[mid_top:mid_bottom, scan_lo:scan_hi]
    _rows = max(1, _sampled.shape[0])
    _frac = _sampled.sum(axis=0) / _rows
    # The tolerance is withdrawn where the clip band reaches, so the note can
    # share a margin with a ruler dash but never with the user's own lines.
    _tol = np.full(_frac.shape, float(_BAND_INK_TOLERANCE))
    _keep = max(0, int(keep_out_px))
    if _keep and side == "right":
        _from = max(0, (W - _keep) - scan_lo)
        _tol[_from:] = 0.0
    elif _keep:
        _tol[:min(_tol.size, max(0, _keep - scan_lo))] = 0.0
    margin_inked = _frac > _tol

    runs: list[tuple[int, int]] = []
    in_run = False
    run_start = 0
    for i, inked in enumerate(margin_inked):
        if not inked and not in_run:
            in_run = True
            run_start = scan_lo + i
        elif inked and in_run:
            in_run = False
            runs.append((run_start, scan_lo + i))
    if in_run:
        runs.append((run_start, scan_hi))

    runs = [(a, b) for (a, b) in runs if b - a >= _MIN_STRIP_WIDTH_PX]
    if not runs:
        return None
    best_left, best_right = max(runs, key=lambda r: r[1] - r[0])
    best_left += _pad
    best_right -= _pad
    if best_right - best_left < _MIN_STRIP_WIDTH_PX:
        return None
    return (best_left, best_right)


def _render_rotated_line(
    text: str,
    strip_h: int,
    strip_w: int,
    font: ImageFont.ImageFont,
    dtype,
    channels: int,
    anchor_px: int | None = None,
) -> np.ndarray:
    """Return a (strip_h, strip_w, channels) numpy array containing `text` rotated 90° CCW.

    Across the strip the line is centred, which is right for the left-clip
    sub-columns: each one is cut to its own text. Pass *anchor_px* to butt the
    line against the strip's PATCH-SIDE edge with that many pixels of white
    instead, which is what the right-margin note wants -- there the strip is a
    fixed 40 px at most and centring stranded the line in the middle of it.

    The unrotated canvas is (strip_h x strip_w) and a 90 degree CCW rotation
    sends a small canvas y to a small destination x, so the anchor is simply a
    small y. Verified rather than assumed: ink drawn in canvas rows 0..5 comes
    out in destination columns 0..5.
    """
    canvas = Image.new("L", (strip_h, strip_w), 255)
    draw = ImageDraw.Draw(canvas)
    bbox = _text_bbox(draw, text, font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = max(0, (strip_h - text_w) // 2 - bbox[0])
    if anchor_px is None:
        y = (strip_w - text_h) // 2 - bbox[1]
    else:
        y = anchor_px - bbox[1]
    draw.text((x, y), text, fill=0, font=font)

    rotated = canvas.rotate(90, expand=True, resample=Image.Resampling.NEAREST)
    band_l = np.asarray(rotated, dtype=np.uint8)
    assert band_l.shape == (strip_h, strip_w), \
        f"rotation produced {band_l.shape}, expected {(strip_h, strip_w)}"

    if dtype == np.uint16:
        band_l = (band_l.astype(np.uint32) * 65535 // 255).astype(np.uint16)

    if channels == 1:
        return band_l[..., None]
    return np.repeat(band_l[..., None], channels, axis=2)


def _render_fitted_rotated_line(
    text: str,
    strip_h: int,
    strip_w: int,
    dtype,
    channels: int,
    anchor_px: int | None = None,
    font_family: str = "",
    size_pt: float = 0.0,
    dpi: float = 200.0,
) -> np.ndarray:
    """Render `text` into a (strip_h, strip_w) sub-band, shrinking font until it fits.

    Targets the left-clip stamp where the band is wider than the right-margin
    case and font sizing must adapt to the available rotated text length.

    **THE SHRINKING STOPS AT 8 POINT, AND ONLY "AUTO" SHRINKS AT ALL.**
    Knut, 2026-09-11, on his own hex chart: *"the text is reduced to a
    mini-sized font almost not readable, instead of warning of the text not
    having room to fit … I suggest a font size limit of 8pt (if the Sheet text
    frame size parameter is set to auto). If the Sheet text frame size
    parameter is set to a value, no shrinking should happen and the warning
    instead shown."*

    So *size_pt* > 0 is used exactly as typed — 6 pt included — and the loop
    below never reduces it; *size_pt* 0 ("auto") starts from the room the strip
    offers and stops at :data:`text_edge_fit.AUTO_SHRINK_FLOOR_PT`. Either way
    the line may then be wider than the strip, and the strip's own edges crop
    it; the warning that says so is raised by the panel
    (`ui/tabs/tab_chart.py::_engine_text_notes`), which reads its floor from the
    same module so the two cannot disagree.

    The floor this replaced was **9 pixels**, which is a floor on the raster and
    not on paper: 3.24 pt at 200 dpi and 1.08 pt at 600. Measured on Knut's own
    `testHex` project at his own numbers (right margin 6 mm, Clip 4 mm), the
    note printed 2.29 mm of ink across the sheet, or 6.5 pt including its gap.

    TWO AXES, TWO DIFFERENT RULES, and only one of them is about the page edge.
    Down the strip's LENGTH the font shrinks and then the text is cut, because
    that axis runs the height of the sheet and what overflows it falls off the
    paper (see the note at the floor below). ACROSS the strip the font is capped
    so the line's own thickness fits the room the caller measured out, because
    that axis ends at the user's "Text distance from edge" and overflowing it is
    the fault this parameter exists to stop.
    """
    shown, font = fit_rotated_line(text, strip_h, strip_w, anchor_px=anchor_px,
                                   font_family=font_family, size_pt=size_pt,
                                   dpi=dpi)
    return _render_rotated_line(shown, strip_h, strip_w, font, dtype,
                                channels, anchor_px=anchor_px)


def _one_step_smaller_pt(size_pt: float, floor_pt: float) -> float:
    """One half-point down from *size_pt*, never past *floor_pt*.

    **THIS USED TO BE `int(font_px * 0.9)`, AND TEN PER CENT IS NOT A SIZE.**
    Measured at 300 dpi from 12 pt it walked 12 -> 10.8 -> 9.6 -> 8.64 -> 7.68
    -> 6.96, stepping straight over 9.5 and landing below its own 7 pt floor on
    the way out. Knut, 2026-09-13: *"the shrinking mechanism ... should be able
    to find a better fit when a text length is too long for 10 pt and far
    within the boundaries for 9 pt, and a 9,5 pt fits better."* His example is
    this loop.

    The grid is `text_edge_fit.next_size_down_pt`, the same 0.5 the Size boxes
    step by, so what the shrink settles on is a value the user could have
    typed. Always strictly smaller than its input, or the loop would not end.
    """
    return max(float(floor_pt),
               text_edge_fit.next_size_down_pt(size_pt))


def fit_rotated_line(
    text: str,
    strip_h: int,
    strip_w: int,
    anchor_px: int | None = None,
    font_family: str = "",
    size_pt: float = 0.0,
    dpi: float = 200.0,
):
    """``(text as it will be printed, the font)`` for a rotated side line.

    THE DECISION, SEPARATED FROM THE DRAWING, so the panel can ask what the
    stamper will do without rendering a strip. Knut's ruling of 2026-09-11
    lowered the automatic floor from 8 pt to 7 because his own 141-character
    note lost its last twelve characters at 8 pt, and that loss reached him
    only as ink he could not read: the log says so at INFO and nothing on
    screen did. A predicate the panel can call is what makes it sayable, and
    it has to be THIS predicate rather than a second copy of the rule, because
    the panel's whole job here is to predict what the stamper does.
    """
    fixed = float(size_pt or 0.0) > 0.0
    floor_px = text_edge_fit.pt_to_px(text_edge_fit.text_floor_pt(size_pt), dpi)
    available_text_w = strip_h - 2 * _PATCH_SAFETY_PAD_PX
    _gap = 0 if anchor_px is None else int(anchor_px)
    available_text_h = strip_w - _gap
    if fixed:
        font_px = floor_px
    else:
        # THE CAP IS A SIZE, SO IT IS IN POINTS. It was the literal 28 PIXELS,
        # which is a different size at every raster: 13.44 pt at 150 dpi,
        # 10.08 at 200, and 6.72 at 300, which is BELOW the 7 pt floor. So from
        # 240 dpi upwards the start was clamped to the floor, the shrink loop
        # had nowhere to go, and a long note went straight to being truncated
        # with an ellipsis at the smallest size allowed instead of being fitted
        # at a readable one. 300 dpi is `LayoutRecipe`'s default.
        #
        # Found by an adversary round measuring the half-point shrink and
        # discovering it never ran: putting the old step back changed the
        # outcome in 0 of 24 configurations at 200 to 600 dpi.
        #
        # 10 pt is what the old constant meant at 200 dpi, which is the raster
        # it was chosen at.
        font_px = max(floor_px, min(text_edge_fit.pt_to_px(NOTE_START_MAX_PT, dpi),
                                    strip_w - 8 if anchor_px is None
                                    else strip_w - _gap))

    # THE SIZE IS CARRIED IN POINTS, NOT PIXELS. The loop used to hold an
    # integer pixel count and step it, and at 300 dpi one pixel is 0.24 pt, so
    # a half-point grid could not be represented at all: every candidate
    # rounded back onto a neighbouring pixel and the pixel did the stepping.
    # Points are the unit the user types and the unit Knut asked the shrink to
    # settle on, so they are the unit the loop counts in; pixels are derived
    # for the draw.
    floor_pt = text_edge_fit.px_to_pt(floor_px, dpi)
    size_now_pt = text_edge_fit.px_to_pt(font_px, dpi)

    probe = Image.new("L", (10, 10), 255)
    draw = ImageDraw.Draw(probe)
    shown = text
    while True:
        font_px = max(1, text_edge_fit.pt_to_px(size_now_pt, dpi))
        font = _pick_font(font_px, font_family)
        bbox = _text_bbox(draw, shown, font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        # THICKNESS FIRST, AND CUTTING THE TEXT NEVER FIXES IT. A shorter line
        # is exactly as thick as a long one, so a thickness overflow handled by
        # the truncation path below would shorten the note one character at a
        # time and still not fit. Shrink for it while there is room to shrink;
        # at the floor let the strip's own edges crop it, which is safe because
        # those edges are inside the page-edge reserve the caller measured.
        if anchor_px is not None and text_h > available_text_h \
                and size_now_pt > floor_pt + 1e-9:
            size_now_pt = _one_step_smaller_pt(size_now_pt, floor_pt)
            continue
        if text_w <= available_text_w:
            return shown, font
        if size_now_pt > floor_pt + 1e-9:
            size_now_pt = _one_step_smaller_pt(size_now_pt, floor_pt)
            continue
        # AT THE FLOOR, SHORTEN THE TEXT RATHER THAN LOSE ITS END IN SILENCE.
        #
        # The loop used to give up here and render anyway, and the renderer
        # CENTRES what it is given, so a note past about 260 characters lost its
        # tail off the paper with nothing to show for it. Measured on a 100x150
        # card: 12.45 mm gone at 300 characters and 63.75 mm at 400, ending
        # mid-word. A note is the user's own words and the end is usually the
        # part that matters, so what cannot be printed is marked as cut instead
        # of vanishing. Nine pixels is already the legibility floor and going
        # below it would trade one silent loss for another.
        if len(shown) <= 8:
            return shown, font
        cut = max(8, int(len(shown) * available_text_w / max(1, text_w)) - 1)
        shown = shown[:cut].rstrip() + "…"
        log.info("Chart note shortened to fit the margin: %d of %d characters",
                 len(shown) - 1, len(text))


#: The largest size the right-margin note STARTS at before fitting, in points.
#: A size, not a pixel count: see `fit_rotated_line` for what a pixel constant
#: did at 300 dpi.
NOTE_START_MAX_PT = 10.0

#: The widest strip the right-margin note is ever drawn into, in pixels.
#: `_stamp_one`: ``strip_w = min(40, …)``. Repeated as a name so the predictor
#: below and the stamper cannot pick different numbers.
NOTE_STRIP_MAX_PX = 40


def note_characters_lost(text: str, paper_h_mm: float, text_edge_mm: float,
                         avail_mm: float, dpi: float, size_pt: float = 0.0,
                         font_family: str = "",
                         text_edge_top_mm: float = -1.0,
                         text_edge_bottom_mm: float = -1.0) -> int:
    """How many characters the chart note loses off the END of the sheet.

    0 when the whole note is printed, which is the ordinary case.

    **THIS IS THE OTHER HALF OF THE SHRINK FLOOR, AND IT WAS SILENT.** A floor
    that stops the type getting smaller is only honest while the text it leaves
    still fits the sheet. Knut, 2026-09-11, on his own 130 x 180 mm card: *"The
    auto setting shrunk the text to size 8, but that cause the long text to
    overflow the height of the page, so I changed to size 7."* Measured through
    `fit_rotated_line` at his own numbers, the 141-character note came out as
    **129 characters and an ellipsis** at an 8 pt floor and whole at 7 pt, and
    what was cut was *"nagement: OFF"*, the end of the colour-management
    instruction the note exists to carry. `_stamp_one` says so in the log at
    INFO and nothing said it on screen.

    The answer comes from the fitter itself rather than from a second copy of
    its rule, because the panel's job here is to predict what the stamper does
    and the two have drifted apart once already.

    *text_edge_top_mm* / *text_edge_bottom_mm* are the reserves for the two
    edges the line's ENDS run into, exactly as in :func:`_stamp_one`, and this
    has to take the same pair or it measures a strip the stamper does not use.
    Negative means "not supplied" and *text_edge_mm* stands for all three.
    """
    body = str(text or "")
    if not body:
        return 0
    try:
        d = float(dpi)
        if d <= 0:
            raise ValueError
    except (TypeError, ValueError):
        d = 200.0
    mm2px = d / 25.4
    pad = int(round(max(0.0, float(text_edge_mm or 0.0)) * mm2px))
    H = int(round(max(0.0, float(paper_h_mm or 0.0)) * mm2px))

    def _end_pad(v: float) -> int:
        if v is None or float(v) < 0.0:
            return pad
        return int(round(max(0.0, float(v)) * mm2px))
    pad_t, pad_b = _end_pad(text_edge_top_mm), _end_pad(text_edge_bottom_mm)
    if pad_t + pad_b >= H:
        pad_t = pad_b = 0
    strip_h = H - pad_t - pad_b
    if strip_h < 100:
        return 0
    floor_px = text_edge_fit.note_min_strip_px(d, size_pt)
    strip_w = int(round(max(0.0, float(avail_mm or 0.0)) * mm2px))
    strip_w = min(NOTE_STRIP_MAX_PX, strip_w)
    if strip_w < floor_px:                 # the overlap path: it gets the floor
        strip_w = floor_px
    shown, _font = fit_rotated_line(body, strip_h, strip_w,
                                    anchor_px=_NOTE_PATCH_GAP_PX,
                                    font_family=font_family, size_pt=size_pt,
                                    dpi=d)
    if shown == body:
        return 0
    # The fitter marks a cut with a trailing ellipsis, which is not one of the
    # user's own characters.
    kept = len(shown) - 1 if shown.endswith("…") else len(shown)
    return max(0, len(body) - kept)


def _pick_font(size_px: int, family: str = "") -> ImageFont.ImageFont:
    """The face the note is drawn in.

    *family* is the Sheet text frame's Font, which now governs the run chart
    notes and the stamped settings too (Knut, 2026-09-11: *"The Sheet text
    frame Font and Size should be used for the Run Chart Notes text and the
    'Stamp settings used on the chart' checkbox, so that the text is
    controllable."*). It is resolved through the layout engine's own resolver,
    so the note is drawn in exactly the face the rest of the sheet uses, and
    the bundled families work as well as the installed ones. Empty, or a name
    that resolves to nothing, falls back to what this stamper always used.
    """
    if family:
        try:
            from workflow.layout_engine import raster as _raster
            return _raster._font(max(6, int(size_px)), family)
        except Exception:                                       # noqa: BLE001
            pass
    for name in ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "Helvetica.ttf"):
        try:
            return ImageFont.truetype(name, size_px)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_bbox(draw: "ImageDraw.ImageDraw", text: str, font) -> tuple[int, int, int, int]:
    try:
        return draw.textbbox((0, 0), text, font=font)
    except AttributeError:
        w, h = draw.textsize(text, font=font)  # type: ignore[attr-defined]
        return (0, 0, w, h)
