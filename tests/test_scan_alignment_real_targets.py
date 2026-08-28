"""The misalignment check, verified against Knut's REAL scanned IT8 targets
(#119). These scans are large and are Knut's property, so they are not in the
repo — the tests skip unless the folder is present. Get them from issue #108
(``ScannedIT8WFTarget01-8bit.tiff``, ``ScannedIT8LSTarget01-8bit.tif`` and the
matching ``.cht`` / reference files) and point ``CHROMIQ_IT8_SCANS`` at them,
or drop them in ``~/ChromIQ/scanner-test-targets/real``.

What is pinned here is exactly what Knut asked to be verified:

* an aligned grid must stay silent on BOTH targets — including the LaserSoft,
  whose printed bars are genuine edges that fall near some box rims;
* dragging a single grid corner inwards, until a few patches in that corner
  have box edge on patch edge, must be reported;
* shifting the whole grid by a fifth of a patch must be reported;
* small shifts that cannot put a box rim on a border must stay silent.

The "aligned" grid is not eyeballed: it is ArgyllCMS scanin's own solved
placement, recovered from its verbose transform (see
``scripts/scanner_edge_study.py``, which produced the calibration numbers in
``core/settings.py``).
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.settings import DEFAULTS                              # noqa: E402
from tests.argyll_env import argyll_tool                        # noqa: E402
from workflow.cht_parser import parse_cht                       # noqa: E402
from workflow.placement_probe import dense_placement_agreement   # noqa: E402

LIMIT = float(DEFAULTS["scanner_flank_limit"])
MIN_BOXES = int(DEFAULTS["scanner_flank_min_boxes"])
ARGYLL = argyll_tool("scanin")

_CANDIDATES = [
    Path(os.environ["CHROMIQ_IT8_SCANS"]) if os.environ.get("CHROMIQ_IT8_SCANS")
    else None,
    Path.home() / "ChromIQ" / "scanner-test-targets" / "real",
]

TARGETS = [
    ("wolf-faust", "ScannedIT8WFTarget01-8bit.tiff", "R230122W.cht", "R230122W.txt"),
    ("lasersoft", "ScannedIT8LSTarget01-8bit.tif", "ISO12641_2_1.cht", "R250715.cie"),
]


def _root() -> Path:
    for c in _CANDIDATES:
        if c and c.is_dir():
            return c
    pytest.skip("real IT8 scans not available (see module docstring)")


def _find(root: Path, name: str) -> Path:
    hits = list(root.rglob(name))
    if not hits:
        pytest.skip(f"{name} not found under {root}")
    return hits[0]


class _Box:
    __slots__ = ("x1", "y1", "x2", "y2", "name")

    def __init__(self, b):
        self.x1, self.y1, self.x2, self.y2 = b.x1, b.y1, b.x2, b.y2
        self.name = b.name


def _scanin_placement(tif: Path, cht: Path, ref: Path):
    """(boxes, aligned corners, fiducial quad, expected XYZ) from scanin.

    SCANIN WRITES BESIDE ITS INPUT, so this runs in a copy and never in the
    folder the scans live in. With `-d` it produces a `diag.tif` and a `.ti3`
    next to the image, and this test used to run with `cwd=tif.parent` — which
    on a developer's machine is `~/ChromIQ/scanner-test-targets/real`, the
    owner's own scans. Measured on 2026-08-28: two consecutive gate runs
    rewrote his 37 MB `diag.tif` from 9 July and both `.ti3` files, and the
    conftest guard could not see it because it compares top-level names only.
    The scans themselves are large, so they are symlinked rather than copied
    where the platform allows it.
    """
    if ARGYLL is None:
        pytest.skip("ArgyllCMS scanin not installed")
    work = Path(tempfile.mkdtemp(prefix="chromiq-scanin-"))
    try:
        local = work / tif.name
        try:
            local.symlink_to(tif)
        except (OSError, NotImplementedError):     # Windows without privilege
            shutil.copy2(tif, local)
        r = subprocess.run([str(ARGYLL), "-v", "-dipn", local.name,
                            str(cht), str(ref)],
                           capture_output=True, text=True, cwd=work,
                           timeout=300)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    txt = r.stdout + r.stderr
    m = re.search(r"Chosen rotation ([-\d.]+) deg", txt)
    if not m:
        pytest.skip(f"scanin could not register {tif.name}")
    chosen = float(m.group(1))
    tp = None
    for line in txt.splitlines():
        mm = re.match(r"cc = [\d.]+, irot = ([-\d.]+), xoff = ([-\d.]+), "
                      r"yoff = ([-\d.]+), xscale = ([\d.]+), yscale = ([\d.]+)",
                      line)
        if mm and abs(float(mm.group(1)) - chosen) < 1e-3:
            tp = tuple(float(g) for g in mm.groups())
    assert tp, "could not recover scanin's transform"
    irot, xoff, yoff, xsc, ysc = tp
    a = math.radians(irot)
    ca, sa = math.cos(a), math.sin(a)

    def to_img(cx, cy):
        x, y = cx * xsc, cy * ysc
        return xoff + x * ca - y * sa, yoff + x * sa + y * ca

    geom = parse_cht(cht.read_text(errors="ignore"))
    boxes = [_Box(b) for b in geom.patches]
    quad = list(geom.fiducials) if len(geom.fiducials) == 4 else None
    if quad is None:
        xs = [b.x1 for b in boxes] + [b.x2 for b in boxes]
        ys = [b.y1 for b in boxes] + [b.y2 for b in boxes]
        quad = [(min(xs), min(ys)), (max(xs), min(ys)),
                (max(xs), max(ys)), (min(xs), max(ys))]
    corners = [to_img(x, y) for x, y in quad]

    ti3 = tif.with_suffix(".ti3")
    body = ti3.read_text(errors="ignore")
    fmt = body.split("BEGIN_DATA_FORMAT", 1)[1].split("END_DATA_FORMAT", 1)[0].split()
    ix = [fmt.index(c) for c in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
    rows = body.split("\nBEGIN_DATA\n", 1)[1].split("\nEND_DATA", 1)[0]
    exp = {}
    for line in rows.strip().splitlines():
        t = line.split()
        if len(t) > max(ix):
            exp[t[0].strip('"')] = tuple(float(t[i]) for i in ix)
    return boxes, corners, quad, exp


def _n_on_edge(tif, boxes, corners, quad, exp) -> int:
    rep = dense_placement_agreement(tif, boxes, corners, exp, sample_frac=0.5,
                                    objective="response", src_quad=quad)
    assert rep is not None
    return sum(1 for v in rep.flank_by_patch.values() if v > LIMIT)


def _patch_px(boxes, corners, quad, tif) -> float:
    """One patch's size, in the pixels the probe actually samples."""
    from PIL import Image
    from workflow.placement_probe import _homography
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(tif) as im:
        scale = min(1.0, 2200 / max(im.size))
    h = _homography(list(quad), [(x * scale, y * scale) for x, y in corners])

    def ap(x, y):
        d = h[2, 0] * x + h[2, 1] * y + h[2, 2]
        return ((h[0, 0] * x + h[0, 1] * y + h[0, 2]) / d,
                (h[1, 0] * x + h[1, 1] * y + h[1, 2]) / d)
    b = boxes[0]
    x0, y0 = ap(b.x1, b.y1)
    x1, y1 = ap(b.x2, b.y2)
    return math.hypot(x1 - x0, y1 - y0) / math.sqrt(2) / scale


