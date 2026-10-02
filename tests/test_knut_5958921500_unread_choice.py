"""After a read, Continue to next or Jump to unread (Knut, #182 5958921500 Q2).

    *"If strips still unread, then re-reading a read strip should not jump to
    next unread, but instead ask with a popup that appears only one time per
    started measurement (resume / re-measurement), then, the behaviour chosen
    by the user is continued until the measurement is stopped (exited) …
    This window function must look at patches not yet measured, not strips,
    as patch-by-patch measurements may have been performed, and this feature
    should work for both patch-by-patch mode and strip mode … This function
    only applies to ChromIQ measurement engine, not ArgyllCMS stock
    chartread."*

Two places are compared after every read: N, the next strip (none after the
last) or the next patch (wrapping), and U, the first strip with an unread
PATCH, or the first unread patch, going forward and wrapping. Equal: go there.
Different: ask once (M-UNREAD-NEXT-OR-JUMP-STRIP / -PATCH) and keep the answer
for the measurement. Nothing unread: the beta-4 rule of
test_knut_5956210745_next_strip_after_a_read.py, unchanged.
"""
from __future__ import annotations

import inspect
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measure_manager import MeasureManager, MeasureParams  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from test_knut_5956210745_next_strip_after_a_read import (  # noqa: E402
    _Runner, _feed, _gotos, _session)

STRIPS = ["A", "B", "C", "D"]
PER = 3


# ---- a chart on disk, and the file the engine resumes from -------------------

def _write_chart(tmp: Path, *, read=(), padding=(), strips=STRIPS,
                 per=PER) -> Path:
    """A .ti2 of *strips* x *per* patches, and a .ti3 holding *read*."""
    rows, sid = [], 1
    for s in strips:
        for k in range(1, per + 1):
            loc = f"{s}{k}"
            rows.append((("0" if loc in padding else str(sid)), loc))
            sid += 1
    ti2 = tmp / "chart.ti2"
    body = "\n".join(f'{i} "{loc}" 50.0 50.0 50.0' for i, loc in rows)
    ti2.write_text(
        'CTI2\n\nORIGINATOR "test"\nNUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n'
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n{body}\nEND_DATA\n",
        encoding="utf-8")
    got = [(i, loc) for i, loc in rows if loc in set(read)]
    if got:
        tbody = "\n".join(f'{i} "{loc}" 50.0 50.0 50.0 20.0 21.0 22.0'
                          for i, loc in got)
        ti2.with_suffix(".ti3").write_text(
            'CTI3\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
            "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
            f"END_DATA_FORMAT\nNUMBER_OF_SETS {len(got)}\nBEGIN_DATA\n"
            f"{tbody}\nEND_DATA\n", encoding="utf-8")
    return ti2


def _all(strips=STRIPS, per=PER):
    return [f"{s}{k}" for s in strips for k in range(1, per + 1)]


def _start(ti2, strips=STRIPS):
    return {"event": "session_start", "chart": str(ti2),
            "strips": [{"strip": s, "read": True} for s in strips]}


def _mgr(tmp, *, read, spot=False, resume=True, padding=(), question=None):
    m, r = _session(question=question)
    m._spot_mode = spot
    m._is_resume = resume
    m._chart_was_complete = False
    asked: list = []
    m.unread_choice_wanted.connect(lambda n, mode: asked.append((n, mode)))
    ti2 = _write_chart(tmp, read=read, padding=padding)
    _feed(m, _start(ti2))
    return m, r, asked


def _sread(strip):
    return {"event": "strip_read", "strip": strip,
            "patches": [{"loc": f"{strip}{k}"} for k in range(1, PER + 1)]}


def _sready(strip, all_done=False):
    return {"event": "strip_ready", "strip": strip, "read": True,
            "all_done": all_done}


def _pread(loc):
    return {"event": "patch_read", "id": "1", "loc": loc}


def _pready(loc, all_done=False):
    return {"event": "spot_ready", "id": "1", "loc": loc, "read": True,
            "all_done": all_done}


def _patch_gotos(runner):
    out = []
    for raw in runner.sent:
        try:
            cmd = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if cmd.get("cmd") == "goto" and "patch" in cmd:
            out.append(cmd["patch"])
    return out


