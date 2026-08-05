"""A measurement window does not outlive its measurement.

Knut, beta.139, answering the question left open in beta.137: *"When the
measurement session ends, everything relating to measurements should end, I
would think. Restarted when starting a measurement, correct?"*

Each of these windows runs its own event loop, so chartread's output keeps
arriving while one is up — and the process can end underneath it. Before this,
the window stayed on screen and its buttons wrote keys into a process that no
longer existed, which is the "no active process" warning in his logs.
"""
from __future__ import annotations

import inspect
import re

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QDialog

from core.settings import DEFAULTS
from core.argyll_runner import ArgyllRunner
from ui.tabs.tab_measure import TabMeasure


class _Settings:
    def __init__(self):
        self.d = dict(DEFAULTS)

    def get(self, k, d=None):
        return self.d.get(k, d)

    def set(self, k, v):
        self.d[k] = v


#: Every window raised while a read is in progress.
DURING_A_READ = [
    "_prompt_too_fast_strip", "_on_strip_misaligned", "_on_wrong_strip",
    "_on_unexpected_response", "_on_sensor_wrong_position",
    "_on_strip_interrupted", "_legacy_patches_still_unread",
    "_on_generic_instrument_error", "_on_xy_place_sheet",
    "_show_instrument_disconnected_window", "_on_strip_error",
    "_on_calibration_done",
]


@pytest.fixture
def tab(qapp):
    return TabMeasure(ArgyllRunner(_Settings()), _Settings())


@pytest.mark.parametrize("name", DURING_A_READ)
def test_every_during_a_read_window_is_registered(tab, name):
    """A bare dlg.exec() cannot be closed by the session ending — it has to go
    through the helper that remembers it."""
    src = inspect.getsource(getattr(tab, name))
    assert not re.search(r"^\s+dlg\.exec\(\)\s*$", src, re.M), \
        f"{name} runs a bare dlg.exec(); use _exec_measurement_window"
    assert "_exec_measurement_window" in src, \
        f"{name} does not register its window"


def test_the_session_ending_closes_an_open_window(tab, qapp):
    """The real thing: a window is up, the measurement ends, the window goes."""
    dlg = QDialog(tab)
    closed_by = []

    def _end_the_session():
        tab._on_measure_done(0)
        closed_by.append(dlg.isVisible())

    # A safety net, so a regression fails the test instead of hanging it: if
    # the ending does not close the window, this does, a beat later.
    QTimer.singleShot(0, _end_the_session)
    QTimer.singleShot(250, dlg.reject)
    tab._exec_measurement_window(dlg)      # returns only once it is closed

    assert closed_by == [False], "the window survived the session ending"
    assert tab._live_measure_windows == []


def test_a_choice_made_after_the_ending_is_not_sent(tab):
    """Its button would otherwise write a key into a finished process, which is
    where the "no active process" warning came from."""
    sent = []
    tab._manager.send_key = lambda k: sent.append(k)
    assert not tab._runner.is_running          # nothing running in a test
    tab._send_failure_choice("\r")
    assert sent == [], "a key went out after the measurement had ended"
