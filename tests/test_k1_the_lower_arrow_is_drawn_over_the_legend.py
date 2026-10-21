"""K1 (Knut, 2026-10-20): the strip-focus arrow below the last row went BEHIND
the "expected / measured (screen colours approximate)" chip.

Since beta 12 the lower arrow hangs just under the lowest strip, and the chip
is placed in that same band (below the last patch, or resting on the last row
when the margin is tight). The arrows were painted first and the chip last, so
whenever the highlighted strip was under the chip the arrow vanished into its
dark panel. The arrows are now painted after every overlay, with a thin light
halo so a near-black accent (Neutral) still reads against the chip.

Real `TiffPreview`, real paint, a real page loaded through `load_tiff`.
"""
from __future__ import annotations

import inspect
import time

from PIL import Image
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication


def _frame(p):
    deadline = time.monotonic() + 2.0
    while p._refresh_timer.isActive() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    for _ in range(3):
        QApplication.processEvents()
    return p._img_label.grab().toImage()


def _preview_with_arrow_under_the_chip(qtbot, tmp_path):
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    qtbot.addWidget(p)
    p.resize(700, 700)
    tif = tmp_path / "sheet.tif"
    Image.new("RGB", (600, 600), (250, 250, 250)).save(tif)
    p.load_tiff([tif])
    # Six strips whose patches run to page row 560: the chip lands in the
    # same band as the lower arrow, centred, so the middle strips sit under it.
    strips = [QRect(60 + 80 * c, 40, 70, 520) for c in range(6)]
    items = [(QRect(60 + 80 * c, 40 + 65 * r, 70, 60),
              QColor("#3050ff"), QColor("#20c060"), False)
             for r in range(8) for c in range(6)]
    p.set_patch_overlay(0, items, replace_page=True)
    p.set_no_swipe(False)
    p.set_stripe_rects(strips, "base")
    p.set_bidirectional(True)
    p.highlight_stripe(3)
    p.show()
    qtbot.waitExposed(p)
    QApplication.processEvents()
    return p, strips


def test_the_lower_arrow_shows_inside_the_legend_chip(qtbot, tmp_path):
    p, strips = _preview_with_arrow_under_the_chip(qtbot, tmp_path)
    img = _frame(p)
    chip = p._legend_rect
    assert chip is not None, "the legend chip was not placed"
    s, ox, oy = p._paint_geom
    sy = p._paint_scale_y or s
    dpr = img.devicePixelRatio() or 1.0
    r = strips[3]
    cx = r.center().x() * s + ox
    assert chip.left() < cx < chip.right(), (
        f"test setup: the highlighted strip should be under the chip ({chip}, x {cx:.0f})")
    want = p._overlay_accent(p._OVERLAY_ARROW)

    def accent(c):
        return (abs(c.red() - want.red()) < 12 and abs(c.green() - want.green()) < 12
                and abs(c.blue() - want.blue()) < 12)

    # Rows in the lower half of the chip, a few pixels either side of the
    # arrow's centre line: the chip there is dark, the arrow is the accent.
    hits = 0
    for yy in range(chip.center().y(), chip.bottom() - 1):
        for xx in range(int(cx) - 3, int(cx) + 4):
            if accent(img.pixelColor(int(xx * dpr), int(yy * dpr))):
                hits += 1
    assert hits >= 10, (
        f"only {hits} accent pixels ({want.name()}) inside the chip where the "
        "arrow is: it is painted under the chip again")


def test_the_arrows_are_painted_after_the_overlay():
    from ui.tiff_preview import TiffPreview
    src = inspect.getsource(TiffPreview._repaint_label)
    assert src.index("self._draw_cq_overlay(") < src.index("self._fill_scan_arrow("), (
        "the scan arrows must be painted after the overlay (legend chip)")