#: A–C read, D not. Re-reading A: N = B, U = D.
ABC = _all(["A", "B", "C"])


# ---- strip mode -----------------------------------------------------------------

def test_next_and_unread_differ_so_it_asks_once_and_moves_nothing(tmp_path):
    m, r, asked = _mgr(tmp_path, read=ABC)
    _feed(m, _sread("A"), _sready("D"))      # the engine jumped to unread D
    assert asked == [(3, "strip")], asked
    assert _gotos(r) == [], "moved before the user had chosen"
    assert m.unread_choice_pending()


@pytest.mark.parametrize("answer, expected", [("next", ["B"]),
                                               ("unread", [])])
def test_the_answer_decides_where_the_reader_goes(tmp_path, answer, expected):
    """Jump to unread: the engine is already on D, so nothing is sent."""
    m, r, asked = _mgr(tmp_path, read=ABC)
    _feed(m, _sread("A"), _sready("D"))
    m.answer_unread_choice(answer)
    m.release_held_strip_move()
    assert _gotos(r) == expected
    m.release_held_strip_move()
    assert _gotos(r) == expected, "released twice"


def test_unread_found_by_patch_where_the_engine_sees_none(tmp_path):
    """C1 read, C2 and C3 not: the engine calls C read (first patch only) and
    stays on A. U is C all the same, and Jump to unread sends the reader."""
    read = _all(["A", "B", "D"]) + ["C1"]
    m, r, asked = _mgr(tmp_path, read=read)
    _feed(m, _sread("A"), _sready("A"))
    assert asked == [(2, "strip")]
    m.answer_unread_choice("unread")
    m.release_held_strip_move()
    assert _gotos(r) == ["C"]


def test_the_second_read_follows_the_answer_without_asking(tmp_path):
    m, r, asked = _mgr(tmp_path, read=ABC)
    _feed(m, _sread("A"), _sready("D"))
    m.answer_unread_choice("next")
    m.release_held_strip_move()
    _feed(m, _sready("B"), _sread("B"), _sready("D"))
    assert asked == [(3, "strip")], "asked a second time"
    assert _gotos(r) == ["B", "C"]


def test_jump_to_unread_is_kept_for_the_next_read(tmp_path):
    m, r, asked = _mgr(tmp_path, read=ABC)
    _feed(m, _sread("A"), _sready("D"))
    m.answer_unread_choice("unread")
    m.release_held_strip_move()
    _feed(m, _sready("B"), _sread("B"), _sready("A"))   # engine stayed put
    assert asked == [(3, "strip")], "asked a second time"
    assert _gotos(r) == ["D"]


def test_continue_on_the_last_strip_stays_on_it(tmp_path):
    """Q1: stay at the last strip. The engine has jumped to unread A, so the
    stay has to be sent."""
    read = _all(["B", "C", "D"])
    m, r, asked = _mgr(tmp_path, read=read)
    _feed(m, _sread("D"), _sready("A"))
    assert asked == [(3, "strip")]
    m.answer_unread_choice("next")
    m.release_held_strip_move()
    assert _gotos(r) == ["D"]


def test_next_equal_to_unread_asks_nothing(tmp_path):
    """A fresh read in order: B is next AND unread, and the engine is there."""
    m, r, asked = _mgr(tmp_path, read=(), resume=False)
    _feed(m, _sread("A"), _sready("B"))
    assert asked == [] and _gotos(r) == []


def test_next_equal_to_unread_is_sent_where_the_engine_went_elsewhere(tmp_path):
    """B's first patch read and the rest not: the engine skips B (first patch
    read) and goes to C; B is next and unread, so the reader goes to B."""
    read = _all(["A"]) + ["B1"]
    m, r, asked = _mgr(tmp_path, read=read)
    _feed(m, _sread("A"), _sready("C"))
    assert asked == [] and _gotos(r) == ["B"]


def test_a_fresh_session_without_resume_counts_the_old_file_as_unread(tmp_path):
    """Without -r the engine starts empty, so a .ti3 on disk reads nothing."""
    m, r, asked = _mgr(tmp_path, read=_all(), resume=False)
    assert m.unread_patch_count() == len(_all())


