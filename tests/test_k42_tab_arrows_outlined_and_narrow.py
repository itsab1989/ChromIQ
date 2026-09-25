"""The graph tab bar's scroll arrows have an outline and are narrow (#182 K42,
Knut 5832746557; register B8-1141, B8-1142).

Knut, testing beta 42: *"the arrow-buttons to the right of the tabs do not
have an outline like all other buttons controls. Also, the arrow buttons are
now much wider than they were. Reduce the width of the arrow buttons to what
they were before, approx. half the width they are in beta 42."*

Measured on the PAINTED PIXELS of each arrow, in the palette and style sheet of
each appearance: an outline is an edge that differs from the button's inside,
live and greyed. The width is Qt's own scroll-button width (what the arrows
were before `PeekTabBar` painted its own), and at most half of beta 42's,
which was the bar's height less 4 px.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QPushButton, QStyle  # noqa: E402

from tests.test_c2_a_greyed_tab_arrow_looks_greyed import (  # noqa: E402
    APPEARANCES, TITLES, _bar, qapp)  # noqa: F401  (the fixture)


def _edge_contrast(btn) -> float:
    """How far the button's outer ring differs from its inside, at the middle
    of each side, averaged over R, G, B; the smallest of the four sides."""
    img = btn.grab().toImage()
    w, h = img.width(), img.height()
    inside = img.pixelColor(w // 2, 3).getRgb()[:3]
    # the inside next to the triangle: a row above it, clear of the ink
    sides = [img.pixelColor(0, h // 2), img.pixelColor(w - 1, h // 2),
             img.pixelColor(w // 2, 0), img.pixelColor(w // 2, h - 1)]
    return min(sum(abs(a - b) for a, b in zip(c.getRgb()[:3], inside)) / 3.0
               for c in sides)


@pytest.mark.parametrize("look", sorted(APPEARANCES))
def test_both_arrows_have_an_outline_live_and_greyed(qapp, look):
    host, bar = _bar(qapp, look)
    try:
        st = bar.peek_state()
        assert st["arrows"] == (False, True), st
        assert not bar._left_btn.autoRaise()
        for btn, state in ((bar._left_btn, "greyed"),
                           (bar._right_btn, "live")):
            c = _edge_contrast(btn)
            assert c >= 10, (look, state, "no outline on the arrow", c)
    finally:
        host.close()
        host.deleteLater()


def _left_edge(widget):
    img = widget.grab().toImage()
    return img.pixelColor(0, img.height() // 2).getRgb()[:3]


@pytest.mark.parametrize("look", sorted(APPEARANCES))
def test_the_outline_is_the_one_a_push_button_has(qapp, look):
    """"like all other buttons": the arrow's edge is the colour of an
    ordinary button's edge in the same appearance, live beside an enabled
    button and greyed beside a disabled one."""
    host, bar = _bar(qapp, look)
    try:
        ok, off = QPushButton("OK", host), QPushButton("OK", host)
        off.setEnabled(False)
        for b in (ok, off):
            b.move(10, 120)
            b.show()
        qapp.processEvents()
        for arrow, button in ((bar._right_btn, ok), (bar._left_btn, off)):
            a, b = _left_edge(arrow), _left_edge(button)
            assert max(abs(x - y) for x, y in zip(a, b)) <= 12, (
                look, arrow.isEnabled(), "arrow edge", a, "button edge", b)
    finally:
        host.close()
        host.deleteLater()


@pytest.mark.parametrize("look", sorted(APPEARANCES))
def test_the_arrows_are_qts_own_width_about_half_of_beta_42(qapp, look):
    host, bar = _bar(qapp, look)
    try:
        beta42 = max(16, bar.height() - 4)
        qt_own = bar.style().pixelMetric(
            QStyle.PixelMetric.PM_TabBarScrollButtonWidth, None, bar)
        for btn in (bar._left_btn, bar._right_btn):
            w = btn.width()
            assert w == max(14, qt_own), (look, w, qt_own)
            assert w <= 0.62 * beta42, (look, "not about half", w, beta42)
        # the two arrows sit side by side at the right, not on top of each
        # other, and the row still ends before them (B8-1008)
        lr, rr = bar._left_btn.geometry(), bar._right_btn.geometry()
        assert rr.right() == bar.width() - 1
        assert lr.right() < rr.left()
        assert bar.peek_state()["area"] <= lr.left()
    finally:
        host.close()
        host.deleteLater()
