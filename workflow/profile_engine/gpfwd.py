"""Candidate "gpfwd" (agent 3, profile-engine research): numpy-only GP forward model.

ARD Matern 5/2 kernel + white noise, hyperparameters by maximising the log
marginal likelihood (shared across the three Lab outputs, each output
standardised), Adam on log-parameters with analytic gradients, then one
Huber reweighting pass (per-point noise inflated by 1/w, the same Huber
constants as accuracy.py). Deterministic.

Intended to be copied verbatim into a candidate tree as
workflow/profile_engine/gpfwd.py.
"""
from __future__ import annotations

import numpy as np

_SQ5 = np.sqrt(5.0)


def _dists(xa, xb, ls):
    a = xa / ls
    b = xb / ls
    d2 = (a * a).sum(1)[:, None] + (b * b).sum(1)[None, :] - 2.0 * a @ b.T
    return np.sqrt(np.clip(d2, 0.0, None))


def _matern(r, s2):
    return s2 * (1.0 + _SQ5 * r + 5.0 / 3.0 * r * r) * np.exp(-_SQ5 * r)


class GPForward:
    def __init__(self, x, y, ls, s2, noise, alpha_extra=None):
        self.x = np.asarray(x, float)
        self.ym = y.mean(0)
        self.ys = y.std(0) + 1e-12
        yn = (y - self.ym) / self.ys
        self.ls, self.s2, self.noise = ls, s2, noise
        K = _matern(_dists(self.x, self.x, ls), s2)
        diag = noise + (0.0 if alpha_extra is None else alpha_extra)
        K[np.diag_indices_from(K)] += diag + 1e-8
        Lc = np.linalg.cholesky(K)
        self.alpha = np.linalg.solve(Lc.T, np.linalg.solve(Lc, yn))

    def predict(self, z, chunk=8192):
        z = np.atleast_2d(np.asarray(z, float))
        out = np.empty((len(z), self.alpha.shape[1]))
        for s in range(0, len(z), chunk):
            ks = _matern(_dists(z[s:s + chunk], self.x, self.ls), self.s2)
            out[s:s + chunk] = ks @ self.alpha
        return out * self.ys + self.ym


def _nlml_grad(theta, x, yn):
    n = x.shape[1]
    ls = np.exp(theta[:n])
    s2 = np.exp(theta[n])
    nz = np.exp(theta[n + 1])
    N, m = yn.shape
    r = _dists(x, x, ls)
    e = np.exp(-_SQ5 * r)
    Ks = s2 * (1.0 + _SQ5 * r + 5.0 / 3.0 * r * r) * e
    K = Ks.copy()
    K[np.diag_indices_from(K)] += nz + 1e-8
    try:
        Lc = np.linalg.cholesky(K)
    except np.linalg.LinAlgError:
        return np.inf, np.zeros_like(theta)
    alpha = np.linalg.solve(Lc.T, np.linalg.solve(Lc, yn))
    nlml = 0.5 * (yn * alpha).sum() + m * np.log(np.diag(Lc)).sum() \
        + 0.5 * N * m * np.log(2 * np.pi)
    Kinv = np.linalg.solve(Lc.T, np.linalg.solve(Lc, np.eye(N)))
    Q = alpha @ alpha.T - m * Kinv          # d nlml/dtheta = -0.5 tr(Q dK)
    g = np.empty_like(theta)
    base = s2 * 5.0 / 3.0 * (1.0 + _SQ5 * r) * e
    for dd in range(n):
        diff2 = (x[:, dd:dd + 1] - x[:, dd][None, :]) ** 2 / ls[dd] ** 2
        g[dd] = -0.5 * (Q * (base * diff2)).sum()
    g[n] = -0.5 * (Q * Ks).sum()
    g[n + 1] = -0.5 * np.trace(Q) * nz
    return nlml, g


