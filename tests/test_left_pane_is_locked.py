"""Every splitter tab locks its left pane the same way, and no window width
the app allows can make the two panes overlap.

Create Chart lost the lock in 3.13.0-beta.126: `left.setFixedWidth(580)` pins
min == max, and a later `left.setMinimumWidth(400)` in the same `_build_ui`
lowered the minimum back to 400, leaving a 180 px drag range on that tab only.

Both halves matter. Locking the left pane alone re-opens the bug beta.126 was
aiming at: Create Chart's right pane wants 774 px, so 580 + 774 does not fit a
900 px window and QSplitter overlaps the panes instead of shrinking one.

Neither assertion names 580 or 200, so changing either width does not need this
file edited.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PyQt6.QtCore import QSettings                    # noqa: E402
from PyQt6.QtWidgets import QApplication, QSplitter   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    w = MainWindow(s)
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def _splitter_tabs(win, qapp):
    """Every tab that has a splitter, SHOWN — a tab that has never been the
    current one has no geometry, so its children all sit at x=0."""
    for i in range(win._tabs.count()):
        tab = win._tabs.widget(i)
        sp = tab.findChild(QSplitter)
        if sp is None:
            continue
        win._tabs.setCurrentIndex(i)
        for _ in range(6):
            qapp.processEvents()
        yield win._tabs.tabText(i), sp


def test_every_tab_locks_its_left_pane_the_same_way(win, qapp):
    """min == max on the left widget is the lock. One tab must not differ."""
    loose = []
    for name, sp in _splitter_tabs(win, qapp):
        left = sp.widget(0)
        if left.minimumWidth() != left.maximumWidth():
            loose.append(
                f"{name}: min={left.minimumWidth()} max={left.maximumWidth()} "
                f"→ {left.maximumWidth() - left.minimumWidth()} px of drag")
    assert not loose, (
        "the left pane must be pinned (minimumWidth == maximumWidth) on every "
        "splitter tab; these are draggable: " + "; ".join(loose))


def test_the_lock_actually_holds_against_a_drag(win, qapp):
    """The property above, proved through the splitter rather than asserted."""
    for name, sp in _splitter_tabs(win, qapp):
        left = sp.widget(0)
        was = left.width()
        sp.setSizes([100, sp.width() - 100])
        qapp.processEvents()
        assert left.width() == was, (
            f"{name}: the left pane moved {was} → {left.width()} px")


def test_the_panes_never_overlap_at_the_smallest_allowed_window(win, qapp):
    """A pinned left pane plus a fat right pane makes QSplitter overlap them —
    the divider is then drawn across the left pane's own fields."""
    win.resize(win.minimumWidth(), win.minimumHeight())
    for _ in range(12):
        qapp.processEvents()
    bad = []
    for name, sp in _splitter_tabs(win, qapp):
        left, right = sp.widget(0), sp.widget(1)
        over = left.x() + left.width() - right.x()
        if over > 0:
            bad.append(f"{name}: {over} px")
    assert not bad, (
        f"at {win.width()}x{win.height()} the panes overlap: " + "; ".join(bad))
