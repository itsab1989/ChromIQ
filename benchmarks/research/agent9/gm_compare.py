"""Property-by-property verdicts between two engines' gamut mapping (gmq).

usage: gm_compare.py DIR_A ENGINE_A DIR_B ENGINE_B [--printers ..] [--out F.json]
Verdict for B against A per (printer, noise, reader, intent, property):
BETTER / WORSE / TIE. Scalar properties: minimum effect only (table below).
Per-point properties (M2 mean, M5 median, M7 p05, M11 median, M11 p95):
minimum effect AND the paired bootstrap 95 % CI excluding 0.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent / "tree"))
from benchmarks.research.stats import paired_bootstrap

LOW, HIGH = "low", "high"
# property -> (direction, abs min effect, rel min effect)
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
    thr = max(mabs, mrel * abs(va))
    if abs(diff) < thr:
        return "TIE", diff
    if prop in BOOT and ppa is not None and ppb is not None:
        key, st = BOOT[prop]
        if key in ppa and key in ppb and ppa[key].shape == ppb[key].shape:
            if st is None:
                ci = p05_boot(ppa[key], ppb[key])
            else:
                ci = paired_bootstrap(ppa[key], ppb[key], st, n_boot=1000)["ci95"]
            if ci[0] <= 0 <= ci[1]:
                return "TIE", diff
    good = diff < 0 if d == LOW else diff > 0
    return ("BETTER" if good else "WORSE"), diff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir_a"); ap.add_argument("eng_a")
    ap.add_argument("dir_b"); ap.add_argument("eng_b")
    ap.add_argument("--printers", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    rows = []
    for fa in sorted(Path(a.dir_a).glob(f"*-{a.eng_a}-*.json")):
        pid, noise, _e, rd, it = fa.stem.rsplit("-", 4) if fa.stem.count("-") == 4 else (None,)*5
        parts = fa.stem.split("-")
        pid, noise, rd, it = parts[0], parts[1], parts[-2], parts[-1]
        if parts[2] != a.eng_a:
            continue
        if a.printers and pid not in a.printers.split(","):
            continue
        fb = Path(a.dir_b) / f"{pid}-{noise}-{a.eng_b}-{rd}-{it}.json"
        if not fb.exists():
            continue
        ra, rb = json.loads(fa.read_text(encoding="utf-8")), json.loads(fb.read_text(encoding="utf-8"))
        if "error" in ra or "error" in rb:
            rows.append({"printer": pid, "noise": noise, "reader": rd, "intent": it,
                         "error": ra.get("error") or rb.get("error")}); continue
        pa = dict(np.load(fa.with_suffix(".npz"))) if fa.with_suffix(".npz").exists() else None
        pb = dict(np.load(fb.with_suffix(".npz"))) if fb.with_suffix(".npz").exists() else None
        for prop in PROPS:
            v, diff = verdict(prop, ra.get(prop), rb.get(prop), pa, pb)
            rows.append({"printer": pid, "noise": noise, "reader": rd, "intent": it,
                         "prop": prop, "a": ra.get(prop), "b": rb.get(prop),
                         "verdict": v})
    tally = {}
    for r in rows:
        if "verdict" in r:
            t = tally.setdefault(r["prop"], {"BETTER": 0, "WORSE": 0, "TIE": 0, "NA": 0})
            t[r["verdict"]] += 1
    print(f"B={a.eng_b} ({a.dir_b}) vs A={a.eng_a} ({a.dir_a}): verdicts for B")
    print(f"{'property':24s} BETTER WORSE TIE")
    for p, t in tally.items():
        print(f"{p:24s} {t['BETTER']:6d} {t['WORSE']:5d} {t['TIE']:4d}")
    if not a.quiet:
        print("\nWORSE rows:")
        for r in rows:
            if r.get("verdict") == "WORSE":
                print(f"  {r['printer']:4s} {r['noise'][:4]} {r['reader']:6s} {r['intent']} "
                      f"{r['prop']:22s} {r['a']:.3f} -> {r['b']:.3f}")
    errs = [r for r in rows if "error" in r]
    if errs:
        print("errors:", errs[:5])
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=0), encoding="utf-8")


if __name__ == "__main__":
    main()
