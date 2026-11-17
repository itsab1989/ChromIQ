"""4.3.45: the `{patchsize}` placeholder (jctay, printerknowledge forum post
150317).

`{patchsize}` prints the chart's patch as it was REALLY laid out, across the
strip x along it, in millimetres with one decimal each and no spaces
("7.0x7.4"): the two numbers, in the same order, that Create Chart's "Patch
size (mm)" boxes take and the Chart layout information's "Patch size" row
shows. Pinned here:

1. the text (one decimal each, a half up, "x", no spaces; empty = unknown);
2. the engine's number is the LAID-OUT size (what was typed, or what fitting
   made of it), not the first patch's pixel box: the review's M1, decided.
   It stays within a pixel of the panel's "on screen" row, for square
   patches, hexagons, a ColorMunki, a CR30 and a size that is not a whole
   number of pixels; and it is printed in the Sheet text and the clip
   border's text exactly as the same characters typed by hand;
3. the run's Chart Notes get it, from the engine's build and from a printtarg
   chart's own .cht, and print nothing where the size cannot be known;
4. a chart that does not use it is byte-identical to one built with 4.3.44's
   placeholder values (no `patchsize` at all), the .ti2's CREATED line aside;
5. it is offered and explained wherever the other placeholders are.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
import tifffile

from workflow.layout_engine import chart, raster
from workflow.layout_engine.chart import (patch_size_text,
                                          text_placeholder_context)
from workflow.layout_engine.presets import LayoutRecipe

TI1 = Path(__file__).parent / "data" / "targen350_rgb.ti1"


# ---- 1. the text ---------------------------------------------------------------

@pytest.mark.parametrize("size,text", [
    ((7.0, 7.4), "7.0x7.4"),
    ((7.027, 7.366), "7.0x7.4"),
    ((7.35, 7.25), "7.4x7.3"),          # a half rounds up
    # through the panel's two decimals: it shows 7.35 and 7.25
    ((7.349999, 7.2500001), "7.4x7.3"),
    ((7.344, 7.2449), "7.3x7.2"),
    ((28.02, 13.97), "28.0x14.0"),
    ((6.94, 8.02), "6.9x8.0"),
    ((120.0, 0.96), "120.0x1.0"),
])
def test_one_decimal_each_across_then_along_no_spaces(size, text):
    assert patch_size_text(size) == text


@pytest.mark.parametrize("size", [None, (), (7.0,), (0.0, 7.4), (7.0, -1.0),
                                  ("a", "b"), (float("nan"), 7.0),
                                  (float("inf"), 7.0)])
def test_no_size_is_no_text(size):
    assert patch_size_text(size) == ""


def test_unknown_prints_nothing_like_an_empty_description():
    ctx = text_placeholder_context(project="P", rundescription="")
    assert ctx["patchsize"] == "" and ctx["rundescription"] == ""
    assert raster.resolve_placeholders("{patchsize}", ctx) == ""
    assert raster.resolve_placeholders("{project} {patchsize}", ctx) == "P "
    ctx = text_placeholder_context(patch_size_mm=(7.0, 7.4))
    assert raster.resolve_placeholders("patches {patchsize} mm", ctx) == \
        "patches 7.0x7.4 mm"
    # not one of the names any more that are printed as typed
    assert raster.resolve_placeholders("{patchsize}x", ctx) == "7.0x7.4x"


# ---- 2. the engine's number is the panel's, and it is printed -----------------

def _recipe(**kw):
    base = dict(instrument="i1", paper="A4", dpi=150, seed=3,
                layout_mode="patch_first")
    base.update(kw)
    return LayoutRecipe(**base)


def _build(tmp: Path, name: str, rec):
    d = tmp / name
    d.mkdir()
    res, used = chart.build_from_recipe(TI1, d / "c", rec)
    return res, used, d


_SIZES = [
    dict(),
    dict(patch_w_mm=7.0, patch_h_mm=7.4),
    dict(instrument="p3", dpi=200, patch_w_mm=7.59, patch_h_mm=7.59),
    dict(instrument="SS", hflag=True),
    dict(instrument="CM"),
    dict(instrument="CR30"),
    dict(instrument="CR30", hflag=True, hex_flat_top=True),
]
_SIZE_IDS = ["i1", "7.0x7.4", "p3_not_whole_pixels", "ss_hex", "cm", "cr30",
             "cr30_turned_hex"]


@pytest.mark.parametrize("kw", _SIZES, ids=_SIZE_IDS)
def test_the_number_is_the_laid_out_size_not_the_pixels(tmp_path, kw):
    """M1 of the 4.3.45 review, decided: `{patchsize}` is the size the layout
    was built on (typed, or what fitting made of it), a hexagon tip to tip.
    The Chart layout information's "on screen" row reads the first patch as
    drawn in whole pixels, so it may differ, by less than a pixel (a
    hexagon's tip-to-tip by 4/3 of one)."""
    from ui.tabs.tab_chart import TabChart
    res, used, d = _build(tmp_path, "c", _recipe(**kw))
    st = json.loads((d / "c.strips.json").read_text(encoding="utf-8"))
    (d / "c.channels.json").write_text(json.dumps({"layout": {
        "patches": st["patches"], "dpi": st["dpi"],
        "recipe": used.to_dict()}}), encoding="utf-8")
    pw, ph, _pitch = TabChart._chart_patch_size_mm(res.ti2_path)
    px = 25.4 / st["dpi"] * 4 / 3 + 1e-9
    assert abs(res.patch_size_mm[0] - pw) <= px
    assert abs(res.patch_size_mm[1] - ph) <= px


@pytest.mark.parametrize("kw,expected", [
    (dict(patch_w_mm=7.0, patch_h_mm=7.4), "7.0x7.4"),        # 41/42 px
    (dict(patch_w_mm=7.0, patch_h_mm=7.4, dpi=300), "7.0x7.4"),
    (dict(instrument="p3", dpi=200, patch_w_mm=7.59, patch_h_mm=7.59),
     "7.6x7.6"),
    (dict(instrument="SS"), "7.0x7.0"),
    (dict(instrument="CM"), "28.0x14.0"),
    (dict(), "8.0x10.0"),
    (dict(instrument="CR30"), "12.0x12.0"),
], ids=["150dpi", "300dpi", "p3_200dpi", "ss", "cm", "i1", "cr30"])
def test_what_was_typed_or_the_default_is_printed(tmp_path, kw, expected):
    """The review's table (M1): at 150 dpi 7.0 x 7.4 used to print "6.9x7.5",
    the SpectroScan "7.1x6.9", the ColorMunki "27.9x14.1", the i1Pro 3's
    7.59 mm "7.5x7.6"; the Create Chart Preview line said "7.0x7.4"."""
    res, _u, _d = _build(tmp_path, "c", _recipe(**kw))
    assert patch_size_text(res.patch_size_mm) == expected


def test_the_sizes_typed_come_back_in_the_same_order(tmp_path):
    res, _u, _d = _build(tmp_path, "c", _recipe(patch_w_mm=7.0,
                                                 patch_h_mm=7.4, dpi=300))
    assert patch_size_text(res.patch_size_mm) == "7.0x7.4"
    res, _u, _d = _build(tmp_path, "d", _recipe(patch_w_mm=9.0,
                                                 patch_h_mm=6.0, dpi=300))
    assert patch_size_text(res.patch_size_mm) == "9.0x6.0"
    res, _u, _d = _build(tmp_path, "e", _recipe(patch_w_mm=9.0,
                                                 patch_h_mm=6.0, dpi=150))
    assert patch_size_text(res.patch_size_mm) == "9.0x6.0"


def test_the_preview_line_and_the_sheet_agree(tmp_path, qapp):
    """What the Preview line of Create Chart shows for typed boxes is what
    the sheet prints, also where the pixels cannot draw it exactly."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    panel = LayoutOptionsPanel()
    panel.patch_x.setValue(7.0)
    panel.patch_y.setValue(7.4)
    res, _u, _d = _build(tmp_path, "c", _recipe(patch_w_mm=7.0,
                                                 patch_h_mm=7.4, dpi=150))
    assert panel._resolve_sample("{patchsize}") == \
        patch_size_text(res.patch_size_mm) == "7.0x7.4"


def test_an_area_fitted_patch_is_the_one_laid_out(tmp_path):
    """"Prioritise chart area" works the size out: the placeholder is that
    size, not the boxes' "auto", and the pitch the strips record averages
    to it."""
    res, _u, d = _build(tmp_path, "c", _recipe(layout_mode="area_first"))
    st = json.loads((d / "c.strips.json").read_text(encoding="utf-8"))
    pats = st["patches"]
    mean_h = sum(r["h"] for r in pats) / len(pats) * 25.4 / st["dpi"]
    w0 = pats[0]["w"] * 25.4 / st["dpi"]
    one = 25.4 / st["dpi"] + 1e-9
    assert res.patch_size_mm is not None
    assert abs(res.patch_size_mm[0] - w0) <= one
    assert abs(res.patch_size_mm[1] - mean_h) <= one


def test_a_hexagon_is_measured_tip_to_tip_from_its_laid_out_slot():
    from workflow.hex_support import shown_patch_size_mm
    from workflow.layout_engine import instruments
    from workflow.layout_engine.chart import laid_out_patch_size_mm
    for inst, kw in (("CR30", dict(hflag=True)),
                     ("CR30", dict(hflag=True, hex_flat_top=True)),
                     ("SS", dict(hflag=True)), ("i1", {}), ("CM", {})):
        g = instruments.build(inst, **kw)
        assert laid_out_patch_size_mm(g) == shown_patch_size_mm(
            g.pwid, g.plen, instruments.is_hexagonal(g),
            bool(getattr(g, "hex_flat_top", False)))[:2]
        if not instruments.is_hexagonal(g):
            assert laid_out_patch_size_mm(g) == (g.pwid, g.plen)


@pytest.mark.parametrize("instr", ["i1", "CR30"])
def test_the_sheet_text_prints_it_as_if_typed(tmp_path, instr):
    kw = dict(instrument=instr, patch_w_mm=8.0, patch_h_mm=9.5,
              chart_text_size_mm=3.0)
    a, _u, _d = _build(tmp_path, "a", _recipe(chart_text="size {patchsize}",
                                              **kw))
    typed = "size " + patch_size_text(a.patch_size_mm)
    b, _u, _d = _build(tmp_path, "b", _recipe(chart_text=typed, **kw))
    assert typed == "size 8.0x9.5" or instr == "CR30"
    for pa, pb in zip(a.tiff_paths, b.tiff_paths):
        assert np.array_equal(tifffile.imread(str(pa)),
                              tifffile.imread(str(pb)))


def test_the_clip_borders_text_is_drawn_with_it(tmp_path, monkeypatch):
    """The clip border's text is drawn with `{patchsize}` filled in (and,
    since the review's N2, measured with it: the next test)."""
    drawn = []
    real = raster.render_clip_strip

    def spy(mode, **kw):
        drawn.append(kw.get("text"))
        return real(mode, **kw)
    monkeypatch.setattr(raster, "render_clip_strip", spy)
    raster._clip_reach_cached.cache_clear()
    a, _u, _d = _build(tmp_path, "a", _recipe(
        patch_w_mm=8.0, patch_h_mm=9.5, clip_border=True,
        clip_content_mode="text", clip_text="{patchsize} mm"))
    raster._clip_reach_cached.cache_clear()
    assert patch_size_text(a.patch_size_mm) == "8.0x9.5"
    assert "8.0x9.5 mm" in drawn


@pytest.mark.parametrize("size_mm", [0.0, 3.0])
def test_the_clip_borders_reach_is_measured_with_the_real_text(tmp_path,
                                                                size_mm):
    """Review of 4.3.45, N2: the clip content's reach was measured with
    `{patchsize}` empty, seven characters shorter than it prints. Now the
    same text typed by hand and the placeholder lay out the same chart."""
    kw = dict(patch_w_mm=8.0, patch_h_mm=9.5, clip_border=True, show_row_indicators=True,
              clip_content_mode="text", clip_text_size_mm=size_mm)
    raster._clip_reach_cached.cache_clear()
    a, _u, _d = _build(tmp_path, "a", _recipe(
        clip_text="size {patchsize} mm", **kw))
    raster._clip_reach_cached.cache_clear()
    b, _u, _d = _build(tmp_path, "b", _recipe(clip_text="size 8.0x9.5 mm",
                                              **kw))
    raster._clip_reach_cached.cache_clear()
    for pa, pb in zip(a.tiff_paths, b.tiff_paths):
        assert np.array_equal(tifffile.imread(str(pa)),
                              tifffile.imread(str(pb)))


def test_the_rule_is_the_panels_rule():
    """`hex_support.shown_patch_size_mm` is the builder's copy of the
    panel's `_panel_patch_size_mm` (the builder may not import the UI)."""
    from ui.tabs.tab_chart import _panel_patch_size_mm
    from workflow.hex_support import shown_patch_size_mm
    for w in (0.0, 5.0, 7.03, 11.3):
        for h in (0.0, 6.0, 9.78, 13.0):
            for hexa in (False, True):
                for flat in (False, True):
                    assert shown_patch_size_mm(w, h, hexa, flat) == \
                        _panel_patch_size_mm(w, h, hexa, flat)


# ---- 3. the Chart Notes ---------------------------------------------------------

def _creator_and_params(notes, instrument="i1", **kw):
    from tests.test_4344_placeholders_in_chart_notes_and_logo import (
        _creator, _params)
    p = _params(notes)
    p.instrument = instrument
    for k, v in kw.items():
        setattr(p, k, v)
    return _creator(), p


def test_the_notes_print_the_engines_size():
    cc, p = _creator_and_params("{page} {patchsize}")
    cc._notes_build = {"seed": 7, "randomize": True, "date": "2026-11-17",
                       "pages": 1, "patches": 192,
                       "patch_size_mm": (7.027, 7.366)}
    assert cc.stamp_lines(p, 192, ctx=cc.notes_context(p, 1, 1, 192)) == \
        ["page 1/1 7.0x7.4"]
    assert p.chart_notes == "{page} {patchsize}"     # stored as typed


def test_unknown_in_the_notes_prints_nothing():
    cc, p = _creator_and_params("Rag {patchsize}")
    assert cc.stamp_lines(p, 10, ctx=cc.notes_context(p, 1, 1, 10)) == ["Rag"]


def _cht(widths_by_strip, h=10.0, step=11.0, n=4):
    lines = ["", "BOXES 99"]
    x = 20.0
    for s, w in enumerate(widths_by_strip):
        for j in range(n):
            lines.append(f"  X {chr(65 + s)}{j + 1} {chr(65 + s)}{j + 1} _ _ "
                         f"{w:.6f} {h:.6f} {x:.6f} {260 - j * step:.6f} 0 0")
        x += w
    return "\n".join(lines) + "\n"


def _sidecar(tmp, pages, engine="printtarg"):
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "c.channels.json").write_text(json.dumps({"layout": {
        "engine": engine, "cht_pages": pages}}), encoding="utf-8")
    return tmp


