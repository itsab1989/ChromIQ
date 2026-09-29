"""A greyed scroll arrow LOOKS greyed, in all three appearances (challenge 2
of beta 42, #2; register B8-1002).

Knut's rule for the graph tab bar (#182 5814390886): with nothing hidden on a
side, that side's arrow is "greyed out". The bar disabled the button, and the
style then painted the disabled arrow in exactly the live colour, because none
of the app's three palettes writes Qt's Disabled colour group: `isEnabled()`
said False and the picture said nothing (photographed on screen, challenge 2,
crop-narrow-tabs-00/06).

So this is measured on the PAINTED PIXELS of each arrow button, in the
palette and the style sheet of each appearance, never on `isEnabled()`.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget  # noqa: E402

from ui.light_styles import LIGHT_STYLESHEET, make_light_palette  # noqa: E402
from ui.neutral_styles import (NEUTRAL_STYLESHEET,  # noqa: E402
                               make_neutral_palette)
from ui.peek_tab_bar import PeekTabBar  # noqa: E402
from ui.styles import APP_STYLESHEET, make_dark_palette  # noqa: E402

TITLES = ["Colour accuracy (ΔE00)", "Paper white (L*)",
          "Paper white difference (ΔE00)", "Darkest black (L*)",
          "Cube corners (ΔE00)", "Grey balance (ΔCh)",
          "Tone ramps 30 to 70 % (ΔL*)", "Repeatability (ΔE00)",
          "Evenness (ΔE00)"]

APPEARANCES = {
    "light": (make_light_palette, LIGHT_STYLESHEET),
    "dark": (make_dark_palette, APP_STYLESHEET),
    "neutral": (make_neutral_palette, NEUTRAL_STYLESHEET),
}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _ink(btn) -> float:
    """How far the most distant painted pixel of *btn* is from the ground
    colour of its picture (the most common one), averaged over R, G, B."""
    from collections import Counter
    img = btn.grab().toImage()
    px = [img.pixelColor(x, y).getRgb()[:3]
          for y in range(img.height()) for x in range(img.width())]
    ground = Counter(px).most_common(1)[0][0]
    return max(sum(abs(a - b) for a, b in zip(p, ground)) / 3.0 for p in px)


def _bar(qapp, look):
    make_palette, sheet = APPEARANCES[look]
    host = QWidget()
    # The appearance on the WIDGET, not the application: a test must never
    # re-polish every widget the suite holds (CLAUDE.md).
    host.setPalette(make_palette())
    host.setStyleSheet(sheet)
    tw = QTabWidget(host)
    tw.setTabBar(PeekTabBar(tw))
    for t in TITLES:
        tw.addTab(QWidget(), t)
    host.resize(700, 200)
    tw.resize(700, 200)
    host.show()
    qapp.processEvents()
    return host, tw.tabBar()


@pytest.mark.parametrize("look", sorted(APPEARANCES))
def test_the_greyed_arrow_is_painted_fainter_than_the_live_one(qapp, look):
    host, bar = _bar(qapp, look)
    try:
        st = bar.peek_state()
        assert st["arrows_shown"], "the bar must overflow for this test"
        # at the left end: left greyed, right live
        assert st["arrows"] == (False, True), st
        dead, live = _ink(bar._left_btn), _ink(bar._right_btn)
        assert live >= 60, (look, "a live arrow must be plain", live)
        assert dead <= 0.5 * live, (look, "the greyed arrow is painted like "
                                    "the live one", dead, live)
        assert dead >= 8, (look, "a greyed arrow is still drawn", dead)
        # and at the right end the other way round, on the same pixels
        for _ in range(len(TITLES)):
            bar.scroll_right()
        qapp.processEvents()
        assert bar.peek_state()["arrows"] == (True, False)
        dead_r, live_l = _ink(bar._right_btn), _ink(bar._left_btn)
        assert dead_r <= 0.5 * live_l, (look, dead_r, live_l)
        # between the ends both are live, and both look it
        bar.scroll_left()
        qapp.processEvents()
        if bar.peek_state()["arrows"] == (True, True):
            assert min(_ink(bar._left_btn), _ink(bar._right_btn)) >= 60
    finally:
        host.close()
        host.deleteLater()
