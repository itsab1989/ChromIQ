"""Agent 25: the relative-colorimetric rows of Agent 23's blind-spot hunt
(F-15, F-17) plus in-gamut accuracy and safety rows, on one profile.

    python -m benchmarks.research.oog25.evalr OUT NAME PROFILE.icc RESULT.json

OUT/NAME follow Agent 23's hunt_run (truth printer or real-set proxy).
Rows (every one printed on the truth):
  F-15: H11 pale sRGB (r): share dL>5, p99, max; H2 24 sRGB/Adobe ramps (r):
        L* reversal steps, max swing, max jump ratio; H6 image new contours
        (r float and r+BPC 8-bit app path); H4 light tint ramps (r) reversals
  F-17: sRGB blue / 60-60-255 IPT and CAM16 hue shift; H8 sRGB cube surface
        out-of-gamut clip hue (IPT p95, blue-sector mean; CIELAB p95)
  in gamut: 6000 printable colours (random device values through the
        truth) -> B2A1 -> truth, dE00 median / p95 / max; the pale subset
        (L* > 85) separately; Lab neutral axis L* 5..100 dE00 and C*
  safety: H1 sRGB grey r and r+BPC (reversals, swing, C* max), ink in paper
        white (r, a), black L*, max TAC seen vs limit.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_k, "1")


def cam16_hue(lab):
    from workflow.profile_engine.ucs import print_ucs
    u = print_ucs().lab_to_ucs(lab)
    return np.degrees(np.arctan2(u[:, 2], u[:, 1]))


def evaluate(out: Path, name: str, icc: Path) -> dict:
    from benchmarks.research import colour, gmq
    from benchmarks.research.blindspots import hunt, hunt_run, xf
    hunt.INTENTS = ("r",)
    hunt.PATHS = [("r", False, 0, False), ("r", True, 0, False),
                  ("r", True, 8, True)]
    ctx, truth = hunt_run.context(out, name, icc)
    res: dict = {"truth": truth, "profile": str(icc)}
    # --- F-15
    h11 = hunt.h11_pale(ctx)["r"]
    h2 = hunt.h2_colour_ramps(ctx)
    rel = [v for v in h2.values() if isinstance(v, dict)]
    h6 = hunt.h6_image(ctx)
    h4 = hunt.h4_tinted(ctx)
    res["F15"] = {
        "pale_share5": h11["share_dL_over_5"], "pale_p99": h11["dL_p99"],
        "pale_max": h11["dL_max"], "pale_max_rgb": h11["dL_max_rgb"],
        "ramp_rev": sum(v.get("l_rev", 0) for v in rel),
        "ramp_swing_max": max(v.get("l_swing", 0) for v in rel),
        "ramp_jump_max": max(v.get("jump_ratio", 0) for v in rel),
        "ramp_d2_max": max(v.get("d2_excess_max", v.get("band_max", 0)) for v in rel),
        "img_edges_r": sum(v.get("new_edges", 0) for v in h6["r"].values()),
        "img_edges_rbpc8": sum(v.get("new_edges", 0) for v in h6["r+bpc-app8"].values()),
        "tint_rev": sum(v.get("l_rev", 0) for k, v in h4.items()
                        if isinstance(v, dict) and k.endswith("-r")),
    }
    res["H2"] = h2
    res["H6"] = h6
    res["H11"] = h11
    res["H4"] = h4
    # --- F-17
    h5 = hunt.h5_memory(ctx)
    rgb = np.array([[0, 0, 1], [0.24, 0.24, 1.0], [1, 0, 0], [0, 1, 0],
                    [0, 1, 1], [1, 0, 1], [1, 1, 0]], float)
    src = xf.srgb_to_lab(rgb)
    pr = ctx.truth_lab(ctx.rgb2dev("srgb", rgb, "r"))
    dcam = hunt.dhue(cam16_hue(src), cam16_hue(pr))
    h8 = hunt.h8_extremes(ctx)
    res["F17"] = {
        "blue_ipt": h5["sRGB_blue-r"]["ipt_hue_shift"],
        "blue6060_ipt": h5["blue_60_60_255-r"]["ipt_hue_shift"],
        "blue_cam16": float(dcam[0]), "blue6060_cam16": float(dcam[1]),
        "prim_cam16": {k: float(v) for k, v in zip("BbRGCMY", dcam)},
        "oog_ipt_p95": h8["r"].get("oog_clip_ipt_hue_p95"),
        "oog_ipt_blue_mean": h8["r"].get("oog_clip_ipt_hue_blue_mean"),
        "oog_lab_p95": h8["r"].get("oog_clip_hue_p95"),
        "mem": {k: v for k, v in h5.items()},
    }
    # --- in gamut
    rng = np.random.default_rng(25)
    dev = rng.uniform(0, 1, (6000, ctx.n))
    half = 3000
    dev[:half] *= rng.uniform(0, 1, (half, 1)) ** 2       # light half
    if ctx.tac and not ctx.additive:
        dev = gmq._scale_tac(dev, ctx.tac)
    if ctx.additive:
        dev[:half] = 1 - rng.uniform(0, 1, (half, ctx.n)) * rng.uniform(0, 1, (half, 1)) ** 2
    tl = ctx.truth_lab(dev)
    ok = tl[:, 0] > 3
    tl = tl[ok]
    if ctx.gamut is not None:
        tl = tl[ctx.gamut.depth(tl) > 0.5]
    got = ctx.truth_lab(ctx.lab2dev(tl, "r"))
    de = colour.de2000(got, tl)
    pale = tl[:, 0] > 85
    res["ingamut"] = {"n": int(len(tl)), "median": float(np.median(de)),
                      "p95": float(np.percentile(de, 95)), "max": float(de.max()),
                      "pale_n": int(pale.sum()),
                      "pale_median": float(np.median(de[pale])) if pale.any() else None,
                      "pale_p95": float(np.percentile(de[pale], 95)) if pale.any() else None}
    ax = np.stack([np.linspace(5, 100, 96), np.zeros(96), np.zeros(96)], 1)
    pa = ctx.truth_lab(ctx.lab2dev(ax, "r"))
    blk = ctx.truth_lab(ctx.lab2dev(np.array([[0.0, 0, 0]]), "r"))[0, 0]
    keep = ax[:, 0] > blk + 1
    res["neutral"] = {"de_median": float(np.median(colour.de2000(pa[keep], ax[keep]))),
                      "de_max": float(colour.de2000(pa[keep], ax[keep]).max()),
                      "c_max": float(np.hypot(pa[keep, 1], pa[keep, 2]).max())}
    # --- safety
    h1 = hunt.h1_grey(ctx)
    res["safety"] = {
        "grey_r": {k: h1["r"][k] for k in ("l_rev", "l_swing", "chroma_max", "black_L",
                                         "white_ink") if k in h1["r"]},
        "grey_rbpc": {k: h1["r+bpc"][k] for k in ("l_rev", "l_swing", "chroma_max",
                                                  "black_L") if k in h1["r+bpc"]},
        "white_ink_r": h8["r"]["white_ink_pct"], "white_ink_a": h8["a"]["white_ink_pct"],
        "black_L_r": h8["r"]["black_L"], "black_C_r": h8["r"]["black_C"],
        "tac": ctx.tac,
        "tac_max_seen": max([v for _, v in ctx.ink_seen] or [0]),
    }
    return res


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    out, name, icc, dst = Path(argv[0]).resolve(), argv[1], Path(argv[2]).resolve(), Path(argv[3])
    res = evaluate(out, name, icc)
    from benchmarks.research.blindspots import hunt
    dst.write_text(json.dumps(hunt.jsonable(res), indent=1), encoding="utf-8")
    f15, f17, ig = res["F15"], res["F17"], res["ingamut"]
    print(f"{name} {icc.name}: pale {f15['pale_share5']:.3f}/{f15['pale_p99']:.1f}/"
          f"{f15['pale_max']:.1f} rev {f15['ramp_rev']} swing {f15['ramp_swing_max']:.1f} "
          f"jump {f15['ramp_jump_max']:.1f} edges {f15['img_edges_r']}/{f15['img_edges_rbpc8']} "
          f"tint {f15['tint_rev']} | blue ipt {f17['blue_ipt']:+.1f} cam {f17['blue_cam16']:+.1f} "
          f"oog ipt p95 {f17['oog_ipt_p95']:.1f} bluemean {f17['oog_ipt_blue_mean']:+.1f} | "
          f"in {ig['median']:.3f}/{ig['p95']:.3f}/{ig['max']:.2f} pale "
          f"{ig['pale_median']:.3f}/{ig['pale_p95']:.3f} | neutral C {res['neutral']['c_max']:.2f}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    raise SystemExit(main())
