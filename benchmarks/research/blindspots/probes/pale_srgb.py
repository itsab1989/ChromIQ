"""Pale sRGB content (every channel 200..255) through each builder: printed L* drop."""
import sys, numpy as np
from pathlib import Path
from benchmarks.research.blindspots import xf
from benchmarks.research import colour
from benchmarks.research.printers import build_printers
name, pid = sys.argv[1], sys.argv[2]
engines = sys.argv[3].split(",") if len(sys.argv) > 3 else ["colprof", "fast", "accurate"]
p = build_printers()[pid]
v = np.arange(200, 256, 5) / 255
rgb = np.stack(np.meshgrid(v, v, v, indexing="ij"), -1).reshape(-1, 3)
src = xf.srgb_to_lab(rgb)
for e in engines:
    icc = Path(f"../out/profiles/{name}-{e}.icc")
    if not icc.exists():
        continue
    for it, bpc in (("r", False), ("r", True), ("p", False), ("s", False)):
        d = np.clip(xf.lcms("srgb", str(icc), rgb, it, bpc=bpc), 0, 1)
        pr = p.lab_rel(d)
        dL = src[:, 0] - pr[:, 0]
        de = colour.de2000(pr, src)
        k = np.argmax(dL)
        print(f"{name} {e:9s} {it}{'+bpc' if bpc else '    '} dL>5: {np.mean(dL > 5):.3f}  dL p99 {np.percentile(dL, 99):5.1f} max {dL.max():5.1f} at sRGB {np.round(rgb[k]*255).astype(int).tolist()} src L {src[k,0]:.1f} -> {pr[k,0]:.1f}  dE00 p95 {np.percentile(de,95):.2f}")
