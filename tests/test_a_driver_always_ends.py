"""A drive always ends, and ends with no window left on Basti's screen.

2026-10-23: four on-screen drivers left a ChromIQ window hanging on Basti's
screen in one day, each fixed only inside its own script. 4.3.11 moves the
fix into the shared harness (`scripts/userdrive.py`, `scripts/onscreen_capture
.py`, `scripts/capture_screens.py`):

* a script that raises ends the run with every window closed and rc 2;
* every run has a hard time limit and ends with rc 3 when it is up;
* the pop-up watchdog closes an unclaimed working window too (20 s by
  default), with "report" as the explicit opt-in that leaves it open;
* an exception in an app slot makes the verdict rc 4, not a pass;
* nothing is handed to another application (Preview, Finder, a browser);
* a button is found by its English label in any language.

Every exec() and run() here carries its own safety timer, so the OLD harness
fails these tests instead of hanging the suite.
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QCoreApplication, QEvent, QTimer  # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QLineEdit,  # noqa: E402
                             QMessageBox, QVBoxLayout, QWidget)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import onscreen_capture  # noqa: E402
from onscreen_capture import PopupWatchdog  # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def userdrive():
    saved = os.environ.get("QT_QPA_PLATFORM")
    try:
        mod = importlib.import_module("userdrive")
    finally:
        if saved is not None:
            os.environ["QT_QPA_PLATFORM"] = saved
    return mod


def _quiet_loop(qapp):
    """As test_a_driver_returns_to_a_modal_it_closed: let windows other tests
    deleteLater()'d go before the loop, where closing one cannot quit it."""
    import gc
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    for _ in range(3):
        qapp.processEvents()


def _bare_drive(userdrive, qapp, tmp_path, monkeypatch, limit=30.0):
    d = userdrive.Drive.__new__(userdrive.Drive)
    d.app = qapp
    d.notes = []
    d.record = {"steps": [], "modals": [], "photos": []}
    d.out = tmp_path
    d.shots = tmp_path / "photographs"
    d.shots.mkdir()
    d._closed_a_modal = False
    d._log = tmp_path / "log.txt"
    d._log.write_text("", encoding="utf-8")
    d._log_offset = 0
    d.time_limit_s = limit
    d.win = QWidget()
    d.win.setWindowTitle("main window stand-in")
    d.win.show()
    # offscreen: no photograph is possible, and none may be attempted
    monkeypatch.setattr(onscreen_capture, "capture_window",
                        lambda w, p, **k: (False, "test"))
    return d


class _Safety:
    """Leaves the event loop after *ms* and remembers that it had to."""

    def __init__(self, app, ms):
        self.app, self.fired = app, False
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fire)
        self.timer.start(ms)

    def fire(self):
        self.fired = True
        for w in QApplication.topLevelWidgets():
            if isinstance(w, QDialog) and w.isVisible():
                w.done(0)
        self.app.exit(99)


def _visible(*widgets):
    return [w for w in widgets if w.isVisible()]


def test_a_script_that_raises_inside_a_modal_ends_with_nothing_on_screen(
        userdrive, qapp, tmp_path, monkeypatch):
    """MUTATION: put back `self.app.quit()` (no window closing) in the
    except branch of `Drive.run.step`: the dialog stays up, the safety fires."""
    d = _bare_drive(userdrive, qapp, tmp_path, monkeypatch)
    dlg = QDialog(d.win)
    dlg.setWindowTitle("A window the script opened")

    def script(dd):
        dd.later(dlg.exec)
        yield 300
        assert dlg.isVisible()
        raise RuntimeError("the script went wrong")

    _quiet_loop(qapp)
    safety = _Safety(qapp, 15_000)
    rc = d.run(script)
    safety.timer.stop()
    assert not safety.fired, "the drive did not end by itself"
    assert rc == userdrive.RC_SCRIPT_RAISED == 2
    assert _visible(dlg, d.win) == []
    notes = "\n".join(d.notes)
    assert "RuntimeError: the script went wrong" in notes
    assert d.record["ended"]["rc"] == 2


