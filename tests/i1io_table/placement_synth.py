# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""Synthetic strip rows SHAPED LIKE THE RECORDED ONES, for the row placement check's tests (4.3.54).

The recordings are private and never enter the repository; what they MEASURED is built in here
(the row placement study of 21 Nov 2026, ``how_it_works_today.txt`` / ``edges.txt``):

* the reading: the i1Pro 2's 4.5 mm aperture (a circle: each slice weighted by its chord) swept
  over the 5.004 ms of one reading, the first reading 0.370 s after the lamp trigger;
* the motion: the planned trapezoid (V, A = 5 V ms), started *dt* after ChromIQ's assumed 0.372 s,
  optionally *speed_err* faster or slower, plus the real arm's S-shaped start (up to 0.9 mm
  behind the trapezoid at 0.15 s) and its ripple in cruise (about 0.1 mm);
* the sheet: ChromIQ's own row (patch + contrast spacer, or no spacer), the whole row *dx* mm
  off where the aims put it (the aims and the print: 1 to 2.5 mm measured), every patch edge
  jittered by *print_sd* (0.15 mm clean, 0.45 mm vendor-like);
* the noise: per reading, a gain and a per-band term, sized like the recorded clean plateaus
  (single readings 0.1 to 0.4 dE00 from their patch, darker patches noisier).