def fit_hyper(x, y, iters=200, lr=0.05, max_points=1200, seed=0,
              starts=(1.0, 3.0, 10.0)):
    """Adam on log(ls, s2, noise) from several length-scale starts; the
    highest marginal likelihood wins. One start is not enough: on X3 seed 26
    a short-length-scale, near-zero-noise local optimum (an interpolant,
    lml 4147.1, truth 0.205/1.054) sits next to the global one (lml 4151.9,
    truth 0.147/0.709) (Experiments/agent3/F0e-gp-optima.txt). For speed the
    hyperparameters are learnt on at most ``max_points`` rows
    (deterministic subsample)."""
    x = np.asarray(x, float)
    yn = (y - y.mean(0)) / (y.std(0) + 1e-12)
    if len(x) > max_points:
        idx = np.random.default_rng(seed).permutation(len(x))[:max_points]
        x, yn = x[idx], yn[idx]
    n = x.shape[1]
    lo = np.concatenate([np.full(n, np.log(0.02)), [np.log(1e-3)], [np.log(1e-6)]])
    hi = np.concatenate([np.full(n, np.log(100.0)), [np.log(1e4)], [np.log(1.0)]])
    best = (np.inf, None)
    for ls0 in starts:
        theta = np.concatenate([np.full(n, np.log(ls0)), [np.log(1.0)],
                                [np.log(1e-2)]])
        mom = np.zeros_like(theta)
        vel = np.zeros_like(theta)
        for t in range(1, iters + 1):
            f, g = _nlml_grad(theta, x, yn)
            if not np.isfinite(f):
                theta = 0.5 * (theta + (best[1] if best[1] is not None
                                        else theta))
                theta[n + 1] += 0.5
                continue
            if f < best[0]:
                best = (f, theta.copy())
            mom = 0.9 * mom + 0.1 * g
            vel = 0.999 * vel + 0.001 * g * g
            step = lr * (mom / (1 - 0.9 ** t)) / (np.sqrt(vel / (1 - 0.999 ** t)) + 1e-8)
            theta = np.clip(theta - step, lo, hi)
    th = best[1]
    return np.exp(th[:n]), float(np.exp(th[n])), float(np.exp(th[n + 1])), \
        float(-best[0])


def huber_weights(res):
    mad = 1.4826 * float(np.median(np.abs(res - np.median(res))))
    scale = max(1.345 * mad, 0.35)
    w = np.minimum(1.0, scale / np.maximum(res, 1e-9))
    w[res > 8.0 * scale] = 0.0
    return w


class _MeanGP:
    """GP on the residual of a parametric mean: far from the data the
    prediction falls back to the mean function instead of to a constant
    (a zero-mean GP reverts to mid-grey in unsampled ink corners: S3 at 150
    patches, p95 10.9 dE00, Experiments/agent3/F0g)."""

    def __init__(self, gp, mean):
        self.gp, self.mean = gp, mean
        self.ls, self.s2, self.noise = gp.ls, gp.s2, gp.noise

    def predict(self, z):
        return self.gp.predict(z) + self.mean(z)


def _affine(x):
    return np.hstack([np.ones((len(x), 1)), x])


def _quad(x):
    n = x.shape[1]
    cols = [np.ones((len(x), 1)), x]
    for i in range(n):
        for j in range(i, n):
            cols.append((x[:, i] * x[:, j])[:, None])
    return np.hstack(cols)


