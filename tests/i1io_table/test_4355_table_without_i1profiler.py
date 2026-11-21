"""2026-11-21: THE TABLE WITHOUT i1PROFILER.

The project owner, Basti, 2026-11-21, after the table owner reported that the arm stayed on the
last patch and asked whether he must open i1Profiler to finish: "remember that driving the table
should work without involving i1profiler".

Until 4.3.54 every ending without the homing (Stop with "Leave it there", "Not now" and Close, the
window closed, the app quit or killed, an error, a lost link) left the table in its AIMING MODE
(f1 sent, no f0). a0 then answers with bit 0x40 (511800 just switched on, 530000 / 540000
started), also after a power cycle, and every later START refused the table: only i1Profiler
helped. What i1Profiler does with such a table is now recorded (numbers and command forms only;
the recordings themselves stay private):

* N1 (the table owner, 21 Nov 2026 18:31): a0 530000, s0, f4 x4 answering 01, s0, p0 (1104, 43),
  i1 (0.336 s), s0; the mode ended at its quit.
* recording A (the owner's start-up capture, 19 Nov 2026): a0 511800, i0 (3.327 s), s0, f4 x4
  answering 01, s0, p0 (1102, 27), i1 (0.288 s), s0.
* R19 (19 Nov 2026): the end of a job s0 p0 i1 s0 f0 f4 f4.

And its WAY HOME from two places: N3 (21 Nov 2026 18:37) from (2134, 1801): m0 to (1102, 1498) at
speed 200 (1.487 s), then i1 (2.367 s); R1 (12 Nov 2026) from the back strip at (1058, 317): m0 to
(1058, 1202) at 200, m0 to (1102, 1202) at 200, then i1. From (1281, 1423) (N2) it homed straight.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from workflow.i1io.table import caps as cp
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J
from workflow.i1io.table import lines as cl
from workflow.i1io.table import session_table as tbl

C = J.Confirm
MOVES = ("m0", "m1", "m2", "i1", "i0")
#: i1Profiler's opening of a started table, as recorded in N1 (the mode answers 01)
OPEN_AIMING = [";a133", ";a133", ";k228", ";u8000060000100d1", ";u8000061000068c3", ";a034",
               ";s022", ";f42b", ";f42b", ";f42b", ";f42b"]
#: the repair: i1Profiler's end of a job (N1's homing, R19's tail) and ChromIQ's reading at rest
REPAIR = [";s022", ";p025", ";i12b", ";s022", ";f02f", ";f42b", ";f42b", ";p025"]
#: the vendor's detour lines, byte for byte as recorded (N3 1.358; R1 84.153, 85.529)
N3_LINE = ";m0044e05da00c806"
R1_OUT = ";m0042204b200c86d"
R1_ACROSS = ";m0044e04b200c838"


@pytest.fixture(autouse=True)
def _no_breach():
    J.HANDS_OFF_BREACHES.clear()
    yield
    assert J.HANDS_OFF_BREACHES == []


def _moves(lines):
    return [ln for ln in lines if ln[1:3] in MOVES]


def _table(pos, cold=False, a0="530000", **kw):
    job, sim, _t = H.make_job(cold=cold, real_table=False, **kw)
    sim.mode = "01"
    sim.a0_aiming = a0
    sim.pos = [float(pos[0]), float(pos[1])]
    return job, sim


def _open(job, sim, script=None):
    p = H.Person(job, sim, script)
    r = p.drive(job.open())
    assert r.ok, (r.reason, r.detail)
    return p, r


# ---- 1. the state at START -> the recorded sequence ----------------------------------------------
#: (-1317, 3185) and (-1193, 3253): where the table owner's real arm was left, held, mode on, after
#: his complete pages of 21 Nov (4.3.54) and 20 Nov (4.3.50); the next START met a0 540000
@pytest.mark.parametrize("a0,pos", [("530000", (1104, 43)), ("540000", (-1193, 3253)),
                                    ("540000", (-1317, 3185)),
                                    ("530000", (0, 1600)), ("540000", (1281, 1423))])
def test_a_started_table_in_its_aiming_mode_is_brought_home_as_i1profiler_does(a0, pos):
    job, sim = _table(pos, a0=a0)
    p, r = _open(job, sim)
    assert sim.received == OPEN_AIMING
    assert r.detail["aiming_mode_left_on"] is True and r.detail["a0"] == a0
    assert r.way_back == J.WayBack.REPAIR_AT_START
    # nothing else may run before the mode is ended
    assert job.park().reason == "aiming_mode_left_on"
    assert not _moves(sim.received)
    n = len(sim.received)
    r = p.drive(job.repair_at_start())
    assert r.ok, (r.reason, r.detail)
    gos = [a for a in p.asked if a[1] == C.GO]
    assert len(gos) == 1 and gos[0][2]["step"] == "repair_at_start" and gos[0][3] == n
    assert sim.received[n:] == REPAIR
    assert sim.mode == "00" and not job._table.mode_on and job.at_rest()
    assert sim.violations == []
    # and the measurement goes on as at any START
    assert p.drive(job.park()).ok
    assert p.drive(job.align()).ok
    assert sim.violations == []


def test_from_the_far_side_the_repair_takes_the_vendors_detour_first():
    job, sim = _table((2506, 1440))
    p, _r = _open(job, sim)
    n = len(sim.received)
    assert p.drive(job.repair_at_start()).ok
    # the arm's state is not known (free or held): read twice; then N3's line, its arrival, i1
    assert sim.received[n:] == [";s022", ";p025", ";p025", N3_LINE, ";p025", ";i12b", ";s022",
                                ";f02f", ";f42b", ";f42b", ";p025"]
    assert sim.detour_moves == [((2506.0, 1440.0), (1102, 1498))]
    assert sim.violations == []


def test_from_the_back_strip_the_repair_takes_the_recorded_way_out():
    job, sim = _table((1058, 317))
    p, _r = _open(job, sim)
    n = len(sim.received)
    assert p.drive(job.repair_at_start()).ok
    assert sim.received[n:] == [";s022", ";p025", ";p025", R1_OUT, ";p025", R1_ACROSS,
                                ";p025", ";i12b", ";s022", ";f02f", ";f42b", ";f42b", ";p025"]
    assert sim.violations == []


def test_a_just_switched_on_table_in_its_aiming_mode_gets_recording_a_then_the_mode_ended():
    job, sim = _table((1102, 27), cold=True)
    sim.i0_after = (1102.0, 27.0)
    p, r = _open(job, sim)
    assert r.detail["table"] == "cold" and r.detail["aiming_mode_left_on"] is True
    assert sim.received[-1] == ";a034" and len(sim.received) == 6
    n = len(sim.received)
    r = p.drive(job.start_up())
    assert r.ok, (r.reason, r.detail)
    start_ups = [a for a in p.asked if a[1] == C.START_UP]
    assert start_ups and start_ups[0][2]["aiming_left_on"] is True
    # recording A, line for line (i0, s0, f4 x4 01, s0, p0, i1, s0), then R19's tail
    assert sim.received[n:] == [";i02c", ";s022", ";f42b", ";f42b", ";f42b", ";f42b", ";s022",
                                ";p025", ";i12b", ";s022", ";f02f", ";f42b", ";f42b", ";p025"]
    assert r.detail["aiming_mode_ended"] is True and job.repaired_at_start == 1
    assert sim.mode == "00" and job.at_rest()
    assert p.drive(job.park()).ok and sim.violations == []


def test_a_just_switched_on_table_with_the_arm_out_after_its_start_up():
    job, sim = _table((0, 1600), cold=True)
    sim.i0_after = (0.0, 1600.0)
    p, _r = _open(job, sim)
    n = len(sim.received)
    r = p.drive(job.start_up())
    assert r.ok, (r.reason, r.detail)
    gos = [a for a in p.asked if a[1] == C.GO and a[2].get("step") == "repair_at_start"]
    assert len(gos) == 1
    assert _moves(sim.received[n:gos[0][3]]) == [";i02c"], "only the start-up before the question"
    assert sim.received[gos[0][3]:] == REPAIR
    assert job.at_rest() and sim.violations == []


def test_not_now_sends_nothing_and_the_offer_stays():
    job, sim = _table((0, 1600))
    p, _r = _open(job, sim, {C.GO: "back"})
    n = len(sim.received)
    r = p.drive(job.repair_at_start())
    assert r.kind == J.Kind.REFUSED and r.reason == "person_chose_back"
    assert sim.received[n:] == [] and r.way_back == J.WayBack.REPAIR_AT_START
    p.script[C.GO] = "yes"
    r = p.drive(job.repair_at_start())
    assert r.ok and sim.received[n:] == REPAIR


def test_with_the_guidance_off_the_countdown_stands_in_for_the_question():
    job, sim = _table((0, 1600))
    job.guided = False
    p, _r = _open(job, sim)
    n = len(sim.received)
    r = p.drive(job.repair_at_start())
    assert r.ok, (r.reason, r.detail)
    assert not [a for a in p.asked if a[1] == C.GO]
    assert [c["for"] for c in job.countdowns] == ["repair_at_start"]
    assert sim.received[n:] == REPAIR


def test_an_unknown_state_answer_still_moves_nothing():
    job, sim, _t = H.make_job(real_table=False)
    sim.inject("a0_other", "a0")
    r = H.Person(job, sim).drive(job.open())
    assert r.kind == J.Kind.STOPPED and r.reason == "table_state_unknown"
    assert not _moves(sim.received)


# ---- 1b. fix round (safety review B-1): the mode answers decide; a disagreement never refuses ----
# THE SIMULATOR'S ASSUMPTIONS ARE SWITCHED HERE (session_sim.SimTable.a0_override / mode): what a0
# answers and what f4 answers are set independently, because no recording shows them disagreeing
# and nobody has read f4 on a 540000 table. Every combination must end with the arm at rest and the
# mode off (f4 00 after f0), never in a refusal: the vendor sends the same lines whether the mode
# is on (N1) or off (N2), f0 included (R19 job end; N2 quit 25.676, answer 00).
WARM = [("530000", "01"), ("540000", "01"), ("530000", "00"), ("540000", "00"), ("130000", "01")]


@pytest.mark.parametrize("a0,f4", WARM, ids=[f"{a}-f4_{f}" for a, f in WARM])
@pytest.mark.parametrize("pos", [(1104, 43), (0, 1600), (-1317, 3185), (2134, 1801)],
                         ids=["at rest", "mid-bed", "front right", "far side"])
def test_every_warm_combination_ends_with_the_arm_at_rest(a0, f4, pos):
    job, sim, _t = H.make_job(real_table=False)
    sim.a0_override, sim.mode = a0, f4
    sim.pos = [float(pos[0]), float(pos[1])]
    p, r = _open(job, sim)
    assert sim.received == OPEN_AIMING and r.detail["aiming_mode_left_on"] is True
    assert job.start_case["a0_f4_disagree"] is ((a0 != "130000") != (f4 == "01"))
    assert job.start_case["f4"] == f4 and job.start_case["a0"] == a0
    n = len(sim.received)
    r = p.drive(job.repair_at_start())
    assert r.ok, (r.kind, r.reason, r.detail)
    sent = sim.received[n:]
    assert sent[-6:] == [";i12b", ";s022", ";f02f", ";f42b", ";f42b", ";p025"], sent
    assert job.at_rest() and sim.mode == "00" and not job._table.mode_on
    assert sim.violations == []
    assert p.drive(job.park()).ok


COLD = [("511800", "01"), ("511800", "00"), ("111800", "01")]


@pytest.mark.parametrize("a0,f4", COLD, ids=[f"{a}-f4_{f}" for a, f in COLD])
def test_every_cold_combination_starts_up_and_ends_the_mode(a0, f4):
    job, sim, _t = H.make_job(cold=True, real_table=False)
    sim.a0_override, sim.mode = a0, f4
    sim.i0_after = (1102.0, 27.0)
    p, r = _open(job, sim)
    assert r.ok and r.detail["table"] == "cold"
    n = len(sim.received)
    r = p.drive(job.start_up())
    assert r.ok, (r.kind, r.reason, r.detail)
    assert sim.received[n:] == [";i02c", ";s022", ";f42b", ";f42b", ";f42b", ";f42b", ";s022",
                                ";p025", ";i12b", ";s022", ";f02f", ";f42b", ";f42b", ";p025"]
    assert job.at_rest() and sim.mode == "00" and sim.violations == []
    assert p.drive(job.park()).ok


def test_a_plain_cold_table_sends_no_tail():
    """111800 with f4 00 (S1): the start-up as before, no f0."""
    job, sim, _t = H.make_job(cold=True, real_table=False)
    sim.i0_after = (1102.0, 27.0)
    p, _r = _open(job, sim)
    n = len(sim.received)
    assert p.drive(job.start_up()).ok
    assert sim.received[n:] == [";i02c", ";s022", ";f42b", ";f42b", ";f42b", ";f42b", ";s022",
                                ";p025", ";i12b", ";s022"]


def test_four_mode_answers_that_differ_move_nothing():
    """The one disagreement that still refuses: the four f4 answers differ among THEMSELVES
    (every recording shows four equal answers). Nothing moves; the page says it plainly."""
    job, sim, _t = H.make_job(real_table=False)
    sim.inject_at(8, "free")                   # the second f4 answers the other way
    r = H.Person(job, sim).drive(job.open())
    assert r.kind == J.Kind.STOPPED and r.reason == "mode_flag_unexpected"
    assert not _moves(sim.received)


@pytest.mark.parametrize("bit_survives,mode_after", [(True, "01"), (True, "00"), (False, "01"),
                                                     (False, "00")])
def test_a_power_cycle_in_the_trap_never_loops(bit_survives, mode_after):
    """The trap, then the power switch, under every assumption about what survives it."""
    sim = _leave_it_there()
    sim.power_cycle(bit_survives=bit_survives, mode_after=mode_after)
    sim.i0_after = (1102.0, 27.0)
    job2, sim2, _t = H.make_job(sim=sim)
    p2 = H.Person(job2, sim2)
    r = p2.drive(job2.open())
    assert r.ok and r.detail["table"] == "cold"
    r = p2.drive(job2.start_up())
    assert r.ok, (r.kind, r.reason, r.detail)
    # (a plain start-up ends with i1 s0, no reading: the job's "unread rest")
    assert (job2.at_rest() or job2.unread_rest()) and sim.mode == "00" and sim.violations == []
    job2.close()
    # and the next START is an ordinary one
    job3, sim3, _t = H.make_job(sim=sim)
    p3 = H.Person(job3, sim3)
    r = p3.drive(job3.open())
    assert r.ok and not r.detail.get("aiming_mode_left_on") and r.detail["table"] == "warm"
    assert p3.drive(job3.park()).ok


# ---- 2. the chain: an ending that sends nothing, then the next START repairs -------------------
def _leave_it_there(sim_pos=None):
    """A sitting that aims and then ends without the homing (the window's "Leave it there", the
    window closed, the app quit, a killed app: close() sends nothing in all of them)."""
    job, sim, _t = H.make_job(real_table=False)
    if sim_pos is not None:
        sim.pos = [float(sim_pos[0]), float(sim_pos[1])]
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    assert p.drive(job.park()).ok
    assert p.drive(job.align()).ok
    n = len(sim.received)
    job.close()
    assert sim.received[n:] == [], "close() sends nothing"
    rec = job.ending_record
    assert rec["mode_left_on"] is True and rec["sent_at_close"] == "nothing"
    assert rec["next_start"] == "start_brings_the_arm_home_and_ends_the_aiming_mode"
    assert sim.mode == "01" and sim.free_arm
    return sim


def test_an_ending_without_the_homing_is_repaired_by_the_next_start():
    sim = _leave_it_there()
    job2, sim2, _t = H.make_job(sim=sim)
    p2 = H.Person(job2, sim2)
    n = len(sim.received)
    r = p2.drive(job2.open())
    assert r.ok and r.detail["aiming_mode_left_on"] and sim.received[n:] == OPEN_AIMING
    r = p2.drive(job2.repair_at_start())
    assert r.ok, (r.reason, r.detail)
    assert sim.mode == "00" and job2.at_rest() and sim.violations == []
    # the arm stood where the person last aimed (the far side of the demo sheet): the detour
    sent = sim.received[n + len(OPEN_AIMING):]
    assert sent[-6:] == [";i12b", ";s022", ";f02f", ";f42b", ";f42b", ";p025"]
    assert p2.drive(job2.park()).ok and p2.drive(job2.align()).ok


def test_the_same_after_a_power_cycle():
    sim = _leave_it_there()
    # the power switch: the table comes back just switched on, the mode bit survives (rec A)
    sim.cold, sim.started, sim.i0_sent = True, False, False
    sim.i0_after = (1102.0, 27.0)
    sim.free_arm = False
    job2, sim2, _t = H.make_job(sim=sim)
    p2 = H.Person(job2, sim2)
    r = p2.drive(job2.open())
    assert r.ok and r.detail["table"] == "cold" and r.detail["aiming_mode_left_on"]
    assert sim.received[-1] == ";a034"
    r = p2.drive(job2.start_up())
    assert r.ok, (r.reason, r.detail)
    assert sim.mode == "00" and job2.at_rest() and sim.violations == []


# ---- 3. the vendor's way home: the region and the gate -----------------------------------------
@pytest.mark.parametrize("p,legs", [
    ((1281, 1423), ()),                                   # N2: straight
    ((1282, 1423), ((1102, 1498),)),                      # beyond N2's X: N3's detour
    ((2134, 1801), ((1102, 1498),)),                      # N3 itself
    ((2507, 1429), ((1102, 1498),)),                      # the alignment start
    ((1500, 3300), ((1102, 1498),)),                      # far side, front
    ((-1288, 3236), ()),                                  # R19's cancel: straight
    ((-1437, 1794), ()),                                  # right-hand end: straight
    ((1102, 1202), ()),                                   # home line: straight
    ((1102, 30), ()),                                     # at rest
    ((1090, 300), ()), ((1115, 300), ()),                 # the home line's band in the strip
    ((1058, 317), ((1058, 1202), (1102, 1202))),          # R1 itself
    ((1089, 472), ((1089, 1202), (1102, 1202))),          # the strip's edges
    ((1116, 0), ((1116, 1202), (1102, 1202))),
    ((1500, 472), ((1500, 1202), (1102, 1202))),          # the strip on the far side: R1's form
    ((1500, 473), ((1102, 1498),)),                       # just in front of the strip: N3's
    # fix round (review m-2): beyond the left end of the target area, in the strip: straight
    # ahead at that end (a few units inwards), never "no way home"
    ((2600, 300), ((2507, 1202), (1102, 1202))),
    ((2507, 300), ((2507, 1202), (1102, 1202))),
])
def test_the_detour_region(p, legs):
    assert geo.homing_detour(p) == legs
    assert J.homing_starts_here(p, False) is (legs is not None)
    assert geo.homing_detour(None) is None


def test_the_no_way_home_page_only_where_there_is_none(monkeypatch):
    """Review M-1: the window's "no way home" page is chosen by homing_detour() is None, never by
    the back strip: (1058, 317) has R1's way out; since the fix round nothing a table reports
    lacks one (a planted reading shows the page's condition still works)."""
    from ui import i1io_table_window as W
    assert not W._J_no_way_home((1058, 317)) and not W._J_no_way_home((2600, 300))
    assert not W._J_no_way_home(None)
    H.plant_no_way_home(monkeypatch)
    assert W._J_no_way_home((2600, 300)) and not W._J_no_way_home((1058, 317))
    way = W.no_way_home_way()
    assert way.index("power switch") < way.index("START MEASUREMENT") and "i1Profiler" not in way


def test_the_detour_lines_are_the_recorded_bytes():
    assert geo.detour_line(1102, 1498).decode().rstrip("\r") == N3_LINE
    assert geo.detour_line(1058, 1202).decode().rstrip("\r") == R1_OUT
    assert geo.detour_line(1102, 1202).decode().rstrip("\r") == R1_ACROSS
    with pytest.raises(geo.AreaRefused):
        geo.detour_line(1102, 1500)
    with pytest.raises(geo.AreaRefused):
        geo.m0_line(1102, 1498, speed=200)          # never a chart move at 200


def test_the_gate_lets_a_detour_move_through_only_on_the_way_home():
    for line in (N3_LINE, R1_OUT, R1_ACROSS):
        assert cl.classify((line + "\r").encode())[2] == "detour m0"
        assert cl.wire_gate((line + "\r").encode()) == "m0"
    with pytest.raises(tbl.ForbiddenLine):
        cl.classify(geo._line("m0", 1000, 1498, 200))      # not a detour target
    with pytest.raises(tbl.ForbiddenLine):
        cl.classify(geo._line("m0", 1102, 1498, 250))      # an unrecorded speed

    class T:
        position_now = (2134, 1801)
        detour_phase = None
    gate = cl.make_gate(T)
    with pytest.raises(tbl.ForbiddenLine):
        gate((N3_LINE + "\r").encode())                    # outside the way home
    T.detour_phase = "out"
    assert gate((N3_LINE + "\r").encode())[0] == "m0"
    T.position_now = (1058, 317)                           # the back strip: only straight ahead
    with pytest.raises(tbl.ForbiddenLine):
        gate((N3_LINE + "\r").encode())
    T.detour_phase = "back_strip"
    assert gate((R1_OUT + "\r").encode())[0] == "m0"
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo._line("m0", 1000, 1202, 200))
    T.position_now = (2600, 300)                           # beyond the left end: to 2507
    assert gate(geo._line("m0", 2507, 1202, 200))[0] == "m0"
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo._line("m0", 2600, 1202, 200))             # outside the target area
    T.position_now = None
    with pytest.raises(tbl.ForbiddenLine):
        gate((R1_OUT + "\r").encode())


