"""Independent safety review of the dual scan on the i1iO 2 table (2026-11-19): the UV pass's
two position checks before its scan move, each of which a planted fault removed with every
other test still green.

* Before the UV pass's first line the arm must read where the lamp pass ended
  (``scan._run_uv_pass``: "the arm stands at ..., not at the end of the lamp pass").
* After the zero-length m0, c4 and d1 210, the fresh p0 right before the UV scan move must
  still be at the UV pass's start ("the arm arrived at ..., not at the UV pass's start").

Neither may let the UV scan move out: the arm was pushed (a hand, a cable), and the move
straight back would no longer run along the row just read.
"""
from __future__ import annotations

from tests.i1io_table import test_dual_table as T
from workflow.i1io.table import job as J
from workflow.i1io.table import scan as sc

import workflow.i1io.table.scan as scm


def _uv_m2_sent(sim) -> int:
    return sum(1 for ln in sim.received if ln.startswith(";m2"))


def test_the_uv_pass_needs_the_arm_where_the_lamp_pass_ended(tmp_path):
    job, sim, helper, run, p = T._job(tmp_path)
    T._ready(job, p)
    real = sc.run_row
    uv = []

    def pushed_before_the_uv_pass(table, *a, **k):
        if k.get("uv_pass") and not uv:
            sim.pos = [sim.pos[0] - 40.0, sim.pos[1]]   # 4 mm along the row, by a hand
            table.position_now = None                    # so the pass reads the arm itself
            uv.append(real(table, *a, **k))
            return uv[-1]
        return real(table, *a, **k)
    scm.run_row = pushed_before_the_uv_pass
    try:
        r = p.drive(job.read_row())
    finally:
        scm.run_row = real
    assert uv and uv[0].kind == "failed_clean", uv
    assert "not at the end of the lamp pass" in uv[0].why, uv[0].why
    # the row was offered again and read patch by patch (the harness's answer): the dual
    # attempt sent its lamp pass's scan move only, and no line of the UV pass
    assert _uv_m2_sent(sim) == 1, [ln for ln in sim.received if ln.startswith(";m2")]
    assert ";d100d23a" not in sim.received
    assert sim.violations == []


def test_the_uv_scan_move_needs_a_fresh_reading_at_its_start(tmp_path):
    job, sim, helper, run, p = T._job(tmp_path)
    T._ready(job, p)
    d = job._table
    real_ex = d.c_exchange

    def pushed_after_d1(line, *a, **k):
        out = real_ex(line, *a, **k)
        if bytes(line) == T.REC_D1_UV or bytes(line).startswith(b";d100d2"):
            sim.pos = [sim.pos[0] + 40.0, sim.pos[1]]   # pushed between d1 210 and the p0
        return out
    d.c_exchange = pushed_after_d1
    try:
        r = p.drive(job.read_row())
    finally:
        d.c_exchange = real_ex
    assert _uv_m2_sent(sim) == 1, [ln for ln in sim.received if ln.startswith(";m2")]
    assert any(ln.startswith(";d100d2") for ln in sim.received)
    assert d.closed_reason is not None or r.kind != J.Kind.OK, (r.reason, r.detail)


def test_the_uv_pass_is_cut_where_the_sensor_really_is_on_its_way_back():
    """The UV pass runs from the lamp pass's END back to its start. Its readings are made here
    from the sensor's PLACE on the table (the row's patches by their table X, the move's own
    profile from the UV pass's start), not from the UV plan's own along-the-row numbers, so a
    UV plan whose positions were not mirrored is caught (the cut test above builds its stream
    from those very numbers and cannot see it)."""
    import math
    from workflow.i1io.table import dual_rows as dl
    from workflow.i1io.table import spot as sp
    pts = [sc.Patch(str(k), f"A{k}", (-1200 + 106 * k, 1700), half_mm=5.3) for k in range(20)]
    lamp = sc.plan_row("r", (-1306, 1700), (920, 1700), 132, pts, dual=True)
    uv = sp.uv_pass_of(lamp)

    def stream(plan, first, start, k):
        ux = (plan.end[0] - plan.start[0]) / plan.dist
        rows = []
        for i in range(plan.N):
            t = first + (i + 0.5) * sc.READING_S - start
            lo, hi = 0.0, plan.dist / 10.0
            for _ in range(40):
                mid = (lo + hi) / 2
                if sc.time_at(plan, mid) < t:
                    lo = mid
                else:
                    hi = mid
            x = plan.start[0] + ux * lo * 10.0           # the sensor's table X now
            q = min(pts, key=lambda p: abs(p.xy[0] - x))
            rows.append([(0.05 + 0.04 * int(q.sample_id)) * k] * 36)
        return rows
    L = stream(lamp, 0.370, sc.MOTION_START_AFTER_LAMP_S, 1.0)
    U = stream(uv, sc.UV_FIRST_READING_AFTER_TRIGGER_S, sc.UV_MOTION_START_AFTER_TRIGGER_S, 0.2)
    assert uv.start == lamp.end and uv.end == lamp.start
    cut = dl.cut_dual(lamp, uv, L, U)
    assert cut.ok, (cut.reason, cut.info)
    for q, l, u in zip(lamp.patches, cut.lamp, cut.uv):
        want = 0.05 + 0.04 * int(q.sample_id)
        assert math.isclose(l[0], want, abs_tol=1e-9), (q.loc, l[0], want)
        assert math.isclose(u[0], 0.2 * want, abs_tol=1e-9), (q.loc, u[0], 0.2 * want)
