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

import threading

import numpy as np

# Research switches, set by builder for one build (b2a.set_research_tokens).
PARAMS: dict = {
    "on": False,
    "space": "lab",        # lab | ucs | jab | oklab | ipt (ablation)
    "wj": 4.0, "wc": 0.35, "wh": 8.0,   # squared LCh weights (Findings s4)
    "c_fade": 10.0,        # chroma over which the hue weight fades in
    "iters": 8,
    "blend_lo": 0.5, "blend_hi": 10.0,  # residual band of the blend (dE76)
    "faces": True,         # device-cube faces in the clip cloud
    "ab_scale": 1.0,       # scale of the opponent axes (Oklab ab are ~3x
                           # compressed against L relative to dE units)
    "l_scale": 1.0,        # scale of the lightness axis
    "hue_start": False,
    "hue_from": "oklab",   # "" = the space's own hue; else oklab | ipt | ucs:
                           # the radial direction in the clip space follows
                           # that space's constant-hue line (hue-linearised)
    "chord": 0.5,          # chroma fraction of the hue-line point (pass 1)
    "pass2": False,
    "descent": True,       # monotone (backtracking) weighted Gauss-Newton
    "propagate": 0,        # rounds of neighbour propagation on a node lattice
    "blend_light": 0.0,    # extra width of the blend band near paper white
    "blend_light_from": 90.0,  # (target L*, smoothstep to 100)
    "neutral_fade": False,  # every weight fades to 1 (the plain nearest clip
                            # in CIELAB) as the target's chroma goes to 0
    "de00": False,         # CIEDE2000 tolerances S_L, S_C, S_H at the target
                           # (space lab only): chroma differences of very
                           # saturated colours count less, as they are seen
    "two_stage": False,    # choose the clip COLOUR without the ink priors,
                           # then separate that colour with them
    "wj_light": 1.0,       # lightness weight multiplier reached at L 100,
    "light_from": 70.0,    # faded in (smoothstep) from this target L
    # Agent 29b (token a29-oog-darkmono): monotone clip into black. Below the
    # black the table's neutral column ends at (dark_floor), the clip aims
    # at that black's L* instead of the target's own: a ramp into black can
    # no longer print darker than its own end and then turn lighter again.
    "dm_on": False,
    "dm_band": 0.0,        # 0: hard floor max(L*, black); > 0: BPC-like
                           # linear scaling of [0, black + band] onto
                           # [black, black + band] (token ...-bpc: 15)
    "dm_blend": 1.0,       # lift (L*) over which a lifted node hands over
                           # fully from the nearest clip to the weighted clip
    "dm_lband": 10.0,      # L* above the black over which the lightness
    "dm_wj": 25.0,         # weight rises (smoothstep) to dm_wj x wj: in the
                           # dark band the clip gives up chroma, not
                           # lightness, so printed L* follows the (monotone)
                           # target L* whatever the target's chroma does
        # re-aim the frame at the pass-1 result's chroma    # also start from the integration-2 hue-gated seed
    # Agent 51 (a51-colprofedge*): colprof's clip metric for the
    # colorimetric table (table_params), set by b2a.set_research_tokens
    "a51": False, "a51_band": 0.0, "a51_ownhue": False, "a51_nofloor": False,
    "a51_lab": False, "a51_soft": 0.0, "a51_ray": False,
    # Agent 56 (a56-blackfade): with a51 on, the chroma of a target lifted
    # to the floor fades smoothly as it lies deeper below the black
    # (blackfade_k); a56_r is the order of the fade
    "a56": False, "a56_r": 2.0, "a56_shape": "rat", "a56_hsmooth": 20.0,
    # Agent 62 (a62-camhue): with a51 on, a target lifted to the floor keeps
    # its CIECAM02 hue (camhue_lift)
    "a62": False,
    # Agent 65 (a65-cmykhue*): on ink devices (no a51 there) the colorimetric
    # clip's hue frame follows this space's constant-hue lines instead of
    # Oklab's ("" = off): "cam02" is colprof's own clip hue (Argyll CIECAM02)
    "a65": "",
}

DEFAULTS = dict(PARAMS)

# The black L* the colorimetric table's neutral column ends at, for the
# thread building that table only (the perceptual / saturation tables may be
# built at the same time on a background thread and must not see it).
_DARK = threading.local()


def set_dark_floor(l_black) -> None:
    """Agent 29b: the colorimetric B2A's black L* (None clears it)."""
    _DARK.l = None if l_black is None else float(l_black)


def dark_floor():
    """The floor in force for this thread, or None (token off / not set)."""
    if not PARAMS.get("dm_on"):
        return None
    return getattr(_DARK, "l", None)


def dark_target_l(l_t: np.ndarray, floor: float, band: float) -> np.ndarray:
    """Monotone (non-decreasing) map of target L* that never goes below
    ``floor``; identity at and above ``floor + band``. band 0 is the hard
    floor max(L*, floor), which leaves every target at or above the black
    exactly as it was."""
    l_t = np.asarray(l_t, float)
    if band <= 0.0:
        return np.maximum(l_t, floor)
    top = floor + band
    scaled = floor + np.maximum(l_t, 0.0) * band / top
    return np.where(l_t >= top, l_t, scaled)


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


