"""Synthetic ground-truth printers S1–S6 (issue #123, W0).

Each printer is an *analytic* spectral device model — reflectance from a
Beer–Lambert ink stack on a paper spectrum, XYZ by CIE 15 integration —
so ``f_true(device) → XYZ`` is known exactly at any point, not just at
chart patches. A built profile is then scored against ``f_true`` on dense
quasi-random evaluation points, which no chart-based referee can do.

The model is deliberately *not* the engine's own model family (the engine
fits a shaped multilinear grid; this is a smooth nonlinear spectral
product), so a candidate cannot win by matching the referee's inductive
bias.

Instrument noise (applied to the "measured" chart only, never to the
referee): heteroscedastic XYZ noise σ(Y) = 0.015 + 0.025·exp(−Y/8) —
i1-class repeatability (≈0.03 ΔE00 on light patches, up to ≈0.8 on the
deepest blacks; the first draft's 0.05+0.10 amplitudes put ~3 ΔE00 of
noise on dark patches, which no working instrument shows) — plus a
misread probability (default 0.5 %) that smudges a patch by a uniform
5–40 ΔE in a random Lab direction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from workflow.profile_engine.icc_writer import BRADFORD
from workflow.profile_engine.spectral import spectra_to_xyz
from workflow.profile_engine.ti3_data import (D50_XYZ100, lab_to_xyz,
                                              xyz_to_lab)

LAM = np.arange(380.0, 731.0, 10.0)          # 36 bands, 380–730 nm


def _band(mu: float, sigma: float, peak: float) -> np.ndarray:
    """Gaussian spectral absorbance band on the LAM grid."""
    return peak * np.exp(-(((LAM - mu) / sigma) ** 2))


# Ink absorbance spectra D_c(λ): total effective density at full coverage
# (double light path through the ink film folded in). Sums of Gaussian
# bands — the classic dye-absorption shapes. Densities are calibrated so a
# 900-patch chart fits a -qm grid at the residual level REAL charts show
# (median ≈ 0.3–0.7 ΔE00): a referee much curvier than any physical
# printer would score model error, not algorithm quality. Calibrated once
# against realism, then frozen — never against a candidate.
_INK_D = {
    "C": _band(625.0, 80.0, 1.10) + _band(680.0, 65.0, 0.35),
    "M": _band(530.0, 52.0, 1.10) + _band(430.0, 36.0, 0.32),
    "Y": _band(435.0, 48.0, 1.25) + _band(490.0, 38.0, 0.26),
    "K": 1.35 + 0.2 * (LAM - 380.0) / 350.0,     # broadband, slight tilt
    "O": _band(450.0, 60.0, 1.15) + _band(515.0, 44.0, 0.62),
    "G": _band(445.0, 55.0, 0.85) + _band(630.0, 70.0, 0.90),
    # Violet for S6: band placed so the solid's hue lands well OFF the
    # engine's 300° anchor (tests the measured-hue path).
    "V": _band(555.0, 65.0, 1.05) + _band(500.0, 48.0, 0.40),
}


def _paper(kind: str) -> np.ndarray:
    """Paper reflectance spectrum: bright glossy vs warmer matte."""
    if kind == "glossy":
        base = 0.89 - 0.04 * np.exp(-(((LAM - 400.0) / 40.0) ** 2))
    else:                                        # matte, warmer
        base = 0.84 - 0.07 * np.exp(-(((LAM - 415.0) / 55.0) ** 2))
    return base


@dataclass(frozen=True)
class SyntheticPrinter:
    """One analytic ground-truth device."""

    id: str
    device_rep: str                  # "RGB", "CMYK", "CMYKOG", "CMYKV"
    paper: str = "glossy"
    dot_gain_gamma: float = 0.85     # a_eff = a**γ (γ<1 = midtones darken)
    # First-surface/scattering floor (× paper reflectance). Even glossy
    # stock reflects ~0.6 % at the surface under 0/45 geometry — without
    # it, deep TAC blacks reach L*≈1 with a curvature no physical print
    # shows (and no realistic referee should score).
    flare: float = 0.006
    tac: float | None = None         # total ink limit in percent
    noise_scale: float = 1.0         # multiplies the standard σ(Y)
    misread_prob: float = 0.005
    density_scale: float = 1.0       # global ink strength
    # Halftone mixing (ink-count devices): Yule–Nielsen n-factor. Inkjets
    # are halftone devices — area-coverage mixing with optical dot gain —
    # not continuous dye stacks; pure Beer–Lambert overstates channel
    # interaction so much that even colprof -qm fits it at avg ≈ 2.8 ΔE,
    # which no physical CMYK chart shows. RGB-driver printers (S1/S2)
    # keep the continuous-tone model (photo pipelines behave that way).
    yn_nu: float = 4.0

    @property
    def channel_letters(self) -> list[str]:
        return list(self.device_rep)

    @property
    def n_channels(self) -> int:
        return len(self.device_rep)

    @property
    def is_additive(self) -> bool:
        return self.device_rep == "RGB"

    @property
    def color_rep(self) -> str:
        return ("iRGB" if self.is_additive else self.device_rep) + "_XYZ"

    # -- ground truth ------------------------------------------------------
    def reflectance(self, device: np.ndarray) -> np.ndarray:
        """(N, n) device fractions 0..1 → (N, bands) true reflectance."""
        device = np.atleast_2d(np.asarray(device, float))
        cov = 1.0 - device if self.is_additive else device
        letters = ["C", "M", "Y"] if self.is_additive else self.channel_letters
        a_eff = np.clip(cov, 0.0, 1.0) ** self.dot_gain_gamma
        paper = _paper(self.paper)
        if self.is_additive:
            # Continuous-tone dye model (RGB photo pipeline).
            absorb = np.zeros((len(device), len(LAM)))
            for i, letter in enumerate(letters):
                absorb += a_eff[:, i:i + 1] * _INK_D[letter][None, :]
            r = paper[None, :] * 10.0 ** (-self.density_scale * absorb)
        else:
            # Halftone: Yule–Nielsen spectral Neugebauer over the 2ⁿ
            # solid-overprint primaries with Demichel area weights.
            n = len(letters)
            combos = np.stack(np.meshgrid(*([[0, 1]] * n), indexing="ij"),
                              -1).reshape(-1, n)
            dens = np.stack([_INK_D[c] for c in letters])      # (n, bands)
            prim = paper[None, :] * 10.0 ** (
                -self.density_scale * combos @ dens)           # (2ⁿ, bands)
            prim_yn = prim ** (1.0 / self.yn_nu)
            mix = np.zeros((len(device), len(LAM)))
            for p, bits in enumerate(combos):
                w = np.ones(len(device))
                for c, bit in enumerate(bits):
                    w = w * (a_eff[:, c] if bit else 1.0 - a_eff[:, c])
                mix += w[:, None] * prim_yn[p][None, :]
            r = mix ** self.yn_nu
        if self.flare:
            r = r + self.flare * paper[None, :]
        return r

    def xyz_true(self, device: np.ndarray) -> np.ndarray:
        """Exact XYZ (Y=100 scale, D50/2°) — the referee's answer."""
        return spectra_to_xyz(self.reflectance(device), LAM)

    def lab_relative_true(self, device: np.ndarray) -> np.ndarray:
        """Media-relative Lab — the basis the profile LUTs store."""
        white = self.xyz_true(self._white_device())
        return xyz_to_lab(_bradford_to_d50(self.xyz_true(device), white[0]))

    def _white_device(self) -> np.ndarray:
        w = 1.0 if self.is_additive else 0.0
        return np.full((1, self.n_channels), w)


