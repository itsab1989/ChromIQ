"""THE BETA "Custom page size in inches or pixels, and high resolution" (#215).

Asked for by a person who images charts on film recorders: a recorder takes a
frame of an exact pixel count at an exact resolution (4096 x 2730 at 2731
pixels per inch; 8192 x 5460 at 5461; 18796 x 15748 at 2032), reads the
resolution in the file, and scales the picture when it differs.

What is pinned here (`workflow.page_output.support` has the reasons):

1. the stored form: a whole millimetre size is spelt exactly as before, a
   fraction keeps four decimals, a side typed in inches or pixels is kept as
   typed with its unit and resolution, and none of it is written unless used;
2. the pixel rule: a side given in pixels comes out with exactly that many
   pixels, on every page, at every resolution up to 6000;
3. the file's resolution in pixels per inch reads back as the whole number,
   and every reader of a chart's TIFF reads it right;
4. the memory budget refuses a page too large to draw BEFORE anything is
   written, with the page's pixel count;
5. the panel's two-way fields: the typed value is the truth, nothing drifts;
6. with the Beta off, the panel is 4.3.42's and a chart made with the Beta is
   held as it is (never rounded) and refused, with words, when it needs it.
"""
from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
TI1 = ROOT / "tests" / "data" / "targen350_rgb.ti1"

from workflow.page_output import support as po          # noqa: E402

FRAME_4K = {"w": [4096, "px"], "h": [2730, "px"], "ppi": 2731}
FRAME_8K = {"w": [8192, "px"], "h": [5460, "px"], "ppi": 5461}


@pytest.fixture
def beta_on():
    before = po._latched
    po.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        po._latched = before


@pytest.fixture
def beta_off():
    before = po._latched
    po.set_enabled_for_this_process(False)
    try:
        yield
    finally:
        po._latched = before


def _film_recipe(page_size, dpi, *, patch=2.0, unit="in"):
    """A SpectroScan chart on a film frame: small patches, no furniture."""
    from workflow.layout_engine.presets import default_recipe
    w, h = po.page_mm(page_size, dpi)
    r = default_recipe("SS", po.paper_code(w, h))
    return replace(
        r, dpi=dpi, page_size=page_size, tiff_res_unit=unit,
        compression="none", seed=7, patch_w_mm=patch, patch_h_mm=patch,
        margin_top=1.0, margin_right=1.0, margin_bottom=1.0, margin_left=1.0,
        border=1.0, show_strip_indicators=False, spacer_mode="none",
        spacer_on=False, use_instrument_margins=False, chart_text="",
        stamp_command=False, clip_content_mode="off")


def _tags(path):
    import tifffile
    with tifffile.TiffFile(str(path)) as t:
        p = t.pages[0]
        return {"w": p.imagewidth, "h": p.imagelength,
                "bits": tuple(p.tags["BitsPerSample"].value)
                if isinstance(p.tags["BitsPerSample"].value, tuple)
                else (p.tags["BitsPerSample"].value,),
                "samples": p.samplesperpixel,
                "xres": tuple(p.tags["XResolution"].value),
                "yres": tuple(p.tags["YResolution"].value),
                "unit": int(p.tags["ResolutionUnit"].value),
                "compression": int(p.tags["Compression"].value),
                "photometric": int(p.tags["PhotometricInterpretation"].value)}


# ---- 1. the stored form -----------------------------------------------------

def test_a_whole_millimetre_size_is_spelt_as_before():
    assert po.paper_code(210, 297) == "210x297"
    assert po.paper_code(210.0, 297.0) == "210x297"
    assert po.format_mm(100.00001) == "100"


def test_a_fraction_keeps_four_decimals_and_no_trailing_zeros():
    assert po.paper_code(234.95, 196.85) == "234.95x196.85"
    assert po.paper_code(9.25 * 25.4, 7.75 * 25.4) == "234.95x196.85"
    w, h = po.page_mm(FRAME_4K, 2731)
    assert po.paper_code(w, h) == "38.0953x25.3907"


def test_every_reader_of_the_code_reads_the_fraction():
    from data.patch_db import paper_name_token
    from workflow.layout_engine import papers
    assert papers.dimensions_mm("234.95x196.85") == (234.95, 196.85)
    assert paper_name_token("234.95x196.85") == "234.95x196.85mm"


def test_nothing_new_is_written_unless_used():
    from workflow.layout_engine.presets import LayoutRecipe, default_recipe
    for r in (LayoutRecipe(), default_recipe("i1", "A4"),
              default_recipe("SS", "210x297")):
        d = r.to_dict()
        assert "page_size" not in d and "tiff_res_unit" not in d
        kw = r.build_kwargs()
        assert "page_size" not in kw and "tiff_res_unit" not in kw
        assert LayoutRecipe.from_dict(d) == r


def test_a_typed_size_round_trips_through_every_stored_form():
    from workflow.layout_engine.presets import LayoutRecipe, default_recipe
    w, h = po.page_mm(FRAME_4K, 2731)
    r = replace(default_recipe("SS", po.paper_code(w, h)), dpi=2731,
                page_size=FRAME_4K, tiff_res_unit="in")
    d = json.loads(json.dumps(r.to_dict()))
    assert d["page_size"] == FRAME_4K and d["tiff_res_unit"] == "in"
    back = LayoutRecipe.from_dict(d)
    assert back.page_size == FRAME_4K and back.tiff_res_unit == "in"
    assert back == r
    kw = json.loads(json.dumps(r.build_kwargs()))
    again = LayoutRecipe.from_build_kwargs(kw)
    assert again.page_size == FRAME_4K and again.tiff_res_unit == "in"


