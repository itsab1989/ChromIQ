"""4.3.52: with -N the alignment's own homing finds the arm out: it is brought home from anywhere
(replaces test_4348_fix2_the_offer_only_where_recorded.py).

4.3.48 (safety review 448, NOTE 1) offered the homing after this stop only inside the envelope of
i1Profiler's recorded homings of a held arm (HOME_AFTER_STOP_AREA, X -1434..1179, Y 1202..2560),
and 4.3.51 added a "try" around it; the two recorded starts 3-4 units beyond the raw box stayed
refused. Since 4.3.52 (the owner's ruling of 2026-11-20) the place decides nothing but the back
strip: every recorded start, every place beyond them, and the two beyond the raw box get the same
recorded lines, after the one question, and the alignment goes on from rest.
"""
from __future__ import annotations

import pytest

from tests.i1io_table.test_4352_start_rule_by_state import F1_PLUS
from tests.i1io_table.test_job_reading import job_for
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl

#: the recorded held starts (4.3.48's HOME_AFTER_STOP_AREA comment), each must be brought home
RECORDED = [(-1314, 1643), (-1285, 1757), (-1263, 1785), (1169, 2560), (-1088, 1636),
            (1172, 1663), (1176, 2120), (1179, 1665), (-1352, 1646), (-1311, 2181),
            (-1307, 2182), (-1343, 1864), (1102, 1202)]
#: recorded, but 3-4 units beyond the measuring area's raw box: refused until 4.3.51
BEYOND_THE_RAW_BOX = [(-1437, 1794), (-1438, 1868)]
#: no recorded start: a "try" in 4.3.51, or refused (the front beyond Y 3114, the alignment start)
NOT_RECORDED = [(1300, 1600), (0, 2700), (0, 3000), (0, 600), (0, 3300), (2507, 1429)]


def _stopped_at_the_homing(tmp_path, pos):
    job, sim, helper, run, p = job_for(tmp_path, None, real_table=False)
    sim.jitter = False
    assert job.set_options(["-N"]).ok
    sim.pos = [float(pos[0]), float(pos[1])]
    assert p.drive(job.open()).ok
    n = len(sim.received)
    r = p.drive(job.align())
    return job, sim, p, r, n


@pytest.mark.parametrize("pos", RECORDED + BEYOND_THE_RAW_BOX + NOT_RECORDED)
def test_brought_home_and_the_alignment_goes_on(tmp_path, pos):
    job, sim, p, r, n = _stopped_at_the_homing(tmp_path, pos)
    assert r.ok, (pos, r.kind, r.reason, r.detail)
    sent = sim.received[n:]
    # the alignment's own check (s0 p0, the arm out), the START homing, then its own homing again
    assert sent[:2] == [";s022", ";p025"]
    # 2026-11-21: from the far side (X beyond 1281) the vendor's detour to the home line first
    from workflow.i1io.table import geometry as geo
    if geo.homing_detour(pos):
        sent = sent[:4] + sent[6:]
        assert sim.received[n:][4:6] == [";m0044e05da00c806", ";p025"], sim.received[n:n + 8]
    assert sent[2:7] == F1_PLUS, sent[:12]
    assert sent[7:11] == [";s022", ";p025", ";i12b", ";s022"]
    gos = [a for a in p.asked if a[1] == J.Confirm.GO and a[2].get("step") == "home_at_start"]
    assert len(gos) == 1
    assert job.alignment is not None and sim.violations == []


def test_the_fresh_reading_before_the_homing_is_checked(tmp_path):
    """Found out, then moved by a hand while the question was shown: nothing moves."""
    def moved(person, res):
        if res.confirm == J.Confirm.GO and res.detail.get("step") == "home_at_start":
            person.sim.pos = [person.sim.pos[0] + 40.0, person.sim.pos[1]]
    job, sim, helper, run, p = job_for(tmp_path, None, real_table=False)
    p.on_ask = moved
    assert job.set_options(["-N"]).ok
    sim.pos = [1179.0, 1700.0]
    assert p.drive(job.open()).ok
    r = p.drive(job.align())
    assert r.kind == J.Kind.STOPPED and r.reason == "arm_moved_before_homing", r.reason
    assert ";i12b" not in sim.received
    assert job._table.closed_reason is not None
    assert not tbl.REST_GUARD.contains(job._table.position_now)
