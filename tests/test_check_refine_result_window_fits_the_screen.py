"""Check & Refine's result window fits the screen it opens on (Basti, 2026-10-04).

With ~25 strips listed the "Profile Quality Assessment" window grew to the full
height of its text, far taller than a 13" MacBook (1470x956 points) or a
1366x768 Windows laptop. Its minimum height was the text's height, so it could
not be shrunk and its buttons fell off the bottom of the screen.

Now the long parts scroll: the window is never taller than the usable area of
its screen (QScreen.availableGeometry, which leaves out the menu bar, a
visible Dock or the taskbar) minus a margin, the headline and the button row
stay inside it, and on a large screen nothing scrolls.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tests.test_check_refine_result_window_shows_every_line as _every  # noqa: E402
from tests.test_check_refine_result_window_shows_every_line import (  # noqa: E402
    CASES, _window)


def _knut_1944():
    """The shape of Basti's screenshot: Knut's 1944-patch chart at ΔE00 1.0,
    22 strips listed first and 50 more (the run1 window of 2026-10-04)."""
    from workflow.profcheck_runner import ProfcheckResult
    from workflow.refine_plan import OUTLIER, OVER, RefinePlan, StripAdvice
    names = [f"{a}{b}".strip() for a in ("", "A", "B") for b in
             "ABCDEFGHIJKLMNOPQRSTUVWXYZ"][:72]
    first = [StripAdvice(n, OUTLIER, f"{n}27", 6.5 - i * 0.1, 9)
             for i, n in enumerate(names[:22])]
    rest = [StripAdvice(n, OVER, f"{n}3", 3.7 - i * 0.04, 8)
            for i, n in enumerate(names[22:])]
    return (ProfcheckResult(avg_de=0.91, peak_de=6.53, raw_log=""),
            RefinePlan(1.0, 1944, 615, 3.0, False, "\u0394E00",
                       first=first, rest=rest))


_every.CASES["knut-1944-limit-1.0"] = _knut_1944


def _room(monkeypatch, w, h):
    from PyQt6.QtCore import QRect
    import ui.tabs.tab_check_refine as cr
    monkeypatch.setattr(cr, "_screen_room", lambda _win: QRect(0, 25, w, h))
    return cr


def _settle():
    from PyQt6.QtWidgets import QApplication
    for _ in range(4):
        QApplication.processEvents()


@pytest.mark.parametrize("w, h", [(1470, 956 - 25), (1366, 768 - 40), (1024, 600)])
@pytest.mark.parametrize("case", ["knut-1944-limit-1.0", "run2-0.5-start-over",
                                  "run3-2.0"])
def test_a_long_result_fits_a_small_screen(qapp, tmp_path, monkeypatch, case,
                                           w, h):
    from PyQt6.QtCore import QRect
    from PyQt6.QtWidgets import QLabel, QPushButton, QScrollArea
    cr = _room(monkeypatch, w, h)
    _tab, dlg = _window(qapp, tmp_path, monkeypatch, case)
    try:
        dlg.show()
        _settle()
        cap = h - cr.SCREEN_MARGIN
        assert dlg.minimumHeight() <= cap, (dlg.minimumHeight(), cap)
        assert dlg.height() <= cap, (dlg.height(), cap)
        inside = QRect(0, 0, dlg.width(), dlg.height())
        buttons = [b for b in dlg.findChildren(QPushButton) if b.isVisible()]
        assert buttons
        for b in buttons:
            r = QRect(b.mapTo(dlg, b.rect().topLeft()), b.size())
            assert inside.contains(r), (b.text(), r.getRect(), dlg.size())
        # The headline is outside the scroll area, so always on screen.
        scroll = dlg.findChild(QScrollArea, "cr_result_scroll")
        head = next(lb for lb in dlg.findChildren(QLabel)
                    if lb.text().startswith("Profile Quality"))
        assert not scroll.isAncestorOf(head)
        assert inside.contains(QRect(head.mapTo(dlg, head.rect().topLeft()),
                                     head.size()))
        # The long lists scroll (Knut's 1944-patch result is far taller than
        # any of these screens); a shorter one simply fits.
        body = scroll.widget()
        if case == "knut-1944-limit-1.0":
            assert body.minimumHeight() > scroll.viewport().height()
        if body.minimumHeight() > scroll.viewport().height():
            assert scroll.verticalScrollBar().maximum() > 0
        assert scroll.height() >= cr.MIN_SCROLL_HEIGHT
        # Scrolling never squeezes a wrapped line away (the old guarantee).
        for lb in body.findChildren(QLabel):
            if lb.isVisible() and lb.wordWrap() and lb.text().strip():
                assert lb.height() >= lb.heightForWidth(lb.width()), lb.text()[:50]
    finally:
        dlg.close()
        dlg.deleteLater()


@pytest.mark.parametrize("case", sorted(CASES))
def test_a_large_screen_shows_everything_without_a_scrollbar(
        qapp, tmp_path, monkeypatch, case):
    from PyQt6.QtWidgets import QScrollArea
    _room(monkeypatch, 4000, 4000)
    _tab, dlg = _window(qapp, tmp_path, monkeypatch, case)
    try:
        dlg.show()
        _settle()
        scroll = dlg.findChild(QScrollArea, "cr_result_scroll")
        assert scroll.verticalScrollBar().maximum() == 0
    finally:
        dlg.close()
        dlg.deleteLater()


def test_the_room_is_the_available_geometry_never_the_whole_screen():
    import inspect
    import ui.tabs.tab_check_refine as cr
    src = inspect.getsource(cr._screen_room)
    assert "availableGeometry()" in src
    assert ".geometry()" not in src


def test_the_window_is_still_centred_over_its_parent(qapp, tmp_path,
                                                      monkeypatch):
    """Beta-9 review, measured on screen: the filter sees the Show event
    BEFORE QDialog::showEvent centres the dialog over its parent, and moving
    the not yet placed window there set WA_Moved, so QDialog never centred it
    and it opened in the top-left corner of the screen (frame at 0,34 under a
    main window at 0,34, where a208f069 put it at 251,91). Keeping it on
    screen waits until QDialog has placed it."""
    from PyQt6.QtCore import Qt
    cr = _room(monkeypatch, 1470, 931)
    _tab, dlg = _window(qapp, tmp_path, monkeypatch, "run3-2.0")
    try:
        dlg.show()
        # Straight after show(): QDialog has centred it (and cleared the
        # flag), nothing moved it by hand.
        assert not dlg.testAttribute(Qt.WidgetAttribute.WA_Moved)
        _settle()
        # And the deferred check still keeps it inside the usable area.
        room = cr._screen_room(dlg)
        assert dlg.frameGeometry().top() >= room.top()
        assert dlg.frameGeometry().left() >= room.left()
    finally:
        dlg.close()
        dlg.deleteLater()


def test_keeping_it_on_screen_never_moves_it_inside_the_show_event():
    import inspect
    import ui.tabs.tab_check_refine as cr
    src = inspect.getsource(cr._FitsItsText._fit)
    assert "QTimer.singleShot(0, self._keep_on_screen)" in src
    assert "self._keep_on_screen()" not in src
