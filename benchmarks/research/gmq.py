"""Gamut-mapping quality: objective properties of the perceptual and
saturation intents (Agent 9, research D-08; design in
Findings/agent9-01-independence.md section 1).

Perceptual and saturation rendering have no ground truth, so nothing here
scores "closeness to colprof". Each property M1-M11 is measured END TO END:
a source colour (ClayRGB 1998, analytic primaries, D50 media-relative PCS)
goes through the profile's B2A table for the intent, read by a real CMM
(Argyll icclu or littleCMS 2), and the device values are printed on the
battery's 1 nm truth printer. The truth gamut comes from the truth printer.
No engine code is imported (the referee must not share code with what it
judges).

    python -m benchmarks.research.gmq PROFILE.icc PRINTER_ID [--reader argyll]
"""
from __future__ import annotations

import json
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np

from benchmarks.research import cmm, colour

INTENT_CODE = {"p": 0, "r": 1, "s": 2}

# --- source: ClayRGB 1998 (= Adobe RGB 1998 primaries), analytic ---------
_ADOBE_XY = np.array([[0.64, 0.33], [0.21, 0.71], [0.15, 0.06]])
_D65_XY = np.array([0.3127, 0.3290])


def _rgb_to_xyz_matrix() -> np.ndarray:
    xy = _ADOBE_XY
    xr = np.stack([xy[:, 0] / xy[:, 1], np.ones(3),
                   (1 - xy[:, 0] - xy[:, 1]) / xy[:, 1]], 0)
    w = _D65_XY
    s = np.linalg.solve(xr, np.array([w[0] / w[1], 1.0,
                                      (1 - w[0] - w[1]) / w[1]]))
    return xr * s[None, :]


def _bradford(src_white: np.ndarray, dst_white: np.ndarray) -> np.ndarray:
    b = colour.BRADFORD
    return np.linalg.inv(b) @ np.diag((b @ dst_white) / (b @ src_white)) @ b


_D65_XYZ = np.array([95.047, 100.0, 108.883])


def source_lab(rgb: np.ndarray) -> np.ndarray:
    """ClayRGB device 0..1 -> D50 Lab (ICC relative PCS of a matrix profile)."""
    lin = np.clip(rgb, 0.0, 1.0) ** (563.0 / 256.0)
    xyz65 = (_rgb_to_xyz_matrix() @ lin.T).T * 100.0
    xyz50 = (_bradford(_D65_XYZ, colour.D50) @ xyz65.T).T
    return colour.xyz_to_lab(xyz50)


# --- IPT (Ebner and Fairchild 1998), for hue angles ------------------------
_IPT_LMS = np.array([[0.4002, 0.7075, -0.0807],
                     [-0.2280, 1.1500, 0.0612],
                     [0.0, 0.0, 0.9184]])
_IPT_IPT = np.array([[0.4000, 0.4000, 0.2000],
                     [4.4550, -4.8510, 0.3960],
                     [0.8056, 0.3572, -1.1628]])


def lab_to_ipt(lab: np.ndarray) -> np.ndarray:
    xyz50 = colour.lab_to_xyz(lab)
    xyz65 = (_bradford(colour.D50, _D65_XYZ) @ xyz50.T).T / 100.0
    lms = (_IPT_LMS @ xyz65.T).T
    lmsp = np.sign(lms) * np.abs(lms) ** 0.43
    return (_IPT_IPT @ lmsp.T).T


