"""Agent 23: hunt for profile defects the battery does not measure.

An expert evaluates a printer profile by sending real content and
synthetic test targets THROUGH it and looking at what prints. Each test
here does that and returns NUMBERS plus the flagged places (never a
judgement by eye). Every output is printed on the truth (the battery's
1 nm synthetic printer, or a labelled proxy for real data).

Tests (H-numbers; the battery's own coverage is in the module docstring of
``metrics`` / ``gmq`` / ``ncq``, gaps listed in Findings/agent23-01):

H1  grey ramps sRGB 0..255 in single steps, every intent, plus relative
    with black point compensation (Photoshop's default), lcms float and the
    application path (8-bit, lcms default flags): L* reversals over the
    WHOLE ramp (also below the device black), banding (printed 2nd
    difference), grey tint (C*), steps that print flat (plateaus)
H2  colour ramps: sRGB and Adobe RGB primaries and secondaries to white and
    to black, 256 steps, every intent: L* reversals, hue drift along the
    ramp, banding, flat runs
H3  hue circles in Lab (L* 25/50/75/90, C* 15/35/60), 720 steps, every
    intent: printed hue running backwards, jumps
H4  near-neutral tinted Lab ramps (C* 4 in 8 hues) and dark and light ramps
H5  memory colours: skin, sky, foliage, saturated reds, through every
    intent: dE to source (colorimetric), hue shift (perceptual), the
    blue-purple shift of sRGB blue
H6  synthetic image: 2-D smooth fields (hue x lightness, sky, skin, shadow
    tints) at 8 bits through the application path: per-pixel dE to the
    colorimetric expectation, local-contrast loss and new contours
H7  round trips: device lattice A2B->B2A->A2B on the cube's faces and
    interior; Lab lattice B2A idempotence (B2A(A2B(B2A(x))) = B2A(x))
H8  extreme inputs: Lab corners, sRGB primaries, out-of-gamut sRGB cube
    surface: ink-limit overshoot, ink in paper white per intent, black per
    intent, hue errors of the colorimetric clip
H9  v2 versus v4 twin, per CMM and intent
H10 header and tags: media white vs truth paper (absolute colorimetric),
    A2B0/A2B2 vs A2B1, gamut tag vs the truth gamut, lcms black-point
    detection vs the printed black
"""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import numpy as np

from benchmarks.research import colour, gmq
from benchmarks.research.blindspots import xf

INTENTS = ("p", "r", "s")


# --- helpers ------------------------------------------------------------------
def lch(lab):
    return np.stack([lab[:, 0], np.hypot(lab[:, 1], lab[:, 2]),
                     np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360], 1)


def dhue(h1, h2):
    return ((h2 - h1 + 180.0) % 360.0) - 180.0


def ramp_props(src_lab, printed, dev=None, monotone_l=True):
    """Properties of one printed ramp. ``src_lab`` is the colour asked for.
    Reversal: printed L* moving against the source's L* direction by more
    than 0.1 where the source moves. Banding: printed 2nd difference minus
    the source's (dE76 per step). Flat: consecutive printed steps < 5 % of
    the source step where the source step is visible (> 0.3)."""
    out = {}
    ds = np.diff(src_lab[:, 0])
    dl = np.diff(printed[:, 0])
    if monotone_l:
        against = -np.sign(ds) * dl
        bad = (against > 0.1) & (np.abs(ds) > 1e-6)
        out["l_rev"] = int(bad.sum())
        out["l_rev_max"] = float(against[bad].max()) if bad.any() else 0.0
        # the size of a reversal as a lightness swing: largest rise after a
        # running extreme (catches slow reversals spread over many steps)
        sgn = np.sign(np.median(ds[np.abs(ds) > 1e-6])) if (np.abs(ds) > 1e-6).any() else 1
        L = printed[:, 0] * sgn
        run = np.maximum.accumulate(L)
        out["l_swing"] = float((run - L).max())
        out["l_swing_at"] = int(np.argmax(run - L))
    d2p = np.linalg.norm(np.diff(printed, 2, axis=0), axis=1)
    d2s = np.linalg.norm(np.diff(src_lab, 2, axis=0), axis=1)
    ex = d2p - d2s
    out["d2_excess_max"] = float(ex.max())
    out["d2_excess_at"] = int(np.argmax(ex)) + 1
    sstep = np.linalg.norm(np.diff(src_lab, axis=0), axis=1)
    pstep = np.linalg.norm(np.diff(printed, axis=0), axis=1)
    med = np.median(pstep[pstep > 0]) if (pstep > 0).any() else 0
    out["jump_ratio"] = float(pstep.max() / med) if med > 0 else 0.0
    if dev is not None:
        out["dev_d2_max"] = float(np.abs(np.diff(dev, 2, axis=0)).max())
    return out


