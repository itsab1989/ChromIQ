"""Reflectance spectra to XYZ the way ArgyllCMS computes them (4.3.24).

ArgyllCMS's ``spec2cie``, ``colprof`` and ``chartread`` turn a spectrum into
XYZ in ``xsp2cie_sconvert`` (``xicc/xspect.c``). ChromIQ computed XYZ from
spectra itself in several places (the i1Profiler import, the CR30, the
analysis of a spectral-only ``.ti3``, the profile engine's illuminant and
observer options), each with a shortcut of its own: the illuminant and the
colour-matching functions sampled at the readings' own 10 nm steps, or a
1 nm sum over the measured range only. Valid CIE 15 shortcuts, but not
ArgyllCMS's method: on jctay's i1Pro 3 files the 10 nm sums came out
0.05 dE76 mean, 0.10 max away from ``spec2cie`` on the very same spectra,
the measured-range sum 0.27 mean, 0.64 max, where his own converter agreed
with ``spec2cie`` to 0.001 (printerknowledge, 2026-11-04). This module does
what ``xspect.c`` does:

* integrate at **1 nm** over the observer's own range (360 to 830 nm for the
  CIE 1931 2 degree and 1964 10 degree observers), not over the measured
  range;
* read the illuminant, the observer and the sample at each 1 nm step through
  ArgyllCMS's interpolation: **linear** for a table spaced closer than
  5.01 nm (the 5 nm illuminant tables, the 1 nm observers), and the
  **4-point Lagrange cubic** for anything coarser (a 10 nm instrument
  spectrum), with the end intervals using the first or last four points;
* hold the first and last value outside a table's range (a 380 to 730 nm
  reading counts as its 380 nm value below 380 nm and as its 730 nm value
  above 730 nm; illuminant C, tabulated to 780 nm, keeps its 780 nm value
  beyond), as CIE 15 and CGATS.5 recommend;
* the M2 (ultraviolet cut) illuminants filter the TABLE, at its own 5 nm
  points, before it is interpolated (``uv_filter``: nothing at or below
  395 nm, a smoothstep up to 425 nm);
* normalise by the integral of illuminant times y-bar over the same steps,
  so a perfect white has Y = 100, and clamp a negative X, Y or Z to 0
  (``CLAMP_XYZ``) unless the caller asks not to.

Every step but the clamp is linear in the reflectance, so the method is one
(3, bands) weight matrix per wavelength grid, illuminant and observer
(:func:`xyz_weights`, cached): XYZ = R . W^T.

The tables are the CIE's standard colorimetric data (the 1931 2 degree and
1964 10 degree observers, illuminants A, C, D50, D65, F5, F8, F10), in
ArgyllCMS's tabulation (:mod:`workflow.profile_engine.spectral_data`,
extracted from ``xicc/xspect.c``; data, not program code, see
THIRD-PARTY-NOTICES.md). The procedure is the standard numeric one
(interpolation, a 1 nm sum, a normalisation) written here in numpy; no
ArgyllCMS code is copied. The method is checked against ``spec2cie``
3.5.0 by ``tests/test_4324_xyz_like_argyll.py``: 0.00002 dE76 mean on
jctay's 600 patches, which is the rounding of spec2cie's printed decimals,
for every illuminant and observer ``spec2cie -i``/``-o`` offers that ChromIQ
has a table for.

Nothing here rewrites a file. A measurement already in a project keeps the
XYZ it was written with.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from workflow.profile_engine import spectral_data as sd

#: Below this spacing ArgyllCMS interpolates a spectrum linearly, at or above
#: it with the 4-point Lagrange cubic (``getval_raw_xspec``).
_LINEAR_BELOW_NM = 5.01

_OBSERVERS = {"": sd.OBS_1931_2, "1931_2": sd.OBS_1931_2,
              "1964_10": sd.OBS_1964_10}
_ILLUMINANTS = {
    "A": sd.ILLUM_A, "C": sd.ILLUM_C, "D50": sd.ILLUM_D50,
    "D65": sd.ILLUM_D65, "F5": sd.ILLUM_F5, "F8": sd.ILLUM_F8,
    "F10": sd.ILLUM_F10,
}


class ColorimetryError(ValueError):
    """An illuminant or observer this module has no table for."""


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


def _uv_filter(lo: float, hi: float, vals: np.ndarray) -> np.ndarray:
    """``uv_filter`` of ``xspect.c``, on the table's own points."""
    wl = np.linspace(lo, hi, len(vals))
    ff = np.clip((wl - 395.0) / 30.0, 0.0, 1.0)
    ff = ff * ff * (3.0 - 2.0 * ff)
    return np.asarray(vals, dtype=float) * ff


