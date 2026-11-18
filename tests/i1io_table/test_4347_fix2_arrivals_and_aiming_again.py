"""4.3.47 fix2 (after the independent safety review's ranked suspects for the volunteer's next run).

Suspect 1: a refused alignment (the three-mark check) must let the person aim again at once,
without the session ending: nothing moves, the arm stays free, the next align asks GO and the
three aims again (no new way out to the alignment start).

Suspect 4: i1Profiler's own arrivals on the volunteer's table reach 5 units, the edge of the
arrival tolerance. An arrival read twice beside its target by 6..10 units (at most 1 mm) after a
move that ended normally now fails the ROW cleanly (the person may read it again, patch by patch
or skip it) instead of ending the measurement; beyond 1 mm it is a doubt, as before. Nothing new
is ever sent: "again" repeats the row's own lines from a fresh reading.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table.job_strip_wire_cases import STRIP_ARGS
from tests.i1io_table.test_job_reading import job_for
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl

MOVES = ("m0", "m1", "m2", "i1", "i0")


# ---- suspect 1: aiming again after the check refused the marks ----------------------------------
@pytest.mark.parametrize("bad", ["mark 3 one cm off", "marks 1 and 2 swapped", "turned 180"])
def test_a_refused_alignment_is_aimed_again_at_once_without_a_move(bad):
    good = H.demo_aims()
    wrong = {"mark 3 one cm off": [good[0], good[1], (good[2][0] + 100, good[2][1])],
             "marks 1 and 2 swapped": [good[1], good[0], good[2]],
             "turned 180": [good[2], (good[0][0], good[2][1]), good[0]]}[bad]
    job, sim, _t = H.make_job(aims=wrong, jitter=False)
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    r = p.drive(job.align())
    assert r.kind == J.Kind.REFUSED, (r.kind, r.reason)
    assert r.state.sending_closed is False and r.state.arm_free is True
    n = len(sim.received)
    asked = len(p.asked)
    sim.aims = list(good)
    r = p.drive(job.align())
    assert r.ok, (r.kind, r.reason)
    # no SHEET_LAID, no way out again: GO, then the three aims, then the recorded lines
    assert [a[1] for a in p.asked[asked:]] == [J.Confirm.GO] + [J.Confirm.AIMED] * 3
    assert not [ln for ln in sim.received[n:] if ln[1:3] in MOVES]
    assert p.drive(job.check_move()).ok
    assert sim.violations == []


def test_the_alignment_may_be_aimed_again_up_to_the_pages_limit():
    good = H.demo_aims()
    wrong = [good[0], good[1], (good[2][0] + 100, good[2][1])]
    job, sim, _t = H.make_job(aims=wrong, jitter=False)
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    reasons = [p.drive(job.align()).reason for _ in range(J.MAX_RUNS["d1"])]
    assert all(r.startswith("aims_") for r in reasons), reasons
    r = p.drive(job.align())
    assert r.reason == "ran_as_often_as_allowed"
    assert r.way_back == J.WayBack.HOME_OFFERED      # the homing is still offered


# ---- suspect 4: an arrival 6..10 units off fails the row cleanly ---------------------------------
def _arrive_beside(sim, after_moves: int, dx: int, dy: int, reads: int = 2):
    """The *after_moves*-th computed m0 from now lands (dx, dy) beside its target, and the next
    *reads* position readings say so (as a real table whose arm stopped a little short)."""
    orig = sim._c_execute
    st = {"m0": 0, "left": 0}

    def ex(line, cid, a, fault):
        status, data, t = orig(line, cid, a, fault)
        if cid == "m0" and line.startswith(";m0") and line not in {
                v.decode().rstrip("\r") for v in tbl.WIRE.values()}:
            st["m0"] += 1
            if st["m0"] == after_moves:
                st["left"] = reads
        elif cid == "p0" and st["left"]:
            st["left"] -= 1
            x, y = int(data[:4], 16), int(data[4:8], 16)
            x = (x - 0x10000 if x & 0x8000 else x) + dx
            y = (y - 0x10000 if y & 0x8000 else y) + dy
            data = f"{x & 0xFFFF:04X}{y & 0xFFFF:04X}"
        return status, data, t
    sim._c_execute = ex
    return st


def _ready(tmp_path, script=None, **kw):
    # the ideal table: the offsets below are the whole arrival error (no random one on top)
    job, sim, helper, run, p = job_for(tmp_path, script, real_table=False, **kw)
    sim.jitter = False
    for s in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, s)()).ok, s
    return job, sim, p


@pytest.mark.parametrize("off", [(0, -6), (7, 0), (-10, 10)])
def test_a_patch_arrival_beside_its_target_fails_the_row_and_it_is_read_again(tmp_path, off):
    job, sim, p = _ready(tmp_path, {J.Confirm.ROW_FAILED: "again"})
    seen = []
    p.on_ask = lambda person, res: seen.append((res.confirm, dict(res.detail))) and None
    _arrive_beside(sim, 2, *off)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "read", (r.reason, r.detail)
    failed = [d for c, d in seen if c == J.Confirm.ROW_FAILED]
    assert failed and failed[0]["why"] == "arrived_beside_the_target", seen
    assert job._table.closed_reason is None
    assert sim.violations == []


@pytest.mark.parametrize("off", [(0, -11), (11, 0), (0, -60)])
def test_a_patch_arrival_more_than_1_mm_off_still_ends_the_sending(tmp_path, off):
    job, sim, p = _ready(tmp_path)
    _arrive_beside(sim, 2, *off)
    n = len(sim.received)
    r = p.drive(job.read_row())
    assert r.kind == J.Kind.STOPPED, (r.kind, r.reason)
    assert job._table.closed_reason is not None
    moves = [ln for ln in sim.received[n:] if ln[1:3] in MOVES]
    assert len(moves) == 2                     # the first two patch moves, nothing after


# one reading beside and the other beyond 1 mm stays a doubt: test_ownerfix_recorded_answers
# (offsets [-6, -11] and [-11, -6])


@pytest.mark.parametrize("off,closed", [((0, 7), False), ((-9, 0), False), ((0, 12), True)])
def test_a_strip_row_start_beside_its_target(tmp_path, off, closed):
    """The row start of a strip row: within 1 mm the row fails cleanly before any scan move
    (nothing is pending) and may be read again or patch by patch; beyond, a doubt."""
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.ROW_FAILED_STRIP: "skip"},
                                       real_table=False)
    assert job.set_options(STRIP_ARGS).ok
    sim.jitter = False
    for s in ("open", "calibrate", "align", "check_move"):
        assert p.drive(getattr(job, s)()).ok, s
    seen = []
    p.on_ask = lambda person, res: seen.append((res.confirm, dict(res.detail))) and None
    # the row's own m0 to its start is the first computed m0 of the step
    _arrive_beside(sim, 1, *off, reads=1)
    n = len(sim.received)
    r = p.drive(job.read_row())
    assert not any(ln.startswith(";m2") for ln in sim.received[n:])
    if closed:
        assert job._table.closed_reason is not None
        assert r.kind == J.Kind.STOPPED
    else:
        assert job._table.closed_reason is None
        failed = [d for c, d in seen if c == J.Confirm.ROW_FAILED_STRIP]
        assert failed and failed[0]["why"] == "arrived_beside_the_target", seen
        assert r.ok and r.detail["status"] == "skipped", (r.reason, r.detail)
    assert sim.violations == []


def test_every_new_reason_has_its_sentence():
    import ui.i1io_table_window as W
    fallback = W.reason_text("a_brand_new_id_nobody_wrote_a_sentence_for")
    for rid in ("arrived_beside_the_target", "free_arm_moved_while_asked",
                "arm_moved_while_asked"):
        text = W.reason_text(rid)
        assert text != fallback and rid not in text and "—" not in text
