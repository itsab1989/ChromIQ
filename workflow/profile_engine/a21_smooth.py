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


def blend_black(model, axis: dict, *, span: float = 10.0, ink_limit=None,
                channel_max=None, weight: float = 1.0) -> dict:
    """Agent 21 D4 ("a21-blendblack"): the dark end of the neutral axis as a
    colour-exact projection of the STRAIGHT device line from the axis at
    L*_black + span to the neutral black. A straight line is monotone in every
    ink, so the CMY-for-spot-ink swap the walk makes in the last few L* (the
    S5/S6 TV excess of agent9-01 6.2) turns into one monotone hand-over, and
    the black itself (depth and device value) is kept exactly."""
    if axis.get("black") is None or axis.get("l_black") is None:
        return axis
    ls, dev, ok = np.asarray(axis["l"]), np.array(axis["dev"], float), np.asarray(axis["ok"], bool)
    lb = float(axis["l_black"])
    join = lb + span
    cand = np.flatnonzero(ok & (ls >= join))
    if not len(cand):
        return axis
    j0 = int(cand[np.argmin(ls[cand])])
    seg = np.flatnonzero((ls < ls[j0]) & (ls > lb))
    if not len(seg):
        return axis
    t = (ls[j0] - ls[seg]) / max(ls[j0] - lb, 1e-9)
    p = (1.0 - t)[:, None] * dev[j0][None, :] + t[:, None] * np.asarray(axis["black"])[None, :]
    tgt = np.stack([ls[seg], np.zeros(len(seg)), np.zeros(len(seg))], 1)
    w = np.full_like(p, weight)
    d_new, good = b2a_mod.project_metamers(model, tgt, p, p, w, ink_limit=ink_limit,
                                           channel_max=channel_max, iters=10)
    out = dict(axis)
    nd = dev.copy()
    nd[seg[good]] = d_new[good]
    out["dev"] = nd
    out["a21_blend"] = {"join_L": float(ls[j0]), "replaced": int(good.sum()), "of": int(len(seg))}
    return out
