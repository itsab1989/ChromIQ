"""LIMITS ROUND 2: NO CAP BUT THE PAGE (4.3.57, item 39).

Basti's rule (22 Nov 2026): *a limit needs a physical reason or it goes*.
Part A took the 60 mm cap off the margins (item 25); this round widens the
rest of Create Chart's layout fields the coordinator listed, to the page or to
ArgyllCMS's own limits, and keeps the ones with a reason (the inventory's
section B says which and why).

What is held here, for every widened field:

* the box takes the new extreme and keeps a typed value exactly (no clamp);
* the extreme gives a CORRECT chart (every patch on the paper) or a PLAIN
  refusal (`LayoutError.plain`, `IsisSheetRefused`): never a crash, never a
  value quietly drawn as something else, never furniture silently left off
  or printed past the sheet's edge.
"""
from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_i1io_aiming_crosses import _ti1  # noqa: E402

from workflow.layout_engine import geometry  # noqa: E402
from workflow.page_output.support import CUSTOM_MM_MAX as PAGE  # noqa: E402

A4_W, A4_H = 210.0, 297.0
STRIP_AND_HEX = ["i1", "CM", "SS", "CR30"]


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


def _build(tmp_path, instrument, n=120, **kw):
    from workflow.layout_engine import chart
    tmp_path.mkdir(parents=True, exist_ok=True)
    ti1 = _ti1(tmp_path / "c.ti1", n)
    return chart.build_chart(ti1, tmp_path / "c", instrument=instrument,
                             paper="A4", dpi=50, seed=7, **kw)


def _patches_on_the_paper(result, dpi=50):
    """Every drawn patch of every page lies on the A4 sheet."""
    rects = result.strip_rects or []
    assert rects, "no patches were drawn"
    k = 25.4 / dpi
    for r in rects:
        x0, y0 = r["x"] * k, r["y"] * k
        x1, y1 = (r["x"] + r["w"]) * k, (r["y"] + r["h"]) * k
        assert x0 >= -0.6 and y0 >= -0.6, r
        assert x1 <= A4_W + 0.6 and y1 <= A4_H + 0.6, r


def _refused_in_words(exc_info, words):
    plain = getattr(exc_info.value, "plain", None) or str(exc_info.value)
    assert words in plain, plain
    assert "—" not in plain
    return plain


# ---- the boxes -----------------------------------------------------------------
def test_every_widened_box_reaches_its_new_limit_and_keeps_the_value(qapp):
    """MUTATION: put any old cap back (60, 100, 300, 30, ±50, 0.5..3.0, 20,
    200, 500) and this goes red at that box."""
    from ui.dialogs.layout_options_panel import (AREA_GRID_MAX, PAGES_MAX,
                                                 LayoutOptionsPanel)
    assert PAGES_MAX == 999 and AREA_GRID_MAX == 2000
    p = LayoutOptionsPanel(with_selectors=True)
    try:
        p.instr.setCurrentIndex(p.instr.findData("i1"))
        to_page = ["patch_x", "patch_y", "area_min_patch", "spacer_width",
                   "inter_patch", "strip_gap", "sig", "offx", "offy",
                   "clip_width", "helper_marker_edge", "helper_marker_len",
                   "text_edge_top", "text_edge", "text_edge_clip",
                   "strip_label_offset", "strip_label_offset_x"]
        for name in to_page:
            box = getattr(p, name)
            assert box.maximum() == pytest.approx(PAGE), name
            box.setValue(1500.0)
            assert box.value() == pytest.approx(1500.0), name
        for name in ("offx", "offy", "strip_label_offset",
                     "strip_label_offset_x"):
            box = getattr(p, name)
            assert box.minimum() == pytest.approx(-PAGE), name
            box.setValue(-1500.0)
            assert box.value() == pytest.approx(-1500.0), name
        assert p.clip_width.minimum() == pytest.approx(10.0)   # kept
        assert (p.pscale.minimum(), p.pscale.maximum()) == (0.1, 4.0)
        assert (p.sscale.minimum(), p.sscale.maximum()) == (0.1, 8.0)
        assert p.pages.maximum() == 999
        p.pages.setValue(999)
        assert p.get_pages() == 999
        assert p.area_cols.maximum() == p.area_rows.maximum() == 2000
        # kept, with their reasons in the inventory (section B)
        assert p.area_ratio.maximum() == 1000.0
        assert p.helper_marker_per_patch.maximum() == 12
        assert p.underline_thickness.maximum() == pytest.approx(5.0)
        assert p.underline_gap.maximum() == pytest.approx(20.0)
        # a typed value reaches the recipe as typed
        p.offx.setValue(-12.5)
        p.text_edge.setValue(250.0)
        p.pscale.setValue(0.1)
        r = p.get_recipe()
        assert r.offset_x_mm == pytest.approx(-12.5)
        assert r.text_edge_mm == pytest.approx(250.0)
        assert r.pscale == pytest.approx(0.1)
    finally:
        p.deleteLater()


