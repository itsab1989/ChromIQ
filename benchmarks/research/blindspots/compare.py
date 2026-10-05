"""Agent 23: line up the H-test numbers of one dataset across builders and
flag where one builder is clearly worse than the best of the others.

    python -m benchmarks.research.blindspots.compare OUT NAME [NAME ...] [--all]
        [--engines colprof,fast,accurate] [--focus accurate]

A metric row is flagged when the focus builder exceeds the best other
builder by more than the row's margin (absolute) AND by 25 % (relative).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# (regex on the flattened key, direction (+1 = larger is worse), margin)
RULES = [
    (r"\.l_rev$", +1, 0.5), (r"\.l_rev_max$", +1, 0.3), (r"\.l_swing$", +1, 0.3),
    (r"\.d2_excess_max$", +1, 0.5), (r"\.jump_ratio$", +1, 1.0),
    (r"\.dev_d2_max$", +1, 0.05), (r"chroma_max$", +1, 0.5), (r"chroma_mean$", +1, 0.3),
    (r"white_ink(_pct)?$", +1, 0.3), (r"shadow_codes_lost$", +1, 4),
    (r"hue_step_max$", +1, 5), (r"hue_range$", +1, 10), (r"hue_back_steps$", +1, 2),
    (r"hue_back_max$", +1, 2), (r"hue_err_max$", +1, 5),
    (r"ingamut_de_(p95|max|mean|p99)$", +1, 0.75), (r"\.de00$", +1, 1.0),
    (r"ipt_hue_shift$", +2, 3.0), (r"new_edges$", +1, 20), (r"new_edge_max$", +1, 0.75),
    (r"contrast_ratio_p05$", -1, 0.1), (r"(p95|max)$", +1, 0.75),
    (r"over_tac_share$", +1, 0.001), (r"oog_clip_hue_(p95|max)$", +1, 5),
    (r"black_L$", +1, 1.0), (r"black_C$", +1, 1.0), (r"gamt_agree$", -1, 0.03),
    (r"gamt_says_\w+$", +1, 0.03), (r"abs_paper_ink_pct$", +1, 0.3),
    (r"wtpt_de00$", +1, 0.3), (r"abs_b2a_(median|p95)$", +1, 0.5),
    (r"a2b_[ps]_vs_r_(p95|max)$", +1, 1.0), (r"idempotence_\w+_(p95|max)$", +1, 0.5),
]


def flat(d, pre=""):
    out = {}
    for k, v in d.items():
        key = f"{pre}.{k}" if pre else k
        if isinstance(v, dict):
            out.update(flat(v, key))
        elif isinstance(v, bool):
            out[key] = float(v)
        elif isinstance(v, (int, float)) and v is not None:
            out[key] = float(v)
    return out


def rule(key):
    for rx, d, m in RULES:
        if re.search(rx, key):
            return d, m
    return None


def compare(out: Path, name: str, engines, focus: str, show_all=False):
    data = {}
    for e in engines:
        p = out / "hunt" / f"{name}-{e}.json"
        if p.exists():
            data[e] = flat(json.loads(p.read_text()))
    if focus not in data:
        return []
    rows = []
    for key, v in data[focus].items():
        r = rule(key)
        if r is None:
            continue
        d, m = r
        others = [data[e][key] for e in data if e != focus and key in data[e]]
        if not others:
            continue
        if d == 2:             # signed: compare magnitudes
            v_, oth = abs(v), [abs(o) for o in others]
            d = 1
        else:
            v_, oth = v, others
        best = min(oth) if d > 0 else max(oth)
        worse = (v_ - best) * d
        if show_all or (worse > m and abs(worse) > 0.25 * max(abs(best), 1e-9)):
            rows.append((key, {e: data[e].get(key) for e in data}, worse))
    rows.sort(key=lambda r: -r[2])
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("names", nargs="+")
    ap.add_argument("--engines", default="colprof,fast,accurate")
    ap.add_argument("--focus", default="accurate")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--grep", default="")
    a = ap.parse_args(argv)
    for name in a.names:
        rows = compare(Path(a.out), name, a.engines.split(","), a.focus, a.all)
        print(f"== {name}: {len(rows)} rows where {a.focus} is worse than the best other builder")
        for key, vals, w in rows:
            if a.grep and not re.search(a.grep, key):
                continue
            print(f"  {key:55s} " + "  ".join(f"{e}={v:.3g}" if v is not None else f"{e}=-"
                                               for e, v in vals.items()))


if __name__ == "__main__":
    main()
