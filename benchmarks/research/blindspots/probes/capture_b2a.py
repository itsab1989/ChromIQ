"""Root-cause probe: run one Maximum accuracy build in-process and capture the
B2A1 node values (per-node inversion, after the hue-preserving clip, after the
refit) plus the forward model, pickled to OUT.pkl.
    python capture_b2a.py TI3 OUT.icc [--limit L]"""
import argparse, os, pickle, sys
from datetime import datetime
from pathlib import Path
import numpy as np
TREE = Path(__file__).resolve().parents[1] / "tree"
sys.path.insert(0, str(TREE)); os.chdir(TREE)
import workflow.profile_engine.b2a as b2a
import workflow.profile_engine.builder as builder
ap = argparse.ArgumentParser(); ap.add_argument("ti3"); ap.add_argument("out")
ap.add_argument("--limit", type=float, default=None); a = ap.parse_args()
cap = {"inv": [], "refine": []}
orig_inv, orig_ref = b2a.invert_to_device, b2a.refine_b2a_clut
def inv(model, target, **kw):
    d, r = orig_inv(model, target, **kw)
    if len(target) >= 30000:
        cap["inv"].append((target.copy(), d.copy(), r.copy(), kw.get("accurate")))
        cap["model"] = model
    return d, r
def ref(model, dev_clut, residual, grid, **kw):
    out = orig_ref(model, dev_clut, residual, grid, **kw)
    cap["refine"].append((dev_clut.copy(), residual.copy(), out.copy(), grid))
    return out
b2a.invert_to_device = inv; b2a.refine_b2a_clut = ref
s = builder.BuildSettings(quality="m", gammap_mode="accurate", ink_limit=a.limit,
                          icc_version="2", argyll_bin="/Applications/Argyll/bin",
                          source_gamut=os.environ.get("SRCGAM") or None, timestamp=datetime(2026, 1, 1))
builder.build_profile(a.ti3, a.out, s)
pickle.dump(cap, open(a.out + ".pkl", "wb"))
print("captured", len(cap["inv"]), len(cap["refine"]))
