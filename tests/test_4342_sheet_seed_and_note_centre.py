"""Two faults on a tester's sheet (jctay, forum 150283, 2026-11-16).

His chart: Canon SELPHY CP1500, 192 patches on two 10 x 15 cm pages, i1Pro 3,
ChromIQ's own layout engine, "Randomise patch order" OFF.

(a) The text up the sheet printed "seed 158695260" although the order was not
    randomised. With randomising off the seed decides nothing on the sheet
    (`permutation.location_permutation` keeps every patch where it is, and no
    spacer, label or mark is drawn from it), so `{seed}` and the layout
    stamp's "seed N" are now left out there, with the separator in front.
(b) The line down the right edge ("Chart layout ... | ChromIQ layout engine |
    ChromIQ 4.3.41") was centred on the paper between the two end reserves,
    and with 28 mm above the patches and 12 mm below it sat 8 mm off the
    middle of the patch area. It is now centred on each page's patch area,
    read from the engine's own strip map, and still never leaves the reserves.

The patches themselves do not move: the work notes of 2026-11-16
(fixround/s4/cmp_geometry.py) compared the strip map, the .ti2 and every
pixel inside every patch rectangle on ten charts across seven instruments,
before and after: all identical.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import tifffile

from workflow import tiff_metadata
from workflow.layout_engine.chart import (stamp_summary_line,
                                          text_placeholder_context)
from workflow.layout_engine.raster import resolve_placeholders

HIS = "{project} - {date} - {instrument} - {seed} - {page}"


def _ctx(randomize):
    c = text_placeholder_context(project="CP1500-192p", instrument="i1",
                                 seed=158695260, chart_date="2026-11-16",
                                 randomize=randomize)
    c["page"] = "page 1/2"
    return c


# ------------------------------------------------------------- (a) the seed
def test_his_line_names_no_seed_when_the_order_is_not_randomised():
    off = resolve_placeholders(HIS, _ctx(False))
    assert "seed" not in off and "158695260" not in off
    assert off == "CP1500-192p - 2026-11-16 - i1Pro - page 1/2"


def test_a_randomised_chart_still_prints_its_seed():
    on = resolve_placeholders(HIS, _ctx(True))
    assert on == "CP1500-192p - 2026-11-16 - i1Pro - seed 158695260 - page 1/2"


@pytest.mark.parametrize("text,expected", [
    ("{seed} - {page}", "page 1/2"),
    ("{page} | {seed}", "page 1/2"),
    ("{page}, {seed}", "page 1/2"),
    ("{seed}", ""),
    ("a\n{seed} - {page}", "a\npage 1/2"),
    ("{page}\n{seed}", "page 1/2\n"),
])
def test_the_separator_goes_with_the_seed(text, expected):
    assert resolve_placeholders(text, _ctx(False)) == expected


def test_the_layout_stamp_names_a_seed_only_on_a_randomised_chart():
    on = stamp_summary_line("i1", "A4", 300, 192, 42)
    off = stamp_summary_line("i1", "A4", 300, 192, 42, randomize=False)
    assert on.endswith("192 patches · seed 42")
    assert off.endswith("192 patches") and "seed" not in off


def test_the_build_hands_the_renderer_no_seed_when_not_randomised(
        tmp_path, monkeypatch):
    """Through `build_chart` itself: the context and the stamp the renderer
    is given, randomised and not."""
    from workflow.layout_engine import chart, raster
    from workflow.layout_engine.presets import LayoutRecipe
    seen = {}

    class _Stop(Exception):
        pass

    def spy(*a, **kw):
        seen.update(ctx=kw.get("text_ctx"), stamp=kw.get("stamp_text"))
        raise _Stop

    monkeypatch.setattr(raster, "render_pages", spy)
    ti1 = Path(__file__).parent / "data" / "targen350_rgb.ti1"
    for rnd in (False, True):
        seen.clear()
        rec = LayoutRecipe(instrument="i1", paper="A4", randomize=rnd,
                           seed=7, stamp_command=True)
        with pytest.raises(_Stop):
            chart.build_from_recipe(ti1, tmp_path / f"c{int(rnd)}", rec)
        assert seen["ctx"]["seed"] == ("seed 7" if rnd else "")
        assert ("seed 7" in seen["stamp"]) is rnd


def test_the_panel_predicts_the_line_the_sheet_prints():
    """The Create Chart panel's width check builds its context from the same
    function, and passes the recipe's randomisation."""
    import inspect
    from ui.tabs import tab_chart
    src = inspect.getsource(tab_chart.TabChart._text_placeholder_context)
    assert 'randomize=bool(getattr(r, "randomize", True))' in src
    src = inspect.getsource(tab_chart.TabChart._bottom_sheet_text_lines)
    assert 'randomize=bool(getattr(r, "randomize", True))' in src


