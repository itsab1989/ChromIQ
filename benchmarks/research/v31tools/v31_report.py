"""Agent 16b: battery v3.1 analysis of the frozen baseline (research-integration-2 vs colprof).

    python v31_report.py BASE_DIR     (BASE_DIR = Benchmarks/baseline-v31-f84456d0)

Writes BASE_DIR/analysis/: seed_sd_v31.json (+ -detail), compare-le4.json, report.md.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "tree"))
from benchmarks.research import oogq, seedspread3, stats3  # noqa: E402


def load(p: Path):
    f = p / "results.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def fmt(x, nd=2):
    if x is None:
        return "-"
    if isinstance(x, float) and abs(x - round(x)) < 1e-9 and abs(x) >= 10:
        return f"{x:.0f}"
    return f"{x:.{nd}f}"


def main():
    base = Path(sys.argv[1])
    an = base / "analysis"
    an.mkdir(exist_ok=True)
    lines = ["# Battery v3.1 frozen baseline: research-integration-2 Maximum accuracy vs colprof", ""]
    # 1. seed SD
    seeds = load(base / "seeds")
    table = {}
    if seeds:
        table, detail = seedspread3.spread(seeds)
        (an / "seed_sd_v31.json").write_text(json.dumps(table, indent=1, sort_keys=True), encoding="utf-8")
        (an / "seed_sd_v31-detail.json").write_text(json.dumps(detail, indent=1), encoding="utf-8")
        nseeds = defaultdict(int)
        for k, v in detail.items():
            eng, pr, r, lv, ch, ep = k.split("|")
            nseeds[(eng, pr, lv)] = max(nseeds[(eng, pr, lv)], v["n"])
        lines += ["## 1. Between-seed SD of the v3.1 rows (seeds3, targen 900)", "",
                  "Seeds per engine x printer x level: " + ", ".join(
                      f"{e} {p} {l} {n}" for (e, p, l), n in sorted(nseeds.items())), "",
                  "| key | finding | floor | " + " | ".join(
                      f"{e} {l} {c}" for e, l, c in COLS) + " | min effect vs colprof, typical CMYK / RGB |",
                  "|---|---|---|" + "---|" * len(COLS) + "---|"]
        for k, (sg, fl, sf, fd, _) in oogq.KEYS.items():
            vals = [table.get(f"{e}|{l}|{c}|q.{k}") for e, l, c in COLS]
            me = []
            for c in ("CMYK", "RGB"):
                sds = [table.get(f"{e}|typical|{c}|q.{k}") for e in ("colprof", "accurate")]
                sds = [s for s in sds if s is not None]
                me.append(fmt(max(fl, 2 * max(sds))) if sds else "-")
            lines.append(f"| {k}{' (S)' if sf else ''} | {fd} | {fl} | " +
                         " | ".join(fmt(v) for v in vals) + f" | {' / '.join(me)} |")
        for ep in ("pale.median", "pale.p95", "pale_dl.mean", "pale_dl.p95"):
            vals = [table.get(f"{e}|{l}|{c}|{ep}") for e, l, c in COLS]
            lines.append(f"| {ep} (points, pooled over readers) | F-14 | - | " +
                         " | ".join(fmt(v, 3) for v in vals) + " | |")
        lines.append("")
    # 2. le4 comparison colprof -> accurate
    le4 = base / "le4"
    if load(le4):
        res = stats3.compare(le4, le4, "colprof", "accurate", list(stats3.DEFAULT_READERS), table)
        rows, prows = res["rows"], res["property_rows"]
        allr, alls = rows + prows, res["ramp_seeds"] + res["property_seeds"]
        nr = stats3.no_regression(allr, alls)
        ra = load(le4)
        w = stats3.weighed_adoption(allr, stats3.safety_rows(ra, ra, "colprof", "accurate"), alls)
        nr_v3 = stats3.no_regression(rows, res["ramp_seeds"])
        w_v3 = stats3.weighed_adoption(rows, stats3.safety_rows(ra, ra, "colprof", "accurate"),
                                       res["ramp_seeds"])
        (an / "compare-le4.json").write_text(json.dumps(
            {"no_regression": nr, "weighed": w, "property_rows": prows,
             "no_regression_v3_rows_only": nr_v3, "weighed_v3_rows_only": w_v3,
             "breakdown": res["breakdown"]}, indent=1, default=str), encoding="utf-8")
        cnt = defaultdict(lambda: defaultdict(int))
        for r in rows:
            cnt["v3 rows"][r["verdict_per_printer_endpoint"]] += 1
        for r in prows:
            cnt["v3.1 property rows"][r["verdict"]] += 1
            if r["safety"]:
                cnt["  of them safety"][r["verdict"]] += 1
        lines += ["## 2. <= 4 inks: colprof (A) -> Maximum accuracy (B), every chart and level", "",
                  "| rows | BETTER | WORSE | TIE | BETTER* | WORSE* |", "|---|---|---|---|---|---|"]
        for k, c in cnt.items():
            lines.append(f"| {k} | " + " | ".join(str(c.get(v, 0)) for v in
                                                 ("BETTER", "WORSE", "TIE", "BETTER*", "WORSE*")) + " |")
        lines += ["", f"Strict no-regression, v3 rows only: {'PASS' if nr_v3['pass'] else 'FAIL'} "
                      f"({len(nr_v3['worse'])} WORSE, {len(nr_v3['open_ramp_rows'])} open)",
                  f"Strict no-regression, v3.1 (with property rows): {'PASS' if nr['pass'] else 'FAIL'} "
                  f"({len(nr['worse'])} WORSE, {len(nr['open_ramp_rows'])} open)",
                  f"D-17 weighed, v3 rows only: {'PASS' if w_v3['pass'] else 'FAIL'}; {w_v3['wins']} wins / "
                  f"{w_v3['losses']} losses, {len(w_v3['safety_losses'])} safety",
                  f"D-17 weighed, v3.1: {'PASS' if w['pass'] else 'FAIL'}; {w['wins']} wins / "
                  f"{w['losses']} losses, {len(w['large_losses'])} above tolerance, "
                  f"{len(w['safety_losses'])} safety", ""]
        # per key: how many datasets x level x chart WORSE*/BETTER*
        per = defaultdict(lambda: defaultdict(int))
        for r in prows:
            per[r["endpoint"]][r["verdict"]] += 1
        lines += ["### Property rows per key (datasets x level x chart)", "",
                  "| key | safety | WORSE* | BETTER* | TIE |", "|---|---|---|---|---|"]
        for k in oogq.KEYS:
            c = per.get(f"q.{k}")
            if c:
                lines.append(f"| {k} | {'yes' if oogq.KEYS[k][2] else ''} | {c['WORSE*']} | "
                             f"{c['BETTER*']} | {c['TIE']} |")
        # headline table typical targen 900
        lines += ["", "### Headline numbers, typical noise, targen 900 (real sets: base), colprof / Maximum accuracy", ""]
        keys = ["oog_ramp_rev_r", "image_contours_r", "pale_oog_dL_max_r", "blue_ipt_abs_r",
                "ramp_rev_p", "ramp_rev_s", "grey_swing_p", "grey_swing_r", "below_black_swing_r",
                "black_gap_p", "black_C_p", "abs_white_de", "gmq_p_M11_rt_median"]
        lines += ["| set | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
        for d in ra["datasets"]:
            if d["variant"] not in ("typical-targen900", "base"):
                continue
            qa = ((d["profiles"].get("colprof") or {}).get("oogq") or {}).get("q") or {}
            qb = ((d["profiles"].get("accurate") or {}).get("oogq") or {}).get("q") or {}
            lines.append(f"| {d['name']} | " + " | ".join(
                f"{fmt(qa.get(k))} / {fmt(qb.get(k))}" for k in keys) + " |")
        lines += ["", "### Safety losses (D-17 2c), all", ""]
        for x in w["safety_losses"]:
            if "cell" in x:
                lines.append(f"- {x['cell']} {x['reader']} {x['level']}: {x['diff']:+.3f}")
            else:
                lines.append(f"- {x['row']}: {x['check']} {fmt(x['a'])} -> {fmt(x['b'])}")
        lines.append("")
    # 3. multi
    mres = load(base / "multi")
    if mres:
        keys = ["grey_swing_p", "grey_shadow_swing_p", "grey_swing_r", "black_gap_p", "black_C_p",
                "pale_oog_dL_max_r", "pale_oog_dL_max_p", "oog_ramp_rev_r", "ramp_rev_p",
                "image_contours_r", "blue_ipt_abs_r", "gmq_p_M1_neutral_C_mean", "gmq_p_M11_rt_median"]
        lines += ["## 3. 5-7 inks and the real 7-ink sets: Maximum accuracy against the PROPOSED absolute limits", "",
                  "Limits (`oogq.ABSOLUTE`, proposed, not confirmed): " + ", ".join(
                      f"{k} {v}" for k, v in oogq.ABSOLUTE.items() if k in keys), "",
                  "| set | variant | " + " | ".join(keys) + " | NC5 jumps | NC3 grey extra ink |",
                  "|---|---|" + "---|" * (len(keys) + 2)]
        above = defaultdict(int)
        for d in mres["datasets"]:
            p = d["profiles"].get("accurate") or {}
            q = (p.get("oogq") or {}).get("q") or {}
            nc = p.get("ncq") or {}
            cells = []
            for k in keys:
                v = q.get(k)
                lim = oogq.ABSOLUTE.get(k)
                flag = "**" if (v is not None and lim is not None and v > lim) else ""
                if flag:
                    above[k] += 1
                cells.append(f"{flag}{fmt(v)}{flag}")
            lines.append(f"| {d['name']} | {d['variant']} | " + " | ".join(cells) +
                         f" | {fmt(nc.get('NC5 visible jumps'))} | {fmt(nc.get('NC3 grey extra ink max'))} |")
        lines += ["", "Bold = above the proposed absolute limit. Profiles above per key: " +
                  ", ".join(f"{k} {n}" for k, n in above.items()), ""]
        refs = an / "references.json"
        if refs.exists():
            rr = json.loads(refs.read_text(encoding="utf-8"))
            lines += ["### Commercial reference profiles on the same rows (yardstick; the set's own proxy truth)", "",
                      "| profile | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
            for nm, q in rr.items():
                lines.append(f"| {nm} | " + " | ".join(fmt(q.get(k)) for k in keys) + " |")
            lines.append("")
    (an / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


COLS = [("colprof", "typical", "RGB"), ("accurate", "typical", "RGB"),
        ("colprof", "typical", "CMYK"), ("accurate", "typical", "CMYK"),
        ("colprof", "pessimistic", "CMYK"), ("accurate", "pessimistic", "CMYK"),
        ("accurate", "typical", "6 inks")]

if __name__ == "__main__":
    main()
