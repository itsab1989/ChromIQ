"""The two drawn icons on the Profile-run bar (#130, Knut 2026-07-29).

Knut asked for mockups of a trash can for **Delete** and of something for
**Restore Used Chart**, reviewed four rounds of them, and then asked to *"finish
the images, so we can conclude that issue"* without naming his letters. These
are the two variants recommended in every round:

* **Delete — the minimal can.** No ribs. The bar is already dense, and this is
  the only trash can of the six that stays completely clean at the size the
  button actually uses, in both themes.
* **Restore Used Chart — a sheet of patches inside a counter-clockwise arc**, on
  the undo theme he specified: *"the focus is the rectangle of a sheet with dots
  inside (representing patches on a chart), and then having a counter clock-wise
  arrow in a circular shape… This design builds on the idea of an Undo button
  for the chart."* Of the six placements it is the one where the arc genuinely
  encircles the sheet, which is what makes an undo mark read as an undo mark at
  button size.

Both are drawn rather than shipped as image files, so they take the active tab's
accent colour like every other mark on the bar, and stay crisp at any scale.

Four rules earned the hard way over those rounds, all of them load-bearing here:

1. **Curves are drawn with a pen**, never converted to a stroke outline and
   simplified — an outline that is simplified leaves faint flats on a small
   circle, which Knut spotted immediately.
2. **The arrowhead sits at the END of the stroke**, pointing along the tangent
   there. A head on the start points backwards and makes a counter-clockwise arc
   read as clockwise.
3. **The head is sized in proportion to its arc**, or it reads as a curl.
4. **Where one shape passes in front of another the one behind is clipped**, so
   the gap is a real hole rather than a patch of background colour — it has to
   look right on the dark theme and the light one alike.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

#: Everything is laid out in this box and scaled to whatever the button asks for.
_BOX = 24.0


def _pen(p: QPainter, colour: str, width: float) -> None:
    pen = QPen(QColor(colour))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _everything_but(hole: QPainterPath) -> QPainterPath:
    full = QPainterPath()
    full.addRect(QRectF(-8, -8, 40, 40))
    return full.subtracted(hole)


def _outline(path: QPainterPath, width: float) -> QPainterPath:
    from PyQt6.QtGui import QPainterPathStroker
    st = QPainterPathStroker()
    st.setWidth(width)
    st.setCapStyle(Qt.PenCapStyle.RoundCap)
    st.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return st.createStroke(path)


def _ccw_arrow(rect: QRectF, start: float, span: float):
    """A counter-clockwise arc and the two wings of its head.

    Qt puts the point at angle t at ``(cx + rx cos t, cy - ry sin t)`` with y
    running down the screen, so increasing t travels counter-clockwise to the
    eye. The head goes on the end the stroke stops at, along the tangent there.
    """
    arc = QPainterPath()
    arc.arcMoveTo(rect, start)
    arc.arcTo(rect, start, span)

    theta = math.radians(start + span)
    cx, cy = rect.center().x(), rect.center().y()
    rx, ry = rect.width() / 2.0, rect.height() / 2.0
    tip = QPointF(cx + rx * math.cos(theta), cy - ry * math.sin(theta))
    vx, vy = -math.sin(theta), -math.cos(theta)
    if span < 0:
        vx, vy = -vx, -vy
    size = max(2.4, min(4.0, (rx + ry) / 2.0 * 0.42))
    wings = []
    for turn in (math.radians(155), math.radians(-155)):
        wx = vx * math.cos(turn) - vy * math.sin(turn)
        wy = vx * math.sin(turn) + vy * math.cos(turn)
        wings.append((tip, QPointF(tip.x() + size * wx, tip.y() + size * wy)))
    return arc, wings


def draw_trash_can(p: QPainter, colour: str) -> None:
    """The Delete button's mark: lid, handle and a tapered body, no ribs."""
    _pen(p, colour, 1.9)
    p.drawLine(QPointF(4.2, 7.0), QPointF(19.8, 7.0))
    p.drawLine(QPointF(9.6, 7.0), QPointF(9.6, 4.4))
    p.drawLine(QPointF(9.6, 4.4), QPointF(14.4, 4.4))
    p.drawLine(QPointF(14.4, 4.4), QPointF(14.4, 7.0))
    body = QPainterPath(QPointF(6.6, 7.0))
    body.lineTo(7.6, 20.0)
    body.lineTo(16.4, 20.0)
    body.lineTo(17.4, 7.0)
    p.drawPath(body)


def draw_restore_chart(p: QPainter, colour: str) -> None:
    """The Restore Used Chart mark: a sheet of patches inside a
    counter-clockwise arc, with a clean gap where the arc passes in front."""
    # 3.4 rather than 1.8: the arrowhead's wings reach OUTWARD from the tip,
    # so an arc drawn to the edge of the box puts the head outside it and the
    # button clips it. The test that caught this measures the margin.
    arc, wings = _ccw_arrow(QRectF(3.4, 3.4, 17.2, 17.2), 200, 250)

    hole = _outline(arc, 1.9 + 2.8)
    for a, b in wings:
        line = QPainterPath(a)
        line.lineTo(b)
        hole = hole.united(_outline(line, 1.9 + 2.8))

    p.save()
    p.setClipPath(_everything_but(hole))
    _pen(p, colour, 1.6)
    sheet = QRectF(7.4, 7.4, 9.2, 9.2)
    p.drawRoundedRect(sheet, 1.5, 1.5)
    inner = sheet.adjusted(2.2, 2.2, -2.2, -2.2)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(colour))
    for row in range(3):
        for col in range(3):
            p.drawEllipse(QPointF(inner.left() + col * inner.width() / 2.0,
                                  inner.top() + row * inner.height() / 2.0),
                          0.75, 0.75)
    p.restore()

    _pen(p, colour, 1.9)
    p.drawPath(arc)
    for a, b in wings:
        p.drawLine(a, b)


def _icon(draw, colour: str, size: int) -> QIcon:
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / _BOX, size / _BOX)
    try:
        draw(p, colour)
    finally:
        p.end()
    return QIcon(pm)


def trash_can_icon(colour: str, size: int = 16) -> QIcon:
    """The Delete button's trash can, in *colour*."""
    return _icon(draw_trash_can, colour, size)


def restore_chart_icon(colour: str, size: int = 16) -> QIcon:
    """The Restore Used Chart icon, in *colour*."""
    return _icon(draw_restore_chart, colour, size)
