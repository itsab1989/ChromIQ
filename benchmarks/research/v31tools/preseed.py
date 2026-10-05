"""Agent 16b: pre-seed a battery run directory with byte-identical builds
from earlier runs, so ``run.py --resume`` builds only what is missing.

    python preseed.py OUT --suite v3 [--datasets A,B] [--levels typical]
        [--no-september] [--no-real] [--engines colprof,accurate]
        --source DIR:engine[,engine] ...

A source build is taken only if (1) its profile file name equals the job's,
(2) the source job's .ti3 has the same SHA-256 as the .ti3 this run
generates for that job, (3) its engine is listed for that source, and the
quality, ink limit, illuminant and source gamut of the two jobs agree.
Engine identity of each source tree with research-integration-2 was checked
separately by rebuilding a sample (idcheck/, logs/idcheck*.log).
Profiles are HARD-LINKED (no extra disk). Writes OUT/builds.json and
OUT/preseed.json (what came from where).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

TREE = Path(__file__).resolve().parent / "tree"
sys.path.insert(0, str(TREE))
from benchmarks.research import run  # noqa: E402
from benchmarks.research.printers import build_printers  # noqa: E402


def sha(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--suite", default="v3")
    ap.add_argument("--datasets", default="")
    ap.add_argument("--levels", default="")
    ap.add_argument("--no-september", action="store_true")
    ap.add_argument("--no-real", action="store_true")
    ap.add_argument("--seeds", type=int, default=run.N_SEEDS3)
    ap.add_argument("--engines", default="colprof,accurate")
    ap.add_argument("--source", action="append", default=[])
    a = ap.parse_args()
    run.NO_SEPT[0] = a.no_september
    run.NO_REAL[0] = a.no_real
    run.SEEDS_N[0] = a.seeds
    if a.levels:
        run.LEVELS_V3[0] = a.levels.split(",")
    out = Path(a.out).resolve()
    (out / "work").mkdir(parents=True, exist_ok=True)
    (out / "profiles").mkdir(parents=True, exist_ok=True)
    only = [d for d in a.datasets.split(",") if d] or None
    specs = run.make_datasets(a.suite, out / "work", build_printers(), only, 900)
    args = SimpleNamespace(engines=a.engines.split(","), quality="m", gamut=True,
                           candidates="")
    trees = {"branch": TREE, "accurate": TREE}
    jobs = []
    for i, s in enumerate(specs):
        for j in run.jobs_for(s, args, trees, out / "profiles"):
            j["spec_index"] = i
            jobs.append(j)
    src_builds = {}
    for spec in a.source:
        d, engs = spec.rsplit(":", 1)
        for b in json.loads((Path(d) / "builds.json").read_text(encoding="utf-8")):
            if b.get("ok") and b["job"].get("engine") in engs.split(",") \
                    and b["job"].get("role") in ("branch", "proxy"):
                src_builds.setdefault(Path(b["job"]["out"]).name, (d, b))
    builds, log, ti3_sha = [], [], {}
    for j in jobs:
        name = Path(j["out"]).name
        hit = src_builds.get(name)
        if hit is None:
            continue
        d, b = hit
        sj = b["job"]
        if not Path(sj["out"]).exists():
            log.append({"job": name, "skip": "source profile missing"})
            continue
        mine = ti3_sha.setdefault(j["ti3"], sha(j["ti3"]))
        theirs = ti3_sha.setdefault(sj["ti3"], sha(sj["ti3"]))
        same = all(str(j.get(k)) == str(sj.get(k)) for k in
                   ("quality", "ink_limit", "illuminant", "engine", "b2a_quality"))
        same = same and bool(j.get("source_gamut")) == bool(sj.get("source_gamut"))
        if mine != theirs or not same:
            log.append({"job": name, "skip": "ti3 or settings differ", "source": d})
            continue
        for suffix in ("", "-v4"):
            sp = Path(sj["out"]).with_name(Path(sj["out"]).stem + suffix + ".icc")
            dp = Path(j["out"]).with_name(Path(j["out"]).stem + suffix + ".icc")
            if sp.exists():
                if dp.exists():
                    dp.unlink()
                os.link(sp, dp)
        nb = {k: v for k, v in b.items() if k not in ("job", "v4_path")}
        nb["job"] = dict(j)
        nb["preseeded_from"] = d
        v4 = Path(j["out"]).with_name(Path(j["out"]).stem + "-v4.icc")
        if v4.exists():
            nb["v4_path"] = str(v4)
        if sha(j["out"]) != b.get("sha256"):
            raise SystemExit(f"{name}: linked file does not match the recorded sha256")
        builds.append(nb)
        log.append({"job": name, "from": d, "ti3_sha256": mine})
    (out / "builds.json").write_text(json.dumps(builds, indent=1), encoding="utf-8")
    (out / "preseed.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    print(f"{len(jobs)} jobs, {len(builds)} pre-seeded, "
          f"{sum(1 for x in log if 'skip' in x)} refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