def _jab_inverse(jab, iters: int = 12):
    """Agent 65: Argyll CIECAM02 Jab -> D50 Lab (lab_to_argyll_jab inverted
    by damped Newton steps with a numerical Jacobian, row by row in one
    vectorised pass; the map is smooth and close to 1:1 in L, hue)."""
    jab = np.atleast_2d(np.asarray(jab, float))
    # start: J ~ L*, the opponent axes rescaled by the chroma ratio
    lab = jab.copy()
    lab[:, 0] = np.clip(jab[:, 0], 0.0, 100.0)
    for _ in range(iters):
        f0 = lab_to_argyll_jab(lab)
        r = f0 - jab
        if np.abs(r).max() < 1e-6:
            break
        jac = np.empty((len(lab), 3, 3))
        h = 1e-4
        for k in range(3):
            d = lab.copy()
            d[:, k] += h
            jac[:, :, k] = (lab_to_argyll_jab(d) - f0) / h
        try:
            step = np.linalg.solve(jac, r[:, :, None])[:, :, 0]
        except np.linalg.LinAlgError:
            step = np.einsum("nij,nj->ni", np.linalg.pinv(jac), r)
        lab = lab - np.clip(step, -20.0, 20.0)
    # a row that did not converge (none on the B2A grid at any chroma
    # fraction; possible far outside the spectrum locus) keeps the start
    bad = ~(np.linalg.norm(lab_to_argyll_jab(lab) - jab, axis=1) < 1e-2)
    if bad.any():
        lab[bad] = jab[bad]
        lab[bad, 0] = np.clip(jab[bad, 0], 0.0, 100.0)
    return lab


def _pair(space: str):
    if space == "cam02":
        return lab_to_argyll_jab, _jab_inverse
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


def _frame_angle(t_lab, t_s, fn, hue_from, k):
    """Radial direction of the clip frame IN THE CLIP SPACE: from the target
    toward the point of the same ``hue_from`` hue at chroma fraction k."""
    fwd, inv = _pair(hue_from)
    s = fwd(t_lab)
    s2 = s.copy()
    kk = np.broadcast_to(np.asarray(k, float), (len(s),))
    s2[:, 1] *= kk
    s2[:, 2] *= kk
    back_s = fn(inv(s2))
    d = t_s[:, 1:] - back_s[:, 1:]
    own = np.arctan2(t_s[:, 2], t_s[:, 1])
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
    if space == "cam02":
        return lab_to_argyll_jab
    if space == "jab":
        # CAM16 J, a, b from CHROMA C (Argyll's CAM clip space is CIECAM02
        # Jab, xicc/xcam.c): the hue of CAM16 with the plain J / C scales.
        from workflow.profile_engine.ti3_data import lab_to_xyz
        from workflow.profile_engine.ucs import print_ucs
        cam = print_ucs().cam

        def jab(lab):
            jmh = cam.xyz_to_jmh(lab_to_xyz(np.atleast_2d(lab)))
            c = jmh[:, 1] / cam.FL ** 0.25
            h = np.radians(jmh[:, 2])
            return np.stack([jmh[:, 0], c * np.cos(h), c * np.sin(h)], 1)
        return jab
    raise ValueError(space)