def test_the_wire_gate_refuses_a_detour_move_outside_the_way_home():
    """Review m-5: the second check at the USB write holds the table too."""
    class T:
        dual_phase = None
        detour_phase = None
    wire = cl.make_wire_gate(T)
    for line in (N3_LINE, R1_OUT, R1_ACROSS):
        with pytest.raises(tbl.ForbiddenLine):
            wire((line + "\r").encode())
    T.detour_phase = "out"
    assert wire((N3_LINE + "\r").encode()) == "m0"


def test_no_other_code_path_sends_a_detour_move(monkeypatch):
    """Review G-3: a whole page (computed moves, rows, homing) with the way home switched off
    sends no m0 at speed 200; every detour line goes out only inside _way_home."""
    seen = []
    real = J.TableJob._way_home

    def spy(self, got):
        seen.append(len(self._table.t.table.received) if hasattr(self._table.t, "table")
                    else None)
        return real(self, got)
    monkeypatch.setattr(J.TableJob, "_way_home", spy)
    monkeypatch.setattr(geo, "homing_detour", lambda p: () if p is not None else None)
    from tests.i1io_table.test_job_reading import job_for, read_page, ready_to_read
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as t:
        job, sim, helper, run, p = job_for(Path(t), real_table=False)
        ready_to_read(job, p)
        read_page(job, p)
        assert p.drive(job.home()).ok
        assert not [ln for ln in sim.received if ln.startswith(";m0") and ln[11:15] == "00c8"]


