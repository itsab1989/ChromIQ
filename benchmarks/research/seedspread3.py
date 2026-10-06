"""Between-seed SD per engine, noise level, ink class and endpoint (protocol v3, B1).

    python -m benchmarks.research.seedspread3 <seeds3 run dir> [--out seed_sd_v3.json]

Reads a ``--suite seeds3`` run (variants ``seed<k>-<level>-<chart><n>``) and
computes, for every engine, printer, reader, level and endpoint, the SD of
the endpoint over the k seeds. Pooled per (engine, level, ink class,
endpoint) as the RMS of the per-printer, per-reader SDs; written as
``{"<engine>|<level>|<class>|<endpoint>": sd}`` for ``stats3 --seed-sd``,
with a detail file of every value and the number of seeds behind each SD.
Endpoints are those of stats3 (medians, MEANS, p95s, and the ramps).
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from benchmarks.research.stats3 import ink_class, split_variant

ENDPOINTS = {"a2b.median": ("a2b", "all", "median"), "a2b.mean": ("a2b", "all", "mean"),
             "a2b.p95": ("a2b", "all", "p95"),
             "b2a.median": ("b2a", "all", "median"), "b2a.mean": ("b2a", "all", "mean"),
             "b2a.p95": ("b2a", "all", "p95"),
             "neutral_de.median": ("neutral", "de", "median"),
             "neutral_de.mean": ("neutral", "de", "mean"),
             "neutral_hi.mean": ("neutral", "highlight", "de", "mean"),
             # v3.1: the pale in-gamut sample (F-14), dE00 and |dL*|
             "pale.median": ("b2a", "pale_sample", "median"),
             "pale.p95": ("b2a", "pale_sample", "p95"),
             "pale_dl.mean": ("b2a", "pale_sample", "dl_abs", "mean"),
             "pale_dl.p95": ("b2a", "pale_sample", "dl_abs", "p95")}
DECISION_READERS = ("argyll", "lcms", "colorsync", "lcms-app", "ghostscript")


def spread(results: dict, readers=DECISION_READERS) -> tuple[dict, dict]:
    vals = defaultdict(list)          # (engine, printer, cls, reader, level, chart, ep) -> [v]
    for d in results["datasets"]:
        v = split_variant(d["variant"])
        if v["seed"] is None:
            continue
        cls = ink_class(d["n_channels"], d["color_rep"])
        chart = f"{v['chart']}{v['patches']}"
        for eng, p in d["profiles"].items():
            for r in readers:
                s = (p.get("scores") or {}).get(r) or {}
                for name, path in ENDPOINTS.items():
                    x = s
                    for k in path:
                        x = x.get(k, {}) if isinstance(x, dict) else {}
                    if isinstance(x, (int, float)):
                        vals[(eng, d["name"], cls, r, v["level"], chart, name)].append(float(x))
            # v3.1: the oogq property rows (one reader: lcms float)
            for k, x in (((p.get("oogq") or {}).get("q")) or {}).items():
                vals[(eng, d["name"], cls, "oogq", v["level"], chart, f"q.{k}")].append(float(x))
    detail = {}
    pooled = defaultdict(list)
    for (eng, pr, cls, r, lv, ch, ep), v in sorted(vals.items()):
        if len(v) < 2:
            continue
        sd = float(np.std(v, ddof=1))
        detail["|".join([eng, pr, r, lv, ch, ep])] = {"n": len(v), "mean": float(np.mean(v)),
                                                      "sd": sd, "values": v}
        pooled[f"{eng}|{lv}|{cls}|{ep}"].append(sd)
    table = {k: float(np.sqrt(np.mean(np.square(v)))) for k, v in pooled.items()}
    return table, detail


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    res = json.loads((Path(args.run_dir) / "results.json").read_text(encoding="utf-8"))
    table, detail = spread(res)
    out = Path(args.out) if args.out else Path(args.run_dir) / "seed_sd_v3.json"
    out.write_text(json.dumps(table, indent=1, sort_keys=True), encoding="utf-8")
    out.with_name(out.stem + "-detail.json").write_text(json.dumps(detail, indent=1), encoding="utf-8")
    print("| engine | level | class | endpoint | pooled SD |")
    print("|---|---|---|---|---|")
    for k, v in sorted(table.items()):
        print("| " + " | ".join(k.split("|")) + f" | {v:.4f} |")


if __name__ == "__main__":
    main()
