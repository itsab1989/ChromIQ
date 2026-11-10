"""Measurement simulation for the research benchmark (Agent 6, v2 2026-10-03).

A "measured" chart = the truth printer's patches as an instrument reports
them: XYZ under D50 at 1 nm, plus SPEC_380..730 at 10 nm (a 10 nm triangular
bandpass of the 1 nm reflectance). **Both are computed from ONE noisy 1 nm
reflectance per patch** (v2): every noise term, every misread and every strip
misread is applied to the reflectance, and the file's XYZ and its SPEC are
then derived from it. A builder reading the spectra therefore sees the same
noise as one reading the XYZ (flaw 6 of `Validation/agent6-02`: in v1 the
spectra carried per-band noise that averages out in integration, 2.9x less
than the XYZ at ``reread``, 14x less at ``battery``, and no misreads at all).

How the XYZ noise of the calibrated model is put into the spectrum: three
smooth basis functions g_k (Gaussians at 450, 550, 610 nm, sigma 40 nm) are
mixed into a dual basis B with XYZ(B_k) = e_k under the measuring
illuminant, so an XYZ perturbation n (N x 3) becomes the spectral
perturbation n @ B, whose XYZ is exactly n. Misreads are reached with a
smooth multiplicative tilt r * (1 + c @ G) solved for the target XYZ.

Noise levels (``level``):

* ``none``        exact truth (noise-robustness reference only).
* ``battery``     September's model, kept for continuity: independent XYZ
                  noise sigma(Y) = 0.015 + 0.025 exp(-Y/8) per component.
* ``reread``      v1 calibration, kept for continuity: fitted to ONE real pair
                  (May 2026, 90 patches, median 0.088, p95 0.257).
* ``reread2x``    v1 with both sigmas doubled.
* ``typical``     v2 calibration on every real re-read pair on this machine
                  (45 within-session pairs, 2 sessions; ``calibrate_v2.py``):
                  the MEDIAN pair (median 0.145, p95 0.384 dE00).
* ``pessimistic`` the 90th-percentile pair (median 0.186, p95 0.450) PLUS the
                  measured whole-strip misread rate (2 bad strips in 12 real
                  reads of 6 strips: 2.8 % per strip).

Per-patch model of the calibrated levels: a common reflectance scale error
N(0, s_common) (positioning/pressure: moves X, Y, Z together) plus an
additive floor N(0, s_floor) per XYZ component.

Printer-specific settings are honoured (flaw 1: v1 ignored them, so S4 was
bit-identical to S3): ``printer.noise_scale`` multiplies every sigma, and
``printer.misread_prob`` is the isolated-misread rate unless the caller
passes one.

Isolated misreads (all levels except ``none``): with probability
``misread_prob`` a patch is moved 5-40 dE76 in a random Lab direction
(September's model). The real re-read data show NONE of these (0 in 45
pairs x 90 patches); they are a stress test of outlier detection, not a
calibrated quantity. Strip misreads (``pessimistic``, or ``strip_prob``):
consecutive chart rows in strips of ``strip_len``; a bad strip reports each
patch's neighbour's reading (one-position shift, cyclic within the strip), as
when a strip is read misaligned. The first 8 rows (white/black duplicates)
are never touched by either.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from benchmarks.research import colour
from benchmarks.research.colour import LAM_1NM

LAM_10 = np.arange(380.0, 731.0, 10.0)

# v1 constants (May pair only), kept for continuity.
REREAD = {"s_common": 0.0029, "s_floor": 0.010}   # real 0.088 / 0.257, sim 0.089 / 0.259
# v2 constants, from Experiments/agent6/v2/calibration_v2.json (calibrate_v2.py)
TYPICAL = {"s_common": 0.0065, "s_floor": 0.006}      # real 0.145 / 0.384, sim 0.142 / 0.391
PESSIMISTIC = {"s_common": 0.0073, "s_floor": 0.010}  # real 0.186 / 0.450, sim 0.173 / 0.463
STRIP = {"rate": 2 / 72, "len": 15}                   # 2 bad strips in 12 reads x 6 strips

LEVELS = {
    "none": None,
    "battery": None,
    "reread": dict(REREAD, k=1.0, strip=0.0),
    "reread2x": dict(REREAD, k=2.0, strip=0.0),
    "typical": dict(TYPICAL, k=1.0, strip=0.0),
    "pessimistic": dict(PESSIMISTIC, k=1.0, strip=STRIP["rate"]),
}
# the levels every benchmark must run at (protocol v2, section 2)
BENCH_LEVELS = ("typical", "pessimistic")


def bandpass_10nm(refl_1nm: np.ndarray) -> np.ndarray:
    """1 nm reflectance -> 10 nm instrument bands (triangular, FWHM 10 nm)."""
    out = np.empty((refl_1nm.shape[0], len(LAM_10)))
    for j, c in enumerate(LAM_10):
        w = np.clip(1.0 - np.abs(LAM_1NM - c) / 10.0, 0.0, None)
        out[:, j] = refl_1nm @ (w / w.sum())
    return out


def _smooth_basis() -> np.ndarray:
    return np.stack([np.exp(-0.5 * ((LAM_1NM - c) / 40.0) ** 2)
                     for c in (450.0, 550.0, 610.0)])


@lru_cache(maxsize=None)
def xyz_dual_basis(illuminant: str = "D50") -> np.ndarray:
    """(3, 471) smooth spectra B with XYZ(B_k) = e_k under ``illuminant``."""
    g = _smooth_basis()
    m = g @ colour.weights(illuminant).T               # (3 basis, 3 XYZ)
    return np.linalg.solve(m.T, np.eye(3)).T @ g        # B = inv(m)^T-mix of g


def _retarget(refl: np.ndarray, xyz_target: np.ndarray, illuminant: str
              ) -> np.ndarray:
    """Smallest smooth multiplicative tilt that gives ``xyz_target``."""
    g = _smooth_basis()
    w = colour.weights(illuminant)
    out = refl.copy()
    for i in range(len(refl)):
        a = (g * refl[i][None, :]) @ w.T                # (3 basis, 3 XYZ)
        cur = refl[i] @ w.T
        c = np.linalg.lstsq(a.T, xyz_target[i] - cur, rcond=None)[0]
        out[i] = np.clip(refl[i] * (1.0 + c @ g), 0.0, None)
    return out


def strip_rows(n: int, strip_len: int, first: int = 8) -> list[np.ndarray]:
    starts = range(first, n, strip_len)
    return [np.arange(s, min(s + strip_len, n)) for s in starts
            if min(s + strip_len, n) - s > 1]


def measure(printer, device: np.ndarray, level: str = "reread", seed: int = 23,
            misread_prob: float | None = None, illuminant: str = "D50",
            strip_prob: float | None = None, strip_len: int | None = None,
            noise_scale: float | None = None, detail: dict | None = None,
            row_gain: np.ndarray | None = None
            ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """-> (xyz_measured, spec10_measured, misread_rows).

    ``misread_rows`` holds every row whose reading is grossly wrong (isolated
    misreads and strip misreads). ``detail`` (optional dict) receives
    ``isolated`` and ``strips`` separately.

    ``row_gain`` (v3, optional): a multiplicative reflectance factor per
    chart row, applied to the printed reflectance before the instrument
    noise: print non-uniformity across the sheet (``zfamily.print_field``).
    None leaves every earlier level bit-identical (no extra random draws)."""
    if level not in LEVELS:
        raise KeyError(level)
    rng = np.random.default_rng(seed)
    device = np.atleast_2d(device)
    n = len(device)
    refl = np.vstack([printer.reflectance(device[s:s + 2048], LAM_1NM)
                      for s in range(0, len(device), 2048)])
    if row_gain is not None:
        refl = refl * np.asarray(row_gain, float).reshape(-1, 1)
    if level == "none":
        return (colour.xyz_from_reflectance_1nm(refl, illuminant),
                bandpass_10nm(refl), np.array([], int))
    scale = float(getattr(printer, "noise_scale", 1.0) if noise_scale is None
                  else noise_scale)
    if misread_prob is None:
        misread_prob = float(getattr(printer, "misread_prob", 0.005))
    xyz0 = colour.xyz_from_reflectance_1nm(refl, illuminant)
    basis = xyz_dual_basis(illuminant)
    cfg = LEVELS[level]
    if level == "battery":
        sigma = scale * (0.015 + 0.025 * np.exp(-xyz0[:, 1] / 8.0))
        floor = rng.normal(0.0, 1.0, (n, 3)) * sigma[:, None]
        noisy = refl + floor @ basis
    else:
        k = cfg["k"] * scale
        common = 1.0 + rng.normal(0.0, k * cfg["s_common"], (n, 1))
        floor = rng.normal(0.0, k * cfg["s_floor"], (n, 3))
        noisy = refl * common + floor @ basis
    # isolated misreads (September's model), reached in the spectrum
    misread = rng.uniform(size=n) < misread_prob
    misread[:8] = False
    iso = np.flatnonzero(misread)
    if len(iso):
        cur = colour.xyz_from_reflectance_1nm(noisy[iso], illuminant)
        lab = colour.xyz_to_lab(cur)
        d = rng.normal(size=(len(iso), 3))
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        lab = lab + d * rng.uniform(5.0, 40.0, (len(iso), 1))
        noisy[iso] = _retarget(noisy[iso], colour.lab_to_xyz(lab), illuminant)
    # whole-strip misreads: a misaligned strip reports its neighbours
    s_prob = (cfg or {}).get("strip", 0.0) if strip_prob is None else strip_prob
    s_len = STRIP["len"] if strip_len is None else strip_len
    strips = []
    if s_prob > 0:
        for rows in strip_rows(n, s_len):
            if rng.uniform() < s_prob:
                noisy[rows] = noisy[np.roll(rows, -1)].copy()
                strips.append(rows)
    noisy = np.clip(noisy, 0.0, None)
    xyz = colour.xyz_from_reflectance_1nm(noisy, illuminant)
    spec = bandpass_10nm(noisy)
    strip_set = np.concatenate(strips) if strips else np.array([], int)
    if detail is not None:
        detail["isolated"] = iso
        detail["strips"] = [r.tolist() for r in strips]
        detail["noise_scale"] = scale
        detail["misread_prob"] = misread_prob
        detail["strip_prob"] = s_prob
    rows = np.union1d(iso, strip_set).astype(int)
    return xyz, spec, rows


def calibrate_reread(read1: str, read2: str, seeds: int = 40) -> dict:
    """v1 calibration on one pair, kept for reproducibility of ``reread``.
    The v2 calibration over every pair is Experiments/agent6/v2/calibrate_v2.py."""
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
