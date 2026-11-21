"""4.3.52: THE START RULE BY STATE, NOT BY PLACE (replaces test_4351_one_start_rule.py).

The project owner, 2026-11-20, after reading the note on 4.3.51 to the table owner: "reading your
reply to the table owner it seems you are overly cautious again. do you really think it matters
for i1profiler or the table how far out the arm is whether the app brings it to home or not? what
else should it do if it is not in the place where it is expected?"

The evidence (the owner's start-up capture of 19 Nov 2026, decoded line by line in the PRIVATE
work folder): i1Profiler opened a STARTED table (a0 130000, f4 00 four times) twice and sent the
SAME four lines s0 p0 i1 s0 both times, with the arm at rest (1102, 48) and with the arm pushed
76 mm out (1098, 810). It decided nothing from the place.

So: a started table, the arm HELD, the aiming mode OFF, the arm not at its resting place: ChromIQ
brings it home from ANYWHERE with that sequence (plus one reading that must find it at rest), as
i1Profiler does at its own start. One page with the guidance on (a hands-off question), the
countdown with it off, and the measurement goes on. The one place kept out is physical: the back
strip beside the white tile's holder (where i1Profiler itself drove the arm out first). The
states that keep their own handling: a free arm / the aiming mode on, an unknown status answer,
a table that does not answer.

What each removed 4.3.51 test protected, and where it went: the work folder's
2026-11-20_start452/removed_tests.txt.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import job_for, small_sheet
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from ui import i1io_table_window as W
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl

#: i1Profiler's own start homing (capture L60-71, L145-156) and the one reading at rest after it
F1_PLUS = [";s022", ";p025", ";i12b", ";s022", ";p025"]
#: i1Profiler's end of a job (with f0: the aiming mode on) and the reading at rest: 4.3.48's
F2 = [";s022", ";p025", ";i12b", ";s022", ";f02f", ";f42b", ";f42b", ";p025"]
MOVES = ("m0", "m1", "m2", "i1", "i0")
C = J.Confirm

#: every kind of place a held arm can stand at a START; 4.3.51 offered 3 forms, a try, or nothing
PLACES = [
    ("near rest on the home line", (1102, 150)),
    ("home line 40 mm out", (1100, 400)),
    ("the recorded place", (1098, 810)),
    ("home line beyond the record", (1102, 1150)),
    ("where recorded homings start", (0, 1600)),
    ("mid-bed", (800, 800)),
    ("the front zone", (0, 3000)),
    ("further forward than any recorded aim", (0, 3300)),
    ("the right-hand end", (-1434, 2755)),
    ("beyond the right-hand end of the box", (-1440, 1800)),
    ("right of the measuring area", (2000, 1500)),
    ("the alignment start", (2507, 1429)),
]
IDS = [p[0] for p in PLACES]
BACK_STRIP = (1058, 317)


@pytest.fixture(autouse=True)
def _no_breach():
    J.HANDS_OFF_BREACHES.clear()
    yield
    J.HANDS_OFF_BREACHES.clear()


def _moves(lines):
    return [ln for ln in lines if ln[1:3] in MOVES]


def _start(tmp_path, path, pos, guided=True, cold=False, **kw):
    """START on a table with the arm held at *pos*; the first reading by *path*: "cal" (yes, a
    white due), "out" (the person said the arm is out), "N" (yes, -N: the alignment's own
    homing reads it). Returns after the first step, driven with the default answers."""
    script = {C.READY_TO_OPEN: "arm out"} if path == "out" else None
    if guided:
        job, sim, helper, run, p = job_for(tmp_path, script, real_table=False, cold=cold, **kw)
    else:
        sheet = small_sheet()
        job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet,
                                                    aims=H.demo_aims(sheet), real_table=False,
                                                    cold=cold, **kw)
        job.guided = False
        job.consent_version = W.CONSENT_VERSION
        job.calibration_place_preference = "table tile"
        p = H.Person(job, sim, script)
    if path == "N":
        assert job.set_options(["-N"]).ok
    sim.pos = [float(pos[0]), float(pos[1])]
    r = p.drive(job.open())
    assert r.ok, (r.reason, r.detail)
    if cold:
        r = p.drive(job.start_up())
        return job, sim, p, r
    assert r.detail["table"] == "warm" and len(sim.received) == 11
    r = p.drive(job.calibrate() if path == "cal" else job.where_is_the_arm() if path == "out"
                else job.align())
    return job, sim, p, r


def _homing_lines(sim, after: int):
    """The lines from the first s0 after *after* that starts the START homing (s0 p0 i1 ...;
    2026-11-21: or s0 p0, the vendor's detour to the home line with its arrival, i1 ...)."""
    rec = sim.received
    for k in range(after, len(rec) - 2):
        if rec[k] == ";s022" and rec[k + 1] == ";p025" and rec[k + 2] == ";i12b":
            return rec[k:k + 5]
        if rec[k] == ";s022" and rec[k + 1] == ";p025" and rec[k + 2] == N3_LINE:
            return rec[k:k + 7]
    return None


#: 2026-11-21: N3's detour line (the table owner's recording of 21 Nov 2026: from the far side
#: i1Profiler drives the arm to (1102, 1498) at speed 200 before its homing)
N3_LINE = ";m0044e05da00c806"


def _expected(pos):
    """F1_PLUS, or (the far side beyond X 1281) F1_PLUS with N3's detour and its arrival."""
    from workflow.i1io.table import geometry as geo
    if geo.homing_detour(pos) == ():
        return F1_PLUS
    return [";s022", ";p025", N3_LINE, ";p025", ";i12b", ";s022", ";p025"]


CASES = [(path, *pl) for pl in PLACES for path in ("cal", "out", "N")
         if not (path == "N" and tbl.START_GUARD.contains(pl[1]))]


# ---- 1. from every place, one question, the recorded sequence, and the measurement goes on ------
@pytest.mark.parametrize("path,name,pos", CASES, ids=[f"{c[1]}-{c[0]}" for c in CASES])
def test_from_anywhere_one_question_the_recorded_homing_and_it_goes_on(tmp_path, path, name,
                                                                      pos):
    job, sim, p, r = _start(tmp_path, path, pos)
    assert r.ok, (name, path, r.kind, r.reason, r.detail)
    gos = [a for a in p.asked if a[1] == C.GO and a[2].get("step") == "home_at_start"]
    assert len(gos) == 1, p.asked
    step, kind, detail, lines_at_ask, moving = gos[0]
    assert detail.get("at_start") is True
    assert not _moves(sim.received[:lines_at_ask]), "nothing moved before the question"
    got = _homing_lines(sim, lines_at_ask)
    # THE WIRE: from every place the same five lines, i1Profiler's start homing + the reading;
    # 2026-11-21: from the far side with the vendor's detour first (N3)
    assert got == _expected(pos), (name, sim.received[lines_at_ask:])
    assert ";f02f" not in sim.received[lines_at_ask:lines_at_ask + 6]
    assert sim.violations == [] and J.HANDS_OFF_BREACHES == []
    assert job.brought_home_at_start == 1 and not job.start_homing_failed
    assert job._table.closed_reason is None
    # and the measurement goes on as usual
    for s in (("align",) if path == "N" else ("calibrate", "align")):
        if s == "calibrate" and path == "cal":
            continue
        assert p.drive(H.step(job, s)).ok, s
    assert sim.violations == []


@pytest.mark.parametrize("path", ["cal", "out", "N"])
def test_the_place_is_never_what_decides_except_the_back_strip(tmp_path, path):
    """2026-11-21: the back strip has i1Profiler's own way out (R1, 12 Nov 2026: m0 to
    (1058, 1202) and to (1102, 1202) at speed 200, then the homing): no longer a refusal."""
    job, sim, p, r = _start(tmp_path, path, BACK_STRIP)
    assert r.ok, (r.reason, r.detail)
    assert ";m0042204b200c86d" in sim.received and ";m0044e04b200c838" in sim.received
    assert sim.violations == []


def test_the_back_strip_is_the_one_physical_place():
    """in_back_strip: behind the measuring area, off the home line. Pinned exactly."""
    assert J.in_back_strip((1058, 317)) and J.in_back_strip((0, 472)) \
        and J.in_back_strip((1089, 100))
    for p in [(1090, 100), (1115, 472), (1102, 30), (0, 473), (2507, 1429), (-1500, 3500),
              (1098, 810), (0, 3300)]:
        assert not J.in_back_strip(p), p
    for p, _n in [(pl[1], pl[0]) for pl in PLACES]:
        assert J.homing_starts_here(p, False), p
    # 2026-11-21: from the back strip by the vendor's own way out (R1)
    assert J.homing_starts_here((1058, 317), False)


# ---- 2. the question, the decline, the arm moved meanwhile, once per sitting --------------------
def test_not_now_sends_nothing_and_the_offer_stays(tmp_path):
    job, sim, p, r0 = None, None, None, None
    job, sim, helper, run, p = job_for(tmp_path, {C.GO: "back"}, real_table=False)
    sim.pos = [800.0, 800.0]
    assert p.drive(job.open()).ok
    n = len(sim.received)
    r = p.drive(job.calibrate())
    assert r.kind == J.Kind.REFUSED and r.reason == "person_chose_back"
    assert sim.received[n:] == [";p025"], "only the reading"
    assert job.way_back() == J.WayBack.HOME_AFTER_STOP
    p.script[C.GO] = "yes"
    m = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert res.ok and sim.received[m:] == F1_PLUS
    assert res.detail["goes_on"] is True and job._table.closed_reason is None
    assert p.drive(job.calibrate()).ok and p.drive(job.align()).ok


def test_an_arm_moved_while_the_question_was_shown_is_not_homed(tmp_path):
    def moved(person, res):
        if res.confirm == C.GO and res.detail.get("step") == "home_at_start":
            person.sim.pos = [800.0, 700.0]          # a hand on it (mode off: it moves by hand)
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    p.on_ask = moved
    sim.pos = [800.0, 800.0]
    assert p.drive(job.open()).ok
    r = p.drive(job.calibrate())
    assert r.kind == J.Kind.STOPPED and r.reason == "arm_moved_before_homing"
    assert ";i12b" not in sim.received
    assert job.start_homing_failed


def test_once_per_sitting(tmp_path):
    job, sim, p, r = _start(tmp_path, "cal", (800, 800))
    assert r.ok
    assert job.home_after_stop().reason == "tried_already"


# ---- 3. a homing that fails: nothing more, the failure page, the sitting guided ----------------
@pytest.mark.parametrize("fault", ["short_homing", "status", "refuse", "no_done"])
@pytest.mark.parametrize("guided", [True, False])
def test_a_homing_that_fails_is_a_fault_and_nothing_more_is_sent(tmp_path, fault, guided):
    job, sim, helper, run, p = (job_for(tmp_path, real_table=False) if guided else
                                (None,) * 5)
    if not guided:
        sheet = small_sheet()
        job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet,
                                                    aims=H.demo_aims(sheet), real_table=False)
        job.guided, job.consent_version = False, W.CONSENT_VERSION
        job.calibration_place_preference = "table tile"
        p = H.Person(job, sim, {})
    sim.pos = [0.0, 3000.0]
    assert p.drive(job.open()).ok
    sim.inject(fault, "i1")
    r = p.drive(job.calibrate())
    assert not r.ok
    assert job.start_homing_failed
    k = sim.received.index(";i12b")
    assert all(ln in (";s022", ";p025") for ln in sim.received[k + 1:]), sim.received[k:]
    assert job._table.closed_reason is not None or fault == "no_done"
    assert job.guided_now, "a failed homing turns the sitting guided"
    assert job.home_after_stop().kind == J.Kind.REFUSED
    n = len(sim.received)
    for s in ("calibrate", "align"):
        assert not H.step(job, s).ok
    assert sim.received[n:] == []


