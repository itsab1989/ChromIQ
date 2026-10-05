"""Agent 15 (profile-engine research, D-14 repair): safer GP forward models
and a per-chart held-out choice between them and the stiff lattice fit.

Research tokens (all OFF by default; read only when "gpfwd" is also set):

* ``gpwarp``  the GP is fitted in the stiff fit's shaper coordinates
              (input warping, Snoek et al. 2014) instead of raw device values.
* ``gpres``   a contender in the choice: a zero-mean GP on the stiff fit's
              residual (in shaper coordinates), added to the stiff fit.
* ``gpclip``  beyond the chart's own largest total ink the GP's contribution
              is tapered to zero over 10 % of total ink, so the table there is
              the stiff fit's (the GP extrapolates to 11-25 dE00 on XKB).
* ``gpsel``   per-chart held-out selection: stiff vs raw GP vs warped GP vs
              residual GP, by K-fold cross-validation on the chart itself with
              folds that keep duplicates together and never hold out paper or
              a solid; a GP is used only when it is better on the pooled
              held-out patches in mean (paired bootstrap CI) and not worse in
              p95 and in the light and dark bands. Otherwise the stiff fit is
              kept unchanged (the table is then the baseline's, bit for bit).

Numpy only (D-07). Deterministic: fixed seeds, fixed fold assignment.
"""
from __future__ import annotations

import numpy as np

from workflow.profile_engine import gpfwd


class Warped:
    """GP(stiff.shape_device(z))."""

    def __init__(self, gp, stiff):
        self.gp, self.stiff = gp, stiff
        self.ls, self.s2, self.noise = gp.ls, gp.s2, gp.noise

    def predict(self, z):
        return self.gp.predict(self.stiff.shape_device(np.atleast_2d(z)))


class ZeroMeanGP(gpfwd.GPForward):
    """A GP whose prior mean is 0 (outputs scaled, never shifted): for a
    residual, far from data the prediction returns to 0."""

    def __init__(self, x, y, ls, s2, noise, alpha_extra=None):
        self.x = np.asarray(x, float)
        self.ym = np.zeros(y.shape[1])
        self.ys = np.sqrt((y * y).mean(0)) + 1e-12
        yn = y / self.ys
        self.ls, self.s2, self.noise = ls, s2, noise
        K = gpfwd._matern(gpfwd._dists(self.x, self.x, ls), s2)
        diag = noise + (0.0 if alpha_extra is None else alpha_extra)
        K[np.diag_indices_from(K)] += diag + 1e-8
        Lc = np.linalg.cholesky(K)
        self.alpha = np.linalg.solve(Lc.T, np.linalg.solve(Lc, yn))


class Residual:
    """stiff(z) + r_GP(stiff.shape_device(z))."""

    def __init__(self, gp, stiff):
        self.gp, self.stiff = gp, stiff
        self.ls, self.s2, self.noise = gp.ls, gp.s2, gp.noise

    def predict(self, z):
        z = np.atleast_2d(z)
        return self.stiff.predict(z) + self.gp.predict(self.stiff.shape_device(z))


class Tapered:
    """stiff + w(total ink) * (model - stiff); w = 1 up to ``limit`` (total
    ink as a fraction, e.g. 3.0 = 300 %), smoothstep to 0 at limit+margin."""

    def __init__(self, model, stiff, limit, margin=0.10, light=None,
                 dark=None):
        self.m, self.stiff, self.limit, self.margin = model, stiff, limit, margin
        # "gplight": below the chart's lightest sampled ink level the GP's
        # contribution fades to 0 (by the largest ink of the point), so the
        # near-paper region the chart never measured stays the stiff fit's
        self.light = light
        # "gpdark": (L_lo, L_hi): the GP fades out where the stiff fit
        # prints darker than L_hi and is gone below L_lo (XKB: the B2A's
        # inversion of a GP that follows an L* reversal near the ink limit)
        self.dark = dark
        self.ls = getattr(model, "ls", None)
        self.s2 = getattr(model, "s2", None)
        self.noise = getattr(model, "noise", None)

    def weight(self, z):
        t = np.clip((self.limit + self.margin - z.sum(1)) / self.margin, 0.0, 1.0)
        w = t * t * (3.0 - 2.0 * t)
        if self.light:
            u = np.clip(z.max(1) / self.light, 0.0, 1.0)
            w = w * u * u * (3.0 - 2.0 * u)
        return w

    def predict(self, z):
        z = np.atleast_2d(np.asarray(z, float))
        w = self.weight(z)
        out = self.stiff.predict(z)
        if self.dark:
            lo, hi = self.dark
            t = np.clip((out[:, 0] - lo) / (hi - lo), 0.0, 1.0)
            w = w * t * t * (3.0 - 2.0 * t)
        on = w > 0.0
        if on.any():
            out[on] += w[on, None] * (self.m.predict(z[on]) - out[on])
        return out


