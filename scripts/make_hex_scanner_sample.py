#!/usr/bin/env python3
"""Build the "try the hexagonal scanner path yourself" sample pack.

A hexagonal chart is a SpectroScan-style honeycomb, and until now the scanner
and camera tools refused one. They no longer have to — but almost nobody has a
honeycomb chart lying about to check that with, so this makes one, together with
a simulated scan of it, so the whole path can be walked with no printer and no
scanner at all.

    python scripts/make_hex_scanner_sample.py [out_dir]

Produces `ChromIQ-hex-scanner-sample.zip`:

    chart/HexChart.*        a real 12 mm honeycomb, ready to print
    chart/SquareChart.*     the SAME 150 colours in square patches, to compare
    scan/*-simulated-scan.tif   what a 300 dpi scan of each would look like
    README.md               what to do with them

The simulated scans are rendered from the charts' own recorded geometry and then
put through a small rotation, a soft blur and a little noise, because a scan
that is pixel-perfect proves nothing about a path whose whole job is coping with
one that is not. They are honest about being simulations: no ink, no paper, no
scanner — good enough to exercise the software, not to judge a profile.
"""
from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PATCHES = 150
PATCH_MM = 12.0
CHART_DPI = 200
SCAN_DPI = 300


def _ti1(path: Path, n: int) -> Path:
    """A spread over the RGB cube, deterministic so the pack rebuilds byte-alike."""
    rows, step = [], max(1, round(n ** (1 / 3)))
    for i in range(n):
        r = (i % step) * 100.0 / (step - 1)
        g = ((i // step) % step) * 100.0 / (step - 1)
        b = ((i // (step * step)) % step) * 100.0 / (step - 1)
        rows.append((r, g, b))
    lines = ["CTI1", "", 'DESCRIPTOR "ChromIQ hexagonal scanner sample"',
             'ORIGINATOR "ChromIQ"', 'KEYWORD "SAMPLE_LOC"',
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i, (r, g, b) in enumerate(rows):
        # Rough sRGB-ish aim values: the pack is about geometry, and a printer
        # profile built from it is replaced by the user's own measurement.
        x = 0.4124 * r + 0.3576 * g + 0.1805 * b
        y = 0.2126 * r + 0.7152 * g + 0.0722 * b
        z = 0.0193 * r + 0.1192 * g + 0.9505 * b
        lines.append(f"{i+1} {r:.4f} {g:.4f} {b:.4f} {x:.4f} {y:.4f} {z:.4f}")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines))
    return path


def build(work: Path, name: str, hexagonal: bool) -> Path:
    """A chart built by the real engine, with the real sidecar the app writes —
    including the FULL LayoutRecipe, so the chart also loads back into Create
    Chart instead of being a dead end."""
    from workflow.layout_engine import chart as le_chart
    from workflow.layout_engine.presets import LayoutRecipe
    folder = work / name
    folder.mkdir(parents=True, exist_ok=True)
    ti1 = _ti1(folder / f"{name}.ti1", PATCHES)
    stem = folder / name
    kwargs = dict(instrument="SS", paper="A4", hflag=hexagonal,
                  pscale=PATCH_MM / 7.0, border=6.0, dpi=CHART_DPI,
                  randomize=False, seed=1)
    res = le_chart.build_chart(ti1, stem, **kwargs)
    layout = json.loads(stem.with_suffix(".strips.json").read_text())
    layout.update({"engine": "chromiq", "engine_version": 1, "dpi": CHART_DPI,
                   "seed": res.seed, "color_rep": res.color_rep,
                   "recipe": LayoutRecipe.from_build_kwargs(kwargs).to_dict()})
    # The sidecar's shape matters: the geometry lives UNDER "layout", which is
    # where `scanin_target` looks. Written flat, the tools reject the chart as
    # "not an engine chart" — which is what the first build of this pack did.
    (folder / f"{name}.channels.json").write_text(json.dumps(
        {"ink_channels": ["r", "g", "b"], "layout": layout}))
    stem.with_suffix(".strips.json").unlink()
    print(f"  {name}: {res.layout.total_patches} patches, "
          f"{res.layout.passes} x {res.layout.steps_in_pass}")
    return stem


def simulate_scan(stem: Path, out: Path) -> Path:
    """What a scanner would hand back: the printed sheet, at scan resolution,
    rotated a little, softened and speckled. Rotation and noise are FIXED, not
    random — a sample pack that differs every time it is built cannot be
    compared against by whoever receives it."""
    from PIL import Image, ImageFilter
    import numpy as np
    src = Image.open(stem.with_suffix(".tif")).convert("RGB")
    w = int(src.width * SCAN_DPI / CHART_DPI)
    img = src.resize((w, int(src.height * SCAN_DPI / CHART_DPI)),
                     Image.Resampling.LANCZOS)
    img = img.rotate(-0.8, resample=Image.Resampling.BICUBIC,
                     expand=True, fillcolor=(252, 251, 249))
    img = img.filter(ImageFilter.GaussianBlur(0.6))       # scanner optics
    a = np.asarray(img).astype(np.int16)
    rng = np.random.default_rng(20260822)                 # fixed: reproducible
    a = np.clip(a + rng.normal(0, 1.6, a.shape).astype(np.int16), 0, 255)
    Image.fromarray(a.astype("uint8")).save(out, dpi=(SCAN_DPI, SCAN_DPI),
                                            compression="tiff_lzw")
    print(f"  {out.name}: {a.shape[1]} x {a.shape[0]} px at {SCAN_DPI} dpi")
    return out


README = """# ChromIQ — hexagonal chart, scanner sample pack

ChromIQ can lay a chart out as a honeycomb instead of a grid of squares (pick
the SpectroScan instrument, then the hexagonal layout). Until this beta the
scanner and camera tools turned such a chart away. They no longer have to, and
this pack is here so you can see it work without printing anything first.

## What is in the box

    chart/HexChart.tif             a 12 mm honeycomb, 150 patches, A4, ready to print
    chart/HexChart.ti1 / .ti2      the patch list and the chart's aim values
    chart/HexChart.channels.json   the exact geometry ChromIQ recorded for it
    chart/SquareChart.*            the SAME 150 colours as square patches
    scan/HexChart-simulated-scan.tif      a stand-in for a 300 dpi scan
    scan/SquareChart-simulated-scan.tif

The simulated scans were rendered from the charts themselves and then rotated
0.8 degrees, softened and speckled, because a pixel-perfect image would prove
nothing about a path whose job is coping with one that is not. They contain no
ink, no paper and no scanner: use them to see the tool work, not to judge a
profile.

## Switch it on first

Preferences -> Beta -> "Allow hexagonal charts in the scanner and camera tools".
Without it the tool will politely refuse the chart and tell you why.

## Try it with no hardware at all

1. Tools -> Build profile with scanner or camera.
2. Measured chart: pick `chart/HexChart.ti2`.
3. Tick "Profile my printer from this scan" (the chart has not been measured
   with an instrument, so this is the path that applies).
4. Scan or photo: pick `scan/HexChart-simulated-scan.tif`.
5. Drag the four corners of the mesh onto the four corners of the patch block.
   The cells are drawn as hexagons, so you can see them sit on the ink.
6. Note "Patch sample area". On this chart it stops at 64 %, not the usual 80:
   the square ChromIQ reads has to stay inside a hexagon, and the next hexagon
   is flush against it, so a square a little too big would read the colour next
   door on every patch at once. ChromIQ works that ceiling out from the shape of
   your own patches. Open `chart/SquareChart.*` the same way and it is 80 again.
7. Build. Then do the same with the square chart and compare.

## Try it for real

Print `chart/HexChart.tif` with colour management switched off, scan it at
300 dpi (or photograph it flat and evenly lit), and use your scan in step 4.

## What is still unproven

Finding a honeycomb chart in a scan WITHOUT your help. ChromIQ asks you to place
the four corners, and with those in hand it no longer runs the search that used
to give up on a honeycomb. Unaided recognition is the reason the switch is still
a beta one.

Faults, or a scan that will not read: please open an issue and attach the scan.
"""


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist"
    out.mkdir(parents=True, exist_ok=True)
    pack = out / "ChromIQ-hex-scanner-sample"
    if pack.exists():
        shutil.rmtree(pack)
    (pack / "chart").mkdir(parents=True)
    (pack / "scan").mkdir(parents=True)

    work = out / "_hexsample_build"
    if work.exists():
        shutil.rmtree(work)
    print("building charts:")
    for name, hexagonal in (("HexChart", True), ("SquareChart", False)):
        stem = build(work, name, hexagonal)
        for suffix in (".tif", ".ti1", ".ti2", ".channels.json"):
            src = stem.with_suffix(suffix)
            if src.is_file():
                shutil.copy(src, pack / "chart" / src.name)
        simulate_scan(stem, pack / "scan" / f"{name}-simulated-scan.tif")
    (pack / "README.md").write_text(README)
    shutil.rmtree(work)

    zpath = out / "ChromIQ-hex-scanner-sample.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(pack.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(pack.parent))
    print(f"\n{zpath}  ({zpath.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
