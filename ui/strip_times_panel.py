"""The reading-time strip under the chart preview (#131, Knut 2026-07-26).

Each strip's scan time is drawn **under the strip it belongs to**, turned on its
side so that even a chart with thirty-five strips across an A4 landscape page
still has room for every one. Knut's layout:

* one label on the left — *"Strip reading times, 15 patches:"* — rather than
  repeating the patch count against every strip;
* each time rotated a quarter-turn clockwise, reading downwards from the top of
  the panel, centred on its own strip and aligned exactly with the strip labels
  above it;
* the verdict line centred underneath, in the colour of the verdict.

The panel knows nothing about measuring: it is given the x positions and the
texts, so its geometry can be tested without an instrument.
"""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import QWidget


class StripTimesPanel(QWidget):
    """Per-strip reading times, drawn on their sides under the preview."""

    #: room around the rotated times
    PAD_TOP = 6
    PAD_BOTTOM = 4
    #: gap between the times and the verdict line
    GAP = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = ""
        self._columns: list[tuple[int, str]] = []      # (widget x, "5.1 s")
        self._verdict = ""
        self._verdict_colour = "#909090"
        self._muted = "#909090"
        self.setVisible(False)

    # ---- content ----------------------------------------------------------
    def set_content(self, label: str, columns, verdict: str = "",
                    verdict_colour: str = "#909090") -> None:
        """Show *columns* — ``(x, text)`` pairs in this widget's coordinates."""
        self._label = label or ""
        self._columns = [(int(x), str(t)) for x, t in columns]
        self._verdict = verdict or ""
        self._verdict_colour = verdict_colour
        self.setVisible(bool(self._columns or self._verdict))
        self.updateGeometry()
        self.update()

    def clear(self) -> None:
        self.set_content("", [], "")

    # ---- geometry ---------------------------------------------------------
    def _times_height(self) -> int:
        """How tall the rotated times are: the longest text, laid on its side."""
        if not self._columns:
            return 0
        fm = QFontMetrics(self._time_font())
        return max(fm.horizontalAdvance(t) for _x, t in self._columns)

    def _time_font(self) -> QFont:
        """The times are read at a glance while measuring, so they are set at
        the interface's normal size — not smaller (Knut, #131 2026-07-27)."""
        return QFont(self.font())

    def sizeHint(self) -> QSize:      # noqa: N802
        if not self._columns and not self._verdict:
            return QSize(200, 0)      # nothing to say: take no room at all
        h = self.PAD_TOP + self._times_height() + self.PAD_BOTTOM
        if self._verdict:
            h += self.GAP + QFontMetrics(self._verdict_font()).height()
        return QSize(200, max(0, h))

    def minimumSizeHint(self) -> QSize:      # noqa: N802
        """The same as the hint: this panel must never be given less than it
        draws, or the verdict line is the first thing to disappear — which is
        exactly what happened when the layout squeezed it (Knut)."""
        return self.sizeHint()

    def _verdict_font(self) -> QFont:
        f = QFont(self.font())
        f.setPointSizeF(f.pointSizeF() + 3)
        f.setBold(True)
        return f

    # ---- painting ---------------------------------------------------------
    def paintEvent(self, _ev) -> None:      # noqa: N802
        # Font metrics are only final once the widget has been polished, so a
        # height worked out before that can be too small and clip the verdict.
        # Asking for a re-layout here corrects it before anyone sees it — the
        # same trap as style-sheet padding (see the target bar).
        want = self.sizeHint().height()
        if want > self.height():
            self.updateGeometry()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        times_h = self._times_height()

        if self._columns:
            p.setFont(self._time_font())
            p.setPen(QColor(self._muted))
            fm = QFontMetrics(self._time_font())
            for x, text in self._columns:
                # A quarter-turn clockwise: the text starts at the top of the
                # panel and reads downwards, so it sits in the strip's own
                # column however narrow that column is.
                p.save()
                p.translate(x + fm.height() // 3, self.PAD_TOP)
                p.rotate(90)
                p.drawText(0, 0, text)
                p.restore()

            if self._label:
                # Centred on the block of times, at the left edge — and never
                # allowed to run into the first strip's time, which owns its x.
                p.setPen(QColor(self._muted))
                lfm = QFontMetrics(self._time_font())
                y = self.PAD_TOP + (times_h + lfm.ascent()) // 2
                room = min(x for x, _t in self._columns) - 8
                if room > 20:
                    p.drawText(0, y, lfm.elidedText(
                        self._label, Qt.TextElideMode.ElideRight, room))

        if self._verdict:
            p.setFont(self._verdict_font())
            p.setPen(QColor(self._verdict_colour))
            vfm = QFontMetrics(self._verdict_font())
            y = self.PAD_TOP + times_h + self.PAD_BOTTOM + self.GAP + vfm.ascent()
            p.drawText(0, y, self.width(), vfm.height(),
                       int(Qt.AlignmentFlag.AlignHCenter), self._verdict)
        p.end()