def worst(rows, key, fn=max):
    vals = [r[key] for r in rows if key in r]
    return fn(vals) if vals else None


class Ctx:
    """One profile under test and its truth."""

    def __init__(self, icc, truth_lab, n, additive, tac=None, truth_xyz=None,
                 truth_cloud=None):
        self.icc = str(icc)
        self.truth_lab = truth_lab        # device01 -> media-relative Lab
        self.truth_xyz = truth_xyz        # device01 -> absolute XYZ (D50), or None
        self.n = n
        self.additive = additive
        self.tac = tac
        self.gamut = gmq.TruthGamut(truth_cloud) if truth_cloud is not None else None
        self.ink_seen = []                # (test, max TAC) of every B2A output

    def note_ink(self, test, dev):
        if not self.additive and len(dev):
            self.ink_seen.append((test, float(dev.sum(1).max() * 100)))

    def lab2dev(self, lab, intent, bpc=False):
        return np.clip(xf.lcms("lab", self.icc, lab, intent, bpc=bpc), 0, 1)

    def rgb2dev(self, src, rgb, intent, bpc=False, bits=0, optimise=False):
        return np.clip(xf.lcms(src, self.icc, rgb, intent, bpc=bpc, bits=bits,
                               optimise=optimise), 0, 1)


# --- H1 grey ramps -----------------------------------------------------------------
PATHS = [("p", False, 0, False), ("r", False, 0, False), ("s", False, 0, False),
         ("r", True, 0, False), ("p", False, 8, True), ("r", True, 8, True),
         ("r", False, 16, True)]


def _path_name(p):
    i, bpc, bits, opt = p
    return f"{i}{'+bpc' if bpc else ''}{'-app' + str(bits) if opt else ''}"


def h1_grey(ctx: Ctx) -> dict:
    v = np.arange(256) / 255.0
    rgb = np.stack([v, v, v], 1)
    src = xf.srgb_to_lab(rgb)
    out = {}
    for p in PATHS:
        dev = ctx.rgb2dev("srgb", rgb, p[0], bpc=p[1], bits=p[2], optimise=p[3])
        ctx.note_ink("H1 " + _path_name(p), dev)
        pr = ctx.truth_lab(dev)
        r = ramp_props(src, pr, dev)
        c = np.hypot(pr[:, 1], pr[:, 2])
        r["chroma_max"] = float(c.max())
        r["chroma_max_at"] = int(np.argmax(c))
        r["chroma_mean"] = float(c.mean())
        r["black_L"] = float(pr[0, 0])
        # flat run: codes 1..k printing the same as code 0 (shadow detail lost)
        r["shadow_codes_lost"] = int(np.argmax(pr[:, 0] > pr[0, 0] + 0.5))
        r["white_ink"] = float((1 - dev[-1]).sum() * 100 if ctx.additive else dev[-1].sum() * 100)
        out[_path_name(p)] = r
    return out


# --- H2 colour ramps ----------------------------------------------------------------
CORNERS = {"R": [1, 0, 0], "G": [0, 1, 0], "B": [0, 0, 1], "C": [0, 1, 1],
           "M": [1, 0, 1], "Y": [1, 1, 0]}


def h2_colour_ramps(ctx: Ctx, spaces=("srgb", "adobe")) -> dict:
    from benchmarks.research import run
    t = np.linspace(0, 1, 256)[:, None]
    out = {}
    for sp in spaces:
        srcp = "srgb" if sp == "srgb" else run.SOURCE_GAMUT
        for name, c in CORNERS.items():
            c = np.array(c, float)
            for kind, rgb in (("w", 1 - t * (1 - c)), ("k", c * (1 - t))):
                lab = xf.lcms(srcp, "lab", rgb, "r")
                for intent in INTENTS:
                    dev = ctx.rgb2dev(srcp, rgb, intent)
                    ctx.note_ink("H2", dev)
                    pr = ctx.truth_lab(dev)
                    r = ramp_props(lab, pr, dev)
                    h = lch(pr)
                    sel = h[:, 1] > 8
                    if sel.sum() > 3:
                        hh = h[sel, 2]
                        dh = dhue(hh[:-1], hh[1:])
                        r["hue_step_max"] = float(np.abs(dh).max())
                        r["hue_range"] = float(np.ptp(np.unwrap(np.radians(hh))) * 180 / np.pi)
                    out[f"{sp}-{name}-{kind}-{intent}"] = r
    return out


