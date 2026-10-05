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
             ("neutral_hi", "mean"),
             # protocol v3 N (Agent 14's v2.2 N2): 5+ inks only
             ("e7", "median"), ("e7", "p95"), ("e7b", "median"), ("e8", "median"),
             ("e8", "p95"), ("e9", "median"), ("e9", "mean"), ("e9", "p95"),
             # Agent 21 (F-14) proposal E10: pale in-gamut colours through the B2A
             ("pale", "median"), ("pale", "p95")]
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


# ---------------------------------------------------------------------------
# D-17: the weighed adoption rule (Basti, 2026-10-05)
# ---------------------------------------------------------------------------

SMALL_LOSS = {"median": 0.05, "mean": 0.05, "p95": 0.15, "max": 0.15}
SMALL_LOSS_REL = 0.10
REREAD_FLOOR = {"median": 0.19, "mean": 0.19, "p95": 0.5, "max": 0.5}   # Agent 6, per reading
# grey axis rows of the decision table are SAFETY rows (D-17 2c): zero tolerance
SAFETY_ENDPOINT_KEYS = ("neutral_de", "neutral_hi")


def _cell(r):
    return (r["dataset"], r["chart"], r["endpoint"])


def small_loss(r: dict, use_ci: bool = False) -> bool:
    """D-17 2b on the point difference; ``use_ci`` reads it the way a
    non-inferiority trial does (ICH E9 / EMA margin guideline): the whole
    95 % CI of the loss must stay inside the margin."""
    st = r["endpoint"].split(".")[-1]
    d = abs(r["diff"]) if not use_ci else max(abs(r["ci95"][0]), abs(r["ci95"][1]))
    return (d <= SMALL_LOSS[st] and abs(r.get("rel", 0.0)) <= SMALL_LOSS_REL
            and d < REREAD_FLOOR[st])


def safety_rows(results_a: dict, results_b: dict | None, engine_a: str, engine_b: str,
                reader: str = "argyll") -> list[dict]:
    """D-17 2c property checks, zero tolerance: B may not be worse than A on
    black depth (0.5 L*) or black chroma (0.5), ink in paper white (0.05 %),
    ink-limit compliance, L* reversals or banding on the neutral ramp (5 %,
    at least 0.05), and B's build must succeed wherever A's did."""
    results_b = results_b or results_a
    by_b = {(d["name"], d["variant"]): d for d in results_b["datasets"]}
    out = []
    for d in results_a["datasets"]:
        db = by_b.get((d["name"], d["variant"]))
        if db is None:
            continue
        pa, pb = d["profiles"].get(engine_a), db["profiles"].get(engine_b)
        if not pa or not pb:
            continue
        tag = f"{d['name']} {d['variant']}"
        if pa.get("ok") and not pb.get("ok"):
            out.append({"row": tag, "check": "build", "a": "ok", "b": "FAILED"})
            continue
        sa = (pa.get("scores") or {}).get(reader) or {}
        sb = (pb.get("scores") or {}).get(reader) or {}
        if "black" not in sa or "black" not in sb:
            continue

        def g(s, *path):
            x = s
            for k in path:
                x = x.get(k) if isinstance(x, dict) else None
            return x
        checks = [("black depth L*", g(sa, "black", "printed_L"), g(sb, "black", "printed_L"), 0.5),
                  ("black chroma", float(np.hypot(*sa["black"]["printed_ab"])),
                   float(np.hypot(*sb["black"]["printed_ab"])), 0.5),
                  ("paper-white ink %", g(sa, "white", "max_ink_pct"), g(sb, "white", "max_ink_pct"), 0.05),
                  ("over ink limit", g(sa, "b2a", "over_limit_frac"), g(sb, "b2a", "over_limit_frac"), 0.0),
                  ("neutral L* reversals", g(sa, "neutral", "L_reversals"), g(sb, "neutral", "L_reversals"), 0),
                  ("neutral banding d2", g(sa, "neutral", "banding_max_d2"),
                   g(sb, "neutral", "banding_max_d2"), None),
                  # v2.2 section 5 N-colour safety rows (5+ inks)
                  ("NC5 visible gradient jumps", g(pa, "ncq", "NC5 visible jumps"),
                   g(pb, "ncq", "NC5 visible jumps"), 0),
                  ("NC3 extra ink on the grey axis", g(pa, "ncq", "NC3 grey extra ink max"),
                   g(pb, "ncq", "NC3 grey extra ink max"), 0.01),
                  ("NC6 over the ink limit", g(pa, "ncq", "NC6 over limit"),
                   g(pb, "ncq", "NC6 over limit"), 0),
                  ("F-12 gross extrapolation", g(sa, "nc", "gross_extrapolation"),
                   g(sb, "nc", "gross_extrapolation"), 0)]
        for name, a, b, tol in checks:
            if a is None or b is None or isinstance(a, dict) or isinstance(b, dict):
                continue
            a, b = float(a), float(b)
            t = max(0.05, 0.05 * abs(a)) if tol is None else tol
            if b > a + t:
                out.append({"row": tag, "check": name, "a": a, "b": b, "tolerance": t})
    return out


