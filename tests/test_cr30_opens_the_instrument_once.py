"""#159 (report 13, V-5): a single Start opened the instrument twice.

The calibration stands the bridge up before the helper starts, deliberately, so
that it calibrates through the SESSION's reader — over Bluetooth a second handle
is a full disconnect and reconnect of a peripheral that accepts one connection
at a time. Then `_on_start` called `_open_cr30_bridge()` again unconditionally,
and that begins with `_close_cr30_bridge()` — closing the instrument the
calibration had just opened and used. Measured on screen: two DeviceReader
constructions and two close() calls for one Start.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                         # noqa: E402

from core.argyll_runner import ArgyllRunner                      # noqa: E402
from core.settings import AppSettings                            # noqa: E402
from ui.tabs.tab_measure import TabMeasure                       # noqa: E402


@pytest.fixture
def tab():
    QApplication.instance() or QApplication([])
    s = AppSettings()
    return TabMeasure(ArgyllRunner(s), s)


def test_a_standing_bridge_is_not_rebuilt(tab):
    tab._open_cr30_bridge()
    first_reader = tab._cr30_reader
    first_bridge = tab._cr30_bridge
    assert first_bridge is not None, "the bridge did not come up at all"

    tab._open_cr30_bridge()          # the second, unconditional call
    assert tab._cr30_reader is first_reader, (
        "the instrument was reopened — the calibration's handle is closed and "
        "over Bluetooth that is a disconnect")
    assert tab._cr30_bridge is first_bridge


def test_a_previous_session_is_not_inherited(tab):
    """The guard must not turn into a leak: a Start still lets go of whatever
    the last session was holding."""
    import inspect
    src = inspect.getsource(TabMeasure._calibrate_and_confirm)
    # The CALLS, not the words: both names appear in the comment above them.
    i = src.index("self._open_cr30_bridge()")
    assert "self._close_cr30_bridge()" in src[:i], (
        "a Start can inherit the previous session's reader")
