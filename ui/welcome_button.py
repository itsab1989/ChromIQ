"""Masthead "?" help button.

Twin of the settings gear button: 44x44 QToolButton with a hand-painted
Instrument Serif Bold Italic "?" glyph in spectrum-magenta. Single color
across light + dark themes — magenta is part of the masthead motif.
"""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPaintEvent, QPen,
)
from PyQt6.QtWidgets import QToolButton, QWidget

from ui.styles import SPEC_MAGENTA
from core.i18n import tr


class WelcomeButton(QToolButton):
    """Top-right help button — re-opens the welcome dialog on click."""

    help_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tooltip_btn")
        self.setToolTip(tr("Help — open the welcome menu"))
        self.setFixedSize(QSize(44, 44))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False
        self.clicked.connect(self.help_clicked)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _ev: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # Instrument Serif ships Regular + Italic only — no Bold face. Use a
        # QPainterPath so we can fill *and* stroke the glyph, faking a bolder
        # weight independently of which faces happen to be installed.
        font = QFont()
        font.setFamilies(["Instrument Serif", "Georgia", "Times New Roman", "serif"])
        font.setPixelSize(26)
        font.setItalic(True)

        fm = QFontMetricsF(font)
        glyph = "?"
        # Nudge 1 px up and 2 px left so the italic "?" sits optically aligned
        # with the tools and settings icons to its left (italic slant pushes
        # the glyph's perceived centre slightly right of its geometric centre).
        gx = (self.width() - fm.horizontalAdvance(glyph)) / 2 - 2
        gy = self.height() / 2 + (fm.ascent() - fm.descent()) / 2 - 1

        path = QPainterPath()
        path.addText(float(gx), float(gy), font, glyph)

        # THE MASTHEAD "?" IS PAINTED HERE, not baked into an asset — the one
        # masthead glyph a theme can still reach. In Neutral it takes the single
        # ACTION value like every other accent surface; the magenta measures
        # 2.55:1 on this frame anyway, so it was not carrying the mark there.
        from ui import index_rule
        if index_rule.use_index_rule():
            from ui import neutral_styles
            color = QColor(neutral_styles.NM_ACTION)
        else:
            color = QColor(SPEC_MAGENTA)
        if not self._hover:
            color.setAlpha(230)
        p.setBrush(color)
        p.setPen(QPen(
            color, 0.8,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        ))
        p.drawPath(path)
        p.end()
