"""4.3.51: ONE rule at a START for an arm that is not at its resting place.

The owner's start-up capture of 19 Nov 2026 (PRIVATE analysis in the work folder, decoded line by
line): i1Profiler opened a STARTED table (a0 130000, f4 00 four times) twice. With the arm at rest
it sent its homing s0 p0 i1 s0 at once (0.352 s). With the arm pushed 76 mm out by hand along its
home line, to (1098, 810), it sent the SAME four lines at once: i1 took 1.312 s, status 0, and
s0 answered 0. No f0 (the aiming mode was off).

At v4.3.50 the same arm at the same place was offered ChromIQ's homing or not depending on which
answer the person gave at START and on whether a white was due first (start_cases.txt in the work
folder). Now the table's state and the arm's measured place decide, whichever step reads it first:

* at rest: the measurement goes on as before;
* on the home line up to the recorded Y 810 (plus the arrival tolerance): offered, GO, then the
  recorded s0 p0 i1 s0, then one reading at rest (F1+);
* where i1Profiler's recorded homings of a held arm start (HOME_AFTER_STOP_AREA): offered, GO,
  then 4.3.48's lines, unchanged (F2);
* anywhere else (in front of Y 815 off that envelope, the back strip off the line, the front
  zone, the alignment start): nothing is sent; the page says why.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table.test_job_reading import job_for
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl

F1_PLUS = [";s022", ";p025", ";i12b", ";s022", ";p025"]
F2 = [";s022", ";p025", ";i12b", ";s022", ";f02f", ";f42b", ";f42b", ";p025"]
MOVES = ("m0", "m1", "m2", "i1", "i0")

#: (name, place, the form offered or None)
PLACES = [
    ("C3 near rest on the home line", (1102, 150), "start"),
    ("C3 beside the home line", (1092, 200), "start"),
    ("C4 home line 40 mm out", (1100, 400), "start"),
    ("C5 the recorded place", (1098, 810), "start"),
    ("C5 recorded plus the tolerance", (1102, 815), "start"),
    ("C6 home line beyond the record", (1102, 900), None),
    ("C6 home line just short of 1202", (1102, 1150), None),
    ("C7 back strip off the line", (1058, 317), None),
    ("C8 where recorded homings start", (0, 1600), "end_of_job"),
    ("C8 next to the recorded at-open place", (1102, 1210), "end_of_job"),
    ("C9 off the line, in front of rest", (800, 800), None),
    ("C9 left of the envelope", (1300, 1600), None),
    ("C9 in front of the envelope", (0, 2700), None),
    ("C10 the front zone", (0, 3000), None),
    ("C11 the alignment start", (2507, 1429), None),
]
IDS = [p[0] for p in PLACES]


def _found(tmp_path, path, pos):
    """START on a started table with the arm held at *pos*; the first reading by *path*:
    "cal" (yes, a white due), "out" (the person said the arm is out), "N" (yes, -N)."""
    script = {J.Confirm.READY_TO_OPEN: "arm out"} if path == "out" else None
    job, sim, helper, run, p = job_for(tmp_path, script, real_table=False)
    if path == "N":
        assert job.set_options(["-N"]).ok
    sim.pos = [float(pos[0]), float(pos[1])]
    r = p.drive(job.open())
    assert r.ok and r.detail["table"] == "warm"
    assert len(sim.received) == 11
    if path == "cal":
        r = p.drive(job.calibrate())
    elif path == "out":
        r = p.drive(job.where_is_the_arm())
    else:
        r = p.drive(job.align())
    return job, sim, p, r


#: every place by every path; with -N an arm in START_GUARD is homed by the alignment's own
#: homing (0.3.1, unchanged: test_the_alignments_own_homing_near_rest_is_unchanged)
CASES = [(path, *pl) for pl in PLACES for path in ("cal", "out", "N")
         if not (path == "N" and tbl.START_GUARD.contains(pl[1]))]


@pytest.mark.parametrize("path,name,pos,form", CASES,
                         ids=[f"{c[1]}-{c[0]}" for c in CASES])
def test_the_place_decides_not_the_answer(tmp_path, path, name, pos, form):
    job, sim, p, r = _found(tmp_path, path, pos)
    assert not [ln for ln in sim.received if ln[1:3] in MOVES], "nothing moved before asking"
    want = J.WayBack.HOME_AFTER_STOP if form else J.WayBack.OPEN_I1PROFILER_ONCE
    assert r.way_back == want, (name, path, r.reason, r.way_back)
    assert job.way_back() == want
    # the usual homing is never what a START offers
    n = len(sim.received)
    assert job.home().kind == J.Kind.REFUSED and sim.received[n:] == []
    if form is None:
        res = job.home_after_stop()
        assert res.kind == J.Kind.REFUSED and res.reason == "homing_not_from_here"
        assert sim.received[n:] == []
        return
    asked = len(p.asked)
    res = p.drive(job.home_after_stop())
    assert res.ok, (res.kind, res.reason, res.detail)
    assert [a[1] for a in p.asked[asked:]] == [J.Confirm.GO]       # hands off first
    assert sim.received[n:] == (F1_PLUS if form == "start" else F2)
    assert tbl.REST_GUARD.contains(job._table.position_now)
    assert sim.violations == []
    if path == "N":
        # its sending had been stopped by the alignment's own check: it ends after the homing
        assert job._table.closed_reason is not None
        assert res.detail.get("goes_on") is False
    else:
        assert res.detail.get("goes_on") is True and job._table.closed_reason is None
        # and the measurement goes on as usual
        for s in ("calibrate", "align"):
            assert p.drive(H.step(job, s)).ok, s
        assert sim.violations == []


@pytest.mark.parametrize("pos", [(1100, 400), (1098, 810)])
def test_the_recorded_form_from_the_home_line_has_no_f0(tmp_path, pos):
    """The capture: s0 p0 i1 s0 and no f0 (f0 only after a homing of a table in its aiming mode,
    or when i1Profiler quits)."""
    job, sim, p, r = _found(tmp_path, "cal", pos)
    n = len(sim.received)
    assert p.drive(job.home_after_stop()).ok
    assert ";f02f" not in sim.received[n:]
    assert sim.received[n:n + 4] == [";s022", ";p025", ";i12b", ";s022"]


def test_back_at_the_go_sends_nothing_and_the_offer_stays(tmp_path):
    job, sim, p, r = _found(tmp_path, "cal", (1098, 810))
    p.script[J.Confirm.GO] = "back"
    n = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert res.kind == J.Kind.REFUSED and res.reason == "person_chose_back"
    assert sim.received[n:] == []
    assert job.way_back() == J.WayBack.HOME_AFTER_STOP


def test_an_arm_moved_while_the_page_was_shown_is_not_homed(tmp_path):
    job, sim, p, r = _found(tmp_path, "cal", (1098, 810))
    sim.pos = [1098.0, 700.0]                  # a hand on it (mode off: it moves by hand)
    n = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert res.kind == J.Kind.STOPPED and res.reason == "arm_moved_before_homing"
    assert sim.received[n:] == [";s022", ";p025"]
    assert job.way_back() == J.WayBack.OPEN_I1PROFILER_ONCE


def test_once_per_sitting(tmp_path):
    job, sim, p, r = _found(tmp_path, "cal", (1098, 810))
    sim.inject("slow_motion", "i1")
    n = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert res.kind in (J.Kind.REFUSED, J.Kind.STOPPED)
    assert sim.received[n:n + 3] == [";s022", ";p025", ";i12b"]
    assert job.home_after_stop().kind == J.Kind.REFUSED


def test_a_homing_much_faster_than_recorded_is_not_taken_as_done(tmp_path):
    job, sim, p, r = _found(tmp_path, "cal", (1098, 810))
    sim.inject("fast_motion", "i1")
    res = p.drive(job.home_after_stop())
    assert not res.ok
    assert res.reason in ("homing_late_but_at_rest", "movement_outside_time_window",
                          "arm_not_where_expected")


@pytest.mark.parametrize("path", ["cal", "out"])
def test_near_rest_uses_the_short_window(tmp_path, path):
    """C3 at v4.3.50: the usual homing's window (0.8-8.0 s) from Y 150 called a 0.74 s homing
    late. Now the window of the homing from near rest (START_GUARD: 0-2.0 s)."""
    job, sim, p, r = _found(tmp_path, path, (1102, 150))
    res = p.drive(job.home_after_stop())
    assert res.ok, (res.reason, res.detail)


def test_the_alignments_own_homing_near_rest_is_unchanged(tmp_path):
    """-N, the arm on the home line within START_GUARD: the alignment's homing (HOME_FIRST, after
    the sheet question that is its hands-off confirmation) runs as in 4.3.50."""
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    assert job.set_options(["-N"]).ok
    sim.pos = [1102.0, 150.0]
    assert p.drive(job.open()).ok
    n = len(sim.received)
    r = p.drive(job.align())
    assert r.ok, (r.kind, r.reason)
    assert sim.received[n:n + 4] == [";s022", ";p025", ";i12b", ";s022"]
    assert job.start_case["where"] == "near_rest_on_the_home_line"
    assert job.start_case["by"] == "the_alignments_own_homing"


# ---- the table states where nothing that moves is sent ------------------------------------------
@pytest.mark.parametrize("answer", ["yes", "arm out"])
def test_aiming_mode_still_on_is_refused_whatever_the_answer(tmp_path, answer):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.READY_TO_OPEN: answer},
                                       real_table=False)
    sim.pos, sim.mode, sim.free_arm = [1098.0, 810.0], "01", True
    r = p.drive(job.open())
    assert r.kind == J.Kind.STOPPED and r.reason == "mode_flag_unexpected"
    assert job.home_after_stop().kind == J.Kind.REFUSED
    assert not [ln for ln in sim.received if ln[1:3] in MOVES]
    assert ";p025" not in sim.received


@pytest.mark.parametrize("answer", ["yes", "arm out"])
def test_an_unknown_status_answer_is_refused_whatever_the_answer(tmp_path, answer):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.READY_TO_OPEN: answer},
                                       real_table=False)
    sim.pos = [1098.0, 810.0]
    sim.inject("a0_after_hand", "a0")
    r = p.drive(job.open())
    assert r.kind == J.Kind.STOPPED and r.reason == "table_state_unknown"
    assert job.home_after_stop().kind == J.Kind.REFUSED
    assert len(sim.received) == 6


def test_a_just_switched_on_table_with_the_arm_out_is_not_started(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.READY_TO_OPEN: "arm out"},
                                       real_table=False, cold=True)
    sim.pos = [1098.0, 810.0]
    r = p.drive(job.open())
    assert r.ok and r.detail["table"] == "cold"
    assert job.start_up().reason == "arm_out_start_up_not_recorded"
    assert job.home_after_stop().kind == J.Kind.REFUSED
    assert len(sim.received) == 6


# ---- what the job records about the START (the session log and the app log read it) ---------
@pytest.mark.parametrize("path", ["cal", "out", "N"])
def test_the_start_case_is_recorded(tmp_path, path):
    job, sim, p, r = _found(tmp_path, path, (1098, 810))
    case = job.start_case
    assert case["table"] == "warm" and J._near(case["place"], (1098, 810), 1)
    assert case["where"] == "out_along_the_home_line"
    assert case["offered"] == "homing_at_start"
    assert case["answer_at_start"] == ("arm out" if path == "out" else "yes")
    assert case.get("answer_to_offer") is None
    seq = job.start_case_seq
    p.drive(job.home_after_stop())
    assert job.start_case["answer_to_offer"] == "yes" and job.start_case_seq > seq


def test_the_start_case_says_why_nothing_is_offered(tmp_path):
    job, sim, p, r = _found(tmp_path, "cal", (0, 3000))
    case = job.start_case
    assert case["offered"] == "nothing" and case["why"] == "homing_not_from_here"


def test_the_start_case_at_rest(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    assert p.drive(job.open()).ok
    assert p.drive(job.calibrate()).ok
    assert job.start_case["where"] == "at_rest" and job.start_case["offered"] == "nothing_needed"


@pytest.mark.parametrize("state,kw,inject", [
    ("aiming_mode_on", {"mode": "01"}, None),
    ("a0_530000", {}, "a0_after_hand"),
])
def test_the_start_case_of_a_refused_table(tmp_path, state, kw, inject):
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    for k, v in kw.items():
        setattr(sim, k, v)
    if inject:
        sim.inject(inject, "a0")
    p.drive(job.open())
    assert job.start_case["table"] == state and job.start_case["offered"] == "nothing"


# ---- the rest of the table's START states, on the simulator --------------------------------------
@pytest.mark.parametrize("fault,cid", [("no_answer", "a0"), ("refuse", "f4"),
                                       ("garbled", "s0")])
def test_a_table_that_does_not_answer_its_opening_as_recorded_is_never_moved(tmp_path, fault,
                                                                               cid):
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    sim.pos = [1098.0, 810.0]
    sim.inject(fault, cid)
    r = p.drive(job.open())
    assert r.kind == J.Kind.STOPPED
    assert job.home_after_stop().kind == J.Kind.REFUSED
    assert not [ln for ln in sim.received if ln[1:3] in MOVES] and ";p025" not in sim.received


def test_a_just_switched_on_table_answered_at_rest_while_the_arm_is_out(tmp_path):
    """B3: the answer is the only information before i0 (no recording shows a reading sent to a
    cold table before it); the start-up's own check stops it, and nothing is offered after."""
    job, sim, helper, run, p = job_for(tmp_path, real_table=False, cold=True,
                                       i0_after=(1098.0, 810.0))
    assert p.drive(job.open()).ok
    r = p.drive(job.start_up())
    assert r.kind == J.Kind.STOPPED
    assert r.way_back != J.WayBack.HOME_AFTER_STOP
    assert job.home_after_stop().reason in ("table_not_started", "moved_in_this_sitting")
    assert [ln for ln in sim.received if ln[1:3] in MOVES] == [";i02c"]


