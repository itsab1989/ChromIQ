"""Measurement simulation for the research benchmark (Agent 6).

A "measured" chart = the truth printer's patches as an instrument reports
them: XYZ under D50 from the 1 nm truth, plus SPEC_380..730 at 10 nm (the
1 nm reflectance averaged through a 10 nm triangular bandpass, as a 10 nm
instrument reports it), both carrying the same noise draw.

Noise models (``level``):

* ``none``       exact truth (for the noise-robustness reference only).
* ``battery``    September's model, kept for continuity: independent XYZ noise
                 sigma(Y) = 0.015 + 0.025 exp(-Y/8) per component.
* ``reread``     calibrated on the owner's two reads of the same 90-patch chart
                 (ColorMunki; Experiments/agent6/real_repeatability.txt):
                 per patch a common reflectance scale error N(0, s_common)
                 (positioning/pressure: moves X, Y, Z together) plus an
                 independent additive floor N(0, s_floor) per XYZ component.
                 Calibration and its result: ``calibrate_reread``.
* ``reread2x``   the same with both sigmas doubled (stress level).

Published instrument figures for context: X-Rite i1Pro 3 short-term
repeatability 0.05 dE00 on white (mean of 10 readings, D50/2), inter-
instrument agreement 0.3 dE00 average / 0.8 max on 12 BCRA tiles (X-Rite
spec sheet L7-701, i1Pro 3 Plus). A chart re-read by hand includes
positioning and print non-uniformity, which a white-tile figure does not,
so the calibrated ``reread`` level sits above the short-term figure.

Misreads (all levels except ``none``): with probability ``misread_prob`` a
patch is moved 5-40 dE76 in a random Lab direction (September's model); the
first 8 rows (white/black duplicates) are never smudged.
"""
from __future__ import annotations

import numpy as np

from benchmarks.research import colour
from benchmarks.research.colour import LAM_1NM

LAM_10 = np.arange(380.0, 731.0, 10.0)

# Calibrated values (see calibrate_reread; re-run to reproduce).
REREAD = {"s_common": 0.0029, "s_floor": 0.010}   # real 0.088 / 0.257, sim 0.089 / 0.259


def bandpass_10nm(refl_1nm: np.ndarray) -> np.ndarray:
    """1 nm reflectance -> 10 nm instrument bands (triangular, FWHM 10 nm)."""
    out = np.empty((refl_1nm.shape[0], len(LAM_10)))
    for j, c in enumerate(LAM_10):
        w = np.clip(1.0 - np.abs(LAM_1NM - c) / 10.0, 0.0, None)
        out[:, j] = refl_1nm @ (w / w.sum())
    return out


def measure(printer, device: np.ndarray, level: str = "reread", seed: int = 23,
            misread_prob: float = 0.005, illuminant: str = "D50"
            ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """-> (xyz_measured, spec10_measured, misread_rows)."""
    rng = np.random.default_rng(seed)
    device = np.atleast_2d(device)
    refl = np.vstack([printer.reflectance(device[s:s + 2048], LAM_1NM)
                      for s in range(0, len(device), 2048)])
    xyz = colour.xyz_from_reflectance_1nm(refl, illuminant)
    spec = bandpass_10nm(refl)
    n = len(device)
    if level == "none":
        return xyz, spec, np.array([], int)
    if level == "battery":
        sigma = 0.015 + 0.025 * np.exp(-xyz[:, 1] / 8.0)
        noisy = xyz + rng.normal(0.0, 1.0, xyz.shape) * sigma[:, None]
        spec = spec * (1.0 + rng.normal(0.0, 0.002, spec.shape))
    elif level in ("reread", "reread2x"):
        k = 2.0 if level == "reread2x" else 1.0
        common = 1.0 + rng.normal(0.0, k * REREAD["s_common"], (n, 1))
        floor = rng.normal(0.0, k * REREAD["s_floor"], xyz.shape)
        noisy = xyz * common + floor
        spec = spec * common + rng.normal(0.0, k * REREAD["s_floor"] / 100.0,
                                          spec.shape)
    else:
        raise KeyError(level)
    misread = rng.uniform(size=n) < misread_prob
    misread[:8] = False
    if misread.any():
        lab = colour.xyz_to_lab(noisy[misread])
        d = rng.normal(size=(misread.sum(), 3))
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        lab = lab + d * rng.uniform(5.0, 40.0, (misread.sum(), 1))
        noisy[misread] = colour.lab_to_xyz(lab)
    return np.clip(noisy, 0.0, None), np.clip(spec, 0.0, None), \
        np.flatnonzero(misread)


def calibrate_reread(read1: str, read2: str, seeds: int = 40) -> dict:
    """Grid-search (s_common, s_floor) so that two simulated reads of read1's
    XYZ reproduce the real read1-vs-read2 dE00 median and p95."""
    import sys
    sys.path.insert(0, ".")
    from workflow.profile_engine.ti3_data import read_ti3
    a, b = read_ti3(read1), read_ti3(read2)
    real = colour.de2000(colour.xyz_to_lab(a.xyz), colour.xyz_to_lab(b.xyz))
    target = np.array([np.median(real), np.percentile(real, 95)])
    best = None
    for sc in np.arange(0.0005, 0.0051, 0.0002):
        for sf in np.arange(0.005, 0.101, 0.005):
            rng = np.random.default_rng(1)
            meds = []
            for _ in range(seeds):
                def draw():
                    return a.xyz * (1 + rng.normal(0, sc, (len(a.xyz), 1))) \
                        + rng.normal(0, sf, a.xyz.shape)
                d = colour.de2000(colour.xyz_to_lab(draw()),
                                  colour.xyz_to_lab(draw()))
                meds.append([np.median(d), np.percentile(d, 95)])
            sim = np.mean(meds, 0)
            err = float(np.sum(((sim - target) / target) ** 2))
            if best is None or err < best[0]:
                best = (err, sc, sf, sim)
    return {"real_median": float(target[0]), "real_p95": float(target[1]),
            "s_common": round(float(best[1]), 5), "s_floor": round(float(best[2]), 4),
            "sim_median": float(best[3][0]), "sim_p95": float(best[3][1])}


if __name__ == "__main__":
    import json
    print(json.dumps(calibrate_reread(
        "/Users/Basti/ChromIQ/printer test/printer test_read1.ti3",
        "/Users/Basti/ChromIQ/printer test/printer test_read2.ti3"), indent=1))
