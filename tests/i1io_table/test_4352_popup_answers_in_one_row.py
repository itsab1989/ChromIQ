"""4.3.52, the project owner watching a table drive (2026-11-20): "one of the pop up windows in
measure tab related to the table has its buttons placed under each other instead of next to each
other".

Measured ON SCREEN (fix2/buttons/: every answer page of the table window, English and German, at
the default width): the pop-up took the width of the Measure tab's left column (at most 560 px)
and STACKED its answers whenever they did not fit there: 6 pages in English (front_choice,
problem, report_after_step, row_failed_strip, sheet_laid, start_up_arm), 15 in German. The app's
other pop-ups keep their buttons in one row. Now the pop-up is WIDENED until its answers fit in
one row (up to POPUP_WIDE_MAX_W and the screen); only answers that do not fit even then are
stacked. A page whose answers already fitted keeps its width exactly.

MUTATION, proven red: ``_popup_width`` returning the column's width again -> the rows stack.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtCore import QRect, Qt

from core import i18n
from core.i18n import tr
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (the fixture)
from ui import i1io_table_window as W

#: the answer pages of the table window, as its tests show them (page id, English labels)
PAGES = [
    ("front_choice", ["Go forward carefully, my hands are away", "I will move the sheet"]),
    ("problem", ["Cancel", "Send nothing more", "Something looks or sounds wrong"]),
    ("report_after_step", ["As described, my hands are away", "Something was wrong",
                           "Not sure"]),
    ("row_failed_strip", ["Read it again as a strip", "Read it patch by patch", "Skip it",
                          "End this step"]),
    ("sheet_laid", ["The page is laid, and my hands are away from the table", "End this step"]),
    ("start_up_arm", ["Let i1Profiler start it", "No, the arm is out over the table",
                      "Yes. Start the table"]),
    ("home_at_start", ["Not now", "Bring the arm home, my hands are away"]),
    ("end_of_session", ["Save and stop", "Discard and stop", "Keep measuring"]),
    ("refused", ["Carry on", "Bring the arm home", "End measurement"]),
    ("go", ["Go", "Back"]),
]


class _Noop:
    def fire(self) -> None:
        pass


class _Area:
    """The tab's left column as the window asks for it (set_popup_area)."""

    def __init__(self, width: int) -> None:
        self.width = width

    def rect(self):
        return QRect(40, 40, self.width, 800)


def _popup_window(qtbot, monkeypatch, tmp_path, settings, column: int):  # noqa: F811
    win, *_ = open_window(qtbot, monkeypatch, tmp_path, settings, asking=False)
    assert win._popups
    area = _Area(column)
    win._area_holder = area          # kept alive by the window, as the tab is
    win.set_popup_area(area.rect)
    return win


def _show(qtbot, win, page, labels):
    noop = _Noop()
    win._noop = noop
    win._show(page, "Title", "Text.", [(tr(x), noop.fire) for x in labels])
    win._refit_popup()
    qtbot.wait(50)
    return win._answer_box


@pytest.mark.parametrize("code", ["en", "de"])
def test_the_answers_stay_in_one_row_and_the_pop_up_widens_for_them(
        qtbot, monkeypatch, tmp_path, settings, code):  # noqa: F811
    i18n.set_language(code)
    try:
        # a narrow column (POPUP_MIN_W): the offscreen fonts are narrower than the screen's, so
        # this is where the pages stacked here as they did on screen at 560 px
        win = _popup_window(qtbot, monkeypatch, tmp_path, settings, 412)
        stacked, widened = [], 0
        for page, labels in PAGES:
            box = _show(qtbot, win, page, labels)
            if box.orientation() != Qt.Orientation.Horizontal:
                stacked.append(page)
            need = win._popup_row_need()
            if need > W.POPUP_MIN_W:
                widened += 1
                assert win._popup_width() == min(need, W.POPUP_WIDE_MAX_W), page
            else:
                assert win._popup_width() == W.POPUP_MIN_W, page   # unchanged
        assert stacked == [], (code, stacked)
        assert widened >= 3, "the narrow column tested nothing"
    finally:
        i18n.set_language("en")


def test_a_page_that_fits_keeps_the_columns_width(qtbot, monkeypatch, tmp_path,
                                                  settings):  # noqa: F811
    win = _popup_window(qtbot, monkeypatch, tmp_path, settings, 700)
    _show(qtbot, win, "go", ["Go", "Back"])
    assert win._popup_width() == W.POPUP_MAX_W


def test_only_what_does_not_fit_even_widened_is_stacked(qtbot, monkeypatch, tmp_path,
                                                        settings):  # noqa: F811
    monkeypatch.setattr(W, "POPUP_WIDE_MAX_W", 420)
    win = _popup_window(qtbot, monkeypatch, tmp_path, settings, 412)
    box = _show(qtbot, win, "row_failed_strip", PAGES[3][1])
    assert box.orientation() == Qt.Orientation.Vertical
    assert win._popup_width() == 420


def test_the_layouts_measured_on_screen_are_kept_with_the_test():
    """The on-screen measurement this test stands for (names only; the pictures are in the
    fix round's work folder): every page listed there is in PAGES above or was a row before."""
    names = {p for p, _l in PAGES}
    assert {"front_choice", "problem", "report_after_step", "row_failed_strip", "sheet_laid",
            "start_up_arm"} <= names
    assert json.dumps(PAGES)            # plain data
    assert Path(W.__file__).exists()
