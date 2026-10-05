"""Confirm F-15/F-16 examples through ColorSync (sRGB -> printer, Quartz)."""
import sys, numpy as np
from benchmarks.research.blindspots import xf
from benchmarks.research.printers import build_printers
name = sys.argv[1]
p = build_printers()[name]
t = np.linspace(0, 1, 256)[:, None]
red = 1 - t * (1 - np.array([1, 0, 0.]))
mag = 1 - t * (1 - np.array([1, 0, 1.]))
pale = np.array([[205, 255, 255], [200, 255, 200], [255, 230, 240]]) / 255
for e in ("colprof", "fast", "accurate"):
    icc = f"../out/profiles/{name}-{e}.icc"
    out = []
    for nm, rgb, it in (("red-p", red, "p"), ("mag-r", mag, "r")):
        d = np.clip(xf.colorsync("srgb", icc, rgb, it), 0, 1)
        L = p.lab_rel(d)[:, 0]
        sgn = -1
        run = np.minimum.accumulate(L)
        out.append(f"{nm} swing {(L - run).max():.2f}")
    d = np.clip(xf.colorsync("srgb", icc, pale, "r"), 0, 1)
    src = xf.srgb_to_lab(pale)
    out.append("pale dL " + " ".join(f"{v:.1f}" for v in src[:, 0] - p.lab_rel(d)[:, 0]))
    print(name, e, " | ".join(out))
