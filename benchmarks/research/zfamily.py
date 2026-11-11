"""Family 3 of the research battery: the "Z" printers (battery v3, Agent 16).

The sealed confirmatory set is drawn from THIS model with a secret seed
(:mod:`sealed`). The model is public so that it can be reviewed; only the
drawn instances are secret. It shares no structural element with the two
families every engine agent has looked at for months:

=================  =========================  ============================  ==============================
                   S family (YNSN)            X family (Clapper-Yule)        Z family (this file)
=================  =========================  ============================  ==============================
ink spectra        Gaussian dye bands          logistic pigment edges         generalised-Lorentzian bands
                                                                              (random centre, width, tail)
                                                                              + Kubelka-Munk scattering
film optics        Beer-Lambert                Beer-Lambert, trapping 88 %    Kubelka-Munk two-flux film over
                                                                              the substrate, inks MIX in one
                                                                              film (no layer order)
surface            none (flare)                Clapper-Yule internal          Saunderson correction, with a
                                               reflections (r_i 0.6)          coverage-dependent surface term
                                                                              (gloss differential, bronzing)
halftone mixing    Yule-Nielsen, Demichel      Clapper-Yule, Demichel         Arney probability model (lateral
                                                                              light scattering, p0) over a
                                                                              MIX of Demichel and dot-off-dot
                                                                              placement
dot gain           one power law per printer   smooth polynomial per ink,     per-ink bump curve with a
                                               alone vs on other inks         minimum printable dot, an
                                                                              optional screen-change jump and
                                                                              an optional linearisation kink
uneven behaviour   none                        none                           light-ink hand-offs behind a
                                                                              device channel, dark ends that
                                                                              LIGHTEN (ink pooling), bronzing,
                                                                              optical brightener in the paper
RGB                continuous-tone dye stack   CMYK behind a fixed driver     CMYK(+light inks) behind a
                                                                              randomised driver (GCR start,
                                                                              strength, ink limit, tone curves)
=================  =========================  ============================  ==============================

Everything a printer instance needs is one JSON-able dict of parameters
(``ZTruth(params)``); :func:`draw_params` draws it for a slot from a numpy
Generator. What the distributions are is visible here; which values a sealed
instance got is not.

Truth is reflectance at 1 nm (360-830 nm), so ``TruthPrinter.xyz`` and
``lab_rel`` apply unchanged. The optical brightener makes the apparent
reflectance of bare paper exceed 1 in the blue (fluorescence under D50, as an
M1 instrument reports it); every other value stays in [0, 1].
"""
from __future__ import annotations

import itertools
import math

import numpy as np

from benchmarks.research.printers import TruthPrinter, split_letters

ZFAMILY_VERSION = "z1"

# ---------------------------------------------------------------------------
# Ink absorption: generalised Lorentzian bands
# ---------------------------------------------------------------------------

# Per ink: list of bands (centre range nm, half-width range nm, strength
# range, tail exponent range). The tail exponent p shapes the band:
# 1 = Lorentzian (long tails), 3-4 = steep shoulders (pigment yellow edge).
INK_BANDS = {
    "C": [((605, 640), (55, 85), (1.6, 2.3), (1.2, 2.5)),
          ((680, 720), (30, 60), (0.2, 0.6), (1.0, 2.0))],
    "M": [((525, 560), (35, 55), (1.7, 2.4), (1.3, 2.8)),
          ((400, 440), (25, 45), (0.1, 0.5), (1.0, 2.0))],
    "Y": [((425, 455), (42, 62), (1.8, 2.6), (2.5, 4.0))],
    "O": [((465, 505), (45, 70), (1.5, 2.2), (2.0, 3.5))],
    "R": [((495, 540), (45, 70), (1.5, 2.2), (2.0, 3.5))],
    "G": [((420, 450), (30, 50), (1.3, 1.9), (1.5, 3.0)),
          ((610, 650), (45, 75), (1.3, 2.0), (1.2, 2.5))],
    "B": [((570, 610), (50, 80), (1.5, 2.2), (1.3, 2.5))],
    "V": [((555, 590), (40, 65), (1.5, 2.1), (1.3, 2.5)),
          ((640, 680), (30, 50), (0.2, 0.6), (1.0, 2.0))],
}
# Black: flat absorption with a slope and two weak bumps.
K_LEVEL = (1.9, 2.7)
K_SLOPE = (-0.25, 0.15)                 # per 350 nm, + = more absorption in the red
LIGHT_DILUTION = (0.18, 0.40)           # light ink = parent at this concentration
LAM_MIN, LAM_MAX = 360.0, 830.0


