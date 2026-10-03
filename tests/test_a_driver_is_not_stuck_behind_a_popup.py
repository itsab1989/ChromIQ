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
    assert "SEEN QMessageBox" in (tmp_path / "popups.log").read_text(encoding="utf-8")


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


# ---- the defects the challenge (G, 2026-10-02) reproduced on screen -------

class _AsksAgain:
    """An answer that opens a second question, as 'Delete run?' -> 'Really?'."""

    def __init__(self):
        self.second = None
        self.hung = False

    def first_answered(self, _button):
        self.second, _cancel = _box("Really?", "This cannot be undone. Really delete?")
        self.hung = _exec_with_safety(self.second)


def test_a_question_asked_by_an_answer_is_seen_too(qapp, tmp_path):
    first, _cancel = _box("Delete?", "Delete the selected run?")
    chain = _AsksAgain()
    first.buttonClicked.connect(chain.first_answered)
    dog = PopupWatchdog(tmp_path, grace_s=0.3, interval_ms=50, log=lambda s: None)
    dog.expect(r"Delete the selected run", "Update this one").start()
    hung = _exec_with_safety(first)
    dog.stop()
    assert not hung
    assert chain.second is not None and not chain.second.isVisible()
    assert not chain.hung, "the second question had to be ended by the safety"
    texts = [e["text"] for e in dog.events]
    assert any("Really delete" in t for t in texts), texts


class _AddsButtonLate:
    def __init__(self, box):
        self.box = box

    def add(self):
        self.box.addButton("Continue anyway", QMessageBox.ButtonRole.AcceptRole)


def test_a_button_that_appears_late_still_gets_the_scripted_answer(qapp, tmp_path):
    box, _cancel = _box("Slow", "Strip read quickly")
    late = _AddsButtonLate(box)
    QTimer.singleShot(400, late.add)
    dog = PopupWatchdog(tmp_path, grace_s=2.0, interval_ms=50, log=lambda s: None)
    dog.expect(r"Strip read quickly", "Continue anyway").start()
    hung = _exec_with_safety(box)
    dog.stop()
    assert not hung
    assert box.clickedButton().text() == "Continue anyway"
    assert dog.unexpected_events() == []


def test_a_popup_that_vanishes_mid_look_never_stops_the_driver(qapp, tmp_path, monkeypatch):
    box, _cancel = _box()
    dog = PopupWatchdog(tmp_path, grace_s=0.1, interval_ms=50, log=lambda s: None)

    def gone(_w):
        raise RuntimeError("wrapped C/C++ object of type QMessageBox has been deleted")
    monkeypatch.setattr(PopupWatchdog, "describe", staticmethod(gone))
    box.show()
    dog._tick()                                   # must not raise
    box.close()
    assert "went away" in (tmp_path / "popups.log").read_text(encoding="utf-8")


def test_photographing_a_popup_never_hides_it(qapp, tmp_path, monkeypatch):
    """Hiding a dialog inside exec() ends it as Rejected: the photograph would
    answer the question."""
    import onscreen_capture as oc
    monkeypatch.setattr(oc, "session_is_locked", lambda: False)
    monkeypatch.setattr(oc, "window_id_for", lambda _w: None)
    box, _cancel = _box()
    box.show()
    ok, why = oc.capture_window(box, tmp_path / "p.png", settle=0, allow_hide=False)
    assert not ok and "hide" in why
    assert box.isVisible()
    box.close()


# ---- review K_review_beta1 ---------------------------------------------------

def test_a_plain_dialog_that_only_asks_is_a_question(qapp, tmp_path):
    """ChromIQ's "Strip Read Quickly" is a QDialog with text and two buttons."""
    from PyQt6.QtWidgets import QCheckBox, QLabel, QPushButton, QVBoxLayout
    dlg = QDialog()
    dlg.setModal(True)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("Strip A was accepted, but it was read quickly."))
    lay.addWidget(QCheckBox("Do not show this message again"))
    again = QPushButton("Re-read strip")
    again.clicked.connect(dlg.accept)
    lay.addWidget(QPushButton("Continue anyway"))
    lay.addWidget(again)
    dog = PopupWatchdog(tmp_path, grace_s=0.2, interval_ms=50, log=lambda s: None).start()
    hung = _exec_with_safety(dlg)
    dog.stop()
    assert not hung
    assert dlg.result() == QDialog.DialogCode.Rejected
    assert dog.events[0]["kind"] == "question" and dog.events[0]["unexpected"]