def fit_gp_forward(device, lab, de_fn, row_weights=None, iters=200,
                   mean="none", ref_pred=None):
    """Fit, Huber-reweight once, refit with the learnt kernel fixed.
    ``mean``: "none" (constant), "linear" or "quadratic" least-squares mean
    function with the GP on its residual."""
    device = np.asarray(device, float)
    if mean != "none":
        basis = _affine if mean == "linear" else _quad
        coef, *_ = np.linalg.lstsq(basis(device), lab, rcond=None)
        mfn = lambda z: basis(np.atleast_2d(z)) @ coef  # noqa: E731
        inner = fit_gp_forward(device, lab - mfn(device), lambda p, r: de_fn(
            p + mfn(device), r + mfn(device)), row_weights, iters, "none")
        out = _MeanGP(inner.gp if isinstance(inner, _MeanGP) else inner, mfn)
        out.lml, out.n_down = inner.lml, inner.n_down
        return out
    if ref_pred is not None:
        # Robustness from a STIFF reference (the shipped accurate fit): a
        # flexible GP partly fits a misread strip and then cannot see it in
        # its own residuals; and misreads left in the rows distort the
        # marginal likelihood. Weights come from the reference's residuals,
        # rejected rows are dropped BEFORE the hyperparameters are learnt.
        w = huber_weights(de_fn(ref_pred, lab))
        if row_weights is not None:
            w = w * np.asarray(row_weights, float)
        keep = w > 0
        ls, s2, nz, lml = fit_hyper(device[keep], lab[keep], iters=iters)
        extra = nz * (1.0 / np.maximum(w[keep], 1e-3) - 1.0)
        gp = GPForward(device[keep], lab[keep], ls, s2, nz, alpha_extra=extra)
        gp.lml = lml
        gp.n_down = int((w < 0.999).sum())
        return gp
    ls, s2, nz, lml = fit_hyper(device, lab, iters=iters)
    gp = GPForward(device, lab, ls, s2, nz)
    w = huber_weights(de_fn(gp.predict(device), lab))
    if row_weights is not None:
        w = w * np.asarray(row_weights, float)
    keep = w > 0
    if (w < 0.999).any():
        extra = nz * (1.0 / np.maximum(w[keep], 1e-3) - 1.0)
        gp = GPForward(device[keep], lab[keep], ls, s2, nz, alpha_extra=extra)
    gp.lml = lml
    gp.n_down = int((w < 0.999).sum())
    return gp


# ---------------------------------------------------------------------------
# Table: L2 projection of the GP onto the A2B lattice under the kernels the
# CMMs read (Argyll icclu: simplex <= 4 inputs, multilinear above; lcms:
# tetrahedral for 3, linear in the leading axes over tetrahedral in the last
# three for 4+). Both kernels' rows are stacked at weight 1/2, so one table
# serves both readouts. (Agent 3, Experiments/agent3/V0-kernel-check.txt.)
# ---------------------------------------------------------------------------

def _flat(i0, grid):
    flat = np.zeros(len(i0), dtype=np.int64)
    for d in range(i0.shape[1]):
        flat = flat * grid + i0[:, d]
    return flat


def simplex_weights(p01, grid, n, axes=None):
    idxf = np.clip(p01, 0.0, 1.0) * (grid - 1)
    i0 = np.clip(idxf.astype(int), 0, grid - 2)
    fr = idxf - i0
    npts = len(p01)
    sax = list(range(n)) if axes is None else list(axes)
    lax = [a for a in range(n) if a not in sax]
    fs = fr[:, sax]
    order = np.argsort(-fs, axis=1, kind="stable")
    fsorted = np.take_along_axis(fs, order, 1)
    m = len(sax)
    ws = np.empty((npts, m + 1))
    ws[:, 0] = 1.0 - fsorted[:, 0]
    for k in range(1, m):
        ws[:, k] = fsorted[:, k - 1] - fsorted[:, k]
    ws[:, m] = fsorted[:, m - 1]
    soff = np.zeros((npts, m + 1, n), dtype=np.int64)
    for k in range(1, m + 1):
        soff[:, k] = soff[:, k - 1]
        ax = np.asarray(sax)[order[:, k - 1]]
        soff[np.arange(npts), k, ax] += 1
    lc = np.stack(np.meshgrid(*([[0, 1]] * len(lax)), indexing="ij"),
                  -1).reshape(-1, len(lax)) if lax else np.zeros((1, 0), int)
    wl = np.ones((npts, len(lc)))
    for j, c in enumerate(lc):
        for d, a in enumerate(lax):
            wl[:, j] *= fr[:, a] if c[d] else 1.0 - fr[:, a]
    k_tot = len(lc) * (m + 1)
    w = np.empty((npts, k_tot))
    cols = np.empty((npts, k_tot), dtype=np.int64)
    t = 0
    for j, c in enumerate(lc):
        off_l = np.zeros(n, dtype=np.int64)
        for d, a in enumerate(lax):
            off_l[a] = c[d]
        for k in range(m + 1):
            w[:, t] = wl[:, j] * ws[:, k]
            cols[:, t] = _flat(i0 + soff[:, k] + off_l[None, :], grid)
            t += 1
    return w, cols


