"""Which chart-only statistic predicts the λ the PRINT wants? (agent C)

Companion to :mod:`benchmarks.lambda_sweep`. For every battery printer
and every ladder factor it computes, from the chart alone, the candidate
selection criteria — the shipped single-split held-out median, the same
over several splits, generalised cross-validation (GCV, Hutchinson trace
of the hat matrix, no split at all), and the discrepancy ratio (fit
residual over the duplicate-patch noise) — next to the ground-truth A2B
error of the full fit at that factor. The table then says which
criterion's pick lands nearest the oracle, per printer.

Dev-only; never imported by the app.

CLI (from the repo root, venv active)::

    python -m benchmarks.lambda_criteria --printers S1,S2 --out crit.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from benchmarks.lambda_sweep import _prepare
from benchmarks.synthetic import eval_points
from workflow.profile_engine.forward_model import (_interp_weights,
                                                   fit_forward_model)
from workflow.profile_engine.metrics import delta_e_2000

FACTORS = (0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
_RTOL = 1e-12


def hat_trace(model, device: np.ndarray, lam: float, n_probe: int = 4,
              weights: np.ndarray | None = None, seed: int = 77) -> float:
    """Hutchinson estimate of tr(H) for the grid smoother with the model's
    shaper curves held fixed: H = W (WᵀW + λC)⁻¹ Wᵀ."""
    from workflow.profile_engine.forward_model import _grid_solve
    shaped = model.shape_device(device)
    w, cols = _interp_weights(shaped, model.grid, model.n_channels)
    sw = None if weights is None else np.sqrt(weights)
    if sw is not None:
        w = w * sw[:, None]
    rng = np.random.default_rng(seed)
    z = rng.choice([-1.0, 1.0], size=(len(device), n_probe))
    x = _grid_solve(w, cols, z, model.grid, model.n_channels, lam, 800,
                    rtol=_RTOL)
    hz = (w[:, :, None] * x[cols]).sum(1)          # W A⁻¹ Wᵀ z
    return float((hz * z).sum(0).mean())


def criteria_for(pid: str, out_dir: Path, *, n_eval: int = 8000,
                 n_splits: int = 5, factors=FACTORS, progress=print) -> dict:
    from workflow.profile_engine.gp import patch_noise_sigma
    printer, meas, grid, base_lam, _misread = _prepare(pid, out_dir)
    dev, lab = meas.device, meas.lab_relative
    npts = len(dev)
    ev = eval_points(printer, n_eval)
    lab_true = printer.lab_relative_true(ev)
    sigma, _ = patch_noise_sigma(dev, lab)
    nho = max(30, npts // 10)
    splits = []
    for k in range(n_splits):
        idx = np.random.default_rng(4242 + k).permutation(npts)
        splits.append((idx[:nho], idx[nho:]))
    rows = []
    for f in factors:
        lam = base_lam * f
        full = fit_forward_model(dev, lab, grid=grid, lam=lam,
                                 curve_rounds=2, cg_rtol=_RTOL)
        de_true = delta_e_2000(full.predict(ev), lab_true)
        pred = full.predict(dev)
        res_lab = pred - lab
        rss = float((res_lab ** 2).sum())
        tr_h = hat_trace(full, dev, lam)
        # GCV on the 3 Lab channels jointly (the smoother is shared).
        n_eff = 3.0 * npts
        gcv = (rss / n_eff) / max(1.0 - 3.0 * tr_h / n_eff, 1e-6) ** 2
        # Whitened GCV: residuals in units of the propagated noise σ.
        wr = res_lab / sigma[:, None]
        gcv_w = (float((wr ** 2).sum()) / n_eff) \
            / max(1.0 - 3.0 * tr_h / n_eff, 1e-6) ** 2
        disc = float(np.sqrt(np.mean((np.linalg.norm(res_lab, axis=1)
                                      / (np.sqrt(3.0) * sigma)) ** 2)))
        ho = []
        for hidx, tidx in splits:
            m = fit_forward_model(dev[tidx], lab[tidx], grid=grid, lam=lam,
                                  curve_rounds=1, cg_iters=350,
                                  cg_rtol=_RTOL)
            r = delta_e_2000(m.predict(dev[hidx]), lab[hidx])
            ho.append(float(np.median(r)))
        row = {"factor": f,
               "true_median": float(np.median(de_true)),
               "true_p95": float(np.percentile(de_true, 95)),
               "ho_median": ho, "ho_mean": float(np.mean(ho)),
               "gcv": gcv, "gcv_w": gcv_w, "tr_h": tr_h,
               "discrepancy": disc,
               "chart_res_median": float(np.median(
                   delta_e_2000(pred, lab)))}
        rows.append(row)
        progress(f"{pid} ×{f:<6g} true {row['true_median']:.3f}/"
                 f"{row['true_p95']:.3f}  ho1 {ho[0]:.3f} ho-mean "
                 f"{row['ho_mean']:.3f}  gcv {gcv:.4f} gcv_w {gcv_w:.3f}  "
                 f"trH {tr_h:.0f}  disc {disc:.2f}")
    picks = {
        "oracle": min(rows, key=lambda r: r["true_median"])["factor"],
        "ho_single": min(rows, key=lambda r: r["ho_median"][0])["factor"],
        "ho_mean": min(rows, key=lambda r: r["ho_mean"])["factor"],
        "gcv": min(rows, key=lambda r: r["gcv"])["factor"],
        "gcv_w": min(rows, key=lambda r: r["gcv_w"])["factor"],
        "discrepancy": min(rows, key=lambda r: abs(np.log(
            max(r["discrepancy"], 1e-9))))["factor"],
    }
    by_f = {r["factor"]: r for r in rows}
    oracle = by_f[picks["oracle"]]["true_median"]
    for name, f in picks.items():
        progress(f"{pid} {name:<12} picks ×{f:<6g} → true median "
                 f"{by_f[f]['true_median']:.3f} "
                 f"({(by_f[f]['true_median'] / oracle - 1) * 100:+.1f}% vs "
                 f"oracle), p95 {by_f[f]['true_p95']:.3f}")
    return {"printer": pid, "grid": grid, "base_lam": base_lam,
            "rows": rows, "picks": picks}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--printers", default="S1,S2,S3,S4,S6")
    ap.add_argument("--eval", type=int, default=8000)
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    out_dir = Path(".bench-sweep")
    out_dir.mkdir(exist_ok=True)
    res = {}
    for pid in args.printers.split(","):
        res[pid] = criteria_for(pid, out_dir, n_eval=args.eval,
                                n_splits=args.splits)
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=1),
                                  encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
