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

LINED UP FIRST (second fix round of 2026-11-21, the verification's V1). The
UV positions are corrected by the offset measured per strip
(:func:`estimate_offset`, the helper's ``cq_dual_align``) before the cut; the
window is then the span less :data:`EDGE_STEPS` (0.25). Replayed per patch with
the UV positions shifted -6 to +6 steps at 1 to 1.5 times the speed: every
patch of every accepted strip within 0.09 dE00 (M2) of the same patch at the
recorded alignment. The text below is the first version's (half a step,
without the correction).

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

#: ruler steps left out at each end of a cell's span AFTER the UV positions
#: are lined up (estimate_offset): the estimate's own scatter, at most 0.20
#: steps replayed at up to 1.5 times the speed and 5 times the noise, rounded
#: up to the next quarter step (second fix round of 2026-11-21; module docstring)
EDGE_STEPS = 0.25
#: lining the UV pass up (chromiq_dualscan.h CQ_DUAL_ALIGN_*): the shifts tried,
#: their step, the fewest UV readings a shift is judged on, the largest offset
#: taken (beyond it the instrument moved between the passes further than
#: anything recorded: -1.0 to +1.45 steps on 13 strips), and how much worse the
#: fit must be one step either side (good passes: 1.36 at least)
ALIGN_SPAN = 6.5
ALIGN_STEP = 0.05
ALIGN_MIN_READINGS = 20
MAX_OFFSET = 3.0
MIN_RISE = 1.15
#: what estimate_offset says when there is nothing clear to line up by: NOT a
#: refusal; the strip is cut uncorrected with 4.3.54's window (``CQ_DUAL_NOT_LINED_UP``)
NOT_LINED_UP = "not_lined_up"
#: fraction of a cell's span left out at each end by the ALIGNMENT gate
#: (:func:`_flatness`) only; not the UV readings' window since 4.3.54
TRIM = 0.2
#: fewest UV readings a patch may be averaged from (a noise floor: three
#: readings of 4.9 ms, the lamp pass's own integration)
MIN_UV_READINGS = 3
#: largest within-cell / between-cell variance of an aligned pass
MAX_FLATNESS = 0.01
#: the same over the AVERAGING window (fix round of 2026-11-21, review B1;
#: ``CQ_DUAL_MAX_EDGE_FLATNESS``): above it ``uv_pass_shifted``. A second
#: check only: an average over the strip, it does not hold a single patch end
#: (the verification's V1); the alignment (estimate_offset) does. Recorded
#: passes give at most 0.00008, simulated up to 1.75 times faster 0.00027
MAX_EDGE_FLATNESS = 0.001
#: fewest relative spread (std / mean) of the cells' UV signal to judge it
MIN_ALIGN_SPREAD = 0.05


@dataclass
class CutResult:
    uv: np.ndarray            # [P, bands] the UV pass per patch
    counts: "list[int]"       # UV readings averaged per patch
    flatness: float           # within-cell / between-cell variance (small = aligned)
    aligned_checked: bool = True   # False: the patches hardly differ, not judged
    window_flatness: float = float("nan")   # the same over the averaging window
    offset: float = 0.0       # the UV positions' measured offset, subtracted (estimate_offset)
    rise: float = float("nan")    # how clearly that offset fits best
    lined_up: str = "not_asked"   # "lined_up", "not_lined_up" (4.3.54's window) or "not_asked"


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
                edge: "float | None" = EDGE_STEPS, lamp_sig=None) -> CutResult:
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
    offset, rise, lined = 0.0, float("nan"), "not_asked"
    if lamp_sig is not None:
        # the helper's order (chromiq_dualdev.c): line the UV pass up first
        ends = []
        for start, length in cells:
            start, length = int(start), int(length)
            if length < 1 or start < 0 or start + length > lp.size:
                raise DualScanRefused("uv_pass_count", "cell outside the lamp pass")
            ends += [lp[start], lp[start + length - 1]]
        why, offset, rise = estimate_offset(lp, lamp_sig, up, ur[:, :3].mean(axis=1),
                                            min(ends), max(ends))
        lined = "lined_up"
        if why == NOT_LINED_UP:
            offset, edge, lined = 0.0, None, NOT_LINED_UP   # 4.3.54's central window, uncorrected
        elif why is not None:
            raise DualScanRefused(why, f"offset {offset:+.2f} rise {rise:.2f}")
        up = up - offset
    out, counts, spans = [], [], []
    for start, length in cells:
        start, length = int(start), int(length)
        if length < 1 or start < 0 or start + length > lp.size:
            raise DualScanRefused("uv_pass_count", "cell outside the lamp pass")
        a, b = lp[start], lp[start + length - 1]
        lo, hi = min(a, b), max(a, b)
        if edge is None:
            m = (up >= lo + trim * (hi - lo)) & (up <= hi - trim * (hi - lo))
        else:
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
    # the passes lined up over the readings that are averaged (review B1)
    wflat = _flatness(spans, up, ur, trim, edge=edge) if edge is not None else float("nan")
    if wflat == wflat and wflat > MAX_EDGE_FLATNESS:
        raise DualScanRefused("uv_pass_shifted", f"window flatness {wflat:.5f}")
    return CutResult(uv=np.array(out), counts=counts, flatness=flat,
                     aligned_checked=flat == flat, window_flatness=wflat,
                     offset=offset, rise=rise, lined_up=lined)


