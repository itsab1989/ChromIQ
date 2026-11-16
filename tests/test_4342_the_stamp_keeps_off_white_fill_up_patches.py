"""The right-edge stamp never lands on a measured patch because it is white
(review 2, 2026-11-16; the fault is in 4.3.41 too).

With "Stamp settings down the right edge" on, the built-in preset
"i1Pro · A4-2052p-4pages · Standard Patch Set v25" (Red River Paper) in fixed
order has a page 4 whose last strip holds 2 pale patches and 23 pure-white
fill-up patches. `_detect_writable_band` finds the note's band on the RASTER
("the widest white run right of the patches"), took that strip for paper, and
the line was printed down it: 17 measured patches overprinted, on screen
"Margins: OK", nothing in red.

The stamp now takes each page's true right edge from the engine's own map
(`ChartCreator._engine_page_patch_boxes_mm`, the patch and strip rectangles)
and never starts left of it. Where that leaves too little paper, the note goes
down the overlap path of Knut's ruling of 2026-09-10 (printed anyway, a log
line, the red warning in the panel), which this change leaves alone.

And the page a map entry belongs to is its place in the list of pages, not a
"_N" at the end of a file name: a one-page chart of a project called
"Baryta_2" was taken for page 2 and lost its patch area.
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import numpy as np
import pytest
import tifffile

from workflow import tiff_metadata

ROOT = Path(__file__).resolve().parents[1]
SLUG = "redriver_i1pro_a4_2052p_4pages"


class _Params:
    chart_layout_name = "i1Pro · A4-2052p-4pages · Standard Patch Set v25"
    instrument = "i1"
    paper = "A4"
    left_clip_info = False
    disable_left_border = False
    chromiq_clip_style = False
    chart_notes = ""
    stamp_commands = True
    cal_target = False
    patches = 2052


def _creator(stem):
    from workflow import chart_creator as cc
    c = cc.ChartCreator.__new__(cc.ChartCreator)
    c._should_use_engine = lambda _p: True
    c._count_patches_in_ti1 = lambda _p: 2052
    c._settings = None
    c._file_mgr = type("FM", (), {
        "chart_stem": staticmethod(lambda cal_target=False: stem)})()
    return c


@pytest.fixture(scope="module")
def red_river(tmp_path_factory):
    """The Red River preset built in fixed order, before and after the
    stamp: (tiffs, unstamped copies, strip map)."""
    pytest.importorskip("PyQt6")
    from ui.tabs.tab_chart import KNUT_PRESETS
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    (p,) = [p for p in KNUT_PRESETS if p.slug == SLUG]
    d = tmp_path_factory.mktemp("redriver")
    lr = dict(p.layout_recipe, randomize=False)
    rec = LayoutRecipe.from_dict(lr)
    src = d / "chart.ti1"
    shutil.copy2(ROOT / p.ti1_asset, src)
    res, rec2 = build_from_recipe(src, d / "chart", rec)
    tiffs = [Path(t) for t in sorted(res.tiff_paths)]
    bare = []
    for t in tiffs:
        c = t.with_name(t.stem + ".bare.tif")
        shutil.copy2(t, c)
        bare.append(c)
    params = _Params()
    params.layout_recipe = rec2
    _creator("chart")._stamp_tiff_metadata(tiffs, params)
    sm = json.loads((d / "chart.strips.json").read_text(encoding="utf-8"))
    return tiffs, bare, sm


def _ink(a, b):
    a = tifffile.imread(str(a)).astype(int)
    b = tifffile.imread(str(b)).astype(int)
    return (a - b).max(axis=2) > 0


def test_the_last_strip_of_page_4_is_white_fill_up(red_river):
    """The case is real: the page the review found still has it."""
    tiffs, bare, sm = red_river
    assert len(tiffs) == 4
    p4 = [r for r in sm["patches"] if r["page"] == 3]
    last_x = max(r["x"] for r in p4)
    col = [r for r in p4 if r["x"] == last_x]
    img = tifffile.imread(str(bare[3]))
    white = sum(1 for r in col
                if img[r["y"] + 5:r["y"] + r["h"] - 5,
                       r["x"] + 5:r["x"] + r["w"] - 5].min() >= 250)
    assert white >= 20, white


def test_no_stamp_pixel_inside_any_measured_patch(red_river):
    tiffs, bare, sm = red_river
    hit = []
    for page, (t, b) in enumerate(zip(tiffs, bare)):
        ink = _ink(b, t)
        assert ink.sum() > 1000, f"page {page + 1} has no stamp at all"
        for r in sm["patches"]:
            if r["page"] != page:
                continue
            n = int(ink[r["y"]:r["y"] + r["h"], r["x"]:r["x"] + r["w"]].sum())
            if n:
                hit.append((page + 1, r["loc"], n))
    assert hit == [], f"{len(hit)} measured patches overprinted: {hit[:6]}"


def test_the_stamp_sits_right_of_the_true_block_on_page_4(red_river):
    tiffs, bare, sm = red_river
    ink = _ink(bare[3], tiffs[3])
    right = max(r["x"] + r["w"] for r in sm["patches"] if r["page"] == 3)
    cols = np.where(ink.any(axis=0))[0]
    assert cols.min() >= right, (cols.min(), right)


# ── synthetic pages: the limit changes nothing it should not ──

DPI = 300


def _px(mm):
    return int(round(mm * DPI / 25.4))


def _page(path, strips, white_last=False, w_mm=120.0, h_mm=150.0):
    """A page with patch strips at the given (x_mm, w_mm); the last one
    pure white (fill-up) when *white_last*."""
    H, W = _px(h_mm), _px(w_mm)
    a = np.full((H, W, 3), 255, np.uint8)
    rng = np.random.default_rng(7)
    for i, (x, w) in enumerate(strips):
        if white_last and i == len(strips) - 1:
            continue
        for y in range(_px(20), _px(130), _px(8)):
            a[y:y + _px(8), _px(x):_px(x + w)] = rng.integers(0, 200, 3)
    tifffile.imwrite(str(path), a, photometric="rgb",
                     resolution=(DPI, DPI), resolutionunit="INCH")
    return path


def _stamp(path, right_mm=None, size_pt=0.0):
    tiff_metadata.stamp_chart_metadata(
        [path], ["targen -v -d2 -G -e6 -B6 -f2052 chart", "ChromIQ 4.3.42"],
        text_edge_mm=4.0, size_pt=size_pt,
        patch_spans_mm={str(path): (20.0, 130.0)},
        **({"patch_right_mm": {str(path): right_mm}} if right_mm else {}))


STRIPS = [(10.0, 8.0), (20.0, 8.0), (30.0, 8.0), (40.0, 8.0)]


def test_a_page_whose_last_strip_is_inked_is_stamped_byte_identically(tmp_path):
    a = _page(tmp_path / "a.tif", STRIPS)
    b = _page(tmp_path / "b.tif", STRIPS)
    _stamp(a)
    _stamp(b, right_mm=48.0)
    assert a.read_bytes() == b.read_bytes()


def test_a_white_last_strip_is_not_paper(tmp_path):
    bare = _page(tmp_path / "bare.tif", STRIPS, white_last=True)
    old = _page(tmp_path / "old.tif", STRIPS, white_last=True)
    new = _page(tmp_path / "new.tif", STRIPS, white_last=True)
    _stamp(old)                      # the raster alone: the bug
    _stamp(new, right_mm=48.0)       # the map's right edge
    x0, x1 = _px(40.0), _px(48.0)
    assert _ink(bare, old)[:, x0:x1].sum() > 0, "the old path no longer shows the fault"
    assert _ink(bare, new)[:, x0:x1].sum() == 0
    assert np.where(_ink(bare, new).any(axis=0))[0].min() >= x1


def test_no_room_beside_the_true_edge_takes_the_ruled_overlap_path(
        tmp_path, caplog):
    """A white last strip that ends just short of the page-edge reserve: the
    note does not fit beside it, so it is printed anyway and logged, as
    Knut's 2026-09-10 ruling has it for every note that does not fit."""
    strips = [(70.0, 8.0), (80.0, 8.0), (90.0, 8.0), (100.0, 14.5)]
    bare = _page(tmp_path / "bare.tif", strips, white_last=True)
    new = _page(tmp_path / "new.tif", strips, white_last=True)
    with caplog.at_level(logging.INFO, logger=tiff_metadata.log.name):
        _stamp(new, right_mm=114.5)
    assert "overlaps the patch block" in caplog.text
    assert _ink(bare, new).sum() > 0             # never dropped