def test_nothing_unread_keeps_the_beta_4_rule(tmp_path):
    m, r, asked = _mgr(tmp_path, read=_all())
    _feed(m, _sread("A"), _sready("A"))
    assert asked == [] and _gotos(r) == ["B"]
    _feed(m, _sread("D"), _sready("D"))
    assert _gotos(r) == ["B"], "the last strip has nowhere further to go"


def test_padding_is_never_unread(tmp_path):
    """printtarg's fill-up (SAMPLE_ID 0) on D3 was never part of the design."""
    m, r, asked = _mgr(tmp_path, read=[x for x in _all() if x != "D3"],
                       padding=("D3",))
    assert m.unread_patch_count() == 0
    _feed(m, _sread("A"), _sready("A"))
    assert asked == [] and _gotos(r) == ["B"]


def test_the_layout_engines_fill_up_is_never_unread(tmp_path):
    """ChromIQ's own layout engine pads with ordinary ids; the .ti1 says how
    many rows were designed (workflow.measurement_state._engine_fill_up_rows)."""
    from workflow.measurement_state import padding_locations
    ti2 = _write_chart(tmp_path)
    text = ti2.read_text(encoding="utf-8").replace(
        'ORIGINATOR "test"', 'ORIGINATOR "ChromIQ layout engine"\n'
        'STEPS_IN_PASS "3"')
    ti2.write_text(text, encoding="utf-8")
    ti2.with_suffix(".ti1").write_text(
        "CTI1\n\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\n"
        "END_DATA_FORMAT\nNUMBER_OF_SETS 10\nBEGIN_DATA\nEND_DATA\n",
        encoding="utf-8")
    assert padding_locations(ti2) == {"D2", "D3"}


def test_no_chart_means_unknown_and_the_beta_4_rule(tmp_path):
    m, r = _session(complete=False)
    asked: list = []
    m.unread_choice_wanted.connect(lambda n, mode: asked.append(n))
    _feed(m, {"event": "session_start", "chart": "",
              "strips": [{"strip": s, "read": False} for s in STRIPS]},
          _sread("A"), _sready("C"))
    assert asked == [] and _gotos(r) == []


# ---- the guards ------------------------------------------------------------------

def test_guided_refinement_is_never_asked_about(tmp_path):
    m, r, asked = _mgr(tmp_path, read=ABC)
    m._guided_strips = ["A", "C"]
    m._guided_state = "waiting"
    _feed(m, _sread("A"), _sready("D"))
    assert asked == []


def test_completion_news_is_never_asked_about(tmp_path):
    m, r, asked = _mgr(tmp_path, read=ABC)
    m._chart_was_complete = False
    m._is_resume = False
    m._read_something = True
    m._after_a_read("strip", "D", True)
    assert asked == []


def test_a_skip_still_being_delivered_is_never_asked_about(tmp_path):
    m, r, asked = _mgr(tmp_path, read=ABC)
    _feed(m, _sread("A"))
    m._pending_post_retry_key = "f"
    _feed(m, _sready("D"))
    assert asked == []


def test_stock_chartread_is_never_asked_about(tmp_path):
    m, r, asked = _mgr(tmp_path, read=ABC)
    m._engine_active = False
    m._just_read_strip = "A"
    m._after_a_read("strip", "D", False)
    assert asked == []


def test_an_open_window_holds_the_question_until_it_closes(tmp_path):
    open_now = [True]
    m, r, asked = _mgr(tmp_path, read=ABC, question=lambda: open_now[0])
    _feed(m, _sread("A"), _sready("D"))
    assert asked == [], "asked on top of a window that was still asking"
    open_now[0] = False
    m.release_held_strip_move()
    assert asked == [(3, "strip")]


def test_read_it_again_from_a_window_cancels_the_decision(tmp_path):
    open_now = [True]
    m, r, asked = _mgr(tmp_path, read=ABC, question=lambda: open_now[0])
    _feed(m, _sread("A"), _sready("D"))
    open_now[0] = False
    m.goto_strip("A")                          # "Re-read" sends its goto first
    m.release_held_strip_move()
    assert asked == [] and _gotos(r) == ["A"]


