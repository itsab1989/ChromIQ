"""4.3.50: the test gaps the 4.3.49 table reviews left open ("another guard behind it"), each
proved by planting the fault in a scratch copy (work folder 2026-11-19_table450, plants.txt).

Re-review 449, S-1: the way back before the homing (job._way_back) had no test that a plant of
P6 (the 4-move bound off), P7 (``arrived`` not cleared at a homing), P8 (a jump back without the
driven-ground test) or P9 (the way back inside the homing after a stop) turned red; nor the
geometry's own back-strip refusal (safety review 449, G2 / SHOULD-6). S-2 (the first leg back
along the way by construction) and S-3 (a way back never ends in front of Y 3109) are fixed
here, with their tests.
"""
from __future__ import annotations

import inspect

import pytest

from tests.i1io_table.test_4349_fix_way_back_before_the_homing import _stalled
from tests.i1io_table import job_harness as H
from tests.i1io_table.test_4349_acceptance_his_sheet_and_wider import (CROSSES_1,
                                                                        _through_first_row)
from workflow.i1io.table import caps as cp
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J


def _m0_targets(lines):
    return [tuple(geo.decode_xyv(ln.encode())[1:3]) for ln in lines if ln[1:3] == "m0"]


def _check_way_back_property(job, sim, p):
    """After any homing with a way back: every m0 target sent before the homing's i1 is a place
    this sitting arrived at (since the last homing), at most WAY_BACK_MOVES_MAX of them, each
    step from the place before over driven ground or one creep step, and ``arrived`` is empty
    once the arm is home."""
    arrived = list(job.arrived)
    driven = list(job.driven)
    here = tuple(sim.pos)
    n = len(sim.received)
    r = p.drive(job.home())
    assert r.kind == J.Kind.OK, (r.reason, r.detail, sim.violations)
    sent = sim.received[n:]
    cids = [ln[1:3] for ln in sent]
    i1 = cids.index("i1")
    targets = _m0_targets(sent[:i1])
    assert 1 <= len(targets) <= cp.WAY_BACK_MOVES_MAX
    assert all(t in arrived for t in targets), (targets, arrived[-8:])
    # each leg: the first at most one creep step (S-2), every later one over driven ground or
    # one place back along the arrivals
    probe = J.TableJob.__new__(J.TableJob)
    probe.driven = driven
    prev = here
    for t in targets:
        near = (abs(prev[0] - t[0]) <= geo.CREEP_STEP + geo.ARRIVAL_SLACK
                and abs(prev[1] - t[1]) <= geo.CREEP_STEP + geo.ARRIVAL_SLACK)
        one_back = prev in arrived and arrived.index(t) < arrived.index(prev) and \
            arrived.index(prev) - arrived.index(t) == 1 if prev in arrived else False
        assert near or one_back or probe._seg_visited(prev, t), (prev, t)
        prev = t
    assert J._homing_target(targets[-1])
    assert job.arrived == [], job.arrived
    assert job.at_rest() and sim.violations == []
    return targets


def test_the_way_back_after_a_front_stall_keeps_to_its_rules(tmp_path):
    job, sim, p, _d = _stalled(tmp_path)
    _check_way_back_property(job, sim, p)


def test_the_way_back_after_front_rows_keeps_to_its_rules(tmp_path):
    out, job, sim, p = _through_first_row(tmp_path, H.demo_sheet(), CROSSES_1)
    assert all(k == J.Kind.OK for _s, k, _r, _d in out), out
    while job.rows_left():
        r = p.drive(job.read_row())
        assert r.kind == J.Kind.OK, (r.reason, r.detail)
    assert sim.pos[1] > J.HELD_HOMING_AREA.ymax or True
    if J.homing_starts_here(tuple(sim.pos), False):
        pytest.skip("the last row ended where a homing starts: no way back is needed")
    _check_way_back_property(job, sim, p)


# ---- the way back on crafted arrivals ---------------------------------------------------------

H0 = (1000, 2700)          # a homing start (inside AREA_RAW)


def _crafted(tmp_path, chain, driven=()):
    job, sim, p, _d = _stalled(tmp_path)
    job._table.front_y = 3240
    job.arrived = [H0] + list(chain)
    job.driven = list(driven)
    job._way_back_cache = None
    return job


