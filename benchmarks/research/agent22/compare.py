"""Compare arms of agent 22 runs, per dataset x reader, on chosen metrics.
python compare.py ARM1 ARM2 [ARM3 ...]  (dirs under bat/; engine accurate unless ARM:engine)"""
import json, sys
from pathlib import Path
import numpy as np

H = Path(__file__).parent / "bat"
KEYS = ["a2b.all.median", "a2b.all.p95", "b2a.all.median", "b2a.all.p95",
        "neutral.de.mean", "neutral.chroma_max", "neutral.highlight.chroma_max",
        "neutral.L_reversals", "black.printed_L"]


def flat(o, pre=""):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                out[pre + k] = float(v)
            elif isinstance(v, dict):
                out.update(flat(v, pre + k + "."))
    return out


def load(arm):
    name, _, eng = arm.partition(":")
    eng = eng or "accurate"
    r = json.loads((H / name / "results.json").read_text())
    out = {}
    for d in r["datasets"]:
        p = d["profiles"].get(eng)
        if not p or not p.get("ok"):
            out[(d["name"], d["variant"])] = None
            continue
        out[(d["name"], d["variant"])] = {rd: flat(s) for rd, s in p["scores"].items()}
        out[(d["name"], d["variant"])]["_sha"] = p.get("sha256")
    return out


arms = sys.argv[1:]
data = [load(a) for a in arms]
keys = KEYS if not any(a.startswith("--all") for a in arms) else None
print("dataset/variant/reader | " + " | ".join(KEYS) + "   (arms: " + ", ".join(arms) + ")")
agg = {a: {k: [] for k in KEYS} for a in arms}
for ds in sorted(data[0]):
    for rd in ("argyll", "lcms", "colorsync"):
        cells = []
        for k in KEYS:
            vals = []
            for a, d in zip(arms, data):
                v = (d.get(ds) or {}).get(rd, {}).get(k)
                vals.append(v)
                if v is not None:
                    agg[a][k].append(v)
            cells.append("/".join("-" if v is None else f"{v:.2f}" for v in vals))
        print(f"{ds[0]} {ds[1]} {rd} | " + " | ".join(cells))
print("\nmeans over all rows:")
for k in KEYS:
    print(f"  {k:32s} " + "  ".join(f"{a}={np.mean(agg[a][k]):.3f}" for a in arms if agg[a][k]))
