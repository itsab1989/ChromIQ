"""Agent 92 (D-06, D-07): the speed round changes no bit.

Every faster path is checked against a frozen copy of the code it replaced
(the originals are reproduced verbatim below), and every parallel path at
several worker counts against the serial one. Run on each CI platform, these
tests carry the identity proof to that platform's numpy and BLAS.
"""
from __future__ import annotations

import numpy as np
import pytest

from workflow.profile_engine import forward_model as F
from workflow.profile_engine import parallel


def _bits(a):
    return np.ascontiguousarray(a).tobytes()


# --- frozen originals (research-integration-11, 598007fb7) -----------------
def _orig_corners(n):
    return np.stack(np.meshgrid(*([[0, 1]] * n), indexing="ij"),
                    -1).reshape(-1, n)


def _orig_interp_weights(p01, grid, n):
    corners = _orig_corners(n)
    idxf = np.clip(p01, 0.0, 1.0) * (grid - 1)
    i0 = np.clip(idxf.astype(int), 0, grid - 2)
    fr = idxf - i0
    npts = len(p01)
    w = np.ones((npts, len(corners)))
    cols = np.zeros((npts, len(corners)), dtype=np.int64)
    for k, c in enumerate(corners):
        wk = np.ones(npts)
        flat = np.zeros(npts, dtype=np.int64)
        for d in range(n):
            wk *= fr[:, d] if c[d] else 1.0 - fr[:, d]
            flat = flat * grid + (i0[:, d] + c[d])
        w[:, k] = wk
        cols[:, k] = flat
    return w, cols


def _orig_grid_solve(w, cols, y, grid, n, lam, iters, x0=None, rtol=0.0):
    ng = grid ** n
    shape = (grid,) * n + (-1,)

    def wmul(x):
        return (w[:, :, None] * x[cols]).sum(1)

    def wtmul(r):
        fc = cols.reshape(-1)
        return np.stack([np.bincount(fc, (w * r[:, c:c + 1]).reshape(-1),
                                     minlength=ng)
                         for c in range(r.shape[1])], 1)

    def curvature(x):
        x3 = x.reshape(shape)
        o = np.zeros_like(x3)
        mid = [slice(None)] * (n + 1)
        lo = [slice(None)] * (n + 1)
        hi = [slice(None)] * (n + 1)
        for ax in range(n):
            mid[ax] = slice(1, -1)
            lo[ax] = slice(0, -2)
            hi[ax] = slice(2, None)
            d2 = (x3[tuple(lo)] - 2 * x3[tuple(mid)] + x3[tuple(hi)])
            o[tuple(lo)] += d2
            o[tuple(mid)] -= 2 * d2
            o[tuple(hi)] += d2
            mid[ax] = lo[ax] = hi[ax] = slice(None)
        return o.reshape(ng, -1)

    def amul(x):
        return wtmul(wmul(x)) + lam * curvature(x) + 1e-7 * x

    b = wtmul(y)
    x = np.zeros((ng, y.shape[1])) if x0 is None else x0.copy()
    r = b - amul(x)
    p = r.copy()
    rs = (r * r).sum()
    stop = max(1e-9, rtol * rs)
    for _ in range(iters):
        ap = amul(p)
        alpha = rs / max((p * ap).sum(), 1e-12)
        x += alpha * p
        r -= alpha * ap
        rs2 = (r * r).sum()
        if rs2 < stop:
            break
        p = r + (rs2 / rs) * p
        rs = rs2
    return x


