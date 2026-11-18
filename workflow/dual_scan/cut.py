"""The UV pass of a hand-held dual strip cut into the lamp pass's patches.

In a hand-held dual scan the strip is swiped twice: forward under the lamp,
back under the UV LED (i1Profiler: lamp pass with "ruler start", UV pass
with "ruler end", so ONE continuous ruler stream covers both). ArgyllCMS's
patch recogniser finds the patches in the lamp pass (cells: first reading
and number of readings). Each reading of either pass has a ruler position
(the position at the reading's centre, interpolated between ruler steps,
as ArgyllCMS's i1Pro 3 code does). A lamp cell spans a position range; the
UV readings whose position lies in its central part (``1 - 2 * TRIM`` of
it) are averaged into that patch's UV reading.

SOURCE: the first analysis of 2026-11-17 (private), ``process.py::_uv_cut``:
central 60 % of each cell; alignment checked 0.00001-0.00004 (variance
inside the carried-over cells against between them) in place against
0.09-0.35 half a pitch off; at least 4-5 UV readings per patch at normal
speed, 9-10 slow.

On the i1iO 2 table in spot mode there is nothing to cut: one lamp and one
UV reading per patch (:func:`pair_spot`).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from workflow.dual_scan.reasons import DualScanRefused

#: fraction of a cell left out at each end (edges blur through the aperture)
TRIM = 0.2
#: fewest UV readings a patch may be averaged from (recordings: 4 or more)
MIN_UV_READINGS = 3


@dataclass
class CutResult:
    uv: np.ndarray            # [P, bands] the UV pass per patch
    counts: "list[int]"       # UV readings averaged per patch
    flatness: float           # within-cell / between-cell variance (small = aligned)


def reading_positions(step_samples: np.ndarray, positions: np.ndarray,
                      n_readings: int, samples_per_reading: float
                      ) -> np.ndarray:
    """Ruler position at the centre of each of *n_readings* readings:
    *positions* is the ruler count at sample index *step_samples* (one entry
    per ruler change, the first at the pass's start); readings are
    *samples_per_reading* samples long. Interpolated linearly, held flat
    beyond the ends."""
    t = np.asarray(step_samples, dtype=float)
    p = np.asarray(positions, dtype=float)
    if t.size < 2 or t.size != p.size or np.any(np.diff(t) < 0):
        raise DualScanRefused("no_ruler", "too few ruler steps")
    centres = (np.arange(n_readings) + 0.5) * float(samples_per_reading)
    return np.interp(centres, t, p)


def cut_uv_pass(cells, lamp_pos, uv_pos, uv_readings, *, trim: float = TRIM,
                min_readings: int = MIN_UV_READINGS) -> CutResult:
    """The UV reading of each lamp cell. *cells*: [(first lamp reading,
    number of readings)] in patch order; *lamp_pos* / *uv_pos*: ruler
    position of each lamp / UV reading; *uv_readings*: [n_uv, bands]."""
    lp = np.asarray(lamp_pos, dtype=float)
    up = np.asarray(uv_pos, dtype=float)
    ur = np.asarray(uv_readings, dtype=float)
    if ur.ndim != 2 or ur.shape[0] == 0:
        raise DualScanRefused("uv_pass_missing")
    if up.size != ur.shape[0]:
        raise DualScanRefused("no_ruler", "a position per UV reading")
    if not (np.all(np.isfinite(lp)) and np.all(np.isfinite(up)) and np.all(np.isfinite(ur))):
        raise DualScanRefused("bad_values", "positions / UV")
    if lp.size < 2 or np.ptp(lp) <= 0 or np.ptp(up) <= 0:
        raise DualScanRefused("no_ruler", "the ruler did not move")
    if not cells:
        raise DualScanRefused("uv_pass_count", "no cells")
    out, counts, spans = [], [], []
    for start, length in cells:
        start, length = int(start), int(length)
        if length < 1 or start < 0 or start + length > lp.size:
            raise DualScanRefused("uv_pass_count", "cell outside the lamp pass")
        a, b = lp[start], lp[start + length - 1]
        lo, hi = min(a, b), max(a, b)
        w = hi - lo
        m = (up >= lo + trim * w) & (up <= hi - trim * w)
        n = int(m.sum())
        counts.append(n)
        spans.append((lo, hi))
        if n < min_readings:
            raise DualScanRefused(
                "uv_pass_not_aligned",
                f"patch {len(out) + 1}: {n} UV readings (need {min_readings})")
        out.append(ur[m].mean(axis=0))
    flat = _flatness(spans, up, ur, trim)
    return CutResult(uv=np.array(out), counts=counts, flatness=flat)


def _flatness(spans, up, ur, trim) -> float:
    """Within-cell variance over between-cell variance of the 400-500 nm UV
    signal (bands 2..12): the alignment check of the analysis."""
    sig = ur[:, 2:13].mean(axis=1) if ur.shape[1] > 13 else ur.mean(axis=1)
    within, means = [], []
    for lo, hi in spans:
        w = hi - lo
        m = (up >= lo + trim * w) & (up <= hi - trim * w)
        if m.sum() < 2:
            continue
        within.append(sig[m].var())
        means.append(sig[m].mean())
    if len(means) < 2:
        return float("nan")
    return float(np.mean(within) / max(np.var(means), 1e-30))


def pair_spot(lamp, uv) -> "tuple[np.ndarray, np.ndarray]":
    """Spot mode: one lamp and one UV reading per patch, in the same order."""
    L = np.atleast_2d(np.asarray(lamp, dtype=float))
    U = np.atleast_2d(np.asarray(uv, dtype=float)) if uv is not None else None
    if U is None or U.size == 0:
        raise DualScanRefused("uv_pass_missing")
    if L.shape != U.shape:
        raise DualScanRefused("uv_pass_count", f"{L.shape} vs {U.shape}")
    return L, U
