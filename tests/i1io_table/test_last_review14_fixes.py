"""Review 14 (the last fix round before 4.3.45): each finding, with a test that failed before its
fix and passes after it.

* M-1: whenever a move may still be waiting, "Switch the table off now" is the first thing shown,
  in both presentations; Report a problem never replaces it, and no later page hides or
  contradicts it. Every text that says where the arm is comes from the job's true state ("at its
  resting place" only when the table reported it there).
* M-2: a session keeps the white reference of its first calibration; a later calibration that
  cannot give it is refused (calibrate again, or save what was read and end), never a silent
  switch and never a Save refused afterwards; readings of the other reference are refused before
  START with what the person can do.
* S-1 .. S-8 and the notes (sounds, the hold of the hands-off answers, the strip offer, the red
  Stop, the screen edges, "in this panel", the attention request)."""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialogButtonBox

from core.i18n import tr
from tests.i1io_table.test_job_reading import job_for, read_page, ready_to_read, small_sheet
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (the fixture)
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W
from workflow import measurement_messages as M
from workflow.i1io.table import job as J
from workflow.i1io.table import spot as sp

MOVES = ("m0", "m1", "m2", "i1", "i0")
STRIP = ["-v", "-c", "1", "chart"]
BOTH = pytest.mark.parametrize("asking", [False, True], ids=["popups", "panel"])


def _moves(sim) -> int:
    return sum(1 for ln in sim.sim.received if ln[1:3] in MOVES)


def _btn(win, english):
    want = tr(english)
    found = [b for b in win._buttons if b.text() == want]
    assert found, (english, [b.text() for b in win._buttons], win.pages_shown[-1:])
    return found[0]


def _switch_off_titles() -> set:
    return {M.M_I1IO_DRIVE_SWITCH_OFF.render(log="x")[0],
            M.M_I1IO_DRIVE_LINK_LOST_SWITCH_OFF.render(log="x")[0],
            M.M_I1IO_DRIVE_COLD_WAY_OUT.render(log="x")[0]}


def _says_switch_off_first(win) -> bool:
    """The page shown starts with the switch-off instruction: its title is one of the switch-off
    messages', or its text starts with the switch-off line."""
    return win._title.text() in _switch_off_titles() or \
        win._text.text().startswith(W.TableMeasureWindow._switch_off_first())


RESTING = "the arm is at its resting place"


# ---- M-1: Report a problem during a strip row whose scan move may still wait ------------------

def _pending_strip(qtbot, monkeypatch, tmp_path, settings, asking, problem=True, scan_at=2):
    """A strip row whose strip move may still wait for the lamp (the helper's lamp never
    comes), with Report a problem pressed while that row runs (quiet mode: the tab's button,
    i.e. _on_problem while busy; the panel: its own problem page, shown at once)."""
    sim = WindowSim(faults={"scan": {"no_lamp": True}, "scan_at": scan_at})
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=asking, sim=sim, args=STRIP)
    p.drive_until("check_mark")
    seen = []
    win.moving_changed.connect(seen.append)
    tsim = sim.sim
    k0 = len(tsim.received)
    state = {"m2": 0}

    def on_command(i):
        # quiet mode: what _on_problem does while a step runs (from the worker thread here, at
        # the strip move the fault makes wait): the stop request and the window wanted
        if i >= k0 and tsim.received[-1].startswith(";m2"):
            state["m2"] += 1
            if state["m2"] == 1 and win._popups and problem:
                win.job.stop_at_next_pause()
                win._problem_by_stop = True
                win._problem_wanted = True
    tsim.on_command = on_command
    labels = {"first_visit": "Make this move, my hands are away", "go": "Go",
              "report_after_step": "As described, my hands are away",
              "reader_consent": "Open the instrument"}
    _btn(win, "Yes, it is centred, my hands are away").click()      # the rows start
    for _ in range(30):
        if problem and not win._popups and win._busy:
            win._on_problem()          # the panel's Report a problem while the row runs
            assert win.pages_shown[-1] == "problem"
        p.idle()
        page = win.pages_shown[-1]
        if page == "problem" and win._deferred is not None \
                and getattr(win._deferred[1], "kind", "") == W.NEEDS:
            _btn(win, "Cancel").click()      # a question of the row waits behind it: answer it
            continue
        if page in labels:
            _btn(win, labels[page]).click()
            continue
        break
    return win, sim, p, seen