def joint_weights(p01, grid, n):
    from workflow.profile_engine.forward_model import _interp_weights
    w1, c1 = simplex_weights(p01, grid, n) if n <= 4 else \
        _interp_weights(p01, grid, n)
    w2, c2 = simplex_weights(p01, grid, n) if n <= 3 else \
        simplex_weights(p01, grid, n, axes=list(range(n - 3, n)))
    return np.hstack([0.5 * w1, 0.5 * w2]), np.hstack([c1, c2])


def project_to_table(gp, base_model, base_lam, seed=2929, max_nodes=150_000,
                     fine=False):
    """Nodes of ``base_model``'s lattice (its curves kept) that best
    reproduce the GP under the CMMs' kernels. Above ``max_nodes`` the grid
    is reduced by 2 per step (6 inks: 9 -> 7; 7 inks: 7 -> 5): a 6-ink
    grid-9 projection from 600,000 samples is under-determined (agent 3,
    F1 S5 seed 23: 0.356/1.83 vs 0.186/0.590 at grid 7)."""
    from workflow.profile_engine.forward_model import ForwardModel, _grid_solve
    grid, n = base_model.grid, base_model.n_channels
    curves = base_model.curves.copy()
    if fine:
        # Agent 3 "a2bfine": the finest odd grid <= 17 within the node
        # budget, evenly spaced nodes (Q3: the fitted shaper curves place
        # nodes worse than even spacing at every grid; the 9^4 lut16 alone
        # costs 0.10/0.31 dE00 at its source, 17^4 0.027/0.09).
        grid = 17
        curves = np.tile(np.linspace(0.0, 1.0, curves.shape[1]), (n, 1))
    while grid ** n > max_nodes and grid > 3:
        grid -= 2
    base_model = ForwardModel(grid=grid, n_channels=n,
                              nodes=np.zeros((1, 3)), curves=curves)
    g1 = np.linspace(0.0, 1.0, grid)
    mesh = np.stack(np.meshgrid(*([g1] * n), indexing="ij"), -1).reshape(-1, n)
    nodes = gp.predict(base_model.unshape_device(mesh))
    rng = np.random.default_rng(seed)
    ns = int(min(max(8 * grid ** n, 40000), 600_000))
    xs = rng.uniform(0.0, 1.0, (ns, n))
    ys = gp.predict(xs)
    w, cols = joint_weights(base_model.shape_device(xs), grid, n)
    nodes = _cg_solve(w, cols, ys, grid, n, 1e-4 * base_lam, 400, nodes,
                      rtol=1e-12)
    return ForwardModel(grid=grid, n_channels=n, nodes=nodes,
                        curves=curves)


def _cg_solve(w, cols, y, grid, n, lam, iters, x0, rtol=1e-12):
    """forward_model._grid_solve's normal equations and CG, with
    np.bincount for W'r (np.add.at made a 6-ink projection take an hour)."""
    ng = grid ** n
    fc = cols.reshape(-1)
    shape = (grid,) * n + (-1,)

    def wmul(x):
        return (w[:, :, None] * x[cols]).sum(1)

    def wtmul(r):
        return np.stack([np.bincount(fc, (w * r[:, c:c + 1]).reshape(-1),
                                     minlength=ng) for c in range(r.shape[1])], 1)

    def curv(x):
        x3 = x.reshape(shape)
        o = np.zeros_like(x3)
        for ax in range(n):
            lo = [slice(None)] * (n + 1)
            mid, hi = list(lo), list(lo)
            lo[ax], mid[ax], hi[ax] = slice(0, -2), slice(1, -1), slice(2, None)
            d2 = x3[tuple(lo)] - 2 * x3[tuple(mid)] + x3[tuple(hi)]
            o[tuple(lo)] += d2
            o[tuple(mid)] -= 2 * d2
            o[tuple(hi)] += d2
        return o.reshape(ng, -1)

    def amul(x):
        return wtmul(wmul(x)) + lam * curv(x) + 1e-7 * x

    b = wtmul(y)
    x = x0.copy()
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
