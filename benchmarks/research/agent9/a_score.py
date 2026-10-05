"""Protocol-v2 scoring (metrics.score) of the item (a) profiles, per variant.
usage: a_score.py RUN_DIR PRINTERS NOISE  -> RUN_DIR/a9score/<pid>-<noise>-<reader>.json/.npz"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "tree"))
import numpy as np
from benchmarks.research import datasets as dsm, metrics
from benchmarks.research.printers import build_printers
run, pids, noise = Path(sys.argv[1]), sys.argv[2].split(","), sys.argv[3]
out = run / "a9score"; out.mkdir(exist_ok=True)
work = Path(__file__).parent / "gm" / "work"; work.mkdir(parents=True, exist_ok=True)
pr = build_printers()
for pid in pids:
    prof = run / "profiles" / f"baseline-{pid}-{noise}-accurate.icc"
    if not prof.exists():
        continue
    ds = dsm.synthetic(pid, work, 900, level=noise, printers=pr)
    truth = metrics.Truth(printer=ds.printer)
    for rd in ("argyll", "lcms"):
        f = out / f"{pid}-{noise}-{rd}.json"
        if f.exists():
            continue
        sink = {}
        res = metrics.score(str(prof), ds, rd, truth, n_eval=20000, sink=sink)
        f.write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
        np.savez_compressed(f.with_suffix(".npz"), **{k: np.asarray(v) for k, v in sink.items()})
        print(pid, noise, rd, "scored", flush=True)