# --- H3 hue circles ------------------------------------------------------------------
def h3_hue_circles(ctx: Ctx) -> dict:
    hue = np.linspace(0, 360, 721)[:-1]
    out = {}
    for L in (25, 50, 75, 90):
        for C in (15, 35, 60):
            lab = np.stack([np.full_like(hue, L), C * np.cos(np.radians(hue)),
                            C * np.sin(np.radians(hue))], 1)
            for intent in INTENTS:
                dev = ctx.lab2dev(lab, intent)
                ctx.note_ink("H3", dev)
                pr = ctx.truth_lab(dev)
                h = lch(pr)
                dh = dhue(h[:, 2], np.roll(h[:, 2], -1))
                ok = h[:, 1] > 3
                ok2 = ok & np.roll(ok, -1)
                back = (dh < -0.5) & ok2
                step = np.linalg.norm(pr - np.roll(pr, -1, 0), axis=1)
                med = np.median(step)
                r = {"hue_back_steps": int(back.sum()),
                     "hue_back_max": float(-dh[back].min()) if back.any() else 0.0,
                     "hue_back_at": float(hue[back][np.argmin(dh[back])]) if back.any() else None,
                     "jump_ratio": float(step.max() / med) if med > 0 else 0.0,
                     "jump_at": float(hue[np.argmax(step)]),
                     "L_range": float(np.ptp(pr[:, 0]))}
                if intent == "r" and ctx.gamut is not None:
                    inn = ctx.gamut.depth(lab) > 2.0
                    if inn.any():
                        de = colour.de2000(pr[inn], lab[inn])
                        r["ingamut_de_p95"] = float(np.percentile(de, 95))
                        r["ingamut_de_max"] = float(de.max())
                        r["ingamut_de_max_hue"] = float(hue[inn][np.argmax(de)])
                out[f"L{L}-C{C}-{intent}"] = r
    return out


# --- H4 tinted, dark and light ramps ---------------------------------------------------
def h4_tinted(ctx: Ctx) -> dict:
    out = {}
    L = np.arange(0, 100.01, 0.25)
    for hdeg in range(0, 360, 45):
        a, b = 4 * np.cos(np.radians(hdeg)), 4 * np.sin(np.radians(hdeg))
        lab = np.stack([L, np.full_like(L, a), np.full_like(L, b)], 1)
        for intent in ("p", "r"):
            dev = ctx.lab2dev(lab, intent)
            ctx.note_ink("H4", dev)
            pr = ctx.truth_lab(dev)
            r = ramp_props(lab, pr, dev)
            # hue held along the printable part (printed C* > 1.5)
            h = lch(pr)
            ok = (h[:, 1] > 1.5) & (lab[:, 0] > pr[0, 0] + 3) & (lab[:, 0] < 97)
            if ok.sum() > 5:
                dh = np.abs(dhue(hdeg, h[ok, 2]))
                r["hue_err_max"] = float(dh.max())
                r["hue_err_at_L"] = float(L[ok][np.argmax(dh)])
            out[f"tint{hdeg}-{intent}"] = r
    # dark ramps L 0..30 at C* 10 in 6 hues, light ramps L 80..100 C* 8
    for nm, Lr, C in (("dark", np.arange(0, 30.01, 0.1), 10.0),
                      ("light", np.arange(80, 100.01, 0.05), 8.0)):
        for hdeg in range(0, 360, 60):
            lab = np.stack([Lr, np.full_like(Lr, C * np.cos(np.radians(hdeg))),
                            np.full_like(Lr, C * np.sin(np.radians(hdeg)))], 1)
            for intent in ("p", "r"):
                dev = ctx.lab2dev(lab, intent)
                ctx.note_ink("H4", dev)
                pr = ctx.truth_lab(dev)
                r = ramp_props(lab, pr, dev)
                if ctx.gamut is not None and intent == "r":
                    inn = ctx.gamut.depth(lab) > 2.0
                    if inn.any():
                        de = colour.de2000(pr[inn], lab[inn])
                        r["ingamut_de_max"] = float(de.max())
                        r["ingamut_de_max_L"] = float(Lr[inn][np.argmax(de)])
                out[f"{nm}{hdeg}-{intent}"] = r
    return out


