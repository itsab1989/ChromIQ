"""Round B, part 1: the instrument's button as "Aimed" (the job, on the simulated table and a
simulated helper behind the app's own ``reader.PressWaiter``; no hardware).

| the brief                                                        | here                        |
|------------------------------------------------------------------|-----------------------------|
| a press answers exactly the aiming question, as the Aimed button | test_a_press_aims_*         |
| the same log line plus "by the instrument's button"               | test_a_press_aims_*         |
| a press never sends a table line, never moves, never counts as GO | test_a_press_is_never_a_go  |
| a press while no aiming question waits: ignored and logged        | test_a_press_while_*        |
| a press after the panel's button: ignored (token)                 | test_a_press_after_the_*    |
| Stop / Report a problem / End measurement cancel the wait          | test_*_cancels_the_wait     |
| the wait has let go of the i1Pro 2 before any reader opens         | test_the_wait_is_closed_*   |
| an older helper: not offered, the panel's Aimed works, same wire   | test_without_the_button_*   |
| a button wait that cannot start / dies: nothing lost               | test_a_button_wait_that_*   |
"""
from __future__ import annotations

import pytest

from tests.i1io_table import tester_d2 as D2
from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import read_page, small_sheet
from workflow.i1io.table import job as J


def _job(tmp_path, press=True, faults=None, asking=False):
    sheet = small_sheet()
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                                ask_after_each_step=asking, press=press,
                                                faults=faults)
    return job, sim, helper, run


class ButtonPerson(H.Person):
    """Answers every aiming question with ONE press of the instrument's button (when the job
    offers it), everything else as the scripted person."""

    def __init__(self, job, sim, helper, by_button=True, script=None):
        super().__init__(job, sim, script)
        self.helper = helper
        self.by_button = by_button
        self.pressed = 0

    def drive(self, res):
        while True:
            if res.kind == J.Kind.NEEDS and res.confirm == J.Confirm.AIMED and self.by_button \
                    and res.detail.get("button"):
                self.asked.append((res.step, res.confirm, dict(res.detail),
                                   len(self.sim.received), self.sim.moving))
                self.sim.aim(res.detail["mark"])
                self.sim.clock += 2.0                   # the person pushes the arm, then presses
                ev = self.helper.press()
                assert ev and ev["event"] == "press", ev
                self.pressed += 1
                res = self.job.answer_by_button(ev["id"])
                continue
            if res.kind != J.Kind.NEEDS:
                return super().drive(res)
            # one scripted answer, then look again
            self.asked.append((res.step, res.confirm, dict(res.detail), len(self.sim.received),
                               self.sim.moving))
            key = (res.confirm, res.detail.get("mark"))
            ans = self.script.get(key, self.script.get(res.confirm))
            if res.confirm == J.Confirm.AIMED and ans == "aimed":
                self.sim.aim(res.detail["mark"])
            res = self.job.answer(res.confirm, ans)


def _to_aims(job, p):
    for s in ("open", "calibrate"):
        r = p.drive(getattr(job, s)())
        assert r.ok, (s, r.reason)


def _log(job) -> str:
    return job.diag.log_path.read_text(encoding="utf-8")


def test_a_press_aims_each_mark_and_the_log_says_so(tmp_path):
    job, sim, helper, _run = _job(tmp_path)
    p = ButtonPerson(job, sim, helper)
    _to_aims(job, p)
    r = p.drive(job.align())
    assert r.ok, r.reason
    assert p.pressed == 3
    assert job.button_aims == [(1, 1), (1, 2), (1, 3)]
    log = _log(job)
    assert log.count("button press received: mark") == 3
    assert log.count("aimed -> aimed (by the instrument's button)") == 3
    assert log.count("(aimed by the instrument's button)") == 3
    rows = read_page(job, p)
    assert rows and all(x.ok for x in rows)
    job.close()


