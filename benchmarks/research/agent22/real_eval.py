"""Agent 22: the real misread (Basti's ColorMunki chart, strip D misread).

Builds Maximum accuracy profiles (base tree = research-integration-2, cand tree
= a22-strip) from: a GOOD read (121205), the BAD read (120701, strip D wrong),
and the mean of the 8 other good reads as the reference. Copies of the .ti3
files live in this folder (Basti's originals are only read).
Scores every profile against the reference profile built from the averaged
good reads: A2B on the chart's own device values and on a 9^3 RGB grid, and
the neutral B2A ramp printed through the reference A2B (chroma, dE00).
python real_eval.py   (any cwd)"""
import glob, json, os, re, shutil, subprocess, sys
from pathlib import Path
import numpy as np

H = Path(__file__).parent
SRC = "/Users/Basti/ChromIQ/printer-test/runs/run1/old"
PY = "/Users/Basti/develop/ChromIQ/.venv/bin/python"
TREES = {"base": H.parent / "base", "cand": H.parent / "cand"}
sys.path.insert(0, str(TREES["base"]))
from benchmarks.research import cmm, colour  # noqa: E402

# corrected 2026-10-05 (section 7): strip D is RIGHT in these three, WRONG in the eight others
GOOD = ["2026-08-08_120701", "2026-08-08_133622"]
BAD = ["2026-08-08_121205", "2026-08-08_125349", "2026-08-08_132320"]
W = H / "work2"; W.mkdir(exist_ok=True)


def copy(name):
    dst = W / f"{name}.ti3"
    if not dst.exists():
        shutil.copy(f"{SRC}/{name}/printer-test.ti3", dst)
    return dst


def mean_ti3():
    """Mean XYZ (and spectra) of the good reads, same rows, same header."""
    dst = W / "good-mean.ti3"
    texts = [copy(g).read_text().splitlines() for g in GOOD]
    t0 = texts[0]
    b, e = t0.index("BEGIN_DATA"), t0.index("END_DATA")
    fields = next(l for l in t0 if l.startswith("SAMPLE_ID")).split()
    rows = [[l.split() for l in t[b + 1:e] if l.strip()] for t in texts]
    num = [i for i, f in enumerate(fields) if f.startswith(("XYZ_", "SPEC_"))]
    out = t0[:b + 1]
    for r in range(len(rows[0])):
        base = list(rows[0][r])
        for i in num:
            base[i] = f"{np.mean([float(x[r][i]) for x in rows]):.6f}"
        out.append(" ".join(base))
    out += t0[e:]
    dst.write_text("\n".join(out) + "\n")
    return dst


def build(ti3, tree, cand, out):
    if out.exists():
        return
    job = {"tree": str(tree), "engine": "accurate", "ti3": str(ti3), "out": str(out),
           "quality": "m", "icc_version": "2", "argyll_bin": "/Applications/Argyll/bin",
           "source_gamut": None, "timestamp": "2026-01-01T00:00:00"}
    if cand:
        job["candidates"] = cand
    env = dict(os.environ, PYTHONHASHSEED="0")
    r = subprocess.run([PY, str(TREES["base"] / "benchmarks/research/build_worker.py"),
                        json.dumps(job)], capture_output=True, text=True, env=env)
    line = [l for l in r.stdout.splitlines() if l.startswith("RESULT ")]
    res = json.loads(line[-1][7:]) if line else {"ok": False, "err": r.stderr[-800:]}
    (out.with_suffix(".json")).write_text(json.dumps(res, indent=1))
    if not res.get("ok"):
        raise SystemExit(f"build failed {out}: {res}")


ref_ti3 = mean_ti3()
P = H / "profiles2"; P.mkdir(exist_ok=True)
build(ref_ti3, TREES["base"], "", P / "ref-good-mean.icc")
arms = {}
for name in ["2026-08-08_120701"] + BAD:
    for arm, cand in (("base", ""), ("cand", "a22-strip")):
        out = P / f"{name}-{arm}.icc"
        build(copy(name), TREES[arm], cand, out)
        arms[f"{name}-{arm}"] = out

dev_chart = None
t = ref_ti3.read_text().splitlines()
b, e = t.index("BEGIN_DATA"), t.index("END_DATA")
f = next(l for l in t if l.startswith("SAMPLE_ID")).split()
ix = [f.index(k) for k in ("RGB_R", "RGB_G", "RGB_B")]
dev_chart = np.array([[float(l.split()[i]) / 100 for i in ix] for l in t[b + 1:e] if l.strip()])
g = np.linspace(0, 1, 9)
grid = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
ref = P / "ref-good-mean.icc"
ls = np.arange(5.0, 100.0, 0.5)
target = np.stack([ls, 0 * ls, 0 * ls], 1)
report = {}
for reader in ("argyll", "lcms"):
    rc = cmm.a2b(ref, dev_chart, reader)
    rg = cmm.a2b(ref, grid, reader)
    for k, p in arms.items():
        ec = colour.de2000(cmm.a2b(p, dev_chart, reader), rc)
        eg = colour.de2000(cmm.a2b(p, grid, reader), rg)
        dev = cmm.b2a(p, target, reader)
        printed = cmm.a2b(ref, dev, reader)
        chroma = np.hypot(printed[:, 1], printed[:, 2])
        hi = ls >= 70
        dl = np.diff(printed[:, 0])
        report[f"{k}/{reader}"] = {
            "a2b_chart_med": round(float(np.median(ec)), 3), "a2b_chart_max": round(float(ec.max()), 2),
            "a2b_grid_med": round(float(np.median(eg)), 3), "a2b_grid_p95": round(float(np.percentile(eg, 95)), 3),
            "grey_chroma_max": round(float(chroma.max()), 2),
            "grey_hi_chroma_max": round(float(chroma[hi].max()), 2),
            "grey_de_mean": round(float(colour.de2000(printed, target).mean()), 3),
            "grey_L_reversals": int((dl < -0.05).sum())}
for k, v in report.items():
    print(k, v)
logs = {k: json.loads(p.with_suffix(".json").read_text()).get("log_tail", []) for k, p in arms.items()}
for k, v in logs.items():
    print(k, [l for l in v if "Strip" in l or "strip" in l])
(H / "real_eval2.json").write_text(json.dumps(report, indent=1))
