"""Agent 69 (research tokens ``a69-cmykport*``): the CMYK colorimetric B2A1
built the way colprof builds it, on OUR forward model (D-30: port colprof's
method where we cannot reach its quality).

What colprof does for a CMYK output profile's B2A1 (ArgyllCMS 3.5.0,
``~/Downloads/Argyll_V3.5.0_orig``):

* ``profile/profout.c:510-555`` (``out_b2a_clut``, table 0): every grid node
  is inverted on its own by ``inv_clut_aux``; no gamut mapping, no refit or
  smoothing afterwards (``USE_LEASTSQUARES_APROX`` undefined, ``:82``), no
  PCS curves (``NO_B2A_PCS_CURVES``, ``:80``), grid 17 at -qm
  (``:1129-1146``). No black pin, no neutral column of its own.
* Black generation (``xicc/xlut.c:1005-1185``, colprof.c:211-212, 1228-1233,
  the default ``-kr``): for an in-gamut node the rev locus gives the range of
  K that still reaches the colour under the ink limit, ``[Kmin, Kmax]``; the
  K target is the inking curve of the node's L* normalised over the
  profile's ``Lmin..Lmax`` (``icxKcurve``, ``xlut.c:818-935``, a linear ramp
  for -kr with a +-0.09 transition filter at both ends, skew 2), as a K
  VALUE (``icxKluma5k``) clipped to the locus; then C, M, Y solve the colour
  exactly with that K (``RSPL_EXACTAUX``).
* An out-of-gamut node (no locus) is clipped to the nearest point in PCS
  Lab, plain Euclidean (``rev.c`` ``nnearest_clip_solve``; the aux target
  has no effect there), under the ink limit (``rev_set_limit``,
  ``xlut.c:1924-1940``); then, because it clipped, again to the nearest
  point in Argyll's CIECAM02 Jab with the rev.c LCh weighting J 2 : C 1 :
  H 2.2 (squared, ``xlut.c:108-111, 2424-2453``; the CAM rspl has the same
  ink limit, ``:2473``), and the two device answers are blended linearly
  over CAMCLIPTRANS = 1 unit of the CAM clip distance (``xlut.c:1325-1418``).

The functions here produce that per-node table from the engine's model;
the builder decides how much of it goes into the written B2A1 (whole
table, colprof's 17 grid, or only a dark / clipped region blended to the
engine's own table).
"""
from __future__ import annotations

import os

import numpy as np

TOKEN = "a69-cmykport"
TOKENS = ("a69-cmykport", "a69-cmykport-17", "a69-cmykport-ourk",
          "a69-cmykport-ourclip", "a69-cmykport-pernode",
          "a69-cmykport-dark", "a69-cmykport-keepblack",
          "a69-cmykport-17in", "a69-cmykport-oog", "a69-cmykport-oogpn")

# Argyll constants
KSMTH = 0.09          # ICXINKDEFSMTH, xicc.h:183
KSKEW = 2.0           # ICXINKDEFSKEW, xicc.h:184
RAMP = (0.0, 0.0, 1.0, 1.0, 1.0)   # -kr: Kstle, Kstpo, Kenpo, Kenle, Kshap
CAMCLIPTRANS = 1.0
FEAS_TOL = 0.2        # dE76: a fixed-K C, M, Y solve this close is "exact"


def mode(candidates) -> dict | None:
    """The port's switches from the build's tokens, or None (port off)."""
    c = frozenset(candidates or ())
    if not any(t.startswith(TOKEN) for t in c):
        return None
    return {"grid17": "a69-cmykport-17" in c,
            "in17": "a69-cmykport-17in" in c,
            "oog": "a69-cmykport-oog" in c or "a69-cmykport-oogpn" in c,
            "oogpn": "a69-cmykport-oogpn" in c,
            "ourk": "a69-cmykport-ourk" in c,
            "ourclip": "a69-cmykport-ourclip" in c,
            "pernode": "a69-cmykport-pernode" in c,
            "dark": "a69-cmykport-dark" in c,
            "keepblack": "a69-cmykport-keepblack" in c}


def applies(candidates, *, accurate: bool, is_additive: bool, n: int,
            letters) -> bool:
    """CMYK (4 inks, K the 4th channel) Maximum accuracy only."""
    return bool(accurate and not is_additive and n == 4
                and list(letters)[:4] == list("CMYK")
                and mode(candidates) is not None)


