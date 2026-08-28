"""#130 (Knut, 2026-07-29): the instrument fault sounds at once, and again with
its window.

His decision, reversing the two-second design of beta.90:

    *"abort changing the design for Instrument errors appearing immediately.
    Leave the code as it was earlier: the instrument sound appearing
    immediately, and then the instrument error window appearing when the error
    run ends, but then keep the sound also when the window appears."*

**One part of the older behaviour is deliberately not restored.** The cue used
to hang off the signal, and a pulled cable emits dozens of identical messages —
so it fired dozens of times. He asked for a sound when the fault appears, not
for a burst of them, so the immediate sound is once per run.
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


class _Tab:
    _sound_instrument_fault_once = TabMeasure._sound_instrument_fault_once

    def __init__(self):
        self.cues = []
        self._instrument_fault_sounded = False

    def _cue_window(self, event):
        self.cues.append(event)


def test_the_fault_sounds_immediately(qapp):
    tab = _Tab()
    tab._sound_instrument_fault_once()
    assert tab.cues == ["INSTRUMENT_ERROR"]


def test_a_stream_of_errors_sounds_once(qapp):
    """His log had dozens of ReadPipeAsync lines. One fault, one sound."""
    tab = _Tab()
    for _ in range(50):
        tab._sound_instrument_fault_once()
    assert tab.cues == ["INSTRUMENT_ERROR"]


def test_the_next_run_can_sound_again():
    """The flag is cleared when a measurement starts."""
    src = inspect.getsource(TabMeasure._on_start)
    assert "self._instrument_fault_sounded = False" in src


def test_the_two_second_design_is_gone():
    """He asked for it to be aborted, so it should leave no remains."""
    src = inspect.getsource(TabMeasure)
    for name in ("_arm_streaming_error_window", "_streaming_error_elapsed",
                 "_STREAMING_ERROR_HOLD_MS"):
        assert name not in src, f"{name} is still there"


def test_the_disconnect_sounds_at_once_and_then_offers_the_one_ending():
    """The sound comes before the ending window, because the window blocks.

    This used to require `abort()` before the sound. `abort()` is a SECOND
    exit, which §1 of measurement_exit_strategy.md forbids, and on every
    instrument that is not a CR30 it destroys the session outright — stock
    chartread writes its .ti3 only on a clean exit. So a disconnect was
    survivable for one instrument and fatal for another on the very same line.
    The reader is still ended, through the ending every route shares, and the
    user is the one who chooses how.
    """
    src = inspect.getsource(TabMeasure._on_instrument_disconnected)
    assert "_sound_instrument_fault_once()" in src
    assert "self._manager.abort()" not in src, (
        "the disconnect ends the session behind the user's back")
    lines = [l.strip() for l in src.splitlines()]
    sound = next(i for i, l in enumerate(lines)
                 if "_sound_instrument_fault_once()" in l)
    ending = next(i for i, l in enumerate(lines)
                  if "_confirm_end_of_session" in l)
    assert sound < ending, (
        "the ending window blocks, so the fault must sound before it opens")


def test_a_save_in_progress_is_still_protected():
    src = inspect.getsource(TabMeasure._on_instrument_disconnected)
    lines = [l.strip() for l in src.splitlines()]
    guard = next(i for i, l in enumerate(lines) if "save_partial_in_progress" in l)
    sound = next(i for i, l in enumerate(lines)
                 if "_sound_instrument_fault_once()" in l)
    assert guard < sound


def test_the_window_still_sounds_when_it_opens():
    """"…but then keep the sound also when the window appears." """
    src = inspect.getsource(TabMeasure._show_instrument_disconnected_window)
    assert '_cue_window("INSTRUMENT_ERROR")' in src


def test_the_window_is_shown_at_the_end_of_the_run():
    src = inspect.getsource(TabMeasure._on_measure_done)
    assert "_show_instrument_disconnected_window()" in src
    assert "_instrument_window_shown" not in src, \
        "the 2-second suppression should be gone with the rest of it"