def test_a_press_sends_exactly_the_wire_of_the_aimed_button(tmp_path):
    """The table hears the same bytes whether the person pressed the panel's Aimed or the
    instrument's button: a press is an answer, never a line."""
    wires = []
    for by_button, sub in ((False, "panel"), (True, "button")):
        job, sim, helper, _run = _job(tmp_path / sub)
        p = ButtonPerson(job, sim, helper, by_button=by_button)
        _to_aims(job, p)
        assert p.drive(job.align()).ok
        read_page(job, p)
        p.drive(job.home())
        job.close()
        wires.append(list(sim.received))
    assert wires[0] == wires[1]


def test_a_press_is_never_a_go(tmp_path):
    job, sim, helper, _run = _job(tmp_path)
    p = ButtonPerson(job, sim, helper)
    _to_aims(job, p)
    assert p.drive(job.align()).ok
    res = D2.check_move(job)
    assert res.kind == J.Kind.NEEDS and res.confirm == J.Confirm.GO
    sent = len(sim.received)
    # the button wait has ended with the aims: nothing hears a press now, and a stale token
    # is refused
    assert helper.press() is None
    tok = [e["id"] for pp in helper.press_procs for e in pp.events if e.get("event") == "press"]
    out = job.answer_by_button(tok[-1])
    assert out.kind == J.Kind.REFUSED and out.reason == J.BUTTON_IGNORED
    assert out.detail["why"] == "no_aiming_question"
    assert len(sim.received) == sent and not sim.moving
    assert job._pending is not None and job._pending.kind == J.Confirm.GO
    assert "ignored (no_aiming_question)" in _log(job)


def test_a_press_while_no_aiming_question_waits_is_ignored_and_logged(tmp_path):
    job, sim, helper, _run = _job(tmp_path)
    p = ButtonPerson(job, sim, helper)
    _to_aims(job, p)
    res = job.align()
    while res.confirm != J.Confirm.AIMED:
        res = job.answer(res.confirm, p.script[res.confirm])
    # an earlier arm is used up by the panel's answer: the next press (between arms) is
    # reported by the helper as not armed; the job never sees it as an answer
    sim.aim(1)
    res = job.answer(J.Confirm.AIMED, "aimed")
    assert res.confirm == J.Confirm.AIMED and res.detail["mark"] == 2
    sent = len(sim.received)
    out = job.answer_by_button("p1-m9-99")
    assert out.reason == J.BUTTON_IGNORED and out.detail["why"] == "not_this_question"
    assert len(sim.received) == sent
    assert "ignored (not_this_question)" in _log(job)


def test_a_press_after_the_panels_button_is_ignored(tmp_path):
    job, sim, helper, _run = _job(tmp_path)
    p = ButtonPerson(job, sim, helper)
    _to_aims(job, p)
    res = job.align()
    while res.confirm != J.Confirm.AIMED:
        res = job.answer(res.confirm, p.script[res.confirm])
    tok1 = res.detail["button_token"]
    sim.aim(1)
    sim.clock += 1.0
    ev = helper.press()                          # the press is reported for mark 1 ...
    assert ev["event"] == "press" and ev["id"] == tok1
    res = job.answer(J.Confirm.AIMED, "aimed")   # ... but the panel's Aimed came first
    assert res.detail["mark"] == 2
    sent = len(sim.received)
    out = job.answer_by_button(tok1)
    assert out.reason == J.BUTTON_IGNORED
    assert len(sim.received) == sent
    assert job._pending.detail["mark"] == 2      # the question for mark 2 is still open
    # and the same press can never answer twice
    sim.aim(2)
    sim.clock += 1.0
    ev2 = helper.press()
    assert job.answer_by_button(ev2["id"]).confirm == J.Confirm.AIMED
    again = job.answer_by_button(ev2["id"])
    assert again.reason == J.BUTTON_IGNORED and again.detail["why"] == "used_already"


