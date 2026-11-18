"""THE GLOW SCALE ``s``: the one number of the formula the instrument does
not store (:mod:`workflow.dual_scan.model`).

WHAT IS KNOWN (two i1Pro 2 instruments, private analyses of 2026-11-17 and
2026-11-18; i1Profiler's own M2 fitted by least squares at 410-550 nm):

* instrument 1 (hand-held dual scans, its own tile): 1.079-1.102 with
  ChromIQ's lamp pass as the base, 1.085-1.098 with i1Profiler's M0;
* instrument 2 (i1iO 2 table, dual spot, the table's tile): 1.212 with
  ChromIQ's lamp reading, 1.186 with i1Profiler's M0.

Nothing in either instrument's memory or calibration readings explained the
difference (``DESIGN.md`` of the work folder; the spec
``docs/design/i1pro2_dual_scan.md``). So:

* :data:`STANDARD_SCALE` is built in, so M1 and M2 work for every i1Pro 2
  without any vendor software (the owner's ruling of 2026-11-18: not every
  i1Pro 2 has an i1Profiler licence, and OEM versions have none at all);
* :func:`refine_scale` is the OPTIONAL improvement for someone who has
  i1Profiler: one strip measured in ChromIQ as a dual scan, and i1Profiler's
  M0 / M1 / M2 of the same strip with the same instrument;
* every measurement records which one was used (:class:`ScaleChoice`).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from workflow.dual_scan.model import (
    SCALE_RANGE, DualCalibration, UVTables, _patches, check_scale, glow)
from workflow.dual_scan.reasons import DualScanRefused

#: The built-in factor, PROVISIONAL (accepted by the owner on 2026-11-18 as
#: provisional): the middle of the two instruments' fitted values on
#: ChromIQ's own lamp readings (1.100 and 1.212), "middle" in the RELATIVE
#: sense: their geometric mean sqrt(1.100 x 1.212) = 1.1547 makes the worst
#: relative error over the two instruments smallest (5.0 % either side).
#: The dE00 a factor error costs is proportional to the relative error times
#: the paper's glow, so this choice does not depend on the papers measured
#: (a minimax in dE00 on these two papers, about 1.12, would bake the
#: papers into the constant: independent review of 2026-11-18). 1.156 and
#: 1.1547 differ by 0.003 dE00. Re-fit when a third instrument, or
#: instrument 2 on its own tile, is measured. See
#: docs/design/i1pro2_dual_scan.md.
STANDARD_SCALE = 1.156
#: Where it comes from (recorded in every measurement that uses it).
STANDARD_SOURCE = "standard"
REFINED_SOURCE = "refined"

# --- the refinement's checks (each from the analyses) -----------------------
#: ChromIQ's M0 against i1Profiler's M0 of the same strip: the analyses'
#: gate (measured 0.05-0.07 mean on two instruments).
M0_GATE_MEAN = 0.35
M0_GATE_P95 = 0.8
#: i1Profiler's own M1 factor against this instrument's kD/kA - 1: 1e-4 on
#: the same instrument, up to 0.32 between the two instruments.
A_LAMBDA_TOLERANCE = 0.02
#: Least glow (M0 - M2, reflectance, largest band mean over the patches) to
#: learn from: paper white glowed 0.17 at 440 nm on both brightened papers.
MIN_GLOW = 0.01
#: Largest M2 residual (rms reflectance, 410-550 nm) of an acceptable fit:
#: measured 0.001 (scans) and 0.0003 (spot).
MAX_FIT_RMS = 0.004


@dataclass(frozen=True)
class ScaleChoice:
    """The factor a measurement used, as it is recorded."""
    value: float
    source: str            # STANDARD_SOURCE or REFINED_SOURCE

    @classmethod
    def standard(cls) -> "ScaleChoice":
        return cls(STANDARD_SCALE, STANDARD_SOURCE)


def _m2_error(s, base, L, U, te, emis, tables, m2_ref):
    j = glow(L, U, te, emis, tables, s, base=base)
    r = (base - j - m2_ref)[:, tables.band]
    return float((r * r).sum())


def fit_scale(lamp, uv, calibration: DualCalibration, tables: UVTables,
              m2_reference, *, base=None) -> "tuple[float, float]":
    """The s that makes the formula's M2 closest (least squares over the
    glow bands) to *m2_reference*, and the rms residual. *base*: the M0 the
    formula starts from (default *lamp*; a reference M0 isolates the glow
    from any difference between the two programs' M0)."""
    nb = tables.kA.size
    cal = calibration.checked(nb)
    L = _patches(lamp, nb, "lamp")
    U = _patches(uv, nb, "uv")
    R = _patches(m2_reference, nb, "reference")
    B = L if base is None else _patches(base, nb, "base")
    if not (L.shape == U.shape == R.shape == B.shape):
        raise DualScanRefused("refine_patches_differ")
    te = cal.te()
    lo, hi = SCALE_RANGE
    grid = np.linspace(lo, hi, 1501)
    errs = []
    for s in grid:
        try:
            errs.append(_m2_error(s, B, L, U, te, cal.emis, tables, R))
        except DualScanRefused:
            errs.append(np.inf)
    k = int(np.argmin(errs))
    a, b = grid[max(k - 1, 0)], grid[min(k + 1, len(grid) - 1)]
    g = (np.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    f = lambda s: _m2_error(s, B, L, U, te, cal.emis, tables, R)  # noqa: E731
    fc, fd = f(c), f(d)
    for _ in range(80):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = f(d)
    s = float((a + b) / 2)
    n = int(tables.band.sum()) * L.shape[0]
    return s, float(np.sqrt(f(s) / max(n, 1)))


def refine_scale(lamp, uv, calibration: DualCalibration, tables: UVTables,
                 reference: "dict[str, np.ndarray]") -> "tuple[ScaleChoice, dict]":
    """THE OPTIONAL REFINEMENT. *lamp* / *uv*: ChromIQ's dual reading of one
    strip (per patch, patch order); *reference*: i1Profiler's ``M0``, ``M1``,
    ``M2`` of the SAME patches in the same order, measured with the same
    instrument. Returns the refined factor and the evidence; refuses with a
    reason when the two do not belong together or hold nothing to learn.

    The fit is on M2 at 410-550 nm with ChromIQ's own lamp reading as the
    base: that is how the factor is used afterwards, so it is the factor
    that brings ChromIQ's M2 closest to i1Profiler's (the proof's transfer
    table, docs/design/i1pro2_dual_scan.md, shows this choice is the better
    one on both instruments)."""
    from workflow.dual_scan.colour import de00_spectra
    nb = tables.kA.size
    if not all(k in reference for k in ("M0", "M1", "M2")):
        raise DualScanRefused("refine_no_conditions")
    L = _patches(lamp, nb, "lamp")
    U = _patches(uv, nb, "uv")
    try:
        I0, I1, I2 = (_patches(reference[k], nb, k) for k in ("M0", "M1", "M2"))
    except DualScanRefused:
        raise DualScanRefused("refine_patches_differ") from None
    if not (L.shape == U.shape == I0.shape == I1.shape == I2.shape) or L.shape[0] < 3:
        raise DualScanRefused("refine_patches_differ")
    d0 = de00_spectra(L, I0)
    if d0.mean() > M0_GATE_MEAN or np.sort(d0)[min(len(d0) - 1, int(0.95 * len(d0)))] > M0_GATE_P95:
        raise DualScanRefused("refine_m0_differs", f"mean {d0.mean():.3f}")
    band = tables.band
    dg = (I0 - I2)[:, band]
    # M2 is the glow taken away, so M0 - M2 is mostly >= 0 where it glows; a
    # file whose M0 - M2 is mostly NEGATIVE has its conditions swapped (review
    # of 2026-11-18, S6: such a file was told "no optical brightener")
    big = np.abs(dg) > MIN_GLOW / 4
    if big.sum() >= 3 and (dg[big] < 0).mean() > 0.5:
        raise DualScanRefused("refine_conditions_swapped")
    if dg.mean(axis=0).max() < MIN_GLOW:
        raise DualScanRefused("refine_no_glow")
    x, y = dg, (I1 - I0)[:, band]
    a_file = (x * y).sum(0) / np.maximum((x * x).sum(0), 1e-30)
    if np.abs(a_file - tables.a[band]).max() > A_LAMBDA_TOLERANCE:
        raise DualScanRefused("refine_other_instrument")
    s, rms = fit_scale(L, U, calibration, tables, I2)
    if rms > MAX_FIT_RMS or not (SCALE_RANGE[0] + 0.01 < s < SCALE_RANGE[1] - 0.01):
        raise DualScanRefused("refine_poor_fit", f"s {s:.4f} rms {rms:.5f}")
    check_scale(s)
    return ScaleChoice(round(s, 4), REFINED_SOURCE), {
        "m0_mean_de00": float(d0.mean()), "fit_rms": rms,
        "a_lambda_max_diff": float(np.abs(a_file - tables.a[band]).max()),
        "patches": int(L.shape[0])}