# ---- the window: the pages, the app log ----------------------------------------------------------
def test_the_window_offers_it_and_goes_on_and_the_app_log_says_so(qtbot, monkeypatch, tmp_path,
                                                                  settings, caplog):  # noqa: F811
    import logging

    from tests.i1io_table.window_sim import WindowSim
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        win, sim, run, p, saved, finished = open_window(
            qtbot, monkeypatch, tmp_path, settings, sim=WindowSim(pos=[1098.0, 810.0]),
            asking=False)
        assert p.drive_until("ready_to_open") == "ready_to_open"
        win._tick_widgets[1].setChecked(True)
        p.press("The arm is out")
        assert p.page() == "refused" and p.labels() == ["End measurement", "Bring the arm home"]
        p.press("Bring the arm home")
        p.press("Go")
        p.idle()
        assert p.page() == "home_after_stop_done" and p.labels() == ["Go on"]
    m = [r.getMessage() for r in caplog.records if r.name == "chromiq.events"]
    cases = [x for x in m if x.startswith("table start case:")]
    assert any("where=out_along_the_home_line" in x and "offered=homing_at_start" in x
               and "arm out" in x for x in cases), cases
    assert any("answer_to_offer=yes" in x for x in cases), cases


def test_the_window_says_why_where_nothing_is_offered(qtbot, monkeypatch, tmp_path,
                                                      settings):  # noqa: F811
    from tests.i1io_table.window_sim import WindowSim
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, sim=WindowSim(pos=[0.0, 3000.0]), asking=False)
    assert p.drive_until("ready_to_open") == "ready_to_open"
    for cb in win._tick_widgets:
        cb.setChecked(True)
    p.press("Start")
    p.drive_until(("refused", "stopped"))
    assert p.page() == "refused" and p.labels() == ["End measurement"]
    text = win._text.text()
    assert "ChromIQ does not bring it home from there" in text and "power switch" in text
    assert not [ln for ln in sim.sim.received if ln[1:3] in MOVES]
