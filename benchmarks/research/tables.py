"""Compact report tables from a research run (Agent 6).

    python -m benchmarks.research.tables <run dir> [--reader argyll]

Prints markdown: the key table (one row per dataset x engine), the
separation/neutral table, the identity and gate lines, and the outlier
table. Used to write the baseline report; no numbers are edited by hand.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ORDER = ["colprof", "fast", "argyll", "accurate"]


def g(d, *ks, f="{:.3f}"):
    for k in ks:
        if not isinstance(d, dict) or k not in d or d[k] is None:
            return "n/a"
        d = d[k]
    return f.format(d) if isinstance(d, (int, float)) else str(d)


def key_table(res: dict, reader: str, suite: str = "baseline") -> str:
    L = [f"| dataset | engine | A2B med | A2B p95 | B2A med | B2A p95 | B2A Lab-unif med | "
         f"RT med | neutral med | neutral p95 | shadow B2A med | highlight B2A med | ITP B2A med | s |",
         "|" + "---|" * 14]
    for d in res["datasets"]:
        if d["suite"] != suite:
            continue
        for e in sorted(d["profiles"], key=lambda x: ORDER.index(x) if x in ORDER else 9):
            p = d["profiles"][e]
            name = d["name"] + ("*" if d["kind"] == "real" else "")
            if not p.get("ok"):
                err = (p.get("error") or "").split("\n")[0][:60].replace("|", "/")
                L.append(f"| {name} | {e} | FAILED: {err} |" + " |" * 11)
                continue
            s = p.get("scores", {}).get(reader, {})
            if "error" in s:
                L.append(f"| {name} | {e} | readout failed: {s['error'][:50]} |" + " |" * 11)
                continue
            a = s.get("a2b") or s.get("a2b_heldout") or {}
            L.append("| " + " | ".join([
                name, e, g(a, "all", "median"), g(a, "all", "p95"),
                g(s, "b2a", "all", "median"), g(s, "b2a", "all", "p95"),
                g(s, "b2a", "lab_uniform", "median"), g(s, "roundtrip", "median"),
                g(s, "neutral", "de", "median"), g(s, "neutral", "de", "p95"),
                g(s, "b2a", "shadow_L<20", "median"),
                g(s, "b2a", "highlight_sample", "median"),
                g(s, "b2a", "itp", "median", f="{:.2f}"),
                g(p, "seconds", f="{:.0f}")]) + " |")
    return "\n".join(L)


def neutral_table(res: dict, reader: str, suite: str = "baseline") -> str:
    L = ["| dataset | engine | black L* a* b* | black TAC % | white ink % | neutral C*max | "
         "L* reversals | banding max | sep max step | sep max rate/L* | sep TV excess | "
         "shadow max step | ramps worst step | raw column step (grid) |",
         "|" + "---|" * 14]
    for d in res["datasets"]:
        if d["suite"] != suite or d["kind"] == "real":
            continue
        for e in sorted(d["profiles"], key=lambda x: ORDER.index(x) if x in ORDER else 9):
            p = d["profiles"][e]
            s = p.get("scores", {}).get(reader, {})
            if not p.get("ok") or "neutral" not in s:
                continue
            b = s["black"]
            raw = p.get("raw_neutral_column")
            L.append("| " + " | ".join([
                d["name"], e,
                f"{b['printed_L']:.1f} {b['printed_ab'][0]:+.1f} {b['printed_ab'][1]:+.1f}",
                g(b, "tac_pct", f="{:.0f}"), g(s, "white", "max_ink_pct", f="{:.2f}"),
                g(s, "neutral", "chroma_max", f="{:.2f}"),
                g(s, "neutral", "L_reversals", f="{}"),
                g(s, "neutral", "banding_max_d2", f="{:.2f}"),
                g(s, "neutral", "separation", "max_step"),
                g(s, "neutral", "separation", "max_rate_per_L"),
                g(s, "neutral", "separation", "tv_excess"),
                g(s, "neutral", "shadow", "separation", "max_step"),
                g(s, "ramps", "worst", "max_step"),
                (f"{raw['max_node_step']:.3f} ({raw['grid']})" if raw else "n/a")]) + " |")
    return "\n".join(L)


def outlier_table(res: dict, suite: str = "baseline") -> str:
    L = ["| dataset | engine | true misreads | flagged | true pos | false pos |", "|---|---|---|---|---|---|"]
    for d in res["datasets"]:
        if d["suite"] != suite:
            continue
        for e, p in d["profiles"].items():
            o = p.get("outliers")
            if o and e == "accurate":
                L.append(f"| {d['name']} | {e} | {o['true']} | {o['flagged']} | "
                         f"{o['true_positive']} | {o['false_positive']} |")
    return "\n".join(L)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--reader", default="argyll")
    ap.add_argument("--suite", default="baseline")
    a = ap.parse_args(argv)
    res = json.loads((Path(a.run_dir) / "results.json").read_text(encoding="utf-8"))
    print(f"### Key table, readout `{a.reader}` (* = real, held-out A2B; B2A via colprof proxy)\n")
    print(key_table(res, a.reader, a.suite))
    print(f"\n### Neutral axis, black, white, separation, readout `{a.reader}`\n")
    print(neutral_table(res, a.reader, a.suite))
    print("\n### Misread detection (accurate)\n")
    print(outlier_table(res, a.suite))


if __name__ == "__main__":
    main()
