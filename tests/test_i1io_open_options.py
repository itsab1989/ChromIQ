"""THE i1iO OPTIONS JOB D OPENED (the owner, 2026-11-13).

"Our defaults should be safe but advanced users should be able to tweak as
much as possible." Controls 4.3.33 greyed only because a careless value could
hurt the reading are live now, behave as on the other instruments (allowed,
said in the log when risky) and refuse only what cannot be printed or
measured. Held here, one option at a time, on a real build:

* the offsets move the patches; the edge spacers and the ruler helper
  markers are printed and SAID (a warning, not a refusal);
* "B" moves the strip letters off the bottom edge, the letters keep past the
  markers' ink; "Clip" is the patch numbers' own distance (default 10 mm);
* the strip-indicator gap and the label offsets move the letters;
* the sheet text's line can start at the left end of its paper;
* the strip-length cap is a person's;
* a patch off the sheet is still refused; a run near the edge is a warning;
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_i1io_chart import _ti1  # noqa: E402

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


def _build(folder, n=300, **kw):
    from workflow.layout_engine import chart
    folder.mkdir(parents=True, exist_ok=True)
    ti1 = _ti1(folder / "c.ti1", n)
    result = chart.build_chart(ti1, folder / "c", instrument="IO2",
                               paper="A4", dpi=DPI, seed=11,
                               project="Open", chart_date="2026-11-13", **kw)
    side = json.loads((folder / "c.i1io.json").read_text(encoding="utf-8"))
    return result, side


def _strip(side, i=0, page=0):
    return side["pages"][page]["strips"][i]


# ---- offsets -----------------------------------------------------------------

def test_the_offsets_move_the_patches(tmp_path):
    """The block moves by the offset, and the floor on that side grows by
    as much (review 5, item 2), so it never reaches a cross or the edge."""
    from workflow.i1io import chart as C
    _r, base = _build(tmp_path / "a")
    _r, moved = _build(tmp_path / "b", offset_x=2.0, offset_y=3.0)
    a, b = _strip(base), _strip(moved)
    assert b["x_mm"] > a["x_mm"]
    w, h = moved["paper_mm"]
    least = C.least_margins_mm({})
    last = moved["pages"][0]["strips"][-1]
    assert last["x_mm"] + moved["patch_mm"][0] / 2 <= w - least[1] + 1e-6


def test_an_offset_is_fitted_and_only_no_room_is_refused(tmp_path):
    """Review 5, item 2: a large offset lays out fewer patches; only an
    offset that leaves no room for one strip is refused."""
    from workflow.i1io.chart import I1ioSheetRefused
    small, _s = _build(tmp_path / "a", offset_x=150.0)
    assert 0 < small.layout.patches_per_page < 528
    with pytest.raises(I1ioSheetRefused, match="too small for one strip"):
        _build(tmp_path / "b", offset_x=180.0)


def test_an_offset_down_the_page_keeps_the_runs_on_the_paper(tmp_path):
    """Chart offset Y 10 used to push the last run to the paper's edge (a
    warning); fitted, the block keeps its floor and nothing is said."""
    result, _side = _build(tmp_path, offset_y=10.0)
    assert not any("arm to reach its speed" in w for w in result.warnings)


# ---- edge spacers and ruler helper markers: allowed, and said ----------------

def test_edge_spacers_are_printed_and_said(tmp_path):
    from workflow.i1io import chart as C
    result, _side = _build(tmp_path, edge_spacers=True)
    assert result.warnings
    assert any("Edge spacers" in w for w in result.warnings)
    assert C.fixed_build_kwargs({"edge_spacers": True})["edge_spacers"]


def test_the_defaults_say_nothing(tmp_path):
    result, _side = _build(tmp_path)
    assert result.warnings == ()


def test_ruler_markers_are_printed_said_and_the_letters_keep_past_them(
        tmp_path):
    from workflow import text_edge_fit as tef
    from workflow.i1io import chart as C
    kw = dict(helper_markers=True, helper_marker_edge=3.0,
              helper_marker_len=4.0)
    result, _side = _build(tmp_path, **kw)
    assert any("ruler helper markers" in w for w in result.warnings)
    labels = C.label_wishes(kw)
    assert labels.edge >= tef.helper_marker_ink_reach_mm(3.0, 4.0) + 1.0
    assert C.fixed_build_kwargs(kw)["helper_markers"] is True
    # only the sides: nothing on the arm's paper, nothing said
    sides = dict(kw, helper_markers_top_bottom=False)
    assert C.option_warnings(sides) == []


# ---- text distances ----------------------------------------------------------

def test_b_moves_the_letters_off_the_bottom_edge():
    from workflow.i1io import chart as C
    from workflow.i1io import table_facts as F
    assert C.label_wishes({}).edge == F.LETTER_EDGE_MM.value
    far = C.label_wishes({"text_edge": 8.0})
    assert far.edge == 8.0
    assert C.letter_band_for(far) == pytest.approx(
        C.letter_band_for(C.label_wishes({})) + 8.0 - F.LETTER_EDGE_MM.value)
    assert C.least_margins_mm({"text_edge": 8.0})[2] > C.least_margins_mm(
        {})[2]


def _numbers_ink_mm(result) -> float:
    """Where the patch numbers' ink starts on the PRINTED page, from its
    left edge: the first dark column in the page's middle band, left of the
    patches (the crosses sit in the corners, outside the band)."""
    import numpy as np
    from PIL import Image
    im = np.asarray(Image.open(result.tiff_paths[0]).convert("L"))
    h, w = im.shape
    band = im[int(h * 0.3):int(h * 0.7), :int(w * 0.3)]
    cols = np.where((band < 128).any(axis=0))[0]
    return cols[0] / DPI * 25.4


@pytest.mark.parametrize("edge", [1.0, 2.0, 10.0, 25.0])
def test_clip_moves_the_printed_numbers(tmp_path, edge):
    """Review 3, item 3: at 2, 10 and 25 mm the numbers printed at 10.9 mm
    whatever was asked; 25 only widened the margin. Measured on the page."""
    from workflow.i1io import chart as C
    result, _side = _build(tmp_path, **{C.NUMBERS_EDGE_KEY: edge})
    ink = _numbers_ink_mm(result)
    assert edge <= ink < edge + 2.0


def test_clip_is_the_numbers_own_distance():
    from workflow.i1io import chart as C
    assert C.numbers_edge_of({}) == 10.0
    assert C.numbers_edge_of({C.NUMBERS_EDGE_KEY: None}) == 10.0
    assert C.numbers_edge_of({C.NUMBERS_EDGE_KEY: 1.0}) == 1.0
    assert C.numbers_edge_of({C.NUMBERS_EDGE_KEY: 6.0}) == 6.0
    # the engine's own clip distance is not it (that is the i1Pro band's)
    assert C.numbers_edge_of({"text_edge_clip": 3.0}) == 10.0
    assert C.fixed_build_kwargs(
        {C.NUMBERS_EDGE_KEY: 6.0})["text_edge_clip"] == 6.0


# ---- the letters: gap and offsets --------------------------------------------

def _letter_starts(tmp_path, name, **kw):
    from workflow.i1io import chart as C
    from workflow.layout_engine import instruments
    result, side = _build(tmp_path / name, **kw)
    geom = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4", "dpi": DPI, **kw})
    w, h = side["paper_mm"]
    return C.strip_letters(geom, result.layout, w, h, 0, DPI,
                           C.label_wishes(kw))


def test_the_gap_and_the_offsets_move_the_letters(tmp_path):
    base = _letter_starts(tmp_path, "a")
    gap = _letter_starts(tmp_path, "b", strip_indicator_gap=2.0)
    off = _letter_starts(tmp_path, "c", strip_label_offset_mm=1.5,
                         strip_label_offset_x_mm=0.5)
    (_t, (x0, y0), _s) = base[0]
    (_t, (xg, yg), _s) = gap[0]
    (_t, (xo, yo), _s) = off[0]
    assert yg != pytest.approx(y0)           # past the run-out, further
    assert (xo, yo) != pytest.approx((x0, y0))


# ---- the sheet text's place --------------------------------------------------

def test_the_line_can_start_at_the_left_end(tmp_path):
    from workflow.i1io import chart as C
    assert C.text_align_of({}) == ""
    assert C.text_align_of({C.TEXT_ALIGN_KEY: "start"}) == "start"
    _r, centred = _build(tmp_path / "a")
    _r, start = _build(tmp_path / "b", **{C.TEXT_ALIGN_KEY: "start"})
    a = centred["pages"][0]["wordmark_mm"]
    b = start["pages"][0]["wordmark_mm"]
    assert a != b


# ---- strip length -------------------------------------------------------------

def test_the_strip_length_cap_is_a_persons(tmp_path):
    from workflow.i1io import chart as C
    assert C.fixed_build_kwargs({})["nolimit"] is True
    assert C.fixed_build_kwargs({"nolimit": False,
                                 "max_strip": 120.0})["max_strip"] == 120.0
    _r, base = _build(tmp_path / "a")
    _r, capped = _build(tmp_path / "b", nolimit=False, max_strip=120.0)
    assert len(_strip(capped)["patches"]) < len(_strip(base)["patches"])


def test_a_build_logs_its_warnings():
    import inspect
    from workflow import chart_creator
    src = inspect.getsource(chart_creator)
    i = src.index('getattr(result, "warnings", ())')
    assert ('tr("[WARNING] The i1iO table may not read this layout "\n'
            in src[i:i + 200])


def test_what_clip_shows_is_stored_built_and_shown_again(qapp, qtbot):
    """Nit 6a: "Clip" on the i1iO starts at 1 mm (0 would read as unset in
    the engine); typing 0 shows 1, and 1 is what is stored, built and shown
    again when the recipe is loaded; a recipe without a value shows 10."""
    from workflow.i1io import chart as C
    from workflow.layout_engine.presets import LayoutRecipe, default_recipe
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    i = p.instr.findData("IO2")
    p.instr.setCurrentIndex(i)
    p.instr.activated.emit(i)
    assert p.text_edge_clip.value() == 10.0
    assert p.get_recipe().i1io_numbers_edge_mm is None
    p.text_edge_clip.setValue(0.0)
    assert p.text_edge_clip.value() == 1.0
    r = p.get_recipe()
    assert r.i1io_numbers_edge_mm == 1.0
    back = LayoutRecipe.from_dict(r.to_dict())
    assert back.i1io_numbers_edge_mm == 1.0
    assert C.numbers_edge_of(back.build_kwargs()) == 1.0
    p.set_recipe(default_recipe("IO2", "A4"))
    assert p.text_edge_clip.value() == 10.0
    p.set_recipe(back)
    assert p.text_edge_clip.value() == 1.0
    # leaving the i1iO gives the shared box its own range back
    i = p.instr.findData("i1")
    p.instr.setCurrentIndex(i)
    assert p.text_edge_clip.minimum() == 0.0
