"""4.3.52: THE START RULE WITH THE GUIDANCE OFF, AS A POLICY (replaces
test_4352_start_rule_stays_asked_unguided.py).

Before this round, 4.3.51's START offers stayed questions with the guidance off, and an arm found
away from rest turned the rest of the sitting guided (35+ questions on screen). The owner's ruling
of 2026-11-20 makes the homing at a START the table's normal job, as i1Profiler does it, so:

* the START rule's homing INSIDE the step that found the arm (GO, step "home_at_start") is a
  countdown with the guidance off, never answered by the setting and never a question;
* an arm found away from rest is not a fault: the sitting stays unguided;
* the homing offered on a PAGE (home_after_stop: after "Not now", after a stop, after the
  ending) stays a question in both modes (the person chose to wait; that is a decision);
* a homing that FAILS is a fault: the rest of the sitting is guided.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import small_sheet
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (the fixture)
from ui import i1io_table_window as W
from workflow.i1io.table import job as J


@pytest.fixture(autouse=True)
def _no_breach():
    J.HANDS_OFF_BREACHES.clear()
    yield
    J.HANDS_OFF_BREACHES.clear()


def _unguided_job(tmp_path):
    sheet = small_sheet()
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet,
                                                aims=H.demo_aims(sheet), real_table=False)
    job.guided = False
    job.consent_version = W.CONSENT_VERSION
    job.calibration_place_preference = "table tile"
    return job, sim, H.Person(job, sim, {})


def test_the_policy_for_each_homing_question(tmp_path):
    job, sim, p = _unguided_job(tmp_path)
    assert job._without_the_person(J.Ask(J.Confirm.GO, {"step": "home_at_start",
                                                         "at_start": True})) == "countdown"
    assert job._without_the_person(J.Ask(J.Confirm.GO, {"step": "home_after_stop",
                                                         "at_start": True})) is None
    assert job._without_the_person(J.Ask(J.Confirm.START_UP, {})) == "countdown"
    assert J.Confirm.GO not in J.BY_SETTING and J.Confirm.START_UP not in J.BY_SETTING
    job.guided = True
    assert job._without_the_person(J.Ask(J.Confirm.GO, {"step": "home_at_start"})) is None


def test_the_constant_puts_the_start_up_question_back(tmp_path, monkeypatch):
    job, sim, p = _unguided_job(tmp_path)
    monkeypatch.setattr(J, "START_UP_ASKS_ABOUT_THE_ARM", True)
    assert job._without_the_person(J.Ask(J.Confirm.START_UP, {})) is None


def test_the_offer_on_a_page_stays_a_question_with_the_guidance_off(tmp_path):
    """The person stopped the countdown (Stop): the rest is guided; the page offers the homing,
    and its GO is asked."""
    job, sim, p = _unguided_job(tmp_path)
    sim.pos = [800.0, 800.0]
    assert p.drive(job.open()).ok

    def stop_in_countdown(ev):
        if ev.get("event") == "countdown" and ev.get("for_step") == "home_at_start":
            job.stop_at_next_pause()
    job.on_progress = stop_in_countdown
    n = len(sim.received)
    r = p.drive(job.calibrate())
    job.on_progress = None
    assert r.reason == J.STOPPED_BEFORE_THE_NEXT_MOVE, (r.kind, r.reason)
    assert sim.received[n:] == [";p025"], "nothing moved"
    assert job.guided_now
    assert job.way_back() == J.WayBack.HOME_AFTER_STOP
    asked = len(p.asked)
    res = p.drive(job.home_after_stop())
    assert res.ok
    assert [a[1] for a in p.asked[asked:]] == [J.Confirm.GO]


def test_a_failed_homing_turns_the_rest_of_the_sitting_guided(tmp_path):
    job, sim, p = _unguided_job(tmp_path)
    sim.pos = [800.0, 800.0]
    assert p.drive(job.open()).ok
    sim.inject("short_homing", "i1")
    r = p.drive(job.calibrate())
    assert not r.ok and job.start_homing_failed
    assert job.guided_now and str(job.turned_guided).startswith("fault:")


# ---- the branch's own page, with the constant on ----------------------------------------------
@pytest.mark.parametrize("code", ["en", "de"])
def test_the_start_up_arm_page_says_the_i1profiler_limit_once(qtbot, monkeypatch, tmp_path,
                                                              settings, code):  # noqa: F811
    """M-I1IO-DRIVE-START-UP-ARM (kept behind job.START_UP_ASKS_ABOUT_THE_ARM) sends the person
    to "i1Profiler 3.8.6 or older" as M-I1IO-DRIVE-START-UP does, so it carries 4.3.51's flag
    and the page shows the limit notice once."""
    from core import i18n
    from tests.i1io_table.test_4352_guidance_off import _unguided
    from tests.i1io_table.window_sim import WindowSim
    from workflow import measurement_messages as M
    monkeypatch.setattr(J, "START_UP_ASKS_ABOUT_THE_ARM", True)
    # 2026-11-21: the page no longer names i1Profiler ("Not now" instead), so no notice
    assert not M.M_I1IO_DRIVE_START_UP_ARM.needs_old_i1profiler
    i18n.set_language(code)
    try:
        win, sim, run, p, saved, finished = _unguided(qtbot, monkeypatch, tmp_path, settings,
                                                      sim=WindowSim(cold=True))
        assert p.page() == "start_up_arm"
        notice = M.M_I1IO_DRIVE_I1PROFILER_LIMIT.render()[1]
        assert win._text.text().count(notice) == 0 and "i1Profiler 3.8" not in win._text.text()
    finally:
        i18n.set_language("en")


def test_without_the_constant_a_just_switched_on_table_asks_nothing(qtbot, monkeypatch, tmp_path,
                                                                    settings):  # noqa: F811
    from tests.i1io_table.test_4352_guidance_off import _to_done, _unguided
    from tests.i1io_table.window_sim import WindowSim
    win, sim, run, p, saved, finished = _unguided(qtbot, monkeypatch, tmp_path, settings,
                                                  sim=WindowSim(cold=True))
    shown = _to_done(p)
    assert shown == ["aimed"] * 3, shown
    assert "start_up_arm" not in win.pages_shown
    job = sim.jobs[0]
    assert job.ended == "saved" and job.at_rest() and job.turned_guided is None
    assert ";i02c" in sim.sim.received