def _glorentz(lam, centre, width, strength, p):
    return strength / (1.0 + ((lam - centre) / width) ** 2) ** p


def ink_absorption(ink: dict, lam: np.ndarray) -> np.ndarray:
    """K(lam) of one ink from its drawn parameters (film units)."""
    if ink["kind"] == "black":
        x = (lam - 380.0) / 350.0
        k = ink["level"] + ink["slope"] * x
        for c, w, s in ink["bumps"]:
            k = k + _glorentz(lam, c, w, s, 1.5)
        return np.clip(k, 0.05, None)
    k = np.zeros_like(lam, dtype=float)
    for c, w, s, p in ink["bands"]:
        k = k + _glorentz(lam, c, w, s, p)
    return k * ink.get("dilution", 1.0) + ink.get("floor", 0.0)


def ink_scattering(ink: dict, lam: np.ndarray) -> np.ndarray:
    """S(lam) of the ink's pigment (0 for a dye)."""
    s0, beta = ink.get("s0", 0.0), ink.get("beta", 1.0)
    return s0 * (lam / 550.0) ** (-beta) * ink.get("dilution", 1.0)


# ---------------------------------------------------------------------------
# Kubelka-Munk film over a substrate (written so that S -> 0 is stable)
# ---------------------------------------------------------------------------

def km_film(K: np.ndarray, S: np.ndarray, Rg: np.ndarray) -> np.ndarray:
    """Reflectance of a KM layer (thickness folded into K, S) over a
    background of reflectance Rg; the S -> 0 limit is Rg exp(-2K)."""
    S = np.maximum(S, 1e-6)
    bS = np.sqrt(K * K + 2.0 * K * S)                    # b * S * X
    coth = 1.0 / np.tanh(np.maximum(bS, 1e-9))
    bc = bS * coth                                        # b S coth(b S X)
    num = S - Rg * (K + S - bc)
    den = K + S - Rg * S + bc
    return np.clip(num / den, 0.0, 1.0)


def saunderson(R: np.ndarray, k1: np.ndarray, k2: float) -> np.ndarray:
    """Body reflectance -> measured reflectance (surface correction)."""
    return k1 + (1.0 - k1) * (1.0 - k2) * R / (1.0 - k2 * R)


def body_from_measured(Rm: np.ndarray, k1: float, k2: float) -> np.ndarray:
    """Inverse Saunderson: the body reflectance that measures as Rm."""
    x = (Rm - k1) / ((1.0 - k1) * (1.0 - k2))
    return np.clip(x / (1.0 + k2 * x), 0.0, 0.999)


# ---------------------------------------------------------------------------
# Halftone placement: Demichel mixed with dot-off-dot
# ---------------------------------------------------------------------------

def demichel(a: np.ndarray, combos: np.ndarray) -> np.ndarray:
    w = np.ones((len(a), len(combos)))
    for c in range(a.shape[1]):
        bit = combos[:, c][None, :]
        ac = a[:, c:c + 1]
        w *= np.where(bit == 1, ac, 1.0 - ac)
    return w


def dot_off_dot(a: np.ndarray, n_combos: int) -> np.ndarray:
    """Minimum-overlap placement: ink i fills the arc [S_(i-1), S_i) of a
    unit circle (S = cumulative coverage), so inks first share bare paper
    and overlap only once the total passes 100 %, as inkjet masks and
    dot-off-dot screens place them. Exact area of every ink combination."""
    N, n = a.shape
    a = np.clip(a, 0.0, 1.0)
    S = np.concatenate([np.zeros((N, 1)), np.cumsum(a, 1)], 1)
    brk = np.sort(np.concatenate([np.mod(S, 1.0), np.zeros((N, 1)),
                                  np.ones((N, 1))], 1), 1)
    lo, hi = brk[:, :-1], brk[:, 1:]
    width = hi - lo
    mid = 0.5 * (lo + hi)
    code = np.zeros(mid.shape, dtype=np.int64)
    for i in range(n):
        inside = np.mod(mid - S[:, i:i + 1], 1.0) < a[:, i:i + 1]
        inside |= a[:, i:i + 1] >= 1.0 - 1e-12
        # combos are enumerated with the FIRST ink as the most significant bit
        code += inside.astype(np.int64) << (n - 1 - i)
    w = np.zeros((N, n_combos))
    rows = np.repeat(np.arange(N), mid.shape[1])
    np.add.at(w, (rows, code.ravel()), width.ravel())
    return w


