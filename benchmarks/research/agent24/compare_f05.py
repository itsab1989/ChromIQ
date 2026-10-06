"""Agent 24, F-05: verdicts per gmq property, arm vs base, per dataset x reader x intent.

    python compare_f05.py <run> <arm> [--base base] [--table]

Property directions and minimum effects are Agent 9's (gm_compare.py, copied unchanged);
per-point properties also need the paired bootstrap 95 % CI to exclude 0."""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(H / "score"))
from benchmarks.research.stats import paired_bootstrap   # noqa: E402

LOW, HIGH = "low", "high"
PROPS = {
 "M1_neutral_C_mean": (LOW, 0.2, 0.10), "M1_neutral_C_max": (LOW, 0.5, 0.10),
 "M2_hue_ipt_wmean": (LOW, 0.3, 0.05), "M2_hue_ipt_p95": (LOW, 0.5, 0.05),
 "M3_L_reversals": (LOW, 2, 0.20), "M3_L_rev_max": (LOW, 0.3, 0.20),
 "M3_neutral_L_reversals": (LOW, 1, 0.0),
 "M3c_C_reversals": (LOW, 2, 0.20),
 "M4_d2_median": (LOW, 0.1, 0.05), "M4_d2_max": (LOW, 0.3, 0.10),
 "M4_jump_median": (LOW, 0.1, 0.05), "M4_jump_max": (LOW, 0.3, 0.10),
 "M5_core_de_median": (LOW, 0.1, 0.05), "M5_core_de_p95": (LOW, 0.2, 0.05),
 "M6_plateau_mean": (LOW, 0.02, 0.0),
 "M7_ratio_median": (HIGH, 0.02, 0.0), "M7_ratio_p05": (HIGH, 0.02, 0.0),
 "M7_core_p05": (HIGH, 0.02, 0.0), "M7_outside_p05": (HIGH, 0.02, 0.0),
 "M8_black_gap": (LOW, 0.3, 0.0), "M8_black_C": (LOW, 0.5, 0.0),
 "M8w_white_de": (LOW, 0.1, 0.0), "M8w_white_ink": (LOW, 0.5, 0.0),
 "M9_over_share": (LOW, 0.001, 0.0),
 "M10_sep_d2_median": (LOW, 0.005, 0.10), "M10_sep_d2_max": (LOW, 0.02, 0.10),
 "M10_neutral_sep_d2": (LOW, 0.005, 0.10), "M10_K_reversals": (LOW, 1, 0.0),
 "M11_rt_median": (LOW, 0.1, 0.05), "M11_rt_p95": (LOW, 0.2, 0.05),
}
BOOT = {"M2_hue_ipt_wmean": ("M2", "mean"), "M5_core_de_median": ("M5", "median"),
        "M7_ratio_p05": ("M7", None), "M11_rt_median": ("M11", "median"),
        "M11_rt_p95": ("M11", "p95")}
# D-17 2c safety properties for a mapped intent: grey cast, black, white, ink limit, banding
SAFETY = ("M1_neutral_C_mean", "M1_neutral_C_max", "M3_neutral_L_reversals", "M8_black_gap",
          "M8_black_C", "M8w_white_ink", "M9_over_share", "M4_jump_max")


def p05_boot(a, b, n_boot=1000, seed=20260929):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), (n_boot, len(a)))
    d = np.percentile(b[idx], 5, axis=1) - np.percentile(a[idx], 5, axis=1)
    return [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]


def verdict(prop, va, vb, ppa=None, ppb=None):
    if va is None or vb is None:
        return "NA", None
    d, mabs, mrel = PROPS[prop]
    diff = vb - va
    if abs(diff) < max(mabs, mrel * abs(va)):
        return "TIE", diff
    if prop in BOOT and ppa is not None and ppb is not None:
        key, st = BOOT[prop]
        if key in ppa and key in ppb and ppa[key].shape == ppb[key].shape:
            ci = p05_boot(ppa[key], ppb[key]) if st is None else \
                paired_bootstrap(ppa[key], ppb[key], st, n_boot=1000)["ci95"]
            if ci[0] <= 0 <= ci[1]:
                return "TIE", diff
    good = diff < 0 if d == LOW else diff > 0
    return ("BETTER" if good else "WORSE"), diff


