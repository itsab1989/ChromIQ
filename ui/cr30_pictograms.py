"""Pictograms for the CR30's two calibration windows (#159).

The two steps ask for OPPOSITE things — cap ON with the white tile, then cap OFF
pointing at nothing — and the owner's worry was that two similar-looking windows
would have a user do the same thing twice. He chose the "steps pair" cue: each
window shows BOTH steps with the current one marked, so the difference is
visible rather than remembered.

**There is deliberately no black tile anywhere in these drawings.** The CR30 has
none; its dark reference is open air. A drawing of a black tile would send
someone hunting for an object that does not exist, and the nearest dark thing to
hand is the cap's GREEN face — the exact surface that silently corrupted this
unit's white reference during the research. The second step is drawn as the
instrument nose-down over emptiness, which is what actually happens.

Everything is drawn at runtime from the LIVE palette, so one drawing is correct
in light and dark by construction rather than by shipping two sets of art. That
was the trap the owner identified himself: a black swatch on a dark window is
invisible, and it is the dark step where being unmistakable matters most.
Sizes come from the font metrics, so the art follows the system font size.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QFontMetrics, QPainter, QPainterPath, QPen,
                         QPixmap)
from PyQt6.QtWidgets import QWidget

WHITE_STEP = "white"
BLACK_STEP = "black"


def _ink(widget: QWidget | None) -> QColor:
    """The theme's own foreground. Never a hard-coded grey: the whole point is
    that this reads on both grounds."""
    if widget is not None:
        return widget.palette().windowText().color()
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    return (app.palette().windowText().color() if app else QColor(0, 0, 0))


def _draw_instrument(p: QPainter, r: QRectF, ink: QColor, nose_down: bool):
    """A CR30 in outline: a rounded body with the measuring opening marked."""
    pen = QPen(ink, max(1.0, r.width() / 28.0))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    body = QRectF(r.left() + r.width() * 0.22, r.top() + r.height() * 0.06,
                  r.width() * 0.56, r.height() * 0.62)
    p.drawRoundedRect(body, r.width() * 0.10, r.width() * 0.10)
    # the aperture, on the end that faces the surface
    ap = QRectF(0, 0, r.width() * 0.20, r.width() * 0.20)
    ap.moveCenter(QPointF(body.center().x(),
                          body.bottom() if nose_down else body.top()))
    p.drawEllipse(ap)


def _draw_cap(p: QPainter, r: QRectF, ink: QColor, face_white: bool):
    """The magnetic cap, showing WHICH FACE meets the opening — the one spatial
    hazard the window exists to prevent."""
    pen = QPen(ink, max(1.0, r.width() / 28.0))
    p.setPen(pen)
    tile = QRectF(r.left() + r.width() * 0.28, r.top() + r.height() * 0.70,
                  r.width() * 0.44, r.height() * 0.20)
    if face_white:
        # An outlined, unfilled disc reads as "white" on BOTH grounds; a filled
        # white one disappears on a light window.
        p.setBrush(Qt.BrushStyle.NoBrush)
    else:
        hatch = QColor(ink)
        hatch.setAlpha(90)
        p.setBrush(hatch)
    p.drawRoundedRect(tile, r.width() * 0.04, r.width() * 0.04)


def _draw_cross(p: QPainter, r: QRectF, ink: QColor):
    pen = QPen(ink, max(1.5, r.width() / 20.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(r.topLeft(), r.bottomRight())
    p.drawLine(r.topRight(), r.bottomLeft())


def _draw_tick(p: QPainter, r: QRectF, ink: QColor):
    pen = QPen(ink, max(1.5, r.width() / 20.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    path = QPainterPath(QPointF(r.left(), r.center().y()))
    path.lineTo(r.left() + r.width() * 0.36, r.bottom())
    path.lineTo(r.right(), r.top())
    p.drawPath(path)


def _draw_nothing(p: QPainter, r: QRectF, ink: QColor):
    """Emptiness under the instrument: a dashed floor line, well below it."""
    faint = QColor(ink)
    faint.setAlpha(110)
    pen = QPen(faint, max(1.0, r.width() / 40.0), Qt.PenStyle.DashLine)
    p.setPen(pen)
    y = r.bottom() - r.height() * 0.04
    p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))


def steps_pair(step: str, widget: QWidget | None = None,
               height: int | None = None) -> QPixmap:
    """Both calibration steps side by side, with `step` marked as the current
    one. The same picture in both windows, so the pair is the thing the user
    reads and the difference cannot be missed."""
    from PyQt6.QtWidgets import QApplication
    fm = QFontMetrics(widget.font() if widget is not None
                      else QApplication.instance().font())
    h = height or fm.height() * 6
    w = int(h * 1.9)
    dpr = (widget.devicePixelRatioF() if widget is not None else 1.0) or 1.0
    pm = QPixmap(int(w * dpr), int(h * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)

    ink = _ink(widget)
    dim = QColor(ink)
    dim.setAlpha(70)                       # the step that is NOT current

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    half = QRectF(0, 0, w / 2.0, h)
    left = QRectF(half)
    right = QRectF(half).translated(w / 2.0, 0)

    # --- step 1: cap on, white face --------------------------------------
    c = ink if step == WHITE_STEP else dim
    box = QRectF(left.left() + left.width() * 0.10, left.top() + h * 0.06,
                 left.width() * 0.80, h * 0.80)
    _draw_instrument(p, box, c, nose_down=True)
    _draw_cap(p, box, c, face_white=True)
    t = QRectF(0, 0, h * 0.16, h * 0.16)
    t.moveCenter(QPointF(box.right() - box.width() * 0.06, box.bottom()))
    _draw_tick(p, t, c)

    # --- step 2: cap off, pointing at nothing -----------------------------
    c = ink if step == BLACK_STEP else dim
    box = QRectF(right.left() + right.width() * 0.10, right.top() + h * 0.06,
                 right.width() * 0.80, h * 0.80)
    _draw_instrument(p, box, c, nose_down=True)
    _draw_nothing(p, box, c)

    # the current step gets an underline; the other is simply fainter
    cur = left if step == WHITE_STEP else right
    pen = QPen(ink, max(2.0, h / 40.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    y = h - max(2.0, h / 40.0)
    p.drawLine(QPointF(cur.left() + cur.width() * 0.18, y),
               QPointF(cur.right() - cur.width() * 0.18, y))
    p.end()
    return pm
