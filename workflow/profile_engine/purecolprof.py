"""Agent 58 (research token ``a58-purecolprof``): the RGB colorimetric B2A1
built exactly the way colprof builds it, on OUR forward model, with none of
the engine's own additions on that table.

What colprof does (ArgyllCMS 3.5.0, ``~/Downloads/Argyll_V3.5.0_orig``):

* ``profile/profout.c:510-555`` (``out_b2a_clut``, table 0): every B2A grid
  node is inverted on its own, ``inv_clut_aux`` on the node's Lab. No gamut
  mapping (``gammap`` is for tables 1 and 2 only), no smoothing or refit
  afterwards (``USE_LEASTSQUARES_APROX`` undefined, ``profout.c:82``), no PCS
  curves (``NO_B2A_PCS_CURVES``, ``:80``); the output curves are the inverse
  of the A2B input curves (``out_b2a_output``, ``:675-684``).
* ``xicc/xlut.c:1321-1418``: the node is first inverted in PCS Lab with the
  plain Euclidean nearest clip (the LCh weights go on the PCS table only
  when there is no CAM clip, ``xlut.c:2356-2365``). If it clipped, it is
  inverted again by nearest point in Argyll's CIECAM02 Jab (``USE_CAM_CLIP_OPT``,
  ``profout.c:81``, ``2287-2317``) with the LCh-weighted distance of
  ``rspl/rev.c:1804-1860``:
  ``4 dJ^2 + 1 dC^2 + 4.84 dH^2`` where ``dC = C1 - C2`` (difference of the
  chroma magnitudes) and ``dH^2 = dab^2 - dC^2`` (``xlut.c:108-111``,
  JCCWEIGHT 2, CCCWEIGHT 1, HCCWEIGHT 2.2, squared by ``rev_set_lchw``).
* The two device answers are blended LINEARLY over CAMCLIPTRANS = 1 unit of
  the CAM clip distance (``xlut.c:104``, ``1399-1418``; the spline blend
  ``USECAMCLIPSPLINE`` is undefined): ``bf = min(|Jab_clip - Jab_target|, 1)``.
* Black: for RGB nothing special. The L* 0 node gets whatever that clip
  finds; the device black (RGB 0) is only the black POINT used for the
  perceptual mapping (``xlut.c:3443-3447``), never pinned into B2A1. White:
  the relative A2B maps device white onto the PCS white exactly
  (``ICX_SET_WHITE``, ``xlut.c:3333-3350``), so the white node inverts to
  device white; the engine's ``pin_white_node`` gives the same answer and
  stays.

So ``a58-purecolprof`` drops, on the RGB colorimetric table only: the a29
dark floor, the a56 fade, the engine's own clip metric (a25/a51 frame:
Oklab hue frame, chroma-faded hue weight, 0.5-10 dE smoothstep band), the
neutral column handling (F-13 ``rgbcol``, ``a25-rgbcol``), the smoothing
refit (``refine_b2a_clut``), a44 / a44b, a42 / a45 (near-black column, B2A
curve space), the a40 dark bridge, the RGB 0 pin of the L* 0 node and the
b2a33s grid: B2A1 is written on colprof's grid for the quality
(``profout.c:1129-1146``, -qm 17 nodes), the per-node values sub-sampled
from the engine's 33 grid (the 17 Lab nodes are every other 33 node).

Each of those comes back on its own with a ``a58-keep-<step>`` token (only
read when ``a58-purecolprof`` is on), so the additions can be measured one
at a time. With every keep token on, the build is int-7 (with ``a56-
blackfade`` in the token set, int-7 + a56) byte for byte.
"""
from __future__ import annotations

import threading

import numpy as np

TOKEN = "a58-purecolprof"
# The engine's additions on the RGB colorimetric table, in add-back order.
KEEP_STEPS = ("black", "floor", "ourclip", "rgbcol", "refit", "a44", "a42",
              "a40", "grid33", "grid33in")
