"""Research token "a38-noisy-rgb" (Agent 38, 2026-10-07): the RGB ramp
positioning curves ("rgbpos") are kept only where the chart itself shows
they help.

"rgbpos" (Agent 3) starts the shaper curves of an RGB printer from the
chart's single-channel ramps. It was decided on the synthetic S2 printer,
where it halved the A2B p95. On real RGB charts a held-out exam finds no gain
(ET-8550 924 patches, X-Rite RGB i1Pro 2033 patches) and on Knut's laser
printer (315 patches, 3-4 points per ramp, toner saturating at 76 % of a
channel) a clear loss: ten-fold held-out A2B 1.77 with the curves, 1.60
without (colprof 1.72), the grey column 2.38 -> 1.92 (colprof 1.78).
ProfileEngineResearch Findings/agent38-01-knut-laser.md.

The exam: five deterministic folds over the chart (duplicates together;
paper, the black and the solids always train), the accurate fit at the
standard smoothing with and without the curves on each training part, dE00
on the held-out part. v2 (in force): the curves are dropped only when they
are clearly WORSE (paired bootstrap 95 % lower bound of the mean held-out
difference with - without above zero) and none of the guards below objects.
v1 (``decide(strict=False)``, measured and rejected, Agent 38 s5): the curves
had to earn their place, KEPT only when they are clearly better (paired
bootstrap 95 % upper bound of the mean held-out difference with - without
below zero; 2000 draws, fixed seed), and also kept when dropping them would
clearly raise the held-out p95 (paired bootstrap 95 % lower bound of
p95 without - p95 with above zero: a p95 of a few hundred noisy patches
moves by tenths between resamples, so a fixed tolerance would decide on
noise), or would cost the near-neutral patches (measured C* < 5) more than
max(0.02, 2 %) or the light patches (L* > 60, where they were meant to
help) more than max(0.02, 5 %) of their mean.
Only then are they dropped for this chart.
When kept, the build is the default build, byte for byte.
"""
from __future__ import annotations

import numpy as np

A38_TOKEN = "a38-noisy-rgb"
A38_FOLDS = 5
A38_BOOT = 2000
A38_SEED = 20261007


def exam_folds(device: np.ndarray, k: int = A38_FOLDS) -> np.ndarray:
    """Fold id per row for an RGB chart (-1 = always trains). gpsel's
    chart_folds reads device 0 as paper; for RGB paper is 1,1,1, so it is
    given the mirrored ("ink") values. The black (RGB 0) also always
    trains: without it the dark corner is extrapolated, which no build
    ever has to do."""
    from workflow.profile_engine.gpsel import chart_folds
    dev = np.asarray(device, float)
    fold = chart_folds(1.0 - dev, k)
    fold[np.all(dev <= 1e-6, axis=1)] = -1
    return fold


def _boot_idx(n: int, n_boot: int = A38_BOOT, seed: int = A38_SEED) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, n, (n_boot, n))


def decide(e_with: np.ndarray, e_without: np.ndarray, lab: np.ndarray,
           strict: bool = True) -> dict:
    """The rule above on per-patch held-out dE00 (aligned arrays) and the
    measured Lab of those patches. -> report dict with "drop" (bool) and
    "why" (the clause that kept the curves, or "")."""
    e_with = np.asarray(e_with, float)
    e_without = np.asarray(e_without, float)
    lab = np.asarray(lab, float)
    idx = _boot_idx(len(e_with))
    upper = float(np.percentile((e_with - e_without)[idx].mean(1), 97.5))
    p95_w, p95_o = (float(np.percentile(e, 95)) for e in (e_with, e_without))
    p95_lower = float(np.percentile(np.percentile(e_without[idx], 95, axis=1)
                                    - np.percentile(e_with[idx], 95, axis=1), 2.5))
    c = np.hypot(lab[:, 1], lab[:, 2])
    rep = {"n": int(len(e_with)), "mean_with": float(e_with.mean()),
           "mean_without": float(e_without.mean()), "upper95_with_minus_without": upper,
           "p95_with": p95_w, "p95_without": p95_o}
    why = []
    lower = float(np.percentile((e_with - e_without)[idx].mean(1), 2.5))
    rep["lower95_with_minus_without"] = lower
    if upper < 0.0:
        why.append("clearly better")
    if strict and lower <= 0.0:
        # v2 (the rule in force): the curves go only when they are clearly
        # WORSE. v1 (strict=False) dropped them whenever they were not
        # clearly better, and on the misread-heavy synthetic t400 charts
        # (exam a coin toss) that doubled the A2B error (Agent 38 s5).
        why.append("not clearly worse")
    rep["p95_rise_lower95"] = p95_lower
    if p95_lower > 0.0:
        why.append("p95")
    for name, m, rel in (("neutral", c < 5.0, 0.02), ("light", lab[:, 0] > 60.0, 0.05)):
        if m.any():
            mw, mo = float(e_with[m].mean()), float(e_without[m].mean())
            rep[f"{name}_with"], rep[f"{name}_without"] = mw, mo
            if mo > mw + max(0.02, rel * mw):
                why.append(name)
    rep["why"] = ", ".join(why)
    rep["drop"] = not why
    return rep


