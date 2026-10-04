"""Protocol v3 statistics (Agent 16, 2026-10-04).

Amends protocol v2.1 (``stats.py``, unchanged so every v2.1 verdict can be
reproduced). What is new, each for a reason Agent 13 measured:

1. **Measured seed term, per engine.** The minimum effect is
   ``max(5 % of base, 0.02, 2 x SD)`` where SD is the larger of the two
   engines' MEASURED between-seed SDs for that endpoint, noise level and ink
   class (``seedspread3``). v2.1 used one placeholder for everything, five
   times too small for the shipped engine's B2A p95 (SD 0.265, Agent 13 5.3).
   Missing cells fall back to the largest measured SD of that engine and
   endpoint over all classes (conservative), then to the placeholder, and
   every row says which (``seed_sd_source``).
2. **Means tested as means.** ISO 12647-7/-8 and ICC WP27 state MEANS; v3
   adds ``a2b.mean``, ``b2a.mean`` (point clouds, bootstrapped as means) and
   ``neutral_de.mean`` (a ramp row) beside the medians and p95s.
3. **Who can make a candidate BETTER.** Only rows on the SEALED set
   (``role == "sealed"``) and on a PRIMARY chart (targen at ChromIQ's
   defaults, or the ECG chart for 5+ inks) are ``claim_eligible``. Every
   other row (development printers, the robustness chart) is reported and
   can VETO, never make a claim.
4. **Families.** BETTER: Holm over every point row of the comparison (as
   v2.1 A7). The no-harm column (vetoes, D-03, D-09) reads Holm per
   printer x chart x endpoint x reader group, where the groups are the CMMs
   (Argyll, lcms, ColorSync), the application path (lcms with default flags,
   Ghostscript) and Ghostscript with black point compensation, each over
   both noise levels. ColorSync is a decision reader in v3.
5. **Per ink count.** ``breakdown`` counts verdicts per ink class and says
   which comparator covers which class, so "0 lost vs colprof" can never
   hide 5-7 inks, which colprof cannot build.

    python -m benchmarks.research.stats3 A_DIR B_DIR --engine-a colprof \\
        --engine-b accurate --seed-sd seed_sd_v3.json [--no-regression]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from benchmarks.research.stats import (N_BOOT, PLACEHOLDER_TERM, _significant, holm,
                                       paired_bootstrap, sign_flip_p)

ENDPOINTS = [("a2b", "median"), ("a2b", "mean"), ("a2b", "p95"),
             ("b2a", "median"), ("b2a", "mean"), ("b2a", "p95"),
             ("neutral_de", "median"), ("neutral_de", "mean"),
             ("neutral_hi", "mean")]
RAMP_KEYS = ("neutral_de", "neutral_hi")
READER_GROUPS = {"argyll": "cmm", "lcms": "cmm", "colorsync": "cmm",
                 "lcms-app": "app", "ghostscript": "app",
                 "ghostscript-bpc": "bpc", "multilinear": "continuity"}
DEFAULT_READERS = ("argyll", "lcms", "colorsync", "lcms-app", "ghostscript",
                   "ghostscript-bpc")
METHOD = ("v3: v2.1 tests; minimum effect from the MEASURED per-engine seed SD "
          "(larger of A and B); means tested as means; BETTER only on sealed rows of a "
          "primary chart; no-harm family = printer x chart x endpoint x reader group")


def ink_class(n_channels: int, color_rep: str) -> str:
    rep = color_rep.split("_")[0]
    if rep in ("iRGB", "RGB"):
        return "RGB"
    if rep == "CMY":
        return "CMY"
    if rep == "CMYK":
        return "CMYK"
    if any(c.islower() for c in rep):
        return f"CMYK+light ({n_channels})"
    return f"{n_channels} inks"


def split_variant(variant: str) -> dict:
    """'typical-targen900' / 'seed3-pessimistic-ecg1617' / 'base' -> parts."""
    parts = str(variant).split("-")
    out = {"seed": None, "level": None, "chart": None, "patches": None}
    for p in parts:
        if p.startswith("seed") and p[4:].isdigit():
            out["seed"] = int(p[4:])
        elif p in ("typical", "pessimistic", "none", "battery", "reread"):
            out["level"] = p
        else:
            for kind in ("targen", "ecg", "september"):
                if p.startswith(kind) and p[len(kind):].isdigit():
                    out["chart"], out["patches"] = kind, int(p[len(kind):])
    if out["level"] is None and variant == "base":
        out["level"] = "real"
    return out


CHART_ROLE = {"targen": "primary", "ecg": "primary", "september": "robustness", None: "real"}


# ---------------------------------------------------------------------------
# seed term
# ---------------------------------------------------------------------------

def seed_sd(table: dict | None, engine: str, level: str | None, cls: str,
            endpoint: str) -> tuple[float | None, str]:
    """SD of ``engine`` for ``endpoint`` (e.g. 'b2a.p95') at ``level`` and
    ink class ``cls``; -> (sd, source)."""
    if not table:
        return None, "placeholder"
    lv = level if level in ("typical", "pessimistic") else "typical"
    k = f"{engine}|{lv}|{cls}|{endpoint}"
    if k in table:
        return float(table[k]), f"measured:{k}"
    same = [v for kk, v in table.items()
            if kk.startswith(f"{engine}|{lv}|") and kk.endswith(f"|{endpoint}")]
    if same:
        return float(max(same)), f"fallback(max over classes):{engine}|{lv}|*|{endpoint}"
    other = [v for kk, v in table.items() if kk.endswith(f"|{endpoint}")
             and kk.split("|")[1] == lv]
    if other:
        return float(max(other)), f"fallback(max over engines):*|{lv}|*|{endpoint}"
    return None, "placeholder"


def minimum_effect(row: dict, table: dict | None, engine_a: str, engine_b: str,
                   min_rel: float = 0.05, min_abs: float = 0.02) -> None:
    st = row["endpoint"].split(".")[-1]
    sa, src_a = seed_sd(table, engine_a, row["level"], row["ink_class"], row["endpoint"])
    sb, src_b = seed_sd(table, engine_b, row["level"], row["ink_class"], row["endpoint"])
    sds = [s for s in (sa, sb) if s is not None]
    sd = max(sds) if sds else PLACEHOLDER_TERM[st] / 2.0
    row["seed_sd"] = sd
    row["seed_sd_source"] = src_a if (sa is not None and sa >= (sb or -1)) else src_b
    row["min_effect"] = max(min_rel * abs(row["a"]), min_abs, 2.0 * sd)


# ---------------------------------------------------------------------------
# rows
# ---------------------------------------------------------------------------

def _points(run_dir: Path, d: dict, engine: str, reader: str):
    stem = f"{d['suite']}-{d['name']}-{d['variant']}-{engine}"
    f = Path(run_dir) / "points" / f"{stem}-{reader}.npz"
    return dict(np.load(f)) if f.exists() else None


def row_arrays(fa: dict, fb: dict, key: str, kind: str):
    if kind == "real" and key != "a2b":
        return None, None
    src = "neutral_de" if key == "neutral_hi" else key
    if src not in fa or src not in fb or fa[src].shape != fb[src].shape:
        return None, None
    xa, xb = fa[src], fb[src]
    if key == "neutral_hi":
        m = fa["neutral_L"] >= 85.0
        xa, xb = xa[m], xb[m]
    if key == "neutral_de":
        lo = max(float(fa["neutral_black_L"]), float(fb["neutral_black_L"])) + 1
        m = fa["neutral_L"] >= lo
        xa, xb = xa[m], xb[m]
    return xa, xb


def is_ramp(r: dict) -> bool:
    return r["endpoint"].split(".")[0] in RAMP_KEYS


def build_rows(dir_a: Path, dir_b: Path, engine_a: str, engine_b: str,
               readers, n_boot: int = N_BOOT, results_a: dict | None = None) -> list[dict]:
    ra = results_a or json.loads((Path(dir_a) / "results.json").read_text(encoding="utf-8"))
    rows = []
    for d in ra["datasets"]:
        v = split_variant(d["variant"])
        cls = ink_class(d["n_channels"], d["color_rep"])
        chart = (d.get("info") or {}).get("chart") or v["chart"]
        for reader in readers:
            fa = _points(dir_a, d, engine_a, reader)
            fb = _points(dir_b, d, engine_b, reader)
            if fa is None or fb is None:
                continue
            for key, st in ENDPOINTS:
                xa, xb = row_arrays(fa, fb, key, d["kind"])
                if xa is None or len(xa) == 0:
                    continue
                r = paired_bootstrap(xa, xb, st, n_boot=n_boot,
                                     block="auto" if key in RAMP_KEYS else 1)
                r.update(dataset=d["name"], variant=d["variant"], reader=reader,
                         reader_group=READER_GROUPS.get(reader, "other"),
                         endpoint=f"{key}.{st}", role=d.get("role", "development"),
                         level=v["level"] or "real", chart=chart,
                         chart_role=CHART_ROLE.get(chart, "real"),
                         ink_class=cls, n_channels=d["n_channels"], kind=d["kind"])
                rows.append(r)
    return rows


def decide(rows: list[dict], engine_a: str, engine_b: str, table: dict | None,
           alpha: float = 0.05, min_rel: float = 0.05, min_abs: float = 0.02) -> list[dict]:
    for r in rows:
        minimum_effect(r, table, engine_a, engine_b, min_rel, min_abs)
    cloud = [i for i, r in enumerate(rows) if not is_ramp(r)]
    sig = [False] * len(rows)
    for i, s_ in zip(cloud, _significant([rows[i] for i in cloud], alpha)):
        sig[i] = s_
    groups: dict = defaultdict(list)
    for i in cloud:
        r = rows[i]
        groups[(r["dataset"], r["chart"], r["endpoint"], r["reader_group"])].append(i)
    sig_pe = [False] * len(rows)
    for idx in groups.values():
        for i, s_ in zip(idx, _significant([rows[i] for i in idx], alpha)):
            sig_pe[i] = s_
    for i, r in enumerate(rows):
        big = abs(r["diff"]) >= r["min_effect"]
        word = "BETTER" if r["diff"] < 0 else "WORSE"
        r["family_size"] = len(cloud)
        r["claim_eligible"] = r["role"] == "sealed" and r["chart_role"] == "primary"
        if is_ramp(r):
            r["holm_significant"] = False
            r["verdict"] = (word + "*") if big else "TIE"
            r["verdict_per_printer_endpoint"] = r["verdict"]
            continue
        r["holm_significant"] = sig[i]
        r["verdict"] = word if (sig[i] and big) else "TIE"
        r["verdict_per_printer_endpoint"] = word if (sig_pe[i] and big) else "TIE"
    return rows


def ramp_seed_verdicts(rows: list[dict], alpha: float = 0.05) -> list[dict]:
    """v2.1 A4 per printer x LEVEL x CHART x reader x endpoint (v2.1 grouped
    without level and chart, which would pool two noise levels)."""
    groups: dict = defaultdict(list)
    for r in rows:
        if is_ramp(r) and split_variant(r["variant"])["seed"] is not None:
            groups[(r["dataset"], r["level"], r["chart"], r["reader"], r["endpoint"])].append(r)
    out = []
    for (ds, lv, ch, rd, ep), rr in groups.items():
        d = np.array([x["diff"] for x in rr])
        out.append({"dataset": ds, "level": lv, "chart": ch, "reader": rd, "endpoint": ep,
                    "seeds": len(d), "mean_diff": float(d.mean()),
                    "a": float(np.mean([x["a"] for x in rr])),
                    "min_effect": max(x["min_effect"] for x in rr),
                    "p": sign_flip_p(d), "p_min_possible": 2.0 / 2 ** len(d)})
    rej = holm([g["p"] for g in out], alpha)
    for g, s_ in zip(out, rej):
        big = abs(g["mean_diff"]) >= g["min_effect"]
        g["verdict"] = (("BETTER" if g["mean_diff"] < 0 else "WORSE")
                        if (s_ and big) else "TIE")
    return out


def no_regression(rows: list[dict], ramp_seeds: list[dict] | None = None,
                  reader_groups=("cmm", "app")) -> dict:
    """v2.1's no-regression test on the v3 per-family column. Rows of the
    'bpc' group (Ghostscript's default black point compensation) are
    reported, not gated: BPC is a CMM policy, not the profile's table."""
    seeds = {(g["dataset"], g["level"], g["chart"], g["reader"], g["endpoint"]): g
             for g in (ramp_seeds or [])}
    worse, open_, cleared = [], [], []
    for r in rows:
        if r["reader_group"] not in reader_groups:
            continue
        v = r["verdict_per_printer_endpoint"]
        tag = f"{r['dataset']} {r['variant']} {r['reader']} {r['endpoint']}"
        if v == "WORSE":
            worse.append(tag)
        elif v == "WORSE*":
            g = seeds.get((r["dataset"], r["level"], r["chart"], r["reader"], r["endpoint"]))
            if g is None:
                open_.append(tag)
            elif g["verdict"] == "WORSE":
                worse.append(tag + " (confirmed over seeds)")
            else:
                cleared.append(tag)
    return {"pass": not worse and not open_, "worse": worse,
            "open_ramp_rows": open_, "cleared_ramp_rows": cleared}


def breakdown(rows: list[dict], engine_a: str, engine_b: str,
              results_a: dict | None = None) -> dict:
    """Verdict counts per ink class (per printer x endpoint column), and
    which classes the comparison covers at all (a comparator that cannot
    build a class contributes NO rows there: 'not covered', never '0 lost')."""
    out: dict = {"engine_a": engine_a, "engine_b": engine_b, "classes": {}}
    for r in rows:
        c = out["classes"].setdefault(r["ink_class"], {"printers": set(), "rows": 0,
                                                       "BETTER": 0, "WORSE": 0, "TIE": 0,
                                                       "BETTER*": 0, "WORSE*": 0})
        c["printers"].add(r["dataset"])
        c["rows"] += 1
        c[r["verdict_per_printer_endpoint"]] += 1
    for c in out["classes"].values():
        c["printers"] = sorted(c["printers"])
    if results_a is not None:
        present = defaultdict(set)
        for d in results_a["datasets"]:
            present[ink_class(d["n_channels"], d["color_rep"])].add(d["name"])
        for cls, names in present.items():
            if cls not in out["classes"]:
                out["classes"][cls] = {"printers": [], "rows": 0, "not_covered": sorted(names),
                                       "why": f"no {engine_a} or {engine_b} profile scored "
                                              f"(e.g. colprof cannot build 5-7 inks)"}
    return out


def compare(dir_a: Path, dir_b: Path, engine_a: str, engine_b: str, readers,
            table: dict | None = None, alpha: float = 0.05, n_boot: int = N_BOOT) -> dict:
    ra = json.loads((Path(dir_a) / "results.json").read_text(encoding="utf-8"))
    rows = build_rows(dir_a, dir_b, engine_a, engine_b, readers, n_boot, results_a=ra)
    decide(rows, engine_a, engine_b, table, alpha)
    seeds = ramp_seed_verdicts(rows, alpha)
    return {"a": str(dir_a), "b": str(dir_b), "engine_a": engine_a, "engine_b": engine_b,
            "method": METHOD, "alpha": alpha, "rows": rows, "ramp_seeds": seeds,
            "breakdown": breakdown(rows, engine_a, engine_b, ra)}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir_a")
    ap.add_argument("dir_b")
    ap.add_argument("--engine-a", default="accurate")
    ap.add_argument("--engine-b", default="accurate")
    ap.add_argument("--reader", nargs="+", default=list(DEFAULT_READERS))
    ap.add_argument("--seed-sd", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--no-regression", action="store_true")
    args = ap.parse_args(argv)
    table = json.loads(Path(args.seed_sd).read_text(encoding="utf-8")) if args.seed_sd else None
    res = compare(Path(args.dir_a), Path(args.dir_b), args.engine_a, args.engine_b,
                  args.reader, table)
    for r in res["rows"]:
        pe = r["verdict_per_printer_endpoint"]
        print(f"{r['dataset']:>22} {r['variant']:>24} {r['reader']:>15} {r['endpoint']:>18}: "
              f"{r['a']:.3f} -> {r['b']:.3f} ({r['rel'] * 100:+.1f} %, CI [{r['ci95'][0]:+.3f}, "
              f"{r['ci95'][1]:+.3f}], min eff {r['min_effect']:.3f}) {r['verdict']}"
              f"{'' if pe == r['verdict'] else f' (per family: {pe})'}"
              f"{'' if r['claim_eligible'] else ' [no claim: ' + r['role'] + '/' + r['chart_role'] + ']'}")
    print("\nPER INK CLASS (per-family column):")
    for cls, c in sorted(res["breakdown"]["classes"].items()):
        if "not_covered" in c:
            print(f"  {cls:>18}: NOT COVERED ({', '.join(c['not_covered'])}): {c['why']}")
        else:
            print(f"  {cls:>18}: {len(c['printers'])} printers, {c['rows']} rows: "
                  + ", ".join(f"{k} {c[k]}" for k in ("BETTER", "WORSE", "TIE", "BETTER*", "WORSE*")))
    if args.no_regression:
        nr = no_regression(res["rows"], res["ramp_seeds"])
        res["no_regression"] = nr
        print(f"\nNO-REGRESSION (v3 family): {'PASS' if nr['pass'] else 'FAIL'}; "
              f"{len(nr['worse'])} WORSE, {len(nr['open_ramp_rows'])} open ramp rows")
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    if args.no_regression and not res["no_regression"]["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
