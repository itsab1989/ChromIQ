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


# Agent 60 (a60-darkfine): in the dark the keep-grid33in hand-over keeps
# the fine grid (int-7's exact inversion) for nodes up to A60_L L* (blended
# out over A60_W L* above it); A60_C, if set, is the hand-over band (dE of
# clip distance) the dark nodes get instead of an unlimited one
A60_L = 30.0
A60_W = 10.0
A60_C = None
# a60-darkacc (the candidate, Findings/agent60-01): darkfine + darkrel +
# darkclip with these: the fine grid kept up to 10 L* above the printer's
# black (hand-over band 16 dE there), blended out over the next 10 L*; the
# engine's own clip below the black, blended out over 10 L* above it
A60_ACC = {"l": 10.0, "w": 10.0, "c": 16.0, "cl": 0.0, "cw": 10.0}


def a60_dark(candidates, node_lab, black_l: float = 0.0):
    """a60-darkfine: (keep weight per node in [0, 1], dark band or None),
    or None with the token off. keep = 1 below A60_L, smoothstep to 0 at
    A60_L + A60_W (env CHROMIQ_A60_L / _W / _C for sweeps). With
    a60-darkrel the limit is measured from the printer's black L*
    (``black_l``): keep = 1 below black_l + A60_L."""
    cand = frozenset(candidates or ())
    acc = "a60-darkacc" in cand
    if "a60-darkfine" not in cand and not acc:
        return None
    import os
    l0 = float(os.environ.get("CHROMIQ_A60_L",
                              A60_ACC["l"] if acc else A60_L))
    if "a60-darkrel" in cand or acc:
        l0 += float(black_l)
    wd = max(float(os.environ.get("CHROMIQ_A60_W",
                                  A60_ACC["w"] if acc else A60_W)), 1e-6)
    c = os.environ.get("CHROMIQ_A60_C", A60_ACC["c"] if acc else A60_C)
    u = np.clip((l0 + wd - np.asarray(node_lab, float)[:, 0]) / wd, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u), (None if c in (None, "") else float(c))


# Agent 63 (a63-palefine): the mirror of a60-darkfine at the light end.
# Near the paper white most Lab nodes clip (the gamut narrows to the white
# point), so pale in-gamut colours sit in fine cells whose corners took the
# coarse table interpolated: int-8 printed them about twice as far off as
# int-7. Nodes within A63_L L* below the printer's white (the model's
# RGB 1 L*) get a hand-over band of A63_C dE of clip distance (None: the
# fine table outright), blended back over the next A63_W L* below.
A63_L = 10.0
A63_W = 10.0
A63_C = 16.0


def a63_pale(candidates, node_lab, white_l: float = 100.0):
    """a63-palefine: (keep weight per node in [0, 1], pale band or None),
    or None with the token off. keep = 1 above white_l - A63_L, smoothstep
    to 0 at white_l - A63_L - A63_W (env CHROMIQ_A63_L / _W / _C for
    sweeps; _C "none" = the fine table outright)."""
    if "a63-palefine" not in frozenset(candidates or ()):
        return None
    import os
    l0 = float(white_l) - float(os.environ.get("CHROMIQ_A63_L", A63_L))
    wd = max(float(os.environ.get("CHROMIQ_A63_W", A63_W)), 1e-6)
    c = os.environ.get("CHROMIQ_A63_C", A63_C)
    if isinstance(c, str) and c.lower() == "none":
        c = None
    u = np.clip((np.asarray(node_lab, float)[:, 0] - (l0 - wd)) / wd,
                0.0, 1.0)
    return u * u * (3.0 - 2.0 * u), (None if c in (None, "") else float(c))


# Agent 63 (a63-lowgrid): at quality l colprof's B2A grid is 9, cells four
# fine cells wide, and the coarse table interpolated into the clipped
# corners of boundary cells costs in-gamut accuracy across the whole gamut
# surface (S1 at l: B2A1 p95 0.54 -> 0.78). The a58 look was measured at
# colprof's -qm grid 17; a coarser one is not used: A63_MIN_COARSE.
A63_MIN_COARSE = 17


def a63_lowoff(candidates, g_coarse: int) -> bool:
    """a63-lowgrid with CHROMIQ_A63_LOWGRID=off: a58 does not act at all
    where colprof's grid is below A63_MIN_COARSE (research sweep)."""
    import os
    return ("a63-lowgrid" in frozenset(candidates or ())
            and os.environ.get("CHROMIQ_A63_LOWGRID") == "off"
            and int(g_coarse) < A63_MIN_COARSE)


def a63_coarse_grid(candidates, g_coarse: int, g_fine: int) -> int:
    """a63-lowgrid: the coarse grid the keep-grid33in hand-over uses. Token
    off: colprof's own grid. On: never below A63_MIN_COARSE (env
    CHROMIQ_A63_LOWGRID for sweeps; "fine" = no coarse table at all, the
    fine grid everywhere), and only grids that sub-sample the fine one."""
    if "a63-lowgrid" not in frozenset(candidates or ()):
        return g_coarse
    import os
    v = os.environ.get("CHROMIQ_A63_LOWGRID", str(A63_MIN_COARSE))
    if v == "off":
        return g_coarse
    if v == "fine":
        return g_fine if g_coarse < g_fine else g_coarse
    g = max(int(g_coarse), int(v))
    return g if g <= g_fine and (g_fine - 1) % (g - 1) == 0 else g_coarse


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
    if not flag:
        _LOCAL.a60 = False
        _LOCAL.a62 = False
    _LOCAL.floor = None if (not flag or floor is None) else float(floor)
    _LOCAL.fade = bool(flag and fade and floor is not None)