# --- Agent 51 (token a51-colprofedge): colprof's own clip metric -----------
# What colprof does for the colorimetric B2A (Argyll 3.5.0; Findings
# agent51-01 s1): every out-of-gamut node is inverted per node to the
# nearest printable colour, first in PCS Lab (plain Euclidean), and beyond
# CAMCLIPTRANS = 1 dE of clip distance the answer is the nearest point in
# CIECAM02 Jab under the output viewing conditions (profout.c
# USE_CAM_CLIP_OPT -> ICX_CAM_CLIP; xlut.c icxLuLut_inv_clut_aux,
# icxLuLut_init_clut_camclip), with the squared LCh weights of rspl/rev.c
# LCHW_SQ: J 2.0^2, C 1.0^2, H 2.2^2 (xlut.c JCCWEIGHT, CCCWEIGHT,
# HCCWEIGHT). Argyll's CIECAM02 adds a Helmholtz-Kohlrausch lift to J
# (xicc/cam02.c HHKR_MUL 0.25, HKLIMIT 0.7; XICC_USE_HK 1). Measured on
# Knut's laser (agent51 clipmetric51.py): that metric reproduces colprof's
# colour-to-black ramps within a few L* / C*, and ours (CIELAB, J 4 /
# C 0.35 / H 8) reproduces int-6's: the difference is the metric.
A51_TOKEN = "a51-colprofedge"
A51_BAND_TOKEN = "a51-colprofedge-band"
A51_NOHK_TOKEN = "a51-colprofedge-nohk"
A51_OWNHUE_TOKEN = "a51-colprofedge-ownhue"
A51_NOFLOOR_TOKEN = "a51-colprofedge-nofloor"
A51_LAB_TOKEN = "a51-colprofedge-lab"
A51_SOFT_TOKEN = "a51-colprofedge-soft"
# a51b: a target darker than the table's black is lifted to the black's L*
# (a29 floor) with its chroma scaled by L*target / L*black, i.e. moved along
# its own ray toward the black instead of straight up. With colprof's
# chroma-keeping metric the plain lift made every colour below the black
# print at the black's lightness with its full chroma: lighter than the
# colours just above it ("darker then lighter", Basti RESUME s57). Only
# nodes below the black move (no printable colour lies there), the map is
# continuous at the black and monotone toward it.
A51B_TOKEN = "a51b-colprofedge"
# Agent 56 (D-30 part 1): with a51 on (RGB), a target lifted to the a29 floor
# keeps its hue but its chroma fades with its depth below the black, so a
# colour approaches the black with a smooth (C1) monotone fade instead of
# holding its chroma to the black (int-7, Knut blue / azure) or snapping onto
# it a few steps early (no floor, Agent 55). The fade rate per hue is
# colprof's own: the cone ratio at which Argyll's clip metric, on a target
# below the black, lands on the black (blackfade_alpha). See blackfade_k.
A56_TOKEN = "a56-blackfade"
A51_PARAMS = {"space": "cam02", "wj": 4.0, "wc": 1.0, "wh": 4.84}
# Agent 62 (a62-camhue): a target lifted to the floor keeps the CIECAM02 hue
# of the target it was lifted from (camhue_lift). Lifting at constant a*, b*
# turns a dark blue's CAM hue toward violet by up to 10 deg (Lab hue lines
# are not constant-hue in the dark blue), and the clip then adds red: a
# violet patch near the black on the blue ramps (Findings agent62-01).
A62_TOKEN = "a62-camhue"
# Agent 65 (a65-cmykhue): ink devices keep the engine's own colorimetric clip
# (a51's metric there made contours: X3 4 -> 142) but its hue frame follows
# Argyll's CIECAM02 constant-hue lines, colprof's clip hue, instead of
# Oklab's: Oklab's blue hue lines bend toward purple (out-of-gamut blues
# +2..+3 IPT deg on every CMYK set, colprof -0.3..-0.9; Findings agent65-01).
# "-ipt" uses IPT hue lines instead; "-pass2" re-aims the frame once at the
# chroma the clip reached (the hue line is curved).
A65_TOKEN = "a65-cmykhue"
A65_IPT_TOKEN = "a65-cmykhue-ipt"
A65_PASS2_TOKEN = "a65-cmykhue-pass2"
# the engine's weights with the whole metric in Argyll CIECAM02 Jab (hue =
# colprof's) or in IPT, instead of CIELAB with an Oklab hue frame
A65_JAB_TOKEN = "a65-cmykhue-jab"
A65_IPTSPACE_TOKEN = "a65-cmykhue-iptspace"
# a65-cmykhue-jabdark: the Jab clip handed over to the engine's own clip near
# the black: weight of the own clip 1 up to A65_DARK[0] L* above the floor,
# smoothstep to 0 over A65_DARK[1] L* above that
A65_JABDARK_TOKEN = "a65-cmykhue-jabdark"
A65_DARK = (10.0, 10.0)
# a65-cmykhue-bluejab: the Jab clip only for targets of CIECAM02 hue in the
# blue window: weight 0 below 200 deg, smoothstep to 1 at 250, 1 to 290,
# smoothstep to 0 at 340 (pure sRGB blue 259, violet 283, azure 248; chain 7: the gentler window; 220-240-300-320 was the first try)
A65_BLUE_TOKEN = "a65-cmykhue-bluejab"
A65_BLUEDARK_TOKEN = "a65-cmykhue-bluejabdark"
A65_BLUE = (200.0, 250.0, 290.0, 340.0)
_HK = {"on": True}
_REL = threading.local()


def set_colorimetric(flag: bool) -> None:
    """The builder marks the thread that builds the colorimetric table:
    the a51 metric acts there only (perceptual / saturation unchanged)."""
    _REL.on = bool(flag)