def test_a_dismissal_answers_nothing_and_does_not_loop(tmp_path):
    m, r, asked = _mgr(tmp_path, read=ABC)
    _feed(m, _sread("A"), _sready("D"))
    m.answer_unread_choice(None)               # the X, Escape
    m.release_held_strip_move()
    assert asked == [(3, "strip")] and _gotos(r) == []
    assert m._unread_policy is None
    _feed(m, _sready("B"), _sread("B"), _sready("D"))
    assert asked == [(3, "strip"), (3, "strip")], "the next read asks again"


@pytest.mark.parametrize("key", ["f", "n", "b"])
def test_the_users_own_key_wins_and_the_answer_survives(tmp_path, key):
    m, r, asked = _mgr(tmp_path, read=ABC)
    _feed(m, _sread("A"), _sready("D"))
    m.send_key(key)
    assert not m.unread_choice_pending()
    m.answer_unread_choice("next")             # answered after the key
    m.release_held_strip_move()
    assert _gotos(r) == [], "overrode the user's own move"
    assert m._unread_policy == "next"


def test_a_swipe_already_started_cancels_the_decision(tmp_path):
    m, r, asked = _mgr(tmp_path, read=ABC)
    _feed(m, _sread("A"), _sready("D"), {"event": "scan_started"})
    m.answer_unread_choice("next")
    m.release_held_strip_move()
    assert _gotos(r) == []


def test_start_forgets_the_answer(tmp_path):
    """One answer per started measurement (resume / re-measurement)."""
    class _StartRunner(_Runner):
        def run(self, *a, **k):
            pass

    m = MeasureManager(_StartRunner())
    m._unread_policy = "unread"
    m._held_after_read = {"mode": "strip", "read": "A", "at": "D"}
    m._unread_locs = {"D1"}
    m.start(MeasureParams(ti1_path=tmp_path / "chart.ti1",
                          engine_helper=Path("/nonexistent/helper")),
            lambda _s: None, lambda _c: None)
    assert m._unread_policy is None
    assert m._held_after_read is None
    assert m.unread_patch_count() == 0


# ---- patch by patch ----------------------------------------------------------------

#: Everything read but C2. Re-reading A1: the engine steps to A2 (N), U = C2.
ALL_BUT_C2 = [x for x in _all() if x != "C2"]


def test_patch_mode_asks_when_the_next_patch_is_not_the_unread_one(tmp_path):
    m, r, asked = _mgr(tmp_path, read=ALL_BUT_C2, spot=True)
    _feed(m, _pread("A1"), _pready("A2"))
    assert asked == [(1, "patch")]
    assert _patch_gotos(r) == []


def test_patch_mode_jump_to_unread_notes_the_goto_first(tmp_path):
    m, r, asked = _mgr(tmp_path, read=ALL_BUT_C2, spot=True)
    order: list = []
    m.set_before_goto_patch(lambda loc: order.append(("note", loc,
                                                      len(r.sent))))
    _feed(m, _pread("A1"), _pready("A2"))
    m.answer_unread_choice("unread")
    m.release_held_strip_move()
    assert _patch_gotos(r) == ["C2"]
    assert order == [("note", "C2", len(r.sent) - 1)], (
        "the CR30 bridge must hear of a jump BEFORE the command goes out")


def test_patch_mode_continue_to_next_sends_nothing(tmp_path):
    """The engine has already stepped to the next patch (incflag = 1)."""
    m, r, asked = _mgr(tmp_path, read=ALL_BUT_C2, spot=True)
    _feed(m, _pread("A1"), _pready("A2"))
    m.answer_unread_choice("next")
    m.release_held_strip_move()
    _feed(m, _pread("A2"), _pready("A3"))
    assert _patch_gotos(r) == [] and asked == [(1, "patch")]


def test_patch_mode_reading_in_order_asks_nothing(tmp_path):
    m, r, asked = _mgr(tmp_path, read=(), spot=True, resume=False)
    _feed(m, _pread("A1"), _pready("A2"), _pread("A2"), _pready("A3"))
    assert asked == [] and _patch_gotos(r) == []


