"""4.3.48 (release review 4.3.47, SHOULD-1): an arrival beside its target is moved to once more.

4.3.47 failed a patch row as soon as the arm read twice 6..10 units (0.6..1 mm) beside its target,
and a page allows only two rows read again, which ordinary scatter on a dense page uses up. Now,
in a PATCH ROW only, such an arrival is moved to once more, automatically, from the fresh reading:
the same m0 line (the same absolute target). i1Profiler does exactly this on the volunteer's
table: 23 recorded m0 lines to the previous move's own target, from a fresh p0 0..3 units off
(R1 285.068, R2 480.292, 18 Nov A 161.408, B 49.904, ...). Only a second arrival beside fails the
row; beyond 1 mm stays a doubt. At most two such moves per row attempt (caps.BESIDE_RETRIES_PER_ROW),
3 lines and 1 movement each (caps.BESIDE_RETRY), counted in the step and the session caps.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import tester_d2 as D2
from tests.i1io_table.test_4347_fix2_arrivals_and_aiming_again import _arrive_beside
from tests.i1io_table.test_job_reading import job_for
from workflow.i1io.table import caps as cp
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl

FIXED = {v.decode().rstrip("\r") for v in tbl.WIRE.values()}


def _computed_m0(line: str) -> bool:
    return line.startswith(";m0") and line not in FIXED


def _land_beside(sim, which: "tuple[int, ...]", dx: int, dy: int):
    """The listed computed m0 moves (1-based, counted from now) really stop (dx, dy) beside their
    target: the simulated arm stands there, so every reading says so, and a second move from
    there brings it to the target."""
    orig = sim._c_execute
    st = {"m0": 0}

    def ex(line, cid, a, fault):
        out = orig(line, cid, a, fault)
        if cid == "m0" and _computed_m0(line):
            st["m0"] += 1
            if st["m0"] in which:
                sim.pos = [sim.pos[0] + dx, sim.pos[1] + dy]
        return out
    sim._c_execute = ex
    return st


def _ready(tmp_path, script=None, **kw):
    job, sim, helper, run, p = job_for(tmp_path, script, real_table=False, **kw)
    sim.jitter = False
    for s in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, s)()).ok, s
    seen = []
    p.on_ask = lambda person, res: seen.append((res.confirm, dict(res.detail))) and None
    return job, sim, p, seen


@pytest.mark.parametrize("off", [(0, -6), (7, 0), (-10, 10), (8, -8)])
def test_an_arrival_beside_is_moved_to_once_more_and_the_row_is_read(tmp_path, off):
    job, sim, p, seen = _ready(tmp_path)
    _land_beside(sim, (2,), *off)
    n = len(sim.received)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "read", (r.reason, r.detail)
    assert not [c for c, _d in seen if c == J.Confirm.ROW_FAILED]      # no row failed
    assert job._table.closed_reason is None and sim.violations == []
    assert len(job.beside_retries) == 1
    # on the wire: the second patch move, its arrival p0, the p0 read again after 0.3 s, then
    # THE SAME m0 line again, and its arrival p0
    sent = sim.received[n:]
    moves = [k for k, ln in enumerate(sent) if _computed_m0(ln)]
    second, again = moves[1], moves[2]
    assert sent[again] == sent[second]
    assert sent[second + 1:again] == [";p025", ";p025"]
    assert sent[again + 1] == ";p025"


def test_without_the_beside_arrival_nothing_changes_on_the_wire(tmp_path):
    """The ideal table: no arrival beside, so no second move (the frozen wire captures of the
    other tests stay byte for byte)."""
    job, sim, p, seen = _ready(tmp_path)
    n = len(sim.received)
    r = p.drive(job.read_row())
    assert r.ok and job.beside_retries == []
    sent = sim.received[n:]
    targets = [ln for ln in sent if _computed_m0(ln)]
    assert len(targets) == len(set(targets))        # every patch moved to once


@pytest.mark.parametrize("off", [(0, -6), (9, 0)])
def test_beside_again_after_the_second_move_fails_the_row_as_before(tmp_path, off):
    job, sim, p, seen = _ready(tmp_path, {J.Confirm.ROW_FAILED: "skip"})
    # the reading says beside four times: the first move's two readings and the second's two
    _arrive_beside(sim, 2, *off, reads=4)
    n = len(sim.received)
    r = p.drive(job.read_row())
    failed = [d for c, d in seen if c == J.Confirm.ROW_FAILED]
    assert failed and failed[0]["why"] == "arrived_beside_the_target_again", seen
    assert r.ok and r.detail["status"] == "skipped"
    assert job._table.closed_reason is None and sim.violations == []
    moves = [ln for ln in sim.received[n:] if _computed_m0(ln)]
    assert len(moves) == 3                    # patch 1, patch 2, patch 2 once more: no more


@pytest.mark.parametrize("off", [(0, -11), (12, 0), (0, -60)])
def test_beyond_1_mm_after_the_second_move_still_ends_the_sending(tmp_path, off):
    job, sim, p, seen = _ready(tmp_path)
    st = _arrive_beside(sim, 2, 0, -7, reads=2)       # the first move: beside
    orig = sim._c_execute
    state = {"m0": 0, "left": 0}

    def ex(line, cid, a, fault):                      # the second move: beyond 1 mm
        status, data, t = orig(line, cid, a, fault)
        if cid == "m0" and _computed_m0(line):
            state["m0"] += 1
            if state["m0"] == 3:
                state["left"] = 2
        elif cid == "p0" and state["left"]:
            state["left"] -= 1
            x, y = int(data[:4], 16), int(data[4:8], 16)
            x = (x - 0x10000 if x & 0x8000 else x) + off[0]
            y = (y - 0x10000 if y & 0x8000 else y) + off[1]
            data = f"{x & 0xFFFF:04X}{y & 0xFFFF:04X}"
        return status, data, t
    sim._c_execute = ex
    n = len(sim.received)
    r = p.drive(job.read_row())
    assert st["m0"] >= 2
    assert r.kind == J.Kind.STOPPED and job._table.closed_reason is not None, (r.kind, r.reason)
    moves = [ln for ln in sim.received[n:] if _computed_m0(ln)]
    assert len(moves) == 3                    # nothing after the second move


def test_at_most_two_second_moves_per_row_attempt(tmp_path):
    """Three arrivals beside in one row: two are moved to again, the third fails the row (the
    step's cap holds them: 4 n + 4 + 2 x 3 lines, n + 2 movements)."""
    job, sim, p, seen = _ready(tmp_path, {J.Confirm.ROW_FAILED: "skip"})
    _land_beside(sim, (1, 3, 5), 0, 7)   # patch 1, patch 2 (after patch 1's second move), 3
    r = p.drive(job.read_row())
    failed = [d for c, d in seen if c == J.Confirm.ROW_FAILED]
    assert len(job.beside_retries) == cp.BESIDE_RETRIES_PER_ROW == 2
    assert failed and failed[0]["why"] == "arrived_beside_the_target"
    assert r.ok and r.detail["status"] == "skipped"
    assert job._table.closed_reason is None and sim.violations == []


def test_each_row_attempt_has_its_own_two(tmp_path):
    job, sim, p, seen = _ready(tmp_path, {J.Confirm.ROW_FAILED: "again"})
    _land_beside(sim, (1, 3, 5, 7), 0, 7)     # 3 in the first attempt, 1 in the row read again
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "read" and r.detail["attempts"] == 2, r.detail
    assert len(job.beside_retries) == 3


# ---- planted faults: the allow decision ------------------------------------------------------
@pytest.mark.parametrize("plant", ["no retries allowed", "the way not confirmed", "arm free",
                                   "a stop waits"])
def test_planted_a_refused_retry_sends_no_second_move(tmp_path, monkeypatch, plant):
    job, sim, p, seen = _ready(tmp_path, {J.Confirm.ROW_FAILED: "skip"})
    real = J.TableJob._beside_retry_allowed
    if plant == "no retries allowed":
        monkeypatch.setattr(cp, "BESIDE_RETRIES_PER_ROW", 0)
    elif plant == "the way not confirmed":
        monkeypatch.setattr(J.TableJob, "_beside_retry_allowed",
                            lambda self, g, t: (setattr(self, "_seg_visited",
                                                        lambda a, b: False)
                                                or real(self, g, t)))
    elif plant == "arm free":
        def free(self, g, t):
            self._table.arm_free = None
            try:
                return real(self, g, t)
            finally:
                self._table.arm_free = False
        monkeypatch.setattr(J.TableJob, "_beside_retry_allowed", free)
    else:
        def stopped(self, g, t):
            self._pause_stop = True
            return real(self, g, t)
        monkeypatch.setattr(J.TableJob, "_beside_retry_allowed", stopped)
    _land_beside(sim, (2,), 0, 8)
    n = len(sim.received)
    r = p.drive(job.read_row())
    moves = [ln for ln in sim.received[n:] if _computed_m0(ln)]
    assert job.beside_retries == []
    assert moves == moves[:2] and len(moves) == 2, moves      # no second move to patch 2
    if plant != "a stop waits":
        failed = [d for c, d in seen if c == J.Confirm.ROW_FAILED]
        assert failed and failed[0]["why"] == "arrived_beside_the_target"
    assert job._table.closed_reason is None
    assert r.kind in (J.Kind.OK, J.Kind.REFUSED)


def test_planted_a_retry_that_ignores_the_stop_is_caught(tmp_path, monkeypatch):
    """The stop check inside the second move itself: a stop pressed while the arrival was read
    again is honoured before the m0 (even if the allow decision were wrong)."""
    job, sim, p, seen = _ready(tmp_path)
    monkeypatch.setattr(J.TableJob, "_beside_retry_allowed", lambda self, g, t: True)
    real_between = J.TableJob._between_patches
    calls = {"n": 0}

    def between(self):
        calls["n"] += 1
        self._pause_stop = True           # the person pressed Stop just now
        return real_between(self)
    monkeypatch.setattr(J.TableJob, "_between_patches", between)
    _land_beside(sim, (1,), 0, 8)
    n = len(sim.received)
    r = p.drive(job.read_row())
    moves = [ln for ln in sim.received[n:] if _computed_m0(ln)]
    assert len(moves) == 1                    # the first patch's move only
    assert r.kind == J.Kind.REFUSED and r.reason == "stopped_between_patches", r.reason


def test_strip_rows_creep_and_the_check_move_never_move_again(tmp_path):
    """Only patch rows retry: any other computed move keeps 4.3.47's clean failure (4.3.50: the
    tests' copy of 4.3.49's check move stands for such a move here, tester_d2)."""
    job, sim, p, seen = _ready(tmp_path)
    _land_beside(sim, (1,), 0, 8)
    n = len(sim.received)
    r = p.drive(D2.check_move(job))
    assert r.kind == J.Kind.REFUSED and r.reason == "arrived_beside_the_target", r.reason
    assert len([ln for ln in sim.received[n:] if _computed_m0(ln)]) == 1
    assert job.beside_retries == []