def _huber_keep(stiff, device, lab, de_fn, row_weights):
    w = gpfwd.huber_weights(de_fn(stiff.predict(device), lab))
    if row_weights is not None:
        w = w * np.asarray(row_weights, float)
    return w


def fit_kind(kind, device, lab, stiff, de_fn, row_weights=None, hyper=None,
             iters=200):
    """One contender. ``hyper``: (ls, s2, noise) to warm-start a short
    re-learning (the CV folds) instead of the full multi-start search."""
    device = np.asarray(device, float)
    if kind == "stiff":
        return stiff, None
    w = _huber_keep(stiff, device, lab, de_fn, row_weights)
    keep = w > 0
    if kind == "raw":
        x = device
    else:
        x = stiff.shape_device(device)
    y = lab - stiff.predict(device) if kind == "res" else lab
    if hyper is None:
        ls, s2, nz, _ = gpfwd.fit_hyper(x[keep], y[keep], iters=iters)
    else:
        ls, s2, nz = _refine_hyper(x[keep], y[keep], hyper, zero_mean=(kind == "res"))
    extra = nz * (1.0 / np.maximum(w[keep], 1e-3) - 1.0)
    if kind == "res":
        g = ZeroMeanGP(x[keep], y[keep], ls, s2, nz, alpha_extra=extra)
        return Residual(g, stiff), (ls, s2, nz)
    g = gpfwd.GPForward(x[keep], y[keep], ls, s2, nz, alpha_extra=extra)
    if kind == "raw":
        return g, (ls, s2, nz)
    return Warped(g, stiff), (ls, s2, nz)


def _refine_hyper(x, y, hyper, zero_mean=False, iters=40, lr=0.02):
    """A short Adam run from the full chart's optimum, on the fold's own
    training rows (the held-out rows never enter)."""
    n = x.shape[1]
    if zero_mean:
        yn = y / (np.sqrt((y * y).mean(0)) + 1e-12)
    else:
        yn = (y - y.mean(0)) / (y.std(0) + 1e-12)
    if len(x) > 1200:
        idx = np.random.default_rng(0).permutation(len(x))[:1200]
        x, yn = x[idx], yn[idx]
    ls, s2, nz = hyper
    theta = np.concatenate([np.log(ls), [np.log(s2)], [np.log(nz)]])
    lo = np.concatenate([np.full(n, np.log(0.02)), [np.log(1e-3)], [np.log(1e-5)]])
    hi = np.concatenate([np.full(n, np.log(100.0)), [np.log(1e4)], [np.log(1.0)]])
    best = (np.inf, theta.copy())
    mom = np.zeros_like(theta)
    vel = np.zeros_like(theta)
    for t in range(1, iters + 1):
        f, g = gpfwd._nlml_grad(theta, x, yn)
        if not np.isfinite(f):
            break
        if f < best[0]:
            best = (f, theta.copy())
        mom = 0.9 * mom + 0.1 * g
        vel = 0.999 * vel + 0.001 * g * g
        step = lr * (mom / (1 - 0.9 ** t)) / (np.sqrt(vel / (1 - 0.999 ** t)) + 1e-8)
        theta = np.clip(theta - step, lo, hi)
    th = best[1]
    return np.exp(th[:n]), float(np.exp(th[n])), float(np.exp(th[n + 1]))


# ----------------------------------------------------------------- folds

def chart_folds(device, k=5, seed=4242):
    """Fold id per row (-1 = always in training). Duplicate device rows
    share a fold; paper and solids (one ink at 100 %, the rest 0) are never
    held out; each single-ink ramp is dealt across the folds in ink order,
    so no fold removes a whole ramp or its light end."""
    dev = np.asarray(device, float)
    key = np.round(dev, 4)
    _, grp = np.unique(key, axis=0, return_inverse=True)
    grp = np.asarray(grp).reshape(-1)
    ng = grp.max() + 1
    gdev = np.zeros((ng, dev.shape[1]))
    gdev[grp] = key
    inked = gdev > 1e-6
    nink = inked.sum(1)
    paper = nink == 0
    solid = (nink == 1) & (gdev.max(1) >= 0.999)
    fold_g = np.full(ng, -2)
    fold_g[paper | solid] = -1
    ramp = (nink == 1) & ~solid
    for c in range(dev.shape[1]):
        idx = np.flatnonzero(ramp & inked[:, c])
        idx = idx[np.argsort(gdev[idx, c], kind="stable")]
        fold_g[idx] = (np.arange(len(idx)) + c) % k
    rest = np.flatnonzero(fold_g == -2)
    perm = np.random.default_rng(seed).permutation(len(rest))
    fold_g[rest[perm]] = np.arange(len(rest)) % k
    return fold_g[grp]