# Agent 60 (a60-darkclip): near the printer's black the clipped nodes take
# the engine's own clip (int-7's answer, oog_clip.clip_nodes) instead of
# colprof's CAM clip: weight 1 for targets up to A60_CL L* above the black,
# smoothstep to 0 over A60_CW L* above that
A60_CL = 10.0
A60_CW = 10.0


def set_a60(candidates) -> None:
    """The builder hands the colorimetric table's tokens to this thread."""
    cand = frozenset(candidates or ())
    _LOCAL.a60 = ("a60-darkclip" in cand or "a60-darkacc" in cand)
    _LOCAL.a60_acc = "a60-darkacc" in cand
    _LOCAL.a62 = "a62-camhue" in cand


def a60_clip_weight(model, target_lab: np.ndarray):
    """a60-darkclip: per target the weight of the engine's own clip, or None
    (token off, or a58 not active on this thread). Env CHROMIQ_A60_CL /
    CHROMIQ_A60_CW for sweeps."""
    if not (active() and getattr(_LOCAL, "a60", False)):
        return None
    import os
    bl = float(model.predict(np.zeros((1, model.n_channels)))[0, 0])
    acc = getattr(_LOCAL, "a60_acc", False)
    l0 = bl + float(os.environ.get("CHROMIQ_A60_CL",
                                   A60_ACC["cl"] if acc else A60_CL))
    wd = max(float(os.environ.get("CHROMIQ_A60_CW",
                                  A60_ACC["cw"] if acc else A60_CW)), 1e-6)
    u = np.clip((l0 + wd - np.asarray(target_lab, float)[:, 0]) / wd, 0.0,
                1.0)
    return u * u * (3.0 - 2.0 * u)


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

    def rows(a: int, b: int) -> None:
        # Agent 92 (D-06): every row's distances and argmin are its own;
        # the row ranges start on block borders, so the blocks are the
        # serial ones
        for lo in range(a, b, block):
            hi = min(lo + block, b)
            tb = t_j[lo:hi]
            dl = cloud_j[None, :, 0] - tb[:, None, 0]
            dchsq = ((cloud_j[None, :, 1] - tb[:, None, 1]) ** 2
                     + (cloud_j[None, :, 2] - tb[:, None, 2]) ** 2)
            dc = cc[None, :] - np.hypot(tb[:, 1], tb[:, 2])[:, None]
            dhsq = np.maximum(dchsq - dc * dc, 0.0)
            s = (LCH_WEIGHTS[0] ** 2 * dl * dl + LCH_WEIGHTS[1] ** 2 * dc * dc
                 + LCH_WEIGHTS[2] ** 2 * dhsq)
            out[lo:hi] = cloud[np.argmin(s, 1)]
    from workflow.profile_engine import parallel
    parallel.map_rows(rows, len(t_j), align=block, min_rows=block, blas=False)
    return out


def _descend(predict_j, t_j: np.ndarray, d0: np.ndarray, *, iters: int = 12,
             damping: float = 1e-3, h: float = 1e-4) -> tuple:
    """:func:`_descend_rows` on row ranges (Agent 92, D-06): every row's
    steps, acceptance and stop depend on that row alone (a row that accepts
    nothing stays where it is, so the batch's shared stop changes no row)."""
    from workflow.profile_engine import parallel
    parts = parallel.map_rows(
        lambda lo, hi: _descend_rows(predict_j, t_j[lo:hi], d0[lo:hi],
                                     iters=iters, damping=damping, h=h),
        len(t_j))
    if len(parts) == 1:
        return parts[0]
    return (np.concatenate([p[0] for p in parts], 0),
            np.concatenate([p[1] for p in parts], 0))


def _descend_rows(predict_j, t_j: np.ndarray, d0: np.ndarray, *,
                  iters: int = 12, damping: float = 1e-3,
                  h: float = 1e-4) -> tuple:
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
            if getattr(_LOCAL, "a62", False):
                # Agent 62 (a62-camhue): the lifted target keeps the
                # CIECAM02 hue of the target it was lifted from
                from workflow.profile_engine.oog_clip import camhue_lift
                t_lab = camhue_lift(t_lab, np.asarray(target_lab, float)[sel],
                                    lift)

    def predict_j(dev):
        return lab_to_argyll_jab(model.predict(dev))

    t_j = lab_to_argyll_jab(t_lab)
    n = model.n_channels
    cloud = clip_cloud(n, None, None, 5858,
                       light=True, faces=True)
    from workflow.profile_engine import parallel
    # Agent 92 (D-06): the two descents are independent, side by side
    (best, best_c), (d2, c2) = parallel.side_by_side([
        lambda: _descend(predict_j, t_j, d_lab[sel]),
        lambda: _descend(predict_j, t_j,
                         _cloud_seed(t_j, cloud, predict_j(cloud)))])
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
                   inside: tuple | None = None,
                   dark: tuple | None = None,
                   pale: tuple | None = None) -> np.ndarray:
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
    if dark is not None:
        # Agent 60 (a60-darkfine): dark nodes keep the fine table, with no
        # hand-over (band None) or a wider one (band dE of clip distance)
        keep, dband = dark
        keep = np.asarray(keep, float)
        if dband is None:
            w = (1.0 - keep) * w
        else:
            b = band + keep * (float(dband) - band)
            u2 = np.clip(np.asarray(residual, float) / np.maximum(b, 1e-9),
                         0.0, 1.0)
            w = u2 * u2 * (3.0 - 2.0 * u2)
    if pale is not None:
        # Agent 63 (a63-palefine): nodes near the paper white keep the fine
        # table with a wider hand-over band (or outright); the wider of the
        # two bands wins where the dark and the pale region meet
        pkeep, pband = pale
        pkeep = np.asarray(pkeep, float)
        if pband is None:
            w = (1.0 - pkeep) * w
        else:
            b = band + pkeep * (float(pband) - band)
            u3 = np.clip(np.asarray(residual, float) / np.maximum(b, 1e-9),
                         0.0, 1.0)
            w = np.minimum(w, u3 * u3 * (3.0 - 2.0 * u3))
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


