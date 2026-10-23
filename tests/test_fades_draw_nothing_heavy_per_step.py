"""The pause note's and the legend chip's fades stay smooth (Basti,
2026-10-23: "the fade in and out of the overlay sometimes does not look
smooth").

Measured on screen with the replay instrument (agent20/fade_timing_before):
drawing the pause note took 140 to 170 ms, and its opacity fade repaints it
on every step, so a 110 ms fade got one or two frames 150 ms apart. The chip's
fade step cost 11 ms of a 16 ms frame: its halo text stroked again (6 ms) and
the whole page scaled again with smooth filtering. These tests hold the
fixes: the note is drawn once into a picture and copied, the chip's text is a
picture drawn once, and the page is scaled once per size.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui import see_through  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _canvas(dpr):
    pix = QPixmap(int(300 * dpr), int(60 * dpr))
    pix.setDevicePixelRatio(dpr)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    for i in range(10):     # stripes of patches under the text
        p.fillRect(i * 30, 0, 30, 60, QColor.fromHsv(i * 36, 200, 50 + i * 20))
    p.end()
    return pix


@pytest.mark.parametrize("dpr", [1.0, 2.0])
def test_the_cached_halo_text_is_the_same_pixels_at_full_opacity(app, dpr):
    font = QFont()
    font.setPixelSize(13)
    text = "expected ◤ · measured ◢ fxkß"
    a, b = _canvas(dpr), _canvas(dpr)
    pa = QPainter(a)
    see_through.paint_halo_text(pa, 10, 38, font, text)
    pa.end()
    pb = QPainter(b)
    see_through.paint_halo_text_cached(pb, 10, 38, font, text)
    pb.end()
    ia = a.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    ib = b.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    worst = 0
    for y in range(ia.height()):
        for x in range(0, ia.width(), 1):
            ca, cb = ia.pixelColor(x, y), ib.pixelColor(x, y)
            worst = max(worst, abs(ca.red() - cb.red()), abs(ca.green() - cb.green()),
                        abs(ca.blue() - cb.blue()))
    assert worst <= 3, worst      # rounding of one compositing step, no more


def test_the_cached_text_is_drawn_once(app, monkeypatch):
    calls = []
    real = see_through.paint_halo_text
    monkeypatch.setattr(see_through, "paint_halo_text",
                        lambda *a, **k: (calls.append(1), real(*a, **k)))
    see_through._PICTURES.clear()
    font = QFont()
    font.setPixelSize(13)
    for op in (0.1, 0.4, 0.8, 1.0):
        pix = _canvas(2.0)
        p = QPainter(pix)
        see_through.paint_halo_text_cached(p, 5, 30, font, "fade me", op)
        p.end()
    assert len(calls) == 1


def test_the_pause_note_is_painted_once_and_copied(app, monkeypatch):
    from ui.pause_note import PauseNote
    from PyQt6.QtWidgets import QPushButton
    note = PauseNote()
    a, b = QPushButton("Re-read strip J"), QPushButton("Continue with page 2")
    a.setParent(note)
    b.setParent(note)
    note.set_buttons(a, b)
    note.set_content("Page 1 is done", ["Look over the chart.", "Then continue."],
                     "Found:", ["Nothing looks wrong."])
    note.resize(560, note.height_for_width(560))
    calls = []
    real = see_through.paint_halo_text
    monkeypatch.setattr(see_through, "paint_halo_text",
                        lambda *a, **k: (calls.append(1), real(*a, **k)))
    note.prepare()
    first = len(calls)
    assert first > 0
    for _ in range(5):                       # five fade steps
        note.grab()
    assert len(calls) == first, "a fade step drew the text again"
    # new words, or a new width, draw it again (once)
    note.set_content("Page 2 is done", ["Look again."], "Found:", ["-"])
    note.grab()
    assert len(calls) > first


def test_the_note_is_drawn_before_its_fade_starts():
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "ui/tabs/tab_measure.py"
           ).read_text(encoding="utf-8")
    i = src.index("self._page_pause_box.prepare()")
    j = src.index("self._page_pause_fade.run(self._page_pause_effect.opacity(), 1.0)")
    assert i < j


def test_a_legend_fade_step_does_not_scale_the_page_again(app, monkeypatch):
    from ui.tiff_preview import TiffPreview
    pv = TiffPreview()
    pv.resize(500, 700)
    img = QImage(1200, 1800, QImage.Format.Format_RGB32)
    img.fill(QColor(200, 120, 40))
    pv._pixmap = QPixmap.fromImage(img)
    pv._scaled_key = None
    n = {"scaled": 0}
    real = QPixmap.scaled

    def counting(self_, *a, **k):
        n["scaled"] += 1
        return real(self_, *a, **k)
    monkeypatch.setattr(QPixmap, "scaled", counting)
    first = pv._scaled_page(400, 600, 2.0)
    for v in (0.9, 0.6, 0.3, 0.0):
        assert pv._scaled_page(400, 600, 2.0) is first
    assert n["scaled"] == 1
    # a different size, or a new page, is scaled afresh
    pv._scaled_page(410, 600, 2.0)
    img.fill(QColor(30, 120, 200))           # a page with other pixels
    pv._pixmap = QPixmap.fromImage(img)
    pv._scaled_page(410, 600, 2.0)
    assert n["scaled"] == 3
