"""B2A construction: Lab grid → device, by inverting the forward model.

Maths C of issue #122. Batched, damped Gauss–Newton over all CLUT nodes at
once (finite-difference Jacobian, one ``np.linalg.solve`` per iteration over
the whole batch — measured in the spike: in-gamut nodes converge to median
ΔE ≈ 0.007).

For more device channels than the 3 PCS dimensions the inversion is
underdetermined; the *ink policy* resolves the surplus degrees of freedom as
soft least-squares priors inside GN (a hard policy measurably shrinks the
reachable gamut — colour accuracy always dominates):

* channel 4 (K) is pulled toward a GCR-style locus ``K(L*)`` — full black
  only in the shadows, fading out by the midtones (the shape colprof's
  ``-k`` exposes);
* channels beyond 4 (O/G/V/…) are pulled toward hue gates: an ink
  participates in the hue sector around its own Lab anchor hue
  (``max(0, cos(h − h_ink))^p``), and never on neutrals.

Out-of-gamut nodes clamp to the nearest printable colour; their residual ΔE
doubles as the ``gamt`` gamut-distance table (ColorSync requires that tag).
"""
from __future__ import annotations

import numpy as np

from workflow.profile_engine.forward_model import ForwardModel
from workflow.profile_engine.icc_writer import lab_grid_axes
from workflow.profile_engine import oog_clip as _oog

# Lab hue anchors for extra inks, keyed by COLOR_REP letter. Measured hues of
# the EXTRA_INK display anchors used across ChromIQ (ui.tiff_preview).
_EXTRA_INK_HUE = {
    "O": 55.0, "R": 30.0, "G": 136.0, "B": 260.0, "V": 300.0,
}


def lab_grid(grid: int) -> np.ndarray:
    """(grid³, 3) Lab CLUT node targets over the legacy-encoding axes."""
    ls, ab = lab_grid_axes(grid)
    return np.stack(np.meshgrid(ls, ab, ab, indexing="ij"), -1).reshape(-1, 3)


def _model_jacobian(model: ForwardModel, d: np.ndarray, free: np.ndarray,
                    f0: np.ndarray, h: float = 1e-3,
                    boundary_fd: bool = False) -> np.ndarray:
    """(N, 3, n_free) finite-difference Jacobian over the free channels.

    ``boundary_fd``: with the plain forward difference, a channel pinned at
    1.0 clips to itself — its Jacobian column is exactly zero and GN can
    never move it off the face (the root cause of the near-saturation
    stalls the retry pass patches over). Switching to a backward difference
    within ``h`` of the top face keeps the column alive everywhere.
    """
    jac = np.empty((len(d), 3, len(free)))
    for j, ch in enumerate(free):
        dp = d.copy()
        if boundary_fd:
            sign = np.where(d[:, ch] + h <= 1.0, 1.0, -1.0)
            dp[:, ch] = np.clip(d[:, ch] + sign * h, 0.0, 1.0)
            jac[:, :, j] = (model.predict(dp) - f0) / (sign * h)[:, None]
        else:
            dp[:, ch] = np.clip(dp[:, ch] + h, 0.0, 1.0)
            jac[:, :, j] = (model.predict(dp) - f0) / h
    return jac


def project_tac(d: np.ndarray, limit: float) -> np.ndarray:
    """Euclidean projection of device rows onto ``{x ≥ 0, Σx ≤ limit}``.

    The parity path enforces the total ink limit by scaling the whole
    vector, which lightens K along with everything else — exactly in the
    deep shadows where the limit binds. The Euclidean projection subtracts
    a common amount instead (clipped at zero), which preserves the dense
    channels and lands strictly closer to the unconstrained solution.
    Rows already under the limit are returned unchanged.
    """
    d = d.copy()
    over = d.sum(1) > limit
    if not over.any():
        return d
    sub = np.clip(d[over], 0.0, None)
    u = np.sort(sub, axis=1)[:, ::-1]
    css = np.cumsum(u, axis=1) - limit
    ks = np.arange(1, sub.shape[1] + 1)[None, :]
    rho = (u - css / ks > 0).sum(1)
    theta = css[np.arange(len(sub)), rho - 1] / rho
    d[over] = np.maximum(sub - theta[:, None], 0.0)
    return d


def _tac_face_step(jtj: np.ndarray, jtr: np.ndarray, cvec: np.ndarray,
                   e: np.ndarray) -> np.ndarray:
    """Batched Gauss–Newton step on the total-ink face.

    Solves ``min ½ sᵀ A s − bᵀ s  s.t.  cᵀ s = e`` per row (A = ``jtj``,
    b = ``jtr``, c = 1 over the channels that may move, e = the ink still
    to be added to land exactly on the limit): ``s = A⁻¹(b + μc)`` with
    ``μ = (e − cᵀA⁻¹b) / (cᵀA⁻¹c)``.

    A projection AFTER the step subtracts a common amount from every
    channel, so a dark target that drives C, M, Y and K all onto the 1.0
    face comes back as equal parts of each — and the K prior's pull is
    undone every iteration. Measured 2026-09-05 on the battery's CMYK
    printer: the objective's own optimum at L*=0 under a 280 % limit is
    (0.66, 0.59, 0.55, K 1.0), true L* 9.9; the projected step delivered
    (0.75, 0.56, 0.75, 0.75), L* 14.8, and fast mode's proportional
    scaling L* 13.5. On the face the solver trades ink BETWEEN channels
    and the colour and the priors decide the split.
    """
    rhs = np.stack([jtr, cvec], -1)                     # (N, k, 2)
    sol = np.linalg.solve(jtj, rhs)
    ab, ac = sol[..., 0], sol[..., 1]
    cab = (cvec * ab).sum(1)
    cac = (cvec * ac).sum(1)
    mu = np.where(cac > 1e-12, (e - cab) / np.maximum(cac, 1e-12), 0.0)
    return ab + mu[:, None] * ac


# Hue-preservation factor on top of the ΔE2000 metric for clipping: gamut-
# mapping practice (hue-preserving minimum-ΔE clipping, Morovič) deliberately
# weights hue beyond the plain metric — a clipped saturated colour should
# lose chroma, not change colour family. 3× keeps the hue weight dominant
# over the chroma weight across the whole chroma range (γ·S_C/S_H ≥ ~4).
_CLIP_HUE_FACTOR = 3.0


def _hue_weight_matrices(target: np.ndarray) -> np.ndarray:
    """(N,3,3) weighting matrices W so ``W·ΔLab`` measures the clip error
    in a first-order local ΔE2000 metric at each target — component
    weights are the formula's own 1/S_L, 1/S_C, 1/S_H (see
    :func:`metrics.de00_scale_factors`), with hue further emphasised by
    :data:`_CLIP_HUE_FACTOR`. Identity for near-neutrals, where there is
    no hue to preserve."""
    from workflow.profile_engine.metrics import de00_scale_factors
    n = len(target)
    chroma = np.hypot(target[:, 1], target[:, 2])
    h = np.arctan2(target[:, 2], target[:, 1])
    ch, sh = np.cos(h), np.sin(h)
    sl, sc, s_h = de00_scale_factors(target)
    wl, wc, wh = 1.0 / sl, 1.0 / sc, _CLIP_HUE_FACTOR / s_h
    w = np.zeros((n, 3, 3))
    w[:, 0, 0] = wl
    w[:, 1, 1] = wc * ch * ch + wh * sh * sh
    w[:, 1, 2] = (wc - wh) * ch * sh
    w[:, 2, 1] = w[:, 1, 2]
    w[:, 2, 2] = wc * sh * sh + wh * ch * ch
    neutral = chroma < 5.0
    w[neutral] = np.eye(3)
    return w


class _UcsView:
    """Forward-model view predicting CAM16-UCS instead of Lab (issue #123,
    candidate ``"ucs"``): with it, Gauss–Newton minimises a perceptually
    uniform residual, so no per-point metric weighting is needed."""

    def __init__(self, model: ForwardModel, space) -> None:
        self._model = model
        self._space = space
        self.n_channels = model.n_channels

    def predict(self, dev: np.ndarray) -> np.ndarray:
        return self._space.lab_to_ucs(self._model.predict(dev))

    def to_space(self, lab: np.ndarray) -> np.ndarray:
        """Targets Lab → the view's residual space."""
        return self._space.lab_to_ucs(lab)


def _ucs_hue_weight_matrices(target_ucs: np.ndarray) -> np.ndarray:
    """(N,3,3) clip-weight matrices in CAM16-UCS. The space is already
    perceptually uniform, so only the *deliberate* hue emphasis remains —
    :data:`_CLIP_HUE_FACTOR` on the hue direction of the (J', a', b')
    frame, identity near neutral (no hue to preserve)."""
    n = len(target_ucs)
    chroma = np.hypot(target_ucs[:, 1], target_ucs[:, 2])
    h = np.arctan2(target_ucs[:, 2], target_ucs[:, 1])
    ch, sh = np.cos(h), np.sin(h)
    wh = _CLIP_HUE_FACTOR
    w = np.zeros((n, 3, 3))
    w[:, 0, 0] = 1.0
    w[:, 1, 1] = ch * ch + wh * sh * sh
    w[:, 1, 2] = (1.0 - wh) * ch * sh
    w[:, 2, 1] = w[:, 1, 2]
    w[:, 2, 2] = sh * sh + wh * ch * ch
    w[chroma < 3.0] = np.eye(3)
    return w


def _gauss_newton(model, target: np.ndarray, seed: np.ndarray,
                  free: np.ndarray, *, iters: int, damping: float,
                  ink_limit: float | None,
                  prior: np.ndarray | None = None,
                  prior_w: np.ndarray | None = None,
                  boundary_fd: bool = False,
                  tac_projection: bool = False,
                  err_weights: np.ndarray | None = None,
                  channel_max: np.ndarray | None = None,
                  progress=None, progress_label: str = "") -> np.ndarray:
    """Row-parallel front of :func:`_gauss_newton_rows` (D-06).

    Every row of the batched Gauss-Newton is solved on its own (its own
    Jacobian, its own k x k solve, its own clip and ink-limit projection),
    so contiguous row chunks on pool threads give the same bytes as one
    batch. Only the maximum-accuracy path (``boundary_fd``) is split; Fast
    and Bit-exact keep the serial call untouched. Chunk 0 reports progress,
    so the log carries exactly the serial run's lines."""
    from workflow.profile_engine import parallel
    kw = dict(iters=iters, damping=damping, ink_limit=ink_limit,
              boundary_fd=boundary_fd, tac_projection=tac_projection,
              channel_max=channel_max, progress_label=progress_label)
    bounds = parallel.chunk_bounds(len(target), parallel.worker_count()) \
        if boundary_fd else [(0, len(target))]
    if len(bounds) <= 1:
        return _gauss_newton_rows(model, target, seed, free, prior=prior,
                                  prior_w=prior_w, err_weights=err_weights,
                                  progress=progress, **kw)

    def one(lo: int, hi: int) -> np.ndarray:
        sl = slice(lo, hi)
        return _gauss_newton_rows(
            model, target[sl], seed[sl], free,
            prior=None if prior is None else prior[sl],
            prior_w=None if prior_w is None else prior_w[sl],
            err_weights=None if err_weights is None else err_weights[sl],
            progress=progress if lo == 0 else None, **kw)
    return np.concatenate(parallel.run_chunks(one, bounds), axis=0)