@pytest.mark.parametrize("junk", [
    None, 1, "4096x2730", {"w": [4096, "px"]},
    {"w": [4096, "px"], "h": [2730, "furlong"], "ppi": 2731},
    {"w": [-1, "px"], "h": [2730, "px"], "ppi": 2731},
    {"w": [4096, "px"], "h": [2730, "px"], "ppi": 0},
    {"w": ["nan", "mm"], "h": [2730, "px"], "ppi": 300}])
def test_a_broken_stored_size_reads_as_none(junk):
    assert po.clean_page_size(junk) is None


def test_millimetres_alone_need_no_page_size():
    assert po.make_page_size((210.0, "mm"), (297.5, "mm"), 300) is None
    assert po.make_page_size((4096, "px"), (25.4, "mm"), 2731) == {
        "w": [4096, "px"], "h": [25.4, "mm"], "ppi": 2731}


def test_only_the_betas_values_count_as_the_betas():
    from workflow.layout_engine.presets import default_recipe
    assert not po.uses_beta_values(default_recipe("i1", "A4"))
    assert not po.uses_beta_values(default_recipe("i1", "100x150"))
    assert not po.uses_beta_values(replace(default_recipe("i1", "A4"), dpi=1200))
    assert po.uses_beta_values(replace(default_recipe("i1", "A4"), dpi=1201))
    assert po.uses_beta_values(default_recipe("i1", "234.95x196.85"))
    assert po.uses_beta_values(replace(default_recipe("i1", "A4"),
                                       tiff_res_unit="in"))


# ---- 2. the pixel rule --------------------------------------------------------

def test_a_side_in_pixels_survives_the_millimetre_round_trip_everywhere():
    """The geometry is laid out in millimetres; a pixel side converted to them
    and back by the renderer's own expression must give the count, for every
    resolution the box offers and pixel counts from 1 to a metre's worth."""
    import random
    rnd = random.Random(215)
    ppis = list(range(72, 6001, 37)) + [2032, 2731, 5461, 6000]
    for ppi in ppis:
        for px in [1, 2, 3, 4095, 4096, 2730, 5460, 8192, 18796, 15748] + \
                [rnd.randint(1, 236_000) for _ in range(40)]:
            mm = po.to_mm(px, "px", ppi)
            assert po.pixels_of(mm, ppi) == px, (px, ppi)


def test_inches_and_millimetres_take_the_renderers_rounding():
    ps = {"w": [9.25, "in"], "h": [7.75, "in"], "ppi": 2032}
    assert po.page_pixels(ps, 2032) == (18796, 15748)
    # 1.5 in at 2731 is 4096.5 pixels on paper: an exact half, which the
    # renderer's round() (half to even, in double precision) takes DOWN. The
    # panel shows the same number before anything is drawn, so the line and
    # the file agree; a person who needs 4097 types pixels.
    ps = {"w": [1.5, "in"], "h": [1.0, "in"], "ppi": 2731}
    assert po.page_pixels(ps, 2731) == (4096, 2731)
    for v, unit in ((1.5, "in"), (38.1, "mm"), (7.75, "in"), (196.85, "mm")):
        mm = po.to_mm(v, unit, 2731)
        assert po.pixels_of(mm, 2731) == max(1, round(mm * (2731 / 25.4)))


def test_the_4k_frame_is_pixel_exact_on_every_page_with_its_tags(
        tmp_path, beta_on):
    """His 4k.tif: 4096 x 2730, 8 bit RGB, uncompressed, 2731 pixels per inch
    exactly. Several pages, to prove the count holds on each."""
    from workflow.layout_engine.chart import build_from_recipe
    res, _ = build_from_recipe(TI1, tmp_path / "frame4k",
                               _film_recipe(FRAME_4K, 2731, patch=4.0))
    assert res.layout.pages >= 2
    assert len(res.tiff_paths) == res.layout.pages
    for p in res.tiff_paths:
        t = _tags(p)
        assert (t["w"], t["h"]) == (4096, 2730)
        assert t["bits"] == (8, 8, 8) and t["samples"] == 3
        assert t["xres"] == (2731, 1) and t["yres"] == (2731, 1)
        assert t["unit"] == 2                           # inch
        assert t["compression"] == 1                    # none
        assert t["photometric"] == 2                    # RGB
    strips = json.loads((tmp_path / "frame4k.strips.json").read_text(encoding="utf-8"))
    assert strips["dpi"] == 2731
    # every patch on whole pixels inside the frame, every page the same grid
    by_page: dict = {}
    for r in strips["patches"]:
        assert all(isinstance(r[k], int) for k in ("x", "y", "w", "h"))
        assert 0 <= r["x"] and r["x"] + r["w"] <= 4096
        assert 0 <= r["y"] and r["y"] + r["h"] <= 2730
        by_page.setdefault(r["page"], set()).add((r["w"], r["h"]))
    assert len(by_page) == res.layout.pages
    # the rounding rule: 4.0 mm at 2731 ppi is round(430.08...) = 430 px,
    # and a patch edge is round(mm * ppi / 25.4) of its position, so a
    # patch is 430 or 431 px, never anything else
    sizes = set().union(*by_page.values())
    assert sizes <= {(w, h) for w in (430, 431) for h in (430, 431)}, sizes


