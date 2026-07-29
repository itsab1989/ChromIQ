"""#130 (Knut, 2026-07-29): a continuing instrument fault shows its window
2 seconds in, not at the end of the run.

    *"After thinking about it, I think it is better to wait 2 seconds, and if
    the instrument error still is present, then show the instrument error
    window. Check if this can be made the rule for all of the instrument errors
    that return a stream of error messages in the terminal log window."*

He pulled the cable mid-measurement and watched `ReadPipeAsync failed` scroll
with nothing to tell him what had happened — the window waited for the reader to
stop. Raising it on the very first line would be the opposite mistake: a glitch
that recovers should not stop you with a window. So the first line starts a
clock, each further line refreshes it, and the window opens only if the fault is
still being reported when the clock runs out.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication              # noqa: E402

from ui.tabs.tab_measure import TabMeasure            # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Tab(__import__("PyQt6.QtCore", fromlist=["QObject"]).QObject):
    """A real QObject (the clock needs a parent), with only the parts the rule
    touches."""
    _arm_streaming_error_window = TabMeasure._arm_streaming_error_window
    _streaming_error_elapsed = TabMeasure._streaming_error_elapsed
    _STREAMING_ERROR_HOLD_MS = TabMeasure._STREAMING_ERROR_HOLD_MS

    def __init__(self):
        super().__init__()
        self.shown = 0
        self._streaming_error_timer = None
        self._instrument_window_shown = False

    def _show_instrument_disconnected_window(self):
        self.shown += 1


def test_it_waits_rather_than_firing_on_the_first_line(qapp):
    tab = _Tab()
    tab._arm_streaming_error_window()
    assert tab.shown == 0, "a single line must not raise a window"
    assert tab._streaming_error_timer is not None, "the clock should be running"


def test_a_fault_that_is_still_happening_shows_the_window(qapp):
    tab = _Tab()
    tab._arm_streaming_error_window()      # the cable comes out
    tab._arm_streaming_error_window()      # …and the errors keep coming
    tab._streaming_error_elapsed()         # 2 seconds later
    assert tab.shown == 1


def test_a_fault_that_recovered_is_left_alone(qapp):
    """A glitch that stopped reporting must not interrupt the user."""
    import time
    tab = _Tab()
    tab._arm_streaming_error_window()
    # pretend the last error was long ago — the fault cleared
    tab._streaming_error_last = time.monotonic() - 10
    tab._streaming_error_elapsed()
    assert tab.shown == 0


def test_the_window_is_shown_once_however_many_errors_arrive(qapp):
    tab = _Tab()
    for _ in range(50):                    # his log had dozens
        tab._arm_streaming_error_window()
    tab._streaming_error_elapsed()
    assert tab.shown == 1


def test_one_clock_runs_at_a_time(qapp):
    tab = _Tab()
    tab._arm_streaming_error_window()
    first = tab._streaming_error_timer
    tab._arm_streaming_error_window()
    assert tab._streaming_error_timer is first, "each error restarted the clock"


def test_the_hold_is_the_two_seconds_he_asked_for():
    assert TabMeasure._STREAMING_ERROR_HOLD_MS == 2000


# ---- and the end of the run does not repeat it --------------------------
def test_the_end_of_run_window_is_skipped_when_it_was_already_shown():
    src = inspect.getsource(TabMeasure._on_measure_done)
    assert "_instrument_window_shown" in src
    assert "if not getattr(self, \"_instrument_window_shown\", False):" in src


def test_the_flag_is_cleared_so_the_next_run_can_warn_again():
    src = inspect.getsource(TabMeasure._on_measure_done)
    assert "self._instrument_window_shown = False" in src


def test_both_paths_use_one_window():
    """The window is defined once, so the two routes cannot drift apart."""
    assert hasattr(TabMeasure, "_show_instrument_disconnected_window")
    src = inspect.getsource(TabMeasure._show_instrument_disconnected_window)
    assert '_cue_window("INSTRUMENT_ERROR")' in src, "it must sound as it opens"
    assert "Instrument Disconnected" in src


def test_the_disconnect_still_stops_the_measurement():
    src = inspect.getsource(TabMeasure._on_instrument_disconnected)
    assert "self._manager.abort()" in src
    lines = [l.strip() for l in src.splitlines()]
    abort = next(i for i, l in enumerate(lines) if "abort()" in l)
    arm = next(i for i, l in enumerate(lines)
               if "_arm_streaming_error_window()" in l)
    assert abort < arm, "stop the reader first, then start the clock"


def test_a_save_in_progress_is_still_protected():
    """The readings live in the reader's memory until it writes them — that
    guard must survive this change."""
    src = inspect.getsource(TabMeasure._on_instrument_disconnected)
    lines = [l.strip() for l in src.splitlines()]
    guard = next(i for i, l in enumerate(lines) if "save_partial_in_progress" in l)
    arm = next(i for i, l in enumerate(lines)
               if "_arm_streaming_error_window()" in l)
    assert guard < arm
