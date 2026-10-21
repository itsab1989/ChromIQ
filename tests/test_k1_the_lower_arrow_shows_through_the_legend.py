"""K1 (Knut, 2026-10-20; reworked as Basti chose, 2026-10-21): the strip-focus
arrow below the last row and the "expected / measured (screen colours
approximate)" chip share one band.

First the chip's nearly solid dark panel hid the arrow; then (7079f3e8f) the
arrow was painted over the chip and covered its words. Basti chose what Knut
asked: the arrow goes UNDER the chip again, the chip's panel is see-through
enough for the arrow to show clearly, and the chip's TEXT stays on top, each
glyph outlined so it reads on paper, on a dark patch and over the arrow.

Real `TiffPreview`, real paint, a real page loaded through `load_tiff`.
"""
from __future__ import annotations

import inspect
import time

import pytest
from PIL import Image
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

TEXT = (244, 242, 239)


def _frame(p):
    deadline = time.monotonic() + 2.0
    while p._refresh_timer.isActive() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    for _ in range(3):
        QApplication.processEvents()
    return p._img_label.grab().toImage()


def _preview(qtbot, tmp_path, page_rgb=(250, 250, 250), patch=None,
             highlight=True):
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    qtbot.addWidget(p)
    p.resize(700, 700)
    tif = tmp_path / "sheet.tif"
    Image.new("RGB", (600, 600), page_rgb).save(tif)
    p.load_tiff([tif])
    # Patches run to page row 560: the chip lands in the lower arrow's band,
    # centred, so the middle strips sit under it.
    strips = [QRect(60 + 80 * c, 40, 70, 520) for c in range(6)]
    pe = QColor(*patch) if patch else QColor("#3050ff")
    pm = QColor(*patch) if patch else QColor("#20c060")
    items = [(QRect(60 + 80 * c, 40 + 65 * r, 70, 60), pe, pm, False)
             for r in range(8) for c in range(6)]
    p.set_patch_overlay(0, items, replace_page=True)
    p.set_no_swipe(False)
    p.set_stripe_rects(strips, "base")
    p.set_bidirectional(True)
    if highlight:
        p.highlight_stripe(3)
    p.show()
    qtbot.waitExposed(p)
    QApplication.processEvents()
    return p, strips


def _near(c, rgb, tol):
    return (abs(c.red() - rgb[0]) <= tol and abs(c.green() - rgb[1]) <= tol
            and abs(c.blue() - rgb[2]) <= tol)


def test_the_lower_arrow_shows_through_the_legend_chip(qtbot, tmp_path):
    p, strips = _preview(qtbot, tmp_path)
    img = _frame(p)
    chip = p._legend_rect
    assert chip is not None, "the legend chip was not placed"
    s, ox, oy = p._paint_geom
    dpr = img.devicePixelRatio() or 1.0
    cx = strips[3].center().x() * s + ox
    assert chip.left() < cx < chip.right(), (
        f"test setup: the highlighted strip should be under the chip ({chip}, x {cx:.0f})")
    acc = p._overlay_accent(p._OVERLAY_ARROW)
    a = p._LEGEND_PANEL_ALPHA / 255.0
    # The arrow seen THROUGH the panel: the accent, darkened by the panel.
    through = tuple(round(v * (1 - a) + 20 * a)
                    for v in (acc.red(), acc.green(), acc.blue()))
    hits = 0
    for yy in range(chip.center().y(), chip.bottom() - 1):
        for xx in range(int(cx) - 3, int(cx) + 4):
            if _near(img.pixelColor(int(xx * dpr), int(yy * dpr)), through, 14):
                hits += 1
    assert hits >= 10, (
        f"only {hits} pixels of the arrow seen through the chip ({through}): "
        "the panel hides it, or the arrow is painted over the chip again")
    # …and none of the arrow's own, undimmed accent: it is UNDER the chip.
    raw = sum(1 for yy in range(chip.top() + 2, chip.bottom() - 1)
              for xx in range(int(cx) - 3, int(cx) + 4)
              if _near(img.pixelColor(int(xx * dpr), int(yy * dpr)),
                       (acc.red(), acc.green(), acc.blue()), 6))
    assert raw == 0, f"{raw} undimmed arrow pixels inside the chip: it is on top"


@pytest.mark.parametrize("page,patch", [((250, 250, 250), None),
                                        ((12, 12, 12), (12, 12, 12))],
                         ids=["white-paper", "dark-patches"])
def test_the_chip_text_stays_on_top_and_readable(qtbot, tmp_path, page, patch):
    p, _ = _preview(qtbot, tmp_path, page_rgb=page, patch=patch)
    img = _frame(p)
    chip = p._legend_rect
    dpr = img.devicePixelRatio() or 1.0
    light = dark = 0
    for yy in range(chip.top(), chip.bottom()):
        for xx in range(chip.left(), chip.right()):
            c = img.pixelColor(int(xx * dpr), int(yy * dpr))
            if _near(c, TEXT, 12):
                light += 1
            elif max(c.red(), c.green(), c.blue()) < 50:
                dark += 1
    assert light > 60, f"only {light} text-coloured pixels: the words are not on top"
    assert dark > 60, f"only {dark} outline pixels: the text has no dark edge"


def test_the_panel_is_see_through_and_the_order_is_arrow_then_chip():
    from ui.tiff_preview import TiffPreview
    assert TiffPreview._LEGEND_PANEL_ALPHA <= 100, (
        "Basti, 2026-10-21: the chip's panel is much more translucent")
    src = inspect.getsource(TiffPreview._repaint_label)
    assert "legend=False" in src
    assert (src.index("self._draw_cq_overlay(") < src.index("self._fill_scan_arrow(")
            < src.index("self._paint_legend_chip(")), (
        "overlay, then the scan arrows, then the legend chip on top")
