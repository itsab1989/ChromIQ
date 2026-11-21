"""4.3.52: "Guided, step by step measurement" OFF (design3 F2/F3, brief release 1, tests T1-T12).

The owner, 2026-11-19 (W8): with the guidance off "the measurement shall be automatic ... so the
first measurement goes through smooth without interruptions". The JOB owns the policy
(BY_SETTING, COUNTDOWN_INSTEAD, SKIPPED); the window answers nothing itself and only shows the
countdown. Nothing on the wire changes (T7): an unguided measurement writes exactly the lines a
guided one answered "yes / go on / save / home" writes, timing aside.

Every test here is written to fail on 4.3.51 (fix/4.3.51-start, 63f5a8492)."""
from __future__ import annotations

import pytest

from core.i18n import tr
from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_4349_acceptance_his_sheet_and_wider import CROSSES_1, HIS_TABLE
from tests.i1io_table.test_job_reading import small_sheet
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (the fixture)
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W
from workflow.i1io.table import job as J
from workflow.i1io.table import reach as rc
from workflow.measurement_state import Ti3State, classify

MOVES = ("m0", "m1", "m2", "i0", "i1")
C = J.Confirm


def _moves(lines) -> int:
    return sum(1 for ln in lines if ln[1:3] in MOVES)


@pytest.fixture
def asked(monkeypatch):
    """Every confirmation kind a job yields to its window, in order."""
    seen: "list[str]" = []
    real = J.TableJob._needs

    def needs(self, step, ask):
        seen.append(ask.kind)
        return real(self, step, ask)
    monkeypatch.setattr(J.TableJob, "_needs", needs)
    return seen


@pytest.fixture(autouse=True)
def _no_breach():
    J.HANDS_OFF_BREACHES.clear()
    yield
    J.HANDS_OFF_BREACHES.clear()


UNGUIDED_ANSWERS = {"aimed": "Aimed", "start_up_arm": "Yes. Start the table",
                    "row_failed": "Read it again", "done": "Close"}
GUIDED_ANSWERS = {"front_choice": "Go forward carefully, my hands are away",
                  "end_of_session": "Save and stop"}


def _unguided(qtbot, monkeypatch, tmp_path, settings, sim=None, sheet=None, extra=None):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    guided=False, sim=sim, sheet=sheet)
    p.script.update(UNGUIDED_ANSWERS)
    p.script.update(extra or {})
    return win, sim, run, p, saved, finished


def _to_done(p, allowed=("aimed", "start_up_arm", "row_failed")) -> "list[str]":
    """Answer the pages an unguided measurement may show, until the done page; any other page
    fails the test (a question the guidance-off mode must not ask)."""
    shown = []
    for _ in range(200):
        page = p.page()
        if page == "done":
            return shown
        assert page in allowed, (page, shown[-6:])
        shown.append(page)
        p.answer_page(page)
    raise AssertionError(shown[-10:])


# ---- T1: exactly these questions, and nothing else ----------------------------------------------

def test_t1_warm_table_the_only_question_is_aiming(qtbot, monkeypatch, tmp_path, settings,
                                                   asked):
    win, sim, run, p, saved, finished = _unguided(qtbot, monkeypatch, tmp_path, settings)
    shown = _to_done(p)
    assert set(asked) == {C.AIMED}, asked
    assert shown == ["aimed"] * 3
    job = sim.jobs[0]
    # saved without being asked (every row read), and the arm brought home after a countdown
    assert saved and classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.COMPLETE
    assert job.ended == "saved" and job.at_rest()
    kinds = [a["kind"] for a in job.auto_answers]
    assert C.READY_TO_OPEN in kinds and C.SHEET_LAID in kinds and C.END in kinds
    assert C.READER_CONSENT in kinds
    assert [c["result"] for c in job.countdowns] and all(
        c["result"] == "done" for c in job.countdowns)
    assert win.countdowns_seen and win.countdowns_seen[0] == 3
    assert J.HANDS_OFF_BREACHES == [] and sim.sim.violations == []
    # the done page offers nothing about the guidance (it is off already)
    assert not win._tick_widgets