# Agent 78 (a78-rgbsmooth, research, off by default): the coarse (colprof
# grid) half of keep-grid33in is smoothed along L* on its clipped nodes.
# Cause (Findings/agent78-01): colprof's per-node CAM clip, run on OUR model
# with the engine's dark floor below the printer black, bends sharply in L*
# from one coarse node to the next (Knut: magenta node L* 25 printed 44.4,
# L* 18.75 printed ~36: the slope between the nodes doubles), so a ramp that
# leaves the gamut holds its colour to a node and then turns into black
# within one coarse cell. A 1-2-1 filter along L* on the clipped coarse nodes
# (clip distance > rmin dE), repeated ``iters`` times, spreads that turn over
# the neighbouring cells. Printable nodes, the black corner and the nodes
# within ``top`` L* of the model's white (the a63-palefine region: smoothing
# there pulled pale out-of-gamut nodes toward the white plane and cost Knut
# pale_oog_dL_max_r 3.18 -> 3.35) are not touched; the fine (printable) table
# is unchanged.
# The gate: smoothing runs only on a table whose clip field bends that much
# overall: the median |second difference along L*| (largest channel, device
# units) over the clipped coarse nodes it would filter is at least ``gate``.
# Measured on the int-10 dumps (Findings/agent78-01 s3): Knut 0.053; every
# other RGB set 0.015-0.027 (ET-8550 0.015, PRO-300 Canon 0.016, RGB default
# 0.019, PRO-300 Epson 0.027, S1/S2/X1 0.020-0.024). Without the gate
# (a78-rgbsmooth-all) the ET-8550 eyecheck rel. col. count went 24 -> 29.
A78_TOKEN = "a78-rgbsmooth"
A78_ALL_TOKEN = "a78-rgbsmooth-all"
A78_SMOOTH = {"s": 1.0, "rmin": 8.0, "iters": 2, "tau": 0.0, "top": 10.0,
              "gate": 0.04}


def a78_params(candidates):
    """(s, rmin, iters, tau) with a78-rgbsmooth on, else None (env
    CHROMIQ_A78_SMOOTH "s:rmin:iters[:tau[:top]]" for research sweeps)."""
    cand = frozenset(candidates or ())
    if A78_TOKEN not in cand and A78_ALL_TOKEN not in cand:
        return None
    import os
    p = dict(A78_SMOOTH)
    if A78_ALL_TOKEN in cand:
        p["gate"] = 0.0
    v = os.environ.get("CHROMIQ_A78_SMOOTH", "")
    if v:
        k = v.split(":")
        p["s"], p["rmin"], p["iters"] = float(k[0]), float(k[1]), int(k[2])
        if len(k) > 3:
            p["tau"] = float(k[3])
        if len(k) > 4:
            p["top"] = float(k[4])
        if len(k) > 5:
            p["gate"] = float(k[5])
    return p


def a78_bend(sub: np.ndarray, sel: np.ndarray, g_coarse: int) -> float:
    """The gate statistic: median |second difference along L*| (largest
    channel) over the selected coarse nodes that have both L* neighbours."""
    n = sub.shape[1]
    x = np.asarray(sub, float).reshape(g_coarse, g_coarse, g_coarse, n)
    c2 = np.abs(x[2:] - 2.0 * x[1:-1] + x[:-2]).max(-1)
    m = np.asarray(sel).reshape(g_coarse, g_coarse, g_coarse)[1:-1]
    return float(np.median(c2[m])) if m.any() else 0.0


def a78_smooth(sub: np.ndarray, node_lab: np.ndarray, residual: np.ndarray,
               g_fine: int, g_coarse: int, params: dict,
               white_l: float = 100.0) -> np.ndarray:
    """a78-rgbsmooth: ``sub`` (the coarse table, g_coarse^3 x n) with its
    clipped nodes filtered along the L* axis (weights 1/4, 1/2, 1/4; the end
    planes reflect), ``iters`` passes of strength ``s``. With ``tau`` > 0 only
    nodes whose |second difference along L*| (largest channel) reaches tau
    are filtered (smoothstep from tau/2 to tau)."""
    st = (g_fine - 1) // (g_coarse - 1)
    n = sub.shape[1]
    nl = np.asarray(node_lab, float).reshape(g_fine, g_fine, g_fine, 3)[
        ::st, ::st, ::st].reshape(-1, 3)
    rr = np.asarray(residual, float).reshape(g_fine, g_fine, g_fine)[
        ::st, ::st, ::st].reshape(-1)
    sel = ((rr > float(params["rmin"])) & (np.linalg.norm(nl, axis=1) > 1.0)
           & (nl[:, 0] < 99.9)
           & (nl[:, 0] <= float(white_l) - float(params.get("top", 0.0))))
    s = float(params["s"])
    tau = float(params.get("tau") or 0.0)
    gate = float(params.get("gate") or 0.0)
    if gate > 0.0 and a78_bend(sub, sel, g_coarse) < gate:
        return np.asarray(sub)
    x = np.asarray(sub, float).reshape(g_coarse, g_coarse, g_coarse, n).copy()
    for _ in range(int(params["iters"])):
        lo = np.concatenate([x[:1], x[:-1]], 0)
        hi = np.concatenate([x[1:], x[-1:]], 0)
        f = (0.25 * lo + 0.5 * x + 0.25 * hi).reshape(-1, n)
        w = np.full(len(f), s)
        if tau > 0.0:
            c2 = np.zeros((g_coarse, g_coarse, g_coarse))
            c2[1:-1] = np.abs(x[2:] - 2.0 * x[1:-1] + x[:-2]).max(-1)
            u = np.clip((c2.reshape(-1) - 0.5 * tau) / (0.5 * tau), 0.0, 1.0)
            w = s * u * u * (3.0 - 2.0 * u)
        y = x.reshape(-1, n).copy()
        y[sel] = (1.0 - w[sel, None]) * y[sel] + w[sel, None] * f[sel]
        x = y.reshape(g_coarse, g_coarse, g_coarse, n)
    return x.reshape(-1, n)


