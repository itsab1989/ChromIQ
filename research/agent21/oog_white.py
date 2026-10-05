"""Agent 21 / F-15 check: pale sRGB content (every channel 200..255, 1,728 colours, the probe of
Agent 23's pale_srgb.py re-implemented without its module) through B2A1 (Argyll, relative
colorimetric), printed on the truth: L* drop vs the source (share > 5, p99, max)."""
import sys, numpy as np
sys.path.insert(0, 'tree')
from benchmarks.research import cmm
from benchmarks.research.printers import build_printers

def srgb_to_lab_d50(rgb):
    c = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4360747, 0.3850649, 0.1430804], [0.2225045, 0.7168786, 0.0606169],
                  [0.0139322, 0.0971045, 0.7141733]])          # sRGB -> XYZ D50 (Bradford)
    xyz = c @ m.T
    w = np.array([0.96422, 1.0, 0.82521])
    t = xyz / w
    f = np.where(t > 216 / 24389, np.cbrt(t), (24389 / 27 * t + 16) / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], 1)

v = np.arange(200, 256, 5) / 255
rgb = np.stack(np.meshgrid(v, v, v, indexing="ij"), -1).reshape(-1, 3)
src = srgb_to_lab_d50(rgb)
for f in sys.argv[1:]:
    icc, pid = f.rsplit(":", 1)
    p = build_printers()[pid]
    d = np.clip(cmm.b2a(icc, src, "argyll"), 0, 1)
    pr = p.lab_rel(d)
    dL = src[:, 0] - pr[:, 0]
    print(f"{icc.split('/')[-1][:44]:44s} dL>5 {np.mean(dL > 5):.3f} p99 {np.percentile(dL, 99):5.1f} max {dL.max():5.1f}")
