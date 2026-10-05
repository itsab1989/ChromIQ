"""Battery v3.1 referee (Agent 16b, 2026-10-05): what battery v3 did not see.

Battery v3 read the colorimetric tables only and only IN gamut, never ran
``gmq`` and left FOGRA55 / APTEC out (Findings/agent23-01, F-13..F-20). This
module turns Agent 23's blind-spot tests into SCORED headline numbers, one
dict per profile, every number "lower is better" after the sign in ``KEYS``.

The measurement code is NOT copied: every number comes from
``benchmarks.research.blindspots.hunt`` / ``xf`` (Agent 23, d17aa9c7; the
same files Agent 25 uses on research/pe-oog) and from ``gmq`` (Agent 9) and
``ncq`` / ``ncpoints`` (Agent 14). This file only chooses which of their
outputs become endpoints, and adds two small probes the hunt does not have
as a single number (the neutral Lab ramp below the device black, F-13; the
grey shadows, F-19).

    evaluate(profile, printer, reader="lcms") -> {"q": {key: value}, ...}

``printer`` is anything with ``n``, ``is_additive``, ``tac``, ``letters``,
``lab_rel(device)`` and (optionally) ``xyz(device)``: a synthetic printer of
``printers.py``, a sealed Z printer (``zfamily.ZTruth``, the generator
interface only), or ``TruthAdapter`` around a real set's labelled proxy.

Reader: lcms2 float without optimisation for the table reads (Agent 23
measured lcms and Argyll identical on every F-15..F-20 number), plus the
8-bit application path where the hunt has one (grey ramp, image). ColorSync
confirmations stay in the hunt (one call per colour; too slow for a battery).
"""
from __future__ import annotations

import numpy as np

from benchmarks.research import colour, gmq
from benchmarks.research.blindspots import hunt, xf

