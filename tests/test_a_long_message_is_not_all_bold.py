"""A long message box text is not set all in bold; a short one is as in 4.3.15.

Qt sets a QMessageBox's text in bold on macOS, every word of it, so a
forty-line warning read as one shout (seen on screen in 4.3.15 and in the
4.3.16 drives). Basti, 2026-10-26: *"some shorter texts might be ok
completely bold if it is justified by the importance of the message. but very
long text should not be completely bold"*. `keep_message_box_inside_the_work_
area`, which warn(), inform() and ask() all go through, keeps the bold for a
text of up to `_MESSAGE_BOX_BOLD_MAX_LINES` lines AS SHOWN, and sets anything
longer regular.

Review of 4.3.16: the first cut decided by "\\n", so "Delete this run?\\n\\n
This cannot be undone." lost the bold it has in 4.3.15. Lines are counted as
the box shows them, and on the text it shows (a shortened box's head).
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


def _box(text: str, rich: bool = False) -> QMessageBox:
    box = QMessageBox()
    if rich:
        box.setTextFormat(Qt.TextFormat.RichText)
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    if not _label(box).font().bold():
        box.deleteLater()
        pytest.skip("this platform does not set a message box's text bold")
    return box


def _bold_after(text: str, rich: bool = False) -> bool:
    from ui import widgets
    box = _box(text, rich)
    widgets.keep_message_box_inside_the_work_area(box)
    bold = _label(box).font().bold()
    box.deleteLater()
    return bold


def _shown_lines(text: str, app) -> int:
    """The lines the text takes in a box shown as 4.3.15 shows it (bold)."""
    from PyQt6.QtGui import QFontMetrics
    box = _box(text)
    box.show()
    app.processEvents()
    lab = _label(box)
    n = round(lab.height() / QFontMetrics(lab.font()).lineSpacing())
    box.close()
    box.deleteLater()
    app.processEvents()
    return n


def test_a_short_one_line_message_stays_bold(_app):
    assert _bold_after("Another process is already running.")


@pytest.mark.parametrize("text", [
    "Delete this run?\n\nThis cannot be undone.",
    "Diesen Lauf löschen?\n\nDas lässt sich nicht rückgängig machen.",
    "The chart could not be read.\n\nIt has no patches.",
    "Nothing was changed.\n\nReason: the file is read-only.",
])
def test_a_short_question_of_two_paragraphs_stays_bold(_app, text):
    assert _bold_after(text)


def test_five_lines_stay_bold_and_six_do_not(_app):
    from ui import widgets
    limit = widgets._MESSAGE_BOX_BOLD_MAX_LINES
    assert limit == 5
    def lines(n):
        return "\n".join(f"Line {i} of a short notice." for i in range(n))
    assert _shown_lines(lines(limit), _app) == limit
    assert _bold_after(lines(limit))
    assert _shown_lines(lines(limit + 1), _app) == limit + 1
    assert not _bold_after(lines(limit + 1))


def test_the_count_is_the_lines_the_box_shows(_app):
    """Wrapped paragraphs, not line breaks: the estimate is what Qt shows."""
    from ui import widgets
    for n in (1, 2, 3, 6):
        text = "\n\n".join(["A sentence that is long enough to wrap " * 4] * n)
        box = _box(text)
        work = box.screen().availableGeometry()
        est = widgets._message_box_text_lines_once_shown(box, _label(box), work)
        box.deleteLater()
        assert est == _shown_lines(text, _app), n


def test_a_long_report_is_regular(_app):
    assert not _bold_after("\n".join(
        f"Line {i} of a moderately long warning." for i in range(12)))


def test_one_long_wrapped_sentence_is_regular(_app):
    assert not _bold_after("This sentence goes on " * 120)


def test_a_shortened_box_shows_a_short_head_in_bold(_app):
    """Step 2 keeps the first paragraph and moves the rest behind Show
    Details: the head the box shows is a short box like any other."""
    from ui import widgets
    work = _app.primaryScreen().availableGeometry().height()
    text = "First paragraph.\n\n" + "\n".join(
        f"Line {i} of a long report." for i in range(work // 8))
    box = _box(text)
    widgets.keep_message_box_inside_the_work_area(box)
    assert box.detailedText() == text
    assert box.text() == "First paragraph."
    assert _label(box).font().bold()
    box.deleteLater()


def test_a_box_with_informative_text_keeps_its_bold_title(_app):
    from ui import widgets
    box = _box("ChromIQ does not know this printer's paper profiles yet")
    box.setInformativeText("A body of several sentences. " * 20)
    widgets.keep_message_box_inside_the_work_area(box)
    assert _label(box).font().bold()
    assert not _label(box).styleSheet()
    box.deleteLater()


def test_rich_text_is_left_to_its_own_weights(_app):
    assert _bold_after("<p>" + "word " * 200 + "</p>", rich=True)
