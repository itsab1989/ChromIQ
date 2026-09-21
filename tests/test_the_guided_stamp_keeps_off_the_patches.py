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


def _render_and_stamp(tmp_path: Path, tag: str, kw: dict):
    """(plain raster, stamped raster) for one Guided sheet."""
    ti1 = tmp_path / f"{tag}.ti1"
    _ti1(ti1, 420)
    le_chart.build_chart(ti1, tmp_path / tag, seed=1234, **kw)
    tif = sorted(tmp_path.glob(f"{tag}*.tif"))[0]
    stamped = tmp_path / f"{tag}_stamped.tiff"
    shutil.copy(tif, stamped)
    from workflow.tiff_metadata import stamp_chart_metadata
    stamp_chart_metadata([stamped], _STAMP_LINES, _EDGE_MM, 0.0, "", 0.0,
                         -1.0, 0.0, _EDGE_MM, _EDGE_MM)
    return tifffile.imread(tif), tifffile.imread(stamped)


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
    on patch ink before and 22 after, and the stamper's own overlap condition
    (28 px of paper where a 7 pt line needs 32) stopped firing.
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
    assert ink_after < ink_before / 2, (
        f"the stamp still lands on {ink_after} pixels of patch ink, against "
        f"{ink_before} before")


def test_the_sheets_that_already_had_room_are_not_touched(tmp_path):
    """A Guided CR30 A4 chart with SQUARE patches has 15.6 mm of white paper on
    the right, so nothing about it may move.

    Without this the guard above would pass just as well if the walk shrank
    every row label on every chart, which is the thing Sebastian ruled out:
    *"the text size reductions ... should only be as much as really needed to
    avoid overlap, not more"*.
    """
    kw = _guided_kwargs(hflag=False, hex_flat_top=False)
    off = _render_and_stamp(tmp_path, "sq_off", dict(kw, side_stamp=False))
    on = _render_and_stamp(tmp_path, "sq_on", dict(kw, side_stamp=True))
    assert np.array_equal(off[0], on[0]), (
        "a chart that already had room for its stamp was laid out differently")
    assert _stamp_ink_on_patch_ink(*on) == 0
