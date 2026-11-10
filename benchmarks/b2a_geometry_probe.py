"""B2A table geometry probe (agent D, 2026-09-05) — measurement only.

The RGB printers' B2A rows are owned by the B2A table's interpolation
(written profile 0.29 / 0.68 on S1 / S2 vs the model inverted directly
0.09 / 0.21). At quality m the B2A grid is 17 per axis and the a/b axes
span −128…128 while a print gamut reaches |a|,|b| ≈ 90: a third of the
cells hold nothing printable. This probe builds one battery printer with
the shipped Lab codec and with a codec whose a/b axes spend ``outer``
cells beyond the fitted model's own gamut edge (+ ``margin``) and the
rest inside, scores both written profiles with the referee, and scores
the outer band against the exact hue-preserving clip.

Measured (quality m, 900 patches, 20 k eval points), B2A median / p95:
  S1 outer=1  0.289 → 0.217 (−25 %) / 1.234 → 1.024 (−17 %)
  S1 outer=2  −3 % / −4 %;  outer=3  +31 % (cells coarser than legacy)
  S2 outer=1  0.680 → 0.652 (−4.2 %) / +0.4 %;  outer=2  +14 %
  S3 outer=2  −3.9 % / −4.2 %
The gain follows the interior cell width against the legacy 16 units
(S1: 12.5 at outer=1, 14.4 at outer=2, 17.0 at outer=3) and the far
out-of-gamut clip gets coarser (S1 outer band vs the exact clip: median
0.41 → 0.79, p95 8.6 → 10.2). Not landed: S2 misses the ≥ 5 % gate.

    python -m benchmarks.b2a_geometry_probe S1 --outer 1 --margin 4
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

from benchmarks.battery import score_profile
from benchmarks.iccread import IccProfile
from benchmarks.synthetic import (PRINTERS, eval_points, make_chart, measure,
                                  write_ti3)
from workflow.profile_engine import b2a as b2a_mod
from workflow.profile_engine import builder as builder_mod
from workflow.profile_engine import icc_writer as icw
from workflow.profile_engine.builder import BuildSettings, build_profile
from workflow.profile_engine.metrics import delta_e_2000
from workflow.profile_engine.pcs import LabPcs


def fitted_lab_codec(edge: float, outer: int, grid: int):
    """A Lab codec whose a/b axes put ``outer`` cells beyond ±``edge``."""
    lo, hi = icw.LAB16_MIN_AB, icw.LAB16_MAX_AB
    if edge >= min(-lo, hi) - 1.0:
        return LabPcs
    c = outer / (grid - 1)

    def ab_to01(v):
        return np.interp(v, [lo, -edge, edge, hi], [0.0, c, 1.0 - c, 1.0])

    class FittedLab(LabPcs):
        @staticmethod
        def node_lab(g):
            ls, _ab = icw.lab_grid_axes(g)
            u = np.linspace(0.0, 1.0, g)
            ab = np.interp(u, [0.0, c, 1.0 - c, 1.0], [lo, -edge, edge, hi])
            return np.stack(np.meshgrid(ls, ab, ab, indexing="ij"),
                            -1).reshape(-1, 3)

        @staticmethod
        def lab_to01(lab):
            out = np.empty_like(lab, dtype=float)
            out[:, 0] = lab[:, 0] / 100.0
            out[:, 1] = ab_to01(lab[:, 1])
            out[:, 2] = ab_to01(lab[:, 2])
            return np.clip(out, 0.0, 1.0)

        @staticmethod
        def b2a_in_tables(entries):
            ident = np.linspace(0.0, 1.0, entries)
            l_tab = np.clip(ident * (0xFFFF / 0xFF00), 0.0, 1.0)
            ab_tab = ab_to01(lo + ident * (hi - lo))
            rows = np.stack([l_tab, ab_tab, ab_tab])
            return np.clip(rows * 0xFFFF, 0, 0xFFFF).round().astype(">u2")

    return FittedLab


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("printer", default="S1", nargs="?")
    ap.add_argument("--outer", type=int, default=1)
    ap.add_argument("--margin", type=float, default=4.0)
    ap.add_argument("--quality", default="m")
    ap.add_argument("--out", default=".bench/geometry")
    a = ap.parse_args(argv)
    printer = PRINTERS[a.printer]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    chart = make_chart(printer, 900)
    xyz, refl, _ = measure(printer, chart)
    ti3 = write_ti3(out / f"{a.printer}.ti3", printer, chart, xyz, refl)
    settings = BuildSettings(quality=a.quality, gammap_mode="accurate",
                             ink_limit=printer.tac)
    icc0 = out / f"{a.printer}-shipped.icc"
    t0 = time.perf_counter()
    res = build_profile(ti3, icc0, settings)
    t_ship = time.perf_counter() - t0
    edge = float(np.abs(res.model.clut_lab()[:, 1:]).max()) + a.margin
    print(f"{a.printer}: gamut |a|,|b| max {edge - a.margin:.2f}, edge "
          f"{edge:.2f}, grid {res.b2a_grid}, outer cells {a.outer}")
    codec = fitted_lab_codec(edge, a.outer, res.b2a_grid)
    orig = builder_mod.codec_for
    builder_mod.codec_for = lambda *args, **kw: codec
    try:
        icc1 = out / f"{a.printer}-fitted-o{a.outer}.icc"
        t0 = time.perf_counter()
        build_profile(ti3, icc1, settings)
        t_fit = time.perf_counter() - t0
    finally:
        builder_mod.codec_for = orig
    s0 = score_profile(printer, icc0, 20000)
    s1 = score_profile(printer, icc1, 20000)
    for k in ("a2b", "b2a", "roundtrip"):
        print(f"{k:9s} shipped med {s0[k]['median']:.3f} p95 {s0[k]['p95']:.3f}"
              f" | fitted med {s1[k]['median']:.3f} p95 {s1[k]['p95']:.3f}"
              f"  ({100 * (s1[k]['median'] / s0[k]['median'] - 1):+.1f} % /"
              f" p95 {100 * (s1[k]['p95'] / s0[k]['p95'] - 1):+.1f} %)")
    for k in ("k_tv_excess", "oog_hue"):
        if k in s0:
            print(k, s0[k], "->", s1[k])
    print(f"build s {t_ship:.0f} -> {t_fit:.0f}")
    # The outer band (|a| or |b| beyond the edge) against the exact clip.
    rng = np.random.default_rng(1)
    n = 3000
    src = np.stack([rng.uniform(20, 90, n),
                    rng.choice([-1, 1], n) * rng.uniform(edge, 127, n),
                    rng.uniform(-100, 100, n)], 1)
    meas = res.measurement
    d_exact, _r = b2a_mod.invert_to_device(
        res.model, src, channel_letters=meas.channel_letters,
        is_additive=printer.is_additive, ink_limit=printer.tac,
        accurate=True,
        black_l=float(meas.lab_relative[meas.black_index, 0]))
    ref = printer.lab_relative_true(d_exact)
    for name, path in (("shipped", icc0), ("fitted", icc1)):
        dev = IccProfile(path).b2a_device(src, "B2A1")
        d = delta_e_2000(printer.lab_relative_true(dev), ref)
        print(f"outer band vs exact clip, {name:8s}: med {np.median(d):.3f} "
              f"p95 {np.percentile(d, 95):.3f} max {d.max():.2f}")


if __name__ == "__main__":
    main()