def test_the_start_rule_homing_from_the_far_side_takes_the_detour():
    """A started table, the mode off, the arm held on the far side: the START rule's homing with
    N3's detour first (4.3.52-4.3.54 homed straight from there)."""
    job, sim, _t = H.make_job(real_table=False)
    sim.pos = [2000.0, 1500.0]
    p = H.Person(job, sim, {C.READY_TO_OPEN: "arm out"})
    assert p.drive(job.open()).ok
    n = len(sim.received)
    r = p.drive(job.where_is_the_arm())
    assert r.ok, (r.reason, r.detail)
    assert sim.received[n:] == [";p025", ";s022", ";p025", N3_LINE, ";p025", ";i12b", ";s022",
                                ";p025"]
    assert sim.violations == []


def test_the_caps_carry_the_detour():
    assert cp.HOME_DETOUR == (cp.HOME[0] + 7, cp.HOME[1] + 2)
    assert J.TableJob.RUN_GRANT["f"][0] >= cp.HOME_DETOUR[0]
    assert J.TableJob.RUN_GRANT["f"][1] >= cp.HOME_DETOUR[1]


# ---- 4. the logs -------------------------------------------------------------------------------
def test_the_start_case_names_the_state_and_the_repair():
    job, sim = _table((0, 1600), a0="540000")
    p, _r = _open(job, sim)
    assert job.start_case["table"] == "aiming_mode_left_on"
    assert job.start_case["a0"] == "540000" and job.start_case["offered"] == "repair_at_start"
    p.drive(job.repair_at_start())
    assert job.start_case["answer_to_offer"] == "yes"
    job.close()
    rec = job.ending_record
    assert rec["repaired_at_start"] == 1