def table_params(p: dict = None) -> dict:
    """PARAMS with the a51 overrides when the a51 token is on and this
    thread builds the colorimetric table; otherwise PARAMS itself."""
    p = PARAMS if p is None else p
    if (p.get("a65") and not p.get("a51")
            and getattr(_REL, "on", False)):
        # Agent 65 (a65-cmykhue): the ink devices' colorimetric clip keeps
        # the engine's metric (weights, band, ink priors) but measures hue
        # along colprof's CIECAM02 hue lines (Findings agent65-01)
        q = dict(p)
        mode = str(p["a65"])
        if mode.startswith("space-"):
            # the whole metric (same weights) measured in that space, the
            # hue frame its own hue (no Oklab hue line)
            q["space"] = mode[len("space-"):]
            q["hue_from"] = ""
        else:
            q["hue_from"] = mode
        if p.get("a65_pass2"):
            q["pass2"] = True
        return q
    if not p.get("a51") or not getattr(_REL, "on", False):
        return p
    q = dict(p)
    q.update(A51_PARAMS)
    if p.get("a51_ownhue"):
        q["hue_from"] = ""
    if p.get("a51_band"):
        q["blend_hi"] = float(p["a51_band"])
    if p.get("a51_lab"):
        q["space"] = "lab"
    if p.get("a51_soft"):
        # the dark floor as a smooth map (a29's -bpc band) instead of the
        # hard max(L*, black): targets below the black keep their order
        q["dm_band"], q["dm_wj"] = float(p["a51_soft"]), 1.0
    if p.get("a51_nofloor"):
        q["dm_off"] = True
    if p.get("a51_ray"):
        q["dm_ray"] = True
    if p.get("a56"):
        q["a56_on"] = True
    if p.get("a62"):
        q["a62_on"] = True
    return q


def camhue_lift(t_lab: np.ndarray, orig_lab: np.ndarray,
                lift: np.ndarray, iters: int = 8) -> np.ndarray:
    """Agent 62 (a62-camhue): ``t_lab`` (targets already lifted, and faded)
    turned about the L* axis, at their own L* and C*, so that their Argyll
    CIECAM02 hue is the hue of ``orig_lab`` (the targets before the lift).
    Rows with no lift are returned unchanged; the turn is solved per row by
    secant steps on the hue angle (it is monotone and close to 1:1). A
    neutral original has no hue to keep: the turn fades in over the hue
    weight's own chroma fade (PARAMS c_fade, in the space's chroma)."""
    t_lab = np.asarray(t_lab, float)
    out = t_lab.copy()
    m = np.flatnonzero(np.asarray(lift) > 0)
    if not len(m):
        return out

    def hue(lab):
        j = lab_to_argyll_jab(lab)
        return np.arctan2(j[:, 2], j[:, 1]), np.hypot(j[:, 1], j[:, 2])

    goal, oc = hue(np.asarray(orig_lab, float)[m])
    base = t_lab[m]
    c = np.hypot(base[:, 1], base[:, 2])
    h0 = np.arctan2(base[:, 2], base[:, 1])

    def at(th):
        x = base.copy()
        x[:, 1] = c * np.cos(h0 + th)
        x[:, 2] = c * np.sin(h0 + th)
        return x

    def err(th):
        e = hue(at(th))[0] - goal
        return (e + np.pi) % (2.0 * np.pi) - np.pi

    th = np.zeros(len(m))
    e = err(th)
    for _ in range(iters):
        d = 1e-3
        de = (err(th + d) - e) / d
        de = np.where(np.abs(de) < 0.2, 1.0, de)
        th = np.clip(th - e / de, -np.radians(45.0), np.radians(45.0))
        e = err(th)
    s = np.clip(oc / max(float(PARAMS["c_fade"]), 1e-9), 0.0, 1.0)
    s = s * s * (3.0 - 2.0 * s)
    out[m] = at(th * s)
    return out


def blackfade_k(c, depth, alpha, r: float = 2.0,
                shape: str = "rat") -> np.ndarray:
    """Agent 56: chroma factor for a target lifted ``depth`` L* to the floor.

    With r = alpha * depth / c, colprof's clip (no floor, Argyll's metric,
    near the black's apex) gives the lifted target's effective chroma
    c - alpha * depth, which hits zero (the clip snaps onto the black) at
    r = 1 with a corner. k = (1 - r / R)^R has the same first order at the
    floor (k = 1 - r + ...), reaches zero at r = R with zero slope, and is
    monotone: the faded chroma k * c is C1 in depth and in c. shape "rat"
    is the long-tailed k = (1 + r / R)^-R (same first order, never zero).
    depth <= 0 or c <= 0 gives 1 (nothing to fade)."""
    c = np.asarray(c, float)
    depth = np.asarray(depth, float)
    alpha = np.broadcast_to(np.asarray(alpha, float), c.shape)
    r_ = max(float(r), 1.0)
    ok = (c > 1e-9) & (depth > 0.0)
    ratio = np.where(ok, alpha * np.maximum(depth, 0.0)
                     / np.where(ok, c, 1.0), 0.0)
    if shape == "rat":
        return np.where(ok, (1.0 + ratio / r_) ** -r_, 1.0)
    return np.where(ok, np.clip(1.0 - ratio / r_, 0.0, 1.0) ** r_, 1.0)


def _blackfade_cloud(n: int) -> np.ndarray:
    g = np.linspace(0.0, 1.0, 41)
    g2 = np.linspace(0.0, 0.35, 36)
    a = np.stack(np.meshgrid(*([g] * n), indexing="ij"), -1).reshape(-1, n)
    b = np.stack(np.meshgrid(*([g2] * n), indexing="ij"), -1).reshape(-1, n)
    return np.unique(np.vstack([a, b]), axis=0)