def all_combos(n: int) -> np.ndarray:
    return np.array(list(itertools.product([0, 1], repeat=n)), dtype=float)


# ---------------------------------------------------------------------------
# Tone response: device value -> physical coverage
# ---------------------------------------------------------------------------

def tone(d: np.ndarray, t: dict) -> np.ndarray:
    """Mechanical + optical-free dot gain of one ink. Features (each drawn
    per ink): a linearisation kink, a minimum printable dot (no dot forms
    below it: a jump), a screen change (the gain steps up by ``jump``)."""
    d = np.clip(d, 0.0, 1.0)
    if t.get("kink"):
        k, s1 = t["kink"]
        s2 = (1.0 - s1 * k) / (1.0 - k)
        d = np.clip(np.where(d < k, s1 * d, s1 * k + s2 * (d - k)), 0.0, 1.0)
    al, be = t["shape"]
    peak = (al / (al + be)) ** al * (be / (al + be)) ** be
    bump = d ** al * (1.0 - d) ** be / peak
    a = d + t["gain"] * bump * (1.0 - d) * 0.9
    if t.get("screen"):
        at, jump = t["screen"]
        # the step fades out toward the solid so a stays <= 1 and monotone
        a = a + jump * np.clip((d - at) / 0.02, 0.0, 1.0) * (1.0 - d) / (1.0 - at)
    if t.get("min_dot"):
        a = np.where(d < t["min_dot"], 0.0, a)
    return np.clip(a, 0.0, 1.0)


def handoff(v: np.ndarray, h: dict) -> tuple[np.ndarray, np.ndarray]:
    """A device channel split into (light ink, dark ink) amounts by a
    driver: the light ink rises to full at ``peak``, then falls to
    ``residual`` at 1; the dark ink starts at ``onset`` with a smooth or a
    sharp shoulder (``power``)."""
    v = np.clip(v, 0.0, 1.0)
    pk, res, on, pw = h["peak"], h["residual"], h["onset"], h["power"]
    light = np.where(v < pk, v / pk, 1.0 - (v - pk) / (1.0 - pk) * (1.0 - res))
    dark = np.clip((v - on) / (1.0 - on), 0.0, 1.0) ** pw
    return np.clip(light, 0.0, 1.0), dark


# ---------------------------------------------------------------------------
# The printer
# ---------------------------------------------------------------------------

