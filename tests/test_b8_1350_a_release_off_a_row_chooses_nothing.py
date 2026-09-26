"""B8-1350 and B8-1351: in the open "Select preset" list, a release chooses
only the row it is on.

Qt's popup does not ask where a release is. It chooses the list's CURRENT row
on any release its viewport receives inside the view's rectangle, and after a
press on a row the viewport keeps receiving the mouse wherever it goes.

* B8-1350 (beta 44 challenge round 7, 9 of 9 with a real Quartz pointer,
  regression from B8-1319): press on a row, drag right past the 8 px scroll
  bar onto the list's edge, hold while the list scrolls by itself, release:
  the row that became current while scrolling was chosen. Beta 43 kept the
  list open.
* B8-1351 (beta 43 and 44): a click on a group heading, which can never be
  current, chose the current preset again. The Built-in presets list does
  nothing on a heading.

On screen: ~/Desktop/ChromIQ-beta44-proof/k53/ (before/scroll, after/scroll-
matrix, after/follow-up). MUTATIONS: k53/mutations.txt.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, QSettings, Qt  # noqa: E402
from PyQt6.QtGui import QMouseEvent                                      # noqa: E402
from PyQt6.QtWidgets import QApplication                                 # noqa: E402

import core.curated_presets as cp                                        # noqa: E402
from ui.tabs import tab_chart as TC                                      # noqa: E402


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


def _send(qapp, widget, kind, pos: QPoint):
    types = {"press": QEvent.Type.MouseButtonPress,
             "release": QEvent.Type.MouseButtonRelease}
    buttons = (Qt.MouseButton.LeftButton if kind == "press"
               else Qt.MouseButton.NoButton)
    ev = QMouseEvent(types[kind], QPointF(pos),
                     QPointF(widget.mapToGlobal(pos)),
                     Qt.MouseButton.LeftButton, buttons,
                     Qt.KeyboardModifier.NoModifier)
    qapp.sendEvent(widget, ev)
    qapp.processEvents()


def _open(tab, qapp, start_row: int):
    cb = tab._preset_combo
    cb.blockSignals(True)
    cb.setCurrentIndex(start_row)
    cb.blockSignals(False)
    cb.view().setStyleSheet("QListView { border: 1px solid #888888; }")
    cb.showPopup()
    qapp.processEvents()
    view = cb.view()
    assert view.isVisible(), "the list did not open"
    return cb, view


def _visible(cb, view, row) -> bool:
    vp = view.viewport()
    return vp.rect().contains(view.visualRect(
        cb.model().index(row, 0)).center())


def _preset_rows(cb, view):
    return [r for r in range(cb.count())
            if not view.isRowHidden(r) and isinstance(cb.itemData(r), str)
            and not cb.itemData(r, cb.MORE_ROLE) and _visible(cb, view, r)]


def _heading_rows(cb, view):
    return [r for r in range(cb.count())
            if not view.isRowHidden(r) and cb.itemData(r, cb.GROUP_ROLE)
            and not isinstance(cb.itemData(r), str)
            and not cb.itemData(r, cb.MORE_ROLE) and cb.itemText(r).strip()
            and _visible(cb, view, r)]


def _spy_activated(cb):
    """The tab's own slot would open the name prompt (a real modal), so the
    spy alone listens."""
    got = []
    cb.activated.disconnect()
    cb.activated.connect(got.append)
    return got


def _off_row_points(view):
    """Where the pointer is after the drag, in the VIEWPORT's coordinates
    (the viewport holds the mouse after the press): on the scroll bar, on
    the list's right edge, below the rows' area."""
    vp = view.viewport()
    sb = view.verticalScrollBar()
    bar_x = vp.mapFrom(view, QPoint(view.width() - 1, 0)).x()
    return {
        "on-the-bar": QPoint(vp.width() + max(1, sb.width() // 2),
                             vp.height() // 2),
        "on-the-edge": QPoint(bar_x, vp.height() // 2),
        "below-the-rows": QPoint(vp.width() // 2, vp.height() + 1),
    }


@pytest.mark.parametrize("where", ["on-the-bar", "on-the-edge",
                                   "below-the-rows"])
def test_a_press_on_a_row_released_off_the_rows_chooses_nothing(
        tab, qapp, where):
    cb = tab._preset_combo
    start = next(r for r in range(8, cb.count())
                 if isinstance(cb.itemData(r), str)
                 and not cb.itemData(r, cb.MORE_ROLE))
    cb, view = _open(tab, qapp, start)
    rows = _preset_rows(cb, view)
    pressed = rows[len(rows) // 2]
    vp = view.viewport()
    # the row the drag made current while the list scrolled
    view.setCurrentIndex(cb.model().index(rows[-1], 0))
    got = _spy_activated(cb)
    _send(qapp, vp, "press",
          view.visualRect(cb.model().index(pressed, 0)).center())
    view.setCurrentIndex(cb.model().index(rows[-1], 0))
    _send(qapp, vp, "release", _off_row_points(view)[where])
    assert view.isVisible(), f"a release {where} closed the list"
    assert not got, f"a release {where} chose row {got}"
    assert cb.currentIndex() == start


def test_the_list_still_gets_its_release_so_it_ends_the_drag(tab, qapp):
    """Kept from Qt's popup, the release must still reach the list, so it
    ends its press-and-drag. Measured on screen with a real pointer: without
    it the list closed by itself during the hover that followed (3 of 3);
    with it, it stays open and the next click chooses the row clicked."""
    cb = tab._preset_combo
    cb, view = _open(tab, qapp, 0)
    vp = view.viewport()
    seen = []

    class _Spy(QObject):
        def eventFilter(self, obj, ev):                   # noqa: N802
            if ev.type() == QEvent.Type.MouseButtonRelease:
                seen.append(ev.position().toPoint())
            return False

    spy = _Spy()
    rows = _preset_rows(cb, view)
    _send(qapp, vp, "press",
          view.visualRect(cb.model().index(rows[0], 0)).center())
    vp.installEventFilter(spy)       # runs before the combo's filter
    try:
        _send(qapp, vp, "release", _off_row_points(view)["on-the-bar"])
    finally:
        vp.removeEventFilter(spy)
    assert len(seen) == 2, seen
    assert not view.rect().contains(seen[1]), \
        "the list's own release must land outside the view"


def test_a_click_on_a_group_heading_does_nothing(tab, qapp):
    cb = tab._preset_combo
    start = next(r for r in range(8, cb.count())
                 if isinstance(cb.itemData(r), str)
                 and not cb.itemData(r, cb.MORE_ROLE))
    cb, view = _open(tab, qapp, start)
    view.scrollToTop()
    qapp.processEvents()
    heads = _heading_rows(cb, view)
    assert heads, "no heading on screen"
    got = _spy_activated(cb)
    p = view.visualRect(cb.model().index(heads[0], 0)).center()
    _send(qapp, view.viewport(), "press", p)
    _send(qapp, view.viewport(), "release", p)
    assert view.isVisible(), "a click on a heading closed the list"
    assert not got, f"a click on a heading chose row {got}"
    assert cb.currentIndex() == start


def test_control_a_click_on_a_preset_row_still_chooses_it(tab, qapp):
    cb = tab._preset_combo
    cb, view = _open(tab, qapp, 0)
    rows = [r for r in _preset_rows(cb, view) if r != 0]
    target = rows[0]
    got = _spy_activated(cb)
    p = view.visualRect(cb.model().index(target, 0)).center()
    view.setCurrentIndex(cb.model().index(target, 0))
    _send(qapp, view.viewport(), "press", p)
    _send(qapp, view.viewport(), "release", p)
    assert got == [target]
    assert not view.isVisible()
