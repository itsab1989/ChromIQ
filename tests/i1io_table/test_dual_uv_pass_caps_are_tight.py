"""NOTE-A of the 4.3.48 re-review: the UV pass's cap is 9 lines, not 10.

The recorded UV pass is 8 lines (zero m0, c4, d1 210, p0, m2, a3, c3, the p0 at its end). ONE
reading more is possible: the job's read-again after a question answered since the lamp pass's
last reading (only when a reading is kept) OR the UV pass's own reading (only when none is kept,
or the last motion is unconfirmed). They exclude each other because, when the UV pass starts,
the lamp pass has ended "done" (its last motion confirmed) and every motion clears the kept
reading. Here: the invariant at the UV pass's entry in both cases, the exact line counts, and a
tenth line refused by the step's own cap."""
from __future__ import annotations

import pytest

from tests.i1io_table import test_dual_table as T
from workflow.i1io.table import caps as cp
from workflow.i1io.table import scan as sc


def _watch(monkeypatch, job):
    """Record, at the UV pass's entry, whether the last motion is confirmed and a reading is
    kept, and the row_uv step's own line count when the step ends."""
    seen = {"entry": [], "uv_lines": []}
    real_uv = sc._run_uv_pass

    def uv(table, *a, **k):
        seen["entry"].append((table.motion_unconfirmed, table.position_now is not None,
                              table.step_lines))
        out = real_uv(table, *a, **k)
        seen["uv_lines"].append(table.step_lines)
        return out
    monkeypatch.setattr(sc, "_run_uv_pass", uv)
    return seen


@pytest.mark.parametrize("asked", [False, True])
def test_the_uv_pass_never_needs_more_than_nine_lines(tmp_path, monkeypatch, asked):
    job, sim, helper, run, p = T._job(tmp_path)
    T._ready(job, p)
    seen = _watch(monkeypatch, job)
    if asked:
        real = job._step

        def step(name, *a, **k):
            out = real(name, *a, **k)
            if name == "row_uv":
                job._mark_answered()       # a question answered during the lamp pass
            return out
        monkeypatch.setattr(job, "_step", step)
    r = p.drive(job.read_row())
    assert r.ok, (r.reason, r.detail)
    assert seen["entry"], "no UV pass ran"
    for unconfirmed, kept, before in seen["entry"]:
        # the lamp pass's last motion is confirmed, and a reading is kept: the UV pass does not
        # read the arm itself; the job's read-again is the only extra line
        assert unconfirmed is False and kept is True
        assert before == (1 if asked else 0)
    assert seen["uv_lines"] == [9 if asked else 8]
    assert max(seen["uv_lines"]) <= cp.DUAL_UV_PASS[0] == 9


def test_a_tenth_line_in_the_uv_pass_is_refused_by_its_cap(tmp_path, monkeypatch):
    """Planted: both extra readings at once (impossible on the real path). The step's cap
    refuses the tenth line (the reading after the UV scan move): the row ends with the cap's
    own refusal instead of passing silently, as it did with a cap of 10."""
    job, sim, helper, run, p = T._job(tmp_path)
    T._ready(job, p)
    real = job._step

    def step(name, *a, **k):
        out = real(name, *a, **k)
        if name == "row_uv":
            job._mark_answered()
        return out
    monkeypatch.setattr(job, "_step", step)
    real_uv = sc._run_uv_pass

    def uv(table, *a, **k):
        table.motion_unconfirmed = True            # forces the pass's own reading as well
        return real_uv(table, *a, **k)
    monkeypatch.setattr(sc, "_run_uv_pass", uv)
    res = p.drive(job.read_row())
    assert not res.ok and res.reason == "step_cap", (res.reason, res.detail)
    assert "row_uv" in res.detail.get("log_reason", "")
