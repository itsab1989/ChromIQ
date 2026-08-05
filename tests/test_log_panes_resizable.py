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
    (999, LOG_MAX_LINES), (9, 9), (2, 2),
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


def test_it_can_be_made_smaller_than_three_lines(bound, qapp):
    """Basti: *"I want to be able to make the log output field even smaller
    (one line of output less should be possible)"*. Two lines still shows a
    message and the one after it, so you can see something arrive."""
    assert LOG_MIN_LINES == 2
    w = _log(qapp)
    tall = w.maximumHeight()
    assert set_log_visible_lines(2) == 2
    assert w.maximumHeight() < tall
    # …and no further, or the panel stops being a panel.
    assert set_log_visible_lines(1) == 2


# ---- and it never grows through the bottom of the window ----------------
#
# Basti, beta.141: *"i also noticed when i expand the log output field to
# maximum then at the bottom of it the border to the frame of the apps main
# window is gone and it looks strange. happens only at maximum size."*
#
# Measured in the real window it began well before the maximum: at 20 lines in
# a 900 px window the panel's bottom was already 75 px BELOW the window. There
# is no scroll area under a tab, so the clipped part was simply gone, and the
# margin under the panel went with it.

def _column(qapp, *, height, above=300, below=30):
    """A log near the bottom of a fixed-height column, like a tab's left side.

    The column is a CHILD of a fixed-size host, not a window of its own. A
    top-level widget grows itself to satisfy its layout's minimum, which is
    exactly what the app's window cannot do — it is the size the user made it,
    on a screen of a certain height — so a top-level column here would quietly
    absorb the bug instead of showing it.
    """
    from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

    host = QWidget()
    host.setFixedSize(400, height)
    pane = QWidget(host)
    pane.setGeometry(0, 0, 400, height)
    lay = QVBoxLayout(pane)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    top = QLabel()
    top.setMinimumHeight(above)
    lay.addWidget(top)
    log = QPlainTextEdit()
    lay.addWidget(log)
    foot = QLabel()
    foot.setMinimumHeight(below)
    lay.addWidget(foot)
    host.show()
    lay.activate()
    fit_log_height(log)
    pane._host, pane._foot = host, foot
    return pane, log


def _fits(pane, log):
    """True when the panel AND the status line under it are still on screen.

    Checking only the panel is not enough: what the user sees go missing is the
    space below it — Basti's *"the border to the frame of the app's main window
    is gone"*.
    """
    pane.layout().activate()
    foot = pane._foot
    log_inside = log.mapTo(pane, log.rect().bottomLeft()).y() <= pane.height()
    # An over-tall panel does not push the status line out of the column — Qt
    # crushes it to nothing and leaves it pinned at the bottom. So its position
    # proves nothing and its height proves everything.
    foot_alive = foot.height() >= foot.minimumHeight()
    return log_inside and foot_alive


def test_a_log_cannot_be_dragged_past_the_bottom_of_its_column(bound):
    pane, log = _column(qapp=None, height=520)
    set_log_visible_lines(LOG_MAX_LINES)
    pane.layout().activate()
    assert _fits(pane, log), (
        f"panel bottom {log.mapTo(pane, log.rect().bottomLeft()).y()} "
        f"is past the column's {pane.height()} px — this is the clipping Basti saw"
    )
    pane._host.deleteLater()


def test_a_taller_window_allows_more_lines_than_a_short_one(bound):
    """Measured one at a time: every live panel caps the shared size, so two
    columns on screen together would both settle on the shorter one's ceiling
    (which is the point of the cap, and is its own test below)."""
    from ui.widgets import _max_lines_for

    short, short_log = _column(qapp=None, height=460)
    ceiling_short = _max_lines_for(short_log)
    short.hide()
    short._host.deleteLater()
    tall, tall_log = _column(qapp=None, height=900)
    ceiling_tall = _max_lines_for(tall_log)
    assert ceiling_tall > ceiling_short, (
        "the ceiling has to follow the window's height, or making the window "
        "bigger would not give the user the size they asked for"
    )
    tall._host.deleteLater()


def test_the_tab_with_the_least_room_sets_the_size_for_all_of_them(bound):
    """Tabs have different amounts of room — Measure gives its preview more and
    its log less. The size is shared, so it has to fit the tightest one, or it
    would clip the moment the user changed tab."""
    roomy, roomy_log = _column(qapp=None, height=900)
    tight, tight_log = _column(qapp=None, height=460)
    used = set_log_visible_lines(LOG_MAX_LINES)
    roomy.layout().activate()
    tight.layout().activate()
    assert _fits(tight, tight_log) and _fits(roomy, roomy_log)
    assert used <= _max_lines_for_or_max(tight_log)
    roomy._host.deleteLater()
    tight._host.deleteLater()


def _max_lines_for_or_max(log):
    from ui.widgets import _max_lines_for

    return _max_lines_for(log)


def test_shrinking_then_growing_lands_back_on_the_same_size(bound):
    """The ceiling is a property of the layout, not of the current size.

    An earlier attempt measured how far the panel currently overflowed, which
    made growth one-way: once shrunk, the space was taken by the widgets above
    and every later request collapsed to the two-line floor.
    """
    pane, log = _column(qapp=None, height=700)
    big = set_log_visible_lines(LOG_MAX_LINES)
    set_log_visible_lines(LOG_MIN_LINES)
    pane.layout().activate()
    again = set_log_visible_lines(LOG_MAX_LINES)
    assert again == big
    pane._host.deleteLater()


def test_the_size_that_is_saved_is_the_size_that_was_shown(bound):
    """A size the column could not show is not a size the user chose.

    Storing the asked-for number would make the panel jump the next time the
    app opened on a taller screen.
    """
    pane, log = _column(qapp=None, height=520)
    used = set_log_visible_lines(LOG_MAX_LINES)
    assert used < LOG_MAX_LINES              # the column is too short for 40
    assert bound.get("log_visible_lines") == used
    pane._host.deleteLater()
