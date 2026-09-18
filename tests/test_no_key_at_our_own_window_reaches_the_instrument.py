"""R23-F2 (B8-389). A key pressed at a window ChromIQ raised is that window's.

`TabMeasure` installs its key filter on the **whole application** while a
session is live, so it is first in line for every keystroke -- including one
pressed at a modal window ChromIQ has just put in front of the user. It
forwarded that key to the reader and then ate it.

What that cost, measured through a real pty in round 23 and again here: with
*"Keep what you have measured so far?"* on screen, Escape put ``\\x1b`` down the
pipe. On stock chartread ``\\x1b`` at a prompt is **give up**, and chartread then
returns without writing its ``.ti3`` (chartread.c:1654) -- so the key the user
pressed to dismiss a window *offering to save their work* had already thrown it
away. The window did not even close, because the filter consumed the event, so
the natural next move was to press Escape again. Return had the mirror fault:
eaten here, so the default button could not be pressed from the keyboard at all.

The fix is a modal gate in `eventFilter` -- ``activeModalWidget() is not None``
-> ``return False`` -- not a tenth remove-and-reinstall. Nine failure-window
slots each removed the filter by hand and the routes every ending goes through
(`_on_stop`, `_confirm_end_of_session`, `confirm_quit_during_measurement`) did
not; a tenth removal would only have left the eleventh window to remember.
`measurement_exit_strategy.md` note 8a.

**These guards run the app's own sequence**: the real Stop button, the real
window, a real key event through the real application (so the real filter is
first in line), and a real `ArgyllRunner` writing to a real pty with a real
live child on the far end. What is asserted is the byte that arrived there.
"""
from __future__ import annotations

import ast
import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import Qt                               # noqa: E402
from PyQt6.QtTest import QTest                            # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from tests.helpers.live_reader import (                   # noqa: E402
    THE_LINES_THAT_START_A_SESSION, WindowDriver, measuring,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _press(key):
    return lambda w: QTest.keyClick(w, key)


# ---- the harness is the app's own starting state -------------------------
def test_the_harness_starts_the_session_the_way_the_app_does():
    """`a_live_session` stands in for pressing Start, so it must not drift.

    If `_on_start` ever makes a session live some other way, these guards are
    measuring a state the app no longer produces -- and they would go on
    passing while doing it.
    """
    from ui.tabs.tab_measure import TabMeasure

    src = inspect.getsource(TabMeasure._on_start)
    for line in THE_LINES_THAT_START_A_SESSION:
        assert line in src, (
            f"`_on_start` no longer contains {line!r}, so the harness in "
            f"tests/helpers/live_reader.py is reproducing a session state the "
            f"app does not create any more")


def test_the_reader_at_the_far_end_is_real(qapp, tmp_path):
    """Without a LIVE child `is_running` is False and nothing is ever sent."""
    with measuring(tmp_path) as (tab, reader):
        assert reader.alive, "the stand-in reader died before the guard ran"
        assert tab._runner.is_running is True, (
            "`_send_failure_choice` early-returns when the runner is not "
            "running, so every byte this file asserts on would be dropped "
            "before it was written and the guards would pass over the fault")
        tab._manager.send_key("x")
        assert reader.wait_for_a_byte() == b"x", (
            "a key sent by the real manager did not arrive at the far end of "
            "the real pty, so this harness cannot see what leaves ChromIQ")


def test_the_far_end_is_in_raw_mode(qapp, tmp_path):
    """A canonical pty holds a byte until a newline -- silence would be a lie.

    Round 23's own stand-in had this wrong. Measured both ways: with the
    default line discipline an Escape written to the master is still invisible
    200 ms later; in raw mode it arrives at once. A guard that asserts NOTHING
    was sent is worthless on a pty that could be hiding it.
    """
    import termios

    with measuring(tmp_path) as (_tab, reader):
        attrs = termios.tcgetattr(reader.slave)
        lflag = attrs[3]
        assert not (lflag & termios.ICANON), (
            "the far end is in canonical mode, so a byte can sit in the line "
            "discipline unread and 'nothing arrived' proves nothing")
        assert not (lflag & termios.ECHO), (
            "ECHO is on, so ChromIQ's own keys come back into its own parser")
        # …and it really does deliver a bare control byte.
        tab_runner = _tab._runner
        tab_runner.write_stdin("\x1b")
        assert reader.wait_for_a_byte() == b"\x1b"


