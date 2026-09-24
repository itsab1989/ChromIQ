"""K32, Knut on beta 41 (#182 5814390886): a scrolling tab bar that shows it
has more tabs than it can hold (`ui/peek_tab_bar.py`).

*"If there are no tabs hidden on the left-most tab position, then the
left-most tab obviously will be aligned with the left side of the scrolling
area, but at this time, the left arrow should also be greyed out ... When
there are tabs hidden in both directions, both arrows are not greyed out and
clickable, AND, the tabs visible within the scrolling area are positioned
such that part of the next left tab ... is showing (maybe between 1/4 part and
1/6 part of the tab width is showing), and at the same time part of the next
right tab"*.

Measured here on the bar's own plan (what it paints, and what the mouse
hits), at several widths, in English and German; photographed on screen by
`scripts/drive_k32_report_rows_and_switch.py` (scene "tabs").
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QPoint, QPointF, Qt                 # noqa: E402
from PyQt6.QtGui import QMouseEvent                          # noqa: E402
from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget  # noqa: E402

from ui.peek_tab_bar import PEEK_MAX, PEEK_MIN, PeekTabBar  # noqa: E402

TITLES = ["Colour accuracy (ΔE00)", "Paper white (L*)",
          "Paper white difference (ΔE00)", "Darkest black (L*)",
          "Cube corners (ΔE00)", "Grey balance (ΔCh)",
          "Tone ramps 30 to 70 % (ΔL*)", "Control strip (ΔE00)",
          "Repeatability (ΔE00)", "Evenness (ΔE00)"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tabs(qapp, width, hidden=()):
    tw = QTabWidget()
    tw.setTabBar(PeekTabBar(tw))
    for t in TITLES:
        tw.addTab(QWidget(), t)
    for i in hidden:
        tw.setTabVisible(i, False)
    tw.resize(width, 200)
    tw.show()
    qapp.processEvents()
    return tw, tw.tabBar()


def _assert_rules(bar, where=""):
    """Every rule, on the bar's own state."""
    st = bar.peek_state()
    vis, shown = st["visible"], st["shown"]
    first, last = st["first"], st["last"]
    left_hidden, right_hidden = first > 0, last < len(vis) - 1
    # the arrows: live exactly while something is hidden on their side
    assert st["arrows"] == (left_hidden, right_hidden), (where, st)
    # every tab between first and last is shown whole
    for k in range(first, last + 1):
        assert shown[vis[k]] == pytest.approx(1.0), (where, k, st)
    # the neighbour on a hidden side peeks, between 1/6 and 1/4 of it
    if left_hidden:
        f = shown[vis[first - 1]]
        assert PEEK_MIN - 0.02 <= f <= PEEK_MAX + 0.02, (where, "left", f)
        for k in range(first - 1):
            assert shown[vis[k]] == 0.0, (where, k)
    else:
        # nothing hidden on the left: the first tab at the left edge
        assert st["rects"][vis[0]][0] == 0 and st["clip"][0] == 0, (where, st)
    if right_hidden:
        f = shown[vis[last + 1]]
        assert PEEK_MIN - 0.02 <= f <= PEEK_MAX + 0.02, (where, "right", f)
        for k in range(last + 2, len(vis)):
            assert shown[vis[k]] == 0.0, (where, k)
    elif st["arrows_shown"]:
        # nothing hidden on the right: the last tab against the arrows
        assert st["rects"][vis[-1]][1] == st["area"] - 1, (where, st)
    return st


@pytest.mark.parametrize("width", [420, 560, 760, 980])
def test_both_ends_and_the_middle_follow_knuts_rules(qapp, width):
    """Scrolled right one arrow press at a time to the end and back: at the
    left end the left arrow is grey and the first tab is at the edge; in the
    middle both arrows are live and both neighbours peek; at the right end
    the right arrow is grey and the last tab is against the arrows.

    MUTATIONS, each proved to land: `PEEK = 0` (no peek: red in the middle);
    the left arrow always enabled (red at the left end); the right end
    clipped like the middle, leaving a gap before the arrows (red at the
    right end)."""
    tw, bar = _tabs(qapp, width)
    try:
        st = _assert_rules(bar, "start")
        assert st["arrows"] == (False, True), st
        seen_middle = False
        for step in range(20):
            if not bar.peek_state()["arrows"][1]:
                break
            bar._right_btn.click()
            qapp.processEvents()
            st = _assert_rules(bar, f"right {step}")
            seen_middle |= st["arrows"] == (True, True)
        assert bar.peek_state()["arrows"] == (True, False), "never reached the end"
        if width < 900:
            assert seen_middle, "no state with tabs hidden on both sides"
        for step in range(20):
            if not bar.peek_state()["arrows"][0]:
                break
            bar._left_btn.click()
            qapp.processEvents()
            _assert_rules(bar, f"left {step}")
        assert bar.peek_state()["arrows"] == (False, True)
    finally:
        tw.deleteLater()


def test_a_partly_shown_tab_is_selected_and_comes_whole(qapp):
    """Clicking the peeking tab on the right selects it, and the bar moves by
    the same rules so it is shown whole.

    MUTATION, proved to land: select the clicked tab with the bar's signals
    blocked and without the click's own `ensure_shown`: the tab is selected
    and stays cut."""
    tw, bar = _tabs(qapp, 560)
    try:
        st = bar.peek_state()
        peeking = st["visible"][st["last"] + 1]
        l, r = st["rects"][peeking]
        x = (l + st["clip"][1]) // 2          # inside the drawn sliver
        ev = QMouseEvent(QMouseEvent.Type.MouseButtonPress,
                         QPointF(x, bar.height() / 2),
                         QPointF(bar.mapToGlobal(QPoint(x, 5))),
                         Qt.MouseButton.LeftButton,
                         Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(bar, ev)
        qapp.processEvents()
        assert tw.currentIndex() == peeking
        st = _assert_rules(bar, "after click")
        assert st["shown"][peeking] == pytest.approx(1.0), st
    finally:
        tw.deleteLater()


def test_hidden_tabs_are_left_out_and_all_fit_means_no_arrows(qapp):
    """A tab the report hides takes no place; when everything fits the bar is
    an ordinary one: no arrows, first tab at the edge."""
    tw, bar = _tabs(qapp, 1400, hidden=range(5, 10))
    try:
        st = bar.peek_state()
        assert not st["arrows_shown"]
        assert all(v == pytest.approx(1.0) for v in st["shown"].values())
        assert set(st["visible"]) == set(range(5))
    finally:
        tw.deleteLater()


def test_german_titles_follow_the_same_rules(qapp):
    from core import i18n
    before = i18n.current_language()
    i18n.set_language("de")
    try:
        global TITLES
        saved = TITLES
        TITLES = [i18n.tr(t) for t in saved]
        try:
            for width in (480, 700):
                tw, bar = _tabs(qapp, width)
                try:
                    _assert_rules(bar, f"de {width}")
                    bar._right_btn.click()
                    qapp.processEvents()
                    _assert_rules(bar, f"de {width} right")
                finally:
                    tw.deleteLater()
        finally:
            TITLES = saved
    finally:
        i18n.set_language(before or "en")
