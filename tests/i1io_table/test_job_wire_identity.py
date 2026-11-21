"""WIRE IDENTITY: for every stage the tester has (open, start-up, park inside the way out, the
alignment, the creep, the check move, the homing, the close), the table job sends byte for byte
what tester 0.6.0's part C sends in the same situation.

The tester's lines were captured from tester 0.6.0 itself on its own simulator
(``data/tester_060_part_c_wire.json``; the capture tool is in the step 6 work folder), for 285
sittings: the warm and the cold table, two recorded i1Profiler alignments with the creep and
with "back", nine wrong alignments, four fault kinds at every line of the warm sitting, and a
cancel (the tester's Ctrl-C) at every line. The job runs the same sittings here, on the app's
copy of the simulator."""
from __future__ import annotations

import hashlib
import json

import pytest

from tests.i1io_table import job_wire_cases as W
from tests.i1io_table import must1_wire as M1
from tests.i1io_table.job_harness import HERE



@pytest.fixture(autouse=True)
def _tester_060s_free_arm_region(monkeypatch):
    """4.3.53 fix round 2 (the re-review's ruling): the job homes a FREE arm from anywhere but
    the back strip; tester 0.6.0 homed it only inside the measuring area's raw box. For the
    comparison with the tester's wire the job holds the tester's region here
    (tests/i1io_table/test_4353_fix_round.py pins the new rule and its lines)."""
    from workflow.i1io.table import geometry as _geo
    from workflow.i1io.table import job as _J
    from workflow.i1io.table import session_table as _tbl
    real = _J.homing_starts_here

    def tester_rule(p, arm_free, cap_y=None):
        import sys as _sys
        # the tester read the free arm afresh (s0 p0) and THEN refused: only the homing's own
        # check (_end_of_job) is the tester's; the step's early check stays the job's
        if p is not None and arm_free is not False and \
                _sys._getframe(1).f_code.co_name == "_end_of_job":
            return _geo.AREA_RAW.contains(p) or _tbl.START_GUARD.contains(p)
        return real(p, arm_free, cap_y)
    monkeypatch.setattr(_J, "homing_starts_here", tester_rule)


@pytest.fixture(autouse=True)
def _tester_060s_four_f4(monkeypatch):
    """4.3.53 fix round (inventory B15): the job sends two f4 after the aims, as i1Profiler
    does; tester 0.6.0 sent four. For the comparison with the tester's wire the job holds
    the tester's four here (test_4353_fix_round pins the two)."""
    from workflow.i1io.table import job as _J
    monkeypatch.setattr(_J, "F4_AFTER_AIMS", 4)

@pytest.fixture(autouse=True)
def _first_time_on_new_ground(monkeypatch):
    """4.3.53 fix round (inventory A8): ground this table's reach record already holds no
    longer gets the guided first-visit question (TableJob._known_ground). The tests in this
    file are about what happens AT and AROUND a first-visit question (or compare the wire with
    tester 0.6.0, which asked it), so they keep the first time on new ground everywhere;
    tests/i1io_table/test_4353_first_visit_once.py proves the new rule."""
    from workflow.i1io.table import job as _J
    monkeypatch.setattr(_J.TableJob, "_known_ground", lambda self, p: False)

TESTER = json.loads((HERE / "data" / "tester_060_part_c_wire.json").read_text(encoding="utf-8"))
CASES = W.cases()
#: 4.3.49 (Basti's ruling: the targets are bounded by the area the person aimed at, with the
#: plan's run-out, no longer by the frontmost recorded aim Y 3109): in this sitting the sheet's
#: frontmost target is a row end at Y 3110, which the old cap left out, so the creep's last step
#: goes to Y 3110 instead of 3109 (one unit, 0.1 mm). Every other line is the tester's.
CHANGED_IN_4349 = {"C R1 401.6 d1 dz d2 f": {60: (";m004f40c25012c3a", ";m004f40c26012c39")}}


def test_every_captured_sitting_has_a_job_case():
    assert set(CASES) == set(TESTER["sittings"])
    assert len(CASES) == 285


@pytest.mark.parametrize("asking", [True, False], ids=["asking mode", "not asking"])
@pytest.mark.parametrize("name", sorted(CASES))
def test_the_job_sends_what_tester_060_sends(name, asking):
    """Both modes of the owner's ruling: asking after each step (the person answers "as
    described" every time, as the tester's automatic person did) and not asking."""
    got, results, sim = W.job_lines(CASES[name], ask_after_each_step=asking)
    # 4.3.47 MUST-1: the job's extra position queries after a question, each checked, out
    if "must1" in CASES[name]:
        assert sim.job.reads_after_question == list(CASES[name]["must1"])
    got = M1.without_must1(got, sim.job)
    want = TESTER["sittings"][name]
    if name in CHANGED_IN_4349:
        want = list(want)
        for i, (old, new) in CHANGED_IN_4349[name].items():
            assert want[i] == old
            want[i] = new
    if isinstance(want, list):
        assert got == want
    else:
        assert len(got) == want["lines"]
        assert hashlib.sha256("\n".join(got).encode()).hexdigest() == want["sha256"]
    assert sim.violations == []