def test_the_8k_frame_at_5461(tmp_path, beta_on):
    from workflow.layout_engine.chart import build_from_recipe
    res, _ = build_from_recipe(TI1, tmp_path / "frame8k",
                               _film_recipe(FRAME_8K, 5461, patch=1.0))
    for p in res.tiff_paths:
        t = _tags(p)
        assert (t["w"], t["h"], t["xres"], t["unit"]) == (8192, 5460,
                                                           (5461, 1), 2)


def test_a_rebuild_from_the_stored_recipe_is_byte_identical(tmp_path, beta_on):
    """Opened again and laid out again without change: the same bytes."""
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    r = _film_recipe(FRAME_4K, 2731, patch=4.0)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    res1, used = build_from_recipe(TI1, tmp_path / "a" / "c", r)
    stored = json.loads(json.dumps(used.to_dict()))
    res2, _ = build_from_recipe(TI1, tmp_path / "b" / "c",
                                LayoutRecipe.from_dict(stored))
    for p1, p2 in zip(res1.tiff_paths, res2.tiff_paths):
        assert p1.read_bytes() == p2.read_bytes()
    assert (tmp_path / "a" / "c.ti2").read_text(encoding="utf-8").splitlines()[5:] == \
        (tmp_path / "b" / "c.ti2").read_text(encoding="utf-8").splitlines()[5:]


def test_px_per_cm_stays_the_default_and_is_written_as_before(tmp_path, beta_on):
    from workflow.layout_engine.chart import build_from_recipe
    r = replace(_film_recipe(FRAME_4K, 1200), tiff_res_unit="cm",
                page_size={"w": [1800, "px"], "h": [1200, "px"], "ppi": 1200})
    res, _ = build_from_recipe(TI1, tmp_path / "c", r)
    t = _tags(res.tiff_paths[0])
    assert t["unit"] == 3 and (t["w"], t["h"]) == (1800, 1200)
    assert t["xres"][0] / t["xres"][1] == pytest.approx(1200 / 2.54)


# ---- 3. every reader of our own TIFFs ----------------------------------------

def test_every_reader_reads_pixels_per_inch(tmp_path, beta_on):
    from workflow.layout_engine.chart import build_from_recipe
    res, _ = build_from_recipe(TI1, tmp_path / "r", _film_recipe(FRAME_4K, 2731))
    page = res.tiff_paths[0]
    import tifffile
    from workflow import page_geometry
    from workflow.margin_inspector import _tiff_dpi
    with tifffile.TiffFile(str(page)) as tf:
        assert page_geometry._read_dpi(tf.pages[0], 0.0) == 2731.0
    assert _tiff_dpi(page, 0.0) == 2731.0
    # the page in points, as the print path reads it (review F10: this
    # check named a function that does not exist and was skipped)
    w_pt, h_pt = page_geometry.read_tiff_dimensions_points(page)
    assert w_pt == pytest.approx(4096 * 72.0 / 2731)
    assert h_pt == pytest.approx(2730 * 72.0 / 2731)
    # the preview's own reader
    from ui.tiff_preview import TiffPreview
    assert TiffPreview._read_page_dpi(page) == pytest.approx(2731.0)


def test_the_right_edge_stamp_keeps_the_resolution_exact(tmp_path, beta_on):
    """`tiff_metadata` rewrites the page to stamp it: the resolution must come
    back as exactly 2731 per inch, not converted through centimetres."""
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.tiff_metadata import stamp_chart_metadata
    r = replace(_film_recipe(FRAME_4K, 2731, patch=4.0), margin_right=6.0)
    res, _ = build_from_recipe(TI1, tmp_path / "s", r)
    stamp_chart_metadata(res.tiff_paths[:1], ["stamped"])
    t = _tags(res.tiff_paths[0])
    assert (t["w"], t["h"], t["xres"], t["unit"]) == (4096, 2730, (2731, 1), 2)


def test_chart_inks_copy_of_a_page_keeps_the_unit(tmp_path):
    """`chart_inks` re-saves one page of a multi-page file for printing: the
    unit and value are carried, whatever they are."""
    import numpy as np
    import tifffile
    src = tmp_path / "two.tif"
    with tifffile.TiffWriter(str(src)) as tw:
        for _ in range(2):
            tw.write(np.zeros((4, 4, 3), np.uint8), photometric="rgb",
                     resolution=(2731.0, 2731.0), resolutionunit=2)
    from workflow import chart_inks
    out = chart_inks.split_page(src, 1)
    try:
        t = _tags(out)
        assert t["xres"] == (2731, 1) and t["unit"] == 2
    finally:
        if out:
            Path(out).unlink(missing_ok=True)


# ---- 4. the memory budget -----------------------------------------------------

def test_the_budget_takes_his_largest_frame_and_refuses_beyond():
    assert po.budget_problem(18796, 15748, 1) is None
    assert po.budget_problem(18796, 15748, 1, bit16=True) is None
    # A2 at 1200 dpi, the largest standard sheet 4.3.42 offers, still fits
    assert po.budget_problem(19843, 28063, 1) is None
    # the same frame as CMYK (87 bytes a pixel, measured) is refused
    why = po.budget_problem(18796, 15748, 1, inks=4, device=True)
    assert why and "18796 x 15748" in why and "296" in why
    # no comma in a number in any language (review F8): a comma is always a
    # decimal point in ChromIQ
    assert "," not in why.split(".")[0]
    # A2 at 6000 is refused
    assert po.budget_problem(99213, 140315, 1)
    many = po.budget_problem(8192, 5460, 100)
    assert many and "100 pages" in many


