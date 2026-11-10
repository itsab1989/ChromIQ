"""Battery v3.1 wide-scale evenness rows (Integrator 8 / Agent 47, 2026-10-08).

Why: the battery's smoothness numbers (banding as the largest second
difference, the 2nd-derivative p99) are NARROW-scale. They repeatedly missed
what Basti saw on paper and in the lifted renders: the i1iSis grey steps and
the Knut sky knee (RESUME.md s52, LESSON 2026-10-07). Agent 44 proposed a
wide-scale measure (Findings/agent44-01-exactkeep.md s10.6); Agent 45 used it
on Agent 41's render rows (Experiments/agent45/scripts/even45.py). This module
turns it into scored rows of the property referee (``oogq``).

The measure (Agent 44 s10.6, unchanged):

* pace = dE00 between neighbouring printed points along a source gradient;
* ``evenness_w`` = max |pace smoothed over w of the gradient - median pace| /
  median pace, w = 30 %, the half window at each end dropped (only full
  windows), 0 = perfectly even;
* ``turn_excess`` = the largest angle between the chords over 15 % of the
  gradient before and after a point, minus the source's own (how sharply the
  print bends where the source does not).

The gradients (every source is fixed, so profiles pair):

* grey: sRGB grey codes 0..255;
* grey lifted: the neutral Lab axis L* 0..35 in the lifted view the eye
  judged the dark end in (Agent 41 render.py: L* x3, chroma x2). Unlike
  Agent 41's fixed L* 15-45 window the window starts at the TRUTH's own black
  (the truth gamut's darkest neutral), so a deep-black printer is not judged
  on a clipped band;
* dark: Agent 41's four sRGB colour-to-black ramps (blue, red, brown, green,
  code 0..110), the worst of the four; also lifted;
* sky: Agent 44's sky-blue diagonal (lower left dark and saturated, upper
  right light), with the wide-scale turn and, rel. col. only, the dE00 to the
  source over its in-gamut part (a rounder turn can be bought with in-gamut
  accuracy, as colprof does: Agent 44 s10.2; the battery must show the trade).

Relative colorimetric rows keep only the part of each gradient whose SOURCE
lies at least 1 L* above the truth's black (below it the print is flat at the
black by design); perceptual rows keep the whole gradient (the source black
maps to the printer black and the ramp must still run evenly).

Every key is "lower is better" (``oogq.KEYS``).
"""
from __future__ import annotations

import numpy as np

from benchmarks.research import colour

W_EVEN = 0.30          # smoothing window, share of the gradient (Agent 44 s10.6)
W_TURN = 0.15          # chord length for the turn (Agent 44 s10.6)
W_STEP = 0.04          # narrow window of the step locator (Agent 45 even45.py)
LIFT_SPAN = 30.0       # lifted view: [black, black + 30] L* -> 0..90
DARK_CODE = 110 / 255  # Agent 41 render.py
DARK_COLOURS = {"blue": (0.25, 0.3, 1.0), "red": (1.0, 0.2, 0.15),
                "brown": (0.6, 0.35, 0.15), "green": (0.2, 0.8, 0.3)}
N_RAMP = 560           # Agent 41 render.py W
N_SKY = 401            # Agent 44 skyprofile.py


def smooth(v: np.ndarray, k: int) -> np.ndarray:
    """Moving mean over k samples, edges padded, same length as v."""
    k = max(1, int(k))
    return np.convolve(np.pad(v, k, mode="edge"), np.ones(k) / k, "same")[k:-k]


def pace(P: np.ndarray) -> np.ndarray:
    P = np.asarray(P, float)
    return colour.de2000(P[:-1], P[1:])


def evenness(P: np.ndarray, w: float = W_EVEN) -> float:
    """Agent 44 s10.6: max |pace smoothed over w - median pace| / median pace,
    over the full windows only. NaN when the path does not move."""
    sp = pace(P)
    med = float(np.median(sp))
    if not np.isfinite(med) or med <= 1e-9:
        return float("nan")
    k = max(1, int(w * len(sp)))
    sm = smooth(sp, k)
    h = k // 2
    if h and len(sm) > 2 * h:
        sm = sm[h:-h]
    return float(np.max(np.abs(sm - med)) / med)


def turn(X: np.ndarray, w: float = W_TURN) -> float:
    """Largest angle (deg) between the chords over w of the path before and
    after a point."""
    X = np.asarray(X, float)
    n = max(1, int(w * len(X)))
    if len(X) <= 2 * n:
        return float("nan")
    a = X[n:-n] - X[:-2 * n]
    b = X[2 * n:] - X[n:-n]
    c = (a * b).sum(1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1) + 1e-12)
    return float(np.degrees(np.arccos(np.clip(c, -1, 1))).max())


def step(P: np.ndarray, S: np.ndarray) -> dict:
    """Agent 45's step locator: the largest excess of the pace smoothed over
    4 % over the pace smoothed over 30 % (a band or a step), and where."""
    sp = pace(P)
    med = float(np.median(sp))
    if not np.isfinite(med) or med <= 1e-9:
        return {"step": float("nan"), "step_at": float("nan"),
                "step_src_L": float("nan"), "step_printed_L": float("nan")}
    loc = smooth(sp, int(W_STEP * len(sp))) - smooth(sp, int(W_EVEN * len(sp)))
    i = int(np.argmax(np.abs(loc)))
    return {"step": float(loc[i] / med), "step_at": i / len(sp),
            "step_src_L": float(S[i, 0]), "step_printed_L": float(P[i, 0])}


