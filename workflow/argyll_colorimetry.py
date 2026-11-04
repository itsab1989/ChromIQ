"""Reflectance spectra to XYZ the way ArgyllCMS computes them (4.3.24).

ArgyllCMS's ``spec2cie``, ``colprof`` and ``chartread`` turn a spectrum into
XYZ in ``xsp2cie_sconvert`` (``xicc/xspect.c``). An i1Profiler import is
converted by ChromIQ itself, because txt2ti3 cannot read CxF, and until
4.3.23 it multiplied the readings by the illuminant and the colour-matching
functions sampled at the readings' own 10 nm steps. That is a valid CIE 15
shortcut, but it is not ArgyllCMS's method, and on jctay's i1Pro 3 files it
came out 0.05 dE76 mean, 0.10 max away from ``spec2cie`` on the very same
spectra, where his own converter agreed with ``spec2cie`` to 0.001
(printerknowledge, 2026-11-04). This module does what ``xspect.c`` does:

* integrate at **1 nm** over the observer's own range (360 to 830 nm for the
  CIE 1931 2 degree observer), not over the measured range;
* read the illuminant, the observer and the sample at each 1 nm step through
  ArgyllCMS's interpolation: **linear** for a table spaced closer than
  5.01 nm (the 5 nm D50 table, the 1 nm observer), and the **4-point
  Lagrange cubic** for anything coarser (a 10 nm instrument spectrum), with
  the end intervals using the first or last four points;
* hold the first and last measured value outside the measured range (a
  380 to 730 nm reading counts as its 380 nm value below 380 nm and as its
  730 nm value above 730 nm), as CIE 15 and CGATS.5 recommend;
* normalise by the integral of illuminant times y-bar over the same steps,
  so a perfect white has Y = 100, and clamp a negative X, Y or Z to 0
  (``CLAMP_XYZ``).

The tables are ArgyllCMS's own (:mod:`workflow.profile_engine.spectral_data`,
extracted from ``xspect.c``). The method is checked against ``spec2cie``
3.5.0 by ``tests/test_4324_xyz_like_argyll.py``: 0.00002 dE76 mean on
jctay's 600 patches, which is the rounding of spec2cie's six decimals.

Only NEW imports use this. A measurement already in a project keeps the XYZ
it was written with; nothing here rewrites a file.
"""
from __future__ import annotations

import numpy as np

from workflow.profile_engine import spectral_data as sd

#: Below this spacing ArgyllCMS interpolates a spectrum linearly, at or above
#: it with the 4-point Lagrange cubic (``getval_raw_xspec``).
_LINEAR_BELOW_NM = 5.01

_OBSERVERS = {"1931_2": sd.OBS_1931_2, "1964_10": sd.OBS_1964_10}
_ILLUMINANTS = {
    "A": sd.ILLUM_A, "C": sd.ILLUM_C, "D50": sd.ILLUM_D50,
    "D65": sd.ILLUM_D65, "F5": sd.ILLUM_F5, "F8": sd.ILLUM_F8,
    "F10": sd.ILLUM_F10,
}


def _resample(values: np.ndarray, lo: float, hi: float,
              at: np.ndarray) -> np.ndarray:
    """ArgyllCMS's ``getval_raw_xspec`` for a uniformly spaced table from
    *lo* to *hi* (the last axis of *values*), at the wavelengths *at*."""
    values = np.asarray(values, dtype=float)
    n = values.shape[-1]
    if n < 2:
        return np.repeat(values[..., :1], len(at), axis=-1)
    spacing = (hi - lo) / (n - 1.0)
    xw = np.clip(np.asarray(at, dtype=float), lo, hi)
    f = (xw - lo) / (hi - lo) * (n - 1.0)
    i = np.floor(f).astype(int)
    if spacing < _LINEAR_BELOW_NM or n < 4:
        i = np.clip(i, 0, n - 2)
        w = f - i
        return values[..., i] * (1.0 - w) + values[..., i + 1] * w
    i = np.clip(i, 1, n - 3)
    x = [lo + (i + k) * spacing for k in (-1, 0, 1, 2)]
    out = np.zeros(values.shape[:-1] + (len(xw),))
    for a in range(4):
        k = np.ones_like(xw)
        for b in range(4):
            if a != b:
                k = k * (xw - x[b]) / (x[a] - x[b])
        out = out + k * values[..., i + a - 1]
    return out


def spectra_to_xyz_like_argyll(refl, wavelengths, *, illuminant: str = "D50",
                               observer: str = "1931_2",
                               percent: bool = False) -> np.ndarray:
    """(N, bands) reflectance on uniformly spaced *wavelengths* to (N, 3)
    XYZ on the Y = 100 scale, by ArgyllCMS's method (see the module text).

    *refl* is a fraction (a perfect white is 1.0) unless *percent* is True
    (a perfect white is 100, as in a ``.ti3``'s ``SPEC_`` columns). Never
    guessed: a fluorescent white can read above 1."""
    r = np.atleast_2d(np.asarray(refl, dtype=float))
    if percent:
        r = r / 100.0
    lam = np.asarray(wavelengths, dtype=float)
    if r.shape[-1] != len(lam) or len(lam) < 2:
        raise ValueError("one reflectance value per wavelength, at least two")
    if not np.allclose(np.diff(lam), lam[1] - lam[0], atol=1e-6):
        raise ValueError("the wavelengths must be evenly spaced")
    obs = _OBSERVERS[observer or "1931_2"]
    ill = _ILLUMINANTS[(illuminant or "D50").upper()]
    o_vals = np.asarray(obs["vals"], dtype=float)
    # The integration steps: 1 nm over the observer's own range
    # (xsp2cie: spec_bw 1.0, observer[1].spec_wl_short .. spec_wl_long).
    steps = np.arange(obs["lo"], obs["hi"] + 0.5, 1.0)
    o = _resample(o_vals, obs["lo"], obs["hi"], steps)
    i_spd = _resample(ill["vals"], ill["lo"], ill["hi"], steps)
    s = _resample(r, float(lam[0]), float(lam[-1]), steps)
    scale = 1.0 / float(np.sum(i_spd * o[1]))
    xyz = 100.0 * scale * ((s * i_spd) @ o.T)
    return np.clip(xyz, 0.0, None)
