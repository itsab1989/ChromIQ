"""Agent 85 (2026-11-07): what relative colorimetric + black point compensation prints near black.

Lightroom, Photoshop and every Little CMS application print "Relative Colorimetric + BPC" by squeezing the
image's black onto the printer profile's black point. That black point is NOT a tag: the CMM measures it
from the tables (Adobe's published algorithm, as Little CMS implements it in ``cmsDetectDestinationBlackPoint``).
If the profile's B2A1 cannot reach that black, the darkest steps of the image are lifted and merge. Nothing
else in the battery measures this (``grey_swing_rbpc`` only sees L* swings of a whole sRGB ramp).

Two parts:

* ``destination_black_point(icc, intent)``: the Adobe / Little CMS black point, re-implemented on the battery's
  lcms reader (the Little CMS bundled with Pillow, float, no optimisation) step by step after
  ``cmssamp.c`` of Little CMS master 6a5a89058c (2026), INCLUDING the neutralising step that master restored
  ("Recover fixing of neutrality when detecting black point", missing from Little CMS 2.16 to 2.19.1):
    - RGB (and gray), rel. col.: the darkest colorant (device 0,0,0 for RGB) through A2B1, a* = b* = 0,
      L* clipped to 0..50 (``BlackPointAsDarkerColorant``);
    - ink spaces (CMY, CMYK, n-colour), rel. col.: Lab 0,0,0 through the PERCEPTUAL B2A0, then A2B1, made
      neutral, L* <= 50 (``BlackPointUsingPerceptualBlack``: "discount ink limiting"); so for CMYK the
      rel. col. + BPC black depends on the perceptual table;
    - then the round trip Lab(L, 0, 0) -> B2A(intent) -> A2B1, L = 0..100 in 256 steps, made monotone; rel. col.
      with a "nearly straight midrange" keeps the first guess, otherwise the root of a least-squares quadratic
      over the normalised shadow section (rel. col. 0.1-0.5, perceptual 0.03-0.25);
    - v4 perceptual / saturation: the fixed ICC perceptual black (not used here: the battery profiles are v2).
* ``bpc_wedge(icc, intent, bp)``: a neutral source wedge L* 0..20 (21 steps, 1 L* apart; source black L* 0, as
  a working space's black) mapped by the BPC scaling Little CMS uses (``ComputeBlackPointCompensation``: per
  XYZ channel, D50 white fixed, source black -> destination black), then B2A(intent) without BPC: device values.

A check against a REAL Little CMS master build is built in: set ``CHROMIQ_LCMS_MASTER`` to a liblcms2 built from
master (Agent 85 keeps one in Experiments/agent85/lcms/) and ``evaluate`` also runs the CMM's own transform
(Lab -> printer, cmsFLAGS_BLACKPOINTCOMPENSATION) and its own ``cmsDetectDestinationBlackPoint``, and records
the largest difference (``cmm_check``). Without it the re-implementation stands alone (Windows, Linux, CI).

``evaluate(icc, refs)`` prints the wedge on each reference (device -> media-relative Lab: the battery truth, an
rbf, the profile's own A2B1) and returns per intent and reference:
    bp_L         the black point the CMM aims at (the profile's, not the reference's); perceptual: usually 0,
                 so perceptual + BPC = perceptual, and the wedge is judged against the rel. col. black point
    black_L      printed L* of the darkest step (source L* 0)
    lift         black_L - bp_L (rel. col.; perceptual: minus the rel. col. black point). Lower is better;
                 0 = the table reaches its own black point
    sep_min      smallest printed L* step among the bottom 6 steps (5 differences; larger is better)
    sep_ratio    smallest printed step / the step BPC asked for there (1 = kept; lower = merged)
    wedge_de     mean dE00, printed vs the BPC target (L_bpc, 0, 0), all 21 steps (tints count too)
    ref_black_L  the reference's own darkest device colour, printed (context: what the printer can do)
"""
from __future__ import annotations

import ctypes
import os
from functools import lru_cache
from pathlib import Path

import numpy as np

from benchmarks.research import cmm, colour
from benchmarks.research.blindspots import xf