def test_patch_mode_wraps_round_to_find_the_unread_patch(tmp_path):
    read = [x for x in _all() if x != "A1"]
    m, r, asked = _mgr(tmp_path, read=read, spot=True)
    m._unread_policy = "unread"
    _feed(m, _pread("C3"), _pready("D1"))
    assert _patch_gotos(r) == ["A1"]


def test_a_patch_read_marks_it_read(tmp_path):
    m, r, asked = _mgr(tmp_path, read=ALL_BUT_C2, spot=True)
    _feed(m, _pread("C2"), _pready("C3", all_done=True))
    assert m.unread_patch_count() == 0 and asked == []


# ---- the verification that is resumed reads the same file ---------------------------

def test_a_staged_verification_is_the_file_the_map_reads(tmp_path):
    """A verification's readings are copied to `<chart>.ti3` before the read
    (`_stage_verification_for_resume`), the very file `-r` resumes from and the
    map counts from."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._stage_verification_for_resume)
    assert 'beside = Path(self._ti1_path).with_suffix(".ti3")' in src
    assert "self._staged_verification_ti3 = beside" in src
    src = inspect.getsource(MeasureManager._build_read_map)
    assert 'ti2.with_suffix(".ti3")' in src
    ti1 = tmp_path / "chart.ti1"
    assert ti1.with_suffix(".ti3") == (tmp_path / "chart.ti2").with_suffix(".ti3")


# ---- the tab: the window, its buttons, its words -------------------------------------

class _Settings:
    def __init__(self):
        self._d = {"appearance": "dark", "chartread_engine": "chromiq"}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


@pytest.fixture
def tab(qapp, monkeypatch):
    from PyQt6.QtCore import QRect

    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings()
    t = TabMeasure(ArgyllRunner(s), s)
    t._page_stripe_rects = [[QRect(0, i * 30, 100, 20) for i in range(4)]]
    t._strips_per_page = [4]
    monkeypatch.setattr(type(t._runner), "is_running",
                        property(lambda self: True))
    mgr = t._manager
    sent: list[str] = []
    mgr._runner.write_stdin = sent.append
    mgr._engine_active = True
    mgr._is_resume = True
    t._sent = sent
    yield t
    t.deleteLater()


def _answer_window(qapp, button_text, seen):
    """Click *button_text* (or close) in the unread window once it is up."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

    def _click():
        dlg = QApplication.activeModalWidget()
        if dlg is None or dlg.objectName() != "unread_choice_window":
            QTimer.singleShot(10, _click)
            return
        seen.append((dlg.windowTitle(),
                     [lb.text() for lb in dlg.findChildren(QLabel)],
                     [b.text() for b in dlg.findChildren(QPushButton)]))
        if button_text is None:
            dlg.reject()
            return
        for b in dlg.findChildren(QPushButton):
            if b.text() == button_text:
                b.click()
                return
    QTimer.singleShot(0, _click)


def _tab_gotos(tab):
    class _R:
        sent = tab._sent
    return _gotos(_R)


def _spin(qapp, n=20):
    for _ in range(n):
        qapp.processEvents()


@pytest.mark.parametrize("button, expected", [("Continue to next", ["B"]),
                                               ("Jump to unread", ["C"]),
                                               (None, [])])
def test_the_window_opens_once_and_each_answer_moves_the_reader(
        tab, qapp, tmp_path, button, expected):
    mgr = tab._manager
    read = _all(["A", "B", "D"]) + ["C1"]
    ti2 = _write_chart(tmp_path, read=read)
    _feed(mgr, _start(ti2))
    seen: list = []
    _answer_window(qapp, button, seen)
    _feed(mgr, _sread("A"), _sready("A"))
    _spin(qapp)
    assert len(seen) == 1, f"the window opened {len(seen)} times"
    title, labels, buttons = seen[0]
    assert title == "Some patches are still not read"
    assert any(lb.startswith("2 patches on this chart") for lb in labels)
    assert buttons == ["Continue to next", "Jump to unread"]
    assert _tab_gotos(tab) == expected
    _spin(qapp)
    assert len(seen) == 1, "the window came back by itself"