def wide_rows(P: np.ndarray, S: np.ndarray) -> dict:
    """All wide-scale numbers of one printed gradient P against its source S."""
    P, S = np.asarray(P, float), np.asarray(S, float)
    if len(P) < 10:           # (almost) nothing of the gradient is printable
        return {"evenness_w": float("nan"), "evenness_src": float("nan"),
                "turn_excess": float("nan"), "n": int(len(P))}
    out = {"evenness_w": evenness(P), "evenness_src": evenness(S),
           "turn_excess": turn(P) - turn(S), "n": int(len(P))}
    out.update(step(P, S))
    return out


def lift(lab: np.ndarray, black_l: float) -> np.ndarray:
    """The lifted viewing aid (Agent 41): [black, black + 30] L* -> 0..90,
    chroma x2."""
    o = np.array(lab, float, copy=True)
    o[:, 0] = np.clip((o[:, 0] - black_l) * (90.0 / LIFT_SPAN), 0, 100)
    o[:, 1:] *= 2.0
    return o


# --- the source gradients -----------------------------------------------------------
def grey_rgb() -> np.ndarray:
    v = np.arange(256) / 255.0
    return np.stack([v, v, v], 1)


def neutral_dark_lab() -> np.ndarray:
    t = np.linspace(0, 1, N_RAMP)
    return np.stack([35 * t, 0 * t, 0 * t], 1)


def dark_rgb() -> dict:
    t = np.linspace(0, 1, N_RAMP)
    return {k: np.outer(t * DARK_CODE, c) for k, c in DARK_COLOURS.items()}


def sky_rgb() -> np.ndarray:
    """Agent 44's sky field diagonal (skyprofile.py)."""
    t = np.linspace(0, 1, N_SKY)
    xs, ys = -1 + 2 * t, -0.35 + 0.6 * t
    base = np.array([130, 160, 217]) / 255
    return np.clip(base + xs[:, None] * np.array([0.25, 0.2, 0.1])
                   + ys[:, None] * np.array([0.3, 0.3, 0.2]), 0, 1)


def _keep(S: np.ndarray, intent: str, black_l: float) -> np.ndarray:
    if intent == "p":
        return np.ones(len(S), bool)
    return S[:, 0] >= black_l + 1.0


def _black_l(ctx) -> float:
    g = getattr(ctx, "gamut", None)
    if g is not None:
        return float(g.black_l)
    black = np.full((1, ctx.n), 0.0 if ctx.additive else 1.0)
    if not ctx.additive:
        black[0, 4:] = 0.0
    return float(ctx.truth_lab(black)[0, 0])


def evaluate(ctx, srgb_to_lab=None) -> tuple[dict, dict]:
    """The scored rows ("q") and their detail ("raw") for one profile.

    ``ctx`` is a ``blindspots.hunt.Ctx`` (or anything with ``rgb2dev(src,
    rgb, intent)``, ``lab2dev(lab, intent)``, ``truth_lab(dev)`` and
    ``gamut`` / ``n`` / ``additive``)."""
    if srgb_to_lab is None:
        from benchmarks.research.blindspots import xf
        srgb_to_lab = xf.srgb_to_lab
    blk = _black_l(ctx)
    q: dict = {}
    raw: dict = {"black_L": blk}

    def put(key, val):
        if val is not None and np.isfinite(val):
            q[key] = float(val)

    grey = grey_rgb()
    S_grey = srgb_to_lab(grey)
    neut = neutral_dark_lab()
    ramps = dark_rgb()
    S_ramps = {k: srgb_to_lab(v) for k, v in ramps.items()}
    sky = sky_rgb()
    S_sky = srgb_to_lab(sky)
    for i in ("r", "p"):
        r = {}
        k = _keep(S_grey, i, blk)
        P = ctx.truth_lab(ctx.rgb2dev("srgb", grey, i))
        r["grey"] = wide_rows(P[k], S_grey[k])
        k = _keep(neut, i, blk)
        P = ctx.truth_lab(ctx.lab2dev(neut, i))
        r["grey_lift"] = wide_rows(lift(P[k], blk), lift(neut[k], blk))
        dk, dl = {}, {}
        for nm, rgb in ramps.items():
            S = S_ramps[nm]
            k = _keep(S, i, blk)
            P = ctx.truth_lab(ctx.rgb2dev("srgb", rgb, i))
            dk[nm] = wide_rows(P[k], S[k])
            dl[nm] = wide_rows(lift(P[k], blk), lift(S[k], blk))
        r["dark"], r["dark_lift"] = dk, dl
        P = ctx.truth_lab(ctx.rgb2dev("srgb", sky, i))
        r["sky"] = wide_rows(P, S_sky)
        if i == "r":
            g = getattr(ctx, "gamut", None)
            inside = g.depth(S_sky) > 1.0 if g is not None else np.ones(len(S_sky), bool)
            r["sky"]["in_gamut_share"] = float(inside.mean())
            if inside.any():
                r["sky"]["de_in_gamut"] = float(colour.de2000(P[inside], S_sky[inside]).mean())
        raw[i] = r
        put(f"even_grey_{i}", r["grey"]["evenness_w"])
        put(f"even_grey_lift_{i}", r["grey_lift"]["evenness_w"])
        dv = [v["evenness_w"] for v in dk.values() if np.isfinite(v["evenness_w"])]
        put(f"even_dark_{i}", max(dv) if dv else None)
        dv = [v["evenness_w"] for v in dl.values() if np.isfinite(v["evenness_w"])]
        put(f"even_dark_lift_{i}", max(dv) if dv else None)
        put(f"even_sky_{i}", r["sky"]["evenness_w"])
        put(f"turn_sky_{i}", r["sky"]["turn_excess"])
    put("sky_de_ingamut_r", raw["r"]["sky"].get("de_in_gamut"))
    return q, raw
