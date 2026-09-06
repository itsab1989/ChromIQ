"""Round 4, issue #182 — MEASURED cost of evaluating every chart preset's patch
set against the standards' patch-population criteria.

Read-only.  Nothing in the ChromIQ checkout is written or imported for effect;
`workflow.ti3_analysis` is imported only to reuse the shipped CGATS reader, so
the timing is the timing of code that would really run.

Run:  python3 measure_preset_check_cost.py
"""
import json, os, statistics, sys, time
from pathlib import Path

REPO = Path(os.environ.get("CHROMIQ_REPO", "~/develop/ChromIQ")).expanduser()
sys.path.insert(0, str(REPO))

import numpy as np

from workflow.ti3_analysis import parse_ti3   # the shipped CGATS reader

# ---------------------------------------------------------------- criteria ---
# Device-value criteria, evaluated on the chart's DESIGN patch set (.ti1), so
# no measurement, no profile and no Argyll process is involved.
CORNERS = {                      # ChromIQ's own CUBE_CORNERS, 0..100 device
    "W": (100, 100, 100), "K": (0, 0, 0),
    "R": (100, 0, 0), "G": (0, 100, 0), "B": (0, 0, 100),
    "C": (0, 100, 100), "M": (100, 0, 100), "Y": (100, 100, 0),
}
CORNER_TOL = 12.0                # measurement_report.CORNER_PRESENT_TOL
EXACT_TOL = 0.5                  # C2 / C3, as stated in the comment
NEUTRAL_TOL = 1.0                # C6, channels within this of each other


def _nearest(rgb, target):
    d = np.abs(rgb - np.asarray(target, float)).max(axis=1)
    return float(d.min())


def evaluate(rgb):
    """Every criterion in the round-4 proposal, on one chart's device values."""
    out = {}
    n = len(rgb)
    out["C1_patch_count"] = n >= 20

    # C2 substrate: a bare-paper patch (no ink at all)
    out["C2_substrate"] = _nearest(rgb, CORNERS["W"]) <= EXACT_TOL

    # C3 composite black
    out["C3_black"] = _nearest(rgb, CORNERS["K"]) <= EXACT_TOL

    # C4 the six chromatic solids, C5 all eight corners
    chroma = [_nearest(rgb, CORNERS[k]) <= CORNER_TOL for k in "RGBCMY"]
    out["C4_six_solids"] = all(chroma)
    out["C5_eight_corners"] = out["C4_six_solids"] and \
        _nearest(rgb, CORNERS["W"]) <= CORNER_TOL and \
        _nearest(rgb, CORNERS["K"]) <= CORNER_TOL

    # C6 neutral scale: patches on the R=G=B axis, >= 8 distinct steps, and
    #    the span must cover at least 10..90 of the device range.
    on_axis = rgb[(np.abs(rgb[:, 0] - rgb[:, 1]) <= NEUTRAL_TOL)
                  & (np.abs(rgb[:, 1] - rgb[:, 2]) <= NEUTRAL_TOL)]
    levels = np.unique(np.round(on_axis[:, 0], 1)) if len(on_axis) else np.array([])
    out["C6_neutral_steps"] = len(levels)
    out["C6_neutral_scale"] = (len(levels) >= 8
                               and levels.min() <= 10.0 and levels.max() >= 90.0)

    # C6+ the ramp is dense and complete: >= 16 levels, spanning 0..100,
    #     and no gap between consecutive levels wider than 10 device units.
    if len(levels) >= 2:
        gap = float(np.diff(levels).max())
    else:
        gap = float("inf")
    out["C6plus_max_gap"] = gap
    out["C6plus_dense_ramp"] = (len(levels) >= 16
                                and levels.min() <= EXACT_TOL
                                and levels.max() >= 100.0 - EXACT_TOL
                                and gap <= 10.0)

    # C7 near-neutral ring: patches close to but off the grey axis
    if len(rgb):
        mx, mn = rgb.max(axis=1), rgb.min(axis=1)
        spread = mx - mn
        near = rgb[(spread > 0.0) & (spread <= 12.0)]
        out["C7_near_neutral_ring"] = len(near) >= 12
    else:
        out["C7_near_neutral_ring"] = False

    # C8 single-channel ramps 30..70 %: for each of the three device axes,
    #    the ramp from white toward C/M/Y — one channel down, two at 100.
    ramps_ok = []
    for ax in range(3):
        others = [i for i in range(3) if i != ax]
        sel = rgb[(np.abs(rgb[:, others[0]] - 100.0) <= 1.0)
                  & (np.abs(rgb[:, others[1]] - 100.0) <= 1.0)]
        # tone value = 100 - device on the varying axis
        tv = 100.0 - sel[:, ax] if len(sel) else np.array([])
        band = np.unique(np.round(tv[(tv >= 30.0) & (tv <= 70.0)], 1)) if len(tv) else []
        # >= 3 distinct values inside the band AND the outermost two >= 20 apart
        ramps_ok.append(len(band) >= 3 and (band[-1] - band[0]) >= 20.0)
    out["C8_ramps_30_70"] = all(ramps_ok)
    return out


