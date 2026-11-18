"""Quiet round, part 3: the open items of the final round's report.

* the true-state box was cut at the scroll edge on the start-up page (the panel): nothing but a
  whole line of the text or the title ends at the edge; any other part is either whole or
  waits below it;
* the failed strip's text says the hands-off sentence FIRST;
* at the smallest main window the ending shows its answers and still some of its explanation
  (the panel)."""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QLabel, QFrame

from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (the fixture)
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W


def _cut_parts(win) -> list:
    """The parts of the scrolled page the visible edge cuts through, other than a plain label
    cut between two of its lines."""
    sc = win._scroll
    edge = sc.viewport().height() + sc.verticalScrollBar().value()
    out = []
    lay = win._page
    for i in range(lay.count()):
        w = lay.itemAt(i).widget()
        if w is None or not w.isVisibleTo(win):
            continue
        top, bottom = w.y(), w.y() + w.height()
        if not (top < edge < bottom):
            continue
        if isinstance(w, QLabel) and w.frameShape() == QFrame.Shape.NoFrame:
            ls = w.fontMetrics().lineSpacing()
            first = top + w.contentsRect().y()
            if (edge - first) % ls == 0:
                continue
        out.append((w.objectName() or type(w).__name__, top, bottom, edge))
    return out


@pytest.mark.parametrize("size", [(440, 300), (440, 360), (500, 420), (560, 470), (440, 520)])
def test_nothing_is_cut_at_the_scroll_edge_on_the_start_up_page(qtbot, monkeypatch, tmp_path,
                                                                settings, size):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sim=WindowSim(cold=True),
                                                    presentation=W.PRESENTATION_PANEL)
    p.drive_until("start_up")
    win.resize(*size)
    qtbot.wait(250)
    assert _cut_parts(win) == [], size


def test_the_failed_strip_text_says_the_hands_off_sentence_first():
    from workflow import measurement_messages as M
    body = M.M_I1IO_DRIVE_ROW_FAILED_STRIP.render(row=3, page=1, why="x")[1]
    hands = body.index("take your hands away from the table and the arm")
    assert hands < body.index("could not be read as a strip"), body
    assert body.startswith("The arm is held where the strip move ended.")


def test_the_ending_shows_answers_and_explanation_in_the_smallest_window(tab, beta, tmp_path,
                                                                         monkeypatch, qtbot):
    """900 x 650 is the main window's minimum; the Measure tab then has about 900 x 540."""
    from tests.i1io_table.test_window_in_the_measure_tab import start, table_run
    from tests.i1io_table.window_person import WindowPerson
    tab._settings.set(W.ASK_KEY, True)                   # the panel
    tab.resize(900, 540)
    tab.show()
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch)
    monkeypatch.setattr(tab, "_show_all_stripes_done", lambda table=False: None)
    win = tab._table_window
    assert win.presentation == W.PRESENTATION_PANEL
    assert not tab._mode_row_widget.isVisible() and not tab._file_grp.isVisible()
    tab._sync_mode_row_visibility()          # the tab's own re-show (seen on screen)
    assert not tab._mode_row_widget.isVisible()
    p = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=15000))
    p.drive_until("end_of_session")
    qtbot.wait(250)
    for b in win._buttons:
        top = b.mapTo(win, QPoint(0, 0)).y()
        assert b.isVisible() and top + b.height() <= win.height(), b.text()
        assert top >= win._scroll.geometry().bottom()
    ls = win._text.fontMetrics().lineSpacing()
    text_top = win._text.mapTo(win._scroll.viewport(), QPoint(0, 0)).y()
    shown = win._scroll.viewport().height() - text_top
    assert shown >= 3 * ls, (shown, ls)                  # at least three lines of it
    p.press("Save and stop")
    p.drive_until("done")
    p.press("Close")
    qtbot.waitUntil(lambda: tab._table_window is None, timeout=5000)
    assert tab._file_grp.isVisibleTo(tab)


from tests.i1io_table.test_window_in_the_measure_tab import beta, tab  # noqa: E402,F401