# ---- 5. texts: no way out through i1Profiler ---------------------------------------------------
RECOVERY_IDS = ("START-UP", "START-UP-ARM", "SWITCH-OFF", "STOPPED", "LINK-LOST",
                "LINK-LOST-SWITCH-OFF", "COLD", "COLD-WAY-OUT", "FREE-LEFT", "STOPPED-END-FIRST",
                "HOME-AFTER-STOP-DONE", "ARM-WAY-OUT", "ARM-WAY-OUT-ENDED", "HOME-NOT-NOW",
                "HOME-AT-END", "LEFT-OUT", "STILL-AIMING", "AFTER-PROBLEM-OUT", "ARM-OUT-BACK",
                "REPAIR-AT-START", "START-UP-AIMING", "HOME-TRY-FAILED", "HOME-AFTER-STOP",
                "HOME-AT-START", "HOME-AT-START-DONE")


@pytest.mark.parametrize("mid", RECOVERY_IDS)
def test_no_way_out_of_the_table_sends_the_person_to_i1profiler(mid):
    from workflow import measurement_messages as M
    m = M.CATALOGUE["M-I1IO-DRIVE-" + mid]
    assert "i1Profiler 3.8" not in m.body and "open i1Profiler" not in m.body.lower()
    assert "i1Profiler once" not in m.body
    assert not getattr(m, "needs_old_i1profiler", False)