def _bradford_to_d50(xyz: np.ndarray, white: np.ndarray) -> np.ndarray:
    """The same media-white → D50 adaptation Ti3Measurement applies."""
    cone = BRADFORD @ (xyz.T / 100.0)
    cone_w = BRADFORD @ (np.asarray(white, float) / 100.0)
    cone_d50 = BRADFORD @ (D50_XYZ100 / 100.0)
    adapted = np.linalg.inv(BRADFORD) @ (cone * (cone_d50 / cone_w)[:, None])
    return adapted.T * 100.0


# The battery (fixed definitions — do not tune these against a candidate).
PRINTERS: dict[str, SyntheticPrinter] = {
    "S1": SyntheticPrinter("S1", "RGB", paper="glossy", dot_gain_gamma=0.85),
    "S2": SyntheticPrinter("S2", "RGB", paper="matte", dot_gain_gamma=0.70,
                           flare=0.018, density_scale=1.5),
    "S3": SyntheticPrinter("S3", "CMYK", tac=280.0, yn_nu=4.0),
    "S4": SyntheticPrinter("S4", "CMYK", tac=280.0, noise_scale=3.0,
                           yn_nu=4.0),
    "S5": SyntheticPrinter("S5", "CMYKOG", tac=320.0, yn_nu=3.2),
    "S6": SyntheticPrinter("S6", "CMYKV", tac=300.0, yn_nu=4.8),
}


