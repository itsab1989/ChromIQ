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

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import (QColor, QIcon, QPainter, QPainterPath, QPalette, QPen,
                         QPixmap)
from PyQt6.QtWidgets import QToolButton, QWidget  # noqa: F401 (QWidget: typing)

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


def _pixmap(draw, colour: str, size: int) -> QPixmap:
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
    return pm


# ---------------------------------------------------------------------------
# The buttons themselves (#130, Knut 2026-07-29)
# ---------------------------------------------------------------------------

class BarIconButton(QToolButton):
    """A Profile-run bar action shown as its mark alone — the mark IS the
    button.

    Knut, #130 2026-07-29: *"The icons REPLACE the previous buttons totally,
    similar to the 'load profile' icon in Create Chart tab or 'load ti2' icon in
    Print Chart tabs… so that clicking the icon functions as a button… The new
    icons should have the same hight as the height of the previous buttons."*

    So this is deliberately the same kind of widget as those load buttons — a
    flat ``#tooltip_btn`` QToolButton with nothing but the drawn mark on it — and
    it is sized to :data:`HEIGHT`, which is the height the text buttons had.

    Everything the old ``QPushButton`` answered to still works unchanged:
    ``setEnabled``, ``setVisible``, ``setToolTip``, ``text()`` and ``clicked``.
    Two details are handled here rather than left to Qt:

    * **Greying.** A coloured pixmap is not dimmed convincingly by Qt's own
      disabled rendering, so the disabled look is drawn explicitly in the
      palette's disabled text colour — a real grey in both themes.
    * **The pointer.** A pointing hand over a greyed button promises something
      that will not happen, so the cursor follows the enabled state.

    The label text is kept on the widget (invisible, ``ToolButtonIconOnly``) so
    the button still has a name for assistive technology and for anything that
    asks what it is.
    """

    #: Matches the height the "Restore Used Chart" / "Delete" text buttons had,
    #: which is what Knut asked the icons to keep. Width follows, so the mark
    #: sits in a square hit target rather than a slot.
    HEIGHT = 26
    #: The mark itself, inside that box. Bigger than the 16 px it was beside a
    #: label, because the mark now has to carry the button on its own.
    ICON = 18

    def __init__(self, draw, colour: str, text: str,
                 parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self._draw = draw
        self._colour = colour
        self.setObjectName("tooltip_btn")
        self.setText(text)
        self.setAccessibleName(text)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setFixedSize(QSize(self.HEIGHT, self.HEIGHT))
        self.setIconSize(QSize(self.ICON, self.ICON))
        # Icon-only and mouse-operated: never take keyboard focus, so the space
        # bar can't fire a destructive action just because a tab handed this
        # button the initial focus — the same rule the load buttons follow.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._apply_icon()
        self._apply_cursor()

    # ---- appearance -------------------------------------------------------
    def set_accent(self, colour: str) -> None:
        """Follow the active tab's accent colour, like everything else on the
        bar."""
        self._colour = colour
        self._apply_icon()

    #: The greys the app already uses for disabled button text — dark theme, then
    #: light. Taken from ``QPushButton:disabled`` in ``ui/styles.py`` and
    #: ``LM_TEXT_FAINT`` in ``ui/light_styles.py``, so a greyed mark greys exactly
    #: like a greyed label; a test fails if either stylesheet moves away from them.
    GREY_ON_DARK = "#505050"
    GREY_ON_LIGHT = "#a8a4a0"

    def _disabled_colour(self) -> str:
        """The app's own disabled grey for whichever theme is on screen.

        Deliberately NOT ``palette(Disabled, ButtonText)``: the light theme sets
        that role, but the dark theme leaves it at near-white — so a mark drawn in
        it came out *brighter* than the enabled mark beside it, which is the
        opposite of greyed. The theme is read from the live palette's text colour
        rather than from the settings, because that is what has just changed when
        this is asked during a theme switch.
        """
        fg = self.palette().color(QPalette.ColorRole.WindowText)
        on_dark = fg.lightness() > 127        # light text ⇒ dark background
        return self.GREY_ON_DARK if on_dark else self.GREY_ON_LIGHT

    def _apply_icon(self) -> None:
        icon = QIcon(_pixmap(self._draw, self._colour, self.ICON))
        icon.addPixmap(_pixmap(self._draw, self._disabled_colour(), self.ICON),
                       QIcon.Mode.Disabled)
        self.setIcon(icon)

    def _apply_cursor(self) -> None:
        self.setCursor(Qt.CursorShape.PointingHandCursor if self.isEnabled()
                       else Qt.CursorShape.ArrowCursor)

    def changeEvent(self, event) -> None:      # noqa: N802
        super().changeEvent(event)
        kind = event.type()
        if kind == QEvent.Type.EnabledChange:
            self._apply_cursor()
        elif kind in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            # The theme switched under us, so the grey has to be re-derived.
            self._apply_icon()


def restore_chart_button(colour: str, text: str,
                         parent: "QWidget | None" = None) -> BarIconButton:
    """The Restore Used Chart button: its mark alone."""
    return BarIconButton(draw_restore_chart, colour, text, parent)


def delete_button(colour: str, text: str,
                  parent: "QWidget | None" = None) -> BarIconButton:
    """The Delete button: its mark alone."""
    return BarIconButton(draw_trash_can, colour, text, parent)