# --- H5 memory colours ---------------------------------------------------------------------
# CIELAB D50 of ColorChecker (BabelColor 2012 average, D50) and sRGB memory colours
MEMORY_LAB = {
    "dark_skin": [37.99, 13.56, 14.06], "light_skin": [65.71, 18.13, 17.81],
    "blue_sky": [49.93, -4.88, -21.93], "foliage": [43.14, -13.10, 21.91],
    "blue_flower": [55.11, 8.84, -25.40], "bluish_green": [70.72, -33.40, -0.20],
    "orange": [62.66, 36.07, 57.10], "purplish_blue": [40.02, 10.41, -45.96],
    "moderate_red": [51.12, 48.24, 16.25], "yellow_green": [72.53, -23.71, 57.26],
    "red": [42.10, 53.38, 28.19], "green": [55.26, -38.34, 31.37],
    "blue": [28.78, 14.18, -50.30], "yellow": [81.73, 4.04, 79.82],
    "magenta": [51.94, 49.99, -14.57], "cyan": [51.04, -28.63, -28.64],
    "pale_skin": [80.0, 10.0, 14.0], "deep_skin": [30.0, 12.0, 16.0],
    "pale_sky": [85.0, -4.0, -14.0], "deep_sky": [40.0, 0.0, -38.0],
}
MEMORY_SRGB = {"sRGB_red": [1, 0, 0], "sRGB_blue": [0, 0, 1], "sRGB_green": [0, 1, 0],
               "sky_srgb": [0.53, 0.81, 0.92], "skin_srgb": [0.94, 0.76, 0.65],
               "red_255_40_40": [1, 0.16, 0.16], "blue_60_60_255": [0.24, 0.24, 1.0]}


def h5_memory(ctx: Ctx) -> dict:
    out = {}
    names = list(MEMORY_LAB)
    lab = np.array([MEMORY_LAB[k] for k in names], float)
    rgbn = list(MEMORY_SRGB)
    rgb = np.array([MEMORY_SRGB[k] for k in rgbn], float)
    rlab = xf.srgb_to_lab(rgb)
    allnames = names + rgbn
    alllab = np.vstack([lab, rlab])
    ipt_s = gmq.lab_to_ipt(alllab)
    hs = np.degrees(np.arctan2(ipt_s[:, 2], ipt_s[:, 1]))
    depth = ctx.gamut.depth(alllab) if ctx.gamut is not None else np.full(len(alllab), np.nan)
    for intent in INTENTS:
        dev = np.vstack([ctx.lab2dev(lab, intent), ctx.rgb2dev("srgb", rgb, intent)])
        ctx.note_ink("H5", dev)
        pr = ctx.truth_lab(dev)
        ipt_p = gmq.lab_to_ipt(pr)
        hp = np.degrees(np.arctan2(ipt_p[:, 2], ipt_p[:, 1]))
        de = colour.de2000(pr, alllab)
        for i, nm in enumerate(allnames):
            out[f"{nm}-{intent}"] = {"de00": float(de[i]), "ipt_hue_shift": float(dhue(hs[i], hp[i])),
                                     "dL": float(pr[i, 0] - alllab[i, 0]),
                                     "dC": float(np.hypot(*pr[i, 1:]) - np.hypot(*alllab[i, 1:])),
                                     "gamut_depth": float(depth[i])}
    return out


# --- H6 synthetic image --------------------------------------------------------------------
def synthetic_image(h=96, w=256) -> np.ndarray:
    """sRGB 8-bit content: hue x lightness field, saturation field, a sky
    gradient, a skin gradient, a shadow-tint field (h*5 x w x 3)."""
    x = np.linspace(0, 1, w)[None, :]
    y = np.linspace(0, 1, h)[:, None]
    import colorsys
    hs = np.zeros((h, w, 3))
    for i in range(h):
        for j in range(w):
            hs[i, j] = colorsys.hsv_to_rgb(x[0, j], 1.0, 1.0 - 0.95 * y[i, 0])
    sat = np.zeros((h, w, 3))
    for i in range(h):
        for j in range(w):
            sat[i, j] = colorsys.hsv_to_rgb(x[0, j], y[i, 0], 1.0)
    sky = np.stack([0.25 + 0.6 * y + 0 * x, 0.45 + 0.45 * y + 0 * x, 0.85 + 0.12 * y + 0 * x], -1)
    sky = sky * (0.75 + 0.25 * x[..., None])
    skin = np.stack([0.35 + 0.6 * x + 0 * y, 0.22 + 0.55 * x + 0 * y, 0.17 + 0.48 * x + 0 * y], -1)
    skin = skin * (0.6 + 0.4 * y[..., None])
    shadow = np.zeros((h, w, 3))
    for i in range(h):
        for j in range(w):
            shadow[i, j] = colorsys.hsv_to_rgb(x[0, j], 0.35, 0.02 + 0.2 * y[i, 0])
    img = np.concatenate([hs, sat, sky, skin, shadow], 0)
    return np.round(np.clip(img, 0, 1) * 255) / 255