def test_a_page_over_the_budget_is_refused_before_any_file(tmp_path, beta_on):
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import default_recipe
    r = replace(default_recipe("SS", "A2"), dpi=6000)
    with pytest.raises(po.PageBudgetError) as e:
        build_from_recipe(TI1, tmp_path / "big", r)
    # the build's own check runs after the patch set was made, so it says
    # what is true there (review F4); nothing of this build is written
    assert "pixels" in str(e.value) and "No page of the chart was drawn" in \
        str(e.value) and "Nothing was written" not in str(e.value)
    assert not list(tmp_path.iterdir())


def test_the_budget_is_not_asked_with_the_beta_off(tmp_path, beta_off,
                                                   monkeypatch):
    """Off is 4.3.42: no new refusal on any path."""
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import default_recipe
    called = []
    monkeypatch.setattr(po, "budget_problem",
                        lambda *a, **k: called.append(a) or None)
    build_from_recipe(TI1, tmp_path / "a4", replace(default_recipe("SS", "A4"),
                                                    dpi=150))
    assert called == []


# ---- 6. the Beta off: a chart that needs it is refused, never redrawn --------

@pytest.mark.parametrize("change", [
    {"page_size": FRAME_4K, "dpi": 2731},
    {"tiff_res_unit": "in"}])
def test_off_a_chart_that_needs_the_beta_is_refused_with_words(
        tmp_path, beta_off, change):
    from workflow import measurement_messages as mm
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import default_recipe
    r = replace(default_recipe("SS", "38.0953x25.3907"), **change)
    with pytest.raises(po.PageBetaOff) as e:
        build_from_recipe(TI1, tmp_path / "off", r)
    from core.i18n import tr
    assert str(e.value) == tr(mm._PAGE_BETA_OFF_REDRAW)
    assert not list(tmp_path.iterdir())


# ---- 5. the panel ------------------------------------------------------------

@pytest.fixture
def panel_on(qapp, beta_on):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(None, with_selectors=True, with_calibration=True)
    p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    yield p
    p.deleteLater()


@pytest.fixture
def panel_off(qapp, beta_off):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(None, with_selectors=True, with_calibration=True)
    yield p
    p.deleteLater()


def test_on_the_fields_open_up(panel_on):
    p = panel_on
    assert p.dpi.maximum() == po.DPI_MAX_ON
    assert p.custom_w.decimals() == 2
    assert set(p._page_in) == {"w", "h"} and set(p._page_px) == {"w", "h"}
    assert p.tiff_res_unit.currentData() == "cm"


def test_pixels_typed_are_kept_through_every_redraw(panel_on):
    p = panel_on
    p.dpi.setValue(2731)
    p._page_px["w"].setValue(4096)
    p._page_px["h"].setValue(2730)
    r = p.get_recipe()
    assert r.page_size == FRAME_4K and r.paper == "38.0953x25.3907"
    assert p.custom_w.value() == pytest.approx(38.10)
    assert p._page_in["w"].value() == pytest.approx(1.4998, abs=1e-4)
    # the resolution moved and back, many times: the pixels never drift
    for dpi in (300, 72, 6000, 1234, 5461, 2731) * 5:
        p.dpi.setValue(dpi)
        assert p._page_px["w"].value() == 4096
    assert p.get_recipe().page_size == FRAME_4K
    # at another resolution the pixels stay and the size follows
    p.dpi.setValue(5461)
    r = p.get_recipe()
    assert r.page_size["w"] == [4096, "px"] and r.page_size["ppi"] == 5461


def test_inches_typed_keep_the_size_and_show_the_pixels(panel_on):
    p = panel_on
    p.dpi.setValue(2032)
    p._page_in["w"].setValue(9.25)
    p._page_in["h"].setValue(7.75)
    r = p.get_recipe()
    assert r.paper == "234.95x196.85"
    assert r.page_size == {"w": [9.25, "in"], "h": [7.75, "in"], "ppi": 2032}
    assert (p._page_px["w"].value(), p._page_px["h"].value()) == (18796, 15748)
    assert "18796 x 15748 pixels" in p._page_px_lbl.text()


def test_millimetres_typed_need_no_page_size(panel_on):
    p = panel_on
    p.custom_w.setValue(234.95)
    p.custom_h.setValue(196.85)
    r = p.get_recipe()
    assert r.paper == "234.95x196.85" and r.page_size is None