def test_t1_cold_table_asks_nothing_about_the_arm(qtbot, monkeypatch, tmp_path, settings,
                                                 asked):
    """4.3.52 (the owner's ruling of 2026-11-20): the start-up is sent wherever the arm is, so
    the arm question after power-on is gone (job.START_UP_ASKS_ABOUT_THE_ARM brings it back,
    test_t1_cold_table_asks_the_arm_question_once_with_the_constant); a countdown stands before
    it, as before every first movement."""
    sim = WindowSim(cold=True)
    win, sim, run, p, saved, finished = _unguided(qtbot, monkeypatch, tmp_path, settings,
                                                  sim=sim)
    shown = _to_done(p)
    assert set(asked) == {C.AIMED}, asked
    assert "start_up_arm" not in shown
    assert any(c["for"] is None or c["for"] == "start_up" or c["step"] == "start_up"
               for c in sim.jobs[0].countdowns)
    assert sim.jobs[0].ended == "saved" and sim.jobs[0].at_rest()
    assert J.HANDS_OFF_BREACHES == [] and sim.sim.violations == []


def test_t1_cold_table_asks_the_arm_question_once_with_the_constant(qtbot, monkeypatch,
                                                                    tmp_path, settings, asked):
    monkeypatch.setattr(J, "START_UP_ASKS_ABOUT_THE_ARM", True)
    sim = WindowSim(cold=True)
    win, sim, run, p, saved, finished = _unguided(qtbot, monkeypatch, tmp_path, settings,
                                                  sim=sim)
    shown = _to_done(p)
    assert set(asked) == {C.START_UP, C.AIMED}, asked
    assert shown[0] == "start_up_arm" and shown.count("start_up_arm") == 1
    assert sim.jobs[0].ended == "saved" and sim.jobs[0].at_rest()
    assert J.HANDS_OFF_BREACHES == [] and sim.sim.violations == []


def test_t1_a_failed_row_is_asked_and_the_end_is_asked_when_one_was_skipped(
        qtbot, monkeypatch, tmp_path, settings, asked):
    sim = WindowSim(faults={"read_loc": {"1-2": "dies"}})
    win, sim, run, p, saved, finished = _unguided(
        qtbot, monkeypatch, tmp_path, settings, sim=sim,
        extra={"row_failed": "Skip it", "end_of_session": "Save and stop"})
    _to_done(p, allowed=("aimed", "row_failed", "end_of_session", "home_at_end"))
    assert set(asked) == {C.AIMED, C.ROW_FAILED, C.END, C.GO}, asked
    # the homing of an ending that is not complete stays a question (W10)
    assert "home_at_end" in win.pages_shown


# ---- T2 / T13: the countdown is what satisfies the hands-off guard, and only it ----------------

def _unguided_job(tmp_path, **kw):
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=small_sheet(),
                                                aims=H.demo_aims(small_sheet()), **kw)
    job.guided = False
    job.consent_version = W.CONSENT_VERSION
    job.calibration_place_preference = "table tile"
    return job, sim, H.Person(job, sim, {})


def test_t2_a_movement_after_an_answer_without_its_countdown_is_refused(tmp_path, monkeypatch):
    """The plant: the countdown that does nothing (the guard is not cleared)."""
    monkeypatch.setattr(J.TableJob, "_countdown", lambda self, step, ask: None)
    job, sim, p = _unguided_job(tmp_path)
    assert p.drive(job.open()).ok and p.drive(job.calibrate()).ok
    n = _moves(sim.received)
    r = p.drive(job.align())
    assert r.kind == J.Kind.STOPPED and J.HANDS_OFF_BREACHES, (r.reason, r.detail)
    assert _moves(sim.received) == n


