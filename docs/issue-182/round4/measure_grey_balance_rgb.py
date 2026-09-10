"""Round 4, issue #182 — Knut's challenge: "RGB printer has no CMY channels to
balance ... is only half true."  He is right about half of it, and this measures
which half.

TR 015-2022 §5.3, verbatim: "The color aim for the 3-color near-neutral tone
scale (a.k.a. gray balance) is defined as a function of substrate CIELAB a* and
b* values, reduced in proportion to the relative darkness of the scale."

That sentence is device-independent.  This script computes exactly it on a REAL
ChromIQ measurement, indexing "relative darkness" by the scale's own L* instead
of by the cyan tone value TV_C (which an RGB chart has no way to carry), and
reports the grey-balance error the same way G7 does: dCh = sqrt(da*^2 + db*^2).

Read-only.
"""
import os, sys
from pathlib import Path
import numpy as np

REPO = Path(os.environ.get("CHROMIQ_REPO", "~/develop/ChromIQ")).expanduser()
sys.path.insert(0, str(REPO))
from workflow.ti3_analysis import parse_ti3, xyz_to_lab       # noqa: E402


def grey_scale(d):
    rgb = np.asarray(d.rgb, float)
    if rgb.max() > 101.0:
        rgb = rgb * (100.0 / 255.0)
    on = (np.abs(rgb[:, 0] - rgb[:, 1]) <= 1.0) & (np.abs(rgb[:, 1] - rgb[:, 2]) <= 1.0)
    idx = np.flatnonzero(on)
    if len(idx) < 6:
        return None
    lab = np.array([xyz_to_lab(tuple(v / 100.0 for v in d.xyz[i])) for i in idx])
    order = np.argsort(-lab[:, 0])            # lightest first
    return rgb[idx][order], lab[order]


def report(path):
    try:
        d = parse_ti3(path)
    except Exception:                                          # noqa: BLE001
        return None
    g = grey_scale(d)
    if g is None:
        return None
    rgb, lab = g
    Lw, Lk = lab[0, 0], lab[-1, 0]
    if Lw - Lk < 20:
        return None
    a_sub, b_sub = lab[0, 1], lab[0, 2]
    D = (Lw - lab[:, 0]) / (Lw - Lk)          # relative darkness, 0 at paper
    aim_a, aim_b = a_sub * (1 - D), b_sub * (1 - D)
    dch = np.hypot(lab[:, 1] - aim_a, lab[:, 2] - aim_b)
    return dict(n=len(lab), Lw=Lw, Lk=Lk, a_sub=a_sub, b_sub=b_sub,
                avg=float(dch.mean()), mx=float(dch.max()))


print("Substrate-relative grey balance of the neutral R=G=B ramp, computed on")
print("real measurements on this machine, with NO reference data of any kind.")
print("(G7 Grayscale press tolerance, for scale only: average dCh 1,5 / max 3,0)\n")
print(f"{'project / measurement':<50}{'steps':>6}{'L* white':>10}{'L* black':>10}"
      f"{'a*,b* paper':>16}{'avg dCh':>9}{'max dCh':>9}")
rows = []
for p in sorted(Path.home().joinpath("ChromIQ").rglob("*.ti3")):
    r = report(p)
    if r:
        rows.append((p, r))
for p, r in rows[:20]:
    lbl = f"{p.parents[2].name}/{p.name}"
    print(f"{lbl:<50}{r['n']:6d}{r['Lw']:10.2f}{r['Lk']:10.2f}"
          f"{r['a_sub']:8.2f},{r['b_sub']:6.2f}{r['avg']:9.2f}{r['mx']:9.2f}")
print(f"\n{len(rows)} of the measurements on this machine carry a neutral ramp long"
      f" enough to compute it on.")