# ---------------------------------------------------------- (b) the centre
DPI = 200


def _mm(v):
    return int(round(v * DPI / 25.4))


def _sheet(path, top_mm=28.0, bottom_mm=137.0, w_mm=100.0, h_mm=150.0):
    W, H = _mm(w_mm), _mm(h_mm)
    arr = np.full((H, W, 3), 255, dtype=np.uint8)
    arr[_mm(top_mm):_mm(bottom_mm), _mm(10.0):_mm(88.0)] = 128
    tifffile.imwrite(str(path), arr, resolution=(DPI, DPI),
                     resolutionunit="INCH")
    return path


LINE = ["Chart layout CP1500-192p", "ChromIQ 4.3.42"]


def _note_rows_mm(path, control):
    a = tifffile.imread(str(control)).min(axis=2).astype(int)
    b = tifffile.imread(str(path)).min(axis=2).astype(int)
    rows = np.where(((a - b) > 40).any(axis=1))[0]
    assert rows.size
    k = 25.4 / DPI
    return rows[0] * k, rows[-1] * k


def test_the_line_is_centred_on_the_patch_area(tmp_path):
    control = _sheet(tmp_path / "control.tif")
    old = _sheet(tmp_path / "old.tif")
    new = _sheet(tmp_path / "new.tif")
    kw = dict(text_edge_mm=4.0, text_edge_top_mm=7.0, text_edge_bottom_mm=7.0)
    tiff_metadata.stamp_chart_metadata([old], LINE, **kw)
    tiff_metadata.stamp_chart_metadata(
        [new], LINE, patch_spans_mm={str(new): (28.0, 137.0)}, **kw)
    o0, o1 = _note_rows_mm(old, control)
    n0, n1 = _note_rows_mm(new, control)
    assert abs((o0 + o1) / 2 - 75.0) < 0.5            # the paper's middle
    assert abs((n0 + n1) / 2 - (28.0 + 137.0) / 2) < 0.5   # the patches'
    assert n1 - n0 == pytest.approx(o1 - o0, abs=0.2)  # same line, same size


def test_a_page_without_a_span_is_stamped_as_before(tmp_path):
    control = _sheet(tmp_path / "control.tif")
    a = _sheet(tmp_path / "a.tif")
    b = _sheet(tmp_path / "b.tif")
    tiff_metadata.stamp_chart_metadata([a], LINE, text_edge_mm=4.0)
    tiff_metadata.stamp_chart_metadata(
        [b], LINE, text_edge_mm=4.0, patch_spans_mm={"elsewhere.tif": (0, 1)})
    assert np.array_equal(tifffile.imread(str(a)), tifffile.imread(str(b)))
    assert _note_rows_mm(a, control)


def test_the_centred_line_never_crosses_an_end_reserve(tmp_path):
    """Patches near the bottom: the line slides back inside the reserve
    rather than leave it."""
    control = _sheet(tmp_path / "control.tif", 100.0, 146.0)
    p = _sheet(tmp_path / "p.tif", 100.0, 146.0)
    tiff_metadata.stamp_chart_metadata(
        [p], LINE * 3, text_edge_mm=4.0, text_edge_top_mm=7.0,
        text_edge_bottom_mm=7.0, patch_spans_mm={str(p): (100.0, 146.0)})
    top, bottom = _note_rows_mm(p, control)
    assert top >= 7.0 and bottom <= 150.0 - 7.0


