"""Build accurate profiles for chosen printers at ONE noise level (run.py builds both).
usage: p_build.py TREE OUT_DIR PRINTERS LEVEL [CANDIDATES]"""
import json, sys
from pathlib import Path
tree, out, pids, level = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3].split(","), sys.argv[4]
cands = sys.argv[5] if len(sys.argv) > 5 else ""
sys.path.insert(0, str(tree))
from benchmarks.research import run as R, datasets as dsm
from benchmarks.research.printers import build_printers
pr = build_printers(); (out / "profiles").mkdir(parents=True, exist_ok=True); (out / "work").mkdir(exist_ok=True)
for pid in pids:
    o = out / "profiles" / f"baseline-{pid}-{level}-accurate.icc"
    if o.exists():
        continue
    ds = dsm.synthetic(pid, out / "work", 900, level=level, printers=pr)
    job = {"ti3": str(ds.ti3), "quality": "m", "icc_version": "both", "ink_limit": ds.ink_limit,
           "argyll_bin": R.ARGYLL, "timestamp": R.TIMESTAMP, "illuminant": "", "b2a_quality": "",
           "source_gamut": str(tree / "assets/profiles/ClayRGB1998.icm"), "engine": "accurate",
           "tree": str(tree), "out": str(o), "role": "branch"}
    if cands:
        job["candidates"] = cands
    res = R.run_build(job)
    print(pid, level, res.get("ok"), res.get("error", "")[:200], flush=True)