# ── the page is its place in the list, not a number in the name ──

def _map(folder, stem, pages):
    doc = {"dpi": 200, "patches": [
        {"page": p, "x": 10, "y": 100 + 50 * p, "w": 50, "h": 50}
        for p in range(pages)]}
    (folder / f"{stem}.strips.json").write_text(json.dumps(doc),
                                                encoding="utf-8")


@pytest.mark.parametrize("stem", ["Baryta_2", "Satin_240_17", "plain"])
def test_a_one_page_chart_whose_name_ends_in_a_number_keeps_its_patch_area(
        tmp_path, stem):
    _map(tmp_path, stem, 1)
    tif = tmp_path / f"{stem}.tif"
    boxes = _creator(stem)._engine_page_patch_boxes_mm([tif], _Params())
    k = 25.4 / 200
    assert boxes[str(tif)] == pytest.approx((100 * k, 150 * k, 60 * k))


def test_each_page_of_a_multi_page_chart_is_its_place_in_the_list(tmp_path):
    _map(tmp_path, "Baryta_2", 3)
    tiffs = [tmp_path / f"Baryta_2_{i:02d}.tif" for i in (1, 2, 3)]
    boxes = _creator("Baryta_2")._engine_page_patch_boxes_mm(tiffs, _Params())
    k = 25.4 / 200
    for p, t in enumerate(tiffs):
        assert boxes[str(t)][0] == pytest.approx((100 + 50 * p) * k)


def test_a_list_shorter_than_the_map_is_not_guessed_at(tmp_path):
    _map(tmp_path, "c", 3)
    assert _creator("c")._engine_page_patch_boxes_mm(
        [tmp_path / "c_01.tif"], _Params()) is None
