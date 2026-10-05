import json,glob,sys,re
from collections import defaultdict
rows=[]
for f in sorted(glob.glob('all/*.json')):
    r=json.load(open(f)); n=f.split('/')[-1][3:-5]
    over=max((v['clut_L_over_100'] for v in r['tags'].values()),default=0)
    get=lambda k,f2: (f2(r[k]) if k in r and 'error' not in r[k] else None)
    rows.append(dict(name=n, n=r['n'], over=over, same=r['non_a2b_identical'],
        arg=get('L1vsL0-argyll',lambda v:v['max']), lc=get('L1vsL0-lcms',lambda v:v['max']), ir=get('L1vsL0-iccref',lambda v:v['max']),
        csw0=get('L0-colorsync',lambda v:v['white_de']), csw1=get('L1-colorsync',lambda v:v['white_de']),
        csn0=get('L0-colorsync',lambda v:v['neutral']['med']), csn1=get('L1-colorsync',lambda v:v['neutral']['med']),
        csnx0=get('L0-colorsync',lambda v:v['neutral']['max']), csnx1=get('L1-colorsync',lambda v:v['neutral']['max']),
        csr0=get('L0-colorsync',lambda v:v['random']['med']), csr1=get('L1-colorsync',lambda v:v['random']['med']),
        csp0=get('L0-colorsync',lambda v:v['random']['p95']), csp1=get('L1-colorsync',lambda v:v['random']['p95'])))
def cls(r):
    nm=r['name']
    if nm.startswith('R-'): kind='real'
    else: kind='synthetic'
    return {3:'RGB/CMY',4:'CMYK'}.get(r['n'],f"{r['n']} inks")
g=defaultdict(list)
for r in rows: g[cls(r)].append(r)
import numpy as np
print("profiles:",len(rows)," any CLUT L*>100:",sum(r['over']>0 for r in rows)," non-A2B tags identical:",all(r['same'] for r in rows))
for k in ('arg','lc','ir'): print(k,"max L1 vs L0 dE00 over all:", max(r[k] for r in rows if r[k] is not None), "n",sum(r[k] is not None for r in rows))
print("| class | profiles | ColorSync white | neutral median | neutral max | random median | random p95 | worse rows |")
for c,rs in g.items():
    f=lambda a: np.median([r[a] for r in rs if r[a] is not None])
    worse=sum(1 for r in rs for a,b in (('csn0','csn1'),('csr0','csr1'),('csp0','csp1'),('csnx0','csnx1'),('csw0','csw1')) if r[a] is not None and r[b]>r[a]+0.005)
    print(f"| {c} | {len(rs)} | {f('csw0'):.3f} -> {f('csw1'):.3f} | {f('csn0'):.3f} -> {f('csn1'):.3f} | {f('csnx0'):.3f} -> {f('csnx1'):.3f} | {f('csr0'):.3f} -> {f('csr1'):.3f} | {f('csp0'):.3f} -> {f('csp1'):.3f} | {worse} |")
for r in rows:
    for a,b in (('csn0','csn1'),('csr0','csr1'),('csp0','csp1'),('csnx0','csnx1'),('csw0','csw1')):
        if r[a] is not None and r[b]>r[a]+0.005: print("WORSE",r['name'],a,r[a],r[b])