def test_t2_the_countdown_clears_the_guard_and_nothing_else(tmp_path):
    job, sim, p = _unguided_job(tmp_path)
    assert p.drive(job.open()).ok and p.drive(job.calibrate()).ok
    assert job._hands_off_due                       # READY answered by the setting: still owed
    r = p.drive(job.align())
    assert r.ok and J.HANDS_OFF_BREACHES == []
    assert job.countdowns and job.countdowns[0]["for"] == "align"


# ---- T3: a just-switched-on table, the arm answered "out" ---------------------------------------

def test_t3_cold_table_arm_out_sends_no_movement(qtbot, monkeypatch, tmp_path, settings):
    """Only with job.START_UP_ASKS_ABOUT_THE_ARM on (4.3.52: off; the start-up is sent)."""
    monkeypatch.setattr(J, "START_UP_ASKS_ABOUT_THE_ARM", True)
    sim = WindowSim(cold=True)
    win, sim, run, p, saved, finished = _unguided(
        qtbot, monkeypatch, tmp_path, settings, sim=sim)
    assert p.page() == "start_up_arm"
    assert p.labels() == [tr("Not now"), tr("No, the arm is out over the table"),
                          tr("Yes. Start the table")] or set(p.labels()) == {
        tr("Not now"), tr("No, the arm is out over the table"),
        tr("Yes. Start the table")}
    p.press("No, the arm is out over the table")
    assert _moves(sim.sim.received) == 0
    assert p.page() == "stopped"
    assert W.reason_text("arm_out_start_up_not_recorded") in win._text.text()
    job = sim.jobs[0]
    assert job.opened_with_arm_out and job.state().sending_closed
    assert job.start_up().kind == J.Kind.REFUSED and _moves(sim.sim.received) == 0


# ---- T4: Preferences, the first page's tick and the done page share ONE key ---------------------

def test_t4_preferences_rows_are_greyed_with_their_values_and_follow_the_beta(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    s.set("i1io_support_beta", False)
    s.set(W.ASK_KEY, False)
    s.set(W.EXTRA_LOG_KEY, False)
    dlg = SettingsDialog(s)
    try:
        rows = dlg.i1io_sub_rows()
        assert len(rows) >= 9 and not dlg._i1io_support_check.isChecked()
        assert all(not w.isEnabled() for w in rows)
        assert dlg._i1io_ask_check.isChecked() is False      # the value shown, greyed
        assert dlg._i1io_log_check.isChecked() is False
        dlg._i1io_support_check.setChecked(True)
        assert all(w.isEnabled() for w in rows)
        dlg._i1io_support_check.setChecked(False)
        assert all(not w.isEnabled() for w in rows)
    finally:
        dlg.deleteLater()


def test_t4_one_key_in_every_direction(qtbot, monkeypatch, tmp_path, settings, qapp):
    from ui.dialogs.settings_dialog import SettingsDialog
    # the done page's offer writes it (False) ...
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path / "a", settings,
                                                    asking=True)
    p.script.update(GUIDED_ANSWERS)
    p.drive_until("done")
    assert win._tick_widgets and tr("From now on, run my table measurements without "
                                    "guidance") in win._tick_widgets[0].text()
    win._tick_widgets[0].setChecked(True)
    p.press("Close")
    assert W.guided(settings) is False
    # ... and Preferences shows it at its next opening, and writes it back (True)
    settings.set("i1io_support_beta", True)
    dlg = SettingsDialog(settings)
    try:
        assert dlg._i1io_ask_check.isChecked() is False
        dlg._i1io_ask_check.setChecked(True)
        dlg._save_and_close()
    finally:
        dlg.deleteLater()
    assert W.guided(settings) is True
    # the first page shows it, and its tick writes it (False) for Preferences to read
    win2, sim2, run2, p2, *_ = open_window(qtbot, monkeypatch, tmp_path / "b", settings,
                                           asking=True)
    assert p2.page() == "prepare" and win2._tick_widgets[0].isChecked()
    assert win2._tick_widgets[0].text() == tr(
        "Guided, step by step measurement (ChromIQ asks before each step)")
    win2._tick_widgets[0].setChecked(False)
    assert W.guided(settings) is False and sim2.jobs[0].guided is False
    dlg = SettingsDialog(settings)
    try:
        assert dlg._i1io_ask_check.isChecked() is False
    finally:
        dlg.deleteLater()


