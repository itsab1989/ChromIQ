"""Spectral colorimetry: colprof's ``-i`` / ``-o`` for the engine (#122).

Recomputes the measurement's XYZ from its spectral bands under a chosen CIE
illuminant and observer — plain CIE 15 integration:

    XYZ = k · Σ R(λ)·S(λ)·CMF(λ),   k = 100 / Σ S(λ)·ȳ(λ)

The illuminant SPDs and observer CMFs in :mod:`spectral_data` are the CIE
standard tables (extracted programmatically, not typed); the M2 (UV-cut)
illuminant variants apply the same 395–425 nm smoothstep cut-off Argyll
uses. Correctness is not assumed: the parity test builds the same spectral
``.ti3`` through ``colprof -i…/-o…`` and through the engine and compares.
"""
from __future__ import annotations

import numpy as np

from workflow.profile_engine import spectral_data as sd
from workflow.profile_engine.ti3_data import Ti3Measurement


class SpectralError(ValueError):
    """Spectral computation impossible (user-facing message)."""


_OBSERVERS = {
    "": sd.OBS_1931_2,
    "1931_2": sd.OBS_1931_2,
    "1964_10": sd.OBS_1964_10,
    # The two 2015 observers the Build Profile tab has offered since #121 —
    # the engine refused them at build time ("Unknown observer") while
    # engine_support said it could build, so the user got a failure
    # dialog instead of the promised colprof fallback (2026-09-04).
    "2015_2": sd.OBS_2015_2,
    "2015_10": sd.OBS_2015_10,
}

_ILLUMS = {
    "A": sd.ILLUM_A, "C": sd.ILLUM_C,
    "D50": sd.ILLUM_D50, "D65": sd.ILLUM_D65,
    "F5": sd.ILLUM_F5, "F8": sd.ILLUM_F8, "F10": sd.ILLUM_F10,
}


def _uv_filter(lam: np.ndarray, spd: np.ndarray) -> np.ndarray:
    """The M2 (UV-excluded) variant: smoothstep cut below 425 nm (Argyll's
    uv_filter — zero ≤395 nm, cubic ramp 395–425 nm)."""
    ff = np.clip((lam - 395.0) / 30.0, 0.0, 1.0)
    ff = ff * ff * (3.0 - 2.0 * ff)
    return spd * ff


def illuminant_spd(name: str, lam: np.ndarray) -> np.ndarray:
    """Illuminant SPD sampled at the wavelengths ``lam`` (nm)."""
    key = (name or "D50").upper()
    m2 = key.endswith("M2")
    base = key[:-2] if m2 else key
    if base not in _ILLUMS:
        raise SpectralError(
            f"Unknown illuminant {name!r} (the engine knows "
            "A, C, D50, D50M2, D65, D65M2, F5, F8, F10).")
    t = _ILLUMS[base]
    grid = np.linspace(t["lo"], t["hi"], len(t["vals"]))
    spd = np.interp(lam, grid, t["vals"], left=0.0, right=0.0)
    return _uv_filter(lam, spd) if m2 else spd


def observer_cmf(name: str, lam: np.ndarray) -> np.ndarray:
    """(3, len(lam)) observer CMFs sampled at ``lam``."""
    key = (name or "1931_2").strip()
    if key not in _OBSERVERS:
        raise SpectralError(
            f"Unknown observer {name!r} (the engine knows 1931_2, 1964_10, "
            "2015_2 and 2015_10).")
    t = _OBSERVERS[key]
    grid = np.linspace(t["lo"], t["hi"], t["vals"].shape[1])
    return np.stack([np.interp(lam, grid, t["vals"][i], left=0.0, right=0.0)
                     for i in range(3)])


# Research C-S1 (Agent 24, after Agent 4's question 2): illuminants whose
# 5 nm tables carry emission lines a 10 nm band grid never samples (the
# mercury lines of the CIE F series at 405, 435 and 545 nm). Only these are
# integrated at 1 nm; the smooth D, A and C illuminants keep the band sum
# (the spline moved them by <= 0.005 dE00), so their builds keep their bytes.
LINE_ILLUMINANTS = frozenset({"F5", "F8", "F10"})


def needs_fine_integration(illuminant: str) -> bool:
    key = (illuminant or "D50").upper()
    return (key[:-2] if key.endswith("M2") else key) in LINE_ILLUMINANTS


def _spline_rows(x: np.ndarray, y: np.ndarray, xn: np.ndarray) -> np.ndarray:
    """Natural cubic spline of each row of ``y`` (on ``x``) at ``xn``; ends held."""
    n = len(x)
    h = np.diff(x)
    a = np.zeros((n, n))
    a[0, 0] = a[-1, -1] = 1.0
    for i in range(1, n - 1):
        a[i, i - 1], a[i, i], a[i, i + 1] = h[i - 1], 2 * (h[i - 1] + h[i]), h[i]
    rhs = np.zeros((y.shape[0], n))
    rhs[:, 1:-1] = 6 * ((y[:, 2:] - y[:, 1:-1]) / h[1:]
                        - (y[:, 1:-1] - y[:, :-2]) / h[:-1])
    m = np.linalg.solve(a, rhs.T).T
    xc = np.clip(xn, x[0], x[-1])
    i = np.clip(np.searchsorted(x, xc) - 1, 0, n - 2)
    t0, t1, hi = xc - x[i], x[i + 1] - xc, h[i]
    return (m[:, i] * t1 ** 3 / (6 * hi) + m[:, i + 1] * t0 ** 3 / (6 * hi)
            + (y[:, i] / hi - m[:, i] * hi / 6) * t1
            + (y[:, i + 1] / hi - m[:, i + 1] * hi / 6) * t0)