def rgbpos_exam(device, lab, *, grid: int, base_lam: float, curve_rounds: int,
                row_weights=None, ucs: bool = False) -> dict:
    """Run the exam (2 x A38_FOLDS accurate fits at the standard smoothing,
    side by side on the engine's pool) and return :func:`decide`'s report."""
    from workflow.profile_engine import parallel
    from workflow.profile_engine.accuracy import fit_forward_model_accurate
    from workflow.profile_engine.metrics import delta_e_2000
    device = np.asarray(device, float)
    lab = np.asarray(lab, float)
    rw = None if row_weights is None else np.asarray(row_weights, float)
    fold = exam_folds(device)

    def one(pos: bool, f: int):
        tr = fold != f
        m, _, _ = fit_forward_model_accurate(
            device[tr], lab[tr], grid=grid, base_lam=base_lam,
            curve_rounds=curve_rounds, ucs=ucs, positioning=pos,
            additive=True, row_weights=None if rw is None else rw[tr],
            lam_factors=(1.0,))
        te = fold == f
        # (with ucs the fit returns its nodes in Lab already)
        return delta_e_2000(m.predict(device[te]), lab[te])

    keys = [(pos, f) for pos in (True, False) for f in range(A38_FOLDS)]
    vals = parallel.run_tasks([(lambda p=p, f=f: one(p, f)) for p, f in keys])
    held = np.concatenate([np.flatnonzero(fold == f) for f in range(A38_FOLDS)])
    e = {True: np.concatenate(vals[:A38_FOLDS]), False: np.concatenate(vals[A38_FOLDS:])}
    return decide(e[True], e[False], lab[held])


def message(rep: dict) -> str:
    verdict = ("dropped for this chart" if rep["drop"]
               else f"kept ({rep['why']})")
    return (f"RGB ramp curves {verdict} (held-out exam over {rep['n']} patches: "
            f"mean {rep['mean_with']:.2f} with, {rep['mean_without']:.2f} without; "
            f"near-neutral {rep.get('neutral_with', float('nan')):.2f} with, "
            f"{rep.get('neutral_without', float('nan')):.2f} without).")


# ---------------------------------------------------------------------------
# Research token "a40-knut-grey" (Agent 38 s6, 2026-10-07): a gentler ramp
# placement where the chart shows the shipped one is clearly worse.
#
# Knut's laser chart (3-4 points per ramp, toner saturating at ~75 % of a
# channel): ten-fold held-out with the shipped curves (blend 0.5) 1.767, grey
# column 2.44; with blend 0.25 1.624, grey 1.99 (colprof 1.721 / 1.768);
# dropping the curves altogether (a38 v1) bought the same accuracy but cost
# the safety rows, and so did blend 0.25 everywhere (a sharper hand-over at
# L* 25). The "mixed" curves are 0.25 over the light part of each channel
# and the shipped 0.5 at the dark end (ten-fold 1.526, grey 1.69). The exam
# is the same five folds; "mixed" replaces 0.5 only when 0.5 is clearly WORSE (lower bound > 0) and none of the guards
# (p95, near-neutral, light) objects.
A40_TOKEN = "a40-knut-grey"
A40_BLENDS = (0.5, "mixed")


def blend_exam(device, lab, *, grid: int, base_lam: float, curve_rounds: int,
               row_weights=None, ucs: bool = False,
               blends: tuple = A40_BLENDS) -> dict:
    """:func:`decide` with "with" = the shipped blend, "without" = the
    gentler one; "drop" True means: use the gentler blend."""
    from workflow.profile_engine import parallel
    from workflow.profile_engine.accuracy import fit_forward_model_accurate
    from workflow.profile_engine.metrics import delta_e_2000
    device = np.asarray(device, float)
    lab = np.asarray(lab, float)
    rw = None if row_weights is None else np.asarray(row_weights, float)
    fold = exam_folds(device)

    def one(b: float, f: int):
        tr = fold != f
        m, _, _ = fit_forward_model_accurate(
            device[tr], lab[tr], grid=grid, base_lam=base_lam,
            curve_rounds=curve_rounds, ucs=ucs, positioning=True,
            additive=True, row_weights=None if rw is None else rw[tr],
            lam_factors=(1.0,), ramp_blend=b)
        te = fold == f
        return delta_e_2000(m.predict(device[te]), lab[te])

    keys = [(b, f) for b in blends for f in range(A38_FOLDS)]
    vals = parallel.run_tasks([(lambda b=b, f=f: one(b, f)) for b, f in keys])
    held = np.concatenate([np.flatnonzero(fold == f) for f in range(A38_FOLDS)])
    rep = decide(np.concatenate(vals[:A38_FOLDS]),
                 np.concatenate(vals[A38_FOLDS:]), lab[held])
    rep["blend"] = blends[1] if rep["drop"] else blends[0]
    return rep


def blend_message(rep: dict) -> str:
    return (f"RGB ramp curves: {'gentler in the light part' if rep['drop'] else 'shipped'} "
            f"(held-out exam over {rep['n']} patches: mean {rep['mean_with']:.2f} shipped, "
            f"{rep['mean_without']:.2f} gentler; near-neutral "
            f"{rep.get('neutral_with', float('nan')):.2f} / "
            f"{rep.get('neutral_without', float('nan')):.2f}).")