# ---------------------------------------------------------------------------
# Quasi-random sampling (Halton with Cranley–Patterson rotation)
# ---------------------------------------------------------------------------

_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47)


def _radical_inverse(idx: np.ndarray, base: int) -> np.ndarray:
    out = np.zeros(len(idx), float)
    f = 1.0 / base
    i = idx.astype(np.int64).copy()
    while i.max(initial=0) > 0:
        out += f * (i % base)
        i //= base
        f /= base
    return out


def halton(n: int, dim: int, seed: int = 0) -> np.ndarray:
    """(n, dim) scrambled Halton points in [0, 1)ᵈ (deterministic)."""
    idx = np.arange(1, n + 1)
    pts = np.stack([_radical_inverse(idx, _PRIMES[d]) for d in range(dim)], 1)
    shift = np.random.default_rng(seed).uniform(0.0, 1.0, dim)
    return (pts + shift[None, :]) % 1.0


def eval_points(printer: SyntheticPrinter, n: int, seed: int = 7
                ) -> np.ndarray:
    """Dense evaluation device points, TAC-respecting (the referee's grid)."""
    pts = halton(n, printer.n_channels, seed)
    if printer.tac is not None and not printer.is_additive:
        from workflow.profile_engine.b2a import project_tac
        pts = project_tac(pts, printer.tac / 100.0)
    return pts


# ---------------------------------------------------------------------------
# Chart composition + measurement simulation
# ---------------------------------------------------------------------------

def make_chart(printer: SyntheticPrinter, n_patches: int = 900,
               seed: int = 11) -> np.ndarray:
    """(n_patches, n) chart device values — ramps, neutrals, corners,
    duplicate endpoints and a quasi-random fill (targen-style mix)."""
    n = printer.n_channels
    rows: list[np.ndarray] = []
    white = 1.0 if printer.is_additive else 0.0
    rows.append(np.full((4, n), white))                      # 4× white
    black = np.zeros((4, n))
    if printer.is_additive:
        black[:] = 0.0
    else:
        black[:, min(3, n - 1)] = 1.0                        # solid K
    rows.append(black)
    steps = np.linspace(0.0, 1.0, 11)
    for c in range(n):                                       # channel ramps
        r = np.full((len(steps), n), white)
        r[:, c] = steps if not printer.is_additive else 1.0 - steps
        rows.append(r)
    grey = np.full((len(steps), n), white)                   # composite grey
    if printer.is_additive:
        grey[:, :] = (1.0 - steps)[:, None]
    else:
        grey[:, :3] = steps[:, None] * np.array([0.9, 0.75, 0.72])
    rows.append(grey)
    corners = np.stack(np.meshgrid(*([[0.0, 1.0]] * min(n, 4)),
                                   indexing="ij"), -1).reshape(-1, min(n, 4))
    pad = np.zeros((len(corners), n))
    pad[:, :corners.shape[1]] = corners
    rows.append(pad)
    fixed = np.vstack(rows)
    fill = halton(max(n_patches - len(fixed), 0), n, seed)
    chart = np.vstack([fixed, fill])
    if printer.tac is not None and not printer.is_additive:
        from workflow.profile_engine.b2a import project_tac
        chart = project_tac(chart, printer.tac / 100.0)
    return chart


