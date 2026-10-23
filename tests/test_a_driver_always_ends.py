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
        box = QMessageBox(QMessageBox.Icon.Question, "x", "y")
        box.show()
        old._tick()
        assert old.events == []           # the older one waits
        new._tick()
        assert len(new.events) == 1
        box.hide()
    finally:
        new.stop()
        old.stop()
    assert new not in PopupWatchdog._live and old not in PopupWatchdog._live


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
