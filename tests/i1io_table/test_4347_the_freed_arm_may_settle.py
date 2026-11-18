"""The freed arm at the alignment start may settle (4.3.47, the volunteer's run of 18 Nov 2026).

ChromIQ 4.3.46 on the volunteer's i1iO 2: the calibration worked, the arm drove out to the
alignment start, m1 landed where it always lands, (2506, 1429), and after i1Profiler's lines
that let the arm go (s0 f4 f4 f3 f4 f4 f1 f4 f4) the next p0, 0.8 s later, read (2501, 1441).
Nobody had been asked to touch it. The program's check "the free arm has not moved more than
5 units" stopped the run with the arm free out on the table.

5 units is a HELD arm's arrival tolerance. i1Profiler never reads the arm between f1 and the
person's first aim, so no recording held such a pair, and the simulated table's freed arm stood
exactly where the motors had left it: no test could see the mistake. The simulator now settles
the freed arm as the real one did (RELEASE_SETTLE_REAL), and every table test drives through it.

Test data (nothing private): `;p025` -> `:$p0009CA059512` = (2506, 1429) after m1;
`;p025` -> `:$p0009C505A11A` = (2501, 1441) after f1.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import part_c_sim as csim
from tests.i1io_table import session_sim as ss
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl

M1_LINE, F1_LINE, P0 = ";m10b10055b012c42", ";f12e", ";p025"


def test_the_volunteers_two_readings_decode_to_the_measured_settling():
    held = tbl.parse_done(":$p0009CA059512", "position").xy()
    free = tbl.parse_done(":$p0009C505A11A", "position").xy()
    assert (held, free) == ((2506, 1429), (2501, 1441))
    assert ss.RELEASE_SETTLE_REAL == (free[0] - held[0], free[1] - held[1]) == (-5, 12)


def test_the_simulated_table_lets_its_arm_settle_like_the_real_one():
    assert ss.SimTable().release_settle == ss.RELEASE_SETTLE_REAL
    assert csim.CSimTable(part_c=True).release_settle == ss.RELEASE_SETTLE_REAL
    sim = ss.SimTable(jitter=False, pos=[2507.0, 1429.0])
    sim._execute(F1_LINE, "f1", "", None)
    assert sim.pos == [2502.0, 1441.0] and sim.free_arm
    sim._execute(F1_LINE, "f1", "", None)          # already free: no second settling
    assert sim.pos == [2502.0, 1441.0]


def test_the_rule_allows_settling_and_says_why():
    assert tbl.RELEASE_SETTLE_UNITS == 50
    # the measured settling is well inside; a held arm's tolerance is still the arrival one
    assert max(abs(v) for v in ss.RELEASE_SETTLE_REAL) * 4 <= tbl.RELEASE_SETTLE_UNITS
    assert tbl.AT_M1 == tbl.near(2507, 1429)
    assert tbl.STILL_UNITS == 2
    ops = [op for st in tbl.B_STEPS if st.key == "b_align" for op in st.ops
           if op[0] in ("p0still", "p0freed")]
    assert ops == [("p0freed", tbl.RELEASE_SETTLE_UNITS, "the free arm at the alignment start")]


def _align_until_felt(**simkw):
    asked = []

    def on_ask(person, res):
        asked.append(res.confirm)
        if res.confirm == J.Confirm.ARM_FELT:
            return res              # stop driving here: the alignment start was accepted
        return None
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims(), jitter=False, **simkw)
    job, sim, _t = H.make_job(sim=sim)
    person = H.Person(job, sim, on_ask=on_ask)
    assert person.drive(job.open()).ok
    res = person.drive(job.align())
    return res, job, sim, asked


def _after_m1(sim):
    i = sim.received.index(M1_LINE)
    return sim.received[i:]


@pytest.mark.parametrize("settle", [(-5.0, 12.0), (0.0, 0.0), (50.0, -50.0), (-50.0, 50.0),
                                    (5.0, -12.0), (30.0, 0.0)])
def test_a_freed_arm_that_settles_reaches_the_touch_question(settle):
    """Failed before 4.3.47 for every settling beyond 5 units, the real one included."""
    res, job, sim, asked = _align_until_felt(release_settle=settle)
    assert J.Confirm.ARM_FELT in asked, (res.kind, res.reason)
    log = "\n".join(job.diag.lines)
    assert "the free arm at the alignment start: the arm reports" in log
    assert "settled by" in log


def test_settling_changes_nothing_that_is_sent():
    """The wire up to the touch question is the same with and without the settling: one p0
    after f1, as before."""
    _r0, _j0, still, _a0 = _align_until_felt(release_settle=(0.0, 0.0))
    _r1, _j1, real, _a1 = _align_until_felt()
    assert real.received == still.received
    tail = _after_m1(real)
    assert tail[-3:] == [";f42b", ";f42b", P0] and F1_LINE in tail


@pytest.mark.parametrize("settle", [(51.0, 0.0), (0.0, -51.0), (-60.0, 70.0), (400.0, 0.0)])
def test_a_larger_shift_still_stops_and_sends_nothing_more(settle):
    """What the check is for: an arm that moved further than settling explains (the motors
    running on, or a hand) is never followed by the question that asks the person to touch it,
    and nothing more is sent after the reading."""
    res, job, sim, asked = _align_until_felt(release_settle=settle)
    assert res.kind == J.Kind.STOPPED, (res.kind, res.reason)
    assert J.Confirm.ARM_FELT not in asked
    assert sim.received[-1] == P0
    assert _after_m1(sim).count(P0) == 2
    assert job._table.closed_reason is not None
    assert res.reason == "free_arm_moved_at_the_alignment_start"
    assert tuple(job._table.outside_at) == (int(2507 + settle[0]), int(1429 + settle[1]))
