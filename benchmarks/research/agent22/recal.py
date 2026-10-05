"""Agent 22: Agent 6's re-read calibration with the corrected strip-D labels (read-only, no builds).
Same pair rules as Experiments/agent6/v2/calibrate_v2.py; adds: which reads carry the wrong strip D
(judged against the chart's expected colours and the other strips), and the targets with strip D
removed from every pair."""
import glob, itertools, json, re, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parents[1] / "tree"))
from benchmarks.research import colour
W = np.array([96.42, 100.0, 82.49]); lab = lambda x: colour.xyz_to_lab(x, W)
def read(p):
    t = Path(p).read_text(errors="replace").splitlines()
    f = next(l for l in t if l.startswith("SAMPLE_ID")).split()
    b = t.index("BEGIN_DATA"); e = t.index("END_DATA")
    rows = [l.split() for l in t[b + 1:e] if l.strip()]
    ix = [f.index(k) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
    loc = [r[f.index("SAMPLE_LOC")].strip('"') for r in rows] if "SAMPLE_LOC" in f else None
    return np.array([[float(r[i]) for i in ix] for r in rows]), loc
exp, LOC = read("/Users/Basti/ChromIQ/printer-test/runs/run1/printer-test.ti2")
D = np.array([l.startswith("D") for l in LOC])
MAY = ["/Users/Basti/ChromIQ/printer test/printer test_read1.ti3", "/Users/Basti/ChromIQ/printer test/printer test_read2.ti3"]
AUG = sorted(f for f in glob.glob("/Users/Basti/ChromIQ/printer-test/runs/run1/old/2026-08-08_1*/printer-test.ti3") if "114739" not in f)
R = {f: read(f)[0] for f in MAY + AUG}
out = {"reads": {}}
for f, x in R.items():
    eD = float(np.median(colour.de2000(lab(x[D]), lab(exp[D]))))
    eO = float(np.median(colour.de2000(lab(x[~D]), lab(exp[~D]))))
    out["reads"][f.split("/")[-2] if "old" in f else Path(f).stem] = {"D_to_expected": round(eD, 1), "others_to_expected": round(eO, 1), "D_wrong": eD > 2 * eO}
wrong = {f for f in R if (colour.de2000(lab(R[f][D]), lab(exp[D]))).mean() > 2 * colour.de2000(lab(R[f][~D]), lab(exp[~D])).mean()}
def pair(a, b, mask=None):
    copied = np.abs(R[a] - R[b]).max(1) < 1e-9
    keep = ~copied if mask is None else (~copied & mask)
    e = colour.de2000(lab(R[a]), lab(R[b]))[keep]
    ok = e <= 5.0
    if ok.sum() < 30: return None
    return float(np.median(e[ok])), float(np.percentile(e[ok], 95)), int((~ok).sum())
res = {}
for label, mask in (("agent6 rule (gross > 5 dE00 dropped per pair)", None), ("strip D removed from every pair", ~D)):
    within = []
    for fs in (MAY, AUG):
        within += [r for r in (pair(a, b, mask) for a, b in itertools.combinations(fs, 2)) if r]
    M = np.array([r[0] for r in within]); P = np.array([r[1] for r in within])
    res[label] = {"pairs": len(within), "typical": [round(float(np.median(M)), 4), round(float(np.median(P)), 4)],
                  "pessimistic": [round(float(np.percentile(M, 90)), 4), round(float(np.percentile(P, 90)), 4)]}
out["targets"] = res
# pairs inside the wrong majority: does strip D (wrong in both) look like ordinary noise?
inside = [f for f in AUG if f in wrong]
dD = [float(np.median(colour.de2000(lab(R[a][D]), lab(R[b][D])))) for a, b in itertools.combinations(inside, 2)]
out["strip_D_between_two_wrong_reads_median_dE00"] = [round(min(dD), 3), round(float(np.median(dD)), 3), round(max(dD), 3)]
nreads = len(MAY) + len(AUG) + 1      # + 114739 (excluded by agent 6 as a copy of the May result)
nwrong = len(wrong) + 0
out["strip_misread"] = {"reads_counted": len(R), "reads_with_wrong_D": sorted(Path(f).parent.name if "old" in f else Path(f).stem for f in wrong),
                        "per_strip_rate_corrected": len(wrong) / (len(R) * 6),
                        "per_strip_rate_agent6": 2 / 72,
                        "distinct_misread_events": 1}
print(json.dumps(out, indent=1))
Path(__file__).with_name("recal.json").write_text(json.dumps(out, indent=1))