def weighed_adoption(rows: list[dict], safety: list[dict] | None = None,
                     ramp_seeds: list[dict] | None = None,
                     reader_groups=("cmm", "app")) -> dict:
    """D-17: may B be adopted although it is not strictly never worse?
    Cells = printer x chart x endpoint over the decision reader groups. A
    cell is a LOSS if any row is WORSE (or WORSE* not cleared over seeds),
    else a WIN if any row is BETTER (or a ramp row confirmed BETTER). PASS
    needs (a) clearly more wins than losses (at least 2 to 1) and a larger
    total win than total loss, (b) every loss small (<= 0.05 median/mean,
    <= 0.15 p95/max, <= 10 % relative, below the reread floor), (c) no loss
    on a safety row (grey axis ramps, and ``safety`` property checks)."""
    seeds = {(g["dataset"], g["level"], g["chart"], g["reader"], g["endpoint"]): g
             for g in (ramp_seeds or [])}
    cells: dict = defaultdict(lambda: {"win": [], "loss": []})
    for r in rows:
        if r["reader_group"] not in reader_groups:
            continue
        v = r["verdict_per_printer_endpoint"]
        key = (r["dataset"], r["level"], r["chart"], r["reader"], r["endpoint"])
        if v == "WORSE*":
            g = seeds.get(key)
            v = "WORSE" if g is None or g["verdict"] == "WORSE" else (
                "BETTER" if g["verdict"] == "BETTER" else "TIE")
        elif v == "BETTER*":
            g = seeds.get(key)
            v = "BETTER" if g is not None and g["verdict"] == "BETTER" else "TIE"
        if v == "WORSE":
            cells[_cell(r)]["loss"].append(r)
        elif v == "BETTER":
            cells[_cell(r)]["win"].append(r)
    wins = {c: v["win"] for c, v in cells.items() if v["win"] and not v["loss"]}
    losses = {c: v["loss"] for c, v in cells.items() if v["loss"]}
    win_size = sum(max(abs(r["diff"]) for r in rr) for rr in wins.values())
    loss_size = sum(max(abs(r["diff"]) for r in rr) for rr in losses.values())
    listed, big, unsafe = [], [], []
    for c, rr in losses.items():
        worst = max(rr, key=lambda r: abs(r["diff"]))
        item = {"cell": " ".join(str(x) for x in c), "diff": worst["diff"], "rel": worst["rel"],
                "reader": worst["reader"], "level": worst["level"], "small": small_loss(worst),
                "small_by_ci": small_loss(worst, use_ci=True), "ci95": worst["ci95"],
                "safety": c[2].split(".")[0] in SAFETY_ENDPOINT_KEYS}
        listed.append(item)
        if item["safety"]:
            unsafe.append(item)
        elif not item["small"]:
            big.append(item)
    safety = safety or []
    net_ok = len(wins) >= 2 * len(losses) and win_size > loss_size
    ok = net_ok and not big and not unsafe and not safety
    ok_ci = net_ok and not unsafe and not safety and all(x["small_by_ci"] for x in listed
                                                          if not x["safety"])
    return {"pass": ok, "pass_noninferiority_ci": ok_ci, "rule": "D-17 weighed adoption", "wins": len(wins), "losses": len(losses),
            "win_size": win_size, "loss_size": loss_size, "net_benefit": net_ok,
            "large_losses": big, "safety_losses": unsafe + safety, "all_losses": listed}


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
    ap.add_argument("--weighed", action="store_true",
                    help="also the D-17 weighed adoption rule (net benefit, small-loss "
                         "tolerance, zero-tolerance safety rows); exit 1 if it fails")
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
    if args.weighed:
        ra = json.loads((Path(args.dir_a) / "results.json").read_text(encoding="utf-8"))
        rb = json.loads((Path(args.dir_b) / "results.json").read_text(encoding="utf-8"))
        w = weighed_adoption(res["rows"], safety_rows(ra, rb, args.engine_a, args.engine_b),
                             res["ramp_seeds"])
        res["weighed"] = w
        print(f"\nD-17 WEIGHED ADOPTION: {'PASS' if w['pass'] else 'FAIL'}; {w['wins']} winning "
              f"cells ({w['win_size']:.3f}) vs {w['losses']} losing ({w['loss_size']:.3f}); "
              f"{len(w['large_losses'])} losses above tolerance, {len(w['safety_losses'])} safety losses")
        for x in w["all_losses"]:
            print(f"  loss {x['cell']} {x['reader']} {x['level']}: {x['diff']:+.3f} "
                  f"({x['rel'] * 100:+.1f} %){' SAFETY' if x['safety'] else ''}"
                  f"{'' if x['small'] else ' ABOVE TOLERANCE'}")
        for x in w["safety_losses"]:
            if "check" in x:
                print(f"  safety {x['row']}: {x['check']} {x['a']} -> {x['b']}")
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    if args.weighed and not res["weighed"]["pass"]:
        raise SystemExit(1)
    if args.no_regression and not res["no_regression"]["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