class ZTruth(TruthPrinter):
    """A Z-family printer from its parameter dict (see ``draw_params``)."""

    family = "z-km-arney"

    def __init__(self, params: dict):
        self.params = params
        self.id = params["id"]
        self.device_rep = params["device_rep"]
        self.tac = params.get("tac")
        self.noise_scale = float(params.get("noise_scale", 1.0))
        self.misread_prob = float(params.get("misread_prob", 0.004))
        self._inks = params["inks"]               # physical inks, in order
        self._phys = [i["letter"] for i in self._inks]
        self._combos = all_combos(len(self._phys))
        self._cache: dict = {}

    # -- device -> physical ink amounts -----------------------------------
    def physical_amounts(self, device: np.ndarray) -> np.ndarray:
        """(N, n_device) device values -> (N, n_physical) coverages."""
        p = self.params
        d = np.clip(np.atleast_2d(np.asarray(device, float)), 0.0, 1.0)
        if self.is_additive:
            d = self._driver(d)
        dev_letters = ["C", "M", "Y", "K"] if self.is_additive else self.letters
        amounts = {}
        for j, letter in enumerate(dev_letters):
            h = p.get("handoff", {}).get(letter)
            if h:
                light, dark = handoff(d[:, j], h)
                amounts[letter.lower() + "~"] = light
                amounts[letter] = dark
            else:
                amounts[letter] = d[:, j]
        out = np.zeros((len(d), len(self._phys)))
        for i, ink in enumerate(self._inks):
            src = ink["source"]
            if src in amounts:
                out[:, i] = tone(amounts[src], ink["tone"])
        return out

    def _driver(self, rgb: np.ndarray) -> np.ndarray:
        dr = self.params["driver"]
        cmy = 1.0 - np.clip(rgb, 0, 1) ** dr["gamma"]
        for c in range(3):
            g = dr["curves"][c]
            cmy[:, c] = np.clip(cmy[:, c] + g * np.sin(np.pi * cmy[:, c]) * 0.08, 0, 1)
        grey = cmy.min(1, keepdims=True)
        k = np.clip((grey - dr["gcr_start"]) / (1.0 - dr["gcr_start"]), 0, 1) ** dr["k_power"]
        cmy = cmy - dr["ucr"] * k * grey
        dev = np.hstack([np.clip(cmy, 0, 1), k])
        s = dev.sum(1, keepdims=True)
        lim = dr["tac"] / 100.0
        return np.where(s > lim, dev * lim / np.maximum(s, 1e-9), dev)

    # -- spectra ----------------------------------------------------------
    def _spectra(self, lam: np.ndarray):
        key = (len(lam), float(lam[0]), float(lam[-1]))
        if key not in self._cache:
            p = self.params
            K = np.stack([ink_absorption(i, lam) * i["film"] for i in self._inks])
            S = np.stack([ink_scattering(i, lam) * i["film"] for i in self._inks])
            pap = p["paper"]
            Rm = (pap["level"] - pap["blue_dip"] * np.exp(-((lam - pap["dip_at"]) / pap["dip_w"]) ** 2)
                  + pap["tilt"] * (lam - 560.0) / 300.0)
            Rm = np.clip(Rm, 0.05, 0.97)
            Rg = body_from_measured(Rm, pap["k1"], pap["k2"])
            uv = (lam >= 360.0) & (lam <= 390.0)
            oba = pap.get("oba", 0.0) * np.exp(-0.5 * ((lam - pap.get("oba_at", 440.0)) / 22.0) ** 2)
            surf = p.get("surface", {})
            bronze = None
            if surf.get("bronze"):
                b = surf["bronze"]
                bronze = b["amp"] / (1.0 + np.exp(-(lam - b["at"]) / b["width"]))
            self._cache[key] = (K, S, Rg, uv, oba, bronze)
        return self._cache[key]

    def reflectance(self, device, lam):
        p = self.params
        lam = np.asarray(lam, float)
        a = self.physical_amounts(device)                      # (N, n)
        K, S, Rg, uv, oba, bronze = self._spectra(lam)
        pap = p["paper"]
        combos = self._combos
        m = combos.sum(1)                                      # inks per primary
        # pooling: a primary carrying more than ``pool_from`` films of ink
        # does not get darker in proportion; the excess raises scattering
        # (the dark end LIGHTENS when pool_scatter is large)
        pool = p.get("pooling") or {}
        excess = np.clip(m - pool.get("from", 99.0), 0.0, None)
        squash = 1.0 / (1.0 + pool.get("squash", 0.0) * excess)
        Kc = (combos * squash[:, None]) @ K                     # (2^n, L)
        Sc = (combos * squash[:, None]) @ S + p["vehicle_s"] * np.minimum(m, 1)[:, None] \
            + pool.get("scatter", 0.0) * excess[:, None]
        Rc = km_film(Kc, Sc, Rg[None, :])                      # body reflectance per primary
        mix = p["placement"]["dod"]
        w = (1.0 - mix) * demichel(a, combos) + mix * dot_off_dot(a, len(combos))
        t = np.sqrt(np.clip(Rc / Rg[None, :], 0.0, 1.0))         # two-way film factor
        p0 = p["p0"]
        Rb = Rg[None, :] * (p0 * (w @ (t * t)) + (1.0 - p0) * (w @ t) ** 2)
        # surface: paper k1, ink k1 (gloss differential), bronzing on
        # cyan/black-rich multi-ink primaries
        k1p = pap["k1"]
        cov = a.max(1) if a.shape[1] else np.zeros(len(a))
        k1 = k1p + (p["surface"].get("ink_k1", k1p) - k1p) * np.clip(a.sum(1), 0, 1)[:, None]
        if bronze is not None:
            idx = [i for i, ink in enumerate(self._inks) if ink["letter"] in ("C", "K", "B")]
            heavy = (m >= 2).astype(float)
            share = (combos[:, idx].max(1) if idx else np.zeros(len(combos))) * heavy
            k1 = k1 + (w @ share)[:, None] * bronze[None, :]
        R = saunderson(Rb, k1, pap["k2"])
        if np.any(oba):
            uvt = (w @ (t[:, uv].mean(1) ** 2 if uv.any() else np.ones(len(combos))))
            R = R + uvt[:, None] * oba[None, :]
        del cov
        return R


# ---------------------------------------------------------------------------
# Drawing an instance
# ---------------------------------------------------------------------------

