"""A drive that answers a modal must hand control back to that modal's loop.

Beta 38 (B8-831). Two drive rounds reported "Save report as PDF…" writing its
file only when the report window closed. Measured on screen: the file
chooser was hidden and Accepted, and its `exec()` still did not return for two
minutes, every timer firing inside it, until the drive closed the report
window. The cause was the harness, not the app: `Drive.answer_file` called
`accept()` from a timer callback running INSIDE the chooser's `exec()` and
then went on calling `processEvents()` (`self.pump(600)`). On macOS that
re-entrant pump can swallow the dispatcher's wake-up, and the loop sleeps on.
`scripts/probe_dialog_exit_after_reentrant_pump.py` shows it with plain Qt:
accept-and-return returned in 0.02 s 6 times of 6; accept-then-pump stayed
stuck in 2 of 6; an accept queued into the pump in 6 of 6. A user's click is
delivered by the chooser's own loop and has nothing on top of it.

These tests pin the harness contract. Offscreen cannot show the macOS stall
itself (the probe and the drive do that on screen); what it can check is the
thing that causes it, a processEvents() call between the answer and the next
`yield`.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def userdrive():
    """Import the harness without letting it take this worker off-screen:
    importing it pops QT_QPA_PLATFORM for the drives it serves."""
    saved = os.environ.get("QT_QPA_PLATFORM")
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        mod = importlib.import_module("userdrive")
    finally:
        sys.path.remove(str(ROOT / "scripts"))
        if saved is not None:
            os.environ["QT_QPA_PLATFORM"] = saved
    return mod


class _CountingApp:
    """Stands in for QApplication in the harness: counts processEvents()."""

    def __init__(self, real):
        self.real = real
        self.calls = 0

    def processEvents(self, *a):
        self.calls += 1
        self.real.processEvents(*a)

    def __getattr__(self, name):
        return getattr(self.real, name)


def _bare_drive(userdrive, qapp, tmp_path):
    d = userdrive.Drive.__new__(userdrive.Drive)
    d.app = _CountingApp(qapp)
    d.notes = []
    d.record = {"steps": [], "modals": [], "photos": []}
    d.out = tmp_path
    d.shots = tmp_path / "photographs"
    d._closed_a_modal = False
    return d


def test_no_pump_between_accepting_the_file_chooser_and_the_next_yield(
        userdrive, qapp, tmp_path, monkeypatch):
    """After `answer_file` accepts the chooser, a `pump` in the same step
    must not reach processEvents().

    MUTATIONS that turn this red: drop the `self._modal_closed()` call after
    `w.accept()` in `Drive.answer_file`; or drop the `if self._closed_a_modal:
    return` guard at the top of `Drive.pump`. Either puts back the
    re-entrant pump that left the PDF export waiting for the report window
    to close.
    """
    from PyQt6.QtWidgets import QFileDialog
    d = _bare_drive(userdrive, qapp, tmp_path)
    w = QFileDialog(None, "Save report as PDF", str(tmp_path))
    w.setOption(QFileDialog.Option.DontUseNativeDialog)
    w.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    w.show()
    monkeypatch.setattr(d, "modal", lambda: w)
    at_accept = {}
    real_accept = w.accept

    def accept():
        at_accept["calls"] = d.app.calls
        real_accept()

    monkeypatch.setattr(w, "accept", accept)
    d.answer_file(tmp_path / "out.pdf", within_ms=2000)
    assert "calls" in at_accept, "the chooser was never accepted"
    assert d.app.calls == at_accept["calls"], (
        "answer_file called processEvents() after accept(): the chooser's "
        "exec() can then miss its own exit on macOS")
    d.pump(300)                       # a caller pumping before its yield
    assert d.app.calls == at_accept["calls"], (
        "pump() ran processEvents() in the step that closed a modal")
    w.deleteLater()


def test_no_pump_after_clicking_a_question_either(
        userdrive, qapp, tmp_path, monkeypatch):
    """The same for `answer`, which clicks a button on a question box.

    MUTATION: drop `self._modal_closed()` after `choice.click()` in
    `Drive.answer` (or restore the `self.pump(600)` that followed it with the
    guard in `pump` removed): this goes red.
    """
    from PyQt6.QtWidgets import QMessageBox
    d = _bare_drive(userdrive, qapp, tmp_path)
    box = QMessageBox(QMessageBox.Icon.Question, "Replace?", "Replace it?",
                      QMessageBox.StandardButton.Yes
                      | QMessageBox.StandardButton.No)
    state = {"shown": False}

    def modal():
        return box if state["shown"] else None

    monkeypatch.setattr(d, "modal", modal)
    monkeypatch.setattr(d, "modal_text", lambda w: "Replace it?")
    real_pump = d.pump
    first = {"done": False}

    def pump(ms=300):
        # the question comes up after the harness starts waiting for it
        if not first["done"]:
            first["done"] = True
            box.show()
            state["shown"] = True
        real_pump(ms)

    monkeypatch.setattr(d, "pump", pump)
    clicked = {}
    box.buttonClicked.connect(lambda b: clicked.setdefault("at", d.app.calls))
    d.answer("Yes", within_ms=2000)
    assert "at" in clicked, "the button was never clicked"
    assert d.app.calls == clicked["at"], (
        "answer() called processEvents() after the click")
    d.pump(300)
    assert d.app.calls == clicked["at"]
    box.deleteLater()


def test_the_next_step_pumps_again(userdrive, qapp, tmp_path, monkeypatch):
    """The guard lasts one step: once the drive has yielded back to the
    loop, `pump` works as before.

    MUTATION: drop `self._closed_a_modal = False` at the top of `step` in
    `Drive.run`: every pump after the first answered modal is then a no-op,
    and this goes red.
    """
    d = _bare_drive(userdrive, qapp, tmp_path)
    d._log = tmp_path / "log.txt"
    d._log.write_text("")
    d._log_offset = 0
    d.win = type("W", (), {"close": lambda self: None})()
    seen = {}

    def script(dd):
        dd._modal_closed()            # as answer/answer_file do
        yield 50
        before = dd.app.calls
        dd.pump(100)
        seen["pumped"] = dd.app.calls - before

    monkeypatch.setattr(d, "app", d.app)
    d.run(script)
    assert seen.get("pumped", 0) > 0, (
        "pump() stayed inert in the step after the one that closed a modal")
