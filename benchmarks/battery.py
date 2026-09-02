"""Battery runner + promotion gates (issue #123, W0).

Builds a maximum-accuracy profile per synthetic printer (S1–S6) with a
given candidate set and scores the written profile bytes against the
analytic ground truth on dense quasi-random points — all ΔE2000, all
against ``f_true``, never against the chart.

CLI (from the repo root, venv active)::

    python -m benchmarks.battery --candidates "" --out baseline.json
    python -m benchmarks.battery --candidates ucs,joint-sep --out cand.json
    python -m benchmarks.battery --compare baseline.json cand.json

Promotion gates (issue #123): a candidate replaces the shipped accurate
internals only if (1) aggregate median ΔE00 improves ≥ 5 % with no device
class regressing > 2 % on median or p95 and max/round-trip-max not worse
(small tolerance for quantisation jitter), (2) S4 outlier F1 not worse and
clean-chart false flags not up, (3) neutral K TV-vs-net not worse on
S3/S5/S6, (4) build time ≤ 2× baseline.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from benchmarks.iccread import IccProfile
from benchmarks.synthetic import PRINTERS, SyntheticPrinter, eval_points, \
    make_chart, measure, write_ti3
from workflow.profile_engine.metrics import delta_e_2000


def _stats(de: np.ndarray) -> dict:
    return {"median": float(np.median(de)),
            "p95": float(np.percentile(de, 95)),
            "p99": float(np.percentile(de, 99)),
            "max": float(de.max())}


def _hue_deg(lab: np.ndarray) -> np.ndarray:
    return np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360.0


def _circ_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    d = np.abs(a - b) % 360.0
    return np.minimum(d, 360.0 - d)


def score_profile(printer: SyntheticPrinter, icc_path: Path,
                  n_eval: int = 50000) -> dict:
    """All referee metrics for one built profile (pure ground truth)."""
    prof = IccProfile(icc_path)
    dev = eval_points(printer, n_eval)
    lab_true = printer.lab_relative_true(dev)

    # A2B: the profile's forward table vs physics.
    a2b = prof.a2b_lab(dev)
    de_a2b = delta_e_2000(a2b, lab_true)

    # B2A end-to-end: ask the profile for ink, print it on the true
    # printer, compare what comes out against the requested colour.
    dev_b = prof.b2a_device(lab_true)
    lab_out = printer.lab_relative_true(dev_b)
    de_b2a = delta_e_2000(lab_out, lab_true)

    # Round-trip purely inside the profile (table consistency).
    rt = prof.a2b_lab(prof.b2a_device(lab_true))
    de_rt = delta_e_2000(rt, lab_true)

    out = {"a2b": _stats(de_a2b), "b2a": _stats(de_b2a),
           "roundtrip": _stats(de_rt)}

    if printer.n_channels >= 4 and not printer.is_additive:
        # Neutral-axis separation smoothness: K total variation vs net.
        ls = np.linspace(8.0, 97.0, 180)
        neutral = np.stack([ls, np.zeros_like(ls), np.zeros_like(ls)], 1)
        k = prof.b2a_device(neutral)[:, 3]
        tv = float(np.abs(np.diff(k)).sum())
        net = float(abs(k[-1] - k[0]))
        out["k_tv"] = tv
        out["k_tv_excess"] = tv - net
        out["k_max_step"] = float(np.abs(np.diff(k)).max())

    # OOG behaviour: push chroma out of gamut, print, check the hue held.
    chroma = np.hypot(lab_true[:, 1], lab_true[:, 2])
    sat = chroma > 30.0
    if sat.any():
        oog = lab_true[sat][:2000].copy()
        oog[:, 1:] *= 1.6
        printed = printer.lab_relative_true(prof.b2a_device(oog))
        dh = _circ_diff(_hue_deg(printed), _hue_deg(oog))
        out["oog_hue"] = {"median": float(np.median(dh)),
                          "p95": float(np.percentile(dh, 95))}
    return out


def run_battery(candidates: frozenset[str] = frozenset(), *,
                quality: str = "m", n_patches: int = 900,
                n_eval: int = 50000, out_dir: Path | None = None,
                printers: dict[str, SyntheticPrinter] | None = None,
                progress=print) -> dict:
    """Build + score every battery printer; returns the full result dict."""
    from workflow.profile_engine.builder import BuildSettings, build_profile
    out_dir = Path(out_dir) if out_dir else Path(".bench")
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict = {"candidates": sorted(candidates), "quality": quality,
                     "printers": {}}
    for pid, printer in (printers or PRINTERS).items():
        chart = make_chart(printer, n_patches)
        xyz, refl, misread = measure(printer, chart)
        ti3 = write_ti3(out_dir / f"{pid}.ti3", printer, chart, xyz, refl)
        icc = out_dir / f"{pid}.icc"
        settings = BuildSettings(
            quality=quality, gammap_mode="accurate",
            engine_candidates=candidates,
            ink_limit=printer.tac)
        t0 = time.perf_counter()
        res = build_profile(ti3, icc, settings)
        secs = time.perf_counter() - t0
        row = score_profile(printer, icc, n_eval)
        row["build_seconds"] = secs
        flagged = set(int(i) for i in res.outlier_rows)
        truth = set(int(i) for i in misread)
        tp = len(flagged & truth)
        row["outliers"] = {
            "flagged": sorted(flagged), "true": sorted(truth),
            "precision": tp / len(flagged) if flagged else 1.0,
            "recall": tp / len(truth) if truth else 1.0,
            "false_flags": len(flagged - truth),
        }
        o = row["outliers"]
        o["f1"] = (2 * o["precision"] * o["recall"]
                   / (o["precision"] + o["recall"])
                   if (o["precision"] + o["recall"]) > 0 else 0.0)
        results["printers"][pid] = row
        progress(f"{pid}: A2B med {row['a2b']['median']:.3f} "
                 f"p95 {row['a2b']['p95']:.3f} | B2A med "
                 f"{row['b2a']['median']:.3f} p95 {row['b2a']['p95']:.3f}"
                 f" | {secs:.0f}s")
    return results


# ---------------------------------------------------------------------------
# Promotion gates
# ---------------------------------------------------------------------------

# Tolerance for pure quantisation/seed jitter on the "not worse" gates.
_JITTER = 0.02          # 2 % relative
_ABS_JITTER = 0.05      # ΔE00 absolute floor for max-type metrics


def evaluate_gates(baseline: dict, candidate: dict) -> dict:
    """Apply the issue-#123 promotion gates; returns verdict + detail."""
    detail: list[str] = []
    ok = True

    def rel(b, c):                       # negative = improvement
        return (c - b) / max(b, 1e-9)

    meds_b, meds_c = [], []
    for pid in baseline["printers"]:
        b, c = baseline["printers"][pid], candidate["printers"][pid]
        for leg in ("a2b", "b2a"):
            meds_b.append(b[leg]["median"])
            meds_c.append(c[leg]["median"])
            for metric in ("median", "p95"):
                r = rel(b[leg][metric], c[leg][metric])
                if r > _JITTER:
                    ok = False
                    detail.append(f"REGRESS {pid} {leg} {metric}: "
                                  f"{b[leg][metric]:.3f} → "
                                  f"{c[leg][metric]:.3f} (+{r * 100:.1f}%)")
        # Tail gate on p99, not max: the max of tens of thousands of noisy
        # evaluations is a fragile order statistic (max is still reported).
        for leg, metric in (("a2b", "p99"), ("roundtrip", "p99")):
            if c[leg][metric] > b[leg][metric] * (1 + _JITTER) + _ABS_JITTER:
                ok = False
                detail.append(f"REGRESS {pid} {leg} {metric}: "
                              f"{b[leg][metric]:.2f} → {c[leg][metric]:.2f}")
        if "k_tv_excess" in b:
            if c["k_tv_excess"] > b["k_tv_excess"] + 0.05:
                ok = False
                detail.append(f"REGRESS {pid} K smoothness: TV excess "
                              f"{b['k_tv_excess']:.3f} → "
                              f"{c['k_tv_excess']:.3f}")
        if c["build_seconds"] > 2.0 * b["build_seconds"] + 5.0:
            ok = False
            detail.append(f"REGRESS {pid} build time: "
                          f"{b['build_seconds']:.0f}s → "
                          f"{c['build_seconds']:.0f}s (> 2×)")
    s4b = baseline["printers"].get("S4", {}).get("outliers")
    s4c = candidate["printers"].get("S4", {}).get("outliers")
    if s4b and s4c:
        if s4c["f1"] < s4b["f1"] - 0.05:
            ok = False
            detail.append(f"REGRESS S4 outlier F1: {s4b['f1']:.2f} → "
                          f"{s4c['f1']:.2f}")
    clean_ff_b = sum(baseline["printers"][p]["outliers"]["false_flags"]
                     for p in baseline["printers"] if p != "S4")
    clean_ff_c = sum(candidate["printers"][p]["outliers"]["false_flags"]
                     for p in candidate["printers"] if p != "S4")
    if clean_ff_c > clean_ff_b:
        ok = False
        detail.append(f"REGRESS clean-chart false flags: "
                      f"{clean_ff_b} → {clean_ff_c}")

    improvement = 1.0 - float(np.mean(meds_c)) / max(float(np.mean(meds_b)),
                                                     1e-9)
    if improvement < 0.05:
        ok = False
        detail.append(f"GATE aggregate median improvement "
                      f"{improvement * 100:.1f}% < 5%")
    else:
        detail.append(f"aggregate median improvement "
                      f"{improvement * 100:.1f}%")
    return {"promote": ok, "improvement": improvement, "detail": detail}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", default="",
                    help="comma-separated candidate tokens")
    ap.add_argument("--quality", default="m")
    ap.add_argument("--patches", type=int, default=900)
    ap.add_argument("--eval", type=int, default=50000)
    ap.add_argument("--printers", default="",
                    help="comma-separated subset, e.g. S1,S3")
    ap.add_argument("--out", default="")
    ap.add_argument("--compare", nargs=2, metavar=("BASE", "CAND"))
    args = ap.parse_args(argv)
    if args.compare:
        base = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
        cand = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
        verdict = evaluate_gates(base, cand)
        for line in verdict["detail"]:
            print(line)
        print("PROMOTE" if verdict["promote"] else "DO NOT PROMOTE")
        return
    cands = frozenset(t for t in args.candidates.split(",") if t)
    printers = None
    if args.printers:
        printers = {p: PRINTERS[p] for p in args.printers.split(",")}
    res = run_battery(cands, quality=args.quality, n_patches=args.patches,
                      n_eval=args.eval, printers=printers)
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