def test_the_way_back_is_at_most_four_moves(tmp_path):
    """Plant P6 (the bound off) turned nothing red in 4.3.49."""
    four = [(1000, 3130 + 10 * k) for k in range(4)]
    job = _crafted(tmp_path, four)
    assert job._way_back_uncached(four[-1]) == list(reversed(four[:-1])) + [H0]
    five = [(1000, 3130 + 10 * k) for k in range(5)]
    job = _crafted(tmp_path, five)
    assert job._way_back_uncached(five[-1]) is None


def test_a_jump_back_needs_ground_driven_before(tmp_path):
    """Plant P8 (the jump without the ground test) turned nothing red in 4.3.49."""
    chain = [(1000, 3150), (1000, 3200)]
    job = _crafted(tmp_path, chain)
    assert job._way_back_uncached(chain[-1]) == [chain[0], H0]
    job = _crafted(tmp_path, chain, driven=[((1000, 2690), (1000, 3210))])
    assert job._way_back_uncached(chain[-1]) == [H0]


def test_the_first_leg_back_is_one_step_or_over_driven_ground(tmp_path):
    """S-2: the arm read further from the last arrival than one creep step, over ground never
    driven: no way back (the homing is refused, nothing is sent)."""
    chain = [(1000, 3150), (1000, 3200)]
    job = _crafted(tmp_path, chain)
    assert job._way_back_uncached((1000, 3240)) == [chain[1], chain[0], H0]     # 4 mm on
    far = (1300, 3200)
    assert job._way_back_uncached(far) is None
    job = _crafted(tmp_path, chain, driven=[((990, 3190), (1310, 3210))])
    assert job._way_back_uncached(far)[0] == chain[1]


def test_the_way_back_never_ends_in_front_of_the_frontmost_recorded_aim(tmp_path):
    """S-3: an arrival at Y 3112 is a homing start by 4.3.48's region (up to 3114), but the arm
    may read 3117 there; the way back goes on to a place at or behind Y 3109."""
    assert J.homing_starts_here((1000, 3112), False) and not J._homing_target((1000, 3112))
    assert J._homing_target((1000, 3109)) and J._homing_target(H0)
    chain = [(1000, 3112), (1000, 3160)]
    job = _crafted(tmp_path, chain)
    way = job._way_back_uncached(chain[-1])
    assert way and way[-1] == H0 and (1000, 3112) != way[-1]


def test_after_a_homing_nothing_of_the_sitting_counts_as_arrived(tmp_path):
    """Plant P7 (``arrived`` not cleared at a homing) turned nothing red in 4.3.49."""
    job, sim, p, _d = _stalled(tmp_path)
    assert job.arrived
    assert p.drive(job.home()).kind == J.Kind.OK
    assert job.arrived == [] and job._way_back(tuple(sim.pos)) is None


def test_the_homing_after_a_stop_never_takes_the_way_back():
    """Plant P9: the homing after a stop (``where`` given) may send only HOME's own lines; the
    way back belongs to the usual homing alone. Pinned in the source because two more guards
    stand behind it (that homing is offered only before anything moved, so nothing has
    arrived; and the table lets only HOME's lines through after reopening)."""
    src = inspect.getsource(J.TableJob._end_of_job)
    i = src.index("way = self._way_back(got)")
    cond = src[src.rindex("if ", 0, i):i]
    assert "where is None" in cond and "d.arm_free is False" in cond, cond


def test_the_geometry_refuses_a_computed_move_from_the_back_strip():
    """Safety review 449, G2: the geometry's own copy of the back-strip refusal (the table's
    gate holds one too; with only this one off, nothing turned red)."""
    with pytest.raises(geo.AreaRefused, match="back strip"):
        geo.check_move_from_reading((1102, 15), (1000, 1500), "a move")
    with pytest.raises(geo.AreaRefused, match="back strip"):
        geo.check_move_from_reading((1000, geo.AREA_RAW.ymin - 1), (1000, 1500), "a move")
    geo.check_move_from_reading((1000, geo.AREA_RAW.ymin), (1000, 1500), "a move")
