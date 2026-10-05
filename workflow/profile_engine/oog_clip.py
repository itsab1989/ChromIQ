"""Out-of-gamut clipping for the colorimetric B2A (research, Agent 25:
F-15 / F-17, tokens ``a25-*``; off by default).

The integration-2 clip (b2a.invert_to_device, "hue-preserving clip") picks
per node between a polished and a RAW cloud seed with a hue-angle gate, in
CIELAB. Two defects follow from that design (Findings F-15, F-17):

* a discrete accept / reject per node is not a continuous function of the
  target, so neighbouring nodes switch between two answers (tonal
  reversals, contours) and a rejected polish writes an unrefined seed
  (pale colours 25-35 L* too dark);
* constant CIELAB hue is not constant perceived hue in the blues, so a
  saturated blue clipped at constant CIELAB hue prints purple.

This module replaces it with ONE objective and no switches: every
out-of-gamut node goes to the printable colour that minimises a weighted
distance in a hue-linear space (default CAM16-UCS; CIELAB, Oklab and IPT for
the ablation)

    cost = wJ dJ^2 + wC dRad^2 + wH(C) dTan^2

measured in the target's own hue frame (dRad along the target's chroma
direction, dTan across it), with the hue weight faded in smoothly with the
target's chroma (no neutral / chromatic switch at any chroma). The minimum
is searched from several starts (the plain nearest clip, the cloud colour of
least cost, the hue-gated seed) and the lowest-cost polished answer wins:
the choice is a minimisation of one continuous function, so it cannot jump
between neighbouring nodes except where two answers genuinely tie. Near
the gamut surface the result is blended into the plain nearest clip over a
transition band (Argyll xlut.c does the same between its PCS and CAM
clips, CAMCLIPTRANS), so the in-gamut / out-of-gamut border is continuous.

Prior art: Argyll colprof clips to the nearest point in CIECAM02 Jab with
LCh weights J 2.0, C 1.0, H 2.2 (xicc/xlut.c JCCWEIGHT/CCCWEIGHT/HCCWEIGHT,
USELCHWEIGHT, rspl/rev.c rev_set_lchw); CIE 156's baseline HPMINDE (hue
preserving minimum dE in CIELAB) is known to lose too much lightness on
light colours and to turn blues purple (Braun, Ebner, Fairchild 1998).
"""
from __future__ import annotations

import numpy as np

# Research switches, set by builder for one build (b2a.set_research_tokens).
PARAMS: dict = {
    "on": False,
    "space": "ucs",        # ucs | lab | oklab | ipt
    "wj": 2.0, "wc": 1.0, "wh": 2.2,
    "c_fade": 10.0,        # chroma over which the hue weight fades in
    "iters": 8,
    "blend_lo": 0.5, "blend_hi": 2.0,   # residual band of the blend (dE76)
    "faces": True,         # device-cube faces in the clip cloud
    "ab_scale": 1.0,       # scale of the opponent axes (Oklab ab are ~3x
                           # compressed against L relative to dE units)
    "l_scale": 1.0,        # scale of the lightness axis
    "hue_start": False,
    "hue_from": "",        # "" = the space's own hue; else oklab | ipt | ucs:
                           # the radial direction in the clip space follows
                           # that space's constant-hue line (hue-linearised)
    "chord": 0.5,          # chroma fraction of the hue-line point (pass 1)
    "pass2": False,        # re-aim the frame at the pass-1 result's chroma    # also start from the integration-2 hue-gated seed
}

DEFAULTS = dict(PARAMS)


# --- hue-linear views ------------------------------------------------------
_BRADFORD = np.array([[0.8951, 0.2664, -0.1614],
                      [-0.7502, 1.7135, 0.0367],
                      [0.0389, -0.0685, 1.0296]])
_D50 = np.array([96.422, 100.0, 82.521])
_D65 = np.array([95.047, 100.0, 108.883])


def _cat(src, dst):
    s = _BRADFORD @ src
    d = _BRADFORD @ dst
    return np.linalg.inv(_BRADFORD) @ np.diag(d / s) @ _BRADFORD


_D50_TO_D65 = _cat(_D50, _D65)
_OK_M1 = np.array([[0.8189330101, 0.3618667424, -0.1288597137],
                   [0.0329845436, 0.9293118715, 0.0361456387],
                   [0.0482003018, 0.2643662691, 0.6338517070]])