@BOTH
@pytest.mark.parametrize("answer", ["Something looks or sounds wrong", "Send nothing more",
                                    "Cancel"])
def test_m1_problem_during_a_pending_strip_shows_switch_off_first(qtbot, monkeypatch, tmp_path,
                                                                  settings, asking, answer):
    win, sim, p, seen = _pending_strip(qtbot, monkeypatch, tmp_path, settings, asking)
    job = sim.jobs[0]
    assert job.way_back() == "switch_off_pending"
    # the step's result replaced the problem page (panel) / came before the problem window
    # (pop-ups): "Switch the table off now", first
    assert win.pages_shown[-1] == "stopped", win.pages_shown[-4:]
    assert win._title.text() == M.M_I1IO_DRIVE_SWITCH_OFF.render(log="x")[0]
    assert RESTING not in win._text.text().lower()
    if win._popups:
        assert win.popup_open() and seen and seen[-1] is True        # the tab's Stop stays
    else:
        assert win._switch_off.isVisibleTo(win) and win._stop_btn.isVisibleTo(win)
    # Report a problem stays, and its page starts with the switch-off line
    assert win._problem_btn.isVisibleTo(win) or win._popups
    win._on_problem()
    assert win.pages_shown[-1] == "problem" and _says_switch_off_first(win)
    _btn(win, answer).click()
    p.idle()
    assert _says_switch_off_first(win), (win.pages_shown[-1], win._title.text())
    assert RESTING not in win._text.text().lower()
    if win._popups:
        assert seen[-1] is True
    else:
        assert win._switch_off.isVisibleTo(win) and win._stop_btn.isVisibleTo(win)
    # the Stop still works (it is taken, nothing breaks, nothing moves)
    n = _moves(sim)
    win._on_stop()
    p.idle()
    assert _moves(sim) == n


@BOTH
def test_m1_the_ending_after_a_pending_move_never_promises_the_homing(qtbot, monkeypatch,
                                                                      tmp_path, settings,
                                                                      asking):
    win, sim, p, seen = _pending_strip(qtbot, monkeypatch, tmp_path, settings, asking,
                                       problem=False, scan_at=3)
    assert sim.jobs[0].way_back() == "switch_off_pending", win.pages_shown[-6:]
    assert win.pages_shown[-1] == "stopped" and _says_switch_off_first(win)
    win._on_end_pressed()
    p.idle()
    assert win.pages_shown[-1] == "end_of_session"
    assert _says_switch_off_first(win)
    assert M.M_I1IO_DRIVE_END.render()[1] not in win._text.text()
    p.press("Save and stop")
    p.idle()
    for _ in range(5):
        if win.pages_shown[-1] == "done":
            break
        p.answer_page(win.pages_shown[-1])
    assert win.pages_shown[-1] == "done"
    assert win._text.text().startswith(M.M_I1IO_DRIVE_SWITCH_OFF.render(log=win._log_name)[1])
    # the panel's switch-off line stays even now that the table has been let go of
    assert win._switch_off.isVisibleTo(win)


# ---- M-1: the homing refused (the alignment start): the arm's true place ----------------------

