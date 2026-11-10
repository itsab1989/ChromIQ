"""Hue-kept rendering for the Perceptual and Saturation tables (x1-huekeep).

Optional, off by default, Maximum accuracy only, RGB printers only
(``BuildSettings.hue_rendering = "kept"``, token :data:`TOKEN`).

colprof's gamut mapping, which the engine's mapped tables reproduce, lets
the hue of a colour drift on its way into the printer's gamut (about 4
degrees on average over twelve hue ramps, 6 to 8 in the worst ramp, on
every RGB set measured). This step re-solves a finished mapped table as ONE
smooth field so that every node prints the colour the table printed before,
turned to the hue of its SOURCE colour:

    minimise over the node values s (the table's own curve space)
        sum over nodes | W (print(s) - target) |^2
        + MU * | second differences of s along the three grid axes |^2
    with 0 <= s <= 1 and the pinned nodes fixed.

* ``print`` is the engine's forward model behind the table's output curves.
* ``target`` is what the table printed at that node, with the hue angle of
  the node's own (source) Lab in the rotation space; lightness and chroma
  of the print are kept. The hue weight fades out towards the neutral axis
  (where a hue is not defined) and below source L* DARK_FADE_L (where the
  "source hue" of neighbouring nodes swings by tens of degrees).
* ``W`` counts an error along the chroma direction CHROMA_WEIGHT times an
  error in lightness or hue, so a target the printer cannot reach loses
  chroma, not hue or lightness, and that decision is made by the one field
  solve instead of node by node.
* Pinned: the whole source-neutral column (white and black included) and
  the nodes around the black that hold the black's own value. The engine
  constructs those on purpose; they keep their bytes.

The construction is ``b2a.smooth_exact``'s (Gauss-Newton on the whole table,
conjugate-gradient inner solve, the same curvature operator ``b2a._curv3``),
with a per-node metric, an active set for the 0..1 box and a backtracking
line search added. smooth_exact itself is left alone: the colorimetric
table's bytes depend on it.

Where it came from and where it was validated: the expert review of
2026-11-10 ("M-smooth, variant c"; handover sections 13a and 15.1). Designed
on six RGB sets (ET-8550, PRO-300, Knut's laser, PRO-1000, PRO-1000 CG,
ET-18100), validated on three sets that played no part (ET-8550 228
patches, X-Rite 2033 patches, PRO-1000 2871 patches). Not for ink devices:
with a free K the curvature term slides the separation where the print does
not see it (measured, 3.6 dE00 p95 on a CMYK set), so the functional would
need a separation term first.

Nothing here keeps state between builds: everything a solve needs is passed
in as arguments.
"""
from __future__ import annotations

import numpy as np

from workflow.profile_engine import icc_writer as icw
from workflow.profile_engine.b2a import _curv3

TOKEN = "x1-huekeep"

# The constants below are properties of the METHOD, the same for every
# printer. None of them is a measured printer property, a gate or a
# threshold: every one enters the solve continuously. They were fixed on the
# six design sets and held unchanged on the three validation sets named in
# the module comment (sensitivity, measured in the review: MU 100 and 300
# equivalent and 0 fails on a folded response; fade L* 16 and 32 clean and 8
# leaves one red ramp rough; chroma weight 0.10 and 0.25 clean and 0.50
# leaves a small lightness reversal in one violet ramp).
#
# Curvature weight on the node values in curve space (b2a.A44B_MU's value).
MU = 100.0
# Source L* below which the hue weight fades out (smoothstep from 0 to it).
DARK_FADE_L = 16.0
# Weight of an error along the chroma direction relative to an error in
# lightness or hue.
CHROMA_WEIGHT = 0.25
# The space the hue angle is taken and turned in. Decided on the design sets
# against IPT with each candidate judged only in hue spaces foreign to it
# (2026-11-11): OKLab-rotated left 0.19 of the engine's mean hue drift,
# IPT-rotated 0.23, and IPT-rotated raised the fine-scale banding of the hue
# ramps on all six sets.
ROTATION_SPACE = "oklab"
# OKLab chroma (Ottosson's scale, white L = 1) over which the hue weight and
# the chroma weighting fade in from the neutral axis (smoothstep).
NEUTRAL_FADE_C = 0.03

# Solver effort (not tuning constants of the rendering): outer Gauss-Newton
# rounds and inner conjugate-gradient iterations, both upper bounds.
_ROUNDS = 8
_CG_ITERS = 300


def applies(candidates, *, accurate: bool, is_additive: bool,
            n_channels: int) -> bool:
    """True when the step acts: the token is set, in a Maximum accuracy
    build, on an RGB device."""
    return bool(accurate and TOKEN in (candidates or ())
                and is_additive and n_channels == 3)