# key -> (sign, absolute floor of the minimum effect, safety, finding, what)
# sign +1: larger is worse; -1: larger is better. Floors are in the unit of
# the number (counts: 1; L*, C*, dE: 0.1; hue degrees: 0.5; shares: 0.005).
KEYS: dict[str, tuple[int, float, bool, str, str]] = {
    # F-15: relative colorimetric out-of-gamut handling (every device class)
    "oog_ramp_rev_r": (1, 1, True, "F-15", "L* reversal steps, 24 sRGB/Adobe RGB primary ramps to white and black, rel. col."),
    "oog_ramp_swing_r": (1, 0.1, False, "F-15", "largest L* swing on those ramps"),
    "oog_ramp_jump_r": (1, 0.5, False, "F-15", "largest step / median step on those ramps"),
    "oog_ramp_d2_r": (1, 0.1, False, "F-15", "largest printed 2nd difference minus the source's"),
    "image_contours_r": (1, 1, True, "F-15", "new contour edges, synthetic sRGB image, rel. col. float"),
    "image_contours_p_app8": (1, 1, True, "F-16", "new contour edges, synthetic image, perceptual, 8-bit application path"),
    "pale_oog_dL_max_r": (1, 0.1, False, "F-15", "pale sRGB (200-255 cube): largest printed L* drop, rel. col."),
    "pale_oog_dL_p99_r": (1, 0.1, False, "F-15", "pale sRGB: p99 L* drop, rel. col."),
    "pale_oog_share5_r": (1, 0.005, False, "F-15", "pale sRGB: share printed > 5 L* darker, rel. col."),
    "pale_oog_dL_max_p": (1, 0.1, False, "F-14", "pale sRGB: largest L* drop, perceptual"),
    "pale_oog_dL_max_s": (1, 0.1, False, "F-14", "pale sRGB: largest L* drop, saturation"),
    "abs_white_de": (1, 0.1, False, "F-15", "absolute intent: D50 white printed vs bare paper, dE00"),
    # F-17: hue of the colorimetric clip in a hue-linear space
    "blue_ipt_abs_r": (1, 0.5, False, "F-17", "sRGB blue (0,0,255) printed IPT hue error, rel. col., degrees"),
    "oog_ipt_hue_p95_r": (1, 0.5, False, "F-17", "out-of-gamut sRGB cube surface: p95 IPT hue error"),
    "oog_blue_ipt_abs_r": (1, 0.5, False, "F-17", "same, blue sector: |mean signed IPT hue error|"),
    # F-16: perceptual / saturation colour ramps
    "ramp_rev_p": (1, 1, True, "F-16", "L* reversal steps, 24 primary ramps, perceptual"),
    "ramp_rev_s": (1, 1, True, "F-16", "L* reversal steps, 24 primary ramps, saturation"),
    "ramp_swing_p": (1, 0.1, False, "F-16", "largest L* swing, perceptual ramps"),
    "ramp_swing_s": (1, 0.1, False, "F-16", "largest L* swing, saturation ramps"),
    "red_ramp_rev_ps": (1, 1, False, "F-16", "reversal steps on the red ramps, p + s"),
    "dark_ramp_rev_ps": (1, 1, False, "F-16", "reversal steps on the colour-to-black ramps, p + s"),
    # F-18 / F-19 / F-13: the grey ramp through every intent
    "grey_swing_p": (1, 0.1, True, "F-18", "sRGB grey 0-255: largest L* swing, perceptual"),
    "grey_swing_s": (1, 0.1, True, "F-18", "same, saturation"),
    "grey_swing_r": (1, 0.1, True, "F-13", "same, relative colorimetric (whole ramp, below the black too)"),
    "grey_swing_rbpc": (1, 0.1, False, "F-18", "same, rel. col. + BPC (Photoshop's default)"),
    "grey_swing_p_app8": (1, 0.1, False, "F-18", "same, perceptual, 8-bit application path"),
    "grey_chroma_max_p": (1, 0.2, False, "F-18", "grey ramp: largest printed C*, perceptual"),
    "grey_chroma_max_s": (1, 0.2, False, "F-18", "grey ramp: largest printed C*, saturation"),
    "grey_shadow_swing_p": (1, 0.1, False, "F-19", "grey codes 0-64: largest L* swing, perceptual"),
    "grey_shadow_swing_s": (1, 0.1, False, "F-19", "grey codes 0-64: largest L* swing, saturation"),
    "below_black_swing_r": (1, 0.1, True, "F-13", "neutral Lab ramp L* 0-25 through B2A1: largest L* swing"),
    "below_black_rev_r": (1, 1, False, "F-13", "same ramp: L* reversal steps"),
    # F-05 / F-20: the perceptual and saturation black
    "black_gap_p": (1, 0.5, True, "F-05/F-20", "printed black L* (perceptual) minus printed black L* (rel. col.)"),
    "black_gap_s": (1, 0.5, True, "F-05/F-20", "same, saturation"),
    "black_C_p": (1, 0.5, True, "F-05/F-20", "printed chroma of the perceptual black"),
    "black_C_s": (1, 0.5, True, "F-05/F-20", "printed chroma of the saturation black"),
}
# gmq (Agent 9, M1-M11) per intent: the scored subset (direction known)
GMQ_KEYS = {"M1_neutral_C_mean": (1, 0.1), "M1_neutral_C_max": (1, 0.2),
            "M3_L_reversals": (1, 1), "M3c_C_reversals": (1, 1), "M4_d2_max": (1, 0.1),
            "M5_core_de_median": (1, 0.05), "M7_core_p05": (-1, 0.02),
            "M8_black_gap": (1, 0.5), "M9_over_share": (1, 0.005),
            "M10_sep_d2_max": (1, 0.01), "M11_rt_median": (1, 0.05), "M11_rt_p95": (1, 0.1)}
for _i in ("p", "s"):
    for _k, (_sg, _fl) in GMQ_KEYS.items():
        KEYS[f"gmq_{_i}_{_k}"] = (_sg, _fl, False, "gmq", f"Agent 9 {_k}, intent {_i}")


# Absolute limits for rows with NO comparator (5-7 inks: colprof cannot build
# them, D-21 drops Fast): what the F-files propose, PROPOSED (not confirmed by
# anyone), read on a single build. A row above its limit is reported as
# "above the absolute limit", never as a pass.
ABSOLUTE = {"grey_swing_p": 0.5, "grey_swing_s": 0.5, "grey_swing_r": 0.5,
            "below_black_swing_r": 0.5, "grey_shadow_swing_p": 0.5, "grey_shadow_swing_s": 0.5,
            "black_gap_p": 3.0, "black_gap_s": 3.0, "black_C_p": 3.0, "black_C_s": 3.0,
            "grey_chroma_max_p": 3.0, "grey_chroma_max_s": 3.0,
            "pale_oog_dL_max_r": 5.0, "pale_oog_dL_max_p": 5.0, "pale_oog_dL_max_s": 5.0,
            "blue_ipt_abs_r": 5.0, "abs_white_de": 0.5,
            # the CMYK colprof level on the same tests (Agent 23 s4) as the yardstick
            "oog_ramp_rev_r": 30, "ramp_rev_p": 16, "ramp_rev_s": 16, "image_contours_r": 5}


