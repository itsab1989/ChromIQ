"""Log panels are user-resizable, shared, remembered, and reset by defaults.

Basti: *"the fields for log output became pretty big now. would it be possible
to make them resizeable by the user (clicking and dragging) and the app should
remember the size? resetting to factory defaults should restore it. and resizing
them on one tab should resize them on all."*

All four properties come from one place: the number of visible lines is a
setting, and ``fit_log_height`` is the only thing that sizes a log — so the
panels cannot drift apart by construction.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QPlainTextEdit

from core.settings import DEFAULTS
from ui.widgets import (LOG_MAX_LINES, LOG_MIN_LINES, LOG_VISIBLE_LINES,
                        LogResizeGrip, bind_log_settings, fit_log_height,
                        log_visible_lines, refresh_log_panes_from_settings,
                        set_log_visible_lines)


class _Settings:
    def __init__(self):
        self.d = dict(DEFAULTS)

    def get(self, k, d=None):
        return self.d.get(k, d)

    def set(self, k, v):
        self.d[k] = v

    def reset_to_defaults(self):
        self.d = dict(DEFAULTS)


@pytest.fixture
def bound(qapp):
    s = _Settings()
    bind_log_settings(s)
    yield s
    bind_log_settings(None)


def _log(qapp):
    w = QPlainTextEdit()
    fit_log_height(w)
    return w


# ---- the default is still what Knut asked for ---------------------------
def test_the_default_is_nine_lines(bound):
    assert DEFAULTS["log_visible_lines"] == LOG_VISIBLE_LINES == 9
    assert log_visible_lines() == 9


# ---- resizing one resizes them all --------------------------------------
def test_every_panel_follows_one_size(bound, qapp):
    logs = [_log(qapp) for _ in range(4)]
    before = [w.maximumHeight() for w in logs]
    assert len(set(before)) == 1, "panels started at different sizes"

    set_log_visible_lines(20)
    after = [w.maximumHeight() for w in logs]
    assert len(set(after)) == 1, "the panels drifted apart"
    assert after[0] > before[0]


def test_a_panel_created_later_gets_the_current_size(bound, qapp):
    """Opening a tab for the first time after a resize must not show a
    nine-line panel among twenty-line ones."""
    set_log_visible_lines(15)
    late = _log(qapp)
    early = _log(qapp)
    assert late.maximumHeight() == early.maximumHeight()


# ---- it is remembered ----------------------------------------------------
def test_the_size_is_remembered(bound, qapp):
    _log(qapp)
    set_log_visible_lines(17)
    assert bound.get("log_visible_lines") == 17
    assert log_visible_lines() == 17


def test_a_drag_in_progress_is_not_saved_until_it_ends(bound, qapp):
    """A slow drag must not write the setting on every pixel."""
    _log(qapp)
    set_log_visible_lines(12)                 # a committed size
    set_log_visible_lines(30, save=False)     # mid-drag
    assert bound.get("log_visible_lines") == 12


# ---- factory defaults ----------------------------------------------------
def test_restore_factory_defaults_puts_it_back(bound, qapp):
    logs = [_log(qapp) for _ in range(3)]
    set_log_visible_lines(25)
    tall = logs[0].maximumHeight()

    bound.reset_to_defaults()
    refresh_log_panes_from_settings()      # what the Settings dialog calls
    assert bound.get("log_visible_lines") == 9
    assert logs[0].maximumHeight() < tall
    assert len({w.maximumHeight() for w in logs}) == 1


# ---- bounds --------------------------------------------------------------
@pytest.mark.parametrize("asked,expected", [
    (1, LOG_MIN_LINES), (0, LOG_MIN_LINES), (-5, LOG_MIN_LINES),
    (999, LOG_MAX_LINES), (9, 9),
])
def test_it_cannot_be_dragged_to_a_useless_size(bound, qapp, asked, expected):
    assert set_log_visible_lines(asked) == expected


def test_a_corrupt_stored_value_falls_back(bound, qapp):
    bound.set("log_visible_lines", "not a number")
    assert log_visible_lines() == LOG_VISIBLE_LINES


# ---- the grip ------------------------------------------------------------
def test_the_grip_is_installed_once(bound, qapp):
    w = _log(qapp)
    grip = getattr(w, LogResizeGrip._INSTALLED, None)
    assert grip is not None
    fit_log_height(w)                          # re-sizing must not stack grips
    assert getattr(w, LogResizeGrip._INSTALLED) is grip


def test_the_panel_says_it_can_be_dragged(bound, qapp):
    """A resize handle nobody knows about is not a feature."""
    w = _log(qapp)
    tip = w.toolTip()
    assert "Drag the top edge" in tip
    assert "Every log panel" in tip            # says it affects them all
    assert "remembered" in tip
    assert "Restore Factory Defaults" in tip   # says how to undo it


def test_dragging_the_top_edge_resizes(bound, qapp):
    """The real path: press near the top edge, move up, release."""
    w = _log(qapp)
    w.resize(400, w.maximumHeight())
    grip = getattr(w, LogResizeGrip._INSTALLED)
    start = log_visible_lines()

    def _mouse(kind, y):
        return QMouseEvent(kind, QPointF(10.0, float(y)), QPointF(10.0, float(y)),
                           Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                           Qt.KeyboardModifier.NoModifier)

    grip.eventFilter(w, _mouse(QEvent.Type.MouseButtonPress, 2))
    line = w.fontMetrics().lineSpacing()
    grip.eventFilter(w, _mouse(QEvent.Type.MouseMove, 2 - 5 * line))   # drag UP
    assert log_visible_lines() == start + 5, "dragging up did not make it taller"
    grip.eventFilter(w, _mouse(QEvent.Type.MouseButtonRelease, 2 - 5 * line))
    assert bound.get("log_visible_lines") == start + 5, "not saved on release"


def test_a_press_away_from_the_edge_is_left_to_the_log(bound, qapp):
    """Selecting text in the middle of a log must not start a resize."""
    w = _log(qapp)
    grip = getattr(w, LogResizeGrip._INSTALLED)
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(10.0, 80.0),
                     QPointF(10.0, 80.0), Qt.MouseButton.LeftButton,
                     Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    assert grip.eventFilter(w, ev) is False
    assert grip._dragging is False


def test_a_finished_drag_keeps_its_size(bound, qapp):
    """Basti, trying it from source: *"when I let go it immediately resets to
    the size it was before"*.

    Releasing used to re-read the size from the setting — which a drag
    deliberately does not write, so it still held the size the drag started
    from, and letting go threw the whole drag away.
    """
    w = _log(qapp)
    grip = getattr(w, LogResizeGrip._INSTALLED)
    start = log_visible_lines()
    line = w.fontMetrics().lineSpacing()

    def _mouse(kind, y):
        return QMouseEvent(kind, QPointF(10.0, float(y)), QPointF(10.0, float(y)),
                           Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                           Qt.KeyboardModifier.NoModifier)

    grip.eventFilter(w, _mouse(QEvent.Type.MouseButtonPress, 2))
    grip.eventFilter(w, _mouse(QEvent.Type.MouseMove, 2 - 6 * line))
    tall = w.maximumHeight()
    grip.eventFilter(w, _mouse(QEvent.Type.MouseButtonRelease, 2 - 6 * line))

    assert w.maximumHeight() == tall, "the panel snapped back on release"
    assert log_visible_lines() == start + 6
    assert bound.get("log_visible_lines") == start + 6


def test_the_drag_reference_does_not_move_with_the_panel(bound, qapp):
    """Basti: *"dragging works but looks jumpy"*.

    The panel's top edge moves as it grows, so a drag measured inside the
    widget fed each resize into the next delta. The reference is the pointer's
    position on the SCREEN, which a resize cannot move.
    """
    import inspect
    src = inspect.getsource(LogResizeGrip)
    assert "globalPosition" in src, "the drag is measured in local coordinates"
    # …and every drag reference goes through the one helper.
    assert src.count("self._global_y(event)") == 2
