"""M0, M1 and M2 of an i1Pro 2 dual reading: the formula.

THE FORMULA (per patch, per wavelength band)::

    L   lamp reading, reflectance (white-calibrated with the lamp)   = M0
    U   UV-LED reading of the same patch, processed with the SAME lamp
        white calibration (so in "lamp-white" reflectance units)
    W   the white tile read with the lamp at calibration, same units
    T   the white tile read with the UV LED at calibration, same units
    EMIS  this calibration's factor from reflectance to emission units
        (ArgyllCMS: emis_coef / white calibration factor)
    kA, kD  the instrument's own factory tables (EEPROM keys 0x2f77 and
        0x2f76, 18 values 380-550 nm), zero outside 410-550 nm
    s   the glow scale, ONE number per instrument (:mod:`.scale`)

    Ue = U * EMIS                  UV reading in emission units
    Te = (T / W) * EMIS            UV LED on the tile per unit reflectance
    J  = s kA (Ue - Te L) / (1 - s kA Te)
    M2 = L - J
    M1 = L + (kD / kA - 1) J
    (outside the bands where kA > 0: M0 = M1 = M2 = L; nothing is clipped)

DERIVATION. ``Ue - Te * R`` is what the UV reading holds beyond the UV
light the patch simply reflects (a patch of reflectance R reflects
``Te * R`` of the LED's light): the patch's glow under the LED. ``s kA``
scales that glow to the glow the instrument's lamp excites (``kA``, the
"A" table) and ``s kD`` to the glow D50 daylight excites. The reflected LED
light must be taken off with the glow-free reflectance M2, not with M0, so
``J = s kA (Ue - Te M2)`` with ``M2 = L - J``; solved for J this gives the
denominator. M1 adds the daylight glow to the glow-free reflectance:
``M1 = M2 + s kD (Ue - Te M2) = L + (kD/kA - 1) J``.

SOURCE. The form is ArgyllCMS's i1Pro 3 computation (``i1pro3_comp_refl_value``
in ``native/instlib/i1pro3_imp.c``, the ``fwa_cal`` denominator), applied with
the i1Pro 2's own tables. It was established on X-Rite i1Profiler's own
results of two different i1Pro 2 instruments (work-folder analyses of
2026-11-17, private tester data): on the first, hand-held dual scans, M2 and
M1 to 0.017-0.047 dE00 given i1Profiler's own M0; on the second, dual spot
readings on an i1iO 2 table, to 0.004 / 0.002 dE00 (residual 0.0001
reflectance rms). ``M1 - M0 = (kD/kA - 1)(M0 - M2)`` holds in every
i1Profiler file of both instruments to 1e-6.

WHAT IS REFUSED (:class:`~workflow.dual_scan.reasons.DualScanRefused`):
a calibration without the UV-LED tile reading (a dual scan on a single-scan
calibration came out 15 % too bright in i1Profiler too), a calibration made
at another exposure than the reading, missing or malformed tables, a UV
reading that does not match the lamp reading patch for patch, values that
are not finite, and a scale that is not a sensible number.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from workflow.dual_scan.reasons import DualScanRefused

#: The i1Pro 2's standard-resolution bands (ArgyllCMS: 36 bands, 380-730 nm).
WAVELENGTHS = np.arange(380, 731, 10)
#: Where the factory tables may be non-zero (MEASURED on two instruments:
#: zero at 380-400 nm, 18 values to 550 nm).
GLOW_BAND_NM = (410, 550)
#: Sensible range of the glow scale (two instruments: 1.08-1.21).
SCALE_RANGE = (0.5, 2.0)


@dataclass(frozen=True)
class UVTables:
    """The instrument's factory tables, on :data:`WAVELENGTHS`."""
    kA: np.ndarray
    kD: np.ndarray

    @classmethod
    def from_values(cls, kA, kD, wavelengths=WAVELENGTHS) -> "UVTables":
        """Validated tables. *kA*, *kD* may be the 18 EEPROM values
        (380-550 nm), padded with zeros to the 36 bands, or the 36 bands."""
        if kA is None or kD is None:
            raise DualScanRefused("no_uv_tables")
        try:
            a = np.asarray(kA, dtype=float).ravel()
            d = np.asarray(kD, dtype=float).ravel()
        except (TypeError, ValueError):
            raise DualScanRefused("bad_uv_tables", "not numbers") from None
        n = len(wavelengths)
        if a.size != d.size or a.size == 0 or a.size > n:
            raise DualScanRefused("bad_uv_tables", "size")
        a = np.r_[a, np.zeros(n - a.size)]
        d = np.r_[d, np.zeros(n - d.size)]
        if not (np.all(np.isfinite(a)) and np.all(np.isfinite(d))):
            raise DualScanRefused("bad_uv_tables", "not finite")
        if np.any(a < 0) or np.any(d < 0):
            raise DualScanRefused("bad_uv_tables", "negative")
        band = a > 0
        if not band.any():
            raise DualScanRefused("no_uv_tables", "all zero")
        wl = np.asarray(wavelengths, dtype=float)
        lo, hi = GLOW_BAND_NM
        if np.any(band & ((wl < lo) | (wl > hi))):
            raise DualScanRefused("bad_uv_tables", "outside 410-550 nm")
        if np.any(band & (d <= 0)) or np.any(~band & (d != 0)):
            raise DualScanRefused("bad_uv_tables", "kD where kA is not")
        return cls(kA=a, kD=d)

    @property
    def band(self) -> np.ndarray:
        """The bands that carry glow (kA > 0)."""
        return self.kA > 0

    @property
    def a(self) -> np.ndarray:
        """The M1 factor ``kD / kA - 1`` (0 outside the glow bands)."""
        b = self.band
        return np.where(b, self.kD / np.where(b, self.kA, 1.0) - 1.0, 0.0)


