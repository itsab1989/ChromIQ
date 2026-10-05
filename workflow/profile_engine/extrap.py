"""Research candidate ``a19-extrap`` (agent 19, F-12): physically plausible
continuation of the stiff forward fit into the device region the chart does
not support.

The lattice fit's curvature penalty (per-axis second differences) fills a
node no patch constrains with the MULTILINEAR continuation, in Lab, of the
nodes around it. Subtractive colour is multiplicative in reflectance, so the
Lab continuation of two dark inks passes L* 0 (F-12: unsampled two- and
three-ink solids of a 7-ink printer predicted L* 0 with a wrong hue). Here
the fit is kept where the data support it and continued beyond in a density
space (-log10 of the media-relative XYZ), where adding ink is close to
additive (Beer-Lambert) and Y can never reach 0; then blended back smoothly.
Nothing changes where no lattice node lies beyond the data (then the model
is returned untouched, so the profile is byte-identical).
"""
from __future__ import annotations

import numpy as np

from workflow.profile_engine.ti3_data import D50_XYZ100, lab_to_xyz, xyz_to_lab

_FLOOR = 1e-4


class DensitySpace:
    """Lab <-> per-channel density D = -log10(XYZ / D50 white).

    Same interface as ucs.PrintUCS (lab_to_ucs / ucs_to_lab), so the
    accurate fit can run in it for ablations."""

    def lab_to_ucs(self, lab: np.ndarray) -> np.ndarray:
        r = lab_to_xyz(np.asarray(lab, float)) / D50_XYZ100
        return -np.log10(np.clip(r, _FLOOR, None))

    def ucs_to_lab(self, d: np.ndarray) -> np.ndarray:
        return xyz_to_lab(D50_XYZ100 * 10.0 ** (-np.asarray(d, float)))


def grid_coords(grid: int, n: int) -> np.ndarray:
    ax = np.linspace(0.0, 1.0, grid)
    return np.stack(np.meshgrid(*([ax] * n), indexing="ij"), -1).reshape(-1, n)


def beyond_data(nodes01: np.ndarray, shaped: np.ndarray,
                chunk: int = 2048) -> np.ndarray:
    """t(x) = max(0, min_p max_i (x_i - p_i)): how far a node lies beyond the
    nearest patch that carries at least as much of every ink (the chart's
    monotone hull), in the same 0..1 shaped units. Paper is at 0, so the
    light side is always inside."""
    # only patches not dominated by another patch can be the minimiser
    p = np.asarray(shaped, float)
    order = np.argsort(-p.sum(1))
    keep = []
    for i in order:
        if not keep or not np.any(np.all(p[keep] >= p[i] - 1e-12, axis=1)):
            keep.append(i)
    p = p[keep]
    out = np.empty(len(nodes01))
    for lo in range(0, len(nodes01), chunk):
        x = nodes01[lo:lo + chunk]
        e = (x[:, None, :] - p[None, :, :]).max(2).min(1)
        out[lo:lo + chunk] = np.maximum(e, 0.0)
    return out


def _curvature(x: np.ndarray, grid: int, n: int) -> np.ndarray:
    """Sum over axes of D2^T D2 x (the same operator as forward_model)."""
    shape = (grid,) * n + (-1,)
    x3 = x.reshape(shape)
    o = np.zeros_like(x3)
    mid = [slice(None)] * (n + 1)
    lo = [slice(None)] * (n + 1)
    hi = [slice(None)] * (n + 1)
    for ax in range(n):
        mid[ax] = slice(1, -1)
        lo[ax] = slice(0, -2)
        hi[ax] = slice(2, None)
        d2 = x3[tuple(lo)] - 2 * x3[tuple(mid)] + x3[tuple(hi)]
        o[tuple(lo)] += d2
        o[tuple(mid)] -= 2 * d2
        o[tuple(hi)] += d2
        mid[ax] = lo[ax] = hi[ax] = slice(None)
    return o.reshape(len(x), -1)


