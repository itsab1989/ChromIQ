#!/usr/bin/env python3
"""Does a chart file still hold its own numbers after macOS has drawn it? (#133)

A chart is not a picture. The values in it are the exact ink amounts to lay
down, so anything that converts them on the way to the paper prints different
colours — and the measurement then faithfully describes those different
colours, with nothing anywhere able to tell that it happened.

ChromIQ's own pipeline sidesteps the question by printing raw. The question is
what happens when someone prints one of the exported files themselves, which is
a reasonable thing to want on macOS, where colour management at print time is
exactly what people have learned not to trust.

This probe answers it by measurement rather than argument: it builds a chart of
deliberately awkward colours through the real layout engine, writes both the
TIFF and the vector PDF, has macOS rasterise each one through Quartz (``sips``,
the same ImageIO path Preview and friends draw with), and compares the pixels
that come back with the values the engine put in.

    python scripts/pdf_colour_passthrough_probe.py [outdir]

Findings on macOS 15 (2026-08-02), reproduced here every run:

* **TIFF — untouched.** Quartz assigns sRGB and passes every value through
  unchanged.
* **PDF — converted.** The chart PDF is untagged DeviceRGB, with no
  ``/OutputIntents`` and no ``/ICCBased``, and Quartz renders DeviceRGB *into
  the destination space* rather than through it. Against the machine's display
  profile, pure red 255,0,0 comes back as 234,51,35.
* **It depends on the destination**, so it varies by machine and application:
  rendered to sRGB the same red survives and the damage is small.

The conclusion is not that the PDF is wrong — it is a correct device-colour PDF,
and a RIP with colour management off honours it. It is that the PDF must go to a
RIP, and the TIFF is the file for anything else.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

#: Saturated primaries and secondaries, a mid grey and two off-axis colours —
#: the places an RGB→RGB conversion moves values most, and one (grey) where it
#: characteristically does not, which keeps a null result honest.
PROBE_COLOURS = [
    (0., 0., 0.), (100., 0., 0.), (0., 100., 0.), (0., 0., 100.),
    (100., 100., 0.), (0., 100., 100.), (100., 0., 100.),
    (50., 50., 50.), (80., 20., 20.), (20., 80., 20.), (100., 100., 100.),
]


def build(out: Path):
    from PIL import Image
    from workflow.layout_engine import (geometry, instruments, papers, raster,
                                        vector_pdf)
    from workflow.layout_engine.ti1_reader import ColorTarget

    target = ColorTarget(
        color_rep="iRGB", device_fields=["RGB_R", "RGB_G", "RGB_B"],
        patches=[(c, (40., 45., 50.)) for c in PROBE_COLOURS * 30])
    geom = instruments.build("i1")
    w, h = papers.dimensions_mm("A4")
    lay = geometry.compute(geom, w, h, len(target.patches))
    res = raster.render_pages(target, lay, geom, seed=3, randomize=False,
                              paper_w_mm=w, paper_h_mm=h, dpi=150,
                              collect_device_geom=True)
    pdf = vector_pdf.save_vector_pdf(res, target, out / "chart.pdf",
                                     paper_w_mm=w, paper_h_mm=h, dpi=150)
    Image.fromarray(_arr(res.images[0])).save(out / "engine.tif")
    return pdf, res.images[0].size[0]


def _arr(img):
    import numpy as np
    return np.asarray(img)


def _top_colours(path: Path, k: int = 8):
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(path).convert("RGB")).reshape(-1, 3)
    u, c = np.unique(a, axis=0, return_counts=True)
    return [tuple(int(x) for x in v) for v in u[np.argsort(-c)][:k]], len(u)


def _sips(args: list[str]) -> None:
    subprocess.run(["sips", *args], check=True, capture_output=True)


def main(out: Path) -> int:
    import numpy as np
    from PIL import Image

    out.mkdir(parents=True, exist_ok=True)
    pdf, width = build(out)

    raw = pdf.read_bytes()
    print(f"chart.pdf: {len(raw)} bytes")
    print(f"  /OutputIntents present: {b'/OutputIntents' in raw}")
    print(f"  /ICCBased present:      {b'/ICCBased' in raw}")
    print("  → untagged device colour, which is correct for a chart and is "
          "also what leaves the decision to whatever opens it.\n")

    srgb = "/System/Library/ColorSync/Profiles/sRGB Profile.icc"
    _sips(["-s", "format", "tiff", "--resampleWidth", str(width),
           str(pdf), "--out", str(out / "pdf_display.tif")])
    _sips(["-s", "format", "tiff", "--resampleWidth", str(width),
           "--matchTo", srgb, str(pdf), "--out", str(out / "pdf_srgb.tif")])
    _sips(["-s", "format", "png", str(out / "engine.tif"),
           "--out", str(out / "tiff_quartz.png")])

    truth = np.asarray(Image.open(out / "engine.tif").convert("RGB")).astype(int)
    same = np.asarray(Image.open(out / "tiff_quartz.png")
                      .convert("RGB")).astype(int)
    print(f"TIFF through Quartz: unchanged = {np.array_equal(truth, same)}, "
          f"largest channel difference = {int(np.abs(truth - same).max())}")

    for label, name in (("engine (what was asked for)", "engine.tif"),
                        ("PDF → display profile     ", "pdf_display.tif"),
                        ("PDF → sRGB                ", "pdf_srgb.tif")):
        cols, n = _top_colours(out / name)
        print(f"\n{label}  ({n} distinct colours)")
        print("   " + "  ".join(f"{c}" for c in cols))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]) if len(sys.argv) > 1
                          else Path("pdf-probe")))
