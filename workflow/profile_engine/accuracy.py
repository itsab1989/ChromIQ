"""Maximum-accuracy model fitting (gammap_mode "accurate").

Two statistical upgrades over the parity fit, both closed-loop instead of
open-loop:

* **Cross-validated smoothing** — the parity fit's λ table is tuned on the
  trusted fixtures; papers, inks and instruments the table has never seen
  may want a very different value. Here a held-out patch subset picks the
  λ that actually generalises best for *this* measurement. The ``-r``
  (avgdev) setting still matters: it sets the centre of the search, so a
  user hint shifts the whole candidate ladder.

* **Robust refit (Huber IRLS)** — plain least squares lets a single
  misread patch pull the local grid nodes and, through the inverse, a whole
  B2A neighbourhood. Down-weighting patches whose residual is far above the
  bulk makes the fit resistant to smudges and misreads, and the patches
  that were down-weighted are reported so the user can remeasure them.

Both loops judge residuals in **ΔE2000**, not Euclidean Lab: near black the
cube-root lightness slope blows ordinary Lab residuals up for differences
nobody can see, so a ΔE76 criterion over-smooths shadows and cries wolf on
dark patches. The robust scale uses the textbook constants — σ from the
median absolute deviation (1.4826·MAD) and Huber's k = 1.345σ (the 95%-
Gaussian-efficiency tuning constant) — with a floor at instrument
repeatability so a clean chart is never touched.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

from workflow.profile_engine.forward_model import (ForwardModel,
                                                   fit_forward_model)
from workflow.profile_engine.metrics import delta_e_2000

# λ search ladder, as factors on the parity table's value (settings -r
# included — it scales the base before the search).
_LAMBDA_FACTORS = (0.25, 0.5, 1.0, 2.0, 4.0)
_CV_FOLDS = 3                  # hold-out splits (1 when a fit is very large)
_CV_FOLD_MAX_NODES = 250_000   # grid**n above which one split has to do
_CV_MARGIN_FRACTION = 0.02     # a factor must beat ×1 by this much (or by
#                                the across-split scatter, whichever is larger)
_NAME_SCALE_FACTOR = 6.0       # "remeasure" threshold in robust-scale units
_HOLDOUT_MIN_PATCHES = 120     # below this a CV split starves the fit
_CG_RTOL = 1e-12               # squared-residual scale → ~1e-6 relative


def fit_forward_model_accurate(
        device: np.ndarray, lab: np.ndarray, *, grid: int, base_lam: float,
        curve_rounds: int = 2,
        progress: Callable[[str], None] | None = None,
        ucs: bool = False,
        gp: bool = False,
        ) -> tuple[ForwardModel, np.ndarray, float]:
    """Cross-validated, outlier-robust forward fit.

    Returns ``(model, outlier_indices, lam_used)`` — outliers are patch row
    indices whose residual stayed far above the bulk even after the robust
    refit (worth remeasuring; they carry almost no weight in the fit).

    ``ucs`` (candidate ``"ucs"``, issue #123): fit in CAM16-UCS instead of
    CIELAB — residuals, curvature penalty and CV criterion all become
    perceptually uniform *by construction* (Euclidean UCS ≈ ΔE2000), and
    the ΔE00 formula drops out of the loops. The returned model's nodes
    are converted back to Lab, so everything downstream is unchanged.

    ``gp`` (candidate ``"gp"``, issue #123): heteroscedastic noise model —
    per-patch measurement σ propagated from the chart's own duplicate
    scatter — whitens every residual (GLS), the CV criterion and robust
    thresholds become true z-scores, and the λ search hill-climbs beyond
    the fixed ladder. Cures the dark-noise chasing a perceptual target
    space otherwise suffers (dark patches are the noisiest AND steepest).
    """
    npts = len(device)
    lam = base_lam
    lab_orig = lab
    space = None
    if ucs:
        from workflow.profile_engine.ucs import print_ucs
        space = print_ucs()
        lab = space.lab_to_ucs(lab)

    def dist(pred: np.ndarray, ref: np.ndarray) -> np.ndarray:
        if ucs:
            return np.linalg.norm(pred - ref, axis=1)
        return delta_e_2000(pred, ref)

    sigma = None
    if gp:
        from workflow.profile_engine.gp import patch_noise_sigma
        sigma, (n_floor, n_dark) = patch_noise_sigma(device, lab_orig,
                                                     space=space)
        if progress is not None:
            progress(f"Estimated reading noise from the repeated patches: "
                     f"±{n_floor:.2f} XYZ on light patches, "
                     f"±{n_floor + n_dark:.2f} near black.")

    # Outlier scan on a deliberately STIFF fit: a smudge cannot hide from
    # the residuals of a stiff surface, whereas a low cross-validated λ can
    # absorb it locally and mask it. (The ladder tops out at ×4, so running
    # the scan before the CV search changes nothing for the parity path.)
    if progress is not None:
        progress("Fitting the printer model: scanning for misread "
                 "patches…")
    scan = fit_forward_model(device, lab, grid=grid,
                             lam=4.0 * base_lam,
                             curve_rounds=min(curve_rounds, 1),
                             cg_iters=350, cg_rtol=_CG_RTOL)
    res_scan = dist(scan.predict(device), lab)

    if sigma is not None:
        # Whitening by measurement noise alone is wrong statistics where
        # MODEL error dominates (light patches: σ_noise ≈ 0.03 ΔE but the
        # grid can only fit to ~0.1–0.3): the total error budget is
        # σ² = σ_noise² + σ_model². The model floor is estimated from the
        # scan fit's residual spread above the typical noise, per
        # lightness band — grid-resolution error is itself worst in the
        # shadows, and a single scalar floor lets the dark corner be
        # down-weighted into a visible tail and then cries misread on it
        # (measured on the battery; so was the reverse failure of a
        # purely multiplicative calibration on noisy charts).
        floors = np.zeros_like(sigma)
        l_star = lab_orig[:, 0]
        for lo, hi in ((-1.0, 30.0), (30.0, 65.0), (65.0, 200.0)):
            band = (l_star >= lo) & (l_star < hi)
            if band.sum() < 12:
                continue
            r_b = res_scan[band]
            mad_b = 1.4826 * float(np.median(np.abs(r_b - np.median(r_b))))
            floors[band] = np.sqrt(max(
                mad_b ** 2 - float(np.median(sigma[band])) ** 2, 0.0))
        sigma = np.sqrt(sigma ** 2 + floors ** 2)
        sh = float(floors[l_star < 30.0].max(initial=0))
        hi = float(floors[l_star >= 65.0].max(initial=0))
        if progress is not None and max(sh, hi) >= 0.005:
            progress(f"The model's own resolution limit is added to that "
                     f"budget (shadows ±{sh:.2f} ΔE, highlights ±{hi:.2f} "
                     f"ΔE).")

    if npts >= _HOLDOUT_MIN_PATCHES:
        # Several hold-out splits, not one: on a real 924-patch chart the
        # single-split criterion spread only 0.01–0.1 ΔE00 across the whole
        # ladder while the same factor moved 0.1 between splits, so the
        # "choice" was the split's noise — ×0.25 on the full chart, ×4 on
        # 90 % of it, and the stiffer profile generalised WORSE than the
        # plain fit (measured 2026-09-05). A factor now has to beat the
        # standard smoothing by more than the criterion's own scatter.
        nho = max(30, npts // 10)
        folds = _CV_FOLDS if grid ** device.shape[1] <= _CV_FOLD_MAX_NODES \
            else 1
        splits = []
        for k in range(folds):
            idx = np.random.default_rng(4242 + k).permutation(npts)
            splits.append((idx[:nho], idx[nho:]))

        def cv_err(lam_try: float, ho: np.ndarray, trn: np.ndarray) -> float:
            m = fit_forward_model(device[trn], lab[trn], grid=grid,
                                  lam=lam_try, cg_iters=350,
                                  curve_rounds=min(curve_rounds, 1),
                                  cg_rtol=_CG_RTOL)
            r = dist(m.predict(device[ho]), lab[ho])
            if sigma is not None:
                r = r / sigma[ho]      # whitened: a true z-score criterion
            return float(np.median(r))

        errs: dict[float, list[float]] = {}
        for ci, f in enumerate(_LAMBDA_FACTORS):
            if progress is not None:
                progress(f"Fitting the printer model: smoothing search "
                         f"{ci + 1}/{len(_LAMBDA_FACTORS)}…")
            errs[f] = [cv_err(base_lam * f, ho, trn) for ho, trn in splits]
        mean = {f: float(np.mean(v)) for f, v in errs.items()}
        std_at_1 = float(np.std(errs[1.0])) if folds > 1 else 0.0
        noise = max(_CV_MARGIN_FRACTION * mean[1.0], std_at_1)
        cand = min(mean, key=mean.get)
        if cand != 1.0 and mean[cand] < mean[1.0] - noise:
            best_f = cand
        else:
            best_f = 1.0
        best_err, best_lam = mean[best_f], base_lam * best_f
        unit_ = "× the instrument noise" if sigma is not None else "ΔE2000"
        if progress is not None:
            if best_f == 1.0:
                progress(f"Smoothing: no candidate beat the standard value "
                         f"by more than the test's own scatter (±{noise:.2f} "
                         f"{unit_}) — keeping the standard smoothing.")
            else:
                at_end = best_f in (_LAMBDA_FACTORS[0], _LAMBDA_FACTORS[-1])
                progress(f"Smoothing chosen by cross-validation: ×{best_f:.2g} "
                         f"of the standard value (held-out median "
                         f"{best_err:.2f} vs {mean[1.0]:.2f} {unit_} at the "
                         f"standard value)"
                         + (" — the end of the search range." if at_end
                            else "."))
        if gp:
            # Hill-climb refinement in half-octave steps (pragmatic v1 of
            # the GP marginal-likelihood optimisation): the optimum is no
            # longer pinned to the five ladder factors — nor to its ends.
            seen = {round(float(np.log2(best_lam / base_lam)), 3)}
            for ri in range(4):
                trials = [best_lam * np.sqrt(2.0), best_lam / np.sqrt(2.0)]
                moved = False
                for lam_try in trials:
                    key = round(float(np.log2(lam_try / base_lam)), 3)
                    if key in seen:
                        continue
                    seen.add(key)
                    if progress is not None:
                        progress(f"Fitting the printer model: smoothing "
                                 f"refine {ri + 1}/4…")
                    err = float(np.mean([cv_err(lam_try, ho, trn)
                                         for ho, trn in splits]))
                    if err < best_err - noise:
                        best_err, best_lam = err, lam_try
                        moved = True
                        break
                if not moved:
                    break
        lam = best_lam

    # Robust weights from the stiff scan. Huber (1 inside the scale,
    # scale/r beyond), scale = Huber's k = 1.345 × the MAD estimate of σ,
    # floored at instrument repeatability (≈0.35 ΔE2000); gross outliers
    # (beyond 8× scale) are rejected outright, and rejections are sticky —
    # once out, a patch cannot pull itself back in through the refit.
    # Whitened residuals (gp): each patch's error in units of its own
    # total budget (noise + model floor) — thresholds become z-scores.
    res = res_scan
    res_w = res / sigma if sigma is not None else res
    mad = 1.4826 * float(np.median(np.abs(res_w - np.median(res_w))))
    if sigma is None:
        scale = max(1.345 * mad, 0.35)
    else:
        # An on-model chart gives mad ≈ 1 in whitened units; never let the
        # scale drop below the instrument's own 1σ.
        scale = 1.345 * max(mad, 1.0)
    w_rob = np.minimum(1.0, scale / np.maximum(res_w, 1e-9))
    w_rob[res_w > 8.0 * scale] = 0.0
    w_noise = None
    if sigma is not None:
        # GLS row weights, clipped so no patch dominates or vanishes —
        # GLS optimality assumes an unbiased model, which a resolution-
        # limited grid is not, so the variance ratios get a trust bound.
        w_noise = np.clip((float(np.median(sigma)) / sigma) ** 2,
                          0.2, 5.0)

    def _total(wr: np.ndarray) -> np.ndarray:
        return wr if w_noise is None else wr * w_noise

    if progress is not None:
        progress("Fitting the printer model: robust fit 1/2…")
    w = _total(w_rob)
    model = fit_forward_model(device, lab, grid=grid, lam=lam,
                              curve_rounds=curve_rounds,
                              weights=w if ((w < 0.999).any()
                                            or w_noise is not None) else None,
                              cg_rtol=_CG_RTOL)
    res = dist(model.predict(device), lab)
    res_w = res / sigma if sigma is not None else res
    # One tightening pass against the final fit (never loosening).
    w2_rob = np.minimum(w_rob, np.minimum(1.0, scale
                                          / np.maximum(res_w, 1e-9)))
    w2_rob[res_w > 8.0 * scale] = 0.0
    if (w2_rob < w_rob - 1e-9).any():
        if progress is not None:
            progress("Fitting the printer model: robust fit 2/2…")
        model = fit_forward_model(device, lab, grid=grid, lam=lam,
                                  curve_rounds=curve_rounds,
                                  weights=_total(w2_rob),
                                  cg_rtol=_CG_RTOL)
        res = dist(model.predict(device), lab)
        res_w = res / sigma if sigma is not None else res
        w_rob = w2_rob

    # Report likely misreads: everything rejected outright, plus whatever
    # still sits clearly above the bulk after the refit. With the noise
    # model a patch must be *visibly wrong AND statistically anomalous*
    # (a misread is both; a light patch's model-error tail is only the
    # latter, a noisy dark patch only the former — neither is a misread).
    # The naming threshold scales with the chart's own scatter: on a chart
    # measured at 3× a healthy instrument's noise a fixed 3 ΔE00 named 61
    # patches of which one was a misread (A-15); 4× the robust scale keeps
    # a clean chart's threshold where it was (scale floors at 0.35).
    named = res_w > max(6.0 * float(np.median(res_w)),
                        3.0 if sigma is None else 3.0 * scale,
                        _NAME_SCALE_FACTOR * scale)
    if sigma is not None:
        named &= res > 3.0
    # A misread is an ISOLATED anomaly — its device-space neighbours read
    # fine. A patch merely sitting in a hard-to-fit region has equally-poor
    # neighbours and is the model's problem, not the user's: don't send
    # them remeasuring the whole shadow end.
    for i in np.flatnonzero(named):
        d2 = ((device - device[i]) ** 2).sum(1)
        nn = np.argsort(d2)[1:9]
        if res[i] < 3.0 * float(np.median(res[nn])) + 1.0:
            named[i] = False
    if sigma is None:
        outliers = np.flatnonzero(named | (w_rob == 0.0))
    else:
        # Down-weighting/rejecting is a conservative *fitting* decision;
        # telling the user to remeasure is a *reporting* one. A patch
        # hard-rejected as collateral of a nearby smudge (the stiff scan
        # smears a big misread over its neighbours) fits fine in the end
        # — only report rejections the final fit still can't explain.
        outliers = np.flatnonzero(named | ((w_rob == 0.0) & (res > 3.0)))
    if space is not None:
        # The fit lived in UCS; hand back a Lab-speaking model so the
        # writer, inversion seeds and statistics stay unchanged.
        model.nodes = space.ucs_to_lab(model.nodes)
    return model, outliers, lam


def fit_forward_model_accurate_challenged(
        device: np.ndarray, lab: np.ndarray, *, grid: int, base_lam: float,
        curve_rounds: int = 2, ucs: bool = False,
        progress: Callable[[str], None] | None = None,
        ) -> tuple[ForwardModel, np.ndarray, float, str]:
    """Noise-aware fitting behind a noise DETECTOR (issue #123).

    The gp pipeline wins on noisy measurements and is neutral-to-slightly
    negative on clean ones, so it must not run unconditionally. A held-out
    exam cannot referee this one: the noisier the chart — exactly where gp
    helps — the noisier the held-out answers, and the exam goes blind
    (measured: at 3× instrument noise the exam called a tie while ground
    truth showed a clear gp win). Instead the chart itself is diagnosed:
    the duplicate white/black patches yield the measurement's actual
    scatter, compared against the published healthy-instrument amplitudes
    (:mod:`gp`'s reference constants). Only when the chart scatters at
    ≥ 2× the healthy level does the noise-aware fit engage — on a clean
    measurement it stands aside and the result is bit-identical to the
    standard fit. Deterministic, explainable, and free (no extra fits).

    Returns ``(model, outliers, lam, winner)`` with winner ``"noise"`` or
    ``"standard"``.
    """
    from workflow.profile_engine.gp import (_DEFAULT_DARK, _DEFAULT_FLOOR,
                                            estimate_xyz_noise)
    floor, dark = estimate_xyz_noise(device, lab)
    ratio = (floor + dark) / (_DEFAULT_FLOOR + _DEFAULT_DARK)
    win = ratio >= 2.0
    if progress is not None:
        if win:
            progress(f"The repeated white and black patches differ by "
                     f"{ratio:.1f}× more than a spectrophotometer's own "
                     f"repeatability (paper or print unevenness across the "
                     f"sheet counts here) — readings will be weighted by "
                     f"their reliability.")
        else:
            progress("The repeated patches agree closely — the readings are "
                     "trusted equally (noise handling stands aside).")
    model, outliers, lam = fit_forward_model_accurate(
        device, lab, grid=grid, base_lam=base_lam,
        curve_rounds=curve_rounds, ucs=ucs, gp=win, progress=progress)
    return model, outliers, lam, ("noise" if win else "standard")
