"""Final fix round, S-3 (review 13): no page's text is cut at the scroll edge while its answers
are in view. Either the whole question is shown above the answers, or the answers come AFTER the
text in the scrolling area (the person scrolls through the text to reach them). Checked on every
page of three walks (a failed row and the problem page, a failed strip, the instrument's button
on the aiming pages), at the panel sizes the main window gives down to its smallest. The
ending's question keeps its answers pinned (review 12, S-3): nothing moves on any of them.

Since 4.3.48 (MUST-1 of the dual scan re-review) EVERY page that waits for an answer keeps its
answers pinned in view: a text longer than the room scrolls above them, and its scroll bar says
there is more. The checks below then hold for any page added later that is not pinned;
test_must1_answers_always_in_view.py is the guard for the pinned ones."""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint

from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.window_sim import WindowSim

STRIP = ["-v", "-c", "1", "-S", "chart"]
SIZES = [(560, 760), (420, 600), (380, 520), (330, 480)]


def _ok(win) -> bool:
    if win._answers_pinned() or not win._buttons:
        return True
    vp = win._scroll.viewport()
    t = win._text
    if win._page.indexOf(win._answers) >= 0:
        return win._answers.y() >= t.y() + t.height() - 1
    return t.mapTo(vp, QPoint(0, t.height())).y() <= vp.height() + 1


def _check(win, page, qtbot=None):
    """Once the panel's layout has settled (it re-fits a moment after a page or a size)."""
    if qtbot is not None:
        try:
            qtbot.waitUntil(lambda: _ok(win), timeout=1500)
        except Exception:      # noqa: BLE001 - the assert below says what is wrong
            pass
    t, vp = win._text, win._scroll.viewport()
    assert _ok(win), (page, win.size(), win._room_level, t.y(), t.height(), vp.height(),
                      win._answers.y())


def _walk(win, p, qtbot, until="end_of_session", on_page=None):
    seen = []
    for _ in range(300):
        page = p.page()
        _check(win, page, qtbot)
        seen.append(page)
        if on_page is not None:
            on_page(page)
        if page == until:
            return seen
        p.answer_page(page)
    raise AssertionError(seen[-10:])


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_a_failed_row_and_the_problem_page(qtbot, monkeypatch, tmp_path, settings, size):
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=True,
        sim=WindowSim(faults={"read_loc": {"1-2": "dies"}}))
    win.resize(*size)

    def on_page(page):
        if page == "row_failed":
            win._problem_btn.click()
            _check(win, "problem", qtbot)
            p.press("Cancel")
            sim.helper.faults = {}
    seen = _walk(win, p, qtbot, on_page=on_page)
    assert {"prepare", "sheet_laid", "aimed", "go", "row_failed"} <= set(seen)


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_a_failed_strip(qtbot, monkeypatch, tmp_path, settings, size):
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False, args=STRIP,
        sim=WindowSim(faults={"scan": {"not_ready": True}, "scan_at": 2}))
    p.script["row_failed_strip"] = "Read it patch by patch"
    win.resize(*size)
    seen = _walk(win, p, qtbot)
    assert "row_failed_strip" in seen


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_the_aiming_pages_with_the_instruments_button(qtbot, monkeypatch, tmp_path, settings,
                                                      size):
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False, sim=WindowSim(press=True))
    win.resize(*size)
    texts = []

    def on_page(page):
        if page == "aimed":
            texts.append(win._text.text())
    _walk(win, p, qtbot, until="go", on_page=on_page)
    assert len(texts) == 3 and all("button on the i1Pro 2" in x for x in texts)


def test_the_failed_strip_text_says_hands_away_first():
    from workflow import measurement_messages as M
    body = M.M_I1IO_DRIVE_ROW_FAILED_STRIP.render(row=3, page=1, why="x")[1]
    assert body.index("take your hands away") < body.index("Read it again as a strip")


@pytest.mark.parametrize("size", [(560, 760), (420, 600)], ids=lambda s: f"{s[0]}x{s[1]}")
def test_the_answers_box_keeps_its_whole_height(qtbot, monkeypatch, tmp_path, settings, size):
    """The pictures of this round: the status line under stacked answers ran under the footer's
    rule (the re-fit shrank the answers' box to its hint after the layout had placed it)."""
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=True)
    win.resize(*size)

    def whole():
        a = win._answers
        lay = a.layout()
        if win._page.indexOf(a) >= 0 or not a.isVisible():
            return True
        return a.height() >= lay.totalHeightForWidth(a.width()) - 1
    for _ in range(40):
        page = p.page()
        if win._buttons:
            try:
                qtbot.waitUntil(whole, timeout=1500)
            except Exception:      # noqa: BLE001
                pass
            assert whole(), (page, win._answers.height())
        if page == "end_of_session":
            break
        p.answer_page(page)


def test_an_ended_session_with_the_arm_left_out_says_only_the_way_home(qtbot, monkeypatch,
                                                                       tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("end_of_session")
    p.press("Save and stop")
    assert p.page() == "home_at_end"
    p.leave_it_there()
    assert p.page() == "done"
    text = win._text.text()
    assert "The arm stayed out over the table" in text and "saved into the run" in text
    assert "you can still save them" not in text