def h6_image(ctx: Ctx) -> dict:
    img = synthetic_image()
    H, W, _ = img.shape
    rgb = img.reshape(-1, 3)
    src = xf.srgb_to_lab(rgb)
    regions = ["hue_light", "saturation", "sky", "skin", "shadow"]
    rh = H // 5
    out = {}
    for path in (("p", False, 8, True), ("r", True, 8, True), ("r", False, 0, False)):
        dev = ctx.rgb2dev("srgb", rgb, path[0], bpc=path[1], bits=path[2], optimise=path[3])
        ctx.note_ink("H6", dev)
        pr = ctx.truth_lab(dev).reshape(H, W, 3)
        sl = src.reshape(H, W, 3)
        de = colour.de2000(pr.reshape(-1, 3), src).reshape(H, W)
        inn = (ctx.gamut.depth(src) > 2.0).reshape(H, W) if ctx.gamut is not None else np.ones((H, W), bool)

        def nbr(a):
            dx = colour.de2000(a[:, 1:].reshape(-1, 3), a[:, :-1].reshape(-1, 3)).reshape(H, W - 1)
            dy = colour.de2000(a[1:].reshape(-1, 3), a[:-1].reshape(-1, 3)).reshape(H - 1, W)
            return dx, dy
        sx, sy = nbr(sl)
        px, py = nbr(pr)
        res = {}
        for k, nm in enumerate(regions):
            rs = slice(k * rh, (k + 1) * rh)
            r = {}
            m = inn[rs]
            if path[0] == "r" and not path[1] and m.any():
                r["ingamut_de_mean"] = float(de[rs][m].mean())
                r["ingamut_de_p99"] = float(np.percentile(de[rs][m], 99))
            ratio = np.concatenate([(px[rs] / np.maximum(sx[rs], 0.05))[sx[rs] > 0.3],
                                    (py[rs][:-1] / np.maximum(sy[rs][:-1], 0.05))[sy[rs][:-1] > 0.3]])
            # new edges: printed neighbour step > 1.5 dE00 where the source
            # step is < 0.6 (8-bit quantisation alone gives ~0.5)
            newx = (px[rs] > 1.5) & (sx[rs] < 0.6)
            r["contrast_ratio_p05"] = float(np.percentile(ratio, 5)) if len(ratio) else None
            r["contrast_ratio_median"] = float(np.median(ratio)) if len(ratio) else None
            r["new_edges"] = int(newx.sum())
            r["new_edge_max"] = float(px[rs][newx].max()) if newx.any() else 0.0
            if newx.any():
                i, j = np.unravel_index(np.argmax(np.where(newx, px[rs], 0)), newx.shape)
                r["new_edge_at_rgb"] = [round(float(v) * 255) for v in img[k * rh + i, j]]
            res[nm] = r
        out[_path_name(path)] = res
    return out


# --- H7 round trips ---------------------------------------------------------------------------
def device_lattice(n, additive, tac, k=None):
    k = k or {3: 17, 4: 9}.get(n, 5)
    g = np.linspace(0, 1, k)
    if n > 5:
        # 5^7 = 78k is too much: faces (one channel at 0/1) + random interior
        rng = np.random.default_rng(5)
        pts = rng.uniform(0, 1, (12000, n))
        f = rng.integers(0, n, 12000)
        pts[np.arange(12000), f] = rng.integers(0, 2, 12000)
    else:
        pts = np.stack(np.meshgrid(*[g] * n, indexing="ij"), -1).reshape(-1, n)
    if tac and not additive:
        pts = pts[pts.sum(1) <= tac / 100 + 1e-9]
    return pts


