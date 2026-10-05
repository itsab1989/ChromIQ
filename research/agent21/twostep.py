"""Agent 21 D3: the two-step chart. A broad first chart (Agent 18b's v2 'ndnew'), its
profile, then a targeted SECOND chart picked where the first profile's separation goes AND
its forward model is uncertain (committee disagreement: the fit on all of chart 1 vs fits on
its two halves; Bala-Zhao refinement idea with damping). Nothing here reads the truth except
to MEASURE the patches (the battery's noise model, another sheet = another seed).

    python twostep.py pool  FIRST.icc FIRST.ti3 PRINTER OUT_DIR   (candidate pool + halves)
    python twostep.py pick  OUT_DIR K TAG [--score committee|fps]   (greedy pick, measure, merge)

Pool: (a) where the separation goes: random device points of the first profile's own gamut
(mixed sparsity: 1-4 inks and all inks, TAC-limited) -> its A2B Lab -> its B2A1 device values;
(b) the profile's B2A1 of a grey ramp; (c) 5+-ink interior points (TAC-limited), so an
uncertain interior can be chosen. The committee members are forward fits (a21build --fit-only)
on halves of chart 1; disagreement = max pairwise dE76 of their predictions.
"""
from __future__ import annotations

import json
import os
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TREE = HERE / "tree"
sys.path[:0] = [str(TREE), str(HERE.parent / "agent18" / "scripts")]
PY = "/Users/Basti/develop/ChromIQ/.venv/bin/python"


def tac_scale(dev, tac):
    s = dev.sum(1, keepdims=True)
    return np.where(s > tac / 100, dev * (tac / 100) / np.maximum(s, 1e-9), dev)


