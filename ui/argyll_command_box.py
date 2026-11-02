"""The Build Profile tab's ArgyllCMS command box: a read-only text that wraps
ANYWHERE and is exactly as tall as its text.

WHY NOT A QLabel, like the Create Chart box (review round 1, finding 6). A
word-wrapped QLabel breaks a line only at a space or after a sign such as
``/`` or ``-``. A command carries tokens with neither: a description typed
without spaces, a long file name. Such a token became the label's minimum
width, the label grew past the scroll area (whose horizontal bar is off), and
its right border went out of sight at the window's minimum size. Inserting
invisible break characters into the text would have fixed the look and broken
the point of the box: they travel with a copy and turn a pasted path into one
the terminal cannot find. A QTextEdit wraps at any character when a word does
not fit (``WrapAtWordBoundaryOrAnywhere``) and copies exactly the text it was
given.

It keeps the QLabel API the tab and the tests use (``text``/``setText``,
``setTextInteractionFlags``) and the ``#info_profile`` look from the three
theme sheets.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import QFrame, QSizePolicy, QTextEdit, QWidget


class ArgyllCommandBox(QTextEdit):
    """Read-only, selectable, wraps anywhere, as tall as its text."""

    def __init__(self, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self._text = ""
        self.setReadOnly(True)
        self.setAcceptRichText(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.document().setDocumentMargin(0)
        # A box among the settings, not an input: Tab moves past it.
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(40)

    # -- the QLabel side of it ------------------------------------------------
    def text(self) -> str:          # noqa: D401 - QLabel's name
        return self._text

    def setText(self, text: str) -> None:      # noqa: N802 - QLabel's name
        self._text = text
        self.setPlainText(text)
        self._fit_height()

    # -- height follows the text ---------------------------------------------
    def _fit_height(self) -> None:
        doc = self.document()
        doc.setTextWidth(max(1, self.viewport().width()))
        chrome = self.height() - self.viewport().height()
        h = int(math.ceil(doc.size().height())) + max(0, chrome)
        if h != self.height():
            self.setFixedHeight(h)

    def resizeEvent(self, event) -> None:      # noqa: N802 - Qt override
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self._fit_height()

    def changeEvent(self, event) -> None:      # noqa: N802 - Qt override
        super().changeEvent(event)
        from PyQt6.QtCore import QEvent
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.FontChange):
            self._fit_height()

    def showEvent(self, event) -> None:        # noqa: N802 - Qt override
        super().showEvent(event)
        self._fit_height()

    def sizeHint(self) -> QSize:               # noqa: N802 - Qt override
        return QSize(super().sizeHint().width(), self.height())

    def minimumSizeHint(self) -> QSize:        # noqa: N802 - Qt override
        return QSize(40, self.height())