def test_t4_the_notice_area_says_the_guidance_is_off(qtbot, monkeypatch, tmp_path, settings):
    notices = []
    win, sim, run, p, saved, finished = _unguided(qtbot, monkeypatch, tmp_path, settings)
    win.notice.connect(notices.append)
    win._guidance_notice()
    assert tr("Guided, step by step measurement is off. You can switch it on in "
              "Preferences > Beta.") in notices
    assert "prepare" not in win.pages_shown


# ---- T5: "Keep the table's detailed log" off ----------------------------------------------------

def _session_log(run) -> str:
    logs = sorted(run.dir.rglob("*.log"))
    assert logs, list(run.dir.rglob("*"))
    return "\n".join(f.read_text(encoding="utf-8") for f in logs)


def _app_table_lines(caplog) -> "list[str]":
    import re
    out = []
    for rec in caplog.records:
        msg = rec.getMessage()
        if not msg.startswith("table") or msg.startswith("table alarm"):
            continue
        msg = re.sub(r" (open_s|stamp|folder|detailed_log|t)=\S+", "", msg)
        out.append(msg)
    return out


def test_t5_logging_off_keeps_a_move_line_and_no_wire_line(qtbot, monkeypatch, tmp_path,
                                                           settings, caplog):
    import logging
    caplog.set_level(logging.INFO, logger="chromiq.events")
    lines = {}
    for on in (True, False):
        settings.set(W.EXTRA_LOG_KEY, on)
        caplog.clear()
        win, sim, run, p, *_ = _unguided(qtbot, monkeypatch, tmp_path / str(on), settings)
        _to_done(p)
        p.press("Close")
        text = _session_log(run)
        moves = _moves(sim.sim.received)
        move_lines = [ln for ln in text.splitlines() if ln.startswith("MOVE")]
        assert len(move_lines) == moves, (len(move_lines), moves)
        sends = [ln for ln in text.splitlines() if ln.startswith(("SEND", "RECV"))]
        if on:
            assert sends
        else:
            assert sends == [] and "the detailed table log is switched off" in text
        lines[on] = _app_table_lines(caplog)
    settings.set(W.EXTRA_LOG_KEY, True)
    assert lines[True] == lines[False]


def test_t5_a_stop_keeps_the_300_lines_before_it_and_everything_after(qtbot, monkeypatch,
                                                                       tmp_path, settings):
    from workflow.i1io.table import diagnostics as dg
    settings.set(W.EXTRA_LOG_KEY, False)
    try:
        sim = WindowSim(faults={"read_loc": {"1-2": "dies"}})
        win, sim, run, p, *_ = _unguided(qtbot, monkeypatch, tmp_path, settings, sim=sim,
                                          extra={"row_failed": "Skip it",
                                                 "end_of_session": "Save and stop",
                                                 "home_at_end":
                                                     "Bring the arm home, my hands are away"})
        _to_done(p, allowed=("aimed", "row_failed", "end_of_session", "home_at_end"))
        p.press("Close")
        text = _session_log(run)
        assert dg.RING_HEADING in text
        after = text.split(dg.RING_HEADING, 1)[1]
        assert "SEND" in after and "RECV" in after
        # everything after the stop: the homing's lines are in it
        assert "SEND" in after.split("the kept lines end here", 1)[1]
    finally:
        settings.set(W.EXTRA_LOG_KEY, True)


