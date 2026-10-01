"""A driver that runs into an unscripted pop-up keeps going and says so.

Basti, 2026-10-02: *"the drivers that either you or your agents are creating
get stuck at some pop ups. would be nice if they could recognize this"*.
`scripts/onscreen_capture.PopupWatchdog` is the shared answer; these tests run
a real ``exec()`` (the thing that blocks a driver) and prove the watchdog ends
it, records it, and answers a scripted question with the button it was told.
Each exec carries its own 10 s safety timer, so a broken watchdog fails the
test instead of hanging the suite.
"""
import sys
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from onscreen_capture import PopupWatchdog  # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def _box(title="Overwrite?", text="Replace the selected report?"):
    box = QMessageBox(QMessageBox.Icon.Question, title, text)
    box.addButton("Create new", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Update this one", QMessageBox.ButtonRole.DestructiveRole)
    cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setEscapeButton(cancel)
    return box, cancel


class _Safety:
    """Ends a dialog after 10 s and remembers that it had to."""

    def __init__(self, dialog):
        self.dialog, self.fired = dialog, False
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fire)

    def fire(self):
        self.fired = True
        self.dialog.reject()


def _exec_with_safety(dialog):
    """True when the dialog had to be ended by the safety, i.e. it hung."""
    safety = _Safety(dialog)
    safety.timer.start(10_000)
    dialog.exec()
    safety.timer.stop()
    return safety.fired


def test_an_unscripted_question_is_dismissed_and_recorded(qapp, tmp_path):
    box, cancel = _box()
    dog = PopupWatchdog(tmp_path, grace_s=0.2, interval_ms=50, log=lambda s: None).start()
    hung = _exec_with_safety(box)
    dog.stop()
    assert not hung, "the watchdog never ended the exec()"
    assert box.clickedButton() is cancel
    [event] = dog.unexpected_events()
    # macOS ignores a message box's window title, so the text is the identity
    assert "Replace the selected report?" in event["text"]
    assert event["buttons"] == ["Create new", "Update this one", "Cancel"]
    assert "Cancel" in event["action"]
    assert "SEEN QMessageBox" in (tmp_path / "popups.log").read_text()


def test_a_scripted_question_gets_the_answer_it_was_given(qapp, tmp_path):
    box, _cancel = _box()
    dog = PopupWatchdog(tmp_path, grace_s=5, interval_ms=50, log=lambda s: None)
    dog.expect(r"replace the selected", "Create new").start()
    hung = _exec_with_safety(box)
    dog.stop()
    assert not hung
    assert box.clickedButton().text() == "Create new"
    assert dog.unexpected_events() == []


def test_a_rule_naming_a_missing_button_is_flagged(qapp, tmp_path):
    box, cancel = _box()
    dog = PopupWatchdog(tmp_path, grace_s=0.2, interval_ms=50, log=lambda s: None)
    dog.expect(r"replace", "Delete everything").start()
    hung = _exec_with_safety(box)
    dog.stop()
    assert not hung
    assert box.clickedButton() is cancel
    assert "NOT FOUND" in dog.events[0]["action"]
    assert dog.unexpected_events()


def test_fail_policy_marks_the_run(qapp, tmp_path):
    dlg = QDialog()
    dlg.setWindowTitle("Some window nobody scripted")
    dlg.setModal(True)
    dog = PopupWatchdog(tmp_path, policy="fail", grace_s=0.2, interval_ms=50, dismiss_windows=True,
                        log=lambda s: None).start()
    hung = _exec_with_safety(dlg)
    dog.stop()
    assert not hung
    assert dlg.result() == QDialog.DialogCode.Rejected
    assert dog.unexpected is True


def test_report_policy_leaves_it_open(qapp, tmp_path):
    box, _cancel = _box()
    dog = PopupWatchdog(tmp_path, policy="report", grace_s=0.1, interval_ms=50,
                        log=lambda s: None).start()
    closer = QTimer()
    closer.setSingleShot(True)
    closer.timeout.connect(box.reject)
    closer.start(600)
    box.exec()
    dog.stop()
    assert box.clickedButton() is None or box.clickedButton().text() != "Cancel"
    assert dog.events and dog.events[0]["action"] == ""


def test_an_unknown_policy_is_refused():
    with pytest.raises(ValueError):
        PopupWatchdog(policy="ignore")


def test_a_working_window_is_left_open(qapp, tmp_path):
    """The first watchdog pressed Escape on the Measurement Report window two
    seconds after a driver opened it. A modal window that is not a question is
    logged, never closed, unless the driver asks for that."""
    dlg = QDialog()
    dlg.setWindowTitle("Measurement Report")
    dlg.setModal(True)
    dog = PopupWatchdog(tmp_path, grace_s=0.1, interval_ms=50, log=lambda s: None).start()
    closer = QTimer()
    closer.setSingleShot(True)
    closer.timeout.connect(dlg.accept)
    closer.start(800)
    dlg.exec()
    dog.stop()
    assert dlg.result() == QDialog.DialogCode.Accepted   # closed by the driver, not the dog
    [event] = dog.events
    assert event["kind"] == "window" and not event["unexpected"]


def test_a_working_window_can_be_dismissed_on_request(qapp, tmp_path):
    dlg = QDialog()
    dlg.setModal(True)
    dog = PopupWatchdog(tmp_path, grace_s=0.1, interval_ms=50, dismiss_windows=True,
                        log=lambda s: None).start()
    hung = _exec_with_safety(dlg)
    dog.stop()
    assert not hung
    assert dlg.result() == QDialog.DialogCode.Rejected


class _DriverAnswers:
    """What a driver does when it answers a question itself."""

    def __init__(self, box, label):
        self.box, self.label = box, label

    def answer(self):
        for b in self.box.buttons():
            if b.text() == self.label:
                b.click()


def test_the_driver_gets_the_grace_period_to_answer_itself(qapp, tmp_path):
    """Unscripted is not the same as unanswered: a driver that clicks within
    the grace period gets its own answer, not the watchdog's Escape."""
    box, _cancel = _box()
    dog = PopupWatchdog(tmp_path, grace_s=2.0, interval_ms=50, log=lambda s: None).start()
    driver = _DriverAnswers(box, "Update this one")
    QTimer.singleShot(600, driver.answer)
    hung = _exec_with_safety(box)
    dog.stop()
    assert not hung
    assert box.clickedButton().text() == "Update this one"
    assert dog.events[0]["action"] == ""


def test_a_message_box_shown_without_exec_is_noticed(qapp, tmp_path):
    """A box opened with show() is not the active MODAL widget, so the
    top-level sweep is what finds it."""
    box, cancel = _box()
    box.setWindowModality(Qt.WindowModality.NonModal)
    dog = PopupWatchdog(tmp_path, grace_s=0.1, interval_ms=50, log=lambda s: None).start()
    box.show()
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.start(1500)
    while deadline.isActive() and box.isVisible():
        qapp.processEvents()
    dog.stop()
    assert not box.isVisible()
    assert box.clickedButton() is cancel
    assert dog.unexpected_events()
