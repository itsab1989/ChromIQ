#!/usr/bin/env python3
"""Build the ChromIQ-CR30-hex-demo pack: a two-page CR30 honeycomb, scans of
both pages, and REAL measurements read off those scans.

What this pack is for, and why it is shaped like this
-----------------------------------------------------
There have been two of these packs and the second one lost most of the first.

The pack shipped with v4.3.0-beta.3 carried a 648-patch two-page honeycomb
(``testHex``), a measurement of it filed beside the chart, three measurements of
increasing noise for the averaging path, and one scan per page. The pack shipped
on 2026-09-12 replaced it with a single-page 396-patch chart, two scans of that
one page, and no measurement at all. That was a regression, and it was reported
as one:

    *"the latest version of ChromIQ-CR30-hex-demo did not have all files as
    before. It is missing ti3 measurements, so I cannot use it to test the
    creation of CHT files, or use them in the scanner function. Add the files
    that previously was included, with real measurements etc."*

Both halves of that are structural, not cosmetic:

* **Tools, Create scanner or camera target** asks for a chart's ``.ti3`` and
  nothing else will do (:mod:`ui.dialogs.scanin_target_dialog`). With no ``.ti3``
  in the pack the window cannot be driven at all, so no ``.cht`` can be created
  from it.
* A **one-page** chart writes one ``.cht`` and exercises none of the per-page
  naming. Two pages write ``<stem>_01.cht`` and ``<stem>_02.cht`` against a
  single ``.cie``, which is the branch worth testing.

So this pack is the older one's contents, rebuilt, plus what the newer one was
made to show. Nothing that was in either is dropped.

The measurements are MEASURED, and that is the whole difference
---------------------------------------------------------------
The older pack's ``.ti3`` files came from ``fakeread``: the chart's own aim
values pushed through a reference profile. They load and they profile, but they
are a restatement of the chart, so nothing that happens to a printed sheet or to
a scan can ever appear in them.

Every ``.ti3`` here is read off an actual image instead, by an actual
``scanin``:

1. the chart is laid out by ChromIQ's own engine, two pages of it;
2. a printed sheet is simulated from each page (see :func:`_sheet`);
3. the sheet is rendered as a scanner would hand it back, turned, softened and
   speckled;
4. ``scanin -c`` reads that image through a scanner profile and writes what it
   measured, page 1 and then page 2 accumulated onto it with ``-ca``;
5. the chart's ``SAMPLE_LOC`` column is put back (:func:`add_sample_loc`), which
   ``scanin -c`` does not write and the scanner-target window requires.

Step 5 restores a fact about the CHART, never about the measurement, and it is
proved rather than trusted: every row's device values must still equal the
``.ti2``'s for the same ``SAMPLE_ID``, so a join that landed on the wrong patch
cannot pass.

What is still a simulation is the sheet. There is no ink, no paper and no
spectrophotometer here, and the pack says so in its own README. What these files
carry that the old ones could not is everything the imaging does: the turn, the
optics, the speckle, the sample square averaging over a hexagon, and above all
what happens to a patch the scanner has driven off the end of its scale.

The three reads
---------------
Three scans of each page, differing only in how much speckle the scanner added,
give three genuinely different measurements of one sheet. That is what the
averaging path is for, and unlike three ``fakeread`` files the difference
between them is a real difference between three real images.

The two brightness states
-------------------------
Page 1 is also rendered a second time with the scanner's automatic brightness
switched on. It drives the paper past the top of the scale and takes every
patch printed near the top of a channel with it, so the build gate stops and
says so. That scan is in the pack on purpose, so the warning can be watched
happening on one file and not happening on another that is otherwise identical.

Nothing here is claimed, all of it is checked
---------------------------------------------
This generator refuses to write a pack that does not do what its README says:

* the in-range scan must read comfortably under ``scanner_max_clipped`` and the
  out-of-scale one comfortably over it, and neither may trip any OTHER warning;
* the shipped ``.ti3`` must actually drive **Create scanner or camera target**
  to two ``.cht`` files and one ``.cie`` covering every patch;
* the scanner path must then read every patch of both pages back through those
  files;
* the three reads must really rise in noise, each one measured against an
  independent rendering of the same sheet at the same speckle (see
  :func:`read_noise` for why the obvious yardstick does not work).

Any of those failing prints the numbers and exits non-zero, and the half-built
pack is removed rather than shipped.

Run it::

    .venv/bin/python scripts/make_cr30_hex_demo.py [destination]

Default destination: ``dist/ChromIQ-CR30-hex-demo``.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PACK = "ChromIQ-CR30-hex-demo"

#: The chart. Knut's own: 648 patches as a flat-top CR30 honeycomb on A4, which
#: the engine lays out on two pages. The name and the count are kept from the
#: pack he already has, so a note he wrote about `testHex` still describes this
#: file. A CR30 is placed on one patch at a time, so its own patch size is what
#: the honeycomb is built from and there is no strip run-up to pay for; the 5 mm
#: margin is the one `data/patch_db.py` gives the instrument.
STEM = "testHex"
PATCHES = 648
INSTRUMENT = "CR30"
PAPER = "A4"
MARGIN_MM = 5.0
CHART_DPI = 300
SCAN_DPI = 200
#: Two, and the generator refuses anything else: one page writes one `.cht` and
#: leaves the per-page naming untested, which is the gap this pack exists to
#: close.
EXPECT_PAGES = 2

#: Grey and single-channel ramps kept eligible, the same shape
#: `scripts/make_report_limit_demos.py` uses, so the chart is a chart somebody
#: could really build a profile from and not a bag of colours.
TARGEN_GREY = 16
TARGEN_SINGLE = 12

#: The device range a printed sheet really occupies once a scanner has read it.
#: Solid ink is not 0 and paper is not 255: measured across the reads this
#: project keeps, the darkest patch of a matte print lands near 22/255 and the
#: paper near 246/255. Every scan in this pack is a rendering of a sheet that
#: sits here.
SHEET_BLACK = 22
SHEET_WHITE = 246

#: What the scanner's automatic brightness and contrast does to that sheet: it
#: decides the paper is meant to be pure white and stretches the scale until it
#: is. AUTO_WHITE is the device value it lifts to 255, so every patch at or
#: above it comes back on the top rail with nothing left to tell those patches
#: apart. It sits UNDER the paper (246) rather than on it, so the paper is
#: driven past the rail instead of onto it and no amount of scanner noise can
#: let a patch back over the line.
AUTO_WHITE = 240
#: The black point is left alone, which is what makes this a demonstration of
#: one thing. Automatic brightness that lifts the highlights and leaves the
#: shadows is the ordinary case, and a scan that ran out of scale at BOTH ends
#: would have the message counting two faults as one number.
AUTO_BLACK = 0

#: Fixed, never random: a pack that differs every time it is built cannot be
#: compared against by whoever receives it.
ROTATION_DEG = -0.8
BLUR_PX = 0.6

#: The three reads, as (folder name, speckle, seed). The speckle is the only
#: thing that differs, which is what makes the averaging path's job real: the
#: sheet, the turn and the optics are identical in all three, so what averaging
#: has to remove is the only thing that was added.
#:
#: The three levels are far apart because the sampling square averages most of
#: the speckle away before it ever reaches a patch value: measured on this
#: chart, a rendering at 1.6 differs from an independent rendering at 1.6 by
#: 0.024, and one at 8.0 from its twin by 0.090. Levels a stop apart would land
#: inside each other.
READS = (
    ("read1-clean",    1.6, 20260912),
    ("read2-noisy",    6.0, 20260913),
    ("read3-noisier", 18.0, 20260914),
)
#: The first read is the one filed beside the chart, and the one the scans in
#: `scan/` are of.
PRIMARY_READ = READS[0][0]

#: How far past `scanner_max_clipped` each scan must land before this pack is
#: allowed to claim it demonstrates anything. A scan that merely squeaks over
#: the line would turn a later change of one decimal place into a pack that
#: quietly stops demonstrating what it says it does.
CLIP_MARGIN = 0.05

#: How much noisier each read must be than the one before it, as a ratio of
#: measured error against a speckle-free rendering of the same sheet. A pack
#: whose "noisier" file is not noisier gives averaging nothing to do and teaches
#: the reader that the feature does nothing.
NOISE_RATIO = 1.3

TIMEOUT_TARGEN = 900
TIMEOUT_SCANIN = 600

ARGYLL = Path(os.environ.get("CHROMIQ_ARGYLL_BIN", "/Applications/Argyll/bin"))
SRGB = ARGYLL.parent / "ref" / "sRGB.icm"


def run(cmd, cwd: Path, timeout: int) -> str:
    """One Argyll call, with a timeout. A `subprocess.run` without one waits for
    ever, and `targen -G` has wedged this project's suite for two and a half
    hours with no output."""
    args = [str(c) for c in cmd]
    try:
        r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise SystemExit(
            f"{Path(args[0]).name} did not finish within {timeout} s in {cwd}. "
            f"Nothing killed it; it simply never returned.")
    if r.returncode != 0:
        raise SystemExit(f"{Path(args[0]).name} failed (exit {r.returncode}):\n"
                         f"{r.stdout}\n{r.stderr}")
    return r.stdout


# --------------------------------------------------------------- the chart
def one_page_capacity() -> int:
    """How many patches a CR30 honeycomb holds on one A4 sheet, asked of the
    layout engine rather than written down.

    Only the README uses this now, to say how the 648 fall across the two
    pages without a typed number going stale when a margin moves.
    """
    from workflow.layout_engine import geometry, instruments, papers
    geom = instruments.build(INSTRUMENT, hflag=True, hex_flat_top=True,
                             pscale=1.0, border=MARGIN_MM)
    w_mm, h_mm = papers.dimensions_mm(PAPER)
    lo, hi = 1, 4000
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if geometry.compute(geom, w_mm, h_mm, mid).pages <= 1:
            lo = mid
        else:
            hi = mid - 1
    return lo


def make_ti1(work: Path, stem: str, patches: int) -> Path:
    """A real ArgyllCMS chart design. Not a cube of round numbers: `targen`
    spreads its patches over the whole device space, which is what makes the
    share of them sitting at the end of a channel a property of a real chart
    instead of an artefact of how the list was written."""
    run([ARGYLL / "targen", "-d2", "-e4", "-B4", f"-g{TARGEN_GREY}",
         f"-s{TARGEN_SINGLE}", f"-f{patches}", stem], work, TIMEOUT_TARGEN)
    return work / f"{stem}.ti1"


def build_chart(work: Path, stem: str, patches: int):
    """Lay the chart out with ChromIQ's own engine, as a flat-top CR30
    honeycomb, and write the sidecar the scanner window reads, including the
    full recipe, so the chart also loads back into Create Chart instead of
    being a dead end. Returns (base path, the layout result)."""
    from workflow.layout_engine import chart as le_chart
    from workflow.layout_engine.presets import LayoutRecipe
    ti1 = make_ti1(work, stem, patches)
    base = work / stem
    kwargs = dict(instrument=INSTRUMENT, paper=PAPER, hflag=True,
                  hex_flat_top=True, pscale=1.0, border=MARGIN_MM,
                  dpi=CHART_DPI, randomize=False, seed=1)
    res = le_chart.build_chart(ti1, base, **kwargs)
    if res.layout.pages != EXPECT_PAGES:
        raise SystemExit(
            f"the chart came out on {res.layout.pages} page(s) and this pack "
            f"needs {EXPECT_PAGES}: one page writes a single .cht and leaves "
            f"the per-page naming, which is the thing this pack is here to "
            f"exercise, untested")
    layout = json.loads(base.with_suffix(".strips.json").read_text(encoding="utf-8"))
    layout.update({"engine": "chromiq", "engine_version": 1, "dpi": CHART_DPI,
                   "seed": res.seed, "color_rep": res.color_rep,
                   "recipe": LayoutRecipe.from_build_kwargs(kwargs).to_dict()})
    # The geometry must live UNDER "layout": that is where `scanin_target`
    # looks, and a sidecar written flat is rejected as "not an engine chart".
    (work / f"{stem}.channels.json").write_text(json.dumps(
        {"ink_channels": ["r", "g", "b"], "layout": layout}), encoding="utf-8")
    base.with_suffix(".strips.json").unlink()
    print(f"  chart: {res.layout.total_patches} patches on "
          f"{res.layout.pages} pages, {PAPER}, {INSTRUMENT} honeycomb")
    return base, res


def page_tif(base: Path, page: int) -> Path:
    """The chart image for a one-based page number."""
    return base.parent / f"{base.name}_{page:02d}.tif"


def page_counts(layout: dict) -> "list[int]":
    """How many patches the engine put on each page, in page order."""
    counts: "dict[int, int]" = {}
    for p in layout["patches"]:
        counts[int(p.get("page", 0))] = counts.get(int(p.get("page", 0)), 0) + 1
    return [counts[k] for k in sorted(counts)]


# ---------------------------------------------------------------- the scans
def _sheet(chart_tif: Path):
    """The printed sheet: the chart's device values squeezed into the part of
    the scale a print really occupies. Linear and deliberately crude. It is not
    a model of ink, paper or a scanner's tone curve and is not meant to be; it
    carries one fact, that a printed sheet read by a scanner sits in the middle
    of the device range."""
    from PIL import Image
    import numpy as np
    a = np.asarray(Image.open(chart_tif).convert("RGB")).astype(np.float64)
    return SHEET_BLACK + a * (SHEET_WHITE - SHEET_BLACK) / 255.0


def _auto_brightness(sheet):
    """What the scanner's automatic brightness and contrast does to that sheet:
    lift :data:`AUTO_WHITE` to 255 and let everything above it go. This is the
    whole difference between the two brightness states in the pack."""
    import numpy as np
    return np.clip((sheet - AUTO_BLACK) * 255.0 / (AUTO_WHITE - AUTO_BLACK),
                   0.0, 255.0)


def render_scan(sheet, out: Path, noise_sd: float, seed: int, quiet: bool = False):
    """Turn a sheet into what a scanner would hand back: rotated a little,
    softened by the optics, speckled. Fixed, not random, so the pack rebuilds
    the same every time."""
    from PIL import Image, ImageFilter
    import numpy as np
    img = Image.fromarray(np.clip(sheet, 0, 255).astype("uint8"), "RGB")
    src_w, src_h = _scan_size(img.width, img.height)
    if (src_w, src_h) != img.size:
        img = img.resize((src_w, src_h), Image.Resampling.LANCZOS)
    coeffs, size = _rotation(src_w, src_h)
    fill = tuple(int(round(min(255.0, sheet[..., c].max()))) for c in range(3))
    img = img.transform(size, Image.Transform.AFFINE, coeffs,
                        resample=Image.Resampling.BICUBIC, fillcolor=fill)
    img = img.filter(ImageFilter.GaussianBlur(BLUR_PX))
    a = np.asarray(img).astype(np.float64)
    if noise_sd > 0:
        rng = np.random.default_rng(seed)
        a = a + rng.normal(0, noise_sd, a.shape)
    a = np.clip(a, 0, 255)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(a.astype("uint8")).save(out, dpi=(SCAN_DPI, SCAN_DPI),
                                            compression="tiff_lzw")
    if not quiet:
        print(f"  {out.name}: {a.shape[1]} x {a.shape[0]} px at {SCAN_DPI} dpi, "
              f"speckle {noise_sd:g}, device range "
              f"{int(a.min())}-{int(a.max())} of 0-255")
    return out


def _scan_size(chart_w: int, chart_h: int):
    """The size the sheet is resampled to before it is turned. A scanner reads
    at its own resolution, not the printer's."""
    return (int(chart_w * SCAN_DPI / CHART_DPI),
            int(chart_h * SCAN_DPI / CHART_DPI))


