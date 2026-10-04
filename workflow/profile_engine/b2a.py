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
    if k_prior is not None and k_prior.get("neutral_only"):
        # Research agent9-01 6.2 ("a9-monok"): a K curve that applies to
        # the NEUTRALS only (blended in with the accurate neutral weight
        # below); chromatic colours keep the engine's own locus.
        neutral_k = np.interp(target[:, 0], k_prior["l_axis"],
                              k_prior["k_curve"])
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
    return prior, prior_w


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

    if accurate:
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
                d_pol[~keep] = seeds_h[found][~keep]
                d[sub_idx] = d_pol
    return d, residual


def neutral_axis(model: ForwardModel, *, step: float = 0.5,
                 **inv_kw) -> dict:
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
    return {"l": ls, "dev": dev, "ok": ok, "l_black": float(lab[last, 0]),
            "black": dev[last].copy()}


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


_CLOUD_CACHE: dict = {}
_CLOUD_LOCK = __import__("threading").Lock()


def _cloud_and_lab(view, model: ForwardModel, n: int, limit: float | None,
                   channel_max: np.ndarray | None, seed: int,
                   memo: bool = True):
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
    key = (h.hexdigest(), type(view).__name__, n, limit,
           None if channel_max is None else tuple(np.asarray(channel_max,
                                                             float)), seed)
    with _CLOUD_LOCK:
        hit = _CLOUD_CACHE.get(key)
    if hit is not None:
        return hit
    cloud = _device_cloud(n, limit, channel_max, np.random.default_rng(seed))
    val = (cloud, view.predict(cloud))
    for a in val:                    # shared: nobody may write into them
        a.flags.writeable = False
    with _CLOUD_LOCK:
        while len(_CLOUD_CACHE) >= 4:
            _CLOUD_CACHE.pop(next(iter(_CLOUD_CACHE)))
        _CLOUD_CACHE[key] = val
    return val


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