def test_a_whole_millimetre_size_on_gives_the_old_recipe(panel_on, qapp):
    """B: the Beta on, nothing new used: the recipe is the off panel's."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = panel_on
    p.custom_w.setValue(150)
    p.custom_h.setValue(200)
    on = p.get_recipe().to_dict()
    po.set_enabled_for_this_process(False)
    q = LayoutOptionsPanel(None, with_selectors=True, with_calibration=True)
    q.paper.setCurrentIndex(q.paper.findData("__custom__"))
    q.custom_w.setValue(150)
    q.custom_h.setValue(200)
    off = q.get_recipe().to_dict()
    q.deleteLater()
    assert on == off


def test_a_stored_page_loads_into_the_fields(panel_on):
    from workflow.layout_engine.presets import default_recipe
    p = panel_on
    r = replace(default_recipe("SS", "38.0953x25.3907"), dpi=2731,
                page_size=FRAME_4K, tiff_res_unit="in")
    p.set_recipe(r)
    back = p.get_recipe()
    assert back.page_size == FRAME_4K and back.dpi == 2731
    assert back.tiff_res_unit == "in" and back.paper == r.paper
    assert p._page_px["w"].value() == 4096


def test_the_pixel_line_says_when_the_page_is_over_the_budget(panel_on):
    p = panel_on
    p.paper.setCurrentIndex(p.paper.findData("A2"))
    p.dpi.setValue(6000)
    p._emit()
    assert "pixels" in p._page_px_lbl.text()
    assert "Generate will be refused" in p._page_px_lbl.text()


def test_off_the_panel_is_4_3_42s(panel_off):
    p = panel_off
    assert (p.dpi.minimum(), p.dpi.maximum()) == (72, 1200)
    assert p.custom_w.decimals() == 0
    assert (p.custom_w.minimum(), p.custom_w.maximum()) == (20, 2000)
    for name in ("_page_in", "_page_px", "_page_px_lbl", "tiff_res_unit",
                 "_page_hold_lbl", "_page_truth"):
        assert not hasattr(p, name), name


def test_off_a_beta_chart_is_held_as_it_is_and_said(panel_off):
    from workflow.layout_engine.presets import default_recipe
    p = panel_off
    r = replace(default_recipe("SS", "38.0953x25.3907"), dpi=2731,
                page_size=FRAME_4K, tiff_res_unit="in")
    p.set_recipe(r)
    # the fields cannot show it...
    assert p.dpi.value() == 1200 and p.custom_w.value() == 38
    # ...and the recipe is the chart's own, unrounded
    back = p.get_recipe()
    assert (back.paper, back.dpi, back.page_size, back.tiff_res_unit) == (
        r.paper, 2731, FRAME_4K, "in")
    assert p._page_hold_lbl.isVisibleTo(p)
    assert "4096 x 2730 pixels" in p._page_hold_lbl.text()
    assert "Generate is refused" in p._page_hold_lbl.text()
    # the person's own change ends the hold
    p.dpi.setValue(300)
    mine = p.get_recipe()
    assert mine.dpi == 300 and mine.page_size is None
    assert mine.paper == "38x25"


def test_off_a_fraction_only_chart_is_made_at_its_own_size(panel_off):
    from workflow.layout_engine.presets import default_recipe
    p = panel_off
    r = default_recipe("SS", "234.95x196.85")
    p.set_recipe(r)
    assert p.get_recipe().paper == "234.95x196.85"
    assert "Generate still makes the chart at 234.95 x 196.85 mm" in \
        p._page_hold_lbl.text()


def test_off_a_4_3_42_recipe_loads_and_comes_back_unchanged(panel_off,
                                                           monkeypatch):
    """With the Beta off the panel gives back, for every recipe 4.3.42 can
    write, exactly what it gives with the Beta's two hooks taken out (i.e.
    4.3.42's panel), field for field (review F10: this compared a recipe
    with itself)."""
    from ui.dialogs import page_output_panel as pop
    from workflow.layout_engine.presets import default_recipe
    p = panel_off
    recipes = (default_recipe("i1", "A4"), default_recipe("SS", "150x200"),
               replace(default_recipe("CM", "A4"), dpi=1200),
               replace(default_recipe("SS", "A3"), bit16=True,
                       compression="none"))
    with_hooks = []
    for r in recipes:
        p.set_recipe(r)
        assert "_page_hold" not in p.__dict__
        got = p.get_recipe()
        assert got.paper == r.paper and got.dpi == r.dpi
        assert got.page_size is None and got.tiff_res_unit == "cm"
        with_hooks.append(got.to_dict())
    monkeypatch.setattr(pop, "load_recipe", lambda *a, **k: None)
    monkeypatch.setattr(pop, "apply_to_recipe", lambda *a, **k: None)
    for r, want in zip(recipes, with_hooks):
        p.set_recipe(r)
        assert p.get_recipe().to_dict() == want


# ---- Preferences -------------------------------------------------------------

def test_preferences_offers_it_off_and_writes_nothing_unless_changed(qapp):
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog, page_output_help
    s = AppSettings()
    s._qs.remove("page_output_beta")
    dlg = SettingsDialog(s)
    try:
        assert dlg._page_output_check.isChecked() is False
        assert "Custom page size in inches or pixels" in \
            dlg._page_output_check.text()
        dlg._save_and_close()
        assert not s._qs.contains("page_output_beta")
    finally:
        dlg.deleteLater()
    dlg = SettingsDialog(s)
    try:
        dlg._page_output_check.setChecked(True)
        assert dlg._page_output_restart_hint.isHidden() is \
            po.page_output_enabled()
        dlg._save_and_close()
        assert s.get("page_output_beta") is True
    finally:
        dlg.deleteLater()
        s._qs.remove("page_output_beta")
    text = page_output_help()
    assert "2731" in text and "6000" in text and "**Default:** off" in text
    assert "\u2014" not in text


# ---- text, labels, marks and lines stay right in millimetres -----------------

def _ink_report(path, dpi, strips):
    import numpy as np
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    ink = np.asarray(Image.open(path).convert("L")) < 128
    ys, xs = np.nonzero(ink)
    mm = 25.4 / dpi
    p0 = strips["patches"][0]
    by, bx = np.nonzero(ink[: p0["y"], :])
    return {"bbox": (xs.min() * mm, ys.min() * mm, xs.max() * mm, ys.max() * mm),
            "patch": tuple(p0[k] * mm for k in ("x", "y", "w", "h")),
            "band": (bx.min() * mm, by.min() * mm, bx.max() * mm, by.max() * mm),
            "area": float(ink.sum()) * mm * mm}


@pytest.mark.parametrize("markers", [False, True])
def test_the_same_chart_at_600_and_3000_ppi_is_the_same_in_millimetres(
        tmp_path, beta_on, markers):
    """The renderer's constants were tuned up to 1200 dpi. Drawn at 600 and
    at 3000 ppi, the ink (patches, strip letters, row numbers, the sheet text,
    the ruler markers) must sit in the same millimetres, to within two pixels
    of the coarser sheet, and cover the same area to within 1 %. Measured to
    4800 ppi as well while building the Beta (issue-215 folder,
    `mm_consistency.py`): within 0.07 mm and 0.3 %."""
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import default_recipe
    base = replace(default_recipe("SS", "70x50"), seed=3, compression="none",
                   helper_markers=markers, chart_text="Film {dpi}",
                   show_row_indicators=True, margin_top=12, margin_left=12,
                   margin_bottom=10, margin_right=6)
    got = {}
    for dpi in (600, 3000):
        res, _ = build_from_recipe(TI1, tmp_path / f"c{dpi}",
                                   replace(base, dpi=dpi))
        strips = json.loads((tmp_path / f"c{dpi}.strips.json").read_text(encoding="utf-8"))
        got[dpi] = _ink_report(res.tiff_paths[0], dpi, strips)
    # two pixels of the coarser sheet: a text size is a whole number of
    # pixels, so a glyph at 600 can be half a pixel taller or shorter
    tol = 25.4 / 600 * 2
    for key in ("bbox", "patch", "band"):
        for a, b in zip(got[600][key], got[3000][key]):
            assert abs(a - b) <= tol, (key, got[600][key], got[3000][key])
    assert got[3000]["area"] == pytest.approx(got[600]["area"], rel=0.01)


def test_a_frame_at_6000_ppi_is_drawn(tmp_path, beta_on):
    """The top of the box: a 30 x 24 mm frame at 6000 ppi, with its labels."""
    from workflow.layout_engine.chart import build_from_recipe
    ps = {"w": [30.0, "mm"], "h": [24.0, "mm"], "ppi": 6000}
    r = replace(_film_recipe(ps, 6000, patch=3.0), show_strip_indicators=True)
    res, _ = build_from_recipe(TI1, tmp_path / "f6000", r)
    t = _tags(res.tiff_paths[0])
    assert (t["w"], t["h"]) == (po.pixels_of(30.0, 6000), po.pixels_of(24.0, 6000))
    assert t["xres"] == (6000, 1) and t["unit"] == 2


def test_generate_refuses_an_over_budget_page_before_anything_runs(qapp,
                                                                     beta_on):
    """Before targen: driven on screen, A2 at 6000 ppi first asked targen for
    tens of thousands of patches and only refused minutes later."""
    from types import SimpleNamespace
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from ui.tabs.tab_chart import TabChart
    panel = LayoutOptionsPanel(None, with_selectors=True, with_calibration=True)
    panel.paper.setCurrentIndex(panel.paper.findData("A2"))
    panel.dpi.setValue(6000)
    lines = []
    fake = SimpleNamespace(_manual_layout_panel=panel,
                           _mode_name=lambda: "manual",
                           _log=SimpleNamespace(appendPlainText=lines.append))
    assert TabChart._refuse_page_over_budget(fake) is True
    assert lines and lines[0].startswith("[ERROR] ") and "99213" in lines[0]
    assert lines[0].endswith("Nothing was written.")
    panel.dpi.setValue(1200)
    lines.clear()
    assert TabChart._refuse_page_over_budget(fake) is False and not lines
    panel.deleteLater()


def test_off_generate_is_refused_only_for_what_needs_the_beta(panel_off):
    from ui.dialogs import page_output_panel as pop
    from workflow.layout_engine.presets import default_recipe
    p = panel_off
    p.set_recipe(replace(default_recipe("SS", "38.0953x25.3907"), dpi=2731,
                         page_size=FRAME_4K))
    assert pop.hold_refusal(p)
    p.set_recipe(default_recipe("SS", "234.95x196.85"))
    assert pop.hold_refusal(p) is None          # made at its own size
    p.set_recipe(default_recipe("SS", "A4"))
    assert pop.hold_refusal(p) is None          # nothing held at all


# ---- review fix round 1 (2026-11-16) -------------------------------------------

def _cmyk_ti1(path, n=60, rgb=False):
    rows = [((i * 37) % 101, (i * 53) % 101, (i * 71) % 101, (i * 13) % 101)
            for i in range(n)]
    if rgb:
        rows = [r[:3] for r in rows]
    fields = ("RGB_R RGB_G RGB_B" if rgb else "CMYK_C CMYK_M CMYK_Y CMYK_K")
    lines = ["CTI1", f'COLOR_REP "{"RGB" if rgb else "CMYK"}"',
             "BEGIN_DATA_FORMAT",
             f"SAMPLE_ID {fields} XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", "BEGIN_DATA"]
    for i, dev in enumerate(rows, 1):
        lines.append(f"{i} " + " ".join(f"{v:.4f}" for v in dev)
                     + " 50.0 50.0 50.0")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


class _Drawn(Exception):
    """Raised in place of drawing: the build got past the budget."""


#: Charts 4.3.42 makes (whole millimetres, at most 1200 dpi) that the memory
#: budget, asked of them, WOULD refuse (review F7): (paper, ti1 kind, patch
#: mm, the least page count the case needs).
F7_CASES = [("A4", "cmyk", 6.0, 1), ("A4", "rgb", 6.0, 8),
            ("A3", "rgb", 6.0, 4), ("A2", "rgb", 6.0, 2)]


@pytest.mark.parametrize("paper,kind,patch,pages", F7_CASES)
def test_f7_a_chart_4_3_42_makes_is_never_refused_with_the_beta_on(
        tmp_path, beta_on, monkeypatch, paper, kind, patch, pages):
    """Review F7: the budget is asked only of what only the Beta allows.
    The build is stopped where it would start drawing, so the test proves the
    budget let it through without drawing gigabytes; and the case is one the
    budget would have refused, so the test is not empty."""
    from workflow.layout_engine import chart as chart_mod
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import default_recipe
    seen = {}

    def stop(printed, layout, geom, **kw):
        seen.update(pages=layout.pages, W=kw["paper_w_mm"],
                    H=kw["paper_h_mm"], dpi=kw["dpi"])
        raise _Drawn()
    monkeypatch.setattr(chart_mod.raster, "render_pages", stop)
    # enough patches for the pages the case needs
    ti1 = _cmyk_ti1(tmp_path / "c.ti1", n=14000, rgb=kind == "rgb")
    r = replace(default_recipe("SS", paper), dpi=1200, patch_w_mm=patch,
                patch_h_mm=patch, layout_mode="patch_first", seed=1)
    with pytest.raises(_Drawn):
        build_from_recipe(ti1, tmp_path / "f7", r)
    assert seen["pages"] >= pages, seen
    w, h = po.pixels_of(seen["W"], 1200), po.pixels_of(seen["H"], 1200)
    k = {"inks": 4, "device": True} if kind == "cmyk" else {}
    assert po.estimated_bytes(w, h, seen["pages"], **k) > \
        po.MEMORY_BUDGET_BYTES, "not a case the budget would refuse"
    assert not po.needs_budget(page_size=r.page_size, dpi=r.dpi,
                               paper=r.paper)


def test_f7_the_panel_line_and_generate_leave_4_3_42_charts_alone(
        qapp, beta_on):
    """The same rule at the other two places: no red line, no refusal."""
    from types import SimpleNamespace
    from ui.dialogs import page_output_panel as pop
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from ui.tabs.tab_chart import TabChart
    panel = LayoutOptionsPanel(None, with_selectors=True, with_calibration=True)
    panel.page_ink_codes = lambda: ["c", "m", "y", "k"]   # CMYK chart
    lines = []
    fake = SimpleNamespace(_manual_layout_panel=panel,
                           _mode_name=lambda: "manual",
                           _log=SimpleNamespace(appendPlainText=lines.append))
    try:
        for paper in ("A4", "A3", "A2"):
            panel.paper.setCurrentIndex(panel.paper.findData(paper))
            panel.dpi.setValue(1200)
            panel._emit()
            assert not pop.needs_budget(panel)
            assert "Generate will be refused" not in panel._page_px_lbl.text()
            assert TabChart._refuse_page_over_budget(fake) is False
        assert lines == []
        # one step past 4.3.42 and the budget is asked again
        panel.dpi.setValue(1201)
        panel._emit()
        assert pop.needs_budget(panel)
        assert "Generate will be refused" in panel._page_px_lbl.text()
        assert TabChart._refuse_page_over_budget(fake) is True
    finally:
        panel.deleteLater()


def test_f4_a_cmyk_page_over_the_budget_is_refused_early_and_truly(
        qapp, beta_on):
    """Review F4: his 9.25 x 7.75 in frame at 2032 fits as RGB (4.1 GiB) and
    not as CMYK (26 GB): the line and Generate's early check use the chart's
    inks, and the early words say nothing was written."""
    from types import SimpleNamespace
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from ui.tabs.tab_chart import TabChart
    panel = LayoutOptionsPanel(None, with_selectors=True, with_calibration=True)
    panel.paper.setCurrentIndex(panel.paper.findData("__custom__"))
    panel.dpi.setValue(2032)
    panel._page_in["w"].setValue(9.25)
    panel._page_in["h"].setValue(7.75)
    lines = []
    fake = SimpleNamespace(_manual_layout_panel=panel,
                           _mode_name=lambda: "manual",
                           _log=SimpleNamespace(appendPlainText=lines.append))
    try:
        inks = {"codes": ["r", "g", "b"]}
        panel.page_ink_codes = lambda: inks["codes"]
        panel._emit()
        assert "18796 x 15748" in panel._page_px_lbl.text()
        assert "Generate will be refused" not in panel._page_px_lbl.text()
        assert TabChart._refuse_page_over_budget(fake) is False
        for codes in (["c", "m", "y", "k"], ["c", "m", "y"],
                      ["c", "m", "y", "k", "lc", "lm"]):
            inks["codes"] = codes
            panel._emit()
            assert "Generate will be refused" in panel._page_px_lbl.text()
            lines.clear()
            assert TabChart._refuse_page_over_budget(fake) is True
            assert lines[0].endswith("Nothing was written."), lines
            assert "18796 x 15748" in lines[0]
    finally:
        panel.deleteLater()


def test_f4_the_build_refuses_a_cmyk_page_with_true_words(tmp_path, beta_on):
    from workflow.layout_engine.chart import build_from_recipe
    r = replace(_film_recipe({"w": [9.25, "in"], "h": [7.75, "in"],
                              "ppi": 2032}, 2032, patch=6.0),
                tiff_res_unit="cm")
    with pytest.raises(po.PageBudgetError) as e:
        build_from_recipe(_cmyk_ti1(tmp_path / "c.ti1"), tmp_path / "x", r)
    assert "No page of the chart was drawn." in str(e.value)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c.ti1"]


def test_f8_no_number_carries_a_thousands_comma(panel_on):
    p = panel_on
    p.dpi.setValue(2731)
    p._page_px["w"].setValue(4096)
    p._page_px["h"].setValue(2730)
    p._emit()
    text = p._page_px_lbl.text()
    assert "4096 x 2730" in text and "11.2 megapixels" in text
    assert "," not in text
    from ui.dialogs.page_output_panel import describe_page
    assert describe_page(p.get_recipe()) == "4096 x 2730 pixels"
    big = po.budget_problem(99213, 140315, 3)
    assert big and "99213 x 140315" in big
    import re
    assert not re.search(r"\d,\d", big)


def test_f5_every_unit_has_the_same_range(panel_on):
    """Review F5: 1 to 2000 mm whatever the unit; the pixel field's top
    follows the resolution, and a pixel side above it after the resolution
    was lowered keeps its unit and becomes the top."""
    p = panel_on
    assert p.custom_w.minimum() == po.CUSTOM_MM_MIN_ON
    assert p.custom_w.maximum() == po.CUSTOM_MM_MAX
    assert p._page_in["w"].maximum() == pytest.approx(2000 / 25.4, abs=1e-4)
    assert p._page_in["w"].minimum() == pytest.approx(1 / 25.4, abs=1e-4)
    p.dpi.setValue(2032)
    p._emit()
    assert p._page_px["w"].maximum() == int(2000 * 2032 / 25.4)
    p._page_px["w"].setValue(18796)
    p._page_px["h"].setValue(15748)
    p.dpi.setValue(72)
    p._emit()
    top = int(2000 * 72 / 25.4)
    assert p._page_px["w"].maximum() == top
    assert p._page_truth["w"] == (float(top), "px")
    assert p.get_recipe().page_size["w"] == [top, "px"]
    assert po.page_mm(p.get_recipe().page_size, 72)[0] <= 2000.0


def test_f3_the_fd9_is_not_offered_pixels_per_inch(qapp, beta_on):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from workflow.fd9 import support as fd9
    before = fd9._latched
    fd9.set_enabled_for_this_process(True)
    panel = LayoutOptionsPanel(None, with_selectors=True, with_calibration=True)
    try:
        combo = panel.tiff_res_unit
        combo.setCurrentIndex(combo.findData("in"))
        panel.instr.setCurrentIndex(panel.instr.findData("FD9"))
        qapp.processEvents()
        assert not combo.isEnabled()
        assert combo.currentData() == "cm"
        assert "FD-9" in combo.toolTip() and "centimetre" in combo.toolTip()
        assert panel.get_recipe().tiff_res_unit == "cm"
        # back on another instrument: enabled, and the person's choice is back
        panel.instr.setCurrentIndex(panel.instr.findData("SS"))
        qapp.processEvents()
        assert combo.isEnabled() and combo.currentData() == "in"
        assert panel.get_recipe().tiff_res_unit == "in"
    finally:
        panel.deleteLater()
        fd9._latched = before


def test_i1io_a_page_typed_in_pixels_stays_pixel_exact_when_turned(
        qapp, beta_on):
    """Review, i1iO point: the i1iO turns a custom page upright in the
    millimetre fields; the typed pixels turn with it and stay the truth."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from workflow.i1io import support as io
    before = io._latched
    io.set_enabled_for_this_process(True)
    panel = LayoutOptionsPanel(None, with_selectors=True, with_calibration=True)
    try:
        panel.instr.setCurrentIndex(panel.instr.findData("IO2"))
        panel.paper.setCurrentIndex(panel.paper.findData("__custom__"))
        panel.dpi.setValue(600)
        panel._page_px["w"].setValue(7000)       # lying: 296.3 x 211.7 mm
        panel._page_px["h"].setValue(5000)
        panel.commit_custom_size()
        qapp.processEvents()
        r = panel.get_recipe()
        assert r.page_size == {"w": [5000, "px"], "h": [7000, "px"], "ppi": 600}
        w_mm, h_mm = po.page_mm(r.page_size, 600)
        assert r.paper == po.paper_code(w_mm, h_mm) and w_mm < h_mm
        assert (panel._page_px["w"].value(), panel._page_px["h"].value()) == (
            5000, 7000)
    finally:
        panel.deleteLater()
        io._latched = before


def test_a_fractional_custom_code_is_the_same_paper_as_its_whole_mm_p():
    """printtarg -p holds whole millimetres: a Beta page's code cut to them
    is read as the same paper (Save as Defaults kept A4 otherwise), and no
    4.3.42 code changes its meaning."""
    from ui.tabs.tab_chart import _recipe_is_for
    rec = {"instrument": "SS", "paper": "234.95x196.85"}
    assert _recipe_is_for(rec, "SS", "234x196")
    assert _recipe_is_for(rec, "SS", "235x197")
    assert not _recipe_is_for(rec, "SS", "A4")
    assert not _recipe_is_for(rec, "SS", "230x196")
    assert not _recipe_is_for({"instrument": "SS", "paper": "234x196"},
                              "SS", "235x196")
    assert _recipe_is_for({"instrument": "SS", "paper": "A4"}, "SS", "A4")
