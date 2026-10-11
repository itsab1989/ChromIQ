"""Research Agent 53 (a53-smoothinv): invert a SMOOTHER copy of the forward model.

Hypothesis (RESUME s60): colprof's relative colorimetric B2A is a per-node
inversion with no smoothing of its own (profout.c:529-555), so its evenness
comes from the forward model it inverts: an rspl fitted with a curvature
penalty sized from the measurement's average deviation (colprof -r, default
0.5 %, colprof.c:73). Ours inverts a more accurate, less smooth A2B and
inherits its wiggles.

The candidate keeps the A2B exactly as fitted and builds the colorimetric
B2A (token ``a53-smoothinv``; with ``a53-smoothinv-all`` also the perceptual
and saturation tables) from a copy whose grid is smoothed by a second-
difference (curvature) penalty, the same operator the grid fit uses
(forward_model._grid_solve):

    min_x  sum_i w_i |x_i - N_i|^2  +  mu * |L x|^2

The strength is not a free knob. It is set by the discrepancy principle
against colprof's own noise assumption: mu is the largest value at which the
smoothed model's prediction at the measured patches moves, on average, by
colprof's default average deviation (0.5 % of the 0-100 range, i.e. 0.5 per
Lab component, mean absolute). In plain words: the smoothed copy may differ
from ours only by as much as colprof assumes the readings are wrong anyway.
``CHROMIQ_A53_AVGDEV`` overrides the target (research only).

The paper-white corner is held exactly (heavy weight), and so is the node the
model prints darkest, so neither the white pin nor the black moves.
"""
from __future__ import annotations

import dataclasses
import os

import numpy as np

A53_TOKEN = "a53-smoothinv"
A53_ALL_TOKEN = "a53-smoothinv-all"
A53_AVGDEV = 0.5          # colprof DEFAVGDEV 0.5 % of the 0-100 range
_PIN_W = 1.0e6


def a53_mode(candidates) -> str | None:
    """None, "b2a1" (colorimetric table only) or "all" (every B2A)."""
    t = frozenset(candidates or ())
    if A53_ALL_TOKEN in t:
        return "all"
    if A53_TOKEN in t:
        return "b2a1"
    return None


def avgdev_target() -> float:
    v = os.environ.get("CHROMIQ_A53_AVGDEV")
    try:
        return float(v) if v else A53_AVGDEV
    except ValueError:
        return A53_AVGDEV


def curvature(x: np.ndarray, grid: int, n: int) -> np.ndarray:
    """sum over axes of D2^T D2 x (interior second differences), as
    forward_model._grid_solve; the null space is the per-axis linear
    functions, so smoothing never pulls a linear trend in."""
    shape = (grid,) * n + (-1,)
    x3 = x.reshape(shape)
    o = np.zeros_like(x3)
    mid = [slice(None)] * (n + 1)
    lo = [slice(None)] * (n + 1)
    hi = [slice(None)] * (n + 1)
    for ax in range(n):
        mid[ax] = slice(1, -1)
        lo[ax] = slice(0, -2)
        hi[ax] = slice(2, None)
        d2 = x3[tuple(lo)] - 2 * x3[tuple(mid)] + x3[tuple(hi)]
        o[tuple(lo)] += d2
        o[tuple(mid)] -= 2 * d2
        o[tuple(hi)] += d2
        mid[ax] = lo[ax] = hi[ax] = slice(None)
    return o.reshape(x.shape)


def smooth_nodes(nodes: np.ndarray, grid: int, n: int, mu: float,
                 pins: np.ndarray, iters: int = 400) -> np.ndarray:
    """Solve (W + mu L^T L) x = W N by CG (W = 1, pins heavy)."""
    if mu <= 0.0:
        return nodes.copy()
    w = np.ones(len(nodes))
    w[np.asarray(pins, int)] = _PIN_W
    # Jacobi-preconditioned CG: the pin rows are 1e6 x the others
    diag = w + mu * 6.0 * n
    b = w[:, None] * nodes

    def amul(x):
        return w[:, None] * x + mu * curvature(x, grid, n)

    x = nodes.copy()
    r = b - amul(x)
    z = r / diag[:, None]
    p = z.copy()
    rz = (r * z).sum()
    stop = 1e-20 * max((b * b).sum(), 1.0)
    for _ in range(iters):
        ap = amul(p)
        alpha = rz / max((p * ap).sum(), 1e-30)
        x += alpha * p
        r -= alpha * ap
        if (r * r).sum() < stop:
            break
        z = r / diag[:, None]
        rz2 = (r * z).sum()
        p = z + (rz2 / rz) * p
        rz = rz2
    return x


def _pins(model) -> np.ndarray:
    """The paper-white corner (the node the model holds at L* 100, 0, 0)
    and the darkest node."""
    nodes = model.nodes
    white = int(np.argmin(np.linalg.norm(nodes - [100.0, 0.0, 0.0], axis=1)))
    black = int(np.argmin(nodes[:, 0]))
    return np.unique([white, black])


def smoothed_copy(model, device: np.ndarray, *, target: float | None = None,
                  rounds: int = 14):
    """A copy of ``model`` whose grid is smoothed until its prediction at the
    measured ``device`` values moves by ``target`` (mean absolute per Lab
    component); curves are shared (the same B2A curve space). Returns
    (model_copy, info)."""
    target = avgdev_target() if target is None else float(target)
    grid, n = model.grid, model.n_channels
    pins = _pins(model)
    base = model.predict(device)

    def at(mu):
        nodes = smooth_nodes(model.nodes, grid, n, mu, pins)
        m = dataclasses.replace(model, nodes=nodes)
        return m, float(np.mean(np.abs(m.predict(device) - base)))

    lo, hi = 0.0, 1.0
    m_hi, d_hi = at(hi)
    while d_hi < target and hi < 1e6:
        lo, hi = hi, hi * 10.0
        m_hi, d_hi = at(hi)
    best, best_d, best_mu = (model, 0.0, 0.0)
    if d_hi <= target:
        best, best_d, best_mu = m_hi, d_hi, hi
    else:
        for _ in range(rounds):            # bisection in log(mu)
            mid = np.sqrt(hi * max(lo, hi * 1e-4)) if lo > 0 else hi / 10.0
            m, d = at(mid)
            if d <= target:
                lo, best, best_d, best_mu = mid, m, d, mid
            else:
                hi = mid
            if lo > 0 and hi / lo < 1.05:
                break
    moved = np.linalg.norm(best.nodes - model.nodes, axis=1)
    return best, {"mu": best_mu, "avgdev": best_d, "target": target,
                  "node_move_p95": float(np.percentile(moved, 95)),
                  "node_move_max": float(moved.max())}