# ----------------------------------------------------------------- OKLab
def _lab_to_oklab(lab: np.ndarray) -> np.ndarray:
    """D50 Lab -> OKLab (white L = 1). Cone responses below zero are set
    to zero: a PCS node that is not a real colour then takes the hue of the
    nearest real one, continuously. With the signed cube root the "hue" of
    neighbouring dark nodes jumps by tens of degrees."""
    from workflow.profile_engine import oog_clip as oc
    lms = (oc._OK_M1 @ oc._xyz65(lab).T).T
    return (oc._OK_M2 @ np.cbrt(np.clip(lms, 0.0, None)).T).T


def _oklab_to_lab(ok: np.ndarray) -> np.ndarray:
    from workflow.profile_engine import oog_clip as oc
    return oc.oklab_to_lab(np.asarray(ok, float) * 100.0)


def _smoothstep(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def source_hue_targets(source_lab: np.ndarray,
                       printed_lab: np.ndarray) -> np.ndarray:
    """``printed_lab`` with the hue of ``source_lab`` in the rotation space;
    lightness and chroma of the print are kept. The turn is weighted by the
    source's chroma (fade-in from the neutral axis) and by the source's L*
    (fade-out towards black)."""
    so, po = _lab_to_oklab(source_lab), _lab_to_oklab(printed_lab)
    cs = np.hypot(so[:, 1], so[:, 2])
    cp = np.hypot(po[:, 1], po[:, 2])
    hs = np.arctan2(so[:, 2], so[:, 1])
    hp = np.arctan2(po[:, 2], po[:, 1])
    w = _smoothstep(cs / NEUTRAL_FADE_C) \
        * _smoothstep(np.asarray(source_lab, float)[:, 0] / DARK_FADE_L)
    h = hp + w * ((hs - hp + np.pi) % (2.0 * np.pi) - np.pi)
    new = _oklab_to_lab(np.stack([po[:, 0], cp * np.cos(h),
                                  cp * np.sin(h)], 1))
    ok = np.isfinite(new).all(1)
    return np.where(ok[:, None], new, printed_lab)


def chroma_metric(target_lab: np.ndarray) -> np.ndarray:
    """(N, 3, 3) W: |W dLab| counts the part of dLab along the chroma
    direction at the target (constant lightness and hue in the rotation
    space) CHROMA_WEIGHT times, everything else once. The identity at the
    neutral axis (same fade as the hue weight)."""
    ok = _lab_to_oklab(target_lab)
    c = np.hypot(ok[:, 1], ok[:, 2])
    h = np.arctan2(ok[:, 2], ok[:, 1])
    d = 1e-3

    def at(cc):
        return _oklab_to_lab(np.stack([ok[:, 0], cc * np.cos(h),
                                       cc * np.sin(h)], 1))
    e = at(c + d) - at(c)
    nrm = np.linalg.norm(e, axis=1)
    good = np.isfinite(e).all(1) & (nrm > 1e-9)
    e = np.where(good[:, None], e / np.where(good, nrm, 1.0)[:, None], 0.0)
    f = (1.0 - CHROMA_WEIGHT) * _smoothstep(c / NEUTRAL_FADE_C) * good
    return np.eye(3)[None] - f[:, None, None] * e[:, :, None] * e[:, None, :]


def free_nodes(shaped: np.ndarray, node_lab: np.ndarray,
               grid: int) -> np.ndarray:
    """Boolean mask of the nodes the solve may move. Pinned: the
    source-neutral column (the a*, b* grid point nearest zero, every L*) and
    the nodes around the black node that hold exactly the black node's
    written value (within four grid steps in L* and three in a*, b*: the
    black cell the build fills on purpose)."""
    ls, ab = icw.lab_grid_axes(grid)
    i0 = int(np.argmin(np.abs(ab)))
    idx = np.arange(grid ** 3)
    free = ~((idx // grid % grid == i0) & (idx % grid == i0))
    q = icw.device_to_u16(np.asarray(shaped, float))
    black = q[(0 * grid + i0) * grid + i0]
    cell = ((q == black[None, :]).all(1)
            & (node_lab[:, 0] < (ls[-1] - ls[0]) * 4.0 / (grid - 1))
            & (np.hypot(node_lab[:, 1], node_lab[:, 2])
               < (ab[-1] - ab[0]) * 3.0 / (grid - 1)))
    free[cell] = False
    return free


def solve_field(pr, s0: np.ndarray, target: np.ndarray, *,
                free: np.ndarray, w: np.ndarray, grid: int,
                mu: float = MU, rounds: int = _ROUNDS,
                cg_iters: int = _CG_ITERS):
    """Gauss-Newton on the whole table (see the module comment).
    ``pr``: node values in curve space -> Lab. Returns ``(s, objective)``,
    the objective as a list of (data term, curvature term) per round."""
    s = np.clip(np.asarray(s0, float).copy(), 0.0, 1.0)
    n = s.shape[1]
    fm0 = free[:, None].astype(float) * np.ones(n)
    h = 1e-3
    eye = np.eye(n)

    def resid(x):
        return np.einsum("nij,nj->ni", w, pr(x) - target)

    def objective(x, r=None):
        r = resid(x) if r is None else r
        return float((r * r).sum()), float(mu * (x * _curv3(x, grid)).sum())

    hist = []
    for _ in range(rounds):
        r = resid(s)
        f_d, f_c = objective(s, r)
        hist.append((f_d, f_c))
        jac = np.stack([(resid(s + h * eye[k]) - resid(s - h * eye[k]))
                        / (2.0 * h) for k in range(n)], 2)
        g = np.einsum("nlk,nl->nk", jac, r) + mu * _curv3(s, grid)
        # the 0..1 box as an active set: at a bound and pushed outwards
        act = ((s <= 0.0) & (g > 0.0)) | ((s >= 1.0) & (g < 0.0))
        fm = fm0 * (~act)
        jtj = np.einsum("nlk,nlm->nkm", jac, jac)
        b = -g * fm

        def amul(x):
            return (np.einsum("nkm,nm->nk", jtj, x * fm)
                    + mu * _curv3(x * fm, grid)) * fm + 1e-6 * x
        x = np.zeros_like(s)
        rr = b.copy()
        p = rr.copy()
        rs = float((rr * rr).sum())
        rs0 = rs
        if rs0 < 1e-20:
            break
        for _i in range(cg_iters):
            ap = amul(p)
            al = rs / max(float((p * ap).sum()), 1e-30)
            x += al * p
            rr -= al * ap
            rs2 = float((rr * rr).sum())
            if rs2 < 1e-10 * rs0:
                break
            p = rr + (rs2 / rs) * p
            rs = rs2
        t = 1.0
        ok = False
        for _i in range(6):                 # backtracking, true objective
            sn = np.clip(s + t * x, 0.0, 1.0)
            fd, fc = objective(sn)
            if fd + fc <= f_d + f_c:
                ok = True
                break
            t *= 0.5
        if not ok:
            break
        done = abs((f_d + f_c) - (fd + fc)) < 1e-5 * (f_d + f_c + 1e-9)
        s = sn
        if done:
            break
    hist.append(objective(s))
    return s, hist


def keep_source_hue(model, shaped: np.ndarray, node_lab: np.ndarray, *,
                    grid: int, out_tables: np.ndarray):
    """One mapped RGB table with the source hue kept.

    ``shaped``: the table's CLUT as it is about to be written (curve space,
    0..1, first PCS axis slowest); ``node_lab``: the Lab of its nodes (the
    source colours); ``out_tables``: the table's u16 output curves, which
    take a CLUT value to the device value the way a CMM does. Returns
    ``(shaped, info)``; pinned nodes come back exactly as they went in."""
    s0 = np.asarray(shaped, float)
    info = {"applied": False}
    if s0.shape[1] != 3 or len(node_lab) != grid ** 3 \
            or len(s0) != grid ** 3:
        return shaped, info
    tabs = np.asarray(out_tables, float) / 65535.0
    e = tabs.shape[1]
    xs = np.arange(e)

    def pr(x):
        x = np.clip(x, 0.0, 1.0)
        dev = np.stack([np.interp(x[:, c] * (e - 1), xs, tabs[c])
                        for c in range(3)], 1)
        return model.predict(np.clip(dev, 0.0, 1.0))

    source = np.asarray(node_lab, float).copy()
    source[:, 0] = np.clip(source[:, 0], 0.0, 100.0)
    printed = pr(s0)
    free = free_nodes(s0, source, grid)
    target = source_hue_targets(source, printed)
    target[~free] = printed[~free]
    s, hist = solve_field(pr, s0, target, free=free,
                          w=chroma_metric(target), grid=grid)
    out = s0.copy()
    out[free] = s[free]
    moved = np.linalg.norm(pr(out) - printed, axis=1)
    miss = np.linalg.norm(pr(out) - target, axis=1)
    info.update(applied=True, pinned=int((~free).sum()),
                rounds=len(hist) - 1, objective_start=sum(hist[0]),
                objective_end=sum(hist[-1]),
                miss_median=float(np.median(miss)),
                miss_p95=float(np.percentile(miss, 95)),
                moved_median=float(np.median(moved)),
                moved_p95=float(np.percentile(moved, 95)))
    return out, info


def progress_line(tag: str, info: dict) -> str:
    """The developer line of one solved table (it names the token, so the
    app's adapter keeps it out of the user's log like every internal
    line)."""
    return (f"Hue-kept rendering ({TOKEN}, {tag}): source hue kept in "
            f"{ROTATION_SPACE}; {info['rounds']} rounds, "
            f"{info['pinned']} nodes pinned, nodes moved "
            f"{info['moved_median']:.2f} median / {info['moved_p95']:.2f} "
            f"p95 dE76 from the table before, target missed by "
            f"{info['miss_median']:.2f} / {info['miss_p95']:.2f}.")


NOT_RGB_LINE = (f"Hue-kept rendering ({TOKEN}): for RGB printers only; "
                "nothing is changed on this device.")
NOT_LAB_LINE = (f"Hue-kept rendering ({TOKEN}): needs a Lab connection "
                "space; nothing is changed in this profile.")