def test_t5_a_status_keeps_the_lines_before_it(qtbot, monkeypatch, tmp_path, settings):
    """A movement answered with a status (the table part ends): the ring of the lines before
    it is written, the status's own SEND / RECV among them."""
    from workflow.i1io.table import diagnostics as dg
    settings.set(W.EXTRA_LOG_KEY, False)
    try:
        sim = WindowSim(table_faults=[("status", "m0")])
        win, sim, run, p, *_ = _unguided(qtbot, monkeypatch, tmp_path, settings, sim=sim)
        assert p.page() == "stopped"
        job = sim.jobs[0]
        assert job.diag.tripped
        text = "\n".join(job.diag.lines)
        before, after = text.split(dg.RING_HEADING, 1)
        assert "SEND" not in before and "SEND" in after and "RECV" in after
        kept = after.split("the kept lines end here", 1)[0]
        assert ";m0" in kept or "m0" in kept
    finally:
        settings.set(W.EXTRA_LOG_KEY, True)


# ---- T6: Stop during a countdown -------------------------------------------------------------

def test_t6_stop_during_the_countdown_moves_nothing(tmp_path):
    job, sim, p = _unguided_job(tmp_path)
    assert p.drive(job.open()).ok and p.drive(job.calibrate()).ok
    seen = {}

    def progress(ev):
        if ev.get("event") == "countdown" and "at" not in seen:
            seen["at"] = len(sim.received)
            job.stop_at_next_pause()
    job.on_progress = progress
    r = p.drive(job.align())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, J.STOPPED_BEFORE_THE_NEXT_MOVE), r
    assert seen and len(sim.received) == seen["at"]
    assert job.countdowns[-1]["result"] == "stopped"


# ---- T7 / T9: the wire -------------------------------------------------------------------------

CASES = {
    "warm": dict(),
    "cold": dict(cold=True),
    "failed_row": dict(faults={"read_twice": {"1-2": "dies"}}),
}


def _run(qtbot, monkeypatch, tmp_path, settings, guided_on: bool, case: str):
    kw = dict(CASES.get(case, {}))
    sheet = None
    if case == "front":
        kw.update(aims=CROSSES_1, reach_store=rc.MemoryReachStore(), **HIS_TABLE)
        sheet = H.demo_sheet()
    sim = WindowSim(**kw)
    if guided_on:
        win, sim, run, p, *_ = open_window(qtbot, monkeypatch, tmp_path, settings, asking=True,
                                           sim=sim, sheet=sheet)
        p.script.update(GUIDED_ANSWERS)
        p.drive_until("done")
    else:
        win, sim, run, p, *_ = _unguided(qtbot, monkeypatch, tmp_path, settings, sim=sim,
                                         sheet=sheet)
        _to_done(p)
    assert sim.sim.violations == [] and J.HANDS_OFF_BREACHES == []
    return list(sim.sim.received), sim.jobs[0]


@pytest.mark.parametrize("case", ["warm", "cold", "front", "failed_row"])
def test_t7_the_unguided_wire_is_the_guided_wire(qtbot, monkeypatch, tmp_path, settings, case):
    guided_lines, gj = _run(qtbot, monkeypatch, tmp_path / "g", settings, True, case)
    unguided_lines, uj = _run(qtbot, monkeypatch, tmp_path / "u", settings, False, case)
    assert gj.ended == uj.ended == "saved"
    assert unguided_lines == guided_lines, _first_difference(guided_lines, unguided_lines)
    if case == "front":
        # the careful 5 mm steps ran without the front question, after a countdown
        assert any(a["kind"] == C.FRONT_CHOICE for a in uj.auto_answers)
        assert any(c["step"] == "creep" for c in uj.countdowns)
        assert sum(1 for ln in unguided_lines if ln.startswith(";m0")) > 0
    if case == "cold":
        assert any(ln.startswith(";i0") for ln in unguided_lines)
    if case == "failed_row":
        assert uj.rows_again


def _first_difference(a, b) -> str:
    for k, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f"line {k}: guided {x!r}, unguided {y!r}; around {a[max(0, k - 3):k + 3]}"
    return f"lengths {len(a)} / {len(b)}"


