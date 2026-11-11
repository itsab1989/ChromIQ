"""λ oracle sweep on the synthetic battery (agent C, 2026-09-05).

For every battery printer, force the maximum-accuracy fit to each factor
of a wide ladder and score the FITTED MODEL (not the written profile)
against ``f_true``: A2B ΔE2000 on dense evaluation points and a model-level
B2A end-to-end (invert in-gamut targets, print them on the true printer).
Next to those ground-truth numbers it records every chart-only statistic
a selection criterion could see — the held-out score the shipped rule
uses, the fit residual at the patches, the duplicate-patch noise estimate
and the whitened residual the discrepancy principle compares against 1.

The point is to see which λ the PRINT wants per printer, and which
chart-only statistic predicts it. Dev-only; never imported by the app.

CLI (from the repo root, venv active)::

    python -m benchmarks.lambda_sweep --printers S1,S2 --out sweep.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from benchmarks.synthetic import PRINTERS, eval_points, make_chart, \
    measure, write_ti3
from workflow.profile_engine.metrics import delta_e_2000

FACTORS = (0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0)


def _prepare(pid: str, out_dir: Path, n_patches: int = 900):
    from workflow.profile_engine.builder import (_A2B_GRID_23, _A2B_GRID_34,
                                                 _fit_lambda)
    from workflow.profile_engine.ti3_data import read_ti3
    printer = PRINTERS[pid]
    chart = make_chart(printer, n_patches)
    xyz, refl, misread = measure(printer, chart)
    ti3 = write_ti3(out_dir / f"{pid}.ti3", printer, chart, xyz, refl)
    meas = read_ti3(ti3)
    meas.average_endpoints()
    n = meas.n_channels
    grid = (_A2B_GRID_34 if n >= 4 else _A2B_GRID_23)[1]
    while grid ** n > 2_000_000 and grid > 3:
        grid -= 2
    return printer, meas, grid, _fit_lambda(grid), misread


def _b2a_proxy(printer, meas, model, n_targets: int, seed: int = 99) -> dict:
    """Model-level B2A end-to-end: invert true in-gamut Lab targets through
    the fitted model, print the ink on the true printer, ΔE00 to target."""
    from workflow.profile_engine.b2a import invert_to_device
    dev_t = eval_points(printer, n_targets, seed=seed)
    target = printer.lab_relative_true(dev_t)
    black_l = float(meas.lab_relative[meas.black_index, 0])
    d, _res = invert_to_device(
        model, target, channel_letters=meas.channel_letters,
        is_additive=meas.is_additive, ink_limit=printer.tac,
        accurate=True, black_l=black_l,
        extra_hues=meas.extra_ink_hues())
    printed = printer.lab_relative_true(d)
    de = delta_e_2000(printed, target)
    out = {"median": float(np.median(de)),
           "p95": float(np.percentile(de, 95))}
    if not meas.is_additive and meas.n_channels >= 4:
        ls = np.linspace(8.0, 97.0, 90)
        neutral = np.stack([ls, np.zeros_like(ls), np.zeros_like(ls)], 1)
        dk, _ = invert_to_device(
            model, neutral, channel_letters=meas.channel_letters,
            is_additive=False, ink_limit=printer.tac, accurate=True,
            black_l=black_l, extra_hues=meas.extra_ink_hues())
        k = dk[:, 3]
        out["k_tv_excess"] = float(np.abs(np.diff(k)).sum()
                                   - abs(k[-1] - k[0]))
    return out


def sweep_printer(pid: str, out_dir: Path, *, n_eval: int = 8000,
                  n_b2a: int = 300, factors=FACTORS, progress=print) -> dict:
    import workflow.profile_engine.accuracy as acc
    from workflow.profile_engine.gp import patch_noise_sigma
    printer, meas, grid, base_lam, misread = _prepare(pid, out_dir)
    dev, lab = meas.device, meas.lab_relative
    ev = eval_points(printer, n_eval)
    lab_true = printer.lab_relative_true(ev)
    sigma, (n_floor, n_dark) = patch_noise_sigma(dev, lab)
    rows = []
    saved = acc._HOLDOUT_MIN_PATCHES, acc.fit_forward_model
    real_fit = acc.fit_forward_model

    def fixed_scan(device, lab_, **kw):
        # The outlier scan stays at 4× the TRUE base λ whatever factor is
        # forced (it is the only cg_iters=350 call once the search is off).
        if kw.get("cg_iters") == 350:
            kw["lam"] = 4.0 * base_lam
        return real_fit(device, lab_, **kw)

    try:
        acc._HOLDOUT_MIN_PATCHES = 10 ** 9        # search off: λ = base
        acc.fit_forward_model = fixed_scan
        for f in factors:
            t0 = time.perf_counter()
            lines: list[str] = []
            model, outliers, lam = acc.fit_forward_model_accurate(
                dev, lab, grid=grid, base_lam=base_lam * f,
                progress=lines.append)
            secs = time.perf_counter() - t0
            de_true = delta_e_2000(model.predict(ev), lab_true)
            res = delta_e_2000(model.predict(dev), lab)
            res_lab = np.linalg.norm(model.predict(dev) - lab, axis=1)
            keep = np.ones(len(dev), bool)
            keep[outliers] = False
            whitened = res_lab[keep] / (np.sqrt(3.0) * sigma[keep])
            row = {"factor": f, "lam": lam, "seconds": secs,
                   "a2b_true": {"median": float(np.median(de_true)),
                                "p95": float(np.percentile(de_true, 95))},
                   "chart_res_de00_median": float(np.median(res[keep])),
                   "chart_res_lab_rms": float(np.sqrt(np.mean(
                       res_lab[keep] ** 2))),
                   "whitened_rms": float(np.sqrt(np.mean(whitened ** 2))),
                   "whitened_median": float(np.median(whitened)),
                   "n_outliers": int(len(outliers)),
                   "log": [ln for ln in lines if ln.startswith("Smoothing")]}
            if n_b2a:
                row["b2a_true"] = _b2a_proxy(printer, meas, model, n_b2a)
            rows.append(row)
            progress(f"{pid} ×{f:<6g} A2B {row['a2b_true']['median']:.3f}/"
                     f"{row['a2b_true']['p95']:.3f}  "
                     + (f"B2A {row['b2a_true']['median']:.3f}/"
                        f"{row['b2a_true']['p95']:.3f}  " if n_b2a else "")
                     + f"res {row['chart_res_de00_median']:.3f}  "
                     f"whit {row['whitened_rms']:.2f}  {secs:.0f}s")
    finally:
        acc._HOLDOUT_MIN_PATCHES, acc.fit_forward_model = saved
    # The shipped rule's own pick, for reference.
    lines = []
    _m, _o, lam_cv = acc.fit_forward_model_accurate(
        dev, lab, grid=grid, base_lam=base_lam, progress=lines.append)
    return {"printer": pid, "grid": grid, "base_lam": base_lam,
            "noise": {"floor": n_floor, "dark": n_dark},
            "shipped_factor": lam_cv / base_lam,
            "shipped_log": [ln for ln in lines if ln.startswith("Smoothing")],
            "rows": rows}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--printers", default="S1,S2,S3,S4,S5,S6")
    ap.add_argument("--eval", type=int, default=8000)
    ap.add_argument("--b2a", type=int, default=300)
    ap.add_argument("--factors", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    factors = tuple(float(x) for x in args.factors.split(",")) \
        if args.factors else FACTORS
    out_dir = Path(".bench-sweep")
    out_dir.mkdir(exist_ok=True)
    res = {}
    for pid in args.printers.split(","):
        res[pid] = sweep_printer(pid, out_dir, n_eval=args.eval,
                                 n_b2a=args.b2a, factors=factors)
        print(f"{pid}: shipped rule picked ×{res[pid]['shipped_factor']:g}")
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=1),
                                  encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
