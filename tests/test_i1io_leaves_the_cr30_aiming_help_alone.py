"""THE CR30's AIMING HELP IS UNCHANGED BY THE i1iO BETA.

The i1iO's later alignment overlay is designed on the CR30's aiming help
(the owner, 2026-11-13; the design note's "Alignment windows (later)"), and
the i1iO turns every preview of its own charts a quarter turn. Neither may
touch the CR30: its chart is never turned, and its body circle and patch
ring are drawn pixel for pixel as they are with the i1iO Beta off.
"""
from __future__ import annotations

import os

import pytest
from PyQt6.QtCore import QRect

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def cr30_chart(tmp_path_factory):
    from test_i1io_aiming_crosses import _ti1
    from workflow.layout_engine import chart
    folder = tmp_path_factory.mktemp("cr30")
    ti1 = _ti1(folder / "c.ti1", 60)
    chart.build_chart(ti1, folder / "c", instrument="CR30", paper="A4",
                      dpi=100, seed=11)
    pages = sorted(folder.glob("c*.tif"))
    assert pages
    return pages


def _render(qtbot, pages, aim=True):
    from PyQt6.QtWidgets import QApplication
    from ui.tiff_preview import TiffPreview
    from workflow.layout_engine.instruments import (
        CR30_APERTURE_DIAMETER_MM, CR30_BODY_DIAMETER_MM)
    p = TiffPreview()
    qtbot.addWidget(p)
    p.resize(700, 900)
    p.load_tiff(pages)
    per_mm = 100 / 25.4
    p._active_patch_box = QRect(200, 300, round(10 * per_mm),
                                round(10 * per_mm))
    p._active_patch_page = 0
    p._current = 0
    p.set_aim_overlay(aim, CR30_APERTURE_DIAMETER_MM * per_mm,
                      CR30_BODY_DIAMETER_MM * per_mm)
    p.show()
    qtbot.waitExposed(p)
    QApplication.processEvents()
    return p.view_rotation(), p.grab().toImage()


def test_the_cr30_preview_is_never_turned_and_draws_as_before(qtbot,
                                                              cr30_chart):
    from workflow.i1io import support
    before = support._latched
    try:
        support.set_enabled_for_this_process(True)
        assert support.display_rotation_for(cr30_chart) == 0
        on_angle, on_image = _render(qtbot, cr30_chart)
        support.set_enabled_for_this_process(False)
        off_angle, off_image = _render(qtbot, cr30_chart)
    finally:
        support._latched = before
    assert on_angle == off_angle == 0
    assert on_image.size() == off_image.size()
    assert on_image == off_image
    # …and the comparison is not of two empty pictures: the help is drawn
    _a, bare = _render(qtbot, cr30_chart, aim=False)
    assert bare != on_image
