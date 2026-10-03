"""Paired statistics for "is candidate B better than A" (Agent 6).

Implements the decision rules of ``Validation/protocol.md`` (Desktop
research folder). Inputs are two run directories of ``benchmarks.research.run``
whose ``points/*.npz`` hold per-point dE arrays; points are deterministic,
so index i in A and in B is the same colour (paired).

    python -m benchmarks.research.stats A_DIR B_DIR \
        --engine-a accurate --engine-b accurate --reader argyll lcms

For each dataset x reader x primary endpoint it reports the paired
difference (B - A) of the endpoint statistic with a 95 % bootstrap CI
(2,000 resamples of points, percentile method, fixed seed), and marks
BETTER / WORSE / TIE after a Holm correction over the whole family.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

# Primary endpoints: (array key, statistic)
ENDPOINTS = [("a2b", "median"), ("a2b", "p95"), ("b2a", "median"),
             ("b2a", "p95"), ("neutral_de", "median"),
             # protocol v2 E6 (agent 7 T2c): the highlight neutral ramp,
             # L* >= 85, where the engine's worst defect lives and which the
             # device-uniform endpoints cannot see
             ("neutral_hi", "mean")]


def _stat(x: np.ndarray, name: str) -> np.ndarray:
    """x: (..., n) -> statistic over the last axis."""
    if name == "median":
        return np.median(x, axis=-1)
    if name == "p95":
        return np.percentile(x, 95, axis=-1)
    if name == "mean":
        return x.mean(axis=-1)
    raise KeyError(name)


def paired_bootstrap(a: np.ndarray, b: np.ndarray, stat: str,
                     n_boot: int = 2000, seed: int = 20260929,
                     chunk: int = 500) -> dict:
    """Difference stat(b) - stat(a) on the SAME resampled indices."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    assert a.shape == b.shape, (a.shape, b.shape)
    rng = np.random.default_rng(seed)
    n = len(a)
    diffs = []
    for s in range(0, n_boot, chunk):
        idx = rng.integers(0, n, (min(chunk, n_boot - s), n))
        diffs.append(_stat(b[idx], stat) - _stat(a[idx], stat))
    d = np.concatenate(diffs)
    obs = float(_stat(b, stat) - _stat(a, stat))
    base = float(_stat(a, stat))
    # two-sided bootstrap p-value for "no difference"
    p = float(min(1.0, 2 * min(np.mean(d <= 0), np.mean(d >= 0))))
    return {"a": base, "b": float(_stat(b, stat)), "diff": obs,
            "rel": obs / base if base else float("nan"),
            "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
            "p": max(p, 1.0 / n_boot)}


def holm(pvals: list[float], alpha: float = 0.05) -> list[bool]:
    order = np.argsort(pvals)
    m = len(pvals)
    reject = [False] * m
    for rank, i in enumerate(order):
        if pvals[i] <= alpha / (m - rank):
            reject[i] = True
        else:
            break
    return reject


def compare(dir_a: Path, dir_b: Path, engine_a: str, engine_b: str,
            readers: list[str], min_rel: float = 0.05, min_abs: float = 0.02,
            alpha: float = 0.05, seed_sd: dict | None = None) -> dict:
    """seed_sd: {"<family>|<endpoint>": sd} from the seeds suite
    (protocol section 6); the minimum effect is max(min_rel*base, min_abs,
    2*sd). Missing entries fall back to the protocol placeholders."""
    seed_sd = seed_sd or {}
    ra = json.loads((Path(dir_a) / "results.json").read_text())
    rows = []
    for d in ra["datasets"]:
        for reader in readers:
            fa = _points(dir_a, d, engine_a, reader)
            fb = _points(dir_b, d, engine_b, reader)
            if fa is None or fb is None:
                continue
            for key, st in ENDPOINTS:
                if d["kind"] == "real" and key != "a2b":
                    continue        # real B2A/neutral use a colprof proxy: biased
                src = "neutral_de" if key == "neutral_hi" else key
                if src not in fa or src not in fb or fa[src].shape != fb[src].shape:
                    continue
                xa, xb = fa[src], fb[src]
                if key == "neutral_hi":
                    m = fa["neutral_L"] >= 85.0
                    xa, xb = xa[m], xb[m]
                if key == "neutral_de":
                    lo = max(float(fa["neutral_black_L"]), float(fb["neutral_black_L"])) + 1
                    m = fa["neutral_L"] >= lo
                    xa, xb = xa[m], xb[m]
                r = paired_bootstrap(xa, xb, st)
                r.update(dataset=d["name"], variant=d["variant"], reader=reader,
                         endpoint=f"{key}.{st}",
                         role=d.get("role") or _role(d["name"]))
                rows.append(r)
    rej = holm([r["p"] for r in rows], alpha)
    for r, sig in zip(rows, rej):
        fam = "X" if r["dataset"].startswith("X") else ("R" if r["dataset"].startswith("R-") else "S")
        placeholder = 0.10 if r["endpoint"].endswith("p95") else 0.03
        sd = seed_sd.get(f"{fam}|{r['endpoint']}", placeholder)
        r["min_effect"] = max(min_rel * abs(r["a"]), min_abs, 2 * sd)
        r["seed_sd_source"] = "measured" if f"{fam}|{r['endpoint']}" in seed_sd else "placeholder"
        big = abs(r["diff"]) >= r["min_effect"]
        if sig and big:
            r["verdict"] = "BETTER" if r["diff"] < 0 else "WORSE"
        else:
            r["verdict"] = "TIE"
        r["holm_significant"] = bool(sig)
    return {"a": str(dir_a), "b": str(dir_b), "engine_a": engine_a,
            "engine_b": engine_b, "rows": rows}


def _role(name: str) -> str:
    from benchmarks.research.datasets import role_of
    return role_of(name)


def _points(run_dir: Path, d: dict, engine: str, reader: str):
    stem = f"{d['suite']}-{d['name']}-{d['variant']}-{engine}"
    f = Path(run_dir) / "points" / f"{stem}-{reader}.npz"
    return dict(np.load(f)) if f.exists() else None


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir_a")
    ap.add_argument("dir_b")
    ap.add_argument("--engine-a", default="accurate")
    ap.add_argument("--engine-b", default="accurate")
    ap.add_argument("--reader", nargs="+", default=["argyll", "lcms"])
    ap.add_argument("--out", default="")
    ap.add_argument("--seed-sd", default="",
                    help="JSON file {family|endpoint: sd} from the seeds suite")
    args = ap.parse_args(argv)
    sd = json.loads(Path(args.seed_sd).read_text()) if args.seed_sd else None
    res = compare(Path(args.dir_a), Path(args.dir_b), args.engine_a,
                  args.engine_b, args.reader, seed_sd=sd)
    for r in res["rows"]:
        print(f"{r['dataset']:>22} {r['variant']:>8} {r['reader']:>9} "
              f"{r['endpoint']:>18}: {r['a']:.3f} -> {r['b']:.3f} "
              f"({r['rel'] * 100:+.1f} %, CI [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]) "
              f"{r['verdict']}{'' if r['role'] == 'confirmatory' else ' (development set)'}")
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
