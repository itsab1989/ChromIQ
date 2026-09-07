"""Round 5, issue #182, agent DD. Re-verifies the FOGRA51 CMYK->RGB column-swap
numbers quoted in comment 5557941490 (item 13) and builds the small table Knut
asked for on 2026-09-06. Read-only: reads FOGRA51.txt, imports ChromIQ's own
ciede2000, writes nothing into the repo."""
import os, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

REPO = Path(os.environ.get("CHROMIQ_REPO", "~/develop/ChromIQ")).expanduser()
F51 = Path(os.environ.get("CHROMIQ_RESEARCH", "~/develop/ChromIQ-research")).expanduser().joinpath("issue-182/02-challenge/fogra/"
           "Fogra Characterisation Data/x/FOGRA51.txt")
sys.path.insert(0, str(REPO))
from workflow.ti3_analysis import ciede2000

lines = F51.read_text(errors="replace").splitlines()
i0 = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
i1 = next(i for i, l in enumerate(lines) if l.strip() == "END_DATA")
rows = [l.split() for l in lines[i0 + 1:i1] if l.strip()]
cmyk = np.array([[float(r[j]) for j in (1, 2, 3, 4)] for r in rows])
lab = np.array([[float(r[j]) for j in (5, 6, 7)] for r in rows])
n = len(rows)

def to_rgb(c):  # Knut's mapping, 0..100 scale: CMYK 0 0 0 0 -> RGB 100 100 100
    C, M, Y, K = (c[:, i] / 100 for i in range(4))
    return np.stack([100*(1-C)*(1-K), 100*(1-M)*(1-K), 100*(1-Y)*(1-K)], 1)

rgb = to_rgb(cmyk)
key = lambda a: tuple(np.round(a, 4))
cmyk_keys = [key(c) for c in cmyk]; rgb_keys = [key(r) for r in rgb]
nc, nr = len(set(cmyk_keys)), len(set(rgb_keys))
print(f"rows: {n}")
print(f"distinct CMYK: {nc}  (duplicates already in the file: {n-nc})")
print(f"distinct RGB : {nr}  (rows sharing an RGB value with another row: {n-nr}; created by the conversion: {(n-nr)-(n-nc)})")

groups = defaultdict(list)
for i, k in enumerate(rgb_keys): groups[k].append(i)
multi = {k: v for k, v in groups.items() if len(v) > 1}
print(f"RGB values carrying more than one CMYK row: {len(multi)}")
sizes = Counter(len(v) for v in multi.values())
print("group sizes:", dict(sorted(sizes.items())))

black = groups[key(np.zeros(3))]
print(f"\nrows landing on RGB 0/0/0: {len(black)}")
k100 = [i for i in black if cmyk[i][3] == 100]
cmy100 = [i for i in black if cmyk[i][3] < 100]
print(f"  with K = 100: {len(k100)}   with C=M=Y=100 and K < 100: {len(cmy100)}")
worst, pair = 0, None
for a in range(len(black)):
    for b in range(a+1, len(black)):
        d = ciede2000(tuple(lab[black[a]]), tuple(lab[black[b]]))
        if d > worst: worst, pair = d, (black[a], black[b])
print(f"  furthest apart of the {len(black)*(len(black)-1)//2} pairs: {worst:.2f} dE00, CMYK {cmyk[pair[0]].astype(int).tolist()} vs {cmyk[pair[1]].astype(int).tolist()}")
Ls = sorted(lab[i][0] for i in black)
print(f"  L* of the 39 runs from {Ls[0]:.2f} to {Ls[-1]:.2f}")

def find(c):
    return next(i for i in range(n) if tuple(cmyk[i].astype(int)) == tuple(c))
def fmt_lab(i): return f"{lab[i][0]:.2f} / {lab[i][1]:.2f} / {lab[i][2]:.2f}"
def fmt_rgb(i): return "/".join(f"{v:g}" for v in np.round(rgb[i], 1))

print("\n--- table rows for Knut ---")
pureK = find((0,0,0,100))
show = [(0,0,0,100),(100,100,100,0),(100,100,100,100),(0,100,0,100),(100,0,100,100),(100,100,0,100)]
for c in show:
    i = find(c)
    print(f"CMYK {c}  -> RGB {fmt_rgb(i)}  Lab {fmt_lab(i)}  dE00 vs pure K: {ciede2000(tuple(lab[pureK]), tuple(lab[i])):.2f}")
print()
for a, b in [((0,0,0,40),(40,40,40,0)), ((0,0,0,20),(20,20,20,0)), ((0,0,0,10),(10,10,10,0))]:
    i, j = find(a), find(b)
    print(f"CMYK {a} -> RGB {fmt_rgb(i)} Lab {fmt_lab(i)} | CMYK {b} -> RGB {fmt_rgb(j)} Lab {fmt_lab(j)} | dE00 {ciede2000(tuple(lab[i]), tuple(lab[j])):.2f}")
paper = [i for i in range(n) if tuple(cmyk[i].astype(int)) == (0,0,0,0)]
print(f"\npaper 0 0 0 0 appears {len(paper)} times, Lab {[fmt_lab(i) for i in paper]}, -> RGB {fmt_rgb(paper[0])}")

# how many of the conversion-created collisions involve K > 0 in at least one member?
created = 0; withK = 0
for k, v in multi.items():
    distinct_cmyk = {cmyk_keys[i] for i in v}
    extra = len(distinct_cmyk) - 1          # collisions the conversion created in this group
    created += extra
    if extra and any(cmyk[i][3] > 0 for i in v): withK += extra
print(f"\nconversion-created collisions: {created}; of these, groups containing a K>0 row: {withK}")
# collisions among rows with K == 0 only
k0 = [i for i in range(n) if cmyk[i][3] == 0]
print(f"rows with K=0: {len(k0)}; distinct CMYK among them {len({cmyk_keys[i] for i in k0})}; distinct RGB among them {len({rgb_keys[i] for i in k0})}")
