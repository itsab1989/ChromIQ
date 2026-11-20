"""The answers-in-view guard (``test_must1_answers_always_in_view``, cherry-picked from the dual
scan branch, 3659120b7) extended to 4.3.48's pages: walked for real in the Measure tab of a
900 x 930 and a 900 x 650 main window, German and English, every page the START with "The arm is
out" shows (the ready question with its third answer, the refused page with "Bring the arm home",
the hands-off GO) keeps one whole answer in view at scroll position 0. The page after the homing
after a stop (``home_after_stop_done``) is pinned and checked by the guard's page-by-page test."""
from __future__ import annotations

import pytest

from tests.i1io_table.test_must1_answers_always_in_view import (  # noqa: F401
    SIZES, _one_answer_in_view, host, language)
from tests.i1io_table.test_window import settings  # noqa: F401
from tests.i1io_table.test_window_in_the_measure_tab import beta, start, tab, table_run  # noqa: F401
from tests.i1io_table.window_person import WindowPerson
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W

OUT_HELD = [0.0, 1600.0]


def test_home_after_stop_done_is_pinned():
    assert "home_after_stop_done" in W.TableMeasureWindow.PINNED_ANSWER_PAGES


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_the_arm_out_start_keeps_its_answers_in_view(tab, beta, tmp_path, monkeypatch, qtbot,
                                                     language, size, host):
    tab._settings.set(W.ASK_KEY, True)
    host.resize(*size)
    host.show()
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch, sim=WindowSim(pos=list(OUT_HELD)))
    win = tab._table_window
    p = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=15000))
    bad, seen = {}, []

    def check():
        qtbot.wait(60)
        page = p.page()
        seen.append(page)
        ok, why = _one_answer_in_view(win)
        if not ok:
            bad[page] = why

    assert p.drive_until("ready_to_open") == "ready_to_open"
    win._tick_widgets[1].setChecked(True)
    check()
    p.press("The arm is out")
    # 4.3.52: the START rule's one question (M-I1IO-DRIVE-HOME-AT-START), then after "Not now"
    # the page that offers the homing, then its hands-off GO
    assert p.page() == "home_at_start"
    check()
    p.press("Not now")
    p.idle()
    assert p.page() == "refused"
    check()
    p.press("Bring the arm home")
    assert p.page() == "go"
    check()
    assert not bad, (size, language, win.size(), seen, bad)
