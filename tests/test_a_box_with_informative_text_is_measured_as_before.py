"""A message box with informative text is measured as in 4.3.15.

Review of 4.3.16: `_message_box_height_once_shown` copies the plain-text part
of `QMessageBoxPrivate::updateSize` and leaves out its informative-text
branch, so a box with `setInformativeText` was estimated at about twice its
real height and could be cut short behind "Show Details" while it fitted. The
Print tab's four §M questions are such boxes. They are measured with
`sizeHint`, exactly as in 4.3.15.
"""
from __future__ import annotations

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QScreen
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox

import pytest

PARA = ("This is a long paragraph explaining what will happen next. " * 6).strip()


@pytest.fixture
def _app():
    return QApplication.instance() or QApplication([])


def _question(paragraphs: int) -> QMessageBox:
    box = QMessageBox()
    box.setWindowTitle("Print the verification chart?")
    box.setText("Print the verification chart?")
    box.setInformativeText("\n\n".join([PARA] * paragraphs))
    box.addButton("Use the macOS Print Dialog", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Print Anyway", QMessageBox.ButtonRole.DestructiveRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    return box


def _title_label(box):
    return next(c for c in box.findChildren(QLabel) if c.text() == box.text())


def test_the_estimate_is_the_size_hint(_app):
    from ui import widgets
    work = _app.primaryScreen().availableGeometry()
    box = _question(6)
    assert widgets._message_box_height_once_shown(
        box, _title_label(box), work) == box.sizeHint().height()
    box.deleteLater()


def test_a_question_that_fits_is_not_cut_short(_app, monkeypatch):
    """A work area with room for the box as it opens, and not for twice it."""
    from ui import widgets
    box = _question(6)
    room_needed = box.sizeHint().height() + 60 + 20
    real = QScreen.availableGeometry

    def short(screen):
        r = real(screen)
        return QRect(r.x(), r.y(), r.width(), min(r.height(), room_needed))
    monkeypatch.setattr(QScreen, "availableGeometry", short)
    title, body = box.text(), box.informativeText()
    widgets.keep_message_box_inside_the_work_area(box)
    assert not box.detailedText(), "a box that fits was moved behind Show Details"
    assert box.text() == title
    assert box.informativeText() == body
    box.deleteLater()
