"""Paired statistics for "is candidate B better than A" (Agent 6, 6b).

Implements the decision rules of ``Validation/protocol-v2.1.md`` (Desktop
research folder). Inputs are two run directories of ``benchmarks.research.run``
whose ``points/*.npz`` hold per-point dE arrays; points are deterministic,
so index i in A and in B is the same colour (paired).

    python -m benchmarks.research.stats A_DIR B_DIR \
        --engine-a accurate --engine-b accurate --reader argyll lcms

For each dataset x reader x primary endpoint it reports the paired
difference (B - A) of the endpoint statistic with a 95 % paired bootstrap
CI (2,000 resamples, percentile method, fixed seed), a p-value, and marks
BETTER / WORSE / TIE after a Holm correction over the whole family.

Protocol v2.1 (agent 6b, 2026-10-03) changes how the p-value is formed;
the endpoints, the CI, the family and the minimum effect keep their meaning:

* p is the two-sided Student-t p of z = diff / SE, where SE is the standard
  deviation of the SAME paired bootstrap distribution (bootstrap-SE test).
  v2's percentile p, 2 * min(P(d* <= 0), P(d* >= 0)), could not fall below
  1 / n_boot = 0.0005, so Holm over more than 100 rows could reject nothing.
  It is still reported as ``p_percentile``.
* A row is significant only if Holm rejects it on p AND the 95 % percentile
  CI excludes 0 (a guard against a skewed bootstrap distribution).
* Ramp endpoints (E5 neutral_de, E6 neutral_hi) leave the point-resampling
  family. A ramp is one dense curve (lag-1 autocorrelation 0.94-0.98), not a
  sample: no resampling of its points gives a valid p (simulated: P(p <= 0.05)
  0.80 iid, 0.40 with blocks, under a null of two equal engines). In one
  build a ramp row is BETTER* / WORSE* when |diff| >= the minimum effect
  ("single build, unconfirmed"); it is confirmed only across noise seeds
  (``ramp_seed_verdicts``: exact sign-flip test of the per-seed differences,
  Holm over the ramp rows), which needs about 10 seeds.
* The placeholder seed term is the TERM of protocol-v2 section 6 (0.03 for
  medians and means, 0.10 for p95s), i.e. an SD of 0.015 / 0.05; v2's code
  read the term as the SD and doubled it.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

# Primary endpoints: (array key, statistic)
ENDPOINTS = [("a2b", "median"), ("a2b", "p95"), ("b2a", "median"),
             ("b2a", "p95"), ("neutral_de", "median"),
             # protocol v2 E6 (agent 7 T2c): the highlight neutral ramp,
             # L* >= 85, where the engine's worst defect lives and which the
             # device-uniform endpoints cannot see
             ("neutral_hi", "mean")]

# endpoints measured on an ordered, dense grid (block bootstrap)
RAMP_KEYS = ("neutral_de", "neutral_hi")

# protocol-v2 section 6 placeholder seed TERM (= 2 x SD), until measured
PLACEHOLDER_TERM = {"p95": 0.10, "median": 0.03, "mean": 0.03}

N_BOOT = 2000
SEED = 20260929
METHOD = ("v2.1: point clouds = paired bootstrap SE, two-sided t p, Holm over the "
          "comparison + percentile-CI guard; ramps = minimum effect only (single "
          "build, starred), confirmed by an exact sign-flip test over seeds")


def _stat(x: np.ndarray, name: str) -> np.ndarray:
    """x: (..., n) -> statistic over the last axis."""
    if name == "median":
        return np.median(x, axis=-1)
    if name == "p95":
        return np.percentile(x, 95, axis=-1)
    if name == "mean":
        return x.mean(axis=-1)
    raise KeyError(name)


# ---------------------------------------------------------------------------
# Student t tail without scipy (regularised incomplete beta, Lentz)
# ---------------------------------------------------------------------------

def _betacf(a: float, b: float, x: float) -> float:
    tiny, eps = 1e-300, 3e-16
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
           + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b


def t_two_sided_p(t: float, df: float) -> float:
    """P(|T| >= |t|) for Student t with df degrees of freedom."""
    if not math.isfinite(t):
        return 0.0
    if df <= 0:
        raise ValueError(df)
    return _betainc(df / 2.0, 0.5, df / (df + t * t))


# ---------------------------------------------------------------------------
# block length (Politis and White 2004; Patton, Politis, White 2009)
# ---------------------------------------------------------------------------

def _acov(x: np.ndarray, k: int) -> float:
    n = len(x)
    return float((x[:n - k] * x[k:]).sum() / n) if k else float((x * x).sum() / n)


def block_length(x: np.ndarray, cap_frac: float = 0.25) -> int:
    """Optimal circular-block-bootstrap block length for the series x.
    Returns 1 for a series without autocorrelation."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 8:
        return 1
    x = x - x.mean()
    g0 = _acov(x, 0)
    if g0 <= 0:
        return 1
    kn = max(5, int(math.ceil(math.sqrt(math.log10(n)))))
    mmax = int(math.ceil(math.sqrt(n))) + kn
    mmax = min(mmax, n - 1)
    rho = np.array([_acov(x, k) / g0 for k in range(mmax + 1)])
    crit = 2.0 * math.sqrt(math.log10(n) / n)
    mhat = None
    for m in range(1, mmax - kn + 2):
        if np.all(np.abs(rho[m:m + kn]) < crit):
            mhat = m - 1          # last significant lag before the run
            break
    if mhat is None:
        mhat = mmax
    M = min(2 * max(mhat, 1), mmax)
    if mhat == 0:
        return 1
    ks = np.arange(-M, M + 1)
    t = np.abs(ks) / M
    lam = np.where(t <= 0.5, 1.0, np.where(t <= 1.0, 2.0 * (1.0 - t), 0.0))
    gam = np.array([_acov(x, abs(int(k))) for k in ks])
    G = float((lam * np.abs(ks) * gam).sum())
    D = (4.0 / 3.0) * float((lam * gam).sum()) ** 2
    if D <= 0:
        return 1
    b = (2.0 * G * G / D) ** (1.0 / 3.0) * n ** (1.0 / 3.0)
    return int(max(1, min(round(b), int(cap_frac * n))))


