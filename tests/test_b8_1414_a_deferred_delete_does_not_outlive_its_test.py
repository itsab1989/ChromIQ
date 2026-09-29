"""B8-1414: a window a test deleteLater()s is gone when the next test starts.

The "stray quit" of `test_the_next_step_pumps_again`
(`tests/test_a_driver_returns_to_a_modal_it_closed.py`) was other tests'
windows. Measured with a probe in 13 everyday runs (7 of them red on it): at
the moment the drive's `QApplication.exec()` ended itself, Qt's
`lastWindowClosed` had fired 3 to 157 ms into the loop, never inside a garbage
collection, and the windows visible at the test's start were ones earlier
tests had shown and then `deleteLater()`'d (`test_log_panes_resizable.py`,
`test_a_spinbox_fits_its_own_special_value.py`, ...). A deferred delete posted
with no event loop running waits for the next loop that STARTS; plain
`processEvents()` never runs it. So the first `exec()` on the worker destroyed
them, the last visible window closed, and quit-on-last-window-closed ended the
drive. It happened with and without B8-1400's collection.

`tests/conftest.py::_a_test_deletes_what_it_deleted_later` sends the queued
DeferredDelete events in every test's teardown. These tests pin that, in
order, in one file (`--dist loadfile` keeps a file on one worker).

Mutations (each red, run as this file alone): M1414-a remove the conftest
fixture: the window survives into the next test, and the loop the third test
starts ends by itself; M1414-b send the posted events of every type but
DeferredDelete (`sendPostedEvents()` with no type): the same.
"""
from __future__ import annotations

import time

import pytest

_LEFT: dict = {}


def test_a_test_shows_a_window_and_deletes_it_later(qapp):
    from PyQt6.QtWidgets import QWidget
    w = QWidget()
    w.setWindowTitle("B8-1414: shown, then deleteLater()'d, no loop running")
    w.show()
    qapp.processEvents()
    _LEFT["window"] = w
    w.deleteLater()
    qapp.processEvents()             # does not run a deferred delete
    from PyQt6 import sip
    assert not sip.isdeleted(w), (
        "processEvents() ran the deferred delete by itself; the premise of "
        "B8-1414 (and of this file) has changed, re-measure it")


def test_it_is_gone_when_the_next_test_starts():
    from PyQt6 import sip
    if "window" not in _LEFT:
        pytest.skip("run with the test above it (the file in order)")
    assert sip.isdeleted(_LEFT["window"]), (
        "a window the previous test deleteLater()'d is still alive: its "
        "deletion now waits for the next event loop anybody starts, and if "
        "it is the last visible window that loop quits by itself (B8-1414)")


def test_an_event_loop_after_it_runs_until_it_is_told_to_stop(qapp):
    """The failure itself: the first exec() after the test above must reach
    its own timer, not end at its first turn because the window the first
    test deleteLater()'d is destroyed inside it and was the last visible one.
    (In the full suite other windows may be visible and hide the fault; run
    as this file alone it is deterministic.)"""
    import gc
    from PyQt6.QtCore import QTimer
    gc.collect()                     # no garbage window may close in the loop
    reached = {}

    def mark():
        reached["timer"] = time.monotonic()
        qapp.quit()

    QTimer.singleShot(150, mark)
    t0 = time.monotonic()
    qapp.exec()
    assert "timer" in reached, (
        f"the event loop ended by itself after {time.monotonic() - t0:.3f} s, "
        "before its own timer: a window deleted inside it was the last "
        "visible one (B8-1414)")