def read_ti1(p):
    d = parse_ti3(p)
    return np.asarray(d.rgb, float)


# ------------------------------------------------------------------- run -----
def main():
    ti1s = sorted(REPO.glob("assets/charts/**/*.ti1"))
    print(f"bundled .ti1 chart assets: {len(ti1s)}")
    rows, t_parse, t_eval = [], [], []
    t0 = time.perf_counter()
    for p in ti1s:
        a = time.perf_counter()
        try:
            rgb = read_ti1(p)
        except Exception as exc:                       # noqa: BLE001
            rows.append((p, None, str(exc)))
            continue
        b = time.perf_counter()
        res = evaluate(rgb)
        c = time.perf_counter()
        t_parse.append(b - a)
        t_eval.append(c - b)
        rows.append((p, len(rgb), res))
    total = time.perf_counter() - t0

    ok = [r for r in rows if isinstance(r[2], dict)]
    print(f"parsed OK: {len(ok)}   failed: {len(rows) - len(ok)}")
    print(f"TOTAL wall for {len(ok)} presets: {total*1000:.1f} ms")
    if t_parse:
        print(f"  parse  .ti1: total {sum(t_parse)*1000:8.1f} ms   "
              f"median {statistics.median(t_parse)*1000:6.2f} ms   "
              f"max {max(t_parse)*1000:6.1f} ms")
        print(f"  evaluate   : total {sum(t_eval)*1000:8.1f} ms   "
              f"median {statistics.median(t_eval)*1000:6.2f} ms   "
              f"max {max(t_eval)*1000:6.1f} ms")
    sizes = [r[1] for r in ok]
    print(f"  patches: min {min(sizes)}  median {int(statistics.median(sizes))}  max {max(sizes)}  sum {sum(sizes)}")

    # per-criterion pass counts
    print("\ncriterion                     presets meeting it")
    keys = [k for k in ok[0][2]
            if k not in ("C6_neutral_steps", "C6plus_max_gap")]
    for k in keys:
        c = sum(1 for r in ok if r[2][k])
        print(f"  {k:<28} {c:4d} / {len(ok)}")

    # how many of the files are actually DISTINCT patch sets?
    import hashlib
    seen = {}
    for r in ok:
        a = np.round(read_ti1(r[0]), 4)
        a = a[np.lexsort((a[:, 2], a[:, 1], a[:, 0]))]      # order-insensitive
        h = hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
        seen.setdefault(h, []).append(r)
    print(f"\nunique patch sets (by content): {len(seen)} of {len(ok)} files")
    for k in ("C7_near_neutral_ring", "C8_ramps_30_70", "C6plus_dense_ramp"):
        fails = sum(1 for v in seen.values() if not v[0][2][k])
        print(f"  unique sets failing {k:<22} {fails:3d} / {len(seen)}")

    out = REPO.parent / "ChromIQ-research/round4/preset-check-cost.json"
    json.dump({
        "n_presets": len(ok),
        "total_ms": total * 1000,
        "parse_total_ms": sum(t_parse) * 1000,
        "eval_total_ms": sum(t_eval) * 1000,
        "parse_median_ms": statistics.median(t_parse) * 1000,
        "eval_median_ms": statistics.median(t_eval) * 1000,
        "patches_sum": sum(sizes),
        "per_preset": [{"path": str(r[0].relative_to(REPO)), "patches": r[1],
                        **{k: (bool(v) if not isinstance(v, (int, float)) or isinstance(v, bool) else v)
                           for k, v in r[2].items()}}
                       for r in ok],
    }, open(out, "w"), indent=1, default=str)
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