# Agent 82 (a82-green, research, off by default): RGB rel. col. greens.
# Cause (Findings/agent82-01): two places where the colorimetric table holds a
# green to the printer's limit and then turns.
#  1. Near the black (Okt26 mid h120, the dark teal spot): the a60-darkacc
#     region keeps the FINE table for clipped nodes (hand-over band 16 dE), and
#     there one clipped node's own clip snaps onto the device's G-only edge
#     (Okt26 node L* 9.4 a* -8 b* 8: RGB 0 .079 0, printed h 158 against a
#     target h 135, while the nodes above and below it print h 133 and h 147),
#     so a dark green ramp turns teal for one fine cell and then back.
#  2. At the green cusp (ET-8550 Adobe green into black, knee at L* 57): the
#     coarse (colprof grid) table's clipped nodes put the cusp node exactly
#     on the gamut's corner, so chroma rises to it and falls from it within
#     one coarse cell.
# The fix: (1) a 1-2-1 filter along L*, a* and b* on the FINE table's clipped
# nodes (strength = clip distance - 1 dE, capped at 1, and faded out again
# from 4 to 8 dE of clip distance: the snap happens just outside the gamut;
# nodes far outside belong to the a29/a56 floor below the black, and
# filtering them cost the RGB default i1Pro dark green ramp's evenness
# 0.09 -> 0.15) within dark_l L* of the printer's black (faded out over
# dark_f L* above it), 2 passes; (2) a
# 1-2-1 filter along L* on the coarse table's clipped nodes (clip distance >
# 4 dE) from 30 L* above the black to 10 L* below the white, 2 passes. Both
# only on nodes whose TARGET hue is green (A82["hue"]); printable nodes are
# never changed, so in-gamut accuracy is untouched.
# a82-green is part (1) only. Part (2) is the separate a82-greencusp: it
# lowers the ET-8550 knee only from 1.15 to 1.07 JND (colprof 0.90) and makes
# Knut's green h150 ramp cross the 1 JND line (0.93 -> 1.02), so it is not
# proposed (Findings/agent82-01 s3).
A82_TOKEN = "a82-green"
A82_CUSP_TOKEN = "a82-greencusp"
# a82-greenin (separate, research): printable green nodes within A82_IN dE of
# a clipped node lean toward the coarse table (Agent 59's inward hand-over,
# a59-inband, on green target hues only): the turn where a green ramp leaves
# the gamut is rounded the way colprof's grid rounds it, at the cost of
# exactness of printable greens next to the gamut edge (Okt26 green h120's
# two faint bands, ET-8550 h105).
A82_IN_TOKEN = "a82-greenin"
A82_IN = (10.0, 1.0)


def a82_in(candidates):
    """(depth, strength) with a82-greenin on, else None."""
    if A82_IN_TOKEN not in frozenset(candidates or ()):
        return None
    return A82_IN
A82 = {"hue": (90.0, 170.0), "dark_l": 20.0, "dark_f": 5.0, "dark_r0": 1.0,
       "dark_rmax": 8.0, "dark_rw": 4.0, "dark_iters": 2, "co_rmin": 4.0, "co_iters": 2, "co_lmin": 30.0,
       "co_top": 10.0}


def a82_params(candidates):
    """a82-green's parameters, or None with the token off (env
    CHROMIQ_A82 "h0:h1:dark_l:dark_iters:co_iters" for research sweeps)."""
    cand = frozenset(candidates or ())
    if A82_TOKEN not in cand and A82_CUSP_TOKEN not in cand:
        return None
    import os
    p = dict(A82)
    p["dark"] = A82_TOKEN in cand
    p["cusp"] = A82_CUSP_TOKEN in cand
    v = os.environ.get("CHROMIQ_A82", "")
    if v:
        k = v.split(":")
        p["hue"] = (float(k[0]), float(k[1]))
        if len(k) > 2:
            p["dark_l"] = float(k[2])
        if len(k) > 3:
            p["dark_iters"] = int(k[3])
        if len(k) > 4:
            p["co_iters"] = int(k[4])
    return p


def _a82_hue_mask(lab: np.ndarray, hue) -> np.ndarray:
    h = np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360.0
    h0, h1 = float(hue[0]), float(hue[1])
    return ((h >= h0) & (h <= h1)) if h0 <= h1 else ((h >= h0) | (h <= h1))


def _a82_filter(x: np.ndarray, axes) -> np.ndarray:
    acc = np.zeros_like(x)
    for k in axes:
        lo = np.concatenate([x.take([0], k), x.take(range(x.shape[k] - 1), k)],
                            k)
        hi = np.concatenate([x.take(range(1, x.shape[k]), k),
                             x.take([x.shape[k] - 1], k)], k)
        acc += 0.25 * lo + 0.5 * x + 0.25 * hi
    return acc / len(axes)


