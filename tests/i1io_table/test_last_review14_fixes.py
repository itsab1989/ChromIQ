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


# ---- M-2: one white reference per session -------------------------------------------------------

def _refuse_stored(monkeypatch, why="stored_white_too_far_from_the_reading"):
    monkeypatch.setattr(sp, "stored_white_factors", lambda stored, spec: (None, why))


def _again_calibrated(job, p):
    job.calibration_due = True
    p.drive(job.home())
    return p.drive(job.calibrate())


def test_m2_a_later_calibration_keeps_the_sessions_reference_and_the_save_works(tmp_path,
                                                                                monkeypatch):
    job, sim, helper, run, p = job_for(tmp_path)
    job.stored_tile_white = True
    sim.stored_tile = tuple([0.88] * 36)
    ready_to_read(job, p)
    assert job.white_scale is not None and job.session_white == "stored"
    r = p.drive(job.read_row())
    assert r.ok, r.reason
    real = sp.stored_white_factors
    _refuse_stored(monkeypatch)
    c = _again_calibrated(job, p)
    # never a silent switch: the calibration is refused, and no row is read with it
    assert (c.kind, c.reason) == (J.Kind.REFUSED, "stored_white_refused_later")
    assert c.detail["why"] == "stored_white_too_far_from_the_reading"
    assert job.calibration is None and job.session_white == "stored"
    assert p.drive(job.read_row()).reason in ("needs_calibration", "needs_alignment",
                                              "arm_not_out_on_the_sheet")
    # calibrate again: the values can be used this time, and the session goes on
    monkeypatch.setattr(sp, "stored_white_factors", real)
    c2 = p.drive(job.calibrate())
    assert c2.ok and job.white_scale is not None
    p.drive(job.align())
    read_page(job, p)
    e = job.end()
    s = job.answer(J.Confirm.END, "save") if e.kind == J.Kind.NEEDS else e
    assert s.ok, (s.reason, s.detail)


def test_m2_end_after_the_refused_calibration_saves_what_was_read(tmp_path, monkeypatch):
    job, sim, helper, run, p = job_for(tmp_path)
    job.stored_tile_white = True
    sim.stored_tile = tuple([0.88] * 36)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    _refuse_stored(monkeypatch)
    assert _again_calibrated(job, p).reason == "stored_white_refused_later"
    e = job.end()
    s = job.answer(J.Confirm.END, "save") if e.kind == J.Kind.NEEDS else e
    assert s.ok, (s.reason, s.detail)
    assert s.detail["measurement"]["state"] == "partial"
    assert "CHROMIQ_TABLE_WHITE" in run.measurement_ti3.read_text(encoding="utf-8")


def test_m2_a_first_white_with_the_own_reference_stays_own(tmp_path, monkeypatch):
    """The stored values unusable at the FIRST calibration: the session measures with the
    i1Pro 2's own reference (said, as before) and keeps it, even when a later calibration
    could use the stored values."""
    job, sim, helper, run, p = job_for(tmp_path)
    job.stored_tile_white = True
    sim.stored_tile = tuple([0.88] * 36)
    real = sp.stored_white_factors
    _refuse_stored(monkeypatch)
    ready_to_read(job, p)
    assert job.white_scale is None and job.session_white == "own"
    assert p.drive(job.read_row()).ok
    monkeypatch.setattr(sp, "stored_white_factors", real)
    c = _again_calibrated(job, p)
    assert c.ok and job.white_scale is None and job.session_white == "own"
    p.drive(job.align())
    read_page(job, p)
    e = job.end()
    s = job.answer(J.Confirm.END, "save") if e.kind == J.Kind.NEEDS else e
    assert s.ok, (s.reason, s.detail)
    assert "CHROMIQ_TABLE_WHITE" not in run.measurement_ti3.read_text(encoding="utf-8")


def _partial_run(tmp_path, stored: bool, monkeypatch):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.ROW_FAILED: "skip"},
                                       faults={"read_loc": {"1-1": "dies"}})
    job.stored_tile_white = stored
    sim.stored_tile = tuple([0.88] * 36)
    ready_to_read(job, p)
    read_page(job, p)
    assert job.save().detail["measurement"]["state"] == "partial"
    job.close()
    return run


