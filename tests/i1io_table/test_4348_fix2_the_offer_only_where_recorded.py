"""Safety review 448, NOTE 1: the homing AFTER A STOP is offered only inside the envelope of the
recorded homings from a held arm out on the table (``HOME_AFTER_STOP_AREA``: X -1438..1179,
Y 1202..2560, 16 homings in 9 recordings), not in the whole of 4.3.47's wider region
(``homing_starts_here``: the measuring area's raw box, the home line near rest, held in the front
zone up to its cap), which stays the rule for the usual homing, unchanged."""
from __future__ import annotations

import pytest

from tests.i1io_table.test_job_reading import job_for
from workflow.i1io.table import job as J

#: the recorded held starts (job.HOME_AFTER_STOP_AREA's comment), each must be offered
RECORDED = [(-1314, 1643), (-1285, 1757), (-1263, 1785), (1169, 2560), (-1088, 1636),
            (1172, 1663), (1176, 2120), (1179, 1665), (-1352, 1646), (-1311, 2181),
            (-1307, 2182), (-1343, 1864), (1102, 1202)]
#: recorded, but 3-4 units beyond the measuring area's raw box: 4.3.47's homing refuses there
BEYOND_THE_RAW_BOX = [(-1437, 1794), (-1438, 1868)]
#: inside 4.3.47's region, outside every recorded start: never offered
NOT_RECORDED = [(1300, 1600), (1700, 2000), (0, 2700), (0, 3000), (0, 1100), (0, 600),
                (1180, 1600), (0, 2561), (-1000, 1201)]


def _stopped_at_the_homing(tmp_path, pos):
    """As the 4.3.48 tests' helper, with the simulated readings exact (no jitter), so a start on
    the envelope's edge reads on it."""
    job, sim, helper, run, p = job_for(tmp_path, None, real_table=False)
    sim.jitter = False
    assert job.set_options(["-N"]).ok
    sim.pos = [float(pos[0]), float(pos[1])]
    assert p.drive(job.open()).ok
    r = p.drive(job.align())
    assert r.kind == J.Kind.STOPPED, (r.kind, r.reason)
    assert job._table.closed_reason.startswith("right before the homing: the arm reports")
    return job, sim, p, r


def test_the_envelope_is_the_recorded_starts_inside_the_raw_box():
    xs, ys = [p[0] for p in RECORDED], [p[1] for p in RECORDED]
    a = J.HOME_AFTER_STOP_AREA
    assert (a.xmax, a.ymin, a.ymax) == (max(xs), min(ys), max(ys))
    assert a.xmin == J.geo.AREA_RAW.xmin == -1434 > max(p[0] for p in BEYOND_THE_RAW_BOX)


@pytest.mark.parametrize("pos", BEYOND_THE_RAW_BOX)
def test_the_two_starts_beyond_the_raw_box_stay_refused(tmp_path, pos):
    assert not J.homing_starts_here(pos, False)
    job, sim, p, r = _stopped_at_the_homing(tmp_path, pos)
    assert r.way_back != J.WayBack.HOME_AFTER_STOP


@pytest.mark.parametrize("pos", RECORDED)
def test_offered_where_a_recorded_homing_started(tmp_path, pos):
    job, sim, p, r = _stopped_at_the_homing(tmp_path, pos)
    assert r.way_back == J.WayBack.HOME_AFTER_STOP, (pos, job._home_after_stop_why())


@pytest.mark.parametrize("pos", NOT_RECORDED)
def test_not_offered_where_no_recorded_homing_started(tmp_path, pos):
    assert J.homing_starts_here(pos, False)          # 4.3.47's wider region holds it
    job, sim, p, r = _stopped_at_the_homing(tmp_path, pos)
    assert r.way_back != J.WayBack.HOME_AFTER_STOP
    n = len(sim.received)
    res = job.home_after_stop()
    assert (res.kind, res.reason) == (J.Kind.REFUSED, "homing_not_from_here")
    assert sim.received[n:] == []


def test_the_fresh_reading_before_the_homing_is_checked_against_the_envelope(tmp_path):
    """Offered at the edge; by the GO the arm reads 3 units beyond it (within the 5-unit held
    re-read, so not a doubt): the homing line is not sent."""
    job, sim, p, r = _stopped_at_the_homing(tmp_path, (1179, 1700))
    assert r.way_back == J.WayBack.HOME_AFTER_STOP
    sim.pos = [1182.0, 1700.0]
    n = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert res.reason == "homing_only_from_inside_the_area", (res.kind, res.reason)
    assert ";i12b" not in sim.received[n:]
    assert job._table.closed_reason is not None
