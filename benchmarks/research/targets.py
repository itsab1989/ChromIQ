"""Band a run's scores against an excellence-target file (targets v2; Agent 16).

The thresholds are NOT in this repository: they are derived from standards
whose values must not appear in what ChromIQ publishes, so they live in the
research folder (``Validation/excellence-targets-v2.json``, frozen with a
date and a commit). This module only applies them.

Target file format::

    {"version": "v2", "frozen": "...", "rows": [
       {"endpoint": "A2B", "metric": [["a2b", "all", "mean"], ["a2b", "all", "p95"]],
        "bands": {"excellent": [0.25, 0.75], "good": [...], "acceptable": [...]},
        "kind": "max"}, ...]}

``metric`` paths are read from one reader's scores (``results.json``,
``datasets[].profiles[engine].scores[reader]``; real sets read ``a2b_heldout``
for ``a2b``). A row reaches a band only if every metric is <= its limit
(``kind`` "max"); ``black_depth`` rows compare the printed black with the
TRUTH's darkest reachable neutral inside the ink limit (absolute, not the
best builder's black). Missing metric -> "n/a" (never a pass).

    python -m benchmarks.research.targets RUN_DIR TARGETS.json [--reader argyll]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ORDER = ("excellent", "good", "acceptable")


def _get(scores: dict, path: list, real: bool):
    x = scores
    for i, k in enumerate(path):
        if i == 0 and k == "a2b" and real:
            k = "a2b_heldout"
        if not isinstance(x, dict) or k not in x:
            return None
        x = x[k]
    return x if isinstance(x, (int, float)) else None


def band_row(row: dict, scores: dict, real: bool) -> tuple[str, list]:
    if row.get("kind") == "black_depth":
        pl = _get(scores, ["black", "printed_L"], real)
        reach = _get(scores, ["black", "reachable_L", "darkest_neutral_L"], real)
        ab = (scores.get("black") or {}).get("printed_ab")
        if pl is None or reach is None or ab is None:
            return "n/a", []
        vals = [pl - reach, (ab[0] ** 2 + ab[1] ** 2) ** 0.5]
    else:
        vals = [_get(scores, m, real) for m in row["metric"]]
        if any(v is None for v in vals):
            return "n/a", vals
    for name in ORDER:
        lim = row["bands"].get(name)
        if lim is not None and all(v <= l for v, l in zip(vals, lim)):
            return name, vals
    return "below", vals


def band_run(results: dict, targets: dict, reader: str = "argyll",
             engines=None) -> list[dict]:
    out = []
    for d in results["datasets"]:
        real = d["kind"] == "real"
        for eng, p in d["profiles"].items():
            if engines and eng not in engines:
                continue
            sc = (p.get("scores") or {}).get(reader)
            if not sc or "error" in sc or "unsupported" in sc:
                continue
            for row in targets["rows"]:
                if real and row.get("synthetic_only"):
                    continue
                b, vals = band_row(row, sc, real)
                out.append({"dataset": d["name"], "variant": d["variant"], "engine": eng,
                            "endpoint": row["endpoint"], "band": b,
                            "values": [None if v is None else round(float(v), 4) for v in vals]})
    return out


def matrix(rows: list[dict], engine: str) -> str:
    letters = {"excellent": "E", "good": "G", "acceptable": "A", "below": "below", "n/a": "-"}
    eps = list(dict.fromkeys(r["endpoint"] for r in rows))
    sets = list(dict.fromkeys((r["dataset"], r["variant"]) for r in rows if r["engine"] == engine))
    lines = ["| dataset | " + " | ".join(eps) + " |", "|---|" + "---|" * len(eps)]
    for ds, var in sets:
        cells = []
        for e in eps:
            r = next((x for x in rows if x["dataset"] == ds and x["variant"] == var
                      and x["engine"] == engine and x["endpoint"] == e), None)
            cells.append(letters[r["band"]] if r else "-")
        lines.append(f"| {ds} {var} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("targets")
    ap.add_argument("--reader", default="argyll")
    ap.add_argument("--engines", default="accurate,colprof,fast,argyll")
    args = ap.parse_args(argv)
    res = json.loads((Path(args.run_dir) / "results.json").read_text(encoding="utf-8"))
    tg = json.loads(Path(args.targets).read_text(encoding="utf-8"))
    engines = args.engines.split(",")
    rows = band_run(res, tg, args.reader, engines)
    out = Path(args.run_dir) / f"bands-{tg.get('version', 'x')}-{args.reader}.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    for e in engines:
        print(f"\n### {e} ({args.reader}, targets {tg.get('version')})\n")
        print(matrix(rows, e))


if __name__ == "__main__":
    main()
