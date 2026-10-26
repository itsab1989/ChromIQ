"""A long message box text is not set all in bold.

Qt sets a QMessageBox's text in bold on macOS, every word of it, so a
forty-line warning read as one shout (seen on screen in 4.3.15 and in the
4.3.16 drives). Basti, 2026-10-26: *"some shorter texts might be ok
completely bold if it is justified by the importance of the message. but very
long text should not be completely bold"*. `keep_message_box_inside_the_work_
area`, which warn(), inform() and ask() all go through, keeps the bold for a
text that fits on one line of the box and sets anything longer regular.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox


@pytest.fixture
def _app():
    return QApplication.instance() or QApplication([])


def _label(box):
    return box.findChild(QLabel, "qt_msgbox_label")


def _bold_after(text: str, rich: bool = False) -> bool:
    from ui import widgets
    box = QMessageBox()
    if rich:
        box.setTextFormat(Qt.TextFormat.RichText)
    box.setText(text)
    if not _label(box).font().bold():
        box.deleteLater()
        pytest.skip("this platform does not set a message box's text bold")
    widgets.keep_message_box_inside_the_work_area(box)
    bold = _label(box).font().bold()
    box.deleteLater()
    return bold


def test_a_short_one_line_message_stays_bold(_app):
    assert _bold_after("Another process is already running.")


def test_a_message_of_several_lines_is_regular(_app):
    assert not _bold_after("The chart could not be read.\n\nIt has no patches.")


def test_one_long_wrapped_sentence_is_regular(_app):
    assert not _bold_after("This sentence goes on " * 30)


def test_a_shortened_box_stays_regular(_app):
    from ui import widgets
    work = _app.primaryScreen().availableGeometry().height()
    text = "First paragraph.\n\n" + "\n".join(
        f"Line {i} of a long report." for i in range(work // 8))
    box = QMessageBox()
    box.setText(text)
    widgets.keep_message_box_inside_the_work_area(box)
    assert box.detailedText() == text
    assert not _label(box).font().bold()
    box.deleteLater()


def test_rich_text_is_left_to_its_own_weights(_app):
    assert _bold_after("<p>" + "word " * 200 + "</p>", rich=True)
