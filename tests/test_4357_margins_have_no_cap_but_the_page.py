"""A MARGIN MAY BE ANY VALUE THE PAGE CAN TAKE (4.3.57, item 25).

Basti, 2026-11-22, on the 60 mm cap every margin box in Create Chart had:
*"i did not even know the margin is limited ... usually such big margins are
not required but the limits are stupid. they would be stupid for other
instruments as well"*. His use: one wide margin so only a few rows fit on a
normal sheet, for small ink-saving test charts (a right margin of 165 mm on
A4 gives the i1iO three rows).

What is held here:

* the four margin boxes go up to the largest page ChromIQ makes, for every
  instrument, and keep a typed 165 mm exactly (no silent clamp);
* margins far beyond 60 mm lay out correctly on a hand-held strip instrument
  (i1Pro), the i1iO table and the i1iSis: the patches stay inside them;
* margins that leave no room are refused in plain words, never with the
  engine's "not enough width for even one row", and never with a crash
  ("division by zero" was what a 290 mm top margin gave);
* the panel outlines the margin boxes that leave no room, with the reason.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_i1io_aiming_crosses import _ti1  # noqa: E402

from workflow.layout_engine import geometry  # noqa: E402
from workflow.page_output.support import CUSTOM_MM_MAX  # noqa: E402

A4_W, A4_H = 210.0, 297.0


@pytest.fixture
def betas_on():
    from workflow.i1io import support as i1io
    from workflow.isis import support as isis
    before = (i1io._latched, isis._latched)
    i1io.set_enabled_for_this_process(True)
    isis.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        i1io._latched, isis._latched = before


def _build(tmp_path, instrument, margins, n=120, **kw):
    from workflow.layout_engine import chart
    tmp_path.mkdir(parents=True, exist_ok=True)
    ti1 = _ti1(tmp_path / "c.ti1", n)
    return chart.build_chart(ti1, tmp_path / "c", instrument=instrument,
                             paper="A4", dpi=50, seed=7, margins=margins, **kw)


def _ink_box_mm(result, dpi=50):
    rects = [r for r in result.strip_rects or [] if r.get("page", 0) == 0]
    assert rects, "no strips were drawn"
    k = 25.4 / dpi
    return (min(r["x"] for r in rects) * k, min(r["y"] for r in rects) * k,
            max(r["x"] + r["w"] for r in rects) * k,
            max(r["y"] + r["h"] for r in rects) * k)


# ---- the boxes --------------------------------------------------------------
@pytest.mark.parametrize("instrument", ["i1", "CM", "SS", "CR30", "IO2",
                                        "XRISIS"])
def test_every_margin_box_goes_up_to_the_largest_page(qapp, betas_on,
                                                      instrument):
    """MUTATION: put `small_mm(top=60.0)` back and this goes red at 165."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    try:
        i = p.instr.findData(instrument)
        assert i >= 0, f"{instrument} is not offered"
        p.instr.setCurrentIndex(i)
        for k, box in p.margins.items():
            assert box.maximum() == pytest.approx(CUSTOM_MM_MAX), k
        p.margins["r"].setValue(165.0)
        assert p.margins["r"].value() == pytest.approx(165.0)
        r = p.get_recipe()
        assert r.margin_right == pytest.approx(165.0)
    finally:
        p.deleteLater()


def _spin(qapp, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.01)


def _flagged(p, k):
    return k in {k2 for k2, box in p.margins.items()
                 if id(box) in getattr(p, "_field_conflict_orig", {})}


