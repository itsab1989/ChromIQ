"""Build ONE profile in ONE source tree, in a fresh process (Agent 6).

Run as a script, never imported by the harness: every build gets its own
interpreter so the engine is imported from exactly the tree under test
(the research worktree, or a detached master checkout for the byte-identity
check) and no in-process cache (the colprof oracle cache in gamut_map)
leaks between builds.

    python build_worker.py '<json job>'

Job keys: tree, engine (colprof|fast|argyll|accurate), ti3, out, quality,
icc_version, ink_limit, source_gamut, candidates, argyll_bin, illuminant,
observer, timestamp (ISO). Prints one JSON line prefixed with ``RESULT ``.

Options audit (Agent 10b, 2026-10-05): a job may instead carry ``params``,
a dict of ``workflow.profile_builder.ProfileParams`` fields (every field the
Build Profile tab sets; unknown keys are an error, so nothing is dropped
silently). The build then takes EXACTLY the app's route:
``engine_builder.settings_from_params`` for the engine (plus the app's
argyll_bin / gammap_mode), ``ProfileBuilder._build_args`` for colprof. Extra
keys: ``settings`` (BuildSettings overrides for what the tab has no control
for, e.g. ink limits), ``log`` (path for the full progress / colprof output).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build_engine(job: dict) -> dict:
    tree = Path(job["tree"]).resolve()
    # The tree under test must win over this script's own directory.
    sys.path[:] = [str(tree)] + [p for p in sys.path
                                 if Path(p or ".").resolve() != Path(__file__).parent.resolve()]
    os.chdir(tree)
    from datetime import datetime
    import workflow.profile_engine.builder as builder_mod
    mod_file = Path(builder_mod.__file__).resolve()
    if tree not in mod_file.parents:
        raise RuntimeError(f"engine imported from {mod_file}, not from {tree}")
    import dataclasses
    if job.get("params") is not None:
        return _build_engine_params(job, builder_mod, mod_file)
    wanted = dict(
        quality=job.get("quality", "m"),
        b2a_quality=job.get("b2a_quality", ""),
        gammap_mode=job["engine"],
        ink_limit=job.get("ink_limit"),
        icc_version=str(job.get("icc_version", "2")),
        argyll_bin=job.get("argyll_bin"),
        source_gamut=job.get("source_gamut"),
        sat_gamut=bool(job.get("source_gamut")),
        illuminant=job.get("illuminant", ""),
        observer=job.get("observer", ""),
        spectral_physics=bool(job.get("spectral_physics", False)),
        timestamp=datetime.fromisoformat(job.get("timestamp",
                                                 "2026-01-01T00:00:00")),
    )
    # An older tree (master) may not know a field; it then gets that tree's
    # default, which is recorded so the identity check can be read correctly.
    known = {f.name for f in dataclasses.fields(builder_mod.BuildSettings)}
    dropped = {k: str(v) for k, v in wanted.items() if k not in known}
    settings = builder_mod.BuildSettings(
        **{k: v for k, v in wanted.items() if k in known})
    if job["engine"] == "accurate" and job.get("candidates"):
        settings.engine_candidates = frozenset(
            t for t in job["candidates"].split(",") if t)
    lines: list[str] = []
    settings.progress = lines.append
    t0 = time.perf_counter()
    res = builder_mod.build_profile(job["ti3"], job["out"], settings)
    secs = time.perf_counter() - t0
    out = Path(job["out"])
    return {"ok": True, "seconds": secs, "sha256": _sha(out),
            "bytes": out.stat().st_size,
            "outlier_rows": list(res.outlier_rows),
            "a2b_grid": res.a2b_grid, "b2a_grid": res.b2a_grid,
            "fit_median_de00": res.fit_median_de00,
            "engine_file": str(mod_file),
            "dropped_settings": dropped,
            "log_tail": lines[-6:],
            "model_lines": [ln for ln in lines if "held-out patches of this"
                            in ln or "Gaussian process" in ln]}


def _params(job: dict):
    """ProfileParams from the job, exactly as the tab would hand them over."""
    from workflow.profile_builder import ProfileParams
    import dataclasses
    known = {f.name for f in dataclasses.fields(ProfileParams)}
    extra = set(job["params"]) - known
    if extra:
        raise KeyError(f"not ProfileParams fields: {sorted(extra)}")
    kw = dict(job["params"])
    kw["ti3_path"] = Path(kw.get("ti3_path") or job["ti3"])
    return ProfileParams(**kw)


def _build_engine_params(job: dict, builder_mod, mod_file: Path) -> dict:
    from datetime import datetime
    from workflow.engine_builder import settings_from_params
    params = _params(job)
    settings = settings_from_params(params)          # the app's own mapping
    settings.argyll_bin = job.get("argyll_bin") or "/Applications/Argyll/bin"
    settings.gammap_mode = job.get("engine", "accurate")
    settings.timestamp = datetime.fromisoformat(job.get("timestamp",
                                                        "2026-01-01T00:00:00"))
    for k, v in (job.get("settings") or {}).items():
        if not hasattr(settings, k):
            raise KeyError(f"BuildSettings has no field {k}")
        setattr(settings, k, v)
    if job.get("candidates"):
        settings.engine_candidates = frozenset(
            t for t in job["candidates"].split(",") if t)
    lines: list[str] = []
    settings.progress = lines.append
    t0 = time.perf_counter()
    res = builder_mod.build_profile(job["ti3"], job["out"], settings)
    secs = time.perf_counter() - t0
    out = Path(job["out"])
    if job.get("log"):
        Path(job["log"]).write_text("\n".join(lines) + "\n", encoding="utf-8")
    import dataclasses as _dc
    applied = {f.name: repr(getattr(settings, f.name))
               for f in _dc.fields(settings) if f.name not in ("progress", "timestamp")}
    return {"ok": True, "seconds": secs, "sha256": _sha(out),
            "bytes": out.stat().st_size,
            "outlier_rows": list(res.outlier_rows),
            "a2b_grid": res.a2b_grid, "b2a_grid": res.b2a_grid,
            "fit_median_de00": res.fit_median_de00,
            "perceptual_distinct": bool(res.perceptual_distinct),
            "engine_file": str(mod_file), "settings_applied": applied,
            "log_tail": lines[-6:], "n_log_lines": len(lines)}


def build_colprof_params(job: dict) -> dict:
    """colprof with the app's own argument list (ProfileBuilder._build_args)."""
    tree = Path(job["tree"]).resolve()
    sys.path[:] = [str(tree)] + [p for p in sys.path
                                 if Path(p or ".").resolve() != Path(__file__).parent.resolve()]
    os.chdir(tree)
    from workflow.profile_builder import ProfileBuilder
    argyll = Path(job.get("argyll_bin") or "/Applications/Argyll/bin")
    out = Path(job["out"])
    base = out.with_suffix("")
    ti3 = Path(str(base) + ".ti3")
    shutil.copyfile(job["ti3"], ti3)
    job = dict(job, params=dict(job["params"], ti3_path=str(ti3)))
    params = _params(job)
    pb = ProfileBuilder.__new__(ProfileBuilder)      # no runner: args only
    args = pb._build_args(params)
    extra = list(job.get("colprof_args") or [])
    args = args[:-1] + extra + args[-1:]
    cmd = [str(argyll / "colprof")] + args
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       timeout=float(job.get("timeout", 1800)), cwd=str(ti3.parent))
    secs = time.perf_counter() - t0
    if job.get("log"):
        Path(job["log"]).write_text("$ " + " ".join(cmd) + "\n" + r.stdout + r.stderr,
                                    encoding="utf-8")
    icc = Path(str(base) + ".icc")
    if r.returncode != 0 or not icc.exists():
        return {"ok": False, "seconds": secs, "returncode": r.returncode, "args": args,
                "error": (r.stderr or r.stdout)[-800:]}
    pb._restore_accents(params)                      # the app's finish step
    if icc != out:
        icc.replace(out)
    tail = [ln for ln in r.stdout.splitlines() if ln.strip()][-4:]
    return {"ok": True, "seconds": secs, "sha256": _sha(out), "args": args,
            "bytes": out.stat().st_size, "log_tail": tail}


