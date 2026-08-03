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


def _pixmap(draw, colour: str, size: int, nudge: "tuple[float, float]" = (0.0, 0.0),
            canvas: "int | None" = None,
            stretch_y: float = 1.0, ink_top: float = 0.0) -> QPixmap:
    """The mark at *size*, drawn on a *canvas*-wide pixmap and offset by *nudge*.

    **The canvas is deliberately bigger than the mark.** Drawn edge to edge, a
    nudged mark loses whatever crosses the boundary — and it did: at right 6 the
    duplicate mark had lost five pixels of its width before anyone noticed,
    which is the same fault Basti spotted on the ⓘ (#130, 2026-08-03). Giving
    the pixmap the button's full width leaves about 6 px of slack on each side,
    which is enough for every offset the bar uses, and Qt centres the larger
    icon in the same button so nothing else moves.
    """
    canvas = canvas or size
    pm = QPixmap(canvas * 2, canvas * 2)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Centre the mark's own box on the canvas, then move it by the nudge.
    p.translate((canvas - size) / 2 + nudge[0], (canvas - size) / 2 + nudge[1])
    # *stretch_y* makes the mark taller. It is anchored on the ink's TOP — that
    # is where *ink_top* comes in, measured from the mark box's origin — so the
    # extra height appears at the BOTTOM and the mark does not appear to drift
    # upward (#130, Basti 2026-08-03: "increase the height of the delete icon
    # by 1 px adding it to the bottom").
    if stretch_y != 1.0:
        p.translate(0.0, ink_top * (1.0 - stretch_y))
        p.scale(1.0, stretch_y)
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

    #: Knut, #130 2026-07-29 on beta.103: *"The two new buttons are too small.
    #: The symbols currently can fit inside the diameter of the circle for the
    #: info icon image… the height of the visible part of the icon must be
    #: increased by maybe 50%, even if that makes them a little taller than the
    #: input boxes for profile run and run type. The buttons should be clearly
    #: bigger and more prominent than the info icons."*
    #:
    #: So the square is no longer tied to the 26 px row: it is as tall as the
    #: mark needs. A mark occupies roughly two thirds of its 24-unit box, so
    #: 27 px of icon draws about 18 px of ink — half again the 12 px it drew at
    #: 18 px, and comfortably more than the ⓘ beside it.
    HEIGHT = 34
    #: The mark itself, inside that box.
    ICON = 27

    #: An OPTICAL nudge for this mark, in device-independent pixels, applied to
    #: the glyph inside its box.
    #:
    #: These are not a geometry fix. Measured, all three marks occupy rows 6-25
    #: of their 32 px button with their centre on 15.5 — pixel-identical, and a
    #: future reader who checks will find them perfectly aligned and be tempted
    #: to take these out again. Please do not: the marks are aligned, and they
    #: still did not LOOK aligned, because their weight is not evenly spread.
    #: Basti judged the row by eye across four rendered variants (#130,
    #: 2026-08-03) and chose these values.
    NUDGE = (0.0, 0.0)

    #: A vertical stretch for this mark, anchored on the top of its ink so the
    #: extra height lands at the bottom. 1.0 leaves it alone.
    STRETCH_Y = 1.0
    #: Where this mark's ink starts, in device-independent pixels from the top
    #: of its ICON box — the anchor :data:`STRETCH_Y` scales about. Only needed
    #: by a mark that is stretched.
    INK_TOP = 0.0

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
        # The icon is canvas-sized; the MARK inside it is still ICON.
        self.setIconSize(QSize(self.HEIGHT, self.HEIGHT))
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
        icon = QIcon(_pixmap(self._draw, self._colour, self.ICON, self.NUDGE,
                             self.HEIGHT, self.STRETCH_Y, self.INK_TOP))
        icon.addPixmap(_pixmap(self._draw, self._disabled_colour(), self.ICON,
                               self.NUDGE, self.HEIGHT, self.STRETCH_Y,
                               self.INK_TOP),
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


def draw_duplicate_run(p: QPainter, colour: str) -> None:
    """The Duplicate mark: a chart page with a folded corner and a plus.

    Variant **2c**, chosen by Knut and Sebastian (#130, 2026-08-01: *"Sebastian
    and I agree on image 2c new now. Use that."*). It says *duplicate a chart*
    rather than *copy a file*, which is what the button actually does.

    Two details are the result of his review and are easy to undo by accident:

    * **The patch block is placed, not centred.** The fold takes a bite out of
      the top-right, so the page's optical centre is not its geometric one —
      centring the four patches mathematically moved them visibly off.
    * **The gap where the page edges meet the plus is measured between the
      geometric endpoints, and allows for the round caps.** A round cap extends
      half a stroke width past the point the line is drawn to, so both the plus
      tip and the page edge overshoot by half a width each. The 1.5 × width
      here is two caps plus the half-width gap Knut asked to see.
    """
    w = 1.9                       # stroke width, as the other bar marks
    # Page outline, open at the bottom-right where the plus sits, with the
    # folded corner drawn as its own two strokes.
    _pen(p, colour, w)
    body = QPainterPath(QPointF(3.0, 17.5))
    body.lineTo(3.0, 2.5)
    body.lineTo(12.4, 2.5)
    body.lineTo(16.0, 6.1)
    body.lineTo(16.0, 11.45)      # stops clear of the plus's upper tip
    p.drawPath(body)

    bottom = QPainterPath(QPointF(3.0, 17.5))
    bottom.lineTo(10.45, 17.5)    # stops clear of the plus's left tip
    p.drawPath(bottom)

    fold = QPainterPath(QPointF(12.4, 2.5))
    fold.lineTo(12.4, 6.1)
    fold.lineTo(16.0, 6.1)
    p.drawPath(fold)

    # The four patches — the chart's own language.
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(colour))
    for x in (6.0, 10.4):
        for y in (7.0, 11.4):
            p.drawRoundedRect(QRectF(x, y, 3.1, 3.1), 0.7, 0.7)

    # The plus: a new one of these.
    _pen(p, colour, w)
    p.drawLine(QPointF(16.5, 14.3), QPointF(16.5, 20.7))
    p.drawLine(QPointF(13.3, 17.5), QPointF(19.7, 17.5))


