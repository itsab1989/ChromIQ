"""Agent 22: shape of the real whole-strip misread (read-only on Basti's data).
Is the bad strip a layout shift (a reading of the chart neighbour, or a blend
of two chart neighbours), in the chart's own patch order (SAMPLE_LOC)?"""
import glob, re, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parents[1] / "tree"))
from benchmarks.research import colour
W = np.array([96.42, 100.0, 82.49])
def read(p):
    t = Path(p).read_text(errors="replace").splitlines()
    f = next(l for l in t if l.startswith("SAMPLE_ID")).split()
    b = t.index("BEGIN_DATA"); e = t.index("END_DATA")
    rows = [l.split() for l in t[b + 1:e] if l.strip()]
    ix = [f.index(k) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
    loc = [r[f.index("SAMPLE_LOC")].strip('"') for r in rows] if "SAMPLE_LOC" in f else None
    return np.array([[float(r[i]) for i in ix] for r in rows]), loc
_, loc = read("/Users/Basti/ChromIQ/printer-test/runs/run1/printer-test.ti2")
aug = sorted(glob.glob("/Users/Basti/ChromIQ/printer-test/runs/run1/old/2026-08-08_1*/printer-test.ti3"))
R = {Path(f).parent.name: read(f)[0] for f in aug}
ref = R["2026-08-08_121205"]
lab = lambda x: colour.xyz_to_lab(x, W)
# layout order: strip letter, then patch number
def key(s):
    m = re.match(r"([A-Z]+)(\d+)", s); return (m.group(1), int(m.group(2)))
order = sorted(range(len(loc)), key=lambda i: key(loc[i]))
pos = {i: k for k, i in enumerate(order)}
for k in ("2026-08-08_120701", "2026-08-08_133622"):
    x = R[k]
    e = colour.de2000(lab(x), lab(ref)); bad = np.flatnonzero(e > 5)
    print(k, "bad locs", sorted([loc[i] for i in bad], key=key))
    strip = sorted(bad, key=lambda i: key(loc[i]))
    seq = [order[pos[i]] for i in strip]
    for sh in (-1, 1):
        nb = [order[min(max(pos[i] + sh, 0), len(order) - 1)] for i in strip]
        d1 = colour.de2000(lab(x[strip]), lab(ref[nb]))
        print(f"  vs layout neighbour {sh:+d}: median dE00 {np.median(d1):.2f}  p90 {np.percentile(d1,90):.2f}")
        best = []
        for a in np.linspace(0, 1, 21):
            mix = (1 - a) * ref[strip] + a * ref[nb]
            best.append((np.median(colour.de2000(lab(x[strip]), lab(mix))), a))
        m, a = min(best)
        print(f"  best blend own*(1-a)+nb*a: a={a:.2f} median dE00 {m:.2f}")
    print("  own-position error dE00: median %.1f, min %.1f, max %.1f" % (np.median(e[bad]), e[bad].min(), e[bad].max()))
print("--- is it another strip of the same chart (wrong strip read), or reversed?")
x = R["2026-08-08_120701"]
letters = sorted(set(key(l)[0] for l in loc))
byl = {L: sorted([i for i in range(len(loc)) if key(loc[i])[0] == L], key=lambda i: key(loc[i])) for L in letters}
D = byl["D"]
for L in letters:
    for rev in (False, True):
        src = byl[L][::-1] if rev else byl[L]
        if len(src) != len(D): continue
        d = colour.de2000(lab(x[D]), lab(ref[src]))
        print(f"  D read vs ref strip {L}{' reversed' if rev else ''}: median {np.median(d):.2f}")
others = [k for k in R if k not in ("2026-08-08_120701", "2026-08-08_133622")]
for k in others:
    d = colour.de2000(lab(R[k][D]), lab(ref[D])); print(f"  {k} strip D vs ref: median {np.median(d):.2f}")
