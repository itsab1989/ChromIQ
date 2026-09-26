"""B8-1319 (Knut, #182 5845615756, a user on Windows): pressing the scroll bar
of the open preset list chose the first preset and closed the list; only the
wheel scrolled.

Measured on screen with a real pointer
(`scripts/drive_b8_1319_preset_list_scroll_bar.py`,
`~/Desktop/ChromIQ-beta44-proof/k50-create-chart/scrollbar/`):

* "Select preset": the bar is 8 px wide (the app's style sheet). The bar
  itself, its page area and the scroll strips above and below the rows
  worked; a press that missed it by a pixel landed on the list view's own
  frame (above it, right of it) and was passed up to Qt's popup frame,
  which closes the list on any press it receives. Qt's popup also reads a
  mouse move or release ON THE VIEW as if it were on the rows, so a release
  on the frame could choose the top visible row.
* The Built-in presets list: its thumb was painted and nothing more. A
  press on it, or on the track, chose the row underneath and closed the
  list (the "Give this project a name" window came up).

Now a press, release or move on the frame of the "Select preset" list is
kept (the list stays open, nothing is chosen), and the Built-in list's
thumb drags and its track pages, and neither ever chooses.

MUTATIONS (mutations.txt of the k50 proof): ``_is_frame_click`` answering
False, red in the first three tests; the Built-in list's strip check taken
out of ``mousePressEvent``, red in the last two.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt  # noqa: E402
from PyQt6.QtGui import QMouseEvent                              # noqa: E402
from PyQt6.QtWidgets import QApplication                         # noqa: E402

import core.curated_presets as cp                                # noqa: E402
from ui.builtin_preset_popup import BuiltinPresetPopup           # noqa: E402
from ui.tabs import tab_chart as TC                              # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set(cp.PAPER_FILTER_KEY, False)          # a long list, so it scrolls
    s.set("chart_instrument", "i1")
    t = TC.TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    t.show()
    qapp.processEvents()
    yield t
    t._preset_combo.hidePopup()
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _mouse(qapp, widget, kind, pos: QPoint):
    types = {"press": QEvent.Type.MouseButtonPress,
             "release": QEvent.Type.MouseButtonRelease,
             "move": QEvent.Type.MouseMove}
    buttons = (Qt.MouseButton.LeftButton if kind == "press"
               else Qt.MouseButton.NoButton)
    ev = QMouseEvent(types[kind], QPointF(pos),
                     QPointF(widget.mapToGlobal(pos)),
                     Qt.MouseButton.LeftButton if kind != "move"
                     else Qt.MouseButton.NoButton,
                     buttons, Qt.KeyboardModifier.NoModifier)
    qapp.sendEvent(widget, ev)
    qapp.processEvents()


def _open(tab, qapp, start_row: int):
    cb = tab._preset_combo
    cb.blockSignals(True)
    cb.setCurrentIndex(start_row)
    cb.blockSignals(False)
    # THE APP'S FRAME, ON THE LIST ONLY. The running app's style sheet gives
    # the popup list a 1 px border (measured on screen: view 771 x 296,
    # viewport 761 x 294 at 1,1); a test may not style the application
    # (CLAUDE.md), so the list is given the same border itself.
    cb.view().setStyleSheet("QListView { border: 1px solid #888888; }")
    cb.showPopup()
    qapp.processEvents()
    view = cb.view()
    assert view.isVisible(), "the list did not open"
    assert view.verticalScrollBar().maximum() > 0, "the list does not scroll"
    return cb, view


def _a_preset_row(cb, below: int = 8) -> int:
    return next(r for r in range(below, cb.count())
                if not cb.view().isRowHidden(r) and isinstance(cb.itemData(r), str)
                and not cb.itemData(r, cb.MORE_ROLE))


def _frame_points(view):
    """Points on the list view's own frame: above the scroll bar and right
    of it, i.e. inside the view and outside its viewport and its bar."""
    vp = view.viewport().geometry()
    sb = view.verticalScrollBar()
    bar = sb.parentWidget().geometry() if sb.parentWidget() is not view \
        else sb.geometry()
    pts = {"above-bar": QPoint(bar.center().x(), max(0, bar.top() - 1)),
           "right-of-bar": QPoint(view.width() - 1, bar.center().y())}
    for name, p in pts.items():
        assert view.rect().contains(p), name
        assert not vp.contains(p) and not bar.contains(p), (name, p, vp, bar)
    return pts


@pytest.mark.parametrize("where", ["above-bar", "right-of-bar"])
def test_a_press_on_the_lists_frame_keeps_it_open_and_chooses_nothing(
        tab, qapp, where):
    cb = tab._preset_combo
    row = _a_preset_row(cb)
    cb, view = _open(tab, qapp, row)
    p = _frame_points(view)[where]
    _mouse(qapp, view, "move", p)
    _mouse(qapp, view, "press", p)
    _mouse(qapp, view, "release", p)
    assert view.isVisible(), f"a press on the list's frame ({where}) closed it"
    assert cb.currentIndex() == row, "a press on the list's frame chose a row"


def test_a_move_on_the_frame_does_not_make_a_row_current(tab, qapp):
    """Qt's popup reads a move on the VIEW as if on the rows: a move on the
    frame above the bar made the top visible row current, and the release
    after it chose that row."""
    cb = tab._preset_combo
    row = _a_preset_row(cb)
    cb, view = _open(tab, qapp, row)
    before = view.currentIndex().row()
    p = _frame_points(view)["above-bar"]
    _mouse(qapp, view, "move", p)
    assert view.currentIndex().row() == before


def test_a_press_outside_the_list_still_closes_it(tab, qapp):
    """The fix keeps the frame, not the whole screen: a click away from the
    list closes it, as before."""
    cb = tab._preset_combo
    cb, view = _open(tab, qapp, 0)
    container = view.window()
    outside = QPoint(container.width() + 40, container.height() + 40)
    _mouse(qapp, container, "press", outside)
    assert not view.isVisible()


# ---- the Built-in presets list -------------------------------------------

@pytest.fixture()
def bubble(tab, qapp):
    tab._open_builtin_preset_overlay()
    pop = tab._builtin_preset_popup
    qapp.processEvents()
    assert pop._max_scroll > 0, "the Built-in list does not scroll"
    chosen = []
    # the tab's own slot would open the name prompt: the spy alone listens
    pop.selected.disconnect()
    pop.selected.connect(chosen.append)
    yield pop, chosen
    pop.close()
    qapp.processEvents()


def test_the_built_in_lists_thumb_drags_and_chooses_nothing(bubble, qapp):
    pop, chosen = bubble
    th = pop._thumb_rect()
    assert not th.isEmpty()
    start = th.center()
    _mouse(qapp, pop, "press", start)
    for k in range(1, 8):
        ev = QMouseEvent(QEvent.Type.MouseMove,
                         QPointF(start.x(), start.y() + 15 * k),
                         QPointF(pop.mapToGlobal(QPoint(start.x(),
                                                        start.y() + 15 * k))),
                         Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
        qapp.sendEvent(pop, ev)
    qapp.processEvents()
    _mouse(qapp, pop, "release", QPoint(start.x(), start.y() + 105))
    assert pop.isVisible(), "dragging the thumb closed the list"
    assert not chosen, f"dragging the thumb chose {chosen}"
    assert pop._scroll_y > 0, "dragging the thumb did not scroll"


@pytest.mark.parametrize("dx", [0, -3, -6])
def test_a_press_on_the_built_in_lists_track_pages_and_chooses_nothing(
        bubble, qapp, dx):
    """On the track below the thumb, and a few pixels left of it, where a
    press used to land on the row underneath."""
    pop, chosen = bubble
    th = pop._thumb_rect()
    p = QPoint(th.center().x() + dx, th.bottom() + 40)
    _mouse(qapp, pop, "press", p)
    _mouse(qapp, pop, "release", p)
    assert pop.isVisible()
    assert not chosen, f"a press on the scroll bar chose {chosen}"
    assert pop._scroll_y > 0


def test_a_row_is_still_chosen_by_a_click_on_it(bubble, qapp):
    """The strip is the bar's, not the row's middle: a click on a preset's
    label still chooses it."""
    pop, chosen = bubble
    row = next(r for r in pop._rows if r.kind == "item")
    rect = pop._row_rect(row)
    _mouse(qapp, pop, "press", QPoint(rect.left() + 40, rect.center().y()))
    assert chosen == [row.key]