# ---- 4. with the guidance off: the countdown, not a fault, and on to the end -------------------
@pytest.mark.parametrize("path", ["cal", "N"])
@pytest.mark.parametrize("pos", [(800, 800), (0, 3000), (-1434, 2755), (2507, 1429)],
                         ids=["mid-bed", "front", "right end", "alignment start"])
def test_with_the_guidance_off_a_countdown_and_it_goes_on(tmp_path, path, pos):
    job, sim, p, r = _start(tmp_path, path, pos, guided=False)
    assert r.ok, (r.kind, r.reason, r.detail)
    assert [a for a in p.asked if a[1] == C.GO] == [], "no question"
    assert any(c["for"] == "home_at_start" and c["result"] == "done" for c in job.countdowns)
    assert job.turned_guided is None, "an arm found away from rest is not a fault"
    assert job._fault_seen is None
    assert job.brought_home_at_start == 1
    assert _homing_lines(sim, 11) == _expected(pos)      # 2026-11-21: N3's detour far left
    assert J.HANDS_OFF_BREACHES == [] and sim.violations == []


def test_with_the_guidance_off_the_whole_sitting_goes_on_by_itself(qtbot, monkeypatch, tmp_path,
                                                                    settings):  # noqa: F811
    from tests.i1io_table.test_4352_guidance_off import _to_done, UNGUIDED_ANSWERS
    from tests.i1io_table.window_sim import WindowSim
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, guided=False,
        sim=WindowSim(pos=[0.0, 3000.0]))
    p.script.update(UNGUIDED_ANSWERS)
    shown = _to_done(p)
    assert shown == ["aimed"] * 3, shown
    job = sim.jobs[0]
    assert job.ended == "saved" and job.at_rest() and job.turned_guided is None
    assert job.brought_home_at_start == 1
    assert J.HANDS_OFF_BREACHES == [] and sim.sim.violations == []