def _rotation(w: int, h: int):
    """The scan's rotation, as an affine this code can invert.

    ``Image.rotate`` would do the same picture, and then the four corners the
    reader has to hand ``scanin`` would have to be guessed at. The mapping is
    written out instead, so :func:`scan_corners` can put the chart's own patch
    bounding box exactly where the rotation left it.

    Returns the coefficients ``Image.transform`` wants (which map an output
    pixel BACK to an input pixel) and the output size.
    """
    import math
    t = math.radians(ROTATION_DEG)
    cos, sin = math.cos(t), math.sin(t)
    cx, cy = w / 2.0, h / 2.0
    xs, ys = [], []
    for px, py in ((0, 0), (w, 0), (w, h), (0, h)):
        xs.append(cos * (px - cx) - sin * (py - cy))
        ys.append(sin * (px - cx) + cos * (py - cy))
    nw, nh = int(math.ceil(max(xs) - min(xs))), int(math.ceil(max(ys) - min(ys)))
    dx, dy = nw / 2.0, nh / 2.0
    # forward:  q = R (p - c) + d      inverse:  p = R^-1 (q - d) + c
    return (cos, sin, cx - cos * dx - sin * dy,
            -sin, cos, cy + sin * dx - cos * dy), (nw, nh)


def _forward(x: float, y: float, w: int, h: int):
    """A chart pixel, where the rotation put it in the scan."""
    import math
    t = math.radians(ROTATION_DEG)
    cos, sin = math.cos(t), math.sin(t)
    (_a, _b, _c, _d, _e, _f), (nw, nh) = _rotation(w, h)
    cx, cy = w / 2.0, h / 2.0
    return (cos * (x - cx) - sin * (y - cy) + nw / 2.0,
            sin * (x - cx) + cos * (y - cy) + nh / 2.0)


