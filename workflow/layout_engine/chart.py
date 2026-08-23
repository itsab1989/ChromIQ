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
    cht_paths: list[Path] | None = None
    pdf_path: Path | None = None
    #: The date drawn on the record strip (``YYYY-MM-DD``). Saved with the chart
    #: so a rebuild can reproduce it instead of stamping the day it ran.
    chart_date: str = ""


def build_ti2_from_ti1(
    ti1_path: str | Path,
    ti2_path: str | Path,
    *,
    instrument: str = "i1",
    paper: str = "A4",
    seed: int | None = None,
    randomize: bool = True,
    hflag: bool = False,
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
        instrument, hflag=hflag, density=density, spacer_on=spacer_on, pscale=pscale,
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
    spacer_width: float | None = None,
    inter_patch: float | None = None,
    strip_gap: float | None = None,
    max_strip: float | None = None,
    strip_indicator_gap: float | None = None,
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
    strip_label_offset_mm: float = 0.0,
    underline_mode: str = "off",
    underline_thickness_mm: float = 0.5,
    underline_gap_mm: float = 0.5,
    chart_text: str = "",
    chart_text_font: str = "Inter",
    chart_text_size_mm: float = 0.0,
    chart_text_bold: bool = False,
    chart_text_italic: bool = False,
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
    clip_text: str = "",
    clip_text_font: str = "Inter",
    clip_text_size_mm: float = 0.0,
    clip_image_path: str = "",
    clip_image_rotation: int = 0,
    clip_image_scale: float = 100.0,
    clip_image_offset_x: float = 0.0,
    clip_image_offset_y: float = 0.0,
    clip_flip_180: bool = False,
    strip_pattern: str = permutation.DEFAULT_STRIP_PATTERN,
    patch_pattern: str = permutation.DEFAULT_PATCH_PATTERN,
    cal_path: str | Path | None = None,
    apply_cal: bool = False,
    emit_cht: bool = False,
) -> ChartResult:
    """Full chart build: write ``out_base.ti2`` + page TIFF(s) + strip geometry.

    ``out_base`` is a path stem; outputs are ``<stem>.ti2``, ``<stem>.tif``
    (or ``<stem>_NN.tif`` for multi-page) and ``<stem>.strips.json`` (exact
    per-strip pixel rects for the measure-tab highlighter).

    *cal_path* attaches a printer calibration: with *apply_cal* True (``-K``) the
    curves are applied to the patch values (TIFF + ``.ti2`` together) **and**
    embedded; with it False (``-I``) the calibration is only embedded.
    """
    target = ti1_reader.read_ti1(ti1_path)

    cal = None
    if cal_path is not None:
        from . import calibration
        cal = calibration.read_cal(cal_path)
        if apply_cal:
            target = calibration.apply_to_target(target, cal)
    spacer_on = spacer_on and spacer_mode != "none"   # "none" ⇒ no gap
    # Build the Geom through the one chokepoint so area-first patch sizing and the
    # furniture reservations (label band, bottom sheet text / stamp) match every
    # capacity estimate exactly (#93).
    geom = instruments.geom_from_build_kwargs({
        "instrument": instrument, "paper": paper, "hflag": hflag,
        "density": density, "cm_stagger": cm_stagger,
        "spacer_on": spacer_on, "pscale": pscale,
        "sscale": sscale, "border": border, "margins": margins,
        "patch_w": patch_w, "patch_h": patch_h, "spacer_width": spacer_width,
        "inter_patch": inter_patch, "strip_gap": strip_gap, "max_strip": max_strip,
        "strip_indicator_gap": strip_indicator_gap, "offset_x": offset_x,
        "offset_y": offset_y, "nolpcbord": nolpcbord, "nolimit": nolimit,
        "clip_border_width": clip_border_width, "clip_side": clip_side,
        "clip_content_mode": clip_content_mode,
        "text_edge_top": text_edge_top, "text_edge_clip": text_edge_clip,
        "use_instrument_margins": use_instrument_margins,
        "edge_spacers": edge_spacers,
        "patch_area_align": patch_area_align, "layout_mode": layout_mode,
        "area_method": area_method, "area_cols": area_cols,
        "area_rows": area_rows, "area_ratio": area_ratio,
        "area_min_patch": area_min_patch,
        # The chart's actual patch count, so area-first sizes the patches to FILL
        # the box with exactly this many (a fixed patch set still fills the area,
        # not just packs at the minimum) (Knut). Ignored by patch-first.
        "area_target_count": len(target.patches),
        "area_default_w": area_default_w, "area_default_h": area_default_h,
        "dpi": dpi, "draw_indicators": draw_indicators,
        "indicator_font": indicator_font, "indicator_size_mm": indicator_size_mm,
        "indicator_bold": indicator_bold, "indicator_italic": indicator_italic,
        "indicator_rotation": indicator_rotation, "underline_mode": underline_mode,
        "underline_thickness_mm": underline_thickness_mm,
        "underline_gap_mm": underline_gap_mm,
        "chart_text": chart_text, "stamp_command": stamp_command,
        "text_edge": text_edge})
    w_mm, h_mm = papers.dimensions_mm(paper)
    layout = geometry.compute(geom, w_mm, h_mm, len(target.patches))
    if seed is None:
        seed = permutation.pick_seed()

    base = Path(out_base)
    stem = base.with_suffix("")

    media = target.media_patch()
    white_point = media[1] if any(media[1]) else ti2_writer.DEFAULT_WHITE_POINT
    ti2_path = stem.with_suffix(".ti2")
    ti2_writer.write_ti2(
        ti2_path, target.patches, target.device_fields, layout, geom,
        color_rep=target.color_rep, seed=seed, randomize=randomize,
        strip_pattern=strip_pattern, patch_pattern=patch_pattern,
        paper_w_mm=w_mm, paper_h_mm=h_mm, media=media, white_point=white_point,
        ink_limit=target.ink_limit,
    )
    if cal is not None:  # embed the calibration table (-K and -I both embed)
        from . import calibration
        with open(ti2_path, "a", encoding="utf-8") as fh:
            fh.write("\n" + calibration.cal_table_text(cal))

    import time as _time
    # Human-friendly placeholder values for {project}/{instrument}/{paper}/… in
    # chart text, clip text and the stamp. {page} is resolved per page inside
    # render_pages (it needs the page index), so it's not in this dict. (#93)
    _instr_friendly = {"i1": "i1Pro", "p3": "i1Pro3+", "CM": "ColorMunki",
                       "SS": "SpectroScan", "41": "DTP41", "51": "DTP51"}
    _ctx = {
        "project": project or Path(out_base).name,
        "rundescription": rundescription,
        "instrument": _instr_friendly.get(instrument, instrument),
        "paper": papers.friendly_label(paper),          # "A4 landscape"
        "dpi": f"{dpi} dpi",
        "patchcount": f"{layout.total_patches} patches",
        "pages": str(layout.pages),                     # total; {page} = "page X/Y"
        "date": chart_date or _time.strftime("%Y-%m-%d"),
        "seed": f"seed {seed}",
    }
    stamp_text = (f"ChromIQ engine · {_ctx['instrument']} · {_ctx['paper']} · "
                  f"{_ctx['dpi']} · {_ctx['patchcount']} · {_ctx['seed']}"
                  if stamp_command else "")
    def _to_rgb(c):
        if isinstance(c, str):
            h = c.lstrip("#")
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        return tuple(int(v) for v in c)
    _palette = [_to_rgb(c) for c in spacer_palette] if spacer_palette else None
    _overrides = ({int(k): _to_rgb(v) for k, v in spacer_overrides.items()}
                  if spacer_overrides else None)
    render = raster.render_pages(
        target, layout, geom, seed=seed, randomize=randomize,
        paper_w_mm=w_mm, paper_h_mm=h_mm, dpi=dpi, strip_pattern=strip_pattern,
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
        chart_text=chart_text, chart_text_font=chart_text_font,
        chart_text_size_mm=chart_text_size_mm, chart_text_bold=chart_text_bold,
        chart_text_italic=chart_text_italic, stamp_text=stamp_text,
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
        collect_device_geom=(target.n_channels >= 4 or export_pdf),
    )
    if target.n_channels >= 4:
        device_pages = raster.build_device_pages(render, target, bit16=bit16)
        tiff_paths = raster.save_separated_tiffs(
            device_pages, stem.with_suffix(".tif"), dpi=dpi,
            ink_names=raster.ink_names_from_fields(target.device_fields),
            compression=compression)
    else:
        tiff_paths = raster.save_tiffs(render.images, stem.with_suffix(".tif"),
                                       dpi=dpi, bit16=bit16, compression=compression)
    pdf_path: Path | None = None
    if export_pdf:
        from . import vector_pdf
        pdf_path = vector_pdf.save_vector_pdf(
            render, target, stem.with_suffix(".pdf"),
            paper_w_mm=w_mm, paper_h_mm=h_mm, dpi=dpi)

    rects = geometry.strip_rects_px(geom, w_mm, h_mm, layout, dpi)
    patch_rects = geometry.patch_rects_px(geom, w_mm, h_mm, layout, dpi,
                                          strip_pattern, patch_pattern)
    strips_path = stem.with_suffix(".strips.json")
    strips_path.write_text(json.dumps({
        "dpi": dpi, "paper_mm": [w_mm, h_mm],
        "steps_in_pass": layout.steps_in_pass, "strip_pattern": strip_pattern,
        "label_band_bottom_px": render.label_band_bottom_px,
        "strips": rects, "patches": patch_rects,
    }, indent=2), encoding="utf-8")

    cht_paths: list[Path] | None = None
    if emit_cht:
        from . import cht_writer
        # slot → reference XYZ, so each box can carry its EXPECTED value.
        slots = permutation.location_permutation(layout.total_patches, seed,
                                                 randomize)
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
            cht = (stem.with_suffix(".cht") if npages == 1
                   else stem.parent / f"{stem.name}_{pg + 1:02d}.cht")
            cht_paths.append(cht_writer.write_cht(cht, boxes, expected))

    return ChartResult(
        ti2_path=ti2_path, seed=seed, randomize=randomize,
        color_rep=target.color_rep, layout=layout,
        tiff_paths=tiff_paths, strip_rects=rects,
        low_contrast_passes=render.low_contrast_passes,
        cht_paths=cht_paths, pdf_path=pdf_path,
        # The date actually drawn, so it can be saved with the chart and handed
        # back to a later rebuild.
        chart_date=_ctx["date"],
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
