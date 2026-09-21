"""§R9 — Guided must not lay patches under its own right-edge stamp.

Sebastian, 2026-09-20, on a Guided CR30 / A4 / hexagon chart: the settings
stamp down the right edge is printed over the patches, and *"if i create the
same thing in manual mode the warning gives hints how to solve this. but guided
module should just work for the user without causing issues for the user"*.

Everything here is measured on a RENDERED sheet, because that is the only place
this fault exists: the stamp is not laid out by the engine at all, it is painted
onto the finished raster by `workflow/tiff_metadata.py::_stamp_one`.

The method is the one `feedback_measuring_a_rendered_sheet` settles on, with one
simplification this particular fault allows: the stamp is applied to a COPY of
the very same TIFF, so the two rasters are bit-identical apart from the stamp's
own ink and nothing about the layout can move between the passes. Differencing
them isolates the stamp exactly, border columns included, with no second render
and no geometry to pin.

The companion guards -- the patch count, the typed size, area-first -- are in
`test_the_row_labels_pay_for_the_stamp_not_the_patches.py`.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from workflow import text_edge_fit
from workflow.chart_creator import ChartCreator, ChartParams
from workflow.layout_engine import chart as le_chart

tifffile = pytest.importorskip("tifffile")

#: What the app stamps down the right edge of a Guided sheet, in the shape
#: `ChartCreator.stamp_lines` produces: the targen command, the engine's name
#: and the version. The exact words do not matter here -- the line's THICKNESS
#: is what runs into the patches -- but a realistic length keeps the render
#: honest about where the ends fall.
_STAMP_LINES = ["targen -d2 -f396 -e4 -B4 -G -g32 test",
                "ChromIQ layout engine", "ChromIQ 4.3.0-beta.30"]

#: Guided's own "Text distance from edge" -> Clip, which is the setting's
#: default because Guided has no box for it (`chart_creator._stamp_tiff_
#: metadata`, the `_should_use_engine` branch).
_EDGE_MM = 4.0
_DPI = 300.0


def _ti1(path: Path, n: int) -> None:
    """A .ti1 with *n* patches. Only the count and the device values matter."""
    rows = [(100.0, 100.0, 100.0)]
    step = 0
    while len(rows) < n:
        step += 1
        r = (step * 37) % 101
        g = (step * 59) % 101
        b = (step * 83) % 101
        rows.append((float(r), float(g), float(b)))
    lines = ["CTI1", 'COLOR_REP "iRGB"', "NUMBER_OF_FIELDS 7",
             "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA"]
    for i, (r, g, b) in enumerate(rows, 1):
        lines.append(f"{i} {r:.4f} {g:.4f} {b:.4f} "
                     f"{r * 0.95:.4f} {g:.4f} {b * 1.08:.4f}")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _guided_kwargs(**over) -> dict:
    """Exactly the kwargs a Guided chart is built from."""
    p = ChartParams(instrument="CR30", paper="A4", pages=1, margin_mm=5,
                    patch_scale=1.0, is_manual=False, double_density=True,
                    disable_left_border=True)
    creator = object.__new__(ChartCreator)
    kw = ChartCreator._engine_build_kwargs(creator, p)
    kw.pop("chart_date", None)
    kw.update(over)
    return kw


def _render_and_stamp(tmp_path: Path, tag: str, kw: dict, *,
                      spend_the_gap: bool = True):
    """(plain raster, stamped raster) for one Guided sheet.

    *spend_the_gap* is §R9's second half: the paper the walk freed is handed to
    the stamper as a minimum patch-side gap, so the line keeps its size instead
    of growing into it. False reproduces B8-556 as Sebastian first saw it.
    """
    ti1 = tmp_path / f"{tag}.ti1"
    _ti1(ti1, 420)
    le_chart.build_chart(ti1, tmp_path / tag, seed=1234, **kw)
    tif = sorted(tmp_path.glob(f"{tag}*.tif"))[0]
    stamped = tmp_path / f"{tag}_stamped.tiff"
    shutil.copy(tif, stamped)
    gap = 0.0
    if spend_the_gap:
        from workflow.layout_engine import instruments
        gap = float(getattr(instruments.geom_from_build_kwargs(kw),
                            "side_stamp_freed_mm", 0.0) or 0.0)
    from workflow.tiff_metadata import stamp_chart_metadata
    stamp_chart_metadata([stamped], _STAMP_LINES, _EDGE_MM, 0.0, "", 0.0,
                         -1.0, 0.0, _EDGE_MM, _EDGE_MM, gap)
    return tifffile.imread(tif), tifffile.imread(stamped)


def _stamp_size_pt(tmp_path: Path, tag: str, kw: dict, *,
                   spend_the_gap: bool = True) -> float:
    """The point size the stamper CHOSE, asked of the stamper.

    `fit_rotated_line` is the function that picks it, so its own answer is
    captured rather than measured back out of glyph ink.
    """
    import workflow.tiff_metadata as tm
    from workflow import text_edge_fit as tef
    got: list[float] = []
    orig = tm.fit_rotated_line

    def spy(text, strip_h, strip_w, anchor_px=None, font_family="",
            size_pt=0.0, dpi=200.0):
        shown, font = orig(text, strip_h, strip_w, anchor_px=anchor_px,
                           font_family=font_family, size_pt=size_pt, dpi=dpi)
        got.append(tef.px_to_pt(getattr(font, "size", 0), dpi))
        return shown, font

    tm.fit_rotated_line = spy
    tm._render_fitted_rotated_line.__globals__["fit_rotated_line"] = spy
    try:
        _render_and_stamp(tmp_path, tag, kw, spend_the_gap=spend_the_gap)
    finally:
        tm.fit_rotated_line = orig
        tm._render_fitted_rotated_line.__globals__["fit_rotated_line"] = orig
    return got[-1] if got else 0.0


def _white_between_patches_and_stamp(plain, stamped) -> int:
    """Device-pixel columns of clear paper between the RIGHT-MOST patch ink and
    the stamp's first ink. Negative when the stamp is printed over them."""
    lum = plain[..., :3].min(axis=2)
    changed = (np.abs(stamped.astype(np.int32) - plain.astype(np.int32))
               .max(axis=2) > 0)
    xs = np.nonzero(changed.any(axis=0))[0]
    if not xs.size:
        return 0
    patch_right = int(np.nonzero((lum < 240).any(axis=0))[0].max())
    return int(xs.min()) - patch_right - 1


