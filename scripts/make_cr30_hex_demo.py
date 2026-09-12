#!/usr/bin/env python3
"""Build the ChromIQ-CR30-hex-demo pack: a CR30 honeycomb and two scans of it.

The ruling this exists for (#182, 2026-09-11) was an answer to one question:
should the demo scans be rebuilt so they look like a real scan and go all the
way through, or should one keep tripping the end-of-scale warning on purpose so
it can be watched happening? The answer was **both, in one pack**.

So there is ONE chart here and TWO scans of it. The chart is a real CR30
honeycomb on A4, filled to the one-page capacity ChromIQ's own layout engine
computes for that instrument, that paper and that patch size. The two scans are
the same printed sheet. Nothing about the sheet, the geometry, the alignment or
the patch values differs between them. The only difference is where the
scanner's brightness control left the sheet on the device scale:

    ...-scan-1-in-range.tif       automatic brightness OFF. The sheet occupies
                                  the middle of the scale, nothing reaches
                                  either end, and the whole path finishes.
    ...-scan-2-out-of-scale.tif   automatic brightness ON. The scanner has
                                  pushed the paper to pure white, taking every
                                  patch printed at the top of a channel with
                                  it. Those patches now sit on the rail, and
                                  the build gate stops to say so.

The share of patches on a rail is measured here, from the real ``.ti3`` a real
``scanin`` writes through the real per-page ``.cht`` the scanner window
prepares, by :func:`workflow.scan_read_check.inspect_read` - the same function
the window itself asks. **This generator refuses to write a pack whose scans do
not do what the README says they do**: if the in-range scan is not comfortably
under ``scanner_max_clipped`` or the out-of-scale one not comfortably over it,
it prints both numbers and exits non-zero.

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

#: The chart. A CR30 is placed on one patch at a time, so its own patch size is
#: what the honeycomb is built from and there is no strip run-up to pay for; the
#: 5 mm margin is the one `data/patch_db.py` gives the instrument, and the patch
#: count is NOT written down - :func:`one_page_capacity` asks the engine.
INSTRUMENT = "CR30"
PAPER = "A4"
MARGIN_MM = 5.0
CHART_DPI = 300
SCAN_DPI = 200

#: Grey and single-channel ramps kept eligible, the same shape
#: `scripts/make_report_limit_demos.py` uses, so the chart is a chart somebody
#: could really build a profile from and not a bag of colours.
TARGEN_GREY = 16
TARGEN_SINGLE = 12

#: The device range a printed sheet really occupies once a scanner has read it.
#: Solid ink is not 0 and paper is not 255: measured across the reads this
#: project keeps, the darkest patch of a matte print lands near 22/255 and the
#: paper near 246/255. Both scans in this pack are renderings of a sheet that
#: sits here; they differ only in what the scanner then did with it.
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
NOISE_SD = 1.6
NOISE_SEED = 20260912

#: How far past `scanner_max_clipped` each scan must land before this pack is
#: allowed to claim it demonstrates anything. A scan that merely squeaks over
#: the line would turn a later change of one decimal place into a pack that
#: quietly stops demonstrating what it says it does.
CLIP_MARGIN = 0.05

TIMEOUT_TARGEN = 900
TIMEOUT_SCANIN = 600

ARGYLL = Path(os.environ.get("CHROMIQ_ARGYLL_BIN", "/Applications/Argyll/bin"))


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

    A typed count is a count that goes stale: the margin, the patch size and
    the apex overhang a flat-top honeycomb reserves are all the engine's to
    decide, and any of them can move.
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


def build_chart(work: Path, stem: str, patches: int) -> Path:
    """Lay the chart out with ChromIQ's own engine, as a flat-top CR30
    honeycomb, and write the sidecar the scanner window reads - including the
    full recipe, so the chart also loads back into Create Chart instead of
    being a dead end."""
    from workflow.layout_engine import chart as le_chart
    from workflow.layout_engine.presets import LayoutRecipe
    ti1 = make_ti1(work, stem, patches)
    base = work / stem
    kwargs = dict(instrument=INSTRUMENT, paper=PAPER, hflag=True,
                  hex_flat_top=True, pscale=1.0, border=MARGIN_MM,
                  dpi=CHART_DPI, randomize=False, seed=1)
    res = le_chart.build_chart(ti1, base, **kwargs)
    if res.layout.pages != 1:
        raise SystemExit(f"the chart came out on {res.layout.pages} pages; "
                         f"this pack is about one sheet")
    layout = json.loads(base.with_suffix(".strips.json").read_text(encoding="utf-8"))
    layout.update({"engine": "chromiq", "engine_version": 1, "dpi": CHART_DPI,
                   "seed": res.seed, "color_rep": res.color_rep,
                   "recipe": LayoutRecipe.from_build_kwargs(kwargs).to_dict()})
    # The geometry must live UNDER "layout": that is where `scanin_target`
    # looks, and a sidecar written flat is rejected as "not an engine chart".
    (work / f"{stem}.channels.json").write_text(json.dumps(
        {"ink_channels": ["r", "g", "b"], "layout": layout}), encoding="utf-8")
    base.with_suffix(".strips.json").unlink()
    print(f"  chart: {res.layout.total_patches} patches, "
          f"{res.layout.passes} rows of {res.layout.steps_in_pass}, "
          f"{PAPER}, {INSTRUMENT} honeycomb")
    return base


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
    whole difference between the two scans in the pack."""
    import numpy as np
    return np.clip((sheet - AUTO_BLACK) * 255.0 / (AUTO_WHITE - AUTO_BLACK),
                   0.0, 255.0)


