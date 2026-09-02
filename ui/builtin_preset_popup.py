"""Speech-bubble popup listing the built-in Create Chart presets.

Opened from the Create Chart tab's star button (next to GUIDED / MANUAL);
auto-closes on outside click (Qt.Popup). Same rounded-panel-with-tail look as
``ui.tools_popup.ToolsPopup``, but the rows are grouped under a small instrument
header (e.g. "i1Pro", "ColorMunki"). Header rows are inert; preset rows behave
like combobox items — hover highlight, click emits ``selected`` with the preset
key. Picking one is wired by the tab to the very same flow as choosing the
preset in the Manual presets dropdown (name prompt + generate).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtCore import (QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt,
                          pyqtSignal)
from PyQt6.QtGui import (
    QColor, QFont, QFontMetricsF, QMouseEvent, QPainter, QPainterPath,
    QPaintEvent, QPen,
)
from PyQt6.QtWidgets import QApplication, QToolButton, QWidget

from ui.styles import SPEC_MAGENTA
from core.i18n import tr
from ui import neutral_styles


# Per-mode visual tokens — kept in step with ui.tools_popup so the two popups
# read as siblings. ``header_text`` is the muted instrument-label colour.
_PALETTE_DARK = {
    "panel_bg":      "#1f1f1f",
    "panel_border":  "#333333",
    "text":          "#e6e6e6",
    "text_hover":    "#ffffff",
    "header_text":   "#8a8a8a",
    "hover_bg":      "#2a2a2a",
    "shadow":        QColor(0, 0, 0, 110),
}
_PALETTE_LIGHT = {
    "panel_bg":      "#ffffff",
    "panel_border":  "#d0ccc6",
    "text":          "#22211f",
    "text_hover":    "#22211f",
    "header_text":   "#9b958c",
    "hover_bg":      "#f0ece6",
    "shadow":        QColor(0, 0, 0, 30),
}
#: Neutral — kept in step with ui.tools_popup, as the two dark/light pairs
#: already are. ``header_text`` is TERTIARY, not faint: at 8.13:1 it still
#: reads, because an instrument label that works may not be faint.
_PALETTE_NEUTRAL = {
    "panel_bg":      neutral_styles.NM_BG_SURFACE,
    "panel_border":  neutral_styles.NM_BORDER,
    "text":          neutral_styles.NM_TEXT_MAIN,
    "text_hover":    neutral_styles.NM_TEXT_MAIN,
    "header_text":   neutral_styles.NM_TEXT_FAINT,
    # THE THEME'S HOVER TOKEN, not the window value it used to name. Those
    # were the same colour until the grounds were collapsed onto one; after
    # that, a hover row painted in the window value IS the card it sits on and
    # the row stops lighting up at all. NM_BG_HOVER steps down instead.
    "hover_bg":      neutral_styles.NM_BG_HOVER,
    "shadow":        QColor(0, 0, 0, 30),
}

#: ``{appearance: palette}`` — a TABLE, not a ternary. ``_PALETTE_LIGHT if
#: mode == "light" else _PALETTE_DARK`` had room for two answers and gave the
#: dark one to everything else: the appearance name arrived intact (that was
#: ``accept_mode``'s job, one layer up) and the COLOURS were still folded.
#: Adding an appearance is adding a row.
_PALETTES = {
    "light":   _PALETTE_LIGHT,
    "dark":    _PALETTE_DARK,
    "neutral": _PALETTE_NEUTRAL,
}


class BuiltinPresetButton(QToolButton):
    """Presets button that opens the Built-in presets overlay.

    Sits next to the GUIDED / MANUAL switch. The glyph is a small **list** (three
    rows, each a bullet + line) — a menu of presets to pick from, which reads as
    "presets" rather than "favourites" (the old star did). It's the app's spectrum
    magenta in the two COLOURED themes, painted directly in ``paintEvent`` like
    the welcome "?" button — building a QIcon from a DPR-scaled pixmap clips on
    Retina, painting in logical coords doesn't. The QSS ``#tooltip_btn`` rule
    still paints the hover background (we chain to ``super().paintEvent``).

    ``set_appearance`` used to be a no-op on the grounds that "magenta is
    theme-independent". That stopped being true the moment a third appearance
    had ONE accent: it now remembers the mode and the glyph is painted in
    whatever that appearance's accent is.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tooltip_btn")
        # Icon-only: never take keyboard focus (space would open the presets
        # overlay just because a tab handed it the initial focus) (Knut).
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(tr("Built-in presets"))
        self.setFixedSize(QSize(40, 40))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False
        self._mode = "dark"

    def set_appearance(self, mode: str) -> None:
        from ui.theme import accept_mode
        self._mode = accept_mode(mode)
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, ev: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(ev)  # QSS background (incl. :hover) under the glyph
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        s = min(w, h)
        from ui.theme import accent_for
        color = QColor(accent_for(SPEC_MAGENTA, self._mode))
        if not self.isEnabled():
            color.setAlpha(70)      # parked (e.g. FROM PROFILE GAMUT active)
        elif not self._hover:
            color.setAlpha(230)
        # Three list rows: a rounded-square bullet + a line, centred with a
        # comfortable margin so the glyph reads as a small icon in the hit target.
        line_w = s * 0.075
        bullet = s * 0.10
        for i in range(3):
            y = h * (0.32 + i * 0.20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(w * 0.22, y - bullet / 2, bullet, bullet),
                              bullet * 0.28, bullet * 0.28)
            pen = QPen(color)
            pen.setWidthF(line_w)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(w * 0.40, y), QPointF(w * 0.78, y))
        p.end()


