"""Agent 21 D2 ("a21-smooth", research token, off by default): smooth-then-reproject
separation field (Findings/agent21-01 s3.0).

Alternate (a) a masked Gaussian smoothing of the per-node separation over the
in-gamut nodes of the B2A grid and (b) the colour-exact projection of every
in-gamut node onto its metamer set nearest the smoothed field
(b2a.project_metamers). The colour of an in-gamut node never changes in the
model; only the choice among metamers becomes a smooth function of the PCS.
Continuous version of the smoothness index of Chen, Berns, Taplin, Imai 2008
(JIST 52(2), eq. 4 and 7).
"""
from __future__ import annotations

import numpy as np

from workflow.profile_engine import b2a as b2a_mod


def _gauss_kernel(sigma: float) -> np.ndarray:
    r = max(1, int(np.ceil(2.5 * sigma)))
    x = np.arange(-r, r + 1, dtype=float)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    return k / k.sum()


def _conv_axis(a: np.ndarray, k: np.ndarray, axis: int) -> np.ndarray:
    r = len(k) // 2
    a = np.moveaxis(a, axis, 0)
    pad = np.concatenate([np.zeros((r,) + a.shape[1:]), a,
                          np.zeros((r,) + a.shape[1:])], 0)
    out = np.zeros_like(a)
    for i, w in enumerate(k):
        out += w * pad[i:i + a.shape[0]]
    return np.moveaxis(out, 0, axis)


def masked_smooth(dev: np.ndarray, mask: np.ndarray, grid: int,
                  sigma: float) -> np.ndarray:
    """Normalised Gaussian smoothing of (grid**3, n) values over the masked nodes."""
    n = dev.shape[1]
    f = (dev * mask[:, None]).reshape(grid, grid, grid, n)
    m = mask.astype(float).reshape(grid, grid, grid)
    k = _gauss_kernel(sigma)
    for ax in range(3):
        f = _conv_axis(f, k, ax)
        m = _conv_axis(m, k, ax)
    out = f.reshape(-1, n) / np.maximum(m.reshape(-1), 1e-9)[:, None]
    return np.where(mask[:, None], out, dev)


def smooth_reproject(model, node_lab: np.ndarray, dev: np.ndarray,
                     residual: np.ndarray, grid: int, *, prior: np.ndarray,
                     prior_w: np.ndarray, ink_limit: float | None,
                     channel_max: np.ndarray | None, rounds: int = 4,
                     sigma: float = 1.0, weight: float = 1.0,
                     fixed_nodes: np.ndarray | None = None,
                     progress=None) -> tuple[np.ndarray, np.ndarray]:
    """Return (dev, field) where field is the final smoothed policy target."""
    mask = residual < 0.5
    if fixed_nodes is not None and len(fixed_nodes):
        keep = np.zeros(len(dev), bool)
        keep[fixed_nodes] = True
    else:
        keep = np.zeros(len(dev), bool)
    move = mask & ~keep
    d = dev.copy()
    field = d
    for r in range(rounds):
        if progress is not None:
            progress(f"Inverting the model: smoothing the separation {r + 1}/{rounds}…")
        field = masked_smooth(d, mask, grid, sigma)
        # policy priors where they are firm (neutral K, ECG rules) win over
        # the smoothed field; elsewhere the field decides
        w = np.maximum(prior_w, weight)
        tgt = np.where(prior_w > weight, prior, field)
        idx = np.flatnonzero(move)
        d_new, ok = b2a_mod.project_metamers(
            model, node_lab[idx], d[idx], tgt[idx], w[idx], ink_limit=ink_limit,
            channel_max=channel_max)
        d[idx] = d_new
    return d, masked_smooth(d, mask, grid, sigma)


def field_prior(field: np.ndarray, grid: int, to01, weight: float = 1.0):
    """Callable for b2a.HARD_COLOUR["smooth_p"]: the smoothed node field
    interpolated at any PCS target (trilinear in the codec's 0..1 space)."""
    from workflow.profile_engine.forward_model import _interp_weights

    def f(target, prior, prior_w):
        w, cols = _interp_weights(to01(target), grid, 3)
        p = (w[:, :, None] * field[cols]).sum(1)
        ww = np.maximum(prior_w, weight)
        return np.where(prior_w > weight, prior, p), ww
    return f