@BOTH
def test_m1_something_wrong_at_the_alignment_start_states_the_true_place(qtbot, monkeypatch,
                                                                         tmp_path, settings,
                                                                         asking):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=asking)
    p.drive_until("arm_felt")
    seen = []
    win.moving_changed.connect(seen.append)
    job = sim.jobs[0]
    _btn(win, "It does not move").click()
    p.idle()
    for _ in range(5):
        if win.pages_shown[-1] == "report_after_step":
            _btn(win, "As described, my hands are away").click()
            p.idle()
    # review 13 on the real table's geometry: from the alignment start (2507, 1429) the homing
    # is refused, so the way back is i1Profiler (the simulated table allows that homing; the
    # job's answer is set as the real table gives it)
    monkeypatch.setattr(job, "way_back", lambda: J.WayBack.OPEN_I1PROFILER_ONCE)
    win._on_problem()
    _btn(win, "Something looks or sounds wrong").click()
    p.idle()
    assert job.way_back() == "open_i1profiler_once"
    assert not win._arm_at_rest()
    text = win._text.text()
    assert RESTING not in text.lower()
    assert win._title.text() == M.M_I1IO_DRIVE_AFTER_PROBLEM_OUT.render(where="x")[0]
    assert W.switch_off_line() in text
    if win._popups:
        assert not seen or seen[-1] is True          # the tab's Stop is never switched off here
    else:
        assert win._switch_off.isVisibleTo(win) and win._stop_btn.isVisibleTo(win)


def test_m1_resting_place_only_when_the_table_reported_it(qtbot, monkeypatch, tmp_path,
                                                          settings):
    """The panel's after-problem page with the arm reported at rest still says so (and hides
    the moving controls: nothing can move)."""
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=True)
    p.drive_until("sheet_laid")          # after the calibration: the arm at rest, read there
    assert win._arm_at_rest()
    win._on_problem()
    _btn(win, "Something looks or sounds wrong").click()
    p.idle()
    assert win._title.text() == M.M_I1IO_DRIVE_AFTER_PROBLEM.render()[0]
    assert not win._stop_btn.isVisibleTo(win)


# ---- M-1, the sweep: every page of random walks ------------------------------------------------

@pytest.mark.parametrize("seed", range(24))
def test_m1_no_page_contradicts_the_true_state(qtbot, monkeypatch, tmp_path, settings, seed):
    """Random walks in both presentations, spot and strip, with strip moves that may wait: on
    every page shown, "at its resting place" (the after-problem sentence) only when the table
    reported the arm there, and while a move may still wait the page starts with the switch-off
    instruction and the moving controls are never switched off while the table is open."""
    import random
    rnd = random.Random(seed)
    asking = bool(seed % 2)
    faults = {"scan": {"no_lamp": True}, "scan_at": 1 + seed % 3} if seed % 3 == 0 else None
    args = STRIP if seed % 3 != 1 else None
    sim = WindowSim(faults=faults) if faults else WindowSim()
    bad = []
    real_show = W.TableMeasureWindow._show

    def show(self, page_id, title, text, buttons=(), ticks=()):
        made = real_show(self, page_id, title, text, buttons, ticks)
        shown = self._text.text().lower()
        if M.M_I1IO_DRIVE_AFTER_PROBLEM.render()[1].lower() in shown and not self._arm_at_rest():
            bad.append(("resting place said", page_id))
        if self._switch_off_needed() and not _says_switch_off_first(self):
            bad.append(("switch-off not first", page_id, self._title.text()))
        return made
    monkeypatch.setattr(W.TableMeasureWindow, "_show", show)
    real_moving = W.TableMeasureWindow._moving_controls

    def moving(self, on):
        real_moving(self, on)
        if self._switch_off_needed() and not self._switch_off.isVisibleTo(self):
            bad.append(("switch-off line hidden", self.pages_shown[-1:]))
    monkeypatch.setattr(W.TableMeasureWindow, "_moving_controls", moving)
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=asking, sim=sim, args=args)
    for _ in range(220):
        p.idle()
        if finished or win._finished:
            break
        page = win.pages_shown[-1] if win.pages_shown else ""
        for cb in win._tick_widgets:
            cb.setChecked(True)
        if page == "aimed":
            sim.aim(win._last.detail["mark"])
        r = rnd.random()
        if r < 0.03:
            win._on_stop()
            continue
        if r < 0.07:
            win._on_problem()
            continue
        cands = [b for b in win._buttons if b.isEnabled()]
        if not cands:
            win.reject()
            continue
        want = tr(p.script.get(page, "")) if page in p.script else None
        fw = [b for b in cands if want and b.text() == want]
        (fw[0] if fw and rnd.random() < 0.9 else rnd.choice(cands)).click()
    assert not bad, (seed, bad[:4], win.pages_shown[-10:])

