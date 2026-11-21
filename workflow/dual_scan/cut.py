"""The UV pass of a hand-held dual strip cut into the lamp pass's patches.

In a hand-held dual scan the strip is swiped twice: forward under the lamp,
back under the UV LED (i1Profiler: lamp pass with "ruler start", UV pass
with "ruler end", so ONE continuous ruler stream covers both). ArgyllCMS's
patch recogniser finds the patches in the lamp pass (cells: first reading
and number of readings, already trimmed by ArgyllCMS to the clean middle
66 % of each patch). Each reading of either pass has a ruler position
(the position at the reading's centre, interpolated between ruler steps,
as ArgyllCMS's i1Pro 3 code does). A lamp cell spans a position range (its
first to its last reading); the UV readings whose position lies in that
span less :data:`EDGE_STEPS` ruler steps at each end are averaged into that
patch's UV reading.

THE WINDOW (after 4.3.54, 2026-11-21). Until 4.3.54 the window was the
central 60 % of the span (``TRIM`` 0.2 at each end), on top of ArgyllCMS's
own trim, so the UV pass needed about 1.5 times slower movement than the
lamp pass (27 of 87 UV passes refused on a tester's instrument). The half
step's PHYSICAL reason: the ruler's count labels the same stripe edge one
count apart in the two directions, so the UV pass's positions sit about one
step off the lamp pass's (instrument 1's 13 recorded hand dual strips: 0.55
to 1.45 steps, median 0.85); the span lies half a lamp reading inside the
lamp readings' own extent, so only the last half step at the leading end
shows the neighbouring patch (0.7 % of the difference at the recorded speed,
1.7 % at 1.5 times; 0.1 % further in). Replayed: M1 / M2 against i1Profiler
unchanged within 0.001 dE00 mean; the speed at which the first strip is
refused rises from about 1.05 to about 1.5 times the recorded one (the lamp
pass's own limit is about 1.67). The C twin is ``chromiq_dualscan.c``
(``CQ_DUAL_EDGE_STEPS``). Work folder 2026-11-21_uv_pass_build, proof.txt.

SOURCE: the first analysis of 2026-11-17 (private), ``process.py::_uv_cut``:
alignment checked 0.00001-0.00004 (variance inside the carried-over cells
against between them) in place against 0.09-0.35 half a pitch off.

ALIGNMENT (review of 2026-11-18, S3). The same analysis's alignment measure
(:func:`_flatness`) is now a gate: above :data:`MAX_FLATNESS` the UV pass
does not line up with the lamp pass (the instrument lifted between the
passes, the ruler's count lost, half a pitch off) and is refused with
``uv_pass_misaligned``. Measured: 0.00001-0.00004 in place, 0.09-0.35 half a
pitch off; the gate sits 250 times above the first and 9 times below the
second. It is asked only when the strip's patches differ enough to tell
(:data:`MIN_ALIGN_SPREAD`, at least 3 patches); otherwise
``CutResult.aligned_checked`` is False (note ``alignment_not_checked``).

On the i1iO 2 table in spot mode there is nothing to cut: one lamp and one
UV reading per patch (:func:`pair_spot`).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from workflow.dual_scan.reasons import DualScanRefused

#: ruler steps left out at each end of a cell's span (the direction offset
#: of the ruler's count; module docstring)
EDGE_STEPS = 0.5
#: fraction of a cell's span left out at each end by the ALIGNMENT gate
#: (:func:`_flatness`) only; not the UV readings' window since 4.3.54
TRIM = 0.2
#: fewest UV readings a patch may be averaged from (a noise floor: three
#: readings of 4.9 ms, the lamp pass's own integration)
MIN_UV_READINGS = 3
#: largest within-cell / between-cell variance of an aligned pass
MAX_FLATNESS = 0.01
#: fewest relative spread (std / mean) of the cells' UV signal to judge it
MIN_ALIGN_SPREAD = 0.05


@dataclass
class CutResult:
    uv: np.ndarray            # [P, bands] the UV pass per patch
    counts: "list[int]"       # UV readings averaged per patch
    flatness: float           # within-cell / between-cell variance (small = aligned)
    aligned_checked: bool = True   # False: the patches hardly differ, not judged


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
                min_readings: int = MIN_UV_READINGS,
                edge: float = EDGE_STEPS) -> CutResult:
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
    if np.any(np.diff(up) == 0) and np.count_nonzero(np.diff(up)) < up.size // 2:
        raise DualScanRefused("uv_pass_stalled", "the ruler stood still")
    out, counts, spans = [], [], []
    for start, length in cells:
        start, length = int(start), int(length)
        if length < 1 or start < 0 or start + length > lp.size:
            raise DualScanRefused("uv_pass_count", "cell outside the lamp pass")
        a, b = lp[start], lp[start + length - 1]
        lo, hi = min(a, b), max(a, b)
        m = (up >= lo + edge) & (up <= hi - edge)
        counts.append(int(m.sum()))
        spans.append((lo, hi))
        out.append(ur[m].mean(axis=0) if m.any() else np.full(ur.shape[1], np.nan))
    verdict = travel_verdict(counts, min_readings)
    if verdict is not None:
        raise DualScanRefused(verdict, f"UV readings per patch {counts}")
    flat = _flatness(spans, up, ur, trim)
    if flat == flat and flat > MAX_FLATNESS:
        raise DualScanRefused("uv_pass_misaligned", f"flatness {flat:.5f}")
    return CutResult(uv=np.array(out), counts=counts, flatness=flat,
                     aligned_checked=flat == flat)


def travel_verdict(counts: "list[int]", min_readings: int = MIN_UV_READINGS
                   ) -> "str | None":
    """Why a UV pass's readings per patch do not make a pass (None = fine):

    * ``uv_pass_short``: one or more patches at an END got no reading (the
      second pass did not cover the whole strip);
    * ``uv_pass_stalled``: a patch INSIDE the strip got none while patches
      on both sides did (a gap or a stall);
    * ``uv_pass_too_fast``: every patch was reached but some by fewer than
      *min_readings* readings (move a little slower)."""
    c = list(counts)
    if not c:
        return "uv_pass_count"
    if c[0] == 0 or c[-1] == 0:
        return "uv_pass_short"
    if any(v == 0 for v in c):
        return "uv_pass_stalled"
    if min(c) < min_readings:
        return "uv_pass_too_fast"
    return None


def pass_direction(positions) -> int:
    """+1 when the ruler counted up over the pass, -1 down, 0 not moving.
    Either direction is a good pass; the ruler says which."""
    p = np.asarray(positions, dtype=float)
    if p.size < 2:
        return 0
    d = p[-1] - p[0]
    return 0 if d == 0 else (1 if d > 0 else -1)


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
    if len(means) < 3:
        return float("nan")
    mu = float(np.mean(means))
    if not (abs(mu) > 0 and np.std(means) / abs(mu) >= MIN_ALIGN_SPREAD):
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