def test_a_press_too_soon_after_the_question_is_not_an_answer(tmp_path):
    job, sim, helper, _run = _job(tmp_path)
    p = ButtonPerson(job, sim, helper)
    _to_aims(job, p)
    res = job.align()
    while res.confirm != J.Confirm.AIMED:
        res = job.answer(res.confirm, p.script[res.confirm])
    ev = helper.press()                          # at once: meant for the question before
    assert ev["event"] == "press_ignored" and ev["why"] == "too_soon"
    assert job.answer_by_button(res.detail["button_token"]).reason == J.BUTTON_IGNORED


def _at_first_aim(tmp_path):
    job, sim, helper, run = _job(tmp_path)
    p = ButtonPerson(job, sim, helper)
    _to_aims(job, p)
    res = job.align()
    while res.confirm != J.Confirm.AIMED:
        res = job.answer(res.confirm, p.script[res.confirm])
    return job, sim, helper, res


def test_stop_cancels_the_wait(tmp_path):
    job, sim, helper, res = _at_first_aim(tmp_path)
    tok = res.detail["button_token"]
    job.stop_at_next_pause()
    w = helper.press_procs[-1]
    assert {"cmd": "press_disarm"} in w.sent
    sim.clock += 2.0
    assert helper.press()["why"] == "not_armed"
    assert job.answer_by_button(tok).reason == J.BUTTON_IGNORED
    # the panel's answer ends the step (the stop is honoured before the next move) and the
    # wait lets go of the instrument
    out = job.answer(J.Confirm.AIMED, "aimed")
    assert out.reason == J.STOPPED_BEFORE_THE_NEXT_MOVE
    job._press_join()
    assert not w.alive()


@pytest.mark.parametrize("kind", J.PROBLEM_KINDS)
def test_report_a_problem_cancels_the_wait(tmp_path, kind):
    job, sim, helper, res = _at_first_aim(tmp_path)
    sent = len(sim.received)
    job.report_problem(kind)
    job._press_join()
    w = helper.press_procs[-1]
    assert not w.alive() and {"cmd": "press_quit"} in w.sent
    assert job.answer_by_button(res.detail["button_token"]).reason == J.BUTTON_IGNORED
    assert len(sim.received) == sent


def test_end_measurement_cancels_the_wait(tmp_path):
    """The window's End measurement withdraws the aiming question (its "stop")."""
    job, sim, helper, res = _at_first_aim(tmp_path)
    out = job.answer(J.Confirm.AIMED, "stop")
    assert out.kind == J.Kind.REFUSED and out.reason == "stopped_during_the_aims"
    job._press_join()
    assert not helper.press_procs[-1].alive()
    assert job.answer_by_button(res.detail["button_token"]).reason == J.BUTTON_IGNORED


def test_cancel_cancels_the_wait(tmp_path):
    job, sim, helper, res = _at_first_aim(tmp_path)
    job.cancel()
    job._press_join()
    assert not helper.press_procs[-1].alive()


def _slow_closing_waits(job, delay_s: float, order: list):
    """Final fix round, S-2: every button wait of *job* takes *delay_s* to let go of the
    instrument; *order* gets ("closed", t) when it has, ("reader", t) when a reader starts."""
    import time
    make = job._press_factory

    def factory(folder, log):
        w = make(folder, log)
        real_close = w.close

        def close():
            time.sleep(delay_s)
            real_close()
            order.append(("closed", time.monotonic()))
        w.close = close
        return w
    job._press_factory = factory
    real_reader = job._reader_factory

    def reader(*a, **k):
        order.append(("reader", time.monotonic()))
        return real_reader(*a, **k)
    job._reader_factory = reader


def test_the_wait_is_closed_before_any_reader_opens(tmp_path):
    """Review 13, S-2 (the planted fault F12, a reader that does not wait, survived): with a wait
    that is slow to let go, the next reader starts only after it has."""
    job, sim, helper, _run = _job(tmp_path)
    p = ButtonPerson(job, sim, helper)
    _to_aims(job, p)
    order = []
    _slow_closing_waits(job, 0.4, order)
    seen = []
    orig = job._reader_factory

    def factory(*a, **k):
        seen.append([pp.alive() for pp in helper.press_procs])
        return orig(*a, **k)
    job._reader_factory = factory
    assert p.drive(job.align()).ok
    read_page(job, p)
    assert seen and all(not any(s) for s in seen)
    kinds = [k for k, _t in order]
    assert kinds[0] == "closed" and "reader" in kinds, order
    first_reader = kinds.index("reader")
    assert order[0][1] <= order[first_reader][1]
    job.close()