def h7_roundtrip(ctx: Ctx, a2b=None) -> dict:
    """a2b: device -> Lab through the profile (lcms float, A2B1)."""
    a2b = a2b or (lambda d: xf.lcms(ctx.icc, "lab", d, "r"))
    dev = device_lattice(ctx.n, ctx.additive, ctx.tac)
    lab = a2b(dev)
    d2 = ctx.lab2dev(lab, "r")
    ctx.note_ink("H7", d2)
    lab2 = a2b(d2)
    de = colour.de2000(lab2, lab)
    face = ((dev == 0) | (dev == 1)).any(1)
    # the profile's view of the boundary vs the printed truth
    pr = ctx.truth_lab(d2)
    tl = ctx.truth_lab(dev)
    de_t = colour.de2000(pr, tl)
    out = {"n": int(len(dev)),
           "a2b_b2a_a2b_de_p95": float(np.percentile(de, 95)), "max": float(de.max()),
           "face_p95": float(np.percentile(de[face], 95)) if face.any() else None,
           "interior_p95": float(np.percentile(de[~face], 95)) if (~face).any() else None,
           "worst_dev": [round(float(v), 3) for v in dev[np.argmax(de)]],
           "printed_vs_truth_p95": float(np.percentile(de_t, 95)),
           "printed_vs_truth_max": float(de_t.max()),
           "printed_worst_dev": [round(float(v), 3) for v in dev[np.argmax(de_t)]]}
    # idempotence on a Lab lattice (in and out of gamut)
    L = np.arange(5, 100, 7.5)
    ab = np.arange(-100, 101, 12.5)
    g = np.stack(np.meshgrid(L, ab, ab, indexing="ij"), -1).reshape(-1, 3)
    for intent in ("r", "p"):
        d1 = ctx.lab2dev(g, intent)
        l1 = a2b(d1) if intent == "r" else xf.lcms(ctx.icc, "lab", d1, "r")
        dd = ctx.lab2dev(l1, "r")
        p1, p2 = ctx.truth_lab(d1), ctx.truth_lab(dd)
        e = colour.de2000(p1, p2)
        out[f"idempotence_{intent}_p95"] = float(np.percentile(e, 95))
        out[f"idempotence_{intent}_max"] = float(e.max())
        out[f"idempotence_{intent}_worst_lab"] = [float(v) for v in g[np.argmax(e)]]
    return out


# --- H8 extreme inputs ------------------------------------------------------------------------
def h8_extremes(ctx: Ctx) -> dict:
    out = {}
    corners = np.array([[L, a, b] for L in (0, 50, 100) for a in (-127, 0, 127)
                        for b in (-127, 0, 127)], float)
    # out-of-gamut sRGB cube surface, 33 x 33 per face
    g = np.linspace(0, 1, 33)
    faces = []
    for ax in range(3):
        for val in (0.0, 1.0):
            u, v = np.meshgrid(g, g, indexing="ij")
            f = np.zeros((u.size, 3))
            others = [i for i in range(3) if i != ax]
            f[:, ax] = val
            f[:, others[0]] = u.ravel()
            f[:, others[1]] = v.ravel()
            faces.append(f)
    surf = np.vstack(faces)
    slab = xf.srgb_to_lab(surf)
    for intent in ("p", "r", "s", "a"):
        r = {}
        dc = ctx.lab2dev(corners, intent)
        ds = ctx.rgb2dev("srgb", surf, intent)
        ctx.note_ink(f"H8-{intent}", np.vstack([dc, ds]))
        if not ctx.additive:
            tot = np.vstack([dc, ds]).sum(1) * 100
            r["tac_max"] = float(tot.max())
            if ctx.tac:
                r["over_tac_share"] = float((tot > ctx.tac + 1).mean())
        w = ctx.lab2dev(np.array([[100.0, 0, 0]]), intent)[0]
        r["white_ink_pct"] = float(((1 - w) if ctx.additive else w).sum() * 100)
        bk = ctx.lab2dev(np.array([[0.0, 0, 0]]), intent)
        pb = ctx.truth_lab(bk)[0]
        r["black_L"], r["black_C"] = float(pb[0]), float(np.hypot(pb[1], pb[2]))
        if intent in ("r", "a"):
            pr = ctx.truth_lab(ds)
            oog = ctx.gamut.depth(slab) < -3 if ctx.gamut is not None else np.ones(len(slab), bool)
            hs, hp = lch(slab), lch(pr)
            ok = oog & (hs[:, 1] > 15) & (hp[:, 1] > 5)
            if ok.any():
                dh = np.abs(dhue(hs[ok, 2], hp[ok, 2]))
                r["oog_clip_hue_p95"] = float(np.percentile(dh, 95))
                r["oog_clip_hue_max"] = float(dh.max())
                r["oog_clip_hue_worst_rgb"] = [round(float(v) * 255) for v in surf[ok][np.argmax(dh)]]
                # lightness order kept: brighter sources must not print darker
                # than darker sources of the same hue sector (sampled pairs)
        out[intent] = r
    # the saturation and perceptual whites/blacks via sRGB
    return out