def _stamp_ink_on_patch_ink(plain, stamped) -> int:
    """Stamp pixels laid on something that was already not paper."""
    lum = plain[..., :3].min(axis=2)
    changed = (np.abs(stamped.astype(np.int32) - plain.astype(np.int32))
               .max(axis=2) > 0)
    return int((changed & (lum < 240)).sum())


def _room_px(plain) -> tuple[int, int]:
    """(paper the stamper finds for its line, the width a legible line needs).

    Both read from the stamper's own code, so this asks the product's question
    rather than a second version of it: `_detect_writable_band` is what decides
    where the line may start, and `note_min_strip_px` is the floor `_stamp_one`
    compares it against before printing across the block anyway.
    """
    from workflow import tiff_metadata as tm
    band = tm._detect_writable_band(plain, keep_out_px=0,
                                    pad_px=tm._safety_pad_px(_DPI))
    width = plain.shape[1]
    right_limit = width - int(round(_EDGE_MM * _DPI / 25.4))
    room = (right_limit - band[0]) if band else 0
    return room, text_edge_fit.note_min_strip_px(_DPI, 0.0)


def test_the_guided_hexagon_sheet_stops_printing_the_stamp_over_its_patches(
        tmp_path):
    """The reported chart, rendered, with the walk on and with it off.

    `side_stamp` is the walk's own gate and the only thing it does, so the two
    sheets differ by exactly the change under test.

    Measured on this sheet at the time it was written: 206 stamp pixels landed
    on patch ink before and **none** after, and the stamper's own overlap
    condition (28 px of paper where a 7 pt line needs 32) stopped firing.
    """
    before = _render_and_stamp(tmp_path, "before",
                               _guided_kwargs(side_stamp=False))
    after = _render_and_stamp(tmp_path, "after",
                              _guided_kwargs(side_stamp=True))

    ink_before = _stamp_ink_on_patch_ink(*before)
    ink_after = _stamp_ink_on_patch_ink(*after)
    room_before, floor = _room_px(before[0])
    room_after, _ = _room_px(after[0])

    assert ink_before > 100, (
        "the fault this guard is about was not reproduced: only "
        f"{ink_before} stamp pixels landed on patch ink with the walk off")
    assert room_before < floor, (
        "the stamper's own overlap condition did not fire on the unfixed "
        f"sheet: {room_before} px of paper against a {floor} px floor")

    assert room_after >= floor, (
        f"the stamp is still forced over the patch block: {room_after} px of "
        f"paper where a line at the {text_edge_fit.AUTO_SHRINK_FLOOR_PT:g} pt "
        f"floor needs {floor} px")
    assert ink_after == 0, (
        f"the stamp still lands on {ink_after} pixels of patch ink, against "
        f"{ink_before} before")