def render_scan(sheet, out: Path):
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
    rng = np.random.default_rng(NOISE_SEED)
    a = np.clip(a + rng.normal(0, NOISE_SD, a.shape), 0, 255)
    Image.fromarray(a.astype("uint8")).save(out, dpi=(SCAN_DPI, SCAN_DPI),
                                            compression="tiff_lzw")
    print(f"  {out.name}: {a.shape[1]} x {a.shape[0]} px at {SCAN_DPI} dpi, "
          f"device range {int(a.min())}-{int(a.max())} of 0-255")
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

    They are read from the chart's own ``.cht`` rather than recomputed: the
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


def read_scan(work: Path, base: Path, scan: Path, frac: float,
              corners, tag: str):
    """What this scan looks like once it has been read, measured the way the
    app measures it: prepare the ``.cht`` exactly as the
    scanner window does, run the real ``scanin`` from the four corners, and ask
    :func:`workflow.scan_read_check.inspect_read` about the ``.ti3`` that comes
    out. Nothing here re-implements the count; a check that re-implemented the
    code it is checking would only agree with itself.
    """
    from core.text_io import read_text
    from workflow.scan_read_check import inspect_read
    from workflow.scanin_runner import (cht_with_patchbox_fiducials,
                                        cht_with_sample_area, scanin_args)
    cht = base.with_suffix(".cht")
    prepared = work / f"{tag}.cht"
    prepared.write_text(cht_with_sample_area(
        cht_with_patchbox_fiducials(read_text(cht, lenient=True)), frac),
        encoding="utf-8")
    # scanin's -O is the WHOLE filename, extension included, and it is written
    # beside the working directory it was run in.
    out = f"{tag}-read.ti3"
    run([ARGYLL / "scanin"] + scanin_args(scan, prepared,
                                          base.with_suffix(".cie"),
                                          corners=corners, out_name=out),
        work, TIMEOUT_SCANIN)
    # The window's own rank agreement, from the window's own module. It is the
    # one number that would notice the four corners going on in the wrong
    # order: a mirrored placement still reads 396 patches, still lands inside
    # the ink, and pairs every one of them with the wrong reference.
    from ui.dialogs.scanin_dialog import scan_reference_correlation
    rho = scan_reference_correlation(work / out)
    got = inspect_read(work / out, rho)
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
                                       frac: float, corners, tag: str):
    """The same scan again, down the OTHER path the window offers.

    "Profile my printer from this scan" runs ``scanin -c``, which writes a
    ``.ti3`` whose ``RGB_*`` are the CHART's printer device values and whose
    ``XYZ_*`` are what the scan measured. That is the right shape for building
    a printer profile and the wrong shape for the read check, which counts a
    patch as clipped from ``RGB_*``: on that path the count is a property of
    the chart and moves not at all with the scan.

    This is measured rather than asserted, because the README says what the
    reader will see and the reader will see whatever the app does. Returns
    ``None`` when there is no scanner ICC to convert through, since the path
    cannot be walked at all without one.
    """
    from core.text_io import read_text
    from workflow.scan_read_check import inspect_read
    from workflow.scanin_runner import (cht_with_patchbox_fiducials,
                                        cht_with_sample_area,
                                        scanin_printer_args)
    srgb = ARGYLL.parent / "ref" / "sRGB.icm"
    if not srgb.is_file():
        return None
    room = work / f"{tag}-printer"
    room.mkdir(parents=True, exist_ok=True)
    prepared = room / f"{tag}.cht"
    prepared.write_text(cht_with_sample_area(
        cht_with_patchbox_fiducials(read_text(base.with_suffix(".cht"),
                                              lenient=True)), frac),
        encoding="utf-8")
    pbase = room / "printer"
    shutil.copy2(base.with_suffix(".ti2"), pbase.with_suffix(".ti2"))
    run([ARGYLL / "scanin"] + scanin_printer_args(scan, prepared, srgb, pbase,
                                                  corners=corners),
        room, TIMEOUT_SCANIN)
    got = inspect_read(pbase.with_suffix(".ti3"), None)
    if got is None:
        raise SystemExit(f"{tag}: scanin -c wrote a .ti3 this cannot read")
    print(f"  {tag} as a printer measurement: {got.rows} patches, "
          f"{got.clipped * 100:.1f} % at an end of the scale")
    return got.clipped


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
def _printer_path_note(cap: float, good_p, bad_p) -> str:
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

