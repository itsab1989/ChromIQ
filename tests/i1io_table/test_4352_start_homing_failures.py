"""4.3.52: WHEN THE START HOMING DOES NOT WORK (replaces test_4351_owner_try.py).

4.3.51 offered a "try" over the measuring area and the front (the owner's decision of
2026-11-20: "let chromiq offer to try it and if it does not work it suggests i1profiler. but the
i1io 2 is not supported by the most recent i1profiler anymore so we should not rely on it"). Since
4.3.52 there is no try: the table's own homing is sent from wherever a held arm stands
(test_4352_start_rule_by_state.py). What the owner's decision still governs is the second half:
when it does not work, ONE page, the power switch first, i1Profiler only last, with its version
limit; and nothing more is sent.

Every failure mode, from places 4.3.51 called a try and from places it refused outright.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table.test_4352_start_rule_by_state import F1_PLUS, MOVES
from tests.i1io_table.test_job_reading import job_for
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from workflow.i1io.table import job as J

#: (kind, cid, value): a status on i1, a homing that reports done and stops short, the held arm
#: moved by hand while the question was shown, a refused line, no done answer
FAILURES = [("status", "i1", 0.0), ("short_homing", "i1", 0.0), ("moved", None, 0.0),
            ("refuse", "i1", 0.0)]
PLACES = [(800, 800), (0, 3000), (0, 3300), (2507, 1429)]


def _found(tmp_path, pos, kind, cid, value):
    def on_ask(person, res):
        if res.confirm == J.Confirm.GO and res.detail.get("step") == "home_at_start" \
                and kind == "moved":
            person.sim.pos = [person.sim.pos[0] + 40.0, person.sim.pos[1]]
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    p.on_ask = on_ask
    sim.pos = [float(pos[0]), float(pos[1])]
    assert p.drive(job.open()).ok
    if kind != "moved":
        sim.inject(kind, cid, value)
    return job, sim, p


@pytest.mark.parametrize("kind,cid,value", FAILURES, ids=[f[0] for f in FAILURES])
@pytest.mark.parametrize("pos", PLACES)
def test_a_homing_that_does_not_work_sends_nothing_more(tmp_path, kind, cid, value, pos):
    job, sim, p = _found(tmp_path, pos, kind, cid, value)
    n = len(sim.received)
    res = p.drive(job.calibrate())
    assert not res.ok, (res.kind, res.reason)
    sent = sim.received[n + 1:]                       # after the reading that found it
    # nothing but the recorded lines (2026-11-21: from the far side N3's detour first)
    want = F1_PLUS if pos[0] <= 1281 else [";s022", ";p025", ";m0044e05da00c806", ";p025",
                                           ";i12b", ";s022", ";p025"]
    assert sent == want[:len(sent)], sent
    assert sent.count(";i12b") <= 1
    assert job.start_homing_failed
    assert job.way_back() in (J.WayBack.END_THEN_START_AGAIN, J.WayBack.SWITCH_OFF_UNFINISHED)
    m = len(sim.received)
    assert job.home_after_stop().kind == J.Kind.REFUSED and job.home().kind == J.Kind.REFUSED
    for s in ("calibrate", "align"):
        p.drive(H.step(job, s))
    assert not [ln for ln in sim.received[m:] if ln[1:3] in MOVES]


@pytest.mark.parametrize("state", ["free", "mode_on"])
def test_a_free_arm_or_the_aiming_mode_gets_no_homing(tmp_path, state):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.READY_TO_OPEN: "arm out"},
                                       real_table=False)
    sim.pos = [800.0, 800.0]
    if state == "free":
        sim.mode, sim.free_arm = "01", True
    else:
        sim.mode = "01"
    p.drive(job.open())
    assert job.home_after_stop().kind == J.Kind.REFUSED
    assert not [ln for ln in sim.received if ln[1:3] in MOVES]


# ---- the window ----------------------------------------------------------------------------------
def _window_at(qtbot, monkeypatch, tmp_path, settings, pos, faults=()):  # noqa: F811
    from tests.i1io_table.window_sim import WindowSim
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings,
        sim=WindowSim(pos=[float(pos[0]), float(pos[1])], table_faults=list(faults)),
        asking=False)
    assert p.drive_until("ready_to_open") == "ready_to_open"
    win._tick_widgets[1].setChecked(True)
    p.press("The arm is out")
    return win, sim, p


@pytest.mark.parametrize("kind", ["status", "short_homing"])
def test_the_window_shows_one_page_when_it_does_not_work(qtbot, monkeypatch, tmp_path, settings,
                                                         kind):  # noqa: F811
    win, sim, p = _window_at(qtbot, monkeypatch, tmp_path, settings, (0, 3000),
                             faults=[(kind, "i1")])
    assert p.page() == "home_at_start"
    p.press("Bring the arm home, my hands are away")
    p.idle()
    assert p.page() == "stopped", win.pages_shown[-3:]
    assert win._title.text() == "The arm did not get home"
    text = win._text.text()
    assert "ChromIQ could not bring the arm home" in text
    if kind == "status":
        assert "error code instead of reporting it finished" in text
    # 2026-11-21 (the owner: "driving the table should work without involving i1profiler"):
    # START MEASUREMENT, then the power switch; never i1Profiler
    assert "START MEASUREMENT" in text and "switch it off at its power switch" in text
    assert "i1Profiler" not in text
    assert "—" not in text
    assert p.labels() == ["End measurement"]


def test_the_back_strip_page_says_the_power_switch_first_and_the_limit(qtbot, monkeypatch,
                                                                       tmp_path,
                                                                       settings):  # noqa: F811
    """2026-11-21: the one place nothing is offered is a back-strip place beyond the left end of
    the target area (the back strip itself has i1Profiler's own way out); its page names the
    power switch and START, never i1Profiler."""
    from tests.i1io_table import job_harness as _H
    _H.plant_no_way_home(monkeypatch)       # fix round: no such place is left
    win, sim, p = _window_at(qtbot, monkeypatch, tmp_path, settings, (2600, 300))
    assert p.page() == "refused" and p.labels() == ["End measurement"]
    text = win._text.text()
    assert "i1Profiler" not in text and "power switch" in text and "START MEASUREMENT" in text
    assert not [ln for ln in sim.sim.received if ln[1:3] in MOVES]