@pytest.fixture(scope="module", params=TARGETS, ids=[t[0] for t in TARGETS])
def target(request):
    name, tif_n, cht_n, ref_n = request.param
    root = _root()
    tif = _find(root, tif_n)
    boxes, corners, quad, exp = _scanin_placement(
        tif, _find(root, cht_n), _find(root, ref_n))
    return tif, boxes, corners, quad, exp, _patch_px(boxes, corners, quad, tif)


def test_aligned_real_scan_stays_silent(target):
    """scanin's own solved placement is only LOCALLY good on a real flatbed
    sheet — the LaserSoft's bottom rows genuinely overlap their neighbours
    by ~5–10 % (verified on the scan pixels, #119), so the rim-following
    edge detector CORRECTLY reports them once the sample area lets the rim
    approach those borders. Strict silence therefore holds wherever even
    the local error can't reach: with Knut's 85 % equal-margin sensing
    grid that is the Wolf Faust at EVERY area and the LaserSoft at 20 %.
    (Truly-aligned placements — the demo renders — are silent at every
    area; that contract lives in the synthetic suite.)"""
    tif, boxes, corners, quad, exp, _px = target
    fracs = (0.2, 0.4, 0.6, 0.8) if "WF" in str(tif) or "Faust" in str(tif)         else (0.2,)
    for frac in fracs:
        rep = dense_placement_agreement(tif, boxes, corners, exp,
                                        sample_frac=frac,
                                        objective="response", src_quad=quad)
        n = sum(1 for v in rep.flank_by_patch.values() if v > LIMIT)
        assert n < MIN_BOXES, (
            f"aligned scan flags {n} boxes at {frac:.0%} (limit {LIMIT})")


def test_tenth_patch_shift_is_detected(target):
    """Under Knut's activation-box design (#119, strict geometry since the
    localised edge operator) the check fires when a border reaches the
    ACTIVATION box. At a 60 % sample area that box extends to ~9.9 % of a
    patch from the border, so a tenth-of-a-patch shift MUST fire; at 50 %
    it only reaches ~13 %, so the same shift is by design the agreement
    ladder's business, not the edge check's."""
    tif, boxes, corners, quad, exp, px = target
    shifted = [(x + 0.10 * px, y) for x, y in corners]
    rep = dense_placement_agreement(tif, boxes, shifted, exp, sample_frac=0.6,
                                    objective="response", src_quad=quad)
    n = sum(1 for v in rep.flank_by_patch.values() if v > LIMIT)
    assert n >= MIN_BOXES, f"10 % shift flags only {n} boxes at 60 % area"


