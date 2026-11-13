"""ANY SHEET INSIDE THE TABLE'S REACH (review 5, item 7; the owner: "does
the i1iO allow for smaller and custom paper sizes as well?").

The build refused everything but A4 and Letter in practice: the lists
offered only those two. Now every sheet that, laid across the table, lies
inside the arm's published reach (`table_facts.REACH_MM`, 320 x 230 mm, a
PUBLISHED figure not yet confirmed on a table) builds: the smaller ones in the
lists (8x10", A5, 13 x 18 cm, 5x7", 4x6", 10 x 15 cm, postcard) and any custom
size in Manual. Everything adapts (capacity, bands, crosses, the name line).
Refused, in words: a sheet outside the reach, a landscape sheet, a sheet
too small for one strip. A sheet larger than A4/Letter in one direction but
inside the reach is built with a warning that the size is untested on a
table. A4 and Letter are unchanged (the baselines prove the bytes).
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_i1io_chart import _ti1  # noqa: E402


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _build(folder, paper, n=300, **kw):
    from workflow.layout_engine import chart
    folder.mkdir(parents=True, exist_ok=True)
    r = chart.build_chart(_ti1(folder / "c.ti1", n), folder / "c",
                          instrument="IO2", paper=paper, dpi=100, seed=1,
                          project="Small", chart_date="x", **kw)
    side = json.loads((folder / "c.i1io.json").read_text(encoding="utf-8"))
    return r, side


def test_the_lists_offer_every_sheet_in_reach():
    from workflow.i1io import chart as C
    from workflow.layout_engine import papers
    codes = [c for c, _l, _d in papers.list_papers("IO2", for_engine=True)]
    assert codes[:2] == ["A4", "Letter"]
    for code in ("148x210", "130x180", "4x6", "10x15cm", "127x178"):
        assert code in codes
    for code in codes:
        C.sheet_size(code)                       # none refused


SIZES = ["148x210", "130x180", "127x178", "4x6", "10x15cm", "postcard",
         "100x150", "155x205"]


@pytest.mark.parametrize("paper", SIZES)
@pytest.mark.parametrize("crosses", [True, False])
def test_a_smaller_sheet_builds_and_adapts(tmp_path, paper, crosses):
    from workflow.i1io import chart as C
    from workflow.layout_engine import geometry, instruments, papers
    kw = {C.CROSSES_KEY: crosses}
    r, side = _build(tmp_path, paper, **kw)
    w, h = (float(v) for v in papers.dimensions_mm(paper))
    assert side["paper_mm"] == [w, h]
    geom = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": paper, "dpi": 100, **kw})
    assert r.layout.patches_per_page == geometry.compute(
        geom, w, h, 300).patches_per_page          # estimate = build
    # every patch, letter and number on the sheet; the name line kept
    for page in side["pages"]:
        for st in page["strips"]:
            for p in st["patches"]:
                x, y = p["centre_mm"]
                assert 0 < x < w and 0 < y < h
        assert page["text_line"]["text"]
    assert not r.warnings


def test_a_sheet_too_small_for_one_strip_is_refused_in_words(tmp_path):
    from workflow.i1io import chart as C
    with pytest.raises(C.I1ioSheetRefused, match="too small for one strip"):
        _build(tmp_path, "30x40")
    _s, notes = C.preview_checks({"instrument": "IO2", "paper": "30x40",
                                  "dpi": 100, "area_target_count": 300})
    assert any("too small for one strip" in n for n in notes)


@pytest.mark.parametrize("paper,word", [("A3", "larger than the area"),
                                        ("297x210", "upright (portrait)")])
def test_outside_the_reach_or_landscape_is_refused_in_words(tmp_path, paper,
                                                            word):
    from workflow.i1io import chart as C
    with pytest.raises(C.I1ioSheetRefused, match=word.replace("(", r"\(")
                       .replace(")", r"\)")):
        _build(tmp_path, paper)


@pytest.mark.parametrize("paper", ["220x310", "230x320"])
def test_a_sheet_larger_than_a4_inside_the_reach_is_said(tmp_path, paper):
    from workflow.i1io import chart as C
    r, _side = _build(tmp_path, paper)
    assert any("untested" in w or "no sheet of this size" in w
               for w in r.warnings)
    _s, notes = C.preview_checks({"instrument": "IO2", "paper": paper,
                                  "dpi": 100, "area_target_count": 300})
    assert sorted(notes) == sorted(r.warnings)


def test_a_custom_size_is_kept_by_recipe_preset_and_panel(qapp, qtbot):
    import json as _j
    from dataclasses import replace
    from workflow.layout_engine.presets import (LayoutRecipe, PresetStore,
                                                default_recipe)
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    r = replace(default_recipe("IO2", "A4"), paper="155x205")
    assert LayoutRecipe.from_dict(_j.loads(_j.dumps(r.to_dict()))).paper \
        == "155x205"
    store = PresetStore()
    store.set(r)
    back = PresetStore.from_dict(_j.loads(_j.dumps(store.to_dict())))
    assert [x.paper for x in back._presets.values()] == ["155x205"]
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    p.set_recipe(r)
    assert p.get_recipe().paper == "155x205"


def test_a_name_line_with_no_room_on_a_tiny_sheet_is_said_rightly(tmp_path):
    """With the crosses on, a tiny sheet leaves no room between crosses 2
    and 3: said, with advice that fits (not "switch the crosses on")."""
    from workflow.i1io import chart as C
    r, _side = _build(tmp_path, "50x50")
    assert any("small sheet" in w for w in r.warnings), r.warnings
    assert not any("switch the aiming crosses on" in w for w in r.warnings)
    _s, notes = C.preview_checks({"instrument": "IO2", "paper": "50x50",
                                  "dpi": 100, "area_target_count": 300,
                                  "project": "Small"})
    assert sorted(notes) == sorted(r.warnings)


def test_a_custom_size_typed_lying_down_is_turned_upright(qtbot):
    """Review 6, item 2: the i1iO's custom boxes are the printed sheet,
    upright. 210 x 148 is turned to 148 x 210 in the boxes, said under them
    and in the log, and `selection` (what the Preview, the estimate and the
    build read) gives the upright size. Another instrument keeps its size and
    its words."""
    from workflow import measurement_messages as _mm
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    said = []
    p.notice.connect(said.append)
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    p.custom_w.setValue(210)
    p.custom_h.setValue(148)
    assert p.selection()[1] == "148x210"      # even before editing finishes
    p.custom_h.editingFinished.emit()
    assert (p.custom_w.value(), p.custom_h.value()) == (148.0, 210.0)
    assert said == [_mm._I1IO_CUSTOM_TURNED.format(w="148", h="210")]
    assert p._custom_turned_lbl.isVisibleTo(p)
    assert "upright" in p._custom_size_lbl.text()
    # another instrument: unchanged
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    p.custom_w.setValue(210)
    p.custom_h.setValue(148)
    p.custom_h.editingFinished.emit()
    assert p.selection()[1] == "210x148"
    assert (p.custom_w.value(), p.custom_h.value()) == (210.0, 148.0)
    assert len(said) == 1 and not p._custom_turned_lbl.isVisibleTo(p)
    assert p._custom_size_lbl.text() == "Custom size (mm):"


def test_the_notes_name_a_custom_sheet_properly():
    """Review 6, nit: the clip border's notes printed the raw code
    ("IO2 · 148x210"); they name the sheet as for A4 now. i1iO only."""
    from workflow.layout_engine import chart, papers
    assert chart._i1io_paper_name("A4") == papers.friendly_label("A4")
    assert chart._i1io_paper_name("148x210") == "A5 portrait"
    assert chart._i1io_paper_name("130x180") == "13 × 18 cm portrait"
    assert chart._i1io_paper_name("155x205") == "155 × 205 mm"
    assert "x" not in chart._i1io_paper_name("155x205")