def _sprague_rows(x: np.ndarray, y: np.ndarray, xn: np.ndarray) -> np.ndarray:
    """Sprague (1880) quintic interpolation, CIE 167:2005 / CIE 15 practice:
    two points extrapolated at each end, six-point coefficients per interval.
    Needs equal spacing; ends held outside the measured range."""
    h = float(x[1] - x[0])
    if not np.allclose(np.diff(x), h):
        return _spline_rows(x, y, xn)
    e_lo = np.array([[884, -1960, 3033, -2648, 1080, -180],
                     [508, -540, 488, -367, 144, -24]]) / 209.0
    p = np.concatenate([y[:, :6] @ e_lo.T,
                        y, (y[:, ::-1][:, :6] @ e_lo.T)[:, ::-1]], 1)
    xc = np.clip(xn, x[0], x[-1])
    i = np.clip(np.floor((xc - x[0]) / h).astype(int), 0, len(x) - 2)
    t = (xc - x[0]) / h - i
    j = i + 2                                 # index of p_i in the padded rows
    pm2, pm1, p0, p1, p2, p3 = (p[:, j + d] for d in (-2, -1, 0, 1, 2, 3))
    a1 = (2 * pm2 - 16 * pm1 + 16 * p1 - 2 * p2) / 24
    a2 = (-pm2 + 16 * pm1 - 30 * p0 + 16 * p1 - p2) / 24
    a3 = (-9 * pm2 + 39 * pm1 - 70 * p0 + 66 * p1 - 33 * p2 + 7 * p3) / 24
    a4 = (13 * pm2 - 64 * pm1 + 126 * p0 - 124 * p1 + 61 * p2 - 12 * p3) / 24
    a5 = (-5 * pm2 + 25 * pm1 - 50 * p0 + 50 * p1 - 25 * p2 + 5 * p3) / 24
    return p0 + t * (a1 + t * (a2 + t * (a3 + t * (a4 + t * a5))))


def spectra_to_xyz(refl: np.ndarray, lam: np.ndarray, *,
                   illuminant: str = "D50", observer: str = "",
                   method: str = "") -> np.ndarray:
    """(N, bands) reflectance (0..1 or 0..100 auto-detected) → (N, 3) XYZ
    on the Y=100 scale, CIE 15 integration.

    ``method`` (research, Maximum accuracy only): "" = the band sum at the
    measurement's own wavelengths (every mode's behaviour); "spline" or
    "sprague" = reflectance interpolated to 1 nm over 360-830 nm (ends held)
    and summed at 1 nm against the linearly interpolated CIE tables."""
    r = np.asarray(refl, dtype=float)
    if np.nanmax(r) > 2.0:          # percent-scaled reflectance
        r = r / 100.0
    lam = np.asarray(lam, dtype=float)
    if method in ("spline", "sprague") and len(lam) > 6 \
            and np.min(np.diff(lam)) > 1.0 + 1e-9:
        l1 = np.arange(360.0, 830.0 + 1e-9, 1.0)
        fn = _sprague_rows if method == "sprague" else _spline_rows
        r = fn(lam, np.atleast_2d(r), l1)
        lam = l1
        spd = illuminant_spd(illuminant, lam)
        cmf = observer_cmf(observer, lam)
        k = 100.0 / float((spd * cmf[1]).sum())
        return k * (r @ (spd[None, :] * cmf).T)
    spd = illuminant_spd(illuminant, lam)
    cmf = observer_cmf(observer, lam)
    k = 100.0 / float((spd * cmf[1]).sum())
    return k * (r[:, None, :] * (spd[None, :] * cmf)[None, :, :]).sum(2)


def apply_spectral(meas: Ti3Measurement, *, illuminant: str = "",
                   observer: str = "", fwa: bool = False,
                   fwa_illum: str = "", method: str = "") -> None:
    """Replace ``meas.xyz`` with spectrally computed values (in place).

    Mirrors colprof's behaviour: ``-i``/``-o``/``-f`` require spectral data
    in the measurement and recompute all colorimetry from it.
    """
    if meas.spectral is None or meas.wavelengths is None:
        raise SpectralError(
            "This measurement has no spectral data. Illuminant, observer "
            "and paper-whitener options need a chart measured in spectral "
            "mode (ChromIQ's high-resolution setting in the Measure tab).")
    refl = meas.spectral
    if fwa:
        from workflow.profile_engine.fwa import fwa_corrected_reflectance
        refl = fwa_corrected_reflectance(
            meas, target_illuminant=fwa_illum or illuminant or "D50")
    meas.xyz = spectra_to_xyz(refl, meas.wavelengths,
                              illuminant=illuminant or "D50",
                              observer=observer, method=method)
    for attr in ("xyz_relative", "lab_relative", "lab_absolute",
                 "media_white_xyz", "white_index", "black_index"):
        meas.__dict__.pop(attr, None)