def scan_corners(cht_text: str, chart_w: int, chart_h: int):
    """The four corners of the patch block, in scan pixels, in the order
    ``scanin -F`` wants them.

    They are read from the page's own ``.cht`` rather than recomputed: the
    ``F`` line of the patch-box copy IS the patch bounding box, in millimetres,
    top-left origin, y down, the same direction as the image. Placing those four
    points is exactly what the reader does by hand in the scanner window; this
    is the same placement, made exactly, so the numbers the pack claims are not
    a story about how well the corners were dragged.
    """
    import re
    m = re.search(r"(?m)^\s*F _ _ (.*)$", cht_text)
    if not m:
        raise SystemExit("the chart's .cht has no F line to take corners from")
    vals = [float(v) for v in m.group(1).split()]
    if len(vals) != 8:
        raise SystemExit(f"the .cht F line names {len(vals) // 2} corners, not 4")
    # mm -> chart pixel -> the resampled sheet -> where the turn put it. The
    # resample comes FIRST, and a first version of this skipped it and mapped
    # chart pixels straight through the rotation; the reads came back ranking
    # -0.04 against their own reference, which is what the agreement guard in
    # `read_scan` is for.
    src_w, src_h = _scan_size(chart_w, chart_h)
    kx, ky = src_w / chart_w, src_h / chart_h
    px = CHART_DPI / 25.4
    return [_forward(vals[i] * px * kx, vals[i + 1] * px * ky, src_w, src_h)
            for i in (0, 2, 4, 6)]


def prepared_cht(cht: Path, frac: float, into: Path, name: str) -> Path:
    """The ``.cht`` the scanner window would hand ``scanin``: the patch-box
    fiducials added, and the sample area set to what the window computed."""
    from core.text_io import read_text
    from workflow.scanin_runner import (cht_with_patchbox_fiducials,
                                        cht_with_sample_area)
    into.mkdir(parents=True, exist_ok=True)
    out = into / name
    out.write_text(cht_with_sample_area(
        cht_with_patchbox_fiducials(read_text(cht, lenient=True)), frac),
        encoding="utf-8")
    return out


def corners_for_page(cht: Path, chart_tif: Path):
    """Where the four corners of that page's patch block ended up in its scan."""
    from PIL import Image
    from core.text_io import read_text
    from workflow.scanin_runner import cht_with_patchbox_fiducials
    with Image.open(chart_tif) as im:
        cw, ch = im.size
    return scan_corners(cht_with_patchbox_fiducials(read_text(cht, lenient=True)),
                        cw, ch)