def estimate_offset(lamp_pos, lamp_sig, uv_pos, uv_sig, lo: float, hi: float
                    ) -> "tuple[str | None, float, float]":
    """(reason or None, offset, rise): the C twin is chromiq_dualscan.c
    ``cq_dual_align`` (its header says why and how). *lamp_sig* / *uv_sig*:
    each reading's (T / W)-weighted / own 380-400 nm mean; [lo, hi]: the
    positions the strip's patches span. Subtract *offset* from the UV
    positions."""
    lp = np.asarray(lamp_pos, dtype=float)
    ls = np.asarray(lamp_sig, dtype=float)
    up = np.asarray(uv_pos, dtype=float)
    us = np.asarray(uv_sig, dtype=float)
    if lp.size < 2 or up.size < ALIGN_MIN_READINGS:
        return NOT_LINED_UP, 0.0, float("nan")
    o = np.argsort(lp, kind="stable")
    xs, ys = lp[o], ls[o]
    nk = int(np.floor(2.0 * ALIGN_SPAN / ALIGN_STEP + 0.5)) + 1
    res = np.full(nk, -1.0)
    best, bestk = 0.0, -1
    for k in range(nk):
        d = -ALIGN_SPAN + k * ALIGN_STEP
        x = up - d
        sel = (x >= lo) & (x <= hi)
        n = int(sel.sum())
        if n < ALIGN_MIN_READINGS:
            continue
        pr = np.interp(x[sel], xs, ys)
        pp, pu, ssum = float(np.dot(pr, pr)), float(np.dot(pr, us[sel])), float(us[sel].sum())
        if not pp > 0.0 or ssum == 0.0:
            continue
        g = pu / pp
        e = us[sel] - g * pr
        res[k] = np.sqrt(float(np.dot(e, e)) / n) / (ssum / n)
        if bestk < 0 or res[k] < best:
            best, bestk = res[k], k
    if bestk < 0:
        return NOT_LINED_UP, 0.0, float("nan")
    bestd = -ALIGN_SPAN + bestk * ALIGN_STEP
    ds = -ALIGN_SPAN + np.arange(nk) * ALIGN_STEP
    far = (res >= 0.0) & (np.abs(ds - bestd) >= 1.0 - 1e-9)
    near = float(res[far].min()) if far.any() else -1.0
    r = (1.0 if near < 0.0 else near / best if best > 0.0
         else float("inf") if near > 0.0 else 1.0)
    if not r >= MIN_RISE:
        return NOT_LINED_UP, bestd, r
    if abs(bestd) > MAX_OFFSET + 1e-9:
        return "uv_pass_shifted", bestd, r
    return None, bestd, r


def lamp_led_signal(lamp_readings, white, tile) -> np.ndarray:
    """Each lamp reading's 380-400 nm mean weighted by the tile's T / W there:
    what the UV pass should read at the same place (nothing glows below 410 nm)."""
    lr = np.asarray(lamp_readings, dtype=float)[:, :3]
    tw = np.asarray(tile, dtype=float)[:3] / np.asarray(white, dtype=float)[:3]
    return (lr * tw[None, :]).mean(axis=1)


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


def _flatness(spans, up, ur, trim, edge: "float | None" = None) -> float:
    """Within-cell variance over between-cell variance of the 400-500 nm UV
    signal (bands 2..12): the alignment check of the analysis. The window is
    the central part of each span (*trim* at each end), or with *edge* the
    span less *edge* ruler steps at each end (the averaging window)."""
    sig = ur[:, 2:13].mean(axis=1) if ur.shape[1] > 13 else ur.mean(axis=1)
    within, means = [], []
    for lo, hi in spans:
        w = hi - lo
        if edge is not None:
            m = (up >= lo + edge) & (up <= hi - edge)
        else:
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
