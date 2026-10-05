"""Agent 21 build harness: one Maximum accuracy build of a .ti3 in the agent 21 tree,
with the forward fit CACHED on disk so B2A-only variants (ink rules, smoothness) cost only
the inversion. Same settings as Agent 18's study.py builds (quality m, v2, ink limit = the
printer's TAC, no source gamut), except argyll_bin None (the 5+ ink colprof proxy shapes
only the mapped tables, never the colorimetric one in Maximum accuracy; builder.py k_prior_col).

    python a21build.py TI3 OUT.icc --limit 320 [--tokens a,b] [--cache DIR] [--no-cache]

Prints one line: RESULT {json} (seconds per stage, cache hit).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE / "tree"
sys.path.insert(0, str(TREE))
ORIG = os.getcwd()
os.chdir(TREE)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ti3")
    ap.add_argument("out")
    ap.add_argument("--limit", type=float, default=None)
    ap.add_argument("--tokens", default="")
    ap.add_argument("--cache", default=str(HERE / "cache"))
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--quality", default="m")
    ap.add_argument("--fit-only", action="store_true",
                    help="stop after the forward fit; pickle (model, outliers, lam) to OUT")
    a = ap.parse_args()
    a.ti3 = os.path.join(ORIG, a.ti3)
    a.out = os.path.join(ORIG, a.out)
    a.cache = os.path.join(ORIG, a.cache)

    from datetime import datetime
    import numpy as np
    import workflow.profile_engine.accuracy as acc
    import workflow.profile_engine.builder as builder

    stage = {}
    orig = acc.fit_forward_model_accurate
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)

    def cached(device, lab, **kw):
        h = hashlib.sha256()
        h.update(np.ascontiguousarray(device, float).tobytes())
        h.update(np.ascontiguousarray(lab, float).tobytes())
        rw = kw.get("row_weights")
        if rw is not None:
            h.update(np.ascontiguousarray(rw, float).tobytes())
        h.update(json.dumps({k: (v if isinstance(v, (int, float, str, bool, type(None))) else str(type(v)))
                             for k, v in sorted(kw.items()) if k not in ("progress", "row_weights")},
                            sort_keys=True).encode())
        f = cache / f"fit-{h.hexdigest()[:24]}.pkl"
        t0 = time.perf_counter()
        if f.exists() and not a.no_cache:
            out = pickle.loads(f.read_bytes())
            stage["fit_cache"] = "hit"
        else:
            out = orig(device, lab, **kw)
            f.write_bytes(pickle.dumps(out))
            stage["fit_cache"] = "miss"
        stage["fit_s"] = time.perf_counter() - t0
        if a.fit_only:
            Path(a.out).write_bytes(pickle.dumps(out))
            print("RESULT " + json.dumps({"ok": True, "fit_only": True, **stage}))
            sys.stdout.flush()
            os._exit(0)
        return out

    acc.fit_forward_model_accurate = cached
    # Capture the colorimetric B2A stage's inputs (model and policy arguments) for the
    # model-level separation probes (sepprobe.py): OUT.b2a.pkl.
    import workflow.profile_engine.b2a as b2a_mod
    capture: dict = {}
    _orig_build, _orig_axis = b2a_mod.build_b2a_clut, b2a_mod.apply_neutral_axis

    def cap_build(model, grid, **kw):
        t0 = time.perf_counter()
        r = _orig_build(model, grid, **kw)
        stage["pernode_s"] = time.perf_counter() - t0
        capture["model"], capture["grid"] = model, grid
        capture["kw"] = {k: v for k, v in kw.items() if k != "progress"}
        capture["dev_clut"], capture["residual"] = r
        return r

    def cap_axis(dev_clut, node_lab, axis, model, **kw):
        capture["axis"] = axis
        return _orig_axis(dev_clut, node_lab, axis, model, **kw)
    b2a_mod.build_b2a_clut, b2a_mod.apply_neutral_axis = cap_build, cap_axis
    settings = builder.BuildSettings(
        quality=a.quality, gammap_mode="accurate", ink_limit=a.limit, icc_version="2",
        argyll_bin=None, source_gamut=None, timestamp=datetime(2026, 1, 1))
    toks = frozenset(t for t in a.tokens.split(",") if t)
    if toks:
        settings.engine_candidates = toks
    lines: list[str] = []
    marks: list[tuple[float, str]] = []
    t_start = time.perf_counter()

    def prog(m: str) -> None:
        lines.append(m)
        marks.append((time.perf_counter() - t_start, m))
    settings.progress = prog
    builder.build_profile(a.ti3, a.out, settings)
    total = time.perf_counter() - t_start
    sha = hashlib.sha256(Path(a.out).read_bytes()).hexdigest()
    if capture:
        Path(a.out + ".b2a.pkl").write_bytes(pickle.dumps(capture))
    print("RESULT " + json.dumps({"ok": True, "seconds": total, "sha256": sha, **stage,
                                   "tokens": sorted(toks),
                                   "marks": [(round(t, 1), m[:90]) for t, m in marks
                                             if "/" not in m or "1/" in m][:60]}))


if __name__ == "__main__":
    main()
