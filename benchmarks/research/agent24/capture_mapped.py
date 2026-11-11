"""Agent 24: capture the mapped targets and the per-node inversion of B2A0/B2A2 in one build.

    python capture_mapped.py TI3 OUT.icc TOKENS(comma or '') LIMIT
Writes OUT.icc.pkl: {"calls": [(targets, device, residual)], "model": model}."""
import os
import pickle
import sys
from datetime import datetime
from pathlib import Path

TREE = Path(os.environ.get("A24_TREE", Path(__file__).resolve().parents[1] / "tree"))
sys.path.insert(0, str(TREE))
os.chdir(TREE)
import workflow.profile_engine.b2a as b2a            # noqa: E402
import workflow.profile_engine.builder as builder    # noqa: E402

ti3, out, toks, lim = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
cap = {"calls": []}
orig = b2a.invert_to_device


def inv(model, target, **kw):
    d, r = orig(model, target, **kw)
    if kw.get("progress_label", "").startswith("Gamut mapping"):
        cap["calls"].append((target.copy(), d.copy(), r.copy()))
        cap["model"] = model
    return d, r


b2a.invert_to_device = inv
s = builder.BuildSettings(quality="m", gammap_mode="accurate", ink_limit=lim, icc_version="2",
                          argyll_bin="/Applications/Argyll/bin",
                          source_gamut=str(TREE / "assets/profiles/ClayRGB1998.icm"),
                          sat_gamut=True, timestamp=datetime(2026, 1, 1))
s.engine_candidates = frozenset(t for t in toks.split(",") if t)
builder.build_profile(ti3, out, s)
pickle.dump(cap, open(out + ".pkl", "wb"))
print("captured", len(cap["calls"]))
