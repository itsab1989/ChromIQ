"""Scoring one built profile (Agent 6).

Every number is computed from the profile BYTES through a CMM readout
(:mod:`cmm`), against ground truth (synthetic) or held-out measurements
(real). Per reader:

* ``a2b``        forward table vs truth at dense TAC-respecting device points
                 (quasi-random); dE00 and dE ITP stats, plus L*<20 shadows,
                 L*>85 highlights and near-neutral (C* < 5) subsets.
* ``b2a``        inverse end to end: ask the table for the ink of an in-gamut
                 colour, print that ink on the truth printer, compare.
* ``roundtrip``  A2B(B2A(lab)) vs lab (table self-consistency).
* ``neutral``    the grey ramp L* from just above the printer's black to 100
                 at 0.25 steps through B2A, printed on the truth: dE00, the
                 printed chroma, L* reversals, a banding proxy (max second
                 difference of printed Lab per step), and the separation
                 (max per-channel change per 1 L*, total-variation excess).
* ``ramps``      the same separation smoothness on straight Lab ramps from
                 paper white to each primary solid and on to the black.
* ``white/black``  ink put into paper white, printed L* of B2A(0,0,0), TAC.

Real data: ``a2b`` at the held-out patches only; ``b2a`` and ``neutral``
are printed through a PROXY printer (the colprof -qh profile of ALL
patches, read by Argyll), labelled ``proxy`` - an estimate, not truth.
"""
from __future__ import annotations

import numpy as np

from benchmarks.research import cmm, colour


def stats(de: np.ndarray) -> dict:
    de = np.asarray(de, float)
    if de.size == 0:
        return {"n": 0}
    return {"n": int(de.size), "mean": float(de.mean()),
            "median": float(np.median(de)),
            "p95": float(np.percentile(de, 95)),
            "p99": float(np.percentile(de, 99)), "max": float(de.max())}


def _subsets(lab_true: np.ndarray, de: np.ndarray, de_itp: np.ndarray | None
             ) -> dict:
    c = np.hypot(lab_true[:, 1], lab_true[:, 2])
    out = {"all": stats(de),
           "shadow_L<20": stats(de[lab_true[:, 0] < 20]),
           "highlight_L>85": stats(de[lab_true[:, 0] > 85]),
           "neutral_C<5": stats(de[c < 5])}
    if de_itp is not None:
        out["itp"] = stats(de_itp)
    return out


def eval_device(n_channels: int, additive: bool, tac: float | None, n: int,
                seed: int = 7) -> np.ndarray:
    from benchmarks.synthetic import halton
    pts = halton(n, n_channels, seed)
    if tac is not None and not additive:
        from workflow.profile_engine.b2a import project_tac
        pts = project_tac(pts, tac / 100.0)
    return pts


def lab_uniform_index(lab: np.ndarray, cell: float = 4.0, seed: int = 3
                      ) -> np.ndarray:
    """One point per occupied Lab voxel: a sample uniform over the printed
    gamut's volume instead of over device space (device-uniform points
    crowd the dark end, where many ink combinations print alike)."""
    key = np.floor(lab / cell).astype(np.int64)
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(lab))
    _, first = np.unique(key[order], axis=0, return_index=True)
    return np.sort(order[first])


def highlight_device(n_channels: int, additive: bool, n: int, seed: int = 13
                     ) -> np.ndarray:
    """Every channel at most 30 % coverage: where light colours live."""
    from benchmarks.synthetic import halton
    pts = halton(n, n_channels, seed) * 0.30
    if n_channels > 4:
        # at most three inks per point, or 5-7 inks at 30 % leave nothing
        # above L* 85 (measured on X7/X8: an empty sample)
        rng = np.random.default_rng(seed)
        keep = np.argsort(rng.uniform(size=pts.shape), axis=1) < 3
        pts = pts * keep
    return 1.0 - pts if additive else pts