@dataclass(frozen=True)
class DualCalibration:
    """What a dual-scan calibration measured, in lamp-white units.

    *white* (W) and *uv_tile* (T) are the tile read with the lamp and with
    the UV LED, *emis* the reflectance-to-emission factor of this
    calibration. *lamp_clocks* / *uv_clocks*: the integration the
    calibration was made at (None = not known, not checked)."""
    white: np.ndarray
    uv_tile: "np.ndarray | None"
    emis: np.ndarray
    lamp_clocks: "int | None" = None
    uv_clocks: "int | None" = None

    def checked(self, nbands: int) -> "DualCalibration":
        if self.uv_tile is None:
            raise DualScanRefused("no_dual_calibration")
        out = []
        for name in ("white", "uv_tile", "emis"):
            v = np.asarray(getattr(self, name), dtype=float).ravel()
            if v.size != nbands:
                raise DualScanRefused("no_dual_calibration", f"{name} size")
            if not np.all(np.isfinite(v)):
                raise DualScanRefused("bad_values", name)
            out.append(v)
        w, t, e = out
        if np.any(w <= 0) or np.any(e <= 0):
            raise DualScanRefused("no_dual_calibration", "white / emis not positive")
        return DualCalibration(w, t, e, self.lamp_clocks, self.uv_clocks)

    def te(self) -> np.ndarray:
        """Te = (T / W) * EMIS."""
        return np.asarray(self.uv_tile) / np.asarray(self.white) * np.asarray(self.emis)


@dataclass
class Conditions:
    """The result: one row per patch, one column per band."""
    m0: np.ndarray
    m1: np.ndarray
    m2: np.ndarray
    glow: np.ndarray            # J, the glow the lamp excites
    scale: float
    extra: dict = field(default_factory=dict)

    def by_name(self) -> "dict[str, np.ndarray]":
        return {"M0": self.m0, "M1": self.m1, "M2": self.m2}