@pytest.mark.parametrize("inst,pages,expected", [
    ("i1", [_cht([12.0, 8.0, 8.0])], (8.0, 10.0)),
    ("i1", [_cht([12.0, 8.0]), _cht([12.0, 8.0, 8.0])], (8.0, 10.0)),
    ("CM", [_cht([42.0, 28.0], h=14.0)], (28.0, 14.0)),
    ("p3", [_cht([24.0, 16.0], h=20.0)], (16.0, 20.0)),
    ("i1", [_cht([12.0])], None),                   # one strip a page
    ("i1", [_cht([12.0, 8.0]), _cht([12.0])], (8.0, 10.0)),
    ("i1", [_cht([12.0]), _cht([12.0])], None),
    ("i1", [_cht([13.0, 8.0])], None),              # not printtarg's rule
    ("i1", [_cht([12.0, 8.0, 7.0])], None),
    ("DTP41", [_cht([12.0, 8.0])], None),           # not measured
    ("i1", [], None),
])
def test_a_printtarg_charts_size_is_read_from_its_cht(tmp_path, inst, pages,
                                                      expected):
    cc, p = _creator_and_params("{patchsize}", instrument=inst)
    d = _sidecar(tmp_path / "w", pages)
    assert cc._printtarg_patch_size_mm(d, "c", p) == expected