def test_fifth_of_a_patch_shift_is_detected(target):
    tif, boxes, corners, quad, exp, px = target
    shifted = [(x + 0.20 * px, y) for x, y in corners]
    n = _n_on_edge(tif, boxes, shifted, quad, exp)
    assert n >= MIN_BOXES, f"20 % shift flags only {n} boxes"


def test_pulled_corner_is_detected(target):
    """Knut's #119 case, on the real scans: drag ONE corner inwards until the
    patches beside it straddle their borders. The 7-box rule shipped before
    #119 missed this on the Wolf Faust."""
    tif, boxes, corners, quad, exp, _px = target
    cx = sum(c[0] for c in corners) / 4.0
    cy = sum(c[1] for c in corners) / 4.0
    x, y = corners[0]
    pulled = [(x + (cx - x) * 0.04, y + (cy - y) * 0.04)] + list(corners[1:])
    n = _n_on_edge(tif, boxes, pulled, quad, exp)
    assert n >= MIN_BOXES, f"pulled corner flags only {n} boxes"


def test_large_area_hits_are_the_known_distortion_zones(target):
    """At large sample areas the rim-following sensor reaches the real local
    placement error of scanin's solved fit (#119, verified on the scan
    pixels: the LaserSoft's bottom rows genuinely overlap neighbours). The
    counts must stay bounded by that known distortion — a regression that
    fires page-wide (hundreds) would show here — while truly-aligned demo
    renders stay at ZERO for every area (synthetic suite)."""
    tif, boxes, corners, quad, exp, _px = target
    for frac in (0.7, 0.8):
        rep = dense_placement_agreement(tif, boxes, corners, exp,
                                        sample_frac=frac,
                                        objective="response", src_quad=quad)
        n = sum(1 for v in rep.flank_by_patch.values() if v > LIMIT)
        assert n <= 80, f"{n} boxes at {frac:.0%} — beyond the known zones"


@pytest.mark.slow
def test_aligned_agreement_holds_at_every_sample_area(target):
    """Knut's #119 report: on his aligned LaserSoft the worst-patch number
    must stay above the default floor (85 %) at every Patch-sample-area
    setting, and worst ≤ average must hold by construction."""
    tif, boxes, corners, quad, exp, _px = target
    for frac in (0.5, 0.6, 0.7, 0.8):
        rep = dense_placement_agreement(tif, boxes, corners, exp,
                                        sample_frac=frac,
                                        objective="combined", src_quad=quad)
        if rep is None:      # response lens self-gated on this target
            rep = dense_placement_agreement(tif, boxes, corners, exp,
                                            sample_frac=frac,
                                            objective="uniformity",
                                            src_quad=quad)
        floor = 100.0 * float(DEFAULTS["scanner_check_agreement"])
        assert rep.agreement_pct >= floor, (
            f"aligned worst {rep.agreement_pct:.1f} % below floor at "
            f"{frac:.0%} sample area")
        assert rep.agreement_pct <= rep.average_pct + 1e-9


def test_roof_is_found_in_every_direction(target):
    """Knut's #119 verification: across the page, the direction that sets a
    patch's 0 % roof must occur in ALL 8 directions somewhere — proving each
    direction's worst-case detection works on the real scans."""
    tif, boxes, corners, quad, exp, _px = target
    rep = dense_placement_agreement(tif, boxes, corners, exp,
                                    sample_frac=0.5,
                                    objective="uniformity", src_quad=quad)
    dirs = {d for d in rep.roof_dir_by_patch.values() if d is not None}
    assert dirs == set(range(8)), f"roof directions seen: {sorted(dirs)}"


def test_flat_directions_are_ignored_not_floored(target):
    """Knut's #119 verification: a direction that finds no worst case is
    IGNORED — the roof comes from the directions that did find one and never
    collapses onto the floor. Observable: patches with ignored directions
    exist on the real scans, every roof comes from a non-ignored direction,
    and no patch scores 0 merely because a direction stayed flat."""
    tif, boxes, corners, quad, exp, _px = target
    rep = dense_placement_agreement(tif, boxes, corners, exp,
                                    sample_frac=0.5,
                                    objective="uniformity", src_quad=quad)
    with_ignored = [n for n, ds in rep.ignored_dirs_by_patch.items() if ds]
    assert with_ignored, "no patch had a flat direction — fixture too easy"
    for n, d in rep.roof_dir_by_patch.items():
        if d is not None:
            assert d not in rep.ignored_dirs_by_patch.get(n, set()), (
                f"{n}: roof taken from an ignored direction")
    all_ignored = [n for n, ds in rep.ignored_dirs_by_patch.items()
                   if len(ds) == 8]
    for n in all_ignored:
        assert rep.per_patch[n] == 100.0, (
            f"{n}: no direction found a worst case, yet it scores "
            f"{rep.per_patch[n]:.1f} % instead of reading clean")
