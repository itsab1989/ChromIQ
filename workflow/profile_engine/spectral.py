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


def spectra_to_xyz(refl: np.ndarray, lam: np.ndarray, *,
                   illuminant: str = "D50", observer: str = ""
                   ) -> np.ndarray:
    """(N, bands) reflectance (0..1 or 0..100 auto-detected) → (N, 3) XYZ
    on the Y=100 scale, CIE 15 integration."""
    r = np.asarray(refl, dtype=float)
    if np.nanmax(r) > 2.0:          # percent-scaled reflectance
        r = r / 100.0
    spd = illuminant_spd(illuminant, lam)
    cmf = observer_cmf(observer, lam)
    k = 100.0 / float((spd * cmf[1]).sum())
    return k * (r[:, None, :] * (spd[None, :] * cmf)[None, :, :]).sum(2)


def apply_spectral(meas: Ti3Measurement, *, illuminant: str = "",
                   observer: str = "", fwa: bool = False,
                   fwa_illum: str = "") -> None:
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
                              observer=observer)
    for attr in ("xyz_relative", "lab_relative", "lab_absolute",
                 "media_white_xyz", "white_index", "black_index"):
        meas.__dict__.pop(attr, None)
