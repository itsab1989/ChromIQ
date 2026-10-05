"""Pale in-gamut colours (truth prints with L* > 90) through the B2A1 (Argyll), printed on the
truth: dE00 median / p95 / max, and the share above 2 dE00. Truth cloud = TAC-respecting prints,
so every target is printable."""
import sys, numpy as np
sys.path.insert(0,'tree')
from benchmarks.research import cmm, colour, gmq
from benchmarks.research.printers import build_printers
cache = {}
for f in sys.argv[1:]:
    icc,pid=f.rsplit(':',1); p=build_printers()[pid]
    if pid not in cache:
        cl = gmq.truth_cloud(p); rng=np.random.default_rng(7)
        pale = cl[cl[:,0] > 90]; pale = pale[rng.choice(len(pale), min(3000,len(pale)), replace=False)]
        # plus light tints made directly: one or two inks at 0.5-6 %
        n=p.n; d=np.zeros((1500,n))
        for i in range(1500):
            k=rng.choice(n, rng.integers(1,3), replace=False); d[i,k]=rng.uniform(0.005,0.06,len(k))
        cache[pid]=np.vstack([pale, p.lab_rel(d)])
    tg=cache[pid]
    dev=np.clip(cmm.b2a(icc,tg,'argyll'),0,1); de=colour.de2000(p.lab_rel(dev),tg)
    print(f"{icc.split('/')[-1][:46]:46s} n {len(tg)} med {np.median(de):.2f} p95 {np.percentile(de,95):.2f} max {de.max():.1f} >2: {100*(de>2).mean():.1f}% extra-ink>1%: {100*((dev[:,4:]>0.01).any(1)).mean():.0f}%")
