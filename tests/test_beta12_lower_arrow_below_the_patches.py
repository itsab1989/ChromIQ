"""Beta 12, Basti #182 6001610646 item 1: the lower of the two reading-
direction arrows in the Measure overlay sits BELOW the patches.

It was hung from the sheet's bottom edge (20 px up from 5 px above it), and on
his Pharmacist A3 Plus chart its tip covered the bottom row of patches. Now
its tip sits just under the lowest strip, in the bottom margin, where it may
cover the chart's help markers (he does not mind: those matter on the paper).
With too little paper under the patches it keeps the old place.
"""
from __future__ import annotations

import time

import pytest
from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QApplication

PAGE_RGB = (140, 140, 140)


def _preview(qtbot, tmp_path):
    from PIL import Image
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    qtbot.addWidget(p)
    tif = tmp_path / "page.tif"
    Image.new("RGB", (600, 600), PAGE_RGB).save(tif)
    p.resize(460, 460)
    p.load_tiff([tif])
    p.show()
    qtbot.waitExposed(p)
    QApplication.processEvents()
    return p


def _frame(p):
    deadline = time.monotonic() + 2.0
    while p._refresh_timer.isActive() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    for _ in range(3):
        QApplication.processEvents()
    return p._img_label.grab().toImage()


def _lower_arrow_rows(p, bottom):
    """The image rows (page pixels) the lower arrow was painted on."""
    p.set_no_swipe(False)
    p.set_stripe_rects([QRect(120, 100, 90, bottom - 100),
                        QRect(240, 100, 90, bottom - 100)], "base")
    p.highlight_stripe(0)
    p.set_bidirectional(False)
    before = _frame(p)
    p.set_bidirectional(True)
    after = _frame(p)
    s, _ox, oy = p._paint_geom
    sy = p._paint_scale_y or s
    dpr = after.devicePixelRatio() or 1.0
    rows = set()
    for y in range(after.height()):
        for x in range(after.width()):
            if before.pixelColor(x, y) != after.pixelColor(x, y):
                rows.add((y / dpr - oy) / sy)
    return rows


def test_the_lower_arrow_is_drawn_under_the_lowest_patch(qtbot, tmp_path):
    p = _preview(qtbot, tmp_path)
    rows = _lower_arrow_rows(p, 460)
    assert rows, "the lower arrow drew nothing"
    assert min(rows) > 460, f"the arrow reaches up to page row {min(rows):.0f}"
    assert max(rows) < 500, "the arrow should hang just under the patches"


def test_a_narrow_bottom_margin_like_bastis_chart(qtbot, tmp_path):
    """25 page px under the patches: the old arrow (from the sheet edge up,
    20 logical px) reached about 7 px into the last row; now it is shortened
    to fit under it."""
    p = _preview(qtbot, tmp_path)
    rows = _lower_arrow_rows(p, 575)
    assert rows and min(rows) > 575, f"covers page row {min(rows):.0f}"
    assert max(rows) < 600


def test_with_no_paper_under_the_patches_it_keeps_the_old_place(qtbot, tmp_path):
    p = _preview(qtbot, tmp_path)
    rows = _lower_arrow_rows(p, 598)
    assert rows and max(rows) < 600


def test_the_span_shortens_to_the_margin_and_counts_the_edge_spacer(qtbot, tmp_path):
    p = _preview(qtbot, tmp_path)
    p.set_stripe_rects([QRect(0, 0, 10, 100)], "base")
    tip, base = p._bottom_arrow_span(1.0, 0.0, 200.0, 20)
    assert (tip, base) == (103.0, 123.0)
    tip, base = p._bottom_arrow_span(1.0, 0.0, 115.0, 20)
    assert tip == 103.0 and base == 114.0             # shortened to the margin
    tip, base = p._bottom_arrow_span(1.0, 0.0, 108.0, 20)
    assert (tip, base) == (83.0, 103.0)               # too little: old place
    p._edge_spacer_px = 12
    tip, _base = p._bottom_arrow_span(1.0, 0.0, 200.0, 20)
    assert tip == 115.0


@pytest.fixture
def qapp():
    return QApplication.instance()