# ---- 5. a just-switched-on table: the start-up wherever the arm is ------------------------------
@pytest.mark.parametrize("answer", ["yes", "arm out"])
def test_a_just_switched_on_table_gets_its_start_up_whatever_the_answer(tmp_path, answer):
    """The start-up as recorded (i0 s0 f4 x4 s0 p0 i1 s0); here the simulated i0 brings the arm
    home (as the real one did from rest), so its own homing runs from rest."""
    path = "out" if answer == "arm out" else "cal"
    job, sim, p, r = _start(tmp_path, path, (800, 800), cold=True)
    assert r.ok, (r.reason, r.detail)
    assert sim.received[6:16] == [";i02c", ";s022", ";f42b", ";f42b", ";f42b", ";f42b",
                                  ";s022", ";p025", ";i12b", ";s022"]
    assert C.START_UP in [a[1] for a in p.asked]


def test_a_start_up_that_leaves_the_arm_out_then_brings_it_home(tmp_path):
    """The table's own start-up reads the arm before its homing; when that reading finds it out
    (here the simulated i0 leaves it at (1098, 810)), the table is started: rule 1 applies."""
    job, sim, p, r = _start(tmp_path, "cal", (1098, 810), cold=True,
                            i0_after=(1098.0, 810.0))
    assert r.ok, (r.reason, r.detail)
    assert sim.received[6:14] == [";i02c", ";s022", ";f42b", ";f42b", ";f42b", ";f42b",
                                  ";s022", ";p025"]
    gos = [a for a in p.asked if a[1] == C.GO and a[2].get("step") == "home_at_start"]
    assert len(gos) == 1
    assert sim.received[14:19] == F1_PLUS
    assert job._table.closed_reason is None and job.brought_home_at_start == 1
    assert p.drive(job.calibrate()).ok and p.drive(job.align()).ok
    assert sim.violations == []


