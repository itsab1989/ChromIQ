"""Protocol-v2 primary endpoints E1-E6 + P7 secondaries, candidate vs base.
usage: a_compare.py BASE_RUN CAND_RUN PRINTERS NOISE"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "tree"))
import numpy as np
from benchmarks.research.stats import paired_bootstrap
base, cand, pids, noise = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3].split(","), sys.argv[4]
SEED = {"median": 0.03, "mean": 0.03, "p95": 0.10}
def ep(z, r, key):
    if key == "E1": return z["a2b"], "median"
    if key == "E2": return z["a2b"], "p95"
    if key == "E3": return z["b2a"], "median"
    if key == "E4": return z["b2a"], "p95"
    L, de = z["neutral_L"], z["neutral_de"]
    if key == "E5": return de, "median", L
    if key == "E6": return de[L >= 85.0], "mean"
rows = []
PENDING = []
for pid in pids:
    for rd in ("argyll", "lcms"):
        fa = base / "a9score" / f"{pid}-{noise}-{rd}"; fb = cand / "a9score" / f"{pid}-{noise}-{rd}"
        if not fa.with_suffix(".json").exists() or not fb.with_suffix(".json").exists():
            continue
        za, zb = np.load(fa.with_suffix(".npz")), np.load(fb.with_suffix(".npz"))
        ja, jb = json.loads(fa.with_suffix(".json").read_text(encoding="utf-8")), json.loads(fb.with_suffix(".json").read_text(encoding="utf-8"))
        for key in ("E1", "E2", "E3", "E4", "E5", "E6"):
            if key == "E5":
                lo = max(float(za["neutral_black_L"]), float(zb["neutral_black_L"])) + 1.0
                m = za["neutral_L"] >= lo
                a, b, st = za["neutral_de"][m], zb["neutral_de"][m], "median"
            else:
                a, st = ep(za, rd, key)[:2]; b = ep(zb, rd, key)[0]
            thr_ = None
            if key in ("E5", "E6"):          # protocol v2.1 A3: single-build star rows
                va = float(np.median(a)) if st == "median" else float(np.mean(a))
                vb = float(np.median(b)) if st == "median" else float(np.mean(b))
                thr = max(0.05 * abs(va), 0.02, SEED[st])
                v = "TIE" if abs(vb - va) < thr else ("BETTER*" if vb < va else "WORSE*")
                rows.append((pid, rd, key, va, vb, v)); continue
            r = paired_bootstrap(a, b, st, n_boot=2000, seed=20260929)
            # v2.1 A1: t p from the bootstrap SE (recomputed with the same seed)
            rng = np.random.default_rng(20260929); n = len(a); d = []
            for s0 in range(0, 2000, 500):
                idx = rng.integers(0, n, (500, n))
                f = {"median": np.median, "p95": lambda x, axis: np.percentile(x, 95, axis=axis),
                     "mean": np.mean}[st]
                d.append(f(b[idx], axis=-1) - f(a[idx], axis=-1))
            se = float(np.std(np.concatenate(d)))
            import math   # n = 20,000: Student t with n-1 df equals the normal to 4 digits
            pval = float(math.erfc(abs(r["diff"]) / max(se, 1e-12) / math.sqrt(2)))
            thr = max(0.05 * abs(r["a"]), 0.02, SEED[st])
            PENDING.append(dict(pid=pid, rd=rd, key=key, a=r["a"], b=r["b"], diff=r["diff"],
                                p=pval, ci=r["ci95"], thr=thr))
        na, nb = ja["neutral"], jb["neutral"]
        sec = {"neutral C*max": (na["chroma_max"], nb["chroma_max"], 0.5),
               "L reversals": (na["L_reversals"], nb["L_reversals"], 0.5),
               "black L": (ja["black"]["printed_L"], jb["black"]["printed_L"], 0.3),
               "black C": (float(np.hypot(*ja["black"]["printed_ab"])), float(np.hypot(*jb["black"]["printed_ab"])), 0.5),
               "neutral sep max_step": (na["separation"]["max_step"], nb["separation"]["max_step"], 0.10),
               "neutral TV excess": (na["separation"]["tv_excess"], nb["separation"]["tv_excess"], 0.25 * max(na["separation"]["tv_excess"], 1e-9)),
               "ramps worst max_step": (ja["ramps"]["worst"]["max_step"], jb["ramps"]["worst"]["max_step"], 0.10),
               "highlight sample B2A med": (ja["b2a"]["highlight_sample"]["median"], jb["b2a"]["highlight_sample"]["median"], 0.05),
               "shadow neutral med": (na.get("shadow", {}).get("de", {}).get("median", np.nan), nb.get("shadow", {}).get("de", {}).get("median", np.nan), 0.05),
               "over-limit share": (ja["b2a"].get("over_limit_frac", 0.0), jb["b2a"].get("over_limit_frac", 0.0), 0.001),
               "roundtrip med": (ja["roundtrip"]["median"], jb["roundtrip"]["median"], 0.03)}
        for k, (a, b, t) in sec.items():
            v = "TIE" if not (abs(b - a) > t) else ("BETTER" if b < a else "WORSE")
            rows.append((pid, rd, k, a, b, v))
# v2.1 A6: Holm per printer x endpoint family (both readers, this noise level)
from collections import defaultdict
fam = defaultdict(list)
for r in PENDING:
    fam[(r["pid"], r["key"])].append(r)
for rs in fam.values():
    order = sorted(rs, key=lambda r: r["p"]); m = len(order); rej = set()
    for i, r in enumerate(order):
        if r["p"] <= 0.05 / (m - i): rej.add(id(r))
        else: break
    for r in rs:
        v = "TIE"
        if id(r) in rej and not (r["ci"][0] <= 0 <= r["ci"][1]) and abs(r["diff"]) >= r["thr"]:
            v = "BETTER" if r["diff"] < 0 else "WORSE"
        rows.append((r["pid"], r["rd"], r["key"], r["a"], r["b"], v))
rows.sort(key=lambda r: (r[0], r[1], r[2]))
print(f"{cand.name} vs {base.name} ({noise})")
for r in rows:
    flag = "" if r[5] == "TIE" else r[5]
    print(f"{r[0]:4s} {r[1]:6s} {r[2]:26s} {r[3]:8.3f} -> {r[4]:8.3f} {flag}")
from collections import Counter
print("primary:", Counter(r[5] for r in rows if r[2] in ('E1','E2','E3','E4','E5','E6')),
      "secondary:", Counter(r[5] for r in rows if r[2] not in ('E1','E2','E3','E4','E5','E6')))