def test_a_wait_that_does_not_let_go_opens_no_reader_and_says_so(tmp_path, monkeypatch):
    """Review 13, S-2: past the bound, nothing is opened over a held instrument: the row is
    refused truthfully before anything moves, and a later try works once it has let go."""
    monkeypatch.setattr(J, "BUTTON_CLOSE_WAIT_S", 0.2)
    job, sim, helper, _run = _job(tmp_path)
    p = ButtonPerson(job, sim, helper)
    _to_aims(job, p)
    order = []
    _slow_closing_waits(job, 1.5, order)
    assert p.drive(job.align()).ok
    assert p.drive(D2.check_move(job)).ok
    n = len(sim.received)
    r = p.drive(job.read_row())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, J.BUTTON_WAIT_HOLDS)
    assert "reader" not in [k for k, _t in order]
    assert [ln for ln in sim.received[n:] if ln[1:3] in ("m0", "m2", "i1")] == []
    assert "did not let go of the instrument" in _log(job)
    import time
    time.sleep(1.6)                              # it lets go after all
    r = p.drive(job.read_row())
    assert r.ok, (r.reason, r.detail)
    job.close()


def test_without_the_button_the_panel_aims_and_the_wire_is_the_same(tmp_path):
    """An older helper (no button wait) and the job built without a factory: not offered."""
    wires = []
    for press, sub in ((False, "older"), (True, "newer")):
        job, sim, helper, _run = _job(tmp_path / sub, press=press)
        p = ButtonPerson(job, sim, helper, by_button=False)
        _to_aims(job, p)
        assert p.drive(job.align()).ok
        aims = [a for a in p.asked if a[1] == J.Confirm.AIMED]
        assert all(a[2]["button"] is press for a in aims)
        read_page(job, p)
        job.close()
        wires.append(list(sim.received))
        if not press:
            assert helper.press_procs == []
    assert wires[0] == wires[1]


def test_an_older_helper_is_never_started_for_the_button(tmp_path, monkeypatch):
    from workflow.i1io.table import reader as rd
    monkeypatch.setattr(rd, "helper_build", lambda *a, **k: "chromiq-chartread 2026-11-17a "
                        "x+i1io-table-scan")
    started = []
    monkeypatch.setattr(rd, "PressWaiter", lambda *a, **k: started.append(a))
    job, sim, helper, _run = _job(tmp_path, press=False)
    job._press_factory = J._default_press_factory
    p = ButtonPerson(job, sim, helper, by_button=False)
    _to_aims(job, p)
    assert p.drive(job.align()).ok
    assert started == []
    assert job.button_unavailable == "helper_without_button_wait"
    assert "this helper has no button wait" in _log(job)


@pytest.mark.parametrize("fault", ["no_instrument", "wrong_model", "dies", "dies_on_arm"])
def test_a_button_wait_that_cannot_start_or_dies_loses_nothing(tmp_path, fault):
    job, sim, helper, _run = _job(tmp_path, faults={"press": fault})
    p = ButtonPerson(job, sim, helper, by_button=False)
    _to_aims(job, p)
    r = p.drive(job.align())
    assert r.ok, r.reason
    rows = read_page(job, p)
    assert rows and all(x.ok for x in rows)
    job.close()


def test_no_button_before_the_reader_consent(tmp_path):
    """The button wait opens the i1Pro 2 with the ArgyllCMS library: not before the consent."""
    job, sim, helper, _run = _job(tmp_path)
    p = ButtonPerson(job, sim, helper)
    assert p.drive(job.open()).ok
    res = p.drive(job.align())
    assert res.ok
    aims = [a for a in p.asked if a[1] == J.Confirm.AIMED]
    assert aims and not any(a[2]["button"] for a in aims)
    assert job.button_unavailable == "no_reader_consent"
    assert helper.press_procs == []


