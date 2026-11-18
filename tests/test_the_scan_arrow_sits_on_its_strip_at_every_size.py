"""The scan arrow is painted over the strip it names, at every preview size.

Basti, 2026-11-18, watching a drive at a very small window: "the arrow
indicators that show the strip to be measured are off". Measured on the
real chart of that drive (21 strips, the layout engine's exact geometry), at
window widths 800, 1000, 1500 and 2400 points, on this branch and on the
released 4.3.45: the arrow's left and right edges land on the strip's
patches within 0.2 px every time. What a very small preview does show is a
strip only 8 to 16 px wide under an arrow of a fixed 20 px height, which
reads as "off" next to the printed column letters. This pins the position,
from the painted pixels (the arrow drawn against the same picture held
back), for the first, a middle and the last strip, top and bottom arrow,
at several preview sizes down to the smallest the window allows.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtGui import QColor, QImage  # noqa: E402

N_STRIPS = 21


def _chart(tmp_path):
    """A white page 2100 x 2970 px with 21 strip columns of grey patches."""
    w, h = 2100, 2970
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(255, 255, 255))
    left, pitch, top = 300, 70, 420
    rects = []
    for k in range(N_STRIPS):
        x = left + k * pitch
        rects.append(QRect(x, top - 100, pitch, 25 * 90 + 100))
        shade = 60 + (k * 7) % 150
        for row in range(25):
            img_rect = QRect(x + 3, top + row * 90, pitch - 6, 84)
            from PyQt6.QtGui import QPainter
            p = QPainter(img)
            p.fillRect(img_rect, QColor(shade, 255 - shade, 128))
            p.end()
    path = tmp_path / "page.tif"
    assert img.save(str(path))
    return path, rects


def _render(pv, qapp):
    pv._update_display()
    for _ in range(5):
        qapp.processEvents()
    return pv._img_label.pixmap().toImage()


@pytest.mark.parametrize("size", [(220, 600), (420, 600), (920, 900),
                                  (1800, 1400)])
@pytest.mark.parametrize("strip", [0, N_STRIPS // 2, N_STRIPS - 1])
def test_the_arrow_is_over_its_strip(qapp, tmp_path, size, strip):
    from ui.tiff_preview import TiffPreview
    path, rects = _chart(tmp_path)
    pv = TiffPreview()
    pv.resize(*size)
    pv.show()
    pv.load_tiff([path])
    for _ in range(10):
        qapp.processEvents()
    pv.set_stripe_rects(rects, "base")
    pv.set_bidirectional(True)
    pv.highlight_stripe(strip)
    pv.set_scan_arrows_held(True)
    without = _render(pv, qapp)
    pv.set_scan_arrows_held(False)
    with_ = _render(pv, qapp)
    assert with_.size() == without.size()
    dpr = pv._img_label.pixmap().devicePixelRatio() or 1.0
    import numpy as np

    def arr(im):
        im = im.convertToFormat(QImage.Format.Format_RGB32)
        b = im.constBits()
        b.setsize(im.sizeInBytes())
        return np.frombuffer(b, np.uint8).reshape(
            im.height(), im.bytesPerLine())[:, :im.width() * 4]
    a, b = arr(with_).astype(int), arr(without).astype(int)
    weight = np.abs(a - b).reshape(a.shape[0], -1, 4)[:, :, :3].sum(axis=2)
    cols = weight.sum(axis=0).astype(float)
    xs = np.nonzero(cols)[0]
    assert xs.size, "no arrow painted"
    s, _ox, _oy = pv._paint_geom
    B = pv._paint_border
    r = rects[strip]
    left, right = (r.x() * s + B) * dpr, ((r.x() + r.width()) * s + B) * dpr
    # pixel centres: column x covers x .. x+1
    centroid = float((cols * (np.arange(cols.size) + 0.5)).sum() / cols.sum())
    # the painted arrows (top and bottom, symmetric triangles) are centred on
    # the strip's column to within half a pixel
    assert abs(centroid - (left + right) / 2) <= 0.5, (
        "the arrow is off its strip", size, strip, centroid, left, right)
    # ...and cover no more than the column and a pixel or two each side
    assert xs.min() >= left - 2.5 and xs.max() <= right + 2.5, (
        size, strip, xs.min(), xs.max(), left, right)
    pv.close()