def continue_in_density(d: np.ndarray, free: np.ndarray, grid: int, n: int,
                        iters: int = 2000) -> np.ndarray:
    """Smoothest (min sum of squared per-axis second differences)
    continuation of ``d`` onto the ``free`` nodes, the others held fixed."""
    x = d.copy()
    f = free

    def amul(v):
        full = np.zeros_like(x)
        full[f] = v
        return _curvature(full, grid, n)[f] + 1e-9 * v

    rhs_full = np.zeros_like(x)
    rhs_full[~f] = x[~f]
    b = -_curvature(rhs_full, grid, n)[f]
    v = x[f].copy()
    r = b - amul(v)
    pdir = r.copy()
    rs = float((r * r).sum())
    stop = max(1e-20, 1e-14 * float((b * b).sum()))
    for _ in range(iters):
        ap = amul(pdir)
        alpha = rs / max(float((pdir * ap).sum()), 1e-30)
        v += alpha * pdir
        r -= alpha * ap
        rs2 = float((r * r).sum())
        if rs2 < stop:
            break
        pdir = r + (rs2 / rs) * pdir
        rs = rs2
    x[f] = v
    return x


def _monotone(d: np.ndarray, free: np.ndarray, grid: int, n: int) -> np.ndarray:
    """Density never decreases with more of any ink (running max along every
    axis), applied to the continued nodes only."""
    m = d.reshape((grid,) * n + (-1,))
    for ax in range(n):
        m = np.maximum.accumulate(m, axis=ax)
    m = m.reshape(d.shape)
    out = d.copy()
    out[free] = m[free]
    return out


def _soft_cap(d: np.ndarray, d_max: np.ndarray, span: float) -> np.ndarray:
    over = d - d_max[None, :]
    capped = d_max[None, :] + span * np.tanh(np.maximum(over, 0.0) / span)
    return np.where(over > 0.0, capped, d)


def repair(model, device: np.ndarray, lab: np.ndarray, *, start: float = 0.5,
           ramp: float = 1.5, cap_span: float = 0.5, monotone: bool = True,
           info: dict | None = None):
    """Return ``model`` with its unsupported nodes continued in density.

    ``start`` / ``ramp``: the blend weight rises from 0 at ``start`` lattice
    cells beyond the data to 1 at ``start + ramp``. ``cap_span``: the
    continued density may exceed the darkest measured patch's by at most
    about this much (log10 units, soft)."""
    grid, n = model.grid, model.n_channels
    cells = grid - 1
    shaped = model.shape_device(np.asarray(device, float))
    t = beyond_data(grid_coords(grid, n), shaped) * cells
    free = t > 1e-9
    w = np.clip((t - start) / max(ramp, 1e-9), 0.0, 1.0)
    w = w * w * (3.0 - 2.0 * w)
    if info is not None:
        info.update(nodes=int(len(t)), beyond=int(free.sum()),
                    blended=int((w > 0).sum()), t_max=float(t.max()))
    if not (w > 0).any():
        return model
    space = DensitySpace()
    d = space.lab_to_ucs(model.nodes)
    d = continue_in_density(d, free, grid, n)
    if monotone:
        d = _monotone(d, free, grid, n)
    if cap_span > 0:
        d_meas = space.lab_to_ucs(lab)
        d = _soft_cap(d, d_meas.max(0), cap_span)
    cont = space.ucs_to_lab(d)
    model.nodes = model.nodes * (1.0 - w)[:, None] + cont * w[:, None]
    return model


def influence(model, device: np.ndarray, lam: float, mu: float,
              iters: int = 400) -> np.ndarray:
    """Data-influence field s (about 1 where patches pin the lattice, falling
    towards 0 away from them): the fit's own normal equations solved for the
    target 1 at every patch with an extra ridge ``mu`` pulling to 0. The
    curvature term carries support across gaps BETWEEN patches (both sides
    pull up) but not beyond them, so s marks the chart's hull, not only the
    cells that hold a patch."""
    from workflow.profile_engine.forward_model import _interp_weights
    grid, n = model.grid, model.n_channels
    ng = grid ** n
    w, cols = _interp_weights(model.shape_device(np.asarray(device, float)),
                              grid, n)
    fc = cols.reshape(-1)

    def wtw(x):
        r = (w * x[cols]).sum(1)
        return np.bincount(fc, (w * r[:, None]).reshape(-1), minlength=ng)

    def amul(x):
        return wtw(x) + lam * _curvature(x[:, None], grid, n)[:, 0] + mu * x

    b = np.bincount(fc, w.reshape(-1), minlength=ng)
    x = np.zeros(ng)
    r = b - amul(x)
    p = r.copy()
    rs = float(r @ r)
    stop = 1e-12 * rs
    for _ in range(iters):
        ap = amul(p)
        a = rs / max(float(p @ ap), 1e-30)
        x += a * p
        r -= a * ap
        rs2 = float(r @ r)
        if rs2 < stop:
            break
        p = r + (rs2 / rs) * p
        rs = rs2
    return x