# Feature probabilities: what may appear in a sealed instance. Public, so a
# reviewer can see the set is not designed against one engine; whether a
# given sealed printer has a feature is secret.
FEATURES = {
    "min_dot": 0.6,          # per ink: no dot below 1-4 %
    "screen": 0.35,          # per ink: gain steps up at 6-25 %
    "kink": 0.35,            # per ink: linearisation kink at 30-70 %
    "handoff": 0.6,          # CMYK/RGB devices: hidden light inks behind C and M
    "pooling": 0.55,         # ink devices: dark end lightens above 2-3 overprints
    "bronze": 0.45,          # surface: bronzing on cyan/black-rich stacks
    "oba": 0.5,              # paper: optical brightener
    "pigment": 0.6,          # pigment inks (KM scattering) rather than dyes
}


def _u(rng, lo_hi):
    lo, hi = lo_hi
    return float(rng.uniform(lo, hi))


def _draw_ink(rng, letter: str, pigment: bool, light: bool = False) -> dict:
    parent = letter.upper()
    if parent == "K":
        ink = {"kind": "black", "level": _u(rng, K_LEVEL), "slope": _u(rng, K_SLOPE),
               "bumps": [[_u(rng, (420, 680)), _u(rng, (30, 80)), _u(rng, (0.0, 0.12))]
                         for _ in range(2)]}
    else:
        ink = {"kind": "colour",
               "bands": [[_u(rng, c), _u(rng, w), _u(rng, s), _u(rng, p)]
                         for c, w, s, p in INK_BANDS[parent]],
               "floor": _u(rng, (0.0, 0.04))}
    if light:
        ink["dilution"] = _u(rng, LIGHT_DILUTION)
    if pigment:
        ink["s0"] = _u(rng, (0.02, 0.14))
        ink["beta"] = _u(rng, (0.5, 2.0))
    ink["film"] = _u(rng, (0.9, 1.25))
    t = {"gain": _u(rng, (0.06, 0.26)), "shape": [_u(rng, (0.8, 1.6)), _u(rng, (0.9, 1.8))]}
    if rng.uniform() < FEATURES["min_dot"]:
        t["min_dot"] = _u(rng, (0.01, 0.04))
    if rng.uniform() < FEATURES["screen"]:
        t["screen"] = [_u(rng, (0.06, 0.25)), _u(rng, (0.015, 0.06))]
    if rng.uniform() < FEATURES["kink"]:
        t["kink"] = [_u(rng, (0.3, 0.7)), _u(rng, (0.6, 0.9))]
    ink["tone"] = t
    return ink


