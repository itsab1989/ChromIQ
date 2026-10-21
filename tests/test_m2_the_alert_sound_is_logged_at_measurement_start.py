"""M2 (Knut, Sonoma 14): the i1Pro 2 "ready" beep is ArgyllCMS's call to the
macOS SYSTEM ALERT, so it follows "Alert volume" and "Play sound effects
through", not the output volume ChromIQ's own sounds use. A measurement start
now logs both, from a background thread (one AppleScript question and an
in-process CoreAudio query), never on the GUI thread and never per strip.
"""
from __future__ import annotations

import inspect
import sys
import threading

import pytest

from core import alert_sound as A


def test_the_line_names_volume_and_device(monkeypatch):
    monkeypatch.setattr(A, "_alert_volume", lambda: 75)
    monkeypatch.setattr(A, "_coreaudio_devices", lambda: ("USB DAC", "Speakers"))
    line = A.describe()
    assert "alert volume 75" in line
    assert "'USB DAC', NOT the same as the output device 'Speakers'" in line


def test_a_muted_alert_says_the_beep_will_not_be_heard(monkeypatch):
    monkeypatch.setattr(A, "_alert_volume", lambda: 0)
    monkeypatch.setattr(A, "_coreaudio_devices", lambda: ("Speakers", "Speakers"))
    line = A.describe()
    assert "alert volume 0 (MUTED" in line and "the same as" in line


def test_nothing_known_is_still_one_line(monkeypatch):
    monkeypatch.setattr(A, "_alert_volume", lambda: None)

    def boom():
        raise OSError("no CoreAudio")
    monkeypatch.setattr(A, "_coreaudio_devices", boom)
    line = A.describe()
    assert "alert volume unknown" in line and "unknown or no device" in line


def test_it_runs_off_the_gui_thread_and_only_on_macos(monkeypatch):
    seen = {}

    def fake():
        seen["thread"] = threading.current_thread()
        return "x"
    monkeypatch.setattr(A, "describe", fake)
    monkeypatch.setattr(sys, "platform", "darwin")
    t = A.log_alert_sound_state_async()
    t.join(5)
    assert seen["thread"] is not threading.main_thread()
    assert t.daemon
    monkeypatch.setattr(sys, "platform", "win32")
    assert A.log_alert_sound_state_async() is None


def test_a_measurement_start_asks_once():
    from workflow.measure_manager import MeasureManager
    src = inspect.getsource(MeasureManager.start)
    assert src.count("log_alert_sound_state_async()") == 1
    # never from the per-strip event handler
    assert "log_alert_sound_state_async" not in inspect.getsource(
        MeasureManager._handle_engine_line)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_the_real_query_answers_quickly_here():
    import time
    t0 = time.monotonic()
    line = A.describe()
    assert line.startswith("macOS alert sound at measurement start")
    assert time.monotonic() - t0 < 10