def test_manuals_pages_box_takes_what_the_panels_takes():
    """The two Pages boxes mirror each other (`_mirror_pages_to_panel`): a
    narrower Manual box would clamp the panel's 999 back to 20 silently."""
    from ui.tabs import tab_chart
    src = inspect.getsource(tab_chart)
    assert "self._manual_pages_spin.setRange(1, _PGMAX)" in src
    assert "self._manual_pages_spin.setRange(1, 20)" not in src


def test_the_isis_trailer_and_notes_band_go_to_the_page(qapp, betas_on):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    try:
        p.instr.setCurrentIndex(p.instr.findData("XRISIS"))
        isis = [w for w in vars(p).values()
                if type(w).__name__ == "IsisPanel"] or [p]
        trailer = getattr(isis[0], "isis_trailer", None) \
            or getattr(p, "isis_trailer", None)
        band = getattr(isis[0], "isis_band_height", None) \
            or getattr(p, "isis_band_height", None)
        if trailer is None or band is None:
            pytest.skip("the i1iSis section is not built in this panel")
        assert trailer.maximum() == pytest.approx(PAGE)
        assert trailer.minimum() == pytest.approx(25.5)        # X-Rite's
        assert band.maximum() == pytest.approx(PAGE)
        assert band.minimum() == pytest.approx(4.0)
    finally:
        p.deleteLater()


# ---- the charts: a correct chart or a plain refusal ------------------------------
@pytest.mark.parametrize("instrument", STRIP_AND_HEX)
@pytest.mark.parametrize("kw,words", [
    (dict(patch_w=PAGE, patch_h=10.0), "no room for even one patch"),
    (dict(patch_w=8.0, patch_h=PAGE), "no room for even one patch"),
    (dict(layout_mode="area_first", area_min_patch=PAGE),
     "no room for even one patch"),
    (dict(strip_indicator_gap=PAGE), "The gaps around the patches"),
    (dict(offset_x=PAGE), "The chart offset moves part of the chart off"),
    (dict(offset_x=-PAGE), "The chart offset moves part of the chart off"),
    (dict(offset_y=-PAGE), "The chart offset moves part of the chart off"),
    (dict(offset_y=PAGE), "The chart offset moves part of the chart off"),
    (dict(helper_markers=True, helper_marker_edge=PAGE),
     "would meet in the middle of the sheet"),
    (dict(helper_markers=True, helper_marker_len=PAGE),
     "would meet in the middle of the sheet"),
    (dict(text_edge=PAGE, chart_text="hello"), "larger than the paper"),
    (dict(text_edge_top=PAGE), "larger than the paper"),
    (dict(text_edge_clip=PAGE), "larger than the paper"),
    (dict(strip_label_offset_mm=-PAGE), "strip letters would be printed off"),
    (dict(strip_label_offset_mm=PAGE), "strip letters would be printed off"),
])
def test_an_extreme_value_is_refused_in_plain_words(tmp_path, instrument, kw,
                                                    words):
    """MUTATION: take `_refuse_off_sheet` (or the check before the layout)
    out of `build_chart` and the offsets, markers, letters and text distances
    build a chart with things off the paper, or say the wrong sentence."""
    with pytest.raises(geometry.LayoutError) as got:
        _build(tmp_path, instrument, **kw)
    _refused_in_words(got, words)


@pytest.mark.parametrize("instrument", STRIP_AND_HEX)
@pytest.mark.parametrize("kw", [
    dict(pscale=0.1), dict(pscale=4.0), dict(sscale=0.1), dict(sscale=8.0),
    dict(spacer_width=PAGE), dict(inter_patch=PAGE), dict(strip_gap=PAGE),
    dict(offset_x=-3.0), dict(strip_label_offset_x_mm=PAGE),
    dict(strip_label_offset_x_mm=-PAGE), dict(clip_border_width=50.0),
    dict(layout_mode="area_first", area_method="by_columns", area_cols=2000),
    dict(layout_mode="area_first", area_method="by_rows", area_rows=2000),
])
def test_an_extreme_value_that_fits_gives_a_correct_chart(tmp_path, instrument,
                                                         kw):
    """A gap of 2000 mm leaves one patch per strip (or one strip per sheet):
    a chart that is wasteful but correct, with every patch on the paper and
    every patch of the set laid out. printtarg's scale limits (0.1 .. 4 / 8)
    build too. The sideways label offset is held at the paper edge with a
    notice (`raster.strip_label_x_plan`), as it was before round 2."""
    r = _build(tmp_path, instrument, **kw)
    assert r.layout.total_patches >= 120
    _patches_on_the_paper(r)