def _indices(rng: np.random.Generator, rows: int, n: int, block: int) -> np.ndarray:
    if block <= 1:
        return rng.integers(0, n, (rows, n))
    k = -(-n // block)
    starts = rng.integers(0, n, (rows, k))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n
    return idx.reshape(rows, k * block)[:, :n]


def paired_bootstrap(a: np.ndarray, b: np.ndarray, stat: str,
                     n_boot: int = N_BOOT, seed: int = SEED,
                     chunk: int = 500, block: int | str = 1) -> dict:
    """Difference stat(b) - stat(a) on the SAME resampled indices.

    block: 1 = ordinary bootstrap of independent points; an integer > 1 =
    circular block bootstrap with that block length; "auto" = block length
    from ``block_length`` of the paired difference series (ordered data)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    assert a.shape == b.shape, (a.shape, b.shape)
    n = len(a)
    if block == "auto":
        block = block_length(b - a)
    block = int(block)
    rng = np.random.default_rng(seed)
    diffs = []
    for s in range(0, n_boot, chunk):
        idx = _indices(rng, min(chunk, n_boot - s), n, block)
        diffs.append(_stat(b[idx], stat) - _stat(a[idx], stat))
    d = np.concatenate(diffs)
    obs = float(_stat(b, stat) - _stat(a, stat))
    base = float(_stat(a, stat))
    # v2's two-sided percentile p (floored at 1 / n_boot; reported only)
    p_pct = float(min(1.0, 2 * min(np.mean(d <= 0), np.mean(d >= 0))))
    se = float(d.std(ddof=1)) if n_boot > 1 else 0.0
    df = max(1, (n if block <= 1 else n // block) - 1)
    if obs == 0.0:
        p = 1.0
    elif se <= 0.0:
        p = 0.0             # every resample gives the same non-zero difference
    else:
        p = t_two_sided_p(obs / se, df)
    ci = [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]
    return {"a": base, "b": float(_stat(b, stat)), "diff": obs,
            "rel": obs / base if base else float("nan"),
            "ci95": ci, "se": se, "z": (obs / se if se > 0 else
                                       (0.0 if obs == 0 else math.copysign(math.inf, obs))),
            "df": df, "block": block, "n": n, "n_boot": n_boot,
            "p": p, "p_percentile": max(p_pct, 1.0 / n_boot)}


def holm(pvals: list[float], alpha: float = 0.05) -> list[bool]:
    """Holm's step-down; stable order so ties are broken by row order."""
    order = np.argsort(np.asarray(pvals, float), kind="stable")
    m = len(pvals)
    reject = [False] * m
    for rank, i in enumerate(order):
        if pvals[i] <= alpha / (m - rank):
            reject[i] = True
        else:
            break
    return reject


def _significant(rows: list[dict], alpha: float) -> list[bool]:
    rej = holm([r["p"] for r in rows], alpha)
    return [bool(s and (r["ci95"][0] > 0 or r["ci95"][1] < 0))
            for r, s in zip(rows, rej)]


def family_of(r: dict) -> str:
    return "X" if r["dataset"].startswith("X") else (
        "R" if r["dataset"].startswith("R-") else "S")


def decide(rows: list[dict], alpha: float = 0.05, min_rel: float = 0.05,
           min_abs: float = 0.02, seed_sd: dict | None = None,
           keep_min_effect: bool = False) -> list[dict]:
    """Holm over ALL rows (the protocol family) plus the per printer x
    endpoint sensitivity column. keep_min_effect: re-verdict saved rows with
    the min_effect they were published with."""
    seed_sd = seed_sd or {}
    for r in rows:
        if keep_min_effect and "min_effect" in r:
            continue
        key = f"{family_of(r)}|{r['endpoint']}"
        st = r["endpoint"].split(".")[-1]
        sd = seed_sd.get(key, PLACEHOLDER_TERM[st] / 2.0)
        r["min_effect"] = max(min_rel * abs(r["a"]), min_abs, 2 * sd)
        r["seed_sd_source"] = "measured" if key in seed_sd else "placeholder"
    cloud = [i for i, r in enumerate(rows) if not is_ramp(r)]
    sig = [False] * len(rows)
    for i, s_ in zip(cloud, _significant([rows[i] for i in cloud], alpha)):
        sig[i] = s_
    groups: dict = {}
    for i in cloud:
        r = rows[i]
        groups.setdefault((r["dataset"], r["endpoint"]), []).append(i)
    sig_pe = [False] * len(rows)
    for idx in groups.values():
        for i, s_ in zip(idx, _significant([rows[i] for i in idx], alpha)):
            sig_pe[i] = s_
    for i, r in enumerate(rows):
        big = abs(r["diff"]) >= r["min_effect"]
        word = "BETTER" if r["diff"] < 0 else "WORSE"
        r["family_size"] = len(cloud)
        if is_ramp(r):
            # no sampling p: one curve per build (see the module docstring)
            r["holm_significant"] = False
            r["verdict"] = (word + "*") if big else "TIE"
            r["verdict_per_printer_endpoint"] = r["verdict"]
            continue
        r["holm_significant"] = sig[i]
        r["verdict"] = word if (sig[i] and big) else "TIE"
        r["verdict_per_printer_endpoint"] = word if (sig_pe[i] and big) else "TIE"
    return rows


def is_ramp(r: dict) -> bool:
    return r["endpoint"].split(".")[0] in RAMP_KEYS


def sign_flip_p(d) -> float:
    """Exact two-sided sign-flip permutation p of mean(d) = 0 over all
    2^k sign vectors (k = number of seeds). Smallest possible: 2 / 2^k."""
    d = np.asarray(d, float)
    k = len(d)
    if k == 0 or not np.any(d):
        return 1.0
    signs = ((np.arange(2 ** k)[:, None] >> np.arange(k)) & 1) * 2 - 1
    t = np.abs(signs @ d)
    return float(np.mean(t >= abs(d.sum()) - 1e-12))


def ramp_seed_verdicts(rows: list[dict], alpha: float = 0.05) -> list[dict]:
    """Ramp rows of a seeds comparison (variants seed0..seedK-1, A and B on
    the same seeds), grouped per dataset x reader x endpoint: mean paired
    difference over seeds, exact sign-flip p, Holm over the groups, and the
    minimum effect on the mean. Confirms or clears BETTER* / WORSE*."""
    groups: dict = {}
    for r in rows:
        if is_ramp(r) and str(r["variant"]).startswith("seed"):
            groups.setdefault((r["dataset"], r["reader"], r["endpoint"]), []).append(r)
    out = []
    for (ds, rd, ep), rr in groups.items():
        d = np.array([x["diff"] for x in rr])
        out.append({"dataset": ds, "reader": rd, "endpoint": ep, "seeds": len(d),
                    "mean_diff": float(d.mean()), "a": float(np.mean([x["a"] for x in rr])),
                    "min_effect": max(x["min_effect"] for x in rr),
                    "p": sign_flip_p(d), "p_min_possible": 2.0 / 2 ** len(d)})
    rej = holm([g["p"] for g in out], alpha)
    for g, s_ in zip(out, rej):
        big = abs(g["mean_diff"]) >= g["min_effect"]
        g["verdict"] = (("BETTER" if g["mean_diff"] < 0 else "WORSE")
                        if (s_ and big) else "TIE")
    return out


def no_regression(res: dict, ramp_seeds: list[dict] | None = None) -> dict:
    """The D-03 / D-09 no-regression test of B (the candidate) against A.

    Reads the per printer x endpoint column (Holm over the 4 rows of one
    dataset x endpoint: both noise levels, both readers). FAILS on:
    * any point-cloud row WORSE there (significant AND >= minimum effect);
    * any ramp row WORSE* (single build, >= minimum effect) that a seeds
      comparison (``ramp_seed_verdicts`` of the same A and B) has not
      cleared; a confirmed ramp WORSE fails outright.
    Development rows count: a regression anywhere is a regression."""
    seeds = {(g["dataset"], g["reader"], g["endpoint"]): g
             for g in (ramp_seeds if ramp_seeds is not None else res.get("ramp_seeds", []))}
    worse, open_, cleared = [], [], []
    for r in res["rows"]:
        v = r.get("verdict_per_printer_endpoint", r["verdict"])
        tag = f"{r['dataset']} {r['variant']} {r['reader']} {r['endpoint']}"
        if v == "WORSE":
            worse.append(tag)
        elif v == "WORSE*":
            g = seeds.get((r["dataset"], r["reader"], r["endpoint"]))
            if g is None:
                open_.append(tag)
            elif g["verdict"] == "WORSE":
                worse.append(tag + " (confirmed over seeds)")
            else:
                cleared.append(tag)
    return {"pass": not worse and not open_, "worse": worse,
            "open_ramp_rows": open_, "cleared_ramp_rows": cleared}


def compare(dir_a: Path, dir_b: Path, engine_a: str, engine_b: str,
            readers: list[str], min_rel: float = 0.05, min_abs: float = 0.02,
            alpha: float = 0.05, seed_sd: dict | None = None,
            n_boot: int = N_BOOT) -> dict:
    """seed_sd: {"<family>|<endpoint>": sd} from the seeds suite
    (protocol section 6); the minimum effect is max(min_rel*base, min_abs,
    2*sd). Missing entries fall back to the protocol placeholder TERM."""
    ra = json.loads((Path(dir_a) / "results.json").read_text(encoding="utf-8"))
    rows = []
    for d in ra["datasets"]:
        for reader in readers:
            fa = _points(dir_a, d, engine_a, reader)
            fb = _points(dir_b, d, engine_b, reader)
            if fa is None or fb is None:
                continue
            for key, st in ENDPOINTS:
                xa, xb = row_arrays(fa, fb, key, d["kind"])
                if xa is None:
                    continue
                r = paired_bootstrap(xa, xb, st, n_boot=n_boot,
                                     block="auto" if key in RAMP_KEYS else 1)
                r.update(dataset=d["name"], variant=d["variant"], reader=reader,
                         endpoint=f"{key}.{st}",
                         role=d.get("role") or _role(d["name"]))
                rows.append(r)
    decide(rows, alpha, min_rel, min_abs, seed_sd)
    return {"a": str(dir_a), "b": str(dir_b), "engine_a": engine_a,
            "engine_b": engine_b, "method": METHOD, "alpha": alpha,
            "rows": rows, "ramp_seeds": ramp_seed_verdicts(rows, alpha)}


def row_arrays(fa: dict, fb: dict, key: str, kind: str):
    """The paired arrays of one endpoint, or (None, None)."""
    if kind == "real" and key != "a2b":
        return None, None   # real B2A/neutral use a colprof proxy: biased
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
    ap.add_argument("--no-regression", nargs="?", const="", default=None,
                    metavar="SEEDS_A,SEEDS_B",
                    help="D-03/D-09 no-regression test of B against A; exit 1 on a "
                         "regression or an open ramp row. Optional value: the seeds "
                         "run dirs of A and B that confirm or clear ramp rows")
    ap.add_argument("--seed-sd", default="",
                    help="JSON file {family|endpoint: sd} from the seeds suite")
    args = ap.parse_args(argv)
    sd = json.loads(Path(args.seed_sd).read_text(encoding="utf-8")) if args.seed_sd else None
    res = compare(Path(args.dir_a), Path(args.dir_b), args.engine_a,
                  args.engine_b, args.reader, seed_sd=sd)
    from benchmarks.research.datasets import ROBUSTNESS_LABEL, is_robustness_only
    for r in res["rows"]:
        pe = r["verdict_per_printer_endpoint"]
        print(f"{r['dataset']:>22} {r['variant']:>8} {r['reader']:>9} "
              f"{r['endpoint']:>18}: {r['a']:.3f} -> {r['b']:.3f} "
              f"({r['rel'] * 100:+.1f} %, CI [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}], "
              f"p {'n/a' if is_ramp(r) else format(r['p'], '.1e')}) {r['verdict']}"
              f"{'' if pe == r['verdict'] else f' (per printer x endpoint: {pe})'}"
              f"{'' if r['role'] == 'confirmatory' else ' (development set)'}"
              f"{' (' + ROBUSTNESS_LABEL + ')' if is_robustness_only(r['dataset']) else ''}")
    for g in res["ramp_seeds"]:
        print(f"{g['dataset']:>22} {g['seeds']} seeds {g['reader']:>9} {g['endpoint']:>18}: "
              f"mean diff {g['mean_diff']:+.3f}, sign-flip p {g['p']:.3f} "
              f"(smallest possible {g['p_min_possible']:.3f}) {g['verdict']}")
    nr = None
    if args.no_regression is not None:
        seeds = None
        if args.no_regression:
            sa, sb = args.no_regression.split(",")
            seeds = compare(Path(sa), Path(sb), args.engine_a, args.engine_b,
                            args.reader, seed_sd=sd)["ramp_seeds"]
        nr = no_regression(res, seeds)
        res["no_regression"] = nr
        print(f"\nNO-REGRESSION (per printer x endpoint): {'PASS' if nr['pass'] else 'FAIL'}; "
              f"{len(nr['worse'])} WORSE, {len(nr['open_ramp_rows'])} open ramp rows, "
              f"{len(nr['cleared_ramp_rows'])} cleared over seeds")
        for t in nr["worse"]:
            print("  WORSE", t)
        for t in nr["open_ramp_rows"]:
            print("  OPEN (needs >= 10 seeds)", t)
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    if nr is not None and not nr["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