def key_info(key: str) -> tuple[int, float, bool, str, str]:
    """(sign, floor, safety, finding, what) for a q-key; ncq headline keys
    (5+ inks) are scored with the floors of protocol v2.2 N4 elsewhere."""
    return KEYS[key]


class TruthAdapter:
    """A real set's labelled proxy as a printer object (gmq, ncq, hunt):
    device -> media-relative Lab through ``metrics.Truth``."""

    def __init__(self, truth, n: int, additive: bool, tac, letters, name: str):
        self._truth = truth
        self.n = n
        self.is_additive = additive
        self.tac = tac
        self._letters = list(letters)
        self.id = f"proxy-{name}"

    @property
    def letters(self):
        return self._letters

    def lab_rel(self, device, illuminant: str = "D50"):
        return self._truth.lab(np.clip(np.atleast_2d(np.asarray(device, float)), 0, 1))


def _ctx(profile, printer, cloud):
    xyz = getattr(printer, "xyz", None)
    return hunt.Ctx(str(profile), printer.lab_rel, printer.n, printer.is_additive,
                    printer.tac, truth_xyz=xyz, truth_cloud=cloud)


def _ramps(h2: dict, suffix: str, name: str | None = None, kind: str | None = None):
    out = []
    for k, v in h2.items():
        if not isinstance(v, dict) or not k.endswith("-" + suffix):
            continue
        sp, nm, kd, _ = k.split("-")
        if (name is None or nm == name) and (kind is None or kd == kind):
            out.append(v)
    return out


def below_black(ctx) -> dict:
    """F-13: the neutral Lab axis L* 0..25 (0.1 steps) through B2A1, printed
    on the truth: a monotone table is flat at the device black, then rises."""
    L = np.arange(0.0, 25.0001, 0.1)
    lab = np.stack([L, np.zeros_like(L), np.zeros_like(L)], 1)
    pr = ctx.truth_lab(ctx.lab2dev(lab, "r"))
    r = hunt.ramp_props(lab, pr)
    return {"swing": r["l_swing"], "rev": r["l_rev"]}


def grey_shadows(ctx, intent: str) -> float:
    """F-19: sRGB grey codes 0..64 through one intent; largest L* swing."""
    v = np.arange(65) / 255.0
    rgb = np.stack([v, v, v], 1)
    src = xf.srgb_to_lab(rgb)
    pr = ctx.truth_lab(ctx.rgb2dev("srgb", rgb, intent))
    return hunt.ramp_props(src, pr)["l_swing"]


def abs_white(ctx) -> float:
    """B2A3 of the D50 white (brighter than any paper) printed vs bare paper."""
    d = ctx.lab2dev(np.array([[100.0, 0.0, 0.0]]), "a")
    paper = np.full((1, ctx.n), 1.0 if ctx.additive else 0.0)
    return float(colour.de2000(ctx.truth_lab(d), ctx.truth_lab(paper))[0])