def pale_device(n_channels: int, additive: bool, n: int, seed: int = 17) -> np.ndarray:
    """Agent 21: 1-2 channels at 0.5-8 % coverage (deterministic)."""
    rng = np.random.default_rng(seed)
    d = np.zeros((n, n_channels))
    for i in range(n):
        k = rng.choice(n_channels, int(rng.integers(1, 3)), replace=False)
        d[i, k] = rng.uniform(0.005, 0.08, len(k))
    return 1.0 - d if additive else d


class Truth:
    """Uniform access: a synthetic printer, or a proxy profile for real data."""

    def __init__(self, printer=None, proxy_icc=None, illuminant: str = "D50",
                 proxy_reader: str = "argyll"):
        self.printer = printer
        self.proxy = proxy_icc
        self.proxy_reader = proxy_reader      # lcms for v4 mAB proxies icclu refuses
        self.illuminant = illuminant or "D50"

    @property
    def is_proxy(self) -> bool:
        return self.printer is None

    def lab(self, device: np.ndarray) -> np.ndarray:
        if self.printer is not None:
            return self.printer.lab_rel(device, self.illuminant)
        return cmm.a2b(self.proxy, device, self.proxy_reader)


def _separation(dev: np.ndarray, l_axis: np.ndarray) -> dict:
    dl = np.abs(np.diff(l_axis))
    step = np.abs(np.diff(dev, axis=0))
    rate = step / np.maximum(dl, 1e-9)[:, None]
    tv = step.sum(0)
    net = np.abs(dev[-1] - dev[0])
    return {"max_step": float(step.max()),
            "max_rate_per_L": float(rate.max()),
            "tv_excess": float((tv - net).sum()),
            "tv_excess_per_channel": [float(v) for v in tv - net]}


def neutral_axis(prof, reader: str, truth: Truth, black_l: float, n_ch: int,
                 additive: bool, sink: dict | None = None) -> dict:
    # fixed start (L* 1) so ramps pair across profiles; the part below the
    # printer's own black is reported separately in "shadow"
    ls = np.arange(1.0, 100.0 + 1e-9, 0.25)
    target = np.stack([ls, np.zeros_like(ls), np.zeros_like(ls)], 1)
    dev = cmm.b2a(prof, target, reader)
    printed = truth.lab(dev)
    de = colour.de2000(printed, target)
    if sink is not None:
        sink["neutral_L"] = ls
        sink["neutral_de"] = de
        sink["neutral_dev"] = dev
        sink["neutral_printed"] = printed
        sink["neutral_black_L"] = np.array(black_l)
    pr = ls >= black_l + 1.0            # targets the printer can reach
    P, D, Lp, E = printed[pr], dev[pr], ls[pr], de[pr]
    chroma = np.hypot(P[:, 1], P[:, 2])
    dL = np.diff(P[:, 0])
    d2 = np.linalg.norm(np.diff(P, 2, axis=0), axis=1)
    out = {"from_L": float(Lp[0]), "de": stats(E), "chroma_max": float(chroma.max()),
           "chroma_mean": float(chroma.mean()),
           "chroma_median": float(np.median(chroma)),
           "a_range": [float(P[:, 1].min()), float(P[:, 1].max())],
           "b_range": [float(P[:, 2].min()), float(P[:, 2].max())],
           "L_reversals": int((dL < -0.05).sum()),
           "L_min_step": float(dL.min()),
           "banding_max_d2": float(d2.max()),
           "separation": _separation(D, Lp),
           # below the printer's black the table should hold the black ink
           # steady: any device movement there is wasted variation
           "below_black_device_tv": float(np.abs(np.diff(dev[~pr], axis=0)).sum())
           if (~pr).sum() > 1 else 0.0}
    hi = ls >= 85.0
    # protocol v2 E6: the highlight neutral ramp (agent 7 T2c: the L* 93.75
    # node printed L* 59-88 on n > 3 / matte printers)
    out["highlight"] = {"de": stats(de[hi]),
                        "printed_L_at_93_75": float(printed[np.argmin(np.abs(ls - 93.75)), 0]),
                        "chroma_max": float(np.hypot(printed[hi, 1], printed[hi, 2]).max())}
    sh = Lp < 30
    if sh.sum() > 3:
        out["shadow"] = {"de": stats(E[sh]),
                         "separation": _separation(D[sh], Lp[sh]),
                         "banding_max_d2": float(np.linalg.norm(
                             np.diff(P[sh], 2, axis=0), axis=1).max())}
    return out