def smooth_hue_ratio(al: np.ndarray, sigma_deg: float) -> np.ndarray:
    """Circular Gaussian smoothing (sigma in degrees) of a positive per-hue
    ratio, in log space (a ratio, so a factor counts the same both ways)."""
    al = np.asarray(al, float)
    if sigma_deg <= 0.0 or not (al > 0).all():
        return al
    n = len(al)
    step = 360.0 / n
    off = np.arange(n)
    off = np.minimum(off, n - off) * step
    ker = np.exp(-0.5 * (off / sigma_deg) ** 2)
    ker /= ker.sum()
    la = np.log(al)
    sm = np.real(np.fft.ifft(np.fft.fft(la) * np.fft.fft(ker)))
    return np.exp(sm)


def blackfade_alpha(model, floor: float, p: dict, fn, n_hues: int = 72,
                    snap: float = 0.3, iters: int = 18) -> np.ndarray:
    """Agent 56: per hue (n_hues CIELAB hues from 0 deg), the cone ratio
    C* / depth below which a target ``d0`` L* under the black (no floor) is
    clipped onto the black by this table's metric ``p`` in space ``fn``:
    bisection on the target's chroma, "on the black" meaning the clip's L*
    is within ``snap`` of the clip of the neutral target at the same depth.
    Argyll's own geometry near the black (colprof's convergence), smoothed
    over hue (``a56_hsmooth`` degrees, smooth_hue_ratio); RGB devices
    (3 channels) only, memoised on the model per floor."""
    key = ("a56", round(float(floor), 6), n_hues, p.get("space"),
           p.get("wj"), p.get("wc"), p.get("wh"), p.get("hue_from"),
           float(p.get("a56_hsmooth", 20.0)))
    memo = getattr(model, "_a56_alpha", None)
    if memo is None:
        memo = {}
        try:
            model._a56_alpha = memo
        except AttributeError:
            pass
    if key in memo:
        return memo[key]
    out = np.zeros(n_hues)
    if model.n_channels == 3 and floor > 0.5:
        cloud = _blackfade_cloud(3)
        c_lab = model.predict(cloud)
        cloud_s = fn(c_lab)
        d0 = min(3.0, floor / 2.0)
        h = np.radians(np.arange(n_hues) * 360.0 / n_hues)
        hue_from = p.get("hue_from") or ""

        def clip_l(c):
            t = np.stack([np.full(n_hues, floor - d0), c * np.cos(h),
                          c * np.sin(h)], 1)
            t_s = fn(t)
            w = weights(t_s, p, _frame_angle(t, t_s, fn, hue_from, p["chord"])
                        if hue_from else None)
            return model.predict(best_cloud_seed(t_s, w, cloud, cloud_s))[:, 0]

        l_ref = clip_l(np.zeros(n_hues))
        lo = np.zeros(n_hues)
        hi = np.full(n_hues, 200.0)
        for _ in range(iters):
            mid = 0.5 * (lo + hi)
            on_black = clip_l(mid) - l_ref < snap
            lo = np.where(on_black, mid, lo)
            hi = np.where(on_black, hi, mid)
        # the fade rate may change with hue only as fast as the hue map can
        # follow without contours: smoothed over +-sigma degrees
        out = smooth_hue_ratio(hi / d0, float(p.get("a56_hsmooth", 20.0)))
    memo[key] = out
    return out


def blackfade_targets(model, t_lab: np.ndarray, lift: np.ndarray,
                      floor: float, p: dict, fn) -> np.ndarray:
    """Agent 56: ``t_lab`` (already lifted to the floor) with the chroma of
    every lifted row scaled by blackfade_k at its hue's cone ratio."""
    al = blackfade_alpha(model, floor, p, fn)
    knots = np.arange(len(al)) * 360.0 / len(al)
    hue = np.degrees(np.arctan2(t_lab[:, 2], t_lab[:, 1])) % 360.0
    a_t = np.interp(hue, knots, al, period=360.0)
    c = np.hypot(t_lab[:, 1], t_lab[:, 2])
    k = blackfade_k(c, lift, a_t, float(p.get("a56_r", 2.0)),
                    str(p.get("a56_shape", "rat")))
    out = t_lab.copy()
    out[:, 1:] *= k[:, None]
    return out