# keep-grid33in: in-gamut nodes keep the fine grid, clipped ones take the
# coarse (colprof) table, handed over over this many dE of clip distance
A58_IN_BAND = 2.0
# Agent 59 (a59-wideband): the hand-over band in dE of clip distance;
# CHROMIQ_A59_BAND overrides it for research sweeps
A59_BAND = 6.0


def a59_band(candidates):
    """The keep-grid33in hand-over band: A58_IN_BAND, or with a59-wideband
    A59_BAND (env CHROMIQ_A59_BAND for sweeps)."""
    if "a59-wideband" not in frozenset(candidates or ()):
        return None
    import os
    return float(os.environ.get("CHROMIQ_A59_BAND", A59_BAND))


def a59_fine(fine, pernode, residual, candidates):
    """a59-pernodefine: the fine table's CLIPPED nodes take the per-node
    inversion instead of the smoothing refit (as colprof writes them); the
    refit keeps the printable nodes. Handed over from 0.5 to 1.5 dE of clip
    distance (a converged in-gamut node stays under 0.5)."""
    if pernode is None or "a59-pernodefine" not in frozenset(candidates or ()):
        return fine
    u = np.clip((np.asarray(residual, float) - 0.5) / 1.0, 0.0, 1.0)
    v = (u * u * (3.0 - 2.0 * u))[:, None]
    return (1.0 - v) * fine + v * pernode


A59_EASE = 6.0
A59_EASE_C = 12.0


def a59_blackease(dev, node_lab, residual, black_dev, black_l):
    """a59-blackease: weight s = smoothstep(1 - L*/(black_l + ease)) x
    smoothstep(1 - C*/A59_EASE_C) x (clipped: residual 0.5 -> 1.5 dE),
    out = (1 - s) dev + s black_dev. The L* 0 corner (s = 1) stays the pin;
    printable nodes are untouched."""
    import os
    ease = float(os.environ.get("CHROMIQ_A59_EASE", A59_EASE))
    top = max(float(black_l) + ease, 1e-6)
    lab = np.asarray(node_lab, float)
    c = np.hypot(lab[:, 1], lab[:, 2])

    def sm(u):
        u = np.clip(u, 0.0, 1.0)
        return u * u * (3.0 - 2.0 * u)
    s = (sm(1.0 - lab[:, 0] / top) * sm(1.0 - c / A59_EASE_C)
         * sm(np.asarray(residual, float) - 0.5))
    return (1.0 - s[:, None]) * dev + s[:, None] * np.asarray(black_dev,
                                                             float)[None, :]


A59_IN_DEPTH = 10.0
A59_IN_STRENGTH = 1.0


def a59_inside(candidates):
    """a59-inband: (depth dE, strength) of the inward hand-over, or None
    (env CHROMIQ_A59_IN / CHROMIQ_A59_INS for sweeps)."""
    if "a59-inband" not in frozenset(candidates or ()):
        return None
    import os
    return (float(os.environ.get("CHROMIQ_A59_IN", A59_IN_DEPTH)),
            float(os.environ.get("CHROMIQ_A59_INS", A59_IN_STRENGTH)))


KEEP_TOKENS = tuple(f"a58-keep-{s}" for s in KEEP_STEPS)

# Argyll's clip constants (xicc/xlut.c:104-111)
CAMCLIPTRANS = 1.0
LCH_WEIGHTS = (2.0, 1.0, 2.2)

_LOCAL = threading.local()


def applies(candidates, *, accurate: bool, is_additive: bool,
            n: int) -> bool:
    """The token acts on RGB (3-channel additive) Maximum accuracy builds."""
    return bool(accurate and is_additive and n == 3
                and TOKEN in frozenset(candidates or ()))


def keep(candidates, step: str, *, active: bool) -> bool:
    """Does the engine's own ``step`` run on the colorimetric table?
    Always when a58 is not active (int-7 behaviour); with a58 only when its
    ``a58-keep-<step>`` token asks for it back."""
    if step not in KEEP_STEPS:
        raise ValueError(step)
    return (not active) or f"a58-keep-{step}" in frozenset(candidates or ())