_OK_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                   [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
_IPT_LMS = np.array([[0.4002, 0.7075, -0.0807],
                     [-0.2280, 1.1500, 0.0612],
                     [0.0, 0.0, 0.9184]])
_IPT_IPT = np.array([[0.4000, 0.4000, 0.2000],
                     [4.4550, -4.8510, 0.3960],
                     [0.8056, 0.3572, -1.1628]])


def _xyz65(lab):
    from workflow.profile_engine.ti3_data import lab_to_xyz
    return (_D50_TO_D65 @ lab_to_xyz(np.atleast_2d(lab)).T).T / 100.0


def lab_to_oklab(lab):
    lms = (_OK_M1 @ _xyz65(lab).T).T
    return 100.0 * (_OK_M2 @ np.cbrt(lms).T).T


def lab_to_ipt(lab):
    lms = (_IPT_LMS @ _xyz65(lab).T).T
    lmsp = np.sign(lms) * np.abs(lms) ** 0.43
    return 100.0 * (_IPT_IPT @ lmsp.T).T


def _lab_from_xyz65(xyz65_1):
    from workflow.profile_engine.ti3_data import xyz_to_lab
    xyz50 = (np.linalg.inv(_D50_TO_D65) @ (np.asarray(xyz65_1) * 100.0).T).T
    return xyz_to_lab(xyz50)


def oklab_to_lab(ok):
    lmsp = (np.linalg.inv(_OK_M2) @ (np.asarray(ok) / 100.0).T).T
    return _lab_from_xyz65((np.linalg.inv(_OK_M1) @ (lmsp ** 3).T).T)


def ipt_to_lab(ipt):
    lmsp = (np.linalg.inv(_IPT_IPT) @ (np.asarray(ipt) / 100.0).T).T
    lms = np.sign(lmsp) * np.abs(lmsp) ** (1.0 / 0.43)
    return _lab_from_xyz65((np.linalg.inv(_IPT_LMS) @ lms.T).T)


def _pair(space: str):
    if space == "oklab":
        return lab_to_oklab, oklab_to_lab
    if space == "ipt":
        return lab_to_ipt, ipt_to_lab
    if space == "ucs":
        from workflow.profile_engine.ucs import print_ucs
        u = print_ucs()
        return u.lab_to_ucs, u.ucs_to_lab
    raise ValueError(space)


def hue_line_angle(t_lab: np.ndarray, space: str, k) -> np.ndarray:
    """Lab angle of the direction from each target toward the point of the
    SAME hue in ``space`` (hue-linear) at chroma fraction ``k`` (scalar or
    per row) and the same lightness there: the radial direction of a
    hue-linearised CIELAB frame (Braun, Ebner, Fairchild 1998)."""
    fwd, inv = _pair(space)
    s = fwd(t_lab)
    s2 = s.copy()
    kk = np.broadcast_to(np.asarray(k, float), (len(s),))
    s2[:, 1] *= kk
    s2[:, 2] *= kk
    back = inv(s2)
    d = t_lab[:, 1:] - back[:, 1:]
    own = np.arctan2(t_lab[:, 2], t_lab[:, 1])
    small = np.hypot(d[:, 0], d[:, 1]) < 1e-6
    ang = np.arctan2(d[:, 1], d[:, 0])
    ang[small] = own[small]
    return ang


def space_fn(space: str):
    k = float(PARAMS.get("ab_scale", 1.0))
    kl = float(PARAMS.get("l_scale", 1.0))
    if k != 1.0 or kl != 1.0:
        base = _space_fn(space)
        sc = np.array([kl, k, k])
        return lambda lab: base(lab) * sc[None, :]
    return _space_fn(space)


def _space_fn(space: str):
    if space == "lab":
        return lambda lab: np.asarray(lab, float)
    if space == "ucs":
        from workflow.profile_engine.ucs import print_ucs
        u = print_ucs()
        return u.lab_to_ucs
    if space == "oklab":
        return lab_to_oklab
    if space == "ipt":
        return lab_to_ipt
    raise ValueError(space)


class SpaceView:
    """Forward model predicting the clip space (Lab -> space after the
    model), the interface _gauss_newton needs."""

    def __init__(self, model, fn) -> None:
        self._model = model
        self._fn = fn
        self.n_channels = model.n_channels

    def predict(self, dev):
        return self._fn(self._model.predict(dev))


# --- the metric -------------------------------------------------------------
def weights(target_s: np.ndarray, p: dict = PARAMS,
            angle: np.ndarray | None = None) -> np.ndarray:
    """(N,3,3) W with |W (y - t)|^2 = wJ dJ^2 + wC dRad^2 + wH(C) dTan^2 in
    the target's hue frame; wH fades from wC (no hue at C = 0) to wH by
    C = c_fade (smoothstep), so the metric is continuous in the target."""
    n = len(target_s)
    c = np.hypot(target_s[:, 1], target_s[:, 2])
    h = np.arctan2(target_s[:, 2], target_s[:, 1]) if angle is None else angle
    ch, sh = np.cos(h), np.sin(h)
    s = np.clip(c / p["c_fade"], 0.0, 1.0)
    s = s * s * (3.0 - 2.0 * s)
    sj, sc = np.sqrt(p["wj"]), np.sqrt(p["wc"])
    shh = np.sqrt(p["wc"] + (p["wh"] - p["wc"]) * s)
    w = np.zeros((n, 3, 3))
    w[:, 0, 0] = sj
    # rows: radial component (sc * u.dab), tangential (shh * u_perp.dab)
    w[:, 1, 1] = sc * ch
    w[:, 1, 2] = sc * sh
    w[:, 2, 1] = -shh * sh
    w[:, 2, 2] = shh * ch
    return w


def cost(pred_s: np.ndarray, target_s: np.ndarray, w: np.ndarray) -> np.ndarray:
    r = np.einsum("nij,nj->ni", w, pred_s - target_s)
    return (r * r).sum(1)


def best_cloud_seed(target_s, w, cloud, cloud_s, block: int = 256):
    """Cloud point of least weighted cost for every target (exact, no gate).
    cost = (c - t)' M (c - t), M = W'W, expanded so a block costs one
    (m, 6) x (6, b) and one (m, 3) x (3, b) product (no (b, m, 3) array)."""
    out = np.empty((len(target_s), cloud.shape[1]))
    m = np.einsum("nji,njk->nik", w, w)                  # (N, 3, 3)
    c = cloud_s
    q = np.stack([c[:, 0] ** 2, c[:, 1] ** 2, c[:, 2] ** 2,
                  2 * c[:, 0] * c[:, 1], 2 * c[:, 0] * c[:, 2],
                  2 * c[:, 1] * c[:, 2]], 1)              # (m, 6)
    for lo in range(0, len(target_s), block):
        mb = m[lo:lo + block]
        tb = target_s[lo:lo + block]
        m6 = np.stack([mb[:, 0, 0], mb[:, 1, 1], mb[:, 2, 2],
                       mb[:, 0, 1], mb[:, 0, 2], mb[:, 1, 2]], 1)   # (b, 6)
        mt = np.einsum("bij,bj->bi", mb, tb)             # (b, 3)
        score = q @ m6.T - 2.0 * (c @ mt.T)              # (m, b)
        out[lo:lo + block] = cloud[np.argmin(score, 0)]
    return out


def clip_cloud(n: int, limit, channel_max, rng, *, light: bool, faces: bool):
    """Uniform device cloud plus light / sparse points and points on the
    device-cube faces (the gamut boundary of a 3-channel device; for ink
    devices the faces near paper are where pale boundary colours live)."""
    m = min(40000, 6000 * n)
    parts = [rng.uniform(0.0, 1.0, (m, n))]
    if light:
        a = rng.uniform(0.0, 1.0, (m // 2, n)) * rng.uniform(0.0, 1.0, (m // 2, 1)) ** 2
        parts.append(a)
    if faces:
        f = rng.uniform(0.0, 1.0, (m, n))
        ax = rng.integers(0, n, m)
        f[np.arange(m), ax] = rng.integers(0, 2, m).astype(float)
        parts.append(f)
        if n > 3:
            # ink devices: two channels at zero (the light 1-2 ink faces)
            g = rng.uniform(0.0, 1.0, (m, n)) ** 2
            for i in range(m):
                g[i, rng.choice(n, n - 2, replace=False)] = 0.0
            parts.append(g)
    c = np.vstack(parts)
    if channel_max is not None:
        c *= channel_max[None, :]
    if limit is not None:
        tot = c.sum(1)
        over = tot > limit
        c[over] *= (limit / tot[over])[:, None]
    return c


def clip_nodes(model, target_lab, d_near, residual, *, free, limit,
               channel_max, prior, prior_w, gn_kw, damping, hue_seeds=None,
               progress_label="") -> np.ndarray:
    """New device values for every node with residual > blend_lo.

    ``d_near``: the nearest-clip answer (first pass + retry) for ALL nodes;
    returns a full copy with the clipped rows replaced."""
    from workflow.profile_engine import b2a
    p = PARAMS
    out = d_near.copy()
    sel = np.flatnonzero(residual > p["blend_lo"])
    if not len(sel):
        return out
    fn = space_fn(p["space"])
    view = SpaceView(model, fn)
    t_lab = target_lab[sel]
    t_s = fn(t_lab)
    hue_from = p.get("hue_from") or ""
    if hue_from and p["space"] != "lab":
        raise ValueError("hue_from needs space 'lab'")
    w = weights(t_s, p, hue_line_angle(t_lab, hue_from, p["chord"])
                if hue_from else None)
    n = model.n_channels
    cloud = clip_cloud(n, limit, channel_max, np.random.default_rng(2525),
                       light=True, faces=p["faces"])
    cloud_s = fn(model.predict(cloud))
    starts = [d_near[sel], best_cloud_seed(t_s, w, cloud, cloud_s)]
    if p.get("hue_start"):
        from workflow.profile_engine import b2a as _b
        c2, c2_lab = _b._cloud_and_lab(model, model, n, limit, channel_max,
                                        4321, memo=True)
        hs, found = _b._hue_gated_seeds(t_lab, c2, c2_lab)
        hs[~found] = d_near[sel][~found]
        starts.append(hs)
    pr = None if prior is None else prior[sel]
    pw = None if prior_w is None else prior_w[sel]
    best = None
    best_cost = None
    for k, s0 in enumerate(starts):
        d = b2a._gauss_newton(view, t_s, s0.copy(), free, iters=p["iters"],
                              damping=damping, ink_limit=limit, err_weights=w,
                              prior=pr, prior_w=pw,
                              progress_label=f"{progress_label}: weighted clip "
                                             f"{k + 1}/{len(starts)}", **gn_kw)
        cst = cost(view.predict(d), t_s, w)
        if best is None:
            best, best_cost = d, cst
        else:
            better = cst < best_cost
            best[better] = d[better]
            best_cost[better] = cst[better]
    if hue_from and p.get("pass2"):
        # Re-aim the hue frame at the chroma the first pass reached (the
        # constant-hue line is curved; the chord to the answer is its
        # direction there), then polish once more from the answer.
        got = model.predict(best)
        fwd, _ = _pair(hue_from)
        cs_t = np.hypot(*fwd(t_lab)[:, 1:].T)
        cs_g = np.hypot(*fwd(got)[:, 1:].T)
        k = np.clip(cs_g / np.maximum(cs_t, 1e-9), 0.05, 1.0)
        w = weights(t_s, p, hue_line_angle(t_lab, hue_from, k))
        d = b2a._gauss_newton(view, t_s, best.copy(), free, iters=p["iters"],
                              damping=damping, ink_limit=limit, err_weights=w,
                              prior=pr, prior_w=pw,
                              progress_label=f"{progress_label}: weighted clip "
                                             f"(re-aimed)", **gn_kw)
        best = d
    # Continuous hand-over to the nearest clip near the surface.
    lo, hi = p["blend_lo"], p["blend_hi"]
    bf = np.clip((residual[sel] - lo) / (hi - lo), 0.0, 1.0)
    bf = bf * bf * (3.0 - 2.0 * bf)
    out[sel] = (1.0 - bf)[:, None] * d_near[sel] + bf[:, None] * best
    if limit is not None:
        tot = out[sel].sum(1)
        over = tot > limit
        if over.any():
            rows = sel[over]
            out[rows] = b2a.project_tac(out[rows], limit)
    if channel_max is not None:
        out = np.minimum(out, channel_max[None, :])
    return out