def test_with_the_guidance_off_the_start_up_comes_after_the_countdown(tmp_path):
    job, sim, p, r = _start(tmp_path, "cal", (1098, 810), guided=False, cold=True,
                            i0_after=(1098.0, 810.0))
    assert r.ok, (r.reason, r.detail)
    assert p.asked == [], p.asked
    fors = [c["for"] for c in job.countdowns]
    assert fors[:2] == ["start_up", "home_at_start"] or fors[:2] == [None, "home_at_start"], fors
    assert job.turned_guided is None
    assert sim.received[14:19] == F1_PLUS


def test_the_constant_brings_the_arm_question_back(tmp_path, monkeypatch):
    monkeypatch.setattr(J, "START_UP_ASKS_ABOUT_THE_ARM", True)
    job, sim, helper, run, p = job_for(tmp_path, {C.READY_TO_OPEN: "arm out"}, real_table=False,
                                       cold=True)
    assert p.drive(job.open()).ok
    assert job.start_up().reason == "arm_out_start_up_not_recorded"
    assert len(sim.received) == 6


# ---- 6. the states that keep their own handling -------------------------------------------------
@pytest.mark.parametrize("answer", ["yes", "arm out"])
def test_aiming_mode_still_on_nothing_is_sent(tmp_path, answer):
    """2026-11-21: a table left in its aiming mode is no longer refused: the opening moves
    nothing and reads nothing, and the repair (its own question first) is what is offered
    (tests/i1io_table/test_4355_table_without_i1profiler.py); the START rule's homing is not."""
    job, sim, helper, run, p = job_for(tmp_path, {C.READY_TO_OPEN: answer}, real_table=False)
    sim.pos, sim.mode, sim.free_arm = [800.0, 800.0], "01", True
    r = p.drive(job.open())
    assert r.ok and r.detail["aiming_mode_left_on"] is True
    assert r.way_back == J.WayBack.REPAIR_AT_START
    assert job.home_after_stop().kind == J.Kind.REFUSED
    assert not _moves(sim.received) and ";p025" not in sim.received


