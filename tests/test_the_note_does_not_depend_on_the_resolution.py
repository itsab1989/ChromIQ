"""The same physical sheet must behave the same however finely it is rastered.

A challenge round found that the stock A4 chart printed its note at 300 dpi and
DROPPED it at 200, which is the resolution of the reporter's own files. The
cause was mixing units: the distance from the paper edge is a measurement in
millimetres, while the patch-side safety guard and the legibility floor were
counted in pixels. Measured on one physical sheet, those pixel constants cost

    150 dpi  3.21 mm of margin
    200 dpi  2.42 mm
    300 dpi  1.61 mm
    600 dpi  0.81 mm

so the amount of paper the note needed depended on the raster rather than on the
sheet. The guard is now a distance on paper with a two-pixel floor, and it is
the 4 px guard's own meaning at 300 dpi, where the note has always printed.

The legibility floor stays in pixels, deliberately: it is a rendering limit, not
a physical one. Below about eleven pixels there is no line to draw, and that is
why a very coarse raster can still drop the note. What must not happen is the
SAME sheet printing at one resolution and not at the next one down.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import tifffile

from workflow import tiff_metadata as TM

NOTE = "Canon PRO-1000, PhotoRag 308, colour management OFF"
EDGE_MM = 4.0


def _sheet(dpi: float, patch_right_mm: float, w_mm=210.0, h_mm=297.0) -> Path:
    def px(v: float) -> int:
        return int(round(v * dpi / 25.4))
    a = np.full((px(h_mm), px(w_mm), 3), 255, np.uint8)
    a[px(20):px(h_mm) - px(20), px(20):px(patch_right_mm)] = (200, 60, 60)
    p = Path(tempfile.mkdtemp()) / "s.tif"
    tifffile.imwrite(str(p), a, resolution=(dpi, dpi), photometric="rgb")
    return p


def _note_edge_mm(path: Path, dpi: float) -> float | None:
    """Distance from the paper edge to the note's last ink, or None if absent."""
    b = np.asarray(tifffile.imread(str(path))).astype(int)
    W = b.shape[1]
    ink = (b.max(axis=2) < 245)
    start = int(round(204.0 * dpi / 25.4))
    cols = np.nonzero(ink[:, start:].sum(axis=0))[0]
    if not len(cols):
        return None
    return (W - 1 - (start + int(cols[-1]))) * 25.4 / dpi


@pytest.mark.parametrize("dpi", [200, 300, 400, 600, 720])
def test_the_same_sheet_prints_its_note_at_every_ordinary_resolution(dpi):
    p = _sheet(dpi, 203.9)
    TM._stamp_one(p, NOTE, EDGE_MM, 0.0)
    got = _note_edge_mm(p, dpi)
    assert got is not None, (
        f"the note was dropped at {dpi} dpi on a sheet that prints it at every "
        "other resolution. The paper did not change; only the raster did.")
    assert got >= EDGE_MM - 0.10, (dpi, got)


def test_the_safety_guard_is_a_distance_on_paper():
    """A pixel guard spends four times as much paper at 150 dpi as at 600."""
    mm = [TM._safety_pad_px(d) * 25.4 / d for d in (150, 200, 300, 600)]
    assert max(mm) - min(mm) < 0.30, mm      # was 1.35 → 0.34, a 1.01 mm spread


def test_the_guard_never_disappears_on_a_coarse_raster():
    assert TM._safety_pad_px(72) >= 2
    assert TM._safety_pad_px(150) >= 2


def test_the_note_never_touches_the_patch_block_at_any_resolution():
    """The guard exists for this, so shrinking it must not cost it."""
    for dpi in (150, 200, 300, 600):
        p = _sheet(dpi, 203.9)
        TM._stamp_one(p, NOTE, EDGE_MM, 0.0)
        b = np.asarray(tifffile.imread(str(p))).astype(int)
        edge = int(round(203.9 * dpi / 25.4))
        ink = (b.max(axis=2) < 245)
        # the column immediately right of the block must stay clean
        assert not ink[:, edge:edge + 1].any(), (
            f"at {dpi} dpi the note is touching the patch block")
