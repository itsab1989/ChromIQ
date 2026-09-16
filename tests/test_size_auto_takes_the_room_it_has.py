""""Size auto" is a size, not a floor: it grows to the room and stops at a ceiling.

A tester, beta 18: *"When Size=auto for the sheet text, the bottom text is still
not automatically sized. The size of text is kept quite small even when there is
a lot of space in both available width and height. Set a reasonable upper limit
to automatically set text to, without the text getting too big (such as 15 or
16pt?), so that if there is a lot of space the text does not become screaming
large. This should apply to all the Size=Auto settings, except the Strip and Row
labels, which have their own auto behaviour."*

`render_page` started the shrink loop at `SHEET_TEXT_DEFAULT_MM` (3.2 mm, or
9.07 pt) and the loop only ever decremented, so "auto" could not grow however
much paper was free. It now starts at
:data:`text_edge_fit.AUTO_SIZE_CEILING_PT` and comes down.

**AND THE ENGINE'S RESERVE HAD TO FOLLOW IT.** `_furniture_reserves_mm` held
back a flat 4.2 mm a line, so the first version of the ceiling positioned the
block for a 4.2 mm line and drew it at 16 pt: the ink crossed the "B" reserve on
its way to the paper edge. Caught by
`tests/test_the_bottom_sheet_text_keeps_its_reserve.py` and
`tests/test_the_top_and_bottom_edges_keep_off_the_helper_markers.py` on the
first full run after the ceiling went in, which is what those two files are for.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import text_edge_fit as tef                       # noqa: E402
from workflow.layout_engine import instruments, raster          # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe         # noqa: E402


def test_the_ceiling_is_where_the_tester_asked_for_it():
    assert 15.0 <= tef.AUTO_SIZE_CEILING_PT <= 16.0, (
        f"the ceiling is {tef.AUTO_SIZE_CEILING_PT} pt; he asked for "
        "'such as 15 or 16pt'")
    assert tef.AUTO_SIZE_CEILING_PT > tef.AUTO_SHRINK_FLOOR_PT


def test_a_short_line_with_room_reaches_the_ceiling():
    """MUTATION: start the search at `SHEET_TEXT_DEFAULT_MM` again and this
    goes red."""
    got = raster.auto_sheet_text_size_mm(["ChromIQ"], 180.0, "Inter", False,
                                         False, 300)
    assert got == pytest.approx(tef.pt_to_mm(tef.AUTO_SIZE_CEILING_PT))
    assert got > tef.SHEET_TEXT_DEFAULT_MM + 1.0, (
        f"auto resolved to {got:.3f} mm, barely past the old 3.2 mm default")


def test_a_long_line_still_shrinks_and_stops_at_the_floor():
    """The half that was already right: nothing may shrink past 7 pt."""
    long_line = "Canon PRO-300 " * 12
    got = raster.auto_sheet_text_size_mm([long_line], 120.0, "Inter", False,
                                         False, 300)
    assert got == pytest.approx(tef.pt_to_mm(tef.AUTO_SHRINK_FLOOR_PT))
    mid = raster.auto_sheet_text_size_mm(["Canon PRO-300 on Photo Rag 308"],
                                         120.0, "Inter", False, False, 300)
    assert tef.pt_to_mm(tef.AUTO_SHRINK_FLOOR_PT) < mid <= \
        tef.pt_to_mm(tef.AUTO_SIZE_CEILING_PT)


def test_the_engine_reserves_the_band_the_resolved_size_needs():
    """Otherwise the ceiling draws the block over the patches.

    MUTATION: reserve `SHEET_TEXT_LINE_MM * nlines` again and this goes red.
    """
    r = LayoutRecipe()
    r.instrument, r.paper, r.dpi = "i1", "A4", 300
    r.use_instrument_margins = False
    r.margin_top = r.margin_bottom = r.margin_left = r.margin_right = 12.0
    r.chart_text = "ChromIQ"
    r.chart_text_size_mm = 0.0
    kw = r.build_kwargs()
    g = instruments.geom_from_build_kwargs(kw)
    anchor = tef.sheet_text_bottom_mm(float(kw.get("text_edge") or 4.0))
    hold = g.bottom_reserve_mm - anchor
    assert hold > tef.SHEET_TEXT_LINE_MM + 0.5, (
        f"the engine holds back {hold:.3f} mm a line while auto resolves to "
        f"{tef.AUTO_SIZE_CEILING_PT} pt, so the block is drawn into the "
        "patches")
    assert hold == pytest.approx(raster.sheet_text_line_mm(
        raster.auto_sheet_text_size_mm(["ChromIQ"], 999.0, "Inter", False,
                                        False, 300),
        "Inter", False, False, 300), abs=0.01)


def test_a_typed_size_still_reserves_the_pitch_and_is_never_shrunk():
    """A typed size is drawn exactly as typed and the WARNING takes the place
    of the shrink, which is the rule everywhere else in this panel. Changing
    the reserve for it would move every chart that has one."""
    r = LayoutRecipe()
    r.instrument, r.paper, r.dpi = "i1", "A4", 300
    r.use_instrument_margins = False
    r.margin_top = r.margin_bottom = r.margin_left = r.margin_right = 12.0
    r.chart_text = "ChromIQ"
    r.chart_text_size_mm = 28.0 * 25.4 / 72.0
    kw = r.build_kwargs()
    g = instruments.geom_from_build_kwargs(kw)
    anchor = tef.sheet_text_bottom_mm(float(kw.get("text_edge") or 4.0))
    assert g.bottom_reserve_mm - anchor == pytest.approx(
        tef.SHEET_TEXT_LINE_MM, abs=1e-6)
