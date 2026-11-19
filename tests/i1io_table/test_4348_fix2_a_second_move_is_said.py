"""Safety review 448, SHOULD-4: the person is told, in one plain sentence where the row's progress
is shown (not as a pop-up), that the arm may move a second time by about 1 mm to reach a patch.
It is shown while a row is read patch by patch (the only rows that may send the second move,
``TableJob._move_again_beside``), and not while a row is read as a strip."""
from __future__ import annotations

from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W


def _live(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sim=WindowSim())
    p.drive_until("ready_to_open")
    win._live = {"page": 1, "rows": 3, "rows_read": set(), "readings": 0, "now": "",
                 "table": "Table: connected."}
    return win


def test_the_sentence_is_one_plain_sentence_about_1_mm():
    text = W.second_move_line()
    assert "1 mm" in text and "second" in text
    assert text.count(". ") == 0 and text.endswith(".")
    assert "—" not in text


def test_shown_while_a_row_is_read_patch_by_patch(qtbot, monkeypatch, tmp_path, settings):
    win = _live(qtbot, monkeypatch, tmp_path, settings)
    assert W.second_move_line() not in win.live_state_text()
    win._live_event({"event": "row_start", "row": 1, "page": 1, "kind": "spot"})
    assert W.second_move_line() in win.live_state_text()
    win._live_event({"event": "patch_next", "row": 1, "page": 1, "loc": "A2", "index": 1})
    state = win.live_state_text()
    assert W.second_move_line() in state and "patch A2" in state


def test_not_shown_while_a_row_is_read_as_a_strip(qtbot, monkeypatch, tmp_path, settings):
    win = _live(qtbot, monkeypatch, tmp_path, settings)
    win._live_event({"event": "row_start", "row": 1, "page": 1, "kind": "spot"})
    win._live_event({"event": "row_start", "row": 2, "page": 1, "kind": "strip"})
    assert W.second_move_line() not in win.live_state_text()
    win._live_event({"event": "strip_fallback", "row": 2, "why": "only_some_patches"})
    assert W.second_move_line() in win.live_state_text()


def test_it_is_never_a_pop_up(qtbot, monkeypatch, tmp_path, settings):
    """In the quiet mode with pop-ups, what the job does goes to the 'Now:' line only; the
    sentence is never said as its own pop-up."""
    win = _live(qtbot, monkeypatch, tmp_path, settings)
    said = []
    monkeypatch.setattr(win, "_say", said.append)
    monkeypatch.setattr(win, "_popups", True)
    monkeypatch.setattr(win, "_busy", False)        # no state label refresh in between
    try:
        win._live_event({"event": "row_start", "row": 1, "page": 1, "kind": "spot"})
        win._live_event({"event": "patch_next", "row": 1, "page": 1, "loc": "A2", "index": 1})
    finally:
        monkeypatch.setattr(win, "_popups", False)
    assert said and all(W.second_move_line() not in s for s in said)