def evaluate(profile, printer, reader: str = "lcms", cloud=None, with_gmq: bool = True,
             with_ncq: bool = False, ncq_reader: str = "argyll") -> dict:
    """Every v3.1 property of one profile. Returns {"q": headline, "raw": the
    hunt outputs that produced it, "gmq": {...}, "ncq": {...}}; an error in
    one block is recorded and the rest still runs."""
    if reader != "lcms":
        raise ValueError("v3.1 property rows read through lcms float (see module doc)")
    cloud = gmq.truth_cloud(printer) if cloud is None else cloud
    ctx = _ctx(profile, printer, cloud)
    q: dict = {}
    raw: dict = {}
    errors: dict = {}

    def block(name, fn):
        try:
            raw[name] = fn()
        except Exception as exc:          # recorded, never a pass
            errors[name] = f"{type(exc).__name__}: {exc}"

    block("H1", lambda: hunt.h1_grey(ctx))
    block("H2", lambda: hunt.h2_colour_ramps(ctx))
    block("H5", lambda: hunt.h5_memory(ctx))
    block("H6", lambda: hunt.h6_image(ctx))
    block("H8", lambda: hunt.h8_extremes(ctx))
    block("H11", lambda: hunt.h11_pale(ctx))
    block("below_black", lambda: below_black(ctx))
    block("shadows", lambda: {i: grey_shadows(ctx, i) for i in ("p", "s")})
    block("abs_white", lambda: abs_white(ctx))
    h1, h2, h5, h6, h8, h11 = (raw.get(k, {}) for k in ("H1", "H2", "H5", "H6", "H8", "H11"))
    if h2:
        rr = _ramps(h2, "r")
        q["oog_ramp_rev_r"] = sum(v["l_rev"] for v in rr)
        q["oog_ramp_swing_r"] = max(v["l_swing"] for v in rr)
        q["oog_ramp_jump_r"] = max(v["jump_ratio"] for v in rr)
        q["oog_ramp_d2_r"] = max(v["d2_excess_max"] for v in rr)
        for i in ("p", "s"):
            ri = _ramps(h2, i)
            q[f"ramp_rev_{i}"] = sum(v["l_rev"] for v in ri)
            q[f"ramp_swing_{i}"] = max(v["l_swing"] for v in ri)
        q["red_ramp_rev_ps"] = sum(v["l_rev"] for i in ("p", "s") for v in _ramps(h2, i, name="R"))
        q["dark_ramp_rev_ps"] = sum(v["l_rev"] for i in ("p", "s") for v in _ramps(h2, i, kind="k"))
    if h6:
        for path, key in (("r", "image_contours_r"), ("p-app8", "image_contours_p_app8")):
            if path in h6:
                q[key] = sum(v.get("new_edges", 0) for v in h6[path].values())
    if h11:
        q["pale_oog_dL_max_r"] = h11["r"]["dL_max"]
        q["pale_oog_dL_p99_r"] = h11["r"]["dL_p99"]
        q["pale_oog_share5_r"] = h11["r"]["share_dL_over_5"]
        q["pale_oog_dL_max_p"] = h11["p"]["dL_max"]
        q["pale_oog_dL_max_s"] = h11["s"]["dL_max"]
    if "abs_white" in raw:
        q["abs_white_de"] = raw["abs_white"]
    if h5 and "sRGB_blue-r" in h5:
        q["blue_ipt_abs_r"] = abs(h5["sRGB_blue-r"]["ipt_hue_shift"])
    if h8 and "r" in h8:
        r8 = h8["r"]
        if "oog_clip_ipt_hue_p95" in r8:
            q["oog_ipt_hue_p95_r"] = r8["oog_clip_ipt_hue_p95"]
        if "oog_clip_ipt_hue_blue_mean" in r8:
            q["oog_blue_ipt_abs_r"] = abs(r8["oog_clip_ipt_hue_blue_mean"])
        for i in ("p", "s"):
            if i in h8:
                q[f"black_gap_{i}"] = h8[i]["black_L"] - r8["black_L"]
                q[f"black_C_{i}"] = h8[i]["black_C"]
    if h1:
        for path, key in (("p", "grey_swing_p"), ("s", "grey_swing_s"), ("r", "grey_swing_r"),
                          ("r+bpc", "grey_swing_rbpc"), ("p-app8", "grey_swing_p_app8")):
            if path in h1:
                q[key] = h1[path]["l_swing"]
        q["grey_chroma_max_p"] = h1["p"]["chroma_max"]
        q["grey_chroma_max_s"] = h1["s"]["chroma_max"]
    if "shadows" in raw:
        q["grey_shadow_swing_p"] = raw["shadows"]["p"]
        q["grey_shadow_swing_s"] = raw["shadows"]["s"]
    if "below_black" in raw:
        q["below_black_swing_r"] = raw["below_black"]["swing"]
        q["below_black_rev_r"] = raw["below_black"]["rev"]
    out = {"reader": reader, "q": q, "raw": hunt.jsonable(raw), "errors": errors,
           "ink_seen_max": max((v for _, v in ctx.ink_seen), default=None)}
    if with_gmq:
        gm = {}
        gamut = gmq.TruthGamut(cloud)
        for i in ("p", "s"):
            try:
                res, _ = gmq.evaluate(profile, printer, reader="lcms", intent=i, gamut=gamut)
                gm[i] = res
                for k in GMQ_KEYS:
                    if res.get(k) is not None:
                        q[f"gmq_{i}_{k}"] = float(res[k])
            except Exception as exc:
                errors[f"gmq_{i}"] = f"{type(exc).__name__}: {exc}"
        out["gmq"] = hunt.jsonable(gm)
    if with_ncq:
        try:
            from benchmarks.research import ncpoints
            out["ncq"] = hunt.jsonable(ncpoints.referee(profile, printer, ncq_reader))
        except Exception as exc:
            errors["ncq"] = f"{type(exc).__name__}: {exc}"
    out["q"] = {k: float(v) for k, v in q.items()}
    return out