def test_printtarg_hexagons_and_derived_layouts_are_unknown(tmp_path):
    cc, p = _creator_and_params("{patchsize}", instrument="SS",
                                double_density=True)
    d = _sidecar(tmp_path / "a", [_cht([10.5, 7.0], h=7.0)])
    assert cc._printtarg_patch_size_mm(d, "c", p) is None
    cc, p = _creator_and_params("{patchsize}", instrument="SS")
    assert cc._printtarg_patch_size_mm(d, "c", p) == (7.0, 7.0)
    d = _sidecar(tmp_path / "b", [_cht([12.0, 8.0])], engine="derived")
    cc, p = _creator_and_params("{patchsize}")
    assert cc._printtarg_patch_size_mm(d, "c", p) is None
    assert cc._printtarg_patch_size_mm(tmp_path / "none", "c", p) is None


@pytest.mark.parametrize("args,expected", [
    (["-ii1"], "8.0x10.0"),
    (["-ii1", "-a1.3"], "10.4x13.0"),
    (["-iCM"], "28.0x14.0"),
    (["-iCM", "-h"], "13.7x14.0"),
])
def test_printtargs_own_cht_against_its_printed_page(tmp_path, args,
                                                     expected):
    """Measured on the page printtarg prints (without -s): the patch is
    the .cht's box, the first strip of a -s page aside."""
    from core.resource_path import argyll_binary
    pt = Path("/Applications/Argyll/bin") / argyll_binary("printtarg")
    if not pt.exists():
        pytest.skip("ArgyllCMS printtarg not installed")
    for sub, extra in (("s", ["-s", "-t72"]), ("n", ["-T200"])):
        (tmp_path / sub).mkdir()
        shutil.copy(TI1, tmp_path / sub / "c.ti1")
        subprocess.run([str(pt), *extra, *args, "-pA4", "c"],
                       cwd=tmp_path / sub, capture_output=True, timeout=120)
    pages = [c.read_text(encoding="utf-8") for c in sorted((tmp_path / "s").glob("c*.cht"))]
    _sidecar(tmp_path / "s", pages)
    cc, p = _creator_and_params("{patchsize}",
                                instrument=args[0][2:],
                                double_density="-h" in args)
    size = cc._printtarg_patch_size_mm(tmp_path / "s", "c", p)
    assert patch_size_text(size) == expected
    # the printed page: strip widths across a row, patch lengths down one
    page = sorted((tmp_path / "n").glob("c*.tif"))[0]
    img = tifffile.imread(str(page))[..., :3].astype(int)
    s = 200 / 25.4
    row = img[int(200 * s)]
    edges = np.where(np.abs(np.diff(row, axis=0)).max(axis=1) > 200)[0]
    pitches = np.round(np.diff(edges) / s, 1)
    assert any(abs(v - size[0]) <= 0.15 for v in pitches), pitches