D50 = np.array([0.9642, 1.0, 0.8249])          # cmsD50_XYZ()
WEDGE_L = np.arange(21, dtype=float)           # source L* 0..20, 1 apart
BOTTOM = 6                                     # the bottom 6 steps: 5 differences


def _f(t):
    return np.where(t > (6 / 29) ** 3, np.cbrt(t), t / (3 * (6 / 29) ** 2) + 4 / 29)


def _finv(t):
    return np.where(t > 6 / 29, t ** 3, 3 * (6 / 29) ** 2 * (t - 4 / 29))


def lab_to_xyz(lab):
    lab = np.atleast_2d(np.asarray(lab, float))
    fy = (lab[:, 0] + 16) / 116
    return np.stack([_finv(fy + lab[:, 1] / 500), _finv(fy), _finv(fy - lab[:, 2] / 200)], 1) * D50


def xyz_to_lab(xyz):
    t = _f(np.atleast_2d(np.asarray(xyz, float)) / D50)
    return np.stack([116 * t[:, 1] - 16, 500 * (t[:, 0] - t[:, 1]), 200 * (t[:, 1] - t[:, 2])], 1)


def _kind(icc):
    n, additive = cmm._profile_n(Path(icc))
    return n, additive


def _darkest_device(n, additive):
    return np.zeros((1, n)) if additive else np.ones((1, n))


def _a2b1(icc, dev):
    return xf.lcms(str(icc), "lab", np.atleast_2d(dev), "r")


def _round_trip(icc, lab, intent):
    """Lab -> B2A(intent) -> A2B1 (Little CMS's CreateRoundtripXForm, float, no optimisation)."""
    dev = xf.lcms("lab", str(icc), lab, intent)
    n, additive = _kind(icc)
    return _a2b1(icc, np.clip(dev, 0, 1))


