import sys, numpy as np
sys.path.insert(0,'tree')
from benchmarks.research import cmm, colour, metrics
from benchmarks.research.printers import build_printers
pid=sys.argv[1]; p=build_printers()[pid]
for f in sys.argv[2:]:
    ls=np.arange(1.0,100.0001,0.25); tg=np.stack([ls,0*ls,0*ls],1)
    d=np.clip(cmm.b2a(f,tg,'argyll'),0,1); pr=p.lab_rel(d)
    bl=p.lab_rel(np.clip(cmm.b2a(f,np.array([[0.,0,0]]),'argyll'),0,1))[0,0]
    m=ls>=bl+1; P=pr[m]; dL=np.diff(P[:,0]); d2=np.linalg.norm(np.diff(P,2,axis=0),axis=1)
    dev=metrics.pale_device(p.n,False,1500); lab=p.lab_rel(dev); k=lab[:,0]>90
    de=colour.de2000(p.lab_rel(np.clip(cmm.b2a(f,lab[k],'argyll'),0,1)),lab[k])
    print(f"{f:45s} black {bl:.2f} rev {(dL<-0.05).sum()} d2 {d2.max():.2f} pale {np.median(de):.2f}/{np.percentile(de,95):.2f}")
