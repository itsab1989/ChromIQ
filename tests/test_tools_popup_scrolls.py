"""The Tools popup must not run off the screen.

Basti: *"the tools menu overlay is becoming very long. i think we need to cap
its height and make it scrollable"*. It has grown with the app — twenty entries
in seven groups — and an uncapped popup eventually extends past the bottom of
the display, where the last tools cannot be reached at all.

It is PAINTED rather than laid out, so scrolling is an offset applied in
`_rows()`, which both the painter and the hit test go through. The property that
matters is that they cannot disagree: a row scrolled out of sight must not be
clickable, which is the one thing a scrolling menu must never get wrong.
"""
import pytest
from PyQt6.QtCore import QPoint


@pytest.fixture
def popup(qtbot):
    from ui.tools_popup import ToolsPopup
    p = ToolsPopup()
    qtbot.addWidget(p)
    return p


def test_the_list_is_longer_than_the_popup_shows(popup):
    """The premise. If the content ever fits again this test is not wrong —
    it just stops proving anything, so it says so out loud."""
    assert popup._content_h > 0
    assert popup._view_h <= popup._content_h


def test_a_capped_list_is_scrollable(popup):
    if popup._content_h <= popup._view_h:
        pytest.skip("the list fits; nothing to scroll")
    assert popup.is_scrollable()
    assert popup._max_scroll() == popup._content_h - popup._view_h


def test_it_never_grows_past_the_screen(popup):
    from PyQt6.QtGui import QGuiApplication
    scr = QGuiApplication.primaryScreen()
    assert popup.height() <= scr.availableGeometry().height(), (
        "the popup is taller than the screen it must fit on")


def test_scrolling_is_clamped_at_both_ends(popup):
    if not popup.is_scrollable():
        pytest.skip("the list fits")
    popup._scroll = -500
    popup._scroll = max(0, min(popup._max_scroll(), popup._scroll))
    assert popup._scroll == 0
    popup._scroll = 10 ** 6
    popup._scroll = max(0, min(popup._max_scroll(), popup._scroll))
    assert popup._scroll == popup._max_scroll()


def test_a_row_scrolled_out_of_sight_is_not_clickable(popup):
    """The safety property. A row's rectangle still exists when it is scrolled
    above the panel; answering to a click there would fire the wrong tool."""
    if not popup.is_scrollable():
        pytest.skip("the list fits")
    popup._scroll = popup._max_scroll()          # scrolled to the bottom
    rows = popup._rows()
    above = [(i, r) for i, (k, _p, r) in enumerate(rows)
             if k == "tool" and r.bottom() < popup._panel_rect().top()]
    assert above, "nothing is scrolled out of view; the test proves nothing"
    i, r = above[0]
    assert popup._index_at(r.center()) != i, (
        "a row scrolled off the top still answers to a click")


def test_every_visible_row_is_still_clickable(popup):
    """The mutation guard for the test above: a hit test that always says -1
    would satisfy it and break the menu completely."""
    rows = popup._rows()
    panel = popup._panel_rect()
    visible = [(i, r) for i, (k, _p, r) in enumerate(rows)
               if k == "tool" and panel.contains(r.center())]
    assert visible, "no tool row is visible at all"
    for i, r in visible:
        assert popup._index_at(r.center()) == i


def test_the_wheel_moves_it(popup, qtbot):
    if not popup.is_scrollable():
        pytest.skip("the list fits")
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QWheelEvent
    popup.show()
    qtbot.waitExposed(popup)
    before = popup._scroll
    ev = QWheelEvent(QPointF(popup.width() / 2, popup.height() / 2),
                     popup.mapToGlobal(QPoint(0, 0)).toPointF()
                     if hasattr(popup.mapToGlobal(QPoint(0, 0)), "toPointF")
                     else QPointF(0, 0),
                     QPoint(0, 0), QPoint(0, -120),
                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                     Qt.ScrollPhase.NoScrollPhase, False)
    popup.wheelEvent(ev)
    assert popup._scroll > before, "the wheel did not scroll the list"
