"""Score a profile built from a REAL 7-ink set (R-FOGRA55) through Agent 14's independent
Argyll MPP proxy fitted to ALL FOGRA55 patches (labelled proxy: B2A dE below about 1 is
proxy-limited). ncq headline + pale test + neutral metrics via the proxy.
    python score_real.py PROFILE.icc"""
import json, subprocess, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / "tree")]
PY = sys.executable
A14 = HERE.parent / "agent14"
icc = str(Path(sys.argv[1]).resolve())
mpp = A14 / "f55mpp" / "full.mpp"
nq = Path(icc + ".ncq.json")
if not nq.exists():
    subprocess.run([PY, "-m", "benchmarks.research.ncq", icc, "R-FOGRA55", "--proxy", f"mpp:{mpp}",
                    "--letters", "CMYKOGV", "--tac", "300", "--out", str(nq)], cwd=str(HERE / "tree"),
                   capture_output=True, text=True, timeout=4 * 3600)
from benchmarks.research.ncq import headline, ProxyPrinter
from benchmarks.research import cmm, colour, gmq, metrics
out = {"ncq": headline(json.loads(nq.read_text()))}
p = ProxyPrinter(f"mpp:{mpp}", list("CMYKOGV"), 300.0)
rng = np.random.default_rng(7)
d = np.zeros((1500, 7))
for i in range(1500):
    k = rng.choice(7, rng.integers(1, 3), replace=False); d[i, k] = rng.uniform(0.005, 0.06, len(k))
tg = p.lab_rel(d)
dev = np.clip(cmm.b2a(icc, tg, "argyll"), 0, 1); de = colour.de2000(p.lab_rel(dev), tg)
out["pale"] = {"n": 1500, "med": float(np.median(de)), "p95": float(np.percentile(de, 95)), "max": float(de.max()),
               "share_gt2": float((de > 2).mean())}
cl = gmq.truth_cloud(p)
gam = gmq.TruthGamut(cl)
na = metrics.neutral_axis(icc, "argyll", metrics.Truth(printer=p), gam.black_l, 7, False)
out["neutral"] = {"de_med": na["de"]["median"], "de_p95": na["de"]["p95"], "chroma_max": na["chroma_max"],
                  "L_reversals": na["L_reversals"], "tv_excess": na["separation"]["tv_excess"],
                  "banding_max_d2": na["banding_max_d2"], "hl_de_med": na["highlight"]["de"]["median"],
                  "black_L": float(p.lab_rel(np.clip(cmm.b2a(icc, np.array([[0.0, 0, 0]]), "argyll"), 0, 1))[0, 0])}
out["own"] = {"printed_med": float("nan"), "printed_p95": float("nan")}
Path(icc + ".score.json").write_text(json.dumps(out, indent=1))
print(json.dumps({"pale": out["pale"], "neutral": out["neutral"]}))
