# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""4.3.53 fix round, inventory A8 (guided mode) and C10 (the pause after every patch).

A8: until the fix round the guided "first visit" question came at almost every row of every
sitting on the owner's sheet: it asked whenever a row left the boxes where the RECORDINGS drove
the arm, never what this table had shown. Now ground this table's reach record holds counts as
visited: the question is asked once per table for new ground (first-time care ends), and a
second sitting on the same table asks none. On the wire the new sitting is the old one minus
the fresh position reading (p0) the job takes after every question (4.3.47 MUST-1): a subset.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import test_4353_rows_where_the_sheet_lies as R
from workflow.i1io.table import job as J
from workflow.i1io.table import reach as rc


def _guided(tmp_path, store, args=R.SPOT, **kw):
    # jitter off: the simulated readings are then exactly where the arm stands (with it on,
    # the +-1 unit a reading gets depends on how many readings came before, so one sitting
    # with fewer readings could land an arrival "beside" and repeat a move)
    return R._job(tmp_path, R.HIS_AIMS, args=args, store=store, guided=True,
                  sight_offset=R.HIS_SIGHT, jitter=False, **kw)


def _asked(p, kind):
    return sum(1 for _s, c, *_r in p.asked if c == kind)


def _is_subsequence(small, big):
    it = iter(big)
    return all(any(x == y for y in it) for x in small)


@pytest.mark.parametrize("args", [R.SPOT, R.STRIP], ids=["patch by patch", "rows"])
def test_the_first_visit_question_is_asked_once_per_table_then_never(tmp_path, monkeypatch,
                                                                      args):
    store = rc.MemoryReachStore()
    job, sim, helper, p = _guided(tmp_path / "1", store, args)
    R._read_all(job, p)
    first = _asked(p, J.Confirm.FIRST_VISIT)
    assert first <= 1, first                       # new ground, once
    motor_front = job.reach.motor_front_y
    job.close()
    # the second sitting on the same table: no first-visit question at all
    job2, sim2, helper2, p2 = _guided(tmp_path / "2", store, args,
                                      motors_have_been_to=motor_front)
    R._read_all(job2, p2)
    assert _asked(p2, J.Confirm.FIRST_VISIT) == 0
    assert sim2.violations == []
    new_wire = list(sim2.received)
    job2.close()
    # the same second sitting with the rule of 4.3.52 (only the recorded boxes count)
    monkeypatch.setattr(J.TableJob, "_known_ground", lambda self, q: False)
    job3, sim3, helper3, p3 = _guided(tmp_path / "3", store, args,
                                      motors_have_been_to=motor_front)
    R._read_all(job3, p3)
    old = _asked(p3, J.Confirm.FIRST_VISIT)
    assert old > first, (old, first)               # almost every row, every sitting before
    old_wire = list(sim3.received)
    # the wire: a subset of 4.3.52's, and what is missing is only position readings
    assert _is_subsequence(new_wire, old_wire)
    missing = len(old_wire) - len(new_wire)
    assert missing == sum(1 for ln in old_wire if ln.startswith(";p0")) - \
        sum(1 for ln in new_wire if ln.startswith(";p0"))
    assert {ln[1:3] for ln in new_wire} <= {ln[1:3] for ln in old_wire}


def test_the_back_strip_is_never_known_ground():
    from workflow.i1io.table import geometry as geo
    job = J.TableJob.__new__(J.TableJob)
    job.reach = rc.Reach(key=None, front_y=3300, right_end_x=-1600)
    assert not job._known_ground((1100, geo.AREA_RAW.ymin - 1))
    assert job._known_ground((1100, geo.AREA_RAW.ymin + 1))
    assert not job._known_ground((-1700, 2000))         # beyond the right that was reached
    assert not job._known_ground((0, 3301))             # beyond the front that was reached