def draw_params(rng: np.random.Generator, slot: dict) -> dict:
    """One printer instance for ``slot`` ({"id", "device_rep", "tac",
    "paper": "glossy"|"matte"|"any"}). All randomness comes from ``rng``."""
    rep = slot["device_rep"]
    additive = rep == "RGB"
    letters = ["C", "M", "Y", "K"] if additive else split_letters(rep)
    pigment = bool(rng.uniform() < FEATURES["pigment"])
    paper_kind = slot.get("paper", "any")
    if paper_kind == "any":
        paper_kind = "glossy" if rng.uniform() < 0.55 else "matte"
    glossy = paper_kind == "glossy"
    paper = {"kind": paper_kind,
             "level": _u(rng, (0.86, 0.93) if glossy else (0.80, 0.90)),
             "blue_dip": _u(rng, (0.02, 0.10)), "dip_at": _u(rng, (395, 430)),
             "dip_w": _u(rng, (25, 55)), "tilt": _u(rng, (-0.03, 0.03)),
             "k1": _u(rng, (0.002, 0.008) if glossy else (0.012, 0.026)),
             "k2": _u(rng, (0.45, 0.62))}
    if rng.uniform() < FEATURES["oba"]:
        paper["oba"] = _u(rng, (0.04, 0.12))
        paper["oba_at"] = _u(rng, (432, 448))
    params = {"id": slot["id"], "device_rep": rep, "version": ZFAMILY_VERSION,
              "tac": slot.get("tac"), "paper": paper, "pigment": pigment,
              "p0": _u(rng, (0.25, 0.8)), "vehicle_s": _u(rng, (0.0, 0.05)),
              "placement": {"dod": _u(rng, (0.2, 0.85))},
              "surface": {"ink_k1": paper["k1"] * _u(rng, (0.5, 1.5))}}
    inks = []
    handoffs = {}
    # hidden light inks behind C and M (driver split), CMYK and RGB devices
    hidden = (additive or rep == "CMYK") and rng.uniform() < FEATURES["handoff"]
    for letter in letters:
        if letter.islower():                      # an explicit light ink channel
            ink = _draw_ink(rng, letter, pigment, light=True)
            ink.update(letter=letter, source=letter)
            inks.append(ink)
            continue
        ink = _draw_ink(rng, letter, pigment)
        ink.update(letter=letter, source=letter)
        inks.append(ink)
        if hidden and letter in ("C", "M"):
            lt = _draw_ink(rng, letter.lower(), pigment, light=True)
            lt.update(letter=letter.lower(), source=letter.lower() + "~")
            inks.append(lt)
            handoffs[letter] = {"peak": _u(rng, (0.25, 0.55)),
                                "residual": _u(rng, (0.0, 0.5)),
                                "onset": _u(rng, (0.12, 0.40)),
                                "power": _u(rng, (0.8, 1.8))}
    # light ink drawn from its parent's bands: copy the parent's colour so
    # a light cyan is a dilute version of THIS printer's cyan
    by_letter = {i["letter"]: i for i in inks}
    for ink in inks:
        if ink["letter"].islower() and ink["letter"].upper() in by_letter:
            parent = by_letter[ink["letter"].upper()]
            for k in ("bands", "level", "slope", "bumps", "kind", "floor"):
                if k in parent:
                    ink[k] = parent[k]
    params["inks"] = inks
    if handoffs:
        params["handoff"] = handoffs
    if not additive and rng.uniform() < FEATURES["pooling"]:
        params["pooling"] = {"from": float(rng.choice([2.0, 3.0])),
                             "squash": _u(rng, (0.05, 0.3)),
                             "scatter": _u(rng, (0.01, 0.08))}
    if rng.uniform() < FEATURES["bronze"]:
        params["surface"]["bronze"] = {"amp": _u(rng, (0.006, 0.035)),
                                       "at": _u(rng, (540, 640)),
                                       "width": _u(rng, (12, 35))}
    if additive:
        params["driver"] = {"gamma": _u(rng, (0.85, 1.25)),
                            "curves": [_u(rng, (-1.0, 1.0)) for _ in range(3)],
                            "gcr_start": _u(rng, (0.15, 0.5)),
                            "ucr": _u(rng, (0.4, 0.95)),
                            "k_power": _u(rng, (0.9, 1.6)),
                            "tac": _u(rng, (220.0, 290.0))}
    params["noise_scale"] = _u(rng, (0.8, 1.5))       # instrument class
    params["misread_prob"] = _u(rng, (0.0, 0.006))
    params["field"] = {"amp": _u(rng, (0.002, 0.008)),      # print non-uniformity
                       "sheet": _u(rng, (0.0, 0.004)),
                       "seed": int(rng.integers(0, 2 ** 31 - 1))}
    return params


def print_field(params: dict, n_rows: int, per_page: int = 560,
                strip_len: int = 15) -> np.ndarray:
    """Multiplicative reflectance gain per chart row: a smooth field over
    each printed page (patches laid out in strips) plus a per-sheet offset.
    Real prints are not uniform; this is error the profile must average,
    not model (the truth is the uniform printer)."""
    f = params.get("field") or {}
    if not f:
        return np.ones(n_rows)
    rng = np.random.default_rng(f["seed"])
    idx = np.arange(n_rows)
    page = idx // per_page
    pos = idx % per_page
    x = (pos // strip_len) / max(1.0, per_page / strip_len - 1)   # across strips
    y = (pos % strip_len) / (strip_len - 1)                         # along a strip
    out = np.ones(n_rows)
    for pg in np.unique(page):
        c = rng.normal(size=6)
        m = page == pg
        fx, fy = x[m], y[m]
        g = (c[0] * fx + c[1] * fy + c[2] * fx * fy
             + c[3] * np.cos(np.pi * fx) + c[4] * np.cos(np.pi * fy)) / 3.0
        out[m] = 1.0 + f["amp"] * g + f["sheet"] * c[5]
    return out


def canonical(params: dict) -> str:
    """Canonical JSON of a parameter dict (for hashing)."""
    import json

    def norm(o):
        if isinstance(o, float):
            return float(repr(o)) if math.isfinite(o) else str(o)
        if isinstance(o, dict):
            return {k: norm(v) for k, v in sorted(o.items())}
        if isinstance(o, (list, tuple)):
            return [norm(v) for v in o]
        if isinstance(o, np.generic):
            return norm(o.item())
        return o
    return json.dumps(norm(params), sort_keys=True, separators=(",", ":"))