def build_colprof(job: dict) -> dict:
    """colprof -q<q> [-S gamut] [-i ill] [-o obs] on a copy named like the out file."""
    argyll = Path(job.get("argyll_bin") or "/Applications/Argyll/bin")
    out = Path(job["out"])
    base = out.with_suffix("")
    shutil.copyfile(job["ti3"], str(base) + ".ti3")
    args = [str(argyll / "colprof"), "-v", f"-q{job.get('quality', 'm')}"]
    if job.get("b2a_quality"):
        args.append(f"-b{job['b2a_quality']}")
    if job.get("ink_limit"):
        # The same limit the engine is handed; colprof itself then applies
        # its own rule to it (documented in the audit).
        args += ["-l", f"{float(job['ink_limit']):g}"]
    if job.get("source_gamut"):
        args += ["-S", str(job["source_gamut"])]
    if job.get("illuminant"):
        args += ["-i", job["illuminant"]]
    if job.get("observer"):
        args += ["-o", job["observer"]]
    args.append(str(base))
    t0 = time.perf_counter()
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       timeout=float(job.get("timeout", 1800)))
    secs = time.perf_counter() - t0
    icc = Path(str(base) + ".icc")
    if r.returncode != 0 or not icc.exists():
        return {"ok": False, "seconds": secs, "returncode": r.returncode,
                "error": (r.stderr or r.stdout)[-800:]}
    if icc != out:
        icc.replace(out)
    tail = [ln for ln in r.stdout.splitlines() if ln.strip()][-4:]
    return {"ok": True, "seconds": secs, "sha256": _sha(out),
            "bytes": out.stat().st_size, "log_tail": tail}


def main() -> None:
    job = json.loads(sys.argv[1])
    try:
        if job["engine"] == "colprof":
            res = build_colprof_params(job) if job.get("params") is not None \
                else build_colprof(job)
        else:
            res = build_engine(job)
    except Exception as exc:                       # reported, not hidden
        import traceback
        res = {"ok": False, "error": f"{type(exc).__name__}: {exc}",
               "traceback": traceback.format_exc()[-2000:]}
    print("RESULT " + json.dumps(res))


if __name__ == "__main__":
    main()