def test_the_windows_own_way_out_texts_name_no_i1profiler(qapp):
    from ui import i1io_table_window as W
    for text in (W.table_state_text("120000"), W.table_state_text("")):
        assert "i1Profiler" not in text
    import inspect
    for fn in (W.TableMeasureWindow._arm_out_text, W.no_way_home_way,
               W.TableMeasureWindow._front_stop_way):
        assert "i1Profiler 3.8" not in inspect.getsource(fn)


# ---- last round: the two remaining lockouts become offers (the person's choice) ----------------
# THE SIMULATOR'S ASSUMPTIONS, LABELLED: the "free" fault makes ONE f4 answer the other way (no
# recording shows four f4 answers that differ); a0_override gives an a0 no recording shows. What a
# real table does with the repair or the start-up in those states is NOT known: the pages say so.
def _mixed_at_opening(**kw):
    job, sim, _t = H.make_job(real_table=False, **kw)
    sim.pos = [0.0, 1600.0]
    sim.inject_at(8, "free")                 # the second f4 of the opening answers 01
    p = H.Person(job, sim)
    r = p.drive(job.open())
    assert r.kind == J.Kind.STOPPED and r.reason == "mode_flag_unexpected"
    assert not _moves(sim.received) and job._table.f4_mixed
    assert r.way_back == J.WayBack.REPAIR_AT_START
    return job, sim, p


