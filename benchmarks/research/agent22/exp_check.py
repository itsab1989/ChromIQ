"""Which read of strip D matches the chart's own expected colours (.ti2) and its device values?"""
import sys, re, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "tree"))
from benchmarks.research import colour
W = np.array([96.42, 100.0, 82.49])
def read(p):
    t = Path(p).read_text(errors="replace").splitlines()
    f = next(l for l in t if l.startswith("SAMPLE_ID")).split()
    b = t.index("BEGIN_DATA"); e = t.index("END_DATA")
    rows = [l.split() for l in t[b + 1:e] if l.strip()]
    ix = [f.index(k) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
    loc = [r[f.index("SAMPLE_LOC")].strip('"') for r in rows]
    dv = [f.index(k) for k in ("RGB_R", "RGB_G", "RGB_B")]
    return np.array([[float(r[i]) for i in ix] for r in rows]), loc, np.array([[float(r[i]) for i in dv] for r in rows])
exp, loc, dev = read("/Users/Basti/ChromIQ/printer-test/runs/run1/printer-test.ti2")
lab = lambda x: colour.xyz_to_lab(x, W)
D = [i for i, l in enumerate(loc) if l.startswith("D")]
for name in ("2026-08-08_121205", "2026-08-08_120701", "2026-08-08_114739", "2026-08-08_133622", "2026-08-08_125349"):
    x, _, _ = read(f"/Users/Basti/ChromIQ/printer-test/runs/run1/old/{name}/printer-test.ti3")
    for nm, rows in (("D", D), ("not D", [i for i in range(90) if i not in D])):
        e = colour.de2000(lab(x[rows]), lab(exp[rows]))
        print(f"{name} strip {nm:5s}: dE00 to the chart's expected colours median {np.median(e):5.1f}")
x, _, _ = read("/Users/Basti/ChromIQ/printer-test/runs/run1/old/2026-08-08_121205/printer-test.ti3")
y, _, _ = read("/Users/Basti/ChromIQ/printer-test/runs/run1/old/2026-08-08_120701/printer-test.ti3")
for i in D[:5]:
    print(loc[i], dev[i], "121205", lab(x[i:i+1]).round(0), "120701", lab(y[i:i+1]).round(0), "expected", lab(exp[i:i+1]).round(0))