@dataclass(frozen=True)
class _VisualRow:
    """One painted line: an instrument header, or a selectable preset."""
    kind:   str          # "header" | "item"
    text:   str
    key:    str | None   # preset key for "item" rows, else None
    top:    int          # y of the row within the widget
    height: int


class BuiltinPresetPopup(QWidget):
    """Grouped speech-bubble popup. Show via ``show_under(button)``.

    ``groups`` is ``[(instrument, [(overlay_label, key), …]), …]`` — exactly
    what the tab derives from BUILTIN_PRESET_GROUPS. Emits ``selected(key)``.
    """

    selected = pyqtSignal(str)  # preset key

    TAIL_W       = 16   # base width of the tail triangle
    TAIL_H       = 9    # height of the tail (sticks up above the panel)
    CORNER_R     = 10
    HEADER_H     = 26   # instrument header row
    ROW_H        = 34   # preset row
    H_PAD        = 18   # horizontal padding inside the panel
    V_PAD        = 8    # vertical padding above the first / below the last row
    ITEM_INDENT  = 12   # extra left inset for preset labels under a header
    PANEL_MARGIN = 12   # transparent space around panel for the drop shadow
    # When the built-in list is taller than this many preset entries the panel
    # caps its height and scrolls (mouse wheel). One leading header is allowed
    # for on top of the visible entries.
    MAX_VISIBLE_ITEMS = 10
    SCROLLBAR_W       = 4    # width of the scroll thumb drawn inside the panel

    def __init__(
        self,
        groups: list[tuple[str, list[tuple[str, str]]]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        # NoDropShadowWindowHint suppresses the platform's own popup shadow (see
        # ui.tools_popup for the rationale); we paint our own soft shadow.
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self._groups  = groups
        self._mode    = "dark"
        self._palette = _PALETTE_DARK
        self._hover_index: int = -1
        self._tail_offset_x: int = 0
        self._anchor: QWidget | None = None

        self._item_font = QFont()
        self._item_font.setPixelSize(13)
        self._header_font = QFont()
        self._header_font.setPixelSize(11)
        self._header_font.setBold(True)
        self.setFont(self._item_font)

        # Scroll state (set in _compute_size). _content_top is the widget-space y
        # of the first row; rows store content-relative tops and are offset by
        # _content_top - _scroll_y when painted / hit-tested.
        self._scroll_y    = 0
        self._max_scroll  = 0
        self._viewport_h  = 0
        self._content_h   = 0
        self._content_top = 0

        self._rows: list[_VisualRow] = []
        self._build_rows()
        self._compute_size()

    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        from ui.theme import accept_mode
        self._mode = accept_mode(mode)
        self._palette = _PALETTES.get(self._mode, _PALETTE_DARK)
        self.update()

    # ------------------------------------------------------------------
    def _build_rows(self) -> None:
        """Flatten the grouped presets into headers + item rows.

        ``top`` is content-relative (first row at y=0); painting/hit-testing add
        ``_content_top - _scroll_y`` so the same list can be scrolled."""
        self._rows = []
        y = 0
        for instr, entries in self._groups:
            self._rows.append(_VisualRow("header", instr, None, y, self.HEADER_H))
            y += self.HEADER_H
            for label, key in entries:
                self._rows.append(_VisualRow("item", label, key, y, self.ROW_H))
                y += self.ROW_H

    def _compute_size(self) -> None:
        item_fm   = QFontMetricsF(self._item_font)
        header_fm = QFontMetricsF(self._header_font)
        text_w = 0.0
        for row in self._rows:
            if row.kind == "item":
                # Items inset by ROW(6)+TEXT(12)+ITEM_INDENT on the left.
                w = item_fm.horizontalAdvance(row.text) + self.ITEM_INDENT
            else:
                w = header_fm.horizontalAdvance(row.text)
            text_w = max(text_w, w)
        inner = 2 * (6 + 12)
        panel_w = math.ceil(text_w) + inner + self.H_PAD + self.SCROLLBAR_W
        panel_w = max(panel_w, 260)

        self._content_h = sum(r.height for r in self._rows)
        # Cap the viewport to one header + MAX_VISIBLE_ITEMS entries; scroll the
        # rest. A short list (≤ cap) shows in full with no scrolling.
        cap_h = self.HEADER_H + self.MAX_VISIBLE_ITEMS * self.ROW_H
        self._viewport_h = min(self._content_h, cap_h)
        self._max_scroll = self._content_h - self._viewport_h
        self._scroll_y = 0

        self._content_top = self.PANEL_MARGIN + self.TAIL_H + self.V_PAD
        panel_h = self._viewport_h + 2 * self.V_PAD
        w = panel_w + 2 * self.PANEL_MARGIN
        h = panel_h + 2 * self.PANEL_MARGIN + self.TAIL_H
        self.setFixedSize(w, h)

    def _panel_rect(self) -> QRect:
        return QRect(
            self.PANEL_MARGIN,
            self.PANEL_MARGIN + self.TAIL_H,
            self.width()  - 2 * self.PANEL_MARGIN,
            self.height() - 2 * self.PANEL_MARGIN - self.TAIL_H,
        )

    def _viewport_rect(self) -> QRect:
        """The scrolling content region inside the panel (rows are clipped here)."""
        panel = self._panel_rect()
        return QRect(panel.left(), self._content_top, panel.width(), self._viewport_h)

    def _row_rect(self, row: _VisualRow) -> QRect:
        panel = self._panel_rect()
        y = self._content_top + row.top - self._scroll_y
        return QRect(panel.left() + 6, y, panel.width() - 12, row.height)

    # ------------------------------------------------------------------
    def show_under(self, anchor: QWidget) -> None:
        """Position so the tail apex lands at the horizontal centre of ``anchor``."""
        self._anchor = anchor
        gp = anchor.mapToGlobal(QPoint(0, anchor.height()))
        anchor_center_x = gp.x() + anchor.width() // 2

        ideal_x = anchor_center_x - self.width() // 2
        screen = anchor.screen()
        avail = screen.availableGeometry() if screen else None
        if avail:
            min_x = avail.left() + 4
            max_x = avail.right() - self.width() - 4
            x = max(min_x, min(ideal_x, max_x))
        else:
            x = ideal_x

        y = gp.y() + 2

        self._tail_offset_x = anchor_center_x - x
        self._tail_offset_x = max(
            self.PANEL_MARGIN + self.CORNER_R + self.TAIL_W,
            min(self._tail_offset_x,
                self.width() - self.PANEL_MARGIN - self.CORNER_R - self.TAIL_W),
        )

        self.move(x, y)
        self._hover_index = -1
        self.show()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------
    def paintEvent(self, _ev: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        pal = self._palette
        panel = self._panel_rect()

        bubble = QPainterPath()
        bubble.addRoundedRect(
            float(panel.left()), float(panel.top()),
            float(panel.width()), float(panel.height()),
            float(self.CORNER_R), float(self.CORNER_R),
        )
        tail = QPainterPath()
        apex_x = self._tail_offset_x
        apex_y = panel.top() - self.TAIL_H + 1
        base_y = panel.top() + 1
        tail.moveTo(float(apex_x),                   float(apex_y))
        tail.lineTo(float(apex_x - self.TAIL_W / 2), float(base_y))
        tail.lineTo(float(apex_x + self.TAIL_W / 2), float(base_y))
        tail.closeSubpath()
        bubble = bubble.united(tail)

        shadow = QPainterPath(bubble)
        shadow.translate(0, 3)
        p.fillPath(shadow, pal["shadow"])

        p.fillPath(bubble, QColor(pal["panel_bg"]))
        p.setPen(QPen(QColor(pal["panel_border"]), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(bubble)

        # Clip the rows to the scrolling viewport so partial rows don't bleed
        # over the rounded corners / tail / padding.
        viewport = self._viewport_rect()
        sb_w = self.SCROLLBAR_W if self._max_scroll > 0 else 0
        p.save()
        p.setClipRect(viewport)
        for i, row in enumerate(self._rows):
            rect = self._row_rect(row)
            if rect.bottom() < viewport.top() or rect.top() > viewport.bottom():
                continue  # fully scrolled out of view
            if row.kind == "header":
                p.setPen(QColor(pal["header_text"]))
                p.setFont(self._header_font)
                p.drawText(
                    QRect(rect.left() + 12, rect.top(),
                          rect.width() - 24 - sb_w, rect.height()),
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
                    row.text,
                )
                continue
            if i == self._hover_index:
                p.setBrush(QColor(pal["hover_bg"]))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(
                    QRect(rect.left(), rect.top(), rect.width() - sb_w, rect.height()),
                    6, 6,
                )
                text_color = pal["text_hover"]
            else:
                text_color = pal["text"]
            p.setPen(QColor(text_color))
            p.setFont(self._item_font)
            p.drawText(
                QRect(rect.left() + 12 + self.ITEM_INDENT, rect.top(),
                      rect.width() - 24 - self.ITEM_INDENT - sb_w, rect.height()),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                row.text,
            )
        p.restore()

        # Scroll thumb on the right edge of the viewport.
        if self._max_scroll > 0:
            track_h = viewport.height()
            thumb_h = max(24, int(track_h * self._viewport_h / self._content_h))
            travel  = track_h - thumb_h
            frac    = self._scroll_y / self._max_scroll if self._max_scroll else 0
            thumb_y = viewport.top() + int(travel * frac)
            thumb_x = panel.right() - self.SCROLLBAR_W - 3
            thumb   = QColor(pal["text"])
            thumb.setAlpha(70)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(thumb)
            p.drawRoundedRect(
                QRect(thumb_x, thumb_y, self.SCROLLBAR_W, thumb_h),
                2, 2,
            )

        p.end()

    # ------------------------------------------------------------------
    def _index_at(self, pt: QPoint) -> int:
        """Index of the selectable (item) row under ``pt``; -1 over headers,
        gaps, the scrolled-away region, or the transparent margin."""
        if not self._viewport_rect().contains(pt):
            return -1
        for i, row in enumerate(self._rows):
            if row.kind != "item":
                continue
            if self._row_rect(row).contains(pt):
                return i
        return -1

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self._max_scroll <= 0:
            return
        # angleDelta is in eighths of a degree; one notch ≈ 120 → ~ROW_H/notch.
        dy = event.angleDelta().y()
        step = int(round(dy / 120 * self.ROW_H)) or (1 if dy > 0 else -1)
        new_y = max(0, min(self._max_scroll, self._scroll_y - step))
        if new_y != self._scroll_y:
            self._scroll_y = new_y
            self._hover_index = self._index_at(
                self.mapFromGlobal(self.cursor().pos())
            )
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        idx = self._index_at(event.position().toPoint())
        if idx != self._hover_index:
            self._hover_index = idx
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._hover_index != -1:
            self._hover_index = -1
            self.update()
        super().leaveEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        # Same synthetic-Leave fix as ToolsPopup: the Qt.Popup mouse grab robs
        # the anchor button of the Leave that would clear its :hover state.
        super().hideEvent(event)
        anchor = self._anchor
        if anchor is not None:
            QApplication.sendEvent(anchor, QEvent(QEvent.Type.Leave))
            anchor.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        pt = event.position().toPoint()
        if not self._panel_rect().contains(pt):
            self.close()
            return
        idx = self._index_at(pt)
        if idx < 0:
            return
        key = self._rows[idx].key
        self.close()
        if key is not None:
            self.selected.emit(key)
