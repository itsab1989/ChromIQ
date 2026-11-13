"""THE i1iO CHART'S LABEL OPTIONS (2026-11-13).

Left greyed in 4.3.33 and queued by the owner ("cue up the label options"):
the label patterns, and the face / underline / alignment controls for the
labels and the sheet text. Held here:

* with every option at its default the chart is the one 4.3.33 made: the
  letters' band, the margins, the files (compared byte for byte);
* the patterns reach the `.ti2`, the strip letters, the side file and the
  aiming names; an unreadable pair is refused as on every chart;
* the letters' band grows for a longer label, a wider face or an
  underline, so the letters never reach a run or the paper edge;
* the alignment (the engine's rule for a side-turned label), the underline
  (between the letters and the run-outs, never on a run) and the face;
* the sheet text's face and size apply to the sheet text only, inside the
  band, never past the printer's edge; its Bold is the i1iO's own (bold,
  as in 4.3.33) unless a person unticks it;
* Manual: the controls are live, Bold shows the i1iO's own and is given
  back on leaving, and the bottom margin's minimum follows the letters.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_i1io_chart import _ti1  # noqa: E402
from tests.test_i1io_layout_options import _agree_and_blank  # noqa: E402

DPI = 100


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _build(folder, n=300, paper="A4", **kw):
    from workflow.layout_engine import chart
    folder.mkdir(parents=True, exist_ok=True)
    ti1 = _ti1(folder / "c.ti1", n)
    result = chart.build_chart(ti1, folder / "c", instrument="IO2",
                               paper=paper, dpi=DPI, seed=11,
                               project="Labels", chart_date="2026-11-13",
                               **kw)
    side = json.loads((folder / "c.i1io.json").read_text(encoding="utf-8"))
    from types import SimpleNamespace
    from workflow.layout_engine import instruments
    # the build's own geometry (the one estimate and build share)
    geom = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": paper, "dpi": DPI, **kw})
    return SimpleNamespace(ti2_path=result.ti2_path,
                           tiff_paths=result.tiff_paths,
                           layout=result.layout, geom=geom), side


#: What a recipe hands the engine for these controls when nobody changed them.
RECIPE_DEFAULTS = dict(
    strip_pattern="A-Z, A-Z", patch_pattern="0-9,@-9,@-9;1-999",
    indicator_font="JetBrains Mono", indicator_bold=False,
    indicator_italic=False, indicator_align="left", underline_mode="off",
    underline_thickness_mm=0.5, underline_gap_mm=0.5,
    chart_text_font="Inter", chart_text_size_mm=0.0, chart_text_bold=False,
    chart_text_italic=False)


# ---- defaults: today's chart --------------------------------------------------

def test_the_defaults_are_todays_band_and_margins():
    from workflow.i1io import chart as C
    from workflow.i1io import table_facts as F
    labels = C.label_wishes(RECIPE_DEFAULTS)
    assert labels == C.Labels()
    assert C.letter_band_for(labels) == F.letter_band_mm() == 11.0
    assert C.least_margins_mm(RECIPE_DEFAULTS) == F.margins_mm()
    assert C.text_style_of(RECIPE_DEFAULTS) is None


@pytest.mark.parametrize("crosses", [True, False])
def test_the_recipe_defaults_build_the_chart_built_without_them(tmp_path,
                                                                crosses):
    text = {"chart_text": "Gloss paper {date}"}
    a, _ = _build(tmp_path / "a", 250, i1io_crosses=crosses, **text)
    b, _ = _build(tmp_path / "b", 250, i1io_crosses=crosses, **text,
                  **RECIPE_DEFAULTS)
    for pa, pb in zip(a.tiff_paths, b.tiff_paths):
        assert pa.read_bytes() == pb.read_bytes()
    assert (tmp_path / "a" / "c.i1io.json").read_bytes() == \
        (tmp_path / "b" / "c.i1io.json").read_bytes()


# ---- patterns ----------------------------------------------------------------

def test_the_patterns_reach_every_file_and_name(tmp_path):
    from workflow.i1io import chart as C
    result, side = _build(tmp_path, 300, i1io_crosses=False,
                          strip_pattern="a-z, a-z")
    _agree_and_blank(tmp_path, result, side)
    locs = [p["loc"] for st in side["pages"][0]["strips"]
            for p in st["patches"]]
    assert locs[0][0].islower() and all(loc[0].islower() for loc in locs)
    body = result.ti2_path.read_text(encoding="utf-8")
    assert '"a1"' in body or " a1 " in body
    assert all(n[0].islower() for n in side["pages"][0]["aim_patches"])
    labels = C.label_wishes({"strip_pattern": "a-z, a-z"})
    letters = C.strip_letters(result.geom, result.layout, *side["paper_mm"],
                              0, DPI, labels)
    assert [t for t, _c, _s in letters][:3] == ["a", "b", "c"]


def test_an_unreadable_pattern_pair_is_refused(tmp_path):
    from workflow.layout_engine.alphix import PatternRefused
    with pytest.raises(PatternRefused):
        _build(tmp_path, 300, strip_pattern="0-9", patch_pattern="0-9")


# ---- the letters' band ----------------------------------------------------------

@pytest.mark.parametrize("kw", [
    dict(indicator_font="Inter", indicator_bold=True),
    dict(strip_pattern="A-Z,A-Z,A-Z"),
    dict(underline_mode="black", underline_thickness_mm=1.0,
         underline_gap_mm=1.5),
    dict(indicator_font="Instrument Serif", indicator_italic=True,
         underline_mode="segments")])
def test_the_band_grows_and_the_letters_stay_inside_it(tmp_path, kw):
    from workflow.i1io import chart as C
    from workflow.i1io import table_facts as F
    labels = C.label_wishes(kw)
    assert C.letter_band_for(labels) > F.letter_band_mm()
    assert C.least_margins_mm(kw)[2] == pytest.approx(
        F.RUN_MM.value + C.letter_band_for(labels))
    result, side = _build(tmp_path, 400, **kw)
    _agree_and_blank(tmp_path, result, side)
    w, h = side["paper_mm"]
    _assert_letters_inside(result, side, labels, w, h)


def _assert_letters_inside(result, side, labels, w, h):
    from PIL import Image, ImageDraw
    from workflow.i1io import chart as C
    from workflow.i1io import table_facts as F
    draw = ImageDraw.Draw(Image.new("L", (1, 1)))
    s = DPI / 25.4
    size_px = max(1, int(round(C.letter_size_mm(result.geom, DPI, labels)
                               * s)))
    font, _p, _v = C._font(size_px, labels.face, labels.italic, labels.bold)
    letters = C.strip_letters(result.geom, result.layout, w, h, 0, DPI,
                              labels, draw)
    runs = {round(st["x_mm"], 3): st["run_mm"][1]
            for st in side["pages"][0]["strips"]}
    for text, (x, start), _size in letters:
        bb = draw.textbbox((0, 0), text, font=font)
        length = (bb[2] - bb[0]) / s
        run_end = runs[round(x, 3)]
        assert start - length >= run_end + F.LABEL_CLEAR_MM.value \
            + labels.rule_mm - 1e-6
        assert start <= h - F.LETTER_EDGE_MM.value + 1e-6


@pytest.mark.parametrize("align", ["left", "center", "right"])
def test_the_alignment_places_the_letters_in_the_band(tmp_path, align):
    from workflow.i1io import chart as C
    from workflow.i1io import table_facts as F
    kw = {"indicator_align": align}       # one letter in a two-letter band
    labels = C.label_wishes(kw)
    result, side = _build(tmp_path, 300, **kw)
    w, h = side["paper_mm"]
    _assert_letters_inside(result, side, labels, w, h)
    letters = C.strip_letters(result.geom, result.layout, w, h, 0, DPI,
                              labels)
    run_end = side["pages"][0]["strips"][0]["run_mm"][1]
    inner = run_end + F.LABEL_CLEAR_MM.value
    outer = h - F.LETTER_EDGE_MM.value
    _t, (_x, start), _s = letters[0]
    if align == "right":
        assert start == pytest.approx(outer)
    elif align == "left":                 # 4.3.33's place, at the strip
        assert start < (inner + outer) / 2.0
        assert start - inner < 4.0
    else:
        assert (inner + outer) / 2.0 < start < outer


@pytest.mark.parametrize("mode", ["black", "segments", "cycle"])
def test_the_underline_lies_past_every_run_out(tmp_path, mode):
    import numpy as np
    from PIL import Image
    from workflow.i1io import chart as C
    from workflow.i1io import table_facts as F
    kw = {"underline_mode": mode, "underline_thickness_mm": 0.8}
    result, side = _build(tmp_path, 300, **kw)
    _agree_and_blank(tmp_path, result, side)
    labels = C.label_wishes(kw)
    w, h = side["paper_mm"]
    rects = C.underline_rects(result.geom, result.layout, w, h, 0, labels)
    assert rects
    run_end = max(st["run_mm"][1] for st in side["pages"][0]["strips"])
    for (x0, y0, x1, y1), rgb in rects:
        assert y0 >= run_end + F.LABEL_CLEAR_MM.value - 1e-6
        assert y1 - y0 == pytest.approx(0.8)
    # and it is printed
    img = np.asarray(Image.open(result.tiff_paths[0]).convert("RGB"))
    s = DPI / 25.4
    (x0, y0, x1, y1), rgb = rects[0]
    px = img[int(round((y0 + y1) / 2 * s)), int(round((x0 + x1) / 2 * s))]
    assert tuple(int(v) for v in px) == tuple(rgb)


def test_the_letters_and_numbers_take_the_face(tmp_path, monkeypatch):
    from workflow.i1io import chart as C
    asked = []
    real = C._font

    def spy(px, family="Inter", italic=False, bold=True):
        asked.append((family, italic, bold))
        return real(px, family, italic, bold)

    monkeypatch.setattr(C, "_font", spy)
    _build(tmp_path, 200, indicator_font="Inter", indicator_italic=True)
    assert ("Inter", True, False) in asked


# ---- the sheet text's style ------------------------------------------------------

def test_the_sheet_text_takes_its_own_face_and_the_name_keeps_its(tmp_path):
    from workflow.i1io import chart as C
    from workflow.layout_engine import geometry, instruments, papers
    style = C.SheetTextStyle(family="Instrument Serif", bold=False,
                             italic=True, size_mm=0.0)
    w, h = papers.dimensions_mm("A4")
    plan = C.styled_line_plan(w, h, "My chart", "Glossy paper, ink set B",
                              300, style)
    assert [p["family"] for p in plan["parts"]] == ["Inter",
                                                    "Instrument Serif"]
    assert plan["parts"][0]["bold"] is True
    assert plan["parts"][1]["italic"] is True
    assert plan["text"] == "My chart  ·  Glossy paper, ink set B"
    # the parts follow each other up the page, inside the room
    _x0, room_y0, _x1, room_y1 = C.text_column(w, h)
    g0, g1 = plan["group"]
    assert room_y0 - 1e-6 <= g0 and g1 <= room_y1 + 1e-6
    assert plan["parts"][1]["y"] < plan["parts"][0]["y"]


def test_a_large_sheet_text_is_held_inside_the_band():
    from PIL import Image, ImageDraw
    from workflow.i1io import chart as C
    from workflow.layout_engine import papers
    w, h = papers.dimensions_mm("A4")
    style = C.SheetTextStyle(family="Inter", size_mm=20.0)
    plan = C.styled_line_plan(w, h, "Chart", "Big text", 300, style)
    part = plan["parts"][-1]
    s = 300 / 25.4
    font, _p, _v = C._font(part["size_px"], "Inter", False, False)
    up, down = C._across(ImageDraw.Draw(Image.new("L", (1, 1))), font,
                         "Big text" + "Hgy…", s)
    x0, _y0, x1, _y1 = C.text_column(w, h)
    assert plan["line_x"] - up >= x0 - 1e-6
    assert plan["line_x"] + down <= x1 + 1e-6
    assert part["size_px"] < round(20.0 * s)


def test_without_crosses_the_styled_text_stays_in_its_spot():
    from workflow.i1io import chart as C
    spot = {"spot": "bottom edge", "x0": 100.0, "x1": 108.0, "y0": 10.0,
            "y1": 287.0, "mid_y": 150.0}
    style = C.SheetTextStyle(family="Instrument Serif", italic=True)
    plan = C.free_text_plan(spot, "1/2  ·  Chart", "Gloss, ink B", 300,
                            style=style)
    assert "sheet text" in plan["kept"]
    assert [p["family"] for p in plan["parts"]] == ["Inter",
                                                    "Instrument Serif"]
    plain = C.free_text_plan(spot, "1/2  ·  Chart", "Gloss, ink B", 300)
    assert "parts" not in plain


def test_the_i1io_sheet_text_is_bold_until_unticked():
    from workflow.i1io import chart as C
    from workflow.layout_engine.presets import LayoutRecipe
    assert C.text_style_of({}) is None
    off = C.text_style_of({C.TEXT_BOLD_KEY: False})
    assert off is not None and off.bold is False
    r = LayoutRecipe(instrument="IO2", i1io_text_bold=False)
    assert r.to_dict()["i1io_text_bold"] is False
    assert r.build_kwargs()["i1io_text_bold"] is False
    assert LayoutRecipe.from_dict(r.to_dict()).i1io_text_bold is False
    assert "i1io_text_bold" not in LayoutRecipe(instrument="IO2").to_dict()
    other = LayoutRecipe(instrument="i1", i1io_text_bold=False)
    assert "i1io_text_bold" not in other.to_dict()
    assert "i1io_text_bold" not in other.build_kwargs()


# ---- Manual ------------------------------------------------------------------

@pytest.fixture
def panel(qapp, qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    return p


def _to(panel, code):
    panel.instr.setCurrentIndex(panel.instr.findData(code))


def test_manual_wires_the_label_options(panel):
    from workflow.i1io import chart as C
    _to(panel, "i1")
    panel.ct_bold.setChecked(False)
    _to(panel, "IO2")
    for c in (panel.strip_pat, panel.patch_pat, panel.indicator_font,
              panel.underline_mode, panel.ind_align_left,
              panel.chart_text_font, panel.chart_text_size, panel.ct_bold):
        assert c.isEnabled(), c
        assert c in panel._i1io_live_controls()
    assert panel.chart_text_align.isEnabled()          # Job D: open
    assert panel.ct_bold.isChecked()                    # the i1iO's own
    assert panel.get_recipe().i1io_text_bold is None
    panel.ct_bold.setChecked(False)
    assert panel.get_recipe().i1io_text_bold is False
    # the bottom margin follows the letters' band
    before = panel.margins["b"].value()
    panel.underline_mode.setCurrentIndex(panel.underline_mode.findData("black"))
    r = panel.get_recipe()
    least = C.least_margins_mm({**r.build_kwargs(), "instrument": "IO2"})
    assert panel.margins["b"].minimum() == pytest.approx(least[2])
    assert panel.margins["b"].value() == pytest.approx(least[2])
    assert panel.margins["b"].value() > before
    panel.underline_mode.setCurrentIndex(panel.underline_mode.findData("off"))
    assert panel.margins["b"].value() == pytest.approx(before)
    _to(panel, "i1")
    assert not panel.ct_bold.isChecked()                # given back
    _to(panel, "IO2")
    assert not panel.ct_bold.isChecked()                # the i1iO's, kept


def test_a_loaded_recipe_shows_the_i1ios_bold(panel):
    from workflow.layout_engine.presets import LayoutRecipe
    _to(panel, "IO2")
    panel.set_recipe(LayoutRecipe.from_dict({"instrument": "IO2",
                                             "paper": "A4"}))
    assert panel.ct_bold.isChecked()
    panel.set_recipe(LayoutRecipe.from_dict({"instrument": "IO2",
                                             "paper": "A4",
                                             "i1io_text_bold": False}))
    assert not panel.ct_bold.isChecked()
    assert panel.get_recipe().i1io_text_bold is False


# ---- review F1: a large sheet-text size never costs the name line ------------

@pytest.mark.parametrize("crosses", [True, False])
@pytest.mark.parametrize("n", [300, 508, 520, 528])
def test_a_72_pt_sheet_text_never_drops_the_name_and_page(crosses, n):
    """Review F1: crosses off, sheet text 16 mm or 72 pt, 508 to 528
    patches printed no line at all. The name and page number come first;
    the sheet text is shrunk, and left off only if even its smallest size
    does not fit."""
    from workflow.i1io import chart as C
    from workflow.layout_engine import geometry, instruments, papers
    kw = {"paper": "A4", "i1io_crosses": crosses,
          "chart_text_size_mm": 25.4}           # 72 pt
    k = {**kw, "instrument": "IO2"}
    geom = instruments.geom_from_build_kwargs(k)
    w, h = papers.dimensions_mm("A4")
    layout = geometry.compute(geom, w, h, n)
    plan = C.line_plan(geom, layout, w, h, 0, name="My chart",
                       sheet_text="Hi there", dpi=300,
                       labels=C.label_wishes(C.fixed_build_kwargs(k)),
                       crosses=crosses, style=C.text_style_of(kw))
    if not crosses and not C.free_spots(geom, layout, w, h, 0,
                                        C.label_wishes(
                                            C.fixed_build_kwargs(k))):
        return                  # a full page has no free paper at all (§24)
    assert plan["text"].startswith("My chart")
    if plan.get("parts"):
        assert plan["parts"][0]["text"].startswith("My chart")
        assert plan["parts"][-1]["size_px"] <= round(25.4 * 300 / 25.4)


def test_a_sheet_text_that_cannot_fit_is_left_off_not_the_name():
    from workflow.i1io import chart as C
    spot = {"spot": "bottom edge", "x0": 100.0, "x1": 104.0, "y0": 10.0,
            "y1": 287.0, "mid_y": 150.0}
    style = C.SheetTextStyle(family="Inter", size_mm=25.4)
    plan = C.free_text_plan(spot, "1/2  ·  Chart", "Hi there", 300,
                            style=style)
    assert "name" in plan["kept"]
    assert plan["text"].startswith("1/2  ·  Chart")


# ---- review F2: Preferences' label style, as for every instrument -----------

@pytest.fixture
def prefs_tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("strip_underline_mode", "black")
    s.set("strip_indicator_font", "Inter")
    s.set("strip_indicator_bold", True)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    yield tab
    tab.deleteLater()


@pytest.mark.parametrize("code", ["i1", "IO2"])
def test_preferences_label_style_is_treated_as_for_the_i1pro(prefs_tab, code):
    """Guided ignores Preferences' label style (no recipe: the engine's
    defaults), Manual uses it while the recipe has no style of its own,
    for the i1Pro and the i1iO alike."""
    from PyQt6.QtWidgets import QApplication
    tab = prefs_tab
    tab._switch_mode("guided")
    i = tab._instr_combo.findData(code)
    tab._instr_combo.setCurrentIndex(i)
    tab._instr_combo.activated.emit(i)
    QApplication.processEvents()
    kw = tab._creator._engine_kwargs(tab._collect_guided())
    assert "underline_mode" not in kw and "indicator_font" not in kw
    # Guided -> Manual as a person does it: the panel follows Guided's
    # instrument, nothing is picked again (review R1 d)
    tab._switch_mode("manual")
    tab._init_manual_layout_panel()
    panel = tab._manual_layout_panel
    QApplication.processEvents()
    assert panel.instr.currentData() == code
    r = tab._current_layout_recipe()
    assert (r.underline_mode, r.indicator_font, r.indicator_bold) == \
        ("black", "Inter", True)


def test_the_i1io_margin_boxes_are_the_builds(prefs_tab):
    """Review F2: the Bottom box showed 21.0 while the build used 26.38."""
    from PyQt6.QtWidgets import QApplication
    from workflow.i1io import chart as C
    tab = prefs_tab
    tab._switch_mode("guided")
    i = tab._instr_combo.findData("IO2")
    tab._instr_combo.setCurrentIndex(i)
    tab._instr_combo.activated.emit(i)
    QApplication.processEvents()
    tab._switch_mode("manual")            # no re-pick (review R1 d)
    tab._init_manual_layout_panel()
    panel = tab._manual_layout_panel
    QApplication.processEvents()
    assert panel.instr.currentData() == "IO2"
    least = C.least_margins_mm({**tab._current_layout_recipe().build_kwargs(),
                                "instrument": "IO2"})
    assert least[2] > 21.0
    # the box shows one decimal
    assert panel.margins["b"].minimum() == pytest.approx(least[2], abs=0.05)
    assert panel.margins["b"].value() >= least[2] - 0.05


# ---- review R4: a larger sheet-text size never loses more than a smaller ----

@pytest.mark.parametrize("paper,crosses,n", [("Letter", False, 300),
                                             ("A4", False, 300),
                                             ("A4", True, 300)])
def test_a_larger_sheet_text_size_never_loses_more(paper, crosses, n):
    """Review R4: Letter, no crosses, 300 patches: at 22 mm the sheet text
    was printed (shortened), at 72 pt it and the logo were dropped. Every
    size from 22 mm up keeps at least what 22 mm keeps."""
    from workflow.i1io import chart as C
    from workflow.layout_engine import geometry, instruments, papers
    name = "Proof chart Glossy Baryta"
    text = "Hahnemuehle Photo Rag 308, ink set B, 2026-11-13"

    def kept(size):
        kw = {"paper": paper, "i1io_crosses": crosses,
              "chart_text_size_mm": size}
        k = {**kw, "instrument": "IO2"}
        geom = instruments.geom_from_build_kwargs(k)
        w, h = papers.dimensions_mm(paper)
        layout = geometry.compute(geom, w, h, n)
        plan = C.line_plan(geom, layout, w, h, 0, name=name,
                           sheet_text=text, dpi=300,
                           labels=C.label_wishes(C.fixed_build_kwargs(k)),
                           crosses=crosses, style=C.text_style_of(kw))
        assert plan["text"].startswith("Proof chart"), (size, plan["text"])
        return ({"name"}
                | ({"sheet text"} if "Hahnemuehle"[:4] in plan["text"]
                   else set())
                | ({"logo"} if plan.get("wordmark") else set()))

    base = kept(22.0)
    for size in (24.0, 25.4, 40.0):
        assert kept(size) >= base, size
