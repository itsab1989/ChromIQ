"""Agent 23: run the H-tests on the built profiles.

    python -m benchmarks.research.blindspots.hunt_run OUT NAME [NAME ...]
        [--engines colprof,fast,accurate] [--only H1,H2]

Reads OUT/profiles/NAME-ENGINE.icc (+ -v4.icc), writes
OUT/hunt/NAME-ENGINE.json. Truth: the synthetic printer (battery v3), or
for a real set a PROXY (colprof -qh of every patch, Argyll reader; for 5+
inks the set's commercial profile through lcms), labelled in the output.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path

import numpy as np

from benchmarks.research import cmm, datasets as dsm, gmq, run
from benchmarks.research.blindspots import build, hunt
from benchmarks.research.printers import build_printers


def proxy_for(out: Path, name: str, src: str):
    d = out / "proxy"
    d.mkdir(parents=True, exist_ok=True)
    ref = dsm.reference_icc(src)
    ti3 = out / "work" / src / f"{src}-full.ti3"
    from benchmarks.research.printers import split_letters
    n = 3 if letters in ("RGB", "iRGB") else len(split_letters(letters))
    if n > 4 and ref is not None and ref.exists():
        return str(ref), "lcms", n, letters in ("RGB", "iRGB")
    icc = d / f"{name}-proxy.icc"
    if not icc.exists():
        base = d / f"{name}-proxy"
        (d / f"{name}-proxy.ti3").write_text(txt, encoding="utf-8")
        subprocess.run([f"{run.ARGYLL}/colprof", "-qh", "-v0", str(base)], check=True,
                       capture_output=True, timeout=7200)
    return str(icc), "argyll", n, letters in ("RGB", "iRGB")


def context(out: Path, name: str, icc: Path):
    spec = [s for s in build.SETS if s[0] == name][0]
    cache = out / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    if spec[1] == "synth":
        p = build_printers()[spec[2][0]]
        cloud = gmq.truth_cloud(p, cache=cache / f"cloud-{p.id}.npz")
        return hunt.Ctx(icc, p.lab_rel, p.n, p.is_additive, p.tac, truth_xyz=p.xyz,
                        truth_cloud=cloud), "printer"
    prox, reader, n, additive = proxy_for(out, name, spec[2])
    tac = run.REAL_TAC.get(spec[2])

    def tl(dev):
        return cmm.a2b(prox, np.clip(dev, 0, 1), reader)
    cf = cache / f"cloud-{name}.npz"
    if cf.exists():
        cloud = np.load(cf)["lab"]
    else:
        rng = np.random.default_rng(5)
        dev = rng.uniform(0, 1, (20000, n))
        if tac and not additive:
            dev = gmq._scale_tac(dev, tac)
        cloud = tl(dev)
        np.savez_compressed(cf, lab=cloud)
    return hunt.Ctx(icc, tl, n, additive, tac, truth_cloud=cloud), f"proxy:{Path(prox).name}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("names", nargs="+")
    ap.add_argument("--engines", default="colprof,fast,accurate")
    ap.add_argument("--only", default="")
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    only = [s for s in a.only.split(",") if s] or None
    (out / "hunt").mkdir(parents=True, exist_ok=True)
    for name in a.names:
        for e in a.engines.split(","):
            icc = out / "profiles" / f"{name}-{e}.icc"
            if not icc.exists():
                print("missing", icc.name, flush=True)
                continue
            dst = out / "hunt" / f"{name}-{e}{a.tag}.json"
            t0 = time.time()
            ctx, truth = context(out, name, icc)
            res = hunt.run_all(ctx, v4=icc.with_name(icc.stem + "-v4.icc"), only=only)
            res["truth"] = truth
            res["profile"] = str(icc)
            if dst.exists() and only:
                import json
                old = json.loads(dst.read_text())
                old.update(hunt.jsonable(res))
                res = old
            hunt.dump(res, dst)
            print(f"{name}-{e}: {time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
              "VECLIB_MAXIMUM_THREADS"):
        os.environ.setdefault(k, "1")
    raise SystemExit(main())
