"""Tools ▸ Read single patches must not throw a measuring session away.

Knut, 2026-09-03, reporting it as an annoyance: *"pressing spacebar there which
is a trigger in measure tab closes the read single patches window even in an
active session."*

Driving the real window shows it was worse than closing. `QWidget::setEnabled(
false)` on the FOCUSED button calls `focusNextChild()`, which skips every
disabled button — so disabling **Take reading** (which the misread-recovery
path and the calibration prompt both do) walked the focus on to the next
enabled button in the bottom row. Measured before the fix:

    [no readings]  focus after disable -> Close   ; SPACE -> the window closed
    [3 readings]   focus after disable -> Clear   ; SPACE -> readings=0, rows=0,
                                                    and the window stayed open

The second one is the one he was most likely to hit, because he was measuring,
and it is silent: `_on_clear` had no question and no way back.

A third defect came out of the same reading: `self._readings` lives in memory
and nowhere else, and `reject()`, `closeEvent()` and therefore **Escape** all
went straight to releasing the instrument and out. Close, the red window button
and a stray Escape each discarded a whole session without a word.

Four layers are pinned here, and each is worth having on its own:

1. a disabled Take reading never hands the focus to a destructive button;
2. Space takes a reading, the way it does in the Measure tab;
3. Clear asks first, and can be undone;
4. closing with unsaved readings asks first.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt                                    # noqa: E402
from PyQt6.QtTest import QTest                                 # noqa: E402
from PyQt6.QtWidgets import (QApplication, QLineEdit,          # noqa: E402
                             QMessageBox, QPushButton)

from core.argyll_runner import ArgyllRunner                    # noqa: E402
from core.settings import AppSettings                          # noqa: E402
from ui.dialogs.spot_read_dialog import SpotReadDialog         # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Answering(SpotReadDialog):
    """The real window, with only the modal loop stubbed.

    `_ask` is the one seam: it is where `box.exec()` lives. Everything the
    windows say, every button they carry and every consequence they run is the
    shipping code. Nothing patches `QMessageBox.exec` process-wide, which this
    suite has been bitten by twice.
    """

    answer = ""          #: the text of the button to "press"
    asked: list

    def _ask(self, box: QMessageBox):
        self.asked.append((box.text(), [b.text() for b in box.buttons()]))
        for b in box.buttons():
            if b.text().replace("&", "") == self.answer:
                return b
        return None


def _dialog(cls=SpotReadDialog):
    s = AppSettings()
    d = cls(ArgyllRunner(s), s)
    d.asked = []
    d.show()
    QApplication.processEvents()
    return d


def _fill(d, n=3):
    for i in range(n):
        d._on_reading((0.3, 0.3, 0.3), (60.0 + i, 1.0, 2.0))
    QApplication.processEvents()


def _focus_label():
    w = QApplication.focusWidget()
    return w.text() if isinstance(w, QPushButton) else w.__class__.__name__


# ---- 1. the focus never lands on a destructive button --------------------
@pytest.mark.parametrize("readings", [0, 3])
def test_disabling_take_reading_does_not_hand_the_focus_to_a_destructive_button(
        qapp, readings):
    d = _dialog()
    try:
        _fill(d, readings)
        d._set_session_running(True)
        d._set_read_enabled(True)
        d._read_btn.setFocus()
        QApplication.processEvents()
        assert _focus_label() == "Take reading"

        d._set_read_enabled(False)          # what the misread path does
        QApplication.processEvents()
        assert _focus_label() not in ("Close", "Clear", "Undo clear"), (
            "the focus walked from Take reading onto a button that ends the "
            "window or empties the list")
    finally:
        d._readings.clear()
        d.close()


def test_the_focus_comes_back_when_take_reading_returns(qapp):
    """The 300 ms misread gap must not cost the keyboard its place."""
    d = _dialog()
    try:
        d._set_session_running(True)
        d._set_read_enabled(True)
        d._read_btn.setFocus()
        QApplication.processEvents()
        d._set_read_enabled(False)
        d._set_read_enabled(True)
        QApplication.processEvents()
        assert _focus_label() == "Take reading"
    finally:
        d.close()


# ---- 2. Space is the trigger --------------------------------------------
def test_space_takes_a_reading_wherever_the_focus_is(qapp):
    d = _dialog()
    took = []
    d._on_take_reading = lambda: took.append(True)
    try:
        d._set_session_running(True)
        d._set_read_enabled(True)
        # The worst case from his report: the focus is on Close.
        close = [b for b in d.findChildren(QPushButton) if b.text() == "Close"][0]
        close.setFocus()
        QApplication.processEvents()
        QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Space)
        QApplication.processEvents()
        assert took == [True], "Space did not take a reading"
        assert d.isVisible(), "Space closed the window"
    finally:
        d.close()


def test_space_does_not_reach_clear_and_empty_the_list(qapp):
    """The silent one: the window stayed open and every reading was gone."""
    d = _dialog()
    try:
        _fill(d, 3)
        d._set_session_running(True)
        d._set_read_enabled(True)
        d._read_btn.setFocus()
        QApplication.processEvents()
        d._set_read_enabled(False)
        d._set_read_enabled(True)
        QApplication.processEvents()
        QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Space)
        QApplication.processEvents()
        assert len(d._readings) == 3, "Space emptied the list"
        assert d._table.rowCount() == 3
    finally:
        d._readings.clear()
        d.close()


def test_a_space_typed_into_a_text_box_is_still_a_space(qapp):
    """The readings table renames a patch in place, and a name may have one."""
    d = _dialog()
    try:
        d._set_session_running(True)
        d._set_read_enabled(True)
        edit = QLineEdit(d)
        edit.show()
        edit.setFocus()
        QApplication.processEvents()
        QTest.keyClicks(edit, "a b")
        QApplication.processEvents()
        assert edit.text() == "a b", (
            f"the trigger ate a typed space: {edit.text()!r}")
    finally:
        d.close()


def test_the_filter_leaves_other_windows_alone(qapp):
    """It is installed on the application, so scope is the whole safety of it."""
    d = _dialog()
    took = []
    d._on_take_reading = lambda: took.append(True)
    try:
        d._set_session_running(True)
        d._set_read_enabled(True)
        stranger = QPushButton("elsewhere")
        stranger.show()
        stranger.setFocus()
        QApplication.processEvents()
        QTest.keyClick(stranger, Qt.Key.Key_Space)
        QApplication.processEvents()
        assert took == [], "the spot window claimed a key pressed in another window"
    finally:
        stranger.deleteLater()
        d.close()


def test_the_filter_is_gone_once_the_window_is(qapp):
    """A filter left on the application eats keys for the rest of the session
    — the exact fault `TabMeasure.eventFilter` carries a paragraph about."""
    d = _dialog()
    took = []
    d._on_take_reading = lambda: took.append(True)
    d._set_session_running(True)
    d._set_read_enabled(True)
    d.close()
    QApplication.processEvents()
    other = QPushButton("after")
    other.show()
    other.setFocus()
    QApplication.processEvents()
    QTest.keyClick(other, Qt.Key.Key_Space)
    QApplication.processEvents()
    other.deleteLater()
    assert took == []


# ---- 3. Clear asks, and can be undone ------------------------------------
def test_clear_asks_before_it_empties_the_list(qapp):
    d = _dialog(_Answering)
    d.answer = "Cancel"
    try:
        _fill(d, 3)
        d._clear_btn.click()
        QApplication.processEvents()
        assert d.asked, "Clear emptied the list without asking"
        assert "Clear every reading in this list?" in d.asked[0][0]
        assert len(d._readings) == 3, "Cancel still cleared the list"
        assert d._table.rowCount() == 3
    finally:
        d._readings.clear()
        d.close()


def test_the_question_counts_what_it_is_about(qapp):
    d = _dialog(_Answering)
    d.answer = "Cancel"
    try:
        _fill(d, 1)
        d._confirm_clear()
        one = d.asked[-1][0]
        d._readings.append(d._readings[0])
        d._confirm_clear()
        many = d.asked[-1][0]
        assert one == many                     # the headline is the same
    finally:
        d._readings.clear()
        d.close()


def test_a_cleared_list_can_be_put_back(qapp):
    """Nothing the user made is destroyed without a way back."""
    d = _dialog(_Answering)
    d.answer = "Clear"
    try:
        _fill(d, 3)
        names = [r.name for r in d._readings]
        d._clear_btn.click()
        QApplication.processEvents()
        assert d._readings == []
        assert d._table.rowCount() == 0
        assert d._clear_btn.isEnabled(), "no way back is offered"
        assert d._clear_btn.text() == "Undo clear"

        d._clear_btn.click()                   # the undo
        QApplication.processEvents()
        assert [r.name for r in d._readings] == names, "the readings did not come back"
        assert d._table.rowCount() == 3
        assert d._clear_btn.text() == "Clear"
    finally:
        d._readings.clear()
        d.close()


def test_a_new_reading_replaces_what_undo_would_restore(qapp):
    """Which is what the window says, so it has to be true."""
    d = _dialog(_Answering)
    d.answer = "Clear"
    try:
        _fill(d, 2)
        d._on_clear()
        assert d._clear_btn.text() == "Undo clear"
        d._on_reading((0.3, 0.3, 0.3), (70.0, 0.0, 0.0))
        QApplication.processEvents()
        assert d._clear_btn.text() == "Clear"
        assert d._cleared == []
        assert len(d._readings) == 1
    finally:
        d._readings.clear()
        d.close()


# ---- 4. closing does not bin a session -----------------------------------
def test_closing_with_unsaved_readings_asks_first(qapp):
    d = _dialog(_Answering)
    d.answer = "Cancel"
    try:
        _fill(d, 2)
        d.reject()
        QApplication.processEvents()
        assert d.asked, "the window closed on unsaved readings without asking"
        assert "These readings are not saved yet" in d.asked[0][0]
        assert d.isVisible(), "Cancel closed the window anyway"
        assert len(d._readings) == 2
    finally:
        d._readings.clear()
        d.close()


def test_escape_asks_too(qapp):
    """Escape is QDialog's own reject, and it used to bin the session."""
    d = _dialog(_Answering)
    d.answer = "Cancel"
    try:
        _fill(d, 2)
        QTest.keyClick(d, Qt.Key.Key_Escape)
        QApplication.processEvents()
        assert d.asked
        assert d.isVisible()
    finally:
        d._readings.clear()
        d.close()