@pytest.mark.parametrize("answer", ["yes", "arm out"])
def test_an_unknown_status_answer_nothing_is_sent(tmp_path, answer):
    job, sim, helper, run, p = job_for(tmp_path, {C.READY_TO_OPEN: answer}, real_table=False)
    sim.pos = [800.0, 800.0]
    sim.inject("a0_other", "a0")
    r = p.drive(job.open())
    assert r.kind == J.Kind.STOPPED and r.reason == "table_state_unknown"
    assert job.home_after_stop().kind == J.Kind.REFUSED
    assert len(sim.received) == 6


@pytest.mark.parametrize("fault,cid", [("no_answer", "a0"), ("refuse", "f4"),
                                       ("garbled", "s0")])
def test_a_table_that_does_not_answer_as_recorded_is_never_moved(tmp_path, fault, cid):
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    sim.pos = [800.0, 800.0]
    sim.inject(fault, cid)
    r = p.drive(job.open())
    assert r.kind == J.Kind.STOPPED
    assert job.home_after_stop().kind == J.Kind.REFUSED
    assert not _moves(sim.received) and ";p025" not in sim.received


def test_a_free_arm_is_never_given_the_start_homing(tmp_path):
    job, sim, p, r = _start(tmp_path, "cal", (800, 800))
    assert r.ok
    job._table.arm_free = True
    assert job._home_after_stop_why() in ("arm_not_held", "tried_already")


# ---- 7. what the job records about the START ----------------------------------------------------
@pytest.mark.parametrize("path", ["cal", "out", "N"])
def test_the_start_case_is_recorded(tmp_path, path):
    job, sim, p, r = _start(tmp_path, path, (800, 800))
    case = job.start_case
    assert case["table"] == "warm" and J._near(case["place"], (800, 800), 1)
    assert case["where"] == "out" and case["offered"] == "homing_at_start"
    assert case["answer_at_start"] == ("arm out" if path == "out" else "yes")
    assert case["answer_to_offer"] == "yes"