def set_active(flag: bool, *, floor=None, fade: bool = False) -> None:
    """The builder marks the thread that inverts the colorimetric table
    (the perceptual / saturation tables may run on another thread).
    ``floor``: the a29 floor L* (keep-floor), ``fade``: a56 on top of it."""
    _LOCAL.on = bool(flag)
    _LOCAL.floor = None if (not flag or floor is None) else float(floor)
    _LOCAL.fade = bool(flag and fade and floor is not None)


def floor():
    return getattr(_LOCAL, "floor", None) if active() else None


def fade_fn(model):
    """a56's fade of the lifted targets (oog_clip.blackfade_targets, with
    the a51 metric it was built on), or None."""
    if not (active() and getattr(_LOCAL, "fade", False)):
        return None
    from workflow.profile_engine import oog_clip as _o
    fl = floor()
    p = dict(_o.PARAMS)
    p.update(_o.A51_PARAMS)
    fn = _o.space_fn(p["space"])
    return lambda t_lab, lift: _o.blackfade_targets(model, t_lab, lift, fl,
                                                    p, fn)


def active() -> bool:
    return bool(getattr(_LOCAL, "on", False))


# --- Argyll's LCh-weighted distance (rspl/rev.c LCHW_SQ) ------------------
def lchw_residual(y: np.ndarray, t: np.ndarray,
                  w=LCH_WEIGHTS) -> np.ndarray:
    """(N, 3) residual r with |r|^2 = wJ^2 dJ^2 + wC^2 dC^2 + wH^2 dH^2, the
    exact rev.c metric (dC = C_y - C_t, dH^2 = dab^2 - dC^2 >= 0):
    dH = 2 sqrt(C_y C_t) sin(dh / 2), signed and smooth in the hue angle."""
    y = np.atleast_2d(np.asarray(y, float))
    t = np.atleast_2d(np.asarray(t, float))
    cy = np.hypot(y[:, 1], y[:, 2])
    ct = np.hypot(t[:, 1], t[:, 2])
    dh = np.arctan2(y[:, 2], y[:, 1]) - np.arctan2(t[:, 2], t[:, 1])
    dh = (dh + np.pi) % (2.0 * np.pi) - np.pi
    dH = 2.0 * np.sqrt(cy * ct) * np.sin(0.5 * dh)
    return np.stack([w[0] * (y[:, 0] - t[:, 0]), w[1] * (cy - ct),
                     w[2] * dH], 1)


def lchw_sq(y: np.ndarray, t: np.ndarray, w=LCH_WEIGHTS) -> np.ndarray:
    """The rev.c weighted distance squared, written as rev.c writes it."""
    y = np.atleast_2d(np.asarray(y, float))
    t = np.atleast_2d(np.asarray(t, float))
    dl = y[:, 0] - t[:, 0]
    dchsq = (y[:, 1] - t[:, 1]) ** 2 + (y[:, 2] - t[:, 2]) ** 2
    dc = np.hypot(y[:, 1], y[:, 2]) - np.hypot(t[:, 1], t[:, 2])
    dhsq = np.maximum(dchsq - dc * dc, 0.0)
    return w[0] ** 2 * dl * dl + w[1] ** 2 * dc * dc + w[2] ** 2 * dhsq


def _cloud_seed(t_j: np.ndarray, cloud: np.ndarray,
                cloud_j: np.ndarray, block: int = 128) -> np.ndarray:
    """Cloud point of least rev.c distance for every target (exhaustive)."""
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


