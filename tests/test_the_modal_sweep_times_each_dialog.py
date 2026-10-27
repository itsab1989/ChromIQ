"""The suite's modal sweep (`tests/conftest.py::_no_modal_may_hang_the_suite`)
times each dialog from when it is first seen visible.

Review r7 of 4.3.18: it used to be one 4 s timer started at the test's setup.
On a loaded worker, setup plus building a box took longer than that, the
already-due timer fired in the test's first `processEvents()`, and a box shown
a moment before was rejected. The preflight test then measured a box that was
no longer visible and failed with "a modal dialog was left open".

These pin both halves: a slow setup never eats a dialog's grace, and a dialog
that really is left up (a hung `exec()`, a static `QMessageBox` helper) is
still ended and named.
"""
from __future__ import annotations

import time

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _box(title="A box under test"):
    box = QMessageBox()
    box.setWindowTitle(title)
    box.setText("A box under test")
    return box


def _gone(box, app):
    box.close()
    box.deleteLater()
    app.processEvents()


def test_a_dialog_is_timed_from_when_it_is_first_seen(
        app, _no_modal_may_hang_the_suite):
    now = [100.0]                     # a setup that took 100 s already
    sweep = type(_no_modal_may_hang_the_suite)(clock=lambda: now[0])
    sweep.tick()                      # nothing up yet
    box = _box()
    box.show()
    for t in (100.25, 101.0, 103.0, 104.0):
        now[0] = t
        sweep.tick()
        assert box.isVisible(), f"closed {t - 100.0:.2f} s after it was shown"
    now[0] = 104.25
    sweep.tick()
    assert not box.isVisible(), "a box visible past its grace was left up"
    # on macOS a QMessageBox ignores its window title, so the class names it
    assert sweep.stuck in (["A box under test"], ["QMessageBox"])
    _gone(box, app)


def test_a_dialog_hidden_in_between_starts_again(app, _no_modal_may_hang_the_suite):
    now = [0.0]
    sweep = type(_no_modal_may_hang_the_suite)(clock=lambda: now[0])
    box = _box()
    box.show()
    sweep.tick()
    now[0] = 3.5
    box.hide()
    sweep.tick()
    box.show()
    now[0] = 3.75
    sweep.tick()
    now[0] = 7.5
    sweep.tick()
    assert box.isVisible() and not sweep.stuck
    _gone(box, app)


def test_a_slow_setup_never_eats_a_dialogs_grace(app, _no_modal_may_hang_the_suite):
    """The real fixture, the real clock: longer than the grace passes before
    the box is shown (the loaded worker of review r7), and the box shown
    afterwards is still up after the event loop has run. With the old single
    timer this is exactly the failure."""
    import conftest as C
    time.sleep(C.MODAL_GRACE_MS / 1000.0 + 0.5)
    box = _box()
    box.show()
    app.processEvents()
    assert box.isVisible(), "the sweep closed a box shown a moment before"
    _gone(box, app)
    assert not _no_modal_may_hang_the_suite.stuck


def test_a_hung_exec_is_still_ended_and_named(app, _no_modal_may_hang_the_suite):
    sweep = type(_no_modal_may_hang_the_suite)(grace_ms=300)
    timer = QTimer()
    timer.setInterval(50)
    timer.timeout.connect(sweep.tick)
    timer.start()
    dlg = QDialog()
    dlg.setWindowTitle("A dialog nobody answers")
    t0 = time.monotonic()
    try:
        got = dlg.exec()
    finally:
        timer.stop()
    took = time.monotonic() - t0
    assert got == QDialog.DialogCode.Rejected.value
    assert sweep.stuck == ["A dialog nobody answers"]
    assert 0.25 <= took < 3.5, f"ended after {took:.2f} s"
    dlg.deleteLater()


def test_a_static_message_box_is_still_ended(app, _no_modal_may_hang_the_suite):
    sweep = type(_no_modal_may_hang_the_suite)(grace_ms=300)
    timer = QTimer()
    timer.setInterval(50)
    timer.timeout.connect(sweep.tick)
    timer.start()
    try:
        QMessageBox.information(None, "Nobody reads this", "Nobody reads this")
    finally:
        timer.stop()
    assert sweep.stuck and sweep.stuck[0] in ("Nobody reads this",
                                               "QMessageBox")


def test_the_sweep_ticks_and_the_grace_is_unchanged():
    import conftest as C
    assert C.MODAL_GRACE_MS == 4000
    assert 0 < C.MODAL_SWEEP_TICK_MS <= 500