def device_cloud(n_inks, tac, n, rng):
    out = []
    for k in (1, 2, 3, 4):
        m = n // 8
        d = np.zeros((m, n_inks))
        for i in range(m):
            idx = rng.choice(n_inks, k, replace=False)
            d[i, idx] = rng.uniform(0, 1, k) ** rng.choice([1.0, 2.0])
        out.append(d)
    d = rng.uniform(0, 1, (n // 2, n_inks)) ** 1.5
    out.append(d)
    return tac_scale(np.vstack(out), tac)


def pool(first_icc, first_ti3, printer_id, out_dir):
    from benchmarks.research import cmm
    from benchmarks.research.printers import build_printers
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = build_printers()[printer_id]
    rng = np.random.default_rng(5)
    cloud = device_cloud(p.n, p.tac, 8000, rng)
    lab = cmm.a2b(first_icc, cloud, "argyll")
    sep = np.clip(cmm.b2a(first_icc, lab, "argyll"), 0, 1)
    grey = np.stack([np.linspace(6, 98, 80), np.zeros(80), np.zeros(80)], 1)
    sep_g = np.clip(cmm.b2a(first_icc, grey, "argyll"), 0, 1)
    interior = tac_scale(rng.uniform(0.15, 1, (3000, p.n)), p.tac)
    cand = np.vstack([sep, sep_g, interior])
    kind = np.array(["sep"] * len(sep) + ["grey"] * len(sep_g) + ["int"] * len(interior))
    np.save(out / "pool.npy", cand)
    np.save(out / "pool_kind.npy", kind)
    # halves of chart 1 for the committee
    chart = np.load(Path(first_ti3).with_suffix(".npy"))
    idx = rng.permutation(len(chart))
    halves = [idx[: len(idx) // 2], idx[len(idx) // 2:]]
    np.save(out / "halves.npy", np.array(halves, dtype=object), allow_pickle=True)
    print(f"pool {len(cand)} (sep {len(sep)}, grey {len(sep_g)}, interior {len(interior)})")


def subset_ti3(src, rows, dst):
    """Write a .ti3 with the given data rows of src (header kept)."""
    lines = Path(src).read_text().splitlines()
    b = lines.index("BEGIN_DATA")
    e = lines.index("END_DATA")
    data = lines[b + 1:e]
    keep = [data[i] for i in sorted(rows)]
    head = [ln if not ln.startswith("NUMBER_OF_SETS") else f"NUMBER_OF_SETS {len(keep)}"
            for ln in lines[:b + 1]]
    Path(dst).write_text("\n".join(head + keep + lines[e:]) + "\n")


def pick(out_dir, k, tag, printer_id, first_ti3, full_fit, score="committee",
         noise="typical", seed=23, radius=0.10):
    from benchmarks.research.datasets import write_ti3
    from benchmarks.research.noise import measure
    from benchmarks.research.printers import build_printers
    out = Path(out_dir)
    p = build_printers()[printer_id]
    cand = np.load(out / "pool.npy")
    kind = np.load(out / "pool_kind.npy")
    chart = np.load(Path(first_ti3).with_suffix(".npy"))
    if score == "committee":
        models = [pickle.loads(Path(f).read_bytes())[0]
                  for f in (full_fit, out / "halfA.fit.pkl", out / "halfB.fit.pkl")]
        preds = [m.predict(cand) for m in models]
        u = np.zeros(len(cand))
        for i in range(3):
            for j in range(i + 1, 3):
                u = np.maximum(u, np.linalg.norm(preds[i] - preds[j], axis=1))
    elif score == "fpsint":                 # ONE-SHOT: interior maximin only (no first profile)
        u = (kind == "int").astype(float)
    else:                                   # farthest point (Agent 18's option C)
        u = np.ones(len(cand))
    d2 = ((cand[:, None, :] - chart[None, :, :]) ** 2).sum(2).min(1)
    w = u * (1.0 - np.exp(-d2 / radius ** 2))
    chosen = []
    for _ in range(int(k)):
        i = int(np.argmax(w))
        chosen.append(i)
        dd = ((cand - cand[i]) ** 2).sum(1)
        w = w * (1.0 - np.exp(-dd / radius ** 2))        # Bala-Zhao damping
    add = cand[chosen]
    xyz1, spec1, _ = measure(p, chart, level=noise, seed=seed)
    xyz2, spec2, _ = measure(p, add, level=noise, seed=seed + 1000)
    full = np.vstack([chart, add])
    xyz = np.vstack([xyz1, xyz2])
    spec = None if spec1 is None else np.vstack([spec1, spec2])
    f = out / f"{tag}.ti3"
    np.save(f.with_suffix(".npy"), full)
    write_ti3(f, p, full, xyz, spec)
    act = add > 0.005
    info = {"tag": tag, "first": len(chart), "added": len(add),
            "kinds": {str(t): int((kind[chosen] == t).sum()) for t in set(kind)},
            "inks_hist": {int(i): int((act.sum(1) == i).sum()) for i in range(p.n + 1)},
            "u_med_chosen": float(np.median(u[chosen])), "u_med_pool": float(np.median(u))}
    (out / f"{tag}.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info))


def halves(first_ti3, out_dir):
    out = Path(out_dir)
    h = np.load(out / "halves.npy", allow_pickle=True)
    subset_ti3(first_ti3, list(h[0]), out / "halfA.ti3")
    subset_ti3(first_ti3, list(h[1]), out / "halfB.ti3")
    for nm in ("halfA", "halfB"):
        np.save(out / f"{nm}.npy", np.load(Path(first_ti3).with_suffix(".npy"))[sorted(h[0 if nm == "halfA" else 1])])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "pool":
        pool(*sys.argv[2:6])
    elif cmd == "halves":
        halves(*sys.argv[2:4])
    elif cmd == "pick":
        a = sys.argv[2:]
        pick(a[0], a[1], a[2], a[3], a[4], a[5], *(a[6:7] or []),
             **({"seed": int(a[7])} if len(a) > 7 else {}))
    else:
        raise SystemExit("see docstring")