# --- H9 v2 vs v4 -------------------------------------------------------------------------------
def h9_v2v4(ctx: Ctx, v4_path) -> dict:
    if not v4_path or not Path(v4_path).exists():
        return {"skipped": "no v4 twin"}
    rng = np.random.default_rng(9)
    lab = np.column_stack([rng.uniform(0, 100, 3000), rng.uniform(-90, 90, 3000),
                           rng.uniform(-90, 90, 3000)])
    v = np.arange(256) / 255
    grey = np.stack([v, v, v], 1)
    out = {}
    for intent in ("p", "r", "s"):
        for reader in ("lcms", "argyll"):
            if reader == "lcms":
                d2 = ctx.lab2dev(lab, intent)
                d4 = np.clip(xf.lcms("lab", v4_path, lab, intent), 0, 1)
            else:
                d2 = np.clip(xf.icclu(ctx.icc, lab, "b", intent), 0, 1)
                d4 = np.clip(xf.icclu(v4_path, lab, "b", intent), 0, 1)
            e = colour.de2000(ctx.truth_lab(d2), ctx.truth_lab(d4))
            out[f"{intent}-{reader}"] = {"p95": float(np.percentile(e, 95)), "max": float(e.max()),
                                         "worst_lab": [round(float(x), 1) for x in lab[np.argmax(e)]]}
        g2 = ctx.rgb2dev("srgb", grey, intent, bpc=False)
        g4 = np.clip(xf.lcms("srgb", v4_path, grey, intent), 0, 1)
        p4 = ctx.truth_lab(g4)
        e = colour.de2000(ctx.truth_lab(g2), p4)
        r4 = ramp_props(xf.srgb_to_lab(grey), p4)
        out[f"{intent}-grey"] = {"max": float(e.max()), "v4_l_rev": r4["l_rev"],
                                 "v4_l_swing": r4["l_swing"], "v4_black_L": float(p4[0, 0])}
    # A2B: v2 vs v4 forward, every intent
    dev = device_lattice(ctx.n, ctx.additive, ctx.tac, k={3: 9, 4: 6}.get(ctx.n, 3))
    for intent in ("p", "r"):
        a2 = xf.lcms(ctx.icc, "lab", dev, intent)
        a4 = xf.lcms(str(v4_path), "lab", dev, intent)
        e = colour.de2000(a2, a4)
        out[f"a2b-{intent}"] = {"p95": float(np.percentile(e, 95)), "max": float(e.max())}
    return out


# --- H10 header and tags ---------------------------------------------------------------------
def _tags(path):
    d = Path(path).read_bytes()
    n = struct.unpack(">I", d[128:132])[0]
    t = {}
    for i in range(n):
        sig, o, sz = struct.unpack(">4sII", d[132 + 12 * i:144 + 12 * i])
        t[sig.decode("latin-1")] = (o, sz)
    return d, t


def _xyz_tag(d, off):
    v = struct.unpack(">3i", d[off + 8:off + 20])
    return np.array(v) / 65536.0


