"""Full-width tab bar where each tab gets one of the 5 spectrum colors.

Drop-in replacement for the standard QTabBar inside ChromIQ's QTabWidget.
Each tab paints a 3px accent strip at the top in its own color, plus
a faint color tint when active. Tabs expand to fill the full width.

Usage in main_window.py:

    from ui.spectrum_tab_bar import SpectrumTabBar
    self._tabs = QTabWidget(central)
    self._tabs.setTabBar(SpectrumTabBar(self._tabs))
    self._tabs.setDocumentMode(True)
    # ... addTab() calls remain unchanged
"""
from __future__ import annotations

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QStyleOptionTab, QTabBar, QWidget

# Five spectrum colors — same order as tabs:
# 1 Create · 2 Print · 3 Measure · 4 Profile · 5 Check
SPECTRUM = [
    "#ff4573",  # 1 Create Chart
    "#ffb42d",  # 2 Print Chart
    "#56d6a5",  # 3 Measure
    "#37bcd6",  # 4 Build Profile
    "#9f82ff",  # 5 Check & Refine
]

# Per-mode palette. Values for "dark" preserve the historical look.
_PALETTE_DARK = {
    "bar_bg":        "#0f0f0f",
    "active_bg":     "#1e1e1e",
    "text_inactive": "#909090",
    "text_active":   "#ffffff",
    "sep":           "#2a2a2a",
    "disabled_overlay": "#0f0f0f",
    "disabled_text":    "#404040",
}
_PALETTE_LIGHT = {
    "bar_bg":        "#e5e2dd",   # inactive tab bg per design spec
    "active_bg":     "#ffffff",   # active tab bg per design spec
    "text_inactive": "#989490",
    "text_active":   "#22211f",
    "sep":           "#d0ccc6",
    "disabled_overlay": "#e5e2dd",
    "disabled_text":    "#b8b4ae",
}

# Module-level back-compat (read by anything still importing these names).
BG_BAR     = _PALETTE_DARK["bar_bg"]
BG_INACTIVE = "transparent"
BG_ACTIVE   = _PALETTE_DARK["active_bg"]
TEXT_INACTIVE = _PALETTE_DARK["text_inactive"]
TEXT_ACTIVE   = _PALETTE_DARK["text_active"]
SEP           = _PALETTE_DARK["sep"]


