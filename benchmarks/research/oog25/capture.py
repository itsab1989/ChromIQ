"""Agent 25 (F-15/F-17): capture the colorimetric B2A stage of one Maximum
accuracy build, so B2A1 variants can be replayed in minutes instead of a full
build (fit, GP layer, colprof oracle, perceptual tables are untouched by the
colorimetric clip).

    python -m benchmarks.research.oog25.capture TI3 OUT.icc [--limit L] [--tokens a,b]

Builds exactly like the battery build worker (engine "accurate", quality m,
ClayRGB source gamut, v2 + v4), and writes OUT.icc.cap.pkl with the forward
model and the arguments of build_b2a_clut / apply_neutral_axis /
refine_b2a_clut. ``replay.py`` re-runs that stage with research tokens and
splices the new B2A1 and gamt CLUTs into a copy of OUT.icc.
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
from datetime import datetime
from pathlib import Path

for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_k, "1")
os.environ.setdefault("PYTHONHASHSEED", "0")

TREE = Path(__file__).resolve().parents[3]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ti3")
    ap.add_argument("out")
    ap.add_argument("--limit", type=float, default=None)
    ap.add_argument("--tokens", default="")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(TREE))
    os.chdir(TREE)
    import workflow.profile_engine.b2a as b2a
    import workflow.profile_engine.builder as builder
    from benchmarks.research import run

    cap: dict = {}
    o_build, o_axis, o_ref = (b2a.build_b2a_clut, b2a.apply_neutral_axis,
                              b2a.refine_b2a_clut)

    def build(model, grid, **kw):
        cap["model"] = model
        cap["grid"] = grid
        cap["build_kw"] = {k: v for k, v in kw.items() if k != "progress"}
        return o_build(model, grid, **kw)

    def axis(dev_clut, node_lab, ax, model, **kw):
        cap["axis"] = ax
        cap["axis_kw"] = {k: v for k, v in kw.items() if k != "progress"}
        return o_axis(dev_clut, node_lab, ax, model, **kw)

    def ref(model, dev_clut, residual, grid, **kw):
        cap["refine_kw"] = {k: v for k, v in kw.items()
                            if k not in ("progress", "fixed_nodes")}
        out = o_ref(model, dev_clut, residual, grid, **kw)
        cap["refined"] = out.copy()
        return out

    b2a.build_b2a_clut, b2a.apply_neutral_axis, b2a.refine_b2a_clut = build, axis, ref
    s = builder.BuildSettings(
        quality="m", b2a_quality="", gammap_mode="accurate", ink_limit=a.limit,
        icc_version="both", argyll_bin=run.ARGYLL, source_gamut=run.SOURCE_GAMUT,
        sat_gamut=True, illuminant="", observer="",
        timestamp=datetime.fromisoformat(run.TIMESTAMP))
    if a.tokens:
        s.engine_candidates = frozenset(t for t in a.tokens.split(",") if t)
    lines: list[str] = []
    s.progress = lines.append
    res = builder.build_profile(a.ti3, a.out, s)
    cap["is_additive"] = res is not None and getattr(res, "is_additive", None)
    cap["tokens"] = a.tokens
    cap["log"] = lines
    Path(a.out + ".cap.pkl").write_bytes(pickle.dumps(cap))
    print("captured", a.out, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
