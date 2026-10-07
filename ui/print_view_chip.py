"""The chart preview's indicator, as a small switch (beta 12, Basti 2026-10-08).

Beta 12 shows a run's chart page as it will print and says so in a label in
the preview's top right corner (M-PREVIEW-AS-PRINTED). Basti asked for that
label to become the switch between the two views, and for it to stay small:

* **collapsed it is only an icon**: a paper sheet with a folded corner while
  the preview shows the page as on paper, a small screen while it shows the
  device values;
* **on hover it slides open** to a short line ("As on paper", and what a click
  does), and closes again when the pointer leaves. The full explanation stays
  in the tooltip. Opening and closing animate the width, fast but smooth,
  growing to the LEFT so the icon under the pointer never moves; the chip
  floats over the image, so nothing in the preview's layout moves with it;
* a click, Space or Enter asks for the other view; when there is no other view
  (no profile yet, calibrated pages, a conversion that failed) a click does
  nothing and the tooltip says so;
* it takes keyboard focus (Tab), shows a focus ring, and opens while it has
  keyboard focus, so the keyboard sees what the pointer sees.

There is no universal soft-proof symbol, so both icons are drawn here, as the
Profile-run bar's are (`ui/bar_icons.py`): vector, with a pen, crisp at any
scale and in the chip's own ink in every appearance.
"""
from __future__ import annotations

import sys

from PyQt6.QtCore import (QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt,
                          pyqtProperty, pyqtSignal)
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QAbstractButton, QWidget

#: The two icons.
ICON_PAPER = "paper"
ICON_SCREEN = "screen"

#: The pill's height, and the room left around it for the focus ring.
PILL_H = 22
RING = 3
#: How long opening or closing takes, unless the system asks for less motion.
ANIM_MS = 170


#: (monotonic time asked, answer): the system is asked again after
#: _MOTION_TTL_S, so turning "Reduce motion" on while ChromIQ runs takes
#: effect at the next hover instead of at the next launch (review C).
_motion_asked: "tuple[float, bool] | None" = None
_MOTION_TTL_S = 5.0


def reduce_motion() -> bool:
    """True when the system asks for less motion (macOS "Reduce motion",
    Windows "Show animations in Windows" off). Qt does not expose it, so it is
    asked of the system, at most every few seconds; anything else, or any
    failure, answers False."""
    global _motion_asked
    import time
    now = time.monotonic()
    if _motion_asked is not None and now - _motion_asked[0] < _MOTION_TTL_S:
        return _motion_asked[1]
    answer = _ask_reduce_motion()
    _motion_asked = (now, answer)
    return answer


def _ask_reduce_motion() -> bool:
    try:
        if sys.platform == "darwin":
            from AppKit import NSWorkspace  # type: ignore[import-not-found]
            return bool(NSWorkspace.sharedWorkspace()
                        .accessibilityDisplayShouldReduceMotion())
        if sys.platform == "win32":
            import ctypes
            on = ctypes.c_int(1)
            spi_getclientareaanimation = 0x1042
            if ctypes.windll.user32.SystemParametersInfoW(   # type: ignore[attr-defined]
                    spi_getclientareaanimation, 0, ctypes.byref(on), 0):
                return not bool(on.value)
    except Exception:      # noqa: BLE001 — a preference, never worth a crash
        pass
    return False


def draw_icon(p: QPainter, kind: str, rect: QRectF, colour: QColor) -> None:
    """Draw *kind* (ICON_PAPER / ICON_SCREEN) into *rect*, in *colour*.

    Laid out on a 24-unit box like `ui/bar_icons.py`, drawn with a round pen
    so curves and corners stay clean at 1x and 2x."""
    p.save()
    p.translate(rect.x(), rect.y())
    s = min(rect.width(), rect.height()) / 24.0
    p.scale(s, s)
    pen = QPen(colour)
    # about 1.3 device-independent pixels at the chip's 14 px icon
    pen.setWidthF(1.3 / s)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    if kind == ICON_PAPER:
        # a sheet with its top right corner folded over
        sheet = QPainterPath()
        sheet.moveTo(5.5, 2.5)
        sheet.lineTo(14.0, 2.5)
        sheet.lineTo(18.5, 7.0)
        sheet.lineTo(18.5, 21.5)
        sheet.lineTo(5.5, 21.5)
        sheet.closeSubpath()
        p.drawPath(sheet)
        fold = QPainterPath()
        fold.moveTo(14.0, 2.5)
        fold.lineTo(14.0, 7.0)
        fold.lineTo(18.5, 7.0)
        p.drawPath(fold)
        # two patches on the sheet: it is a chart
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colour)
        p.drawRect(QRectF(8.5, 12.0, 3.0, 3.0))
        p.drawRect(QRectF(12.5, 12.0, 3.0, 3.0))
        p.drawRect(QRectF(8.5, 16.0, 3.0, 3.0))
        c = QColor(colour)
        c.setAlphaF(c.alphaF() * 0.45)
        p.setBrush(c)
        p.drawRect(QRectF(12.5, 16.0, 3.0, 3.0))
    else:
        # a small screen on a stand
        p.drawRoundedRect(QRectF(2.5, 4.0, 19.0, 12.5), 1.8, 1.8)
        p.drawLine(QPointF(12.0, 16.5), QPointF(12.0, 20.5))
        p.drawLine(QPointF(8.0, 20.5), QPointF(16.0, 20.5))
    p.restore()


