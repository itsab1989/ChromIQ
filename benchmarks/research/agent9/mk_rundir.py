"""Lay out scored profiles as a run directory that benchmarks.research.stats
reads (results.json + points/<suite>-<name>-<variant>-<engine>-<reader>.npz).
usage: mk_rundir.py OUT_RUN ENGINE PROFILE_GLOB_TEMPLATE PRINTERS VARIANTS
  template keys {pid} {variant} {k}; {k} is the seed number of a "seedK"
  variant (empty otherwise), e.g. "runs/seeds/fast/{pid}-typical-k{k}.icc"; variant "seedK" = seeds dataset k (typical),
  "typical"/"pessimistic" = chart seed 11, noise seed 23.
"""
import json, sys
from pathlib import Path
here = Path(__file__).parent
sys.path.insert(0, str(here / "w2"))
import numpy as np
from benchmarks.research import datasets as dsm, metrics
from benchmarks.research.printers import build_printers
out, eng, tmpl = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
pids, variants = sys.argv[4].split(","), sys.argv[5].split(",")
(out / "points").mkdir(parents=True, exist_ok=True)
resf = out / "results.json"
res = json.loads(resf.read_text(encoding="utf-8")) if resf.exists() else {"datasets": []}
have = {(d["name"], d["variant"]) for d in res["datasets"]}
pr = build_printers(); work = here / "gm" / "work"; work.mkdir(parents=True, exist_ok=True)
for pid in pids:
    for v in variants:
        prof = Path(tmpl.format(pid=pid, variant=v,
                                k=v[4:] if v.startswith("seed") else ""))
        if not prof.exists():
            print("missing", prof); continue
        if v.startswith("seed"):
            k = int(v[4:]); ds = dsm.synthetic(pid, work, 900, level="typical", seed=23 + k, chart_seed=11 + k, printers=pr)
            suite = "seeds"
        else:
            ds = dsm.synthetic(pid, work, 900, level=v, printers=pr); suite = "baseline"
        truth = metrics.Truth(printer=ds.printer)
        for rd in ("argyll", "lcms"):
            f = out / "points" / f"{suite}-{pid}-{v}-{eng}-{rd}.npz"
            if f.exists():
                continue
            sink = {}
            metrics.score(str(prof), ds, rd, truth, n_eval=20000, sink=sink)
            np.savez_compressed(f, **{kk: np.asarray(vv) for kk, vv in sink.items()})
        if (pid, v) not in have:
            res["datasets"].append({"name": pid, "variant": v, "kind": "synthetic",
                                    "role": dsm.role_of(pid), "suite": suite})
            have.add((pid, v))
        resf.write_text(json.dumps(res, indent=1), encoding="utf-8")
        print("scored", pid, v, eng, flush=True)
