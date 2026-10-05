"""Agent 25: how much of an out-of-gamut colour the rel. col. clip keeps.

sRGB and Adobe RGB cube surfaces (33 x 33 per face) that the truth gamut
cannot print (depth < -3): dE00 printed vs source (mean, p95), printed vs
source lightness (mean |dL|, mean dL), chroma kept (median printed C* /
truth-gamut max C* is not known, so printed C* / source C*), and the same
for pale (L* > 85) and dark (L* < 30) subsets.

    python -m benchmarks.research.oog25.oogstats OUT NAME TAG=PROFILE ...
"""
import sys
from pathlib import Path

import numpy as np


def surface():
    g = np.linspace(0, 1, 33)
    faces = []
    for ax in range(3):
        for val in (0.0, 1.0):
            u, v = np.meshgrid(g, g, indexing="ij")
            f = np.zeros((u.size, 3))
            o = [i for i in range(3) if i != ax]
            f[:, ax] = val
            f[:, o[0]] = u.ravel()
            f[:, o[1]] = v.ravel()
            faces.append(f)
    return np.unique(np.vstack(faces), axis=0)


def stats(ctx, space="srgb"):
    from benchmarks.research import colour, run
    from benchmarks.research.blindspots import xf
    surf = surface()
    srcp = "srgb" if space == "srgb" else run.SOURCE_GAMUT
    src = xf.lcms(srcp, "lab", surf, "r")
    pr = ctx.truth_lab(ctx.rgb2dev(srcp, surf, "r"))
    oog = ctx.gamut.depth(src) < -3
    out = {}
    for nm, m in (("all", oog), ("pale", oog & (src[:, 0] > 85)),
                  ("dark", oog & (src[:, 0] < 30))):
        if not m.any():
            continue
        de = colour.de2000(pr[m], src[m])
        dl = pr[m, 0] - src[m, 0]
        cs, cp = np.hypot(*src[m, 1:].T), np.hypot(*pr[m, 1:].T)
        out[nm] = {"n": int(m.sum()), "de_mean": float(de.mean()),
                   "de_p95": float(np.percentile(de, 95)),
                   "dl_abs": float(np.abs(dl).mean()), "dl_mean": float(dl.mean()),
                   "c_kept": float(np.median(cp / np.maximum(cs, 1e-6)))}
    return out


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from benchmarks.research.blindspots import hunt_run
    out, name = Path(sys.argv[1]).resolve(), sys.argv[2]
    for spec in sys.argv[3:]:
        tag, p = spec.split("=", 1)
        ctx, _ = hunt_run.context(out, name, Path(p).resolve())
        for sp in ("srgb", "adobe"):
            s = stats(ctx, sp)
            print(f"{name:6s} {tag:12s} {sp:5s} " + " | ".join(
                f"{k} n{v['n']} dE {v['de_mean']:.2f}/{v['de_p95']:.2f} |dL| {v['dl_abs']:.2f} "
                f"dL {v['dl_mean']:+.2f} C {v['c_kept']:.2f}" for k, v in s.items()), flush=True)


if __name__ == "__main__":
    main()
