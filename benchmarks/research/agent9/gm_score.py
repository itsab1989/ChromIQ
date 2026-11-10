"""Score the gamut-mapping properties (gmq M1-M11) of a set of profiles.

usage: gm_score.py OUT_DIR PRINTER[,PRINTER..] --profiles DIR --tag TAG
       [--engines accurate,colprof,argyll,fast] [--noise typical,pessimistic]
Profiles are found as DIR/<tag>-<printer>-<noise>-<engine>.icc (the baseline
naming). Writes OUT_DIR/<printer>-<noise>-<engine>-<reader>-<intent>.json
plus .npz of per-point arrays.
"""
import argparse, json, os, sys, time
from pathlib import Path
TREE = Path(__file__).parent / "tree"
sys.path.insert(0, str(TREE))
import numpy as np
from benchmarks.research import gmq
from benchmarks.research.printers import build_printers

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("printers")
ap.add_argument("--profiles", required=True); ap.add_argument("--tag", default="baseline")
ap.add_argument("--engines", default="accurate,colprof,argyll,fast")
ap.add_argument("--noise", default="typical,pessimistic")
ap.add_argument("--readers", default="argyll,lcms")
ap.add_argument("--intents", default="p,s")
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
printers = build_printers()
cache = Path(__file__).parent / "gm" / "cache"
sets = gmq.source_sets()
for pid in a.printers.split(","):
    pr = printers[pid]
    gam = gmq.TruthGamut(gmq.truth_cloud(pr, cache=cache / f"{pid}.npz"))
    for noise in a.noise.split(","):
        for eng in a.engines.split(","):
            prof = Path(a.profiles) / f"{a.tag}-{pid}-{noise}-{eng}.icc"
            if not prof.exists():
                continue
            for rd in a.readers.split(","):
                for it in a.intents.split(","):
                    stem = out / f"{pid}-{noise}-{eng}-{rd}-{it}"
                    if stem.with_suffix(".json").exists():
                        continue
                    t0 = time.process_time()
                    try:
                        res, pp = gmq.evaluate(prof, pr, rd, it, gam, sets)
                    except Exception as exc:
                        res, pp = {"error": repr(exc)}, {}
                    res.update(profile=str(prof), printer=pid, noise=noise, engine=eng)
                    stem.with_suffix(".json").write_text(json.dumps(res, indent=1), encoding="utf-8")
                    if pp:
                        np.savez_compressed(stem.with_suffix(".npz"), **pp)
                    print(stem.name, round(time.process_time() - t0, 1), "cpu s", flush=True)
