"""The Measure tab's pause note (jctay, forum 149802; Basti 2026-10-23), laid
over the chart preview in the legend chip's own look: the same see-through
panel and the same light words over a dark halo (`ui.see_through`), so the
page shows through and the words read on any patch colour.

Painted, not QLabels: a label cannot carry the halo, and without it the
chip's transparency could not carry the words. The buttons are ordinary
buttons in the bottom row; the ⓘ sits top right.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QFont, QFontMetricsF, QPainter, QPixmap, QTextLayout,
                         QTextOption)
from PyQt6.QtWidgets import QWidget

from ui import see_through

PAD_X = 16
PAD_TOP = 12
PAD_BOTTOM = 12
PARA_GAP = 8
BUTTON_GAP = 10
ICON_ROOM = 30


class _Part:
    """A piece of the note's text, as a label would hold it (tests and
    drivers read it back with ``text()``)."""

    def __init__(self) -> None:
        self._text = ""

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802 - Qt-like on purpose
        self._text = str(text or "")


class PauseNote(QWidget):
    """The note: a headline, paragraphs, a heading with lines under it, and a
    row of buttons (added by the owner with :meth:`set_buttons`)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("pagePauseNote")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.title = _Part()
        self.body = _Part()
        self.found = _Part()
        self._paragraphs: "list[str]" = []
        self._found_head = ""
        self._found_lines: "list[str]" = []
        self._buttons: list = []
        self._icon = None
        self._lines: list = []          # (font, text, x, baseline)
        self._generation = 0            # bumped whenever the lines change
        #: The panel's alpha (see `ui.see_through.NOTE_PANEL_ALPHA`).
        self.panel_alpha = see_through.NOTE_PANEL_ALPHA
        self._laid_width = -1

    # ---- content ----------------------------------------------------
    def set_content(self, title: str, paragraphs: "list[str]",
                    found_head: str, found_lines: "list[str]") -> None:
        self._title = title
        self._paragraphs = [p for p in paragraphs if p]
        self._found_head = found_head
        self._found_lines = list(found_lines)
        self.title.setText(title)
        self.body.setText("\n\n".join(self._paragraphs))
        self.found.setText("\n".join([found_head] + self._found_lines))
        self._laid_width = -1
        self.update()

    def set_buttons(self, left, right, icon=None) -> None:
        self._buttons = [left, right]
        self._generation += 1
        self._icon = icon
        for b in (left, right, icon):
            if b is not None:
                b.setParent(self)

    # ---- fonts ------------------------------------------------------
    def _fonts(self) -> "tuple[QFont, QFont, QFont]":
        base = QFont(self.font())
        title = QFont(base)
        title.setBold(True)
        title.setPointSizeF(base.pointSizeF() * 1.15 if base.pointSizeF() > 0
                            else 14.0)
        bold = QFont(base)
        bold.setBold(True)
        return title, base, bold

    # ---- layout -----------------------------------------------------
    def _wrap(self, font: QFont, text: str, width: float, x: float,
              y: float, indent: float = 0.0) -> "tuple[list, float]":
        """Word-wrapped lines of *text* from *y* down; returns them and the
        y under the last one."""
        out = []
        fm = QFontMetricsF(font)
        layout = QTextLayout(text, font)
        opt = QTextOption()
        opt.setWrapMode(QTextOption.WrapMode.WordWrap)
        layout.setTextOption(opt)
        layout.beginLayout()
        first = True
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(max(40.0, width - (0 if first else indent)))
            seg = text[line.textStart():line.textStart() + line.textLength()]
            out.append((font, seg.rstrip(), x + (0 if first else indent),
                        y + fm.ascent()))
            y += fm.lineSpacing()
            first = False
        layout.endLayout()
        return out, y

    def _layout(self, width: int) -> float:
        """Lay the words out for *width*; returns the height they need."""
        title_f, body_f, bold_f = self._fonts()
        inner = width - 2 * PAD_X
        lines: list = []
        y = float(PAD_TOP)
        t_lines, y = self._wrap(title_f, getattr(self, "_title", ""),
                                inner - ICON_ROOM, PAD_X, y)
        lines += t_lines
        for para in self._paragraphs:
            y += PARA_GAP
            for chunk in para.split("\n"):
                c_lines, y = self._wrap(body_f, chunk, inner, PAD_X, y)
                lines += c_lines
        if self._found_head:
            y += PARA_GAP
            h_lines, y = self._wrap(bold_f if self._found_lines else body_f,
                                    self._found_head, inner, PAD_X, y)
            lines += h_lines
            bullet = "•  "
            ind = QFontMetricsF(body_f).horizontalAdvance(bullet)
            for ln in self._found_lines:
                f_lines, y = self._wrap(body_f, bullet + ln, inner, PAD_X, y,
                                        indent=ind)
                lines += f_lines
        self._lines = lines
        self._generation += 1
        self._laid_width = width
        return y

    def height_for_width(self, width: int) -> int:
        words = self._layout(width)
        row = max([b.sizeHint().height() for b in self._buttons if b] + [32])
        return int(words + BUTTON_GAP + row + PAD_BOTTOM + 1)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_children()

    def _place_children(self) -> None:
        w, h = self.width(), self.height()
        row_h = max([b.sizeHint().height() for b in self._buttons if b] + [32])
        y = h - PAD_BOTTOM - row_h
        if len(self._buttons) == 2:
            left, right = self._buttons
            # ONE HEIGHT FOR BOTH, the taller one's, so a primary button and a
            # plain one never stand at different heights in the same row
            for b in (left, right):
                if b is not None:
                    b.setFixedHeight(row_h)
            if left is not None:
                lw = max(left.sizeHint().width(), 120)
                left.setGeometry(PAD_X, y, lw, row_h)
            if right is not None:
                rw = max(right.sizeHint().width(), 160)
                right.setGeometry(w - PAD_X - rw, y, rw, row_h)
        if self._icon is not None:
            s = self._icon.sizeHint()
            self._icon.setGeometry(w - PAD_X - s.width(), PAD_TOP,
                                   s.width(), s.height())

    # ---- paint ------------------------------------------------------
    #
    # PAINTED ONCE, THEN COPIED (Basti, 2026-10-23: "the fade in and out of
    # the overlay sometimes does not look smooth"). Every line of the note is
    # a glyph outline stroked for its halo and filled again, and drawing the
    # whole note that way took 140 to 170 ms, measured on screen. The fade
    # (an opacity effect over the note) asks for a full paint on EVERY step,
    # so a 110 ms fade got one or two frames, 150 ms apart: a jump, not a
    # fade. The note is now drawn into a picture when its text, size, panel
    # or screen changes, and each paint only copies that picture (well under
    # a millisecond). `prepare()` draws it before the fade starts, so not even
    # the first step waits for it.
    def _cache_key(self) -> tuple:
        return (self.width(), self.height(), float(self.devicePixelRatioF()),
                int(self.panel_alpha), self._laid_width, self._generation)

    def prepare(self) -> None:
        """Draw the note's picture now (before a fade), if it is out of date."""
        if self.width() <= 0 or self.height() <= 0:
            return
        if self._laid_width != self.width():
            self._layout(self.width())
        if getattr(self, "_picture_key", None) == self._cache_key():
            return
        dpr = float(self.devicePixelRatioF())
        pic = QPixmap(max(1, int(round(self.width() * dpr))),
                      max(1, int(round(self.height() * dpr))))
        pic.setDevicePixelRatio(dpr)
        pic.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pic)
        self._paint_into(painter)
        painter.end()
        self._picture = pic
        self._picture_key = self._cache_key()

    def _paint_into(self, painter: QPainter) -> None:
        see_through.paint_panel(painter, self.rect(), 1.0, self.panel_alpha)
        row_h = max([b.sizeHint().height() for b in self._buttons if b] + [32])
        limit = self.height() - PAD_BOTTOM - row_h - BUTTON_GAP / 2
        for font, text, x, baseline in self._lines:
            if baseline > limit:
                break               # the rest is in the ⓘ, never under a button
            see_through.paint_halo_text(painter, x, baseline, font, text)

    def paintEvent(self, event) -> None:  # noqa: N802
        self.prepare()
        pic = getattr(self, "_picture", None)
        if pic is None:
            return
        painter = QPainter(self)
        painter.drawPixmap(0, 0, pic)
        painter.end()
