"""N-colour quality: the critical tests an expert would run on a 5-8 ink
profile (Agent 14, research D-12; criteria and sources in
Validation/ncolour-excellence.md). Beside gmq (M1-M11, gamut mapping) and
metrics (E1-E6); no engine code is imported (the referee must not share
code with what it judges).

Every test reads the profile BYTES through a real CMM (Argyll icclu by
default, lcms2 optional), prints device values on the battery's 1 nm truth
printer and compares with the truth. Intent: colorimetric (B2A1) unless
``--intent`` says otherwise.

NC1  single-ink ramps: forward (A2B) accuracy along each ink alone, and the
     inverse's purity: does B2A reproduce an ink's own tint with that ink?
NC2  overprints: A2B accuracy on every two-ink grid and on the "ECG-like"
     region (at most 3 or 4 inks on, which is where professional ECG charts
     sample and where a real separation lives), beside the all-ink region.
NC3  ink switching: hue circles at fixed L* and chroma (a fraction of the
     truth gamut's chroma at that L*, hue), through B2A: per-ink rise-and-
     fall count, total-variation excess, largest per-degree jump, inks on
     at once, complementary inks on together; plus the grey: extra (non
     CMYK) ink on the neutral axis.
NC4  gamut extension: targets the printer reaches ONLY with its extra inks
     (truth points farther than 3 dE00 from every CMYK-only truth colour):
     B2A accuracy there and the share reproduced within 1 / 2 dE00 (the
     ECG spot-colour criterion), plus truth volume CMYK-only vs all inks.
NC5  smooth gradients through B2A: straight Lab ramps between in-gamut
     colours, white and black; printed step / target step ratio (p99, max),
     visible jumps (printed step > 3x target and > 1 dE00), largest second
     difference.
NC6  limits: TAC and per-channel maxima over every B2A output above.

    python -m benchmarks.research.ncq PROFILE.icc PRINTER_ID [--reader argyll]
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np

from benchmarks.research import cmm, colour, gmq
from benchmarks.research.printers import build_printers

CMYK = ("C", "M", "Y", "K")


def stats(x) -> dict:
    x = np.asarray(x, float)
    if x.size == 0:
        return {"n": 0}
    return {"n": int(x.size), "mean": float(x.mean()), "median": float(np.median(x)),
            "p95": float(np.percentile(x, 95)), "max": float(x.max())}


def _tac_ok(dev: np.ndarray, tac: float | None) -> np.ndarray:
    return np.ones(len(dev), bool) if tac is None else dev.sum(1) <= tac / 100.0 + 1e-9


def _b2a(prof, lab, reader, intent):
    if intent == "r":
        return cmm.b2a(prof, lab, reader)
    return gmq.b2a_intent(Path(prof), lab, reader, intent)


def extra_ink_index(letters) -> list[int]:
    """Channels that are not C, M, Y or K (light inks c/m count as extra)."""
    return [i for i, l in enumerate(letters) if l not in CMYK]


def solid_hues(printer) -> np.ndarray:
    n = printer.n
    lab = printer.lab_rel(np.eye(n))
    return np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360.0, np.hypot(lab[:, 1], lab[:, 2])


def complementary_pairs(printer, min_angle: float = 150.0, min_chroma: float = 20.0):
    """Chromatic ink pairs whose solids lie at least ``min_angle`` apart in
    hue (CO, MG, YV in CMYKOGV; CR, MG, YB in CMYKRGB). Light inks pair with
    nothing their parent does not."""
    h, c = solid_hues(printer)
    out = []
    for i, j in itertools.combinations(range(printer.n), 2):
        if c[i] < min_chroma or c[j] < min_chroma:
            continue
        d = abs((h[i] - h[j] + 180.0) % 360.0 - 180.0)
        if d >= min_angle:
            out.append((i, j))
    return out


# --- NC1 / NC2: forward ---------------------------------------------------------
def nc1_ramps(prof, printer, reader, intent="r", steps: int = 33) -> dict:
    n = printer.n
    t = np.linspace(0, 1, steps)
    per = {}
    worst_fwd, purity = [], []
    for i, letter in enumerate(printer.letters):
        dev = np.zeros((steps, n))
        dev[:, i] = t
        truth = printer.lab_rel(dev)
        pred = cmm.a2b(prof, dev, reader)
        de = colour.de2000(pred, truth)
        # inverse: the tint's own Lab -> device -> printed; purity = share of
        # the ink mass that is this ink (1 = reproduced with the ink alone)
        inv = _b2a(prof, truth[1:], reader, intent)
        printed = printer.lab_rel(inv)
        de_b = colour.de2000(printed, truth[1:])
        mass = inv.sum(1)
        pur = np.where(mass > 1e-6, inv[:, i] / np.maximum(mass, 1e-9), 1.0)
        per[letter] = {"a2b": stats(de), "b2a": stats(de_b),
                       "purity_min": float(pur.min()), "purity_median": float(np.median(pur)),
                       "solid_b2a_de": float(de_b[-1])}
        worst_fwd.append(de)
        purity.append(pur)
    allde = np.concatenate(worst_fwd)
    return {"a2b_all": stats(allde), "purity_min": float(np.min(np.concatenate(purity))),
            "per_ink": per}


def nc2_overprints(prof, printer, reader, steps: int = 9, n_sparse: int = 4000,
                   seed: int = 17, intent: str | None = "r") -> dict:
    n, tac = printer.n, printer.tac
    g = np.linspace(0, 1, steps)
    a, b = np.meshgrid(g, g, indexing="ij")
    pairs = {}
    allde = []
    for i, j in itertools.combinations(range(n), 2):
        dev = np.zeros((steps * steps, n))
        dev[:, i], dev[:, j] = a.ravel(), b.ravel()
        dev = dev[_tac_ok(dev, tac)]
        de = colour.de2000(cmm.a2b(prof, dev, reader), printer.lab_rel(dev))
        pairs[printer.letters[i] + printer.letters[j]] = stats(de)
        allde.append(de)
    allde = np.concatenate(allde)
    rng = np.random.default_rng(seed)
    regions = {}
    for k_on in (3, 4, n):
        dev = rng.uniform(0, 1, (n_sparse, n))
        if k_on < n:
            keep = np.argsort(rng.uniform(size=dev.shape), axis=1) < k_on
            dev = dev * keep
        dev = gmq._scale_tac(dev, tac)
        lab = printer.lab_rel(dev)
        de = colour.de2000(cmm.a2b(prof, dev, reader), lab)
        regions[f"max_{k_on}_inks"] = stats(de)
        # the inverse for the same colours (all reachable): colorimetric
        # B2A -> printed on the truth
        if intent is not None:
            pr = printer.lab_rel(_b2a(prof, lab, reader, intent))
            regions[f"b2a_max_{k_on}_inks"] = stats(colour.de2000(pr, lab))
    worst = max(pairs, key=lambda k: pairs[k]["p95"])
    return {"pairs_all": stats(allde), "worst_pair": worst,
            "worst_pair_stats": pairs[worst], "regions": regions, "per_pair": pairs}


# --- NC3: ink switching ---------------------------------------------------------
def _chroma_table(cloud: np.ndarray, l_bin: float = 2.5, h_bin: float = 5.0):
    c = np.hypot(cloud[:, 1], cloud[:, 2])
    h = np.degrees(np.arctan2(cloud[:, 2], cloud[:, 1])) % 360.0
    li = np.clip((cloud[:, 0] / l_bin).astype(int), 0, int(100 / l_bin))
    hi = np.minimum((h / h_bin).astype(int), int(360 / h_bin) - 1)
    tab = np.zeros((int(100 / l_bin) + 1, int(360 / h_bin)))
    np.maximum.at(tab, (li, hi), c)
    idx = np.arange(tab.shape[1])
    for r in range(tab.shape[0]):            # empty hue bins: interpolate
        good = tab[r] > 0
        if good.sum() >= 2 and not good.all():
            tab[r, ~good] = np.interp(idx[~good], idx[good], tab[r, good],
                                      period=tab.shape[1])
    return tab, l_bin, h_bin


def _max_chroma(tab, l_bin, h_bin, L, hue):
    row = tab[int(L / l_bin)]
    # smooth over +-2 hue bins (the cloud is sampled, not a boundary)
    k = np.array([0.25, 0.5, 1, 0.5, 0.25])
    ext = np.concatenate([row[-2:], row, row[:2]])
    sm = np.array([np.max(ext[i:i + 5] * k / k.max()) for i in range(len(row))])
    idx = np.minimum((hue / h_bin).astype(int), len(row) - 1)
    return sm[idx]


def _rise_fall(x: np.ndarray, amp: float = 0.05) -> int:
    """Number of times a channel rises by > amp and then falls by > amp
    (cyclic sweeps are unrolled once)."""
    count, lo, hi, state = 0, x[0], x[0], 0
    for v in x[1:]:
        if state >= 0:                   # looking for a rise, then a fall
            lo = min(lo, v)
            if v - lo > amp:
                state, hi = 1, v
        if state == 1:
            hi = max(hi, v)
            if hi - v > amp:
                count += 1
                state, lo = 0, v
    return count


def _switch_props(dev, letters, comp, extra, tac, step_deg):
    step = np.abs(np.diff(dev, axis=0))
    tv = step.sum(0)
    net = np.abs(dev[-1] - dev[0])
    on = dev > 0.02
    co = np.zeros(len(dev), bool)
    for i, j in comp:
        co |= (dev[:, i] > 0.05) & (dev[:, j] > 0.05)
    return {"rise_fall": {letters[i]: _rise_fall(dev[:, i]) for i in range(dev.shape[1])},
            "tv_excess": float((tv - net).sum()),
            "max_jump_per_deg": float(step.max() / step_deg),
            "inks_on_max": int(on.sum(1).max()), "inks_on_mean": float(on.sum(1).mean()),
            "complementary_share": float(co.mean()),
            "tac_max": float(dev.sum(1).max() * 100)}


def nc3_switching(prof, printer, reader, intent="r", cloud=None,
                  levels=(30.0, 45.0, 60.0, 75.0), fracs=(0.5, 0.85)) -> dict:
    cloud = gmq.truth_cloud(printer) if cloud is None else cloud
    tab, lb, hb = _chroma_table(cloud)
    comp = complementary_pairs(printer)
    extra = extra_ink_index(printer.letters)
    hues = np.arange(0.0, 360.0, 1.0)
    sweeps = {}
    agg = {"rise_fall_excess": 0, "tv_excess": [], "max_jump": [], "inks_on_max": 0,
           "complementary_share": [], "de": []}
    for L in levels:
        cmax = _max_chroma(tab, lb, hb, L, hues)
        for f in fracs:
            C = f * cmax
            lab = np.stack([np.full_like(hues, L), C * np.cos(np.radians(hues)),
                            C * np.sin(np.radians(hues))], 1)
            lab = np.vstack([lab, lab[:1]])              # close the circle
            dev = _b2a(prof, lab, reader, intent)
            printed = printer.lab_rel(dev)
            de = colour.de2000(printed, lab)
            inside = in_gamut(lab, cloud)
            p = _switch_props(dev, printer.letters, comp, extra, printer.tac, 1.0)
            p["de_in_gamut"] = stats(de[inside])
            p["in_gamut_share"] = float(inside.mean())
            agg.setdefault("de_in", []).append(de[inside])
            # expected: each chromatic ink enters and leaves at most once per
            # circle; every further rise-and-fall is a switch
            exc = sum(max(0, v - 1) for v in p["rise_fall"].values())
            p["rise_fall_excess"] = int(exc)
            p["de"] = stats(de)
            sweeps[f"L{L:.0f}-f{f:.2f}"] = p
            agg["rise_fall_excess"] += exc
            agg["tv_excess"].append(p["tv_excess"])
            agg["max_jump"].append(p["max_jump_per_deg"])
            agg["inks_on_max"] = max(agg["inks_on_max"], p["inks_on_max"])
            agg["complementary_share"].append(p["complementary_share"])
            agg["de"].append(de)
    # grey: extra ink on the neutral axis (L* from the darkest neutral + 2)
    neut = np.hypot(cloud[:, 1], cloud[:, 2]) < 3.0
    black_l = float(cloud[neut, 0].min()) if neut.any() else 10.0
    ls = np.arange(np.ceil(black_l + 2.0), 99.0, 0.5)
    nd = _b2a(prof, np.stack([ls, 0 * ls, 0 * ls], 1), reader, intent)
    grey = {"extra_ink_max": float(nd[:, extra].sum(1).max()) if extra else 0.0,
            "extra_ink_mean": float(nd[:, extra].sum(1).mean()) if extra else 0.0,
            "inks_on_max": int((nd > 0.02).sum(1).max()),
            "rise_fall": {printer.letters[i]: _rise_fall(nd[:, i])
                          for i in range(printer.n)}}
    grey["rise_fall_excess"] = int(sum(max(0, v - 1) for v in grey["rise_fall"].values()))
    return {"complementary_pairs": ["".join(printer.letters[k] for k in pr) for pr in comp],
            "rise_fall_excess_total": int(agg["rise_fall_excess"]),
            "tv_excess_max": float(max(agg["tv_excess"])),
            "max_jump_per_deg": float(max(agg["max_jump"])),
            "inks_on_max": int(agg["inks_on_max"]),
            "complementary_share_max": float(max(agg["complementary_share"])),
            "de": stats(np.concatenate(agg["de"])),
            "de_in_gamut": stats(np.concatenate(agg["de_in"])),
            "grey": grey, "sweeps": sweeps}


def in_gamut(lab: np.ndarray, cloud: np.ndarray, tol: float = 2.0) -> np.ndarray:
    """True where a truth colour lies within ``tol`` dE76 of the target (the
    truth cloud is 60,000 TAC-respecting prints: a sampled gamut, so a small
    tolerance; colours deeper inside always have a neighbour)."""
    _, first = np.unique(np.floor(cloud).astype(np.int64), axis=0, return_index=True)
    thin = cloud[first]
    out = np.zeros(len(lab), bool)
    for s in range(0, len(lab), 256):
        d = ((lab[s:s + 256, None, :] - thin[None, :, :]) ** 2).sum(2).min(1)
        out[s:s + 256] = d <= tol * tol
    return out


# --- NC4: gamut extension -------------------------------------------------------
def nc4_extension(prof, printer, reader, intent="r", n: int = 30000, seed: int = 29,
                  min_gap: float = 3.0) -> dict:
    extra = extra_ink_index(printer.letters)
    rng = np.random.default_rng(seed)
    k = printer.n
    dev = rng.uniform(0, 1, (n, k))
    edge = (rng.uniform(0, 1, (n // 2, k)) > 0.6) * rng.uniform(0.4, 1, (n // 2, k))
    dev = gmq._scale_tac(np.vstack([dev, edge]), printer.tac)
    lab = printer.lab_rel(dev)
    cm = dev.copy()
    cm[:, extra] = 0.0
    cdev = rng.uniform(0, 1, (4 * n, k))
    cedge = (rng.uniform(0, 1, (2 * n, k)) > 0.5) * rng.uniform(0.3, 1, (2 * n, k))
    cdev = np.vstack([cdev, cedge])
    # volumes from EQUAL sample counts (the dense CMYK cloud is for the gap)
    vdev = dev.copy()
    vdev[:, extra] = 0.0
    vlab = printer.lab_rel(gmq._scale_tac(vdev, printer.tac))
    cdev[:, extra] = 0.0
    cdev = gmq._scale_tac(cdev, printer.tac)
    clab = printer.lab_rel(cdev)
    # nearest CMYK-only colour (dE76 prefilter on a voxel index, then dE00)
    _, first = np.unique(np.floor(clab / 1.0).astype(np.int64), axis=0, return_index=True)
    thin = clab[np.sort(first)]                        # one colour per 1-unit voxel
    idx = np.empty((len(lab), 8), int)
    for s in range(0, len(lab), 256):
        d = ((lab[s:s + 256, None, :] - thin[None, :, :]) ** 2).sum(2)
        idx[s:s + 256] = np.argpartition(d, 8, axis=1)[:, :8]
    gap = np.min(np.stack([colour.de2000(lab, thin[idx[:, j]]) for j in range(8)], 1), 1)
    ext = gap > min_gap
    out = {"n_targets": int(ext.sum()), "share_of_gamut_samples": float(ext.mean())}
    vox = lambda L: len(np.unique(np.floor(L / 3.0).astype(int), axis=0))
    out["volume_voxels_all"] = vox(lab)
    out["volume_voxels_cmyk"] = vox(vlab)
    out["volume_gain"] = float(out["volume_voxels_all"] / max(out["volume_voxels_cmyk"], 1))
    if ext.sum():
        tgt = lab[ext]
        ink = _b2a(prof, tgt, reader, intent)
        printed = printer.lab_rel(ink)
        de = colour.de2000(printed, tgt)
        used = ink[:, extra].sum(1) > 0.02 if extra else np.zeros(len(ink), bool)
        out.update({"b2a": stats(de), "within_1": float((de <= 1.0).mean()),
                    "within_2": float((de <= 2.0).mean()),
                    "extra_ink_used_share": float(used.mean()),
                    "gap_of_targets": stats(gap[ext]),
                    "printed_gap_recovered_median": float(np.median(
                        np.clip(1.0 - de / gap[ext], -1, 1)))})
    return out


# --- NC5: gradients -------------------------------------------------------------
def nc5_gradients(prof, printer, reader, intent="r", cloud=None, n_pairs: int = 120,
                  steps: int = 64, seed: int = 31) -> dict:
    cloud = gmq.truth_cloud(printer) if cloud is None else cloud
    gam = gmq.TruthGamut(cloud)
    rng = np.random.default_rng(seed)
    inside = cloud[gam.depth(cloud) > 4.0]
    ends = inside[rng.choice(len(inside), (n_pairs, 2))]
    white = np.array([100.0, 0, 0])
    black = np.array([gam.black_l + 1.0, 0, 0])
    ends = np.vstack([ends, np.stack([np.tile(white, (n_pairs // 2, 1)),
                                      inside[rng.choice(len(inside), n_pairs // 2)]], 1),
                      np.stack([inside[rng.choice(len(inside), n_pairs // 2)],
                                np.tile(black, (n_pairs // 2, 1))], 1)])
    t = np.linspace(0, 1, steps)[:, None]
    paths = np.concatenate([a * (1 - t) + b * t for a, b in ends])
    dev = _b2a(prof, paths, reader, intent)
    printed = printer.lab_rel(dev).reshape(len(ends), steps, 3)
    tgt = paths.reshape(len(ends), steps, 3)
    dev = dev.reshape(len(ends), steps, -1)
    ps = colour.de2000(printed[:, 1:].reshape(-1, 3), printed[:, :-1].reshape(-1, 3))
    ts = colour.de2000(tgt[:, 1:].reshape(-1, 3), tgt[:, :-1].reshape(-1, 3))
    ratio = ps / np.maximum(ts, 1e-6)
    jumps = (ps > 3.0 * ts) & (ps > 1.0)
    d2 = np.linalg.norm(np.diff(printed, 2, axis=1), axis=2)
    dstep = np.abs(np.diff(dev, axis=1)).max(2)
    return {"n_ramps": int(len(ends)), "step_ratio": stats(ratio),
            "step_ratio_p99": float(np.percentile(ratio, 99)),
            "visible_jumps": int(jumps.sum()),
            "ramps_with_jump": int(jumps.reshape(len(ends), -1).any(1).sum()),
            "max_d2": float(d2.max()), "d2_p99": float(np.percentile(d2, 99)),
            "max_device_step": float(dstep.max()),
            "tac_max": float(dev.sum(2).max() * 100)}


class ProxyPrinter:
    """A stand-in printer for real data (no truth printer): device -> media-
    relative Lab through an independent model, either an Argyll MPP
    (``mpp:PATH``, mpplu, media-relative to its own white) or an ICC A2B1
    (``icc:PATH``, Argyll icclu). Labelled "proxy" in every result: an
    estimate of the print, not the print."""

    is_additive = False

    def __init__(self, spec: str, letters: list[str], tac: float | None):
        self.kind, path = spec.split(":", 1)
        self.path = Path(path)
        self._letters = list(letters)
        self.tac = tac
        self.n = len(letters)
        self.id = f"proxy-{self.kind}"
        self._white = None

    @property
    def letters(self):
        return self._letters

    def _mpp_xyz(self, dev):
        import subprocess
        inp = "\n".join(" ".join(f"{v:.6f}" for v in r) for r in dev) + "\n"
        out = subprocess.run(["/Applications/Argyll/bin/mpplu", "-px", str(self.path)],
                             input=inp, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=3600,
                             check=True).stdout
        rows = [[float(x) for x in ln.split("->")[1].split("[")[0].split()[:3]]
                for ln in out.splitlines() if "->" in ln]
        return np.array(rows) * 100.0

    def lab_rel(self, device, illuminant: str = "D50"):
        dev = np.clip(np.atleast_2d(np.asarray(device, float)), 0, 1)
        if self.kind == "icc":
            return cmm.a2b(self.path, dev, "argyll")
        if self._white is None:
            self._white = self._mpp_xyz(np.zeros((1, self.n)))[0]
        return colour.media_relative_lab(self._mpp_xyz(dev), self._white)


def evaluate(profile, printer_id: str, reader: str = "argyll", intent: str = "r",
             tests: str = "1,2,3,4,5", cloud_cache: Path | None = None,
             proxy: str | None = None, letters: str | None = None,
             tac: float | None = None) -> dict:
    if proxy:
        from benchmarks.research.printers import split_letters
        printer = ProxyPrinter(proxy, split_letters(letters), tac)
    else:
        printer = build_printers()[printer_id]
    cloud = gmq.truth_cloud(printer, cache=cloud_cache)
    out = {"profile": str(profile), "printer": printer_id if not proxy else f"{printer_id} via {proxy}",
           "truth": "proxy" if proxy else "printer", "reader": reader,
           "intent": intent, "letters": printer.letters, "tac": printer.tac}
    t = set(tests.split(","))
    if "1" in t:
        out["NC1"] = nc1_ramps(profile, printer, reader, intent)
    if "2" in t:
        out["NC2"] = nc2_overprints(profile, printer, reader, intent=intent)
    if "3" in t:
        out["NC3"] = nc3_switching(profile, printer, reader, intent, cloud)
    if "4" in t:
        out["NC4"] = nc4_extension(profile, printer, reader, intent)
    if "5" in t:
        out["NC5"] = nc5_gradients(profile, printer, reader, intent, cloud)
    lim = [out[k].get("tac_max") for k in ("NC5",) if k in out]
    if "NC3" in out:
        lim.append(max(s["tac_max"] for s in out["NC3"]["sweeps"].values()))
    if lim:
        out["NC6_tac_max"] = float(max(lim))
        out["NC6_over_limit"] = bool(printer.tac and max(lim) > printer.tac + 1.0)
    return out


def headline(r: dict) -> dict:
    """The row a report table prints."""
    h = {}
    if "NC1" in r:
        h["NC1 ramp A2B p95"] = r["NC1"]["a2b_all"]["p95"]
        h["NC1 purity min"] = r["NC1"]["purity_min"]
    if "NC2" in r:
        h["NC2 pairs A2B p95"] = r["NC2"]["pairs_all"]["p95"]
        h["NC2 <=3 inks A2B med"] = r["NC2"]["regions"]["max_3_inks"]["median"]
        h["NC2 <=3 inks A2B p95"] = r["NC2"]["regions"]["max_3_inks"]["p95"]
        h["NC2 all inks A2B med"] = r["NC2"]["regions"][f"max_{len(r['letters'])}_inks"]["median"]
        if "b2a_max_3_inks" in r["NC2"]["regions"]:
            h["NC2 <=3 inks B2A med"] = r["NC2"]["regions"]["b2a_max_3_inks"]["median"]
            h["NC2 <=3 inks B2A p95"] = r["NC2"]["regions"]["b2a_max_3_inks"]["p95"]
            h["NC2 all inks B2A med"] = r["NC2"]["regions"][f"b2a_max_{len(r['letters'])}_inks"]["median"]
    if "NC3" in r:
        d = r["NC3"].get("de_in_gamut", r["NC3"]["de"])
        h["NC3 hue-circle B2A med"] = d["median"]
        h["NC3 hue-circle B2A p95"] = d["p95"]
        h["NC3 rise-fall excess"] = r["NC3"]["rise_fall_excess_total"]
        h["NC3 TV excess max"] = r["NC3"]["tv_excess_max"]
        h["NC3 jump/deg max"] = r["NC3"]["max_jump_per_deg"]
        h["NC3 inks on max"] = r["NC3"]["inks_on_max"]
        h["NC3 complementary share"] = r["NC3"]["complementary_share_max"]
        h["NC3 grey extra ink max"] = r["NC3"]["grey"]["extra_ink_max"]
        h["NC3 grey rise-fall excess"] = r["NC3"]["grey"]["rise_fall_excess"]
    if "NC4" in r and "b2a" in r["NC4"]:
        h["NC4 ext B2A med"] = r["NC4"]["b2a"]["median"]
        h["NC4 ext within 2"] = r["NC4"]["within_2"]
        h["NC4 extra ink used"] = r["NC4"]["extra_ink_used_share"]
    if "NC5" in r:
        h["NC5 step ratio p99"] = r["NC5"]["step_ratio_p99"]
        h["NC5 visible jumps"] = r["NC5"]["visible_jumps"]
        h["NC5 max d2"] = r["NC5"]["max_d2"]
    if "NC6_tac_max" in r:
        h["NC6 TAC max"] = r["NC6_tac_max"]
    return h


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("printer")
    ap.add_argument("--reader", default="argyll")
    ap.add_argument("--intent", default="r")
    ap.add_argument("--tests", default="1,2,3,4,5")
    ap.add_argument("--out")
    ap.add_argument("--proxy", help="mpp:PATH or icc:PATH (real data: no truth printer)")
    ap.add_argument("--letters", help="ink letters for --proxy, e.g. CMYKOGV")
    ap.add_argument("--tac", type=float)
    a = ap.parse_args(argv)
    r = evaluate(a.profile, a.printer, a.reader, a.intent, a.tests, proxy=a.proxy,
                 letters=a.letters, tac=a.tac)
    r["headline"] = headline(r)
    txt = json.dumps(r, indent=1)
    if a.out:
        Path(a.out).write_text(txt, encoding="utf-8")
    print(json.dumps(r["headline"], indent=1))


if __name__ == "__main__":
    main()