class PrintViewChip(QAbstractButton):
    """The indicator: an icon that slides open to a short line on hover.

    It knows nothing about previews: :meth:`set_state` gives it what to show
    and :attr:`activated` says the user asked for the other view. It never
    emits while :meth:`switchable` is False.

    A button, not a bare widget (review C of beta 12): a screen reader then
    announces it as a button and can press it (VoiceOver's "press", Windows
    Narrator's invoke), which a plain QWidget offers neither of. It paints
    itself; the click comes from QAbstractButton's own mouse handling."""

    activated = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon = ICON_PAPER
        self._title = ""
        self._hint = ""
        self._switchable = False
        self._bg = QColor(30, 30, 30, 185)
        self._ink = QColor("#f4f2ef")
        self._ring = QColor("#4dd0e1")
        self._edge = QColor(0, 0, 0, 0)
        # Basti, 2026-10-08: quiet and neutral; the icon alone may carry the
        # CURRENT TAB's accent, the same for both views (the view is told
        # apart by the icon's shape and the words only)
        self._icon_ink: "QColor | None" = None
        self._hint_ink: "QColor | None" = None
        self._hovered = False
        self._kb_focus = False
        self._anchor = (0, 0)          # (right, top) in the parent
        self._max_w = 0                # 0: no limit (see set_max_width)
        side = PILL_H + 2 * RING
        self._width = side
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.resize(side, side)
        self._anim = QPropertyAnimation(self, b"revealWidth", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.clicked.connect(self._activate)

    # -------------------------------------------------------------- state
    def set_state(self, *, icon: str, title: str, hint: str, tooltip: str,
                  switchable: bool) -> None:
        """What the chip shows. *hint* is the short "click: ..." line, empty
        when a click does nothing."""
        self._icon = icon
        self._title = title
        self._hint = hint if switchable else ""
        self._switchable = bool(switchable)
        self.setToolTip(tooltip)
        # not setText: a "&" in a translation would make it a mnemonic
        self.setAccessibleName(title)
        self.setAccessibleDescription(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor if switchable
                       else Qt.CursorShape.ArrowCursor)
        if self.is_open():
            self._animate_to(self.expanded_width(), instant=True)
        self.update()

    def set_colours(self, bg: str, ink: str, ring: str, edge: str = "", *,
                    icon_ink: str = "", hint_ink: str = "") -> None:
        """*ink*: the short line. *edge*: a hairline round the pill, where the
        pill would otherwise vanish on the well or the paper. *icon_ink*: the
        icon (*ink* when not given), the same in both views; *hint_ink*: the
        click hint (*ink* at 72 % when not given)."""
        self._bg, self._ink, self._ring = QColor(bg), QColor(ink), QColor(ring)
        self._edge = QColor(edge) if edge else QColor(0, 0, 0, 0)
        self._icon_ink = QColor(icon_ink) if icon_ink else None
        self._hint_ink = QColor(hint_ink) if hint_ink else None
        self.update()

    def icon_ink(self) -> QColor:
        return self._icon_ink if self._icon_ink is not None else self._ink

    def text_ink(self) -> QColor:
        return self._ink

    def icon(self) -> str:
        return self._icon

    def title(self) -> str:
        return self._title

    def hint(self) -> str:
        return self._hint

    def switchable(self) -> bool:
        return self._switchable

    def place(self, right: int, top: int) -> None:
        """Anchor the chip's top RIGHT corner; it opens to the left."""
        self._anchor = (int(right), int(top))
        self._apply_geometry()

    # ------------------------------------------------------------ widths
    def collapsed_width(self) -> int:
        return PILL_H + 2 * RING

    def _font(self) -> QFont:
        f = QFont(self.font())
        f.setPixelSize(11)
        return f

    def set_max_width(self, w: int) -> None:
        """The most the chip may open to: the room left of its anchor in the
        image area (review C of beta 12). The French line is 300 px and the
        image area 316 px at the window's minimum size, and the splitter
        makes it narrower still: past that the open chip ran off the image's
        left edge, cut. Now the hint goes first, then the title is elided."""
        w = max(0, int(w))
        if w == self._max_w:
            return
        self._max_w = w
        if self.is_open():
            self._animate_to(self.expanded_width(), instant=True)

    def _shown_text(self) -> "tuple[str, str]":
        """The title and hint that fit in the width the chip may open to."""
        fm = QFontMetrics(self._font())
        frame = 10 + 4 + PILL_H + 2 * RING
        title, hint = self._title, self._hint
        if not self._max_w:
            return title, hint
        room = self._max_w - frame
        if hint and fm.horizontalAdvance(title) + 8 + fm.horizontalAdvance(hint) <= room:
            return title, hint
        if fm.horizontalAdvance(title) <= room:
            return title, ""
        return fm.elidedText(title, Qt.TextElideMode.ElideRight, max(0, room)), ""

    def expanded_width(self) -> int:
        fm = QFontMetrics(self._font())
        title, hint = self._shown_text()
        w = 10 + fm.horizontalAdvance(title)
        if hint:
            w += 8 + fm.horizontalAdvance(hint)
        return w + 4 + PILL_H + 2 * RING

    def is_open(self) -> bool:
        return self._hovered or self._kb_focus

    def _get_reveal(self) -> int:
        return self._width

    def _set_reveal(self, w: int) -> None:
        self._width = max(self.collapsed_width(), int(w))
        self._apply_geometry()
        self.update()

    revealWidth = pyqtProperty(int, fget=_get_reveal, fset=_set_reveal)

    def _apply_geometry(self) -> None:
        right, top = self._anchor
        side = PILL_H + 2 * RING
        self.setGeometry(right - self._width, top, self._width, side)

    def _animate_to(self, target: int, *, instant: bool = False) -> None:
        self._anim.stop()
        if instant or reduce_motion() or self._width == target:
            self._set_reveal(target)
            return
        self._anim.setDuration(ANIM_MS)
        self._anim.setStartValue(self._width)
        self._anim.setEndValue(int(target))
        self._anim.start()

    def _reconsider(self) -> None:
        self._animate_to(self.expanded_width() if self.is_open()
                         else self.collapsed_width())

    # ------------------------------------------------------------ events
    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._hovered = True
        self._reconsider()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._hovered = False
        self._reconsider()
        super().leaveEvent(event)

    def focusInEvent(self, event) -> None:  # type: ignore[override]
        # Only the keyboard opens it and rings it: a click also gives focus,
        # and that must not keep it open after the pointer has gone.
        self._kb_focus = event.reason() in (
            Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason)
        self._reconsider()
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        self._kb_focus = False
        self._reconsider()
        self.update()
        super().focusOutEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return,
                           Qt.Key.Key_Enter, Qt.Key.Key_Select):
            self._activate()
            event.accept()
            return
        super().keyPressEvent(event)

    def _activate(self) -> None:
        if self._switchable:
            self.activated.emit()

    # ------------------------------------------------------------ paint
    def paintEvent(self, _event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        pill = QRectF(RING, RING, self.width() - 2 * RING, PILL_H)
        r = PILL_H / 2.0
        if self._kb_focus:
            ring = QPen(self._ring)
            ring.setWidthF(2.0)
            p.setPen(ring)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(pill.adjusted(-1.5, -1.5, 1.5, 1.5),
                              r + 1.5, r + 1.5)
        if self._edge.alpha():
            edge = QPen(self._edge)
            edge.setWidthF(1.0)
            p.setPen(edge)
        else:
            p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._bg)
        p.drawRoundedRect(pill.adjusted(0.5, 0.5, -0.5, -0.5), r - 0.5, r - 0.5)
        # the icon sits at the RIGHT end, where the chip is anchored
        icon_box = QRectF(pill.right() - PILL_H + 4, pill.top() + 4,
                          PILL_H - 8, PILL_H - 8)
        draw_icon(p, self._icon, icon_box, self.icon_ink())
        # the text is revealed from behind the icon as the pill grows
        text_w = pill.width() - PILL_H
        title, hint = self._shown_text()
        if text_w > 4 and title:
            clip = QPainterPath()
            clip.addRoundedRect(pill, r, r)
            p.setClipPath(clip)
            p.setClipRect(QRectF(pill.left(), pill.top(), text_w, PILL_H),
                          Qt.ClipOperation.IntersectClip)
            p.setFont(self._font())
            fm = QFontMetrics(self._font())
            # laid out against the RIGHT end, so the words slide in from it
            full = self.expanded_width() - 2 * RING - PILL_H
            x = pill.right() - PILL_H - full + 10
            base = pill.top() + (PILL_H + fm.ascent() - fm.descent()) / 2.0
            p.setPen(self._ink)
            p.drawText(int(round(x)), int(round(base)), title)
            if hint:
                if self._hint_ink is not None:
                    dim = QColor(self._hint_ink)
                else:
                    dim = QColor(self._ink)
                    dim.setAlphaF(0.72)
                p.setPen(dim)
                p.drawText(int(x + fm.horizontalAdvance(title) + 8),
                           int(round(base)), hint)
        p.end()
