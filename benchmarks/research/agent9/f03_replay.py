"""Replay captured helper calls: shipped bp vs neutral bp. usage: f03_replay.py CAPDIR"""
import sys, subprocess, tempfile, json
from pathlib import Path
import numpy as np
d = Path(sys.argv[1]); exe = "/Users/Basti/develop/ChromIQ/native/chromiq-gammap"
nbp = np.load(d / "neutral_bp_jab.npy")
out = {}
for f in sorted(d.glob("call*.npz")):
    z = np.load(f)
    cl = z["cloud"]; c = np.hypot(cl[:, 1], cl[:, 2]); near = c < max(3.0, float(np.percentile(c, 1)))
    shell_bp = cl[near][np.argmin(cl[near][:, 0])]
    for tag, bp in (("shipped_bp", z["bp"]), ("neutral_bp", nbp), ("shell_bp", shell_bp)):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); np.savetxt(td/"q.txt", z["query"], fmt="%.9f")
            np.savetxt(td/"c.txt", z["cloud"], fmt="%.9f")
            args = [exe, "--src", str(d/"src.gam"), "--intent", str(z["intent"]), "--mapres", str(int(z["mapres"])),
                    "--query", str(td/"q.txt"), "--out", str(td/"o.txt"), "--dst-cloud", str(td/"c.txt"),
                    "--wp", *[f"{v:.9f}" for v in z["wp"]], "--bp", *[f"{v:.9f}" for v in bp]]
            r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=1200)
            key = f"{f.stem}-{z['intent']}-{tag}"
            out[key] = {"rc": r.returncode, "msg": r.stderr.strip()[-120:], "bp": [round(float(v), 2) for v in bp]}
            if r.returncode == 0 and tag == "shipped_bp":
                np.savetxt(d / f"{f.stem}-shipped.out", np.loadtxt(td/"o.txt"))
            print(key, out[key], flush=True)
(d / "replay.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