def test_t9_no_countdown_at_all_changes_nothing_on_the_wire(qtbot, monkeypatch, tmp_path,
                                                            settings):
    with_cd, _j = _run(qtbot, monkeypatch, tmp_path / "a", settings, False, "warm")
    monkeypatch.setattr(J, "UNGUIDED_COUNTDOWN_S", 0)
    win, sim, run, p, *_ = _unguided(qtbot, monkeypatch, tmp_path / "b", settings)
    _to_done(p)
    assert win.countdowns_seen == [] and sim.jobs[0].countdowns
    assert J.HANDS_OFF_BREACHES == []
    assert list(sim.sim.received) == with_cd


# ---- T8: the auto-answer path refuses anything not on BY_SETTING --------------------------------

def test_t8_a_kind_not_on_the_list_ends_the_sitting_unanswered(tmp_path, monkeypatch):
    monkeypatch.setattr(J.TableJob, "AUTO_KINDS", J.TableJob.AUTO_KINDS | {C.CAL_OWN_TILE})
    job, sim, p = _unguided_job(tmp_path)
    job.calibration_place_preference = "own tile"
    assert p.drive(job.open()).ok
    n = len(sim.received)
    r = p.drive(job.calibrate())
    assert (r.kind, r.reason) == (J.Kind.STOPPED, J.AUTO_ANSWER_REFUSED), r
    assert not any(a["kind"] == C.CAL_OWN_TILE for a in job.auto_answers)
    assert job.state().sending_closed and _moves(sim.received[n:]) == 0
    assert not any("calibration_own_tile ->" in ln for ln in job.diag.lines)


def test_t8_the_window_answers_no_question_itself():
    import inspect
    src = inspect.getsource(W.TableMeasureWindow._ask)
    assert "self.answer(calibration_place" not in src


# ---- T10: the switch-off alarm ------------------------------------------------------------------

def test_t10_the_alarm_opens_with_the_page_repeats_and_stops(qtbot, monkeypatch, tmp_path,
                                                             settings):
    """4.3.53: made independent of the machine's load. Until then it let a real 40 ms timer
    run for 300 ms and asked for at least three plays, which a loaded machine (the gate on
    every core) does not always give. Now the repeat timer never fires by itself (an interval
    of 1000 s), the window's clock is a fake one, and each repeat is the timer's own slot
    called at a chosen time: the same code, the same rule (repeat while the page is open, stop
    at ALARM_FOR_MS), no wall-clock race."""
    import core.sound as snd
    assert hasattr(snd, W.ALARM_SOUND)                                   # W-4
    monkeypatch.setattr(W, "ALARM_REPEAT_MS", 1_000_000)
    monkeypatch.setattr(W, "ALARM_FOR_MS", 300)
    sim = WindowSim(table_faults=[("no_answer", "m0")])
    win, sim, run, p, *_ = _unguided(qtbot, monkeypatch, tmp_path, settings, sim=sim)
    heard = []
    win.alarm.connect(lambda name, ignore: heard.append((name, ignore)))
    page = p.page()
    assert sim.jobs[0].way_back() in W.SWITCH_OFF_WAYS, (page, sim.jobs[0].way_back())
    assert win.alarm_plays >= 1                                          # as the page opened
    assert win._alarm_timer.isActive()
    n0 = win.alarm_plays
    t0 = win._alarm_t0
    # the fake clock only from here (the job's own waits ran on the real one)
    now = [t0]
    monkeypatch.setattr(W.time, "monotonic", lambda: now[0])
    for k, dt in enumerate((0.1, 0.2), 1):                              # repeated while open
        now[0] = t0 + dt
        win._alarm_tick()
        assert win.alarm_plays == n0 + k and win._alarm_timer.isActive()
    now[0] = t0 + 0.31                                                   # ALARM_FOR_MS reached
    win._alarm_tick()
    assert not win._alarm_timer.isActive()
    n = win.alarm_plays
    assert n >= 3                                                        # repeated, then over
    now[0] = t0 + 0.5
    win._alarm_tick()                                                    # a late tick: silent
    assert win.alarm_plays == n
    assert all(h == (W.ALARM_SOUND, W.ALARM_IGNORES_SOUND_SETTING) for h in heard)