def _quad_root(x, y):
    """Little CMS RootOfLeastSquaresFitQuadraticCurve, line by line."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 4:
        return 0.0
    m = np.array([[len(x), x.sum(), (x ** 2).sum()], [x.sum(), (x ** 2).sum(), (x ** 3).sum()],
                  [(x ** 2).sum(), (x ** 3).sum(), (x ** 4).sum()]])
    v = np.array([y.sum(), (y * x).sum(), (y * x * x).sum()])
    try:
        c, b, a = np.linalg.solve(m, v)
    except np.linalg.LinAlgError:
        return 0.0
    if abs(a) < 1e-10:
        return 0.0 if abs(b) < 1e-10 else float(max(0, min(50, -c / b)))
    d = b * b - 4 * a * c
    if d <= 0:
        return 0.0
    return float(max(0, min(50, (-b + np.sqrt(d)) / (2 * a))))


def initial_black(icc, intent="r"):
    """cmsDetectBlackPoint for an output profile (v2), Little CMS master: (L*, how)."""
    n, additive = _kind(icc)
    if intent == "r" and not additive:
        lab = _round_trip(icc, np.zeros((1, 3)), "p")[0]          # BlackPointUsingPerceptualBlack
        return float(min(lab[0], 50.0)), "perceptual black (ink space)"
    lab = _a2b1(icc, _darkest_device(n, additive))[0] if intent == "r" else \
        xf.lcms(str(icc), "lab", _darkest_device(n, additive), intent)[0]
    L = lab[0]
    L = 0.0 if (L > 95 or L < 0) else min(L, 50.0)
    return float(L), "darkest colorant"


def destination_black_point(icc, intent="r"):
    """cmsDetectDestinationBlackPoint (Adobe), v2 output profile with cLUTs: (L*, how). Always neutral."""
    if intent == "r":
        L0, how = initial_black(icc, "r")
    else:
        L0, how = 0.0, "zero first guess"
    inr = np.arange(256) * 100.0 / 255.0
    out = _round_trip(icc, np.stack([inr, np.zeros(256), np.zeros(256)], 1), intent)[:, 0].copy()
    for k in range(254, 0, -1):
        out[k] = min(out[k], out[k + 1])
    if not out[0] < out[255]:
        return 0.0, "round trip not increasing"
    mn, mx = out[0], out[255]
    if intent == "r":
        straight = np.all((inr <= mn + 0.2 * (mx - mn)) | (np.abs(inr - out) < 4.0))
        if straight:
            return L0, how + ", straight midrange"
    y = (out - mn) / (mx - mn)
    lo, hi = (0.1, 0.5) if intent == "r" else (0.03, 0.25)
    sel = (y >= lo) & (y < hi)
    if sel.sum() < 3:
        return 0.0, "no shadow points"
    return max(0.0, _quad_root(inr[sel], y[sel])), "quadratic fit"


def bpc_targets(bp_L, src_L=WEDGE_L):
    """The PCS Lab BPC asks for: source neutral L* -> XYZ, D50 fixed, black 0 -> the (neutral) black point."""
    src = np.stack([src_L, np.zeros_like(src_L), np.zeros_like(src_L)], 1)
    bp = lab_to_xyz([[bp_L, 0, 0]])[0]
    xyz = lab_to_xyz(src) * (1 - bp / D50) + bp
    return xyz_to_lab(xyz)


def bpc_wedge(icc, intent, bp_L, src_L=WEDGE_L):
    """Device values Rel. Col. (or perceptual) + BPC gives the neutral source wedge (re-implementation)."""
    tgt = bpc_targets(bp_L, src_L)
    return np.clip(xf.lcms("lab", str(icc), tgt, intent), 0, 1), tgt


# --- the real Little CMS master, if one is given ------------------------------------------------------------
@lru_cache(maxsize=None)
def _master():
    p = os.environ.get("CHROMIQ_LCMS_MASTER", "")
    if not p or not Path(p).exists():
        return None
    lib = ctypes.CDLL(p, mode=ctypes.RTLD_LOCAL)
    lib.cmsOpenProfileFromFile.restype = ctypes.c_void_p
    lib.cmsOpenProfileFromFile.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.cmsCreateLab4Profile.restype = ctypes.c_void_p
    lib.cmsCreateLab4Profile.argtypes = [ctypes.c_void_p]
    lib.cmsCreateTransform.restype = ctypes.c_void_p
    lib.cmsCreateTransform.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                                       ctypes.c_uint32, ctypes.c_uint32]
    lib.cmsDoTransform.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
    lib.cmsDeleteTransform.argtypes = [ctypes.c_void_p]
    lib.cmsCloseProfile.argtypes = [ctypes.c_void_p]
    lib.cmsDetectDestinationBlackPoint.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                                   ctypes.c_uint32]
    lib.cmsGetEncodedCMMversion.restype = ctypes.c_int
    return lib


def master_wedge(icc, intent, src_L=WEDGE_L):
    """(device, bp_L) from the real Little CMS master: Lab -> printer, BPC flag, float, no optimisation."""
    lib = _master()
    if lib is None:
        return None
    n, additive = _kind(icc)
    dfmt, scale = cmm._dev_fmt(n, additive)
    hp = lib.cmsOpenProfileFromFile(str(icc).encode(), b"r")
    hl = lib.cmsCreateLab4Profile(None)
    try:
        it = xf.INTENTS[intent]
        t = lib.cmsCreateTransform(hl, cmm._fmt(10, 3), hp, dfmt, it, xf.BPC | xf.NOOPT | xf.NOCACHE)
        src = np.ascontiguousarray(np.stack([src_L, 0 * src_L, 0 * src_L], 1), np.float64)
        dst = np.zeros((len(src_L), n))
        lib.cmsDoTransform(t, src.ctypes.data, dst.ctypes.data, len(src_L))
        lib.cmsDeleteTransform(t)
        bp = (ctypes.c_double * 3)()
        lib.cmsDetectDestinationBlackPoint(ctypes.cast(bp, ctypes.c_void_p), hp, it, 0)
        bpL = float(xyz_to_lab([[bp[0], bp[1], bp[2]]])[0, 0])
        return np.clip(dst / scale, 0, 1), bpL
    finally:
        lib.cmsCloseProfile(hp)
        lib.cmsCloseProfile(hl)


# --- the metric ------------------------------------------------------------------------------------------------
def wedge_numbers(printed, tgt, bp_L):
    L = printed[:, 0]
    d = np.diff(L[:BOTTOM])
    t = np.diff(tgt[:BOTTOM, 0])
    return {"bp_L": float(bp_L), "black_L": float(L[0]), "lift": float(L[0] - bp_L),
            "sep_min": float(d.min()), "sep_ratio": float((d / t).min()),
            "wedge_de": float(colour.de2000(printed, tgt).mean()),
            "printed_L": [round(float(x), 3) for x in L]}


def evaluate(icc, refs: dict, intents=("r", "p")) -> dict:
    """refs: name -> callable(device 0..1) -> media-relative Lab. 'own' (the profile's A2B1) is always added.
    Returns {intent: {"bp_L", "bp_how", "device", "target_L", ref: wedge_numbers, ...}, "cmm_check": {...}}."""
    n, additive = _kind(icc)
    refs = dict(refs)
    refs.setdefault("own", lambda d: _a2b1(icc, d))
    out: dict = {"cmm_check": {}}
    bp_r = None
    for it in intents:
        bp, how = destination_black_point(icc, it)
        dev, tgt = bpc_wedge(icc, it, bp)
        # perceptual: the black point is usually 0 (the table already reaches black), so BPC changes nothing;
        # the wedge is then judged against what rel. col. + BPC asks for (the printer's own black, steps kept)
        aim = bp
        if it != "r":
            bp_r = bp_r if bp_r is not None else destination_black_point(icc, "r")[0]
            aim, tgt = bp_r, bpc_targets(bp_r)
        else:
            bp_r = bp
        rec = {"bp_L": bp, "bp_how": how, "aim_L": aim, "device": np.round(dev, 6).tolist(),
               "target_L": [round(float(x), 3) for x in tgt[:, 0]]}
        for name, fn in refs.items():
            pr = np.atleast_2d(fn(dev))
            rec[name] = wedge_numbers(pr, tgt, aim)
            rec[name]["ref_black_L"] = float(np.atleast_2d(fn(_darkest_device(n, additive)))[0, 0])
        m = master_wedge(icc, it)
        if m is not None:
            mdev, mbp = m
            own_m = _a2b1(icc, mdev)[:, 0]
            out["cmm_check"][it] = {"bp_L_master": mbp, "bp_L_diff": abs(mbp - bp),
                                    "device_max_diff": float(np.abs(mdev - dev).max()),
                                    "own_black_L_master": float(own_m[0]),
                                    "own_L_max_diff": float(np.abs(own_m - rec["own"]["printed_L"]).max())}
        out[it] = rec
    return out


# battery rows (oogq): key -> (sign, floor, safety, finding, what); measured on the battery truth
KEYS = {}
for _i, _nm in (("r", "rel. col. + BPC"), ("p", "perceptual + BPC")):
    KEYS[f"bpc_lift_{_i}"] = (1, 0.1, False, "BPC", f"{_nm}: darkest wedge step printed L* minus the profile's "
                                                      f"black point L* (Adobe / Little CMS master)")
    KEYS[f"bpc_sep_min_{_i}"] = (-1, 0.1, False, "BPC", f"{_nm}: smallest printed L* step, bottom 6 steps of a "
                                                         f"neutral L* 0-20 wedge")
    KEYS[f"bpc_sep_ratio_{_i}"] = (-1, 0.02, False, "BPC", f"{_nm}: that step / the step BPC asked for")
    KEYS[f"bpc_wedge_de_{_i}"] = (1, 0.1, False, "BPC", f"{_nm}: mean dE00 printed vs the BPC target, 21 steps")


def q_rows(res: dict, ref: str = "truth") -> dict:
    q = {}
    for it in ("r", "p"):
        r = (res.get(it) or {}).get(ref)
        if not r:
            continue
        q[f"bpc_lift_{it}"] = r["lift"]
        q[f"bpc_sep_min_{it}"] = r["sep_min"]
        q[f"bpc_sep_ratio_{it}"] = r["sep_ratio"]
        q[f"bpc_wedge_de_{it}"] = r["wedge_de"]
    return q