def a82_coarse(sub: np.ndarray, node_lab: np.ndarray, residual: np.ndarray,
               g_fine: int, g_coarse: int, params: dict, black_l: float,
               white_l: float) -> np.ndarray:
    """a82-green part 2: the coarse table's clipped green nodes between
    black + co_lmin and white - co_top filtered along L*."""
    if not params.get("cusp", True):
        return np.asarray(sub)
    st = (g_fine - 1) // (g_coarse - 1)
    n = sub.shape[1]
    nl = np.asarray(node_lab, float).reshape(g_fine, g_fine, g_fine, 3)[
        ::st, ::st, ::st].reshape(-1, 3)
    rr = np.asarray(residual, float).reshape(g_fine, g_fine, g_fine)[
        ::st, ::st, ::st].reshape(-1)
    sel = ((rr > float(params["co_rmin"])) & _a82_hue_mask(nl, params["hue"])
           & (nl[:, 0] >= float(black_l) + float(params["co_lmin"]))
           & (nl[:, 0] <= float(white_l) - float(params["co_top"]))
           & (np.linalg.norm(nl, axis=1) > 1.0))
    if not sel.any():
        return np.asarray(sub)
    x = np.asarray(sub, float).reshape(g_coarse, g_coarse, g_coarse, n).copy()
    for _ in range(int(params["co_iters"])):
        f = _a82_filter(x, (0,)).reshape(-1, n)
        y = x.reshape(-1, n).copy()
        y[sel] = f[sel]
        x = y.reshape(g_coarse, g_coarse, g_coarse, n)
    return x.reshape(-1, n)


def a82_dark(table: np.ndarray, node_lab: np.ndarray, residual: np.ndarray,
             g: int, params: dict, black_l: float) -> np.ndarray:
    """a82-green part 1: the written (fine) table's clipped green nodes near
    the black filtered along L*, a* and b*."""
    if not params.get("dark", True):
        return np.asarray(table)
    nl = np.asarray(node_lab, float)
    r = np.asarray(residual, float)
    n = table.shape[1]
    top = float(black_l) + float(params["dark_l"])
    fd = max(float(params["dark_f"]), 1e-9)
    u = np.clip((top + fd - nl[:, 0]) / fd, 0.0, 1.0)
    rmax = params.get("dark_rmax")
    v = (np.ones(len(r)) if rmax is None else
         np.clip((float(rmax) - r) / max(float(params.get("dark_rw", 4.0)),
                                         1e-9), 0.0, 1.0))
    s = (u * u * (3.0 - 2.0 * u) * v * v * (3.0 - 2.0 * v)
         * np.clip(r - float(params["dark_r0"]), 0, 1)
         * _a82_hue_mask(nl, params["hue"])
         * (np.linalg.norm(nl, axis=1) > 1.0))
    if not (s > 0).any():
        return np.asarray(table)
    x = np.asarray(table, float).reshape(g, g, g, n).copy()
    for _ in range(int(params["dark_iters"])):
        f = _a82_filter(x, (0, 1, 2)).reshape(-1, n)
        y = x.reshape(-1, n)
        y = (1.0 - s[:, None]) * y + s[:, None] * f
        x = y.reshape(g, g, g, n)
    return x.reshape(-1, n)


# --- Agent 85 (a85-bpcblack): the neutral shadows reach the printer's black ------------------------------------
# Rel. col. + black point compensation (Lightroom, Photoshop, every Little CMS application) squeezes the image's
# black onto the profile's black point, which Adobe's algorithm (Little CMS cmsDetectDestinationBlackPoint) takes
# from device RGB 0 through A2B1, made neutral. On a printer whose deepest black is tinted (ET-8550: L* 4.1,
# a* 2.2, b* -3.4) there is no neutral that dark, so the B2A1 column node has to clip. colprof's CAM clip (above)
# measures the miss in Argyll's CIECAM02 Jab, where lightness near black is squashed (J 7.9 at L* 0, 10.9 at
# L* 7.3: 7.3 L* into 3 J) while the black's tint is not: the clip picks the darkest NEUTRAL, L* 7.2-7.5, for
# every column node from the black up, a plateau the BPC wedge lands on (bottom step 7.3 for a black point of
# 4.1, the bottom six steps 0.1 L* apart; colprof itself 7.5). The token re-solves those column nodes with the
# same rev.c LCh weights (2, 1, 2.2) in CIELAB (for a neutral target 4 dL^2 + C^2), which reaches the black
# (4.9 at the black point, as Argyll's own exact inverse) at the cost of the black's own tint in the last few L*.
# Gate (measured on the build's model): the darkest printable neutral (C* <= 1) lies at least A85["gap"] L*
# above the device black; Knut, both PRO-300s, X1 (neutral blacks) never fire.
A85_TOKEN = "a85-bpcblack"
A85 = {"gap": 1.5, "fade": 4.0, "ring": 0.0, "cmax": 1.0, "w": LCH_WEIGHTS}


def a85_params(candidates):
    """a85-bpcblack's parameters, or None with the token off (env CHROMIQ_A85 "gap:fade:ring:wL" for sweeps)."""
    if A85_TOKEN not in frozenset(candidates or ()):
        return None
    import os
    p = dict(A85)
    v = os.environ.get("CHROMIQ_A85", "")
    if v:
        k = v.split(":")
        p["gap"] = float(k[0])
        if len(k) > 1:
            p["fade"] = float(k[1])
        if len(k) > 2:
            p["ring"] = float(k[2])
        if len(k) > 3:
            p["w"] = (float(k[3]), LCH_WEIGHTS[1], LCH_WEIGHTS[2])
    return p


def _a85_cloud(dmax: float, n: int = 3, steps: int = 48) -> np.ndarray:
    ax = np.linspace(0.0, dmax, steps)
    return np.stack(np.meshgrid(*([ax] * n), indexing="ij"), -1).reshape(-1, n)


