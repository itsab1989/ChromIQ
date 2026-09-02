"""Spectrum-segments progress bar — variant B from the design exploration.

Five colored chunks light up sequentially while pulsing. Used while
colprof is building (Tab 4 · Build Profile). Optionally drives a
determinate fill from 0..1 if a percentage is known.

Usage:

    from ui.spectrum_progress import SpectrumSegmentsBar

    self.progress = SpectrumSegmentsBar(self)
    self.progress.set_label("Building", "ETA 18 s · pass 2/3")
    self.progress.start()        # begin animation (indeterminate)
    # ...later:
    self.progress.set_value(0.42)  # determinate
    self.progress.stop()           # freeze animation
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

SPECTRUM = [
    "#ff4573",  # Create Chart
    "#ffb42d",  # Print Chart
    "#56d6a5",  # Measure
    "#37bcd6",  # Build Profile
    "#9f82ff",  # Check & Refine
]

LABEL_COLOR    = "#909090"
SUBLABEL_COLOR = "#606060"


class SpectrumSegmentsBar(QWidget):
    """Five-segment animated progress bar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(46)
        self._phase: int = 0
        self._value: float | None = None  # None = indeterminate
        self._label = "Building"
        self._sub   = ""
        self._timer = QTimer(self)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def reset(self) -> None:
        self._value = None
        self._phase = 0
        self.update()

    def set_value(self, v: float | None) -> None:
        """Set determinate progress (0.0–1.0) or None for indeterminate."""
        if v is None:
            self._value = None
        else:
            self._value = max(0.0, min(1.0, float(v)))
        self.update()

    def set_label(self, label: str, sub: str = "") -> None:
        self._label = label
        self._sub = sub
        self.update()

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        self._phase = (self._phase + 1) % len(SPECTRUM)
        self.update()

    # ------------------------------------------------------------------
    def _palette(self) -> "tuple[list[str], str, str]":
        """``(segment colours, label, sub-label)`` for the appearance on screen.

        The bar is ALREADY the handoff's five-cell geometry — five segments,
        a gap, filled left to right — so Neutral needs no new component, only
        the hue taken out: every cell is ACTION, and the two labels become dark
        ink instead of the dark theme's greys (``#909090`` is 3.0:1 on this
        theme's surface, and nothing that works may be faint).
        """
        from ui.theme import APPEARANCE_NEUTRAL, active_mode
        if active_mode() != APPEARANCE_NEUTRAL:
            return SPECTRUM, LABEL_COLOR, SUBLABEL_COLOR
        from ui import neutral_styles as _n
        return ([_n.NM_ACTION] * len(SPECTRUM), _n.NM_TEXT_DIM, _n.NM_TEXT_FAINT)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        spectrum, label_color, sublabel_color = self._palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Top row: label + sub
        p.setPen(QColor(label_color))
        font = self.font()
        font.setPixelSize(10)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        font.setCapitalization(QFont.Capitalization.AllUppercase)
        p.setFont(font)
        p.drawText(QRectF(0, 0, self.width(), 14),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   self._label)

        if self._sub:
            p.setPen(QColor(sublabel_color))
            sub_text = self._sub
            if self._value is not None:
                pct = int(self._value * 100)
                sub_text = f"{pct}% · {self._sub}" if self._sub else f"{pct}%"
            p.drawText(QRectF(0, 0, self.width(), 14),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                       sub_text)

        # Bar geometry
        bar_y = 22
        bar_h = 14
        gap = 4
        n = len(spectrum)
        seg_w = (self.width() - gap * (n - 1)) / n

        # Segments
        if self._value is None:
            # Indeterminate: pulse outward from current phase
            for i, hex_col in enumerate(spectrum):
                col = QColor(hex_col)
                dist = abs(i - self._phase)
                intensity = max(0.18, 1.0 - dist * 0.32)
                col.setAlphaF(intensity)
                rect = QRectF(i * (seg_w + gap), bar_y, seg_w, bar_h)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                p.drawRoundedRect(rect, bar_h / 2, bar_h / 2)
        else:
            # Determinate: fill segments left-to-right based on value
            filled = self._value * n
            for i, hex_col in enumerate(spectrum):
                col = QColor(hex_col)
                if i + 1 <= filled:
                    col.setAlphaF(1.0)
                elif i < filled:
                    # Partial segment: render full faint + clip a colored slice
                    pass
                else:
                    col.setAlphaF(0.18)
                rect = QRectF(i * (seg_w + gap), bar_y, seg_w, bar_h)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                p.drawRoundedRect(rect, bar_h / 2, bar_h / 2)
                # Partial fill on the active segment
                if i < filled < i + 1:
                    frac = filled - i
                    fill_rect = QRectF(rect.x(), rect.y(),
                                       rect.width() * frac, rect.height())
                    full = QColor(hex_col)
                    full.setAlphaF(1.0)
                    p.setBrush(full)
                    p.drawRoundedRect(fill_rect, bar_h / 2, bar_h / 2)

        p.end()