There are two ways into this window, and only one of them looks at the scan.

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
against the chart's own reference and reports what the scan really did, which
is the comparison this pack was made for. Everything below is about that.
"""
    return f"""
## Either way in

Ticked or unticked, the window agrees about these two files: the in-range scan
reports {good_p * 100:.0f} % on the printer path and the out-of-scale one {bad_p * 100:.0f} %.
"""


def readme(patches: int, cap: float, frac: float, good: float, bad: float,
           good_p, bad_p) -> str:
    return f"""# ChromIQ CR30 honeycomb, two scans of one sheet

This pack is here so the end-of-scale warning can be watched happening, and
then watched not happening, on a chart that is otherwise the same in every
respect.

Everything in it is a simulation. There is no ink, no paper and no scanner:
the chart was laid out by ChromIQ's own engine, and the two scans were rendered
from that chart. Use them to see the tool work, not to judge a profile.

## What is in the box

    chart/CR30HexDemo.tif             a {patches}-patch CR30 honeycomb on {PAPER}, ready to print
    chart/CR30HexDemo.ti1 / .ti2      the patch list and the chart's aim values
    chart/CR30HexDemo.channels.json   the exact geometry ChromIQ recorded for it
    scan/CR30HexDemo-scan-1-in-range.tif       a scan that goes all the way through
    scan/CR30HexDemo-scan-2-out-of-scale.tif   a scan that keeps tripping the warning
    measured.json                     the numbers below, as this pack measured them

The chart is a flat-top honeycomb for the CR30, on {PAPER}, at the instrument's own
patch size and its {MARGIN_MM:g} mm margin. {patches} patches is what ChromIQ's layout engine
says one sheet holds at that size, so the sheet is full.
{_printer_path_note(cap, good_p, bad_p)}
## The two scans

They are the SAME printed sheet. The geometry, the patch values, the rotation,
the softening and the speckle are identical. The only difference is where the
scanner's brightness control left the sheet on the device scale.

**`scan-1-in-range.tif`** is what you get with the automatic brightness and
contrast switched off. The sheet occupies the middle of the scale: solid ink
around {SHEET_BLACK} of 255 and paper around {SHEET_WHITE}, with room left at both ends.
Measured through ChromIQ's own read check, **{good * 100:.1f} %** of its patches sit at an
end of the scale. The limit is {cap * 100:.0f} %, so Check alignment passes it without a word
about the scale and there is nothing in the way of the rest of the job.

**`scan-2-out-of-scale.tif`** is what you get with it switched on. The scanner
has decided the paper is meant to be pure white and stretched the scale until
it is, and every patch printed at the top of a channel has gone over the edge
with it. Measured the same way, **{bad * 100:.1f} %** of its patches are on the rail. That
is over the {cap * 100:.0f} % limit, so ChromIQ stops and says so:

    Part of this scan has no colour left in it

    ... of the patches were read at the very end of the scan's brightness
    range, where there is nothing left to record. Their real colours are gone,
    not merely shifted ...

**That one is deliberate.** It is not a broken file and there is nothing to fix
in it. It is in the pack so the warning can be seen, read and clicked past, and
so the difference between a scan with headroom and a scan without one can be
looked at side by side.

## Watching it happen, and not happen

1. Preferences, Beta, "Allow hexagonal charts in the scanner and camera tools".
   Without it the tool will politely refuse a honeycomb and tell you why.
2. Tools, Build profile with scanner or camera.
3. Measured chart: pick `chart/CR30HexDemo.ti2`.
4. Scan or photo: pick `scan/CR30HexDemo-scan-1-in-range.tif`.
5. Drag the four corners of the mesh onto the four corners of the patch block,
   or press Auto align. The cells are drawn as hexagons, so you can see them
   sit on the ink.
6. Note "Patch sample area". On this chart it stops at {frac * 100:.0f} %, not the 80 % a
   grid of squares allows: the square ChromIQ reads has to stay inside a
   hexagon, and the next hexagon is flush against it.
7. Leave "Profile my printer from this scan" UNTICKED and press
   **Check alignment**. The window reports the grid sitting cleanly on the
   patches and says nothing about the scale.
8. Now load `scan/CR30HexDemo-scan-2-out-of-scale.tif` in its place, align it
   the same way and press Check alignment again. This time the warning comes
   up, with its own figure.