def lab_to_argyll_jab(lab: np.ndarray) -> np.ndarray:
    """CIECAM02 Jab exactly as Argyll computes it (argyll_cam02, a port of
    xicc/cam02.c checked against ``xicclu -pj``: median 0.08, max 0.2 Jab
    over 390 colours of a colprof profile), for D50-relative Lab, under
    the viewing conditions xicclu and colprof default to for a print
    (La 40 cd/m^2, Yb 20 %, average surround, 1 % flare)."""
    from workflow.profile_engine.argyll_cam02 import lab_to_jab
    return lab_to_jab(lab, La=40.0, Yb=0.2, Yf=0.01, Yg=0.0, hk=bool(_HK["on"]))


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
    lt = np.clip((target_s[:, 0] - p["light_from"])
                 / max(100.0 - p["light_from"], 1e-9), 0.0, 1.0)
    lt = lt * lt * (3.0 - 2.0 * lt)
    wj = p["wj"] * (1.0 + (p["wj_light"] - 1.0) * lt)
    wc = p["wc"] * np.ones(n)
    wh = p["wc"] + (p["wh"] - p["wc"]) * s
    if p.get("neutral_fade"):
        # a neutral target is clipped to the nearest colour, as integration 2
        # did below C* 5: a lightness-keeping metric would accept a tint on
        # the grey axis (battery S2 neutral highlight +0.17-0.34 dE00)
        wj = 1.0 + (wj - 1.0) * s
        wc = 1.0 + (wc - 1.0) * s
        wh = 1.0 + (wh - 1.0) * s
    sj, sc, shh = np.sqrt(wj), np.sqrt(wc), np.sqrt(wh)
    if p.get("de00"):
        from workflow.profile_engine.metrics import de00_scale_factors
        s_l, s_c, s_h = de00_scale_factors(target_s)
        sj = sj / s_l
        sc = sc / s_c
        # hue tolerance faded in with the hue weight (S_H -> S_C at C = 0)
        shh = shh / (s_c + (s_h - s_c) * s)
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


def _lattice_neighbours(target_lab: np.ndarray):
    """(N, 6) indices of the +-1 neighbours along each axis when the targets
    are a full C-order lattice (the B2A node grid), -1 at the borders; None
    for any other target set (mapped targets, samples)."""
    axes = [np.unique(target_lab[:, c]) for c in range(3)]
    shape = tuple(len(a) for a in axes)
    n = len(target_lab)
    if int(np.prod(shape)) != n:
        return None
    grid = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
    if not np.array_equal(grid, target_lab):
        return None
    idx = np.arange(n).reshape(shape)
    out = np.full((n, 6), -1)
    col = 0
    for ax in range(3):
        for step in (-1, 1):
            sh = np.full(shape, -1)
            src = [slice(None)] * 3
            dst = [slice(None)] * 3
            if step == 1:
                dst[ax] = slice(0, shape[ax] - 1)
                src[ax] = slice(1, shape[ax])
            else:
                dst[ax] = slice(1, shape[ax])
                src[ax] = slice(0, shape[ax] - 1)
            sh[tuple(dst)] = idx[tuple(src)]
            out[:, col] = sh.reshape(-1)
            col += 1
    return out


def _descend(b2a, view, t_s, d0, w, *, free, iters, damping, limit, prior,
             prior_w, gn_kw, label):
    """Weighted Gauss-Newton that never accepts a step raising the weighted
    colour cost (backtracking by halving; the box and the ink limit are
    convex, so every halved step stays printable). Plain GN overshoots on
    targets 30-80 dE outside the gamut and lands on arbitrary cube corners
    (measured on Knut's RGB printer: red (51, 76, 66) -> (98, -3, 26))."""
    d = d0.copy()
    c = cost(view.predict(d), t_s, w)
    for it in range(iters):
        d_try = b2a._gauss_newton(view, t_s, d.copy(), free, iters=1,
                                  damping=damping, ink_limit=limit,
                                  err_weights=w, prior=prior, prior_w=prior_w,
                                  progress_label=f"{label} {it + 1}/{iters}"
                                  if it == 0 else "", **gn_kw)
        step = d_try - d
        acc = np.zeros(len(d), bool)
        for k in range(5):
            cand = d + step * (0.5 ** k)
            cc = cost(view.predict(cand), t_s, w)
            good = (cc < c) & ~acc
            d[good] = cand[good]
            c[good] = cc[good]
            acc |= good
            if acc.all():
                break
        if not acc.any():
            break
    return d, c


