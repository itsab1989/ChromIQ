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

from ui import index_rule

SPECTRUM = [
    "#ff4573",  # Create Chart
    "#ffb42d",  # Print Chart
    "#56d6a5",  # Measure
    "#37bcd6",  # Build Profile
    "#9f82ff",  # Check & Refine
]

LABEL_COLOR    = "#909090"
SUBLABEL_COLOR = "#606060"


def _palette() -> "tuple[str, str, QColor, QColor]":
    """``(label, sublabel, filled, empty)`` for the appearance on screen.

    THIS BAR IS A SPECTRUM SITE AND ALSO A PROGRESS READOUT, which is why the
    chosen accent draft fits it exactly: five segments filled left to right
    already *is* the Index rule, drawn fat. In Neutral it keeps its geometry
    and loses its hues — filled cells in ACTION, unreached ones in BORDER_HI at
    28 %, the same two values every other site uses.

    The two label greys move too, and not for tidiness: `#909090` is **2.53:1**
    on the Neutral panel and `#606060` is 5.13:1. In this theme low contrast
    means "disabled" and nothing else, and a bar that is building is the
    opposite of disabled — so they become TEXT_DIM and TEXT_FAINT. Light and
    Dark keep both greys.
    """
    if index_rule.use_index_rule():
        from ui import neutral_styles
        filled, empty = index_rule.rule_colours()
        return (neutral_styles.NM_TEXT_DIM, neutral_styles.NM_TEXT_FAINT,
                filled, empty)
    return LABEL_COLOR, SUBLABEL_COLOR, QColor(), QColor()


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
    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        label_col, sub_col, index_filled, index_empty = _palette()
        neutral = index_rule.use_index_rule()

        # Top row: label + sub
        p.setPen(QColor(label_col))
        font = self.font()
        font.setPixelSize(10)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        font.setCapitalization(QFont.Capitalization.AllUppercase)
        p.setFont(font)
        p.drawText(QRectF(0, 0, self.width(), 14),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   self._label)

        if self._sub:
            p.setPen(QColor(sub_col))
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
        n = len(SPECTRUM)
        seg_w = (self.width() - gap * (n - 1)) / n

        # Segments
        if self._value is None:
            # Indeterminate: pulse outward from current phase
            for i, hex_col in enumerate(SPECTRUM):
                if neutral:
                    # THE PULSE CANNOT BE A FADE HERE. Fading ACTION toward
                    # the panel makes a "faint" cell LIGHTER than an unreached
                    # one (ACTION at 18 % lands at L* 196; BORDER_HI at 28 %
                    # lands at 182), so the dimmest cell would out-shine the
                    # empty ones — backwards, and against rule 1. It sweeps
                    # instead: cells fill up to the phase and start again, so
                    # the animation IS the Index rule, moving.
                    col = QColor(index_filled if i <= self._phase
                                 else index_empty)
                else:
                    col = QColor(hex_col)
                    dist = abs(i - self._phase)
                    col.setAlphaF(max(0.18, 1.0 - dist * 0.32))
                rect = QRectF(i * (seg_w + gap), bar_y, seg_w, bar_h)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                p.drawRoundedRect(rect, bar_h / 2, bar_h / 2)
        else:
            # Determinate: fill segments left-to-right based on value
            filled = self._value * n
            for i, hex_col in enumerate(SPECTRUM):
                col = QColor(index_empty if neutral else hex_col)
                if i + 1 <= filled:
                    col = QColor(index_filled) if neutral else QColor(hex_col)
                    if not neutral:
                        col.setAlphaF(1.0)
                elif i < filled:
                    # Partial segment: render full faint + clip a colored slice
                    pass
                elif not neutral:
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
                    full = QColor(index_filled) if neutral else QColor(hex_col)
                    if not neutral:
                        full.setAlphaF(1.0)
                    p.setBrush(full)
                    p.drawRoundedRect(fill_rect, bar_h / 2, bar_h / 2)

        p.end()