class YuleNielsenSpace:
    """Lab <-> (XYZ / D50 white) ** (1/n), sign-preserving (n = 1: linear
    reflectance, the Neugebauer / Murray-Davies space; n -> inf: density)."""

    def __init__(self, n: float):
        self.n = float(n)

    def lab_to_ucs(self, lab):
        r = lab_to_xyz(np.asarray(lab, float)) / D50_XYZ100
        return np.sign(r) * np.abs(r) ** (1.0 / self.n)

    def ucs_to_lab(self, u):
        u = np.asarray(u, float)
        return xyz_to_lab(D50_XYZ100 * np.sign(u) * np.abs(u) ** self.n)


def axis_ratios(nodes_xyz: np.ndarray, grid: int, n: int) -> np.ndarray:
    """(n, grid-1, 3): per ink, per lattice step along that ink's own axis
    from paper, the factor each XYZ channel keeps (<= 1): how much one step
    of that ink darkens bare paper, read from the fitted single-ink ramp."""
    x = nodes_xyz.reshape((grid,) * n + (3,))
    out = np.ones((n, grid - 1, 3))
    for i in range(n):
        idx = [0] * n
        ramp = []
        for k in range(grid):
            idx[i] = k
            ramp.append(x[tuple(idx)])
        ramp = np.maximum(np.array(ramp), 1e-6)
        out[i] = np.clip(ramp[1:] / ramp[:-1], 1e-6, 1.0)
    return out


