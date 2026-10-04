"""Seed builds (protocol v2.1 3b). usage: s_build.py TREE ENGINE OUT_DIR PRINTERS SEEDS(a-b) LEVEL [CANDIDATES]
Dataset k = synthetic(pid, seed=23+k, chart_seed=11+k) as run.py's seeds suite."""
import sys
from pathlib import Path
here = Path(__file__).parent
tree, eng, out = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).resolve()
label = eng
if ":" in eng:
    label, eng = eng.split(":", 1)        # LABEL:ENGINE
pids = sys.argv[4].split(","); a, b = (int(x) for x in sys.argv[5].split("-")); level = sys.argv[6]
cands = sys.argv[7] if len(sys.argv) > 7 else ""
sys.path.insert(0, str(here / "w2"))          # runner and datasets from the w2 tree (records signals)
from benchmarks.research import run as R, datasets as dsm
from benchmarks.research.printers import build_printers
pr = build_printers(); (out / label).mkdir(parents=True, exist_ok=True); work = out / "work"; work.mkdir(exist_ok=True)
for k in range(a, b + 1):
    for pid in pids:
        o = out / label / f"{pid}-{level}-k{k}.icc"
        if o.exists():
            continue
        ds = dsm.synthetic(pid, work, 900, level=level, seed=23 + k, chart_seed=11 + k, printers=pr)
        job = {"ti3": str(ds.ti3), "quality": "m", "icc_version": "2", "ink_limit": ds.ink_limit,
               "argyll_bin": R.ARGYLL, "timestamp": R.TIMESTAMP, "illuminant": "", "b2a_quality": "",
               "source_gamut": str(tree / "assets/profiles/ClayRGB1998.icm"), "engine": eng,
               "tree": str(tree), "out": str(o), "role": "branch"}
        if cands:
            job["candidates"] = cands
        res = R.run_build(job)
        print(pid, k, eng, res.get("ok"), res.get("error", "")[:200], flush=True)