# --- interpolation ---------------------------------------------------------
@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6])
def test_interp_weights_are_the_original_bits(n):
    rng = np.random.default_rng(n)
    for grid in (2, 5, 9, 17):
        for npts in (0, 1, 7, 300):
            p = rng.random((npts, n))
            if npts > 4:
                p[:npts // 4] = np.round(p[:npts // 4] * (grid - 1)) / (grid - 1)
                p[0], p[1], p[2] = 0.0, 1.0, -0.3
            w0, c0 = _orig_interp_weights(p, grid, n)
            w1, c1 = F._interp_weights(p, grid, n)
            assert w1.dtype == w0.dtype and c1.dtype == c0.dtype
            assert _bits(w0) == _bits(w1) and _bits(c0) == _bits(c1)


@pytest.mark.parametrize("m", [1, 2, 3, 4, 6])
def test_corner_sum_is_numpys_sum_including_signed_zeros(m):
    rng = np.random.default_rng(m)
    for n, grid in ((3, 9), (4, 5), (6, 3)):
        for npts in (1, 2, 9, 500):
            p = rng.random((npts, n))
            vals = rng.standard_normal((grid ** n, m))
            vals[::7] = -0.0
            vals[1::11] = 0.0
            w, c = _orig_interp_weights(p, grid, n)
            want = (w[:, :, None] * vals[c]).sum(1)
            wt, ct = F._interp_weights_t(p, grid, n)
            assert _bits(F._corner_sum(wt, ct, vals)) == _bits(want)


def test_predict_is_the_original_expression():
    rng = np.random.default_rng(5)
    dev = rng.random((800, 4))
    lab = rng.random((800, 3)) * 50
    model = F.fit_forward_model(dev, lab, grid=5, lam=0.02, curve_rounds=1)
    q = rng.random((3000, 4))
    w, c = _orig_interp_weights(model.shape_device(q), model.grid, 4)
    assert _bits(model.predict(q)) == _bits((w[:, :, None] * model.nodes[c]).sum(1))


# --- grid solve ------------------------------------------------------------
@pytest.mark.parametrize("case", [(3, 17, 20000, 3), (3, 9, 300, 4), (6, 9, 400, 3),
                                  (4, 9, 900, 3), (3, 17, 6000, 1)])
@pytest.mark.parametrize("threads", ["1", "2", "4", "8"])
def test_grid_solve_equals_the_original_at_every_worker_count(case, threads,
                                                              monkeypatch):
    n, grid, npts, m = case
    rng = np.random.default_rng(npts)
    p = rng.random((npts, n))
    y = rng.standard_normal((npts, m))
    w, c = _orig_interp_weights(p, grid, n)
    want = _orig_grid_solve(w, c, y, grid, n, 0.03, 25)
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", threads)
    with parallel.accurate_scope():
        got = F._grid_solve(w, c, y, grid, n, 0.03, 25)
    assert _bits(got) == _bits(want)
    assert _bits(F._grid_solve(w, c, y, grid, n, 0.03, 25)) == _bits(want)


def test_grid_solve_uses_the_pool_only_in_maximum_accuracy(monkeypatch):
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", "4")
    rng = np.random.default_rng(2)
    w, c = _orig_interp_weights(rng.random((20000, 3)), 33, 3)
    y = rng.random((20000, 3))
    made = []
    real = parallel.Pool.__init__

    def spy(self, workers=None):
        real(self, workers)
        made.append(self.workers)
    monkeypatch.setattr(parallel.Pool, "__init__", spy)
    F._grid_solve(w, c, y, 33, 3, 0.03, 2)
    assert made == [1]                                # Fast / Bit-exact
    made.clear()
    with parallel.accurate_scope():
        F._grid_solve(w, c, y, 33, 3, 0.03, 2)
    assert made == [4]


# --- chunking, BLAS check, worker budget -----------------------------------
def test_aligned_chunks_start_on_the_alignment_and_cover_every_row():
    for n_rows in (0, 1, 47, 48, 1001, 4913, 35937):
        for w in (1, 2, 3, 5, 8, 12):
            b = parallel.chunk_bounds(n_rows, w, min_rows=50,
                                      align=parallel.ROW_ALIGN)
            if n_rows == 0:
                assert b == []
                continue
            assert b[0][0] == 0 and b[-1][1] == n_rows
            assert all(x[1] == y[0] for x, y in zip(b, b[1:]))
            assert all(lo % parallel.ROW_ALIGN == 0 for lo, _ in b)
            assert len(b) <= max(1, w)


def test_rows_stable_is_a_cached_boolean():
    a = parallel.rows_stable()
    assert isinstance(a, bool) and parallel.rows_stable() is a


def test_row_bounds_are_one_range_outside_maximum_accuracy(monkeypatch):
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", "8")
    assert parallel.row_bounds(100000) == [(0, 100000)]
    with parallel.accurate_scope():
        assert len(parallel.row_bounds(100000, blas=False)) == 8
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", "1")
    with parallel.accurate_scope():
        assert parallel.row_bounds(100000, blas=False) == [(0, 100000)]


def test_default_workers_and_the_apps_budget(monkeypatch):
    monkeypatch.delenv("CHROMIQ_ENGINE_THREADS", raising=False)
    for cpus, want in ((1, 1), (2, 1), (4, 3), (8, 7),
                       (16, parallel._MAX_WORKERS),
                       (64, parallel._MAX_WORKERS)):
        monkeypatch.setattr(parallel, "usable_cpus", lambda c=cpus: c)
        assert parallel.worker_count() == min(want, parallel._MAX_WORKERS)
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", "2")
    assert parallel.worker_count() == 2
    with parallel.worker_budget(5):
        assert parallel.worker_count() == 5          # the app wins
    with parallel.worker_budget(0):
        assert parallel.worker_count() == 2
    assert parallel.worker_count() == 2


def test_pool_map_keeps_order_and_reraises():
    with parallel.Pool(4) as pool:
        out = pool.map(lambda lo, hi: (lo, hi), [(0, 1), (1, 5), (5, 9)])
        assert out == [(0, 1), (1, 5), (5, 9)]

        def boom(lo, hi):
            if lo == 1:
                raise ValueError("x")
            return lo
        with pytest.raises(ValueError):
            pool.map(boom, [(0, 1), (1, 2), (2, 3)])
    with parallel.Pool(1) as pool:                   # serial
        assert pool.map(lambda lo, hi: lo, [(0, 1), (1, 2)]) == [0, 1]


# --- clip searches ---------------------------------------------------------
def test_seeded_clip_cloud_is_the_fresh_generators_cloud():
    from workflow.profile_engine import oog_clip as O
    O._CLOUD_MEMO.clear()
    for n, lim, cm in ((3, None, None), (4, 2.8, np.array([1, 1, 1, .9]))):
        fresh = O._clip_cloud(n, lim, cm, np.random.default_rng(2525),
                              light=True, faces=True)
        a = O.clip_cloud(n, lim, cm, 2525, light=True, faces=True)
        b = O.clip_cloud(n, lim, cm, 2525, light=True, faces=True)
        assert _bits(a) == _bits(fresh) == _bits(b)
        a[0, 0] = 9.0                                  # a private copy
        assert _bits(O.clip_cloud(n, lim, cm, 2525, light=True,
                                  faces=True)) == _bits(fresh)
    O._CLOUD_MEMO.clear()


@pytest.mark.parametrize("threads", ["2", "3", "8"])
def test_cloud_seeds_and_descents_are_split_without_a_bit_changing(threads,
                                                                   monkeypatch):
    from workflow.profile_engine import oog_clip as O
    from workflow.profile_engine import purecolprof as P
    rng = np.random.default_rng(11)
    dev = rng.random((600, 3))
    lab = np.column_stack([100 - 80 * dev.mean(1), 70 * (dev[:, 0] - dev[:, 1]),
                           70 * (dev[:, 1] - dev[:, 2])])
    model = F.fit_forward_model(dev, lab, grid=9, lam=0.02, curve_rounds=1)
    t_lab = np.column_stack([rng.uniform(5, 95, 1500), rng.uniform(-90, 90, 1500),
                             rng.uniform(-90, 90, 1500)])
    t_j = O.lab_to_argyll_jab(t_lab)
    cloud = O.clip_cloud(3, None, None, 5858, light=True, faces=True)

    def pj(d):
        return O.lab_to_argyll_jab(model.predict(d))
    cj = pj(cloud)
    d0 = np.clip(rng.random((1500, 3)), 0, 1)
    w = np.tile(np.eye(3), (1500, 1, 1)) * rng.uniform(.5, 2, (1500, 1, 1))

    def run():
        return (P._cloud_seed(t_j, cloud, cj), P._descend(pj, t_j, d0, iters=4),
                O.best_cloud_seed(t_lab, w, cloud, model.predict(cloud)))
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", "1")
    with parallel.accurate_scope():
        s1, (d1, c1), b1 = run()
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", threads)
    with parallel.accurate_scope():
        s2, (d2, c2), b2 = run()
    assert _bits(s1) == _bits(s2) and _bits(b1) == _bits(b2)
    assert _bits(d1) == _bits(d2) and _bits(c1) == _bits(c2)


# --- GP --------------------------------------------------------------------
def test_gp_gradient_side_by_side_is_the_serial_gradient(monkeypatch):
    from workflow.profile_engine import gpfwd
    rng = np.random.default_rng(3)
    x = rng.random((300, 4))
    yn = rng.standard_normal((300, 3))
    theta = np.log(np.array([0.5, 0.7, 0.9, 1.1, 1.0, 1e-2]))
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", "1")
    f1, g1 = gpfwd._nlml_grad(theta, x, yn)
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", "4")
    with parallel.accurate_scope():
        f2, g2 = gpfwd._nlml_grad(theta, x, yn)
    assert np.float64(f1).tobytes() == np.float64(f2).tobytes()
    assert _bits(g1) == _bits(g2)


def _orig_cloud_seed(t_j, cloud, cloud_j, block=128):
    from workflow.profile_engine.purecolprof import LCH_WEIGHTS
    out = np.empty((len(t_j), cloud.shape[1]))
    cc = np.hypot(cloud_j[:, 1], cloud_j[:, 2])
    for lo in range(0, len(t_j), block):
        tb = t_j[lo:lo + block]
        dl = cloud_j[None, :, 0] - tb[:, None, 0]
        dchsq = ((cloud_j[None, :, 1] - tb[:, None, 1]) ** 2
                 + (cloud_j[None, :, 2] - tb[:, None, 2]) ** 2)
        dc = cc[None, :] - np.hypot(tb[:, 1], tb[:, 2])[:, None]
        dhsq = np.maximum(dchsq - dc * dc, 0.0)
        s = (LCH_WEIGHTS[0] ** 2 * dl * dl + LCH_WEIGHTS[1] ** 2 * dc * dc
             + LCH_WEIGHTS[2] ** 2 * dhsq)
        out[lo:lo + block] = cloud[np.argmin(s, 1)]
    return out


@pytest.mark.parametrize("threads", ["1", "4"])
def test_tiled_cloud_seed_is_the_original_including_ties(threads, monkeypatch):
    from workflow.profile_engine.purecolprof import _cloud_seed
    rng = np.random.default_rng(21)
    cloud = rng.random((9000, 4))
    cj = np.column_stack([rng.uniform(0, 100, 9000), rng.uniform(-60, 60, 9000),
                          rng.uniform(-60, 60, 9000)])
    cj[5000:5100] = cj[100:200]                      # exact ties across tiles
    tj = np.column_stack([rng.uniform(0, 100, 700), rng.uniform(-90, 90, 700),
                          rng.uniform(-90, 90, 700)])
    tj[:50] = cj[150:200]
    want = _orig_cloud_seed(tj, cloud, cj)
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", threads)
    with parallel.accurate_scope():
        assert _bits(_cloud_seed(tj, cloud, cj)) == _bits(want)
    tj2 = tj.copy()
    tj2[3, 1] = np.nan                               # the original's NaN rule
    assert _bits(_cloud_seed(tj2, cloud, cj)) == _bits(_orig_cloud_seed(tj2, cloud, cj))