def _gauss_newton_rows(model: ForwardModel, target: np.ndarray, seed: np.ndarray,
                  free: np.ndarray, *, iters: int, damping: float,
                  ink_limit: float | None,
                  prior: np.ndarray | None = None,
                  prior_w: np.ndarray | None = None,
                  boundary_fd: bool = False,
                  tac_projection: bool = False,
                  err_weights: np.ndarray | None = None,
                  channel_max: np.ndarray | None = None,
                  progress=None, progress_label: str = "") -> np.ndarray:
    """Batched damped Gauss–Newton on the free channels.

    ``channel_max``: per-channel upper bound (device fraction) — the black
    ink limit (colprof ``-L`` / BLACK_INK_LIMIT) is a box constraint on the
    K channel, applied at every clip like the 0..1 cube itself.

    ``prior``/``prior_w``: optional per-channel soft targets over the free
    channels (the ink policy). They enter as extra least-squares rows, so
    colour accuracy always dominates — the priors only resolve the surplus
    degrees of freedom that n > 3 devices have.
    ``err_weights``: optional (N,3,3) matrices reshaping the Lab error norm
    per point (the hue-preserving clip); ``boundary_fd``/``tac_projection``
    are the maximum-accuracy levers (see :func:`_model_jacobian` /
    :func:`project_tac`).
    """
    d = seed.copy()
    eye = np.eye(len(free))
    for it in range(iters):
        if progress is not None and progress_label:
            progress(f"{progress_label} {it + 1}/{iters}…")
        f0 = model.predict(d)
        r = target - f0
        jac = _model_jacobian(model, d, free, f0, boundary_fd=boundary_fd)
        if err_weights is not None:
            r = np.einsum("nij,nj->ni", err_weights, r)
            jac = np.einsum("nij,njk->nik", err_weights, jac)
        jtj = np.einsum("nik,nil->nkl", jac, jac) + damping * eye[None]
        jtr = np.einsum("nik,ni->nk", jac, r)
        if prior is not None:
            jtj += np.einsum("nk,kl->nkl", prior_w, eye)
            jtr += prior_w * (prior - d[:, free])
        step = np.linalg.solve(jtj, jtr[..., None])[..., 0]
        bad = None
        if boundary_fd:
            # Active-set guard: with the boundary-aware Jacobian a pinned
            # channel keeps a live column, so an *unreachable* target keeps
            # pulling it outward — the clipped joint step then distorts the
            # other channels. Drop the outward-pointing pinned columns and
            # re-solve; channels wanting to move inward stay free (that is
            # the stall fix).
            # A channel is pinned at ITS OWN ceiling, not at 1.0: under a
            # black ink limit (-L) the K channel sits at e.g. 0.70 and an
            # outward step there must leave the face constraint too, or
            # the KKT step hands K ink the clip then removes and C/M/Y
            # never receive the total-ink budget (research agent5-02 E6:
            # S3 -L70 black L* 21.3 -> 14.3, X3 a green 18.0 -> 9.6).
            eps = 1e-9
            top = 1.0 if channel_max is None else channel_max[free]
            bad = (((d[:, free] >= top - eps) & (step > 0))
                   | ((d[:, free] <= eps) & (step < 0)))
            if bad.any():
                jac_m = jac * (~bad)[:, None, :]
                jtj = (np.einsum("nik,nil->nkl", jac_m, jac_m)
                       + damping * eye[None])
                jtr = np.einsum("nik,ni->nk", jac_m, r)
                if prior is not None:
                    jtj += np.einsum("nk,kl->nkl", prior_w, eye)
                    jtr += prior_w * (prior - d[:, free])
                step = np.linalg.solve(jtj, jtr[..., None])[..., 0]
                step[bad] = 0.0
        hi = 1.0 if channel_max is None else channel_max[free]
        if ink_limit is not None and tac_projection:
            # Rows whose move would cross the total ink limit take the same
            # least-squares step ON the limit's face instead (the
            # projection below then only tidies clip rounding). Pinned
            # columns stay out of the constraint — their step is zero.
            trial = np.clip(d[:, free] + step, 0.0, hi)
            others = d.sum(1) - d[:, free].sum(1)
            over = trial.sum(1) + others > ink_limit + 1e-9
            if over.any():
                cvec = np.ones((int(over.sum()), len(free)))
                if bad is not None:
                    cvec[bad[over]] = 0.0
                e = (ink_limit - others[over]) - d[over][:, free].sum(1)
                s_face = _tac_face_step(jtj[over], jtr[over], cvec, e)
                if bad is not None:
                    s_face[bad[over]] = 0.0
                step[over] = s_face
        d[:, free] = np.clip(d[:, free] + step, 0.0, hi)
        if ink_limit is not None:
            if tac_projection:
                d = project_tac(d, ink_limit)
            else:
                total = d.sum(1)
                over = total > ink_limit
                if over.any():
                    d[over] *= (ink_limit / total[over])[:, None]
    return d