def ramps(prof, reader: str, truth: Truth, n_ch: int, additive: bool,
          fwd: bool = True) -> dict:
    """Paper -> solid -> black straight Lab ramps, separation smoothness.
    ``fwd`` False (a B2A-only reader): the black end is the truth's black."""
    white_dev = np.full((1, n_ch), 1.0 if additive else 0.0)
    solids = []
    for i in range(n_ch):
        d = white_dev.copy()
        d[0, i] = 0.0 if additive else 1.0
        solids.append(d[0])
    solid_lab = truth.lab(np.array(solids))
    bdev = np.full((1, n_ch), 0.0) if additive else _black_dev(n_ch)
    black_lab = (cmm.a2b(prof, bdev, reader) if fwd else truth.lab(bdev))[0]
    worst = {"max_step": 0.0, "max_rate_per_L": 0.0, "tv_excess": 0.0}
    per = {}
    t = np.linspace(0, 1, 121)[:, None]
    for i, s in enumerate(solid_lab):
        path = np.vstack([np.array([100.0, 0, 0]) * (1 - t) + s * t,
                          s * (1 - t[1:]) + black_lab * t[1:]])
        dev = cmm.b2a(prof, path, reader)
        arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
        sep = _separation(dev, arc)
        per[str(i)] = {k: sep[k] for k in ("max_step", "max_rate_per_L", "tv_excess")}
        for k in worst:
            worst[k] = max(worst[k], sep[k])
    return {"worst": worst, "per_solid": per}


def _black_dev(n_ch: int) -> np.ndarray:
    d = np.zeros((1, n_ch))
    d[0, :min(4, n_ch)] = 1.0
    return d


