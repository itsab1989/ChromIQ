"""Score one profile: ncq headline (Agent 14/18 referee), Agent 18's own-separation (P7/P8),
the pale-colour test (s3.1) and the jump diagnosis. Writes PROFILE.score.json.
    python score.py PROFILE.icc PRINTER"""
import json, subprocess, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / "tree"), str(HERE.parent / "agent18" / "scripts")]
PY = sys.executable
icc, pid = str(Path(sys.argv[1]).resolve()), sys.argv[2]
out = {}
nq = Path(icc + ".ncq.json")
if not nq.exists():
    subprocess.run([PY, "-m", "benchmarks.research.ncq", icc, pid, "--out", str(nq)], cwd=str(HERE / "tree"),
                   capture_output=True, text=True, timeout=3 * 3600)
from benchmarks.research.ncq import headline
r = json.loads(nq.read_text())
out["ncq"] = headline(r)
out["ncq"]["NC1 solid B2A max"] = max(v["solid_b2a_de"] for v in r["NC1"]["per_ink"].values())
from study import own_separation
out["own"] = own_separation(icc, pid)
# pale colours
from benchmarks.research import cmm, colour, gmq
from benchmarks.research.printers import build_printers
p = build_printers()[pid]
cl = gmq.truth_cloud(p); rng = np.random.default_rng(7)
pale = cl[cl[:, 0] > 90]; pale = pale[rng.choice(len(pale), min(3000, len(pale)), replace=False)]
d = np.zeros((1500, p.n))
for i in range(1500):
    k = rng.choice(p.n, rng.integers(1, 3), replace=False); d[i, k] = rng.uniform(0.005, 0.06, len(k))
tg = np.vstack([pale, p.lab_rel(d)])
dev = np.clip(cmm.b2a(icc, tg, "argyll"), 0, 1); de = colour.de2000(p.lab_rel(dev), tg)
out["pale"] = {"n": int(len(tg)), "med": float(np.median(de)), "p95": float(np.percentile(de, 95)),
               "max": float(de.max()), "share_gt2": float((de > 2).mean())}
from benchmarks.research import metrics
gam = gmq.TruthGamut(cl)
na = metrics.neutral_axis(icc, "argyll", metrics.Truth(printer=p), gam.black_l, p.n, False)
out["neutral"] = {"de_med": na["de"]["median"], "de_p95": na["de"]["p95"], "chroma_max": na["chroma_max"],
                  "L_reversals": na["L_reversals"], "tv_excess": na["separation"]["tv_excess"],
                  "banding_max_d2": na["banding_max_d2"], "hl_de_med": na["highlight"]["de"]["median"],
                  "black_L": float(p.lab_rel(np.clip(cmm.b2a(icc, np.array([[0.0, 0, 0]]), "argyll"), 0, 1))[0, 0])}
jd = subprocess.run([PY, str(HERE / "jumpdiag.py"), icc, pid], capture_output=True, text=True)
try:
    out["jumps"] = json.loads(jd.stdout)
except Exception:
    out["jumps"] = {"error": jd.stderr[-300:]}
Path(icc + ".score.json").write_text(json.dumps(out, indent=1))
h = out["ncq"]
print(json.dumps({"icc": Path(icc).name, "pale": out["pale"], "own": {k: out["own"][k] for k in ("printed_med", "printed_p95")},
                  "jumps": out["jumps"].get("visible_jumps"), **{k: h[k] for k in list(h)[:40]}}))
