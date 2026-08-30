"""#159 / Windows: the "how to measure" window outlived its measurement.

Knut's rule, beta.139: *"When the measurement session ends, everything relating
to measurements should end."* Every window that can end a session was brought
under it. This one was not — it explains how to measure the chart, it is shown
once per session, and it stayed on screen afterwards, offering "Start
measuring" for a session that had already finished.

The reason it was missed is worth keeping: `_live_measure_windows` is filled by
`_exec_measure_dialog`, which wraps `exec()`. This window is MODELESS — it uses
`show()`, deliberately, because the reading is driven by the instrument's own
button and a modal would sit between the user and the preview they are meant to
be watching. So it never went through the one place that registers a window.

Found on the owner's Windows VM; reproduced on macOS, so it was never
platform-specific — only unnoticed.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                     # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,               # noqa: E402
                             QWidget)

from ui.tabs.tab_measure import TabMeasure                         # noqa: E402


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


class _Tab(QWidget):
    """Carries the real methods; everything they touch is a stand-in.

    A QWidget because the window is parented to the tab — which is also what
    makes the leak survivable rather than fatal: it is destroyed with the tab,
    eventually. "Eventually" is not what Knut's rule asks for.
    """

    _show_cr30_measuring_window = TabMeasure._show_cr30_measuring_window
    _close_measurement_windows = TabMeasure._close_measurement_windows
    _forget_measure_window = TabMeasure._forget_measure_window

    def __init__(self):
        super().__init__()
        self._live_measure_windows: list = []
        self._cr30_how_shown = False


def test_the_window_is_registered_with_the_session(app):
    tab = _Tab()
    tab._show_cr30_measuring_window()
    try:
        assert tab._live_measure_windows, (
            "the how-to window is not registered, so the ending cannot reach it")
        assert isinstance(tab._live_measure_windows[0], QDialog)
    finally:
        tab._close_measurement_windows()


def test_it_closes_when_the_measurement_ends(app):
    """The assertion that matters to the user: the window goes away."""
    tab = _Tab()
    tab._show_cr30_measuring_window()
    dlg = tab._live_measure_windows[0]
    assert dlg.isVisible(), "the window never appeared"

    tab._close_measurement_windows()
    app.processEvents()

    assert not dlg.isVisible(), (
        "the how-to window survived its measurement — it still offers 'Start "
        "measuring' for a session that has finished")


def test_closing_it_by_hand_does_not_leave_a_dead_entry(app):
    """It is modeless, so the user can close it while the session runs. The
    registry must not then hold a window that is already gone — the ending
    would call reject() on it, and a deleted C++ object raises."""
    tab = _Tab()
    tab._show_cr30_measuring_window()
    dlg = tab._live_measure_windows[0]

    dlg.accept()                       # the user presses "Start measuring"
    app.processEvents()

    assert tab._live_measure_windows == [], (
        "the closed window is still registered as live")
    tab._close_measurement_windows()   # must not raise


def test_the_ending_survives_a_window_qt_has_already_destroyed(app):
    """Belt and braces: _close_measurement_windows already guards RuntimeError,
    and this proves that guard covers the window just added to its list."""
    tab = _Tab()
    tab._show_cr30_measuring_window()
    dlg = tab._live_measure_windows[0]
    dlg.deleteLater()
    app.processEvents()
    tab._close_measurement_windows()   # must not raise
