"""Agent 23 (blind-spot hunt): build the profiles to hunt in.

Every profile is built from THIS tree (research-integration-2, default token
state) by the battery's own build worker, so the builds are what the battery
builds: same ti3 generator (battery v3, targen chart at ChromIQ's defaults,
seed 23, chart seed 11), same source gamut (ClayRGB), v2 file + v4 twin.

    python -m benchmarks.research.blindspots.build OUT [--only S1,X3] [--parallel 4]

Writes OUT/profiles/<name>-<engine>.icc (+ -v4.icc), OUT/work/*.ti3 and
OUT/builds.json (one record per build, appended as they finish).
"""
from __future__ import annotations

import argparse
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from benchmarks.research import datasets as dsm, run
from benchmarks.research.printers import build_printers

# (name, kind, source, engines). kind "synth": battery v3 dataset; "real":
# the full real set (every patch; a defect hunt, not a held-out score)
SETS = [
    ("S1", "synth", ("S1", "targen", 900), ("colprof", "fast", "accurate")),
    ("X1", "synth", ("X1", "targen", 900), ("colprof", "fast", "accurate")),
    ("S2", "synth", ("S2", "targen", 900), ("colprof", "fast", "accurate")),
    ("X3", "synth", ("X3", "targen", 900), ("colprof", "fast", "accurate")),
    ("S3", "synth", ("S3", "targen", 900), ("colprof", "fast", "accurate")),
    ("XKH", "synth", ("XKH", "targen", 900), ("colprof", "fast", "accurate")),
    ("XKB", "synth", ("XKB", "targen", 900), ("colprof", "fast", "accurate")),
    ("X3m", "synth", ("X3m", "targen", 900), ("colprof", "fast", "accurate")),
    ("R-Pro300-CanonSG", "real", "R-Pro300-CanonSG", ("colprof", "fast", "accurate")),
    ("R-Knut-printer", "real", "R-Knut-printer", ("colprof", "fast", "accurate")),
    ("R-FOGRA39L", "real", "R-FOGRA39L", ("colprof", "fast", "accurate")),
    ("R-GRACoL2006", "real", "R-GRACoL2006", ("colprof", "fast", "accurate")),
    ("X8", "synth", ("X8", "targen", 900), ("fast", "accurate")),
    ("X5", "synth", ("X5", "targen", 900), ("fast", "accurate")),
    ("S5", "synth", ("S5", "targen", 900), ("fast", "accurate")),
    ("X7", "synth", ("X7", "targen", 900), ("fast", "accurate")),
    ("S7", "synth", ("S7", "targen", 900), ("fast", "accurate")),
    ("X5e", "synth", ("X5", "ecg", 900), ("fast", "accurate")),
    ("R-FOGRA55", "real", "R-FOGRA55", ("fast", "accurate")),
    ("R-APTEC7C", "real", "R-APTEC7C", ("fast", "accurate")),
]


def datasets(out: Path, only: list[str] | None) -> list[tuple[str, str, int, list[str]]]:
    printers = build_printers()
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    res = []
    for name, kind, src, engines in SETS:
        if only and name not in only:
            continue
        if kind == "synth":
            pid, chart, n = src
            ds = dsm.synthetic_chart(pid, work, chart, n, level="typical",
                                     printers=printers)
            ti3, lim = ds.ti3, ds.ink_limit
        else:
            ds = dsm.real(src, work / src)
            ti3 = ds.full_ti3 or ds.ti3
            lim = run.REAL_TAC.get(src)
        res.append((name, str(ti3), lim, list(engines)))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--only", default="")
    ap.add_argument("--parallel", type=int, default=4)
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    only = [s for s in a.only.split(",") if s] or None
    tree = run.TREE
    jobs = []
    for name, ti3, lim, engines in datasets(out, only):
        for e in engines:
            o = out / "profiles" / f"{name}-{e}.icc"
            if o.exists() and o.with_name(o.stem + "-v4.icc").exists() or \
                    (o.exists() and e == "colprof"):
                continue
            jobs.append(dict(ti3=ti3, quality="m", icc_version="both", ink_limit=lim,
                             argyll_bin=run.ARGYLL, timestamp=run.TIMESTAMP,
                             illuminant="", b2a_quality="", source_gamut=run.SOURCE_GAMUT,
                             engine=e, tree=str(tree), out=str(o), role="branch",
                             timeout=7200))
    lock = threading.Lock()
    log = out / "builds.json"

    def one(j):
        r = run.run_build(j)
        r.pop("traceback", None) if r.get("ok") else None
        with lock:
            with open(log, "a", encoding="utf-8") as f:
                f.write(json.dumps({k: r.get(k) for k in
                                    ("ok", "seconds", "sha256", "v4_sha256", "error",
                                     "fit_median_de00", "a2b_grid", "b2a_grid")}
                                   | {"out": j["out"], "engine": j["engine"]}) + "\n")
            print(("ok  " if r.get("ok") else "FAIL"), f"{r.get('seconds', 0):6.0f}s",
                  Path(j["out"]).name, flush=True)
        return r

    print(f"{len(jobs)} builds, {a.parallel} at a time", flush=True)
    with ThreadPoolExecutor(a.parallel) as ex:
        list(ex.map(one, jobs))
    return 0


if __name__ == "__main__":
    for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
              "VECLIB_MAXIMUM_THREADS", "CHROMIQ_ENGINE_THREADS"):
        os.environ[k] = "1"
    os.environ.setdefault("PYTHONHASHSEED", "0")
    raise SystemExit(main())