def a85_gate(model, params: dict) -> dict:
    """The device black (model, RGB 0), the darkest printable neutral (least L* with C* <= cmax on a dark device
    cloud) and whether the gap between them fires the token."""
    n = model.n_channels
    k = np.asarray(model.predict(np.zeros((1, n)))[0], float)
    ln = None
    for dmax in (0.3, 0.6, 1.0):
        cl = _a85_cloud(dmax, n)
        lab = np.asarray(model.predict(cl), float)
        ok = np.hypot(lab[:, 1], lab[:, 2]) <= float(params["cmax"])
        if ok.any():
            ln = float(lab[ok, 0].min())
            if ln < float(lab[:, 0].max()) - 5.0:
                break
    gap = None if ln is None else ln - float(k[0])
    return {"black": k, "neutral_l": ln, "gap": gap,
            "fires": gap is not None and gap >= float(params["gap"])}


def _inv_out(tables: np.ndarray, dev: np.ndarray) -> np.ndarray:
    """device (N, n) -> table values whose B2A output curves give that device (monotone u16 tables inverted)."""
    t = np.asarray(tables, float) / 65535.0
    x = np.linspace(0.0, 1.0, t.shape[1])
    out = np.empty_like(np.asarray(dev, float))
    for c in range(t.shape[0]):
        y = np.maximum.accumulate(t[c])
        out[:, c] = np.interp(dev[:, c], y, x)
    return out


def _fwd_out(tables: np.ndarray, val: np.ndarray) -> np.ndarray:
    t = np.asarray(tables, float) / 65535.0
    x = np.linspace(0.0, 1.0, t.shape[1])
    return np.stack([np.interp(val[:, c], x, t[c]) for c in range(t.shape[0])], 1)


def a85_bpcblack(table: np.ndarray, node_lab: np.ndarray, residual: np.ndarray, model, params: dict,
                 out_tables: np.ndarray, gate: dict | None = None):
    """(table, info): the written B2A1 table (values in the space of ``out_tables``) with its clipped neutral
    column nodes from L* 0 up to the darkest printable neutral (+ fade) re-solved by the rev.c LCh-weighted
    nearest point in CIELAB, blended in device space (full weight up to the darkest neutral, smoothstep to 0
    over ``fade`` L*, over 0.5-1.5 dE of the node's own clip distance; ring > 0 lets the first off-axis nodes
    take that share too). Untouched (``table`` returned as is) where the gate does not fire."""
    gate = a85_gate(model, params) if gate is None else gate
    info = dict(gate, nodes=0)
    if not gate["fires"]:
        return np.asarray(table), info
    nl = np.asarray(node_lab, float)
    r = np.asarray(residual, float)
    c = np.hypot(nl[:, 1], nl[:, 2])
    top = float(gate["neutral_l"]) + float(params["fade"])
    u = np.clip((top - nl[:, 0]) / max(float(params["fade"]), 1e-9), 0.0, 1.0)
    wl = u * u * (3.0 - 2.0 * u)
    v = np.clip(r - 0.5, 0.0, 1.0)
    wr = v * v * (3.0 - 2.0 * v)
    ring = float(params["ring"])
    wc = np.where(c < 0.5, 1.0, np.where(c < 12.0, ring, 0.0))
    w = wl * wr * wc
    sel = np.flatnonzero(w > 0)
    if not len(sel):
        return np.asarray(table), info
    tab = np.asarray(table, float).copy()
    cur = _fwd_out(out_tables, tab[sel])
    t_lab = nl[sel]
    wts = tuple(params["w"])
    dmax = float(min(1.0, max(0.05, 1.5 * cur.max())))
    cloud = _a85_cloud(dmax, model.n_channels)
    lab_c = np.asarray(model.predict(cloud), float)
    seed = np.empty_like(cur)
    for i, t in enumerate(t_lab):
        seed[i] = cloud[np.argmin(lchw_sq(lab_c, np.broadcast_to(t, lab_c.shape), wts))]

    def res_fn(y, t):
        return lchw_residual(y, t, wts)

    best = _a85_descend(model.predict, t_lab, seed, res_fn)
    new = (1.0 - w[sel])[:, None] * cur + w[sel][:, None] * best
    tab[sel] = _inv_out(out_tables, np.clip(new, 0.0, 1.0))
    info.update(nodes=int(len(sel)), top=top)
    return tab, info


def _a85_descend(predict, t_lab, d0, res_fn, iters: int = 20, h: float = 1e-4):
    """Projected Gauss-Newton with backtracking inside the device cube (few nodes, so plain loops)."""
    d = np.clip(np.array(d0, float), 0.0, 1.0)
    n = d.shape[1]
    for i in range(len(d)):
        t = t_lab[i:i + 1]
        x = d[i:i + 1].copy()
        r = res_fn(predict(x), t)
        cst = float((r * r).sum())
        for _ in range(iters):
            jac = np.empty((3, n))
            for k in range(n):
                xk = x.copy()
                s = h if xk[0, k] + h <= 1.0 else -h
                xk[0, k] += s
                jac[:, k] = (res_fn(predict(xk), t) - r)[0] / s
            stp = np.linalg.lstsq(jac, -r[0], rcond=None)[0]
            held = ((x[0] <= 0.0) & (stp < 0)) | ((x[0] >= 1.0) & (stp > 0))
            if held.any() and (~held).any():
                stp = np.zeros(n)
                stp[~held] = np.linalg.lstsq(jac[:, ~held], -r[0], rcond=None)[0]
            elif held.all():
                break
            ok = False
            for f in (1.0, 0.5, 0.25, 0.125, 0.0625):
                xn = np.clip(x + f * stp, 0.0, 1.0)
                rn = res_fn(predict(xn), t)
                cn = float((rn * rn).sum())
                if cn < cst - 1e-12:
                    x, r, cst, ok = xn, rn, cn, True
                    break
            if not ok:
                break
        d[i] = x[0]
    return d