def _descend(predict_j, t_j: np.ndarray, d0: np.ndarray, *, iters: int = 12,
             damping: float = 1e-3, h: float = 1e-4) -> tuple:
    """Levenberg-Marquardt on the rev.c residual inside the device cube
    (active set: a channel on a face whose step points outward is held),
    never accepting a step that raises the distance (backtracking)."""
    d = np.clip(d0.astype(float).copy(), 0.0, 1.0)
    n = d.shape[1]
    r = lchw_residual(predict_j(d), t_j)
    c = (r * r).sum(1)
    eye = np.eye(n)
    for _ in range(iters):
        jac = np.empty((len(d), 3, n))
        for k in range(n):
            step = np.where(d[:, k] + h <= 1.0, h, -h)
            dk = d.copy()
            dk[:, k] += step
            jac[:, :, k] = (lchw_residual(predict_j(dk), t_j) - r) / step[:, None]
        jtj = np.einsum("nik,nil->nkl", jac, jac)
        lam = damping * (np.trace(jtj, axis1=1, axis2=2) / n + 1e-12)
        a = jtj + lam[:, None, None] * eye[None]
        g = np.einsum("nik,ni->nk", jac, r)
        stp = -np.linalg.solve(a, g[..., None])[..., 0]
        bad = ((d >= 1.0 - 1e-12) & (stp > 0)) | ((d <= 1e-12) & (stp < 0))
        if bad.any():
            jm = jac * (~bad)[:, None, :]
            a = np.einsum("nik,nil->nkl", jm, jm)
            a = a + (damping * (np.trace(a, axis1=1, axis2=2) / n + 1e-12)
                     )[:, None, None] * eye[None] + bad[:, :, None] * eye[None]
            g = np.einsum("nik,ni->nk", jm, r)
            stp = -np.linalg.solve(a, g[..., None])[..., 0]
            stp[bad] = 0.0
        acc = np.zeros(len(d), bool)
        for k in range(6):
            cand = np.clip(d + stp * (0.5 ** k), 0.0, 1.0)
            rc = lchw_residual(predict_j(cand), t_j)
            cc = (rc * rc).sum(1)
            good = (cc < c) & ~acc
            d[good] = cand[good]
            r[good] = rc[good]
            c[good] = cc[good]
            acc |= good
            if acc.all():
                break
        if not acc.any():
            break
    return d, c


def cam_clip(model, target_lab: np.ndarray, d_lab: np.ndarray,
             residual: np.ndarray, *, floor=None, fade=None,
             tol: float = 1e-3) -> np.ndarray:
    """colprof's colorimetric clip for every node that clipped in Lab.

    ``d_lab``: the plain Euclidean nearest-clip answer in PCS Lab for all
    nodes (``invert_to_device`` with no clip of its own); ``residual``: its
    Lab distance. Each clipped node (residual > tol) is re-solved by the
    rev.c LCh-weighted nearest point in Argyll's CIECAM02 Jab, and the two
    answers are blended linearly over CAMCLIPTRANS of the CAM clip
    distance (xlut.c:1399-1418). ``floor`` (keep-floor, the engine's a29
    addition, not colprof): a target below that L* aims at it; ``fade``
    (a56, with the floor): callable(t_lab_lifted, lift) -> faded targets.
    A lifted node hands over to the CAM answer over 1 L* of lift (as
    clip_nodes does)."""
    from workflow.profile_engine.oog_clip import (clip_cloud,
                                                  lab_to_argyll_jab)
    out = np.array(d_lab, float, copy=True)
    sel = np.flatnonzero(np.asarray(residual) > tol)
    if not len(sel):
        return out
    t_lab = np.asarray(target_lab, float)[sel].copy()
    lift = np.zeros(len(sel))
    if floor is not None:
        new_l = np.maximum(t_lab[:, 0], float(floor))
        lift = new_l - t_lab[:, 0]
        if (lift > 0).any():
            t_lab[:, 0] = new_l
            if fade is not None:
                t_lab = fade(t_lab, lift)

    def predict_j(dev):
        return lab_to_argyll_jab(model.predict(dev))

    t_j = lab_to_argyll_jab(t_lab)
    n = model.n_channels
    cloud = clip_cloud(n, None, None, np.random.default_rng(5858),
                       light=True, faces=True)
    seed_c = _cloud_seed(t_j, cloud, predict_j(cloud))
    best, best_c = _descend(predict_j, t_j, d_lab[sel])
    d2, c2 = _descend(predict_j, t_j, seed_c)
    take = c2 < best_c
    best[take] = d2[take]
    cdist = np.linalg.norm(predict_j(best) - t_j, axis=1)
    bf = np.clip(cdist / CAMCLIPTRANS, 0.0, 1.0)
    u = np.clip(lift, 0.0, 1.0)              # as clip_nodes (dm_blend 1)
    bf = np.maximum(bf, u * u * (3.0 - 2.0 * u))
    out[sel] = (1.0 - bf)[:, None] * out[sel] + bf[:, None] * best
    return out


