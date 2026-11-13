"""THE i1iO CHART'S CLIP BORDER, AN OPTION OFF BY DEFAULT (2026-11-13).

The owner: "the clip border should be possible to enable if a user wants it
as an option. just off by default". The table holds the sheet itself, so the
band holds no clip: it is the engine's notes band (Notes box, custom text,
branding, image), as on a ColorMunki, SpectroScan or CR30 chart, down the
page's LEFT edge (the table's top edge). Held here:

* off by default everywhere, and a recipe saved before the option (whose
  `clip_content_mode` carries the recipe default "notes") stays without it;
* on: the capacity is the geometry's own, and the band stays inside the
  printable area (content 10 mm from every edge), clear of the aiming
  crosses, of every strip's blank run-in and run-out, of the strip letters
  and of the patches;
* the side file records it; the `.ti2` gains nothing;
* Manual (the "Clip border" selector, the margins' minimums following it,
  leaving the i1iO gives the content box back) and Guided (its own box);
* every other instrument's chart is untouched by the new key.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_i1io_chart import _ti1  # noqa: E402
from tests.test_i1io_layout_options import _agree_and_blank  # noqa: E402

DPI = 100
S = DPI / 25.4


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _build(tmp_path, n=300, paper="A4", **kw):
    from workflow.layout_engine import chart
    ti1 = _ti1(tmp_path / "c.ti1", n)
    result = chart.build_chart(ti1, tmp_path / "c", instrument="IO2",
                               paper=paper, dpi=DPI, project="Clip test",
                               **kw)
    side = json.loads((tmp_path / "c.i1io.json").read_text(encoding="utf-8"))
    return result, side


# ---- off by default ---------------------------------------------------------

def test_off_by_default_everywhere():
    from workflow.i1io import chart as C
    from workflow.i1io import table_facts as F
    from workflow.layout_engine.presets import LayoutRecipe
    assert F.CLIP_BORDER.value is False
    f = C.fixed_build_kwargs({"paper": "A4"})
    assert f["clip_band"] == 0.0 and f["clip_content_mode"] == "off"
    assert f[C.CLIP_KEY] is False
    r = LayoutRecipe(instrument="IO2")
    assert r.i1io_clip_border is False
    assert "i1io_clip_border" not in r.to_dict()
    assert "i1io_clip_border" not in r.build_kwargs()


def test_a_recipe_from_before_the_option_stays_without_the_band():
    """`clip_content_mode` "notes" is the recipe default: it must not turn
    the band on (the option has its own field)."""
    from workflow.i1io import chart as C
    from workflow.layout_engine.presets import LayoutRecipe
    old = LayoutRecipe.from_dict({"instrument": "IO2", "paper": "A4",
                                  "clip_content_mode": "notes",
                                  "clip_border_width": 26.0})
    assert old.i1io_clip_border is False
    kw = {**old.build_kwargs(), "instrument": "IO2"}
    assert C.capacity(kw, True) == 528
    assert C.fixed_build_kwargs(kw)["clip_band"] == 0.0


@pytest.mark.parametrize("paper,crosses,off,on", [
    ("A4", True, 528, 480), ("A4", False, 552, 504),
    ("Letter", True, 506, 462), ("Letter", False, 528, 484)])
def test_the_capacity_both_ways(paper, crosses, off, on):
    from workflow.i1io import chart as C
    base = {"paper": paper}
    assert C.capacity(base, crosses) == off
    assert C.capacity({**base, C.CLIP_KEY: True}, crosses) == on


def test_a_wider_band_costs_more_and_never_goes_below_its_minimum():
    from workflow.i1io import chart as C
    from workflow.i1io import table_facts as F
    kw = {"paper": "A4", C.CLIP_KEY: True}
    widths = [C.capacity({**kw, "clip_border_width": w}, True)
              for w in (20, 26, 40, 60)]
    assert widths == sorted(widths, reverse=True)
    assert C.clip_width_of({**kw, "clip_border_width": 12}) == \
        F.CLIP_MIN_MM.value


# ---- where the band is --------------------------------------------------------

@pytest.mark.parametrize("paper", ["A4", "Letter"])
@pytest.mark.parametrize("crosses", [True, False])
@pytest.mark.parametrize("mode", ["notes", "text", "branding"])
def test_the_band_is_inside_the_printable_area_and_clear(tmp_path, paper,
                                                        crosses, mode):
    from workflow.i1io import chart as C
    from workflow.i1io import table_facts as F
    from workflow.layout_engine import geometry, papers
    from workflow.layout_engine import instruments
    kw = {C.CLIP_KEY: True, "clip_content_mode": mode,
          "clip_text": "Printer, ink set and paper\nsecond line",
          "i1io_crosses": crosses}
    result, side = _build(tmp_path, 400, paper, **kw)
    _agree_and_blank(tmp_path, result, side)
    w, h = papers.dimensions_mm(paper)
    rec = side["clip_border"]
    assert rec["side"] == "left" and rec["content"] == mode
    x0, y0, x1, y1 = rec["area_mm"]
    assert x0 == 0.0 and x1 == pytest.approx(26.0)
    assert y0 == pytest.approx(F.CLIP_EDGE_MM.value)
    bottom = C.clip_bottom_mm(crosses)
    assert h - y1 == pytest.approx(bottom)
    assert bottom == (21.0 if crosses else 10.0)
    # the content itself starts 10 mm in from the paper edge
    geom = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": paper, **kw})
    ax, ay, aw, ah = geometry.clip_area_mm(geom, h, w)
    assert ax >= F.NUMBERS_EDGE_MM.value - 1e-6
    # clear of the crosses (cross 1 is the only one on this edge)
    if crosses:
        zone = C.mark_zone(C.marks(w, h)[0])
        assert y1 <= zone[1] - 1e-6
    # clear of the patches, the patch numbers' band and the strip letters
    xs = [p["centre_mm"][0] - side["patch_mm"][0] / 2
          for st in side["pages"][0]["strips"] for p in st["patches"]]
    assert min(xs) >= x1 + F.LABEL_CLEAR_MM.value - 1e-6


@pytest.mark.parametrize("crosses", [True, False])
def test_nothing_is_printed_outside_the_band_that_was_not_there(tmp_path,
                                                                crosses):
    """Compared with the same chart without the band, ink is added only
    inside the band (the block moves right by whole strips' worth, so the
    comparison is of the left page edge region, the corners and the runs)."""
    from PIL import Image
    from workflow.i1io import chart as C
    on, side = _build(tmp_path, 300, "A4", i1io_crosses=crosses,
                      **{C.CLIP_KEY: True})
    img = np.asarray(Image.open(on.tiff_paths[0]).convert("L"))
    x0, y0, x1, y1 = side["clip_border"]["area_mm"]
    # outside the band, left of the block: nothing but the patch numbers'
    # column and cross 1; paper above and below the band's ends is blank
    top = img[:int(y0 * S) - 1, :int(x1 * S)]
    assert top.min() >= 250
    if not crosses:
        bot = img[int(y1 * S) + 1:, :int(x1 * S)]
        assert bot.min() >= 250
    else:
        zone = C.mark_zone(C.marks(*side["paper_mm"])[0])
        gap = img[int(y1 * S) + 1:int(zone[1] * S) - 1, :int(x1 * S)]
        assert gap.size == 0 or gap.min() >= 250


def test_the_band_holds_its_content(tmp_path):
    from PIL import Image
    from workflow.i1io import chart as C
    on, side = _build(tmp_path, 300, "A4", **{C.CLIP_KEY: True})
    img = np.asarray(Image.open(on.tiff_paths[0]).convert("L"))
    x0, y0, x1, y1 = side["clip_border"]["area_mm"]
    band = img[int(y0 * S):int(y1 * S), int(x0 * S):int(x1 * S)]
    assert band.min() < 128          # the Notes box is printed


def test_a_band_that_would_reach_the_patches_is_refused(tmp_path):
    from dataclasses import replace
    from workflow.i1io import chart as C
    from workflow.layout_engine import geometry, instruments, papers
    kw = {"instrument": "IO2", "paper": "A4", C.CLIP_KEY: True,
          "clip_content_mode": "notes"}
    geom = instruments.geom_from_build_kwargs(kw)
    w, h = papers.dimensions_mm("A4")
    layout = geometry.compute(geom, w, h, 300)
    C.check_sheet(geom, layout, w, h, True)            # sound as built
    with pytest.raises(C.I1ioSheetRefused, match="clip border"):
        C.check_sheet(replace(geom, clip_content_reach_mm=200.0), layout,
                      w, h, True)


def test_the_free_text_spot_never_takes_the_band():
    from workflow.i1io import chart as C
    from workflow.layout_engine import geometry, instruments, papers
    kw = {"instrument": "IO2", "paper": "A4", C.CLIP_KEY: True,
          "i1io_crosses": False, "row_indicators": False,
          "margins": (12, 5, 30, 60)}
    geom = instruments.geom_from_build_kwargs(kw)
    w, h = papers.dimensions_mm("A4")
    layout = geometry.compute(geom, w, h, 200)
    labels = C.label_wishes(C.fixed_build_kwargs(kw))
    spots = {s["spot"]: s for s in C.free_spots(geom, layout, w, h, 0,
                                                labels)}
    assert spots["top edge"]["x0"] >= 26.0 + 1.0 - 1e-6


def test_the_ti2_gains_nothing(tmp_path):
    from workflow.i1io import chart as C
    (tmp_path / "on").mkdir()
    (tmp_path / "off").mkdir()
    on, _side = _build(tmp_path / "on", 300, **{C.CLIP_KEY: True})
    off, _side = _build(tmp_path / "off", 300)

    def keywords(p):
        return sorted(ln.split()[0] for ln in p.read_text(encoding="utf-8").splitlines()
                      if ln and ln[0].isupper() and not ln.startswith(
                          ("CREATED", "BEGIN", "END", "SAMPLE")))
    assert keywords(on.ti2_path) == keywords(off.ti2_path)


def test_every_other_instrument_ignores_the_key(tmp_path):
    from workflow.layout_engine import chart, instruments
    for code in ("i1", "CM", "SS"):
        a = instruments.geom_from_build_kwargs(
            {"instrument": code, "paper": "A4"})
        b = instruments.geom_from_build_kwargs(
            {"instrument": code, "paper": "A4", "i1io_clip_border": True})
        assert a == b, code
    ti1 = _ti1(tmp_path / "c.ti1", 100)
    r1 = chart.build_chart(ti1, tmp_path / "a", instrument="i1", paper="A4",
                           dpi=DPI, seed=5)
    r2 = chart.build_chart(ti1, tmp_path / "b", instrument="i1", paper="A4",
                           dpi=DPI, seed=5, i1io_clip_border=True)
    assert r1.tiff_paths[0].read_bytes() == r2.tiff_paths[0].read_bytes()


# ---- Manual ------------------------------------------------------------------

@pytest.fixture
def panel(qapp, qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    return p


def _to(panel, code):
    panel.instr.setCurrentIndex(panel.instr.findData(code))


def test_manual_offers_the_band_off_and_the_margins_follow(panel):
    from workflow.i1io import chart as C
    _to(panel, "IO2")
    assert not panel.clip_enable.isHidden()
    assert panel.clip_enable.isEnabled()
    assert panel.clip_enable.currentData() == "off"
    assert not panel.clip_side.isEnabled()          # always the left edge
    r = panel.get_recipe()
    assert r.i1io_clip_border is False
    left_off = panel.margins["l"].value()
    panel.clip_enable.setCurrentIndex(panel.clip_enable.findData("on"))
    r = panel.get_recipe()
    assert r.i1io_clip_border is True
    assert r.clip_content_mode == "notes"
    kw = r.build_kwargs()
    assert kw[C.CLIP_KEY] is True
    least = C.least_margins_mm({**kw, "instrument": "IO2"})
    assert panel.margins["l"].minimum() == pytest.approx(least[3])
    assert panel.margins["l"].value() == pytest.approx(least[3])
    assert least[3] > left_off
    # the content kinds are live
    assert panel.clip_content_mode.isEnabled()
    panel.clip_content_mode.setCurrentIndex(
        panel.clip_content_mode.findData("text"))
    assert panel.clip_text.isEnabled()
    panel.clip_enable.setCurrentIndex(panel.clip_enable.findData("off"))
    assert panel.get_recipe().i1io_clip_border is False
    assert panel.margins["l"].value() == pytest.approx(left_off)


def test_leaving_the_i1io_gives_the_content_box_back(panel):
    _to(panel, "SS")
    panel.clip_enable.setCurrentIndex(panel.clip_enable.findData("on"))
    panel.clip_content_mode.setCurrentIndex(
        panel.clip_content_mode.findData("branding"))
    _to(panel, "IO2")
    assert panel.clip_content_mode.currentData() == "off"   # the i1iO's own
    panel.clip_enable.setCurrentIndex(panel.clip_enable.findData("on"))
    panel.clip_content_mode.setCurrentIndex(
        panel.clip_content_mode.findData("text"))
    _to(panel, "SS")
    assert panel.clip_content_mode.currentData() == "branding"
    _to(panel, "IO2")                                    # and its own again
    assert panel.clip_content_mode.currentData() == "text"
    assert panel.get_recipe().i1io_clip_border is True


def test_a_loaded_recipe_shows_its_own_band(panel):
    from workflow.layout_engine.presets import LayoutRecipe
    _to(panel, "IO2")
    old = LayoutRecipe.from_dict({"instrument": "IO2", "paper": "A4",
                                  "clip_content_mode": "notes"})
    panel.set_recipe(old)
    assert panel.clip_enable.currentData() == "off"
    assert panel.get_recipe().i1io_clip_border is False
    on = LayoutRecipe.from_dict({**old.to_dict(), "i1io_clip_border": True,
                                 "clip_content_mode": "branding"})
    panel.set_recipe(on)
    assert panel.clip_enable.currentData() == "on"
    assert panel.clip_content_mode.currentData() == "branding"
    back = panel.get_recipe()
    assert back.i1io_clip_border is True
    assert LayoutRecipe.from_dict(back.to_dict()).i1io_clip_border is True


# ---- Guided ------------------------------------------------------------------

@pytest.fixture
def chart_tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    yield tab
    tab.deleteLater()


def test_guided_has_its_own_box_off_by_default(chart_tab):
    tab = chart_tab
    box = tab._i1io_clip_check
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("i1"))
    assert box.isHidden()
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("IO2"))
    assert not box.isHidden() and not box.isChecked()
    p = tab._collect_guided()
    assert p.i1io_clip_border is False
    kw = tab._creator._engine_build_kwargs(p)
    assert "i1io_clip_border" not in kw
    off = tab._creator._engine_total_patches(p)
    box.setChecked(True)
    p = tab._collect_guided()
    kw = tab._creator._engine_build_kwargs(p)
    assert kw["i1io_clip_border"] is True and kw["clip_content_mode"] == "notes"
    on = tab._creator._engine_total_patches(p)
    assert on < off
    assert tab._collect_ui_state()["guided"]["i1io_clip_border"] is True


@pytest.mark.parametrize("mode", ["notes", "text", "branding"])
@pytest.mark.parametrize("crosses", [True, False])
def test_the_patch_numbers_stay_1_mm_clear_of_the_band_content(tmp_path, mode,
                                                               crosses):
    """Review F3: the numbers may stand in the part of the band its
    content leaves free (the engine's row-label rule), never within 1 mm of
    that content: the paper between the content's reach and 1 mm past it
    is blank over the band's height."""
    from PIL import Image
    from workflow.i1io import chart as C
    from workflow.layout_engine import instruments
    kw = {C.CLIP_KEY: True, "clip_content_mode": mode,
          "clip_text": "Printer and ink\nsecond line", "i1io_crosses": crosses}
    result, side = _build(tmp_path, 300, "A4", **kw)
    geom = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4", "dpi": DPI, **kw})
    reach = geom.clip_content_reach_mm
    assert reach >= 0
    img = np.asarray(Image.open(result.tiff_paths[0]).convert("L"))
    _x0, y0, _x1, y1 = side["clip_border"]["area_mm"]
    gap = img[int(y0 * S) + 2:int(y1 * S) - 2,
              int(round(reach * S)) + 1:int((reach + 1.0) * S)]
    assert gap.size and gap.min() >= 250
