"""4.3.51, THE OWNER'S DECISION of 2026-11-20 (Basti: "let chromiq offer to try it and if it does
not work it suggests i1profiler. but the i1io 2 is not supported by the most recent i1profiler
anymore so we should not rely on it").

At a START, a held arm on a started table (aiming mode off) found over the measuring area or the
front zone (4.3.47's homing region, where 4.3.50 offered its homing after "The arm is out") is
offered a TRY, on every path (the white's rest check, "The arm is out", -N), with exactly the
lines 4.3.50 sent from there (4.3.48's homing after a stop: s0 p0 i1 s0 f0 f4 f4 p0), after the
hands-off GO, and the reading at the end must find the arm at rest. When it does not work: ONE
page, the power switch first, i1Profiler only as a further option with its version limit.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table.test_4351_one_start_rule import F2, MOVES, _found
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl

#: 4.3.50's homing lines from these places at a START (the review's wire_tree_450.json:
#: start_bed_*, start_front_0_3000, start_line1000, start_line600_x40mm), frozen
WIRE_450 = [";s022", ";p025", ";i12b", ";s022", ";f02f", ";f42b", ";f42b", ";p025"]

#: places where the try is offered (none on the home line up to 815, none in 4.3.48's envelope)
TRY = [(1102, 900), (1102, 1150), (800, 800), (1502, 600), (1300, 1600), (1700, 2000),
       (0, 2700), (0, 3000), (0, 3110), (-1000, 1201), (0, 600), (1180, 1600), (-1434, 2700),
       (1766, 480)]
#: places that stay refused: the back strip beside the line, the alignment start, beyond the
#: raw box's right edge (the recorded starts at X -1437, -1438), in front of the held cap
STILL_REFUSED = [(1058, 317), (2507, 1429), (-1437, 1794), (0, 3120), (1767, 1000),
                 (500, 460)]


def test_the_frozen_wire_is_4_3_50s():
    assert F2 == WIRE_450


@pytest.mark.parametrize("pos", TRY)
def test_the_rule_names_a_try(pos):
    assert J.start_homing_form(pos) == "try"
    assert J.start_place(pos) == "over_the_table_a_try"


@pytest.mark.parametrize("pos", STILL_REFUSED)
def test_the_rule_still_refuses(pos):
    assert J.start_homing_form(pos) is None


TRY_CASES = [(path, pos) for pos in TRY for path in ("cal", "out", "N")]


@pytest.mark.parametrize("path,pos", TRY_CASES, ids=[f"{p[1]}-{p[0]}" for p in TRY_CASES])
def test_the_try_is_offered_on_every_path_and_sends_4_3_50s_lines(tmp_path, path, pos):
    job, sim, p, r = _found(tmp_path, path, pos)
    assert not [ln for ln in sim.received if ln[1:3] in MOVES]
    assert r.way_back == J.WayBack.HOME_AFTER_STOP, (pos, path, r.reason)
    assert job.start_case["offered"] == "homing_at_start" and job.start_case["form"] == "try"
    asked = len(p.asked)
    n = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert res.ok, (res.kind, res.reason, res.detail)
    assert [a[1] for a in p.asked[asked:]] == [J.Confirm.GO]       # hands off first
    assert sim.received[n:] == WIRE_450
    assert tbl.REST_GUARD.contains(job._table.position_now)
    assert sim.violations == []
    assert job.home_after_stop().kind == J.Kind.REFUSED              # once per sitting
    if path != "N":
        assert res.detail.get("goes_on") is True
        for s in ("calibrate", "align"):
            assert p.drive(H.step(job, s)).ok, s


@pytest.mark.parametrize("pos", STILL_REFUSED)
def test_nothing_is_offered_where_it_stays_refused(tmp_path, pos):
    job, sim, p, r = _found(tmp_path, "out", pos)
    assert r.way_back == J.WayBack.OPEN_I1PROFILER_ONCE
    n = len(sim.received)
    assert job.home_after_stop().kind == J.Kind.REFUSED and sim.received[n:] == []


@pytest.mark.parametrize("state", ["free", "mode_on"])
def test_a_free_arm_or_the_aiming_mode_gets_no_try(tmp_path, state):
    from tests.i1io_table.test_job_reading import job_for
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


def test_the_region_is_checked_again_right_before_i1(tmp_path):
    """Found at the raw box's edge (1766, 1000), read at (1769, 1000) right before i1: within the
    5-unit "arm moved" compare, outside the region. Nothing moves."""
    job, sim, p, r = _found(tmp_path, "cal", (1766, 1000))
    assert r.way_back == J.WayBack.HOME_AFTER_STOP
    sim.pos = [1769.0, 1000.0]
    n = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert not res.ok and ";i12b" not in sim.received[n:]


# ---- when it does not work: each failure mode ---------------------------------------------------
FAILURES = [("status", "i1", 0.0), ("short_homing", "i1", 0.0), ("moved", None, 0.0)]


def _fail(sim, kind, cid, value):
    if kind == "moved":
        sim.pos = [sim.pos[0] + 40.0, sim.pos[1]]
    else:
        sim.inject(kind, cid, value)


@pytest.mark.parametrize("kind,cid,value", FAILURES, ids=[f[0] for f in FAILURES])
@pytest.mark.parametrize("pos", [(800, 800), (0, 3000)])
def test_a_try_that_does_not_work_sends_nothing_more(tmp_path, kind, cid, value, pos):
    job, sim, p, r = _found(tmp_path, "cal", pos)
    _fail(sim, kind, cid, value)
    n = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert not res.ok, (res.kind, res.reason)
    sent = sim.received[n:]
    assert sent == WIRE_450[:len(sent)], sent                     # nothing but 4.3.50's lines
    assert sent.count(";i12b") <= 1
    assert job.way_back() == J.WayBack.OPEN_I1PROFILER_ONCE
    m = len(sim.received)
    assert job.home_after_stop().kind == J.Kind.REFUSED and job.home().kind == J.Kind.REFUSED
    for s in ("calibrate", "align"):
        p.drive(H.step(job, s))
    assert not [ln for ln in sim.received[m:] if ln[1:3] in MOVES]


# ---- the window ----------------------------------------------------------------------------------
def _window_at(qtbot, monkeypatch, tmp_path, settings, pos):  # noqa: F811
    from tests.i1io_table.window_sim import WindowSim
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, sim=WindowSim(pos=[float(pos[0]), float(pos[1])]),
        asking=False)
    assert p.drive_until("ready_to_open") == "ready_to_open"
    win._tick_widgets[1].setChecked(True)
    p.press("The arm is out")
    return win, sim, p


def test_the_window_offers_a_try_and_says_it_is_one(qtbot, monkeypatch, tmp_path,
                                                    settings):  # noqa: F811
    win, sim, p = _window_at(qtbot, monkeypatch, tmp_path, settings, (800, 800))
    assert p.page() == "refused"
    assert p.labels() == ["Bring the arm home", "End measurement"]
    text = win._text.text()
    assert "This is a try: ChromIQ has no recording" in text and "power switch" in text
    assert "i1Profiler" not in text
    n = len(sim.sim.received)
    p.press("Bring the arm home")
    p.press("Go")
    p.idle()
    assert sim.sim.received[n:] == WIRE_450
    assert p.page() == "home_after_stop_done" and p.labels() == ["Go on"]
    p.press("Go on")
    p.idle()
    assert p.page() not in ("refused", "stopped"), win.pages_shown[-3:]
    assert sim.sim.violations == []


@pytest.mark.parametrize("kind,cid,value", FAILURES[:2], ids=[f[0] for f in FAILURES[:2]])
def test_the_window_shows_one_page_when_it_does_not_work(qtbot, monkeypatch, tmp_path, settings,
                                                         kind, cid, value):  # noqa: F811
    win, sim, p = _window_at(qtbot, monkeypatch, tmp_path, settings, (0, 3000))
    _fail(sim.sim, kind, cid, value)
    p.press("Bring the arm home")
    p.press("Go")
    p.idle()
    assert p.page() == "stopped", win.pages_shown[-3:]
    assert win._title.text() == "The arm did not get home"
    text = win._text.text()
    assert "ChromIQ could not bring the arm home" in text
    sw, i1p = text.index("Switch the table off at its power switch"), text.index("i1Profiler 3.8.6")
    assert sw < i1p                                   # the power switch first
    assert "i1Profiler 3.8.7 and newer no longer work with the i1iO 2" in text
    assert text.count("3.8.7") == 1                   # the limit paragraph is not added twice
    assert "—" not in text
    assert p.labels() == ["End measurement"]


def test_every_page_naming_i1profiler_says_its_limit(qtbot, monkeypatch, tmp_path,
                                                     settings):  # noqa: F811
    """The alignment start: nothing offered; the page names i1Profiler 3.8.6 and now says that
    3.8.7 and newer no longer work with the i1iO 2."""
    win, sim, p = _window_at(qtbot, monkeypatch, tmp_path, settings, (2507, 1429))
    assert p.page() == "refused" and p.labels() == ["End measurement"]
    text = win._text.text()
    assert "3.8.6" in text and "3.8.7 and newer no longer work with the i1iO 2" in text
    assert text.index("Switch the table off at its power switch") < text.index("i1Profiler 3.8.6")