def test_a_clip_border_wider_than_the_paper_names_the_clip_border(tmp_path):
    """Not "the left and right margins": the clip border widens its side's
    margin, and that is the box to change (NO_ROOM_CLIP)."""
    with pytest.raises(geometry.LayoutError) as got:
        _build(tmp_path, "i1", clip_border_width=PAGE)
    _refused_in_words(got, "The clip border is so wide")


def test_no_room_kind_names_the_clip_border_and_the_gaps():
    from dataclasses import replace
    from workflow.layout_engine import instruments
    g = instruments.build("i1", border=6.0)
    assert geometry.no_room_kind(g, A4_W, A4_H) is None
    assert geometry.no_room_kind(replace(g, strip_indicator_gap=PAGE),
                                 A4_W, A4_H) == geometry.NO_ROOM_SPACING
    # a big margin beside small gaps is still the margin's doing (part A)
    assert geometry.no_room_kind(replace(g, margin_t=290.0), A4_W,
                                 A4_H) == geometry.NO_ROOM_ALONG


def test_a_ruler_marker_pair_is_held_only_to_its_own_side():
    """Top and bottom marks reach down the page's HEIGHT, side marks across
    its WIDTH. Until 4.3.57 both were held to the shorter side, so top and
    bottom marks of 120 mm on portrait A4 (less than half of 297) were
    silently left off. Drawing and refusal now share one rule."""
    assert not geometry.helper_markers_meet(A4_W, A4_H, 100.0, 20.0,
                                            top_bottom=True, sides=False)
    assert geometry.helper_markers_meet(A4_W, A4_H, 100.0, 20.0,
                                        top_bottom=False, sides=True)
    assert geometry.helper_markers_meet(A4_W, A4_H, 100.0, 20.0)
    from workflow.layout_engine import instruments
    g = instruments.build("i1", border=6.0)
    lay = geometry.compute(g, A4_W, A4_H, 120)
    lines = geometry.helper_marker_lines_mm(g, A4_W, A4_H, lay, edge_mm=100.0,
                                            length_mm=20.0, top_bottom=True,
                                            sides=False)
    assert lines, "the top and bottom marks were left off"
    assert geometry.ruler_markers_off_sheet(
        g, A4_W, A4_H, helper_markers=True, helper_marker_edge=100.0,
        helper_marker_len=20.0, helper_markers_top_bottom=True,
        helper_markers_sides=False) is None


def test_ruler_marks_that_would_meet_are_refused_not_dropped(tmp_path):
    with pytest.raises(geometry.LayoutError) as got:
        _build(tmp_path, "i1", helper_markers=True, helper_marker_edge=100.0,
               helper_marker_len=20.0)
    _refused_in_words(got, "Marker length")


# ---- the i1iSis -------------------------------------------------------------------
def _isis(tmp_path, **kw):
    return _build(tmp_path, "XRISIS", project="m", **kw)


def test_isis_notes_band_taller_than_the_header_holds_is_refused(tmp_path,
                                                                 betas_on):
    """It was clamped to 48 mm silently (X-Rite's 80 mm header less its own
    32 mm). Now it says so, and names the trailer as the place that takes it."""
    from workflow.isis.chart import IsisSheetRefused
    with pytest.raises(IsisSheetRefused) as got:
        _isis(tmp_path, isis_notes_band=True, isis_notes_place="header",
              isis_notes_height_mm=60.0)
    assert got.value.kind == "band_header"
    assert "put it in the trailer" in str(got.value)


def test_isis_notes_band_of_60_mm_in_the_trailer_is_drawn(tmp_path, betas_on):
    from workflow.isis import chart as ic
    r = _isis(tmp_path, isis_notes_band=True, isis_notes_place="trailer",
              isis_notes_height_mm=60.0)
    assert r.layout.total_patches >= 120
    opts = ic.options_from({ic.BAND_KEY: True, "isis_notes_place": "trailer",
                            ic.BAND_HEIGHT_KEY: 60.0})
    assert opts.notes_height == pytest.approx(60.0)      # not 48


def test_isis_trailer_as_long_as_the_page_is_refused_in_words(tmp_path,
                                                              betas_on):
    from workflow.isis.chart import IsisSheetRefused
    with pytest.raises(IsisSheetRefused) as got:
        _isis(tmp_path, isis_trailer_mm=PAGE)
    assert got.value.kind in ("long", "off_page", "short")   # A4: too short
    assert "—" not in str(got.value)


def test_isis_negative_offset_is_refused_not_read_as_zero(tmp_path, betas_on):
    from workflow.isis.chart import IsisSheetRefused
    with pytest.raises(IsisSheetRefused) as got:
        _isis(tmp_path, offset_x=-3.0)
    assert got.value.kind == "offset_negative"
    assert "—" not in str(got.value)