def test_mixed_answers_do_nothing_sends_nothing():
    job, sim, p = _mixed_at_opening()
    n = len(sim.received)
    p.script[C.GO] = "back"                  # the repair's own question: Not now
    r = p.drive(job.repair_at_start())
    assert r.reason == "person_chose_back" and sim.received[n:] == []
    job.close()                              # End measurement
    assert sim.received[n:] == []


def test_mixed_answers_try_sends_the_recorded_repair_and_ends_the_sitting():
    job, sim, p = _mixed_at_opening()
    n = len(sim.received)
    r = p.drive(job.repair_at_start())
    assert r.ok, (r.kind, r.reason, r.detail)
    gos = [a for a in p.asked if a[1] == C.GO]
    assert len(gos) == 1 and gos[0][2]["f4_mixed"] is True and gos[0][3] == n
    assert sim.received[n:] == REPAIR
    assert job.at_rest() and sim.mode == "00"
    # the sitting began in a state ChromIQ does not know: it ends; nothing else may run
    assert job.state().sending_closed and job.park().kind != J.Kind.OK
    job.close()
    # the next START reads the table afresh and is an ordinary one
    job2, sim2, _t = H.make_job(sim=sim)
    p2 = H.Person(job2, sim2)
    r2 = p2.drive(job2.open())
    assert r2.ok and not r2.detail.get("aiming_mode_left_on")
    assert p2.drive(job2.park()).ok and sim.violations == []