def test_the_time_limit_ends_a_drive_that_never_finishes(
        userdrive, qapp, tmp_path, monkeypatch):
    """MUTATION: drop the limit timer in `Drive.run`: the script yields for
    ever and only the safety ends the loop."""
    d = _bare_drive(userdrive, qapp, tmp_path, monkeypatch, limit=1.0)
    box = QMessageBox(QMessageBox.Icon.Question, "Left open",
                      "A question the script never answers")
    box.addButton("Delete everything", QMessageBox.ButtonRole.DestructiveRole)
    keep = box.addButton("Keep", QMessageBox.ButtonRole.RejectRole)

    def script(dd):
        dd.later(box.exec)
        while True:
            yield 100

    _quiet_loop(qapp)
    safety = _Safety(qapp, 20_000)
    rc = d.run(script)
    safety.timer.stop()
    assert not safety.fired, "the time limit did not end the drive"
    assert rc == userdrive.RC_TIME_LIMIT == 3
    assert _visible(box, d.win) == []
    # never the destructive answer: closing is "do nothing"
    assert box.clickedButton() in (None, keep)
    assert "time limit" in d.record["ended"]["why"]


def test_the_time_limit_can_be_set_from_the_environment(userdrive, monkeypatch):
    monkeypatch.setenv("CHROMIQ_DRIVE_TIME_LIMIT", "42")
    assert userdrive._time_limit(None) == 42.0
    assert userdrive._time_limit(7) == 7.0
    monkeypatch.delenv("CHROMIQ_DRIVE_TIME_LIMIT")
    assert userdrive._time_limit(None) == userdrive.DEFAULT_TIME_LIMIT_S == 600


def test_an_exception_in_an_app_slot_is_not_a_pass(
        userdrive, qapp, tmp_path, monkeypatch):
    """The drivers' excepthook keeps the app alive (as main() does); the drive
    must still not call the run a pass."""
    fake = types.SimpleNamespace(UNCAUGHT=[])
    monkeypatch.setitem(sys.modules, "scripts.capture_screens", fake)
    d = _bare_drive(userdrive, qapp, tmp_path, monkeypatch)

    def script(dd):
        fake.UNCAUGHT.append("Traceback ...\nTypeError: a slot raised\n")
        yield 50

    _quiet_loop(qapp)
    safety = _Safety(qapp, 15_000)
    rc = d.run(script)
    safety.timer.stop()
    assert not safety.fired, "the drive did not end by itself"
    assert rc == userdrive.RC_APP_RAISED == 4
    assert d.record["app_exceptions"]


def test_a_finished_drive_closes_its_windows_too(
        userdrive, qapp, tmp_path, monkeypatch):
    d = _bare_drive(userdrive, qapp, tmp_path, monkeypatch)
    side = QWidget()
    side.setWindowTitle("a second window")

    def script(dd):
        side.show()
        yield 50

    _quiet_loop(qapp)
    safety = _Safety(qapp, 15_000)
    rc = d.run(script)
    safety.timer.stop()
    assert not safety.fired
    assert rc == 0
    assert _visible(side, d.win) == []


# -- the watchdog ---------------------------------------------------------------
def _working_window(title="Measurement Report"):
    dlg = QDialog()
    dlg.setWindowTitle(title)
    dlg.setModal(True)
    QVBoxLayout(dlg).addWidget(QLineEdit(dlg))      # makes it a working window
    return dlg


def _exec_with_safety(dialog, ms=10_000):
    fired = {"v": False}
    t = QTimer()
    t.setSingleShot(True)

    def fire():
        fired["v"] = True
        dialog.done(0)
    t.timeout.connect(fire)
    t.start(ms)
    dialog.exec()
    t.stop()
    return fired["v"]