def test_the_red_window_button_asks_too(qapp):
    d = _dialog(_Answering)
    d.answer = "Cancel"
    try:
        _fill(d, 2)
        assert d.close() is False, "closeEvent did not refuse"
        QApplication.processEvents()
        assert d.asked
        assert len(d._readings) == 2
    finally:
        d._readings.clear()
        d.close()


def test_the_red_window_button_asks_ONCE(qapp):
    """`QDialog::closeEvent` calls `reject()`, so this window is reached twice.

    Found by driving the real window on screen and NOT by any of the tests
    above: answering Cancel stops at the first question, and `reject()` on its
    own only reaches the guard once. Answering Discard from `close()` put a
    second, identical window up that nothing was left to answer, and the app
    simply stopped.
    """
    d = _dialog(_Answering)
    d.answer = "Discard"
    try:
        _fill(d, 2)
        d.close()
        QApplication.processEvents()
        assert len(d.asked) == 1, f"asked {len(d.asked)} times"
        assert not d.isVisible()
    finally:
        d._readings.clear()
        d.close()


def test_discard_still_closes(qapp):
    """The guard is a question, not a lock."""
    d = _dialog(_Answering)
    d.answer = "Discard"
    try:
        _fill(d, 2)
        d.reject()
        QApplication.processEvents()
        assert d.asked
        assert not d.isVisible()
    finally:
        d._readings.clear()
        d.close()


def test_a_save_the_user_backed_out_of_leaves_the_window_open(qapp):
    """Choosing Save and then cancelling the file dialog must not close the
    window on readings it did not write."""
    d = _dialog(_Answering)
    d.answer = "Save"
    d._on_save = lambda: False          # the file dialog was cancelled
    try:
        _fill(d, 2)
        d.reject()
        QApplication.processEvents()
        assert d.isVisible()
        assert len(d._readings) == 2
    finally:
        d._readings.clear()
        d.close()


def test_a_saved_session_closes_without_a_question(qapp):
    """The ordinary end of a session stays one click."""
    d = _dialog(_Answering)
    d.answer = "Cancel"
    try:
        _fill(d, 2)
        d._unsaved = False              # what a successful save leaves behind
        d.reject()
        QApplication.processEvents()
        assert d.asked == [], "a saved session was questioned"
        assert not d.isVisible()
    finally:
        d._readings.clear()
        d.close()


def test_an_empty_window_closes_without_a_question(qapp):
    d = _dialog(_Answering)
    d.answer = "Cancel"
    d.reject()
    QApplication.processEvents()
    assert d.asked == []
    assert not d.isVisible()
