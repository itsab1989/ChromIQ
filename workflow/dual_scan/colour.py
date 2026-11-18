"""Spectrum -> CIELAB (D50, CIE 1931 2 degree) for the scale refinement's
checks, and CIEDE2000 (:func:`workflow.profile_engine.metrics.delta_e_2000`).

Spectra: reflectance 0..1 at 380..730 nm, 10 nm. Catmull-Rom interpolation
to 1 nm, held flat outside its range; CMFs and D50 at 1 nm over 360..780 nm
from :mod:`workflow.cie_data`; Lab against the ICC D50 white
(96.42, 100, 82.49), as ArgyllCMS's spec2cie (the dual-scan analyses
measured this conversion against spec2cie: 0.0007 dE00 mean).
"""
from __future__ import annotations

import numpy as np

from workflow import cie_data as C

WL10 = np.arange(380, 731, 10, dtype=float)
_WL1 = np.arange(360, 781, 1, dtype=float)
WHITE_D50 = np.array([96.42, 100.0, 82.49])


def _tab(t):
    lo, hi, v = t
    return np.interp(_WL1, np.linspace(lo, hi, len(v)), np.asarray(v, float))


def _cr_matrix(wl):
    wl = np.asarray(wl, float)
    n = len(wl)
    M = np.zeros((len(_WL1), n))
    for r, x in enumerate(_WL1):
        if x <= wl[0]:
            M[r, 0] = 1
            continue
        if x >= wl[-1]:
            M[r, -1] = 1
            continue
        i = int(np.searchsorted(wl, x) - 1)
        t = (x - wl[i]) / (wl[i + 1] - wl[i])
        w = [0.5 * (-t + 2 * t * t - t ** 3), 0.5 * (2 - 5 * t * t + 3 * t ** 3),
             0.5 * (t + 4 * t * t - 3 * t ** 3), 0.5 * (-t * t + t ** 3)]
        for j, ww in zip((i - 1, i, i + 1, i + 2), w):
            M[r, min(max(j, 0), n - 1)] += ww
    return M


_W = None
_CR10 = None


def _weights():
    global _W, _CR10
    if _W is None:
        X, Y, Z = (_tab(C.OBS_1931_2_X), _tab(C.OBS_1931_2_Y), _tab(C.OBS_1931_2_Z))
        d50 = _tab(C.IL_D50)
        k = 100.0 / np.sum(d50 * Y)
        _W = np.stack([d50 * X, d50 * Y, d50 * Z]) * k
        _CR10 = _cr_matrix(WL10)
    return _W, _CR10


def spec_to_lab(spec) -> np.ndarray:
    W, M = _weights()
    s = np.atleast_2d(np.asarray(spec, float))
    xyz = (s @ M.T) @ W.T
    r = xyz / WHITE_D50
    e, k = 216 / 24389, 24389 / 27
    f = np.where(r > e, np.cbrt(r), (k * r + 16) / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]),
                     200 * (f[:, 1] - f[:, 2])], axis=1)


def de00_spectra(a, b) -> np.ndarray:
    from workflow.profile_engine.metrics import delta_e_2000
    return delta_e_2000(spec_to_lab(a), spec_to_lab(b))