# --- Agent 88 (a88-black-balanced / a88-black-deepest): how deep the darkest shadows go on a tinted black ----------
# A three-level choice built on a85-bpcblack. Neutral (no token, the default) leaves the colorimetric table exactly
# as int-11 writes it: the neutral shadows stop at the darkest truly neutral grey. Deepest follows Agent 85: the
# clipped neutral column below the darkest neutral is re-solved in CIELAB, so rel. col. + BPC reaches the printer's
# own (tinted) black. Balanced goes deeper only while the colour cast stays within one just-noticeable step: the
# same re-solve, but a node may not print further than A88["cast"] dE00 (the battery's JND, 1.75) from the neutral
# grey of its own lightness. Same gate as a85 (darkest printable neutral >= 1.5 L* above the device black), so a
# printer with a near-neutral black is byte-identical at every level. Safety knobs (measured by Agent 88):
#   gfade  the share of the re-solve falls from full at the device black to 0 at the darkest neutral over this
#          fraction of the gap (0 = Agent 85's full share up to the darkest neutral; 1, the default, takes the
#          S1 pessimistic grey-ramp corner from banding 0.186 to 0.149, tolerance 0.175, for 0.15 L* of depth)
#   ring   share of the first ring of off-axis nodes (C* < 12) that take the CIELAB re-solve too (Agent 85: 0;
#          measured: no gain in the wedge, new ramp defects on RGB default, so 0)
#   rshift ring nodes follow the column's device shift instead (measured: does not remove the yellow step, 0)
#   dcast  Deepest only: an optional cast cap (dE00) on the re-solve (None = no cap, Agent 85)
# The L* = 0 plane is never touched (the profile's black stays device 0). Env CHROMIQ_A88 "key=value,..." (sweeps).
A88_LEVELS = {"a88-black-balanced": "balanced", "a88-black-deepest": "deepest"}
A88 = {"gap": 1.5, "fade": 4.0, "ring": 0.0, "cmax": 1.0, "w": LCH_WEIGHTS, "cast": 1.75, "gfade": 1.0,
       "dcast": None, "pen": 40.0, "rshift": 0.0, "rreach": 12.0}
A88_DEEPEST = {}
A88_BALANCED = {}


def a88_params(candidates):
    """The chosen level's parameters, or None with neither token (Deepest wins if both are given)."""
    c = frozenset(candidates or ())
    lv = "deepest" if "a88-black-deepest" in c else ("balanced" if "a88-black-balanced" in c else None)
    if lv is None:
        return None
    import os
    p = dict(A88, **(A88_DEEPEST if lv == "deepest" else A88_BALANCED), level=lv)
    for kv in filter(None, os.environ.get("CHROMIQ_A88", "").split(",")):
        k, v = kv.split("=", 1)
        p[k] = None if v in ("", "none", "None") else float(v)
    return p


def a88_cast(lab: np.ndarray) -> np.ndarray:
    """dE00 between each colour and the neutral grey of its own lightness: how visible its colour cast is."""
    from .metrics import delta_e_2000
    y = np.atleast_2d(np.asarray(lab, float))
    return delta_e_2000(y, np.stack([y[:, 0], 0 * y[:, 0], 0 * y[:, 0]], 1))


def a88_dark_end(model, cmax: float = 1.0) -> dict:
    """What the printer's dark end looks like, for a report: the device black (model, device 0) and the darkest
    printable neutral (least L* with C* <= cmax on a dark device cloud), both as Lab, and the gap in L*."""
    n = model.n_channels
    k = np.asarray(model.predict(np.zeros((1, n)))[0], float)
    best = None
    for dmax in (0.3, 0.6, 1.0):
        cl = _a85_cloud(dmax, n)
        lab = np.asarray(model.predict(cl), float)
        ok = np.flatnonzero(np.hypot(lab[:, 1], lab[:, 2]) <= float(cmax))
        if len(ok):
            best = lab[ok[np.argmin(lab[ok, 0])]]
            if best[0] < float(lab[:, 0].max()) - 5.0:
                break
    return {"black": k, "neutral": best, "neutral_l": None if best is None else float(best[0]),
            "gap": None if best is None else float(best[0] - k[0])}


