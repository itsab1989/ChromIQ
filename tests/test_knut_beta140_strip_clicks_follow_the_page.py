"""#130 beta.140 — the clickable strips belong to the page on screen.

Knut, on a chart with strips A-E on sheet 1 and F on sheet 2: he read D, the
reader jumped to the next unread (F, page 2), and he pressed PREV to come back.

    *"Now I am unable to click any of the strips to select them, except strip A.
    When I select strip A, then all the others suddenly allow for selecting
    them."*

``TiffPreview`` keeps stripe rects for ONE page, and they were set in exactly
one place — when the READER moves. Paging by hand left the previous page's rects
in place, so page 2's single rect sat over page 1's strip A, and clicking it
moved the reader, which recomputed everything.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QRect

from core.settings import DEFAULTS
from core.argyll_runner import ArgyllRunner
from ui.tabs.tab_measure import TabMeasure


class _Settings:
    def __init__(self):
        self.d = dict(DEFAULTS)

    def get(self, k, d=None):
        return self.d.get(k, d)

    def set(self, k, v):
        self.d[k] = v


@pytest.fixture
def tab(qapp):
    t = TabMeasure(ArgyllRunner(_Settings()), _Settings())
    # Knut's chart: five strips on page 1, one on page 2.
    t._page_stripe_rects = [
        [QRect(0, 100 * i, 500, 60) for i in range(5)],     # page 1: A-E
        [QRect(0, 100, 500, 60)],                           # page 2: F
    ]
    t._strips_per_page = [5, 1]
    t._stripe_arrow_mode = "base"
    return t


def test_paging_back_restores_every_strip(tab):
    # The reader jumped to F, so the preview holds page 2's single rect…
    tab._preview.set_stripe_rects(tab._page_stripe_rects[1])
    assert len(tab._preview._stripe_rects) == 1

    # …and the user presses PREV.
    tab._on_preview_page_changed(0)
    assert len(tab._preview._stripe_rects) == 5, (
        "only one strip is clickable on a five-strip page")


def test_paging_forward_narrows_to_that_page(tab):
    tab._on_preview_page_changed(0)
    tab._on_preview_page_changed(1)
    assert len(tab._preview._stripe_rects) == 1


def test_it_is_wired_to_the_preview(tab):
    """A handler nothing calls would leave the bug exactly where it was."""
    import inspect
    src = inspect.getsource(TabMeasure._build_ui) if hasattr(
        TabMeasure, "_build_ui") else inspect.getsource(TabMeasure)
    assert "page_changed.connect(self._on_preview_page_changed)" in src


def test_an_out_of_range_page_is_survivable(tab):
    """Never raise from a paging signal — the preview can outlive a chart."""
    tab._on_preview_page_changed(99)
    assert len(tab._preview._stripe_rects) == 1        # clamped to the last
    tab._on_preview_page_changed(-1)
    assert len(tab._preview._stripe_rects) == 5        # clamped to the first


def test_no_chart_is_a_no_op(tab):
    tab._page_stripe_rects = []
    tab._preview.set_stripe_rects([QRect(0, 0, 10, 10)])
    tab._on_preview_page_changed(0)
    assert len(tab._preview._stripe_rects) == 1        # left alone, no crash