@pytest.mark.parametrize("instrument", ["i1", "CM", "IO2"])
def test_the_panel_outlines_margins_that_leave_no_room(qapp, betas_on,
                                                       instrument):
    """A margin that leaves no room is outlined with the reason, the value
    kept as typed; one that leaves room is not.

    MUTATION: drop `_apply_margin_room_flags` from
    `_update_clip_margin_conflict` and nothing is outlined."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    try:
        p.instr.setCurrentIndex(p.instr.findData(instrument))
        p.margins["t"].setValue(150.0)
        _spin(qapp, 0.4)
        assert not _flagged(p, "t") and not _flagged(p, "b")
        p.margins["t"].setValue(290.0)
        _spin(qapp, 0.4)
        assert p.margins["t"].value() == pytest.approx(290.0)
        assert _flagged(p, "t") and _flagged(p, "b")
        assert "top and bottom margins" in p.margins["t"].toolTip()
        p.margins["t"].setValue(20.0)
        p.margins["l"].setValue(205.0)
        _spin(qapp, 0.4)
        assert not _flagged(p, "t")
        assert _flagged(p, "l") and _flagged(p, "r")
        assert "left and right margins" in p.margins["l"].toolTip()
    finally:
        p.deleteLater()


# ---- the charts ---------------------------------------------------------------
def test_a_hand_held_strip_chart_with_a_100_mm_right_margin(tmp_path):
    r = _build(tmp_path, "i1", (6.0, 100.0, 6.0, 6.0))
    x0, _y0, x1, _y1 = _ink_box_mm(r)
    assert x1 <= A4_W - 100.0 + 0.6, f"patches run to {x1:.1f} mm"
    assert r.layout.total_patches >= 120


def test_a_hand_held_strip_chart_with_a_150_mm_top_margin(tmp_path):
    r = _build(tmp_path, "i1", (150.0, 6.0, 6.0, 6.0))
    _x0, y0, _x1, _y1 = _ink_box_mm(r)
    assert y0 >= 150.0 - 0.6, f"patches start at {y0:.1f} mm"


def test_the_i1io_table_with_basti_s_165_mm_right_margin(tmp_path, betas_on):
    """His example: three rows on A4."""
    r = _build(tmp_path, "IO2", (15.0, 165.0, 15.0, 15.0))
    _x0, _y0, x1, _y1 = _ink_box_mm(r)
    assert x1 <= A4_W - 165.0 + 0.6, f"patches run to {x1:.1f} mm"
    assert r.layout.strips_per_page >= 1


def test_the_i1iso_with_a_70_mm_top_margin(tmp_path, betas_on):
    r = _build(tmp_path, "XRISIS", (70.0, 6.0, 6.0, 6.0), project="m")
    _x0, y0, _x1, _y1 = _ink_box_mm(r)
    assert y0 >= 70.0 - 0.6


def test_the_i1isis_refuses_side_margins_it_cannot_take_in_words(tmp_path,
                                                                 betas_on):
    from workflow.isis.chart import IsisSheetRefused
    with pytest.raises(IsisSheetRefused) as got:
        _build(tmp_path, "XRISIS", (6.0, 120.0, 6.0, 80.0), project="m")
    assert "too narrow for even one column" in str(got.value)


def test_the_i1io_refuses_a_sheet_with_no_room_in_words(tmp_path, betas_on):
    from workflow import measurement_messages as M
    from workflow.i1io.chart import I1ioSheetRefused
    with pytest.raises(I1ioSheetRefused) as got:
        _build(tmp_path, "IO2", (290.0, 15.0, 15.0, 15.0))
    assert str(got.value) == M._I1IO_SHEET_TOO_SMALL


@pytest.mark.parametrize("instrument", ["i1", "CM", "CR30"])
@pytest.mark.parametrize("margins,words", [
    ((6.0, 105.0, 6.0, 105.0), "left and right margins"),
    ((290.0, 6.0, 6.0, 6.0), "top and bottom margins"),
])
def test_no_room_is_refused_in_plain_words(tmp_path, instrument, margins,
                                           words):
    """The engine's refusal carries the plain sentence the Generate window
    shows (`chart_creator`: `exc.plain`), never "division by zero".

    MUTATION: remove the `pitch <= 0` guard in `area_fit._max_rows_at` and
    the 290 mm top margin dies with ZeroDivisionError."""
    with pytest.raises(geometry.LayoutError) as got:
        _build(tmp_path, instrument, margins)
    assert got.value.plain and words in got.value.plain
    assert "—" not in got.value.plain


def test_the_generate_window_shows_the_plain_reason():
    import inspect
    from workflow import chart_creator
    src = inspect.getsource(chart_creator)
    assert 'getattr(exc, "plain", None)' in src


def test_no_room_kind_names_the_right_pair():
    from workflow.layout_engine.presets import LayoutRecipe
    r = LayoutRecipe()
    r.instrument, r.paper = "CM", "A4"
    assert geometry.recipe_no_room_kind(r) is None
    r.margin_left = 205.0
    assert geometry.recipe_no_room_kind(r) == geometry.NO_ROOM_ACROSS
    r.margin_left, r.margin_top = 6.0, 290.0
    assert geometry.recipe_no_room_kind(r) == geometry.NO_ROOM_ALONG


def test_printtargs_own_margin_limit_is_the_box_limit():
    """printtarg 3.5.0 takes -m up to 50 and refuses 50.5 ("Border margin ...
    is outside expected range"); the box stopped at 30 for no reason."""
    import yaml
    data = yaml.safe_load(Path("data/parameters.yaml").read_text("utf-8"))
    m = [p for p in data["parameters"]["printtarg"] if p["flag"] == "-m"][0]
    assert m["max"] == 50