def a88_black(table: np.ndarray, node_lab: np.ndarray, residual: np.ndarray, model, params: dict,
              out_tables: np.ndarray, gate: dict | None = None):
    """(table, info) for the level in ``params`` (a88_params); the table is untouched where the gate does not
    fire. See the section comment."""
    gate = a88_dark_end(model, params["cmax"]) if gate is None else gate
    gap = gate["gap"]
    info = dict(gate, level=params["level"], fires=gap is not None and gap >= float(params["gap"]), nodes=0)
    if not info["fires"]:
        return np.asarray(table), info
    nl = np.asarray(node_lab, float)
    r = np.asarray(residual, float)
    c = np.hypot(nl[:, 1], nl[:, 2])
    ln, kl = float(gate["neutral_l"]), float(gate["black"][0])
    top = ln + float(params["fade"])
    u = np.clip((top - nl[:, 0]) / max(float(params["fade"]), 1e-9), 0.0, 1.0)
    wl = u * u * (3.0 - 2.0 * u)
    v = np.clip(r - 0.5, 0.0, 1.0)
    wr = v * v * (3.0 - 2.0 * v)
    ring = float(params["ring"])
    col = c < 0.5
    wc = np.where(col, 1.0, np.where(c < 12.0, ring, 0.0))
    gf = float(params["gfade"] or 0.0)
    if gf > 0:
        g = np.clip((ln - nl[:, 0]) / max(gf * (ln - kl), 1e-9), 0.0, 1.0)
        wl = wl * g * g * (3.0 - 2.0 * g)
    w = wl * wr * wc * (nl[:, 0] >= 0.5)
    sel = np.flatnonzero(w > 0)
    if not len(sel):
        return np.asarray(table), info
    tab = np.asarray(table, float).copy()
    cur = _fwd_out(out_tables, tab[sel])
    t_lab = nl[sel]
    wts = tuple(params["w"])
    cap = params["cast"] if params["level"] == "balanced" else params["dcast"]
    caps = np.where(col[sel], np.inf if cap is None else float(cap), np.inf)
    dmax = float(min(1.0, max(0.05, 1.5 * cur.max())))
    cloud = _a85_cloud(dmax, model.n_channels)
    lab_c = np.asarray(model.predict(cloud), float)
    cast_c = a88_cast(lab_c)
    seed = np.empty_like(cur)
    for i, t in enumerate(t_lab):
        d = lchw_sq(lab_c, np.broadcast_to(t, lab_c.shape), wts)
        if np.isfinite(caps[i]):
            d = d + float(params["pen"]) ** 2 * np.maximum(cast_c - caps[i], 0.0) ** 2
        seed[i] = cloud[np.argmin(d)]
    pen = float(params["pen"])

    def res_fn(y, t, cp):
        rr = lchw_residual(y, t, wts)
        if not np.isfinite(cp):
            return rr
        return np.concatenate([rr, pen * np.maximum(a88_cast(y) - cp, 0.0)[:, None]], 1)

    best = _a88_descend(model.predict, t_lab, seed, res_fn, caps)
    if np.isfinite(caps).any():
        # a capped level is never shallower than Neutral: where the capped point prints lighter than the node
        # already does (the clip had a deeper, more tinted colour), the node keeps its Neutral device
        lb = np.asarray(model.predict(best), float)[:, 0]
        lc = np.asarray(model.predict(cur), float)[:, 0]
        keep = np.isfinite(caps) & (lb > lc)
        best[keep] = cur[keep]
    new = (1.0 - w[sel])[:, None] * cur + w[sel][:, None] * best
    tab[sel] = _inv_out(out_tables, np.clip(new, 0.0, 1.0))
    rs = float(params.get("rshift") or 0.0)
    if rs > 0:
        # the clipped off-axis nodes next to a moved column node take the same device shift (share rs, fading
        # with their distance from the axis over rreach), so the colours that turn into black meet the deeper
        # black without a seam; nothing is re-solved, the shift only follows the column
        shift = {round(float(nl[i, 0]), 6): new[k] - cur[k] for k, i in enumerate(sel) if col[i]}
        reach = float(params["rreach"])
        nb = np.flatnonzero((~col) & (c < reach) & (wr > 0) & (nl[:, 0] >= 0.5))
        nb = np.array([i for i in nb if round(float(nl[i, 0]), 6) in shift], int)
        if len(nb):
            f = rs * np.clip(1.0 - c[nb] / reach, 0.0, 1.0) * wr[nb]
            d0 = _fwd_out(out_tables, np.asarray(table, float)[nb])
            dv = np.stack([shift[round(float(nl[i, 0]), 6)] for i in nb])
            tab[nb] = _inv_out(out_tables, np.clip(d0 + f[:, None] * dv, 0.0, 1.0))
            info["ring_nodes"] = int(len(nb))
    pr = np.asarray(model.predict(np.clip(new, 0.0, 1.0)), float)
    cs = col[sel]
    info.update(nodes=int(len(sel)), top=top,
                column=[(float(t_lab[i, 0]), [round(float(x), 2) for x in pr[i]], round(float(a88_cast(pr[i])[0]), 2))
                        for i in np.flatnonzero(cs)])
    return tab, info


def _a88_descend(predict, t_lab, d0, res_fn, caps, iters: int = 30, h: float = 1e-4):
    """_a85_descend for a residual of any length (the cast penalty adds one)."""
    d = np.clip(np.array(d0, float), 0.0, 1.0)
    n = d.shape[1]
    for i in range(len(d)):
        t, cp = t_lab[i:i + 1], caps[i]
        x = d[i:i + 1].copy()
        r = res_fn(predict(x), t, cp)
        cst = float((r * r).sum())
        for _ in range(iters):
            jac = np.empty((r.shape[1], n))
            for k in range(n):
                xk = x.copy()
                s = h if xk[0, k] + h <= 1.0 else -h
                xk[0, k] += s
                jac[:, k] = (res_fn(predict(xk), t, cp) - r)[0] / s
            stp = np.linalg.lstsq(jac, -r[0], rcond=None)[0]
            held = ((x[0] <= 0.0) & (stp < 0)) | ((x[0] >= 1.0) & (stp > 0))
            if held.any() and (~held).any():
                stp = np.zeros(n)
                stp[~held] = np.linalg.lstsq(jac[:, ~held], -r[0], rcond=None)[0]
            elif held.all():
                break
            ok = False
            for f in (1.0, 0.5, 0.25, 0.125, 0.0625):
                xn = np.clip(x + f * stp, 0.0, 1.0)
                rn = res_fn(predict(xn), t, cp)
                cn = float((rn * rn).sum())
                if cn < cst - 1e-12:
                    x, r, cst, ok = xn, rn, cn, True
                    break
            if not ok:
                break
        d[i] = x[0]
    return d
