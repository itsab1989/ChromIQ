import sys, numpy as np
sys.path.insert(0,'tree')
from benchmarks.research import cmm, colour
from benchmarks.research.printers import build_printers
pts=[(99,0.4,0.6),(99,1,1),(98,4,0),(98,-4,0),(98,0,4),(98,0,-4),(97,3,3),(95,5,5),(100,4,4),(100,8,8)]
lab=np.array(pts,float)
for f in sys.argv[1:]:
    icc,pid=f.split(':'); p=build_printers()[pid]
    d=np.clip(cmm.b2a(icc,lab,'argyll'),0,1); pr=p.lab_rel(d)
    de=colour.de2000(pr[:8],lab[:8])
    print(icc.split('/')[-1][:40].ljust(40), 'printed L:', ' '.join(f'{x:5.1f}' for x in pr[:,0]), '| dE00 in-gamut max %.1f'%de.max())
