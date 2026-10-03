"""Which interpolation kernel does each CMM use on a given profile? (Agent 6, v2)

Flaw 7 of `Validation/agent6-02`: v1 said "the battery reads multilinearly
while every CMM reads simplex". Agent 7 (T6) measured that Argyll reads the
engine's 6-ink (``6CLR``) tables N-linearly, so that is not universal. This
module replays an ``mft2`` table with each candidate kernel and reports which
one reproduces a real CMM's output on the same bytes, so the per-CMM table in
:mod:`cmm` is measured, not remembered.

Kernels (all on the CLUT after the input curves, before the output curves):

* ``multilinear``  2^n-corner N-linear (the battery's reader, ColorSync).
* ``simplex``      Kuhn simplex (n+1 vertices, coordinates sorted), which is
                   Argyll's simplex and, for 3 inputs, lcms's tetrahedral.
* ``lcms-linear-over-tetrahedral``  littleCMS's Eval4..Eval15Inputs: linear
                   interpolation in the FIRST input between two evaluations
                   of the remaining inputs, recursively, down to tetrahedral
                   in the last three.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

KERNEL_NAMES = ("multilinear", "simplex", "lcms-linear-over-tetrahedral")


def _flat(idx: np.ndarray, grid: int) -> np.ndarray:
    flat = np.zeros(len(idx), dtype=np.int64)
    for d in range(idx.shape[1]):
        flat = flat * grid + idx[:, d]
    return flat


def _cell(p01: np.ndarray, grid: int):
    idxf = np.clip(p01, 0.0, 1.0) * (grid - 1)
    i0 = np.clip(np.floor(idxf).astype(int), 0, grid - 2)
    return i0, idxf - i0


def multilinear(p01: np.ndarray, clut: np.ndarray, grid: int) -> np.ndarray:
    n = p01.shape[1]
    i0, fr = _cell(p01, grid)
    out = np.zeros((len(p01), clut.shape[1]))
    for c in range(1 << n):
        bits = np.array([(c >> (n - 1 - d)) & 1 for d in range(n)])
        w = np.prod(np.where(bits[None, :] == 1, fr, 1.0 - fr), axis=1)
        out += w[:, None] * clut[_flat(i0 + bits[None, :], grid)]
    return out


def simplex(p01: np.ndarray, clut: np.ndarray, grid: int) -> np.ndarray:
    n = p01.shape[1]
    i0, fr = _cell(p01, grid)
    order = np.argsort(-fr, axis=1, kind="stable")
    fs = np.take_along_axis(fr, order, axis=1)
    vert = i0.copy()
    out = (1.0 - fs[:, 0])[:, None] * clut[_flat(vert, grid)]
    for k in range(n):
        vert = vert.copy()
        vert[np.arange(len(p01)), order[:, k]] += 1
        w = fs[:, k] - (fs[:, k + 1] if k + 1 < n else 0.0)
        out += w[:, None] * clut[_flat(vert, grid)]
    return out


def lcms_linear_over_tetrahedral(p01: np.ndarray, clut: np.ndarray, grid: int
                                 ) -> np.ndarray:
    n = p01.shape[1]
    if n <= 3:
        return simplex(p01, clut, grid)
    i0, fr = _cell(p01[:, :1], grid)
    sub = clut.reshape(grid, -1, clut.shape[1])
    lo = np.empty((len(p01), clut.shape[1]))
    hi = np.empty_like(lo)
    for g in np.unique(i0[:, 0]):
        m = i0[:, 0] == g
        lo[m] = lcms_linear_over_tetrahedral(p01[m, 1:], sub[g], grid)
        hi[m] = lcms_linear_over_tetrahedral(p01[m, 1:], sub[g + 1], grid)
    return lo + fr[:, :1] * (hi - lo)


_FUNCS = {"multilinear": multilinear, "simplex": simplex,
          "lcms-linear-over-tetrahedral": lcms_linear_over_tetrahedral}


def apply(lut, x01: np.ndarray, kernel: str) -> np.ndarray:
    """Replay an ``iccread.Mft2`` with ``kernel`` (input curves, CLUT, output
    curves; the 3x3 matrix is identity in every table we read)."""
    x = np.clip(np.atleast_2d(x01), 0.0, 1.0)
    shaped = np.empty_like(x)
    for c in range(lut.n_in):
        t = lut.in_tables[c]
        shaped[:, c] = np.interp(x[:, c], np.linspace(0.0, 1.0, len(t)), t)
    mid = _FUNCS[kernel](shaped, lut.clut, lut.grid)
    out = np.empty_like(mid)
    for c in range(lut.n_out):
        t = lut.out_tables[c]
        out[:, c] = np.interp(mid[:, c], np.linspace(0.0, 1.0, len(t)), t)
    return out


def a2b(path, device01: np.ndarray, kernel: str, tag: str = "A2B1") -> np.ndarray:
    from benchmarks.iccread import IccProfile
    p = IccProfile(path)
    return p.pcs_decode(apply(p.lut(tag), device01, kernel))


def b2a(path, lab: np.ndarray, kernel: str, tag: str = "B2A1") -> np.ndarray:
    from benchmarks.iccread import IccProfile
    p = IccProfile(path)
    return apply(p.lut(tag), p.pcs_encode(lab), kernel)


def identify(path, reader: str, direction: str = "a2b", n: int = 300,
             seed: int = 5) -> dict:
    """Read ``path`` through the real CMM ``reader`` and through every kernel
    emulation; -> {kernel: max |difference|} (Lab units for A2B, device
    percent for B2A) and ``best``."""
    from benchmarks.research import cmm
    path = Path(path)
    n_ch, additive = cmm._profile_n(path)
    rng = np.random.default_rng(seed)
    if direction == "a2b":
        x = rng.uniform(0, 1, (n, n_ch))
        real = cmm.a2b(path, x, reader)
        diffs = {k: float(np.abs(a2b(path, x, k) - real).max()) for k in KERNEL_NAMES}
    else:
        lab = np.column_stack([rng.uniform(5, 95, n), rng.uniform(-60, 60, n),
                               rng.uniform(-60, 60, n)])
        real = cmm.b2a(path, lab, reader)
        diffs = {k: float(100 * np.abs(np.clip(b2a(path, lab, k), 0, 1) - real).max())
                 for k in KERNEL_NAMES}
    best = min(diffs, key=diffs.get)
    return {"reader": reader, "direction": direction, "n_inks": n_ch,
            "space": path.read_bytes()[16:20].decode("latin1"),
            "pcs": path.read_bytes()[20:24].decode("latin1"),
            "max_diff": diffs, "best": best}