That is the pair, in one window, a checkbox and a file apart.

## Building a profile from it

Tick "Profile my printer from this scan" and pick a scanner profile, then
Build. The chart has not been measured with an instrument, so this is the path
that turns it into a printer profile: the scanner is the measuring instrument
and its own profile is how ChromIQ knows what the colours are. Any input
profile lets the path run, but only a scanner profile you built yourself makes
the printer profile mean anything, and this pack is about the scan's range
rather than about the profile's accuracy.

## Try it for real

Print `chart/CR30HexDemo.tif` with colour management switched off and read it
with a CR30, or scan it at {SCAN_DPI} dpi and use your own scan at step 4. If your own
scan trips the warning, the second file in this pack is what that looks like
and the first is what to aim for.

Faults, or a scan that will not read: please open an issue and attach the scan.
"""


# ---------------------------------------------------------------------- main
def main() -> int:
    from core.settings import DEFAULTS
    cap = float(DEFAULTS["scanner_max_clipped"])

    dest = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "dist" / PACK
    if dest.name != PACK:
        dest = dest / PACK
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "chart").mkdir(parents=True)
    (dest / "scan").mkdir(parents=True)
    work = dest.parent / f"_{PACK}-build"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    stem = "CR30HexDemo"
    patches = one_page_capacity()
    print(f"building {PACK}:")
    print(f"  one {PAPER} sheet holds {patches} patches as a {INSTRUMENT} honeycomb")
    base = build_chart(work, stem, patches)

    # The .cht and .cie the scanner window would build from this chart. The app
    # writes its own copies when the chart is picked; these are here so the
    # measurement below is made through the same geometry the reader will get.
    from workflow.scanin_target import build_scanin_target_from_paths
    build_scanin_target_from_paths(work / f"{stem}.channels.json",
                                   base.with_suffix(".ti2"), base)

    from PIL import Image
    from core.text_io import read_text
    from workflow.scanin_runner import cht_with_patchbox_fiducials
    with Image.open(base.with_suffix(".tif")) as im:
        chart_w, chart_h = im.size
    corners = scan_corners(
        cht_with_patchbox_fiducials(read_text(base.with_suffix(".cht"),
                                              lenient=True)),
        chart_w, chart_h)

    sheet = _sheet(base.with_suffix(".tif"))
    print("rendering scans:")
    good_tif = render_scan(sheet, dest / "scan" / f"{stem}-scan-1-in-range.tif")
    bad_tif = render_scan(_auto_brightness(sheet),
                          dest / "scan" / f"{stem}-scan-2-out-of-scale.tif")

    layout = json.loads((work / f"{stem}.channels.json").read_text(
        encoding="utf-8"))["layout"]
    frac = sample_area(layout)
    print(f"measuring both scans at the window's own {frac * 100:.0f} % sample area:")
    good_read = read_scan(work, base, good_tif, frac, corners, "in-range")
    bad_read = read_scan(work, base, bad_tif, frac, corners, "out-of-scale")
    good, bad = good_read.clipped, bad_read.clipped
    good_p = read_scan_as_a_printer_measurement(work, base, good_tif, frac,
                                                corners, "in-range")
    bad_p = read_scan_as_a_printer_measurement(work, base, bad_tif, frac,
                                               corners, "out-of-scale")

    for suffix in (".tif", ".ti1", ".ti2", ".channels.json"):
        src = base.with_suffix(suffix)
        if src.is_file():
            shutil.copy2(src, dest / "chart" / src.name)
    (dest / "README.md").write_text(
        readme(patches, cap, frac, good, bad, good_p, bad_p), encoding="utf-8")
    (dest / "measured.json").write_text(json.dumps({
        "patches": patches, "instrument": INSTRUMENT, "paper": PAPER,
        "sample_area": frac, "scanner_max_clipped": cap,
        "in_range_clipped": good, "out_of_scale_clipped": bad,
        "in_range_clipped_printer_path": good_p,
        "out_of_scale_clipped_printer_path": bad_p,
        "margin": CLIP_MARGIN}, indent=2), encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)

    # THE PACK MUST DEMONSTRATE WHAT IT SAYS IT DEMONSTRATES.
    faults = clipping_faults(good, bad, cap)
    faults += _other_findings(good_read, DEFAULTS, "in-range",
                              "a scan the README says runs to the end")
    faults += _other_findings(bad_read, DEFAULTS, "out-of-scale",
                              "a scan the README says trips one warning and "
                              "one only")
    print()
    if faults:
        for f in faults:
            print(f"REFUSING: {f}")
        shutil.rmtree(dest, ignore_errors=True)
        return 1
    print(f"in range {good * 100:.1f} % clipped, out of scale {bad * 100:.1f} %, "
          f"limit {cap * 100:.0f} %")
    print(f"written to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