def test_mixed_answers_with_the_guidance_off_are_still_asked():
    job, sim, p = _mixed_at_opening()
    job.guided = False
    r = p.drive(job.repair_at_start())
    assert r.ok and [a for a in p.asked if a[1] == C.GO] and job.countdowns == []


def test_mixed_answers_a_failed_try_says_so():
    job, sim, p = _mixed_at_opening()
    sim.inject("status", "i1", 3)
    r = p.drive(job.repair_at_start())
    assert r.kind == J.Kind.STOPPED and job.start_homing_failed
    assert job.state().sending_closed


def test_mixed_answers_after_the_start_up_offer_the_repair():
    job, sim, _t = H.make_job(cold=True, real_table=False)
    sim.mode = "01"
    sim.i0_after = (1102.0, 27.0)
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    sim.inject_at(len(sim.received) + 3, "free")     # i0, s0, f4, [f4 differs]
    r = p.drive(job.start_up())
    assert r.kind == J.Kind.STOPPED and r.reason == "mode_flag_unexpected"
    assert _moves(sim.received) == [";i02c"]
    assert r.way_back == J.WayBack.REPAIR_AT_START
    n = len(sim.received)
    r = p.drive(job.repair_at_start())
    assert r.ok and sim.received[n:] == REPAIR and job.at_rest()