def test_t10_a_button_stops_the_alarm(qtbot, monkeypatch, tmp_path, settings):
    monkeypatch.setattr(W, "ALARM_REPEAT_MS", 40)
    monkeypatch.setattr(W, "ALARM_FOR_MS", 5000)
    sim = WindowSim(table_faults=[("no_answer", "m0")])
    win, sim, run, p, *_ = _unguided(qtbot, monkeypatch, tmp_path, settings, sim=sim)
    p.page()
    assert win._alarm_timer.isActive()
    win._buttons[0].click()
    assert not win._alarm_timer.isActive()
    n = win.alarm_plays
    qtbot.wait(150)
    assert win.alarm_plays == n


def test_t10_a_page_that_is_not_shown_plays_nothing(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, *_ = _unguided(qtbot, monkeypatch, tmp_path, settings)
    p.page()
    win._hide_popup()
    win.alarm_for_switch_off()                                           # W-2
    assert win.alarm_plays == 0


@pytest.mark.parametrize("ignore", [False, True])
def test_t10_sounds_off_the_alarm_follows_the_one_constant(qapp, ignore):
    import core.sound as snd
    from core.settings import AppSettings
    s = AppSettings()
    was = s.get("sound_enabled", False)
    s.set("sound_enabled", False)
    try:
        out = snd.SoundManager(s).play_alarm(snd.INSTRUMENT_ERROR, ignore)
    finally:
        s.set("sound_enabled", was)
    if ignore:
        assert out in ("played", "no_audio"), out
    else:
        assert out == "sounds_off"


def test_t10_the_default_respects_the_sound_setting():
    """measurement_window_sounds.md W-3 (play_window is the window sound without the reading
    gate only; the master switch and a sound set to Off still hold): the default keeps it."""
    assert W.ALARM_IGNORES_SOUND_SETTING is False


# ---- T11 / T12: consent page version 4 -----------------------------------------------------------

@pytest.mark.parametrize("stored,shown", [(3, True), (4, False)])
def test_t11_consent_v4_is_shown_once_more(qtbot, monkeypatch, tmp_path, settings, stored,
                                           shown):
    win, sim, run, p, *_ = open_window(qtbot, monkeypatch, tmp_path, settings, guided=False,
                                       consent=False)
    # (open_window with consent=False stored nothing; the window asks now. Give it *stored*.)
    settings.set(W.CONSENT_KEY, stored)
    win2 = W.TableMeasureWindow(None, settings, small_sheet(), run, ["-v"])
    qtbot.addWidget(win2)
    win2.start()
    assert (win2.pages_shown[:1] == ["consent"]) is shown
    if shown:
        from workflow import measurement_messages as M
        add = M.M_I1IO_DRIVE_CONSENT_GUIDANCE.render(
            mac="", countdown="", alarm="")[1].split("\n\n")[0][:40]
        assert add.split(".")[0] in win2._text.text()


def test_t12_reader_consent_is_asked_without_consent_v4(tmp_path, asked):
    job, sim, p = _unguided_job(tmp_path)
    job.consent_version = 3
    assert p.drive(job.open()).ok
    r = job.calibrate()
    assert r.confirm == C.READER_CONSENT and not any(
        a["kind"] == C.READER_CONSENT for a in job.auto_answers)
    job4, sim4, p4 = _unguided_job(tmp_path / "v4")
    assert p4.drive(job4.open()).ok and p4.drive(job4.calibrate()).ok
    assert any(a["kind"] == C.READER_CONSENT for a in job4.auto_answers)