def clip_nodes(model, target_lab, d_near, residual, *, free, limit,
               channel_max, prior, prior_w, gn_kw, damping, hue_seeds=None,
               progress_label="", _params=None) -> np.ndarray:
    """New device values for every node with residual > blend_lo.

    ``d_near``: the nearest-clip answer (first pass + retry) for ALL nodes;
    returns a full copy with the clipped rows replaced."""
    from workflow.profile_engine import b2a
    p = table_params() if _params is None else _params
    if _params is None and p.get("a65") and (p.get("a65_dark") or p.get("a65_blue")):
        # Agent 65 (a65-cmykhue-jabdark / -bluejab / -bluejabdark): the Jab
        # clip only where it is needed, the engine's own clip (CIELAB, Oklab
        # frame: int-8b's answer) elsewhere, blended in device space with
        # smooth weights: near the black (dark: 1 up to A65_DARK[0] L* above
        # the floor, smoothstep to 0 over A65_DARK[1]) and outside the blue
        # CIECAM02 hue window (A65_BLUE, faded in with the target's chroma).
        # Measured: the Jab metric everywhere made the CMYK colour-to-black
        # ramps less even and cost cyan / red ramps (eyecheck FOGRA, SWOP).
        tl = np.asarray(target_lab, float)
        u = np.zeros(len(tl))
        if p.get("a65_dark"):
            fl = dark_floor()
            if fl is not None:
                cl, cw = A65_DARK
                v = np.clip((fl + cl + cw - tl[:, 0]) / cw, 0.0, 1.0)
                u = np.maximum(u, v * v * (3.0 - 2.0 * v))
        if p.get("a65_blue"):
            j = lab_to_argyll_jab(tl)
            h = np.degrees(np.arctan2(j[:, 2], j[:, 1])) % 360.0
            import os
            lo0, lo1, hi1, hi0 = (tuple(float(x) for x in os.environ["CHROMIQ_A65_BLUE"].split(":"))
                                  if os.environ.get("CHROMIQ_A65_BLUE") else A65_BLUE)
            win = np.clip(np.minimum((h - lo0) / (lo1 - lo0), (hi0 - h) / (hi0 - hi1)), 0.0, 1.0)
            win = win * win * (3.0 - 2.0 * win)
            cs = np.clip(np.hypot(j[:, 1], j[:, 2]) / max(float(p["c_fade"]), 1e-9), 0.0, 1.0)
            win = win * cs * cs * (3.0 - 2.0 * cs)
            u = np.maximum(u, 1.0 - win)
        kw = dict(free=free, limit=limit, channel_max=channel_max,
                  prior=prior, prior_w=prior_w, gn_kw=gn_kw,
                  damping=damping, hue_seeds=hue_seeds,
                  progress_label=progress_label)
        d_lo = clip_nodes(model, target_lab, d_near, residual, _params=PARAMS, **kw)
        if (u >= 1.0).all():
            return d_lo
        hi = dict(p)
        hi["a65_dark"] = hi["a65_blue"] = False
        d_hi = clip_nodes(model, target_lab, d_near, residual, _params=hi, **kw)
        out = (1.0 - u[:, None]) * d_hi + u[:, None] * d_lo
        if limit is not None:
            over = out.sum(1) > limit
            if over.any():
                out[over] = b2a.project_tac(out[over], limit)
        return out
    out = d_near.copy()
    sel = np.flatnonzero(residual > p["blend_lo"])
    if not len(sel):
        return out
    fn = space_fn(p["space"])
    view = SpaceView(model, fn)
    t_lab = target_lab[sel]
    lift = None
    floor = None if p.get("dm_off") else dark_floor()
    if floor is not None:
        # Agent 29b: below the table's black the clip aims at the black's
        # L* (with the target's own a*, b*), so lightness along a ramp into
        # black is monotone; apply_neutral_axis does the same for C* < 5.
        new_l = dark_target_l(t_lab[:, 0], floor, float(p.get("dm_band", 0.0)))
        lift = new_l - t_lab[:, 0]
        if (lift > 0).any():
            t_lab = t_lab.copy()
            if p.get("dm_ray"):
                k = np.clip(t_lab[:, 0] / np.maximum(new_l, 1e-9), 0.0, 1.0)
                t_lab[:, 1:] *= k[:, None]
            t_lab[:, 0] = new_l
            if p.get("a56_on"):
                # Agent 56: the lifted chroma fades with the depth
                t_lab = blackfade_targets(model, t_lab, lift, floor, p, fn)
            if p.get("a62_on"):
                # Agent 62: the lifted target keeps its own CAM hue
                t_lab = camhue_lift(t_lab, target_lab[sel], lift)
        else:
            lift = None
    t_s = fn(t_lab)
    hue_from = p.get("hue_from") or ""
    w = weights(t_s, p, _frame_angle(t_lab, t_s, fn, hue_from, p["chord"])
                if hue_from else None)
    if floor is not None and float(p.get("dm_wj", 1.0)) != 1.0:
        lb = max(float(p.get("dm_lband", 10.0)), 1e-9)
        u = np.clip((floor + lb - target_lab[sel][:, 0]) / lb, 0.0, 1.0)
        u = u * u * (3.0 - 2.0 * u)
        mult = 1.0 + (float(p["dm_wj"]) - 1.0) * u
        if (mult > 1.0).any():
            w = w.copy()
            w[:, 0, :] *= np.sqrt(mult)[:, None]
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
    pr_clip, pw_clip = (None, None) if p.get("two_stage") else (pr, pw)
    best = None
    best_cost = None
    for k, s0 in enumerate(starts):
        if p.get("descent", True):
            d, cst = _descend(b2a, view, t_s, s0, w, free=free,
                              iters=p["iters"], damping=damping, limit=limit,
                              prior=pr_clip, prior_w=pw_clip, gn_kw=gn_kw,
                              label=f"{progress_label}: weighted clip "
                                    f"{k + 1}/{len(starts)}")
        else:
            d = b2a._gauss_newton(view, t_s, s0.copy(), free, iters=p["iters"],
                                  damping=damping, ink_limit=limit, err_weights=w,
                                  prior=pr_clip, prior_w=pw_clip,
                                  progress_label=f"{progress_label}: weighted clip "
                                                 f"{k + 1}/{len(starts)}", **gn_kw)
            cst = cost(view.predict(d), t_s, w)
        if best is None:
            best, best_cost = d, cst
        else:
            better = cst < best_cost
            best[better] = d[better]
            best_cost[better] = cst[better]
    rounds = int(p.get("propagate", 0))
    nb = _lattice_neighbours(target_lab) if rounds else None
    if nb is not None:
        # Neighbour propagation (PatchMatch-like): a node whose lattice
        # neighbour found a cheaper basin starts again from that answer.
        # Every decision is still "lower cost wins", so it only removes
        # places where the search missed the minimum; it makes the field
        # agree with itself where two basins compete (Findings s4.3).
        pos = np.full(len(target_lab), -1)
        pos[sel] = np.arange(len(sel))
        for r in range(rounds):
            cand_best = best.copy()
            cand_cost = best_cost.copy()
            for col in range(nb.shape[1]):
                j = nb[sel, col]
                okj = j >= 0
                okj[okj] = pos[j[okj]] >= 0
                if not okj.any():
                    continue
                rows = np.flatnonzero(okj)
                src = best[pos[j[okj]]]
                c = cost(view.predict(src), t_s[rows], w[rows])
                better = c < cand_cost[rows]
                cand_best[rows[better]] = src[better]
                cand_cost[rows[better]] = c[better]
            moved = np.flatnonzero(cand_cost < best_cost - 1e-9)
            if not len(moved):
                break
            d, c = _descend(
                b2a, view, t_s[moved], cand_best[moved], w[moved], free=free,
                iters=p["iters"], damping=damping, limit=limit,
                prior=None if pr_clip is None else pr_clip[moved],
                prior_w=None if pw_clip is None else pw_clip[moved],
                gn_kw=gn_kw, label=f"{progress_label}: weighted clip, "
                                   f"neighbours {r + 1}")
            use = c < cand_cost[moved]
            cand_best[moved[use]] = d[use]
            cand_cost[moved[use]] = c[use]
            best, best_cost = cand_best, cand_cost
    if hue_from and p.get("pass2"):
        # Re-aim the hue frame at the chroma the first pass reached (the
        # constant-hue line is curved; the chord to the answer is its
        # direction there), then polish once more from the answer.
        got = model.predict(best)
        fwd, _ = _pair(hue_from)
        cs_t = np.hypot(*fwd(t_lab)[:, 1:].T)
        cs_g = np.hypot(*fwd(got)[:, 1:].T)
        k = np.clip(cs_g / np.maximum(cs_t, 1e-9), 0.05, 1.0)
        w = weights(t_s, p, _frame_angle(t_lab, t_s, fn, hue_from, k))
        d = b2a._gauss_newton(view, t_s, best.copy(), free, iters=p["iters"],
                              damping=damping, ink_limit=limit, err_weights=w,
                              prior=pr, prior_w=pw,
                              progress_label=f"{progress_label}: weighted clip "
                                             f"(re-aimed)", **gn_kw)
        best = d
    if p.get("two_stage") and pr is not None:
        # Stage 2: the chosen colour is printable; separate it under the ink
        # policy (an in-gamut inversion, residual ~0), seeded at stage 1.
        y = model.predict(best)
        d2 = b2a._gauss_newton(model, y, best.copy(), free, iters=p["iters"],
                               damping=damping, ink_limit=limit, prior=pr,
                               prior_w=pw, progress_label=f"{progress_label}: "
                               "separating the clipped colours", **gn_kw)
        e1 = np.linalg.norm(model.predict(d2) - y, axis=1)
        ok = e1 < 0.5
        best[ok] = d2[ok]
    # Continuous hand-over to the nearest clip near the surface.
    lo, hi = p["blend_lo"], p["blend_hi"]
    if p.get("blend_light"):
        # Near paper white the B2A cells mix in-gamut and clipped nodes for
        # every pale colour; there the clip hands over to the nearest clip
        # over a wider band (in-gamut pale accuracy, battery X1 pale p95).
        u = np.clip((t_lab[:, 0] - p["blend_light_from"])
                    / max(100.0 - p["blend_light_from"], 1e-9), 0.0, 1.0)
        hi = hi + p["blend_light"] * u * u * (3.0 - 2.0 * u)
    bf = np.clip((residual[sel] - lo) / (hi - lo), 0.0, 1.0)
    bf = bf * bf * (3.0 - 2.0 * bf)
    if lift is not None:
        # the nearest clip aims at the darker original target: a lifted node
        # takes the weighted clip of the lifted target instead
        u = np.clip(lift / max(float(p.get("dm_blend", 1.0)), 1e-9), 0.0, 1.0)
        bf = np.maximum(bf, u * u * (3.0 - 2.0 * u))
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