def score(prof, dataset, reader: str, truth: Truth, n_eval: int = 20000,
          light: bool = False, sink: dict | None = None) -> dict:
    """All metrics for one profile under one reader. ``sink`` (optional)
    receives the per-point dE arrays, index-aligned across profiles of the
    same dataset (deterministic points), for the paired statistics."""
    sink = sink if sink is not None else {}
    n = dataset.n_channels
    additive = dataset.color_rep.startswith(("iRGB", "RGB"))
    # v3: B2A-only readers (a RIP: Ghostscript) score the inverse endpoints
    # only; A2B, the round trip and the white's A2B are not theirs to read
    fwd = cmm.supports(reader, "a2b")
    out: dict = {"reader": reader, "truth": "proxy" if truth.is_proxy else "printer"}
    if not fwd:
        out["a2b_unsupported"] = True
    if dataset.kind == "real":
        if fwd:
            pred = cmm.a2b(prof, dataset.holdout_device, reader)
            de = colour.de2000(pred, dataset.holdout_lab)
            sink["a2b"] = de
            out["a2b_heldout"] = _subsets(dataset.holdout_lab, de,
                                          colour.de_itp(pred, dataset.holdout_lab))
        dev = eval_device(n, additive, dataset.ink_limit, n_eval // 4)
    else:
        dev = eval_device(n, additive, dataset.ink_limit, n_eval)
        if fwd:
            lab_t = truth.lab(dev)
            pred = cmm.a2b(prof, dev, reader)
            de = colour.de2000(pred, lab_t)
            sink["a2b"] = de
            out["a2b"] = _subsets(lab_t, de, colour.de_itp(pred, lab_t))
    lab_t = truth.lab(dev)
    ink = cmm.b2a(prof, lab_t, reader)
    printed = truth.lab(ink)
    de_b = colour.de2000(printed, lab_t)
    out["b2a"] = _subsets(lab_t, de_b, colour.de_itp(printed, lab_t))
    sink["b2a"] = de_b
    uni = lab_uniform_index(lab_t)
    sink["b2a_lab_uniform_index"] = uni
    out["b2a"]["lab_uniform"] = stats(de_b[uni])
    # dedicated highlight sample (true L* > 85): the device-uniform grid
    # holds only a handful of points there (12 of 20,000 on S3)
    hdev = highlight_device(n, additive, max(n_eval // 4, 2000))
    hlab = truth.lab(hdev)
    keep = hlab[:, 0] > 85
    hdev, hlab = hdev[keep], hlab[keep]
    if len(hlab):
        hp = truth.lab(cmm.b2a(prof, hlab, reader))
        out["b2a"]["highlight_sample"] = stats(colour.de2000(hp, hlab))
        if dataset.kind != "real" and fwd:
            out["a2b"]["highlight_sample"] = stats(
                colour.de2000(cmm.a2b(prof, hdev, reader), hlab))
    # Agent 21 (F-14, protocol v3 proposal E10): PALE in-gamut colours, the
    # region the highlight sample above barely reaches: 1-2 inks (channels)
    # at 0.5-8 % coverage, kept where the truth prints L* > 90. Every target
    # is printable by construction. The Maximum accuracy B2A printed these
    # 10-40 L* too dark on 5-7 inks (CMYK p95 5-7 dE00 vs Fast 2.6).
    pdev = pale_device(n, additive, 1500)
    plab = truth.lab(pdev)
    pk = plab[:, 0] > 90.0
    if pk.any():
        pp = truth.lab(cmm.b2a(prof, plab[pk], reader))
        de_p = colour.de2000(pp, plab[pk])
        sink["pale"] = de_p
        out["b2a"]["pale_sample"] = stats(de_p)
        out["b2a"]["pale_sample"]["share_gt2"] = float(np.mean(de_p > 2.0))
        # v3.1 (F-14): the LIGHTNESS error of the same pale colours, |dL*|,
        # and the signed mean (positive = printed darker than asked)
        dl = plab[pk][:, 0] - pp[:, 0]
        sink["pale_dl"] = np.abs(dl)
        out["b2a"]["pale_sample"]["dl_abs"] = stats(np.abs(dl))
        out["b2a"]["pale_sample"]["dl_signed_mean"] = float(dl.mean())
    if not additive:
        tac = ink.sum(1) * 100.0
        out["b2a"]["tac_max"] = float(tac.max())
        if dataset.ink_limit:
            out["b2a"]["over_limit_frac"] = float(
                np.mean(tac > dataset.ink_limit + 1.0))
    if fwd:
        rt = cmm.a2b(prof, ink, reader)
        sink["roundtrip"] = colour.de2000(rt, lab_t)
        out["roundtrip"] = stats(sink["roundtrip"])
        # v3 (targets v2): ICC WP27 states its round-trip limit in dE*ab;
        # dE00 can read a near-neutral a* error 1.5x LARGER, so it is not a
        # conservative stand-in (Agent 13 7.3). Both are kept.
        out["roundtrip_ab"] = stats(np.linalg.norm(rt - lab_t, axis=1))
    # black and the neutral ramp (E5, E6) are scored in light mode too:
    # protocol v2.1 decides ramp rows across noise seeds, so the seeds suite
    # must keep the ramp arrays (agent 6b, 2026-10-03)
    bd = cmm.b2a(prof, np.array([[0.0, 0, 0]]), reader)
    blab = truth.lab(bd)[0]
    out["black"] = {"printed_L": float(blab[0]), "printed_ab": [float(blab[1]), float(blab[2])],
                    "tac_pct": float(bd.sum() * 100) if not additive else None}
    # v3 (targets v2, black row): the darkest neutral the TRUTH can print
    # inside the ink limit, so the black is judged against what is
    # reachable, not against the best builder (Agent 13 7.4)
    if not truth.is_proxy:
        out["black"]["reachable_L"] = reachable_black(truth, n, additive, dataset.ink_limit)
    out["neutral"] = neutral_axis(prof, reader, truth, float(blab[0]), n, additive,
                                  sink=sink)
    if light:
        return out
    wd = cmm.b2a(prof, np.array([[100.0, 0, 0]]), reader)[0]
    white_ink = (1.0 - wd) if additive else wd
    out["white"] = {"max_ink_pct": float(white_ink.max() * 100)}
    if fwd:
        out["white"]["a2b_white_de"] = float(colour.de2000(
            cmm.a2b(prof, np.full((1, n), 1.0 if additive else 0.0), reader),
            np.array([[100.0, 0, 0]]))[0])
    if not additive:
        out["ramps"] = ramps(prof, reader, truth, n, additive, fwd=fwd)
    return out


def reachable_black(truth, n: int, additive: bool, ink_limit, samples: int = 6000,
                    chroma_max: float = 2.0) -> dict:
    """The darkest colour the truth prints inside the ink limit, and the
    darkest NEAR-NEUTRAL one (C* <= ``chroma_max``): a quasi-random search
    over the in-limit ink space, dark-weighted (cached per truth)."""
    key = (n, additive, ink_limit, samples)
    cache = getattr(truth, "_reach_cache", None)
    if cache is None:
        cache = truth._reach_cache = {}
    if key in cache:
        return cache[key]
    from benchmarks.synthetic import halton
    pts = halton(samples, n, 29)
    if additive:
        pts = pts * 0.35                      # dark RGB device values
    else:
        pts = 0.4 + 0.6 * pts
        if ink_limit:
            from workflow.profile_engine.b2a import project_tac
            pts = project_tac(pts, ink_limit / 100.0)
    lab = truth.lab(pts)
    c = np.hypot(lab[:, 1], lab[:, 2])

    def cost(L, C):
        return L + 4.0 * np.clip(C - chroma_max, 0.0, None)
    # refine the best few by a shrinking random pattern search inside the limit
    rng = np.random.default_rng(31)
    best = pts[np.argsort(cost(lab[:, 0], c))[:8]].copy()
    step = 0.08
    for _ in range(40):
        cand = np.clip(best[:, None, :] + rng.normal(0, step, (len(best), 12, n)), 0, 1)
        cand = cand.reshape(-1, n)
        if ink_limit and not additive:
            from workflow.profile_engine.b2a import project_tac
            cand = project_tac(cand, ink_limit / 100.0)
        allp = np.vstack([best, cand])
        al = truth.lab(allp)
        k = np.argsort(cost(al[:, 0], np.hypot(al[:, 1], al[:, 2])))[:8]
        best = allp[k]
        step *= 0.92
    bl = truth.lab(best)
    bc = np.hypot(bl[:, 1], bl[:, 2])
    neu = bc <= chroma_max + 1e-9
    res = {"darkest_L": float(lab[:, 0].min()),
           "darkest_neutral_L": float(bl[neu, 0].min()) if neu.any() else None,
           "darkest_neutral_ink_pct": float(best[neu][np.argmin(bl[neu, 0])].sum() * 100)
           if neu.any() else None}
    cache[key] = res
    return res


def raw_neutral_column(icc_path) -> dict | None:
    """F-00's own metric, read from the B2A1 CLUT bytes: the node column at
    a* = b* = 0 of a Lab-PCS table (as tests/test_engine_accurate_mode.py
    reads it). None for XYZ-PCS tables."""
    import struct
    data = open(icc_path, "rb").read()
    if data[20:24] != b"Lab ":
        return None
    ntags = struct.unpack(">I", data[128:132])[0]
    off = None
    for i in range(ntags):
        sig, o, _ = struct.unpack(">4sII", data[132 + 12 * i:144 + 12 * i])
        if sig == b"B2A1":
            off = o
    if off is None or data[off:off + 4] != b"mft2":
        return None
    n_in, n_out, grid = data[off + 8], data[off + 9], data[off + 10]
    n_ine, _ = struct.unpack(">HH", data[off + 48:off + 52])
    clut_off = off + 52 + 2 * n_in * n_ine
    clut = np.frombuffer(data, dtype=">u2", count=grid ** 3 * n_out,
                         offset=clut_off).reshape(grid, grid, grid, n_out)
    mid = grid // 2
    col = clut[:, mid, mid, :].astype(float) / 0xFFFF
    step = np.abs(np.diff(col, axis=0))
    return {"grid": int(grid), "max_node_step": float(step.max()),
            "argmax_node": int(step.max(1).argmax()),
            "column": col.round(4).tolist()}
