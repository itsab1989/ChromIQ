"""4.3.50 fix round, MUST-2 (independent review of 20 Nov 2026): THE FIRST STRIP ROW STARTS FROM
THE FREE ARM, and every guard on that path has a test of its own.

With the mark-3 check move gone, row 1 of a page read as strips (and as dual strips) starts right
after the aims, from the arm the person has just aimed by hand. 4.3.49 never sent a strip row
this way (its rows started after the check move, from a held arm), and the only guard in front of
the first motor move that is about a hand on the arm, scan.run_row's two-reading stillness check,
had no test: the reviewer removed it and every test stayed green.

The wire, compared with 4.3.49 (work notes of the fix round, first_row_wire.txt):
  4.3.49: GO, p0 p0 (D2's pair), first visit, p0, m0 to mark 3, p0, first visit (row), p0, c4,
          p0, m0 to the row start, d1, p0, m2 ...
  4.3.50: GO, p0 (where the free arm is), first visit (row), p0 p0 (run_row's pair), c4, p0,
          m0 to the row start, d1, p0, m2 ...
  i1Profiler's own strip sittings (18 Nov, after the third aim, the arm free): p0, c4, p0, m0 to
          the row start at 300, d1, p0, m2 ...
So the first motor move from the free arm is the m0 at 300 to the row start, the move i1Profiler
itself sends from the free arm in both of its recorded strip sittings; the scan move (m2) only
follows once the motors have taken the arm to the row start and it was read there.

What these tests pin, for a single strip row and for a dual row:
* nothing is sent before the hands-off GO, and "back" there sends nothing;
* the free arm is read before the first-visit question judges the way to the row start, and a
  "No" there moves nothing;
* a hand that moves the free arm between the two readings right before the first motor move:
  no c4, no m0, a clean failure the person can answer (and a new GO before the row is read
  again);
* a free arm that was moved (and held still) after the first-visit answer: the way from its new
  place is not the way that was confirmed, so nothing moves;
* the instrument's lights-off failing there: a clean failure, nothing moved;
* the shape: the first motor line is m0 at 300 to the row start, m2 only after d1 and a reading
  at the start, and there are two readings of the free arm after the last question before it.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_dual_table import dual_setup, long_sheet
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J


@pytest.fixture(autouse=True)
def _first_time_on_new_ground(monkeypatch):
    """4.3.53 fix round (inventory A8): ground this table's reach record already holds no
    longer gets the guided first-visit question (TableJob._known_ground). The tests in this
    file are about what happens AT and AROUND a first-visit question (or compare the wire with
    tester 0.6.0, which asked it), so they keep the first time on new ground everywhere;
    tests/i1io_table/test_4353_first_visit_once.py proves the new rule."""
    from workflow.i1io.table import job as _J
    monkeypatch.setattr(_J.TableJob, "_known_ground", lambda self, p: False)

STRIP_ARGS = ["-v", "-c", "1", "chart"]          # no -p: strip rows
MOVES = ("m0", "m1", "m2", "i0", "i1")
KINDS = ["strip", "dual"]


def _job(tmp_path, kind, faults=None, script=None):
    kw = {}
    if kind == "dual":
        sheet = long_sheet()
        kw = {"sheet": sheet, "aims": H.demo_aims(sheet)}
    job, sim, helper, _run = RS.make_reading_job(tmp_path, faults=faults,
                                                 ask_after_each_step=False, **kw)
    if kind == "dual":
        job.dual = dual_setup("M2")
    assert job.set_options(STRIP_ARGS).ok
    p = H.Person(job, sim, script)
    for s in ("open", "calibrate", "align"):
        r = p.drive(getattr(job, s)())
        assert r.ok, (s, r.reason, r.detail)
    assert job.front_need is None and job.state().arm_free is True
    return job, sim, p


def _cids(sim, since):
    return [ln[1:3] for ln in sim.received[since:]]


def _no_motion(sim, since):
    return not [c for c in _cids(sim, since) if c in MOVES]


@pytest.mark.parametrize("kind", KINDS)
def test_row_one_from_the_free_arm_is_read_and_its_first_motor_move_is_the_travel_to_the_start(
        tmp_path, kind):
    job, sim, p = _job(tmp_path, kind)
    k, n = len(p.asked), len(sim.received)
    r = p.drive(job.read_row())
    assert r.ok and r.detail.get("row_kind") == "strip", (r.reason, r.detail)
    asked = [(a[0], a[1], a[3]) for a in p.asked[k:]]
    # the hands-off GO first, with nothing sent before it
    assert asked[0] == ("read_row", J.Confirm.GO, n)
    last_q = max(a[2] for a in asked)
    sent = _cids(sim, n)
    first_motor = next(i for i, c in enumerate(sent) if c in MOVES)
    assert sent[first_motor] == "m0"
    # two readings of the free arm after the last question, before the first motor move
    assert sent[last_q - n:first_motor].count("p0") >= 2
    line = sim.received[n + first_motor]
    _c, x, y, v = geo.decode_xyv(line.encode())
    plan = J.sp.plan_row(job.sheet, job.page, 0, job.alignment, job._table.front_y,
                         cap_y=job._cap(), kind="strip").scan
    assert (x, y) == tuple(plan.start) and v == 300
    # the scan move only after d1 and a reading at the row start
    first_m2 = sent.index("m2")
    assert sent[first_motor + 1:first_m2] == ["d1", "p0"]
    assert sim.violations == []


@pytest.mark.parametrize("kind", KINDS)
def test_back_at_the_go_sends_nothing(tmp_path, kind):
    job, sim, p = _job(tmp_path, kind, script={J.Confirm.GO: "back"})
    n = len(sim.received)
    r = p.drive(job.read_row())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "person_chose_back")
    assert sim.received[n:] == []


@pytest.mark.parametrize("kind", KINDS)
def test_the_free_arm_is_read_before_the_first_visit_and_no_there_moves_nothing(tmp_path, kind):
    job, sim, p = _job(tmp_path, kind, script={J.Confirm.FIRST_VISIT: "no"})
    k, n = len(p.asked), len(sim.received)
    r = p.drive(job.read_row())
    assert r.kind == J.Kind.REFUSED and r.reason == "first_visit_declined", (r.kind, r.reason)
    fv = [a for a in p.asked[k:] if a[1] == J.Confirm.FIRST_VISIT]
    assert fv and fv[0][3] == n + 1
    # after the "No" nothing at all is sent (not even the reader's own readings of the arm):
    # the step ends at the answer, with no row failure to answer
    assert _cids(sim, n) == ["p0"]
    assert J.Confirm.ROW_FAILED_STRIP not in [a[1] for a in p.asked[k:]]


def _hand_at_pair(sim, job, where, second: bool):
    """The person's hand moves the free arm right when ChromIQ reads it for the stillness pair
    (the second reading of the pair, or the first: then both readings see the new place)."""
    state = {"after": None, "p0": 0, "done": False}

    def on_command(index):
        if state["done"] or state["after"] is None or index < state["after"]:
            return
        if sim.received[index][1:3] == "p0":
            state["p0"] += 1
            if state["p0"] == (2 if second else 1):
                sim.hand_to(*where)
                state["done"] = True
    sim.on_command = on_command
    return state


@pytest.mark.parametrize("kind", KINDS)
def test_a_hand_on_the_free_arm_between_the_two_readings_stops_it_before_any_move(tmp_path, kind):
    """MUST-2: scan.run_row's two-reading stillness check, the guard the review removed with all
    tests green. The arm moved 3 mm between the two readings: nothing moves, the row fails
    cleanly, and reading it again asks the hands-off GO first."""
    job, sim, p = _job(tmp_path, kind, script={J.Confirm.ROW_FAILED_STRIP: "stop"})
    here = list(sim.pos)
    state = _hand_at_pair(sim, job, (here[0] + 30, here[1]), second=True)
    k, n = len(p.asked), len(sim.received)

    def arm_the_hand(person, res):
        if res.confirm == J.Confirm.FIRST_VISIT:
            state["after"] = len(sim.received)
        return None
    p.on_ask = arm_the_hand
    r = p.drive(job.read_row())
    assert state["done"], "the hand never moved the arm (the test did not reach the pair)"
    assert _no_motion(sim, n), _cids(sim, n)
    assert "c4" not in _cids(sim, n)
    failed = [a for a in p.asked[k:] if a[1] == J.Confirm.ROW_FAILED_STRIP]
    assert failed, [a[1] for a in p.asked[k:]]
    assert r.reason == "stopped_after_a_failed_row", (r.kind, r.reason)
    assert sim.violations == []


@pytest.mark.parametrize("kind", KINDS)
def test_reading_the_row_again_after_the_hand_asks_go_and_reads_the_pair_again(tmp_path, kind):
    job, sim, p = _job(tmp_path, kind, script={J.Confirm.ROW_FAILED_STRIP: "again"})
    here = list(sim.pos)
    state = _hand_at_pair(sim, job, (here[0] + 30, here[1]), second=True)

    def arm_the_hand(person, res):
        if res.confirm == J.Confirm.FIRST_VISIT and state["after"] is None:
            state["after"] = len(sim.received)
        return None
    p.on_ask = arm_the_hand
    k = len(p.asked)
    r = p.drive(job.read_row())
    assert state["done"]
    kinds = [a[1] for a in p.asked[k:]]
    i = kinds.index(J.Confirm.ROW_FAILED_STRIP)
    assert J.Confirm.GO in kinds[i + 1:]
    at_go = [a[3] for a in p.asked[k + i + 1:] if a[1] == J.Confirm.GO][0]
    sent = _cids(sim, at_go)
    first_motor = next(j for j, c in enumerate(sent) if c in MOVES)
    assert sent[:first_motor].count("p0") >= 2
    assert r.ok, (r.reason, r.detail)
    assert sim.violations == []


@pytest.mark.parametrize("kind", KINDS)
def test_an_arm_moved_after_the_first_visit_answer_is_not_driven_from_its_new_place(
        tmp_path, kind):
    """The arm was pushed (and held still) after the person confirmed the way from where it was:
    the way from its new place was not confirmed, so the row fails cleanly before any move."""
    job, sim, p = _job(tmp_path, kind, script={J.Confirm.ROW_FAILED_STRIP: "stop"})
    state = _hand_at_pair(sim, job, (1500.0, 600.0), second=False)

    def arm_the_hand(person, res):
        if res.confirm == J.Confirm.FIRST_VISIT:
            state["after"] = len(sim.received)
        return None
    p.on_ask = arm_the_hand
    n = len(sim.received)
    p.drive(job.read_row())
    assert state["done"]
    assert _no_motion(sim, n), _cids(sim, n)
    assert sim.violations == []


@pytest.mark.parametrize("kind", KINDS)
def test_the_lights_off_failing_there_is_a_clean_failure_and_nothing_moves(tmp_path, kind):
    faults = {"scan": {"lights_err": True}, "scan_at": 2}
    if kind == "dual":
        pytest.skip("the dual row's lamp pass has its own lights-off (DualPass), pinned in "
                    "test_dual_table; the free-arm order before it is the same lines")
    job, sim, p = _job(tmp_path, kind, faults=faults,
                       script={J.Confirm.ROW_FAILED_STRIP: "stop"})
    n = len(sim.received)
    p.drive(job.read_row())
    assert _no_motion(sim, n) and "c4" not in _cids(sim, n)
