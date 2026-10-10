"""Forward model: device (n-D) → Lab, fitted from real measurements (maths A).

A regularised multilinear grid fit — structurally what Argyll's rspl does —
with per-channel monotone *input shaper curves* fitted alternately with the
grid (colprof xlut's "in & out optimising"; measured on the real fixtures:
the curves are what removes the off-sample error tail that a bare grid
leaves).

The fitted curves and grid map 1:1 onto an ``mft2`` A2B tag: curves → the
input shaper tables, grid nodes → the CLUT (same resolution, so the LUT
reproduces the fit exactly, no resampling error).

Numpy-only; conjugate-gradient normal equations. Grid solve cost is
O(N·2ⁿ + Gⁿ) per iteration — a 6-channel grid-9 fit (531 441 nodes) stays in
the seconds range.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ForwardModel:
    grid: int                      # nodes per axis
    n_channels: int
    nodes: np.ndarray              # (grid**n, 3) Lab at grid nodes
    curves: np.ndarray             # (n, K) monotone 0..1 → 0..1 input shapers

    def shape_device(self, dev: np.ndarray) -> np.ndarray:
        """Apply the input shaper curves: device 0..1 → grid coordinate 0..1."""
        k = self.curves.shape[1]
        xp = np.linspace(0.0, 1.0, k)
        out = np.empty_like(dev)
        for c in range(self.n_channels):
            out[:, c] = np.interp(dev[:, c], xp, self.curves[c])
        return out

    def unshape_device(self, shaped: np.ndarray) -> np.ndarray:
        """Inverse of :meth:`shape_device` (curves are monotone)."""
        k = self.curves.shape[1]
        xp = np.linspace(0.0, 1.0, k)
        out = np.empty_like(shaped)
        for c in range(self.n_channels):
            out[:, c] = np.interp(shaped[:, c], self.curves[c], xp)
        return out

    def predict(self, dev: np.ndarray) -> np.ndarray:
        """(N, n) device 0..1 → (N, 3) Lab.

        Every row is interpolated on its own, so in a Maximum accuracy
        build a large batch is split into row blocks on pool threads with
        the same bits (D-06); elsewhere it is one serial call."""
        from workflow.profile_engine import parallel
        if len(dev) >= 16384 and parallel.in_accurate_scope() \
                and parallel.worker_count() > 1:
            out = np.empty((len(dev), 3))

            def block(lo: int, hi: int) -> None:
                out[lo:hi] = self._predict_rows(dev[lo:hi])
            parallel.run_chunks(block, parallel.chunk_bounds(
                len(dev), parallel.worker_count(), min_rows=8192))
            return out
        return self._predict_rows(dev)

    def _predict_rows(self, dev: np.ndarray) -> np.ndarray:
        w, cols = _interp_weights(self.shape_device(dev), self.grid,
                                  self.n_channels)
        return (w[:, :, None] * self.nodes[cols]).sum(1)

    def clut_lab(self) -> np.ndarray:
        """The A2B CLUT contents (= the grid nodes, first axis slowest)."""
        return self.nodes


def _corners(n: int) -> np.ndarray:
    return np.stack(np.meshgrid(*([[0, 1]] * n), indexing="ij"),
                    -1).reshape(-1, n)


def _interp_weights(p01: np.ndarray, grid: int, n: int
                    ) -> tuple[np.ndarray, np.ndarray]:
    """Multilinear weights: (N, 2ⁿ) weights + flat node columns."""
    corners = _corners(n)
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


def _grid_solve(w: np.ndarray, cols: np.ndarray, y: np.ndarray, grid: int,
                n: int, lam: float, iters: int, x0: np.ndarray | None = None,
                rtol: float = 0.0) -> np.ndarray:
    """CG on (WᵀW + λ LᵀL + εI) x = Wᵀy — the maths-A normal equations."""
    ng = grid ** n
    shape = (grid,) * n + (-1,)

    def wmul(x: np.ndarray) -> np.ndarray:
        return (w[:, :, None] * x[cols]).sum(1)

    def wtmul(r: np.ndarray) -> np.ndarray:
        # np.bincount accumulates in input order exactly like np.add.at
        # (same products, same sequence of additions from 0.0, so the same
        # bits; Experiments/agent8 addat_vs_bincount.py and
        # tests/test_engine_parallel_identity.py) at a fraction of the cost.
        fc = cols.reshape(-1)
        return np.stack([np.bincount(fc, (w * r[:, c:c + 1]).reshape(-1),
                                     minlength=ng)
                         for c in range(r.shape[1])], 1)

    def curvature(x: np.ndarray) -> np.ndarray:
        """Σ_axis D₂ᵀD₂ x — second-difference penalty, interior rows only.

        Symmetric PSD by construction (required by CG); its null space is the
        per-axis linear functions, so unmeasured regions fill by smooth
        linear interpolation/extrapolation from the data instead of decaying
        toward zero (a zero decay puts a fake Lab(0,0,0) "black" into empty
        corners — measured: it captured every deep-shadow B2A inversion).
        """
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

    # D-06 (agent 8): in a Maximum accuracy build with a large lattice
    # (5+ inks: 9^6 = 531,441 nodes, two thirds of the fit's CPU) the
    # curvature runs one Lab column per pool thread. The operator is purely
    # element-wise per column, so each column's numbers are the same bits
    # as in the (grid..., 3) array; Fast and Bit-exact never take this path.
    from workflow.profile_engine import parallel as _par
    col_threads = (ng >= 100_000 and _par.in_accurate_scope()
                   and _par.worker_count() > 1)

    def curvature_cols(x: np.ndarray) -> np.ndarray:
        out = np.empty_like(x)

        def one(c: int):
            def run():
                out[:, c] = curvature(np.ascontiguousarray(x[:, c:c + 1]))[:, 0]
            return run
        _par.run_tasks([one(c) for c in range(x.shape[1])])
        return out

    curv = curvature_cols if col_threads else curvature

    def amul(x: np.ndarray) -> np.ndarray:
        return wtmul(wmul(x)) + lam * curv(x) + 1e-7 * x

    b = wtmul(y)
    x = np.zeros((ng, y.shape[1])) if x0 is None else x0.copy()
    r = b - amul(x)
    p = r.copy()
    rs = (r * r).sum()
    # rtol: optional relative termination (squared-residual scale) — the
    # absolute 1e-9 over/under-iterates depending on problem magnitude.
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


def fit_forward_model(device: np.ndarray, lab: np.ndarray, *, grid: int,
                      lam: float = 0.01, cg_iters: int = 800,
                      curve_knots: int = 21, curve_rounds: int = 2,
                      weights: np.ndarray | None = None,
                      cg_rtol: float = 0.0,
                      init_curves: np.ndarray | None = None,
                      ) -> ForwardModel:
    """Alternating curves ⇄ grid fit of device → Lab.

    ``curve_rounds = 0`` gives the bare grid fit (P1 baseline); each round
    refits every channel's monotone shaper by coordinate descent against the
    current grid, then re-solves the grid with the shaped inputs.
    ``weights``: optional per-patch weights (robust IRLS in maximum-accuracy
    mode) — they scale the least-squares rows, not the smoothing.
    ``init_curves``: (n, curve_knots) starting shaper curves (maximum
    accuracy's ramp positioning, :func:`ramp_positioning_curves`); None =
    the identity, as every other mode has always used.
    """
    npts, n = device.shape
    if init_curves is None:
        curves = np.tile(np.linspace(0.0, 1.0, curve_knots), (n, 1))
    else:
        curves = np.array(init_curves, float, copy=True)
    model = ForwardModel(grid=grid, n_channels=n,
                         nodes=np.zeros((grid ** n, 3)), curves=curves)
    sw = None if weights is None else np.sqrt(np.asarray(weights, float))

    def solve(x0: np.ndarray | None = None) -> None:
        shaped = model.shape_device(device)
        w, cols = _interp_weights(shaped, grid, n)
        if sw is None:
            model.nodes = _grid_solve(w, cols, lab, grid, n, lam, cg_iters,
                                      x0, rtol=cg_rtol)
        else:
            model.nodes = _grid_solve(w * sw[:, None], cols,
                                      lab * sw[:, None], grid, n, lam,
                                      cg_iters, x0, rtol=cg_rtol)

    solve()
    xp = np.linspace(0.0, 1.0, curve_knots)
    for _ in range(curve_rounds):
        for c in range(n):
            _refit_curve(model, device, lab, c, xp, weights=weights)
        solve(model.nodes)
    return model


def ramp_positioning_curves(device: np.ndarray, lab: np.ndarray, *,
                            knots: int = 21, blend: float = 0.5,
                            min_ramp: int = 3) -> np.ndarray:
    """Shaper curves placed by the chart's own single-ink ramps (ink devices).

    For each channel the patches that carry that ink alone, plus the paper,
    give the visual distance travelled from paper (cumulative ΔE76 along the
    ramp). The curve maps ink to that distance, normalised, blended half way
    with the identity so every grid cell keeps some ink range. A printer's
    dot gain makes the first few per cent of ink move the colour most; with
    identity curves those few per cent share the first grid cell with paper
    and the model read light tints as far too light (research agent5-03,
    D6: Clapper-Yule CMYK neutral highlights 2.24 -> 0.36 ΔE00 model error).
    A channel with fewer than ``min_ramp`` single-ink patches keeps the
    identity. Curves are monotone, pinned at 0 and 1.
    """
    n = device.shape[1]
    xp = np.linspace(0.0, 1.0, knots)
    out = np.tile(xp, (n, 1))
    inked = device > 1e-6
    paper = ~inked.any(1)
    if not paper.any():
        return out
    white = lab[paper].mean(0)
    single = inked.sum(1) == 1
    for c in range(n):
        rows = single & inked[:, c]
        if rows.sum() < min_ramp:
            continue
        x = np.concatenate([[0.0], device[rows, c]])
        y = np.vstack([white, lab[rows]])
        order = np.argsort(x, kind="stable")
        x, y = x[order], y[order]
        # duplicates of one ink value: their mean colour
        ux, inv = np.unique(x, return_inverse=True)
        uy = np.zeros((len(ux), 3))
        np.add.at(uy, inv, y)
        uy /= np.bincount(inv)[:, None]
        if ux[-1] < 0.5:
            continue
        dist = np.concatenate(
            [[0.0], np.cumsum(np.linalg.norm(np.diff(uy, axis=0), axis=1))])
        if dist[-1] <= 1e-9:
            continue
        # beyond the last measured ink the ramp continues at its last slope
        xs = np.append(ux, 1.0) if ux[-1] < 1.0 else ux
        ds = dist if ux[-1] >= 1.0 else np.append(
            dist, dist[-1] + (1.0 - ux[-1]) * (dist[-1] - dist[-2])
            / max(ux[-1] - ux[-2], 1e-9))
        pos = np.interp(xp, xs, ds / ds[-1])
        cur = blend * pos + (1.0 - blend) * xp
        cur = np.maximum.accumulate(cur)
        cur = (cur - cur[0]) / max(cur[-1] - cur[0], 1e-9)
        out[c] = cur
    return out


def ramp_positioning_curves_mixed(device: np.ndarray, lab: np.ndarray, *,
                                  light_blend: float = 0.25,
                                  band: tuple = (0.65, 0.9),
                                  knots: int = 21, min_ramp: int = 3
                                  ) -> np.ndarray:
    """Research (Agent 38 s6, token a40-knut-grey): the ramp curves with a
    gentler placement (``light_blend`` instead of 0.5) over the light part
    of each channel's ink range, handed over by a smoothstep across
    ``band`` (ink fraction) to the shipped placement at the dark end, so the
    dark corner keeps the lattice the shipped curves give it. Knut's laser
    chart, ten-fold held-out: 1.767 shipped, 1.526 mixed (colprof 1.721);
    grey column 2.44 -> 1.69 (colprof 1.77)."""
    a = ramp_positioning_curves(device, lab, knots=knots, blend=light_blend,
                                min_ramp=min_ramp)
    b = ramp_positioning_curves(device, lab, knots=knots, blend=0.5,
                                min_ramp=min_ramp)
    xp = np.linspace(0.0, 1.0, knots)
    lo, hi = band
    t = np.clip((xp - lo) / (hi - lo), 0.0, 1.0)
    w = t * t * (3.0 - 2.0 * t)
    return np.maximum.accumulate((1.0 - w) * a + w * b, axis=1)


# Research token "a45b-shaperfloor" (Agent 45, Findings/agent45-01-darkend.md
# s8): the shaper refit may not make any knot interval flatter than this
# slope (None: only kept monotone, 1e-4 apart). The shipped ramp curves
# guarantee half the identity's slope ("so every grid cell keeps some ink
# range"); the refit could collapse an interval between two chart levels to
# a sliver (i1iSis K 0.60-0.65, slope 0.13, between the chart's K 0.5 and
# 0.69), where the model then reads the ink as doing nothing: the neutral
# column put a node there that every reference prints 2.4 L* lighter than
# the model (a light band at printed L* 31-33). Set per build by
# b2a.set_research_tokens.
SHAPER_FLOOR: dict = {"slope": None}
# Agent 51 (token a51-shapersmooth): colprof's input curves cannot fold a
# single knot interval flat, because xfit builds them from a few harmonics
# whose higher orders are penalised (xicc/xfit.c SHAPE_WEIGHT, SHAPE_HW01,
# SHAPE_HWBR, SHAPE_HWINC); a stretch of ink no patch constrains (i1iSis:
# K 0.5 to 0.69) is filled smoothly. Here the same idea as a curvature
# penalty on the shaper refit: mu x (the fit error at the start of the
# refit, mu 0.01: Agent 51 sweep) x the sum of squared changes of the knot slopes, relative to the
# curve the refit started from (so measured curvature stays free; a new
# fold costs). None = off (the plain refit).
SHAPER_SMOOTH: dict = {"mu": None}


def _refit_curve(model: ForwardModel, device: np.ndarray, lab: np.ndarray,
                 channel: int, xp: np.ndarray,
                 weights: np.ndarray | None = None) -> None:
    """Coordinate descent on one channel's shaper knots (monotone-projected)."""
    knots = model.curves[channel].copy()
    k = len(knots)
    n = model.n_channels
    # The other channels' shaped coordinates don't change during this
    # channel's refit — precompute them once and only re-interpolate the
    # channel under test per trial (identical numbers, ~n× fewer interps).
    shaped = model.shape_device(device)
    wts = None if weights is None else np.asarray(weights, float)

    def fit_err(kn: np.ndarray) -> float:
        model.curves[channel] = kn
        shaped[:, channel] = np.interp(device[:, channel], xp, kn)
        w, cols = _interp_weights(shaped, model.grid, n)
        r2 = (((w[:, :, None] * model.nodes[cols]).sum(1) - lab) ** 2).sum(1)
        return float(r2.sum() if wts is None else (wts * r2).sum())

    mu = SHAPER_SMOOTH["mu"]
    if mu is None:
        err = fit_err
    else:
        d2_0 = np.diff(knots, 2) * (k - 1)
        scale = float(mu) * max(fit_err(knots), 1e-12)

        def err(kn: np.ndarray) -> float:
            d2 = np.diff(kn, 2) * (k - 1) - d2_0
            return fit_err(kn) + scale * float((d2 * d2).sum())

    base = err(knots)
    step = 1.0 / (k - 1) / 2.0
    gap = 1e-4
    if SHAPER_FLOOR["slope"] is not None and np.all(
            np.diff(knots) >= SHAPER_FLOOR["slope"] / (k - 1) - 1e-12):
        gap = SHAPER_FLOOR["slope"] / (k - 1)   # a45b: only from a feasible start
    for _ in range(3):                      # a few sweeps, halving the step
        improved = False
        for j in range(1, k - 1):           # endpoints pinned at 0 and 1
            for delta in (step, -step):
                trial = knots.copy()
                trial[j] = np.clip(trial[j] + delta,
                                   trial[j - 1] + gap, trial[j + 1] - gap)
                e = err(trial)
                if e < base - 1e-9:
                    knots, base, improved = trial, e, True
                    break
        step /= 2.0
        if not improved and step < 1e-3:
            break
    model.curves[channel] = knots
