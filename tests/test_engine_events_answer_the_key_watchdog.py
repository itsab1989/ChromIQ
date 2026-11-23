"""A calibration the engine answers with events only raises no false warning.

4.3.58, seen 8 times in a tester's logs: "Start Calibration" sends its key and
arms the 12 s no-response watchdog (`TabMeasure._arm_key_watchdog`). The
watchdog was reset only by a prose line (`_on_log_line`), but ChromIQ's engine
helper answers a calibration with typed JSON events only (`dual_calibration`,
`cal_done`). So the log said "No response from chartread after sending a key"
12 s after the key, although the calibration had finished after 6 s
(key 07:34:04, cal_done 07:34:10, warning 07:34:16).

Pinned here, on the real `TabMeasure` and the real `MeasureManager`, with the
watchdog's interval shortened so the test takes a second, not twelve:

* a calibration answered only by JSON events leaves no warning;
* a helper that really says nothing after the key still gets the warning.
"""
from __future__ import annotations

import functools
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtTest import QTest                            # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

WARNING = "No response from chartread after sending a key"
INTERVAL_MS = 400


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Settings:
    def __init__(self):
        self._d = {"appearance": "dark", "chartread_engine": "chromiq"}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


@pytest.fixture
def tab(qapp):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    t = TabMeasure(ArgyllRunner(_Settings()), _Settings())
    mgr = t._manager
    mgr._runner.write_stdin = lambda _data: None
    mgr._engine_active = True
    mgr._guided_state = "disabled"
    # The "Calibration complete" window is not what this pins; it is modal.
    mgr.calibration_done.disconnect(t._on_calibration_done)
    t._cal_done_seen = []
    mgr.calibration_done.connect(functools.partial(t._cal_done_seen.append, 1))
    t._stop_btn.setEnabled(True)          # a reader is running
    t._key_watchdog.setInterval(INTERVAL_MS)
    yield t
    t._key_watchdog.stop()
    t.deleteLater()


def _feed(tab, *events):
    for ev in events:
        tab._manager._handle_engine_line(json.dumps(ev), tab._on_log_line)


def _warned(tab) -> bool:
    return WARNING in tab._log.toPlainText()


def test_a_calibration_answered_by_events_only_gives_no_warning(tab):
    tab._arm_key_watchdog()               # "Start Calibration" sent its key
    _feed(tab,
          {"event": "dual_calibration", "ok": True},
          {"event": "cal_done"})
    assert tab._cal_done_seen, "the cal_done event was not handled"
    QTest.qWait(INTERVAL_MS * 3)
    assert not _warned(tab), (
        "the watchdog warned although the helper answered the key with "
        "cal_done")


def test_any_engine_event_counts_as_an_answer(tab):
    tab._arm_key_watchdog()
    _feed(tab, {"event": "strip_ready", "strip": "A"})
    QTest.qWait(INTERVAL_MS * 3)
    assert not _warned(tab)


def test_a_really_silent_helper_still_warns(tab):
    tab._arm_key_watchdog()
    QTest.qWait(INTERVAL_MS * 3)
    assert _warned(tab), "a helper that said nothing must still be reported"


def test_the_warning_is_still_possible_after_an_answer(tab):
    """An answer to one key does not switch the watchdog off for the next."""
    tab._arm_key_watchdog()
    _feed(tab, {"event": "cal_done"})
    QTest.qWait(INTERVAL_MS * 3)
    assert not _warned(tab)
    tab._arm_key_watchdog()               # the next key, and then silence
    QTest.qWait(INTERVAL_MS * 3)
    assert _warned(tab)
