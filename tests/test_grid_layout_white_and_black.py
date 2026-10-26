"""The scanner path "Where the chart was laid out: In i1Profiler" (#120) must
read a correct i1Profiler page whose patch set holds pure white or black.

`grid_layout_from_render._block_bbox` took "every pixel with an exported patch
colour" as the patch block. Almost every real patch set holds paper white, and
most hold black; i1Profiler's page is white and its frame marks are black, so
the "block" became the whole page and `derive_grid_layout` refused a correct
chart (study of 2026-10-26: refused as shipped, 540 of 540 verified with white
and black left out of the block search). The module's own tests only used probe
colours, which never include white.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from workflow.grid_layout_from_render import derive_grid_layout

DATA = Path(__file__).resolve().parent / "data" / "i1profiler_turned_render"
DPI = 101.6


def _page(path: Path, rgb100: np.ndarray, cols: int, rows: int,
          pw_mm=10.0, ph_mm=8.0) -> Path:
    """An i1Profiler-like page: white paper, a black frame and corner marks,
    and the patch block filled column-major from 15.5 / 24.5 mm."""
    mm = DPI / 25.4
    w, h = int(296.93 * mm), int(210.06 * mm)
    img = np.full((h, w, 3), 255, np.uint8)
    x0, y0 = 15.5 * mm, 24.5 * mm
    for i, v in enumerate(rgb100):
        c, r = divmod(i, rows)
        xa, ya = int(round(x0 + c * pw_mm * mm)), int(round(y0 + r * ph_mm * mm))
        xb = int(round(x0 + (c + 1) * pw_mm * mm))
        yb = int(round(y0 + (r + 1) * ph_mm * mm))
        img[ya:yb, xa:xb] = np.round(np.asarray(v) / 100 * 255)
    # the page's furniture, in pure black: a thin frame and four corner marks
    img[8:10, 8:w - 8] = 0
    img[h - 10:h - 8, 8:w - 8] = 0
    img[8:h - 8, 8:10] = 0
    img[8:h - 8, w - 10:w - 8] = 0
    for cx, cy in ((20, 20), (w - 30, 20), (20, h - 30), (w - 30, h - 30)):
        img[cy:cy + 10, cx:cx + 10] = 0
    Image.fromarray(img).save(path, dpi=(DPI, DPI))
    return path


def _patch_set(n: int, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    rgb = rng.uniform(5, 95, (n, 3)).round(3)
    rgb[0] = (100, 100, 100)            # paper white, as targen writes it
    rgb[7] = (100, 100, 100)
    rgb[13] = (0, 0, 0)                 # and black
    rgb[n - 1] = (0, 0, 0)
    return rgb


def test_a_page_with_white_and_black_patches_is_read(tmp_path):
    rgb = _patch_set(24 * 15)
    page = _page(tmp_path / "p.png", rgb, cols=24, rows=15)
    lay = derive_grid_layout([page], rgb)
    assert len(lay["patches"]) == 360
    p0 = lay["patches"][0]
    assert p0["x"] * 25.4 / lay["dpi"] == pytest.approx(15.5, abs=0.3)
    assert p0["y"] * 25.4 / lay["dpi"] == pytest.approx(24.5, abs=0.3)
    assert p0["w"] * 25.4 / lay["dpi"] == pytest.approx(10.0, abs=0.1)


def test_a_real_i1profiler_page_with_white_and_black_is_read():
    """The chart i1Profiler 3.8.8 itself saved for a ChromIQ patch set that
    holds white and black (the turned export of a 600-patch chart)."""
    doc = json.loads((DATA / "turned10_patch_list.json").read_text())
    assert doc["white"] >= 1 and doc["black"] >= 1
    lay = derive_grid_layout([DATA / "turned10_i1pro3_page.png"], doc["rgb100"])
    assert len(lay["patches"]) == 600


def test_the_wrong_patch_set_is_still_refused(tmp_path):
    """The fix must not loosen the colour check: a shuffled list on the same
    page is refused, white and black or not."""
    from workflow.grid_layout_from_render import GridGeometryError
    rgb = _patch_set(24 * 15)
    page = _page(tmp_path / "p.png", rgb, cols=24, rows=15)
    shuffled = rgb.copy()
    np.random.default_rng(1).shuffle(shuffled)
    with pytest.raises(GridGeometryError):
        derive_grid_layout([page], shuffled)


def test_a_set_of_only_white_and_black_still_finds_its_block(tmp_path):
    """Nothing else to go by: the block search falls back to every colour."""
    rgb = np.array([(100, 100, 100), (0, 0, 0)] * 6, dtype=float)
    page = _page(tmp_path / "p.png", rgb, cols=4, rows=3)
    from workflow.grid_layout_from_render import _block_bbox, _load_page, \
        _rgb100_to_key8
    img, _dpi = _load_page(page)
    x0, y0, x1, y1 = _block_bbox(img, np.unique(_rgb100_to_key8(rgb)))
    assert (x0, y0) == (0, 0)           # the old behaviour: no better answer