def illuminant_table(illuminant) -> "tuple[float, float, tuple]":
    """``(lo, hi, values)`` of *illuminant*: a name ("D50", "D50M2", "A",
    "C", "D65", "D65M2", "F5", "F8", "F10"; upper or lower case), a
    ``dict(lo=, hi=, vals=)`` table or a ``(lo, hi, values)`` tuple."""
    if isinstance(illuminant, dict):
        return (float(illuminant["lo"]), float(illuminant["hi"]),
                tuple(float(v) for v in illuminant["vals"]))
    if isinstance(illuminant, (tuple, list)):
        lo, hi, vals = illuminant
        return float(lo), float(hi), tuple(float(v) for v in vals)
    key = str(illuminant or "D50").strip().upper()
    m2 = key.endswith("M2")
    base = key[:-2] if m2 else key
    if base not in _ILLUMINANTS:
        raise ColorimetryError(
            f"Unknown illuminant {illuminant!r} (known: A, C, D50, D50M2, "
            "D65, D65M2, F5, F8, F10).")
    t = _ILLUMINANTS[base]
    vals = np.asarray(t["vals"], dtype=float)
    if m2:
        vals = _uv_filter(t["lo"], t["hi"], vals)
    return float(t["lo"]), float(t["hi"]), tuple(float(v) for v in vals)


def _observer(observer) -> dict:
    key = str(observer or "").strip()
    if key not in _OBSERVERS:
        raise ColorimetryError(
            f"Unknown observer {observer!r} (known: 1931_2, 1964_10).")
    return _OBSERVERS[key]


@lru_cache(maxsize=64)
def _weights(lam: tuple, ill: tuple, observer: str) -> np.ndarray:
    obs = _observer(observer)
    o_vals = np.asarray(obs["vals"], dtype=float)
    # The integration steps: 1 nm over the observer's own range
    # (xsp2cie: spec_bw 1.0, observer[1].spec_wl_short .. spec_wl_long).
    steps = np.arange(obs["lo"], obs["hi"] + 0.5, 1.0)
    o = _resample(o_vals, obs["lo"], obs["hi"], steps)
    lo, hi, vals = ill
    i_spd = _resample(np.asarray(vals), lo, hi, steps)
    # How each band of the sample reaches each 1 nm step (identity spectra
    # through ArgyllCMS's interpolation): (bands, steps).
    bands = np.eye(len(lam))
    s = _resample(bands, lam[0], lam[-1], steps)
    scale = 100.0 / float(np.sum(i_spd * o[1]))
    w = scale * (s * i_spd) @ o.T          # (bands, 3)
    w.setflags(write=False)
    return w.T                             # (3, bands)


#: The fewest bands a spectrum may have. ArgyllCMS's cubic needs four points;
#: on two or three, ``spec2cie`` 3.5.0 gives numbers that look like an edge
#: case of its own (a flat 100 % white on 500/600 nm reads Y = 113.9), so
#: such a spectrum is refused rather than computed differently (review r1,
#: L5). No instrument writes fewer than 31.
MIN_BANDS = 4


def _grid(wavelengths) -> tuple:
    lam = np.asarray(wavelengths, dtype=float).ravel()
    if len(lam) < MIN_BANDS:
        raise ValueError(
            f"a spectrum needs at least {MIN_BANDS} wavelengths to be turned "
            f"into XYZ as ArgyllCMS does; this one has {len(lam)}")
    if not np.allclose(np.diff(lam), lam[1] - lam[0], atol=1e-6) \
            or lam[1] <= lam[0]:
        raise ValueError("the wavelengths must be evenly spaced and rising")
    return tuple(round(float(v), 6) for v in lam)


def xyz_weights(wavelengths, *, illuminant="D50",
                observer: str = "1931_2") -> np.ndarray:
    """The (3, bands) matrix W with XYZ = R . W^T (R a fraction, XYZ on the
    Y = 100 scale, before the clamp), for evenly spaced *wavelengths*."""
    return _weights(_grid(wavelengths), illuminant_table(illuminant),
                    str(observer or ""))


def spectra_to_xyz_like_argyll(refl, wavelengths, *, illuminant="D50",
                               observer: str = "1931_2",
                               percent: bool = False,
                               clamp: bool = True) -> np.ndarray:
    """(N, bands) reflectance on evenly spaced *wavelengths* to (N, 3) XYZ on
    the Y = 100 scale, by ArgyllCMS's method (see the module text).

    *refl* is a fraction (a perfect white is 1.0) unless *percent* is True
    (a perfect white is 100, as in a ``.ti3``'s ``SPEC_`` columns). Never
    guessed: a fluorescent white can read above 1. *clamp* sets negative
    X, Y, Z to 0 as ArgyllCMS does."""
    r = np.atleast_2d(np.asarray(refl, dtype=float))
    if percent:
        r = r / 100.0
    lam = _grid(wavelengths)
    if r.shape[-1] != len(lam):
        raise ValueError("one reflectance value per wavelength")
    xyz = r @ _weights(lam, illuminant_table(illuminant),
                       str(observer or "")).T
    return np.clip(xyz, 0.0, None) if clamp else xyz


def white_xyz_like_argyll(illuminant="D50",
                          observer: str = "1931_2") -> np.ndarray:
    """XYZ of a perfect white diffuser under *illuminant* (Y = 100)."""
    obs = _observer(observer)
    steps = np.arange(obs["lo"], obs["hi"] + 0.5, 1.0)
    o = _resample(np.asarray(obs["vals"], dtype=float), obs["lo"],
                  obs["hi"], steps)
    lo, hi, vals = illuminant_table(illuminant)
    i_spd = _resample(np.asarray(vals), lo, hi, steps)
    return 100.0 * (o @ i_spd) / float(np.sum(i_spd * o[1]))