def test_an_unclaimed_working_window_is_closed_by_default(qapp, tmp_path):
    """MUTATION: restore `return  # a working window: leave it be` in
    `PopupWatchdog._look_at`: the window stays until the safety."""
    dlg = _working_window()
    dog = PopupWatchdog(tmp_path, grace_s=0.1, window_grace_s=0.5,
                        interval_ms=50, log=lambda s: None).start()
    hung = _exec_with_safety(dlg)
    dog.stop()
    assert not hung
    assert dlg.result() == QDialog.DialogCode.Rejected
    [event] = dog.events
    assert event["kind"] == "window" and event["unexpected"]


def test_the_default_grace_for_a_working_window_is_twenty_seconds():
    assert PopupWatchdog().window_grace_s == 20.0
    assert PopupWatchdog().policy == "dismiss"


def test_a_claimed_working_window_stays_open(qapp, tmp_path):
    dlg = _working_window()
    dog = PopupWatchdog(tmp_path, grace_s=0.1, window_grace_s=0.3,
                        interval_ms=50, log=lambda s: None).start()
    dog.claim(dlg)
    closer = QTimer()
    closer.setSingleShot(True)
    closer.timeout.connect(dlg.accept)
    closer.start(1200)
    dlg.exec()
    dog.stop()
    assert dlg.result() == QDialog.DialogCode.Accepted   # the driver's close


def test_an_expected_window_stays_open(qapp, tmp_path):
    dlg = _working_window("Preferences")
    dog = PopupWatchdog(tmp_path, grace_s=0.1, window_grace_s=0.3,
                        interval_ms=50, log=lambda s: None)
    dog.expect_window(r"^preferences$").start()
    closer = QTimer()
    closer.setSingleShot(True)
    closer.timeout.connect(dlg.accept)
    closer.start(1200)
    dlg.exec()
    dog.stop()
    assert dlg.result() == QDialog.DialogCode.Accepted


def test_report_policy_is_the_opt_in_that_leaves_a_window_open(qapp, tmp_path):
    dlg = _working_window()
    dog = PopupWatchdog(tmp_path, policy="report", grace_s=0.1,
                        window_grace_s=0.2, interval_ms=50,
                        log=lambda s: None).start()
    closer = QTimer()
    closer.setSingleShot(True)
    closer.timeout.connect(dlg.accept)
    closer.start(1200)
    dlg.exec()
    dog.stop()
    assert dlg.result() == QDialog.DialogCode.Accepted


@pytest.mark.parametrize("label,role,explicit", [
    ("Delete everything", QMessageBox.ButtonRole.DestructiveRole, False),
    ("Yes, replace it", QMessageBox.ButtonRole.YesRole, False),
    ("Save", QMessageBox.ButtonRole.AcceptRole, False),
    ("Apply", QMessageBox.ButtonRole.ApplyRole, False),
    # an Escape answer set by the app itself is checked the same way
    ("Discard", QMessageBox.ButtonRole.DestructiveRole, True),
])
def test_a_lone_unsafe_button_is_never_pressed(qapp, tmp_path, label, role,
                                               explicit):
    """Review 36: Qt makes a box's ONLY button its Escape answer, whatever it
    says, so the watchdog's Escape pressed a lone "Delete everything".
    MUTATION: drop the role check in `PopupWatchdog._dismiss`: the button is
    clicked."""
    box = QMessageBox(QMessageBox.Icon.Question, "Lone", "A question")
    b = box.addButton(label, role)
    if explicit:
        box.addButton("Keep", QMessageBox.ButtonRole.ActionRole)
        box.setEscapeButton(b)
    dog = PopupWatchdog(tmp_path, grace_s=0.1, interval_ms=50,
                        log=lambda s: None).start()
    hung = _exec_with_safety(box, 8_000)
    dog.stop()
    assert not hung
    assert box.clickedButton() is not b
    assert "no answer" in dog.events[0]["action"]