# --- colprof's inking curve -------------------------------------------------
def _kcurve_nf(L: np.ndarray, c) -> np.ndarray:
    """icxKcurveNF (xlut.c:730-800): L normalised, 0 = black, 1 = white."""
    stle, stpo, enpo, enle, shap = c
    if not stpo < enpo:
        stle, stpo, enpo, enle = enle, enpo, stpo, stle
    p = np.clip(1.0 - np.asarray(L, float), 0.0, 1.0)
    out = np.where(p <= stpo, stle, enle).astype(float)
    mid = (p > stpo) & (p < enpo)
    if mid.any():
        lp = (p[mid] - stpo) / (enpo - stpo)
        lp = lp ** KSKEW
        g = shap / 2.0
        lp = lp / ((1.0 / g - 2.0) * (1.0 - lp) + 1.0)
        lp = lp ** (1.0 / KSKEW)
        out[mid] = lp * (enle - stle) + stle
    return out


def kcurve(L: np.ndarray, c=RAMP) -> np.ndarray:
    """icxKcurve (xlut.c:818-935): the inking curve with its transition
    filters at the white and black ends. ``L`` normalised 0 black, 1 white."""
    stle, stpo, enpo, enle, shap = c
    if not stpo < enpo:
        stle, stpo, enpo, enle = enle, enpo, stpo, stle
    Li = np.clip(1.0 - np.asarray(L, float), 0.0, 1.0)   # 0 white, 1 black
    rv = _kcurve_nf(1.0 - Li, c)
    wbs, wbe = stpo - KSMTH, stpo + KSMTH
    bbs, bbe = enpo - KSMTH, enpo + KSMTH
    mt = 0.5 * (wbe + bbs)
    if wbs < 0.0:
        wbe += wbs
        wbs = 0.0
    if bbe > 1.0:
        bbs += bbe - 1.0
        bbe = 1.0
    if wbe > mt:
        wbs += wbe - mt
        wbe = mt
    if bbs < mt:
        bbe += mt - bbs
        bbs = mt
    if wbs < wbe:
        wbl = (Li - wbe) / (wbs - wbe)
        m = (wbl > 0.0) & (wbl < 1.0)
        if m.any():
            wfv = float(_kcurve_nf(np.array([1.0 - wbe]), c)[0])
            w = 1.0 - (1.0 - wbl[m]) ** 2
            rv[m] = w * stle + (1.0 - w) * wfv
    if bbs < bbe:
        bbl = (Li - bbe) / (bbs - bbe)
        m = (bbl > 0.0) & (bbl < 1.0)
        if m.any():
            bfv = float(_kcurve_nf(np.array([1.0 - bbs]), c)[0])
            w = bbl[m] ** 2
            rv[m] = w * bfv + (1.0 - w) * enle
    return np.clip(rv, 0.0, 1.0)


def k_target(l_star: np.ndarray, l_min: float, l_max: float = 100.0,
             c=RAMP) -> np.ndarray:
    """K target for target L* (inv_clut_aux: L normalised over Lmin..Lmax)."""
    L = (np.asarray(l_star, float) - l_min) / max(l_max - l_min, 1e-6)
    return kcurve(L, c)


# --- solvers ----------------------------------------------------------------
def _project_cmy(d: np.ndarray, limit, cmax) -> np.ndarray:
    """Clamp C, M, Y to their box and project them under ``limit - K``
    (K is held)."""
    from workflow.profile_engine.b2a import project_tac
    d = d.copy()
    d[:, :3] = np.clip(d[:, :3], 0.0, cmax[None, :3])
    if limit is not None:
        room = np.maximum(limit - d[:, 3], 0.0)
        over = d[:, :3].sum(1) > room + 1e-12
        if over.any():
            for i in np.flatnonzero(over):
                d[i, :3] = project_tac(d[i:i + 1, :3], room[i])[0]
    return d


def solve_cmy(model, target: np.ndarray, d0: np.ndarray, *, limit, cmax,
              iters: int = 10) -> tuple[np.ndarray, np.ndarray]:
    """C, M, Y for the target colour with K held at d0[:, 3]: damped GN on the
    three free channels, box + ink limit by the active-set / face step of
    the engine's solver, K re-imposed after every step."""
    from workflow.profile_engine.b2a import _gauss_newton
    k = d0[:, 3].copy()
    d = _project_cmy(d0, limit, cmax)
    d = _gauss_newton(model, target, d, np.arange(3), iters=iters,
                      damping=1e-3, ink_limit=limit, boundary_fd=True,
                      tac_projection=True, channel_max=cmax)
    d[:, 3] = k
    d = _project_cmy(d, limit, cmax)
    res = np.linalg.norm(model.predict(d) - target, axis=1)
    return d, res