Everything is seeded: the same arguments give the same row.
"""
from __future__ import annotations

import math
import os

import numpy as np

from workflow.dual_scan.colour import de00_spectra, spec_to_lab
from workflow.i1io.table import scan as sc
from workflow.i1io.table import strip as stp

WL = [380 + 10 * j for j in range(36)]
PAPER = np.full(36, 0.88)


def palette(seed: int = 7, n: int = 40) -> np.ndarray:
    """Printed-looking spectra: smooth, 0.03..0.9, lights, darks and saturated ones."""
    rng = np.random.default_rng(seed)
    out = []
    x = np.linspace(0, 1, 36)
    for i in range(n):
        knots = rng.uniform(0.03, 0.9, 5)
        if i % 5 == 0:
            knots *= 0.15                       # a dark patch (L* below 30)
        v = np.interp(x, np.linspace(0, 1, 5), knots)
        v = np.convolve(np.pad(v, 3, mode="edge"), np.ones(7) / 7, mode="valid")
        out.append(np.clip(v, 0.02, 0.92))
    return np.array(out)


PALETTE = palette()
#: ChromIQ's contrast spacers: a few extreme colours, the one most unlike both neighbours
SPACERS = np.array([np.full(36, 0.04), np.full(36, 0.88),
                    np.interp(np.arange(36), [0, 12, 24, 35], [0.05, 0.05, 0.8, 0.85]),
                    np.interp(np.arange(36), [0, 12, 24, 35], [0.8, 0.85, 0.05, 0.05]),
                    np.interp(np.arange(36), [0, 10, 20, 35], [0.1, 0.8, 0.1, 0.1])])


def plan(patch_mm: float, speed: int, spacer_mm: float = 1.0, n: int = 24,
         run_in: float = 9.0, name: str = "r"):
    pitch = patch_mm + spacer_mm
    length = 2 * run_in + pitch * (n - 1) + patch_mm
    pts = [sc.Patch(str(i + 1), f"A{i + 1}", ((run_in + patch_mm / 2 + i * pitch) * 10.0, 0.0),
                    half_mm=patch_mm / 2) for i in range(n)]
    return sc.plan_row(name, (0, 0), (int(round(length * 10)), 0), speed, pts)


def _kernel(sweep_mm: float, ap: float = 4.5, step: float = 0.05):
    r = ap / 2
    u = np.arange(-r - sweep_mm / 2 - step, r + sweep_mm / 2 + step, step)
    chord = np.sqrt(np.clip(r * r - u * u, 0, None))
    box = np.ones(max(1, int(round(sweep_mm / step))))
    k = np.convolve(chord, box / box.sum(), mode="same")
    return u, k / k.sum()


def _pos(p, t):
    from workflow.i1io.table.placement import _positions
    return _positions(p, t)


class Row:
    """One synthetic pass: ``readings`` (list of spectra), ``truth`` (each patch's colour),
    ``clean`` (per patch, the readings whose whole footprint lies on that patch)."""

    def __init__(self, p, *, dt_s=0.0, dx_mm=0.0, scale=0.0, speed_err=0.0, print_sd=0.15,
                 seed=1, spacer_mm=1.0, noise=1.0, lag=True, colours=None, spacer=None,
                 patch_shift=None):
        rng = np.random.default_rng(seed)
        n = len(p.patches)
        half = p.patches[0].half_mm
        cols = (PALETTE[rng.choice(len(PALETTE), n, replace=True)] if colours is None
                else np.asarray(colours, float))
        self.truth = cols
        cen = np.array([q.along_mm for q in p.patches])
        # the sheet along the row (paper coordinates = what the aims call the row's place)
        edges = []
        for i, c in enumerate(cen):
            # *patch_shift* {index: mm}: that one patch printed so far along the row (4.3.54 fix
            # round: a row refused by the run tolerance alone)
            c = c + float((patch_shift or {}).get(i, 0.0))
            edges.append((c - half + rng.normal(0, print_sd), c + half + rng.normal(0, print_sd)))
        segs = [(-1e3, edges[0][0], PAPER)]
        lab = spec_to_lab(cols)
        slab = spec_to_lab(SPACERS)
        for i in range(n):
            segs.append((edges[i][0], edges[i][1], cols[i]))
            if i < n - 1:
                if spacer is not None:
                    sp_ = np.asarray(spacer, float)
                elif spacer_mm > 0:
                    sc_ = [min(float(de00_spectra(SPACERS[j:j + 1], cols[i:i + 1])[0]),
                               float(de00_spectra(SPACERS[j:j + 1], cols[i + 1:i + 2])[0]))
                           for j in range(len(SPACERS))]
                    sp_ = SPACERS[int(np.argmax(sc_))]
                else:
                    sp_ = cols[i]                 # no spacer: the patches abut
                segs.append((edges[i][1], edges[i + 1][0], sp_))
        segs.append((edges[-1][1], 1e4, PAPER))
        # the motion
        N = p.N
        t = sc.FIRST_READING_AFTER_LAMP_S + np.arange(N) * sc.READING_S \
            - (sc.MOTION_START_AFTER_LAMP_S + dt_s)
        sub = (np.arange(5) + 0.5) / 5 * sc.READING_S
        tt = (t[:, None] + sub[None, :]) * (1.0 + speed_err)
        arm = _pos(p, tt)
        if lag:
            arm = arm - 0.9 * np.exp(-((tt - 0.15) / 0.09) ** 2) * (tt > 0) \
                + 0.1 * np.sin(2 * math.pi * 7.0 * tt) * (tt > 0.3)
        # where on the paper the opening is: the row lies dx further on, its scale off by *scale*
        L = p.dist / 10.0
        paper = arm - dx_mm - scale * (arm - L / 2)
        u, k = _kernel(0.0)
        xb = np.array([s[0] for s in segs] + [segs[-1][1]])
        colarr = np.array([s[2] for s in segs])
        pts = paper[:, :, None] + u[None, None, :]
        idx = np.clip(np.searchsorted(xb, pts, side="right") - 1, 0, len(segs) - 1)
        refl = np.einsum("m,nsmb->nb", k, colarr[idx]) / 5.0
        # the noise: a gain per reading and a smooth per-band term, darker = relatively noisier
        g = 1.0 + noise * rng.normal(0, 0.002, (N, 1))
        band = noise * rng.normal(0, 0.002, (N, 36))
        band = np.apply_along_axis(lambda r: np.convolve(r, np.ones(5) / 5, mode="same"), 1, band)
        refl = refl * g + band * np.sqrt(np.clip(refl, 0.02, 1.0)) \
            + noise * rng.normal(0, 0.0004, (N, 36))
        self.readings = np.clip(refl, 0.001, 1.2)
        reach = 2.25 + p.speed * sc.READING_S
        mid = paper.mean(axis=1)
        self.clean = [np.nonzero((mid - reach >= a) & (mid + reach <= b))[0] for a, b in edges]
        self.edges = edges

    def floor(self) -> np.ndarray:
        """Per patch: the dE00 of its truly clean readings' mean (the best a window can do)."""
        out = []
        for i, w in enumerate(self.clean):
            if len(w) == 0:
                out.append(0.0)
                continue
            out.append(float(de00_spectra(self.readings[w].mean(0, keepdims=True),
                                          self.truth[i:i + 1])[0]))
        return np.array(out)


def write_and_cut(p, row: Row, folder) -> "stp.Cut":
    """The released strip row's cut (strip.cut_row) on the row's readings, as the job makes it."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, p.name + ".spec.csv")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("reading," + ",".join(str(w) for w in WL) + "\n")
        for i, r in enumerate(row.readings):
            fh.write(f"{i}," + ",".join(f"{v:.6f}" for v in r) + "\n")
    return stp.cut_row(p, str(folder), {"ok": True, "got": len(row.readings)})


def errors(cut, row: Row) -> np.ndarray:
    got = np.array([c[2] for c in cut.patches])
    return de00_spectra(got, row.truth)
