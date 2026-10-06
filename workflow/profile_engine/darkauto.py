"""Research token "a32-darkmodel-auto" (Agent 32): the dark-corner fit weight
chosen per chart, from the chart's own held-out patches.

Agent 29a's "a29-darkmodel" multiplies every forward-fit row weight by
``1 + alpha * clip((50 - L*) / 50, 0, 1)`` with a FIXED alpha of 3. On clean
dark readings that is right (real ET-8550 held-out darks 0.718 -> 0.591
dE00); on noisy ones the fit follows the noise (pessimistic XKB / X3 at 400
patches, A2B p95 about doubles). A fixed weight cannot serve both, so here
the chart decides:

* the smoothing is the one the shipped fit chose for this chart without any
  dark weight (``lam``); it is held FIXED for every candidate weight. Letting
  the noisy single-split smoothing search run again under the weights is
  how a29-darkmodel jumped to the softest end of the ladder on XKB
  pessimistic (x2 -> x0.25, Findings/agent32-01 s2);
* every candidate alpha (0 = off) is fitted on the training part of five
  deterministic chart folds (``gpsel.chart_folds``: duplicates share a fold,
  paper and solids never leave, the ramps are dealt across the folds) and
  judged on the held-out fifth, in dE00, the same exam gpsel uses for the
  GP layer;
* a weight is taken only when it clearly beats "off" on THIS chart: the
  paired bootstrap 95 % interval of the mean held-out difference lies below
  zero, the held-out p95 does not rise, and neither the light patches nor
  the single-ink ramps get worse. Otherwise the build is the base build,
  byte for byte.

Variants for the A/B only: "a32-darkmodel-auto-lamcv" also chooses the
smoothing by the same five-fold exam (mean held-out dE00 over the shipped
ladder, at alpha 0) before the weight is chosen.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

TOKEN = "a32-darkmodel-auto"
ALPHAS = (0.0, 1.5, 3.0, 6.0)
L_CUT = 50.0
FOLDS = 5
LAM_FACTORS = (0.25, 0.5, 1.0, 2.0, 4.0)


def wanted(candidates) -> bool:
    return any(t == TOKEN or t.startswith(TOKEN + "-")
               for t in (candidates or ()))


def lam_cv_wanted(candidates) -> bool:
    return TOKEN + "-lamcv" in set(candidates or ())


def dark_weights(lab: np.ndarray, alpha: float,
                 l_cut: float = L_CUT) -> np.ndarray:
    """Per-patch weight 1 + alpha * clip((l_cut - L*) / l_cut, 0, 1)."""
    l_star = np.asarray(lab, float)[:, 0]
    return 1.0 + alpha * np.clip((l_cut - l_star) / l_cut, 0.0, 1.0)


def _boot_upper(diff: np.ndarray, n_boot: int = 2000,
                seed: int = 20261006) -> float:
    rng = np.random.default_rng(seed)
    n = len(diff)
    means = np.array([diff[rng.integers(0, n, n)].mean()
                      for _ in range(n_boot)])
    return float(np.percentile(means, 97.5))


def _cv_errors(device, lab, rw, fit_fn, lam, alphas, folds, de_fn):
    """Held-out dE00 per alpha (rows with fold >= 0), fits side by side on
    the build's pool (each fit is the same computation, so the same bits)."""
    from workflow.profile_engine import parallel
    held = folds >= 0
    k = int(folds.max()) + 1
    keys = [(a, f) for a in alphas for f in range(k)]

    def task(a, f):
        def run():
            tr = folds != f
            w = dark_weights(lab, a)
            w = w if rw is None else w * rw
            m = fit_fn(device[tr], lab[tr], w[tr], lam)
            return m.predict(device[folds == f])
        return run

    outs = parallel.run_tasks([task(a, f) for a, f in keys]) \
        if parallel.worker_count() > 1 else [task(a, f)() for a, f in keys]
    pred = {a: np.zeros_like(lab) for a in alphas}
    for (a, f), p in zip(keys, outs):
        pred[a][folds == f] = p
    return {a: de_fn(pred[a][held], lab[held]) for a in alphas}


def choose(device: np.ndarray, lab: np.ndarray, rw: np.ndarray | None,
           fit_fn: Callable, lam: float, de_fn: Callable, *,
           alphas=ALPHAS, lam_factors=None, base_lam: float | None = None,
           ) -> tuple[float, float, dict]:
    """(alpha, lam, report). ``fit_fn(dev, lab, row_weights, lam)`` returns a
    forward model fitted at that fixed smoothing. ``lam_factors`` (variant
    lamcv): first choose the smoothing among ``base_lam * factor`` by the
    mean held-out dE00 at alpha 0."""
    from workflow.profile_engine.gpsel import chart_folds
    device = np.asarray(device, float)
    lab = np.asarray(lab, float)
    folds = chart_folds(device, FOLDS)
    held = folds >= 0
    report: dict = {"n_heldout": int(held.sum()), "lam_in": float(lam)}
    if lam_factors:
        means = {}
        for fx in lam_factors:
            e = _cv_errors(device, lab, rw, fit_fn, base_lam * fx, (0.0,),
                           folds, de_fn)[0.0]
            means[fx] = float(e.mean())
        best = min(lam_factors, key=lambda f: (means[f], abs(np.log(f))))
        lam = base_lam * best
        report["lam_cv"] = {str(f): round(v, 4) for f, v in means.items()}
    report["lam"] = float(lam)
    err = _cv_errors(device, lab, rw, fit_fn, lam, alphas, folds, de_fn)
    base = err[alphas[0]]
    lab_h = lab[held]
    light = lab_h[:, 0] > 80.0
    ramp = (device[held] > 1e-6).sum(1) == 1
    p95_0 = float(np.percentile(base, 95))

    def band_ok(d, m):
        if m.sum() < 10:
            return True
        return float(np.mean(d[m])) <= max(0.02, 0.05 * float(np.mean(base[m])))

    best_a, best_mean = alphas[0], float(base.mean())
    rows = {}
    for a in alphas[1:]:
        e = err[a]
        d = e - base
        up = _boot_upper(d)
        p95_d = float(np.percentile(e, 95)) - p95_0
        ok = (up < 0.0 and p95_d <= max(0.02, 0.02 * p95_0)
              and band_ok(d, light) and band_ok(d, ramp))
        rows[a] = {"mean": round(float(e.mean()), 4),
                   "dark_mean": round(float(e[lab_h[:, 0] < 20].mean()), 4)
                   if (lab_h[:, 0] < 20).any() else None,
                   "diff_upper": round(up, 4), "p95_diff": round(p95_d, 4),
                   "accepted": bool(ok)}
        if ok and float(e.mean()) < best_mean:
            best_a, best_mean = a, float(e.mean())
    report["off"] = {"mean": round(float(base.mean()), 4),
                     "dark_mean": round(float(base[lab_h[:, 0] < 20].mean()), 4)
                     if (lab_h[:, 0] < 20).any() else None}
    report["alphas"] = rows
    report["alpha"] = best_a
    return best_a, lam, report
