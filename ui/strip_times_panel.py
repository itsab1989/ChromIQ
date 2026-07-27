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
    PAD_TOP = 10
    PAD_BOTTOM = 8
    #: gap between the times and the verdict line
    GAP = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = ""
        self._columns: list[tuple[int, str]] = []      # (widget x, "5.1 s")
        self._verdict = ""
        self._verdict_colour = "#909090"
        self._muted = "#909090"
        self._frame = "#3a3a3a"          # the faint border around this area
        self.setVisible(False)

    # ---- content ----------------------------------------------------------
    def set_content(self, label: str, columns, verdict: str = "",
                    verdict_colour: str = "#909090") -> None:
        """Show *columns* — ``(x, text)`` pairs in this widget's coordinates.

        *label* may carry a newline; it is drawn as two lines so a long caption
        cannot run into the first strip's time on charts whose strips start
        close to the page edge (Knut, #131 2026-07-27).
        """
        self._label = label or ""
        self._columns = [(int(x), str(t)) for x, t in columns]
        self._verdict = verdict or ""      # kept for callers; drawn by the host
        self._verdict_colour = verdict_colour
        self.setVisible(bool(self._columns))
        # A layout may shrink a widget to its minimum, and the verdict line is
        # what disappears first when it does — so the minimum IS what we draw
        # (Knut saw the red warning vanish twice). setMinimumHeight forces it,
        # where minimumSizeHint alone can still be overridden by a stretch.
        self.setMinimumHeight(self.sizeHint().height())
        self.updateGeometry()
        self.update()

    def clear(self) -> None:
        self.set_content("", [])

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
        return QSize(200, max(0, self.PAD_TOP + self._times_height()
                              + self.PAD_BOTTOM))

    def minimumSizeHint(self) -> QSize:      # noqa: N802
        """The same as the hint: this panel must never be given less than it
        draws. It used to hold the verdict too, and that was always the first
        thing a squeeze removed (Knut saw it vanish three times) — the verdict
        is now a label of its own in the layout, which cannot be painted over
        the edge of anything."""
        return self.sizeHint()

    # ---- painting ---------------------------------------------------------
    def paintEvent(self, _ev) -> None:      # noqa: N802
        # Font metrics are only final once the widget has been polished, so a
        # height worked out before that can be too small and clip the verdict.
        # Asking for a re-layout here corrects it before anyone sees it — the
        # same trap as style-sheet padding (see the target bar).
        # Font metrics are only final once the widget has been polished, so the
        # height worked out in set_content can be too small — and the verdict is
        # the first thing to fall off the bottom. Re-apply it here, which lands
        # before anyone sees the result.
        want = self.sizeHint().height()
        if want > self.minimumHeight():
            self.setMinimumHeight(want)
            self.updateGeometry()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        # No frame of its own any more: it lives inside a group box that looks
        # like every other framed panel in the window, and the box's title
        # carries the caption (Knut, #131 2026-07-27 — "replace this hard box
        # with a frame, same frames used in left part of the window").
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
                lines = self._label.split("\n")
                room = min(x for x, _t in self._columns) - 8
                if room > 20:
                    block = lfm.height() * len(lines)
                    top = self.PAD_TOP + max(0, (times_h - block) // 2)
                    for i, line in enumerate(lines):
                        p.drawText(0, top + lfm.ascent() + i * lfm.height(),
                                   lfm.elidedText(line, Qt.TextElideMode.ElideRight,
                                                  room))

        p.end()