def saturation_clamp(nodes_lab: np.ndarray, grid: int, n: int, *,
                     sigma: float = 1.5,
                     info: dict | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Physical lower bound on every node (ink devices).

    Halftone ink printed on any base removes at most the share of light it
    removes from bare paper (Murray-Davies on a base: Y' = Y (1 - a (1 - T));
    trapping and ink-on-ink spread only make it less), so one lattice step of
    ink i keeps at least rho_i(k)**sigma of each XYZ channel of the node it
    starts from, rho read from the fitted ramp of ink i on paper and
    ``sigma`` > 1 a safety margin. Nodes are swept in order of total ink
    (a node's bound uses its already bounded predecessors). Returns the
    bounded Lab nodes and a mask of the nodes that moved."""
    xyz = lab_to_xyz(np.asarray(nodes_lab, float)) / D50_XYZ100
    rho = axis_ratios(xyz, grid, n) ** sigma
    x = xyz.reshape((grid,) * n + (3,)).copy()
    idx = np.stack(np.meshgrid(*([np.arange(grid)] * n), indexing="ij"),
                   -1).reshape(-1, n)
    level = idx.sum(1)
    flat = x.reshape(-1, 3)
    strides = np.array([grid ** (n - 1 - d) for d in range(n)])
    moved = np.zeros(len(flat), bool)
    for s in range(1, int(level.max()) + 1):
        sel = np.flatnonzero(level == s)
        lb = np.zeros((len(sel), 3))
        for i in range(n):
            has = idx[sel, i] > 0
            if not has.any():
                continue
            rows = sel[has]
            parent = rows - strides[i]
            b = rho[i, idx[rows, i] - 1] * flat[parent]
            lb[has] = np.maximum(lb[has], b)
        low = flat[sel] < lb - 1e-12
        if low.any():
            m = low.any(1)
            moved[sel[m]] = True
            flat[sel] = np.maximum(flat[sel], lb)
    out = np.array(nodes_lab, float, copy=True)
    out[moved] = xyz_to_lab(flat[moved] * D50_XYZ100)
    if info is not None:
        info.update(clamped=int(moved.sum()), nodes=int(len(flat)))
    return out, moved


def monotone_lower_bounds(dev_axes: list, patch_dev: np.ndarray,
                          patch_xyz: np.ndarray, *, tol: float = 1e-6,
                          chunk_axes: int = 2) -> np.ndarray:
    """LB[c] at every lattice node: the largest XYZ_c of any patch that
    carries at least as much of EVERY ink as the node (-inf where none does).

    Absorbing inks only take light away, at every wavelength, so a node
    cannot be darker in any XYZ channel than a measured patch that has all
    of its ink and more. ``dev_axes``: per ink, the device value of each
    lattice index (the lattice is a product grid in device space too)."""
    n = len(dev_axes)
    grid = [len(a) for a in dev_axes]
    masks = [patch_dev[None, :, i] >= np.asarray(dev_axes[i])[:, None] - tol
             for i in range(n)]                      # (grid_i, P)
    xyz = patch_xyz.astype(np.float64)
    out = np.full(tuple(grid) + (3,), -np.inf)
    head = int(np.prod(grid[:chunk_axes]))
    tail_shape = tuple(grid[chunk_axes:])
    # tail masks: (prod tail, P), built once
    tail = np.ones((1, patch_dev.shape[0]), bool)
    for i in range(chunk_axes, n):
        tail = (tail[:, None, :] & masks[i][None, :, :]).reshape(-1, patch_dev.shape[0])
    for h in range(head):
        idx = np.unravel_index(h, tuple(grid[:chunk_axes]))
        m = np.ones(patch_dev.shape[0], bool)
        for d, k in enumerate(idx):
            m &= masks[d][k]
        if not m.any():
            continue
        sub = tail[:, m]                              # (T, P')
        x = xyz[m]
        any_ = sub.any(1)
        for c in range(3):
            v = np.where(sub, x[None, :, c], -np.inf).max(1)
            out[idx + (Ellipsis, c)] = v.reshape(tail_shape)
        del any_
    return out.reshape(-1, 3)


def monotone_envelope(patch_dev: np.ndarray, patch_xyz: np.ndarray
                      ) -> np.ndarray:
    """Per patch and channel: the minimum over itself and every patch that
    carries no more of any ink."""
    out = patch_xyz.copy()
    for k in range(len(patch_dev)):
        le = np.all(patch_dev <= patch_dev[k] + 1e-6, axis=1)
        out[k] = patch_xyz[le].min(0)
    return out


def lightening_patches(patch_dev: np.ndarray, patch_xyz: np.ndarray,
                       dl: float = 2.0) -> np.ndarray:
    """Patches LIGHTER, by more than ``dl`` L*, than some patch carrying no
    more of any ink: bronzing, gloss, a saturated press, a misread. They are
    not used as bounds. (A relative-Y rule of 5 % flagged 325 of APTEC's
    2972 patches, among them the very 600 % patch that bounds its 500 %
    held-out colours.)"""
    p = patch_dev
    l_star = 116.0 * np.cbrt(np.clip(patch_xyz[:, 1], 0.0, None)) - 16.0
    bad = np.zeros(len(p), bool)
    for k in range(len(p)):
        le = np.all(p <= p[k] + 1e-6, axis=1)
        le[k] = False
        if le.any() and l_star[k] > l_star[le].min() + dl:
            bad[k] = True
    return bad


def bound_by_data(model, device: np.ndarray, lab: np.ndarray, *,
                  margin: float = 3.0, floor_l: float = 2.5,
                  use_measured: bool = True, near: float = 0.5,
                  slack: float = 0.0,
                  ramp: float = 1.0, info: dict | None = None):
    """Lift every node that is darker, in any XYZ channel, than (a) a
    measured patch carrying at least as much of every ink, or (b) the
    darkest patches by more than ``floor_l`` L*-units; both compared in the
    CIELAB cube-root scale per XYZ channel with a ``margin`` (L*-units).
    Applied only where the lattice is extrapolated (``near``/``ramp`` cells
    from the nearest patch). Returns (Lab nodes, moved mask); nodes that
    obey are untouched and an unchanged model gives the same bytes."""
    grid, n = model.grid, model.n_channels
    ax = np.linspace(0.0, 1.0, grid)
    dev_axes = [model.unshape_device(np.tile(ax[:, None], (1, n)))[:, i]
                for i in range(n)]
    pdev = np.asarray(device, float)
    # the bounds come from the model's OWN values at the patches (a misread
    # is down-weighted by the robust fit, so its fitted value is sound), and
    # never lighter than the measurement itself
    fitted = lab_to_xyz(model.predict(pdev)) / D50_XYZ100
    measured = lab_to_xyz(np.asarray(lab, float)) / D50_XYZ100
    pxyz = np.minimum(fitted, measured) if use_measured else fitted
    # Each patch bounds with its MONOTONE ENVELOPE: the darkest of itself and
    # every patch carrying no more of any ink. On monotone data that is the
    # patch itself; where a press lightens with more ink (APTEC: the 700 %
    # patch reads L* 18.3, lighter than several 400-500 % patches; trapping
    # fails) or a patch is misread light, the bound drops to what the chart
    # shows with less ink instead of trusting the lighter reading.
    pxyz = monotone_envelope(pdev, pxyz)
    ok = np.ones(len(pdev), bool)
    lb = monotone_lower_bounds(dev_axes, pdev, pxyz, tol=max(slack, 1e-6))
    # floor: ``floor_l`` L* below the darkest patch as the robust fit sees
    # it (a single misread or noisy black read at L* 0, as on the typical-
    # noise X5 chart, must not set it). Truth over the battery: no device
    # corner is more than 1.93 L* darker than the chart's darkest patch.
    l_floor = float(model.predict(pdev[ok])[:, 0].min()) - floor_l
    # Compared in the CIELAB cube-root scale with an absolute margin of
    # ``margin`` L* units per channel: a dark node within noise of its bound
    # is left alone (relative XYZ noise near black is large).
    # Lightness only (the Y channel, compared in the cube-root scale with an
    # absolute ``margin`` in L*-units: relative XYZ noise near black is
    # large). Lifting X and Z as well pushed lifted nodes to neutral and
    # threw away a plausible hue (X5 K+O: dE00 4.97 -> 8.79).
    nodes = np.asarray(model.nodes, float)
    l_lb = 116.0 * np.cbrt(np.clip(lb[:, 1], 0.0, None)) - 16.0 - margin
    l_lb = np.where(np.isfinite(lb[:, 1]), l_lb, -np.inf)
    l_lb = np.maximum(l_lb, l_floor)
    moved = nodes[:, 0] < l_lb
    # Only where the chart leaves the lattice to extrapolation: a node at or
    # next to a patch is what the data say (real presses break channel
    # monotonicity by a few L* through trapping: X5's C+K is bluer, Z
    # higher, than K alone in the truth too). Weight 0 within ``near``
    # cells of a patch, 1 from ``near + ramp`` cells, smoothstep between.
    if moved.any():
        dist = nearest_patch_cells(grid, n, model.shape_device(pdev))
        w = np.clip((dist - near) / max(ramp, 1e-9), 0.0, 1.0)
        w = w * w * (3.0 - 2.0 * w)
        moved &= w > 0
    out = nodes.copy()
    if moved.any():
        tgt = nodes[moved].copy()
        tgt[:, 0] = l_lb[moved]
        # chroma no larger than the chart shows at that lightness or darker
        # (+25 % and 2 units): an extrapolated L* 0 node carried a* -72 (X7)
        lab_m = np.asarray(lab, float)[ok]
        cm = np.hypot(lab_m[:, 1], lab_m[:, 2])
        order = np.argsort(lab_m[:, 0])
        env = np.maximum.accumulate(cm[order])
        pos = np.searchsorted(lab_m[order, 0], tgt[:, 0] + 5.0, side="right")
        cmax = np.where(pos > 0, env[np.maximum(pos - 1, 0)], 0.0) * 1.25 + 2.0
        c = np.hypot(tgt[:, 1], tgt[:, 2])
        k = np.where(c > cmax, cmax / np.maximum(c, 1e-9), 1.0)
        tgt[:, 1:] *= k[:, None]
        out[moved] = nodes[moved] + w[moved, None] * (tgt - nodes[moved])
    if info is not None:
        info.update(moved=int(moved.sum()), nodes=int(len(out)))
    return out, moved


def smooth_correction(delta: np.ndarray, moved: np.ndarray, grid: int,
                      n: int, lam: float = 1.0, keep: float = 1.0,
                      iters: int = 300) -> np.ndarray:
    """Spread a node correction so it does not leave a kink: minimise
    sum_moved |d - delta|^2 + keep * sum_other |d|^2 + lam |L d|^2."""
    a = np.where(moved, 1.0, keep)[:, None]

    def amul(x):
        return a * x + lam * _curvature(x, grid, n)

    b = a * np.where(moved[:, None], delta, 0.0)
    x = b / a
    r = b - amul(x)
    p = r.copy()
    rs = float((r * r).sum())
    stop = 1e-14 * max(float((b * b).sum()), 1e-30)
    for _ in range(iters):
        ap = amul(p)
        al = rs / max(float((p * ap).sum()), 1e-30)
        x += al * p
        r -= al * ap
        rs2 = float((r * r).sum())
        if rs2 < stop:
            break
        p = r + (rs2 / rs) * p
        rs = rs2
    return x


def nearest_patch_cells(grid: int, n: int, shaped: np.ndarray,
                        chunk_axes: int = 2) -> np.ndarray:
    """L-infinity distance, in lattice cells, from every node to the nearest
    patch (shaped coordinates). 0 on a measured patch's own node."""
    g = np.linspace(0.0, 1.0, grid)
    P = len(shaped)
    d = [np.abs(g[:, None] - shaped[None, :, i]) * (grid - 1)
         for i in range(n)]                            # (grid, P)
    tail = np.zeros((1, P))
    for i in range(chunk_axes, n):
        tail = np.maximum(tail[:, None, :], d[i][None, :, :]).reshape(-1, P)
    out = np.empty((grid,) * chunk_axes + (len(tail),))
    for h in range(grid ** chunk_axes):
        idx = np.unravel_index(h, (grid,) * chunk_axes)
        head = np.zeros(P)
        for k, j in enumerate(idx):
            head = np.maximum(head, d[k][j])
        out[idx] = np.maximum(tail, head[None, :]).min(1)
    return out.reshape(-1)


def _fdiff(x: np.ndarray, ax: int) -> np.ndarray:
    return np.diff(x, axis=ax)


def _fdiff_t(y: np.ndarray, ax: int) -> np.ndarray:
    """Adjoint of the forward difference along ``ax`` (length grows by 1)."""
    pad = [(0, 0)] * y.ndim
    pad[ax] = (1, 1)
    yp = np.pad(y, pad)
    sl0 = [slice(None)] * y.ndim
    sl1 = [slice(None)] * y.ndim
    sl0[ax] = slice(0, -1)
    sl1[ax] = slice(1, None)
    return yp[tuple(sl0)] - yp[tuple(sl1)]


def interaction(x: np.ndarray, grid: int, n: int, order: int = 3) -> np.ndarray:
    """Sum over ink subsets of size ``order`` of (D..)^T (D..) x. order 2 =
    the torsion regulariser of Gupta et al. 2016 (JMLR 17:109), which also
    penalises PAIRWISE (bilinear) interactions; order 3 leaves them free."""
    import itertools
    x3 = x.reshape((grid,) * n + (-1,))
    o = np.zeros_like(x3)
    for sub in itertools.combinations(range(n), order):
        d = x3
        for a in sub:
            d = _fdiff(d, a)
        for a in reversed(sub):
            d = _fdiff_t(d, a)
        o += d
    return o.reshape(x.shape)


def interaction3(x: np.ndarray, grid: int, n: int) -> np.ndarray:
    """Sum over ink triples of (Di Dj Dk)^T (Di Dj Dk) x: penalises every
    interaction of three or more inks; additive and pairwise (bilinear)
    structure costs nothing (functional-ANOVA order 2; cf. additive GPs)."""
    import itertools
    x3 = x.reshape((grid,) * n + (-1,))
    o = np.zeros_like(x3)
    for i, j, k in itertools.combinations(range(n), 3):
        d = _fdiff(_fdiff(_fdiff(x3, i), j), k)
        o += _fdiff_t(_fdiff_t(_fdiff_t(d, k), j), i)
    return o.reshape(x.shape)


def resolve_with_order_penalty(model, device, lab, lam, mu, *, weights=None,
                               iters=400, order: int = 3):
    """Re-solve the lattice (fixed curves) with the curvature penalty plus
    ``mu`` x interaction3; from the current nodes."""
    from workflow.profile_engine.forward_model import _interp_weights
    grid, n = model.grid, model.n_channels
    ng = grid ** n
    w, cols = _interp_weights(model.shape_device(np.asarray(device, float)),
                              grid, n)
    y = np.asarray(lab, float)
    if weights is not None:
        sw = np.sqrt(np.asarray(weights, float))
        w = w * sw[:, None]
        y = y * sw[:, None]
    fc = cols.reshape(-1)

    def wt(r):
        return np.stack([np.bincount(fc, (w * r[:, c:c + 1]).reshape(-1),
                                     minlength=ng) for c in range(r.shape[1])], 1)

    def amul(x):
        return (wt((w[:, :, None] * x[cols]).sum(1)) + lam * _curvature(x, grid, n)
                + mu * interaction(x, grid, n, order) + 1e-7 * x)

    b = wt(y)
    x = np.array(model.nodes, float, copy=True)
    r = b - amul(x)
    p = r.copy()
    rs = float((r * r).sum())
    stop = 1e-12 * rs
    for _ in range(iters):
        ap = amul(p)
        a = rs / max(float((p * ap).sum()), 1e-30)
        x += a * p
        r -= a * ap
        rs2 = float((r * r).sum())
        if rs2 < stop:
            break
        p = r + (rs2 / rs) * p
        rs = rs2
    return x
