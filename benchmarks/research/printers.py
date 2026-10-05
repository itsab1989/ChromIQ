"""Ground-truth printers for the research benchmark (Agent 6).

Two model FAMILIES, so that no forward model can win by sharing the
generator's structure (agent 1's circularity caveat on S3-S7):

* ``YnsnTruth`` re-evaluates the September battery printers S1-S7
  (``benchmarks.synthetic``: Beer-Lambert continuous tone for RGB, Yule-
  Nielsen spectral Neugebauer with Demichel weights and a power-law dot gain
  for inks) on ANY wavelength grid. At the synthetic module's own 10 nm grid
  it reproduces ``SyntheticPrinter.reflectance`` exactly (checked in the
  tests), so September's printers are unchanged; the truth is now
  integrated at 1 nm by :mod:`colour`, not by the engine.

* ``ClapperYuleTruth`` (the "X" printers) is structurally different on every
  axis a model could key on:
    - optics: Clapper-Yule (1953) halftone reflectance with multiple internal
      reflections at the print/air interface (r_i = 0.6) instead of a
      Yule-Nielsen power law;
    - dot gain: per-ink tone-value-increase curves that depend on what the
      ink is printed on (alone vs on other inks), after Hersch et al.'s
      ink-spreading model (JOSA A 2005 / JEI 2006), instead of one global
      gamma per channel;
    - trapping: an ink printed on earlier inks transfers 88 % of its film;
    - different ink spectra: logistic absorption edges (pigment-like), not
      Gaussian dye bands;
    - an RGB variant (X1) is a CMYK halftone printer behind a driver
      separation (UCR/GCR, TAC), which is how real RGB inkjet drivers work,
      instead of a continuous-tone dye stack.

Truth is always ``xyz(device, illuminant)`` at 1 nm (360-830 nm), and the
media-relative Lab the ICC tables store is Bradford(media white -> D50).
Measurement simulation lives in :mod:`noise`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from benchmarks.research import colour
from benchmarks.research.colour import LAM_1NM


def split_letters(rep: str) -> list[str]:
    import re
    letters = re.findall(r"2c|2m|2y|2k|1k|[cmyk]|[A-Z]", rep)
    assert "".join(letters) == rep, rep
    return letters


class TruthPrinter:
    """Interface: ``reflectance(device, lam)`` and everything derived from it."""

    id: str
    device_rep: str
    tac: float | None
    family: str

    @property
    def letters(self) -> list[str]:
        return split_letters(self.device_rep)

    @property
    def n(self) -> int:
        return len(self.letters)

    @property
    def is_additive(self) -> bool:
        return self.device_rep == "RGB"

    @property
    def color_rep(self) -> str:
        return ("iRGB" if self.is_additive else self.device_rep) + "_XYZ"

    def white_device(self) -> np.ndarray:
        return np.full((1, self.n), 1.0 if self.is_additive else 0.0)

    def reflectance(self, device: np.ndarray, lam: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    # -- truth -------------------------------------------------------------
    def xyz(self, device: np.ndarray, illuminant: str = "D50",
            chunk: int = 4096) -> np.ndarray:
        device = np.atleast_2d(np.asarray(device, float))
        out = np.empty((len(device), 3))
        for s in range(0, len(device), chunk):
            r = self.reflectance(device[s:s + chunk], LAM_1NM)
            out[s:s + chunk] = colour.xyz_from_reflectance_1nm(r, illuminant)
        return out

    def lab_rel(self, device: np.ndarray, illuminant: str = "D50") -> np.ndarray:
        """Media-relative Lab (the basis the ICC relative tables store)."""
        white = self.xyz(self.white_device(), illuminant)[0]
        return colour.media_relative_lab(self.xyz(device, illuminant), white)


# ---------------------------------------------------------------------------
# Family 1: the September battery, re-evaluated at any wavelength
# ---------------------------------------------------------------------------

def _band(lam, mu, sigma, peak):
    return peak * np.exp(-(((lam - mu) / sigma) ** 2))


def _ynsn_ink_d(letter: str, lam: np.ndarray) -> np.ndarray:
    # Same constants as benchmarks/synthetic.py::_INK_D (frozen referee).
    if letter == "C":
        return _band(lam, 625.0, 80.0, 1.10) + _band(lam, 680.0, 65.0, 0.35)
    if letter == "M":
        return _band(lam, 530.0, 52.0, 1.10) + _band(lam, 430.0, 36.0, 0.32)
    if letter == "Y":
        return _band(lam, 435.0, 48.0, 1.25) + _band(lam, 490.0, 38.0, 0.26)
    if letter == "K":
        return 1.35 + 0.2 * (lam - 380.0) / 350.0
    if letter == "O":
        return _band(lam, 450.0, 60.0, 1.15) + _band(lam, 515.0, 44.0, 0.62)
    if letter == "G":
        return _band(lam, 445.0, 55.0, 0.85) + _band(lam, 630.0, 70.0, 0.90)
    if letter == "V":
        return _band(lam, 555.0, 65.0, 1.05) + _band(lam, 500.0, 48.0, 0.40)
    raise KeyError(letter)


def _ynsn_paper(kind: str, lam: np.ndarray) -> np.ndarray:
    if kind == "glossy":
        return 0.89 - 0.04 * np.exp(-(((lam - 400.0) / 40.0) ** 2))
    return 0.84 - 0.07 * np.exp(-(((lam - 415.0) / 55.0) ** 2))


class YnsnTruth(TruthPrinter):
    """A ``benchmarks.synthetic.SyntheticPrinter`` evaluated at any lam."""

    family = "ynsn"

    def __init__(self, sp) -> None:
        self.sp = sp
        self.id = sp.id
        self.device_rep = sp.device_rep
        self.tac = sp.tac
        # measurement settings of the September printer (S4: noise_scale 3),
        # honoured by noise.measure since v2 (v1 ignored them: S4 == S3)
        self.noise_scale = float(sp.noise_scale)
        self.misread_prob = float(sp.misread_prob)

    def _ink(self, letter, lam):
        for light, frac in self.sp.light_inks:
            if light == letter:
                parent = "K" if light in ("1k", "2k") else light.upper()
                return frac * _ynsn_ink_d(parent, lam)
        return _ynsn_ink_d(letter, lam)

    def reflectance(self, device, lam):
        sp = self.sp
        device = np.atleast_2d(np.asarray(device, float))
        cov = 1.0 - device if self.is_additive else device
        letters = ["C", "M", "Y"] if self.is_additive else self.letters
        a_eff = np.clip(cov, 0.0, 1.0) ** sp.dot_gain_gamma
        paper = _ynsn_paper(sp.paper, lam)
        if self.is_additive:
            absorb = np.zeros((len(device), len(lam)))
            for i, letter in enumerate(letters):
                absorb += a_eff[:, i:i + 1] * _ynsn_ink_d(letter, lam)[None, :]
            r = paper[None, :] * 10.0 ** (-sp.density_scale * absorb)
        else:
            n = len(letters)
            combos = np.stack(np.meshgrid(*([[0, 1]] * n), indexing="ij"),
                              -1).reshape(-1, n)
            dens = np.stack([self._ink(c, lam) for c in letters])
            prim = paper[None, :] * 10.0 ** (-sp.density_scale * combos @ dens)
            prim_yn = prim ** (1.0 / sp.yn_nu)
            w = _demichel(a_eff, combos)
            r = (w @ prim_yn) ** sp.yn_nu
        if sp.flare:
            r = r + sp.flare * paper[None, :]
        return r


def _demichel(a: np.ndarray, combos: np.ndarray) -> np.ndarray:
    """(N, n) coverages -> (N, 2^n) Demichel weights."""
    w = np.ones((len(a), len(combos)))
    for c in range(a.shape[1]):
        bit = combos[:, c][None, :]
        ac = a[:, c:c + 1]
        w *= np.where(bit == 1, ac, 1.0 - ac)
    return w


# ---------------------------------------------------------------------------
# Family 2: Clapper-Yule with ink spreading and trapping ("X" printers)
# ---------------------------------------------------------------------------

def _edge(lam, at, width, rising=True):
    z = (lam - at) / width
    s = 1.0 / (1.0 + np.exp(-z))
    return s if rising else 1.0 - s


def _cy_ink_d(letter: str, lam: np.ndarray) -> np.ndarray:
    """Double-pass film densities, pigment-like logistic edges."""
    if letter == "C":      # absorbs red; soft blue shoulder
        return 1.45 * _edge(lam, 575.0, 18.0) + 0.18 * _edge(lam, 440.0, 20.0, False)
    if letter == "M":      # absorbs green; unwanted blue absorption
        return (1.40 * _edge(lam, 492.0, 12.0) * _edge(lam, 592.0, 11.0, False)
                + 0.30 * _edge(lam, 455.0, 18.0, False))
    if letter == "Y":      # absorbs blue, sharp edge
        return 1.55 * _edge(lam, 497.0, 9.0, False) + 0.03
    if letter == "K":      # carbon black, slightly bluer absorption
        return 1.70 + 0.12 * (700.0 - lam) / 320.0
    if letter == "O":      # absorbs blue and green
        return 1.30 * _edge(lam, 568.0, 10.0, False)
    if letter == "R":      # absorbs blue and green, edge further out
        return 1.50 * _edge(lam, 598.0, 9.0, False)
    if letter == "G":      # absorbs blue and red
        return (1.20 * _edge(lam, 478.0, 12.0, False)
                + 1.15 * _edge(lam, 585.0, 14.0))
    if letter == "B":      # absorbs green and red
        return 1.30 * _edge(lam, 492.0, 14.0) + 0.05
    if letter == "V":      # absorbs yellow-green
        return 1.25 * _edge(lam, 505.0, 12.0) * _edge(lam, 640.0, 14.0, False)
    raise KeyError(letter)


def _cy_paper(kind: str, lam: np.ndarray) -> np.ndarray:
    if kind == "glossy":      # OBA-free bright coated
        return 0.905 - 0.10 * _edge(lam, 420.0, 12.0, False) - 0.01 * (lam - 400) / 400
    return 0.86 - 0.14 * _edge(lam, 430.0, 15.0, False)   # warm matte


def _tvi(a: np.ndarray, gain: float, skew: float) -> np.ndarray:
    """Monotone tone value increase, peak near mid tone, exact at 0 and 1."""
    g = 4.0 * a * (1.0 - a) * (1.0 + skew * (1.0 - 2.0 * a))
    return np.clip(a + gain * g * (1.0 - a) * 1.4, 0.0, 1.0)


def _cy_ink_d_alt(letter: str, lam: np.ndarray) -> np.ndarray:
    """A second, independent ink set (agent 18b, challenge B2: X9 reused the
    X5/X6 spectra). Different edges, widths and densities for every ink, and
    unwanted absorptions the first set does not have."""
    if letter == "C":      # greener cyan, broader red absorption
        return 1.35 * _edge(lam, 588.0, 24.0) + 0.25 * _edge(lam, 455.0, 25.0, False)
    if letter == "M":      # bluer magenta, wider green band
        return (1.30 * _edge(lam, 482.0, 16.0) * _edge(lam, 605.0, 14.0, False)
                + 0.18 * _edge(lam, 445.0, 20.0, False) + 0.06 * _edge(lam, 640.0, 30.0))
    if letter == "Y":      # warmer yellow, softer edge
        return 1.45 * _edge(lam, 505.0, 14.0, False) + 0.06
    if letter == "K":      # warmer black, more transparent in the red
        return 1.55 - 0.15 * (lam - 380.0) / 320.0
    if letter == "O":      # red-orange, edge far out, some red leak
        return 1.40 * _edge(lam, 585.0, 13.0, False) + 0.10 * _edge(lam, 640.0, 25.0)
    if letter == "G":      # bluish (teal) green
        return (1.05 * _edge(lam, 462.0, 15.0, False)
                + 1.30 * _edge(lam, 570.0, 18.0) + 0.05)
    if letter == "V":      # blue-violet, absorbs green and orange
        return 1.35 * _edge(lam, 498.0, 16.0) * _edge(lam, 625.0, 20.0, False) + 0.08
    raise KeyError(letter)


def _kink(a: np.ndarray, at: float, amp: float) -> np.ndarray:
    """A slope break at ``at`` (a drop-size change in an inkjet driver, an AM
    dot join): continuous, zero at 0 and 1, so solids and paper stay exact.
    No smooth model can absorb it, and a grid that never samples near ``at``
    misses it (challenge S1)."""
    if amp == 0.0:
        return a
    up = np.where(a > at, (a - at) * (1.0 - a) / max(1e-9, (1.0 - at) ** 2), 0.0)
    return np.clip(a + amp * 4.0 * up * (1.0 - at), 0.0, 1.0)


@dataclass(frozen=True)
class ClapperYuleTruth(TruthPrinter):
    id: str
    device_rep: str                   # ink letters, or "RGB" (driver-fed CMYK)
    tac: float | None = None
    paper: str = "glossy"
    r_i: float = 0.6                  # internal reflectance (n = 1.5)
    flare: float = 0.004              # first-surface/scatter floor x paper
    trap: float = 0.88                # film transferred onto earlier inks
    gain_alone: float = 0.17          # TVI of an ink printed on paper
    gain_super: float = 0.09          # TVI of an ink printed on other inks
    light_inks: tuple = ()            # (("c", 0.30), ...) diluted parent
    light_gain: float = 0.22          # light inks spread more (bigger drops)
    inkset: str = "a"                 # "b": _cy_ink_d_alt (agent 18b)
    kink_at: float = 0.45             # TVI slope break (only when kink_amp > 0)
    kink_amp: float = 0.0
    family: str = field(default="clapper-yule", compare=False)

    def _ink_d(self, letter, lam):
        return (_cy_ink_d_alt if self.inkset == "b" else _cy_ink_d)(letter, lam)

    def _ink(self, letter, lam):
        for light, frac in self.light_inks:
            if light == letter:
                return frac * self._ink_d(letter.upper(), lam)
        return self._ink_d(letter, lam)

    def _driver(self, rgb: np.ndarray) -> np.ndarray:
        """RGB driver: complement, black generation above 30 % grey
        component, 75 % UCR, then a 260 % limit (inkjet-driver-like)."""
        cmy = 1.0 - np.clip(rgb, 0, 1)
        grey = cmy.min(1, keepdims=True)
        k = np.clip((grey - 0.30) / 0.70, 0, 1) ** 1.3
        cmy = cmy - 0.75 * k * grey
        dev = np.hstack([cmy, k])
        s = dev.sum(1, keepdims=True)
        return np.where(s > 2.6, dev * 2.6 / np.maximum(s, 1e-9), dev)

    def reflectance(self, device, lam):
        device = np.atleast_2d(np.asarray(device, float))
        if self.is_additive:
            a = self._driver(device)
            letters = ["C", "M", "Y", "K"]
        else:
            a = np.clip(device, 0.0, 1.0)
            letters = self.letters
        n = len(letters)
        light = {l for l, _ in self.light_inks}
        # Ink spreading: each ink's effective coverage mixes its "alone" and
        # "on other inks" curves by the chance the others are underneath.
        eff = np.empty_like(a)
        for i, letter in enumerate(letters):
            others = np.delete(a, i, axis=1)
            p_bare = np.prod(1.0 - others, axis=1) if n > 1 else np.ones(len(a))
            ga = self.light_gain if letter in light else self.gain_alone
            skew = 0.25 - 0.1 * (i % 3)
            eff[:, i] = (p_bare * _tvi(a[:, i], ga, skew)
                         + (1 - p_bare) * _tvi(a[:, i], self.gain_super, skew))
            if self.kink_amp:
                eff[:, i] = _kink(eff[:, i], self.kink_at, self.kink_amp)
        combos = np.stack(np.meshgrid(*([[0, 1]] * n), indexing="ij"),
                          -1).reshape(-1, n)
        dens = np.stack([self._ink(c, lam) for c in letters])     # (n, L)
        # Trapping: the k-th ink laid in a stack transfers trap**(k) of its film.
        order_pos = np.cumsum(combos, axis=1) - combos             # inks below
        film = combos * self.trap ** order_pos
        t = 10.0 ** (-(film @ dens) / 2.0)                         # single pass
        w = _demichel(eff, combos)
        paper = _cy_paper(self.paper, lam)
        ri = self.r_i
        rg = paper / ((1 - ri) + ri * paper)        # substrate so blank = paper
        num = (1 - ri) * rg[None, :] * (w @ t) ** 2
        den = 1.0 - ri * rg[None, :] * (w @ (t ** 2))
        r = num / den
        return r + self.flare * paper[None, :]


# ---------------------------------------------------------------------------
# Agent 13's uneven CMYK printers (K1, 2026-10-04): DEVELOPMENT sets since
# battery v3 (they are known; the sealed Z family is the confirmatory test).
# Definitions copied unchanged from Experiments/agent13/K1_kink_stress.py so
# his numbers reproduce.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HandoffTruth(TruthPrinter):
    """XKH: a CMYK device whose C and M channels a driver splits into a light
    and a dark ink (X8's inks, 30 % dilution): the light ink rises to full
    at device 0.40 and falls to 0.25 at 1.0, the dark ink starts at 0.30."""
    id: str = "XKH"
    device_rep: str = "CMYK"
    tac: float | None = 300.0
    family: str = field(default="clapper-yule-kinked", compare=False)

    @staticmethod
    def split(v):
        light = np.where(v < 0.40, v / 0.40, 1.0 - (v - 0.40) / 0.60 * 0.75)
        dark = np.clip((v - 0.30) / 0.70, 0.0, 1.0)
        return np.clip(light, 0, 1), dark

    def reflectance(self, device, lam):
        d = np.clip(np.atleast_2d(np.asarray(device, float)), 0, 1)
        lc, c = self.split(d[:, 0])
        lm, m = self.split(d[:, 1])
        six = np.stack([c, m, d[:, 2], d[:, 3], lc, lm], 1)   # CMYKcm
        return _X8.reflectance(six, lam)


@dataclass(frozen=True)
class KinkBronzeTruth(TruthPrinter):
    """XKB: X3 behind a piecewise-linear linearisation (slope 0.75 below 50 %,
    1.25 above) plus a reddish bronzing sheen that switches on between 230 %
    and 250 % total ink: the darkest neutral is L* 7.2 near 226 %, the
    stack at 260-300 % prints lighter (a dark end that LIGHTENS)."""
    id: str = "XKB"
    device_rep: str = "CMYK"
    tac: float | None = 300.0
    family: str = field(default="clapper-yule-kinked", compare=False)

    def reflectance(self, device, lam):
        d = np.clip(np.atleast_2d(np.asarray(device, float)), 0, 1)
        lin = np.where(d < 0.5, 0.75 * d, 0.375 + 1.25 * (d - 0.5))
        r = _X3.reflectance(lin, lam)
        tot = d.sum(1)
        s = np.clip((tot - 2.3) / 0.2, 0.0, 1.0)
        s = s * s * (3 - 2 * s)                       # smoothstep, 20 % band
        sheen = 0.035 * (0.3 + 0.7 * d[:, 0]) * s
        spec = 1.0 / (1.0 + np.exp(-(np.asarray(lam) - 600.0) / 25.0))
        return r + sheen[:, None] * (0.3 + 0.7 * spec)[None, :]


_X3 = ClapperYuleTruth("X3", "CMYK", tac=300.0)
_X8 = ClapperYuleTruth("X8", "CMYKcm", tac=320.0, light_inks=(("c", 0.30), ("m", 0.30)))


def build_printers() -> dict[str, TruthPrinter]:
    from benchmarks.synthetic import PRINTERS
    out: dict[str, TruthPrinter] = {k: YnsnTruth(v) for k, v in PRINTERS.items()}
    x = [
        ClapperYuleTruth("X1", "RGB", paper="glossy"),
        ClapperYuleTruth("X3", "CMYK", tac=300.0),
        ClapperYuleTruth("X3m", "CMYK", tac=260.0, paper="matte",
                         gain_alone=0.24, gain_super=0.14),
        ClapperYuleTruth("X5", "CMYKOG", tac=320.0),
        ClapperYuleTruth("X6", "CMYKOV", tac=320.0),
        ClapperYuleTruth("X7", "CMYKRGB", tac=340.0),
        ClapperYuleTruth("X8", "CMYKcm", tac=320.0,
                         light_inks=(("c", 0.30), ("m", 0.30))),
        # agent 18: a 7-ink ECG (CMYKOGV) development printer, the ink set of
        # FOGRA55 and of the owner's own 7-ink test; not in any baseline suite
        ClapperYuleTruth("X9", "CMYKOGV", tac=320.0),
        # agent 18b: INDEPENDENT development printers (challenge B2): a second
        # ink set for every ink, matte paper, more gain, weaker trapping and a
        # kinked TVI (S1). X10 = 7 inks (CMYKOGV), X11 = CMY (no K), X12 = CMYK.
        ClapperYuleTruth("X10", "CMYKOGV", tac=300.0, paper="matte", inkset="b",
                         gain_alone=0.22, gain_super=0.12, trap=0.82,
                         kink_at=0.42, kink_amp=0.05),
        ClapperYuleTruth("X11", "CMY", tac=260.0, paper="matte", inkset="b",
                         gain_alone=0.22, gain_super=0.12, trap=0.82,
                         kink_at=0.42, kink_amp=0.05),
        ClapperYuleTruth("X12", "CMYK", tac=300.0, paper="matte", inkset="b",
                         gain_alone=0.22, gain_super=0.12, trap=0.82,
                         kink_at=0.42, kink_amp=0.05),
    ]
    out.update({p.id: p for p in x})
    # battery v3: Agent 13's uneven printers, development
    out.update({"XKH": HandoffTruth(), "XKB": KinkBronzeTruth()})
    return out
