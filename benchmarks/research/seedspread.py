"""Between-seed spread of the primary endpoints (Agent 6).

    python -m benchmarks.research.seedspread <seeds run dir> [--engine accurate]

Reads a ``--suite seeds`` run, and for each printer the five seeds' values of
each primary endpoint (Argyll and lcms readouts); writes ``seed_sd.json``
({"<family>|<endpoint>": pooled sd}, family S / X, pooled as the RMS of the
per-printer SDs over both readouts) for ``stats.py --seed-sd`` and prints the
table for protocol.md section 6.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ENDPOINTS = {"a2b.median": ("a2b", "all", "median"), "a2b.p95": ("a2b", "all", "p95"),
             "b2a.median": ("b2a", "all", "median"), "b2a.p95": ("b2a", "all", "p95"),
             # protocol v2.1: the ramps (E5, E6), scored in light mode since 6b
             "neutral_de.median": ("neutral", "de", "median"),
             "neutral_hi.mean": ("neutral", "highlight", "de", "mean")}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--engine", default="accurate")
    ap.add_argument("--readers", nargs="+", default=["argyll", "lcms"])
    args = ap.parse_args(argv)
    res = json.loads((Path(args.run_dir) / "results.json").read_text(encoding="utf-8"))
    vals = defaultdict(list)                  # (printer, reader, endpoint) -> [v]
    for d in res["datasets"]:
        if d["suite"] != "seeds":
            continue
        p = d["profiles"].get(args.engine, {})
        for r in args.readers:
            s = p.get("scores", {}).get(r, {})
            for name, path in ENDPOINTS.items():
                v = s
                for k in path:
                    v = v.get(k, {}) if isinstance(v, dict) else {}
                if isinstance(v, (int, float)):
                    vals[(d["name"], r, name)].append(float(v))
    per_printer = {}
    pooled = defaultdict(list)
    for (pr, r, ep), v in sorted(vals.items()):
        sd = float(np.std(v, ddof=1)) if len(v) > 1 else float("nan")
        per_printer[f"{pr}|{r}|{ep}"] = {"values": v, "mean": float(np.mean(v)), "sd": sd}
        pooled[f"{'X' if pr.startswith('X') else 'S'}|{ep}"].append(sd)
    out = {k: float(np.sqrt(np.mean(np.square(v)))) for k, v in pooled.items()}
    Path(args.run_dir, "seed_sd.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    Path(args.run_dir, "seed_spread_detail.json").write_text(json.dumps(per_printer, indent=1), encoding="utf-8")
    print("| printer | reader | endpoint | mean | sd | cv % |")
    print("|---|---|---|---|---|---|")
    for k, v in per_printer.items():
        pr, r, ep = k.split("|")
        print(f"| {pr} | {r} | {ep} | {v['mean']:.3f} | {v['sd']:.3f} | {100 * v['sd'] / v['mean']:.1f} |")
    print("\npooled:", json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