def main():
    run = H / "f05" / "runs" / sys.argv[1]
    arm = sys.argv[2]
    base = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "base"
    g = run / "gmq"
    rows = []
    for fb in sorted(g.glob(f"*-{arm}-*-?.json")):
        stem = fb.stem
        pre, rd, it = stem.rsplit("-", 2)
        tag = pre[: -len(arm) - 1]
        fa = g / f"{tag}-{base}-{rd}-{it}.json"
        if not fa.exists():
            continue
        ra, rb = json.loads(fa.read_text(encoding="utf-8")), json.loads(fb.read_text(encoding="utf-8"))
        if "error" in ra or "error" in rb:
            rows.append({"tag": tag, "reader": rd, "intent": it, "error": ra.get("error") or rb.get("error")})
            continue
        pa = dict(np.load(fa.with_suffix(".npz"))) if fa.with_suffix(".npz").exists() else None
        pb = dict(np.load(fb.with_suffix(".npz"))) if fb.with_suffix(".npz").exists() else None
        for prop in PROPS:
            v, diff = verdict(prop, ra.get(prop), rb.get(prop), pa, pb)
            rows.append({"tag": tag, "reader": rd, "intent": it, "prop": prop,
                         "a": ra.get(prop), "b": rb.get(prop), "verdict": v})
    tally = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if "verdict" in r:
            tally[r["prop"]][r["verdict"]] += 1
    print(f"{arm} vs {base} ({run.name}): {len({(r['tag'], r['reader'], r['intent']) for r in rows})} "
          "dataset x reader x intent cells")
    print("| property | BETTER | WORSE | TIE |")
    for p in PROPS:
        t = tally[p]
        print(f"| {p}{' (safety)' if p in SAFETY else ''} | {t['BETTER']} | {t['WORSE']} | {t['TIE']} |")
    print("\nWORSE rows:")
    for r in rows:
        if r.get("verdict") == "WORSE":
            print(f"  {r['tag']:28s} {r['reader']:9s} {r['intent']} {r['prop']:22s} "
                  f"{r['a']:.3f} -> {r['b']:.3f}{'  SAFETY' if r['prop'] in SAFETY else ''}")
    errs = [r for r in rows if "error" in r]
    if errs:
        print("errors:", errs[:6])
    if "--table" in sys.argv:
        print("\n| dataset | reader | intent | neutral C* mean | C* max | round trip med | black L* | black C* | core dE med | hue IPT |")
        cells = sorted({(r["tag"], r["reader"], r["intent"]) for r in rows if "prop" in r})
        for tag, rd, it in cells:
            ra = json.loads((g / f"{tag}-{base}-{rd}-{it}.json").read_text(encoding="utf-8"))
            rb = json.loads((g / f"{tag}-{arm}-{rd}-{it}.json").read_text(encoding="utf-8"))
            f = lambda k: f"{ra[k]:.2f} -> {rb[k]:.2f}" if ra.get(k) is not None else "n/a"
            print(f"| {tag} | {rd} | {it} | {f('M1_neutral_C_mean')} | {f('M1_neutral_C_max')} | "
                  f"{f('M11_rt_median')} | {f('M8_black_L')} | {f('M8_black_C')} | "
                  f"{f('M5_core_de_median')} | {f('M2_hue_ipt_wmean')} |")
    (run / f"cmp-{arm}-vs-{base}.json").write_text(json.dumps(rows, indent=0), encoding="utf-8")


if __name__ == "__main__":
    main()
