"""Tables for the options audit (Agent 10b): analysis.json -> markdown.

    python -m benchmarks.research.options_report --out DIR > tables.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def g(d, *ks, f="{:.3f}"):
    for k in ks:
        if not isinstance(d, dict) or k not in d:
            return "-"
        d = d[k]
    if isinstance(d, (int, float)):
        return f.format(d)
    return str(d)


def lut_line(row):
    vb = row.get("vs_base")
    if not vb:
        return "(base)" if row["label"] == "base" else "-"
    diff = [k for k, same in vb["lut_identical"].items() if not same]
    return "identical" if not diff else ",".join(diff)


def grids(row):
    f = row.get("facts") or {}
    L = f.get("luts", {})
    a = L.get("A2B1") or L.get("A2B0") or {}
    b = L.get("B2A1") or L.get("B2A0") or {}
    return f"{a.get('grid', '-')}/{b.get('grid', '-')}"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--blocks", default="")
    a = ap.parse_args(argv)
    rows = json.loads((Path(a.out) / "analysis.json").read_text(encoding="utf-8"))
    blocks = [b for b in a.blocks.split(",") if b] or sorted({r["block"] for r in rows})
    order = {"base": 0}
    for blk in sorted(blocks, key=lambda b: order.get(b, 1)):
        rs = [r for r in rows if r["block"] in (blk,)]
        if not rs:
            continue
        print(f"\n### {blk}\n")
        print("| ds | label | builder | ok | grids A2B/B2A | LUTs differing from default | "
              "A2B vs default p95 | B2A vs default max dev | A2B med/p95 | B2A med/p95 | "
              "neutral dE med / C*max / rev | black L* | note |")
        print("|" + "---|" * 13)
        for r in sorted(rs, key=lambda r: (r["ds"], r["label"], r["builder"])):
            s = ((r.get("score") or {}).get("argyll")) or {}
            vb = (r.get("vs_base") or {}).get("diff") or {}
            note = ""
            if not r["ok"]:
                note = (r.get("error") or "")[-160:].replace("\n", " ").replace("|", "/")
            k = (r.get("score") or {}).get("k")
            if k:
                note += (f"K@L20/40/60/80 rel {k['neutral_r']['K']} perc {k['neutral_p']['K']}; "
                         f"ink mean {k['ink_mean']:.0f} max {k['ink_max']:.0f}")
                if "dark_sat_K_mean" in k:
                    note += f"; dark-sat K {k['dark_sat_K_mean']:.2f}"
            gq = (r.get("score") or {}).get("gmq")
            if gq:
                for it in ("p", "s"):
                    q = gq.get(it) or {}
                    if "M1_neutral_C_mean" in q:
                        note += f" gmq-{it} M1 {q['M1_neutral_C_mean']:.2f}"
            print(f"| {r['ds']} | {r['label']} | {'eng' if r['builder'] == 'accurate' else 'cp'} "
                  f"| {'ok' if r['ok'] else 'FAIL'} | {grids(r)} | {lut_line(r)} | "
                  f"{g(vb, 'a2b_de00', 'p95')} | {g(vb, 'b2a_device_maxch', 'max')} | "
                  f"{g(s, 'a2b', 'all', 'median')}/{g(s, 'a2b', 'all', 'p95')} | "
                  f"{g(s, 'b2a', 'all', 'median')}/{g(s, 'b2a', 'all', 'p95')} | "
                  f"{g(s, 'neutral', 'de', 'median')} / {g(s, 'neutral', 'chroma_max')} / "
                  f"{g(s, 'neutral', 'L_reversals', f='{}')} | {g(s, 'black', 'printed_L', f='{:.2f}')} "
                  f"| {note} |")


if __name__ == "__main__":
    main()
