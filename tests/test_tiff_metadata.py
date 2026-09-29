"""Byte-integrity tests for workflow.tiff_metadata.stamp_chart_metadata.

ChromIQ is a color-profiling tool, so the non-negotiable constraint is that
**patch pixels remain byte-identical** after stamping. Only pixels inside
the detected right-edge margin (the white space to the right of the patch
area) may change. Tests cover both 8-bit and 16-bit TIFFs.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import tifffile

from workflow.tiff_metadata import stamp_chart_metadata


# A4 portrait @ 300 DPI: 2480 x 3508
_DPI = 300
_W = 2480
_H = 3508
# Patches occupy the left two-thirds; everything to the right is white margin.
_PATCH_RIGHT_X = 1700


def _make_chart_tif(path: Path, dtype) -> np.ndarray:
    """Synthesize a printtarg-shaped TIFF: dense patch area on the left, white margin on the right."""
    max_val = 255 if dtype == np.uint8 else 65535
    arr = np.full((_H, _W, 3), max_val, dtype=dtype)
    # Dense vertical stripes in the patch area so each column registers as inked
    for c in range(0, _PATCH_RIGHT_X, 40):
        arr[:, c : c + 32, 0] = 0
        arr[:, c : c + 32, 1] = max_val // 2
        arr[:, c : c + 32, 2] = 0
    # Right margin (white) stays at max_val
    tifffile.imwrite(
        str(path),
        arr,
        photometric="rgb",
        compression="lzw",
        resolution=(_DPI, _DPI),
        resolutionunit="INCH",
    )
    return arr


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16], ids=["8bit", "16bit"])
def test_patch_pixels_byte_identical_after_stamp(tmp_path: Path, dtype) -> None:
    path = tmp_path / "chart.tif"
    before = _make_chart_tif(path, dtype)

    stamp_chart_metadata(
        [path],
        ["targen -d2 -f400 chart", "printtarg -ii1 -pA4 -t300 -L -m10 -M10 chart",
         "ChromIQ 3.5.9"],
    )

    after = tifffile.imread(str(path))
    # Left of the patch boundary: byte-identical
    assert np.array_equal(before[:, :_PATCH_RIGHT_X], after[:, :_PATCH_RIGHT_X]), (
        f"Patch-area pixels changed after stamp (dtype={dtype.__name__})"
    )
    # Right margin: must have changed (otherwise stamp silently no-op'd)
    assert not np.array_equal(before[:, _PATCH_RIGHT_X:], after[:, _PATCH_RIGHT_X:]), (
        "Right margin did not change — stamp call had no effect"
    )


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16], ids=["8bit", "16bit"])
def test_bit_depth_and_dpi_preserved(tmp_path: Path, dtype) -> None:
    path = tmp_path / "chart.tif"
    _make_chart_tif(path, dtype)

    stamp_chart_metadata([path], ["one line is enough"])

    with tifffile.TiffFile(str(path)) as tf:
        page = tf.pages[0]
        assert page.dtype == dtype
        assert page.shape == (_H, _W, 3)
        xres = page.tags.get("XResolution")
        yres = page.tags.get("YResolution")
        ru = page.tags.get("ResolutionUnit")
        for tag in (xres, yres):
            n, d = tag.value
            unit = ru.value if ru else 2
            dpi = (n / d) * (2.54 if unit == 3 else 1.0)
            assert abs(dpi - _DPI) < 1.0


def test_a_sheet_with_no_right_margin_is_stamped_over_the_patches(
        tmp_path: Path) -> None:
    """Patches reaching the right edge → the note prints ANYWAY, over them.

    REVERSED BY KNUT'S RULING OF 2026-09-10, and this test used to assert the
    opposite: *"the text must still be visible, even if the patch area overlaps
    on the right Run Chart Notes text. Else the user will not notice that it is
    silently dropped, like you now do."* An untouched file was the silent drop,
    and it was the outcome he named as the one thing that must not happen.

    The ink is measured against the sheet as it was, not counted absolutely, and
    it has to land inside the "Text distance from edge" reserve's inner side:
    the reserve is still a limit and is the only thing here that is.
    """
    path = tmp_path / "edge_to_edge.tif"
    # Fill the WHOLE image with dense stripes so no usable right margin exists.
    arr = np.full((_H, _W, 3), 255, dtype=np.uint8)
    for c in range(0, _W, 40):
        arr[:, c : c + 32, :] = 50
    tifffile.imwrite(str(path), arr, photometric="rgb", compression="lzw",
                     resolution=(_DPI, _DPI), resolutionunit="INCH")
    before = tifffile.imread(str(path))

    edge_mm = 4.0
    stamp_chart_metadata([path], ["this must appear"], edge_mm)

    after = tifffile.imread(str(path))
    assert not np.array_equal(before, after), (
        "the note was dropped on a sheet with no right margin, which is the "
        "silent drop Knut's ruling of 2026-09-10 forbids"
    )
    # Compositing only darkens, so every changed pixel is the note's own ink.
    changed = (after < before).any(axis=2)
    assert changed.any(), "the file changed but no ink was added"
    right = int(np.flatnonzero(changed.any(axis=0)).max())
    to_edge = (_W - 1 - right) * 25.4 / _DPI
    assert to_edge >= edge_mm - 0.1, (
        f"the note ends {to_edge:.2f} mm from the paper edge and "
        f"“Text distance from edge” asks for {edge_mm:.2f} mm"
    )


def test_stamp_skips_when_lines_empty(tmp_path: Path) -> None:
    """Empty or whitespace-only lines short-circuit before opening the file."""
    path = tmp_path / "chart.tif"
    _make_chart_tif(path, np.uint8)
    before = tifffile.imread(str(path))

    stamp_chart_metadata([path], ["   ", ""])

    after = tifffile.imread(str(path))
    assert np.array_equal(before, after)