def test_printtarg_notes_without_a_placeholder_never_read_the_cht(
        monkeypatch, tmp_path):
    from workflow.chart_creator import ChartCreator
    cc, p = _creator_and_params("Photo Rag 308")
    monkeypatch.setattr(ChartCreator, "_printtarg_patch_size_mm",
                        lambda *a, **k: pytest.fail("read for no reason"))
    seen = []
    monkeypatch.setattr(ChartCreator, "_stamp_tiff_metadata",
                        lambda self, t, prm: seen.append(self._notes_build))
    monkeypatch.setattr(ChartCreator, "_write_channel_sidecar",
                        lambda *a, **k: None)
    monkeypatch.setattr(ChartCreator, "_capture_scanner_cht",
                        lambda *a, **k: None)
    (tmp_path / "c.tif").write_bytes(b"")
    cc._pending_params = p
    cc._printtarg_done(0, tmp_path, None, stem="c")
    assert seen == [None] and cc._notes_build is None


def test_printtarg_notes_with_it_are_handed_the_size(monkeypatch, tmp_path):
    from workflow.chart_creator import ChartCreator
    cc, p = _creator_and_params("{patchsize}")
    seen = []
    monkeypatch.setattr(ChartCreator, "_stamp_tiff_metadata",
                        lambda self, t, prm: seen.append(
                            self.stamp_lines(prm, 10, ctx=self.notes_context(
                                prm, 1, 1, 10))))
    monkeypatch.setattr(ChartCreator, "_write_channel_sidecar",
                        lambda *a, **k: None)
    monkeypatch.setattr(ChartCreator, "_capture_scanner_cht",
                        lambda *a, **k: None)
    _sidecar(tmp_path, [_cht([12.0, 8.0])])
    (tmp_path / "c.tif").write_bytes(b"")
    cc._pending_params = p
    cc._printtarg_done(0, tmp_path, None, stem="c")
    assert seen == [["8.0x10.0"]] and cc._notes_build is None


