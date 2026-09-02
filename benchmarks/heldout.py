"""Held-out protocol for real measurements (issue #123, W0 — secondary leg).

Formalises the ET8550 benchmark: split a real ``.ti3`` 90/10 (endpoints
protected — white/black duplicates always stay in the training set), build
a profile on the training split, score the held-out patches in ΔE2000
through the *written* profile bytes.

Real measurements are smoke tests only: instrument noise puts a floor of
roughly ±0.05 ΔE00 on the median — differences below that are noise, and
only the synthetic battery (``benchmarks.battery``) decides ties.

CLI::

    python -m benchmarks.heldout chart.ti3 [more.ti3 …] \
        --candidates ucs,joint-sep --quality m
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import numpy as np

from benchmarks.iccread import IccProfile
from workflow.profile_engine.metrics import delta_e_2000
from workflow.profile_engine.ti3_data import read_ti3


def split_ti3(ti3_path: Path, out_path: Path, holdout_frac: float = 0.1,
              seed: int = 4242) -> tuple[Path, np.ndarray]:
    """Write a training-split .ti3; returns (path, held-out row indices)."""
    meas = read_ti3(ti3_path)
    npts = len(meas.device)
    target = 1.0 if meas.is_additive else 0.0
    dist_w = np.abs(meas.device - target).sum(1)
    protected = set(np.flatnonzero(dist_w <= dist_w.min() + 1e-9))
    protected |= set(np.flatnonzero(
        np.abs(meas.device - meas.device[meas.black_index]).sum(1) <= 1e-9))
    rng = np.random.default_rng(seed)
    order = rng.permutation(npts)
    order = [i for i in order if i not in protected]
    nho = max(20, int(npts * holdout_frac))
    holdout = np.array(sorted(order[:nho]))

    text = ti3_path.read_text(errors="replace", encoding="utf-8")
    import re
    dm = re.search(r"BEGIN_DATA\s*\n(.*?)\nEND_DATA", text, re.S)
    rows = [ln for ln in dm.group(1).splitlines() if ln.strip()]
    keep = [rows[i] for i in range(npts) if i not in set(holdout)]
    new = (text[:dm.start(1)] + "\n".join(keep) + text[dm.end(1):])
    new = re.sub(r"NUMBER_OF_SETS\s+\d+", f"NUMBER_OF_SETS {len(keep)}", new)
    out_path.write_text(new, encoding="utf-8")
    return out_path, holdout


def run_heldout(ti3_path: Path, candidates: frozenset[str] = frozenset(),
                quality: str = "m") -> dict:
    from workflow.profile_engine.builder import BuildSettings, build_profile
    ti3_path = Path(ti3_path)
    meas = read_ti3(ti3_path)
    with tempfile.TemporaryDirectory() as td:
        train = Path(td) / "train.ti3"
        _, holdout = split_ti3(ti3_path, train)
        icc = Path(td) / "out.icc"
        settings = BuildSettings(quality=quality, gammap_mode="accurate",
                                 engine_candidates=candidates)
        build_profile(train, icc, settings)
        prof = IccProfile(icc)
        lab_pred = prof.a2b_lab(meas.device[holdout])
        de = delta_e_2000(lab_pred, meas.lab_relative[holdout])
    return {"file": ti3_path.name, "held_out": len(holdout),
            "median": float(np.median(de)),
            "p95": float(np.percentile(de, 95)),
            "max": float(de.max())}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ti3", nargs="+")
    ap.add_argument("--candidates", default="")
    ap.add_argument("--quality", default="m")
    args = ap.parse_args(argv)
    cands = frozenset(t for t in args.candidates.split(",") if t)
    for f in args.ti3:
        r = run_heldout(Path(f), cands, args.quality)
        print(f"{r['file']}: held-out {r['held_out']} patches — median "
              f"{r['median']:.3f}, p95 {r['p95']:.3f}, max {r['max']:.2f} "
              f"ΔE00")


if __name__ == "__main__":
    main()