def test_the_freed_paper_is_spent_as_white_and_not_as_type(tmp_path):
    """§R9's second half, and it is Sebastian's ruling of 2026-09-21.

    He judged the first before/after picture and asked for one change:

        *"although it is not overlapping anymore the stamps font size became a
        tad bigger. I'd rather have the stamp size the same as before (so
        little smaller than now) but with a tiny gap to the patches."*

    He had read it correctly. `fit_rotated_line` starts the automatic size at
    the width of the paper beside the note, so every pixel the row-label walk
    freed went into the TYPE and the clearance stayed at nothing. Measured on
    this sheet: **7.20 pt before the walk, 8.88 pt after**, with the ink still
    four pixels inside the outermost hexagon points.

    Three states, and all three are pinned here, because the middle one is the
    whole reason this test exists: a guard that only checked the end state
    would pass just as well if the size had never moved.
    """
    off = _guided_kwargs(side_stamp=False)
    on = _guided_kwargs(side_stamp=True)

    pt_a = _stamp_size_pt(tmp_path, "sz_a", off, spend_the_gap=False)
    pt_b = _stamp_size_pt(tmp_path, "sz_b", on, spend_the_gap=False)
    pt_c = _stamp_size_pt(tmp_path, "sz_c", on, spend_the_gap=True)

    assert pt_b > pt_a + 0.4, (
        "the growth this guard is about did not happen: the stamp printed at "
        f"{pt_a:.2f} pt before the walk and {pt_b:.2f} pt after it")
    assert pt_c == pytest.approx(pt_a, abs=0.05), (
        f"the stamp prints at {pt_c:.2f} pt where it printed {pt_a:.2f} pt "
        "before the walk; the freed paper is being spent on type again")

    gap_a = _white_between_patches_and_stamp(
        *_render_and_stamp(tmp_path, "gp_a", off, spend_the_gap=False))
    gap_b = _white_between_patches_and_stamp(
        *_render_and_stamp(tmp_path, "gp_b", on, spend_the_gap=False))
    gap_c = _white_between_patches_and_stamp(
        *_render_and_stamp(tmp_path, "gp_c", on, spend_the_gap=True))

    assert gap_a < 0 and gap_b < 0, (
        "neither earlier state printed the stamp over the patches, so this "
        f"guard proves nothing about the gap: {gap_a} px, {gap_b} px")
    assert gap_c > 0, (
        f"the stamp still has no clear paper beside it: {gap_c} px")


def test_an_absurd_gap_cannot_push_the_note_off_the_sheet(tmp_path):
    """The gap is capped at what the strip has above the legibility floor.

    Without the cap the anchor can exceed the strip's own width, and the
    renderer then draws the line outside its canvas: the note is not shrunk,
    not warned about, it simply is not there. That is the silent drop Knut
    reversed 4.2.3 for -- *"the text must still be visible, even if the patch
    area overlaps … else the user will not notice that it is silently
    dropped"*.

    Asked by handing the stamper 50 mm of gap on a sheet that has under one:
    the note must land on exactly the same pixels as with the real gap, because
    the cap binds long before 50 mm.
    """
    kw = _guided_kwargs(side_stamp=True)
    ti1 = tmp_path / "floor.ti1"
    _ti1(ti1, 420)
    le_chart.build_chart(ti1, tmp_path / "floor", seed=1234, **kw)
    tif = sorted(tmp_path.glob("floor*.tif"))[0]
    plain = tifffile.imread(tif)

    from workflow.layout_engine import instruments
    from workflow.tiff_metadata import stamp_chart_metadata
    real = float(getattr(instruments.geom_from_build_kwargs(kw),
                         "side_stamp_freed_mm", 0.0) or 0.0)
    assert real > 0.0, "this chart is not one the walk touched"

    out = []
    for tag, gap in (("real", real), ("absurd", 50.0)):
        p = tmp_path / f"floor_{tag}.tiff"
        shutil.copy(tif, p)
        stamp_chart_metadata([p], _STAMP_LINES, _EDGE_MM, 0.0, "", 0.0,
                             -1.0, 0.0, _EDGE_MM, _EDGE_MM, gap)
        out.append(tifffile.imread(p))

    assert not np.array_equal(out[0], plain), "the note was not stamped at all"
    assert np.array_equal(out[0], out[1]), (
        "a 50 mm gap moved the note; the cap that keeps it inside its own "
        "strip is not holding")


def test_the_sheets_that_already_had_room_are_not_touched(tmp_path):
    """A Guided CR30 A4 chart with SQUARE patches has 15.6 mm of white paper on
    the right, so nothing about it may move.

    Without this the guard above would pass just as well if the walk shrank
    every row label on every chart, which is the thing Sebastian ruled out:
    *"the text size reductions ... should only be as much as really needed to
    avoid overlap, not more"*.
    """
    kw = _guided_kwargs(hflag=False, hex_flat_top=False)
    off = _render_and_stamp(tmp_path, "sq_off", dict(kw, side_stamp=False),
                            spend_the_gap=False)
    on = _render_and_stamp(tmp_path, "sq_on", dict(kw, side_stamp=True))
    assert np.array_equal(off[0], on[0]), (
        "a chart that already had room for its stamp was laid out differently")
    assert _stamp_ink_on_patch_ink(*on) == 0
    # …AND ITS STAMP IS STAMPED IDENTICALLY, which is the half Sebastian's
    # 2026-09-21 change could have broken. A chart the walk never touched
    # carries `side_stamp_freed_mm` 0, so the gap is 0 and the whole raster is
    # the same page it was. Measured: it prints at 9.12 pt with 0.762 mm of
    # white beside it, and holding EVERY chart to the floor to give this one a
    # gap would have cost it 1.9 pt of type.
    assert np.array_equal(off[1], on[1]), (
        "the stamp moved or changed size on a chart the walk never touched")
