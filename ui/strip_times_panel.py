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

The panel knows nothing about measuring: it is given strip indices, the texts,
and a *position provider* answering "where is strip N right now?", so its
geometry can be tested without an instrument.

Positions are resolved at PAINT time, never stored. Storing them looked fine
until the panel's own appearance re-fitted the preview a little smaller — the
strips compressed, the stored positions kept the old, wider spacing, and every
time drifted further right of its strip the further along the sheet it sat
(Sebastian, 2026-08-11: "they tend to start more on the left and then go more
to the right"). Live resolution also makes the times follow every window
resize for free.
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QEvent, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import QWidget


class StripTimesPanel(QWidget):
    """Per-strip reading times, drawn on their sides under the preview."""

    #: room around the rotated times
    PAD_TOP = 10
    PAD_BOTTOM = 8
    #: gap between the times and the verdict line
    GAP = 6
    #: vertical gap between the two staggered bands on a small preview
    BAND_GAP = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = ""
        self._reference: "QWidget | None" = None
        self._provider: "Callable[[], list[int]] | None" = None
        # (strip index on the current page, "5.1 s", drawn-at-all-costs?)
        self._columns: list[tuple[int, str, bool]] = []
        self._verdict = ""
        self._verdict_colour = "#909090"
        self._muted = "#909090"
        self._frame = "#3a3a3a"          # the faint border around this area
        #: how many staggered bands the last paint needed (1 = normal)
        self._bands = 1
        self.setVisible(False)

    # ---- content ----------------------------------------------------------
    def set_reference_widget(self, widget: "QWidget | None") -> None:
        """The widget whose coordinate space the provider's x values live in —
        the chart preview. The translation into THIS panel's space happens at
        paint time, when both widgets' geometry is real: mapping at
        set_content time returned identity while the panel was still hidden
        with unset geometry, and every time sat a constant 21 px right of its
        strip (Sebastian, 2026-08-11). The panel watches the reference for
        resizes so the times move the moment the preview does."""
        if self._reference is not None:
            self._reference.removeEventFilter(self)
        self._reference = widget
        if widget is not None:
            widget.installEventFilter(self)

    def set_position_provider(
            self, provider: "Callable[[], list[int]] | None") -> None:
        """A callable answering, right now, where each strip of the current
        page sits — a list of x centres in the reference widget's coordinates,
        indexed by strip position. Queried fresh on every paint."""
        self._provider = provider

    def eventFilter(self, obj, ev) -> bool:      # noqa: N802
        if obj is self._reference and ev.type() in (
                QEvent.Type.Resize, QEvent.Type.Move):
            self.update()
        return False

    def set_content(self, label: str, columns, verdict: str = "",
                    verdict_colour: str = "#909090") -> None:
        """Show *columns* — ``(strip_index, text)`` or
        ``(strip_index, text, important)`` tuples. *important* marks a time
        that must stay visible even when strips sit too close for every label
        (a too-fast warning is the whole point of the panel).

        *label* may carry a newline; it is drawn as two lines so a long caption
        cannot run into the first strip's time on charts whose strips start
        close to the page edge (Knut, #131 2026-07-27).
        """
        self._label = label or ""
        self._columns = [(int(c[0]), str(c[1]),
                          bool(c[2]) if len(c) > 2 else False)
                         for c in columns]
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
        return max(fm.horizontalAdvance(t) for _i, t, _imp in self._columns)

    def _time_font(self) -> QFont:
        """The times are read at a glance while measuring, so they are set at
        the interface's normal size — not smaller (Knut, #131 2026-07-27)."""
        return QFont(self.font())

    def _muted_ink(self) -> str:
        """The times' ink for the appearance on screen NOW.

        THIS PANEL IS ONLY EVER ON SCREEN WHILE A STRIP IS BEING READ, so no
        pixel census has drawn it — and the census would not have flagged it if
        one had: `#909090` is a perfect grey, chroma 0, and an instrument that
        looks for hue cannot see that a grey is the wrong LIGHTNESS. It is
        2.53:1 on the Neutral panel, where low contrast means "disabled" and
        nothing else (handoff rule 3) — and a time being written under a strip
        as you swipe it is the opposite of disabled. `ui.spectrum_progress`
        moved its two label greys for exactly this reason.

        Asked at paint time so the panel follows an appearance switched under
        it. Light and Dark get `#909090` straight back from `ink_for`.
        """
        from ui.theme import ink_for
        return ink_for(self._muted, level="dim")

    def sizeHint(self) -> QSize:      # noqa: N802
        if not self._columns and not self._verdict:
            return QSize(200, 0)      # nothing to say: take no room at all
        th = self._times_height()
        return QSize(200, max(0, self.PAD_TOP + th * self._bands
                              + (self._bands - 1) * self.BAND_GAP
                              + self.PAD_BOTTOM))

    def minimumSizeHint(self) -> QSize:      # noqa: N802
        """The same as the hint: this panel must never be given less than it
        draws. It used to hold the verdict too, and that was always the first
        thing a squeeze removed (Knut saw it vanish three times) — the verdict
        is now a label of its own in the layout, which cannot be painted over
        the edge of anything."""
        return self.sizeHint()

    @staticmethod
    def _column_translate_x(x: int, fm: QFontMetrics) -> int:
        """Where to translate so the rotated glyph column is CENTRED on *x*.

        After ``rotate(90)`` a glyph column drawn at the origin occupies
        widget-x from ``tx - descent`` to ``tx + ascent`` — its visual centre
        sits at ``tx + (ascent - descent) / 2``, not at ``tx``. The old
        ``x + height/3`` nudge compounded that: every time sat ~10 px right
        of its strip before the panel-offset was even counted (Sebastian
        remembered the times "very far right of the strip" — measured
        2026-08-11 at +21 px, constant across strips)."""
        return x - (fm.ascent() - fm.descent()) // 2

    def _placed_columns(self, dx: int, fm: QFontMetrics
                        ) -> list[tuple[int, str, bool, int]]:
        """The columns as they will be drawn RIGHT NOW — ``(x, text,
        important, band)``: each strip index resolved through the position
        provider's current answer and shifted into this panel's space.

        While every rotated label has room, everything sits in one band
        (band 0). On a small preview, where strips sit closer than a label
        is wide, the labels split into TWO staggered bands — odd strips a
        label-length lower — which halves the room each one needs before
        any label has to be dropped ("for this very small one we still need
        a solution" — Sebastian, 2026-08-11). Only when even that is not
        enough are ordinary times thinned; a too-fast warning never is.

        Updates ``self._bands`` so sizeHint asks for the extra band's room.
        """
        if self._provider is None:
            return []
        try:
            xs = list(self._provider())
        except Exception:      # noqa: BLE001 — never break a paint
            return []
        placed = [(xs[i] + dx, text, important)
                  for i, text, important in self._columns
                  if 0 <= i < len(xs)]
        placed.sort()
        # A rotated glyph column needs about a line-height of horizontal room.
        min_gap = fm.height() + 1
        fits = all(b[0] - a[0] >= min_gap for a, b in zip(placed, placed[1:]))
        if fits and self._bands == 2 and len(placed) > 1:
            # hysteresis: drop back to one band only with room to spare, so a
            # width sitting exactly on the boundary cannot flip-flop (the
            # panel's own height changes the preview's, which changes this).
            fits = all(b[0] - a[0] >= min_gap * 1.2
                       for a, b in zip(placed, placed[1:]))
        if fits:
            self._bands = 1
            return [(x, t, imp, 0) for x, t, imp in placed]
        self._bands = 2
        out: list[tuple[int, str, bool, int]] = []
        for band in (0, 1):
            cols = placed[band::2]
            out += [(x, t, imp, band)
                    for x, t, imp in self._thin_columns(cols, min_gap)]
        out.sort()
        return out

    @staticmethod
    def _thin_columns(placed: list[tuple[int, str, bool]], min_gap: int
                      ) -> list[tuple[int, str, bool]]:
        """When the preview is small enough that strips sit closer than a
        label is wide, drawing every time turns the panel into overlapping
        ink. Keep every important time (a too-fast warning must never be
        thinned away), then as many of the rest as genuinely fit."""
        keep = [c for c in placed if c[2]]
        for c in placed:
            if not c[2] and all(abs(c[0] - k[0]) >= min_gap for k in keep):
                keep.append(c)
        keep.sort()
        return keep

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
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        # No frame of its own any more: it lives inside a group box that looks
        # like every other framed panel in the window, and the box's title
        # carries the caption (Knut, #131 2026-07-27 — "replace this hard box
        # with a frame, same frames used in left part of the window").
        times_h = self._times_height()

        dx = 0
        if self._reference is not None:
            try:
                from PyQt6.QtCore import QPoint
                dx = self.mapFromGlobal(
                    self._reference.mapToGlobal(QPoint(0, 0))).x()
            except Exception:      # noqa: BLE001 — never break a paint
                dx = 0

        if self._columns:
            p.setFont(self._time_font())
            p.setPen(QColor(self._muted_ink()))
            fm = QFontMetrics(self._time_font())
            placed = self._placed_columns(dx, fm)
            # _placed_columns may have changed the band count, and polish may
            # have changed the font — re-request the height this paint needs
            # (equality, not only growth: dropping back to one band must give
            # the preview its room back).
            want = self.sizeHint().height()
            if want != self.minimumHeight():
                self.setMinimumHeight(want)
                self.updateGeometry()
            for x, text, _important, band in placed:
                # A quarter-turn clockwise: the text starts at the top of the
                # panel and reads downwards, so it sits in the strip's own
                # column however narrow that column is. Band 1 (a small
                # preview's every second strip) starts a label-length lower.
                p.save()
                p.translate(self._column_translate_x(x, fm),
                            self.PAD_TOP + band * (times_h + self.BAND_GAP))
                p.rotate(90)
                p.drawText(0, 0, text)
                p.restore()

            if self._label and placed:
                # Centred on the block of times, at the left edge — and never
                # allowed to run into the first strip's time, which owns its x.
                p.setPen(QColor(self._muted_ink()))
                lfm = QFontMetrics(self._time_font())
                lines = self._label.split("\n")
                room = min(x for x, _t, _i, _b in placed) - 8
                if room > 20:
                    block = lfm.height() * len(lines)
                    top = self.PAD_TOP + max(0, (times_h - block) // 2)
                    for i, line in enumerate(lines):
                        p.drawText(0, top + lfm.ascent() + i * lfm.height(),
                                   lfm.elidedText(line, Qt.TextElideMode.ElideRight,
                                                  room))

        p.end()