def locus_k(model, target: np.ndarray, d_ok: np.ndarray, kt: np.ndarray, *,
            limit, cmax, w: float = 0.02,
            iters: int = 24) -> tuple[np.ndarray, np.ndarray]:
    """colprof's in-gamut separation: K = the K target clipped to the K locus
    of the colour (icxKluma5k + RSPL_EXACTAUX). Solved as one Gauss-Newton
    problem: the colour exactly (Lab rows) plus a weak pull of K toward the
    target (one prior row, weight ``w``, no prior on C, M, Y). Along the
    locus the colour rows are flat, so K goes to the target, or stops at the
    locus edge where the colour would be lost (the colour error there is
    ~w / slope^2, far below 0.01 dE). Started from ``d_ok`` (a feasible
    separation); a node whose solve does not stay exact keeps d_ok."""
    from workflow.profile_engine.b2a import _gauss_newton
    n = d_ok.shape[1]
    prior = np.zeros((len(target), n))
    prior_w = np.zeros((len(target), n))
    prior[:, 3] = np.clip(kt, 0.0, cmax[3])
    prior_w[:, 3] = w
    d = _gauss_newton(model, target, d_ok.copy(), np.arange(n), iters=iters,
                      damping=1e-4, ink_limit=limit, prior=prior,
                      prior_w=prior_w, boundary_fd=True, tac_projection=True,
                      channel_max=cmax)
    res = np.linalg.norm(model.predict(d) - target, axis=1)
    res0 = np.linalg.norm(model.predict(d_ok) - target, axis=1)
    bad = res > np.maximum(res0, 0.05) + 0.02
    d[bad] = d_ok[bad]
    res[bad] = res0[bad]
    return d, res


def _cloud(n, limit, cmax, seed=6969):
    from workflow.profile_engine.oog_clip import clip_cloud
    return clip_cloud(n, limit, cmax, np.random.default_rng(seed),
                      light=True, faces=True)


def nearest_lab(model, target: np.ndarray, d0: np.ndarray, *, limit, cmax,
                iters: int = 14) -> np.ndarray:
    """colprof's first clip: the nearest printable colour in plain Lab (no
    ink priors), under the ink limit; started from d0 and from the nearest
    cloud point, the closer answer kept."""
    from workflow.profile_engine.b2a import _gauss_newton
    free = np.arange(4)
    kw = dict(iters=iters, damping=1e-3, ink_limit=limit, boundary_fd=True,
              tac_projection=True, channel_max=cmax)
    a = _gauss_newton(model, target, np.minimum(d0, cmax[None]), free, **kw)
    ra = np.linalg.norm(model.predict(a) - target, axis=1)
    cl = _cloud(4, limit, cmax)
    cl_lab = model.predict(cl)
    seeds = np.empty_like(d0)
    c2 = (cl_lab ** 2).sum(1)
    for lo in range(0, len(target), 1024):
        t = target[lo:lo + 1024]
        seeds[lo:lo + 1024] = cl[np.argmin(c2[None] - 2.0 * t @ cl_lab.T, 1)]
    b = _gauss_newton(model, target, seeds, free, **kw)
    rb = np.linalg.norm(model.predict(b) - target, axis=1)
    take = rb < ra
    a[take] = b[take]
    return a


def _project4(d, limit, cmax):
    from workflow.profile_engine.b2a import project_tac
    d = np.clip(d, 0.0, cmax[None])
    if limit is not None:
        d = project_tac(d, limit)
    return d


def _descend_jab(predict_j, t_j, d0, *, limit, cmax, iters: int = 14,
                 damping: float = 1e-3, h: float = 1e-4):
    """Levenberg-Marquardt on the rev.c LCh-weighted residual in Jab, inside
    the device box and under the ink limit (projected steps, backtracking,
    never accepting a step that raises the distance)."""
    from workflow.profile_engine.purecolprof import lchw_residual
    d = _project4(d0.astype(float), limit, cmax)
    n = d.shape[1]
    r = lchw_residual(predict_j(d), t_j)
    c = (r * r).sum(1)
    eye = np.eye(n)
    for _ in range(iters):
        jac = np.empty((len(d), 3, n))
        for k in range(n):
            step = np.where(d[:, k] + h <= cmax[k], h, -h)
            dk = d.copy()
            dk[:, k] += step
            jac[:, :, k] = (lchw_residual(predict_j(dk), t_j) - r) \
                / step[:, None]
        jtj = np.einsum("nik,nil->nkl", jac, jac)
        lam = damping * (np.trace(jtj, axis1=1, axis2=2) / n + 1e-12)
        g = np.einsum("nik,ni->nk", jac, r)
        stp = -np.linalg.solve(jtj + lam[:, None, None] * eye[None],
                               g[..., None])[..., 0]
        acc = np.zeros(len(d), bool)
        for k in range(6):
            cand = _project4(d + stp * (0.5 ** k), limit, cmax)
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


