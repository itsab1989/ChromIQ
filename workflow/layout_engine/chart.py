"""High-level entry point: build a chart's ``.ti2`` from a targen ``.ti1``.

This wires the headless pieces together (read ``.ti1`` → pack → write ``.ti2``)
for any colorant the ``.ti1`` declares.  The page **TIFF** raster is a later
phase (issue #93); this module already produces the measurement-side ``.ti2``
that chartread consumes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.stem_paths import artefact, without_ext

from . import geometry, instruments, papers, permutation, raster
from . import ti1_reader, ti2_writer


@dataclass(frozen=True)
class ChartResult:
    ti2_path: Path
    seed: int
    randomize: bool
    color_rep: str
    layout: geometry.Layout
    tiff_paths: list[Path] | None = None
    strip_rects: list[dict] | None = None
    low_contrast_passes: list[int] | None = None
    #: The flagged strips by their sheet labels (``raster.RenderResult``).
    low_contrast_labels: list[str] | None = None
    cht_paths: list[Path] | None = None
    pdf_path: Path | None = None
    #: The date drawn on the record strip (``YYYY-MM-DD``). Saved with the chart
    #: so a rebuild can reproduce it instead of stamping the day it ran.
    chart_date: str = ""
    #: Paper whites added so each calibration ramp starts its own strip
    #: (``ramps_per_strip``); 0 when nothing was rearranged.
    ramp_whites_added: int = 0
    #: Why the layout may read less well (an i1iO chart, Job D: risky
    #: options are warned about, not refused), translated, for the log.
    warnings: tuple = ()
    #: R7: the patches that changed places so that no near-black patch sits
    #: next to a near-white one, as (location, location) pairs; and the
    #: pairs left because no swap could clear them.
    neighbour_moves: tuple = ()
    neighbour_pairs_left: int = 0
    #: how many patches sit somewhere else than the patch order puts them
    neighbour_patches_moved: int = 0
    #: The chart's own slot list when it has one (canonical patch -> sheet
    #: slot: R7's, an i1iO's), else None (the seed's permutation).
    slots: "list[int] | None" = None
    #: The patch as laid out, ``(across the strip, along it)`` in mm
    #: (`laid_out_patch_size_mm`), or None: what `{patchsize}` prints, for
    #: the chart notes stamped after the build (4.3.45).
    patch_size_mm: "tuple[float, float] | None" = None


def build_ti2_from_ti1(
    ti1_path: str | Path,
    ti2_path: str | Path,
    *,
    instrument: str = "i1",
    paper: str = "A4",
    seed: int | None = None,
    randomize: bool = True,
    hflag: bool = False,
    hex_flat_top: bool = False,
    density: int = 1,
    spacer_on: bool = True,
    pscale: float = 1.0,
    sscale: float = 1.0,
    border: float = 6.0,
    nolpcbord: bool = False,
    nolimit: bool = False,
    strip_pattern: str = permutation.DEFAULT_STRIP_PATTERN,
    patch_pattern: str = permutation.DEFAULT_PATCH_PATTERN,
) -> ChartResult:
    """Read *ti1_path*, lay it out for *instrument* on *paper*, write *ti2_path*.

    *paper* is a named code ("A4", "A4R", "Letter", …) or a custom ``WxH`` (mm).
    *seed* defaults to a fresh reproducible value (surfaced in the result so the
    UI can show it and accept it back).
    """
    target = ti1_reader.read_ti1(ti1_path)
    geom = instruments.build(
        instrument, hflag=hflag, hex_flat_top=hex_flat_top, density=density, spacer_on=spacer_on, pscale=pscale,
        sscale=sscale, border=border, nolpcbord=nolpcbord, nolimit=nolimit,
    )
    w_mm, h_mm = papers.dimensions_mm(paper)
    layout = geometry.compute(geom, w_mm, h_mm, len(target.patches))

    if seed is None:
        seed = permutation.pick_seed()

    media = target.media_patch()
    white_point = media[1] if any(media[1]) else ti2_writer.DEFAULT_WHITE_POINT

    ti2_writer.write_ti2(
        ti2_path, target.patches, target.device_fields, layout, geom,
        color_rep=target.color_rep, seed=seed, randomize=randomize,
        strip_pattern=strip_pattern, patch_pattern=patch_pattern,
        paper_w_mm=w_mm, paper_h_mm=h_mm, media=media, white_point=white_point,
        ink_limit=target.ink_limit,
    )
    return ChartResult(
        ti2_path=Path(ti2_path), seed=seed, randomize=randomize,
        color_rep=target.color_rep, layout=layout,
    )



#: Instrument key → the name a person reads, used in the layout stamp and in
#: the {instrument} placeholder. The CR30's device key IS its friendly name
#: (#159), so the .get() fallback below would already be right — listed
#: explicitly so the table is a complete answer to "which instruments does the
#: engine know", not a coincidence that happens to work.
_INSTR_FRIENDLY = {"i1": "i1Pro", "p3": "i1Pro3+", "CM": "ColorMunki",
                   "SS": "SpectroScan", "41": "DTP41", "51": "DTP51",
                   "CR30": "CR30",
                   # R8 (4.3.39): the i1iO's clip-border notes printed the
                   # internal code "IO2" for {instrument}
                   "IO2": "i1iO"}


def friendly_instrument(instrument: str) -> str:
    """The name of *instrument* as the sheet prints it."""
    return _INSTR_FRIENDLY.get(instrument, instrument)


def text_placeholder_context(*, project: str = "", rundescription: str = "",
                             instrument: str = "", paper: str = "",
                             dpi: int = 300, patches: int = 0, pages: int = 1,
                             seed: int = 0, chart_date: str = "",
                             randomize: bool = True,
                             patch_size_mm: "tuple[float, float] | None" = None
                             ) -> dict:
    """The values `{project}`, `{paper}`, `{seed}` and the rest resolve to.

    `{patchsize}` (4.3.45, jctay, forum post 150317) is *patch_size_mm*, the
    patch as the chart was really laid out (:func:`laid_out_patch_size_mm`),
    across the strip x along it, in millimetres with one decimal each and no
    spaces ("7.0x7.4", :func:`patch_size_text`). Not given, the size is not
    known and `{patchsize}` prints nothing, the way `{rundescription}` does
    with no description.

    LIFTED OUT OF `build_chart` FOR THE SAME REASON `stamp_summary_line` WAS.
    The Create Chart panel warns about a line that is too long, and it measured
    the string with the braces still in it while the sheet prints the resolved
    one. On Knut's own example line, `{project}-{rundescription}-{page}-{paper}-
    {date}-{pages}-{patchcount}-{dpi}-{seed}` at 12 pt, the panel measured
    172.3 mm and the sheet prints 184.8: it is two characters longer and
    12.6 mm wider, because digits and capitals are wider than braces and
    lowercase. The error goes both ways, `{seed}` alone is 23.3 mm wider
    resolved and a long chain of token names is 11.3 mm narrower, so the panel
    could equally miss a real overflow or warn about a sheet that comes out
    clean.

    `{page}` is NOT here. It needs the page index and `render_pages` adds it
    per page, which is the one placeholder a prediction cannot know; the panel
    supplies its own first-page stand-in.

    4.3.42 (a tester's sheet, 2026-11-16): `{seed}` is empty on a chart whose
    patch order is NOT randomised. The seed then decides nothing on the sheet
    (`permutation.location_permutation` keeps every patch in its place, and
    no spacer, label or mark is drawn from it), so a number there only
    suggested an order that was never shuffled. `raster.resolve_placeholders`
    takes the separator in front of it away with it.
    """
    import time as _time
    return {
        "project": project,
        "rundescription": rundescription,
        "instrument": friendly_instrument(instrument),
        "paper": (_i1io_paper_name(paper) if instrument == "IO2"
                  else papers.friendly_label(paper)) if paper else "",
        "dpi": f"{dpi} dpi",
        "patchcount": f"{patches} patches",
        "pages": str(pages),
        "date": chart_date or _time.strftime("%Y-%m-%d"),
        "seed": f"seed {seed}" if randomize else "",
        "patchsize": patch_size_text(patch_size_mm),
    }


def patch_size_text(size_mm: "tuple[float, float] | None") -> str:
    """`{patchsize}` for *size_mm* ``(across, along)``: one decimal each, a
    point in every language (it goes on the chart, like "page 1/2"), an
    "x" between and no spaces, "7.0x7.4". A half rounds up, as people
    round. Empty when the size is not known or not a size."""
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
    try:
        w, h = (float(v) for v in size_mm)          # type: ignore[union-attr]
    except (TypeError, ValueError):
        return ""
    if not (w > 0 and h > 0) or w != w or h != h or w == float("inf") \
            or h == float("inf"):
        return ""

    def one(v: float) -> str:
        # through the 2-decimal value the Chart layout information shows, so
        # 7.349999 is 7.3 there and here, and 7.35 is 7.4 in both
        try:
            return str(Decimal(f"{v:.2f}").quantize(Decimal("0.1"),
                                                    rounding=ROUND_HALF_UP))
        except InvalidOperation:
            return ""
    a, b = one(w), one(h)
    return f"{a}x{b}" if a and b else ""


def laid_out_patch_size_mm(geom, paper_w_mm: float = 0.0,
                           paper_h_mm: float = 0.0, layout=None,
                           dpi: int = 0) -> "tuple[float, float] | None":
    """The patch as the chart was laid out: ``(across the strip, along it)``
    in mm, what `{patchsize}` prints (4.3.45).

    THE LAID-OUT SIZE, NOT THE PIXELS (review of 4.3.45, M1, decided by the
    coordinator): the size the layout was built on, ``geom.pwid`` x
    ``geom.plen``, which is what the person typed in "Patch size (mm)" or
    what automatic fitting made of it. 7.0 x 7.4 typed at 150 dpi prints
    "7.0x7.4", although the raster draws those patches 41 or 42 pixels wide
    (6.9 or 7.1 mm): the patch pitch averages to the laid-out size exactly,
    while the first patch's pixel box depends on where it sits on the pixel
    grid. A printtarg chart prints its .cht's box, which is nominal too, so
    the two engines follow one rule. A honeycomb's hexagon is measured tip to
    tip from its slot (`hex_support.shown_patch_size_mm`); an i1iSis chart's
    patch is its nominal one anyway. The paper, layout and dpi are not
    needed any more and are accepted so older callers keep working.
    None when it cannot be worked out."""
    from workflow.hex_support import shown_patch_size_mm
    from .instruments import is_hexagonal
    try:
        pw, ph, _pitch = shown_patch_size_mm(
            float(geom.pwid), float(geom.plen), is_hexagonal(geom),
            bool(getattr(geom, "hex_flat_top", False)))
    except Exception:          # noqa: BLE001 - unknown, never a failure
        import logging
        logging.getLogger(__name__).debug(
            "patch size for {patchsize} unavailable", exc_info=True)
        return None
    return (pw, ph) if pw > 0 and ph > 0 else None


def _i1io_paper_name(paper: str) -> str:
    """The paper an i1iO chart's notes name (review 6, nit): the app's own
    name where it has one ("A4 portrait"), A5 and 13 x 18 cm by name, any
    other custom size by its millimetres, never the raw code ("148x210")."""
    from data.patch_db import PAPER_LABELS
    if paper in PAPER_LABELS:
        return papers.friendly_label(paper)
    named = {"148x210": "A5 portrait", "130x180": "13 × 18 cm portrait"}
    if paper in named:
        return named[paper]
    try:
        w, h = papers.dimensions_mm(paper)
    except (ValueError, TypeError):
        return str(paper)
    return f"{w:g} × {h:g} mm"


def stamp_summary_line(instrument: str, paper: str, dpi: int, patches: int,
                       seed: int, randomize: bool = True) -> str:
    """The one line "Stamp layout summary along the bottom" prints.

    LIFTED OUT OF `build_chart` SO THE PANEL CAN ASK FOR IT. Knut, 2026-09-13,
    testing beta 8: *"When using 'Stamp layout information along the bottom'
    (and no custom text) with font size 13 or 14 makes text that cross into the
    right clip-border text, but no warning is given. This happens regardless of
    the clip-border is on left of right side."*

    He is right, and the reason is that the panel's width check measured
    `chart_text` alone while the renderer measures BOTH bottom lines and shrinks
    the pair (`raster.render_pages`, `_btxt`). With no custom text there was
    nothing to measure, so the check did not run at all. The panel now predicts
    this line, and it must be THIS function rather than a second copy of the
    f-string: a re-implementation that drifts from the shipped one is how a
    prediction comes to warn about a sheet nobody prints.
    """
    # 4.3.42: no seed on a chart in fixed order (see text_placeholder_context)
    return (f"ChromIQ engine · {friendly_instrument(instrument)} · "
            f"{papers.friendly_label(paper)} · {dpi} dpi · "
            f"{patches} patches" + (f" · seed {seed}" if randomize else ""))


def build_chart(
    ti1_path: str | Path,
    out_base: str | Path,
    *,
    instrument: str = "i1",
    paper: str = "A4",
    seed: int | None = None,
    randomize: bool = True,
    dpi: int = 300,
    hflag: bool = False,
    hex_flat_top: bool = False,
    density: int = 1,
    cm_stagger: bool = False,
    spacer_on: bool = True,
    spacer_mode: str = "colored",
    spacer_palette: list | None = None,
    spacer_overrides: dict | None = None,
    edge_spacers: bool = False,
    patch_area_align: str = "center-left",
    layout_mode: str = "patch_first",
    area_method: str = "by_width",
    area_cols: int = 0,
    area_rows: int = 0,
    area_ratio: float = 0.0,
    area_min_patch: float = 0.0,
    area_default_w: float = 0.0,
    area_default_h: float = 0.0,
    pscale: float = 1.0,
    sscale: float = 1.0,
    border: float = 6.0,
    margins: tuple[float, float, float, float] | None = None,
    patch_w: float | None = None,
    patch_h: float | None = None,
    fd9_gap: float | None = None,
    spacer_width: float | None = None,
    inter_patch: float | None = None,
    strip_gap: float | None = None,
    max_strip: float | None = None,
    strip_indicator_gap: float | None = None,
    row_indicators: bool | None = None,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    bit16: bool = False,
    compression: str = "lzw",
    export_pdf: bool = False,
    draw_indicators: bool = True,
    indicator_font: str = "JetBrains Mono",
    indicator_size_mm: float = 0.0,
    indicator_bold: bool = False,
    indicator_italic: bool = False,
    indicator_rotation: int = 0,
    indicator_align: str = "left",
    # The row labels' own rotation ("Row indicators only", Basti 2026-10-25).
    # Carried on the geometry (`Geom.row_label_rotation`), which the renderer
    # already receives.
    row_indicator_rotation: int = 0,
    strip_label_offset_mm: float = 0.0,
    strip_label_offset_x_mm: float = 0.0,
    underline_mode: str = "off",
    underline_thickness_mm: float = 0.5,
    underline_gap_mm: float = 0.5,
    chart_text: str = "",
    chart_text_font: str = "Inter",
    chart_text_size_mm: float = 0.0,
    chart_text_bold: bool = False,
    chart_text_italic: bool = False,
    #: Where the bottom lines sit across the page (Knut, 2026-09-14).
    chart_text_align: str = "left_margin",
    helper_markers: bool = False,
    helper_marker_edge: float = 2.0,
    helper_marker_len: float = 2.0,
    helper_marker_per_patch: int = 3,
    helper_markers_top_bottom: bool = True,
    helper_markers_sides: bool = True,
    text_edge: float = 4.0,
    text_edge_top: float = 4.0,
    text_edge_clip: float = 4.0,
    use_instrument_margins: bool = False,
    stamp_command: bool = False,
    #: Whether anything will be stamped down the RIGHT page edge afterwards --
    #: the run's chart notes, the "Stamp settings down the right edge" line, or
    #: both. Not drawn here: `workflow/tiff_metadata.py::stamp_chart_metadata`
    #: paints it onto the finished raster. The layout is told because it has to
    #: leave the strip clear -- see `raster._clear_the_side_stamp` (§R9).
    #:
    #: **THE DEFAULT IS True BECAUSE THE APP'S IS.** `ChartParams.stamp_
    #: commands` ships True and Guided has no control for it, so a caller that
    #: does not know reserves the strip rather than laying patches under it.
    #: `stamp_command` above is a DIFFERENT control (the layout summary along
    #: the BOTTOM); the two have been confused before.
    side_stamp: bool = True,
    project: str = "",
    # #130: the run's own description (or the calibration's), for the
    # {rundescription} placeholder in sheet text and the clip border. Empty
    # renders as nothing, the way {seed} does on a chart with no seed.
    rundescription: str = "",
    # The date the chart's record strip carries, as ``YYYY-MM-DD``. Left unset
    # it is today — right for a chart being made. A chart being REBUILT from a
    # stored copy must pass the date it was originally made on, or the sheet
    # that comes back is stamped with the day it was restored rather than the
    # day it was measured (Knut, #130 2026-08-01).
    chart_date: str = "",
    nolpcbord: bool = False,
    nolimit: bool = False,
    clip_border_width: float = 26.0,
    clip_side: str = "left",
    clip_content_mode: str = "off",
    # B8-1402: carried by `LayoutRecipe.build_kwargs` so a chart restored from
    # its build settings keeps the kind a clip border switched On takes (K57).
    # A setting of the panel, not of the sheet: nothing here draws with it.
    clip_content_when_on: str = "",
    clip_text: str = "",
    clip_text_font: str = "Inter",
    clip_text_size_mm: float = 0.0,
    clip_image_path: str = "",
    clip_image_rotation: int = 0,
    clip_image_scale: float = 100.0,
    clip_image_offset_x: float = 0.0,
    clip_image_offset_y: float = 0.0,
    clip_flip_180: bool = False,
    # False only for a recipe saved before 4.3.14: the clip border keeps
    # 4.3.13's rules (`instruments.old_clip_border_rule`).
    clip_border_free_space: bool = True,
    strip_pattern: str = permutation.DEFAULT_STRIP_PATTERN,
    patch_pattern: str = permutation.DEFAULT_PATCH_PATTERN,
    cal_path: str | Path | None = None,
    apply_cal: bool = False,
    emit_cht: bool = False,
    label_rule: str = permutation.ARGYLL,
    #: A calibration chart: lay each ink's ramp out on its own strip (see
    #: `calibration_ramps`). Rewrites the .ti1 in place when it is targen's
    #: pure ramp set; any other .ti1 is laid out exactly as it is.
    ramps_per_strip: bool = False,
    #: R7 (4.3.39): on a chart in FIXED order, move the fewest patches needed
    #: so that no near-black patch sits directly next to a near-white one
    #: along a strip (`neighbour_order`). Off here, so every direct caller
    #: lays out as before; a recipe made from 4.3.39 on asks for it. Strip
    #: instruments only; never a randomised chart, a calibration chart, an
    #: i1iO, i1iSis or FD-9 chart.
    avoid_dark_light_neighbours: bool = False,
    #: FD-9 only (4.3.25): the run, for the Notes box of the FD-9 clip
    #: border, and that border's On/Off (None:
    #: `workflow.fd9.furniture.FD9_CLIP_BORDER_DEFAULT`).
    #: No other instrument reads them.
    fd9_run: str = "",
    fd9_clip_border: "bool | None" = None,
    #: i1iO only (a Beta): the three numbered aiming crosses on (default) or
    #: off; off, the person aims at the corner patches
    #: (`workflow.i1io.chart.fixed_build_kwargs`, `sheet_slots`). No other
    #: instrument reads it.
    i1io_crosses: bool = True,
    #: i1iO only: Manual's "Patch area alignment" chosen for the i1iO ("" =
    #: the i1iO's own, `workflow.i1io.chart.align_of`). No other instrument
    #: reads it.
    i1io_align: str = "",
    #: i1iO only: the clip border On/Off (an option, off by default,
    #: `workflow.i1io.chart.CLIP_KEY`): the notes band down the page's left
    #: edge, with the clip-border content asked for. No other instrument
    #: reads it.
    i1io_clip_border: bool = False,
    #: i1iO only: the sheet text's Bold (`workflow.i1io.chart.TEXT_BOLD_KEY`,
    #: None = the i1iO's own, bold). No other instrument reads it.
    i1io_text_bold: "bool | None" = None,
    #: i1iO only (Job D): the patch numbers' distance from the paper edge
    #: (0 = the i1iO's own 10 mm) and where the name line sits in its room
    #: ("" = centred, "start"). No other instrument reads them.
    i1io_numbers_edge_mm: "float | None" = None,
    i1io_text_align: str = "",
    #: i1iSis only (a Beta, `workflow.isis.chart`): the model width, the
    #: header, tight margins, barcode, trailer, arrows, outline, corner
    #: labels, strip letters, row numbers, the notes band and the chart's
    #: alignment (None / "" = the i1iSis chart's own). No other instrument
    #: reads them.
    isis_model: str = "",
    isis_header_mm: "float | None" = None,
    isis_tight: "bool | None" = None,
    isis_barcode: "bool | None" = None,
    isis_trailer_mm: "float | None" = None,
    isis_arrows: "bool | None" = None,
    isis_outline: "bool | None" = None,
    isis_corner_labels: "bool | None" = None,
    isis_strip_letters: str = "",
    isis_notes_band: "bool | None" = None,
    isis_notes_place: str = "",
    isis_notes_height_mm: "float | None" = None,
    isis_align: str = "",
    #: i1iSis only: the run's chart-note lines (and the settings line),
    #: printed in the trailer when no notes band holds them. No other
    #: instrument reads it.
    isis_trailer_lines: "tuple | list | None" = None,
    #: The Beta "Custom page size in inches or pixels, and high resolution"
    #: (#215, `workflow.page_output.support`): the sides as typed, and the
    #: unit of the resolution written into the TIFF. Both absent from every
    #: chart that does not use the Beta (`LayoutRecipe.build_kwargs`).
    page_size: "dict | None" = None,
    tiff_res_unit: str = "cm",
) -> ChartResult:
    """Full chart build: write ``out_base.ti2`` + page TIFF(s) + strip geometry.

    *label_rule* is how the strip and patch labels are made. ``"argyll"``
    (every new chart) labels exactly as ArgyllCMS does, and a pattern pair the
    readers could not read back is refused with
    :class:`~workflow.layout_engine.alphix.PatternRefused` before any file is
    written. ``"legacy"`` is ChromIQ's rule before 4.3.3-beta.7, for a redraw
    of a chart printed with it (Restore Used Chart): that chart is already on
    paper, so it is drawn again exactly as it was and never refused.

    ``out_base`` is a path stem; outputs are ``<stem>.ti2``, ``<stem>.tif``
    (or ``<stem>_NN.tif`` for multi-page) and ``<stem>.strips.json`` (exact
    per-strip pixel rects for the measure-tab highlighter).

    *cal_path* attaches a printer calibration: with *apply_cal* True (``-K``) the
    curves are applied to the PRINTED patch colours (the TIFF / PDF pixels)
    **and** embedded; with it False (``-I``) the calibration is only embedded.
    Either way the ``.ti2`` keeps the ``.ti1``'s own, uncalibrated device
    values, exactly as ``printtarg -K`` does (printtarg.c: ``ps_setcolor`` /
    ``tiff_setcolor`` calibrate a local ``cdev`` for the page, while the
    ``.ti2`` rows are written from ``cols[i].dev``). Those are the values
    chartread copies into the ``.ti3`` and colprof profiles against: the
    profile is of the CALIBRATED device, and ``applycal`` folds the curves in
    once. A ``.ti2`` carrying calibrated values made a profile of the raw
    printer, and ``applycal`` then calibrated it a second time.
    """
    from workflow.fd9.support import fd9_enabled
    # THE PAGE-OUTPUT BETA (#215). Its two values reach this function only
    # from a recipe the Beta wrote; with the Beta off they are refused with
    # words that name it, never drawn silently (the i1iO's rule).
    _page_px = None
    if page_size is not None or (tiff_res_unit or "cm") != "cm":
        from workflow.page_output import support as _po
        if not _po.page_output_enabled():
            from core.i18n import tr as _tr
            from workflow import measurement_messages as _mm
            raise _po.PageBetaOff(_tr(_mm._PAGE_BETA_OFF_REDRAW))
        page_size = _po.clean_page_size(page_size)
        if page_size is not None:
            _page_px = _po.page_pixels(page_size, dpi)
            # a side typed in pixels that this resolution makes shorter than
            # 1 mm or longer than 2000 mm is refused before anything is drawn
            # (re-review R3-a; the panel and Generate say it first)
            _why = _po.size_problem(page_size, dpi)
            if _why:
                raise _po.PageBudgetError(_why)
        tiff_res_unit = ("in" if tiff_res_unit == _po.RES_UNIT_IN else "cm")
    # An X-Rite i1iO chart (a Beta): the engine's own grid with the settings
    # an i1iO chart fixes (`workflow.i1io.chart.fixed_build_kwargs`), and its
    # marks and side file added below. Off, the engine refuses "IO2" as an
    # unknown instrument (`instruments._build_base`), as 4.3.32 did.
    from workflow.i1io.support import i1io_enabled, is_i1io_code
    _i1io = is_i1io_code(instrument) and i1io_enabled()
    _i1io_chart_text = chart_text
    if _i1io:
        from workflow.i1io import chart as _i1io_chart
        # What the person asked for (patch size, labels) is kept inside the
        # table's limits; everything else is the i1iO's own.
        _f = _i1io_chart.fixed_build_kwargs({
            "patch_w": patch_w, "patch_h": patch_h,
            "strip_gap": strip_gap, "inter_patch": inter_patch,
            "margins": margins, "spacer_mode": spacer_mode,
            "draw_indicators": draw_indicators,
            "row_indicators": row_indicators,
            "indicator_size_mm": indicator_size_mm,
            "spacer_width": spacer_width,
            # the label options (2026-11-13): the strip letters' pattern,
            # face, underline and place in their band
            "strip_pattern": strip_pattern,
            "indicator_font": indicator_font,
            "indicator_bold": indicator_bold,
            "indicator_italic": indicator_italic,
            "indicator_align": indicator_align,
            "underline_mode": underline_mode,
            "underline_thickness_mm": underline_thickness_mm,
            "underline_gap_mm": underline_gap_mm,
            "clip_border_width": clip_border_width,
            "clip_content_mode": clip_content_mode,
            _i1io_chart.ALIGN_KEY: i1io_align,
            _i1io_chart.CROSSES_KEY: i1io_crosses,
            _i1io_chart.CLIP_KEY: i1io_clip_border,
            # options open, defaults safe (Job D): what a person set
            "edge_spacers": edge_spacers, "max_strip": max_strip,
            "nolimit": nolimit, "offset_x": offset_x, "offset_y": offset_y,
            "helper_markers": helper_markers,
            "helper_marker_edge": helper_marker_edge,
            "helper_marker_len": helper_marker_len,
            "helper_markers_top_bottom": helper_markers_top_bottom,
            "strip_indicator_gap": strip_indicator_gap,
            "strip_label_offset_mm": strip_label_offset_mm,
            "strip_label_offset_x_mm": strip_label_offset_x_mm,
            "text_edge": text_edge,
            _i1io_chart.NUMBERS_EDGE_KEY: i1io_numbers_edge_mm,
            _i1io_chart.TEXT_ALIGN_KEY: i1io_text_align})
        _i1io_chart.sheet_size(paper)
        (patch_w, patch_h, pscale, sscale, spacer_on, spacer_mode,
         spacer_width, inter_patch, strip_gap, edge_spacers, margins,
         use_instrument_margins, layout_mode, patch_area_align,
         density, cm_stagger, max_strip, offset_x, offset_y,
         nolpcbord, nolimit, clip_content_mode, helper_markers, chart_text,
         stamp_command, side_stamp, strip_indicator_gap, text_edge_top,
         strip_label_offset_mm, strip_label_offset_x_mm, indicator_rotation,
         row_indicator_rotation) = (_f[k] for k in (
            "patch_w", "patch_h", "pscale", "sscale", "spacer_on",
            "spacer_mode", "spacer_width", "inter_patch", "strip_gap",
            "edge_spacers", "margins", "use_instrument_margins",
            "layout_mode", "patch_area_align",
            "density", "cm_stagger", "max_strip", "offset_x", "offset_y",
            "nolpcbord", "nolimit", "clip_content_mode", "helper_markers",
            "chart_text", "stamp_command", "side_stamp",
            "strip_indicator_gap", "text_edge_top", "strip_label_offset_mm",
            "strip_label_offset_x_mm", "indicator_rotation",
            "row_indicator_rotation"))
        _i1io_labels = _f[_i1io_chart.LABELS_KEY]
        _i1io_crosses = _f[_i1io_chart.CROSSES_KEY]
        _i1io_clip = _f[_i1io_chart.CLIP_KEY]
        if _i1io_clip:
            # the clip border's band, on the page's left edge, its content
            # clear of the crosses and inside the printable area
            # (`workflow.i1io.chart.fixed_build_kwargs`)
            clip_border_width = _f["clip_border_width"]
            clip_side = _f["clip_side"]
            text_edge = _f["text_edge"]
        # never above the i1iO's largest label size (review r3 M1)
        indicator_size_mm = _f["indicator_size_mm"]
        # the patch numbers beside the strips, clear of a printer's edge
        text_edge_clip = _f["text_edge_clip"]
        # the strip letters are the i1iO's own (`draw_furniture`); the
        # engine draws the patch numbers only
        draw_indicators = _f["draw_indicators"]
        row_indicators = _f["row_indicators"]
        hflag = False          # an i1iO grid is never a honeycomb
        # THE LABEL PATTERNS ARE THE RECIPE'S (2026-11-13): the `.ti2`, the
        # patch numbers, the strip letters (`draw_furniture`), the aiming
        # names and the side file all take them, so "C7" still means the
        # same everywhere; a pair the readers could not read back is refused
        # below, as on every chart.
        # Manual's "Sheet text" goes on the turned text line (`draw_furniture`),
        # where it costs no patch, not under the patches, in its own face
        # and size (2026-11-13; the name and the logo keep theirs).
        _i1io_sheet_text = _i1io_chart_text
        _i1io_text_style = _i1io_chart.text_style_of({
            "chart_text_font": chart_text_font,
            _i1io_chart.TEXT_BOLD_KEY: i1io_text_bold,
            "chart_text_italic": chart_text_italic,
            "chart_text_size_mm": chart_text_size_mm})
    # An X-Rite i1iSis chart (a Beta): the engine's own grid at the place
    # and with the furniture i1Profiler uses (`workflow.isis.chart`). Off,
    # the engine refuses "XRISIS" as an unknown instrument.
    from workflow.isis.support import isis_enabled, is_isis_code
    _isis = is_isis_code(instrument) and isis_enabled()
    if _isis:
        from workflow.isis import chart as _isis_chart
        _isis_kw = {
            "paper": paper, "patch_w": patch_w, "patch_h": patch_h,
            "margins": margins, "offset_x": offset_x, "offset_y": offset_y,
            "max_strip": max_strip, "stamp_command": stamp_command,
            _isis_chart.MODEL_KEY: isis_model,
            _isis_chart.HEADER_KEY: isis_header_mm,
            _isis_chart.TIGHT_KEY: isis_tight,
            _isis_chart.BARCODE_KEY: isis_barcode,
            _isis_chart.TRAILER_KEY: isis_trailer_mm,
            _isis_chart.ARROWS_KEY: isis_arrows,
            _isis_chart.OUTLINE_KEY: isis_outline,
            _isis_chart.CORNERS_KEY: isis_corner_labels,
            _isis_chart.LETTERS_KEY: isis_strip_letters,
            _isis_chart.BAND_KEY: isis_notes_band,
            _isis_chart.BAND_PLACE_KEY: isis_notes_place,
            _isis_chart.BAND_HEIGHT_KEY: isis_notes_height_mm,
            _isis_chart.ALIGN_KEY: isis_align,
            # the engine's own label controls and layout mode, which the
            # i1iSis chart honours in its own zones (`workflow.isis.chart`)
            "draw_indicators": draw_indicators,
            "row_indicators": row_indicators,
            "indicator_font": indicator_font,
            "indicator_size_mm": indicator_size_mm,
            "indicator_bold": indicator_bold,
            "indicator_italic": indicator_italic,
            "indicator_rotation": indicator_rotation,
            "row_indicator_rotation": row_indicator_rotation,
            "indicator_align": indicator_align,
            "underline_mode": underline_mode,
            "underline_thickness_mm": underline_thickness_mm,
            "underline_gap_mm": underline_gap_mm,
            "strip_label_offset_mm": strip_label_offset_mm,
            "strip_label_offset_x_mm": strip_label_offset_x_mm,
            "layout_mode": layout_mode, "area_method": area_method,
            "area_cols": area_cols, "area_rows": area_rows,
            "area_ratio": area_ratio, "area_min_patch": area_min_patch,
            _isis_chart.NOTES_LINES_KEY: tuple(isis_trailer_lines or ())}
        # Refused before anything is read or written when no page of this
        # size can carry an i1iSis chart at all.
        _f = _isis_chart.fixed_build_kwargs(_isis_kw)
        _isis_sheet_text = chart_text
        _isis_stamp = stamp_command
        # the notes band's content, as the clip border's content box says
        # ("off" there means the band's own default, the Notes box)
        clip_content_mode_asked = (clip_content_mode
                                   if clip_content_mode not in (None, "", "off")
                                   else "notes")
        (patch_w, patch_h, pscale, sscale, spacer_on, spacer_mode,
         spacer_width, inter_patch, strip_gap, edge_spacers,
         use_instrument_margins, layout_mode, patch_area_align, density,
         cm_stagger, nolpcbord, nolimit, clip_content_mode, helper_markers,
         chart_text, stamp_command, side_stamp, strip_indicator_gap,
         draw_indicators, row_indicators, underline_mode, hflag,
         strip_label_offset_mm, strip_label_offset_x_mm,
         indicator_rotation, row_indicator_rotation) = (_f[k] for k in (
            "patch_w", "patch_h", "pscale", "sscale", "spacer_on",
            "spacer_mode", "spacer_width", "inter_patch", "strip_gap",
            "edge_spacers", "use_instrument_margins", "layout_mode",
            "patch_area_align", "density", "cm_stagger", "nolpcbord",
            "nolimit", "clip_content_mode", "helper_markers", "chart_text",
            "stamp_command", "side_stamp", "strip_indicator_gap",
            "draw_indicators", "row_indicators", "underline_mode", "hflag",
            "strip_label_offset_mm",
            "strip_label_offset_x_mm", "indicator_rotation",
            "row_indicator_rotation"))
    if instrument == "FD9" and fd9_enabled():
        from workflow.fd9.chart import build_chart as build_fd9
        return build_fd9(ti1_path, out_base, paper=paper, dpi=dpi,
                         randomize=randomize, seed=seed, bit16=bit16,
                         cal_path=cal_path, apply_cal=apply_cal, export_pdf=export_pdf,
                         ramps_per_strip=ramps_per_strip, patch_mm=patch_w or 8.0,
                         patch_height_mm=patch_h,
                         gap_mm=(fd9_gap if fd9_gap is not None else inter_patch if inter_patch is not None else 1.0),
                         strip_gap_mm=(strip_gap if strip_gap is not None else fd9_gap),
                         compression=compression, sheet_project=project,
                         sheet_run=fd9_run, clip_border=fd9_clip_border,
                         sheet_description=rundescription,
                         clip_content=(clip_content_mode
                                       if clip_content_mode not in (None, "", "off", "example")
                                       else "notes"),
                         clip_text=clip_text,
                         clip_options=dict(
                             font_family=clip_text_font,
                             text_size_mm=clip_text_size_mm,
                             image_path=clip_image_path,
                             image_rotation=clip_image_rotation,
                             image_scale=clip_image_scale,
                             image_offset_x_mm=clip_image_offset_x,
                             image_offset_y_mm=clip_image_offset_y))
    target = ti1_reader.read_ti1(ti1_path)
    # What goes on paper. Differs from `target` only under -K.
    printed = target

    cal = None
    if cal_path is not None:
        from . import calibration
        cal = calibration.read_cal(cal_path)
        # -K AND -I: printtarg refuses both for a calibration made for other
        # inks, and an RGB chart carrying a CMYK calibration is no use to
        # anything downstream (#182 5956560815).
        calibration.check_matches(target, cal)
    spacer_on = spacer_on and spacer_mode != "none"   # "none" ⇒ no gap
    # Build the Geom through the one chokepoint so area-first patch sizing and the
    # furniture reservations (label band, bottom sheet text / stamp) match every
    # capacity estimate exactly (#93). A function of the patch count, because
    # area-first sizes the patches from it and the calibration ramps below
    # change it.
    def _geom_for(npat: int):
        return instruments.geom_from_build_kwargs({
        # the i1iO's labels as asked for, past the fixed settings above
        **({_i1io_chart.LABELS_KEY: _i1io_labels,
            _i1io_chart.ALIGN_KEY: patch_area_align,
            _i1io_chart.CROSSES_KEY: _i1io_crosses,
            _i1io_chart.CLIP_KEY: _i1io_clip,
            # the patch numbers' distance (review 3, item 3): without it
            # the geometry re-derived the default and the numbers never moved
            _i1io_chart.NUMBERS_EDGE_KEY: i1io_numbers_edge_mm}
           if _i1io else {}),
        "instrument": instrument, "paper": paper, "hflag": hflag,
        "hex_flat_top": hex_flat_top,
        "density": density, "cm_stagger": cm_stagger,
        "spacer_on": spacer_on, "pscale": pscale,
        "sscale": sscale, "border": border, "margins": margins,
        "patch_w": patch_w, "patch_h": patch_h, "spacer_width": spacer_width,
        "inter_patch": inter_patch, "strip_gap": strip_gap, "max_strip": max_strip,
        "strip_indicator_gap": strip_indicator_gap,
        "row_indicators": row_indicators, "offset_x": offset_x,
        "offset_y": offset_y, "nolpcbord": nolpcbord, "nolimit": nolimit,
        "clip_border_width": clip_border_width, "clip_side": clip_side,
        "clip_content_mode": clip_content_mode,
        "text_edge_top": text_edge_top, "text_edge_clip": text_edge_clip,
        # THE RULER HELPER MARKERS ARE GEOMETRY, AND THIS DICT LEFT THEM OUT.
        #
        # `instruments.GEOM_BUILD_KEYS` lists them, `build()` takes them and
        # `geom_from_build_kwargs` copies them onto the `Geom` — but only from
        # the dict it is handed, and this one is assembled by hand. Every key
        # missing here reads as its default, so the geometry that lays out the
        # REAL sheet was built with `helper_markers=False`, a 0.0 mm distance
        # and a 0.0 mm dash, while the same markers were passed to
        # `render_pages` below and drawn. The whole of #182's marker reserve
        # therefore reached the panel, the capacity estimate and the note
        # stamper (they all start from `LayoutRecipe.build_kwargs()`, which
        # carries the keys) and reached the sheet nowhere.
        #
        # Measured on screen, ColorMunki / A4 / 200 dpi, markers at 4.0 mm with
        # a 2.0 mm dash and "Clip" / "T" at 4.0, each element isolated against
        # a control sheet with only that element switched off:
        #
        # * the clip band's text was printed at 4.70 mm from the paper edge,
        #   bit-identical to the same sheet with the markers OFF, with 917
        #   pixels of it inside the 4.0 to 6.0 mm dash band — the collision
        #   Knut reported, whose fix in `geometry.clip_area_mm` could not act
        #   because `geom.helper_markers` was False;
        # * the strip letters' ink began 5.97 mm down with the markers on and
        #   5.97 mm down with them off, while `geometry.strip_label_reserve_mm`
        #   answers 7.0 mm for that recipe;
        # * the row indicator labels' leftmost ink was 9.65 mm in with the
        #   markers on and 9.65 mm with them off, while the panel quoted a
        #   7.0 mm floor and a 17.38 mm left margin against the 4.0 / 14.38 the
        #   sheet used.
        #
        # `_engine_total_patches` builds its geometry straight from
        # `build_kwargs()`, so the patch-count estimate reserved the marker
        # room this build did not, which is the same disagreement one level up.
        "helper_markers": helper_markers,
        "helper_marker_edge": helper_marker_edge,
        "helper_marker_len": helper_marker_len,
        "helper_markers_top_bottom": helper_markers_top_bottom,
        "helper_markers_sides": helper_markers_sides,
        "use_instrument_margins": use_instrument_margins,
        "edge_spacers": edge_spacers,
        "patch_area_align": patch_area_align, "layout_mode": layout_mode,
        "area_method": area_method, "area_cols": area_cols,
        "area_rows": area_rows, "area_ratio": area_ratio,
        "area_min_patch": area_min_patch,
        # The chart's actual patch count, so area-first sizes the patches to FILL
        # the box with exactly this many (a fixed patch set still fills the area,
        # not just packs at the minimum) (Knut). Ignored by patch-first.
        "area_target_count": npat,
        "area_default_w": area_default_w, "area_default_h": area_default_h,
        "dpi": dpi, "draw_indicators": draw_indicators,
        "indicator_font": indicator_font, "indicator_size_mm": indicator_size_mm,
        "indicator_bold": indicator_bold, "indicator_italic": indicator_italic,
        "indicator_rotation": indicator_rotation, "underline_mode": underline_mode,
        **({"row_indicator_rotation": int(row_indicator_rotation)}
           if int(row_indicator_rotation or 0) % 360 else {}),
        "underline_thickness_mm": underline_thickness_mm,
        "underline_gap_mm": underline_gap_mm,
        # The geometry needs the label OFFSET too, and only for one thing: a
        # turned honeycomb's patch block has to start below the labels' ink, and
        # this is what moves that ink. Without it a +3 mm offset printed the
        # letters 2.46 mm into the first row of hexagons. Read by
        # `raster._furniture_reserves_mm` alone, so no other layout moves.
        "strip_label_offset_mm": strip_label_offset_mm,
        "chart_text": chart_text, "stamp_command": stamp_command,
        "side_stamp": side_stamp,
        "chart_text_size_mm": chart_text_size_mm,
        "text_edge": text_edge,
        # WHAT THE CLIP BORDER PRINTS, so the row labels can be held 1 mm
        # clear of it rather than clear of the whole border (Basti,
        # 2026-10-25, `raster.clip_content_reach_mm`). Left out, the build
        # would measure an empty border while the panel measured the real one.
        "clip_text": clip_text, "clip_text_font": clip_text_font,
        "clip_text_size_mm": clip_text_size_mm,
        "clip_image_path": clip_image_path,
        "clip_image_rotation": clip_image_rotation,
        "clip_image_scale": clip_image_scale,
        "clip_image_offset_x": clip_image_offset_x,
        "clip_image_offset_y": clip_image_offset_y,
        "clip_flip_180": clip_flip_180,
        "project": project, "rundescription": rundescription,
        "chart_date": chart_date,
        # …AND WHICH CLIP-BORDER RULE THE RECIPE WAS SAVED UNDER (Basti,
        # 2026-10-25): a recipe saved before 4.3.14 lays out as it did.
        **({} if clip_border_free_space else
           {"clip_border_free_space": False}),
        # an i1iSis chart's own options LAST, as the person asked for them
        # (patch size, layout mode, labels), so the margins hold its grid
        **({**_isis_kw, "area_target_count": npat} if _isis else {})})
    w_mm, h_mm = papers.dimensions_mm(paper)
    if _page_px is not None:
        # A side typed in pixels IS its pixel count: the page in millimetres
        # is that count at this resolution, unrounded, so every position on
        # it is measured from the same page the pixels make
        # (`page_output.support`, THE PIXEL RULE).
        w_mm, h_mm = _po.page_mm(page_size, dpi)
    geom = _geom_for(len(target.patches))
    try:
        layout = geometry.compute(geom, w_mm, h_mm, len(target.patches))
    except geometry.LayoutError as exc:
        if not _i1io:
            # NO ROOM, SAID IN WORDS (4.3.57): the margins have no cap any
            # more, so the page is what refuses, and the window names the
            # margins that leave no room (`geometry.no_room_reason`).
            try:
                exc.plain = geometry.no_room_reason(
                    geom, w_mm, h_mm, len(target.patches))
            except Exception:   # noqa: BLE001 - the engine's words remain
                exc.plain = None
            raise
        # A SHEET TOO SMALL FOR ONE STRIP, said in words (review 5, item 7):
        # any size inside the table's reach may be chosen now
        from workflow import measurement_messages as _mm
        from core.i18n import tr as _tr
        raise _i1io_chart.I1ioSheetRefused(_tr(_mm._I1IO_SHEET_TOO_SMALL))

    def _refuse_unreadable_patterns(layout_now) -> None:
        if label_rule == permutation.LEGACY:
            return
        # ArgyllCMS'S LABELS, SO ARGYLLCMS'S LIMITS (forum report, 2026-10-03;
        # Knut, #182 5965589190). A pattern pair the readers could not read
        # back (too few labels, halves that run together) is refused before
        # anything is written. A redraw of a chart printed with the old rule
        # passes "legacy" and is drawn exactly as it was printed.
        from . import alphix
        problem = alphix.check_patterns(
            strip_pattern, patch_pattern,
            alphix.strips_of(layout_now.total_patches,
                             layout_now.steps_in_pass),
            layout_now.steps_in_pass)
        if problem is not None:
            raise alphix.PatternRefused(problem)

    def _isis_check(layout_now, npat: int):
        """The i1iSis chart of *npat* patches, checked, and the engine's
        grid proved to be that chart's grid (the margins put it there)."""
        _o, _g, _s = _isis_chart.layout_for(
            npat, w_mm, h_mm, {**_isis_kw, _isis_chart.COUNT_KEY: npat})
        _per = (layout_now.patches_per_page // layout_now.steps_in_pass
                if layout_now.steps_in_pass else 0)
        if (layout_now.steps_in_pass, _per, layout_now.pages,
                layout_now.padding) != (_g.R, _g.C, _g.P, 0):
            raise RuntimeError(
                f"i1iSis grid mismatch: engine {layout_now.steps_in_pass} "
                f"rows x {_per} columns x {layout_now.pages} pages, chart "
                f"{_g.R} x {_g.C} x {_g.P}")
        return _s

    # Refused BEFORE a calibration's ramps rewrite the .ti1 on disk, and again
    # on the layout those ramps settle on (it can have a different strip count).
    _refuse_unreadable_patterns(layout)
    if _isis:
        _isis_sheet = _isis_check(layout, len(target.patches))
    if _i1io:
        # The table must be able to read this layout at all: refused BEFORE
        # anything is written (and again below if calibration ramps re-lay it).
        _i1io_chart.check_sheet(geom, layout, w_mm, h_mm,
                                        crosses=_i1io_crosses)

    # EACH INK'S RAMP ON ITS OWN STRIP (#182, Knut 5965186237). Only for a
    # calibration build, and only when the .ti1 is targen's pure ramp set:
    # anything else keeps its rows. The .ti1 is rewritten on disk as well, so
    # the patch set, the .ti2 and the sheet all say the same thing.
    ramps_arranged = 0
    if ramps_per_strip:
        from . import calibration_ramps as _cr
        _ramps = _cr.ramps_in_ti1(ti1_path)
        if _ramps is not None and _ramps.is_targen_order:
            def _steps(n: int) -> int:
                return geometry.compute(_geom_for(n), w_mm, h_mm,
                                        n).steps_in_pass

            def _count(steps: int) -> int:
                return len(_cr.arranged_order(_ramps, steps) or [])

            # None when no strip length agrees with its own count: targen's
            # order is then kept, rather than ramps arranged for one strip
            # length and laid out on another.
            _fit = _cr.settle(_count, _steps, len(target.patches))
            _new = (_cr.arrange_ti1(ti1_path, _fit[1], total=_fit[0])
                    if _fit is not None else None)
            if _fit is None:
                import logging
                logging.getLogger(__name__).info(
                    "calibration ramps left in targen's order: no strip "
                    "length agrees with the count it lays out (area-first)")
            if _new is not None:
                ramps_arranged = _new - len(target.patches)
                target = ti1_reader.read_ti1(ti1_path)
                printed = target
                geom = _geom_for(len(target.patches))
                layout = geometry.compute(geom, w_mm, h_mm,
                                          len(target.patches))
                _refuse_unreadable_patterns(layout)
                if _i1io:
                    _i1io_chart.check_sheet(geom, layout, w_mm, h_mm,
                                        crosses=_i1io_crosses)
                if _isis:
                    _isis_sheet = _isis_check(layout, len(target.patches))
    if cal is not None and apply_cal:
        from . import calibration
        printed = calibration.apply_to_target(target, cal)
    if seed is None:
        seed = permutation.pick_seed()

    # `out_base` IS a stem. A project name may contain a dot ("…-w10.0mm",
    # "…-TC9.18-…"), so it must never go through with_suffix() or .stem — see
    # core/stem_paths.py for what that costs. The ONE extension a caller may
    # legitimately hand us is the .ti1 it just built, and that is removed BY
    # NAME rather than by guessing which tail is an extension: an allow-list of
    # "extensions" is wrong for every project name that ends in one of them
    # (".ps", ".pdf", ".cht", ".json" are all legal names — `_WORKFILE_EXTS` in
    # core/file_manager.py does not block them). Everything below concatenates.
    stem = without_ext(out_base, ".ti1")

    # THE MEMORY BUDGET (the page-output Beta, #215): a page too large to
    # draw is refused HERE, before any page is drawn or file of this build
    # written, with its pixel count and what to reduce
    # (`page_output.support.budget_problem`, with the measurements it rests
    # on). Only with the Beta on, and only for a chart that uses something
    # only the Beta allows (review F7): every chart 4.3.42 can make is drawn
    # with the Beta on exactly as with it off.
    from workflow.page_output.support import page_output_enabled
    from workflow.page_output import support as _po
    if page_output_enabled() and _po.needs_budget(
            page_size=page_size, dpi=dpi, paper=paper):
        _bw, _bh = (_page_px if _page_px is not None else
                    (_po.pixels_of(w_mm, dpi), _po.pixels_of(h_mm, dpi)))
        _device = target.n_channels >= 4 or raster.is_cmy_target(target)
        _why = _po.budget_problem(_bw, _bh, layout.pages,
                                  inks=target.n_channels, device=_device,
                                  bit16=bool(bit16))
        if _why:
            raise _po.PageBudgetError(_why)

    media = target.media_patch()
    white_point = media[1] if any(media[1]) else ti2_writer.DEFAULT_WHITE_POINT
    ti2_path = artefact(stem, ".ti2")
    # ONE patch order for every file of the chart: the seed's, and for an
    # i1iO chart without crosses clearly visible patches in the corners
    # (`workflow.i1io.chart.sheet_slots`). None for every other chart, which
    # is then written exactly as before.
    _slots = None
    _ti2_geom = geom
    if _i1io:
        _slots = _i1io_chart.sheet_slots(target, layout, geom, w_mm, h_mm,
                                         seed, randomize, _i1io_crosses)
        # Which pages carry the crosses: all of them, or without them only
        # a page whose corner patches cannot be aimed at (`page_crosses`).
        _i1io_pages = _i1io_chart.page_crosses(target, layout, geom, w_mm,
                                               h_mm, _slots, _i1io_crosses)
        _i1io_warnings = list(_i1io_chart.check_sheet(
            geom, layout, w_mm, h_mm, crosses=_i1io_pages))
        # 4.3.57 (item 30): pages aimed at corner patches that lie close
        _i1io_warnings += _i1io_chart.corner_warnings(geom, layout, w_mm, h_mm,
                                                      _i1io_pages)
        _i1io_warnings += _i1io_chart.option_warnings(_f)
        # "Label offset" X held as on every chart, and the letters and the
        # numbers where the options put them: said, or refused when wholly
        # off the sheet (review 3, items 2 and 5)
        _i1io_labels, _i1io_xs = _i1io_chart.held_letters(
            geom, layout, w_mm, h_mm, dpi, _i1io_labels, label_rule)
        for _why in _i1io_chart.furniture_warnings(
                geom, layout, w_mm, h_mm, dpi, _i1io_labels, _i1io_pages,
                label_rule):
            if _why not in _i1io_warnings:
                _i1io_warnings.append(_why)
        # what the person aims at, recorded (`chart.aim_recorded`), and on
        # every page the names of the three patches when they are patches
        from dataclasses import replace as _replace
        _ti2_geom = _replace(geom, extra_keywords=tuple(geom.extra_keywords) + (
            (_i1io_chart.AIM_KEYWORD, _i1io_chart.aim_of(_i1io_crosses)),
            (_i1io_chart.AIM_DIGITS_KEYWORD,
             "yes" if any(_i1io_pages) else "no"),)
            + (() if _i1io_crosses else (
                (_i1io_chart.AIM_PATCHES_KEYWORD,
                 _i1io_chart.aim_patches_value(
                     geom, layout, w_mm, h_mm, _i1io_pages,
                     (strip_pattern, patch_pattern, label_rule))),)))
    if _isis:
        from dataclasses import replace as _replace
        _ti2_geom = _replace(geom, extra_keywords=tuple(geom.extra_keywords) + (
            (_isis_chart.MODEL_KEYWORD, _isis_sheet.opts.model),))
    # R7 (4.3.39): no near-black patch straight next to a near-white one on
    # a chart in fixed order. Through the same one slot list as the i1iO's
    # order, so the .ti2, the pages, the side files and the .cht agree; None
    # when nothing has to move, and the chart is then written as before.
    from .instruments import finds_patches_by_edges as _finds_patches_by_edges
    _nb_moves: "list[tuple[str, str]]" = []
    _nb_left = 0
    _nb_count = 0
    if (avoid_dark_light_neighbours and not randomize and _slots is None
            and not ramps_per_strip and not _i1io and not _isis
            and _finds_patches_by_edges(instrument)):
        from . import neighbour_order as _nb
        _all = list(target.patches) + [media] * layout.padding
        _xyzs = [xyz for _dev, xyz in _all]
        # judged against the paper the patch set names, not its lightest
        # patch (review of 4.3.39)
        _wy = _nb.white_y_of_ti1(ti1_path)
        # a spacer drawn between two patches separates them: nothing is a
        # neighbour pair then, and nothing moves (review of 4.3.39)
        _separated = bool(spacer_on and float(geom.pspa or 0) > 0
                          and str(spacer_mode or "none") != "none")
        if _separated:
            _nb_slots, _mv = None, []
            _nb_left = 0
        else:
            _nb_slots, _mv = _nb.arrange(_xyzs, layout.total_patches,
                                         layout.steps_in_pass,
                                         len(target.patches),
                                         layout.patches_per_page, _wy)
            _nb_left = _nb.remaining_pairs(_xyzs, _nb_slots,
                                           layout.total_patches,
                                           layout.steps_in_pass, _wy)
        _nb_count = (sum(1 for i, sl in enumerate(_nb_slots) if i != sl)
                     if _nb_slots is not None else 0)
        if _nb_slots is not None:
            _slots = _nb_slots

            def _loc(slot: int) -> str:
                return permutation.location_label(
                    slot, layout.steps_in_pass, strip_pattern, patch_pattern,
                    label_rule)
            _nb_moves = [(_loc(m.slot_b), _loc(m.slot_a)) for m in _mv]
    ti2_writer.write_ti2(
        ti2_path, target.patches, target.device_fields, layout, _ti2_geom,
        color_rep=target.color_rep, seed=seed, randomize=randomize,
        strip_pattern=strip_pattern, patch_pattern=patch_pattern,
        paper_w_mm=w_mm, paper_h_mm=h_mm, media=media, white_point=white_point,
        ink_limit=target.ink_limit, label_rule=label_rule,
        **({"slots": _slots} if _slots is not None else {}),
    )
    if cal is not None:  # embed the calibration table (-K and -I both embed)
        from . import calibration
        with open(ti2_path, "a", encoding="utf-8") as fh:
            fh.write("\n" + calibration.cal_table_text(cal))

    # Human-friendly placeholder values for {project}/{instrument}/{paper}/… in
    # chart text, clip text and the stamp. {page} is resolved per page inside
    # render_pages (it needs the page index), so it's not in this dict. (#93)
    _patch_size = laid_out_patch_size_mm(geom, w_mm, h_mm, layout, dpi)
    _ctx = text_placeholder_context(
        project=project or Path(out_base).name,
        rundescription=rundescription, instrument=instrument, paper=paper,
        dpi=dpi, patches=layout.total_patches, pages=layout.pages, seed=seed,
        chart_date=chart_date, randomize=randomize,
        # `{patchsize}` (4.3.45): the patch as laid out, after any fitting
        patch_size_mm=_patch_size)
    stamp_text = (stamp_summary_line(instrument, paper, dpi,
                                     layout.total_patches, seed,
                                     randomize=randomize)
                  if (stamp_command or (_isis and _isis_stamp)) else "")
    # an i1iSis chart draws the summary in its own trailer (draw_furniture)
    _isis_stamp_text = stamp_text if _isis else ""
    if _isis:
        stamp_text = ""
    def _to_rgb(c):
        if isinstance(c, str):
            h = c.lstrip("#")
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        return tuple(int(v) for v in c)
    _palette = [_to_rgb(c) for c in spacer_palette] if spacer_palette else None
    _overrides = ({int(k): _to_rgb(v) for k, v in spacer_overrides.items()}
                  if spacer_overrides else None)
    render = raster.render_pages(
        printed, layout, geom, seed=seed, randomize=randomize,
        **({"page_px": _page_px} if _page_px is not None else {}),
        paper_w_mm=w_mm, paper_h_mm=h_mm, dpi=dpi, strip_pattern=strip_pattern,
        patch_pattern=patch_pattern, label_rule=label_rule,
        spacer_mode=spacer_mode, spacer_palette=_palette,
        spacer_overrides=_overrides, edge_spacers=edge_spacers,
        draw_indicators=draw_indicators,
        indicator_font=indicator_font, indicator_size_mm=indicator_size_mm,
        indicator_bold=indicator_bold, indicator_italic=indicator_italic,
        indicator_rotation=indicator_rotation,
        indicator_align=indicator_align,
        underline_mode=underline_mode,
        underline_thickness_mm=underline_thickness_mm,
        underline_gap_mm=underline_gap_mm,
        strip_label_offset_mm=strip_label_offset_mm,
        strip_label_offset_x_mm=strip_label_offset_x_mm,
        chart_text=chart_text, chart_text_font=chart_text_font,
        chart_text_size_mm=chart_text_size_mm, chart_text_bold=chart_text_bold,
        chart_text_italic=chart_text_italic,
        chart_text_align=chart_text_align, stamp_text=stamp_text,
        helper_markers=helper_markers,
        helper_marker_edge_mm=helper_marker_edge,
        helper_marker_len_mm=helper_marker_len,
        helper_marker_per_patch=helper_marker_per_patch,
        helper_markers_top_bottom=helper_markers_top_bottom,
        helper_markers_sides=helper_markers_sides,
        text_edge_mm=text_edge,
        clip_content_mode=clip_content_mode, clip_text=clip_text,
        clip_text_font=clip_text_font, clip_text_size_mm=clip_text_size_mm,
        clip_image_path=clip_image_path,
        clip_image_rotation=clip_image_rotation, clip_image_scale=clip_image_scale,
        clip_image_offset_x_mm=clip_image_offset_x,
        clip_image_offset_y_mm=clip_image_offset_y,
        clip_flip_180=clip_flip_180,
        text_ctx=_ctx,
        # CMYK / CMYK+N targets get a device-native separated TIFF (Tier D, #72);
        # RGB/CMY/Gray keep the exact display-RGB raster. n>=4 ⇒ the display path
        # would only approximate the ink values, so collect the real device grid.
        # A vector-PDF export also needs the collected display list (#72).
        # 4.3.5 B2: a CMY chart too. It was an RGB TIFF of the inverted ink
        # values (255 - ink), which every printing path sent as RGB colours;
        # printtarg writes it as CMYK with K = 0, and so does the engine now.
        collect_device_geom=(target.n_channels >= 4 or export_pdf
                             or raster.is_cmy_target(target)),
        **({"slots": _slots} if _slots is not None else {}),
    )
    if _i1io:
        # The marks, the arrow, the page and the name, after the check that
        # the table can read this layout at all, and before anything is saved.
        _i1io_chart.draw_furniture(render, w_mm, h_mm, dpi,
                                   name=project or Path(out_base).name,
                                   geom=geom, layout=layout,
                                   labels=_i1io_labels,
                                   patterns=(strip_pattern, patch_pattern,
                                             label_rule),
                                   sheet_text=_i1io_sheet_text,
                                   text_ctx=_ctx, crosses=_i1io_pages,
                                   text_style=_i1io_text_style,
                                   text_align=_i1io_chart.text_align_of(_f))
    _isis_warnings: list = []
    if _isis:
        # The bar, the diamonds, the arrows, the outline, the labels, the
        # barcode and the notes band, after the check that an i1iSis can read
        # this layout at all, and before anything is saved.
        _isis_name = project or Path(out_base).name
        # THE BARCODE CARRIES THE .txf's TitleString, the chart's file name
        # (review of a7ca1489e, M2: "My Printer Glossy" in the barcode,
        # "My-Printer-Glossy" in the .txf); the name line keeps the
        # project's own name
        _isis_title = Path(out_base).name
        _isis_left_off = _isis_chart.draw_furniture(
            render, _isis_sheet, dpi, name=_isis_name,
            sheet_text=_isis_sheet_text,
            patterns=(strip_pattern, patch_pattern, label_rule),
            title=_isis_title,
            stamp_text=_isis_stamp_text,
            band=dict(mode=clip_content_mode_asked, text=clip_text,
                      font_family=clip_text_font, ctx=_ctx,
                      text_size_mm=clip_text_size_mm,
                      image_path=clip_image_path,
                      image_rotation=clip_image_rotation,
                      image_scale=clip_image_scale,
                      image_offset_x_mm=clip_image_offset_x,
                      image_offset_y_mm=clip_image_offset_y,
                      flip=clip_flip_180),
            layout=layout)
        _isis_warnings = [_isis_chart.keep_out_message(w)
                          for w in _isis_left_off]
        # more pages than the paper needs (3000 patches / 660 mm): said
        _isis_more = _isis_chart.extra_page_message(
            _isis_chart.extra_page_reasons(layout.total_patches, w_mm, h_mm,
                                           _isis_sheet.opts),
            _isis_sheet.grid.P)
        if _isis_more:
            _isis_warnings.append(_isis_more)
    # The file's resolution in pixels per inch, only when asked for (the
    # page-output Beta): every other chart is written exactly as before.
    _res_kw = ({"res_unit": "in"} if (tiff_res_unit or "cm") == "in" else {})
    if target.n_channels >= 4:
        device_pages = raster.build_device_pages(render, printed, bit16=bit16)
        tiff_paths = raster.save_separated_tiffs(
            device_pages, artefact(stem, ".tif"), dpi=dpi,
            ink_names=raster.ink_names_from_fields(target.device_fields),
            compression=compression, **_res_kw)
    elif raster.is_cmy_target(target):
        device_pages = [raster.cmy_with_empty_k(a) for a in
                        raster.build_device_pages(render, printed, bit16=bit16)]
        tiff_paths = raster.save_separated_tiffs(
            device_pages, artefact(stem, ".tif"), dpi=dpi,
            ink_names=raster.ink_names_from_fields(target.device_fields),
            compression=compression, **_res_kw)
    else:
        tiff_paths = raster.save_tiffs(render.images, artefact(stem, ".tif"),
                                       dpi=dpi, bit16=bit16, compression=compression,
                                       **_res_kw)
    pdf_path: Path | None = None
    if export_pdf:
        from . import vector_pdf
        pdf_path = vector_pdf.save_vector_pdf(
            render, printed, artefact(stem, ".pdf"),
            paper_w_mm=w_mm, paper_h_mm=h_mm, dpi=dpi)

    rects = geometry.strip_rects_px(geom, w_mm, h_mm, layout, dpi)
    patch_rects = geometry.patch_rects_px(geom, w_mm, h_mm, layout, dpi,
                                          strip_pattern, patch_pattern,
                                          label_rule=label_rule)
    strips_path = artefact(stem, ".strips.json")
    strips_path.write_text(json.dumps({
        "dpi": dpi, "paper_mm": [w_mm, h_mm],
        "steps_in_pass": layout.steps_in_pass, "strip_pattern": strip_pattern,
        # BOTH patterns, or the row band cannot be reproduced. The sidecar
        # recorded only the strip pattern, so a restored chart could not say
        # what its own row labels were -- and now that the band follows the
        # chart's patch pattern (K8), that is the difference between a sheet
        # whose labels match its .ti2 and one whose labels are a guess.
        "patch_pattern": patch_pattern,
        # Which rule made the labels: "argyll" for every chart from 4.3.3-
        # beta.7 on, "legacy" for a redraw of one printed before it.
        "label_rule": label_rule,
        "label_band_bottom_px": render.label_band_bottom_px,
        "patch_ink_top_px": render.patch_ink_top_px,
        "strips": rects, "patches": patch_rects,
    }, indent=2), encoding="utf-8")

    if _i1io:
        _i1io_chart.write_side_file(
            artefact(stem, ".i1io.json"), geom=geom, layout=layout, w=w_mm,
            h=h_mm, paper=paper, dpi=dpi, seed=seed, randomize=randomize,
            strip_pattern=strip_pattern, patch_pattern=patch_pattern,
            label_rule=label_rule, designed=len(target.patches),
            labels=_i1io_labels, name=project or Path(out_base).name,
            sheet_text=_i1io_sheet_text, text_ctx=_ctx,
            crosses=_i1io_pages, slots=_slots,
            clip_content=clip_content_mode if _i1io_clip else "off",
            text_style=_i1io_text_style,
            text_align=_i1io_chart.text_align_of(_f))
        # A NAME LINE WITH NO PAPER LEFT IS SAID, never dropped silently
        # (the whole-workflow drive: crosses off, a small right margin and
        # a strip cap left no free paper beside the last strip)
        try:
            _pages = json.loads(artefact(stem, ".i1io.json").read_text(
                encoding="utf-8")).get("pages") or []
        except (OSError, ValueError):
            _pages = []
        _lost = [pg for pg in _pages
                 if not (pg.get("text_line") or {}).get("text")]
        if _lost:
            from workflow import measurement_messages as _mm
            from core.i18n import tr as _tr
            # with the crosses on the sheet is simply too small for it
            # (review 5, item 7: any size inside the reach)
            _why = _tr(_mm._I1IO_LINE_LEFT_OFF_SMALL
                       if any(pg.get("aim") == "crosses" for pg in _lost)
                       else _mm._I1IO_LINE_LEFT_OFF)
            if _why not in _i1io_warnings:
                _i1io_warnings.append(_why)

    if _isis:
        _isis_chart.write_side_file(
            artefact(stem, ".isis.json"), _isis_sheet, paper=paper,
            name=project or Path(out_base).name,
            title=Path(out_base).name,
            patterns=(strip_pattern, patch_pattern, label_rule),
            designed=len(target.patches))

    cht_paths: list[Path] | None = None
    if emit_cht:
        from . import cht_writer
        # slot → reference XYZ, so each box can carry its EXPECTED value.
        slots = (_slots if _slots is not None else
                 permutation.location_permutation(layout.total_patches, seed,
                                                  randomize))
        all_patches = list(target.patches) + [media] * layout.padding
        xyz_by_slot: dict[int, tuple] = {}
        for i, (_dev, xyz) in enumerate(all_patches):
            xyz_by_slot[slots[i]] = xyz
        cht_paths = []
        npages = layout.pages
        for pg in range(npages):
            boxes = cht_writer.boxes_from_patch_rects(patch_rects, h_mm, dpi, page=pg)
            expected = []
            for r in patch_rects:
                if r.get("page", 0) != pg:
                    continue
                x, y, z = xyz_by_slot.get(r["slot"], (0.0, 0.0, 0.0))
                expected.append((r["loc"], x, y, z))
            cht = (artefact(stem, ".cht") if npages == 1
                   else stem.parent / f"{stem.name}_{pg + 1:02d}.cht")
            cht_paths.append(cht_writer.write_cht(cht, boxes, expected))

    return ChartResult(
        ti2_path=ti2_path, seed=seed, randomize=randomize,
        color_rep=target.color_rep, layout=layout,
        tiff_paths=tiff_paths, strip_rects=rects,
        low_contrast_passes=render.low_contrast_passes,
        low_contrast_labels=list(render.low_contrast_labels),
        cht_paths=cht_paths, pdf_path=pdf_path,
        # The date actually drawn, so it can be saved with the chart and handed
        # back to a later rebuild.
        chart_date=_ctx["date"],
        ramp_whites_added=ramps_arranged,
        warnings=(tuple(_i1io_warnings) if _i1io
                  else tuple(_isis_warnings) if _isis else ()),
        neighbour_moves=tuple(_nb_moves), neighbour_pairs_left=_nb_left,
        neighbour_patches_moved=_nb_count,
        slots=(list(_slots) if _slots is not None else None),
        patch_size_mm=_patch_size,
    )


def build_from_recipe(ti1_path: str | Path, out_base: str | Path, recipe
                      ) -> tuple[ChartResult, "object"]:
    """Build a chart from a :class:`~workflow.layout_engine.presets.LayoutRecipe`.

    Returns ``(result, recipe_used)`` where *recipe_used* has the actual seed
    filled in, ready to persist with the chart for the Create Chart ⇄ editor
    round-trip.
    """
    from dataclasses import replace
    result = build_chart(ti1_path, out_base, **recipe.build_kwargs())
    return result, replace(recipe, seed=result.seed)
