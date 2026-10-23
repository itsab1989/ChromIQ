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
          "a69-cmykport-17in", "a69-cmykport-oog", "a69-cmykport-oogpn",
          "a69-cmykport-oogdark", "a69-cmykport-oogfine",
          "a69-cmykport-darkin")

# Argyll constants
KSMTH = 0.09          # ICXINKDEFSMTH, xicc.h:183
KSKEW = 2.0           # ICXINKDEFSKEW, xicc.h:184
RAMP = (0.0, 0.0, 1.0, 1.0, 1.0)   # -kr: Kstle, Kstpo, Kenpo, Kenle, Kshap
CAMCLIPTRANS = 1.0
FEAS_TOL = 0.2        # dE76: a fixed-K C, M, Y solve this close is "exact"


def mode(candidates) -> dict | None:
    """The port's switches from the build's tokens, or None (port off)."""
    c = frozenset(candidates or ())
    if "a69-cmykport-oogdark" in c:
        c = c | {"a69-cmykport-oog"}
    if not any(t.startswith(TOKEN) for t in c):
        return None
    return {"grid17": "a69-cmykport-17" in c,
            "in17": "a69-cmykport-17in" in c,
            "oog": "a69-cmykport-oog" in c or "a69-cmykport-oogpn" in c,
            "oogpn": "a69-cmykport-oogpn" in c,
            "oogdark": "a69-cmykport-oogdark" in c,
            "oogfine": "a69-cmykport-oogfine" in c,
            "darkin": "a69-cmykport-darkin" in c,
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


# --- Agent 70: the ink fold near black -----------------------------------------
A70_FOLDCAP = "a70-foldcap"
FOLD_DL = 1.0         # L* a single ink may LIGHTEN the print before it counts
FOLD_KEEP = 0.5       # the fold region: lightening above this, run ending at K 1
FOLD_PEAK = 1.5       # and reaching this somewhere (else model noise)
FOLD_C0, FOLD_C1 = 6.0, 12.0   # target C*: cap gone below C0, full above C1
FOLD_L0, FOLD_L1 = -10.0, 0.0   # target L* - black: cap gone below L0, full above L1


def _ss(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def k_fold(model, n: int = 4):
    """Where the ink fold near black starts, or None. Adding 5-20 % of C, M or
    Y to K alone must make the print LIGHTER: the fold region is the run of K
    (0.7..1, step 0.01) ending at K 1 in which it lightens by more than
    FOLD_KEEP L*; it counts only if it lightens by FOLD_PEAK somewhere in it
    (fitted synthetic printers show up to 0.8 L* of noise at K 1, i1iSis 2,
    i1Pro 5); the fold starts at the first K of the run above FOLD_DL,
    minus 0.01."""
    ks = np.arange(0.70, 1.0001, 0.01)
    base = np.zeros((len(ks), n))
    base[:, 3] = ks
    l0 = model.predict(base)[:, 0]
    worst = np.full(len(ks), -np.inf)
    for c in (0.05, 0.1, 0.2):
        for ch in range(3):
            d = base.copy()
            d[:, ch] = c
            worst = np.maximum(worst, model.predict(d)[:, 0] - l0)
    if worst[-1] <= FOLD_KEEP:
        return None
    j = len(ks) - 1
    while j > 0 and worst[j - 1] > FOLD_KEEP:
        j -= 1
    run = worst[j:]
    if run.max() < FOLD_PEAK:
        return None
    first = j + int(np.flatnonzero(run > FOLD_DL)[0])
    return float(max(ks[first] - 0.01, 0.7))


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
                  progress=None, fold: bool = False) -> tuple[np.ndarray, dict]:
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
        kf = k_fold(model) if fold else None
        info["k_fold"] = kf
        if kf is None:
            d_n = nearest_lab(model, node_lab[oo], d_ours[oo], limit=limit,
                              cmax=cmax)
            out[oo] = cam_clip(model, node_lab[oo], d_n, limit=limit,
                               cmax=cmax)
        else:
            # Agent 70 (a70-foldcap): on a printer whose inks LIGHTEN the
            # print above some K (i1Pro: K 0.97 alone L* 26, + 8 % C/M/Y
            # L* 28-30; i1iSis from K 0.8), the clip of a chromatic target
            # jumps between a K+C/M/Y answer and the K-only black and the
            # ramp goes dark, colour, dark. Chromatic clipped nodes may not
            # use K above the fold; the cap relaxes toward the neutrals.
            # the cap relaxes toward the neutrals (C* below FOLD_C1, gone
            # below FOLD_C0) and toward the black (target L* below the
            # black + FOLD_L1, gone at the black + FOLD_L0), so dark targets
            # still reach the K-only black, at the end of the ramp
            cc = np.hypot(node_lab[oo, 1], node_lab[oo, 2])
            fc = _ss((FOLD_C1 - cc) / (FOLD_C1 - FOLD_C0))
            fl = _ss((l_min + FOLD_L1 - node_lab[oo, 0]) / (FOLD_L1 - FOLD_L0))
            frac = np.round(np.maximum(fc, fl) * 4.0) / 4.0
            for f in np.unique(frac):
                sel = oo[frac == f]
                cm = cmax.copy()
                cm[3] = min(cm[3], kf + f * (cm[3] - kf))
                seed = np.minimum(d_ours[sel], cm[None])
                d_n = nearest_lab(model, node_lab[sel], seed, limit=limit,
                                  cmax=cm)
                out[sel] = cam_clip(model, node_lab[sel], d_n, limit=limit,
                                    cmax=cm)
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


# --- Agent 70 (a70-portrefit) -------------------------------------------------
A70_PORTREFIT = "a70-portrefit"


def oog_target(model, node_lab, dev_clut, residual, *, ink_limit,
               channel_max, l_min, grid, oogfine, progress=None,
               fold=False):
    """The a69-cmykport-oog(+oogfine) clipped-node target as the builder
    blends it: (shaped device table, hand-over weight w per node). Same
    arithmetic as the builder's oog branch (band CHROMIQ_A69_BAND, fine
    hand-over CHROMIQ_A69_FINE)."""
    n = model.n_channels
    pure, info = colprof_table(model, node_lab, dev_clut, residual,
                               ink_limit=ink_limit, channel_max=channel_max,
                               l_min=l_min, progress=progress, fold=fold)
    pure_s = np.clip(model.shape_device(pure), 0.0, 1.0)
    if channel_max is not None:
        pure_s = np.minimum(pure_s, model.shape_device(
            np.asarray(channel_max, float)[None, :]))
    st = (grid - 1) // 16
    up = (upsample(pure_s.reshape(grid, grid, grid, n)[::st, ::st, ::st]
                   .reshape(-1, n), 17, grid)
          if (grid - 1) % 16 == 0 else pure_s)
    band = float(os.environ.get("CHROMIQ_A69_BAND",
                                "6.0" if oogfine else "2.0"))
    if oogfine:
        fb = float(os.environ.get("CHROMIQ_A69_FINE", "8.0"))
        v = np.clip((np.asarray(residual, float) - band)
                    / max(fb - band, 1e-6), 0.0, 1.0)
        v = (v * v * (3.0 - 2.0 * v))[:, None]
        up = (1.0 - v) * pure_s + v * up
    u = np.clip(np.asarray(residual, float) / band, 0.0, 1.0)
    w = u * u * (3.0 - 2.0 * u)
    return up, w, info


A70_EDGESMOOTH = "a70-edgesmooth"
A70_EDGEADAPT = "a70-edgeadapt"


def _nb_morph(m, op):
    out = m.copy()
    for ax in range(3):
        for sh in (1, -1):
            r = np.roll(m, sh, axis=ax)
            idx = [slice(None)] * 3
            idx[ax] = 0 if sh == 1 else -1
            r[tuple(idx)] = m[tuple(idx)]
            out = op(out, r)
    return out


def edge_layers(inside: np.ndarray, grid: int, depth: int = 6):
    """Grid distance (in cells, 1..depth) of every in-gamut node to the
    nearest clipped node (``dep``) and of every clipped node to the nearest
    in-gamut node (``hgt``); 0 where farther than ``depth``."""
    ins = inside.reshape(grid, grid, grid)
    dep = np.zeros(ins.shape)
    hgt = np.zeros(ins.shape)
    cur = ins.copy()
    for k in range(1, depth + 1):
        nxt = _nb_morph(cur, np.logical_and)
        dep[cur & ~nxt] = k
        cur = nxt
    cur = ~ins
    for k in range(1, depth + 1):
        nxt = _nb_morph(cur, np.logical_and)
        hgt[cur & ~nxt] = k
        cur = nxt
    return dep.reshape(-1), hgt.reshape(-1)


def edge_smooth(shaped: np.ndarray, residual: np.ndarray, node_lab: np.ndarray,
                grid: int, fixed_nodes=None, params: str | None = None,
                model=None, adapt: str | None = None):
    """Agent 70 (a70-edgesmooth): soften the slope break where the colour-to-
    black ramps leave the gamut. In-gamut nodes print their target exactly
    and the clipped neighbour prints the surface colour, so along a ramp the
    printed L* follows the source with slope 1 and then the surface: a band
    edge at the boundary node plane (FOGRA mid yellow, L* 21.9). colprof's
    17 grid softens the same break over its wider cells (at an accuracy cost
    there). Here a few Jacobi passes average chromatic dark nodes with their
    six neighbours in a thin band across the boundary: clipped nodes up to
    ``hmax`` cells out (weight ``ac``), the first in-gamut layer (``a1``) and
    the second (``a2``). Params (env CHROMIQ_A70_EDGE)
    a1:a2:hmax:iters:lmax:cmin:ac, default 0.3:0:3:4:75:6:0.5."""
    p = (params or os.environ.get("CHROMIQ_A70_EDGE")
         or "0.3:0:3:4:75:6:0.5").split(":")
    a1, a2, hmax, it, lmax, cmin, ac = (float(v) for v in p)
    nl = np.asarray(node_lab, float)
    inside = np.asarray(residual, float) < 0.5
    dep, hgt = edge_layers(inside, grid)
    a = np.zeros(len(nl))
    a[dep == 1] = a1
    a[dep == 2] = a2
    if model is not None and adapt:
        # Agent 70 (a70-edgeadapt): the in-gamut layer moves only as much
        # as the break next to it needs: its weight rises (smoothstep) with
        # how far its clipped neighbours print from their own targets, from
        # b0 to b1 dE (CHROMIQ_A70_ADAPT, default 2:5). Where the gamut
        # surface is close to the targets there is no break to soften and
        # the in-gamut node keeps its exact value (synthetic X3 B2A p95:
        # 1.55 with the plain weight, 1.25 adaptive, base 0.86).
        b0, b1 = (float(v) for v in adapt.split(":"))
        pr = model.predict(np.clip(model.unshape_device(
            np.asarray(shaped, float)), 0.0, 1.0))
        off = np.linalg.norm(pr - nl, axis=1)
        off[inside] = 0.0
        O = off.reshape(grid, grid, grid)
        nb = np.zeros_like(O)
        for ax in range(3):
            for sh in (1, -1):
                r = np.roll(O, sh, axis=ax)
                idx = [slice(None)] * 3
                idx[ax] = 0 if sh == 1 else -1
                r[tuple(idx)] = 0.0
                nb = np.maximum(nb, r)
        nb = nb.reshape(-1)
        m1 = dep == 1
        a[m1] = a1 * _ss((nb[m1] - b0) / max(b1 - b0, 1e-6))
    a[(hgt >= 1) & (hgt <= hmax)] = ac
    chrom = np.hypot(nl[:, 1], nl[:, 2]) > cmin
    a[~chrom | (nl[:, 0] >= lmax)] = 0.0
    if fixed_nodes is not None and len(fixed_nodes):
        a[np.asarray(fixed_nodes)] = 0.0
    g = grid
    T = np.asarray(shaped, float).reshape(g, g, g, -1).copy()
    W = a.reshape(g, g, g, 1)
    for _ in range(int(it)):
        nb = np.zeros_like(T)
        cnt = np.zeros((g, g, g, 1))
        for ax in range(3):
            for sh in (1, -1):
                r = np.roll(T, sh, axis=ax)
                v = np.ones((g, g, g, 1))
                idx = [slice(None)] * 3
                idx[ax] = 0 if sh == 1 else g - 1
                v[tuple(idx)] = 0.0
                nb += r * v
                cnt += v
        T = (1.0 - W) * T + W * (nb / cnt)
    return T.reshape(-1, shaped.shape[1]), {"nodes": int((a > 0).sum())}


A70_BLACKSHELL = "a70-blackshell"


def fold_at_black(model, n: int = 4) -> float:
    """How much 5-20 % of C, M or Y LIGHTENS the print at K 1 (L*; <= 0 on a
    press, 1 on i1iSis, 5 on i1Pro)."""
    base = np.zeros((1, n))
    base[0, 3] = 1.0
    l0 = float(model.predict(base)[0, 0])
    worst = -np.inf
    for c in (0.05, 0.1, 0.2):
        for ch in range(3):
            d = base.copy()
            d[0, ch] = c
            worst = max(worst, float(model.predict(d)[0, 0]) - l0)
    return worst


def black_shell(shaped: np.ndarray, residual: np.ndarray, node_lab: np.ndarray,
                black_dev_shaped: np.ndarray, l_min: float, model=None,
                params: str | None = None):
    """Agent 70 (a70-blackshell): below the printable black the clipped nodes
    lean toward the table's black as L* -> 0 and C* -> 0, so a colour-to-
    black ramp's last cells do not interpolate between a dark-blue clip
    answer (K 0.5 + C/M) and the black corner (K 1) through a lighter mix
    (i1iSis sRGB blue: printed L* 22.7 -> 27.4 -> 17.5 over the last 2 % of
    the ramp). Weight smoothstep((l_min - off - L*) / (l_min - off)) ** p *
    smoothstep(1 - C* / cmax); only on a printer whose inks lighten the
    black by about 1 L* (i1iSis), off without a fold and off on a strong one
    (i1Pro: the blend itself crosses it). Params (env CHROMIQ_A70_SHELL) off:p:cmax, default
    3:0.5:80."""
    off, p, cmax = (float(v) for v in (params or os.environ.get(
        "CHROMIQ_A70_SHELL") or "3:0.5:80").split(":"))
    nl = np.asarray(node_lab, float)
    top = max(l_min - off, 1e-6)
    wl = _ss((top - nl[:, 0]) / top) ** p
    wc = _ss(1.0 - np.hypot(nl[:, 1], nl[:, 2]) / cmax)
    w = wl * wc
    w[np.asarray(residual, float) < 0.5] = 0.0
    ff = 1.0
    if model is not None:
        # only on a printer with a fold at the black (i1iSis: inks lighten K
        # 1 by 1.0 L*); presses (<= 0.1) and fitted synthetic printers (0.4-
        # 0.6, model noise) keep the table as it is: there the shell only
        # added a chroma knee at L* 10 (eyecheck GRACoL proxy 41 -> 63);
        # off again on a strong fold (i1Pro, 5 L*) that the blend crosses
        # (the same fold test as a70-foldcap: a fold that reaches the black
        # and peaks above FOLD_PEAK; synthetic fitted models show up to
        # 0.8 L* of noise at K 1 and do not pass it)
        f1 = fold_at_black(model)
        ff = (float(_ss((3.0 - f1) / 2.0))
              if k_fold(model) is not None else 0.0)
    w = w * ff
    out = (1.0 - w[:, None]) * shaped + w[:, None] * np.asarray(
        black_dev_shaped, float)[None, :]
    return out, {"nodes": int((w > 0.01).sum()), "fold_factor": ff}


# --- Agent 71 (a71-darkray) ----------------------------------------------------
A71_DARKRAY = "a71-darkray"
RAY_APEX = -16.0      # colour-to-black ramps are straight lines toward L* -16 (CIE f(t) = t^(1/3))


def _tri(shaped: np.ndarray, grid: int, axes, pts: np.ndarray) -> np.ndarray:
    """Trilinear lookup of a (grid^3, n) Lab-input table at Lab points (as a
    CMM reads a Lab-input table)."""
    T = shaped.reshape(grid, grid, grid, -1)
    idx, frac = [], []
    for k in range(3):
        ax = axes[k]
        x = np.clip(pts[:, k], ax[0], ax[-1])
        i = np.clip(np.searchsorted(ax, x, side="right") - 1, 0, grid - 2)
        idx.append(i)
        frac.append((x - ax[i]) / (ax[i + 1] - ax[i]))
    out = 0.0
    for a in (0, 1):
        wa = frac[0] if a else 1.0 - frac[0]
        for b in (0, 1):
            wb = frac[1] if b else 1.0 - frac[1]
            for c in (0, 1):
                wc = frac[2] if c else 1.0 - frac[2]
                out = out + (wa * wb * wc)[:, None] * T[idx[0] + a, idx[1] + b,
                                                          idx[2] + c]
    return out


def _path(d: np.ndarray, db: np.ndarray, w: np.ndarray, kind: str,
          q: float = 3.0, kf: float | None = None) -> np.ndarray:
    w = np.asarray(w, float)[:, None]
    if kind == "linear":
        return (1.0 - w) * d + w * db[None, :]
    out = d.copy()
    out[:, 3] = d[:, 3] + (db[3] - d[:, 3]) * (1.0 - (1.0 - w[:, 0]) ** q)
    out[:, :3] = d[:, :3] + (db[None, :3] - d[:, :3]) * w ** q
    if kind == "kfold" and kf is not None:
        # K first, but above the fold only as fast as C/M/Y leave
        rem = 1.0 - w[:, 0] ** q
        kmax = np.maximum(d[:, 3], kf + (db[3] - kf) * (1.0 - rem))
        out[:, 3] = np.minimum(out[:, 3], kmax)
    return out


def _tac(d: np.ndarray, lim) -> np.ndarray:
    if lim is None:
        return d
    s = d.sum(1)
    over = s > lim
    if over.any():
        f = np.clip((lim - d[:, 3]) / np.maximum(d[:, :3].sum(1), 1e-6),
                    0.0, 1.0)
        d = d.copy()
        d[over, :3] *= f[over, None]
    return d


def dark_ray(shaped: np.ndarray, residual: np.ndarray, node_lab: np.ndarray,
             grid: int, model, black_dev: np.ndarray, l_min: float, *,
             ink_limit=None, fixed_nodes=None, params: str | None = None):
    """Agent 71 (a71-darkray): below the printable black, a colour-to-black
    ramp must darken steadily into the black. Ramps are straight lines in
    Lab toward L* -16 (``RAY_APEX``), so for every clipped node below
    ``l_min + top`` the table must print no lighter than at the point one
    step further OUT along that line (its "outer" point), and no darker than
    the table's own black. Nodes that break either rule move along a device
    path toward the black (unshaped ``black_dev``) just far enough. The path
    is the one that darkens monotonically on this printer (linear, or K first
    and C/M/Y late where linear mixes print lighter, i1iSis / i1Pro). Sweeps
    run from the outside in. Params (env CHROMIQ_A71_RAY) top:step:tol:sweeps:
    floor:gamma:cmin:cdesc, default 0:3:a:10:0:a:6:12 (tol a = 0.3 where the
    straight path toward the black darkens steadily, else 0; gamma a = 0
    there, else 1: below C* cdesc the cap also descends toward the black's
    L* by (|node| / |outer point|) ** gamma; nodes within C* cmin of the
    neutral axis untouched). Nodes printing darker than the black are
    first lifted (all inks scaled down) to the black's L*, which keeps their
    colour (CHROMIQ_A71_LIFT=0: toward the black instead)."""
    ps = (params or os.environ.get("CHROMIQ_A71_RAY")
          or "0:3:a:10:0:a:6:12").split(":")
    kf = k_fold(model)
    auto_tol = ps[2] == "a"
    if auto_tol:
        ps[2] = "0"
    auto_gam = len(ps) > 5 and ps[5] == "a"
    if auto_gam:
        ps[5] = "0"
    pv = [float(v) for v in ps]
    top, step, tol, sweeps, floor = pv[:5]
    gam = pv[5] if len(pv) > 5 else 0.0
    cmin = pv[6] if len(pv) > 6 else 0.0
    cdesc = pv[7] if len(pv) > 7 else 1e9
    lift = os.environ.get("CHROMIQ_A71_LIFT", "1") == "1"
    nl = np.asarray(node_lab, float)
    out = np.asarray(shaped, float).copy()
    lim = None if ink_limit is None else float(ink_limit) / 100.0
    db = np.clip(np.asarray(black_dev, float), 0.0, 1.0)
    lb = float(model.predict(db[None])[0, 0])
    axes = [np.unique(nl[:, k]) for k in range(3)]
    reg = (np.asarray(residual, float) >= 0.5) & (nl[:, 0] < l_min + top)
    reg &= np.linalg.norm(nl, axis=1) > 1e-6
    # the neutral column and its neighbours stay the engine's (grey ramps)
    reg &= np.hypot(nl[:, 1], nl[:, 2]) > cmin
    if fixed_nodes is not None and len(fixed_nodes):
        reg[np.asarray(fixed_nodes)] = False
    ri = np.flatnonzero(reg)
    info = {"nodes": int(len(ri)), "moved": 0, "path": "", "black_l": lb}
    if not len(ri):
        return out, info
    # the path: the one whose mixes from the region's nodes to the black
    # darken monotonically (fewest L* rises on the model)
    d0 = np.clip(model.unshape_device(out[ri]), 0.0, 1.0)
    ts = np.linspace(0.0, 1.0, 21)
    best, kind = None, "linear"
    kinds = ("linear", "klead") + (("kfold",) if kf is not None
                                   and os.environ.get("CHROMIQ_A71_KFOLD")
                                   == "1" else ())
    for k in kinds:
        Lp = np.stack([model.predict(_tac(_path(d0, db, np.full(len(ri), t),
                                                k, kf=kf), lim))[:, 0]
                       for t in ts], 1)
        r = float(np.mean(np.max(Lp - np.minimum.accumulate(Lp, axis=1),
                                 axis=1) > 0.3))
        if best is None or r < best - 0.02:
            best, kind = r, k
    kind = os.environ.get("CHROMIQ_A71_PATH", kind)
    info["path"] = kind
    if auto_tol and kind == "linear":
        # where the straight mix toward the black already darkens steadily
        # (presses, synthetic printers), model wiggles below 0.3 L* are
        # noise: moving those nodes cost chroma on XKB (oog_ramp_jump
        # 4.2 -> 10); where it does not (i1iSis), every rise is real
        tol = 0.3
    if auto_gam and kind != "linear":
        # where only the K-first path darkens (i1iSis), near the neutral
        # axis (C* < cdesc) the last cells must also DESCEND into the black
        # in proportion to how far along the line they are: there the
        # printer's fold makes K-heavy mixes with a little C/M/Y print up to
        # 2 L* lighter than the model says (proxy), a light stripe before
        # the black (i1iSis proxy blue rise 9.5 -> 2.3, colprof 2.2)
        gam = 1.0
    info["tol"] = tol
    info["gamma"] = gam
    apex = np.array([RAY_APEX, 0.0, 0.0])
    v = nl[ri] - apex
    v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
    outer = nl[ri] + step * v
    moved = np.zeros(len(ri), bool)
    ws = np.linspace(0.0, 1.0, 26)
    for _ in range(int(sweeps)):
        dcur = np.clip(model.unshape_device(out[ri]), 0.0, 1.0)
        Lc = model.predict(dcur)[:, 0]
        do = np.clip(model.unshape_device(_tri(out, grid, axes, outer)),
                     0.0, 1.0)
        Lo = model.predict(do)[:, 0]
        cap = np.maximum(Lo + tol, lb)
        if gam > 0:
            # descend toward the black in proportion to how far along the
            # line the node still is from the black corner (L* 0)
            rho = (np.linalg.norm(nl[ri], axis=1)
                   / np.maximum(np.linalg.norm(outer, axis=1), 1e-9)) ** gam
            dcap = np.maximum(lb + (Lo - lb) * rho, lb)
            near = np.hypot(nl[ri, 1], nl[ri, 2]) < cdesc
            cap = np.where(near, np.minimum(cap, dcap), cap)
        bad = (Lc > cap) | (Lc < lb - floor)
        if not bad.any():
            break
        if lift:
            # nodes printing darker than the black: less ink (all inks
            # scaled down) until they print the black's L*, so the ramp
            # keeps its colour into the last cell instead of greying out
            lo = np.flatnonzero((Lc < lb - floor) & ~(Lc > cap))
            if len(lo):
                fs = np.linspace(0.0, 0.5, 51)
                fb = np.zeros(len(lo))
                got = np.zeros(len(lo), bool)
                for fv in fs:
                    Lw = model.predict(dcur[lo] * (1.0 - fv))[:, 0]
                    ok = (Lw >= lb - floor) & ~got
                    fb[ok] = fv
                    got |= ok
                fb[~got] = 0.5
                dcur[lo] = dcur[lo] * (1.0 - fb[:, None])
                out[ri[lo]] = np.clip(model.shape_device(dcur[lo]), 0.0, 1.0)
                moved[lo] = True
                bad[lo] = False
                if not bad.any():
                    continue
        bi = np.flatnonzero(bad)
        wbest = np.ones(len(bi))
        found = np.zeros(len(bi), bool)
        for wv in ws:
            dd = _tac(_path(dcur[bi], db, np.full(len(bi), wv), kind,
                            kf=kf), lim)
            Lw = model.predict(dd)[:, 0]
            ok = (Lw <= cap[bi]) & (Lw >= lb - floor) & ~found
            wbest[ok] = wv
            found |= ok
        dd = _tac(_path(dcur[bi], db, wbest, kind, kf=kf), lim)
        out[ri[bi]] = np.clip(model.shape_device(dd), 0.0, 1.0)
        moved[bi] = True
    info["moved"] = int(moved.sum())
    return out, info


FOLD_STRONG = 3.0     # L* by which C/M/Y lighten K 1: above this the ray repair is not used


def k_shell(shaped: np.ndarray, residual: np.ndarray, node_lab: np.ndarray,
            model, black_dev: np.ndarray, l_min: float, *, ink_limit=None,
            fixed_nodes=None, params: str | None = None):
    """Agent 71 (a71-darkray on a strong fold at the black, i1Pro): the
    a70-blackshell lean of clipped nodes below the black toward the table's
    black, but along a K-first path (K moves as 1-(1-w)^q, C/M/Y as w^q) in
    device space: on a printer whose C/M/Y LIGHTEN a heavy K, the straight
    mix prints lighter than both ends and the K-first one darkens steadily.
    Weight smoothstep((l_min - off - L*) / (l_min - off)) ** p *
    smoothstep(1 - C* / cmax). Params (env CHROMIQ_A71_KSHELL) off:p:cmax:q,
    default 3:0.5:80:3."""
    off, p, cmax, q = (float(v) for v in (params or os.environ.get(
        "CHROMIQ_A71_KSHELL") or "3:0.5:80:3").split(":"))
    nl = np.asarray(node_lab, float)
    top = max(l_min - off, 1e-6)
    w = (_ss((top - nl[:, 0]) / top) ** p
         * _ss(1.0 - np.hypot(nl[:, 1], nl[:, 2]) / cmax))
    w[np.asarray(residual, float) < 0.5] = 0.0
    if fixed_nodes is not None and len(fixed_nodes):
        w[np.asarray(fixed_nodes)] = 0.0
    out = np.asarray(shaped, float).copy()
    sel = np.flatnonzero(w > 1e-4)
    if len(sel):
        lim = None if ink_limit is None else float(ink_limit) / 100.0
        db = np.clip(np.asarray(black_dev, float), 0.0, 1.0)
        d = np.clip(model.unshape_device(out[sel]), 0.0, 1.0)
        dd = _tac(_path(d, db, w[sel], "klead", q), lim)
        out[sel] = np.clip(model.shape_device(dd), 0.0, 1.0)
    return out, {"nodes": int(len(sel))}


# --- Agent 74 (a74-shellhold, a74-shellhue) ------------------------------------
A74_SHELLHOLD = "a74-shellhold"
A74_SHELLHUE = "a74-shellhue"
A74_SHELL = "3:0.5:50:3"   # k_shell off:p:cmax:q with a74-shellhold (a71 default 3:0.5:80:3)


def shell_hue(pre: np.ndarray, out: np.ndarray, model, *, ink_limit=None,
              cmin: float = 4.0) -> tuple[np.ndarray, dict]:
    """Agent 74 (a74-shellhue): the k-shell moves dark clipped nodes along
    a K-first path toward the black; on a strongly folding printer (i1Pro)
    that path also turns the hue (sRGB blue printed h 293 -> 299, toward
    violet, while the chroma fades). For every moved node with printed C*
    above ``cmin``, C, M and Y are solved again with K held so the print
    keeps the hue the node had before the shell (its clip hue) at the
    shell's own L* and C*; kept only where that lands closer to the
    hue-held target than the shell's answer."""
    moved = np.flatnonzero(np.abs(np.asarray(out) - np.asarray(pre)).max(1)
                           > 1e-6)
    info = {"hue_nodes": 0}
    if not len(moved):
        return out, info
    lim = None if ink_limit is None else float(ink_limit) / 100.0
    d0 = np.clip(model.unshape_device(np.asarray(pre)[moved]), 0.0, 1.0)
    d1 = np.clip(model.unshape_device(np.asarray(out)[moved]), 0.0, 1.0)
    l0, l1 = model.predict(d0), model.predict(d1)
    h0 = np.arctan2(l0[:, 2], l0[:, 1])
    c1 = np.hypot(l1[:, 1], l1[:, 2])
    sel = np.flatnonzero(c1 > cmin)
    if not len(sel):
        return out, info
    tgt = np.stack([l1[sel, 0], c1[sel] * np.cos(h0[sel]),
                    c1[sel] * np.sin(h0[sel])], 1)
    d2, res = solve_cmy(model, tgt, d1[sel], limit=lim,
                        cmax=np.ones(d1.shape[1]))
    ok = res < np.linalg.norm(l1[sel] - tgt, axis=1)
    dd = d1.copy()
    dd[sel[ok]] = d2[ok]
    o = np.asarray(out, float).copy()
    o[moved] = np.clip(model.shape_device(dd), 0.0, 1.0)
    info["hue_nodes"] = int(ok.sum())
    return o, info


def dark_end(shaped, residual, node_lab, grid, model, black_dev, l_min, *,
             ink_limit=None, fixed_nodes=None, hold: bool = False,
             hue: bool = False):
    """Agent 71 (a71-darkray): the dark end of the colorimetric table
    (replaces a70-blackshell). On a printer whose C/M/Y lighten the black
    strongly (by FOLD_STRONG L* or more at K 1, i1Pro), ``k_shell``; else
    ``dark_ray``. Agent 74: ``hold`` (a74-shellhold) runs the k-shell with
    CHROMIQ_A74_SHELL (default A74_SHELL: chromatic nodes lean less, so
    colour holds closer to the black), ``hue`` (a74-shellhue) re-solves the
    moved nodes' C, M, Y to keep their clip hue (``shell_hue``). Neither
    acts on the ray branch."""
    f1 = fold_at_black(model)
    if k_fold(model) is not None and f1 >= FOLD_STRONG:
        out, info = k_shell(shaped, residual, node_lab, model, black_dev,
                            l_min, ink_limit=ink_limit,
                            fixed_nodes=fixed_nodes,
                            params=(os.environ.get("CHROMIQ_A74_SHELL")
                                    or A74_SHELL) if hold else None)
        if hue:
            out, hi = shell_hue(shaped, out, model, ink_limit=ink_limit)
            info.update(hi)
        info["mode"] = "k-shell"
    else:
        out, info = dark_ray(shaped, residual, node_lab, grid, model,
                             black_dev, l_min, ink_limit=ink_limit,
                             fixed_nodes=fixed_nodes)
        info["mode"] = "ray"
    info["fold"] = float(f1)
    return out, info