def test_the_window_waits_for_a_window_already_open(tab, qapp, tmp_path):
    """Strip Read Quickly is up when the read lands: no second window on top
    of it, and the question comes when it closes."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QDialog
    mgr = tab._manager
    _feed(mgr, _start(_write_chart(tmp_path, read=ABC)))
    _feed(mgr, _sread("A"))
    seen: list = []
    dlg = QDialog(tab)
    asked_while_open: list = []

    def _inside():
        _feed(mgr, _sready("D"))
        _spin(qapp, 5)
        asked_while_open.append(len(seen))
        _answer_window(qapp, "Continue to next", seen)
        dlg.accept()
    QTimer.singleShot(0, _inside)
    tab._exec_measurement_window(dlg)
    _spin(qapp, 40)
    assert asked_while_open == [0]
    assert len(seen) == 1
    assert _tab_gotos(tab) == ["B"]


def test_a_question_already_queued_never_opens_on_top_of_a_window(
        tab, qapp, tmp_path):
    """The question was asked straight from a read, and a window opened before
    the event loop came round to it: it waits for that window's release."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QDialog
    mgr = tab._manager
    _feed(mgr, _start(_write_chart(tmp_path, read=ABC)))
    from PyQt6.QtWidgets import QApplication, QPushButton
    dlg = QDialog(tab)
    on_top: list = []
    answered: list = []

    def _watch():
        w = QApplication.activeModalWidget()
        if w is not None and w.objectName() == "unread_choice_window":
            if dlg.isVisible():
                on_top.append(1)
                w.reject()
            else:
                for b in w.findChildren(QPushButton):
                    if b.text() == "Jump to unread":
                        answered.append(1)
                        b.click()
                return
        QTimer.singleShot(5, _watch)

    def _inside():
        mgr._decide_after_read({"mode": "strip", "read": "A", "at": "D"})
        _spin(qapp, 10)
        dlg.accept()
    QTimer.singleShot(0, _watch)
    QTimer.singleShot(0, _inside)
    tab._exec_measurement_window(dlg)
    _spin(qapp, 40)
    assert on_top == [], "opened on top of the window already up"
    assert answered == [1] and mgr._unread_policy == "unread"


def test_the_cr30_bridge_hears_of_the_jump_first(tab, qapp, tmp_path):
    mgr = tab._manager
    mgr._spot_mode = True

    class _Bridge:
        def note_goto(self, loc):
            tab._sent.append(f"NOTE {loc}")

        def __getattr__(self, _name):          # the bridge's other slots
            return lambda *a, **k: None
    tab._cr30_bridge = _Bridge()
    _feed(mgr, _start(_write_chart(tmp_path, read=ALL_BUT_C2)))
    seen: list = []
    _answer_window(qapp, "Jump to unread", seen)
    _feed(mgr, _pread("A1"), _pready("A2"))
    _spin(qapp)
    tab._cr30_bridge = None
    assert len(seen) == 1 and seen[0][0] == "One patch is still not read"
    tail = tab._sent[-2:]
    assert tail[0] == "NOTE C2"
    assert json.loads(tail[1]) == {"cmd": "goto", "patch": "C2"}


def test_the_window_takes_its_words_from_the_catalogue():
    from workflow import measurement_messages as M
    for msg in (M.M_UNREAD_NEXT_OR_JUMP_STRIP, M.M_UNREAD_NEXT_OR_JUMP_PATCH):
        assert msg.approved, "Knut approved these words, #182 5962907586"
        t1, b1 = msg.render(n=1)
        tn, bn = msg.render(n=5)
        assert t1 == "One patch is still not read"
        assert tn == "Some patches are still not read"
        assert b1.startswith("One patch on this chart")
        assert bn.startswith("5 patches on this chart")
        for text in (t1, b1, tn, bn):
            assert "—" not in text and "(s)" not in text
        assert "Continue to next:" in bn and "Jump to unread:" in bn