def cam_clip(model, target_lab: np.ndarray, d_lab: np.ndarray, *, limit,
             cmax) -> np.ndarray:
    """colprof's second clip (xlut.c:1325-1418): nearest in Argyll Jab under
    the rev.c LCh weights and the ink limit, blended with the Lab answer
    linearly over CAMCLIPTRANS of the CAM clip distance."""
    from workflow.profile_engine.oog_clip import lab_to_argyll_jab
    def pj(dev):
        return lab_to_argyll_jab(model.predict(dev))
    t_j = lab_to_argyll_jab(target_lab)
    best, bc = _descend_jab(pj, t_j, d_lab, limit=limit, cmax=cmax)
    from workflow.profile_engine.purecolprof import _cloud_seed
    cl = _cloud(4, limit, cmax, seed=5858)
    seeds = _cloud_seed(t_j, cl, pj(cl))
    d2, c2 = _descend_jab(pj, t_j, seeds, limit=limit, cmax=cmax)
    take = c2 < bc
    best[take] = d2[take]
    cdist = np.linalg.norm(pj(best) - t_j, axis=1)
    bf = np.clip(cdist / CAMCLIPTRANS, 0.0, 1.0)[:, None]
    return (1.0 - bf) * d_lab + bf * best


def colprof_table(model, node_lab: np.ndarray, d_ours: np.ndarray,
                  residual: np.ndarray, *, ink_limit, channel_max, l_min: float,
                  ourk: bool = False, ourclip: bool = False,
                  progress=None) -> tuple[np.ndarray, dict]:
    """The colorimetric B2A1 per node, colprof's recipe (module docstring).

    ``d_ours``: the engine's own per-node answer (feasible start for the
    locus search, start for the clip). ``ourk``: in-gamut nodes keep the
    engine's own separation (ablation of the K rule); ``ourclip``: clipped
    nodes keep the engine's own clip (ablation of the clip)."""
    n = model.n_channels
    limit = None if ink_limit is None else float(ink_limit) / 100.0
    cmax = np.ones(n) if channel_max is None else np.asarray(channel_max,
                                                             float)
    d_ours = np.clip(np.asarray(d_ours, float), 0.0, cmax[None])
    if limit is not None:
        d_ours = _project4(d_ours, limit, cmax)
    res0 = np.linalg.norm(model.predict(d_ours) - node_lab, axis=1)
    # in gamut: the engine's own per-node inversion converged there (its
    # residual; the neutral column's axis values may sit a step off)
    inside = (np.asarray(residual) < FEAS_TOL) | (res0 < FEAS_TOL)
    out = d_ours.copy()
    info = {"inside": int(inside.sum()), "l_min": float(l_min)}
    ii = np.flatnonzero(inside)
    if len(ii) and not ourk:
        if progress:
            progress("colprof K rule on the in-gamut nodes…")
        kt = k_target(node_lab[ii, 0], l_min)
        d_in, r_in = locus_k(model, node_lab[ii], d_ours[ii], kt,
                             limit=limit, cmax=cmax)
        out[ii] = d_in
        info["k_at_target"] = float(np.mean(np.abs(d_in[:, 3] - kt) < 1e-3))
        info["in_res_p99"] = float(np.percentile(r_in, 99))
    oo = np.flatnonzero(~inside)
    if len(oo) and not ourclip:
        if progress:
            progress("colprof clip (Lab nearest, then CAM Jab)…")
        d_n = nearest_lab(model, node_lab[oo], d_ours[oo], limit=limit,
                          cmax=cmax)
        out[oo] = cam_clip(model, node_lab[oo], d_n, limit=limit, cmax=cmax)
    info["clipped"] = int(len(oo))
    return out, info


def upsample(coarse: np.ndarray, g_coarse: int, g_fine: int) -> np.ndarray:
    """Trilinear upsample of a (g_coarse^3, n) table onto the g_fine grid
    (exact at the shared nodes): what a CMM reads from colprof's grid."""
    n = coarse.shape[1]
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
    return up.reshape(-1, n)


def dark_weight(node_lab: np.ndarray, l_black: float) -> np.ndarray:
    """a69-cmykport-dark: weight of colprof's table per node, 1 up to
    black + A69_DARK_L L*, smoothstep to 0 over the next A69_DARK_W L*
    (env CHROMIQ_A69_DARK=l:w)."""
    l0, w = (float(v) for v in os.environ.get("CHROMIQ_A69_DARK",
                                              "20:15").split(":"))
    u = np.clip((l_black + l0 + w - np.asarray(node_lab, float)[:, 0])
                / max(w, 1e-6), 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)