def test_the_creator_reads_each_pages_patch_area_from_the_strip_map(tmp_path):
    from workflow.chart_creator import ChartCreator
    doc = {"dpi": 200, "patches": [
        {"page": 0, "x": 10, "y": 200, "w": 50, "h": 50},
        {"page": 0, "x": 10, "y": 400, "w": 50, "h": 100},
        {"page": 1, "x": 10, "y": 300, "w": 50, "h": 50}]}
    (tmp_path / "stem.strips.json").write_text(json.dumps(doc), encoding="utf-8")
    tiffs = [tmp_path / "stem_01.tif", tmp_path / "stem_02.tif"]
    c = ChartCreator.__new__(ChartCreator)
    c._file_mgr = type("FM", (), {
        "chart_stem": staticmethod(lambda cal_target=False: "stem")})()

    class _P:
        cal_target = False

    spans = c._engine_patch_spans_mm(tiffs, _P())
    k = 25.4 / 200
    assert spans[str(tiffs[0])] == pytest.approx((200 * k, 500 * k))
    assert spans[str(tiffs[1])] == pytest.approx((300 * k, 350 * k))
    assert c._engine_patch_spans_mm([tmp_path / "x" / "a_01.tif"], _P()) is None


def test_an_engine_chart_hands_its_patch_areas_to_the_stamper(
        tmp_path, monkeypatch):
    from workflow import chart_creator as cc
    from workflow.layout_engine.presets import LayoutRecipe
    seen = {}
    monkeypatch.setattr(tiff_metadata, "stamp_chart_metadata",
                        lambda tiffs, lines, *a, **kw: seen.update(kw))
    (tmp_path / "stem.strips.json").write_text(json.dumps({
        "dpi": 200, "patches": [{"page": 0, "x": 0, "y": 100, "w": 9,
                                 "h": 300}]}), encoding="utf-8")
    tif = tmp_path / "stem.tif"

    class _Params:
        layout_recipe = LayoutRecipe(instrument="i1", paper="A4",
                                     helper_markers=False)
        chart_layout_name = "CP1500-192p"
        instrument = "i1"
        paper = "A4"
        left_clip_info = False
        disable_left_border = False
        chromiq_clip_style = False
        chart_notes = ""
        stamp_commands = True
        cal_target = False
        patches = 1

    creator = cc.ChartCreator.__new__(cc.ChartCreator)
    creator._should_use_engine = lambda _p: True
    creator._count_patches_in_ti1 = lambda _p: 1
    creator._file_mgr = type("FM", (), {
        "chart_stem": staticmethod(lambda cal_target=False: "stem")})()
    creator._stamp_tiff_metadata([tif], _Params())
    k = 25.4 / 200
    assert seen["patch_spans_mm"][str(tif)] == pytest.approx((100 * k,
                                                              400 * k))


def test_the_map_is_read_from_channels_json_after_it_was_folded_in(tmp_path):
    """In the app `_embed_layout_geometry` moves the strip map into
    channels.json and deletes .strips.json before the stamp runs (found on
    screen); the spans come from there."""
    from workflow.chart_creator import ChartCreator
    (tmp_path / "stem.channels.json").write_text(json.dumps({
        "ink_channels": ["r", "g", "b"], "layout": {"dpi": 200, "patches": [
            {"page": 0, "x": 0, "y": 226, "w": 59, "h": 52},
            {"page": 0, "x": 0, "y": 900, "w": 59, "h": 52}]}}),
        encoding="utf-8")
    c = ChartCreator.__new__(ChartCreator)
    c._file_mgr = type("FM", (), {
        "chart_stem": staticmethod(lambda cal_target=False: "stem")})()

    class _P:
        cal_target = False

    tif = tmp_path / "stem.tif"
    k = 25.4 / 200
    assert c._engine_patch_spans_mm([tif], _P())[str(tif)] == \
        pytest.approx((226 * k, 952 * k))