def measure(printer: SyntheticPrinter, device: np.ndarray, seed: int = 23
            ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simulate an instrument read of the chart.

    Returns ``(xyz_measured, reflectance_measured, misread_rows)`` — the
    misread rows are ground truth for scoring outlier detection (S4).
    """
    rng = np.random.default_rng(seed)
    xyz = printer.xyz_true(device)
    refl = printer.reflectance(device)
    sigma = printer.noise_scale * (0.015 + 0.025 * np.exp(-xyz[:, 1] / 8.0))
    noisy = xyz + rng.normal(0.0, 1.0, xyz.shape) * sigma[:, None]
    # Correlated small reflectance noise so SPEC data stays consistent-ish.
    refl = np.clip(refl * (1.0 + rng.normal(0.0, 0.002 * printer.noise_scale,
                                            refl.shape)), 0.0, None)
    misread = rng.uniform(size=len(device)) < printer.misread_prob
    # Endpoint duplicates stay clean: a smudged white would poison the
    # adaptation basis for *every* builder equally and score nothing.
    misread[:8] = False
    if misread.any():
        lab = xyz_to_lab(noisy[misread])
        direction = rng.normal(size=(misread.sum(), 3))
        direction /= np.linalg.norm(direction, axis=1, keepdims=True)
        lab = lab + direction * rng.uniform(5.0, 40.0,
                                            (misread.sum(), 1))
        noisy[misread] = lab_to_xyz(lab)
    noisy = np.clip(noisy, 0.0, None)
    return noisy, refl, np.flatnonzero(misread)


def write_ti3(path: Path, printer: SyntheticPrinter, device: np.ndarray,
              xyz: np.ndarray, refl: np.ndarray | None = None) -> Path:
    """Write a CGATS .ti3 the engine's ``read_ti3`` accepts."""
    letters = printer.channel_letters
    prefix = printer.device_rep
    fields = [f"{prefix}_{c}" for c in letters] + ["XYZ_X", "XYZ_Y", "XYZ_Z"]
    spec_fields: list[str] = []
    if refl is not None:
        spec_fields = [f"SPEC_{int(w):d}" for w in LAM]
    lines = [
        "CTI3   ",
        'DESCRIPTOR "Synthetic ground-truth chart (ChromIQ benchmarks)"',
        'ORIGINATOR "ChromIQ benchmarks"',
        'DEVICE_CLASS "OUTPUT"',
        f'COLOR_REP "{printer.color_rep}"',
    ]
    if printer.tac is not None:
        lines.append(f'TOTAL_INK_LIMIT "{printer.tac:g}"')
    if spec_fields:
        lines += [f'SPECTRAL_BANDS "{len(LAM)}"',
                  f'SPECTRAL_START_NM "{LAM[0]:g}"',
                  f'SPECTRAL_END_NM "{LAM[-1]:g}"']
    lines += [f"NUMBER_OF_FIELDS {1 + len(fields) + len(spec_fields)}",
              "BEGIN_DATA_FORMAT",
              "SAMPLE_ID " + " ".join(fields + spec_fields),
              "END_DATA_FORMAT",
              f"NUMBER_OF_SETS {len(device)}",
              "BEGIN_DATA"]
    for i in range(len(device)):
        row = [str(i + 1)]
        row += [f"{v * 100.0:.4f}" for v in device[i]]
        row += [f"{v:.5f}" for v in xyz[i]]
        if refl is not None:
            row += [f"{v:.5f}" for v in refl[i]]
        lines.append(" ".join(row))
    lines.append("END_DATA")
    path = Path(path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
