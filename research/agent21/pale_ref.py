"""Pale sample (metrics.pale_device, Argyll) on battery v3 baseline colprof profiles (same charts)."""
import sys, numpy as np
from pathlib import Path
sys.path.insert(0, 'tree')
from benchmarks.research import cmm, colour, metrics
from benchmarks.research.printers import build_printers
P = Path('/Users/Basti/develop/ProfileEngineResearch/Benchmarks/baseline-v3-8d269c8e/profiles')
pr = build_printers()
for pid in sys.argv[1].split(','):
    p = pr[pid]
    for f in sorted(P.glob(f'v3-{pid}-*-colprof.icc')):
        dev = metrics.pale_device(p.n, False, 1500); lab = p.lab_rel(dev); k = lab[:, 0] > 90
        out = p.lab_rel(np.clip(cmm.b2a(str(f), lab[k], 'argyll'), 0, 1)); de = colour.de2000(out, lab[k])
        print(f"{f.name[3:-4]:45s} med {np.median(de):.2f} p95 {np.percentile(de,95):.2f} >2 {np.mean(de>2):.2f}")
