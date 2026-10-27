"""`keep_message_box_inside_the_work_area` measures a box at the height it
will really open with, its text wrapped.

Found 2026-10-26 on screen in German: a warning of long paragraphs measured
749 px with ``box.sizeHint()`` and opened 1101 px tall on a 1083 px work area,
so step 2 (move the overflow behind "Show Details") never ran. Until a
QMessageBox is shown its label does not wrap, and every paragraph counts as
one line; ``QMessageBoxPrivate::updateSize`` wraps it when the box is shown.
"""
from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox

PARA = ("Dieser Absatz ist ein langer Satz, der auf dem Bildschirm umbrochen "
        "wird, weil er viel breiter ist als das Fenster, und er erklärt, was "
        "passiert ist und was man jetzt tun kann, damit nichts verloren geht. ")


@pytest.fixture
def _app():
    return QApplication.instance() or QApplication([])


def _box(text: str) -> QMessageBox:
    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Warnung")
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.Ok
                           | QMessageBox.StandardButton.Cancel)
    return box


def _shown_height(box: QMessageBox, app) -> int:
    # NO processEvents() WHILE THE BOX IS SHOWN. `show()` runs
    # QMessageBox::showEvent, and its updateSize(), synchronously, so the
    # height is final here. Pumping the loop with the box on screen let the
    # suite's `_no_modal_may_hang_the_suite` sweep (every 4 s) fire inside it
    # and fail this test as "a modal dialog was left open": measured in a
    # loaded `--runslow` gate, 2026-10-27, while it passed 3 of 3 alone.
    box.show()
    h = box.height()
    box.close()
    box.deleteLater()
    app.processEvents()
    return h


def _label(box):
    return next(c for c in box.findChildren(QLabel) if c.text() == box.text())


def _text_that_hides_its_height(app, room: int) -> str:
    """Paragraphs whose UNWRAPPED size hint fits *room* and whose shown,
    wrapped height does not: the shape of the German warning. A quarter over,
    so that step 1's wider box cannot make it fit either."""
    for n in range(1, 60):
        text = "\n\n".join([(PARA * 2).strip()] * n)
        probe = _box(text)
        hint = probe.sizeHint().height()
        if _shown_height(probe, app) > room * 1.25:
            assert hint <= room, "this screen cannot show the fault"
            return text
    pytest.skip("the work area is too tall for this test")


def test_a_box_that_opens_too_tall_is_shortened(_app, monkeypatch):
    from ui import widgets
    work = _app.primaryScreen().availableGeometry()
    room = work.height() - 60
    text = _text_that_hides_its_height(_app, room)
    box = _box(text)
    widgets.keep_message_box_inside_the_work_area(box)
    assert box.detailedText() == text, (
        "the box opens taller than the work area and was not shortened: "
        "the helper measured it before its text wrapped")
    assert box.text() == text.split("\n\n", 1)[0]
    assert _shown_height(box, _app) <= room


def test_the_estimate_is_the_height_the_box_opens_with(_app):
    from ui import widgets
    work = _app.primaryScreen().availableGeometry()
    for n in (1, 2, 3):
        box = _box("\n\n".join([PARA.strip()] * n))
        est = widgets._message_box_height_once_shown(box, _label(box), work)
        assert box.text().count("\n\n") == n - 1      # nothing was changed
        real = _shown_height(box, _app)
        assert abs(est - real) <= 8, (n, est, real)


def test_a_short_box_is_left_as_it_was(_app):
    from ui import widgets
    for text in ("The chart was saved.", "Kurz."):
        box = _box(text)
        widgets.keep_message_box_inside_the_work_area(box)
        assert box.text() == text
        assert not box.detailedText()
        box.deleteLater()


def test_the_estimate_never_raises(_app):
    from ui import widgets
    work = _app.primaryScreen().availableGeometry()
    box = _box("x")
    assert widgets._message_box_height_once_shown(box, None, work) == \
        box.sizeHint().height()
    box.deleteLater()