# ---- Escape ---------------------------------------------------------------
def test_escape_at_the_ending_window_sends_nothing_to_the_instrument(
        qapp, tmp_path):
    """The whole fault in one byte: Escape here used to mean GIVE UP."""
    with measuring(tmp_path) as (tab, reader):
        reader.forget()
        driver = WindowDriver(_press(Qt.Key.Key_Escape)).arm()
        tab._stop_btn.click()            # the real Stop button
        driver.disarm()

        assert driver.acted_on == "Keep what you have measured so far?", (
            f"the ending window did not open; the key went to "
            f"{driver.acted_on!r}")
        assert reader.wait_for_a_byte() == b"", (
            "Escape pressed at ChromIQ's own window reached the instrument. "
            "On stock chartread that byte is give-up, and the .ti3 the window "
            "was offering to save is then never written (chartread.c:1654)")


def test_escape_at_the_ending_window_closes_it(qapp, tmp_path):
    """It was consumed, so the window stayed up and the key did nothing."""
    with measuring(tmp_path) as (tab, reader):
        driver = WindowDriver(_press(Qt.Key.Key_Escape)).arm()
        tab._stop_btn.click()
        driver.disarm()

        assert driver.stuck is False, (
            "the ending window was still up after Escape, so the filter ate "
            "the key instead of handing it to the window")


def test_escape_at_the_ending_window_means_keep_measuring(qapp, tmp_path):
    """The positive half: the window answered, and it answered harmlessly."""
    with measuring(tmp_path) as (tab, reader):
        driver = WindowDriver(_press(Qt.Key.Key_Escape)).arm()
        tab._stop_btn.click()
        driver.disarm()

        clicked = driver.window.clickedButton()
        assert clicked is not None and clicked.text() == "Keep measuring", (
            f"Escape pressed {clicked and clicked.text()!r}; a dismissal takes "
            f"the option that changes nothing")
        assert tab._session_live is True
        assert tab._runner.is_running is True, \
            "the session ended, when the user only dismissed a window"


# ---- Return ---------------------------------------------------------------
def test_return_at_the_ending_window_sends_the_save_chain_not_the_key(
        qapp, tmp_path):
    """Return was eaten here, so the default button could not be pressed.

    Now it presses it, and what reaches the instrument is ``d`` -- the first
    key of stock chartread's save chain (`send_save_partial_and_quit`: 'd'
    raises "are you sure", and 'y' there is what writes the .ti3). A bare
    ``\\r`` would be the forwarded keystroke instead.
    """
    with measuring(tmp_path) as (tab, reader):
        reader.forget()
        driver = WindowDriver(_press(Qt.Key.Key_Return)).arm()
        tab._stop_btn.click()
        driver.disarm()

        assert driver.acted_on == "Keep what you have measured so far?"
        assert reader.wait_for_a_byte() == b"d", (
            "what reached the instrument was not the save chain. A bare "
            "carriage return is the forwarded keystroke, which is the fault: "
            "the key was eaten here and the default button never pressed")
        assert driver.stuck is False, \
            "the ending window was still up after Return"
        clicked = driver.window.clickedButton()
        assert clicked is not None and clicked.text() == "Save and stop", (
            f"Return did not press the default button; it pressed "
            f"{clicked and clicked.text()!r}")


# ---- and the filter still does its job ------------------------------------
def test_with_no_window_up_the_keys_still_reach_the_instrument(qapp, tmp_path):
    """The gate must not switch the filter off. A key pressed at the TAB is
    still the instrument's -- that is what the filter is for."""
    with measuring(tmp_path) as (tab, reader):
        reader.forget()
        assert QApplication.instance().activeModalWidget() is None
        QTest.keyClick(tab, Qt.Key.Key_Space)
        assert reader.wait_for_a_byte() == b" ", (
            "a key pressed with no window up no longer reaches the reader, so "
            "the fix has switched the filter off rather than gating it")


def test_the_gate_asks_about_a_modal_window_not_about_a_flag():
    """A removal has a failure mode this fix exists to avoid.

    Nine slots removed the filter by hand and the ending routes did not. If the
    gate ever goes back to a flag somebody has to set, the eleventh window is
    unguarded again -- so the structure is held as well as the behaviour.
    """
    from ui.tabs.tab_measure import TabMeasure

    fn = next(n for n in ast.walk(ast.parse(inspect.getsource(TabMeasure)))
              if isinstance(n, ast.FunctionDef) and n.name == "eventFilter")
    calls = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "activeModalWidget"]
    assert calls, (
        "`eventFilter` no longer asks whether one of ChromIQ's own windows is "
        "up, so every window that forgets to remove the filter by hand sends "
        "the user's keystrokes to the instrument again")