def _seed_nearest(model: ForwardModel, target: np.ndarray, seed_res: int,
                  channel_max: np.ndarray | None = None,
                  threads: bool = False) -> np.ndarray:
    """Seed each target with the nearest point of a coarse device mesh.

    ``threads`` (Maximum accuracy, D-06): the rows are searched in parallel
    blocks. Each row's distances are element-wise and summed over the
    three Lab axes only, so a row's answer does not depend on which other
    rows share its block."""
    n = model.n_channels
    top = np.ones(n) if channel_max is None else np.asarray(channel_max)
    axes = [np.linspace(0.0, float(top[c]), seed_res) for c in range(n)]
    mesh = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, n)
    mesh_lab = model.predict(mesh)
    out = np.empty((len(target), n))
    # Chunked distance search, the chunk sized to the mesh: a fixed 4096
    # targets against the 5**7 = 78,125-point mesh of a 7-ink device made a
    # 7.7 GB temporary (14.3 GB peak RSS per build; agent9-01 6.4). Each row
    # is computed by the same expression whatever the chunk (D-06).
    step = max(1, min(4096, int(4.0e6 // max(len(mesh), 1))))

    def block(a: int, b: int) -> None:
        for lo in range(a, b, step):
            hi = min(lo + step, b)
            chunk = target[lo:hi]
            d2 = ((mesh_lab[None, :, :] - chunk[:, None, :]) ** 2).sum(2)
            out[lo:hi] = mesh[np.argmin(d2, 1)]
    if threads:
        from workflow.profile_engine import parallel
        parallel.run_chunks(block, parallel.chunk_bounds(
            len(target), parallel.worker_count()))
    else:
        block(0, len(target))
    return out


def k_locus(lightness: np.ndarray, *, k_max: float = 1.0,
            l_start: float = 60.0, l_full: float = 5.0,
            gamma: float = 1.6) -> np.ndarray:
    """GCR-style black amount as a function of target L* (0 above ``l_start``,
    ``k_max`` at ``l_full``, smooth power ramp between)."""
    t = np.clip((l_start - lightness) / max(l_start - l_full, 1e-6), 0.0, 1.0)
    return k_max * t ** gamma


# colprof -k letter rules as (stle, stpo, enpo, enle, shape) curve parameters
# (colprof.html: -kr ≡ -kp 0 0 1 1 1; z/h/x are the constant curves).
K_RULE_PARAMS = {
    "z": (0.0, 0.0, 1.0, 0.0, 1.0),
    "h": (0.5, 0.0, 1.0, 0.5, 1.0),
    "x": (1.0, 0.0, 1.0, 1.0, 1.0),
    "r": (0.0, 0.0, 1.0, 1.0, 1.0),
}


def argyll_k_curve(l_star: np.ndarray, *, params: tuple,
                   l_min: float = 5.0, l_max: float = 100.0,
                   skew: float = 2.0) -> np.ndarray:
    """colprof's inking curve — a faithful port of ``icxKcurveNF``
    (ArgyllCMS xicc/xlut.c): K target as a function of L*.

    L* is normalised over the device's printable range [``l_min``,
    ``l_max``] and inverted (0 = white, 1 = black), exactly as Argyll
    normalises over its profile's Lmin..Lmax. Below ``stpo`` the curve sits
    at ``stle``, above ``enpo`` at ``enle``; the transition applies
    Argyll's shape mapping under the default skew of 2.0
    (``ICXINKDEFSKEW`` — "matches typical device behaviour").
    """
    stle, stpo, enpo, enle, shape = (float(v) for v in params)
    if stpo > enpo:                            # Argyll reorders swapped stops
        stle, stpo, enpo, enle = enle, enpo, stpo, stle
    shape = min(max(shape, 0.01), 1.99)
    ln = np.clip((np.asarray(l_star, float) - l_min)
                 / max(l_max - l_min, 1e-6), 0.0, 1.0)
    p = 1.0 - ln                               # 0 = white, 1 = black
    out = np.empty_like(p)
    lo = p <= stpo
    hi = p >= enpo
    out[lo] = stle
    out[hi] = enle
    mid = ~(lo | hi)
    if mid.any():
        lp = (p[mid] - stpo) / max(enpo - stpo, 1e-9)
        lp = lp ** skew
        g = shape / 2.0
        lp = lp / ((1.0 / g - 2.0) * (1.0 - lp) + 1.0)
        lp = lp ** (1.0 / skew)
        out[mid] = stle + lp * (enle - stle)
    return out


def extra_ink_amount(target: np.ndarray, letter: str, *,
                     power: float = 3.0,
                     hue_override: float | None = None) -> np.ndarray:
    """Hue-gated participation 0..1 for an extra ink at each Lab target.

    ``hue_override``: the ink's *measured* hue from the chart's own solid
    patch (maximum-accuracy mode) — the anchor table is only a fallback.
    """
    hue = hue_override if hue_override is not None \
        else _EXTRA_INK_HUE.get(letter)
    if hue is None:
        return np.zeros(len(target))
    chroma = np.hypot(target[:, 1], target[:, 2])
    h = np.degrees(np.arctan2(target[:, 2], target[:, 1])) % 360.0
    gate = np.maximum(0.0, np.cos(np.radians(h - hue))) ** power
    # Only saturated colours pull the spot ink in; neutrals never do.
    sat = np.clip((chroma - 15.0) / 60.0, 0.0, 1.0)
    return gate * sat


def ink_priors(target: np.ndarray, n: int, *,
               channel_letters: list[str],
               k_prior: dict | None = None,
               k_gen: dict | None = None,
               accurate: bool = False,
               extra_hues: dict[str, float] | None = None,
               black_l: float | None = None,
               ) -> tuple[np.ndarray, np.ndarray]:
    """The ink policy as soft least-squares priors over the free channels.

    All channels stay free (a hard policy shrinks the reachable gamut —
    measured: median 18 ΔE on random in-gamut targets); the policy only
    resolves the surplus degrees of freedom n > 3 devices have: K follows
    the GCR locus (or the colprof oracle / an explicit -k rule), extra
    inks their hue gates, C/M/Y are unconstrained. Shared by the per-node
    Gauss–Newton inversion and the joint separation solve (#123 W2), so
    both resolve metamerism with the same policy.
    """
    prior = np.zeros((len(target), n))
    prior_w = np.zeros((len(target), n))
    neutral_k = None
    neutral_dev = None
    if k_prior is not None and k_prior.get("neutral_only"):
        # Research agent9-01 6.2 ("a9-monok"): a K curve that applies to
        # the NEUTRALS only (blended in with the accurate neutral weight
        # below); chromatic colours keep the engine's own locus.
        neutral_k = np.interp(target[:, 0], k_prior["l_axis"],
                              k_prior["k_curve"])
        if k_prior.get("dev_curve") is not None:
            # Research agent17-01 item 1: the re-routed neutral axis of a
            # printer whose dark end lightens. There K alone does not pick
            # the branch (XKB, L* 22: K 0.70 with C/M/Y 1.0/0.63/0.62 at
            # 295 % prints the same as K 0.73 with 0.37/0.35/0.35 at 179 %),
            # so near-neutral targets are pulled toward the axis's whole
            # separation; the colour terms still dominate wherever the
            # model has slope, the prior only picks among metamers.
            dc = np.asarray(k_prior["dev_curve"], float)
            neutral_dev = np.stack([np.interp(target[:, 0],
                                              k_prior["l_axis"], dc[:, c])
                                    for c in range(dc.shape[1])], 1)
        k_prior = None
    if k_prior is not None:
        # colprof-calibrated K behaviour (CMYK proxy oracle) — a firmer
        # prior than the generic locus, matching how colprof separates.
        prior[:, 3] = np.interp(target[:, 0], k_prior["l_axis"],
                                k_prior["k_curve"])
        prior_w[:, 3] = 0.15
    elif k_gen is not None and k_gen.get("rule"):
        # Explicit colprof -k/-K rule from the user. -K (locus) is
        # approximated on the full 0..1 K range: on the neutral axis —
        # where the prior does its work — the feasible K range spans
        # nearly the full scale, so locus and value curves coincide;
        # the true per-colour feasible range would need a nested
        # inversion per node. The soft prior keeps colour accuracy
        # dominant either way.
        params = (k_gen.get("params")
                  or K_RULE_PARAMS[k_gen["rule"]])
        prior[:, 3] = argyll_k_curve(
            target[:, 0], params=params,
            l_min=max(float(black_l), 2.0)
            if black_l is not None else 5.0)
        prior_w[:, 3] = 0.10          # explicit user intent: firmer
    elif accurate and black_l is not None:
        prior[:, 3] = k_locus(target[:, 0],
                              l_full=max(float(black_l), 2.0))
        prior_w[:, 3] = 0.05
    else:
        prior[:, 3] = k_locus(target[:, 0])
        prior_w[:, 3] = 0.05
    if accurate:
        # Dark neutrals have the widest metameric freedom — a weak K
        # prior lets adjacent B2A nodes settle on different K/CMY splits
        # (visible as banding in shadow gradients). Firm the K prior up
        # where that freedom lives and fade it out with chroma, so the
        # gamut-relevant saturated targets keep their full freedom.
        chroma_t = np.hypot(target[:, 1], target[:, 2])
        neutral_w = np.exp(-(chroma_t / 25.0) ** 2)
        prior_w[:, 3] = np.maximum(prior_w[:, 3], 2.0 * neutral_w)
        if neutral_k is not None:
            prior[:, 3] = neutral_w * neutral_k + (1.0 - neutral_w) * prior[:, 3]
    hues = extra_hues or {}
    for ch in range(4, n):
        prior[:, ch] = extra_ink_amount(
            target, channel_letters[ch],
            hue_override=hues.get(channel_letters[ch]))
        prior_w[:, ch] = 0.05
    if accurate and ECG_SEPARATION.get("on"):
        _ecg_separation_priors(target, prior, prior_w, channel_letters, hues)
    if accurate and neutral_dev is not None and neutral_dev.shape[1] == n:
        nw = np.exp(-(np.hypot(target[:, 1], target[:, 2]) / 25.0) ** 2)
        prior = nw[:, None] * neutral_dev + (1.0 - nw[:, None]) * prior
        prior_w = np.maximum(prior_w, 2.0 * nw[:, None])
    return prior, prior_w


# Research token "a14-ecgsep" (agent14-01, Validation/ncolour-excellence.md):
# the professional ECG separation rule that an extra ink never prints with
# the process ink on the far side of the hue circle (CMYKOGV: O with C, G
# with M, V with Y; Fogra/IDEAlliance ECG practice, Tzeng-Berns, Deshpande's
# 4-ink sectors). Where an extra ink's hue gate is open, the complementary
# process ink gets a soft prior towards 0, weighted by that gate; elsewhere
# nothing changes. Set by the builder per build (one build per process).
ECG_SEPARATION: dict = {"on": False, "sector": False, "weight": 0.5, "cmy_hues": None}
_CMY_HUE_DEFAULT = {"C": 235.0, "M": 355.0, "Y": 95.0}


def _ecg_separation_priors(target, prior, prior_w, letters, extra_hues):
    cmy = ECG_SEPARATION.get("cmy_hues") or _CMY_HUE_DEFAULT
    w = float(ECG_SEPARATION.get("weight", 0.5))
    for ch in range(4, len(letters)):
        hue = extra_hues.get(letters[ch], _EXTRA_INK_HUE.get(letters[ch]))
        if hue is None or letters[ch] in ("c", "m", "y", "k"):
            continue                       # light inks have no complement
        far = max((abs((hue - h + 180.0) % 360.0 - 180.0), i)
                  for i, h in ((letters.index(l), cmy[l]) for l in "CMY" if l in letters))
        if far[0] < 120.0:
            continue
        comp = far[1]
        gate = extra_ink_amount(target, letters[ch], power=1.0, hue_override=hue)
        wt = w * np.clip(gate * 2.0, 0.0, 1.0)
        # target 0 for the complement where the gate is open (the strongest
        # gate wins when two extra inks want the same process ink out)
        take = wt > prior_w[:, comp]
        prior[take, comp] = 0.0
        prior_w[take, comp] = wt[take]
        if ECG_SEPARATION.get("sector"):
            # a14-ecgsep2: the extra ink itself stays out of the hue sectors
            # it does not belong to (measured with a14-ecgsep alone: O moved
            # into the green-cyan sector on X5, so C+O reappeared there)
            out = w * np.clip(1.0 - 2.0 * gate, 0.0, 1.0) * np.clip(
                np.hypot(target[:, 1], target[:, 2]) / 15.0, 0.0, 1.0)
            more = out > prior_w[:, ch]
            prior[more, ch] = 0.0
            prior_w[more, ch] = out[more]


def invert_to_device(model: ForwardModel, target: np.ndarray, *,
                     channel_letters: list[str], is_additive: bool,
                     ink_limit: float | None = None,
                     iters: int = 6, damping: float = 0.05,
                     seed_res: int = 7,
                     seed: np.ndarray | None = None,
                     k_prior: dict | None = None,
                     accurate: bool = False,
                     extra_hues: dict[str, float] | None = None,
                     black_l: float | None = None,
                     k_gen: dict | None = None,
                     ucs: bool = False,
                     channel_max: np.ndarray | None = None,
                     progress=None,
                     progress_label: str = "Inverting the model",
                     ) -> tuple[np.ndarray, np.ndarray]:
    """Invert the forward model at ``target`` Lab points.

    ``channel_max``: per-channel device ceiling (the black ink limit on K);
    None = the plain 0..1 cube.

    Returns ``(device, residual_de)`` — residual is the remaining ΔE76 after
    convergence, i.e. ~0 in gamut and the clamp distance outside (this array
    *is* the ``gamt`` table content).

    ``accurate`` (maximum-accuracy mode) switches on the boundary-aware
    Jacobian, Euclidean TAC projection and a hue-preserving re-clip of the
    out-of-gamut nodes; ``extra_hues`` carries the measured extra-ink hues.
    ``black_l`` anchors the GCR locus's full-black point on the printer's
    *measured* black L* — the in-gamut K separation then converges to the
    max-density clamp at the gamut boundary instead of jumping between
    metameric alternatives on adjacent nodes (shadow banding).
    """
    n = model.n_channels
    limit = None if ink_limit is None or is_additive else ink_limit / 100.0
    if n > 3:
        iters = max(iters, 10)      # surplus dof converge slower with priors
    # Candidate "ucs": GN minimises the residual in CAM16-UCS (a true
    # perceptual metric) — targets/seeds/retries all run through the UCS
    # view; the returned *residual* stays plain Lab ΔE76, because the gamt
    # tag encodes distance-from-gamut and must stay metric in PCS terms.
    gn_model, gn_target = model, target
    if ucs:
        from workflow.profile_engine.ucs import print_ucs
        _space = print_ucs()
        gn_model = _UcsView(model, _space)
        gn_target = _space.lab_to_ucs(target)
    if seed is None:
        seed = _seed_nearest(gn_model, gn_target, seed_res if n <= 4 else 5,
                             channel_max=channel_max, threads=accurate)
    d = seed.copy()
    if channel_max is not None:
        d = np.minimum(d, channel_max[None, :])

    free = np.arange(n)
    prior = prior_w = None
    if n > 3:
        prior, prior_w = ink_priors(
            target, n, channel_letters=channel_letters, k_prior=k_prior,
            k_gen=k_gen, accurate=accurate, extra_hues=extra_hues,
            black_l=black_l)
        d[:, 3:] = prior[:, 3:]

    gn_kw = dict(boundary_fd=accurate, tac_projection=accurate,
                 channel_max=channel_max, progress=progress)
    d = _gauss_newton(gn_model, gn_target, d, free, iters=iters,
                      damping=damping,
                      ink_limit=limit, prior=prior, prior_w=prior_w,
                      progress_label=f"{progress_label}: converging", **gn_kw)
    residual = np.linalg.norm(model.predict(d) - target, axis=1)

    # Projected GN can stall with a channel pinned against the wrong cube
    # face (measured: ~20% of near-saturation targets, while a good seed
    # never fails; the boundary-aware Jacobian removes the root cause but
    # the retry stays as a safety net). Retry the failures from a
    # dense-cloud nearest seed and keep whichever lands closer.
    retry = residual > 0.5
    if retry.any():
        cloud, cloud_lab = _cloud_and_lab(gn_model, model, n, limit,
                                          channel_max, 1234, memo=accurate)
        sub = gn_target[retry]
        seeds2 = np.empty((len(sub), n))
        cl2 = (cloud_lab ** 2).sum(1)
        for lo in range(0, len(sub), 2048):
            chunk = sub[lo:lo + 2048]
            d2 = cl2[None, :] - 2.0 * chunk @ cloud_lab.T
            seeds2[lo:lo + 2048] = cloud[np.argmin(d2, 1)]
        lmin = LIGHT_CLOUD.get("l_min")
        if lmin is not None and accurate:
            # Agent 21 "a21-lightcloud60" (ported by Agent 25 from 5fa8afdb):
            # light seeds only for light targets; dark targets keep exactly
            # the seeds they had (no change below L* lmin)
            lt = np.flatnonzero(target[retry][:, 0] >= lmin)
            if len(lt):
                lc_, lcl_ = _cloud_and_lab(gn_model, model, n, limit,
                                           channel_max, 1234, memo=True,
                                           light=True)
                c2 = (lcl_ ** 2).sum(1)
                for lo in range(0, len(lt), 2048):
                    ix = lt[lo:lo + 2048]
                    d2 = c2[None, :] - 2.0 * sub[ix] @ lcl_.T
                    seeds2[ix] = lc_[np.argmin(d2, 1)]
        d_retry = _gauss_newton(
            gn_model, sub, seeds2, free, iters=iters, damping=damping,
            ink_limit=limit,
            prior=None if prior is None else prior[retry],
            prior_w=None if prior_w is None else prior_w[retry],
            progress_label=f"{progress_label}: retrying difficult nodes",
            **gn_kw)
        res_retry = np.linalg.norm(model.predict(d_retry) - target[retry],
                                   axis=1)
        better = res_retry < residual[retry]
        idx = np.flatnonzero(retry)[better]
        d[idx] = d_retry[better]
        residual[idx] = res_retry[better]

    if accurate and _oog.PARAMS.get("on"):
        # Research (Agent 25, tokens a25-*): one continuous weighted
        # nearest-point clip in a hue-linear space, no accept/reject switch
        # (oog_clip module docstring; Findings agent25-01).
        d = _oog.clip_nodes(
            model, target, d, residual, free=free, limit=limit,
            channel_max=channel_max, prior=prior, prior_w=prior_w,
            gn_kw=gn_kw, damping=damping, progress_label=progress_label)
    elif accurate:
        # Hue-preserving clip: nodes that stay out of gamut are re-clipped
        # under a norm that punishes hue errors hardest — a clipped
        # saturated colour loses chroma instead of changing colour family.
        # The *residual* keeps the nearest-clip distance from above: the
        # ``gamt`` tag encodes distance-from-gamut and must stay metric.
        oog = residual > 1.0
        chroma_t = np.hypot(target[:, 1], target[:, 2])
        oog &= chroma_t >= 5.0          # neutrals keep the nearest clip
        if oog.any():
            # Seed every out-of-gamut node from a printable colour of the
            # SAME HUE (angle-gated), then polish under the hue-weighted
            # norm; a polish that drifts in hue or gains chroma is dropped.
            cloud2, cloud2_lab = _cloud_and_lab(model, model, n, limit,
                                                channel_max, 4321, memo=True)
            seeds_h, found = _hue_gated_seeds(target[oog], cloud2, cloud2_lab)
            lmin = LIGHT_CLOUD.get("l_min")
            if lmin is not None:
                lt = np.flatnonzero(target[oog][:, 0] >= lmin)
                if len(lt):
                    lc_, lcl_ = _cloud_and_lab(model, model, n, limit,
                                               channel_max, 4321, memo=True,
                                               light=True)
                    sh2, f2 = _hue_gated_seeds(target[oog][lt], lc_, lcl_)
                    seeds_h[lt] = sh2
                    found[lt] = f2
            sub_idx = np.flatnonzero(oog)[found]
            if len(sub_idx):
                wm = _ucs_hue_weight_matrices(gn_target[sub_idx]) if ucs \
                    else _hue_weight_matrices(target[sub_idx])
                d_pol = _gauss_newton(
                    gn_model, gn_target[sub_idx], seeds_h[found], free,
                    iters=4, damping=damping,
                    ink_limit=limit, err_weights=wm,
                    prior=None if prior is None else prior[sub_idx],
                    prior_w=None if prior_w is None else prior_w[sub_idx],
                    progress_label=f"{progress_label}: hue-preserving clip",
                    **gn_kw)
                lab_pol = model.predict(d_pol)
                lab_seed = model.predict(seeds_h[found])
                t_sub = target[sub_idx]
                t_h = np.degrees(np.arctan2(t_sub[:, 2], t_sub[:, 1]))
                p_h = np.degrees(np.arctan2(lab_pol[:, 2], lab_pol[:, 1]))
                dh = np.abs((p_h - t_h + 180.0) % 360.0 - 180.0)
                gained = (np.hypot(lab_pol[:, 1], lab_pol[:, 2])
                          > np.hypot(t_sub[:, 1], t_sub[:, 2]) + 3.0)
                keep = (dh <= 10.0) & ~gained
                if CLIP_FIX.get("on"):
                    # Agent 21 / F-15 (token a21-clipfix, ported by Agent 25
                    # from research/pe-nink-research a2e64114): a hue angle is
                    # meaningless at low chroma, and a rejected polish must
                    # not write the RAW cloud seed: fall back to the plain
                    # nearest clip already in d, unless the seed is closer.
                    c_pol = np.hypot(lab_pol[:, 1], lab_pol[:, 2])
                    c_t = np.hypot(t_sub[:, 1], t_sub[:, 2])
                    keep = (((dh <= 10.0) | (np.minimum(c_pol, c_t) < 5.0))
                            & ~gained)
                    near = d[sub_idx]
                    e_near = np.linalg.norm(model.predict(near) - t_sub, axis=1)
                    e_seed = np.linalg.norm(lab_seed - t_sub, axis=1)
                    fb = np.where((e_near <= e_seed)[:, None], near,
                                  seeds_h[found])
                    d_pol[~keep] = fb[~keep]
                else:
                    d_pol[~keep] = seeds_h[found][~keep]
                d[sub_idx] = d_pol
    return d, residual


def neutral_axis(model: ForwardModel, *, step: float = 0.5,
                 deep_black: bool = True, **inv_kw) -> dict:
    """The neutral axis of an ink device, solved once by continuation.

    Walks a* = b* = 0 from paper white (device 0) down in ``step`` L*
    increments; every solve is seeded with the previous solution, so the
    separation changes continuously along the axis (no metameric jump
    between neighbouring L*, whatever the channel count) and a light tint
    is never seeded from a 25 % mesh point. The darkest L* that still
    converges neutral (residual < 0.5 ΔE76, model C* < 1) is the device's
    NEUTRAL BLACK under its limits: colprof's Lmin (xicc/xlut.c,
    efv_wh_bk_points) where the engine used the darkest measured patch,
    which is usually chromatic. ``inv_kw`` are :func:`invert_to_device`'s
    keywords. Returns ``l`` (targets, light to dark), ``dev``, ``ok``,
    ``l_black`` (model L* of the neutral black), ``black`` (its device
    value). Research agent5-03 item 5.
    """
    n = model.n_channels
    ls = np.arange(100.0, -1e-9, -step)
    dev = np.zeros((len(ls), n))
    res = np.zeros(len(ls))
    cur = np.zeros((1, n))
    kw = {k: v for k, v in inv_kw.items()
          if k not in ("node_lab", "progress", "seed")}
    for i, lv in enumerate(ls):
        d, r = invert_to_device(model, np.array([[lv, 0.0, 0.0]]),
                                seed=cur.copy(), **kw)
        dev[i], res[i] = d[0], r[0]
        cur = d
    lab = model.predict(dev)
    ok = (res < 0.5) & (np.hypot(lab[:, 1], lab[:, 2]) < 1.0)
    if not ok.any():
        return {"l": ls, "dev": dev, "ok": ok, "l_black": None,
                "black": None}
    last = int(np.flatnonzero(ok)[-1])
    axis = {"l": ls, "dev": dev, "ok": ok, "l_black": float(lab[last, 0]),
            "black": dev[last].copy()}
    if deep_black:
        axis = _deepen_neutral_black(model, axis, step=step, kw=kw)
    return axis


# Research agent17-01 item 1: the walk from paper white is a CONTINUATION
# under the ink policy, whose K prior on neutrals (the late-GCR locus, weight
# 2.0, full K only at the darkest MEASURED patch) is firm. On a printer whose
# dark end lightens (bronzing, over-inked matte media: L* rises again above
# some total coverage) that branch loads C, M and Y into the lightening zone
# and stops at the ink-limit face: agent 13's XKB walks to L* 22.1 at 295 %
# ink while the model itself prints a neutral L* 7.5 at 205 % (K 1.0,
# C/M/Y 0.35). The black is therefore also searched WITHOUT the policy (a
# constrained minimum of L* over the model, many seeds), and when it is
# clearly deeper the dark end of the axis is re-walked from a join point on
# the forward walk down to it, with the neutral K prior blended linearly
# from the walk's K at the join to the deep black's K: K enters earlier,
# the separation stays continuous at the join, and C/M/Y stay out of the
# lightening zone. Printers on which the walk already finds the deepest
# neutral are untouched (the walk's axis is returned as is).
_DEEP_BLACK_MARGIN = 1.0      # L*: below this gain the walk's black stays
_DEEP_BLACK_SEEDS = 12
_DEEP_BLACK_JOIN_STEP = 2.0   # L*: spacing of the join points tried
_DEEP_BLACK_JOIN_TOP = 60.0   # L*: lightest join tried (K starts near here)
# CMYK only for now: on the battery's 6-ink S7 (walk 12.8, global 8.7) the
# re-route gave a 3.2 L* deeper neutral black and a better B2A (median
# 0.882 -> 0.828, p95 1.990 -> 1.600) but C/M/Y rise and fall along the
# grey ramp (P7 TV excess 0.05 -> 0.25) and the L* 14-30 neutral median
# went 0.61 -> 0.74. 5+ inks wait for an N-ink-aware blend (agent17-01 1.6).
_DEEP_BLACK_MAX_INKS = 4


def _neutral_ok(model: ForwardModel, d: np.ndarray, r: np.ndarray):
    lab = model.predict(d)
    return (r < 0.5) & (np.hypot(lab[:, 1], lab[:, 2]) < 1.0), lab


def deepest_neutral(model: ForwardModel, *, step: float = 0.5,
                    kw: dict) -> tuple[float, np.ndarray] | None:
    """The darkest neutral the MODEL prints under the build's limits,
    whatever the ink policy says.

    Seeds: the darkest near-neutral points (model C* < 4) of the
    limit-respecting device cloud the inversion's retries use, chosen
    greedily so no two seeds are within 0.15 of each other in device space
    (different branches of the metamer family). From each seed the axis is
    walked DOWN in ``step`` L* by plain damped Gauss-Newton on the colour
    alone (no priors; same TAC projection, channel ceilings and
    boundary-aware Jacobian as the inversion), accepting a step by the
    walk's own rule (residual < 0.5 ΔE76, model C* < 1) and stopping after
    two failures in a row. Returns ``(model L*, device)`` of the darkest
    accepted point, or None. Deterministic (fixed cloud seed, stable sort)."""
    n = model.n_channels
    ink_limit = kw.get("ink_limit")
    limit = (None if ink_limit is None or kw.get("is_additive")
             else ink_limit / 100.0)
    cmax = kw.get("channel_max")
    cloud, lab = _cloud_and_lab(model, model, n, limit, cmax, 2718,
                                memo=True)
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    cand = np.flatnonzero(chroma < 4.0)
    if not len(cand):
        return None
    cand = cand[np.argsort(lab[cand, 0], kind="stable")]
    seeds: list[int] = []
    for i in cand:
        if all(np.max(np.abs(cloud[i] - cloud[j])) > 0.15 for j in seeds):
            seeds.append(int(i))
            if len(seeds) >= _DEEP_BLACK_SEEDS:
                break
    free = np.arange(n)
    best = None
    for i in seeds:
        cur = cloud[i][None, :].copy()
        lv = np.ceil(lab[i, 0] / step) * step
        fails = 0
        while lv >= -1e-9 and fails < 2:
            t = np.array([[lv, 0.0, 0.0]])
            d = _gauss_newton_rows(model, t, cur, free, iters=12,
                                   damping=0.05, ink_limit=limit,
                                   boundary_fd=True, tac_projection=True,
                                   channel_max=cmax)
            r = np.linalg.norm(model.predict(d) - t, axis=1)
            okv, labd = _neutral_ok(model, d, r)
            if okv[0]:
                fails = 0
                cur = d
                if best is None or labd[0, 0] < best[0] - 1e-9:
                    best = (float(labd[0, 0]), d[0].copy())
            else:
                fails += 1
            lv -= step
    return best


def _deepen_neutral_black(model: ForwardModel, axis: dict, *, step: float,
                          kw: dict) -> dict:
    """Re-walk the dark end of the axis to a deeper neutral black when one
    exists (see the comment above). Join points on the forward walk are
    tried every ``_DEEP_BLACK_JOIN_STEP`` L* from its black up to
    ``_DEEP_BLACK_JOIN_TOP``; from each, the blended-K walk must stay
    accepted all the way down to the deep black. Of the joins that work the
    one with the least ink total variation along the whole axis wins (the
    grey ramp then neither rises and falls in any ink nor detours through
    the ink-limit face), the darker join on a tie. Needs a K channel (the
    blend is a K prior); with none, or when no join works, the walk's axis
    is returned unchanged."""
    letters = kw.get("channel_letters") or []
    if "K" not in letters or model.n_channels > _DEEP_BLACK_MAX_INKS:
        return axis
    found = deepest_neutral(model, step=step, kw=kw)
    if found is None or found[0] > axis["l_black"] - _DEEP_BLACK_MARGIN:
        return axis
    l_deep, black = found
    ki = letters.index("K")
    ls = np.asarray(axis["l"])
    dev_f = np.asarray(axis["dev"], float)
    ok_f = np.asarray(axis["ok"], bool)
    seg_kw = {k: v for k, v in kw.items() if k != "k_prior"}
    joins = [int(j) for j in np.flatnonzero(
        ok_f & (ls >= axis["l_black"] - 1e-9) & (ls <= _DEEP_BLACK_JOIN_TOP)
        & (np.abs(np.round((ls - axis["l_black"]) / _DEEP_BLACK_JOIN_STEP)
                  * _DEEP_BLACK_JOIN_STEP - (ls - axis["l_black"])) < step / 2
           ))]
    best = None
    for j in sorted(joins, reverse=True):        # darkest join first
        k_curve = {"l_axis": np.array([l_deep, ls[j]]),
                   "k_curve": np.array([black[ki], dev_f[j, ki]]),
                   "neutral_only": True}
        dev_s = dev_f.copy()
        ok_s = ok_f.copy()
        cur = dev_f[j][None, :].copy()
        i = j + 1
        good = True
        while i < len(ls) and ls[i] >= l_deep - 1e-9:
            d, r = invert_to_device(model, np.array([[ls[i], 0.0, 0.0]]),
                                    seed=cur.copy(), k_prior=k_curve,
                                    **seg_kw)
            okv, _ = _neutral_ok(model, d, r)
            if not okv[0]:
                good = False
                break
            dev_s[i], ok_s[i] = d[0], True
            cur = d
            i += 1
        if not good:
            continue
        last = i - 1
        tv = float(np.abs(np.diff(dev_s[:last + 1], axis=0)).sum())
        if best is None or tv < best[0] - 1e-9:
            ok_s[last + 1:] = False
            best = (tv, j, last, dev_s, ok_s, k_curve)
    if best is None:
        return axis
    tv, j, last, dev_s, ok_s, k_curve = best
    lab_last = model.predict(dev_s[last][None, :])[0]
    return {"l": ls, "dev": dev_s, "ok": ok_s, "l_black": float(lab_last[0]),
            "black": dev_s[last].copy(), "deep_black": True,
            "walk_l_black": axis["l_black"], "join_l": float(ls[j]),
            "axis_tv": tv}


# Research token "a29-blackhandover" (Agent 29a, Findings/agent29a-01).
# The neutral axis ends at the darkest point the model prints NEUTRAL (C* <
# 1). Where the printer's deepest black is slightly tinted, colprof's black
# is that deeper tinted one (xicc/xlut.c bfindfunc: minimise L* with a soft
# penalty on a*b*, then the clip vector lines every out-of-gamut neutral up
# with the white-black line), and ours was up to 2-5 L* lighter (battery
# v3.1: R-CMYK-default, XKB, X3; perceptually S1, S2, X1, XKH). The axis is
# kept neutral down to its neutral black and then HANDED OVER to a deeper,
# slightly tinted black: the device value is blended linearly from the
# neutral black to the deep black, so no ink jumps and C* rises from ~0 at
# the neutral black to the deep black's C*. The deep black is the darkest
# model point under the build's limits for a ladder of chroma bounds,
# scored L* + _HANDOVER_LAMBDA * C* (1 C* costs half an L*), and it is only
# used when that score beats the neutral black by _HANDOVER_MIN_GAIN.
_HANDOVER_LADDER = (1.0, 2.0, 3.0)
_HANDOVER_LAMBDA = 0.5
_HANDOVER_MIN_GAIN = 0.3
_HANDOVER_SEEDS = 12


def deepest_tinted(model: ForwardModel, *, chroma_max: float, kw: dict,
                   step: float = 0.5, seeds_n: int = _HANDOVER_SEEDS
                   ) -> tuple[np.ndarray, np.ndarray] | None:
    """The darkest point the MODEL prints with C* <= ``chroma_max`` under
    the build's limits (TAC, channel ceilings), whatever the ink policy.

    Seeds: the darkest points of the limit-respecting device cloud with
    C* below max(2 * chroma_max, 4), greedily 0.15 apart in device space,
    plus K alone when there is a K channel (colprof's first trial, 000K).
    From each, damped Gauss-Newton walks down in L* holding the current
    a*b* (pulled inside 0.8 * ``chroma_max``), halving the step on a
    failure and stopping after three. Returns ``(model Lab, device)`` of the
    darkest accepted point, or None. Deterministic."""
    n = model.n_channels
    ink_limit = kw.get("ink_limit")
    limit = (None if ink_limit is None or kw.get("is_additive")
             else ink_limit / 100.0)
    cmax = kw.get("channel_max")
    cloud, lab = _cloud_and_lab(model, model, n, limit, cmax, 2718,
                                memo=True)
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    cand = np.flatnonzero(chroma < max(2.0 * chroma_max, 4.0))
    cand = cand[np.argsort(lab[cand, 0], kind="stable")]
    seeds: list[np.ndarray] = []
    for i in cand:
        if all(np.max(np.abs(cloud[i] - s)) > 0.15 for s in seeds):
            seeds.append(cloud[i])
            if len(seeds) >= seeds_n:
                break
    letters = kw.get("channel_letters") or []
    if "K" in letters:
        k = np.zeros(n)
        k[letters.index("K")] = 1.0
        if cmax is not None:
            k = np.minimum(k, np.asarray(cmax, float))
        seeds.append(k)
    free = np.arange(n)
    gn = dict(free=free, damping=0.05, ink_limit=limit, boundary_fd=True,
              tac_projection=True, channel_max=cmax)
    best = None
    for s in seeds:
        cur = np.asarray(s, float)[None, :].copy()
        lc = model.predict(cur)[0]
        c = float(np.hypot(lc[1], lc[2]))
        if c > chroma_max:
            ab = lc[1:] * (0.8 * chroma_max / c)
            cur = _gauss_newton_rows(model, np.array([[lc[0], ab[0], ab[1]]]),
                                     cur, iters=20, **gn)
            lc = model.predict(cur)[0]
            if np.hypot(lc[1], lc[2]) > chroma_max:
                continue
        st, fails = step, 0
        while fails < 3:
            c = float(np.hypot(lc[1], lc[2]))
            ab = lc[1:] * min(1.0, 0.8 * chroma_max / max(c, 1e-9))
            d = _gauss_newton_rows(
                model, np.array([[lc[0] - st, ab[0], ab[1]]]), cur,
                iters=12, **gn)
            ln = model.predict(d)[0]
            if ln[0] < lc[0] - 0.01 and np.hypot(ln[1], ln[2]) <= chroma_max:
                cur, lc, fails = d, ln, 0
            else:
                fails += 1
                st /= 2.0
        if best is None or lc[0] < best[0][0] - 1e-9:
            best = (lc.copy(), cur[0].copy())
    return best


def handover_black(model: ForwardModel, *, l_neutral: float,
                   c_neutral: float, kw: dict,
                   ladder: tuple = _HANDOVER_LADDER) -> dict | None:
    """The deep black the axis is handed over to, or None when it does not
    beat the neutral black (``l_neutral``, chroma ``c_neutral``) by
    _HANDOVER_MIN_GAIN in L* + _HANDOVER_LAMBDA * C*."""
    base = l_neutral + _HANDOVER_LAMBDA * c_neutral
    best = None
    for cm in ladder:
        found = deepest_tinted(model, chroma_max=cm, kw=kw)
        if found is None:
            continue
        lab, dev = found
        score = float(lab[0] + _HANDOVER_LAMBDA * np.hypot(lab[1], lab[2]))
        if best is None or score < best["score"] - 1e-9:
            best = {"lab": lab, "dev": dev, "score": score, "chroma_max": cm}
    if best is None or best["score"] > base - _HANDOVER_MIN_GAIN:
        return None
    return best


def blackhandover_axis(model: ForwardModel, axis: dict, *,
                       ladder: tuple = _HANDOVER_LADDER,
                       chooser=None, **inv_kw) -> dict:
    """Research token "a29-blackhandover": extend the neutral axis below its
    neutral black to a deeper, slightly tinted black (see the comment
    above). Grid points of ``axis["l"]`` between the deep black's L* and the
    neutral black's take the device value of the linear device blend
    neutral black -> deep black at that model L* (the blend's L* made
    monotone by keeping only new minima). The axis black becomes the deep
    black; ``neutral_l_black`` keeps the old one. Returns the axis
    unchanged when there is no deeper black worth it."""
    if axis.get("black") is None:
        return axis
    kw = {k: v for k, v in inv_kw.items()
          if k not in ("node_lab", "progress", "seed")}
    nb = np.asarray(axis["black"], float)
    lab_nb = model.predict(nb[None, :])[0]
    # ``chooser``: research a34-blackseam picks the deep black by its own
    # rule (rate_deep_black); None keeps the a29 rule.
    deep = (chooser or handover_black)(
        model, l_neutral=float(lab_nb[0]),
        c_neutral=float(np.hypot(lab_nb[1], lab_nb[2])), kw=kw,
        ladder=ladder)
    if deep is None:
        return axis
    dd = np.asarray(deep["dev"], float)
    u = np.linspace(0.0, 1.0, 81)
    blend = nb[None, :] + u[:, None] * (dd - nb)[None, :]
    if kw.get("ink_limit") is not None and not kw.get("is_additive"):
        blend = project_tac(blend, kw["ink_limit"] / 100.0)
    bl = model.predict(blend)[:, 0]
    keep = [0]
    for i in range(1, len(u)):
        if bl[i] < bl[keep[-1]] - 1e-6:
            keep.append(i)
    keep = np.asarray(keep)
    if len(keep) < 2:
        return axis
    l_k, d_k = bl[keep], blend[keep]
    l_deep = float(l_k[-1])
    ls = np.asarray(axis["l"], float)
    dev = np.asarray(axis["dev"], float).copy()
    ok = np.asarray(axis["ok"], bool).copy()
    order = np.argsort(l_k)
    for i, lv in enumerate(ls):
        if lv >= lab_nb[0] - 1e-9 or lv < l_deep - 1e-9:
            continue
        dev[i] = [np.interp(lv, l_k[order], d_k[order, c])
                  for c in range(dev.shape[1])]
        ok[i] = True
    last = int(np.flatnonzero(ok)[-1])
    ok[last + 1:] = False
    lab_k = model.predict(d_k)
    out = dict(axis)
    out.update({"dev": dev, "ok": ok, "l_black": l_deep,
                "black": d_k[-1].copy(), "handover": True,
                "neutral_l_black": float(lab_nb[0]),
                "neutral_black": nb.copy(),
                "handover_lab": lab_k[-1],
                "blend_l": l_k, "blend_dev": d_k,
                "blend_c": np.hypot(lab_k[:, 1], lab_k[:, 2])})
    return out


# Research token "a34-blackseam" (Agent 34, Findings/agent34-01). Two
# parts on top of the a29 hand-over (which it replaces as the black rule):
#
# 1. The deep black is chosen by a RATE, not by a fixed chroma cap: from
#    the neutral black, step to the deeper, slightly tinted black of the
#    chroma ladder that buys the most L* per C* of tint, and only while
#    every C* buys at least A34_RATE L*; the tint may not exceed the
#    printer's own darkest measured near-neutral patches by more than
#    A34_MEAS_MARGIN. The a29 cap (C* 2) was below the i1iSis's tinted black
#    (its darkest measured patches are C* 2.5-2.9; colprof's black C* 4.1)
#    and above what XKB pessimistic t400's 0.2 L* extra depth was worth.
# 2. Every neutral column node above the black takes an axis value: the
#    walk leaves rows it cannot solve neutral (i1Pro: 23.5-28 L*, where the
#    K-only and the rich C+M+Y+K separations meet), and a column node whose
#    row failed fell back to its own per-node inversion, a third
#    separation (i1Pro node L* 28.1 printed model L* 39.9 before the refit
#    smoothed it). Such rows are filled by interpolating the two nearest
#    solved rows when both lie on the same separation branch and the
#    filled device prints neutral in the model.
A34_RATE = 1.0
A34_LADDER = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
A34_MEAS_MARGIN = 1.0
A34_MEAS_N = 3
A34_MEAS_MAX_C = 6.0
A34_FILL_BRANCH = 0.3       # max channel difference of the two neighbours
A34_FILL_TOL_L = 1.0        # filled row: model L* within this of its target
A34_FILL_TOL_C = 1.5        # ... and model C* below this


def measured_dark_chroma(lab: np.ndarray, device: np.ndarray, *,
                         ink_limit: float | None = None,
                         n: int = A34_MEAS_N,
                         max_c: float = A34_MEAS_MAX_C) -> float | None:
    """Median C* of the ``n`` darkest measured patches that are
    near-neutral (C* < ``max_c``) and within the ink limit (percent): the
    tint of the printer's own deepest blacks. None without such patches."""
    lab = np.asarray(lab, float)
    device = np.asarray(device, float)
    c = np.hypot(lab[:, 1], lab[:, 2])
    keep = c < max_c
    if ink_limit is not None:
        keep &= device.sum(1) * 100.0 <= float(ink_limit) + 1e-6
    idx = np.flatnonzero(keep)
    if not len(idx):
        return None
    idx = idx[np.argsort(lab[idx, 0], kind="stable")][:n]
    return float(np.median(c[idx]))


def rate_deep_black(model: ForwardModel, *, l_neutral: float,
                    c_neutral: float, kw: dict,
                    ladder: tuple = A34_LADDER, rate: float = A34_RATE,
                    max_chroma: float | None = None,
                    candidates: list | None = None) -> dict | None:
    """a34-blackseam's deep black (see the comment above): greedy on the
    chroma ladder, from the neutral black, take the rung with the best
    L* gained per C* added while that is at least ``rate``; rungs above
    ``max_chroma`` are not tried. ``candidates``: precomputed (model Lab,
    device) per rung, for tests. None when no rung is worth it."""
    rungs = [c for c in ladder if max_chroma is None or c <= max_chroma]
    found = []
    for i, cm in enumerate(rungs):
        f = (candidates[i] if candidates is not None
             else deepest_tinted(model, chroma_max=cm, kw=kw))
        if f is None:
            continue
        lab, dev = f
        found.append({"lab": np.asarray(lab, float),
                      "dev": np.asarray(dev, float), "chroma_max": cm,
                      "c": float(np.hypot(lab[1], lab[2]))})
    cur_l, cur_c, best = float(l_neutral), float(c_neutral), None
    while True:
        step = None
        for f in found:
            dl = cur_l - float(f["lab"][0])
            dc = f["c"] - cur_c
            if dl <= 1e-6:
                continue
            r = dl / dc if dc > 1e-6 else np.inf
            if r >= rate and (step is None or r > step[0] + 1e-12):
                step = (r, f)
        if step is None:
            break
        best = step[1]
        cur_l, cur_c = float(best["lab"][0]), best["c"]
    if best is None:
        return None
    out = dict(best)
    out["score"] = float(best["lab"][0])
    return out


def fill_axis_gaps(model: ForwardModel, axis: dict, *,
                   branch: float = A34_FILL_BRANCH,
                   tol_l: float = A34_FILL_TOL_L,
                   tol_c: float = A34_FILL_TOL_C) -> dict:
    """a34-blackseam part 2: rows of the walk between its paper white and
    its (neutral) black that did not solve neutral take the linear
    interpolation in L* of the nearest solved rows above and below, when
    those two are on the same branch (no channel differs by more than
    ``branch``) and the filled device prints within ``tol_l`` L* of the row
    and below ``tol_c`` C* in the model. Returns a new axis (``filled``:
    the L* values filled) or the axis itself when nothing was filled."""
    if axis.get("black") is None:
        return axis
    ls = np.asarray(axis["l"], float)
    dev = np.asarray(axis["dev"], float).copy()
    ok = np.asarray(axis["ok"], bool).copy()
    l_bottom = float(axis.get("neutral_l_black", axis["l_black"]))
    rows = np.flatnonzero(~ok & (ls >= l_bottom - 1e-9))
    good = np.flatnonzero(ok)
    filled = []
    for i in rows:
        hi = good[ls[good] > ls[i]]
        lo = good[(ls[good] < ls[i]) & (ls[good] >= l_bottom - 0.5 - 1e-9)]
        if not len(hi) or not len(lo):
            continue
        a = hi[np.argmin(ls[hi])]
        b = lo[np.argmax(ls[lo])]
        if np.max(np.abs(dev[a] - dev[b])) > branch:
            continue
        t = (ls[a] - ls[i]) / (ls[a] - ls[b])
        d = dev[a] + t * (dev[b] - dev[a])
        lab = model.predict(d[None, :])[0]
        if (abs(lab[0] - ls[i]) > tol_l
                or np.hypot(lab[1], lab[2]) > tol_c):
            continue
        filled.append((i, d))
    if not filled:
        return axis
    for i, d in filled:
        dev[i], ok[i] = d, True
    out = dict(axis)
    out.update({"dev": dev, "ok": ok,
                "filled": [float(ls[i]) for i, _ in filled]})
    return out


# Research tokens "a35-percblack-blend" / "a35-percblack-deep" (Agent 35,
# Findings/agent35-01-percblack.md; Basti 2026-10-06 night). The perceptual
# and saturation tables end at the SAME black as the colorimetric one (RGB
# 0 on an RGB printer, a34-blackseam's rate-chosen deep black on ink), not
# at the neutral black (S1 28.8 vs colprof 26.8, ET on paper +1.1 L*). The
# neutral column's target a*b* is handed over from neutral to the deep
# black's a*b* over a band [l_deep, l_deep + width] of target L*:
#
# * blend (option 3): smoothstep (C1 at both ends, monotone). The width is
#   the L* gap between the neutral and the deep black, widened only as far
#   as the measured hand-over path (the device line from the neutral black
#   to the deep black, monotone part) needs for every band target to be
#   printable: the curve's fraction of the deep black's tint must reach the
#   path's own fraction at every path sample (in-gamut, so the inversion
#   never has to clip a target to a lighter neutral).
# * deep (option 1, colprof's way): Argyll's gmm_bendBP (gamut/gammap.c
#   l. 1378-1445): the band is the black's a*b* distance from neutral
#   ("brad", in L* units), the blend is smoothstep of smoothstep near the
#   top and linear at the black, towards the straight white-to-black axis.
#   Never narrower than the printable width above.
A35_TOKENS = ("a35-percblack-blend", "a35-percblack-deep")
_A35_WIDTH_STEPS = 32           # width search resolution: gap / 32 ...
_A35_WIDTH_MAX = 4.0            # ... up to 4 x the gap


def a35_mode(candidates) -> str | None:
    """'blend', 'deep' or None from the build's candidate tokens (deep
    wins when both are given)."""
    c = set(candidates or ())
    if "a35-percblack-deep" in c:
        return "deep"
    if "a35-percblack-blend" in c:
        return "blend"
    return None


def _smoothstep(t: np.ndarray) -> np.ndarray:
    t = np.clip(np.asarray(t, float), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def percblack_fraction(target_l: np.ndarray, *, l_deep: float,
                       width: float, mode: str) -> np.ndarray:
    """Fraction (0 above the band, 1 at and below the deep black) of the
    deep black's a*b* at each target L*."""
    u = (float(l_deep) + float(width) - np.asarray(target_l, float)) \
        / max(float(width), 1e-9)
    if mode == "deep":
        t = _smoothstep(u)
        ty = _smoothstep(t)
        return (1.0 - t) * ty + t * t      # gammap.c: spline at 0, linear at 1
    return _smoothstep(u)


def percblack_tint(target_l: np.ndarray, *, l_deep: float,
                   ab_deep: np.ndarray, width: float, mode: str,
                   l_white: float = 100.0) -> np.ndarray:
    """a*b* targets of the hand-over (see the comment above). ``deep``
    blends towards the straight white-to-black axis, as gammap.c does."""
    tl = np.asarray(target_l, float)
    f = percblack_fraction(tl, l_deep=l_deep, width=width, mode=mode)
    if mode == "deep":
        span = max(float(l_white) - float(l_deep), 1e-9)
        f = f * np.clip((float(l_white) - tl) / span, 0.0, 1.0)
    return f[:, None] * np.asarray(ab_deep, float)[None, :]


def percblack_width(path_l: np.ndarray, path_c: np.ndarray, *,
                    l_neutral: float, l_deep: float, c_deep: float,
                    mode: str) -> float:
    """Band width (L*) of the hand-over. ``path_l`` / ``path_c``: model L*
    and C* along the hand-over path from the neutral black (first) to the
    deep black (last). blend: the smallest gap * (1 + k / 32) whose
    smoothstep fraction reaches the path's fraction (C* above the neutral
    black's, over the deep black's) at every path sample; deep: the black's
    chroma (gammap.c brad), at least that printable width."""
    gap = max(float(l_neutral) - float(l_deep), 1e-6)
    pl = np.asarray(path_l, float)
    pc = np.asarray(path_c, float)
    c_top = float(pc[0]) if len(pc) else 0.0
    den = max(float(c_deep) - c_top, 1e-9)
    need = np.clip((pc - c_top) / den, 0.0, 1.0)
    w_ok = gap * _A35_WIDTH_MAX
    for k in range(int(_A35_WIDTH_STEPS * (_A35_WIDTH_MAX - 1.0)) + 1):
        w = gap * (1.0 + k / _A35_WIDTH_STEPS)
        f = percblack_fraction(pl, l_deep=l_deep, width=w, mode="blend")
        if np.all(f >= need - 1e-6):
            w_ok = w
            break
    if mode == "deep":
        return max(float(c_deep), w_ok)
    return w_ok


def rgb_handover_path(model: ForwardModel, neutral_dev: np.ndarray,
                      n: int = 81):
    """RGB: the device line from the neutral black's device value to RGB 0,
    its monotone (darkening) part: ``(l, dev, c)`` from the neutral black
    to RGB 0, as blackhandover_axis builds the ink path."""
    nb = np.asarray(neutral_dev, float)
    u = np.linspace(0.0, 1.0, n)
    line = nb[None, :] * (1.0 - u)[:, None]
    lab = model.predict(line)
    keep = [0]
    for i in range(1, n):
        if lab[i, 0] < lab[keep[-1], 0] - 1e-6:
            keep.append(i)
    keep = np.asarray(keep)
    return lab[keep, 0], line[keep], np.hypot(lab[keep, 1], lab[keep, 2])


def path_device_at(target_l: np.ndarray, path_l: np.ndarray,
                   path_dev: np.ndarray) -> np.ndarray:
    """Device values on the hand-over path at the given L* (linear in L*,
    clamped to the path's ends)."""
    o = np.argsort(path_l)
    pl, pd = np.asarray(path_l, float)[o], np.asarray(path_dev, float)[o]
    tl = np.asarray(target_l, float)
    return np.column_stack([np.interp(tl, pl, pd[:, c])
                            for c in range(pd.shape[1])])


def percblack_band_devices(model: ForwardModel, target: np.ndarray,
                           inverted: np.ndarray, on_path: np.ndarray
                           ) -> np.ndarray:
    """Per band node, the device value of the two candidates (the inversion
    of the hand-over target, and the hand-over path at the target L*) that
    the model prints closer to the target (dE76). The path value is always
    printable and monotone, so a node whose inversion had to clip keeps the
    path."""
    a = model.predict(np.asarray(inverted, float))
    b = model.predict(np.asarray(on_path, float))
    t = np.asarray(target, float)
    da = np.linalg.norm(a - t, axis=1)
    db = np.linalg.norm(b - t, axis=1)
    return np.where((da <= db)[:, None], inverted, on_path)


def axis_points(axis: dict, chroma_cap: float | None = None):
    """The axis as interpolation points for the mapped intents: ``(ls
    ascending, devices, l_black, black)``. The accepted grid points, and on
    a hand-over axis the neutral part plus the exact blend samples (the
    0.5 L* grid alone ends above the deep black). ``chroma_cap``: the blend
    stops at the last sample whose model C* is within it (research
    a29-blackhandover: the perceptual black is handed over only as far as
    colprof's own perceptual black is tinted, at least C* 1)."""
    ls = np.asarray(axis["l"], float)
    ok = np.asarray(axis["ok"], bool)
    dev = np.asarray(axis["dev"], float)
    if not axis.get("handover"):
        o = np.argsort(ls[ok])
        return ls[ok][o], dev[ok][o], float(axis["l_black"]), \
            np.asarray(axis["black"], float)
    top = ok & (ls >= axis["neutral_l_black"] - 1e-9)
    bl = np.asarray(axis["blend_l"], float)
    bd = np.asarray(axis["blend_dev"], float)
    if chroma_cap is not None:
        bc = np.asarray(axis["blend_c"], float)
        over = np.flatnonzero(bc > chroma_cap)
        n_keep = int(over[0]) if len(over) else len(bl)
        n_keep = max(n_keep, 1)                # the neutral black itself
        bl, bd = bl[:n_keep], bd[:n_keep]
    pl = np.concatenate([ls[top], bl])
    pd = np.vstack([dev[top], bd])
    o = np.argsort(pl, kind="stable")
    pl, pd = pl[o], pd[o]
    keep = np.concatenate([[True], np.diff(pl) > 1e-9])
    pl, pd = pl[keep], pd[keep]
    return pl, pd, float(pl[0]), pd[0].copy()


def handover_target_ab(target_l: np.ndarray, *, l_top: float,
                       l_deep: float, ab_deep: np.ndarray) -> np.ndarray:
    """a*b* of the hand-over curve at ``target_l``: 0 at and above
    ``l_top``, the deep black's a*b* at and below ``l_deep``, smoothstep in
    between (C1 at both ends)."""
    span = max(float(l_top) - float(l_deep), 1e-6)
    t = np.clip((float(l_top) - np.asarray(target_l, float)) / span,
                0.0, 1.0)
    s = t * t * (3.0 - 2.0 * t)
    return s[:, None] * np.asarray(ab_deep, float)[None, :]


def anchor_column_black(target_l: np.ndarray, source_l: np.ndarray,
                        black_l: float, fade: float = 25.0) -> np.ndarray:
    """Perceptual column lightness with the SOURCE black on the destination
    black: the darkest source-neutral node's target L* is moved onto
    ``black_l`` and the correction fades out linearly by source L* =
    ``fade``; then made non-increasing from light to dark. Research
    a29-blackhandover: on XKH september the engine's model prints colprof's
    perceptual black device value at L* 9.0 (colprof's own A2B: 5.0), so
    the column ended 3.8 L* above the black B2A1 prints."""
    tl = np.asarray(target_l, float).copy()
    sl = np.asarray(source_l, float)
    if not len(tl):
        return tl
    i0 = int(np.argmin(sl))
    shift = float(black_l) - tl[i0]
    w = np.clip(1.0 - (sl - sl[i0]) / fade, 0.0, 1.0)
    tl = tl + shift * w
    order = np.argsort(-sl, kind="stable")             # light to dark
    tl[order] = np.minimum.accumulate(tl[order])
    return tl


def monotone_black(model: ForwardModel, axis: dict,
                   tol: float = 0.02) -> dict:
    """Research agent9-01 6.2 ("a9-monoblack"): end the neutral axis at
    the darkest step reached WITHOUT any ink falling back (by more than
    ``tol``) after it rose. Deeper neutrals on 5+ ink printers are bought
    at the ink-limit face by swapping one ink for another (S6: M 0.66 ->
    0.03 for V 0 -> 0.58 in the last 4 L*), which is the grey ramp's rise
    and fall (P7 TV excess). The black is then that last monotone step."""
    if axis.get("black") is None:
        return axis
    dev = np.asarray(axis["dev"], float)
    ok = np.asarray(axis["ok"], bool).copy()
    run_max = np.maximum.accumulate(dev, axis=0)
    fell = (run_max - dev > tol).any(1)
    if not fell.any():
        return axis
    first = int(np.argmax(fell))
    good = np.flatnonzero(ok[:first])
    if not len(good):
        return axis
    last = int(good[-1])
    ok[last + 1:] = False
    lab = model.predict(dev[last][None, :])[0]
    return {"l": axis["l"], "dev": dev, "ok": ok, "l_black": float(lab[0]),
            "black": dev[last].copy(), "monotone_black": True}


def monotone_neutral_axis(model: ForwardModel, axis: dict, *,
                          step: float = 0.5, **inv_kw) -> dict:
    """Research agent9-01 6.2 ("a9-monok"): the neutral axis walked BACK
    from the neutral black to paper white with every channel capped at its
    value one step darker, so no ink rises and falls along the grey ramp
    (P7 "TV excess"). The black is the forward walk's (same depth); the
    caps force the K the black composition needs to enter early enough that
    C/M/Y never exceed their amount in the black. Same return keys as
    :func:`neutral_axis` (``l`` light to dark)."""
    if axis.get("black") is None:
        return axis
    n = model.n_channels
    l_nb = float(axis["l_black"])
    base_max = inv_kw.pop("channel_max", None)
    base_max = np.ones(n) if base_max is None else np.asarray(base_max, float)
    kw = {k: v for k, v in inv_kw.items()
          if k not in ("node_lab", "progress", "seed")}
    ls_up = np.arange(l_nb, 100.0 + 1e-9, step)
    cur = np.asarray(axis["black"], float)[None, :]
    devs, ress = [], []
    for lv in ls_up:
        cap = np.minimum(base_max, cur[0] + 1e-9)
        d, r = invert_to_device(model, np.array([[lv, 0.0, 0.0]]),
                                seed=np.minimum(cur, cap), channel_max=cap,
                                **kw)
        d = np.minimum(d, cap)
        devs.append(d[0]); ress.append(r[0]); cur = d
    devs, ress = np.array(devs), np.array(ress)
    # light to dark, on the forward walk's grid (targets above the black)
    ls = np.asarray(axis["l"])
    out_dev = np.array(axis["dev"], float).copy()
    out_ok = np.array(axis["ok"]).copy()
    for i, lv in enumerate(ls):
        if lv < l_nb - 1e-9:
            continue
        j = int(np.argmin(np.abs(ls_up - lv)))
        out_dev[i] = devs[j]
        lab = model.predict(devs[j][None, :])[0]
        out_ok[i] = ress[j] < 0.5 and np.hypot(lab[1], lab[2]) < 1.0
    return {"l": ls, "dev": out_dev, "ok": out_ok, "l_black": axis["l_black"],
            "black": axis["black"], "monotone": True}


def apply_neutral_axis(dev_clut: np.ndarray, node_lab: np.ndarray,
                       axis: dict, model: ForwardModel,
                       **inv_kw) -> np.ndarray:
    """Put the continuation solution on the B2A neutral column.

    Column nodes (C* < 1) at or above the neutral black take the walk's
    device value at their L*; column nodes darker than it take the neutral
    black itself, and near-neutral nodes (C* < 5) darker than it are
    re-inverted at the neutral black's L* with their own a*, b*: the dark
    end of the axis is clipped ALONG the axis instead of onto the nearest
    (often chromatic) vertex of the ink-limit face (research agent5-01 P3:
    X3 black L* 8.8 a* -12 -> 5.3 neutral). Returns the indices of the
    nodes it set (the refit anchors them). The caller keeps the residual
    measured against the original targets (gamt stays a distance).
    """
    if axis.get("black") is None:
        return np.array([], dtype=int)
    l_nb = axis["l_black"]
    chroma = np.hypot(node_lab[:, 1], node_lab[:, 2])
    col = np.flatnonzero(chroma < 1.0)
    set_idx = []
    for i in col:
        lt = node_lab[i, 0]
        if lt < l_nb:
            dev_clut[i] = axis["black"]
            set_idx.append(i)
            continue
        j = int(np.argmin(np.abs(axis["l"] - lt)))
        if abs(axis["l"][j] - lt) <= 0.26 and axis["ok"][j]:
            dev_clut[i] = axis["dev"][j]
            set_idx.append(i)
    below = np.flatnonzero((chroma >= 1.0) & (chroma < 5.0)
                           & (node_lab[:, 0] < l_nb))
    if len(below):
        tgt = node_lab[below].copy()
        tgt[:, 0] = l_nb
        kw = {k: v for k, v in inv_kw.items()
              if k not in ("node_lab", "progress", "seed")}
        dev_clut[below] = invert_to_device(model, tgt, **kw)[0]
    return np.array(set_idx, dtype=int)


def build_b2a_clut(model: ForwardModel, grid: int, *,
                   channel_letters: list[str], is_additive: bool,
                   ink_limit: float | None = None,
                   node_lab: np.ndarray | None = None,
                   k_prior: dict | None = None,
                   accurate: bool = False,
                   extra_hues: dict[str, float] | None = None,
                   black_l: float | None = None,
                   k_gen: dict | None = None,
                   ucs: bool = False,
                   channel_max: np.ndarray | None = None,
                   progress=None,
                   ) -> tuple[np.ndarray, np.ndarray]:
    """Full B2A CLUT: (grid³, n) device fractions + (grid³,) OOG distance.

    ``node_lab`` overrides the CLUT node targets (the XYZ-PCS grid of an
    ``-a x`` profile, expressed in Lab); default = the legacy Lab16 grid.
    """
    target = lab_grid(grid) if node_lab is None else node_lab
    return invert_to_device(model, target, channel_letters=channel_letters,
                            is_additive=is_additive, ink_limit=ink_limit,
                            k_prior=k_prior, accurate=accurate,
                            extra_hues=extra_hues, black_l=black_l,
                            k_gen=k_gen, ucs=ucs, channel_max=channel_max,
                            progress=progress)


def refine_b2a_clut(model: ForwardModel, dev_clut: np.ndarray,
                    residual: np.ndarray, grid: int, *,
                    ink_limit: float | None = None,
                    is_additive: bool = True,
                    channel_letters: list[str] | None = None,
                    samples: int = 30000, lam: float = 0.03,
                    deep_oog: float = 5.0,
                    node_lab: np.ndarray | None = None,
                    lab_to01=None,
                    k_prior: dict | None = None,
                    accurate: bool = False,
                    extra_hues: dict[str, float] | None = None,
                    black_l: float | None = None,
                    k_gen: dict | None = None,
                    ucs: bool = False,
                    channel_max: np.ndarray | None = None,
                    fixed_nodes: np.ndarray | None = None,
                    progress=None) -> np.ndarray:
    """Refit the B2A CLUT as one smooth field over exact inverse samples.

    ``fixed_nodes``: node indices whose value is already decided (the
    neutral column of :func:`apply_neutral_axis`); they get the heavy
    anchor weight, like the deep out-of-gamut clamps.

    Every random device point is an *exact* sample of the inverse function
    (its Lab comes from the forward model, its device value is known), so the
    whole B2A grid can be least-squares fitted to tens of thousands of them —
    trilinear interpolation between nodes is then accurate by construction,
    which removes the boundary-cell kink that per-node inversion leaves
    (measured: round-trip max 15 ΔE → the kink cells mix converged and
    clamped nodes). Nodes deep out of gamut keep their nearest-surface clamp
    values via strong anchors; near-boundary nodes get weak anchors so the
    fit may extrapolate smoothly across the gamut surface.
    """
    from workflow.profile_engine.forward_model import (_grid_solve,
                                                       _interp_weights)
    n = model.n_channels
    rng = np.random.default_rng(99)
    limit = None if ink_limit is None or is_additive else ink_limit / 100.0
    if n <= 3:
        # Bijective: any random device point is an exact inverse sample.
        dev_s = rng.uniform(0.0, 1.0, (samples, n))
        # Extra samples on the device-cube faces: the gamut boundary is their
        # image, and boundary cells are exactly where interpolation needs the
        # most support (measured: halves the worst-case round-trip error).
        nf = samples // 2
        faces = rng.uniform(0.0, 1.0, (nf, n))
        faces[np.arange(nf), rng.integers(0, n, nf)] = \
            rng.integers(0, 2, nf).astype(float)
        dev_s = np.vstack([dev_s, faces])
        if channel_max is not None:
            dev_s *= channel_max[None, :]
        if limit is not None:
            total = dev_s.sum(1)
            over = total > limit
            dev_s[over] *= (limit / total[over])[:, None]
        lab_s = model.predict(dev_s)
    else:
        # n > 3: many device values share one Lab — fitting raw random
        # samples would average competing separations and erase the ink
        # policy (measured: K ≈ 0.4 at L*=50 instead of the locus value).
        # Sample *reachable* Lab targets instead and invert them through the
        # same policy the per-node pass used; those pairs are consistent.
        probe_dev = rng.uniform(0.0, 1.0, (samples // 3, n))
        if accurate:
            # Uniform device points almost never print light: on a CMYK
            # Clapper-Yule printer 3 of 10,000 landed above L* 80, on six
            # inks none, so the highlight nodes were extrapolated from the
            # midtones and the L* 93.75 neutral printed L* 58-88 (research
            # agent5-03, item 1 cause A). Half the probes are scaled toward
            # paper (coverage s², s ~ U(0, 1)) so light Lab is sampled too.
            half = len(probe_dev) // 2
            probe_dev[:half] *= rng.uniform(0.0, 1.0, (half, 1)) ** 2
        if channel_max is not None:
            probe_dev *= channel_max[None, :]
        if limit is not None:
            total = probe_dev.sum(1)
            over = total > limit
            probe_dev[over] *= (limit / total[over])[:, None]
        lab_targets = model.predict(probe_dev)
        dev_s, res_s = invert_to_device(
            model, lab_targets, channel_letters=channel_letters or [],
            is_additive=is_additive, ink_limit=ink_limit, k_prior=k_prior,
            accurate=accurate, extra_hues=extra_hues, black_l=black_l,
            k_gen=k_gen, ucs=ucs, channel_max=channel_max, progress=progress,
            progress_label="Inverting the model: sampling the separation")
        keep = res_s < 1.0
        dev_s, lab_s = dev_s[keep], lab_targets[keep]

    if lab_to01 is None:
        ls, ab = lab_grid_axes(grid)
        span = np.array([ls[-1] - ls[0], ab[-1] - ab[0], ab[-1] - ab[0]])
        origin = np.array([ls[0], ab[0], ab[0]])

        def to01(lab: np.ndarray) -> np.ndarray:
            return np.clip((lab - origin[None, :]) / span[None, :], 0.0, 1.0)
    else:
        to01 = lab_to01

    # Anchor rows: every node contributes its v1 value — heavy anchors deep
    # out of gamut (their clamp IS the answer there), light anchors elsewhere
    # (keep the fit stable where samples are sparse, let data win).
    anchor_w = np.where(residual > deep_oog, 4.0, 0.05)
    if fixed_nodes is not None and len(fixed_nodes):
        anchor_w[fixed_nodes] = 4.0
    if node_lab is None:
        node_lab = lab_grid(grid)
    # Fit in *curve space* — the CLUT stores shaped device values (the output
    # shaper tables undo them), so interpolation accuracy must be optimised
    # in the space the CMM actually interpolates in.
    p_all = np.vstack([to01(lab_s), to01(node_lab)])
    y_all = np.vstack([model.shape_device(dev_s),
                       model.shape_device(dev_clut)])
    w_all = np.concatenate([np.ones(len(dev_s)), anchor_w])

    x0 = model.shape_device(dev_clut)
    refined = x0
    probe_dev = rng.uniform(0.0, 1.0, (4000, n)) if n <= 3 else None
    rounds_total = 3 if n <= 3 else 1
    for round_ in range(rounds_total):
        if progress is not None:
            progress(f"Inverting the model: smoothing refit "
                     f"{round_ + 1}/{rounds_total}…")
        w, cols = _interp_weights(p_all, grid, 3)
        sw = np.sqrt(w_all)[:, None]
        refined = np.clip(_grid_solve(w * sw, cols, y_all * sw, grid, 3, lam,
                                      400, x0=refined), 0.0, 1.0)
        if probe_dev is None or round_ == 2:
            break
        # Adaptive densification: score in-gamut probes through the refined
        # grid, then support the worst regions with fresh exact samples
        # (measured: cuts the worst-case round-trip error by ~40%).
        probe_lab = model.predict(probe_dev)
        wp, cp = _interp_weights(to01(probe_lab), grid, 3)
        landed = model.predict(np.clip(
            model.unshape_device((wp[:, :, None] * refined[cp]).sum(1)),
            0.0, 1.0))
        err = np.linalg.norm(landed - probe_lab, axis=1)
        worst = np.argsort(err)[-200:]
        extra = np.clip(np.repeat(probe_dev[worst], 40, axis=0)
                        + rng.normal(0.0, 0.06, (200 * 40, n)), 0.0, 1.0)
        p_all = np.vstack([p_all, to01(model.predict(extra))])
        y_all = np.vstack([y_all, model.shape_device(extra)])
        w_all = np.concatenate([w_all, np.ones(len(extra))])
    if limit is not None:
        raw = model.unshape_device(refined)
        total = raw.sum(1)
        over = total > limit
        if accurate:
            raw = project_tac(raw, limit)
        else:
            raw[over] *= (limit / total[over])[:, None]
        refined[over] = model.shape_device(raw[over])
    return refined


def pin_white_node(dev_clut: np.ndarray, node_lab: np.ndarray,
                   is_additive: bool, tol: float = 1.0) -> np.ndarray:
    """Force the B2A node(s) that stand for the PCS white to DEVICE white.

    The colorimetric table is refitted as one smooth field
    (:func:`refine_b2a_clut`) and the mapped tables come from a per-node
    inversion of a mapped target; both leave the white corner a fitted
    value — measured 2026-09-04 on a synthetic CMYK chart: C 0.6 %, M 1.3 %,
    Y 3.5 % at L*=100 (ink in the paper white), with the forward model's
    white already pinned. Argyll's ICX_SET_WHITE makes the white exact on
    both sides; this is the B2A half. Works in device space and in the
    curve (shaped) space alike, because the shaper curves are pinned at 0
    and 1. Only nodes within ``tol`` ΔE76 of (100, 0, 0) qualify — the top
    row's a=b≈0 node, never its coloured neighbours."""
    d = np.linalg.norm(node_lab - np.array([100.0, 0.0, 0.0]), axis=1)
    hit = d <= tol
    if not hit.any():
        return dev_clut
    out = dev_clut.copy()
    out[hit] = 1.0 if is_additive else 0.0
    return out


def pin_black_node(dev_clut: np.ndarray, node_lab: np.ndarray,
                   device_black: np.ndarray, tol: float = 1.0) -> np.ndarray:
    """Force the B2A node(s) that stand for L*=0 to the printer's DEEPEST
    black. The Lab grid's black corner lies only ~3 ΔE76 outside a real
    printer's gamut, so the smooth refit treated it as a weak anchor and
    extrapolated — measured 2026-09-05 on a real chart: L*=0 printed as
    RGB 3/4/18 (fast, a blue cast, L* 6.2) and 3/0/4 (accurate, magenta)
    while colprof gives 0/0/0. Every "pure black" pixel carries L*=0.
    ``device_black`` is given in the same space as ``dev_clut`` (device or
    curve space) — the caller shapes it."""
    d = np.linalg.norm(node_lab, axis=1)
    hit = d <= tol
    if not hit.any():
        return dev_clut
    out = dev_clut.copy()
    out[hit] = np.asarray(device_black, float)[None, :]
    return out


def below_black_column(node_lab: np.ndarray, black_l: float,
                       chroma_tol: float = 1.0) -> np.ndarray:
    """Indices of the B2A neutral-column nodes (C* < ``chroma_tol``) whose
    target L* lies below ``black_l``, the L* of the device black.

    Research F-13 (agent20-01): on an RGB printer whose black is well above
    L* 0 these nodes are only a few dE76 outside the gamut, so the smoothing
    refit (:func:`refine_b2a_clut`) gave them the weak anchor and set them
    from their heavy-anchored chromatic neighbours: lighter than the black
    and lighter than the next node up (X1: sRGB grey 7.86 -> 10.99 -> 9.90
    L* through lcms and ColorSync). colprof clips each node on its own
    (nearest, LCh-weighted, xicc/xlut.c), so its column is flat at the
    black until the ramp enters the gamut; this is the same answer."""
    chroma = np.hypot(node_lab[:, 1], node_lab[:, 2])
    return np.flatnonzero((chroma < chroma_tol)
                          & (node_lab[:, 0] < float(black_l)))


def rgb_neutral_black(model: ForwardModel, black_l: float, *,
                      ucs: bool = False, step: float = 0.05,
                      span: float = 15.0, tol: float = 0.5
                      ) -> tuple[float, np.ndarray]:
    """The NEUTRAL black of an RGB device: the darkest L* (from the device
    black's L* upward, ``step`` apart) whose neutral target (L*, 0, 0) the
    model reaches within ``tol`` dE76, and its device value. Returns the
    device black (``black_l``, RGB 0) when RGB 0 is itself neutral (model
    C* < 1, the test :func:`neutral_axis` uses) or
    no neutral is reached within ``span`` L*.

    Research F-13 (agent20-01 s5.2, s6.2): the B2A neutral column is held
    below this point (design A3). Design A2 clipped the column TO it, as
    Agent 5's :func:`apply_neutral_axis` does for ink devices, which kept
    the grey axis neutral above a chromatic black (battery S2: C* 3.0) but
    cost dark-colour accuracy."""
    n = model.n_channels
    zero = np.zeros((1, n))
    lab0 = model.predict(zero)[0]
    if np.hypot(lab0[1], lab0[2]) < 1.0:
        # RGB 0 is already neutral (C* < 1, Agent 5's neutrality test)
        return float(black_l), zero[0]
    ls = np.arange(float(black_l), float(black_l) + span + 1e-9, step)
    tgt = np.column_stack([ls, np.zeros_like(ls), np.zeros_like(ls)])
    dev, res = invert_to_device(model, tgt, channel_letters=[],
                                is_additive=True, accurate=True, ucs=ucs)
    ok = np.flatnonzero(res < tol)
    if not len(ok):
        return float(black_l), zero[0]
    i = int(ok[0])
    return float(ls[i]), np.clip(dev[i], 0.0, 1.0)


def monotone_column(model: ForwardModel, values: np.ndarray,
                    target_l: np.ndarray) -> np.ndarray:
    """Column device values made monotone in the model's L*: walking from
    the lightest target down, a node whose value would print lighter than
    the node above it takes that node's value. Research F-13 (design A3):
    the per-node nearest clips below the black are monotone on every
    printer measured, this makes it a guarantee."""
    values = np.asarray(values, float).copy()
    if not len(values):
        return values
    order = np.argsort(-np.asarray(target_l, float))       # light to dark
    vals = values[order]
    lp = model.predict(vals)[:, 0]
    for i in range(1, len(vals)):
        if lp[i] > lp[i - 1]:
            vals[i], lp[i] = vals[i - 1], lp[i - 1]
    out = np.empty_like(vals)
    out[order] = vals
    return out


def pin_nodes(dev_clut: np.ndarray, nodes: np.ndarray,
              value: np.ndarray) -> np.ndarray:
    """Set ``nodes`` of a CLUT to one device value (same space as the
    table). The column generalisation of :func:`pin_black_node`."""
    if nodes is None or not len(nodes):
        return dev_clut
    out = dev_clut.copy()
    value = np.asarray(value, float)
    out[np.asarray(nodes, int)] = value if value.ndim == 2 else value[None, :]
    return out


_CLOUD_CACHE: dict = {}
_CLOUD_LOCK = __import__("threading").Lock()


def _cloud_and_lab(view, model: ForwardModel, n: int, limit: float | None,
                   channel_max: np.ndarray | None, seed: int,
                   memo: bool = True, light: bool | None = None):
    """The retry / hue-clip device cloud and its predicted colours.

    Every call rebuilt both from a fresh ``default_rng(seed)``: the same
    numbers each time for the same model, and the prediction is the
    expensive part (the neutral-axis walk asks for it once per step). D-06:
    remembered per model CONTENT (nodes and curves hashed, so an in-place
    change of the model can never hit a stale entry) and per limits; the
    arrays returned are the ones a fresh computation gives, bit for bit."""
    if not memo:                     # Fast / Bit-exact: the serial path
        cloud = _device_cloud(n, limit, channel_max,
                              np.random.default_rng(seed))
        return cloud, view.predict(cloud)
    import hashlib
    h = hashlib.blake2b(digest_size=16)
    h.update(np.ascontiguousarray(model.nodes).tobytes())
    h.update(np.ascontiguousarray(model.curves).tobytes())
    use_light = bool(LIGHT_CLOUD.get("on")) if light is None else bool(light)
    key = (h.hexdigest(), type(view).__name__, n, limit, use_light,
           None if channel_max is None else tuple(np.asarray(channel_max,
                                                             float)), seed)
    with _CLOUD_LOCK:
        hit = _CLOUD_CACHE.get(key)
    if hit is not None:
        return hit
    cloud = _device_cloud(n, limit, channel_max, np.random.default_rng(seed))
    if use_light:
        cloud = np.vstack([cloud, _light_cloud(
            n, limit, channel_max, np.random.default_rng(seed + 7))])
    val = (cloud, view.predict(cloud))
    for a in val:                    # shared: nobody may write into them
        a.flags.writeable = False
    with _CLOUD_LOCK:
        while len(_CLOUD_CACHE) >= 4:
            _CLOUD_CACHE.pop(next(iter(_CLOUD_CACHE)))
        _CLOUD_CACHE[key] = val
    return val


# Agent 21 (Findings/agent21-01 s3.1, token "a21-lightcloud", Maximum
# accuracy; ported by Agent 25 from research/pe-nink-research c6b75dea /
# 9ed806ab): the retry and clip clouds are uniform in the N-cube, which on
# 5-7 inks under a 300 % limit holds no light colour at all, so pale nodes
# were seeded from dark colours (F-14). Light and sparse points are added.
LIGHT_CLOUD: dict = {"on": False, "l_min": None}
CLIP_FIX: dict = {"on": False}      # agent 21 / F-15, token "a21-clipfix"


def additive_column_nodes(node_lab: np.ndarray, residual: np.ndarray) -> np.ndarray:
    """Research (Agent 25, token a25-rgbcol): the in-gamut nodes of the B2A
    neutral column of a 3-channel device. Ink devices anchor their column
    through apply_neutral_axis; an RGB table had no anchor at all, so the
    smoothing refit could move a light neutral node by 3 L* (battery S2:
    node L* 96.9 printed 100) and an out-of-gamut neighbour's clip value
    could tint it (S2 with a25-oog: b* -0.5)."""
    chroma = np.hypot(node_lab[:, 1], node_lab[:, 2])
    return np.flatnonzero((chroma < 1.0) & (residual < 0.5))


def set_research_tokens(tokens, *, is_additive) -> None:
    """Module switches for one build (research tokens a21-*, a25-*).
    Called by the builder before the first inversion and with an empty set
    afterwards; Fast and Bit-exact never reach the code they switch."""
    from workflow.profile_engine import oog_clip
    t = frozenset(tokens or ())
    LIGHT_CLOUD["on"] = bool(("a21-lightcloud" in t and is_additive is False)
                             or "a21-lightcloud-all" in t)
    # a25-oog carries Agent 21's L* >= 60 variant (a21-lightcloud60): the
    # plain light cloud also moved the retry seeds of DARK near-neutral
    # nodes (battery XKB pessimistic L* 12.5 reversal 0 -> 1, d2 0.47 -> 2.09)
    LIGHT_CLOUD["l_min"] = (60.0 if ("a21-lightcloud60" in t or "a25-oog" in t)
                            and is_additive is False else None)
    CLIP_FIX["on"] = "a21-clipfix" in t
    p = oog_clip.PARAMS
    p.clear()
    p.update(oog_clip.DEFAULTS)
    p["on"] = "a25-oog" in t or "a25-clip" in t
    # Agent 29b: monotone clip into black (acts only with the a25 clip on and
    # a floor set by the builder for the colorimetric table)
    p["dm_on"] = any(x.startswith("a29-oog-darkmono") for x in t)
    if "a29-oog-darkmono-bpc" in t:
        p["dm_band"] = 15.0
    if "a29-oog-darkmono-soft" in t:
        # ablation after the A/B (Findings agent29b-01 s5): a gentler
        # lightness-first band (the x25 band made dark-blue contours)
        p["dm_wj"], p["dm_lband"] = 6.0, 20.0
    if "a29-oog-darkmono-floor" in t and not t & {
            "a29-oog-darkmono", "a29-oog-darkmono-soft",
            "a29-oog-darkmono-bpc"}:
        # the floor alone (Agent 29b ablation; default ON since integration
        # 4). An explicitly requested other variant wins over the default,
        # so each one still builds exactly as on its own branch.
        p["dm_wj"] = 1.0
    oog_clip.set_dark_floor(None)       # the builder sets it per table
    for tok in t:
        if tok.startswith("a25-space-"):
            p["space"] = tok[len("a25-space-"):]
        elif tok.startswith("a25-p-") and "=" in tok:
            k, v = tok[len("a25-p-"):].split("=", 1)
            p[k] = type(oog_clip.DEFAULTS[k])(v) if not isinstance(
                oog_clip.DEFAULTS[k], bool) else v in ("1", "true", "on")


def _light_cloud(n: int, limit, channel_max, rng: np.random.Generator) -> np.ndarray:
    m = min(40000, 6000 * n)
    a = rng.uniform(0.0, 1.0, (m // 2, n)) * rng.uniform(0.0, 1.0, (m // 2, 1)) ** 2
    sp = np.zeros((m // 2, n))
    for k in (1, 2, 3):
        rows = np.arange(k - 1, m // 2, 3)
        for i in rows:
            sp[i, rng.choice(n, k, replace=False)] = 1.0
    sp *= rng.uniform(0.0, 1.0, sp.shape) ** 2
    c = np.vstack([a, sp])
    if channel_max is not None:
        c *= channel_max[None, :]
    if limit is not None:
        total = c.sum(1)
        over = total > limit
        c[over] *= (limit / total[over])[:, None]
    return c


def _device_cloud(n: int, limit: float | None,
                  channel_max: np.ndarray | None,
                  rng: np.random.Generator) -> np.ndarray:
    cloud = rng.uniform(0.0, 1.0, (min(40000, 6000 * n), n))
    if channel_max is not None:
        cloud *= channel_max[None, :]
    if limit is not None:
        total = cloud.sum(1)
        over = total > limit
        cloud[over] *= (limit / total[over])[:, None]
    return cloud


def _hue_gated_seeds(target: np.ndarray, cloud: np.ndarray,
                     cloud_lab: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For out-of-gamut targets: the printable colour of the SAME HUE that
    loses chroma rather than lightness. Returns ``(seeds, found)``.

    A first-order hue metric (the previous clip) cannot tell a colour from
    its complement — both lie on one line through the neutral axis, so the
    "hue error" of the opposite hue is zero — and the solver walked round
    the hue circle for far-out targets (measured: 5.7 % of out-of-gamut
    nodes printed the complementary hue in accurate mode; colprof 0 %).
    Gating candidates by hue ANGLE first makes the flip impossible."""
    n_t = len(target)
    out = np.zeros((n_t, cloud.shape[1]))
    found = np.zeros(n_t, bool)
    c_l, c_c = cloud_lab[:, 0], np.hypot(cloud_lab[:, 1], cloud_lab[:, 2])
    c_h = np.degrees(np.arctan2(cloud_lab[:, 2], cloud_lab[:, 1]))
    t_l, t_c = target[:, 0], np.hypot(target[:, 1], target[:, 2])
    t_h = np.degrees(np.arctan2(target[:, 2], target[:, 1]))
    # D-06: every row is scored and chosen on its own (element-wise maths,
    # argmin along the cloud), so 256-row blocks run on pool threads with
    # the same bits. Only the Maximum accuracy path calls this.
    from workflow.profile_engine import parallel
    blocks = list(range(0, n_t, 256))
    groups = parallel.chunk_bounds(len(blocks), parallel.worker_count(),
                                   min_rows=4)
    parallel.run_chunks(
        lambda a, b: _hue_gated_block(blocks[a:b], out, found, cloud,
                                      c_l, c_c, c_h, t_l, t_c, t_h),
        groups)
    return out, found


def _hue_gated_block(starts, out, found, cloud, c_l, c_c, c_h, t_l, t_c,
                     t_h) -> None:
    for lo in starts:
        sl = slice(lo, lo + 256)
        dh = np.abs((c_h[None, :] - t_h[sl, None] + 180.0) % 360.0 - 180.0)
        # Lightness is worth keeping more than chroma: score = (2·ΔL)² + ΔC²
        score = (4.0 * (c_l[None, :] - t_l[sl, None]) ** 2
                 + (c_c[None, :] - t_c[sl, None]) ** 2)
        chosen = np.full(dh.shape[0], -1)
        for gate in (6.0, 12.0, 25.0):
            ok = dh <= gate
            need = chosen < 0
            if not need.any():
                break
            masked = np.where(ok, score, np.inf)
            best = np.argmin(masked, 1)
            have = np.isfinite(masked[np.arange(len(best)), best]) & need
            chosen[have] = best[have]
        got = chosen >= 0
        idx = np.flatnonzero(got) + lo
        out[idx] = cloud[chosen[got]]
        found[idx] = True


def inverse_curves(curves: np.ndarray, knots: int = 256) -> np.ndarray:
    """Per-channel inverse of monotone 0..1 shaper curves (for B2A out tables).

    Storing *curve-space* device values in the B2A CLUT and undoing them in
    the output shaper tables linearises the CLUT contents — the same device
    non-linearity the A2B input curves absorb would otherwise sit as
    curvature inside the B2A grid cells and show up as interpolation error
    (measured: the high-chroma boundary-cell tail).
    """
    n, k = curves.shape
    xs = np.linspace(0.0, 1.0, knots)
    xp = np.linspace(0.0, 1.0, k)
    out = np.empty((n, knots))
    for c in range(n):
        out[c] = np.interp(xs, curves[c], xp)   # swap axes = inverse
    return out