def test_the_window_is_german_in_german(monkeypatch):
    from core import i18n
    from workflow import measurement_messages as M
    cat = json.loads((Path(__file__).resolve().parent.parent / "data" / "i18n"
                      / "de.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(i18n, "tr", lambda s: cat.get(s, s))
    monkeypatch.setattr(M, "tr", lambda s: cat.get(s, s))
    title, body = M.M_UNREAD_NEXT_OR_JUMP_STRIP.render(n=4)
    assert title == "Einige Messfelder sind noch nicht gelesen"
    assert body.startswith("4 Messfelder dieses Charts")
    assert cat["Continue to next"] and cat["Jump to unread"]


# ---- the engine itself, on its replay instrument -------------------------------------

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402


class _PipeRunner:
    is_running = True

    def __init__(self, session):
        self.s = session
        self.sent: list[str] = []

    def write_stdin(self, data):
        self.sent.append(data)
        self.s.proc.stdin.write(data)
        self.s.proc.stdin.flush()


@pytest.mark.slow
@pytest.mark.skipif(not HELPER.exists(),
                    reason="chromiq-chartread helper not built")
def test_the_real_engine_on_a_partial_chart(tmp_path):
    """A resumed chart with its last strip unread: re-reading the first strip
    sends the engine to the unread strip; ChromIQ asks, and Continue to next
    puts it on the second strip."""
    targen = shutil.which("targen") or "/Applications/Argyll/bin/targen"
    if not Path(targen).exists():
        pytest.skip("Argyll targen not available")
    base = tmp_path / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", "-f60", str(base)],
                   check=True, capture_output=True, cwd=tmp_path, timeout=120)
    from workflow.layout_engine.chart import build_chart
    build_chart(base.with_suffix(".ti1"), base, instrument="i1", paper="A4",
                randomize=False)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay)
    # Session 1: read every strip but the last, and quit saving.
    s = ReplaySession(base, replay)
    try:
        labels = [x["strip"] for x in s.wait_event("session_start")["strips"]]
        assert len(labels) >= 3
        for _ in labels[:-1]:
            i = s.event_index()
            s.send(cmd="swipe")
            s.wait_event("strip_read", after=i)
            s.wait_event("strip_ready", after=i)
    finally:
        s.proc.kill()
        s.finish()
    ti3 = base.with_suffix(".ti3")
    assert ti3.is_file(), "the engine autosaves after every strip"

    # Session 2: resume, with the manager on the real pipe.
    s = ReplaySession(base, replay, extra_args=["-r"])
    try:
        runner = _PipeRunner(s)
        m = MeasureManager(runner)
        m._engine_active = True
        m._spot_mode = False
        m._is_resume = True
        asked: list = []
        m.unread_choice_wanted.connect(lambda n, mode: asked.append((n, mode)))
        fed = [0]

        def pump():
            with s._lock:
                evs = list(s.events[fed[0]:])
            fed[0] += len(evs)
            for ev in evs:
                m._handle_engine_line(json.dumps(ev), lambda _l: None)

        s.wait_event("session_start")
        pump()
        assert m.unread_patch_count() > 0
        i = s.event_index()
        m.goto_strip(labels[0])
        s.wait_event("strip_ready", after=i, strip=labels[0])
        pump()
        i = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=i)
        ev = s.wait_event("strip_ready", after=i)
        assert ev["strip"] == labels[-1], "the engine went to the unread strip"
        pump()
        assert asked and asked[0][1] == "strip"
        m.answer_unread_choice("next")
        i = s.event_index()
        m.release_held_strip_move()
        assert s.wait_event("strip_ready", after=i, strip=labels[1])
    finally:
        s.proc.kill()
        s.finish()


def test_a_question_queued_as_the_measurement_ends_never_opens(
        tab, qapp, tmp_path):
    """Review AR, 2026-10-02: the question is asked from the event loop, so the
    session can end between the read and the turn that would open it. A
    measurement's windows end with it (Knut, beta.139), so it must not open
    afterwards, and the held decision is dropped rather than kept for later."""
    mgr = tab._manager
    _feed(mgr, _start(_write_chart(tmp_path, read=ABC)))
    seen: list = []
    _answer_window(qapp, "Continue to next", seen)
    _feed(mgr, _sread("A"), _sready("D"))
    tab._session_live = False          # the session ends before the turn
    _spin(qapp, 40)
    assert seen == []
    assert not mgr.unread_choice_pending()
    assert _tab_gotos(tab) == []