def _boot_ci(diff, stat, n_boot=2000, seed=20260929):
    rng = np.random.default_rng(seed)
    n = len(diff)
    out = np.empty(n_boot)
    for b in range(n_boot):
        out[b] = stat(diff[rng.integers(0, n, n)])
    return np.percentile(out, [2.5, 97.5])


def select(device, lab, stiff, fit_stiff, de_fn, row_weights=None,
           kinds=("raw", "warp", "res"), k=5, full_hyper=None, progress=None):
    """Held-out choice. ``fit_stiff(dev, lab, rw)`` refits the stiff model on
    a fold's training rows. Returns (winner kind, report dict)."""
    device = np.asarray(device, float)
    folds = chart_folds(device, k)
    held = folds >= 0
    pred = {kd: np.zeros((len(device), 3)) for kd in ("stiff",) + tuple(kinds)}
    rw = None if row_weights is None else np.asarray(row_weights, float)
    for f in range(k):
        te = folds == f
        tr = ~te
        if progress is not None:
            progress(f"Choosing the printer model: held-out fold {f + 1}/{k}…")
        st = fit_stiff(device[tr], lab[tr], None if rw is None else rw[tr])
        pred["stiff"][te] = st.predict(device[te])
        for kd in kinds:
            m, _ = fit_kind(kd, device[tr], lab[tr], st, de_fn,
                            None if rw is None else rw[tr],
                            hyper=None if full_hyper is None else full_hyper.get(kd))
            pred[kd][te] = m.predict(device[te])
    lab_h = lab[held]
    w_h = np.ones(held.sum()) if rw is None else rw[held]
    err = {kd: de_fn(p[held], lab_h) for kd, p in pred.items()}
    base = err["stiff"]
    light = lab_h[:, 0] > 80.0
    dark = lab_h[:, 0] < 30.0
    ramp = (device[held] > 1e-6).sum(1) == 1
    # Agent 14: ramps AND 1-2-ink patches must never get worse
    few = (device[held] > 1e-6).sum(1) <= 2
    report = {"n_heldout": int(held.sum()),
              "stiff": _summ(base, light, dark)}
    winner, best_mean = "stiff", float(np.mean(base))
    for kd in kinds:
        e = err[kd]
        d = e - base
        s = _summ(e, light, dark)
        ci_mean = _boot_ci(d, np.mean)
        p95_d = float(np.percentile(e, 95) - np.percentile(base, 95))
        ok_mean = ci_mean[1] < 0.0
        # A band "gets worse" when its mean rises by more than the larger of
        # 0.02 dE00 and 5 % of the stiff fit's band mean (B3: on FOGRA39L
        # a strict "<= 0" rejected a GP that was 29 % better in mean and
        # 38 % in p95 for a +0.004 light band and a +0.012 ramp band).
        def band_ok(m):
            if m.sum() < 10:
                return True
            return float(np.mean(d[m])) <= max(0.02, 0.05 * float(np.mean(base[m])))
        ok_p95 = p95_d <= max(0.02, 0.02 * float(np.percentile(base, 95)))
        ok_light = band_ok(light)
        ok_dark = band_ok(dark)
        # the chart's own single-ink ramps and 1-2-ink patches must not get
        # worse (agent 14)
        ok_ramp = band_ok(ramp)
        ok_few = band_ok(few)
        s.update(mean_diff_ci=[float(ci_mean[0]), float(ci_mean[1])],
                 p95_diff=p95_d, ramp_mean_diff=float(np.mean(d[ramp])) if ramp.any() else None,
                 accepted=bool(ok_mean and ok_p95 and ok_light and ok_dark and ok_ramp and ok_few))
        report[kd] = s
        if s["accepted"] and float(np.mean(e)) < best_mean:
            winner, best_mean = kd, float(np.mean(e))
    report["winner"] = winner
    return winner, report


def _summ(e, light, dark):
    return {"mean": float(np.mean(e)), "median": float(np.median(e)),
            "p95": float(np.percentile(e, 95)),
            "light_mean": float(np.mean(e[light])) if light.any() else None,
            "dark_mean": float(np.mean(e[dark])) if dark.any() else None}


def light_scale(device, default=0.25):
    """The chart's lightest sampled level: for each ink the smallest nonzero
    value among its single-ink patches; the largest of those over the inks
    (the most conservative), ``default`` when an ink has no ramp patch."""
    dev = np.asarray(device, float)
    inked = dev > 1e-6
    one = inked.sum(1) == 1
    lv = []
    for c in range(dev.shape[1]):
        v = dev[one & inked[:, c], c]
        lv.append(float(v.min()) if len(v) else default)
    return max(lv)