class SpectrumTabBar(QTabBar):
    """Custom tab bar — full width, per-tab spectrum accent."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode = "dark"
        self._palette = _PALETTE_DARK
        self.setExpanding(True)        # spread tabs to fill the bar
        self.setDrawBase(False)        # we paint our own bottom line
        self.setUsesScrollButtons(False)
        self.setDocumentMode(True)
        self.setFixedHeight(48)

    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        """Switch between dark and light palettes; called by MainWindow.apply_theme."""
        from ui.theme import accept_mode
        new_mode = accept_mode(mode)
        if new_mode == self._mode:
            return
        self._mode = new_mode
        self._palette = _PALETTE_LIGHT if new_mode == "light" else _PALETTE_DARK
        self.update()

    # ------------------------------------------------------------------
    # Sizing — each tab gets equal share of total width
    # ------------------------------------------------------------------
    def tabSizeHint(self, index: int):  # type: ignore[override]
        sh = super().tabSizeHint(index)
        n = self.count()
        if n > 0 and self.parent() is not None:
            # Use the parent (QTabWidget) width so tabs stretch full bar
            parent = self.parent()
            total = parent.width() if parent else self.width()
            sh.setWidth(max(120, total // n))
        sh.setHeight(48)
        return sh

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        pal = self._palette

        # Fill the entire bar background — covers any gap to the right
        p.fillRect(self.rect(), QColor(pal["bar_bg"]))

        # Bottom border line
        p.setPen(QPen(QColor(pal["sep"]), 1))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

        for i in range(self.count()):
            rect: QRect = self.tabRect(i)
            if not rect.isValid():
                continue

            color_hex = SPECTRUM[i] if i < len(SPECTRUM) else SPECTRUM[-1]
            color = QColor(color_hex)
            is_active = (i == self.currentIndex())
            is_enabled = self.isTabEnabled(i)
            # Reserve 1px on the right of every tab except the last so per-tab
            # fills don't paint into the leading pixel of the next tab.
            right_inset = 0 if i == self.count() - 1 else 1
            paint_w = rect.width() - right_inset

            # Disabled tab: dim background overlay and skip accent
            if not is_enabled:
                overlay = QColor(pal["disabled_overlay"])
                overlay.setAlpha(160)
                p.fillRect(rect.x(), rect.y(), paint_w, rect.height(), overlay)

                if i < self.count() - 1:
                    p.setPen(QPen(QColor(pal["sep"]), 1))
                    p.drawLine(rect.x() + rect.width() - 1, rect.y() + 8,
                               rect.x() + rect.width() - 1,
                               rect.y() + rect.height() - 8)

                p.setPen(QColor(pal["disabled_text"]))
                font: QFont = self.font()
                font.setFamilies(["Inter"])
                font.setPixelSize(13)
                font.setWeight(QFont.Weight.Medium)
                p.setFont(font)
                label_rect = rect.adjusted(8, 3, -8, -2)
                p.drawText(label_rect, int(Qt.AlignmentFlag.AlignCenter), self.tabText(i))
                continue

            # Active tab: per-mode 1px shift so the colored overlay reads
            # correctly aligned in each theme. Light mode shrinks the right
            # edge by 1; dark mode extends the left edge by 1 (when there's
            # a previous tab to extend into).
            if is_active:
                if self._mode == "light":
                    overlay_x = rect.x()
                    overlay_w = paint_w - 1
                elif i > 0:
                    overlay_x = rect.x() - 1
                    overlay_w = paint_w + 1
                else:
                    overlay_x = rect.x()
                    overlay_w = paint_w

                p.fillRect(overlay_x, rect.y(), overlay_w, rect.height(),
                           QColor(pal["active_bg"]))
                tint = QColor(color)
                tint.setAlpha(15)
                p.fillRect(overlay_x, rect.y(), overlay_w, rect.height(), tint)

            # Top accent strip (3px)
            strip_h = 3
            if is_active:
                p.fillRect(overlay_x, rect.y(),
                           overlay_w, strip_h, color)
            else:
                # Inactive: very faint colored hint
                hint = QColor(color)
                hint.setAlpha(60)
                p.fillRect(rect.x(), rect.y() + 1,
                           paint_w, 2, hint)

            # Vertical separator on the right edge of every tab except last
            if i < self.count() - 1:
                p.setPen(QPen(QColor(pal["sep"]), 1))
                p.drawLine(rect.x() + rect.width() - 1, rect.y() + 8,
                           rect.x() + rect.width() - 1,
                           rect.y() + rect.height() - 8)

            # Active underline glow
            if is_active:
                under = QColor(color)
                under.setAlpha(120)
                p.fillRect(overlay_x + 14, rect.y() + rect.height() - 4,
                           overlay_w - 28, 1, under)

            # Label
            text_color = pal["text_active"] if is_active else pal["text_inactive"]
            p.setPen(QColor(text_color))
            font = self.font()
            font.setFamilies(["Inter"])
            font.setPixelSize(13)
            font.setWeight(QFont.Weight.DemiBold if is_active
                           else QFont.Weight.Medium)
            p.setFont(font)
            label_rect = rect.adjusted(8, strip_h, -8, -2)
            p.drawText(label_rect,
                       int(Qt.AlignmentFlag.AlignCenter),
                       self.tabText(i))

        p.end()

    # ------------------------------------------------------------------
    # Helpers — used by Workspace tinting in the body of each tab
    # ------------------------------------------------------------------
    @staticmethod
    def color_for(index: int) -> str:
        if 0 <= index < len(SPECTRUM):
            return SPECTRUM[index]
        return SPECTRUM[-1]