@pytest.mark.parametrize("a0", ["121800", "711800", "001800"])
def test_an_unknown_a0_of_the_switched_on_family_is_offered_the_start_up(a0):
    job, sim, _t = H.make_job(cold=True, real_table=False)
    sim.a0_override = a0
    sim.i0_after = (1102.0, 27.0)
    job.guided = False                       # asked all the same
    p = H.Person(job, sim, {C.START_UP: "i1profiler"})       # the page's "Not now"
    r = p.drive(job.open())
    assert r.ok and r.detail["table"] == "cold" and job._table.a0_unknown
    n = len(sim.received)
    r = p.drive(job.start_up())
    asks = [a for a in p.asked if a[1] == C.START_UP]
    assert asks and asks[-1][2]["a0_unknown"] == a0
    assert r.kind != J.Kind.OK and sim.received[n:] == []      # Not now: nothing sent
    job2, sim2, _t = H.make_job(sim=sim)
    p2 = H.Person(job2, sim2)
    assert p2.drive(job2.open()).ok
    n = len(sim.received)
    r = p2.drive(job2.start_up())
    assert r.ok and sim.received[n] == ";i02c"


@pytest.mark.parametrize("a0", ["123456", "130001", "541900"])
def test_any_other_unknown_a0_stays_a_refusal(a0):
    job, sim, _t = H.make_job(real_table=False)
    sim.a0_override = a0
    r = H.Person(job, sim).drive(job.open())
    assert r.kind == J.Kind.STOPPED and r.reason == "table_state_unknown"
    assert len(sim.received) == 6 and not _moves(sim.received)


def test_the_window_offers_the_try_after_mixed_answers(qtbot, monkeypatch, tmp_path, settings):
    from tests.i1io_table.test_window import open_window
    from tests.i1io_table.window_sim import WindowSim
    from workflow import measurement_messages as M
    sim = WindowSim(table_faults=[("free", "f4")])
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sim=sim, asking=False)
    assert p.drive_until(("stopped", "refused", "done")) == "stopped"
    assert p.labels() == ["End measurement", "Try to bring the arm home"]
    assert "does not know this state" in win._text.text()
    p.press("Try to bring the arm home")
    assert p.page() == "repair_at_start"
    assert win._title.text() == M.M_I1IO_DRIVE_REPAIR_MIXED.render()[0]
    assert p.labels() == ["Not now", "Bring the arm home, my hands are away"]
    p.press("Not now")
    assert p.labels() == ["End measurement", "Try to bring the arm home"]
    assert not _moves(sim.sim.received)
    p.press("Try to bring the arm home")
    p.press("Bring the arm home, my hands are away")
    p.idle()
    assert p.page() == "home_after_stop_done" and p.labels() == ["End measurement"]
    assert sim.jobs[-1].at_rest() and sim.sim.violations == []


from tests.i1io_table.test_window import settings  # noqa: E402,F401  (the fixture)


def test_the_window_says_the_unknown_answer_on_the_start_up_page(qtbot, monkeypatch, tmp_path,
                                                                settings):  # noqa: F811
    from tests.i1io_table.test_window import open_window
    from tests.i1io_table.window_sim import WindowSim
    from workflow import measurement_messages as M

    class Unknown(WindowSim):
        def factory(self, *a, **k):
            job = super().factory(*a, **k)
            self.sim.a0_override = "121800"
            return job
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sim=Unknown(cold=True), asking=False)
    assert p.drive_until(("start_up",)) == "start_up"
    text = win._text.text()
    assert M.M_I1IO_DRIVE_START_UP_UNKNOWN.render(a0="121800")[1] in text
    assert "Not now" in p.labels() and not _moves(sim.sim.received)
    p.press("Not now")
    p.idle()
    assert not _moves(sim.sim.received)