@pytest.mark.parametrize("first,now", [(False, True), (True, False)])
def test_m2_a_resume_of_the_other_reference_is_refused_before_start(tmp_path, monkeypatch,
                                                                   first, now):
    run = _partial_run(tmp_path, first, monkeypatch)
    job2, sim2, helper2, _r, p2 = job_for(tmp_path / "second", sheet=small_sheet())
    job2.run = run
    job2._chart_ti2 = run.chart_ti2
    job2.stamp = "20261117-150000"
    from workflow.i1io.table.diagnostics import Diagnostics
    job2.diag = Diagnostics(run.i1io_table_session_dir(job2.stamp),
                            run.i1io_table_log(job2.stamp))
    job2.stored_tile_white = now
    r = job2.set_options(["-p", "-r"])
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "built_on_another_white_reference")
    assert r.detail["built_on"] == ("stored" if first else "own")
    assert job2.phase == "new" and not sim2.received        # nothing was sent
    # with the option as the readings were made, the resume goes on
    job2.stored_tile_white = first
    assert job2.set_options(["-p", "-r"]).ok


@pytest.mark.parametrize("built_on", ["stored", "own"])
def test_m2_the_window_names_what_the_person_can_do(qtbot, monkeypatch, tmp_path, settings,
                                                    built_on):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=True)
    p.drive_until("prepare")
    res = J.StepResult("options", J.Kind.REFUSED, "built_on_another_white_reference",
                       detail={"built_on": built_on, "asked": "own" if built_on == "stored"
                               else "stored"})
    monkeypatch.setattr(win.job, "set_options", lambda *a, **k: res)
    win._set_options()
    assert win.pages_shown[-1] == "white_other_reference"
    msg = M.M_I1IO_DRIVE_WHITE_BASE_STORED if built_on == "stored" else M.M_I1IO_DRIVE_WHITE_BASE_OWN
    assert win._title.text() == msg.render()[0]
    text = win._text.text()
    assert "Preferences > Beta" in text and "measure the chart again" in text
    assert ("switch that option on" in text) == (built_on == "stored")
    assert ("switch that option off" in text) == (built_on == "own")
    assert [b.text() for b in win._buttons] == ["Close"]


def test_m2_the_refused_later_calibration_page_offers_both_ways(qtbot, monkeypatch, tmp_path,
                                                                settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("sheet_laid")
    res = J.StepResult("calibrate", J.Kind.REFUSED, "stored_white_refused_later",
                       detail={"why": "stored_white_too_far_from_the_reading"})
    win._on_refused(res)
    assert win.pages_shown[-1] == "white_later_refused"
    assert [b.text() for b in win._buttons] == ["Save what was read and end", "Calibrate again"]
    assert W.stored_white_reason("stored_white_too_far_from_the_reading") in win._text.text()
    assert W.POPUP_SOUND["white_later_refused"] == "INSTRUMENT_ERROR"
    # the reason the Save could still give names no option the person did not touch
    old = W.reason_text("readings_with_different_white_references")
    assert "Set the option" not in old and "(Preferences > Beta)" not in old


# ---- S-1: a hands-off answer is taken only after its page has been on screen a moment ----------

@BOTH
def test_s1_go_is_not_taken_in_its_first_moment(qtbot, monkeypatch, tmp_path, settings, asking,
                                                hands_off_hold):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=asking)
    p.idle()
    # the first hands-off page of a walk (the sheet is laid / GO), answered at once
    for _ in range(40):
        page = p.page()
        if page in W.MOVES_AT_ONCE_PAGES:
            break
        p.answer_page(page)            # (no hands-off answer before this page)
    label = {"go": "Go", "sheet_laid": "The page is laid, and my hands are away from the table",
             "start_up": "Start the table, my hands are away",
             "first_visit": "Make this move, my hands are away",
             "check_mark": "Yes, it is centred, my hands are away",
             "report_after_step": "As described, my hands are away"}[page]
    b = _btn(win, label)
    n = _moves(sim)
    assert not b.isEnabled()                        # shown as not yet ready
    QTest.mouseClick(b, Qt.MouseButton.LeftButton)   # a click meant for the window before
    b.click()
    qtbot.wait(200)                                  # laid out, still not ready
    assert _moves(sim) == n and win.pages_shown[-1] == page and not win._busy
    assert not b.isEnabled()
    size = b.size()
    qtbot.waitUntil(b.isEnabled, timeout=3000)
    assert b.size() == size                          # the same size, ready now
    b.click()
    p.idle()
    assert win.pages_shown[-1] != page