def test_a_lone_cancel_is_still_pressed(qapp, tmp_path):
    """The safe answers still work: the Escape answer of a lone Cancel."""
    box = QMessageBox(QMessageBox.Icon.Question, "Lone", "A question")
    b = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    dog = PopupWatchdog(tmp_path, grace_s=0.1, interval_ms=50,
                        log=lambda s: None).start()
    hung = _exec_with_safety(box, 8_000)
    dog.stop()
    assert not hung
    assert box.clickedButton() is b


class _AsksFirst(QDialog):
    """A window whose reject() asks first and stays open on Cancel, as the
    spot-read window does with unsaved readings."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spot Read")
        self.setModal(True)
        QVBoxLayout(self).addWidget(QLineEdit(self))
        self.asked = 0

    def reject(self):
        self.asked += 1
        box = QMessageBox(QMessageBox.Icon.Warning, "Unsaved readings",
                          "Save them first?", parent=self)
        box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not cancel and box.clickedButton() is not None:
            super().reject()


def test_a_window_that_refuses_to_close_is_ended_without_saving(qapp, tmp_path):
    """MUTATION: drop `_escalate`: the window stays up after its question
    was answered Cancel, until the safety."""
    dlg = _AsksFirst()
    dog = PopupWatchdog(tmp_path, grace_s=0.1, window_grace_s=0.3,
                        retry_s=0.6, interval_ms=50, log=lambda s: None).start()
    hung = _exec_with_safety(dlg, 15_000)
    dog.stop()
    assert not hung
    assert dlg.asked == 1                     # asked once, answered Cancel
    assert dlg.result() == QDialog.DialogCode.Rejected
    assert "done(Rejected)" in dog.events[0]["action"]


def test_only_the_newest_watchdog_acts(qapp, tmp_path):
    old = PopupWatchdog(tmp_path, log=lambda s: None).start()
    new = PopupWatchdog(tmp_path, log=lambda s: None).start()
    try:
        assert PopupWatchdog._live[-1] is new
        box = QMessageBox(QMessageBox.Icon.Question, "x", "the newest's own")
        box.show()
        old._tick()
        assert old.events == []           # the older one waits
        new._tick()
        # ITS OWN BOX, not "one event": a window another test left visible
        # on this worker is a pop-up too (gate 3 of 4.3.11 saw three)
        mine = [e for e in new.events if e["text"] == "the newest's own"]
        assert len(mine) == 1, new.events
        box.hide()
    finally:
        new.stop()
        old.stop()
    assert new not in PopupWatchdog._live and old not in PopupWatchdog._live


# -- nothing outlives its test ---------------------------------------------------
def test_a_drive_leaves_nothing_queued_when_qt_ends_its_loop_first(
        userdrive, qapp, tmp_path, monkeypatch):
    """4.3.11 gate 3 of 3. Qt leaves app.exec() by itself when the last
    visible window closes, which `_end_close_main` does, 3 s before
    `_end_leave`. That step stayed queued, fired inside the NEXT test's
    dialog, hid it and called app.exit() outside app.exec(), and every
    exec() on the worker returned at once from then on (13 bystanders red).
    Here the loop is left early on purpose, as Qt does, and the drive is held
    alive, as an uncollected cycle held it in the gate.
    MUTATION: drop the `if not self._in_loop: return` guards and the
    `_stop_timers()` in `Drive.run`: the dialog below is hidden by the old
    drive's ending and comes back Rejected at once."""
    d = _bare_drive(userdrive, qapp, tmp_path, monkeypatch)
    # the ending's turns, short enough for the suite's 4 s modal sweep
    d.END_CLOSE_MAIN_AFTER_MS, d.END_LEAVE_AFTER_MS = 600, 300
    left = []
    monkeypatch.setattr(d, "_end_leave",
                        lambda real=d._end_leave: (left.append(1), real()))

    def script(dd):
        yield 50

    def leave_as_qt_does():
        # the ending has started (the script finished at 50 ms) and its
        # first turn ran; now the loop goes, as on "last window closed"
        assert d._ending
        qapp.exit(0)

    _quiet_loop(qapp)
    safety = _Safety(qapp, 15_000)
    QTimer.singleShot(300, leave_as_qt_does)
    rc = d.run(script)
    safety.timer.stop()
    assert not safety.fired
    assert rc == 0
    # the next window, after the old drive's ending was due
    dlg = _working_window("The next test's window")
    waited = d.END_CLOSE_MAIN_AFTER_MS + d.END_LEAVE_AFTER_MS + 1000
    closer = QTimer()
    closer.setSingleShot(True)
    closer.timeout.connect(dlg.accept)
    closer.start(waited)
    hung = _exec_with_safety(dlg, waited + 10_000)
    closer.stop()
    assert not hung
    assert left == [], "the old drive's ending ran after its run() returned"
    assert dlg.result() == QDialog.DialogCode.Accepted, (
        "the next window was ended by a drive that had already returned")