def _hue_deg(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.degrees(np.arctan2(b, a)) % 360.0


def _dhue(h1: np.ndarray, h2: np.ndarray) -> np.ndarray:
    return np.abs(((h2 - h1 + 180.0) % 360.0) - 180.0)


# --- the source sets -------------------------------------------------------
_HUES = np.array([[1, 0, 0], [1, .5, 0], [1, 1, 0], [.5, 1, 0], [0, 1, 0],
                  [0, 1, .5], [0, 1, 1], [0, .5, 1], [0, 0, 1], [.5, 0, 1],
                  [1, 0, 1], [1, 0, .5]], float)
_CORNERS = np.array([[1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 1, 1], [0, 0, 1],
                     [1, 0, 1]], float)


def source_sets(lattice: int = 17, ramp: int = 65, neutral: int = 129) -> dict:
    """Device (ClayRGB) points of every set, and how they are laid out."""
    g = np.linspace(0.0, 1.0, lattice)
    u = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
    t = np.linspace(0.0, 1.0, ramp)[:, None]
    tn = np.linspace(0.0, 1.0, neutral)[:, None]
    n = tn * np.ones((1, 3))                               # black -> white
    ramps, kinds = [], []
    for h in _HUES:
        ramps.append(1.0 + t * (h - 1.0)); kinds.append("white_to_colour")
        ramps.append(h * (1.0 - t)); kinds.append("colour_to_black")
        ramps.append(0.5 + t * (h - 0.5)); kinds.append("grey_to_colour")
    for i in range(6):
        a, b = _CORNERS[i], _CORNERS[(i + 1) % 6]
        ramps.append(a + t * (b - a)); kinds.append("hue_sweep")
    return {"U": u, "N": n, "R": ramps, "R_kind": kinds, "lattice": lattice}


# --- the truth gamut ---------------------------------------------------------
def _scale_tac(dev: np.ndarray, tac: float | None) -> np.ndarray:
    if tac is None:
        return dev
    total = dev.sum(1)
    over = total > tac / 100.0
    dev = dev.copy()
    dev[over] *= (tac / 100.0 / total[over])[:, None]
    return dev


def truth_cloud(printer, n: int = 60000, seed: int = 5,
                cache: Path | None = None) -> np.ndarray:
    """Lab of TAC-respecting truth device points: random interior, random
    cube faces, and a dark set (every channel 0.6-1), then scaled to TAC."""
    if cache is not None and cache.exists():
        return np.load(cache)["lab"]
    rng = np.random.default_rng(seed)
    k = printer.n
    inner = rng.uniform(0, 1, (n // 3, k))
    face = rng.uniform(0, 1, (n // 3, k))
    face[np.arange(len(face)), rng.integers(0, k, len(face))] = \
        rng.integers(0, 2, len(face)).astype(float)
    # faces with several channels pinned (edges of the cube: solids, 2-ink)
    edge = (rng.uniform(0, 1, (n // 6, k)) > 0.5).astype(float) \
        * rng.uniform(0.5, 1, (n // 6, k))
    dark = rng.uniform(0.6, 1.0, (n // 6, k))
    dev = np.vstack([inner, face, edge, dark])
    if not printer.is_additive:
        dev = _scale_tac(dev, printer.tac)
    lab = printer.lab_rel(dev)
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, lab=lab)
    return lab


class TruthGamut:
    """Radial maximum per direction about L* 50 (72 hue x 36 elevation)."""

    NH, NE = 72, 36

    def __init__(self, cloud: np.ndarray) -> None:
        self.centre = np.array([50.0, 0.0, 0.0])
        hb, eb, r = self._bins(cloud)
        tab = np.zeros((self.NH, self.NE))
        np.maximum.at(tab, (hb, eb), r)
        for e in range(self.NE):              # fill empty bins along hue
            col = tab[:, e]
            good = col > 0
            if good.any() and not good.all():
                idx = np.arange(self.NH)
                col[~good] = np.interp(idx[~good], idx[good], col[good],
                                       period=self.NH)
        for e in range(self.NE):
            if not (tab[:, e] > 0).any():
                near = [q for q in range(self.NE) if (tab[:, q] > 0).any()]
                q = min(near, key=lambda q: abs(q - e))
                tab[:, e] = tab[:, q]
        self.tab = tab
        chroma = np.hypot(cloud[:, 1], cloud[:, 2])
        neut = chroma < 3.0
        self.black_l = float(cloud[neut, 0].min()) if neut.any() else float(
            cloud[:, 0].min())
        self.min_l = float(cloud[:, 0].min())

    def _bins(self, lab):
        rel = lab - self.centre
        r = np.linalg.norm(rel, axis=1)
        hue = np.arctan2(rel[:, 2], rel[:, 1]) % (2 * np.pi)
        elev = np.arcsin(np.clip(rel[:, 0] / np.maximum(r, 1e-9), -1, 1))
        hb = np.minimum((hue / (2 * np.pi) * self.NH).astype(int), self.NH - 1)
        eb = np.minimum(((elev + np.pi / 2) / np.pi * self.NE).astype(int),
                        self.NE - 1)
        return hb, eb, r

    def depth(self, lab: np.ndarray) -> np.ndarray:
        """Positive = inside by that many dE76 (radially), negative = out."""
        hb, eb, r = self._bins(lab)
        return self.tab[hb, eb] - r


# --- reading an intent -------------------------------------------------------
def b2a_intent(path: Path, lab: np.ndarray, reader: str, intent: str,
               argyll_bin: str = "/Applications/Argyll/bin") -> np.ndarray:
    path = Path(path)
    n, _ = cmm._profile_n(path)
    if reader == "argyll":
        inp = "\n".join(" ".join(f"{v:.7f}" for v in r) for r in lab) + "\n"
        out = subprocess.run(
            [str(Path(argyll_bin) / "icclu"), "-v0", "-fb", f"-i{intent}",
             "-pl", str(path)], input=inp, capture_output=True, text=True,
            encoding="utf-8", timeout=900, check=True).stdout
        arr = np.array([[float(x) for x in ln.split()[:n]]
                        for ln in out.splitlines() if ln.strip()])
        if arr.shape != (len(lab), n):
            raise RuntimeError(f"icclu returned {arr.shape}")
        return np.clip(arr, 0.0, 1.0)
    if reader == "lcms":
        lib = cmm._lcms()
        n, additive = cmm._profile_n(path)
        dfmt, dscale = cmm._dev_fmt(n, additive)
        lab_fmt = cmm._fmt(10, 3)
        hp = lib.cmsOpenProfileFromFile(str(path).encode(), b"r")
        hl = lib.cmsCreateLab4Profile(None)
        t = lib.cmsCreateTransform(hl, lab_fmt, hp, dfmt, INTENT_CODE[intent],
                                   cmm._NOOPT | cmm._NOCACHE)
        if not t:
            raise RuntimeError("lcms transform failed")
        src = np.ascontiguousarray(lab, dtype=np.float64)
        dst = np.zeros((len(lab), n))
        lib.cmsDoTransform(t, src.ctypes.data, dst.ctypes.data, len(lab))
        lib.cmsDeleteTransform(t)
        lib.cmsCloseProfile(hp)
        lib.cmsCloseProfile(hl)
        return np.clip(dst / dscale, 0.0, 1.0)
    raise KeyError(reader)


# --- the properties ------------------------------------------------------------
def _ramp_props(p_lab: np.ndarray, s_lab: np.ndarray, dev: np.ndarray,
                kind: str, depth: np.ndarray) -> dict:
    dp = np.diff(p_lab, axis=0)
    step = np.linalg.norm(dp, axis=1)
    d2 = np.linalg.norm(np.diff(p_lab, 2, axis=0), axis=1)
    med = float(np.median(step)) if len(step) else 0.0
    out = {"max_d2": float(d2.max()),
           "jump": float(step.max() / med) if med > 1e-9 else 0.0,
           "dev_d2": float(np.abs(np.diff(dev, 2, axis=0)).max())}
    ds = np.diff(s_lab[:, 0])
    dl = np.diff(p_lab[:, 0])
    if kind in ("white_to_colour", "colour_to_black", "neutral"):
        against = -np.sign(ds) * dl            # > 0 = moves against source
        bad = (against > 0.1) & (np.abs(ds) > 1e-6)
        out["l_rev"] = int(bad.sum())
        out["l_rev_max"] = float(against[bad].max()) if bad.any() else 0.0
    if kind == "grey_to_colour":
        c = np.hypot(p_lab[:, 1], p_lab[:, 2])
        dc = np.diff(c)
        out["c_rev"] = int((dc < -0.2).sum())
        src_step = colour.de2000(s_lab[:-1], s_lab[1:])
        prn_step = colour.de2000(p_lab[:-1], p_lab[1:])
        outside = (depth[:-1] < -3.0) & (depth[1:] < -3.0)
        if outside.any():
            out["plateau"] = float((prn_step[outside]
                                    < 0.15 * src_step[outside]).mean())
            out["outside_steps"] = int(outside.sum())
    return out


def evaluate(profile: Path | str, printer, reader: str = "argyll",
             intent: str = "p", gamut: TruthGamut | None = None,
             sets: dict | None = None, n_round: int = 2000,
             seed: int = 7) -> tuple[dict, dict]:
    """All properties of one intent of one profile under one reader.

    Returns (summary, per_point) where per_point holds the arrays the paired
    bootstrap needs (index-aligned across profiles of the same printer)."""
    sets = sets or source_sets()
    if gamut is None:
        gamut = TruthGamut(truth_cloud(printer))
    u_lab = source_lab(sets["U"])
    n_lab = source_lab(sets["N"])
    r_lab = [source_lab(r) for r in sets["R"]]
    rng = np.random.default_rng(seed)
    rt_dev = rng.uniform(0, 1, (n_round, printer.n))
    if not printer.is_additive:
        rt_dev = _scale_tac(rt_dev, printer.tac)
    rt_lab = printer.lab_rel(rt_dev)
    blocks = [u_lab, n_lab] + r_lab + [rt_lab]
    allp = np.vstack(blocks)
    dev = b2a_intent(Path(profile), allp, reader, intent)
    printed = printer.lab_rel(dev)
    cuts = np.cumsum([0] + [len(b) for b in blocks])
    sl = lambda i: slice(cuts[i], cuts[i + 1])
    pu, du = printed[sl(0)], dev[sl(0)]
    pn, dn = printed[sl(1)], dev[sl(1)]
    pr = [printed[sl(2 + i)] for i in range(len(r_lab))]
    dr = [dev[sl(2 + i)] for i in range(len(r_lab))]
    prt = printed[sl(len(blocks) - 1)]

    res: dict = {"reader": reader, "intent": intent}
    pp: dict = {}
    # M1 neutral
    black_l = float(pn[0, 0])
    printable = n_lab[:, 0] > black_l + 2.0
    cn = np.hypot(pn[:, 1], pn[:, 2])
    res["M1_neutral_C_mean"] = float(cn[printable].mean())
    res["M1_neutral_C_max"] = float(cn[printable].max())
    pp["M1"] = cn[printable]
    # M2 hue (IPT and CIELAB), U with source C* >= 10
    cs = np.hypot(u_lab[:, 1], u_lab[:, 2])
    m = cs >= 10.0
    ipt_s, ipt_p = lab_to_ipt(u_lab[m]), lab_to_ipt(pu[m])
    dh_ipt = _dhue(_hue_deg(ipt_s[:, 1], ipt_s[:, 2]),
                   _hue_deg(ipt_p[:, 1], ipt_p[:, 2]))
    dh_lab = _dhue(_hue_deg(u_lab[m, 1], u_lab[m, 2]),
                   _hue_deg(pu[m, 1], pu[m, 2]))
    w = cs[m] / cs[m].sum()
    res["M2_hue_ipt_wmean"] = float((dh_ipt * w).sum())
    res["M2_hue_ipt_p95"] = float(np.percentile(dh_ipt, 95))
    res["M2_hue_lab_wmean"] = float((dh_lab * w).sum())
    pp["M2"] = dh_ipt
    # ramps: M3, M3c, M4, M6, M10
    rows = []
    nprops = _ramp_props(pn, n_lab, dn, "neutral", gamut.depth(n_lab))
    for i, kind in enumerate(sets["R_kind"]):
        rows.append(_ramp_props(pr[i], r_lab[i], dr[i], kind,
                                gamut.depth(r_lab[i])))
    rows_all = rows + [nprops]
    res["M3_L_reversals"] = int(sum(r.get("l_rev", 0) for r in rows_all))
    res["M3_L_rev_max"] = float(max(r.get("l_rev_max", 0.0) for r in rows_all))
    res["M3_neutral_L_reversals"] = nprops["l_rev"]
    res["M3c_C_reversals"] = int(sum(r.get("c_rev", 0) for r in rows))
    res["M4_d2_median"] = float(np.median([r["max_d2"] for r in rows_all]))
    res["M4_d2_max"] = float(max(r["max_d2"] for r in rows_all))
    res["M4_jump_median"] = float(np.median([r["jump"] for r in rows_all]))
    res["M4_jump_max"] = float(max(r["jump"] for r in rows_all))
    pl = [r["plateau"] for r in rows if "plateau" in r]
    res["M6_plateau_mean"] = float(np.mean(pl)) if pl else None
    res["M6_outside_ramps"] = len(pl)
    res["M10_sep_d2_median"] = float(np.median([r["dev_d2"] for r in rows_all]))
    res["M10_sep_d2_max"] = float(max(r["dev_d2"] for r in rows_all))
    res["M10_neutral_sep_d2"] = nprops["dev_d2"]
    letters = printer.letters
    if "K" in letters:
        k = dn[:, letters.index("K")][::-1]               # white -> black
        res["M10_K_reversals"] = int((np.diff(k) < -0.01).sum())
    # M5 core preservation
    depth_u = gamut.depth(u_lab)
    core = depth_u >= 3.0
    outside = depth_u <= -3.0
    de_u = colour.de2000(u_lab, pu)
    res["M5_core_n"] = int(core.sum())
    res["M5_core_de_median"] = float(np.median(de_u[core])) if core.any() else None
    res["M5_core_de_p95"] = float(np.percentile(de_u[core], 95)) if core.any() else None
    pp["M5"] = de_u[core]
    # M7 detail / local contrast on lattice neighbours
    L = sets["lattice"]
    idx = np.arange(L ** 3).reshape(L, L, L)
    pairs = np.vstack([np.stack([idx[:-1].ravel(), idx[1:].ravel()], 1),
                       np.stack([idx[:, :-1].ravel(), idx[:, 1:].ravel()], 1),
                       np.stack([idx[:, :, :-1].ravel(), idx[:, :, 1:].ravel()], 1)])
    sde = colour.de2000(u_lab[pairs[:, 0]], u_lab[pairs[:, 1]])
    pde = colour.de2000(pu[pairs[:, 0]], pu[pairs[:, 1]])
    ratio = pde / np.maximum(sde, 1e-6)
    pc = core[pairs[:, 0]] & core[pairs[:, 1]]
    po = outside[pairs[:, 0]] & outside[pairs[:, 1]]
    res["M7_ratio_median"] = float(np.median(ratio))
    res["M7_ratio_p05"] = float(np.percentile(ratio, 5))
    res["M7_core_p05"] = float(np.percentile(ratio[pc], 5)) if pc.any() else None
    res["M7_outside_median"] = float(np.median(ratio[po])) if po.any() else None
    res["M7_outside_p05"] = float(np.percentile(ratio[po], 5)) if po.any() else None
    pp["M7"] = ratio
    # M8 black point use, M8w white
    res["M8_black_L"] = black_l
    res["M8_black_C"] = float(cn[0])
    res["M8_truth_neutral_black_L"] = gamut.black_l
    res["M8_black_gap"] = black_l - gamut.black_l
    white = dn[-1]
    res["M8w_white_ink"] = float(white.sum() * 100.0) if not printer.is_additive \
        else float((1.0 - white).sum() * 100.0)
    res["M8w_white_de"] = float(colour.de2000(n_lab[-1:], pn[-1:])[0])
    # M9 ink limit
    if not printer.is_additive and printer.tac is not None:
        tot = dev[: cuts[-2]].sum(1) * 100.0
        res["M9_ink_max"] = float(tot.max())
        res["M9_over_share"] = float((tot > printer.tac + 1.0).mean())
        res["M9_tac"] = printer.tac
    # M11 round trip on printable colours
    de_rt = colour.de2000(rt_lab, prt)
    res["M11_rt_median"] = float(np.median(de_rt))
    res["M11_rt_p95"] = float(np.percentile(de_rt, 95))
    pp["M11"] = de_rt
    res["outside_share_U"] = float(outside.mean())
    return res, pp


def main(argv=None) -> None:
    import argparse
    from benchmarks.research.printers import build_printers
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("printer")
    ap.add_argument("--reader", default="argyll")
    ap.add_argument("--intent", default="p")
    a = ap.parse_args(argv)
    p = build_printers()[a.printer]
    res, _ = evaluate(a.profile, p, a.reader, a.intent)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