def test_the_press_never_reaches_any_other_question(tmp_path):
    """Every other confirmation refuses a press: only AIMED carries a token."""
    job, sim, helper, _run = _job(tmp_path)
    p = ButtonPerson(job, sim, helper)
    res = job.open()
    while res.kind == J.Kind.NEEDS:
        assert job.answer_by_button("p1-m1-1").reason == J.BUTTON_IGNORED
        res = job.answer(res.confirm, p.script[res.confirm])
    assert res.ok


# ---- the panel (pytest-qt, the simulated table and helper) -------------------------------------

from tests.i1io_table.test_window import open_window, settings  # noqa: E402,F401
from tests.i1io_table.window_sim import WindowSim  # noqa: E402
from core.i18n import tr  # noqa: E402


def test_the_panel_says_both_ways_and_a_press_answers_like_aimed(qtbot, monkeypatch, tmp_path,
                                                                  settings):  # noqa: F811
    sim = WindowSim(press=True)
    win, sim, run, person, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                         sim=sim, asking=False)
    person.drive_until("aimed")
    text = win._text.text()
    assert "button on the i1Pro 2 itself" in text and "has been tried on one real table so far" in text
    qtbot.waitUntil(lambda: "is ready" in win._status.text(), timeout=5000)
    for mark in (1, 2, 3):
        assert person.page() == "aimed" and win._last.detail["mark"] == mark
        sim.aim(mark)
        sim.sim.clock += 2.0
        ev = sim.helper.press()
        assert ev["event"] == "press"
        qtbot.waitUntil(lambda m=mark: win._busy or person.page() != "aimed"
                        or win._last.detail.get("mark") != m, timeout=5000)
        person.idle()
        if mark < 3:
            # the panel says so on the next mark's question
            assert f"Mark {mark} was aimed by the button on the i1Pro 2." in win._status.text()
    log = run.i1io_table_log(win._stamp).read_text(encoding="utf-8")
    assert log.count("button press received: mark") == 3
    # the next question is the hands-off GO: the button has no say there
    assert person.page() == "go"
    assert sim.helper.press() is None


def test_the_panel_without_the_button_says_nothing_of_it(qtbot, monkeypatch, tmp_path,
                                                         settings):  # noqa: F811
    win, sim, run, person, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                         asking=False)
    person.drive_until("aimed")
    assert "button on the i1Pro 2" not in win._text.text()
    assert "button on the i1Pro 2" not in win._status.text()
    assert win._aim_token is None


def test_a_press_after_the_panels_aimed_is_not_taken(qtbot, monkeypatch, tmp_path,
                                                     settings):  # noqa: F811
    sim = WindowSim(press=True)
    win, sim, run, person, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                         sim=sim, asking=False)
    person.drive_until("aimed")
    tok = win._aim_token
    sim.aim(1)
    person.press("Aimed")                        # the panel first
    assert win._aim_token != tok
    assert win._last.detail["mark"] == 2
    sent = len(sim.sim.received)
    out = win.job.answer_by_button(tok)           # a late press for mark 1
    assert out.reason == "button_press_ignored"
    assert len(sim.sim.received) == sent


def test_a_press_reported_before_stop_is_not_taken_after_it(tmp_path):
    """The helper reported the press, but Stop came before the window passed it on: the wait
    was cancelled, so the press does not answer (the question waits for the panel)."""
    job, sim, helper, res = _at_first_aim(tmp_path)
    tok = res.detail["button_token"]
    sim.aim(1)
    sim.clock += 2.0
    assert helper.press()["event"] == "press"
    job.stop_at_next_pause()
    out = job.answer_by_button(tok)
    assert out.reason == J.BUTTON_IGNORED and out.detail["why"] == "not_this_question"
    assert job._pending is not None and job._pending.kind == J.Confirm.AIMED