def test_a_dialog_with_working_widgets_stays_a_window(qapp, tmp_path):
    from PyQt6.QtWidgets import QComboBox, QPushButton, QVBoxLayout
    dlg = QDialog()
    dlg.setModal(True)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QComboBox())
    lay.addWidget(QPushButton("Generate report"))
    dog = PopupWatchdog(tmp_path, grace_s=0.1, interval_ms=50, log=lambda s: None).start()
    closer = QTimer()
    closer.setSingleShot(True)
    closer.timeout.connect(dlg.accept)
    closer.start(700)
    dlg.exec()
    dog.stop()
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert dog.events[0]["kind"] == "window"


class _DismissAsksAgain:
    """Pressing Cancel opens 'Discard your changes?'."""

    def __init__(self):
        self.second = None
        self.hung = False

    def on_click(self, button):
        if button.text() == "Cancel":
            self.second, _c = _box("Discard?", "Discard your changes?")
            self.hung = _exec_with_safety(self.second)


def test_a_question_opened_by_a_dismissal_is_seen_too(qapp, tmp_path):
    first, _cancel = _box("Close?", "Close the window?")
    chain = _DismissAsksAgain()
    first.buttonClicked.connect(chain.on_click)
    dog = PopupWatchdog(tmp_path, grace_s=0.2, interval_ms=50, log=lambda s: None).start()
    hung = _exec_with_safety(first)
    dog.stop()
    assert not hung and not chain.hung
    assert any("Discard your changes" in e["text"] for e in dog.events)


# ---- review P_review2_beta1 W-1: Escape is the box's own safe answer --------

def test_escape_takes_the_reject_role_answer_when_no_escape_button_is_set(qapp, tmp_path):
    """Like "Scan doesn't match the chart": Stop (RejectRole) + Build anyway,
    no explicit escape button. reject() from code answered nothing, which the
    app read as "build anyway"; a real Escape key presses Stop."""
    box = QMessageBox(QMessageBox.Icon.Warning, "Scan doesn't match", "The alignment check failed:")
    stop = box.addButton("Stop", QMessageBox.ButtonRole.RejectRole)
    box.addButton("Build anyway", QMessageBox.ButtonRole.AcceptRole)
    box.setDefaultButton(stop)
    dog = PopupWatchdog(tmp_path, grace_s=0.2, interval_ms=50, log=lambda s: None).start()
    hung = _exec_with_safety(box)
    dog.stop()
    assert not hung
    assert box.clickedButton() is stop


def test_escape_takes_cancel_in_stuck_print_jobs(qapp, tmp_path):
    box = QMessageBox(QMessageBox.Icon.Warning, "Stuck Print Jobs Detected", "Clear them before printing?")
    box.addButton("Clear && Print", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Print Anyway", QMessageBox.ButtonRole.DestructiveRole)
    cancel = box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(cancel)
    dog = PopupWatchdog(tmp_path, grace_s=0.2, interval_ms=50, log=lambda s: None).start()
    hung = _exec_with_safety(box)
    dog.stop()
    assert not hung
    assert box.clickedButton() is cancel


def test_a_box_with_no_escape_answer_is_still_closed(qapp, tmp_path):
    """Review T_review_beta2: a box with only Accept/Destructive buttons has
    no Escape answer, so the real Escape key does nothing, and the watchdog
    dismisses a pop-up only once: the driver hung behind it. It is closed with
    no answer after a grace period."""
    box = QMessageBox(QMessageBox.Icon.Warning, "Unsaved", "Keep them?")
    box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
    dog = PopupWatchdog(tmp_path, grace_s=0.2, interval_ms=50, log=lambda s: None).start()
    hung = _exec_with_safety(box)
    dog.stop()
    assert not hung
    assert box.clickedButton() is None