# -------------------------------------------------------- measuring the scans
def sample_area(layout: dict) -> float:
    """The share of each patch the scanner window would read on THIS chart.

    A honeycomb cannot take the 80 % a grid of squares can: the sampled square
    has square corners and the hexagon does not, and the next hexagon is flush
    against it. The window computes the ceiling from the chart's own patch
    shape, so this asks the same function rather than naming a percentage.
    """
    from workflow.hex_support import recipe_is_flat_top, ring_mm_of
    from workflow.scanin_runner import hex_sample_area_cap
    patches = layout["patches"]
    ws = sorted(float(p["w"]) for p in patches if float(p.get("w", 0)) > 0)
    hs = sorted(float(p["h"]) for p in patches if float(p.get("h", 0)) > 0)
    # Pixels for both, which is the mistake the window had to be fixed for:
    # `w`/`h` come straight off `patch_rects_px` and the ring is millimetres,
    # and mixing them makes the ceiling depend on the chart's resolution.
    recipe = layout.get("recipe")
    ring_px = ring_mm_of(recipe) * float(layout["dpi"]) / 25.4
    frac = hex_sample_area_cap(ws[len(ws) // 2], hs[len(hs) // 2],
                               flat_top=recipe_is_flat_top(recipe),
                               ring_mm=ring_px)
    # The window shows whole percent and floors, never rounds up.
    return max(0.20, min(0.80, int(frac * 100.0) / 100.0))


# ------------------------------------------------------- a CGATS table, plainly
def _table(path: Path):
    """(all lines, the format's field names, the data slice, the data rows)."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    fi = lines.index("BEGIN_DATA_FORMAT")
    fields = lines[fi + 1].split()
    di, de = lines.index("BEGIN_DATA"), lines.index("END_DATA")
    return lines, fields, (di, de), [l.split() for l in lines[di + 1:de] if l.strip()]


def add_sample_loc(ti3: Path, ti2: Path) -> None:
    """Put the chart's ``SAMPLE_LOC`` column back onto a ``scanin -c``
    measurement.

    ``scanin -c`` reads the chart's ``.ti2`` for the device values and writes
    them back under the same ``SAMPLE_ID``, but it does not carry ``SAMPLE_LOC``
    across. That column is what tells ChromIQ where each patch sits on the
    sheet, and **Create scanner or camera target** refuses a measurement without
    it, with the message about a ``.ti3`` that numbers its patches instead of
    naming their positions. So a pack built without this step ships a ``.ti3``
    that cannot drive the very window it was added for. Measured: the tool
    raised exactly that refusal on the first build of this pack.

    The column is a fact about the CHART and not about the measurement, so
    restoring it invents nothing. It is PROVED rather than assumed: every row's
    device values must still equal the ``.ti2``'s for the same ``SAMPLE_ID``, so
    a join that landed on the wrong patch cannot pass silently.
    """
    _l2, f2, _s2, rows2 = _table(ti2)
    i_id2, i_loc2 = f2.index("SAMPLE_ID"), f2.index("SAMPLE_LOC")
    rgb2 = [f2.index(c) for c in ("RGB_R", "RGB_G", "RGB_B")]
    loc = {r[i_id2]: r[i_loc2] for r in rows2}
    dev = {r[i_id2]: tuple(round(float(r[i]), 3) for i in rgb2) for r in rows2}

    lines, f3, (di, de), rows3 = _table(ti3)
    if "SAMPLE_LOC" in f3:
        return
    i_id3 = f3.index("SAMPLE_ID")
    rgb3 = [f3.index(c) for c in ("RGB_R", "RGB_G", "RGB_B")]
    out = []
    for r in rows3:
        sid = r[i_id3]
        if sid not in loc:
            raise SystemExit(f"the measurement holds patch {sid} and the chart "
                             f"does not: these are not the same chart")
        got = tuple(round(float(r[i]), 3) for i in rgb3)
        if got != dev[sid]:
            raise SystemExit(
                f"patch {sid} carries {got} in the measurement and {dev[sid]} "
                f"in the chart, so pairing them by SAMPLE_ID would put the "
                f"wrong position on the wrong patch")
        out.append(r[:i_id3 + 1] + [loc[sid]] + r[i_id3 + 1:])
    f3n = f3[:i_id3 + 1] + ["SAMPLE_LOC"] + f3[i_id3 + 1:]
    lines[lines.index("BEGIN_DATA_FORMAT") + 1] = " ".join(f3n)
    for i, l in enumerate(lines):
        if l.startswith("NUMBER_OF_FIELDS"):
            lines[i] = f"NUMBER_OF_FIELDS {len(f3n)}"
            break
    lines[di + 1:de] = [" ".join(r) for r in out]
    ti3.write_text("\n".join(lines) + "\n", encoding="utf-8")


def measure_sheet(work: Path, base: Path, scans: "dict[int, Path]",
                  frac: float, tag: str, quiet: bool = False) -> Path:
    """Read every page of one rendering of the sheet, into ONE ``.ti3``.

    This is the "Profile my printer from this scan" path, run the way the window
    runs it: ``scanin -c`` on the first page, ``-ca`` to accumulate each page
    after it, through a scanner profile. What comes out carries the chart's
    device values and the colour the scan measured, which is the shape a printer
    measurement has, and is what **Create scanner or camera target** wants.
    """
    from workflow.scanin_runner import scanin_printer_args
    room = work / f"meas-{tag}"
    if room.exists():
        shutil.rmtree(room)
    room.mkdir(parents=True)
    pbase = room / STEM
    shutil.copy2(base.with_suffix(".ti2"), pbase.with_suffix(".ti2"))
    for i, pg in enumerate(sorted(scans)):
        cht = base.parent / f"{base.name}_{pg:02d}.cht"
        prepared = prepared_cht(cht, frac, room, f"page{pg}.cht")
        run([ARGYLL / "scanin"] + scanin_printer_args(
            scans[pg], prepared, SRGB, pbase,
            corners=corners_for_page(cht, page_tif(base, pg)),
            accumulate=(i > 0)), room, TIMEOUT_SCANIN)
    ti3 = pbase.with_suffix(".ti3")
    add_sample_loc(ti3, base.with_suffix(".ti2"))
    _l, _f, _s, rows = _table(ti3)
    if not quiet:
        print(f"  {tag}: {len(rows)} patches measured across "
              f"{len(scans)} page(s)")
    return ti3


def read_scan(work: Path, base: Path, cie: Path, scan: Path, page: int,
              frac: float, tag: str):
    """What one page's scan looks like once it has been read, measured the way
    the app measures it: prepare that page's ``.cht`` exactly as the scanner
    window does, run the real ``scanin`` from the four corners, and ask
    :func:`workflow.scan_read_check.inspect_read` about the ``.ti3`` that comes
    out. Nothing here re-implements the count; a check that re-implemented the
    code it is checking would only agree with itself.
    """
    from workflow.scan_read_check import inspect_read
    from workflow.scanin_runner import scanin_args
    room = work / f"read-{tag}"
    if room.exists():
        shutil.rmtree(room)
    room.mkdir(parents=True)
    cht = base.parent / f"{base.name}_{page:02d}.cht"
    prepared = prepared_cht(cht, frac, room, f"page{page}.cht")
    # scanin's -O is the WHOLE filename, extension included, and it is written
    # beside the working directory it was run in.
    out = f"{tag}.ti3"
    run([ARGYLL / "scanin"] + scanin_args(
        scan, prepared, cie,
        corners=corners_for_page(cht, page_tif(base, page)), out_name=out),
        room, TIMEOUT_SCANIN)
    # The window's own rank agreement, from the window's own module. It is the
    # one number that would notice the four corners going on in the wrong
    # order: a mirrored placement still reads every patch, still lands inside
    # the ink, and pairs every one of them with the wrong reference.
    from ui.dialogs.scanin_dialog import scan_reference_correlation
    rho = scan_reference_correlation(room / out)
    got = inspect_read(room / out, rho)
    if got is None:
        raise SystemExit(f"{tag}: scanin wrote a .ti3 this cannot read")
    if got.rows == 0:
        raise SystemExit(f"{tag}: scanin read no patches at all")
    white = ("?" if got.highlight is None else f"{got.highlight:.1f}")
    print(f"  {tag}: {got.rows} patches read, "
          f"{got.clipped * 100:.1f} % at an end of the scale "
          f"(top {got.clipped_high * 100:.1f} %, "
          f"bottom {got.clipped_low * 100:.1f} %), white at {white} of 100, "
          f"agreement {'?' if rho is None else f'{rho:+.3f}'}")
    return got


def read_scan_as_a_printer_measurement(work: Path, base: Path, scan: Path,
                                       page: int, frac: float, tag: str):
    """The same scan again, down the OTHER path the window offers.

    "Profile my printer from this scan" runs ``scanin -c``, which writes a
    ``.ti3`` whose ``RGB_*`` are the CHART's printer device values and whose
    ``XYZ_*`` are what the scan measured. That is the right shape for building
    a printer profile and the wrong shape for the two checks that ask about the
    scan's exposure, which read ``RGB_*``: on that path they were answering
    about the chart, so the clipped share did not move with the scan at all and
    the too-dark check could never fire.

    The window now does what this does: a second ``scanin -o`` pass over the
    same image, at the same corners and with the same prepared ``.cht``, which
    reports the scan's own device values (:mod:`workflow.scan_device_values`).
    Both figures then come off the scan, and the two brightness states below
    stop reading the same.

    This is measured rather than asserted, because the README says what the
    reader will see and the reader will see whatever the app does. Returns
    ``None`` when there is no scanner ICC to convert through, since the path
    cannot be walked at all without one.
    """
    from workflow.scan_device_values import measure_scan_device_values
    from workflow.scan_read_check import inspect_read
    if not SRGB.is_file():
        return None
    ti3 = measure_sheet(work, base, {page: scan}, frac, f"printerpath-{tag}")
    room = work / f"printervals-{tag}"
    if room.exists():
        shutil.rmtree(room)
    room.mkdir(parents=True)
    cht = base.parent / f"{base.name}_{page:02d}.cht"
    prepared = prepared_cht(cht, frac, room, f"page{page}.cht")
    values = measure_scan_device_values(
        ARGYLL / "scanin", scan, prepared, room / "vals",
        corners=corners_for_page(cht, page_tif(base, page)),
        ti2=base.with_suffix(".ti2"))
    if values is None:
        raise SystemExit(f"{tag}: the values pass produced nothing to check")
    got = inspect_read(ti3, None, scan=values)
    if got is None:
        raise SystemExit(f"{tag}: scanin -c wrote a .ti3 this cannot read")
    if got.clipped is None:
        raise SystemExit(f"{tag}: the printer path could not measure the scan")
    print(f"  {tag} as a printer measurement: {got.rows} patches, "
          f"{len(values)} read off the scan, "
          f"{got.clipped * 100:.1f} % at an end of the scale")
    return got.clipped


# ------------------------------------------------------------ the noise ladder
def _mean_error(ti3: Path, ref: Path, locs: "set | None" = None) -> float:
    """Mean distance in XYZ between two reads, over the patches in *locs*.

    Not a colour difference formula and not meant to be one: it is a number
    that rises with the speckle, which is what the three reads have to be
    ordered by.
    """
    import numpy as np
    out = []
    for p in (ti3, ref):
        _l, f, _s, rows = _table(p)
        i = [f.index(c) for c in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
        key = f.index("SAMPLE_LOC") if "SAMPLE_LOC" in f else f.index("SAMPLE_ID")
        out.append({r[key].strip('"'): np.array([float(r[k]) for k in i])
                    for r in rows})
    a, b = out
    shared = sorted(set(a) & set(b) & locs) if locs else sorted(set(a) & set(b))
    if not shared:
        raise SystemExit("the two reads share no patch, so they cannot be "
                         "compared")
    return float(np.mean([np.linalg.norm(a[s] - b[s]) for s in shared]))


def page_locs(layout: dict, page: int) -> set:
    """The SAMPLE_LOC of every patch the engine put on one page.

    CGATS quotes a string field, so the ``.ti3`` carries ``"A1"`` where the
    layout carries ``A1``; :func:`_mean_error` strips the quotes so the two
    sets can meet. Skipping that is not a wrong answer, it is an empty
    intersection, and the first build of this pack stopped with "the two reads
    share no patch".
    """
    return {p["loc"] for p in layout["patches"]
            if int(p.get("page", 0)) == page - 1}


def read_noise(work: Path, base: Path, sheet, name: str, sd: float, seed: int,
               frac: float, locs: set) -> float:
    """How much speckle one read really carries, measured against an
    INDEPENDENT rendering of the same sheet at the same speckle.

    The obvious yardstick, a speckle-free rendering, does not work and the first
    build of this pack proved it: measured on this chart, a read at speckle 1.6
    sits 0.240 from a speckle-free read and one at 8.0 sits 0.282, so five times
    the speckle moved the number by a sixth. Almost all of that 0.24 is a fixed
    difference between a rendering that was speckled and one that was not, and
    it swamps the speckle itself. Two independent renderings at the SAME level
    have no such term: they differ by 0.024 at 1.6 and 0.090 at 8.0, which
    tracks the speckle and is the quantity averaging removes.
    """
    twin = render_scan(sheet, work / "renders" / f"{name}-twin" /
                       f"{STEM}_01-scan.tif", sd, seed + 1000, quiet=True)
    a = measure_sheet(work, base, {1: twin}, frac, f"{name}-twin", quiet=True)
    b = measure_sheet(work, base,
                      {1: work / "renders" / name / f"{STEM}_01-scan.tif"},
                      frac, f"{name}-solo", quiet=True)
    return _mean_error(a, b, locs)


def noise_faults(errors: "dict[str, float]") -> list:
    """The averaging demo's one claim: each read is noisier than the last.

    Three files that are equally noisy give averaging nothing to remove, and a
    reader who follows the README then watches a feature appear to do nothing.
    The order is measured against a speckle-free rendering of the same sheet,
    so the number rises with the speckle and with nothing else.
    """
    faults = []
    names = [n for n, _sd, _seed in READS]
    for lo, hi in zip(names, names[1:]):
        if not errors[hi] > errors[lo] * NOISE_RATIO:
            faults.append(
                f"{hi} carries {errors[hi]:.4f} of read noise and {lo} carries "
                f"{errors[lo]:.4f}, which is not the {NOISE_RATIO:g} times "
                f"noisier this pack says it is; averaging these three would "
                f"have nothing to remove")
    return faults


# --------------------------------------------------- the two paths, walked here
def target_faults(work: Path, base: Path, meas: Path, layout: dict,
                  frac: float) -> "tuple[list, dict]":
    """Walk both windows this pack exists for, on the pack's own files.

    Knut's report was that the pack could not be used to test the creation of
    CHT files or the scanner function. It is not enough to put a ``.ti3`` in the
    box and hope: the two windows are driven here, on the files that are about
    to be shipped, and the pack is refused if either cannot be.

    1. **Create scanner or camera target** takes the chart's ``.channels.json``
       and the shipped ``.ti3`` and must write one ``.cht`` per page and one
       ``.cie`` covering every patch.
    2. **Build profile with scanner or camera** must then read every patch of
       every page back through those files.
    """
    from workflow.scanin_target import (ScaninTargetError,
                                        build_scanin_target_from_paths)
    from workflow.scanin_runner import scanin_args
    room = work / "target-check"
    if room.exists():
        shutil.rmtree(room)
    room.mkdir(parents=True)
    shutil.copy2(base.parent / f"{STEM}.channels.json",
                 room / f"{STEM}.channels.json")
    shutil.copy2(meas, room / f"{STEM}.ti3")
    faults: list = []
    facts: dict = {}
    try:
        res = build_scanin_target_from_paths(room / f"{STEM}.channels.json",
                                             room / f"{STEM}.ti3", room / STEM)
    except ScaninTargetError as exc:
        return [f"Create scanner or camera target refuses the .ti3 this pack "
                f"is about to ship: {exc}"], {}
    facts["cht_pages"] = len(res.cht_paths)
    facts["cie_patches"] = res.n_patches
    if len(res.cht_paths) != EXPECT_PAGES:
        faults.append(f"the target came out as {len(res.cht_paths)} .cht "
                      f"file(s) and this pack claims {EXPECT_PAGES}")
    if res.n_patches != PATCHES:
        faults.append(f"the .cie covers {res.n_patches} patches and the chart "
                      f"has {PATCHES}")
    print(f"  Create scanner or camera target: "
          f"{', '.join(p.name for p in res.cht_paths)} + {res.cie_path.name}, "
          f"{res.n_patches} patches on {res.n_pages} pages")

    wanted = page_counts(layout)
    read_back = []
    for pg in range(1, EXPECT_PAGES + 1):
        scan = work / "scans" / f"{STEM}_{pg:02d}-scan.tif"
        cht = room / f"{STEM}_{pg:02d}.cht"
        prepared = prepared_cht(cht, frac, room / f"p{pg}", f"{STEM}.cht")
        out = f"page{pg}.ti3"
        run([ARGYLL / "scanin"] + scanin_args(
            scan, prepared, room / f"{STEM}.cie",
            corners=corners_for_page(cht, page_tif(base, pg)), out_name=out),
            room / f"p{pg}", TIMEOUT_SCANIN)
        _l, _f, _s, rows = _table(room / f"p{pg}" / out)
        read_back.append(len(rows))
        if len(rows) != wanted[pg - 1]:
            faults.append(
                f"the scanner path read {len(rows)} of page {pg}'s "
                f"{wanted[pg - 1]} patches back through the pack's own .cht "
                f"and .cie")
    facts["read_back"] = read_back
    print(f"  Build profile with scanner or camera: read "
          f"{' + '.join(str(n) for n in read_back)} patches back through the "
          f"pack's own recognition files")
    return faults, facts


def clipping_faults(good: float, bad: float, cap: float) -> list:
    """The pack's two claims, checked against what the two scans measured.

    This is the whole reason the generator runs ``scanin`` on its own output.
    A demo pack is read by somebody who has been told what they are about to
    see, so a pack that no longer shows it is worse than no pack: it teaches
    the reader that the warning is noise. Both claims are checked with room to
    spare, so a later change of one decimal place in the limit cannot quietly
    turn this into a pack that demonstrates nothing.
    """
    faults = []
    if not good < cap - CLIP_MARGIN:
        faults.append(
            f"the in-range scan reads {good * 100:.1f} % clipped, which is not "
            f"comfortably under the {cap * 100:.0f} % limit "
            f"({(cap - CLIP_MARGIN) * 100:.0f} % or less); a reader following "
            f"the README would be stopped by the very warning it says they "
            f"will not see")
    if not bad > cap + CLIP_MARGIN:
        faults.append(
            f"the out-of-scale scan reads {bad * 100:.1f} % clipped, which is "
            f"not comfortably over the {cap * 100:.0f} % limit "
            f"({(cap + CLIP_MARGIN) * 100:.0f} % or more); the warning this "
            f"pack exists to show would not appear")
    return faults


def _other_findings(got, defaults, tag: str, why: str) -> list:
    """Everything the build gate asks about a read EXCEPT the clipping, on both
    scans.

    Clipping is the one thing this pack is about, and it is the one thing that
    is allowed to differ between the two files. If either scan also disagreed
    with its reference, came back too dark, or gave the fit too few distinct
    colours, the reader would meet a second window and the demonstration would
    be of nothing in particular.
    """
    out = []
    if got.disagrees(float(defaults["scanner_min_agreement"])):
        out.append(f"the {tag} scan ranks {got.agreement:+.3f} against its "
                   f"reference, under the {defaults['scanner_min_agreement']} "
                   f"floor: the four corners have gone on in the wrong order "
                   f"or the grid has slipped, and this is {why}")
    if got.underexposed(float(defaults["scanner_min_highlight"])):
        out.append(f"the {tag} scan's own white sits at "
                   f"{got.highlight:.1f} of 100, under the "
                   f"{defaults['scanner_min_highlight']:.0f} floor, so it "
                   f"raises the too-dark warning as well, and this is {why}")
    if got.fit_is_unsupported(int(defaults["scanner_min_fit_support"])):
        out.append(f"the {tag} scan's reference gives the fit "
                   f"{got.support} distinct colours, under the "
                   f"{defaults['scanner_min_fit_support']} floor, and this "
                   f"is {why}")
    return out


# -------------------------------------------------------------------- README
def _printer_path_note(good_p, bad_p) -> str:
    """What the reader will see on the "Profile my printer from this scan"
    path, written from what that path actually measured here.

    It is written this way, rather than typed once and left, because the
    sentence is about the app and not about the pack: if the app changes, the
    numbers change with it and so does the paragraph. A README that describes
    an app that no longer behaves that way is worse than one that says nothing.
    """
    if good_p is None or bad_p is None:
        return ""
    if abs(good_p - bad_p) < 0.005:
        return f"""
## One thing to know before you start

There are two ways into the scanner window, and only one of them looks at the
scan.

With **"Profile my printer from this scan" ticked**, ChromIQ converts the scan
to colour through a scanner profile, and the file it then checks carries the
CHART's patch values where the scan's own values would be. Measured on this
pack, that path reports **{good_p * 100:.0f} %** for the in-range scan and
**{bad_p * 100:.0f} %** for the out-of-scale one: the same figure for both, because on
that path the figure comes from the chart and not from the scan. Both files
therefore raise the warning, and it says nothing about either of them.

**That is a fault, not a design.** It was found by building this pack and is
reported on issue 182. Until it is settled, judge a scan's brightness with the
box unticked, where the check reads the scan.

With the box **unticked**, press **Check alignment**. That path reads the scan
against the chart's own reference and reports what the scan really did.
"""
    return f"""
## Either way in

Ticked or unticked, the window agrees about these two files: the in-range scan
reports {good_p * 100:.0f} % on the printer path and the out-of-scale one {bad_p * 100:.0f} %.
"""


def readme(facts: dict) -> str:
    counts = facts["page_counts"]
    split = " and ".join(f"{n} on page {i + 1}" for i, n in enumerate(counts))
    return f"""# ChromIQ CR30 honeycomb demo pack

A {PATCHES}-patch flat-top CR30 honeycomb on {PAPER}, laid out by ChromIQ's own engine
across {len(counts)} pages ({split}), together with scans of those pages and real
measurements read off those scans.

Everything here is a simulation. There is no ink, no paper and no
spectrophotometer: the chart was laid out by ChromIQ, the printed sheet was
rendered from it, and the scans were rendered from the sheet. Use them to see
the tools work, not to judge a profile.

What IS real is every measurement. Each `.ti3` below was read off an actual
image by ArgyllCMS's own `scanin`, so the turn of the sheet, the softness of the
optics, the speckle, and the sampling square averaging over a hexagon are all in
the numbers. That is the difference from the measurements this pack used to
carry, which were `fakeread` restatements of the chart's own aim values and
could not show any of it.

## What is in the box

    chart/{STEM}.ti1 / .ti2            the patch set and the chart
    chart/{STEM}.channels.json         the exact geometry ChromIQ recorded
    chart/{STEM}_01.tif                page 1, ready to print
    chart/{STEM}_02.tif                page 2
    chart/{STEM}.ti3                   the clean measurement, filed beside the
                                          chart, which is where the scanner
                                          tools look for the geometry sidecar

    measurements/{READS[0][0]}.ti3            the same clean measurement
    measurements/{READS[1][0]}.ti3            the same sheet, read again with more
                                          scanner speckle
    measurements/{READS[2][0]}.ti3          and again with more still, so
                                          averaging has work to do

    scan/{STEM}_01-scan.tif            page 1 as a {SCAN_DPI} dpi scan
    scan/{STEM}_02-scan.tif            page 2
    scan/{STEM}_01-scan-out-of-scale.tif  page 1 again, with the scanner's
                                          automatic brightness switched on

    measured.json                         every number below, as this pack
                                          measured it

## Creating the recognition files (.cht + .cie)

This is the path that needs the measurement, and it is why the `.ti3` files are
here.

1. Preferences, Beta, "Allow hexagonal charts in the scanner and camera tools".
   Without it the tools will politely refuse a honeycomb and tell you why.
2. Tools, **Create scanner or camera target**.
3. Leave "In ChromIQ" selected and pick `chart/{STEM}.ti3`.
4. The line under the box should read that it is ready. Press **Create the
   files**.

ChromIQ writes `{STEM}_01.cht`, `{STEM}_02.cht` and a single
`{STEM}.cie` next to the chart: **one .cht per page**, which is the part a
one-page chart cannot show you. Measured here, they cover all {facts['cie_patches']} patches.

## Using them in the scanner function

5. Tools, **Build profile with scanner or camera**.
6. Measured chart: `chart/{STEM}.ti2`. ChromIQ finds the recognition files you
   just made.
7. One scan per page: `scan/{STEM}_01-scan.tif` and
   `scan/{STEM}_02-scan.tif`.
8. Drag the four corners of the mesh onto the four corners of each page's patch
   block, or press Auto align. The cells are drawn as hexagons, so you can see
   them sit on the ink.
9. Note "Patch sample area". On this chart it stops at {facts['sample_area'] * 100:.0f} %, not the 80 % a
   grid of squares allows: the square ChromIQ reads has to stay inside a
   hexagon, and the next hexagon is flush against it.
10. Press **Check alignment**, then Build.

Measured here, that path reads {' + '.join(str(n) for n in facts['read_back'])} patches back through the pack's own
recognition files, which is every patch on both pages.
{_printer_path_note(facts['in_range_clipped_printer_path'],
                    facts['out_of_scale_clipped_printer_path'])}
## Averaging three reads

`measurements/` holds three measurements of the same sheet. They are three
different scans of it, differing only in how much speckle the scanner added, so
the difference between them is the difference between three real images and not
three different sets of numbers.

Load them in turn in the Measure tab under "I already have a measurement".
Each one's read noise was measured against an independent scan of the same
sheet at the same setting, and the three sit at {facts['noise'][READS[0][0]]:.4f}, {facts['noise'][READS[1][0]]:.4f} and
{facts['noise'][READS[2][0]]:.4f}, so each really is noisier than the one before it and averaging has
something to remove.

## Watching the end-of-scale warning happen, and not happen

`scan/{STEM}_01-scan.tif` and `scan/{STEM}_01-scan-out-of-scale.tif`
are the SAME printed page. The geometry, the patch values, the turn, the
softening and the speckle are identical. The only difference is where the
scanner's brightness control left the sheet on the device scale.

**The plain scan** is what you get with the automatic brightness and contrast
switched off. The sheet occupies the middle of the scale: solid ink around
{SHEET_BLACK} of 255 and paper around {SHEET_WHITE}, with room left at both ends. Measured through
ChromIQ's own read check, **{facts['in_range_clipped'] * 100:.1f} %** of its patches sit at an end of the scale.
The limit is {facts['scanner_max_clipped'] * 100:.0f} %, so Check alignment passes it without a word about the
scale.

**The out-of-scale one** is what you get with it switched on. The scanner has
decided the paper is meant to be pure white and stretched the scale until it is,
and every patch printed at the top of a channel has gone over the edge with it.
Measured the same way, **{facts['out_of_scale_clipped'] * 100:.1f} %** of its patches are on the rail. That is over
the {facts['scanner_max_clipped'] * 100:.0f} % limit, so ChromIQ stops and says so:

    Part of this scan has no colour left in it

    ... of the patches were read at the very end of the scan's brightness
    range, where there is nothing left to record. Their real colours are gone,
    not merely shifted ...

**That one is deliberate.** It is not a broken file and there is nothing to fix
in it. It is in the pack so the warning can be seen, read and clicked past, and
so the difference between a scan with headroom and a scan without one can be
looked at side by side.

## Try it for real

Print both pages of `chart/` with colour management switched off and read them
with a CR30, or scan them at {SCAN_DPI} dpi and use your own scans. If your own scan
trips the warning, the out-of-scale file is what that looks like and the plain
one is what to aim for.

Faults, or a scan that will not read: please open an issue and attach the scan.
"""


# ---------------------------------------------------------------------- main
def main() -> int:
    from core.settings import DEFAULTS
    cap = float(DEFAULTS["scanner_max_clipped"])

    if not (ARGYLL / "targen").is_file():
        print(f"ArgyllCMS is required ({ARGYLL}).")
        return 2

    dest = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "dist" / PACK
    if dest.name != PACK:
        dest = dest / PACK
    if dest.exists():
        shutil.rmtree(dest)
    for sub in ("chart", "measurements", "scan"):
        (dest / sub).mkdir(parents=True)
    work = dest.parent / f"_{PACK}-build"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    print(f"building {PACK}:")
    print(f"  one {PAPER} sheet holds {one_page_capacity()} patches as a "
          f"{INSTRUMENT} honeycomb, so {PATCHES} needs more than one")
    base, _res = build_chart(work, STEM, PATCHES)

    # The per-page .cht ChromIQ would write for this chart. It is built from the
    # chart's AIM values here, because nothing has been measured yet, and it is
    # used only to know where the patches are; it never leaves the build folder.
    # What ships is built again below, from the measurement.
    from workflow.scanin_target import build_scanin_target_from_paths
    build_scanin_target_from_paths(work / f"{STEM}.channels.json",
                                   base.with_suffix(".ti2"), base)

    layout = json.loads((work / f"{STEM}.channels.json").read_text(
        encoding="utf-8"))["layout"]
    counts = page_counts(layout)
    frac = sample_area(layout)
    pages = list(range(1, EXPECT_PAGES + 1))

    print("rendering scans:")
    sheets = {pg: _sheet(page_tif(base, pg)) for pg in pages}
    scans = {}
    for name, sd, seed in READS:
        scans[name] = {
            pg: render_scan(sheets[pg], work / "renders" / name /
                            f"{STEM}_{pg:02d}-scan.tif", sd, seed + pg,
                            quiet=(name != PRIMARY_READ))
            for pg in pages}
    # The one the pack ships as its scans, and the one the out-of-scale file is
    # a second version of.
    shipped = scans[PRIMARY_READ]
    (work / "scans").mkdir(exist_ok=True)
    for pg in pages:
        shutil.copy2(shipped[pg], work / "scans" / f"{STEM}_{pg:02d}-scan.tif")
    out_of_scale = render_scan(
        _auto_brightness(sheets[1]),
        work / "scans" / f"{STEM}_01-scan-out-of-scale.tif",
        READS[0][1], READS[0][2] + 1)

    print(f"measuring the sheet at the window's own {frac * 100:.0f} % sample area:")
    measured = {name: measure_sheet(work, base, scans[name], frac, name)
                for name, _sd, _seed in READS}
    locs1 = page_locs(layout, 1)
    noise = {name: read_noise(work, base, sheets[1], name, sd, seed, frac, locs1)
             for name, sd, seed in READS}
    for name, _sd, _seed in READS:
        print(f"  {name}: {noise[name]:.4f} of read noise, measured against an "
              f"independent scan of the same sheet")

    # The measured .cie the two brightness states are judged against. Built from
    # the clean read, which is the one the pack tells the reader to make.
    check = work / "cie-check"
    if check.exists():
        shutil.rmtree(check)
    check.mkdir()
    shutil.copy2(work / f"{STEM}.channels.json", check / f"{STEM}.channels.json")
    shutil.copy2(measured[PRIMARY_READ], check / f"{STEM}.ti3")
    build_scanin_target_from_paths(check / f"{STEM}.channels.json",
                                   check / f"{STEM}.ti3", check / STEM)

    print("the two brightness states, on page 1:")
    good_read = read_scan(work, base, check / f"{STEM}.cie",
                          shipped[1], 1, frac, "in-range")
    bad_read = read_scan(work, base, check / f"{STEM}.cie",
                         out_of_scale, 1, frac, "out-of-scale")
    good, bad = good_read.clipped, bad_read.clipped
    good_p = read_scan_as_a_printer_measurement(work, base, shipped[1], 1,
                                                frac, "in-range")
    bad_p = read_scan_as_a_printer_measurement(work, base, out_of_scale, 1,
                                               frac, "out-of-scale")

    print("walking the two windows this pack is for:")
    tfaults, tfacts = target_faults(work, base, measured[PRIMARY_READ],
                                    layout, frac)

    # ------------------------------------------------------------ the pack
    for suffix in (".ti1", ".ti2", ".channels.json"):
        shutil.copy2(base.with_suffix(suffix),
                     dest / "chart" / f"{STEM}{suffix}")
    for pg in pages:
        shutil.copy2(page_tif(base, pg), dest / "chart" / page_tif(base, pg).name)
    shutil.copy2(measured[PRIMARY_READ], dest / "chart" / f"{STEM}.ti3")
    for name, _sd, _seed in READS:
        shutil.copy2(measured[name], dest / "measurements" / f"{name}.ti3")
    for pg in pages:
        shutil.copy2(shipped[pg], dest / "scan" / f"{STEM}_{pg:02d}-scan.tif")
    shutil.copy2(out_of_scale,
                 dest / "scan" / f"{STEM}_01-scan-out-of-scale.tif")

    facts = {
        "stem": STEM, "patches": PATCHES, "instrument": INSTRUMENT,
        "paper": PAPER, "pages": EXPECT_PAGES, "page_counts": counts,
        "sample_area": frac, "scanner_max_clipped": cap,
        "in_range_clipped": good, "out_of_scale_clipped": bad,
        "in_range_clipped_printer_path": good_p,
        "out_of_scale_clipped_printer_path": bad_p,
        "margin": CLIP_MARGIN, "noise": noise, "noise_ratio": NOISE_RATIO,
        **tfacts,
    }
    (dest / "README.md").write_text(readme(facts), encoding="utf-8")
    (dest / "measured.json").write_text(json.dumps(facts, indent=2),
                                        encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)

    # THE PACK MUST DEMONSTRATE WHAT IT SAYS IT DEMONSTRATES.
    faults = clipping_faults(good, bad, cap)
    faults += _other_findings(good_read, DEFAULTS, "in-range",
                              "a scan the README says runs to the end")
    faults += _other_findings(bad_read, DEFAULTS, "out-of-scale",
                              "a scan the README says trips one warning and "
                              "one only")
    faults += noise_faults(noise)
    faults += tfaults
    print()
    if faults:
        for f in faults:
            print(f"REFUSING: {f}")
        shutil.rmtree(dest, ignore_errors=True)
        return 1
    size = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
    print(f"in range {good * 100:.1f} % clipped, out of scale {bad * 100:.1f} %, "
          f"limit {cap * 100:.0f} %")
    print(f"written to {dest}  ({size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