# ---- 4. a chart without it is 4.3.44's, byte for byte ---------------------------

def _digest(folder: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(folder.iterdir()):
        data = p.read_bytes()
        if p.suffix == ".ti2":
            data = b"\n".join(l for l in data.splitlines()
                              if not l.startswith(b"CREATED"))
        h.update(p.name.encode() + b"\0" + data)
    return h.hexdigest()


def _as_4344(monkeypatch):
    """4.3.44's placeholder values: no `patchsize` key, no size worked out."""
    real = chart.text_placeholder_context

    def old_ctx(**kw):
        kw.pop("patch_size_mm", None)
        ctx = real(**kw)
        ctx.pop("patchsize")
        return ctx
    monkeypatch.setattr(chart, "text_placeholder_context", old_ctx)
    monkeypatch.setattr(chart, "laid_out_patch_size_mm",
                        lambda *a, **k: None)


IDENTITY = [
    dict(),
    dict(chart_text="{project} - {rundescription} - {page} - {paper} - "
                    "{instrument} - {patchcount} - {pages} - {seed} - {dpi} "
                    "{logo} {abc}", chart_text_size_mm=3.0),
    dict(clip_border=True, clip_content_mode="text",
         clip_text="{project}\n{page} {date} {seed}"),
    dict(clip_border=True, clip_content_mode="notes"),
    dict(instrument="SS", hflag=True, chart_text="{patchcount}"),
    dict(instrument="CM", randomize=False, chart_text="{seed} {date}"),
    dict(instrument="CR30", layout_mode="area_first", stamp_command=True),
]


@pytest.mark.parametrize("kw", IDENTITY, ids=[str(i) for i in
                                              range(len(IDENTITY))])
def test_a_chart_without_it_is_byte_identical_to_4344s(tmp_path, monkeypatch,
                                                        kw):
    rec = _recipe(**kw)
    raster._clip_reach_cached.cache_clear()
    _build(tmp_path, "new", rec)
    with monkeypatch.context() as m:
        _as_4344(m)
        raster._clip_reach_cached.cache_clear()
        _build(tmp_path, "old", rec)
    raster._clip_reach_cached.cache_clear()
    assert _digest(tmp_path / "new") == _digest(tmp_path / "old")


# ---- 5. offered and explained where the others are ------------------------------

def test_the_insert_menu_offers_it():
    from ui.dialogs.layout_options_panel import SHEET_TOKENS
    assert "patchsize" in dict(SHEET_TOKENS)


def test_every_help_that_lists_the_placeholders_explains_it():
    import inspect
    from ui.dialogs import layout_options_panel as lop
    from ui.tabs import tab_chart
    text = lop.patchsize_help()
    assert "{patchsize}" in text and "“7.0x7.4”" in text
    assert "across the strip" in text and "along the strip" in text
    assert "—" not in text
    src = inspect.getsource(lop)
    # the Sheet text's and the clip border's help
    assert src.count('+ "\\n\\n" + patchsize_help()') == 2
    assert '+ "\\n\\n" + _patchsize_help()' in inspect.getsource(tab_chart)


def test_the_preview_line_fills_it(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    panel = LayoutOptionsPanel()
    panel.patch_x.setValue(7.0)
    panel.patch_y.setValue(7.4)
    assert panel._resolve_sample("{patchsize}") == "7.0x7.4"
    panel.patch_x.setValue(0.0)
    assert panel._resolve_sample("{patchsize}") == "7.0x7.4"   # a sample


def test_the_width_prediction_uses_the_estimate():
    from types import SimpleNamespace
    from ui.tabs.tab_chart import TabChart
    tab = SimpleNamespace(_layout_info_panel=SimpleNamespace(
        predicted=lambda: {"patch": (7.03, 7.37)}))
    assert TabChart._predicted_patch_size(tab) == (7.03, 7.37)
    tab = SimpleNamespace(_layout_info_panel=SimpleNamespace(
        predicted=lambda: None))
    assert patch_size_text(TabChart._predicted_patch_size(tab)) == "88.8x88.8"
    tab = SimpleNamespace()
    assert TabChart._predicted_patch_size(tab) == (88.8, 88.8)
    # the laid-out size the estimate was worked out from wins over the
    # pixels it shows: that is what the sheet prints (M1)
    tab = SimpleNamespace(_laid_out_patch_estimate=(7.0, 7.4),
                          _layout_info_panel=SimpleNamespace(
                              predicted=lambda: {"patch": (6.94, 7.45)}))
    assert TabChart._predicted_patch_size(tab) == (7.0, 7.4)