def restore_chart_button(colour: str, text: str,
                         parent: "QWidget | None" = None) -> BarIconButton:
    """The Restore Used Chart button: its mark alone."""
    return _RestoreButton(draw_restore_chart, colour, text, parent)


class _RestoreButton(BarIconButton):
    #: Right 3 (#130, Basti 2026-08-03, in two passes: right 1, then a further
    #: right 2). The arrow tail sweeps left and the head sits high-right, so the
    #: mark's weight is left of its box centre and it sat further from its own ⓘ
    #: than the other two.
    #:
    #: The second pass was asked for as "move the ⓘ 2 px left". It is done from
    #: the mark's side because moving the ⓘ CLIPPED it: that circle fills all but
    #: about 7 % of its pixmap, while a mark uses roughly two thirds of its box
    #: and has room to move. The gap closes by the same amount either way.
    NUDGE = (4.0, 0.0)


class _DuplicateButton(BarIconButton):
    #: Right 4, down 1 (#130, Basti 2026-08-03, in two passes: right 2 / down 1,
    #: then a further right 2 once he saw the whole row). The mark carries its
    #: weight low and left — the "+" hangs off the bottom-right of a page that
    #: sits left in its box.
    NUDGE = (7.0, 1.0)


class _DeleteButton(BarIconButton):
    #: Right 3, up 2 (#130, Basti 2026-08-03, in two passes: right 1 / up 2, then
    #: a further right 2). The lid is a solid horizontal stroke across the top,
    #: which makes the bin read as sitting low.
    NUDGE = (4.0, -2.0)
    #: One device-independent pixel taller, added at the bottom (#130, Basti
    #: 2026-08-03). Its ink is 20.5 px tall, so the factor is 21.5/20.5.
    STRETCH_Y = 21.5 / 20.5
    #: Measured: the bin's ink starts 3.5 px below its box origin at ICON = 27.
    #: (Canvas origin 5.0, box origin (34-27)/2 + NUDGE_y = 1.5.)
    INK_TOP = 3.5


def duplicate_run_button(colour: str, text: str,
                         parent: "QWidget | None" = None) -> BarIconButton:
    """The Duplicate button: its mark alone."""
    return _DuplicateButton(draw_duplicate_run, colour, text, parent)


def delete_button(colour: str, text: str,
                  parent: "QWidget | None" = None) -> BarIconButton:
    """The Delete button: its mark alone."""
    return _DeleteButton(draw_trash_can, colour, text, parent)