def test_a_watchdog_that_outlives_its_test_is_caught_and_stopped(qapp):
    """The suite's guard (`conftest._no_driver_tool_outlives_its_test`)
    stops a watchdog left running, puts back the opener block, and names
    both. MUTATION: make `_driver_tools_left_running` return [] without
    stopping anything: the dog is still live and this goes red."""
    from PyQt6.QtGui import QDesktopServices
    conftest = next(m for m in list(sys.modules.values())
                    if hasattr(m, "_driver_tools_left_running"))
    real_system = os.system
    dog = PopupWatchdog(log=lambda s: None).start()
    installed = onscreen_capture.block_external_apps()
    try:
        assert dog in PopupWatchdog._live
        left = conftest._driver_tools_left_running()
        assert dog not in PopupWatchdog._live and dog._timer is None
        assert any("PopupWatchdog" in x for x in left), left
        if installed:
            assert any("block_external_apps" in x for x in left), left
            assert not getattr(QDesktopServices.openUrl, "_chromiq_blocked",
                               False)
            assert os.system is real_system
    finally:
        dog.stop()
        onscreen_capture.unblock_external_apps()


def test_a_stopped_watchdog_cancels_the_answer_it_queued(qapp, tmp_path):
    """A dismissal is queued on a zero-delay timer; a watchdog stopped
    before it runs must not answer anything afterwards."""
    box = QMessageBox(QMessageBox.Icon.Question, "Queued", "A question")
    cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.show()
    dog = PopupWatchdog(tmp_path, grace_s=0.0, log=lambda s: None).start()
    try:
        dog._tick()                       # first sight
        dog._tick()                       # past the grace: queues Escape
        assert dog._pending, "nothing was queued"
    finally:
        dog.stop()
    for _ in range(5):
        qapp.processEvents()
    assert box.isVisible() and box.clickedButton() is not cancel
    box.hide()


# -- any language ---------------------------------------------------------------
def test_a_button_is_found_by_its_english_label_in_german(qapp):
    """MUTATION: compare `b.text()` with the English label only, as
    `Drive.answer` did: the German button is not found."""
    from core import i18n
    before = i18n.current_language()
    i18n.set_language("de")
    try:
        german = i18n.tr("Cancel")
        assert german != "Cancel", "the German catalogue lost 'Cancel'"
        assert onscreen_capture.label_matches(german, "Cancel")
        assert onscreen_capture.label_matches("&" + german, "Cancel")
        assert not onscreen_capture.label_matches(german, "Save")
        box = QMessageBox()
        box.addButton(i18n.tr("Save"), QMessageBox.ButtonRole.AcceptRole)
        b = box.addButton(german, QMessageBox.ButtonRole.RejectRole)
        box.show()
        assert onscreen_capture.find_button(box, "Cancel") is b
        box.hide()
    finally:
        i18n.set_language(before)


