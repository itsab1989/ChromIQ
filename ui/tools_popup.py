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
        self._tail_offset_x: int = 0  # tail apex X within the widget
        self._anchor: QWidget | None = None  # button we're anchored under, for hover-reset on close

        font = QFont()
        font.setPixelSize(13)
        self.setFont(font)

        self._compute_size()

    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        self._mode = "light" if mode == "light" else "dark"
        self._palette = _PALETTE_LIGHT if self._mode == "light" else _PALETTE_DARK
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
        panel_w = math.ceil(text_w) + inner + self.H_PAD
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
        panel_h = content + 2 * self.V_PAD
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

    def _rows(self) -> list[tuple[str, object, QRect]]:
        """Laid-out display rows: ``(kind, payload, rect)`` where kind is
        ``"header"`` (payload = label) or ``"tool"`` (payload = ToolEntry)."""
        panel = self._panel_rect()
        out: list[tuple[str, object, QRect]] = []
        y = panel.top() + self.V_PAD
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

        p.end()

    # ------------------------------------------------------------------
    def _index_at(self, pt: QPoint) -> int:
        """Index of the row under ``pt``; -1 over gaps or the transparent margin
        to either side of the panel (so a row never highlights when the cursor is
        level with it but outside the bubble)."""
        for i, (kind, _payload, rect) in enumerate(self._rows()):
            if kind == "tool" and rect.contains(pt):
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
