"""D-06 (speed never costs quality): the engine's speed paths give the SAME
BYTES as the serial code they replace.

* np.bincount accumulation == np.add.at accumulation (forward-fit normal
  equations), bit for bit;
* the row-parallel Gauss-Newton (pool threads over contiguous chunks) ==
  one serial batch, bit for bit, at several thread counts;
* the worker count never takes every core and honours the override;
* an oracle colprof started ahead of need is killed and its folder removed
  when the build does not collect it.

The full-profile proof (battery-v2 datasets, v2 + v4, byte identity
against the unaccelerated build) is Experiments/agent8 identity runs,
reported in Findings/agent8-01-performance.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from workflow.profile_engine import b2a, parallel
from workflow.profile_engine.forward_model import (_grid_solve,
                                                   _interp_weights,
                                                   fit_forward_model)


def _bits(a: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


@pytest.mark.parametrize("n,grid", [(3, 17), (4, 9), (6, 5)])
def test_bincount_accumulates_exactly_like_add_at(n, grid):
    rng = np.random.default_rng(n * 100 + grid)
    npts = 2500
    w, cols = _interp_weights(rng.random((npts, n)), grid, n)
    r = rng.normal(size=(npts, 3)) * 40.0
    o = np.zeros((grid ** n, 3))
    np.add.at(o, cols.reshape(-1),
              (w[:, :, None] * r[:, None, :]).reshape(-1, 3))
    fc = cols.reshape(-1)
    o2 = np.stack([np.bincount(fc, (w * r[:, c:c + 1]).reshape(-1),
                               minlength=grid ** n) for c in range(3)], 1)
    assert np.array_equal(_bits(o), _bits(o2))


def test_grid_solve_matches_the_add_at_reference():
    """_grid_solve (now bincount) against a copy of the add.at version."""
    rng = np.random.default_rng(5)
    n, grid = 4, 5
    dev = rng.random((600, n))
    lab = np.column_stack([100 - 80 * dev.mean(1), 30 * (dev[:, 1] - dev[:, 0]),
                           30 * (dev[:, 2] - dev[:, 1])])
    w, cols = _interp_weights(dev, grid, n)
    got = _grid_solve(w, cols, lab, grid, n, 0.03, 120)

    ng = grid ** n
    import workflow.profile_engine.forward_model as fm
    real_bincount = np.bincount

    def add_at_bincount(idx, weights, minlength):
        o = np.zeros(minlength)
        np.add.at(o, idx, weights)
        return o
    try:
        fm.np.bincount = add_at_bincount          # the old accumulation
        ref = _grid_solve(w, cols, lab, grid, n, 0.03, 120)
    finally:
        fm.np.bincount = real_bincount
    assert ng == len(got)
    assert np.array_equal(_bits(got), _bits(ref))


@pytest.fixture(scope="module")
def cmyk_model():
    rng = np.random.default_rng(11)
    dev = rng.random((500, 4))
    dev[dev.sum(1) > 3.0] *= 0.75
    ink = dev[:, :3] + dev[:, 3:4] * 0.9
    lab = np.column_stack([100 - 90 * (1 - np.prod(1 - 0.85 * ink, 1)),
                           60 * (dev[:, 1] - 0.6 * dev[:, 0]) * (1 - dev[:, 3]),
                           60 * (dev[:, 2] - 0.7 * dev[:, 1]) * (1 - dev[:, 3])])
    return fit_forward_model(dev, lab, grid=5, lam=0.02, curve_rounds=1)


@pytest.mark.parametrize("threads", ["2", "3", "7"])
def test_row_parallel_inversion_is_bit_identical(cmyk_model, monkeypatch,
                                                 threads):
    """build_b2a_clut (accurate) at 17^3 nodes: serial == threaded."""
    monkeypatch.setattr(parallel, "MIN_ROWS_PER_CHUNK", 300)
    kw = dict(channel_letters=list("CMYK"), is_additive=False,
              ink_limit=280.0, accurate=True, black_l=10.0)
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", "1")
    d1, r1 = b2a.build_b2a_clut(cmyk_model, 17, **kw)
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", threads)
    calls = []
    real = parallel.run_chunks

    def spy(fn, bounds):
        calls.append(len(bounds))
        return real(fn, bounds)
    monkeypatch.setattr(parallel, "run_chunks", spy)
    d2, r2 = b2a.build_b2a_clut(cmyk_model, 17, **kw)
    assert calls and max(calls) == int(threads)      # really split
    assert np.array_equal(_bits(d1), _bits(d2))
    assert np.array_equal(_bits(r1), _bits(r2))


def test_fast_mode_inversion_is_never_split(cmyk_model, monkeypatch):
    monkeypatch.setattr(parallel, "MIN_ROWS_PER_CHUNK", 10)
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", "4")
    monkeypatch.setattr(parallel, "run_chunks",
                        lambda fn, bounds: pytest.fail("Fast mode split"))
    b2a.build_b2a_clut(cmyk_model, 9, channel_letters=list("CMYK"),
                       is_additive=False, ink_limit=280.0, accurate=False)


def test_chunks_are_contiguous_and_cover_every_row():
    for n_rows in (0, 1, 999, 4913, 35937):
        for w in (1, 2, 5, 8):
            b = parallel.chunk_bounds(n_rows, w, min_rows=1000)
            if n_rows == 0:
                assert b == []
                continue
            assert b[0][0] == 0 and b[-1][1] == n_rows
            assert all(x[1] == y[0] for x, y in zip(b, b[1:]))
            assert len(b) <= max(1, w)


def test_worker_count_leaves_headroom(monkeypatch):
    monkeypatch.delenv("CHROMIQ_ENGINE_THREADS", raising=False)
    for cpus, want in ((1, 1), (2, 1), (4, 2), (8, 6), (16, 8), (64, 8)):
        monkeypatch.setattr(parallel, "usable_cpus", lambda c=cpus: c)
        assert parallel.worker_count() == want
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", "1")
    assert parallel.worker_count() == 1


def test_cgroup_quota_caps_the_cpu_count(monkeypatch, tmp_path):
    monkeypatch.setattr(parallel, "_cgroup_cpu_limit", lambda: 3)
    assert parallel.usable_cpus() <= 3


def test_unused_oracle_run_is_killed_and_cleaned(tmp_path):
    from workflow.profile_engine import gamut_map as gm
    ti3 = tmp_path / "x.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    # A stand-in "colprof" that would run for a minute.
    run = gm.OracleRun(("k",), [sys.executable, "-c",
                                "import time,sys; time.sleep(60)"], ti3)
    folder = Path(run.base).parent
    assert run.proc in gm._LIVE_CHILDREN and folder.exists()
    run.close()
    assert run.proc.poll() is not None
    assert run.proc not in gm._LIVE_CHILDREN
    assert not folder.exists()


def test_oracle_run_reports_a_failed_colprof(tmp_path):
    from workflow.profile_engine import gamut_map as gm
    ti3 = tmp_path / "x.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    run = gm.OracleRun(("k",), [sys.executable, "-c",
                                "import sys; print('boom'); sys.exit(3)"], ti3)
    try:
        with pytest.raises(gm.OracleUnavailable, match="boom"):
            run.wait()
    finally:
        run.close()


def test_no_oracle_is_started_without_argyll(tmp_path):
    from workflow.profile_engine import gamut_map as gm
    from types import SimpleNamespace
    meas = SimpleNamespace(device_rep="CMYK", path=tmp_path / "x.ti3")
    assert gm.start_colprof_oracle(meas, "src.icm", SimpleNamespace(),
                                   tmp_path / "no-argyll", None) is None