def test_partial_labels_need_asking_for():
    assert onscreen_capture.label_matches("Save report as PDF…", "Save",
                                          exact=False)
    assert not onscreen_capture.label_matches("Save report as PDF", "Save")
    assert onscreen_capture.label_matches("Open…", "Open")


# -- no other application -------------------------------------------------------
_PROBE = r"""
import os, sys, webbrowser
sys.path.insert(0, {scripts!r}); sys.path.insert(0, {root!r})
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication
app = QApplication([])
import onscreen_capture as oc
assert oc.block_external_apps({log!r}) is True
assert oc.block_external_apps() is False          # idempotent
assert QDesktopServices.openUrl(QUrl("https://example.invalid/x")) is True
assert webbrowser.open("https://example.invalid/y") is True
assert os.system("open /nonexistent/path/for/chromiq/test") == 0
assert os.system("true") == 0                      # anything else still runs
print("OPENS", oc.EXTERNAL_OPENS)
"""


def test_nothing_is_handed_to_another_application(tmp_path):
    """MUTATION: make `block_external_apps` do nothing: openUrl answers via
    the real Launch Services, and the recorded list is empty."""
    log = tmp_path / "opened-elsewhere.txt"
    code = _PROBE.format(scripts=str(ROOT / "scripts"), root=str(ROOT),
                         log=str(log))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, encoding="utf-8", timeout=120, cwd=str(ROOT),
                       env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
    assert r.returncode == 0, r.stderr[-1500:]
    text = log.read_text(encoding="utf-8")
    assert "https://example.invalid/x" in text
    assert "https://example.invalid/y" in text
    assert "open /nonexistent/path/for/chromiq/test" in text
    assert "true" not in text.split()


def test_build_app_blocks_them_and_installs_the_excepthook():
    src = (ROOT / "scripts" / "capture_screens.py").read_text(encoding="utf-8")
    body = src[src.index("def build_app"):]
    body = body[:body.index("\ndef ", 10)]
    assert "block_external_apps()" in body
    assert "install_logging_excepthook()" in body


_HOOK_PROBE = r"""
import sys
sys.path.insert(0, {scripts!r}); sys.path.insert(0, {root!r})
import capture_screens as cs
app = cs.build_app()
from PyQt6.QtWidgets import QPushButton
b = QPushButton("x")
def boom():
    raise TypeError("boom in a slot")
b.clicked.connect(boom)
b.click()
assert len(cs.UNCAUGHT) == 1 and "boom in a slot" in cs.UNCAUGHT[0]
from PyQt6.QtGui import QDesktopServices
assert getattr(QDesktopServices.openUrl, "_chromiq_blocked", False)
print("STILL ALIVE", flush=True)
import os; os._exit(0)
"""


def test_build_app_really_keeps_a_driver_alive_and_records_the_exception(
        tmp_path):
    """(d) verified on the real build_app, not only by reading its source."""
    code = _HOOK_PROBE.format(scripts=str(ROOT / "scripts"), root=str(ROOT))
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
               CHROMIQ_SETTINGS_FILE=str(tmp_path / "settings.ini"))
    env.pop("CHROMIQ_DRIVER_ALLOW_EXTERNAL_APPS", None)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, encoding="utf-8", timeout=240, cwd=str(ROOT),
                       env=env)
    assert r.returncode == 0 and "STILL ALIVE" in r.stdout, \
        (r.stdout[-800:], r.stderr[-1500:])


def test_an_offscreen_app_never_photographs_a_rectangle_of_the_real_screen(
        qapp, tmp_path, monkeypatch):
    """Offscreen, the rectangle fallback would copy whatever is really on
    Basti's screen at that place. MUTATION: drop the platform check in
    `_grab_region`: screencapture is called."""
    called = []
    monkeypatch.setattr(onscreen_capture.subprocess, "run",
                        lambda *a, **k: called.append(a))
    assert QApplication.platformName() == "offscreen"
    assert onscreen_capture._grab_region("0,0,10,10", tmp_path / "x.png") is False
    assert called == []
