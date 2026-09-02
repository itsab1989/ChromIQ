"""Speech-bubble popup listing the standalone utilities.

Opened from the masthead Tools button; auto-closes on outside click (Qt.Popup).
Rounded panel with a small upward-pointing tail aligned under the button. Each
row behaves like a combobox item — hover highlight, click emits ``selected``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontMetricsF, QMouseEvent, QPainter, QPainterPath,
    QPaintEvent, QPen,
)
from PyQt6.QtWidgets import QApplication, QWidget
from core.i18n import tr
from ui import neutral_styles


# Per-mode visual tokens. Hover background uses a translucent accent so the
# row sits naturally on the panel fill without an explicit border.
_PALETTE_DARK = {
    "panel_bg":      "#1f1f1f",
    "panel_border":  "#333333",
    "text":          "#e6e6e6",
    "text_hover":    "#ffffff",
    "hover_bg":      "#2a2a2a",
    "shadow":        QColor(0, 0, 0, 110),
}
_PALETTE_LIGHT = {
    "panel_bg":      "#ffffff",
    "panel_border":  "#d0ccc6",
    "text":          "#22211f",
    "text_hover":    "#22211f",
    "hover_bg":      "#f0ece6",
    "shadow":        QColor(0, 0, 0, 30),
}
#: Neutral. The popup is a raised card, and its hover steps DOWN from that
#: card rather than up — nothing in this theme is lighter than its ground.
_PALETTE_NEUTRAL = {
    "panel_bg":      neutral_styles.NM_BG_SURFACE,
    "panel_border":  neutral_styles.NM_BORDER,
    "text":          neutral_styles.NM_TEXT_MAIN,
    "text_hover":    neutral_styles.NM_TEXT_MAIN,
    "hover_bg":      neutral_styles.NM_BG_WINDOW,
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


@dataclass(frozen=True)
class ToolEntry:
    key:   str
    label: str


# Tools grouped by task (Knut) — headers are non-clickable; alphabetical-ish
# order within each group follows the workflow.
_GROUPS: tuple[tuple[str, tuple[ToolEntry, ...]], ...] = (
    (tr("Measurements"), (
        ToolEntry("spot_read",  tr("Read single patches")),
        ToolEntry("average",    tr("Average measurements")),
        ToolEntry("merge",      tr("Merge measurements")),
        ToolEntry("ti3_info",   tr("Inspect a measurement")),
        ToolEntry("measurement_report", tr("Measurement report (accuracy & drift)")),
    )),
    (tr("Charts & patch sets"), (
        ToolEntry("ti2_relayout", tr("Edit / create chart patch set")),
        ToolEntry("patch_cube",   tr("Show patch distribution (3D)")),
    )),
    (tr("Scanner & camera"), (
        ToolEntry("scanner_target",  tr("Create scanner or camera target (.cht + .cie)")),
        ToolEntry("scanner_profile", tr("Build profile with scanner or camera (from a scan or photo)")),
    )),
    (tr("i1Profiler interchange"), (
        ToolEntry("ti1_to_i1p", tr("Convert TI1 → i1Profiler")),
        ToolEntry("i1p_to_ti3", tr("Convert i1Profiler → TI3")),
        ToolEntry("i1p_to_ti1", tr("Convert i1Profiler → TI1")),
    )),
    (tr("Profiles"), (
        ToolEntry("profile_info",   tr("Inspect a profile")),
        ToolEntry("verify_profile", tr("Verify a profile (independent check)")),
        ToolEntry("verify",         tr("Verify against reference")),
        ToolEntry("device_link",    tr("Create device-link profile")),
        ToolEntry("devicelink_apply", tr("Apply a device-link to an image")),
        ToolEntry("softproof",      tr("Soft-proof / check an image")),
    )),
    (tr("Instruments"), (
        ToolEntry("cr30_bt_report",
                  tr("CR30 Bluetooth report (for when it will not connect)")),
    )),
    (tr("Language"), (
        ToolEntry("translate", tr("Translate / edit language")),
    )),
)

# Flat display model: ("header", label) or ("tool", ToolEntry), in order.
_ROWS: tuple[tuple[str, object], ...] = tuple(
    row
    for header, entries in _GROUPS
    for row in ((("header", header),) + tuple(("tool", e) for e in entries))
)
_ENTRIES: tuple[ToolEntry, ...] = tuple(
    e for _, entries in _GROUPS for e in entries)


class ToolsPopup(QWidget):
    """Speech-bubble popup. Show via ``show_under(button)``; emits ``selected``."""

    selected = pyqtSignal(str)  # tool key

    TAIL_W      = 16    # base width of the tail triangle
    TAIL_H      = 9     # height of the tail (sticks up above the panel)
    CORNER_R    = 10
    ROW_H       = 36
    HEADER_H    = 24    # non-clickable group header row
    GROUP_GAP   = 8     # extra space above each header (except the first)
    H_PAD       = 18    # horizontal padding inside the panel
    V_PAD       = 8     # vertical padding above the first / below the last row
    PANEL_MARGIN = 12   # transparent space around panel for the drop shadow
    SCROLLBAR_W  = 4    # thumb width, matching ui/builtin_preset_popup

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # NoDropShadowWindowHint suppresses the platform's own popup shadow.
        # On Windows that native shadow sits on the bottom/right edges of this
        # translucent frameless window and reads as a hard border; we paint our
        # own soft shadow in paintEvent, so the OS one is both redundant and ugly.
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self._mode    = "dark"
        self._palette = _PALETTE_DARK
        self._hover_index: int = -1
        #: How far the list is scrolled, in pixels. The popup is painted rather
        #: than laid out, so scrolling is an offset applied in `_rows()` --
        #: which both the painter and the hit test go through, so they cannot
        #: disagree about where a row is.
        self._scroll: int = 0
        self._content_h: int = 0     # the full list's height
        self._view_h: int = 0        # what the capped panel can show
        self._tail_offset_x: int = 0  # tail apex X within the widget
        self._anchor: QWidget | None = None  # button we're anchored under, for hover-reset on close

        font = QFont()
        font.setPixelSize(13)
        self.setFont(font)

        self._compute_size()

    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        from ui.theme import accept_mode
        self._mode = accept_mode(mode)
        self._palette = _PALETTES.get(self._mode, _PALETTE_DARK)
        self.update()

    # ------------------------------------------------------------------
    def _compute_size(self) -> None:
        fm = QFontMetricsF(self.font())
        text_w = max(fm.horizontalAdvance(e.label) for e in _ENTRIES)
        # Each row insets its label by ROW(6)+TEXT(12) px on each side (see
        # _row_rect / paintEvent), which alone consumed all of 2*H_PAD and left the
        # widest label flush against the edge — the last glyph clipped. Reserve the
        # true insets plus H_PAD of actual breathing room, and round up so a
        # fractional advance never truncates.
        inner = 2 * (6 + 12)
        panel_w = math.ceil(text_w) + inner + self.H_PAD + self.SCROLLBAR_W
        panel_w = max(panel_w, 240)
        content = 0
        first = True
        for kind, _payload in _ROWS:
            if kind == "header":
                if not first:
                    content += self.GROUP_GAP
                content += self.HEADER_H
            else:
                content += self.ROW_H
            first = False
        # CAP IT AGAINST THE SCREEN, AND SCROLL THE REST. The list has grown
        # with the app -- twenty entries in seven groups -- and an uncapped
        # popup eventually runs off the bottom of the display, where the last
        # tools are simply unreachable. Two thirds of the available height
        # leaves the anchor button and some page visible above and below.
        self._content_h = content
        avail = 700
        try:
            from PyQt6.QtGui import QGuiApplication
            scr = QGuiApplication.screenAt(self.pos()) or \
                QGuiApplication.primaryScreen()
            if scr is not None:
                avail = scr.availableGeometry().height()
        except Exception:            # noqa: BLE001 — a cap, never fatal
            pass
        room = max(240, int(avail * 0.66) - 2 * self.PANEL_MARGIN
                   - self.TAIL_H - 2 * self.V_PAD)
        self._view_h = min(content, room)
        panel_h = self._view_h + 2 * self.V_PAD
        w = panel_w + 2 * self.PANEL_MARGIN
        h = panel_h + 2 * self.PANEL_MARGIN + self.TAIL_H
        self.setFixedSize(w, h)
        self._scroll = min(self._scroll, self._max_scroll())

    def _panel_rect(self) -> QRect:
        return QRect(
            self.PANEL_MARGIN,
            self.PANEL_MARGIN + self.TAIL_H,
            self.width()  - 2 * self.PANEL_MARGIN,
            self.height() - 2 * self.PANEL_MARGIN - self.TAIL_H,
        )

    def _rows(self) -> list[tuple[str, object, QRect]]:
        """Laid-out display rows: ``(kind, payload, rect)`` where kind is
        ``"header"`` (payload = label) or ``"tool"`` (payload = ToolEntry)."""
        panel = self._panel_rect()
        out: list[tuple[str, object, QRect]] = []
        y = panel.top() + self.V_PAD - self._scroll
        first = True
        for kind, payload in _ROWS:
            if kind == "header":
                if not first:
                    y += self.GROUP_GAP
                h = self.HEADER_H
            else:
                h = self.ROW_H
            out.append((kind, payload, QRect(panel.left() + 6, y, panel.width() - 12, h)))
            y += h
            first = False
        return out

    # ------------------------------------------------------------------
    def show_under(self, anchor: QWidget) -> None:
        """Position so the tail apex lands at the horizontal centre of ``anchor``."""
        self._anchor = anchor
        gp = anchor.mapToGlobal(QPoint(0, anchor.height()))
        anchor_center_x = gp.x() + anchor.width() // 2

        # Panel ideal X: centred under the anchor.
        ideal_x = anchor_center_x - self.width() // 2

        # Clamp to the anchor widget's screen so we never cross the screen edge.
        screen = anchor.screen()
        avail = screen.availableGeometry() if screen else None
        if avail:
            min_x = avail.left() + 4
            max_x = avail.right() - self.width() - 4
            x = max(min_x, min(ideal_x, max_x))
        else:
            x = ideal_x

        y = gp.y() + 2  # slight gap below the button

        # Tail apex offset within the widget, so paintEvent draws it pointing
        # straight up at the anchor regardless of clamping.
        self._tail_offset_x = anchor_center_x - x
        self._tail_offset_x = max(
            self.PANEL_MARGIN + self.CORNER_R + self.TAIL_W,
            min(self._tail_offset_x, self.width() - self.PANEL_MARGIN - self.CORNER_R - self.TAIL_W),
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

        # Build speech-bubble path: rounded rectangle + triangular tail at top.
        bubble = QPainterPath()
        bubble.addRoundedRect(
            float(panel.left()), float(panel.top()),
            float(panel.width()), float(panel.height()),
            float(self.CORNER_R), float(self.CORNER_R),
        )
        tail = QPainterPath()
        apex_x = self._tail_offset_x
        apex_y = panel.top() - self.TAIL_H + 1   # +1 to overlap and avoid hairline gap
        base_y = panel.top() + 1
        tail.moveTo(float(apex_x),                       float(apex_y))
        tail.lineTo(float(apex_x - self.TAIL_W / 2),     float(base_y))
        tail.lineTo(float(apex_x + self.TAIL_W / 2),     float(base_y))
        tail.closeSubpath()
        bubble = bubble.united(tail)

        # Soft shadow — translate the bubble path down a few pixels and fill faint.
        shadow = QPainterPath(bubble)
        shadow.translate(0, 3)
        p.fillPath(shadow, pal["shadow"])

        # Panel fill + border (single combined path so the tail joins seamlessly).
        p.fillPath(bubble, QColor(pal["panel_bg"]))
        p.setPen(QPen(QColor(pal["panel_border"]), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(bubble)

        # CLIP TO THE PANEL BEFORE DRAWING ROWS. Scrolled rows still have
        # rectangles above and below the visible area; without this they paint
        # over the tail, the shadow margin and whatever is behind the popup.
        p.save()
        p.setClipRect(panel.adjusted(1, 1, -1, -1))

        # Rows (grouped: muted uppercase headers, hoverable tool rows)
        header_font = QFont(self.font())
        header_font.setPixelSize(10)
        header_font.setBold(True)
        header_color = QColor(pal["text"])
        header_color.setAlpha(120)
        for i, (kind, payload, row) in enumerate(self._rows()):
            if kind == "header":
                p.setPen(header_color)
                p.setFont(header_font)
                p.drawText(
                    QRect(row.left() + 12, row.top(), row.width() - 24, row.height()),
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
                    str(payload).upper(),
                )
                continue
            if i == self._hover_index:
                p.setBrush(QColor(pal["hover_bg"]))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(row, 6, 6)
                text_color = pal["text_hover"]
            else:
                text_color = pal["text"]
            p.setPen(QColor(text_color))
            p.setFont(self.font())
            p.drawText(
                QRect(row.left() + 12, row.top(), row.width() - 24, row.height()),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                payload.label,
            )

        p.restore()

        # A HINT THAT THERE IS MORE. Without it a capped list looks like the
        # whole list, and the tools below the fold simply do not exist as far
        # as the user is concerned. Two soft fades, each shown only when there
        # is something in that direction, plus a slim thumb on the right.
        if self.is_scrollable():
            from PyQt6.QtGui import QLinearGradient
            edge = QColor(pal["panel_bg"])
            fade_h = 18
            if self._scroll > 0:
                g = QLinearGradient(0, panel.top(), 0, panel.top() + fade_h)
                c0 = QColor(edge); c0.setAlpha(235)
                c1 = QColor(edge); c1.setAlpha(0)
                g.setColorAt(0.0, c0); g.setColorAt(1.0, c1)
                p.fillRect(QRect(panel.left() + 1, panel.top() + 1,
                                 panel.width() - 2, fade_h), g)
            if self._scroll < self._max_scroll():
                g = QLinearGradient(0, panel.bottom() - fade_h, 0, panel.bottom())
                c0 = QColor(edge); c0.setAlpha(0)
                c1 = QColor(edge); c1.setAlpha(235)
                g.setColorAt(0.0, c0); g.setColorAt(1.0, c1)
                p.fillRect(QRect(panel.left() + 1, panel.bottom() - fade_h,
                                 panel.width() - 2, fade_h), g)
            track_h = panel.height() - 2 * self.V_PAD
            frac = self._view_h / float(max(1, self._content_h))
            thumb_h = max(24, int(track_h * frac))
            span = track_h - thumb_h
            pos = 0 if self._max_scroll() == 0 else int(
                span * self._scroll / self._max_scroll())
            # `pal` HAS NO "row_text" KEY, so this fell back to the panel
            # BORDER colour at alpha 70 -- #333 on #1f1f1f, which is why Basti
            # saw no scrollbar at all. The preset popup draws its thumb from
            # "text" at the same alpha, and that is visible; matching it also
            # makes the two overlays look like the same app.
            thumb = QColor(pal["text"])
            thumb.setAlpha(70)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(thumb)
            p.drawRoundedRect(
                QRect(panel.right() - self.SCROLLBAR_W - 3,
                      panel.top() + self.V_PAD + pos,
                      self.SCROLLBAR_W, thumb_h),
                self.SCROLLBAR_W / 2.0, self.SCROLLBAR_W / 2.0)

        p.end()

    # ------------------------------------------------------------------
    def _max_scroll(self) -> int:
        return max(0, self._content_h - self._view_h)

    def is_scrollable(self) -> bool:
        return self._max_scroll() > 0

    def wheelEvent(self, event) -> None:  # noqa: N802
        if not self.is_scrollable():
            super().wheelEvent(event)
            return
        # THE SAME FEEL AS THE PRESET POPUP, which already solved this
        # (`ui/builtin_preset_popup.py`): angleDelta is in eighths of a degree,
        # one notch is 120, so one notch moves one row. My first version jumped
        # three rows per notch and quantised everything smaller to a whole row,
        # which is what made a trackpad feel jumpy.
        dy = event.angleDelta().y() or event.angleDelta().x()
        step = int(round(dy / 120 * self.ROW_H)) or (1 if dy > 0 else -1)
        before = self._scroll
        self._scroll = max(0, min(self._max_scroll(), self._scroll - step))
        if self._scroll != before:
            # The row under the cursor has changed without the cursor moving.
            self._hover_index = self._index_at(
                self.mapFromGlobal(self.cursor().pos()))
            self.update()
        event.accept()

    def _index_at(self, pt: QPoint) -> int:
        """Index of the row under ``pt``; -1 over gaps or the transparent margin
        to either side of the panel (so a row never highlights when the cursor is
        level with it but outside the bubble)."""
        # …AND ONLY WITHIN THE PANEL. A row scrolled above or below the visible
        # area still has a rectangle; without this it would answer to a click
        # level with it but outside the bubble, which is the one thing a
        # scrolling menu must never do.
        view = self._panel_rect()
        for i, (kind, _payload, rect) in enumerate(self._rows()):
            if kind == "tool" and rect.contains(pt) \
                    and view.contains(rect.center()):
                return i
        return -1

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
        # Qt.Popup grabs the mouse the moment the anchor button is pressed, so
        # the underlying QToolButton never receives the Leave event that would
        # clear its :hover background. After dismissing the popup the button
        # would otherwise read as still-highlighted until the cursor next
        # enters and leaves it. Send a synthetic Leave so Qt re-evaluates.
        super().hideEvent(event)
        anchor = self._anchor
        if anchor is not None:
            QApplication.sendEvent(anchor, QEvent(QEvent.Type.Leave))
            anchor.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        # Clicks outside the panel close the popup (Qt.Popup also handles this
        # by closing the window — but only for clicks fully outside our
        # geometry; here we explicitly close when the panel area is missed).
        pt = event.position().toPoint()
        if not self._panel_rect().contains(pt):
            self.close()
            return
        idx = self._index_at(pt)
        if idx < 0:
            return
        kind, payload, _rect = self._rows()[idx]
        if kind != "tool":
            return
        self.close()
        self.selected.emit(payload.key)