def _patches(x, nbands: int, what: str) -> np.ndarray:
    if x is None:
        raise DualScanRefused("uv_pass_missing" if what == "uv" else "bad_values", what)
    try:
        a = np.asarray(x, dtype=float)
    except (TypeError, ValueError):
        raise DualScanRefused("bad_values", what) from None
    if a.ndim == 1:
        a = a[None, :]
    if a.ndim != 2 or a.shape[1] != nbands:
        raise DualScanRefused("bad_values", f"{what} shape {a.shape}")
    if not np.all(np.isfinite(a)):
        raise DualScanRefused("bad_values", what)
    return a


def check_scale(s) -> float:
    try:
        v = float(s)
    except (TypeError, ValueError):
        raise DualScanRefused("bad_scale") from None
    if not np.isfinite(v) or not (SCALE_RANGE[0] <= v <= SCALE_RANGE[1]):
        raise DualScanRefused("bad_scale", repr(s))
    return v


def glow(lamp: np.ndarray, uv: np.ndarray, te: np.ndarray, emis: np.ndarray,
         tables: UVTables, s: float, base: "np.ndarray | None" = None
         ) -> np.ndarray:
    """J for already validated arrays. *base* is the M0 the reflected LED
    light is reckoned from (default: *lamp*; the scale fit can pass a
    reference instrument's M0 instead)."""
    b = lamp if base is None else base
    ue = uv * emis
    ka = tables.kA
    den = 1.0 - s * ka * te
    if np.any(den[tables.band] <= 0.05):
        raise DualScanRefused("bad_scale", "denominator")
    j = s * ka * (ue - te * b) / den
    j[:, ~tables.band] = 0.0
    return j


def compute(lamp, uv, calibration: DualCalibration, tables: UVTables, s, *,
            lamp_clocks: "int | None" = None, uv_clocks: "int | None" = None,
            ) -> Conditions:
    """M0, M1 and M2 of each patch from its lamp reading (row of *lamp*)
    and its UV reading (the same row of *uv*), by the formula above.

    *lamp_clocks* / *uv_clocks*: the integration of the readings; when both
    the reading and the calibration say, they must agree (a calibration at
    another exposure is refused, see the module docstring)."""
    if not isinstance(tables, UVTables):
        raise DualScanRefused("no_uv_tables")
    nb = tables.kA.size
    if calibration is None:
        raise DualScanRefused("no_dual_calibration")
    cal = calibration.checked(nb)
    for have, want in ((lamp_clocks, cal.lamp_clocks), (uv_clocks, cal.uv_clocks)):
        if have is not None and want is not None and int(have) != int(want):
            raise DualScanRefused("calibration_mismatch", f"{have} != {want}")
    sv = check_scale(s)
    L = _patches(lamp, nb, "lamp")
    U = _patches(uv, nb, "uv")
    if L.shape[0] != U.shape[0]:
        raise DualScanRefused("uv_pass_count", f"{L.shape[0]} lamp, {U.shape[0]} uv")
    te = cal.te()
    j = glow(L, U, te, cal.emis, tables, sv)
    return Conditions(m0=L.copy(), m1=L + tables.a * j, m2=L - j, glow=j, scale=sv)


def forward(m2: np.ndarray, glow_d50_unit: np.ndarray, calibration: DualCalibration,
            tables: UVTables, s: float) -> "tuple[np.ndarray, np.ndarray, np.ndarray]":
    """THE INVERSE, for tests and the proof: an invented instrument reading
    a paper. *m2* is the paper's glow-free reflectance, *glow_d50_unit* the
    patch's glow per unit of LED excitation in emission units (G, so that
    the UV reading holds ``Te * M2 + G`` beyond nothing else). Returns
    (L, U, M1) as the instrument and the formula define them:
    ``L = M2 + s kA G``, ``Ue = Te M2 + G``, ``M1 = M2 + s kD G``."""
    cal = calibration.checked(tables.kA.size)
    te = cal.te()
    g = np.asarray(glow_d50_unit, dtype=float)
    g = np.where(tables.band, g, 0.0)
    L = m2 + s * tables.kA * g
    ue = te * m2 + g
    U = ue / cal.emis
    M1 = m2 + s * tables.kD * g
    return L, U, M1
