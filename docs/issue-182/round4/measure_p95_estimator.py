"""Round 4, issue #182, K9 — what the 95th-percentile estimator choice actually
changes.  Read-only; nothing in the ChromIQ checkout is modified on disk.

ChromIQ today:  k = round(0.95*n);  p95 = max(a[:k])  ->  a[k-1]
Nearest-rank :  r = ceil (0.95*n);  p95 = a[r-1]

Part 2 captures the REAL delta list the shipped report builds, by wrapping
`_stats` in memory for the duration of the run.
"""
import math, os, sys
from pathlib import Path
import numpy as np

REPO = Path(os.environ.get("CHROMIQ_REPO", "~/develop/ChromIQ")).expanduser()
sys.path.insert(0, str(REPO))
import workflow.measurement_report as MR                       # noqa: E402


def ranks(n):
    k = max(1, min(n - 1, int(round(n * 0.95))))
    r = max(1, min(n, math.ceil(n * 0.95)))
    return k, r


print("== 1. Where the two ranks differ at all ==")
print(" n      0.95n    ChromIQ rank  nearest-rank  differ?")
for n in (24, 46, 72, 84, 100, 128, 204, 300, 324, 918, 1160, 1617, 1944):
    k, r = ranks(n)
    print(f"{n:5d}  {n*0.95:9.2f}  {k:12d}  {r:12d}  {'YES' if k != r else 'no'}")
diff = [n for n in range(20, 2001) if ranks(n)[0] != ranks(n)[1]]
print(f"\n  over every chart size 20..2000: they differ for {len(diff)} of 1981 "
      f"({100*len(diff)/1981:.0f} %), and never by more than one rank.")

print("\n== 2. On real measurements on this machine ==")
CAP = []
_orig = MR._stats
def _spy(vals):
    if vals:
        CAP.append(list(vals))
    return _orig(vals)
MR._stats = _spy

rows = []
for p in sorted(Path.home().joinpath("ChromIQ").rglob("*.ti3")):
    CAP.clear()
    try:
        MR.build_report(p)
    except Exception:                                          # noqa: BLE001
        continue
    if not CAP:
        continue
    a = np.sort(np.asarray(CAP[0], float))
    n = a.size
    if n < 20:
        continue
    k, r = ranks(n)
    rows.append((p, n, float(a[k - 1]), float(a[r - 1]), k != r))
MR._stats = _orig

d = [x for x in rows if x[4]]
print(f"  {len(rows)} measurements read;  {len(d)} of them have a patch count "
      f"where the two estimators pick different patches.")
print(f"\n{'project / file':<52}{'n':>6}{'ChromIQ':>10}{'nearest':>10}{'diff':>9}")
for p, n, c, nr, _ in d[:16]:
    lbl = f"{p.parents[2].name}/{p.name}"
    print(f"{lbl:<52}{n:6d}{c:10.3f}{nr:10.3f}{nr-c:9.3f}")
if d:
    gaps = [nr - c for _, _, c, nr, _ in d]
    print(f"\n  gap between the two answers: min {min(gaps):.3f}  "
          f"median {float(np.median(gaps)):.3f}  max {max(gaps):.3f} dE00")
    # how many would flip a verdict at ChromIQ's shipped 3.0 maximum?
    flip = [(p, n, c, nr) for p, n, c, nr, _ in d if (c <= 3.0) != (nr <= 3.0)]
    print(f"  measurements where the choice flips pass/fail at a 3,0 limit: {len(flip)}")
    for p, n, c, nr in flip:
        print(f"      {p.parents[2].name}/{p.name}  n={n}  {c:.3f} vs {nr:.3f}")
    for lim in (2.0, 2.5, 5.0):
        f2 = sum(1 for _, _, c, nr, _ in d if (c <= lim) != (nr <= lim))
        print(f"  ... at a {lim:.1f} limit: {f2}")

    # --- 3. Can a flip happen AT ALL on this corpus? -------------------------
    # A flip needs a limit strictly between the two answers.  So measure how
    # close any measurement here comes to any of the four limits.
    LIMS = (2.0, 2.5, 3.0, 5.0)
    dist = min(abs(c - lim) for _, _, c, _, _ in rows for lim in LIMS)
    inside = sum(1 for _, _, c, nr, _ in d
                 if any(min(c, nr) < lim < max(c, nr) for lim in LIMS))
    print(f"\n  nearest any of the {len(rows)} measurements comes to a limit of "
          f"2,0 / 2,5 / 3,0 / 5,0: {dist:.3f} dE00")
    print(f"  measurements sitting between the two answers at any limit: {inside}")

    # And prove the flip counter is not simply dead: put a limit inside each gap.
    fired = sum(1 for _, _, c, nr, _ in d
                if (c <= (c + nr) / 2.0) != (nr <= (c + nr) / 2.0))
    print(f"  control: with a limit placed inside each observed gap, "
          f"flips detected: {fired} of {len(d)}")