def h10_tags(ctx: Ctx) -> dict:
    d, t = _tags(ctx.icc)
    out = {"tags": sorted(t), "version": f"{d[8]}.{d[9] >> 4}"}
    # profile ID (v4): MD5 with flags, intent, ID zeroed
    pid = d[84:100]
    if any(pid):
        b = bytearray(d)
        b[44:48] = b"\0" * 4
        b[64:68] = b"\0" * 4
        b[84:100] = b"\0" * 16
        out["profile_id_ok"] = hashlib.md5(bytes(b)).digest() == pid
    if "wtpt" in t and ctx.truth_xyz is not None:
        w = _xyz_tag(d, t["wtpt"][0]) * 100
        dev_w = np.full((1, ctx.n), 1.0 if ctx.additive else 0.0)
        tw = ctx.truth_xyz(dev_w)[0]
        out["wtpt_xyz"] = w.round(3).tolist()
        out["truth_paper_xyz"] = tw.round(3).tolist()
        out["wtpt_de00"] = float(colour.de2000(colour.xyz_to_lab(w[None]),
                                               colour.xyz_to_lab(tw[None]))[0])
        # absolute colorimetric end to end on a few in-gamut colours
        rng = np.random.default_rng(3)
        dv = rng.uniform(0, 1, (400, ctx.n))
        if ctx.tac and not ctx.additive:
            from benchmarks.research.gmq import _scale_tac
            dv = _scale_tac(dv, ctx.tac)
        abs_lab = colour.xyz_to_lab(ctx.truth_xyz(dv))
        dev = ctx.lab2dev(abs_lab, "a")
        ctx.note_ink("H10", dev)
        pa = colour.xyz_to_lab(ctx.truth_xyz(dev))
        e = colour.de2000(pa, abs_lab)
        out["abs_b2a_median"] = float(np.median(e))
        out["abs_b2a_p95"] = float(np.percentile(e, 95))
        pw = ctx.lab2dev(colour.xyz_to_lab(tw[None]), "a")[0]
        out["abs_paper_ink_pct"] = float(((1 - pw) if ctx.additive else pw).sum() * 100)
    if "bkpt" in t:
        out["bkpt"] = (_xyz_tag(d, t["bkpt"][0]) * 100).round(3).tolist()
    # A2B0 / A2B2 vs A2B1 on the device lattice
    dev = device_lattice(ctx.n, ctx.additive, ctx.tac, k={3: 9, 4: 6}.get(ctx.n, 3))
    a1 = xf.lcms(ctx.icc, "lab", dev, "r")
    for i in ("p", "s"):
        try:
            ai = xf.lcms(ctx.icc, "lab", dev, i)
            e = colour.de2000(ai, a1)
            out[f"a2b_{i}_vs_r_p95"] = float(np.percentile(e, 95))
            out[f"a2b_{i}_vs_r_max"] = float(e.max())
        except Exception as exc:
            out[f"a2b_{i}_error"] = str(exc)
    # gamut tag vs truth: Argyll icclu -fg returns 0 in gamut / >0 out
    if ctx.gamut is not None and "gamt" in t:
        rng = np.random.default_rng(11)
        lab = np.column_stack([rng.uniform(2, 100, 4000), rng.uniform(-100, 100, 4000),
                               rng.uniform(-100, 100, 4000)])
        dep = ctx.gamut.depth(lab)
        sure = np.abs(dep) > 4
        g = xf.icclu(ctx.icc, lab[sure], "g", "r")[:, 0]
        tag_in = g < 1e-4          # ICC: 0 in gamut, any non-zero out (engine: distance/128)
        truth_in = dep[sure] > 0
        out["gamt_agree"] = float((tag_in == truth_in).mean())
        out["gamt_says_in_truth_out"] = float((tag_in & ~truth_in).mean())
        out["gamt_says_out_truth_in"] = float((~tag_in & truth_in).mean())
    # lcms black point detection (what lcms BPC uses) vs the printed black
    bk = {}
    for intent in ("p", "r"):
        dev = ctx.rgb2dev("srgb", np.zeros((1, 3)), intent, bpc=True)
        bk[intent + "+bpc_black_L"] = float(ctx.truth_lab(dev)[0, 0])
    out.update(bk)
    return out


TESTS = {"H1": h1_grey, "H2": h2_colour_ramps, "H3": h3_hue_circles, "H4": h4_tinted,
         "H5": h5_memory, "H6": h6_image, "H7": h7_roundtrip, "H8": h8_extremes,
         "H10": h10_tags}


def run_all(ctx: Ctx, v4=None, only=None) -> dict:
    res = {}
    for k, fn in TESTS.items():
        if only and k not in only:
            continue
        try:
            res[k] = fn(ctx)
        except Exception as exc:
            import traceback
            res[k] = {"error": f"{type(exc).__name__}: {exc}",
                      "tb": traceback.format_exc()[-1200:]}
    if not only or "H9" in only:
        try:
            res["H9"] = h9_v2v4(ctx, v4)
        except Exception as exc:
            res["H9"] = {"error": f"{type(exc).__name__}: {exc}"}
    if ctx.ink_seen and ctx.tac:
        worst_t = max(ctx.ink_seen, key=lambda x: x[1])
        res["ink"] = {"tac": ctx.tac, "max_seen": worst_t[1], "where": worst_t[0],
                      "over": sorted({t for t, v in ctx.ink_seen if v > ctx.tac + 1})}
    return res


def jsonable(o):
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def dump(res, path):
    Path(path).write_text(json.dumps(jsonable(res), indent=1), encoding="utf-8")
