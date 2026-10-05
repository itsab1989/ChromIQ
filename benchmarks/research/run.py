"""One-command research benchmark (Agent 6, 2026-09-29).

    source /Users/Basti/develop/ChromIQ/.venv/bin/activate
    cd /Users/Basti/develop/ChromIQ-engine-research
    python -m benchmarks.research.run --suite baseline --out <dir>

Suites (``--suite``, comma-separated):

* ``baseline``  every dataset: synthetic S1-S7 + X1..X8 at BOTH benchmark
                noise levels (``typical`` and ``pessimistic``, protocol v2),
                and the real held-out sets; engines colprof / fast / argyll /
                accurate, every CMM readout; Fast and Bit-exact also from
                ``--upstream-ref`` (scored as ``fast@upstream`` etc.).
* ``seeds``     S1, S3, X1, X3 at five noise+chart seeds (``typical``): the
                between-seed spread the protocol's minimum effect size uses.
* ``noise``     S3, X3, X1, X5 at noise none / battery / reread (v1) /
                typical / pessimistic.
* ``b2agrid``   accurate with -bh (B2A grid 33) and colprof -bh vs default.
* ``spectral``  S3, X3, X1 built with -i F8 from the SPEC data; truth under F8
                at 1 nm (agent 2's E4).
* ``f00``       the F-00 question: accurate at HEAD vs accurate at
                37357e92~1 vs colprof vs fast on the CMYK printers at -ql and
                -qm, neutral ramp printed on the truth.
* ``repeat``    the same accurate/fast build twice: byte determinism.
* ``physics``   accurate with and without spectral_physics on S3/S5 (YNSN)
                and X3/X5 (Clapper-Yule): the size of the family circularity.

Hard rules enforced here, not by convention:

1. **Fast and Bit-exact must be byte-identical to the identity reference**
   (D-02: the branch's own Fast/Bit-exact frozen at a commit,
   ``--identity-ref``). For every typical-noise dataset the fast and argyll
   builds are repeated from a detached checkout of that ref with the same
   inputs and a fixed timestamp; the v2 file and the v4 twin are
   hash-compared. Any difference prints a banner and the process exits 2.
   Master's Fast/Bit-exact (``--upstream-ref``, default origin/master) is
   built from its own checkout and SCORED as a separate column; it is not a
   gate (it differs by the September paper-white fix, agent 7 T7).
2. **CMY+N and ICC v4 must build.** Every accurate build writes a v2 file
   and a v4 twin (``icc_version="both"``); both must exist and pass iccdump,
   littleCMS and ColorSync loading. A failure is a hard-gate failure (exit 3).

Candidates: ``--candidates tok1,tok2`` sets CHROMIQ_ENGINE_NEXT-style tokens
on the accurate builds; ``--accurate-tree <path>`` builds the accurate
engine from another tree (e.g. a candidate worktree). Output: ``results.json``
(everything), ``summary.md``, ``env.json``, ``profiles/``, ``work/``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from benchmarks.research import cmm, datasets as dsm, identity, metrics
from benchmarks.research.noise import BENCH_LEVELS
from benchmarks.research.printers import build_printers

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[1]
ARGYLL = "/Applications/Argyll/bin"
GAMMAP = "/Users/Basti/develop/ChromIQ/native/chromiq-gammap"
SOURCE_GAMUT = str(TREE / "assets/profiles/ClayRGB1998.icm")
TIMESTAMP = "2026-01-01T00:00:00"

SYNTH_BASE = ["S1", "S2", "S3", "S4", "S5", "S6", "S7",
              "X1", "X3", "X3m", "X5", "X6", "X7", "X8"]
REAL_BASE = list(dsm.REAL_SOURCES)
# Ink limits for the real CMYK sets (percent). FOGRA39 and GRACoL 2006 use
# their published TAC (330 / 320); the X-Rite sample chart has no stamp.
REAL_TAC = {"R-FOGRA39L": 330.0, "R-GRACoL2006": 320.0,
            "R-CMYK-default-i1Pro": 300.0, "R-CMYK-default-i1iSis": 300.0,
            "R-FOGRA55": 300.0, "R-APTEC7C": 300.0,
            "R-SWOP2006C3": 300.0, "R-SWOP2006C5": 300.0}


# battery v3 (Agent 16): development printers (every known printer; the
# sealed Z family is the only confirmatory set), their charts, the seeds
V3_SYNTH = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "X1", "X3", "X3m", "X5", "X6",
            "X7", "X8", "XKH", "XKB"]
V3_SPARSE = ("S1", "S3", "X1", "X3", "XKH", "XKB")   # also targen 400 (one sheet or less)
# Fast/Bit-exact identity re-builds (hard rule 1) on these typical targen-900
# sets and every real set; Integrator 3's hash battery covers the rest
V3_IDENTITY = ("X3",)
V3_IDENTITY_REAL = ("R-FOGRA39L", "R-Pro300-CanonSG")
# the 7-ink real sets (4884 / 3534 patches) were left out of the v3 freeze;
# protocol v3.1 (Agent 16b) scores them (F-20 was found on FOGRA55)
V3_REAL_SKIP: tuple = ()
# v3.1: the real multi-ink sets that join the sealed set's 5+ ink slots in
# the FINAL benchmark (development-exposed: they can veto, never claim)
V31_MULTI_REAL = ("R-FOGRA55", "R-APTEC7C")
SEEDS3_PRINTERS = ["X1", "X3", "X5"]
SEEDS3_LEVELS = {"X1": ("typical",), "X5": ("typical",)}
# seeds per printer and level: 10 where ramp rows must be confirmable (v2.1
# A4), 6 elsewhere (SD only). Cut on 2026-10-05 01:05 to 3 build processes
# (coordinator: machine 2x oversubscribed); classes without a measured SD
# take the documented fallback (stats3.seed_sd)
SEEDS3_K = {("X1", "typical"): 10, ("X3", "typical"): 10, ("X3", "pessimistic"): 6,
            ("X5", "typical"): 6}
LEVELS_V3 = [list(BENCH_LEVELS)]
N_SEEDS3 = 10
SEEDS_N = [N_SEEDS3]
SEALED_DIR = [None]
NO_REAL = [False]
V3_READERS = "argyll,lcms,colorsync,lcms-app,ghostscript,ghostscript-bpc"


NO_SEPT = [False]


def v3_charts(p) -> list[tuple[str, int]]:
    out = [("targen", 900)] + ([] if NO_SEPT[0] else [("september", 900)])
    if p.id in V3_SPARSE:
        out.append(("targen", 400))
    if p.n >= 5:
        out.append(("ecg", 900))
    return out


def sh(cmd, **kw) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120,
                          **kw).stdout.strip()


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def environment(trees: dict) -> dict:
    import numpy
    from benchmarks.research.cmm import _lcms
    heavy = [ln for ln in sh(["ps", "-Ao", "pcpu,command", "-r"]).splitlines()[1:8]]
    return {
        "commit": sh(["git", "-C", str(TREE), "rev-parse", "HEAD"]),
        "dirty": sh(["git", "-C", str(TREE), "status", "--porcelain",
                     "--untracked-files=no"]),
        "branch": sh(["git", "-C", str(TREE), "rev-parse", "--abbrev-ref", "HEAD"]),
        "identity_tree_commit": sh(["git", "-C", str(trees["identity"]), "rev-parse", "HEAD"])
        if trees.get("identity") else None,
        "upstream_tree_commit": sh(["git", "-C", str(trees["upstream"]), "rev-parse", "HEAD"])
        if trees.get("upstream") else None,
        "i1profiler_data": str(dsm.xrite_root()),
        "argyll": next((ln for ln in subprocess.run(
            [f"{ARGYLL}/colprof"], capture_output=True, text=True, encoding="utf-8",
            timeout=60).stderr.splitlines() if "Version" in ln), ""),
        "gammap_helper_sha256": sha(Path(GAMMAP)) if Path(GAMMAP).exists() else None,
        "python": sys.version, "numpy": numpy.__version__,
        "lcms": int(_lcms().cmsGetEncodedCMMversion()),
        "platform": platform.platform(),
        "cpu": sh(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "ncpu": os.cpu_count(),
        "loadavg_start": os.getloadavg(),
        "top_processes_start": heavy,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


# ---------------------------------------------------------------------------
# builds
# ---------------------------------------------------------------------------

def run_build(job: dict) -> dict:
    env = dict(os.environ, CHROMIQ_GAMMAP=GAMMAP, PYTHONHASHSEED="0")
    t_start = time.time()
    Path(job["out"]).parent.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run([sys.executable, str(HERE / "build_worker.py"),
                            json.dumps(job)], capture_output=True, text=True, encoding="utf-8",
                           timeout=job.get("timeout", 5400), env=env)
        line = [ln for ln in r.stdout.splitlines() if ln.startswith("RESULT ")]
        res = json.loads(line[-1][7:]) if line else {
            "ok": False, "error": (r.stderr or r.stdout)[-1500:]}
        if not line:
            # A worker that dies without a RESULT line (killed by a signal,
            # crashed in C code) used to be recorded as ok=False with an
            # EMPTY error and "0s" (agent9-01 6.4: five workers of three
            # runs SIGKILLed at the same second, 2026-10-04 01:06:33). Say
            # how it ended, and when.
            import signal as _sig
            rc = r.returncode
            how = (f"killed by signal {_sig.Signals(-rc).name}" if rc < 0
                   else f"exited with code {rc}")
            res["returncode"] = rc
            res["error"] = (f"worker {how} without a result after "
                            f"{time.time() - t_start:.0f} s, ended "
                            f"{time.strftime('%Y-%m-%d %H:%M:%S')}; "
                            + (res["error"] or "no output"))
            res["seconds"] = time.time() - t_start
    except subprocess.TimeoutExpired:
        res = {"ok": False, "error": f"did not finish in {job.get('timeout', 5400)} s"}
    res["job"] = {k: v for k, v in job.items() if k not in ("tree",)}
    res["job"]["tree"] = job.get("tree")
    v4 = Path(job["out"]).with_name(Path(job["out"]).stem + "-v4.icc")
    if res.get("ok") and v4.exists():
        res["v4_sha256"] = sha(v4)
        res["v4_path"] = str(v4)
    return res


def validate(icc: Path, n_channels: int) -> dict:
    """Independent loaders: iccdump (Argyll icclib), littleCMS, ColorSync."""
    out = {}
    r = subprocess.run([f"{ARGYLL}/iccdump", "-v1", str(icc)],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    txt = (r.stdout + r.stderr)
    out["iccdump_ok"] = r.returncode == 0 and "Error" not in txt
    out["iccdump_version"] = next((ln.split(":")[-1].strip() for ln in txt.splitlines()
                                   if "Version" in ln), "")
    try:
        cmm.a2b(icc, np.zeros((1, n_channels)), "lcms")
        cmm.b2a(icc, np.array([[50.0, 0, 0]]), "lcms")
        out["lcms_ok"] = True
    except Exception as exc:
        out["lcms_ok"] = False
        out["lcms_error"] = str(exc)
    # ColorSync: reported, but not a gate - it crashes on EVERY n > 4 profile
    # (engine or not), so it cannot judge CMY+N (recorded in the audit).
    out["colorsync_loads"] = cmm.colorsync_supported(str(icc))
    return out


def worktree(ref: str, where: Path) -> Path:
    if where.exists():
        subprocess.run(["git", "-C", str(TREE), "worktree", "remove", "--force",
                        str(where)], capture_output=True, timeout=120)
    subprocess.run(["git", "-C", str(TREE), "worktree", "add", "--detach",
                    str(where), ref], check=True, capture_output=True, timeout=300)
    return where


def drop_worktree(where: Path) -> None:
    subprocess.run(["git", "-C", str(TREE), "worktree", "remove", "--force",
                    str(where)], capture_output=True, timeout=120)


# ---------------------------------------------------------------------------
# suites -> dataset specs and build jobs
# ---------------------------------------------------------------------------

def make_datasets(suite: str, work: Path, printers, only: list[str] | None,
                  n_patches: int) -> list[dict]:
    """[{dataset, tags, engines}] for one suite."""
    specs = []
    def keep(name):
        return not only or name in only
    if suite == "baseline":
        for lvl in BENCH_LEVELS:
            for pid in SYNTH_BASE:
                if keep(pid):
                    specs.append({"ds": dsm.synthetic(pid, work, n_patches, level=lvl,
                                                      printers=printers),
                                  "variant": lvl})
        for name in REAL_BASE:
            if keep(name):
                d = dsm.real(name, work / name)
                if name in REAL_TAC:
                    d.ink_limit = REAL_TAC[name]
                specs.append({"ds": d, "variant": "base"})
    elif suite == "seeds":
        # Agent 15: BENCH_SEEDS (default 5) seeds; protocol v2.1 A4 needs >= 10
        nseeds = int(os.environ.get("BENCH_SEEDS", "5"))
        pids = os.environ.get("BENCH_SEED_PIDS", "S1,S3,X1,X3").split(",")
        for pid in pids:
            for k in range(nseeds):
                if keep(pid):
                    specs.append({"ds": dsm.synthetic(pid, work, n_patches, seed=23 + k,
                                                      chart_seed=11 + k, printers=printers),
                                  "variant": f"seed{k}"})
    elif suite == "noise":
        for pid in ["S3", "X3", "X1", "X5"]:
            for lvl in ["none", "battery", "reread", "typical", "pessimistic"]:
                if keep(pid):
                    specs.append({"ds": dsm.synthetic(pid, work, n_patches, level=lvl,
                                                      printers=printers),
                                  "variant": f"noise-{lvl}"})
    elif suite == "b2agrid":
        for pid in ["S1", "S3", "X1", "X3"]:
            if keep(pid):
                specs.append({"ds": dsm.synthetic(pid, work, n_patches, printers=printers),
                              "variant": "bh", "b2a_quality": "h"})
    elif suite == "spectral":
        for pid in ["S3", "X3", "X1"]:
            if keep(pid):
                specs.append({"ds": dsm.synthetic(pid, work, n_patches, illuminant="F8",
                                                  printers=printers),
                              "variant": "F8"})
    elif suite == "f00":
        for pid in ["S3", "S4", "X3", "X3m"]:
            for q in ("l", "m"):
                if keep(pid):
                    specs.append({"ds": dsm.synthetic(pid, work, n_patches, printers=printers),
                                  "variant": f"f00-q{q}", "quality": q})
    elif suite == "physics":
        # audit R3: size of the YNSN circularity. The engine's opt-in
        # spectral_physics is a YNSN model; compare its gain on the YNSN
        # printers (S) with its gain on the Clapper-Yule printers (X).
        for pid in ["S3", "S5", "X3", "X5"]:
            if keep(pid):
                specs.append({"ds": dsm.synthetic(pid, work, n_patches, printers=printers),
                              "variant": "physics"})
    elif suite == "ecgchart":
        # agent 14: the same printers and noise, charts composed like a
        # professional ECG chart (datasets.make_chart_ecg), 900 and 600 patches
        for pid, npat in (("X5", 900), ("X8", 900), ("X7", 900), ("X7", 600)):
                if keep(pid):
                    specs.append({"ds": dsm.synthetic(pid, work, npat, printers=printers,
                                                      chart="ecg"),
                                  "variant": f"ecg{npat}"})
    elif suite == "ncsep":
        # agent 14: separation-policy candidates on the multi-ink printers
        # (typical noise, September chart and the ECG chart)
        for pid in ["X5", "X6"]:
            if keep(pid):
                specs.append({"ds": dsm.synthetic(pid, work, n_patches, printers=printers),
                              "variant": "typical"})
                specs.append({"ds": dsm.synthetic(pid, work, n_patches, printers=printers,
                                                  chart="ecg"),
                              "variant": "ecg900"})
    elif suite == "v3":
        # battery v3 frozen baseline (protocol v3): every development printer
        # on the charts ChromIQ produces (targen at its defaults), the
        # robustness chart (september) and, for 5+ inks, the ECG chart; both
        # noise levels; plus every real held-out set
        for lvl in LEVELS_V3[0]:
            for pid in V3_SYNTH:
                if not keep(pid):
                    continue
                for kind, n in v3_charts(printers[pid]):
                    specs.append({"ds": dsm.synthetic_chart(pid, work, kind, n, level=lvl,
                                                            printers=printers),
                                  "variant": f"{lvl}-{kind}{n}", "role": "development"})
        for name in ([] if NO_REAL[0] else [r for r in REAL_BASE if r not in V3_REAL_SKIP]):
            if keep(name):
                d = dsm.real(name, work / name)
                if name in REAL_TAC:
                    d.ink_limit = REAL_TAC[name]
                specs.append({"ds": d, "variant": "base", "role": "development"})
    elif suite == "seeds3":
        # protocol v3 B1: k noise seeds on the ChromIQ-default chart, both
        # levels, every engine: the measured between-seed SD per engine
        for pid in SEEDS3_PRINTERS:
            if not keep(pid):
                continue
            for lvl in SEEDS3_LEVELS.get(pid, BENCH_LEVELS):
                for k in range(min(SEEDS_N[0], SEEDS3_K.get((pid, lvl), SEEDS_N[0]))):
                    specs.append({"ds": dsm.synthetic_chart(pid, work, "targen", 900, level=lvl,
                                                            seed=23 + k, printers=printers),
                                  "variant": f"seed{k}-{lvl}-targen900", "role": "development"})
    elif suite == "sealed":
        from benchmarks.research import sealed as sealed_mod
        for lvl, d in sealed_mod.load_datasets(SEALED_DIR[0], work, only=only):
            specs.append({"ds": d, "variant": f"{lvl}-{d.info['chart']}{d.info['patches']}",
                          "role": "sealed"})
        # protocol v3.1: the real 7-ink sets are scored beside the sealed
        # 5+ ink slots in the same final run (role development: veto only)
        for name in ([] if NO_REAL[0] else V31_MULTI_REAL):
            if keep(name):
                d = dsm.real(name, work / name)
                d.ink_limit = REAL_TAC.get(name, d.ink_limit)
                specs.append({"ds": d, "variant": "base", "role": "development"})
    elif suite == "repeat":
        for pid in ["S3", "X5"]:
            if keep(pid):
                specs.append({"ds": dsm.synthetic(pid, work, n_patches, printers=printers),
                              "variant": "repeat"})
    else:
        raise KeyError(suite)
    for s in specs:
        s["suite"] = suite
    return specs


def jobs_for(spec: dict, args, trees: dict, profdir: Path) -> list[dict]:
    ds = spec["ds"]
    suite = spec["suite"]
    q = spec.get("quality", args.quality)
    engines = list(args.engines)
    if suite in ("seeds", "noise", "spectral"):
        engines = [e for e in engines if e in ("colprof", "fast", "accurate")]
    if suite == "b2agrid":
        engines = [e for e in engines if e in ("colprof", "accurate")]
    if suite == "v3" and "-ecg" in spec["variant"]:
        # 5+ ink ECG charts: Bit-exact left out of this freeze (3-process
        # cap; 20-30 min per multi-ink build); Fast is the comparator there
        engines = [e for e in engines if e != "argyll"]
    if suite == "repeat":
        engines = ["accurate", "fast"]
    if suite == "physics":
        engines = ["accurate"]
    base = {"ti3": str(ds.ti3), "quality": q, "icc_version": "both",
            "ink_limit": ds.ink_limit, "argyll_bin": ARGYLL,
            "timestamp": TIMESTAMP, "illuminant": ds.illuminant,
            "b2a_quality": spec.get("b2a_quality", ""),
            "source_gamut": SOURCE_GAMUT if args.gamut else None}
    tag = f"{suite}-{ds.name}-{spec['variant']}"
    jobs = []
    for e in engines:
        tree = trees["accurate"] if e == "accurate" else trees["branch"]
        j = dict(base, engine=e, tree=str(tree),
                 out=str(profdir / f"{tag}-{e}.icc"), role="branch")
        if e == "accurate" and args.candidates:
            j["candidates"] = args.candidates
        jobs.append(j)
        if suite == "repeat":
            jobs.append(dict(j, out=str(profdir / f"{tag}-{e}-again.icc"), role="repeat"))
    if (suite == "baseline" and spec["variant"] in ("typical", "base")) or \
            (suite == "v3" and ((spec["variant"] == "base" and ds.name in V3_IDENTITY_REAL) or (
                spec["variant"] == "typical-targen900" and ds.name in V3_IDENTITY))):
        for role in ("identity", "upstream"):
            if not trees.get(role):
                continue
            for e in ("fast", "argyll"):
                if e in args.engines:
                    jobs.append(dict(base, engine=e, tree=str(trees[role]),
                                     out=str(profdir / role / f"{tag}-{e}.icc"),
                                     role=role))
    if suite == "physics":
        jobs.append(dict(base, engine="accurate", tree=str(trees["accurate"]),
                         spectral_physics=True,
                         out=str(profdir / f"{tag}-accurate-sp.icc"), role="sp"))
    if suite == "f00" and trees.get("f00"):
        jobs.append(dict(base, engine="accurate", tree=str(trees["f00"]),
                         out=str(profdir / f"{tag}-accurate-37357e92parent.icc"),
                         role="f00-parent"))
    if ds.kind == "real" and ds.n_channels <= 4:
        jobs.append(dict(base, engine="colprof", quality="h", source_gamut=None,
                         ti3=str(ds.full_ti3), tree=str(trees["branch"]),
                         out=str(profdir / f"{tag}-PROXY-colprof-qh-full.icc"),
                         role="proxy"))
    return jobs


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", default="baseline")
    ap.add_argument("--out", required=True)
    ap.add_argument("--datasets", default="", help="subset of dataset names")
    ap.add_argument("--engines", default="colprof,fast,argyll,accurate")
    ap.add_argument("--readers", default="",
                    help="default: argyll,lcms,colorsync,multilinear; v3 suites: " + V3_READERS)
    ap.add_argument("--quality", default="m")
    ap.add_argument("--patches", type=int, default=900)
    ap.add_argument("--eval", type=int, default=20000)
    ap.add_argument("--parallel", type=int, default=2)
    ap.add_argument("--no-gamut", dest="gamut", action="store_false",
                    help="skip the perceptual/saturation tables (faster; the "
                         "byte-identity check then covers only the colorimetric path)")
    ap.add_argument("--identity-ref", "--master-ref", dest="identity_ref",
                    default=identity.IDENTITY_REF,
                    help="frozen commit Fast/Bit-exact must equal byte for byte "
                         "(D-02; default identity.IDENTITY_REF); empty = no check")
    ap.add_argument("--upstream-ref", default=identity.UPSTREAM_REF,
                    help="ref whose Fast/Bit-exact are scored as a separate "
                         "column (empty to skip)")
    ap.add_argument("--i1profiler-data", default="",
                    help=f"i1Profiler data root (default {dsm.XRITE_DEFAULT}, "
                         f"or ${dsm.XRITE_ENV})")
    ap.add_argument("--f00-ref", default="37357e92~1")
    ap.add_argument("--candidates", default="")
    ap.add_argument("--accurate-tree", default="")
    ap.add_argument("--trees-dir", default="",
                    help="where the reference worktrees go (default <out>/trees)")
    ap.add_argument("--rebuild-failed", action="store_true",
                    help="load <out>/builds.json, rebuild every failed build "
                         "(fresh reference worktrees; refusals such as colprof "
                         "on 5+ inks fail again), then score everything")
    ap.add_argument("--score-only", action="store_true",
                    help="re-score the builds recorded in <out>/builds.json")
    ap.add_argument("--resume", action="store_true",
                    help="v3: keep every ok build of <out>/builds.json whose profile "
                         "exists, build the rest, then score (reuses <out>/scores/)")
    ap.add_argument("--engine-ref", default="",
                    help="v3: build every engine from a detached checkout of this ref "
                         "(e.g. research-integration-1), the benchmark code from this tree")
    ap.add_argument("--sealed-dir", default="",
                    help="v3 --suite sealed: the UNSEALED sealed directory")
    ap.add_argument("--seeds", type=int, default=N_SEEDS3,
                    help="seeds3: number of noise seeds (protocol v3: 10)")
    ap.add_argument("--levels", default="", help="v3: noise levels (default both)")
    ap.add_argument("--no-real", action="store_true", help="v3: synthetic sets only")
    ap.add_argument("--no-september", action="store_true",
                    help="v3: leave out the robustness chart")
    ap.add_argument("--no-oogq", action="store_true",
                    help="v3 suites: skip the v3.1 property referee (oogq)")
    ap.add_argument("--score-parallel", type=int, default=0,
                    help="scoring processes (default = --parallel)")
    args = ap.parse_args(argv)
    if args.sealed_dir:
        SEALED_DIR[0] = Path(args.sealed_dir).expanduser()
    SEEDS_N[0] = args.seeds
    NO_REAL[0] = args.no_real
    NO_SEPT[0] = args.no_september
    if args.levels:
        LEVELS_V3[0] = args.levels.split(",")
    if args.i1profiler_data:
        os.environ[dsm.XRITE_ENV] = str(Path(args.i1profiler_data).expanduser())
    args.engines = [e for e in args.engines.split(",") if e]
    v3 = any(x in args.suite for x in ("v3", "seeds3", "sealed"))
    readers = [r for r in (args.readers or (V3_READERS if v3 else
                                            "argyll,lcms,colorsync,multilinear")).split(",") if r]
    out = Path(args.out).resolve()
    work, profdir = out / "work", out / "profiles"
    for d in (work, profdir):
        d.mkdir(parents=True, exist_ok=True)
    suites = [s for s in args.suite.split(",") if s]
    # The reference worktrees live INSIDE the run directory (v2): in v1 they
    # sat in $TMPDIR/chromiq-agent6-trees, where another process's sweep of
    # chromiq-* temp folders deleted them in the middle of a baseline run
    # (2026-10-03: every identity/upstream build after X1 failed).
    scratch = Path(args.trees_dir).resolve() if args.trees_dir else out / "trees"
    scratch.mkdir(parents=True, exist_ok=True)
    trees = {"branch": TREE,
             "accurate": Path(args.accurate_tree).resolve() if args.accurate_tree else TREE}
    made = []
    try:
        if args.engine_ref:
            eng = scratch / "engine"
            if not (eng / ".git").exists():
                worktree(args.engine_ref, eng)
                made.append(eng)
            trees["branch"] = eng
            if not args.accurate_tree:
                trees["accurate"] = eng
        if "baseline" in suites or "v3" in suites:
            for role, ref in (("identity", args.identity_ref),
                              ("upstream", args.upstream_ref)):
                if ref:
                    trees[role] = worktree(ref, scratch / role)
                    made.append(trees[role])
        if "f00" in suites:
            trees["f00"] = worktree(args.f00_ref, scratch / "f00parent")
            made.append(trees["f00"])
        env = environment(trees)
        env["args"] = vars(args)
        (out / "env.json").write_text(json.dumps(env, indent=1, default=str), encoding="utf-8")
        printers = build_printers()
        only = [d for d in args.datasets.split(",") if d] or None
        specs = []
        for s in suites:
            specs += make_datasets(s, work, printers, only, args.patches)
        jobs = []
        for idx, s in enumerate(specs):
            for j in jobs_for(s, args, trees, profdir):
                j["spec_index"] = idx
                jobs.append(j)
        print(f"{len(specs)} datasets, {len(jobs)} builds, {args.parallel} at a time",
              flush=True)
        builds_path = out / "builds.json"
        if args.rebuild_failed and builds_path.exists():
            builds = json.loads(builds_path.read_text(encoding="utf-8"))
            by_out = {j["out"]: j for j in jobs}
            redo = [i for i, b in enumerate(builds) if not b.get("ok")]
            print(f"rebuilding {len(redo)} failed builds", flush=True)
            t0 = time.time()
            def again(i):
                j = dict(by_out.get(builds[i]["job"]["out"], builds[i]["job"]))
                return i, run_build(j)
            with ThreadPoolExecutor(max_workers=args.parallel) as ex:
                for i, res in ex.map(again, redo):
                    res["rebuilt"] = True
                    builds[i] = res
                    print(f"[{time.time() - t0:6.0f}s] rebuilt {Path(res['job']['out']).name}: "
                          f"{'ok' if res.get('ok') else 'FAILED'} "
                          f"{'' if res.get('ok') else res.get('error', '')[:200]}", flush=True)
                    builds_path.write_text(json.dumps(builds, indent=1), encoding="utf-8")
        elif args.score_only and builds_path.exists():
            builds = json.loads(builds_path.read_text(encoding="utf-8"))
        elif args.resume and builds_path.exists():
            old = {b["job"]["out"]: b for b in json.loads(builds_path.read_text(encoding="utf-8"))
                   if b.get("ok") and Path(b["job"]["out"]).exists()}
            todo = [j for j in jobs if j["out"] not in old]
            print(f"resume: {len(jobs) - len(todo)} builds kept, {len(todo)} to build", flush=True)
            builds = []
            for j in jobs:
                if j["out"] in old:
                    b = old[j["out"]]
                    b["job"] = dict(b["job"], spec_index=j["spec_index"])
                    builds.append(b)
            t0 = time.time()
            with ThreadPoolExecutor(max_workers=args.parallel) as ex:
                for res in ex.map(run_build, todo):
                    builds.append(res)
                    j = res["job"]
                    print(f"[{time.time() - t0:6.0f}s] {Path(j['out']).name}: "
                          f"{'ok' if res.get('ok') else 'FAILED'} {res.get('seconds', 0):.0f}s "
                          f"{'' if res.get('ok') else res.get('error', '')[:200]}", flush=True)
                    builds_path.write_text(json.dumps(builds, indent=1), encoding="utf-8")
        else:
            t0 = time.time()
            builds = []
            with ThreadPoolExecutor(max_workers=args.parallel) as ex:
                for res in ex.map(run_build, jobs):
                    builds.append(res)
                    j = res["job"]
                    print(f"[{time.time() - t0:6.0f}s] {Path(j['out']).name}: "
                          f"{'ok' if res.get('ok') else 'FAILED'} "
                          f"{res.get('seconds', 0):.0f}s "
                          f"{'' if res.get('ok') else res.get('error', '')[:200]}",
                          flush=True)
                    builds_path.write_text(json.dumps(builds, indent=1), encoding="utf-8")
        # --- the two hard rules ------------------------------------------------
        ident = check_identity(builds)
        upstream = compare_upstream(builds, specs)
        gates = check_gates(builds, specs)
        # --- scoring ------------------------------------------------------------
        results = {"env": env, "identity": ident, "upstream": upstream, "gates": gates,
                   "datasets": [], "builds": builds}
        tasks, entries = [], []
        for i, s in enumerate(specs):
            ds = s["ds"]
            entry = {"name": ds.name, "suite": s["suite"], "variant": s["variant"],
                     "role": s.get("role") or dsm.role_of(ds.name),
                     "kind": ds.kind, "n_channels": ds.n_channels,
                     "color_rep": ds.color_rep, "ink_limit": ds.ink_limit,
                     "info": ds.info, "profiles": {}}
            entries.append(entry)
            mine = [b for b in builds if b["job"].get("spec_index") == i]
            proxy = next((b for b in mine if b["job"]["role"] == "proxy" and b.get("ok")), None)
            for b in mine:
                j = b["job"]
                if j["role"] in ("proxy", "identity", "repeat"):
                    continue
                key = j["engine"] if j["role"] == "branch" else f"{j['engine']}@{j['role']}"
                stem = Path(j["out"]).stem if j["role"] == "branch" else \
                    f"{Path(j['out']).stem}@{j['role']}"
                tasks.append({"i": i, "key": key, "stem": stem, "build": b, "ds": ds,
                              "proxy": proxy["job"]["out"] if proxy else None,
                              "readers": readers, "n_eval": args.eval,
                              "light": s["suite"] in ("seeds", "noise", "seeds3"),
                              "oogq": s["suite"] in ("v3", "seeds3", "sealed") and not args.no_oogq,
                              "out": str(out), "reuse": args.resume or args.score_only})
        sp = args.score_parallel or args.parallel
        print(f"scoring {len(tasks)} profiles, {sp} processes", flush=True)
        import multiprocessing as mp
        from concurrent.futures import ProcessPoolExecutor
        done = 0
        with ProcessPoolExecutor(max_workers=sp, mp_context=mp.get_context("spawn")) as ex:
            for i, key, rec in ex.map(score_task, tasks):
                entries[i]["profiles"][key] = rec
                done += 1
                print(f"scored {entries[i]['name']} {entries[i]['variant']} {key} "
                      f"({done}/{len(tasks)})", flush=True)
                if done % 20 == 0 or done == len(tasks):
                    results["datasets"] = entries
                    (out / "results.json").write_text(json.dumps(results, indent=1, default=_js),
                                                      encoding="utf-8")
        results["datasets"] = entries
        env["loadavg_end"] = os.getloadavg()
        (out / "results.json").write_text(json.dumps(results, indent=1, default=_js), encoding="utf-8")
        from benchmarks.research.summary import write_summary
        write_summary(results, out / "summary.md")
        code = 0
        if ident["failures"]:
            print("\n" + "!" * 72 + "\nFAST / BIT-EXACT ARE NOT BYTE-IDENTICAL TO THE IDENTITY REF\n"
                  + "\n".join(ident["failures"]) + "\n" + "!" * 72)
            code = 2
        if gates["failures"]:
            print("\n" + "!" * 72 + "\nHARD GATE FAILED (CMY+N / ICC v4)\n"
                  + "\n".join(gates["failures"]) + "\n" + "!" * 72)
            code = code or 3
        print(f"wrote {out / 'results.json'} and {out / 'summary.md'} (exit {code})")
        return code
    finally:
        for t in made:
            drop_worktree(t)


def _truth_for(ds, proxy_out):
    if ds.kind == "real":
        # 5+ inks: colprof cannot build the proxy; the set's own published
        # reference profile (FOGRA55: ColorLogic CoPrA) stands in, labelled
        # in results.json (agent 14)
        pxy = proxy_out or ds.info.get("reference_icc")
        if not pxy:
            return None
        vers = Path(pxy).read_bytes()[8]
        return metrics.Truth(proxy_icc=pxy, proxy_reader="lcms" if vers >= 4 and not proxy_out
                             else "argyll")
    return metrics.Truth(printer=ds.printer, illuminant=ds.illuminant or "D50")


def score_task(t: dict):
    """Score one profile under every reader (runs in a spawned process).
    Per-profile scores are cached in <out>/scores/<stem>.json so a killed
    run resumes without re-scoring (``--resume`` / ``--score-only``)."""
    import os as _os
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        _os.environ.setdefault(k, "1")
    b, ds, out = t["build"], t["ds"], Path(t["out"])
    j = b["job"]
    cache = out / "scores" / f"{t['stem']}.json"
    if t.get("reuse") and cache.exists():
        rec = json.loads(cache.read_text(encoding="utf-8"))
        stale = ds.kind == "synthetic" and ds.n_channels >= 5 and not t["light"] \
            and "ncq" not in rec
        stale = stale or _pale_dl_missing(rec)
        if rec.get("sha256") == b.get("sha256") and not stale:
            if t.get("oogq") and b.get("ok") and "oogq" not in rec:
                # v3.1: only the property referee is new; the reader scores stand
                truth = _truth_for(ds, t["proxy"])
                if truth is not None:
                    _score_oogq(rec, j, ds, truth, out)
                    cache.write_text(json.dumps(rec, default=_js), encoding="utf-8")
            return t["i"], t["key"], rec
    rec = {k: b.get(k) for k in ("ok", "seconds", "sha256", "v4_sha256",
                                   "error", "outlier_rows", "fit_median_de00")}
    truth = _truth_for(ds, t["proxy"])
    if b.get("ok") and truth is not None:
        rec["raw_neutral_column"] = metrics.raw_neutral_column(j["out"])
        rec["scores"] = {}
        for r in t["readers"]:
            if not cmm.supports(r, "b2a", j["out"]):
                rec["scores"][r] = {"unsupported": f"{r} cannot read this profile "
                                                   f"({ds.color_rep}, {ds.n_channels} channels)"}
                continue
            sink: dict = {}
            t0 = time.time()
            try:
                rec["scores"][r] = metrics.score(j["out"], ds, r, truth, n_eval=t["n_eval"],
                                                 light=t["light"], sink=sink)
                # protocol v3 N (Agent 14's v2.2): N-colour point endpoints
                # E7-E9 and the F-12 gross-extrapolation fact, 5+ inks
                if (ds.kind == "synthetic" and ds.n_channels >= 5
                        and r in ("argyll", "lcms") and not t["light"]):
                    from benchmarks.research import ncpoints
                    rec["scores"][r]["nc"] = ncpoints.evaluate(j["out"], ds.printer, r, sink)
                rec["scores"][r]["seconds"] = time.time() - t0
            except Exception as exc:
                rec["scores"][r] = {"error": f"{type(exc).__name__}: {exc}"}
            if sink:
                (out / "points").mkdir(exist_ok=True)
                np.savez_compressed(out / "points" / f"{t['stem']}-{r}.npz",
                                    **{k: np.asarray(v) for k, v in sink.items()})
        if ds.kind == "synthetic" and ds.n_channels >= 5 and not t["light"]:
            try:
                from benchmarks.research import ncpoints
                rec["ncq"] = ncpoints.referee(j["out"], ds.printer, "argyll")
            except Exception as exc:
                rec["ncq"] = {"error": f"{type(exc).__name__}: {exc}"}
        if t.get("oogq"):
            _score_oogq(rec, j, ds, truth, out)
        if ds.kind == "synthetic" and j["engine"] != "colprof":
            flagged = set(b.get("outlier_rows") or [])
            true = set(int(x) for x in ds.misread_rows)
            tp = len(flagged & true)
            rec["outliers"] = {"flagged": len(flagged), "true": len(true),
                               "true_positive": tp, "false_positive": len(flagged - true),
                               "recall": tp / len(true) if true else None,
                               "precision": tp / len(flagged) if flagged else None}
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps(rec, default=_js), encoding="utf-8")
    return t["i"], t["key"], rec


def _pale_dl_missing(rec: dict) -> bool:
    """A cached score from before v3.1 has the pale sample but not its
    lightness error (F-14): re-score it."""
    for s in (rec.get("scores") or {}).values():
        ps = (s.get("b2a") or {}).get("pale_sample") if isinstance(s, dict) else None
        if ps is not None and "dl_abs" not in ps:
            return True
    return False


def oogq_printer(ds, truth):
    """The printer object the v3.1 referee prints on: the synthetic or
    sealed truth printer itself (generator interface), or a real set's
    labelled proxy wrapped as a printer."""
    from benchmarks.research import oogq
    if ds.kind != "real":
        return ds.printer
    from benchmarks.research.printers import split_letters
    rep = ds.color_rep.split("_")[0]
    additive = rep in ("RGB", "iRGB")
    letters = list("RGB") if additive else split_letters(rep)
    return oogq.TruthAdapter(truth, ds.n_channels, additive, ds.ink_limit, letters, ds.name)


def _score_oogq(rec: dict, job: dict, ds, truth, out: Path) -> None:
    """Protocol v3.1 property rows (F-13..F-20, gmq p/s, ncq on real 5+ ink
    sets), stored as rec["oogq"]; never raises."""
    from benchmarks.research import gmq, oogq
    try:
        pr = oogq_printer(ds, truth)
        key = pr.id if ds.kind != "real" else ds.name
        cloud = gmq.truth_cloud(pr, cache=out / "cache" / f"cloud-{key}.npz")
        multi_real = ds.kind == "real" and ds.n_channels >= 5
        res = oogq.evaluate(job["out"], pr, cloud=cloud, with_ncq=multi_real)
        res["truth"] = "printer" if ds.kind != "real" else f"proxy:{Path(str(truth.proxy)).name}"
        if multi_real and "ncq" in res:
            rec["ncq"] = res.pop("ncq")
        rec["oogq"] = res
    except Exception as exc:
        rec["oogq"] = {"error": f"{type(exc).__name__}: {exc}"}


def _js(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def check_identity(builds: list[dict]) -> dict:
    out = {"compared": [], "failures": []}
    for m in [b for b in builds if b["job"].get("role") == "identity"]:
        br_out = str(Path(m["job"]["out"]).parent.parent / Path(m["job"]["out"]).name)
        br = next((b for b in builds if b["job"]["out"] == br_out), None)
        name = Path(br_out).name
        if br is None or not br.get("ok") or not m.get("ok"):
            out["failures"].append(f"{name}: a build failed (branch ok="
                                   f"{br and br.get('ok')}, identity ok={m.get('ok')})")
            continue
        same_v2 = br["sha256"] == m["sha256"]
        same_v4 = br.get("v4_sha256") == m.get("v4_sha256")
        out["compared"].append({"profile": name, "v2_identical": same_v2,
                                "v4_identical": same_v4, "sha256": br["sha256"]})
        if not (same_v2 and same_v4):
            out["failures"].append(f"{name}: v2 identical={same_v2}, v4 identical={same_v4}")
    return out


def compare_upstream(builds: list[dict], specs: list[dict]) -> dict:
    """The measured, non-gating master column (D-02): for every upstream
    Fast / Bit-exact build, how it differs from the branch's own build of the
    same dataset (tags, A2B dE00, B2A device units; v2 file and v4 twin)."""
    out = {"compared": [], "errors": []}
    for m in [b for b in builds if b["job"].get("role") == "upstream"]:
        br_out = str(Path(m["job"]["out"]).parent.parent / Path(m["job"]["out"]).name)
        br = next((b for b in builds if b["job"]["out"] == br_out), None)
        name = Path(br_out).name
        if br is None or not br.get("ok") or not m.get("ok"):
            out["errors"].append(f"{name}: a build failed")
            continue
        ds = specs[m["job"]["spec_index"]]["ds"]
        rec = {"profile": name, "dataset": ds.name, "engine": m["job"]["engine"]}
        try:
            rec["v2"] = identity.measure_difference(
                br["job"]["out"], m["job"]["out"], ds.n_channels,
                ds.color_rep == "RGB", ds.ink_limit)
            if br.get("v4_path") and m.get("v4_path"):
                rec["v4_tags"] = identity.differing_tags(br["v4_path"], m["v4_path"])
        except Exception as exc:  # reported, never a gate
            rec["error"] = f"{type(exc).__name__}: {exc}"
        out["compared"].append(rec)
    return out


def check_gates(builds: list[dict], specs: list[dict]) -> dict:
    out = {"checked": [], "failures": []}
    for b in builds:
        j = b["job"]
        if j["engine"] != "accurate" or j.get("role") not in ("branch", "repeat", "sp"):
            continue
        ds = specs[j["spec_index"]]["ds"]
        name = Path(j["out"]).name
        if not b.get("ok"):
            out["failures"].append(f"{name}: accurate build failed: {b.get('error', '')[:300]}")
            continue
        v2 = validate(Path(j["out"]), ds.n_channels)
        v4p = b.get("v4_path")
        v4 = validate(Path(v4p), ds.n_channels) if v4p else {"missing": True}
        rec = {"profile": name, "n_channels": ds.n_channels, "v2": v2, "v4": v4}
        out["checked"].append(rec)
        bad = [k for k, v in {**{f"v2.{k}": v for k, v in v2.items()},
                              **{f"v4.{k}": v for k, v in v4.items()}}.items()
               if (k.endswith("_ok") and v is False) or k.endswith("missing")]
        if bad:
            out["failures"].append(f"{name}: {', '.join(bad)}")
    return out


if __name__ == "__main__":
    sys.exit(main())
