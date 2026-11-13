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
* a recipe from before the options (4.3.33's) ignores every one of them.
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
    _r, base = _build(tmp_path / "a")
    _r, moved = _build(tmp_path / "b", offset_x=2.0, offset_y=3.0)
    a, b = _strip(base), _strip(moved)
    assert b["x_mm"] == pytest.approx(a["x_mm"] + 2.0)
    assert b["patches"][0]["centre_mm"][1] == pytest.approx(
        a["patches"][0]["centre_mm"][1] + 3.0)


def test_an_offset_off_the_sheet_is_refused_not_built(tmp_path):
    from workflow.i1io.chart import I1ioSheetRefused
    with pytest.raises(I1ioSheetRefused):
        _build(tmp_path, offset_x=150.0)


def test_an_offset_into_the_run_is_a_warning(tmp_path):
    """The patches pushed so far down the page that a strip's blank paper
    reaches the edge: built, and said."""
    result, _side = _build(tmp_path, offset_y=10.0)
    assert any("arm to reach its speed" in w for w in result.warnings)


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


def test_clip_is_the_numbers_own_distance():
    from workflow.i1io import chart as C
    assert C.numbers_edge_of({}) == 10.0
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


# ---- 4.3.33's recipes ignore them ---------------------------------------------

OPENED = dict(edge_spacers=True, max_strip=120.0, nolimit=False,
              offset_x=2.0, offset_y=3.0, helper_markers=True,
              text_edge=8.0, strip_indicator_gap=2.0,
              strip_label_offset_mm=1.0, strip_label_offset_x_mm=1.0,
              i1io_numbers_edge_mm=6.0, i1io_text_align="start")


def test_a_recipe_from_before_the_options_ignores_them():
    from workflow.i1io import chart as C
    kw = dict(OPENED, **{C.OPTIONS_KEY: False})
    out = C.fixed_build_kwargs(kw)
    assert (out["edge_spacers"], out["max_strip"], out["nolimit"],
            out["offset_x"], out["offset_y"], out["helper_markers"]) == (
        False, None, True, 0.0, 0.0, False)
    labels = C.label_wishes(kw)
    assert (labels.edge, labels.gap, labels.off_x, labels.off_y) == (
        4.0, 0.0, 0.0, 0.0)
    assert C.numbers_edge_of(kw) == 10.0
    assert C.text_align_of(kw) == ""
    assert C.option_warnings(out) == []


def test_reading_a_4333_recipe_resets_the_new_fields():
    from workflow.layout_engine.presets import LayoutRecipe
    d = LayoutRecipe(instrument="IO2", edge_spacers=True, offset_x_mm=2.0,
                     offset_y_mm=1.0, helper_markers=True, max_strip_mm=120.0,
                     nolimit=False, strip_indicator_gap_mm=2.0,
                     strip_label_offset_mm=1.0, text_edge_mm=8.0,
                     i1io_numbers_edge_mm=6.0,
                     i1io_text_align="start").to_dict()
    d.pop("i1io_label_options")
    r = LayoutRecipe.from_dict(d)
    assert r.i1io_label_options is False
    assert (r.edge_spacers, r.offset_x_mm, r.offset_y_mm, r.helper_markers,
            r.max_strip_mm, r.nolimit, r.strip_indicator_gap_mm,
            r.strip_label_offset_mm, r.text_edge_mm, r.i1io_numbers_edge_mm,
            r.i1io_text_align) == (False, 0.0, 0.0, False, 0.0, True, 0.0,
                                   0.0, 4.0, 0.0, "")


def test_a_build_logs_its_warnings():
    import inspect
    from workflow import chart_creator
    src = inspect.getsource(chart_creator)
    i = src.index('getattr(result, "warnings", ())')
    assert ('tr("[WARNING] The i1iO table may not read this layout "\n'
            in src[i:i + 200])
