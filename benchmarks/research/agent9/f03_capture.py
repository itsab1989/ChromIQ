"""F-03: capture the helper's inputs inside a real Bit-exact build, then
replay the helper with the shipped black and with the neutral black.

usage: f03_capture.py TREE TI3 OUT_DIR [mode=argyll] [ink_limit]
"""
import json, sys, subprocess, os
from pathlib import Path
import numpy as np
tree, ti3, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
mode = sys.argv[4] if len(sys.argv) > 4 else "argyll"
limit = float(sys.argv[5]) if len(sys.argv) > 5 else None
sys.path.insert(0, str(tree)); os.chdir(tree)
out.mkdir(parents=True, exist_ok=True)
import workflow.profile_engine.gammap_port.wire as wire
import workflow.profile_engine.gammap_helper as gh
from workflow.profile_engine import b2a as b2a_mod
from workflow.profile_engine.builder import BuildSettings, build_profile
cap = {}
orig_fit = wire.fit_gammap_argyll_mappers
def fit(model, meas, *a, **k):
    cap["model"] = model; cap["meas"] = meas; cap["ink_limit"] = k.get("ink_limit")
    return orig_fit(model, meas, *a, **k)
wire.fit_gammap_argyll_mappers = fit
orig_run = gh.run_gammap
def run(q, **k):
    i = len([p for p in out.glob("call*.npz")])
    np.savez(out / f"call{i}.npz", query=q, cloud=k["dst_cloud_jab"],
             wp=k["wp_jab"], bp=k["bp_jab"], intent=k["intent"], mapres=k["mapres"],
             src_gam=str(k["src_gam"]))
    import shutil; shutil.copy(k["src_gam"], out / "src.gam")
    try:
        return orig_run(q, **k)
    except Exception as e:
        (out / f"call{i}.err").write_text(str(e), encoding="utf-8")
        raise
wire.run_gammap = run
s = BuildSettings(quality="m", gammap_mode=mode, ink_limit=limit,
                  argyll_bin="/Applications/Argyll/bin",
                  source_gamut=str(tree / "assets/profiles/ClayRGB1998.icm"))
res = {}
try:
    build_profile(ti3, out / "build.icc", s); res["build"] = "ok"
except Exception as e:
    res["build"] = f"{type(e).__name__}: {str(e)[:200]}"
m = cap["model"]; meas = cap["meas"]
ax = b2a_mod.neutral_axis(m, channel_letters=meas.channel_letters, is_additive=False,
                          ink_limit=cap["ink_limit"], accurate=True,
                          black_l=float(meas.lab_relative[meas.black_index, 0]))
nb_lab = m.predict(ax["black"][None, :])[0]
full_lab = m.predict(np.ones((1, m.n_channels)))[0]
ap = wire.Appearance(wire.lab_to_xyz(m.predict(np.zeros((1, m.n_channels))))[0])
res.update(neutral_black_lab=nb_lab.tolist(), full_ink_lab=full_lab.tolist(),
           neutral_black_dev=ax["black"].tolist(), neutral_black_jab=ap.lab_to_jab(nb_lab[None])[0].tolist())
np.save(out / "neutral_bp_jab.npy", ap.lab_to_jab(nb_lab[None])[0])
(out / "capture.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps(res))
