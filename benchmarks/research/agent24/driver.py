"""Agent 24, F-05: build arms (base + a24-f05* variants) on 5+ ink datasets.

    python driver.py <run> <datasets> <arms> [--par 4]

datasets: comma list of PID:level:chart:n:seed (e.g. X5:typical:ecg:900:23) or
R-FOGRA55 / R-APTEC7C. arms: comma list of name=tokens ("base=", "f05=a24-f05").
The first arm of each dataset builds first (it fills the fit cache); the other
arms reuse that forward fit (bit-identical pickle) and differ only in B2A tokens.
Data generation and scoring use the scoring tree (../score, has X9/X10 and the
current ncq); builds use ../tree (research/pe-agent24).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

H = Path(__file__).resolve().parent.parent
TREE, SCORE = Path(os.environ.get("A24_TREE", H / "tree")), H / "score"
PY = "/Users/Basti/develop/ChromIQ/.venv/bin/python"
sys.path.insert(0, str(SCORE))
ENV = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
           MKL_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1",
           CHROMIQ_ENGINE_THREADS="1", PYTHONHASHSEED="0",
           TMPDIR=str(H / "tmp"),
           CHROMIQ_GAMMAP="/Users/Basti/develop/ChromIQ/native/chromiq-gammap",
           CHROMIQ_A24_FIT_CACHE=str(H / "fitcache"))
CLAY = str(TREE / "assets/profiles/ClayRGB1998.icm")


def dataset(spec: str, work: Path):
    from benchmarks.research import datasets as dsm
    from benchmarks.research import run as runmod
    from benchmarks.research.printers import build_printers
    if spec.startswith("R-"):
        d = dsm.real(spec, work / spec)
        return spec, Path(d.ti3), runmod.REAL_TAC.get(spec), ""
    pid, lvl, kind, n, seed, *ill = spec.split(":")
    pr = build_printers()
    d = dsm.synthetic_chart(pid, work, kind, int(n), level=lvl, seed=int(seed),
                            printers=pr)
    tag = f"{pid}-{lvl}-{kind}{n}-s{seed}" + (f"-{ill[0]}" if ill else "")
    return tag, Path(d.ti3), pr[pid].tac, (ill[0] if ill else "")


def build(job: dict, log: Path) -> dict:
    t0 = time.time()
    r = subprocess.run([PY, str(TREE / "benchmarks/research/build_worker.py"),
                        json.dumps(job)], capture_output=True, text=True,
                       encoding="utf-8", env=ENV, timeout=4 * 3600)
    res = None
    for ln in r.stdout.splitlines():
        if ln.startswith("RESULT "):
            res = json.loads(ln[7:])
    if res is None:
        res = {"ok": False, "error": f"rc {r.returncode}: {r.stderr[-800:]}"}
    res["wall"] = time.time() - t0
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"out": job["out"], **{k: res.get(k) for k in
                ("ok", "seconds", "wall", "sha256", "error")}}) + "\n")
    print(f"{time.strftime('%H:%M')} {Path(job['out']).name}: "
          f"{'ok' if res.get('ok') else 'FAIL ' + str(res.get('error'))[:200]}"
          f" {res.get('wall', 0):.0f}s", flush=True)
    return res


def main() -> None:
    run, dss, arms = sys.argv[1], sys.argv[2].split(","), sys.argv[3].split(",")
    par = int(sys.argv[sys.argv.index("--par") + 1]) if "--par" in sys.argv else 4
    out = H / "f05" / "runs" / run
    (out / "profiles").mkdir(parents=True, exist_ok=True)
    work = out / "work"
    work.mkdir(exist_ok=True)
    arms = [a.split("=", 1) for a in arms]
    jobs = []
    for spec in dss:
        tag, ti3, tac, ill = dataset(spec, work)
        per = []
        for name, toks in arms:
            dst = out / "profiles" / f"{tag}-{name}.icc"
            if dst.exists():
                continue
            per.append({"tree": str(TREE), "engine": "accurate", "ti3": str(ti3),
                        "out": str(dst), "quality": "m", "icc_version": "both",
                        "ink_limit": tac, "argyll_bin": "/Applications/Argyll/bin",
                        "timestamp": "2026-01-01T00:00:00", "source_gamut": CLAY,
                        "candidates": toks.replace("%", ","), "illuminant": ill})
        if per:
            jobs.append(per)
    log = out / "builds.jsonl"
    (out / "COMMAND.txt").write_text(" ".join(sys.argv) + "\n", encoding="utf-8")

    def chain(per):
        first = build(per[0], log)
        for j in per[1:]:                       # rest of this dataset in turn
            build(j, log)
        if "--score" in sys.argv:               # same slot: score this dataset's arms
            tag = Path(per[0]["out"]).stem.rsplit("-", 1)[0]
            subprocess.run([PY, str(H / "f05" / "score_f05.py"), run, "--tag", tag, "--ncq"],
                           env=ENV, stdout=open(out / f"score-{tag}.log", "w", encoding="utf-8"),
                           stderr=subprocess.STDOUT, timeout=4 * 3600)
            print(f"{time.strftime('%H:%M')} scored {tag}", flush=True)
        return first

    with ThreadPoolExecutor(par) as ex:
        list(ex.map(chain, jobs))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