def coarse_outside(fine: np.ndarray, coarse: np.ndarray, residual: np.ndarray,
                   g_fine: int, g_coarse: int,
                   band: float | None = None,
                   inside: tuple | None = None) -> np.ndarray:
    """Agent 58, keep-grid33in: the fine-grid table where the node is in
    gamut and the coarse grid (trilinear, exact at the shared nodes) where it
    clipped: w = smoothstep(residual / band), out = (1 - w) fine + w coarse."""
    band = A58_IN_BAND if band is None else float(band)
    n = fine.shape[1]
    c = coarse.reshape(g_coarse, g_coarse, g_coarse, n)
    x = np.linspace(0.0, g_coarse - 1.0, g_fine)
    i0 = np.minimum(np.floor(x).astype(int), g_coarse - 2)
    f = x - i0
    up = np.zeros((g_fine, g_fine, g_fine, n))
    for a in (0, 1):
        wa = (f if a else 1.0 - f)[:, None, None, None]
        for b in (0, 1):
            wb = (f if b else 1.0 - f)[None, :, None, None]
            for d in (0, 1):
                wd = (f if d else 1.0 - f)[None, None, :, None]
                up += wa * wb * wd * c[np.ix_(i0 + a, i0 + b, i0 + d)]
    up = up.reshape(-1, n)
    u = np.clip(np.asarray(residual, float) / max(band, 1e-9), 0.0, 1.0)
    w = u * u * (3.0 - 2.0 * u)
    if inside is not None:
        # Agent 59 (a59-inband): printable nodes within ``depth`` dE of a
        # clipped node lean toward the coarse table too, so the clip's bend
        # starts a little inside the gamut, as colprof's coarse grid does
        depth, strength = inside
        d = depth_inside(np.asarray(residual, float), g_fine, depth)
        v = np.clip(1.0 - d / max(depth, 1e-9), 0.0, 1.0)
        # printable nodes only: the clipped ones keep the outward band
        v = np.where(np.asarray(residual, float) <= 1.0, v, 0.0)
        w = np.maximum(w, strength * v * v * (3.0 - 2.0 * v))
    w = w[:, None]
    return (1.0 - w) * fine + w * up


def depth_inside(residual: np.ndarray, g: int, depth: float,
                 clipped_at: float = 1.0) -> np.ndarray:
    """Lab distance (dE76, node centres on the B2A grid) from each node to
    the nearest clipped node (residual > clipped_at), searched up to
    ``depth``; inf where none is that close. Clipped nodes get 0."""
    from workflow.profile_engine.icc_writer import lab_grid_axes
    la, ab = lab_grid_axes(g)
    sl, sab = float(la[1] - la[0]), float(ab[1] - ab[0])
    cl = (residual > clipped_at).reshape(g, g, g)
    best = np.where(cl, 0.0, np.inf)
    rl, rab = int(np.ceil(depth / sl)), int(np.ceil(depth / sab))
    for i in range(-rl, rl + 1):
        for j in range(-rab, rab + 1):
            for k in range(-rab, rab + 1):
                dist = np.sqrt((i * sl) ** 2 + (j * sab) ** 2 + (k * sab) ** 2)
                if dist == 0 or dist > depth:
                    continue
                sh = np.zeros_like(cl)
                src = cl[max(i, 0):g + min(i, 0), max(j, 0):g + min(j, 0),
                         max(k, 0):g + min(k, 0)]
                sh[max(-i, 0):g + min(-i, 0), max(-j, 0):g + min(-j, 0),
                   max(-k, 0):g + min(-k, 0)] = src
                best = np.where(sh & (dist < best), dist, best)
    return best.reshape(-1)
