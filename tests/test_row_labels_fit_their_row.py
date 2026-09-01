"""The row labels: never taller than their row, never past Knut's floor.

Neither half of that had a test. A second challenge round reverted each in turn
and 261 tests across the eleven layout files stayed green, so the next refactor
would have removed them in silence.
"""
from __future__ import annotations

import pytest

from workflow.layout_engine import instruments, presets
from workflow.layout_engine.raster import (ROW_LABEL_PITCH_FRAC,
                                           apply_row_label_geometry,
                                           effective_indicator_size_mm,
                                           effective_row_label_size_mm)

FONT = "DejaVuSans"


def _tall_grid(instrument="CR30", paper="A3", cols=20, rows=105):
    """A grid whose rows are much shorter than a strip label wants to be."""
    r = presets.default_recipe(instrument, paper)
    r.layout_mode = "area_first"
    r.area_method = "by_grid"
    r.area_cols, r.area_rows, r.area_ratio = cols, rows, 1.0
    r.show_row_indicators = True
    r.indicator_size_mm = 0.0
    kw = r.build_kwargs()
    return instruments.geom_from_build_kwargs(kw), kw


def test_an_automatic_row_label_is_never_taller_than_its_row():
    geom, _kw = _tall_grid()
    pitch = geom.plen + geom.pspa
    strip = effective_indicator_size_mm(geom, 600, FONT, 0.0)
    row = effective_row_label_size_mm(geom, 600, FONT, 0.0)

    assert strip > pitch, (
        "the premise failed: this grid no longer asks for a label taller than "
        "its own row, so the test proves nothing")
    assert row <= pitch * ROW_LABEL_PITCH_FRAC + 1e-9, (
        f"the row labels are {row:.3f} mm on a {pitch:.3f} mm row; they print "
        "over each other")


def test_the_strip_letters_are_not_capped_with_them():
    """The cap is for labels beside a row, not above a strip."""
    geom, _kw = _tall_grid()
    before = effective_indicator_size_mm(geom, 600, FONT, 0.0)
    assert before == effective_indicator_size_mm(geom, 600, FONT, 0.0)
    assert effective_row_label_size_mm(geom, 600, FONT, 0.0) < before


def test_a_size_the_user_typed_is_left_alone():
    """Capping a number somebody chose would be the app arguing with them."""
    geom, _kw = _tall_grid()
    assert effective_row_label_size_mm(geom, 600, FONT, 9.0) == 9.0


def test_the_geometry_carries_the_floor_the_renderer_clamps_at():
    """§R1.3. The band's docstring promised the renderer would clamp at the
    same floor it measures from; the renderer clamped at the PAGE EDGE, so a
    three-digit row number printed 1.4 mm from the paper against a 4 mm rule.
    """
    geom, kw = _tall_grid()
    out = apply_row_label_geometry(geom, kw)
    floor = float(getattr(out, "row_label_floor", 0.0) or 0.0)
    assert floor > 0.0, (
        "the geometry carries no row-label floor, so the renderer has nothing "
        "to clamp at but the page edge")
    assert floor >= float(kw.get("text_edge_clip") or 0.0) - 1e-9


@pytest.mark.parametrize("instrument,paper", [("SS", "A4"), ("CR30", "A3")])
def test_the_cap_holds_on_the_grids_it_was_found_on(instrument, paper):
    geom, _kw = _tall_grid(instrument, paper, 20, 110 if paper == "A4" else 105)
    pitch = geom.plen + geom.pspa
    assert effective_row_label_size_mm(geom, 600, FONT, 0.0) <= pitch