def test_the_start_case_says_why_nothing_is_offered_in_the_back_strip(tmp_path):
    """2026-11-21: the back strip is offered the homing too (with R1's way out first)."""
    job, sim, p, r = _start(tmp_path, "cal", BACK_STRIP)
    case = job.start_case
    assert case["where"] == "back_strip"
    assert case["offered"] == "homing_at_start"


# ---- 8. the window: one short page, the failure page, the back strip -----------------------------
def _window(qtbot, monkeypatch, tmp_path, settings, pos, **kw):
    from tests.i1io_table.window_sim import WindowSim
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, sim=WindowSim(pos=list(pos), **kw), asking=False)
    assert p.drive_until("ready_to_open") == "ready_to_open"
    for cb in win._tick_widgets:
        cb.setChecked(True)
    p.press("Start")
    return win, sim, p


def test_the_window_shows_one_short_page_and_goes_on(qtbot, monkeypatch, tmp_path,
                                                     settings):  # noqa: F811
    from workflow import measurement_messages as M
    win, sim, p = _window(qtbot, monkeypatch, tmp_path, settings, (0.0, 3000.0))
    p.drive_until(("home_at_start",))
    assert p.page() == "home_at_start"
    assert p.labels() == ["Not now", "Bring the arm home, my hands are away"]
    text = win._text.text()
    assert M.M_I1IO_DRIVE_HOME_AT_START.render()[1].split("\n\n")[0] in text
    for word in ("try", "record", " mm", " cm", "i1Profiler"):
        assert word not in text, word
    p.press("Bring the arm home, my hands are away")
    p.idle()
    assert sim.sim.jobs if hasattr(sim.sim, "jobs") else True
    job = sim.jobs[0]
    assert job.brought_home_at_start == 1 and tbl.REST_GUARD.contains(job._table.position_now)
    assert p.page() not in ("refused", "stopped"), p.page()


@pytest.mark.parametrize("fault", ["short_homing", "status"])
def test_the_window_shows_the_failure_page(qtbot, monkeypatch, tmp_path, settings,
                                           fault):  # noqa: F811
    win, sim, p = _window(qtbot, monkeypatch, tmp_path, settings, (800.0, 800.0),
                          table_faults=[(fault, "i1")])
    p.drive_until(("home_at_start",))
    p.press("Bring the arm home, my hands are away")
    p.drive_until(("stopped", "refused"))
    assert win._title.text() == "The arm did not get home"
    text = win._text.text()
    # 2026-11-21 (the owner: "driving the table should work without involving i1profiler"):
    # the way on is the power switch and START, never i1Profiler
    assert "power switch" in text and "START MEASUREMENT" in text
    assert "i1Profiler" not in text
    assert sim.jobs[0].guided_now


def test_the_window_says_the_back_strip(qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    """2026-11-21: from the back strip the arm is brought home by i1Profiler's own way out (R1);
    only a place in the back strip beyond the left end of the target area has none."""
    win, sim, p = _window(qtbot, monkeypatch, tmp_path, settings, (1058.0, 317.0))
    p.drive_until(("home_at_start",))
    p.press("Bring the arm home, my hands are away")
    p.idle()
    assert ";m0042204b200c86d" in sim.sim.received and ";m0044e04b200c838" in sim.sim.received
    assert tbl.REST_GUARD.contains(sim.jobs[0]._table.position_now)
    win2, sim2, p2 = _window(qtbot, monkeypatch, tmp_path / "far", settings, (2600.0, 300.0))
    p2.drive_until(("refused", "stopped"))
    assert p2.page() == "refused" and p2.labels() == ["End measurement"]
    assert "beside the holder of the white tile" in win2._text.text()
    assert "i1Profiler" not in win2._text.text()
    assert not _moves(sim2.sim.received)
