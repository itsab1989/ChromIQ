"""`keep_message_box_inside_the_work_area` must finish its work on a box it
shortens, and must not move a rich-text body behind "Show Details".

Found 2026-10-26 driving the verification pre-flight on screen in German
(work area 1083 px, box 1275 px): the log said "could not fit the message box
to the work area" with ``RuntimeError: wrapped C/C++ object of type QGridLayout
has been deleted``. ``QMessageBox.setDetailedText`` builds the box a new grid
layout and deletes the old one, so step 2 called ``activate()`` on a dead
wrapper, on every box it shortened; the exception was swallowed and step 3,
the frame clamp, was never scheduled. And because the pre-flight is one line
of HTML, step 2 also put that HTML, tags and all, into Qt's plain-text
details pane.
"""
from __future__ import annotations

import logging

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox


@pytest.fixture
def _app():
    return QApplication.instance() or QApplication([])


def _too_tall(_app) -> int:
    work = _app.primaryScreen().availableGeometry().height()
    return max(80, work // 8)


def test_a_long_plain_box_is_shortened_without_an_error(_app, caplog,
                                                        monkeypatch):
    from ui import widgets
    scheduled = []
    monkeypatch.setattr("PyQt6.QtCore.QTimer.singleShot",
                        lambda ms, fn: scheduled.append(fn))
    first = "The first paragraph says what happened, on its own."
    rest = "\n\n".join(f"Paragraph {i} adds a detail." for i in range(_too_tall(_app)))
    box = QMessageBox()
    box.setText(first + "\n\n" + rest)
    with caplog.at_level(logging.DEBUG, logger=widgets._log.name):
        widgets.keep_message_box_inside_the_work_area(box)
    assert not [r for r in caplog.records
                if "could not fit the message box" in r.getMessage()], (
        "the helper hit an error and gave up half way")
    assert box.text() == first
    assert box.detailedText() == first + "\n\n" + rest
    assert scheduled, "step 3 (the frame clamp) was never scheduled"
    lay = box.layout()
    spacers = [lay.itemAt(i).spacerItem() for i in range(lay.count())
               if lay.itemAt(i).spacerItem()]
    assert any(s.sizeHint().width() > 0 for s in spacers), (
        "the width step 1 asked for was lost with the old layout")
    box.deleteLater()


def test_a_rich_text_body_never_goes_behind_show_details(_app, caplog,
                                                         monkeypatch):
    from ui import widgets
    scheduled = []
    monkeypatch.setattr("PyQt6.QtCore.QTimer.singleShot",
                        lambda ms, fn: scheduled.append(fn))
    html = "".join(f"<p>Paragraph {i} of a rich text body.</p>"
                   for i in range(_too_tall(_app)))
    box = QMessageBox()
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setText(html)
    with caplog.at_level(logging.DEBUG, logger=widgets._log.name):
        widgets.keep_message_box_inside_the_work_area(box)
    assert not box.detailedText(), "markup was put in the plain details pane"
    assert box.text() == html
    assert scheduled, "the frame clamp was not scheduled"
    assert not [r for r in caplog.records
                if "could not fit the message box" in r.getMessage()]
    box.deleteLater()
