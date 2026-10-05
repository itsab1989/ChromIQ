"""Agent 22 harness: run.py with a custom suite of (printer, chart, seed) rows.

Run from a tree (cwd = tree, PYTHONPATH=.): python a22run.py <run.py args> --suite a22
Env:
  A22_ROWS   "X3m:targen:2,X3:september:0,..."  (printer:chart:k; seed 23+k,
             chart seed 11+k for september, as the seeds suites do)
  A22_LEVEL  noise level (default pessimistic)
  A22_ARM    "asis" (default) or "oracle" (the same noise draw without the
             strip misreads: strip_prob=0; every other draw is identical
             because the strip loop is the last use of the generator)
  A22_LOC    "1": add a SAMPLE_LOC column that names the noise model's strips
             (rows 0-7 strip A, then 15-row strips B, C, ... = noise.strip_rows),
             as a real chartread .ti3 does with printtarg's strip letters
  A22_SHUFFLE "1": the strips are random subsets of rows (a printtarg-random
             layout) instead of consecutive file rows (realism check)
"""
import os
import sys
from pathlib import Path

import numpy as np

import benchmarks.research.run as R
from benchmarks.research import datasets as dsm
from benchmarks.research import noise

ROWS = [tuple(r.split(":")) for r in os.environ.get("A22_ROWS", "").split(",") if r]
LEVEL = os.environ.get("A22_LEVEL", "pessimistic")
ARM = os.environ.get("A22_ARM", "asis")
LOC = os.environ.get("A22_LOC", "") == "1"
SHUFFLE = os.environ.get("A22_SHUFFLE", "") == "1"

_measure = noise.measure


def _strip_groups(n, seed):
    """Row groups the noise model treats as strips (and the first 8 rows)."""
    groups = [np.arange(0, min(8, n))] + noise.strip_rows(n, noise.STRIP["len"])
    if SHUFFLE:
        rng = np.random.default_rng(1000 + seed)
        perm = np.concatenate([np.arange(8), 8 + rng.permutation(n - 8)])
        groups = [groups[0]] + [perm[g] for g in groups[1:]]
    return groups


def measure(printer, device, level="reread", seed=23, **kw):
    if ARM == "oracle":
        kw["strip_prob"] = 0.0
    if SHUFFLE and (kw.get("strip_prob", None) != 0.0):
        # strips are random row subsets: run the model on a permuted chart
        n = len(device)
        groups = _strip_groups(n, seed)
        order = np.concatenate(groups)
        inv = np.argsort(order)
        xyz, spec, mis = _measure(printer, np.atleast_2d(device)[order], level=level,
                                  seed=seed, **kw)
        return xyz[inv], spec[inv], np.sort(order[mis])
    return _measure(printer, device, level=level, seed=seed, **kw)


dsm.measure = measure


def _letters(k):
    s = ""
    k += 1
    while k:
        k, r = divmod(k - 1, 26)
        s = chr(65 + r) + s
    return s


def add_loc(ti3: Path, seed: int) -> None:
    lines = ti3.read_text(encoding="utf-8").splitlines()
    n = int(next(l for l in lines if l.startswith("NUMBER_OF_SETS")).split()[1])
    loc = [""] * n
    for gi, g in enumerate(_strip_groups(n, seed)):
        for pi, r in enumerate(g):
            loc[int(r)] = f"{_letters(gi)}{pi + 1}"
    out, data, row = [], False, 0
    for l in lines:
        if l.startswith("NUMBER_OF_FIELDS"):
            if SHUFFLE:
                out.append('RANDOM_START "1"')   # printtarg's mark of a random layout
            l = f"NUMBER_OF_FIELDS {int(l.split()[1]) + 1}"
        elif l.startswith("SAMPLE_ID "):
            l = "SAMPLE_ID SAMPLE_LOC " + l[len("SAMPLE_ID "):]
        elif l == "BEGIN_DATA":
            data = True
        elif l == "END_DATA":
            data = False
        elif data and l.strip():
            p = l.split(" ", 1)
            l = f'{p[0]} "{loc[row]}" {p[1]}'
            row += 1
        out.append(l)
    ti3.write_text("\n".join(out) + "\n", encoding="utf-8")


def drop_random(src, dst, n_drop, seed):
    """Control arm: the same chart without n_drop random rows (never the
    first 8), i.e. the information a dropped strip takes away."""
    lines = src.read_text(encoding="utf-8").splitlines()
    n = int(next(l for l in lines if l.startswith("NUMBER_OF_SETS")).split()[1])
    gone = set((8 + np.random.default_rng(seed).permutation(n - 8)[:n_drop]).tolist())
    out, data, row = [], False, 0
    for l in lines:
        if l.startswith("NUMBER_OF_SETS"):
            l = f"NUMBER_OF_SETS {n - n_drop}"
        elif l == "BEGIN_DATA":
            data = True
        elif l == "END_DATA":
            data = False
        elif data and l.strip():
            row += 1
            if row - 1 in gone:
                continue
        out.append(l)
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")


_orig = R.make_datasets


def make_datasets(suite, work, printers, only, n_patches):
    if suite != "a22":
        return _orig(suite, work, printers, only, n_patches)
    specs = []
    for pid, kind, k in ROWS:
        k = int(k)
        if kind == "september":
            d = dsm.synthetic(pid, work, 900, level=LEVEL, seed=23 + k, chart_seed=11 + k,
                              printers=printers)
        else:
            n = int(kind[len("targen"):] or 900)
            d = dsm.synthetic_chart(pid, work, "targen", n, level=LEVEL, seed=23 + k,
                                    printers=printers)
        if LOC:
            add_loc(d.ti3, 23 + k)
        var = f"{LEVEL}-{kind}-k{k}"
        for dseed in [x for x in os.environ.get("A22_DROPSEEDS", "").split(",") if x]:
            import copy, shutil
            n_drop = int(os.environ.get("A22_DROPN", "15"))
            d2 = copy.copy(d)
            d2.ti3 = d.ti3.with_name(d.ti3.stem + f"-drop{dseed}.ti3")
            drop_random(d.ti3, d2.ti3, n_drop, int(dseed))
            specs.append({"ds": d2, "variant": var + f"-drop{dseed}", "suite": "a22"})
        if os.environ.get("A22_DROPSEEDS"):
            continue
        specs.append({"ds": d, "variant": var, "suite": "a22"})
    return specs


R.make_datasets = make_datasets
if __name__ == "__main__":
    sys.exit(R.main(sys.argv[1:]))