@BOTH
def test_s1_a_double_click_on_aimed_never_answers_go(qtbot, monkeypatch, tmp_path, settings,
                                                     asking, hands_off_hold):
    """Review 14's probe P-W1, fixed: the second click of a double click on Aimed (mark 3) lands
    on the hands-off answer that follows, and is not taken."""
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=asking)
    monkeypatch.setattr(W, "HANDS_OFF_READY_MS", 0)      # the walk there: a patient person
    for _ in range(60):
        page = p.page()
        if page == "aimed" and win._last.detail.get("mark") == 3:
            break
        p.answer_page(page)
    monkeypatch.setattr(W, "HANDS_OFF_READY_MS", hands_off_hold)
    sim.aim(3)
    QTest.mouseClick(_btn(win, "Aimed"), Qt.MouseButton.LeftButton)
    p.idle()
    nxt = win.pages_shown[-1]
    ho = {"go": "Go", "report_after_step": "As described, my hands are away"}
    assert nxt in ho, nxt
    n = _moves(sim)
    QTest.mouseClick(_btn(win, ho[nxt]), Qt.MouseButton.LeftButton)   # no wait at all
    qtbot.wait(30)
    assert _moves(sim) == n and win.pages_shown[-1] == nxt


def test_s1_the_instruments_button_has_the_same_minimum(hands_off_hold):
    assert J.BUTTON_MIN_MS == W.HANDS_OFF_READY_MS == 600
    import inspect
    from workflow.i1io.table import reader
    assert inspect.signature(reader.PressWaiter.arm).parameters["min_ms"].default == 600


def test_s1_every_hands_off_answer_is_held(hands_off_hold):
    """The held labels are exactly the answers QUESTIONS.md marks as the hands-off
    confirmation (the job's own list, by the window's words)."""
    shown = {W.choice_label(k, v) for k, v in J.HANDS_OFF_ANSWERS}
    shown |= {"Yes, it is centred, my hands are away"}
    assert set(W.HANDS_OFF_LABELS) == shown


# ---- S-2: the strip offer's neutral answer stands where Close stands ----------------------------

def test_s2_not_now_is_the_offers_confirming_answer(qtbot, monkeypatch, tmp_path, settings):
    from tests.i1io_table.test_final_table_pbp_default import KEY, STRIP as PBP_STRIP, _measure
    settings.set(KEY, True)
    settings.set("i1io_table_strip_offer_declined", False)
    try:
        win, p = _measure(qtbot, monkeypatch, tmp_path, settings, PBP_STRIP)
        assert "Reading rows as strips worked for this chart" in win._text.text()
        box = win._answer_box
        R = QDialogButtonBox.ButtonRole
        roles = {b.text(): box.buttonRole(b) for b in box.buttons()}
        assert roles["Not now"] == R.AcceptRole
        assert roles["Yes, make strips the default"] == R.ActionRole
        filled = [b.text() for b in box.buttons() if b.objectName() == "primary"]
        assert filled == ["Not now"]
        assert not any(b.isDefault() or b.autoDefault() for b in box.buttons())
    finally:
        settings.set(KEY, True)
        settings.set("i1io_table_strip_offer_declined", False)


# ---- S-3: a pop-up after whose answer the arm moves at once says how to stop it ----------------

@BOTH
def test_s3_every_page_that_moves_at_once_carries_the_switch_off_line(qtbot, monkeypatch,
                                                                      tmp_path, settings,
                                                                      asking):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=asking)
    p.script.update({"end_of_session": "Save and stop"})
    seen = set()
    for _ in range(200):
        page = p.page()
        if page in W.MOVES_AT_ONCE_PAGES:
            seen.add(page)
            assert W.switch_off_line() in win._text.text(), page
        if page == "done":
            break
        p.answer_page(page)
    assert {"go", "sheet_laid", "check_mark"} <= seen

