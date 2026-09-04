"""Put the marquee on the patches by itself, using ArgyllCMS's own recogniser.

ChromIQ reads a scan with ``scanin -F`` — four corners the user places by hand.
That is the robust path and it stays the one that does the reading. But the same
``scanin`` binary also has an *automatic* mode, and the ``.cht`` ChromIQ writes
carries the XLIST/YLIST edge lists that mode needs
(:mod:`workflow.layout_engine.cht_writer`). So the placement can be found by the
recogniser and then handed back to the marquee as four ordinary corners, which
the user can still drag.

**Where the corners come from.** At ``-v2`` ``scanin`` prints, for every
candidate chart rotation (``scanrd.c::calc_rotation``, guarded by ``verb >= 2``)::

    cc = .., irot = <deg>, xoff = .., yoff = .., xscale = .., yscale = ..

and ``compute_ptrans`` builds the reference→raster affine from exactly those
five numbers, then applies it to the bounding box of the ``.cht`` patch boxes —
which is the very quad ChromIQ's marquee is defined against, because
:func:`workflow.scanin_runner.cht_with_patchbox_fiducials` rewrites the ``F``
line to that bounding box. Reproducing those six lines of arithmetic
(:func:`corners_from_candidate`) turns Argyll's answer into ChromIQ's corners.

**No ``-p``.** With ``-p`` the transform additionally passes through
``ppersp()``, whose coefficients are *not* printed, so the recovered corners
would be an approximation of a number we cannot see. ChromIQ already runs the
manual path without ``-p`` for measured reasons (:mod:`workflow.scanin_runner`);
the automatic stage follows the same rule. Measured on a 2480x3508 synthetic
ChromIQ chart: 0.7 px worst corner error without ``-p``, 2.1 px with it.

**Two recogniser modes, and why the second one is not trusted on its own.**
By default ``scanin`` tries all four chart angles and refuses unless one clearly
wins — ``wcc < 0.5 * bcc`` in ``do_match``. A ChromIQ chart is a plain rectangle
of patches, so it is close to symmetric under 180 degrees, and that test fails
as soon as the sheet is a fraction of a degree off square. ``-a`` (normal
orientation only) skips the test — but it then returns an answer for *anything*,
including a chart the reference does not describe. So ``-a`` is used only as a
fallback and its answer must pass this module's own checks before it is offered.

**Nothing is applied without a check.** :func:`auto_align` scores every
candidate against the chart's own reference the way
:func:`ui.dialogs.scanin_dialog.scan_reference_correlation` scores a finished
read — a rank correlation between what the boxes see and what the chart is
known to be — and refuses when no candidate clears the floor or when the
candidate is not better than where the user's corners already are. A refusal
leaves the user's placement untouched.

**And one check that is not about colour at all.** Look again at
:func:`corners_from_candidate`: it builds the quad from a rotation and two
scales, so the quad's two edge vectors are orthogonal by construction. **The
placement this module can return is always a rotated RECTANGLE** — five degrees
of freedom where a placement needs eight — and a sheet photographed even
slightly off square is a keystone, which no rectangle is. Every check in the
paragraph above is then blind to it, because a rank correlation is blind to
shear: the patches keep their brightness ORDER while they slide onto their
neighbours. Measured with a pinhole camera at three sheet-widths and a compound
pitch+yaw tilt, this module accepted placements **0.921 of a patch pitch** out
at rho 0.98 (beta 8, B8-02). :func:`seating_drift` is the answer, and it asks
the patches rather than the colours.
"""
from __future__ import annotations

import math
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from core.logger import get_logger

log = get_logger(__name__)

__all__ = ["AutoAlignResult", "auto_align", "border_agreement",
           "chart_pitch", "orientation_scores", "plain_id",
           "corners_from_candidate", "expected_luminance", "parse_candidates",
           "chosen_index", "quad_is_sane", "reference_agreement_at",
           "seating_drift"]

# scanin -v2, scanrd.c::calc_rotation
_CAND_RE = re.compile(
    r"cc\s*=\s*([-\d.eE+]+),\s*irot\s*=\s*([-\d.eE+]+),\s*xoff\s*=\s*([-\d.eE+]+),"
    r"\s*yoff\s*=\s*([-\d.eE+]+),\s*xscale\s*=\s*([-\d.eE+]+),"
    r"\s*yscale\s*=\s*([-\d.eE+]+)")
_CHOSEN_RE = re.compile(r"Chosen rotation\s+([-\d.eE+]+)\s+deg")
_PLAIN_ID_RE = re.compile(r"([A-Za-z]+)0*(\d+)$")


def _split_row(line: str) -> list[str]:
    """CGATS data row -> fields, keeping a quoted field in one piece. Same
    split as :func:`workflow.scan_read_check._split_row`, because a reference
    read one way here and another way there would disagree about a chart
    neither of them is wrong about."""
    return re.findall(r'"[^"]*"|\S+', line)


def plain_id(sid: str) -> str:
    """``H01`` -> ``H1``. The same normalisation
    :func:`ui.dialogs.scanin_dialog._plain_id` applies, so a reference that
    zero-pads its ids still pairs with a ``.cht`` that does not."""
    m = _PLAIN_ID_RE.match(sid)
    return (m.group(1) + m.group(2)) if m else sid

#: Rank correlation a candidate must reach before it may replace the user's
#: corners. The shipped read-time checks call ≥0.8 "the reference can predict
#: this scan" and treat ≤0.33 as scrambled (#108); 0.80 is deliberately the
#: strict end, because this number is the only thing standing between a wrong
#: guess and a wrong profile.
AGREEMENT_FLOOR = 0.80

#: A candidate must beat the placement already on screen by this much before it
#: is worth moving anything.
IMPROVEMENT_MARGIN = 0.02

#: How far the best of the four chart orientations must beat the second best
#: before the sheet's direction counts as known. Measured over the targets
#: ChromIQ supports (``AUTO-ALIGN/exp/rotation_margin.py``): every chart with a
#: real orientation scored 0.26 or more (QPcard_202 0.26, ChromIQ 20x26 0.49,
#: ColorChecker 0.78, a square ChromIQ chart 0.98, SpyderChecker 1.10,
#: SpyderChecker24 1.16), and every chart built to be symmetric scored 0.000.
#: 0.15 sits in the gap, nearer the ambiguous end.
ORIENTATION_MARGIN = 0.15

#: How far, in PATCH PITCHES, the sheet's own patches may say the grid should
#: move before the answer is refused (:func:`seating_drift`). Every other gate
#: in this module is blind to a keystone, because the quad this module can
#: return is always a rotated rectangle (see :func:`corners_from_candidate`)
#: and a rank correlation is blind to shear -- the patches keep their
#: brightness ORDER while sliding onto their neighbours.
#:
#: **The window, measured over three populations, none of them scored by this
#: module's own opinion of itself.** 600 compound and single-axis camera views
#: of 25 targets (0-20 degrees, a pinhole at three sheet-widths); 216 CROSSED
#: views of six targets carrying a paper bow, a lens distortion and a tilt at
#: once; the 38-case challenge set at its own ground truth, Knut's two real
#: flatbed scans and nine legitimate degradations of his Wolf Faust sheet:
#:
#: * **328 placements that were CORRECT** -- worst error inside 0.113 pitch,
#:   where the sample box begins to overhang its patch -- read at most
#:   **0.0631**. That single worst one is a 24-patch half Passport at 15
#:   degrees; the next is 0.0583 (Knut's own scan with sigma-14 noise added),
#:   and his two untouched scans read 0.0175 and 0.0139.
#: * **106 placements that were more than HALF A PITCH out** -- the point at
#:   which a sample box reads the neighbouring patch -- read at least
#:   **0.0989**.
#:
#: **Every value from 0.065 to 0.095 gives the same two counts: 0 false
#: refusals out of 328, and 106 of 106 wrong answers refused.** 0.075 is near
#: the middle of that range (its geometric centre is 0.079) -- 1.19x above the
#: worst correct placement and 1.32x below the worst wrong one. It is a floor
#: with room on both sides, not a constant tuned until a case passed.
#:
#: What the choice inside the window trades is the middle band -- 0.25 to 0.5
#: pitch, where the box overhangs its patch but does not reach the neighbour.
#: 126 of 252 of those are refused at 0.075, 112 at 0.085, 134 at 0.065. That
#: is a judgement about how much a slightly overhanging read is worth, and it
#: is the one number here somebody may reasonably want moved.
SEATING_DRIFT_LIMIT = 0.075

#: The smallest dispersion, on the 0-255 luminance scale every image is read
#: on, that counts as a patch having anything to say about where it sits. One
#: level is what an 8-bit scan quantises to, so a difference below it is
#: arithmetic rather than evidence. It sits in the DENOMINATOR of the gain, so
#: it damps a near-flat patch smoothly instead of cutting it off at a second
#: threshold nobody measured.
_DISPERSION_FLOOR = 1.0

#: The share of each patch the drift measurement looks at, as an AREA -- the
#: same reading ``cht_with_sample_area`` gives the number, so the box measured
#: is the box ``scanin`` actually reads. Deliberately NOT the user's Sample
#: area spinbox: the question "are the patches where this grid says they are"
#: is a fact about the picture, and a safety gate whose sensitivity moves when
#: a user drags a spinbox is a safety gate that can be dragged open.
SEATING_SAMPLE_AREA = 0.60


@dataclass
class AutoAlignResult:
    """What the button found, and whether it may be used."""

    corners: list[tuple[float, float]] | None = None
    rho: float | None = None                 # agreement of the winning quad
    rho_before: float | None = None          # agreement where the user is now
    source: str = ""                         # "auto" | "auto -a" | ""
    reason: str = ""                         # machine-readable refusal reason
    candidates: int = 0
    #: how far the winning orientation beat the runner-up
    margin: "float | None" = None
    #: :func:`seating_drift` of the answer, in patch pitches -- recorded
    #: whether the answer was accepted or refused for it, so the log says how
    #: close a refusal was and a support question has a number to quote
    drift: "float | None" = None
    log_tail: str = ""
    rejected: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.corners is not None


# ---------------------------------------------------------------------------
# parsing scanin's own numbers
# ---------------------------------------------------------------------------
def parse_candidates(text: str) -> list[tuple[float, float, float, float,
                                              float, float]]:
    """Every ``cc = .., irot = .., …`` line, in the order scanin printed them."""
    return [tuple(float(v) for v in m.groups())  # type: ignore[misc]
            for m in _CAND_RE.finditer(text)]


def chosen_index(text: str, candidates: Sequence) -> int:
    """Index of the rotation scanin settled on. With a single candidate it
    prints no "Chosen rotation" line and uses the first."""
    last = None
    for last in _CHOSEN_RE.finditer(text):
        pass
    if last is None or not candidates:
        return 0
    want = float(last.group(1))
    return min(range(len(candidates)), key=lambda i: abs(candidates[i][1] - want))


def corners_from_candidate(candidate: Sequence[float],
                           bbox: tuple[float, float, float, float],
                           ) -> list[tuple[float, float]]:
    """``(cc, irot_deg, xoff, yoff, xscale, yscale)`` + the ``.cht`` patch-area
    bounding box → four raster corners in the marquee's TL, TR, BR, BL order.

    The arithmetic is ``scanrd.c::compute_ptrans``, lines 2946-2957."""
    _cc, irot_deg, xoff, yoff, xscale, yscale = candidate
    ir = math.radians(irot_deg)
    c, s = math.cos(ir), math.sin(ir)
    t0 = c * xoff + s * yoff
    t1 = xscale * c
    t2 = yscale * s
    t3 = -s * xoff + c * yoff
    t4 = xscale * -s
    t5 = yscale * c
    minx, miny, maxx, maxy = bbox
    ref = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)]
    return [(t0 + x * t1 + y * t2, t3 + x * t4 + y * t5) for x, y in ref]


# ---------------------------------------------------------------------------
# sanity + agreement
# ---------------------------------------------------------------------------
def quad_is_sane(corners: Sequence[tuple[float, float]],
                 image_size: tuple[int, int],
                 bbox: tuple[float, float, float, float],
                 aspect_tol: float = 0.12) -> str:
    """``""`` when the quad could plausibly be the patch area, else the reason
    it could not. Cheap geometry only — it catches the answers that are wrong
    by a mile before anything is sampled."""
    if len(corners) != 4:
        return "not four corners"
    w, h = image_size
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    if not all(map(math.isfinite, xs + ys)):
        return "not a number"
    pad = 0.02 * max(w, h)
    if min(xs) < -pad or min(ys) < -pad or max(xs) > w + pad or max(ys) > h + pad:
        return "outside the image"
    qw = max(xs) - min(xs)
    qh = max(ys) - min(ys)
    if qw < 8 or qh < 8:
        return "degenerate"
    if qw * qh < 0.02 * w * h:
        return "far too small for the sheet"
    rw = bbox[2] - bbox[0]
    rh = bbox[3] - bbox[1]
    if rw <= 0 or rh <= 0:
        return "chart has no area"
    want = rw / rh
    got = qw / qh
    # a 90-degree candidate legitimately swaps the aspect
    if min(abs(got / want - 1.0), abs(got * want - 1.0)) > aspect_tol:
        return "shape does not match the chart"
    return ""


def _spearman(a: Sequence[float], b: Sequence[float]) -> float | None:
    n = len(a)
    if n < 8:
        return None

    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = float(pos)
        return r
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra)
           * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else None


def _agreement(prepared, boxes: Sequence,
               corners: Sequence[tuple[float, float]],
               want: dict[str, float],
               sample_frac: float) -> "float | None":
    """The rank agreement for one placement, from an already-sampled image."""
    import numpy as np
    integ, wdt, hgt, scale = prepared
    minx = min(b.x1 for b in boxes)
    maxx = max(b.x2 for b in boxes)
    miny = min(b.y1 for b in boxes)
    maxy = max(b.y2 for b in boxes)
    src = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)]
    dst = [(x * scale, y * scale) for x, y in corners]
    a = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    try:
        _, _, vt = np.linalg.svd(np.asarray(a, dtype=float))
    except np.linalg.LinAlgError:
        return None
    h = vt[-1].reshape(3, 3)
    if not np.isfinite(h).all() or h[2, 2] == 0:
        return None
    h = h / h[2, 2]
    named = [b for b in boxes if plain_id(getattr(b, "name", "")) in want]
    if len(named) < 8:
        return None

    def warp(x, y):
        d = h[2, 0] * x + h[2, 1] * y + h[2, 2]
        if d == 0:
            return None
        return ((h[0, 0] * x + h[0, 1] * y + h[0, 2]) / d,
                (h[1, 0] * x + h[1, 1] * y + h[1, 2]) / d)

    read: list[float] = []
    ref: list[float] = []
    for b in named:
        cx, cy = (b.x1 + b.x2) / 2.0, (b.y1 + b.y2) / 2.0
        hx = (b.x2 - b.x1) * sample_frac / 2.0
        hy = (b.y2 - b.y1) * sample_frac / 2.0
        pa, pb = warp(cx - hx, cy - hy), warp(cx + hx, cy + hy)
        if pa is None or pb is None:
            continue
        x0 = int(math.floor(min(pa[0], pb[0])))
        x1 = int(math.ceil(max(pa[0], pb[0])))
        y0 = int(math.floor(min(pa[1], pb[1])))
        y1 = int(math.ceil(max(pa[1], pb[1])))
        if x0 < 0 or y0 < 0 or x1 > wdt or y1 > hgt or x1 - x0 < 2 or y1 - y0 < 2:
            continue
        s = integ[y1, x1] - integ[y0, x1] - integ[y1, x0] + integ[y0, x0]
        read.append(float(s) / ((x1 - x0) * (y1 - y0)))
        ref.append(want[plain_id(b.name)])
    if len(read) < max(8, len(named) // 2):
        return None
    return _spearman(read, ref)


def reference_agreement_at(image_path: Path, boxes: Sequence,
                           corners: Sequence[tuple[float, float]],
                           expected_y: dict[str, float],
                           sample_frac: float = 0.6,
                           max_side: int = 1400) -> "float | None":
    """Rank correlation between what the sample boxes would see at *corners*
    and the chart's known luminance -- the same question
    :func:`ui.dialogs.scanin_dialog.scan_reference_correlation` asks of a
    finished ``.ti3``, asked before anything is read.

    Sampling is the ``-F`` homography and the per-box mean over the sample
    area, exactly as :mod:`workflow.placement_probe` does it, so the number is
    comparable with the ones the Check-alignment step reports. Sample ids are
    paired on :func:`plain_id`, because scanin zero-pads and some bundled
    references are padded where the ``.cht`` is not."""
    prepared = _sampler(image_path, max_side)
    if prepared is None:
        return None
    want = {plain_id(k): v for k, v in expected_y.items()}
    return _agreement(prepared, boxes, corners, want, sample_frac)


def orientation_scores(image_path: Path, boxes: Sequence,
                       corners: Sequence[tuple[float, float]],
                       expected_y: dict[str, float],
                       sample_frac: float = 0.6,
                       max_side: int = 1400) -> "list[float | None]":
    """Score the four ways the chart can sit inside one quad.

    A quad is four points; which corner of the ``.cht`` each of them is decides
    whether the sheet is read upright, sideways or upside down. Rotating the
    corner ORDER leaves the quad exactly where it is and turns the chart inside
    it, so the four cyclic orderings ARE the four chart orientations, and each
    can be scored like any other placement. The image is sampled once for all
    four.

    The number that matters is the MARGIN between the best and the second best.
    A chart with a real orientation has a wide one; a chart that reads the same
    in every direction has none, and then there is no answer to give. Measured
    (``AUTO-ALIGN/exp/rotation_margin.py``): SpyderChecker24 1.16,
    SpyderChecker 1.10, ColorCheckerPassport 1.03, a square ChromIQ chart 0.98,
    ColorChecker 0.78, a 20x26 ChromIQ chart 0.49, QPcard_202 0.26 -- and a
    chart whose colours are deliberately symmetric under 180 degrees, 0.000."""
    prepared = _sampler(image_path, max_side)
    if prepared is None:
        return [None, None, None, None]
    want = {plain_id(k): v for k, v in expected_y.items()}
    return [_agreement(prepared, boxes,
                       list(corners[k:]) + list(corners[:k]),
                       want, sample_frac)
            for k in range(4)]


# ---------------------------------------------------------------------------
# the button's worker
# ---------------------------------------------------------------------------
def _run_scanin(runner, scanin_exe, workdir: Path, scan: Path, cht: Path,
                cie: Path, extra: Sequence[str], timeout: int) -> str:
    # Absolute paths: scanin runs with cwd set to the throwaway folder the
    # .ti3 is written into, so a relative scan path would resolve there.
    args = [str(scanin_exe), "-v2", "-O", "chromiq-autoalign.ti3", *extra,
            str(Path(scan).resolve()), str(Path(cht).resolve()),
            str(Path(cie).resolve())]
    log.debug("auto-align scanin: %s", " ".join(args))
    try:
        r = runner(args, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=str(workdir), timeout=timeout,
                   stdin=subprocess.DEVNULL)
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning("auto-align scanin failed to run: %s", exc)
        return ""
    out = (r.stdout or "") + (r.stderr or "")
    # scanin says WHY it gave up ("Pattern match wasn't good enough"), and it
    # says it on the way out with a non-zero code. Both used to be discarded,
    # so a refusal reached the log file as the single word "not-recognised"
    # and a user's report could not be told apart from a missing binary, an
    # unreadable chart or a recogniser that simply declined. Keep the code and
    # the last thing it said.
    if getattr(r, "returncode", 0):
        tail = [ln.strip() for ln in out.splitlines() if ln.strip()]
        log.info("auto-align scanin rc=%s: %s", r.returncode,
                 tail[-1] if tail else "(no output)")
    return out


def auto_align(scanin_exe: str | Path,
               scan: Path,
               cht: Path,
               cie: Path,
               boxes: Sequence,
               expected_y: dict[str, float],
               image_size: tuple[int, int],
               current_corners: Sequence[tuple[float, float]] | None = None,
               sample_frac: float = 0.6,
               floor: float = AGREEMENT_FLOOR,
               drift_limit: float = SEATING_DRIFT_LIMIT,
               search_region: "tuple[float, float, float, float] | None" = None,
               timeout: int = 300,
               runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
               ) -> AutoAlignResult:
    """Find the four marquee corners for *scan*, or refuse and say why.

    *boxes* are ``.cht`` patch boxes (:mod:`workflow.cht_parser`), *expected_y*
    maps each box name to the chart's known luminance, *current_corners* is
    where the user's quad sits now.

    *drift_limit* is the seating-drift limit this call refuses at, in patch
    pitches. It exists so :func:`workflow.scan_placement.place_grid` can SUSPEND
    the drift gate for the search and re-run it once, at the end, on the
    placement that is actually about to be applied -- the fit runs in between
    and a gate in the middle would throw away the very answer the fit is there
    to rescue. Measured over 290 starting placements, suspending it here and
    asking it last is what takes an 8-degree photograph three quarters of a
    patch out from "no button in the window can do this" to 0.112 pitch. Every
    caller that does not chain a fit onto the answer leaves it alone, and then
    this is :data:`SEATING_DRIFT_LIMIT` exactly as before. The measured drift is
    recorded on the result either way, so a suspended gate is still a number in
    the log.

    *search_region* ``(x0, y0, x1, y1)`` in image pixels narrows the search to
    a rectangle the user drew loosely round the chart. It is not a different
    algorithm: the image is cropped to that rectangle, the same recogniser runs
    on the crop, and the corners are shifted back. It exists because a
    PHOTOGRAPH often has other things in the frame, and everything outside the
    rectangle is then simply not there to be mistaken for a chart. The returned corners are in image pixels,
    marquee order, and are only non-``None`` when they beat both the floor and
    the placement already on screen."""
    import tempfile

    if not boxes:
        return AutoAlignResult(reason="no-chart-geometry")
    bbox = (min(b.x1 for b in boxes), min(b.y1 for b in boxes),
            max(b.x2 for b in boxes), max(b.y2 for b in boxes))

    tmp = Path(tempfile.mkdtemp(prefix="chromiq-autoalign-"))
    seen: list[tuple[str, list[tuple[float, float]]]] = []
    log_tail = ""
    look_at = scan
    off = (0.0, 0.0)
    try:
        if search_region is not None:
            from PIL import Image
            x0, y0, x1, y1 = (float(v) for v in search_region)
            box = (int(max(0, min(x0, x1))), int(max(0, min(y0, y1))),
                   int(max(x0, x1)), int(max(y0, y1)))
            try:
                with Image.open(scan) as im:
                    Image.MAX_IMAGE_PIXELS = None
                    crop = im.crop(box)
                    look_at = tmp / "region.tif"
                    crop.save(look_at)
                off = (float(box[0]), float(box[1]))
            except Exception:  # noqa: BLE001 — a bad rectangle is not a crash
                log.warning("auto align could not crop to the region",
                            exc_info=True)
                look_at, off = scan, (0.0, 0.0)
    except Exception:  # noqa: BLE001
        look_at, off = scan, (0.0, 0.0)
    try:
        for extra, source in (((), "auto"), (("-a",), "auto -a")):
            text = _run_scanin(runner, scanin_exe, tmp, look_at, cht, cie,
                               extra, timeout)
            log_tail = "\n".join(
                [ln for ln in text.strip().splitlines() if ln.strip()][-3:])
            cands = parse_candidates(text)
            if not cands:
                continue
            best_i = chosen_index(text, cands)
            order = [best_i] + [i for i in range(len(cands)) if i != best_i]
            for i in order:
                q = corners_from_candidate(cands[i], bbox)
                seen.append((source, [(x + off[0], y + off[1]) for x, y in q]))
            if source == "auto":
                # Argyll's own four-way discrimination accepted this image;
                # there is no need for the ungated -a pass.
                break
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    if not seen:
        return AutoAlignResult(reason="not-recognised", log_tail=log_tail)

    rho_before = None
    if current_corners:
        rho_before = reference_agreement_at(scan, boxes, current_corners,
                                            expected_y, sample_frac)

    rejected: list[str] = []
    ambiguous = False
    best_margin = None
    best: tuple[float, str, list[tuple[float, float]]] | None = None
    for source, quad in seen:
        why = quad_is_sane(quad, image_size, bbox)
        if why:
            rejected.append(f"{source}: {why}")
            continue
        # Which way up is the sheet? The four cyclic orderings of this quad are
        # the four chart orientations; score them all and take the best, but
        # only when it BEATS the runner-up. A chart that reads the same in
        # every direction has no answer, and picking one of four at random is
        # worse than not picking: a wrong orientation reads every patch as
        # another patch and the profile comes out confidently wrong.
        scores = orientation_scores(scan, boxes, quad, expected_y, sample_frac)
        ranked = sorted(
            ((-9.0 if s is None else s, k) for k, s in enumerate(scores)),
            reverse=True)
        rho, k = ranked[0]
        margin = rho - ranked[1][0]
        if rho <= -9.0:
            rejected.append(f"{source}: could not be measured")
            continue
        turned = list(quad[k:]) + list(quad[:k])
        if margin < ORIENTATION_MARGIN:
            rejected.append(f"{source}: the chart reads the same more than one "
                            f"way up (margin {margin:.2f})")
            ambiguous = True
            continue
        # The second gate, and the one that sees what a rank correlation
        # cannot: a placement shifted by a whole patch pitch reads every patch
        # as its neighbour, and on a chart whose patches step smoothly the
        # ranks survive that. The chart's outer boundary does not.
        if border_agreement(scan, boxes, turned) is False:
            rejected.append(f"{source}: the grid's edges are not the chart's")
            continue
        if best is None or rho > best[0]:
            best = (rho, source, turned)
            best_margin = margin

    if best is None:
        return AutoAlignResult(
            reason="ambiguous-orientation" if ambiguous else "no-usable-candidate",
            rho_before=rho_before, candidates=len(seen), log_tail=log_tail,
            rejected=rejected)
    rho, source, quad = best
    if rho < floor:
        return AutoAlignResult(reason="below-floor", rho=rho,
                               rho_before=rho_before, source=source,
                               candidates=len(seen), log_tail=log_tail,
                               rejected=rejected)
    if rho_before is not None and rho < rho_before + IMPROVEMENT_MARGIN:
        return AutoAlignResult(reason="no-better", rho=rho,
                               rho_before=rho_before, source=source,
                               candidates=len(seen), log_tail=log_tail,
                               rejected=rejected)
    # THE LAST GATE, AND THE ONLY ONE THAT CAN SEE A KEYSTONE.
    # Everything above scores the placement against the chart's colours, and
    # the quad reaching this line is always a rotated rectangle
    # (:func:`corners_from_candidate`), so on a sheet photographed off square
    # it is wrong in a way none of those checks can express: a rank
    # correlation is blind to shear. Measured with a pinhole camera at three
    # sheet-widths, compound pitch+yaw, this module accepted placements
    # **0.921 of a patch pitch** out at rho 0.98 and told the user the grid
    # agreed with the chart "to 0.98, where anything below 0.80 is refused".
    # Ask the patches instead. This runs once, on the winner, because every
    # candidate is the same rectangle at a different rotation.
    drift = None
    try:
        drift = seating_drift(scan, boxes, quad)
    except Exception:  # noqa: BLE001 — a safety check must not become a crash
        log.warning("auto align could not measure the seating drift",
                    exc_info=True)
    if drift is not None and drift > drift_limit:
        rejected.append(f"{source}: the patches do not sit where this grid "
                        f"puts them (drift {drift:.3f} pitch)")
        return AutoAlignResult(reason="not-seated", rho=rho,
                               rho_before=rho_before, source=source,
                               candidates=len(seen), log_tail=log_tail,
                               rejected=rejected, margin=best_margin,
                               drift=drift)
    return AutoAlignResult(corners=quad, rho=rho, rho_before=rho_before,
                           source=source, candidates=len(seen),
                           log_tail=log_tail, rejected=rejected,
                           margin=best_margin, drift=drift)


# ---------------------------------------------------------------------------
def expected_luminance(cht_text: str, cie: Path | None = None,
                       chart_ids: "Sequence[str] | None" = None) -> dict[str, float]:
    """``{patch name: reference Y}`` for the agreement check.

    **The reference file wins when it describes at least as much of the chart.**
    A ``.cht``'s ``EXPECTED`` block is approximate and generic — ArgyllCMS's own
    ``cht_format.html`` says of it, in capitals, "NOTE that these are not color
    reference values!" — while the ``.cie`` / ``.txt`` / ``.ti3`` is the colour
    of the sheet actually in front of the user.

    This used to prefer the ``.cht`` unconditionally, and it made "Try with a
    demo scan" fail on every target whose ``.cht`` carries an ``EXPECTED``
    block: the demo image is painted in :func:`standard_targets.demo_patch_color`'s
    deliberately scrambled colours, so scoring it against the REAL target's
    colours gave rank agreements of 0.049 (ColorCheckerSG) and orientation
    margins of 0.03-0.07 where 0.15 is needed. Auto align refused, correctly,
    a placement that is pixel-perfect. ChromIQ's own eight bundled targets
    carry no ``EXPECTED`` block, so they fell back to the demo's ``.cie`` and
    passed — which is why the fault looked like "the small ColorChecker ones
    don't work" when it is really "the ones with an EXPECTED block don't".

    The ``EXPECTED`` block is still used when there is no reference, or when it
    describes more of the chart than the reference does — a short or unreadable
    reference must not throw away colours the chart already knows."""
    out: dict[str, float] = {}
    lines = cht_text.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("EXPECTED XYZ"):
            try:
                n = int(s.split()[-1])
            except ValueError:
                break
            for j in range(i + 1, min(i + 1 + n, len(lines))):
                t = lines[j].split()
                if len(t) >= 4:
                    try:
                        out[t[0]] = float(t[2])
                    except ValueError:
                        continue
            break
    if cie is None:
        return out
    from_cht, out = out, {}
    from core.text_io import read_text
    try:
        text = read_text(cie, lenient=True)
    except OSError:
        return from_cht
    rows = text.splitlines()
    try:
        fb = next(i for i, l in enumerate(rows)
                  if l.strip().upper() == "BEGIN_DATA_FORMAT")
        fields = [f.upper() for f in _split_row(rows[fb + 1])]
        # WHICH COLUMN CARRIES THE PATCH NAME. The same rule
        # :func:`workflow.scan_read_check.reference_patch_ids` applies, and
        # kept deliberately in step with it: a `.cie` / `.txt` names the patch
        # in SAMPLE_ID, while a `.ti3` — the shape `cxf2ti3` and `txt2ti3`
        # produce, and the shape LaserSoft's own reference comes in — numbers
        # its rows in SAMPLE_ID and puts the name in SAMPLE_LOC. Reading
        # SAMPLE_ID unconditionally paired 0 of 864 LaserSoft patches with the
        # chart, so every candidate scored None and Auto align refused with a
        # perfectly good placement in its hand.
        if "SAMPLE_LOC" in fields:
            li = fields.index("SAMPLE_LOC")
        else:
            li = fields.index("SAMPLE_ID")
        # Y, or L* when the reference carries no XYZ. Only the RANK of these
        # numbers is ever used (:func:`_spearman`), and L* is monotone in Y, so
        # the two give the identical correlation — this widens what can be read
        # without changing any answer.
        yi = fields.index("XYZ_Y") if "XYZ_Y" in fields else fields.index("LAB_L")
        db = next(i for i, l in enumerate(rows) if l.strip().upper() == "BEGIN_DATA")
        de = next(i for i, l in enumerate(rows[db:], db)
                  if l.strip().upper() == "END_DATA")
    except (StopIteration, ValueError, IndexError):
        return from_cht
    for line in rows[db + 1:de]:
        t = _split_row(line)
        if len(t) > max(li, yi):
            try:
                out[t[li].strip('"')] = float(t[yi])
            except ValueError:
                continue
    # The reference wins on a tie, because it is the sheet in front of the user
    # rather than the chart's generic idea of it; the EXPECTED block wins when
    # it names MORE of the chart, so a short or half-read reference can never
    # lose colours the .cht already had.
    #
    # Compared on HOW MANY OF THE CHART'S OWN PATCHES each side names, not on
    # row count. A reference can be long and still name nothing the chart knows
    # — LaserSoft's R250715.cie carries 864 rows numbered 1..864 with the name
    # in SAMPLE_LOC — so counting rows would let it displace a good EXPECTED
    # block with keys no box can match.
    #
    # *chart_ids* is the chart's real box names. Without them the EXPECTED
    # block's own keys stand in for the chart, and that proxy can itself be
    # wrong: CMP_Digital_Target-7 names its boxes "2A01" while its EXPECTED
    # block says "A1", covering only 534 of 570 patches — the reference covered
    # all 570 and still lost, and every orientation then scored ~0.00 because
    # the demo image was being judged against colours belonging to other
    # patches. Ask the chart rather than guessing from one of the answers.
    # `plain_id` throughout because a .cht zero-pads ("A01") where a reference
    # often does not ("A1").
    known = ({plain_id(k) for k in chart_ids} if chart_ids
             else {plain_id(k) for k in from_cht})

    def _covers(m: dict) -> int:
        return len(known & {plain_id(k) for k in m})

    return out if _covers(out) >= _covers(from_cht) else from_cht


# ---------------------------------------------------------------------------
def _sampler(image_path: Path, max_side: int = 1400):
    """(luminance integral image, width, height, scale) for one scan."""
    import numpy as np
    from PIL import Image
    try:
        img = Image.open(image_path)
        img.load()
    except Exception:  # noqa: BLE001
        return None
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    scale = min(1.0, max_side / max(img.size))
    if scale < 1.0:
        img = img.resize((max(1, int(img.width * scale)),
                          max(1, int(img.height * scale))))
    arr = np.asarray(img, dtype=np.float64)
    lum = ((0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2])
           if arr.ndim == 3 else arr)
    h, w = lum.shape
    integ = np.zeros((h + 1, w + 1))
    integ[1:, 1:] = np.cumsum(np.cumsum(lum, axis=0), axis=1)
    return integ, w, h, scale


def border_agreement(image_path: Path, boxes: Sequence,
                     corners: Sequence[tuple[float, float]],
                     sides_needed: int = 3,
                     ratio: float = 0.40) -> bool | None:
    """Does the quad's OUTSIDE look like paper and its INSIDE look like patches?

    A rank correlation cannot see a placement shifted by a whole patch pitch on
    a chart whose patches step smoothly — every box still reads a patch, and
    the ranks survive. What does not survive is the chart's own outer boundary:
    shift the grid by a pitch and one edge of it walks off the printed block
    onto bare paper, while the opposite edge samples the sheet.

    So each side is sampled twice, in the ``.cht``'s own coordinates: a band
    just inside the patch area, and a band a patch further out. On a correct
    placement the outer band is one flat colour and the inner band steps from
    patch to patch. *sides_needed* of the four must show the outer band at most
    *ratio* as varied as the inner one -- three, not four, because a ChromIQ
    sheet carries its strip labels below the patch block.

    ``None`` when the image cannot be read; then the caller has only the
    reference agreement to go on."""
    import numpy as np
    got = _sampler(image_path)
    if got is None or not boxes:
        return None
    integ, w, h, scale = got
    minx = min(b.x1 for b in boxes)
    maxx = max(b.x2 for b in boxes)
    miny = min(b.y1 for b in boxes)
    maxy = max(b.y2 for b in boxes)
    src = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)]
    dst = [(x * scale, y * scale) for x, y in corners]
    a = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    try:
        _, _, vt = np.linalg.svd(np.asarray(a, dtype=float))
    except np.linalg.LinAlgError:
        return None
    hm = vt[-1].reshape(3, 3)
    if not np.isfinite(hm).all() or hm[2, 2] == 0:
        return None
    hm = hm / hm[2, 2]

    def warp(x, y):
        d = hm[2, 0] * x + hm[2, 1] * y + hm[2, 2]
        if d == 0:
            return None
        return ((hm[0, 0] * x + hm[0, 1] * y + hm[0, 2]) / d,
                (hm[1, 0] * x + hm[1, 1] * y + hm[1, 2]) / d)

    pw = float(np.median([b.x2 - b.x1 for b in boxes])) or 1.0
    ph = float(np.median([b.y2 - b.y1 for b in boxes])) or 1.0

    def cell_mean(x0, y0, x1, y1):
        pa, pb = warp(x0, y0), warp(x1, y1)
        if pa is None or pb is None:
            return None
        ax = int(math.floor(min(pa[0], pb[0])))
        bx = int(math.ceil(max(pa[0], pb[0])))
        ay = int(math.floor(min(pa[1], pb[1])))
        by = int(math.ceil(max(pa[1], pb[1])))
        if ax < 0 or ay < 0 or bx > w or by > h or bx - ax < 1 or by - ay < 1:
            return None
        s = integ[by, bx] - integ[ay, bx] - integ[by, ax] + integ[ay, ax]
        return float(s) / ((bx - ax) * (by - ay))

    def band(axis: str, lo: float, hi: float, n: int = 24):
        vals = []
        for i in range(n):
            if axis in ("top", "bottom"):
                x0 = minx + (maxx - minx) * i / n
                x1 = minx + (maxx - minx) * (i + 1) / n
                y0, y1 = (lo, hi)
            else:
                y0 = miny + (maxy - miny) * i / n
                y1 = miny + (maxy - miny) * (i + 1) / n
                x0, x1 = (lo, hi)
            v = cell_mean(x0, y0, x1, y1)
            if v is not None:
                vals.append(v)
        return float(np.std(vals)) if len(vals) >= n // 2 else None

    sides = [
        ("top", (miny + 0.05 * ph, miny + 0.45 * ph),
         (miny - 0.90 * ph, miny - 0.30 * ph)),
        ("bottom", (maxy - 0.45 * ph, maxy - 0.05 * ph),
         (maxy + 0.30 * ph, maxy + 0.90 * ph)),
        ("left", (minx + 0.05 * pw, minx + 0.45 * pw),
         (minx - 0.90 * pw, minx - 0.30 * pw)),
        ("right", (maxx - 0.45 * pw, maxx - 0.05 * pw),
         (maxx + 0.30 * pw, maxx + 0.90 * pw)),
    ]
    good = 0
    seen = 0
    for name, ins, out in sides:
        si = band(name, *ins)
        so = band(name, *out)
        if si is None or so is None:
            continue
        seen += 1
        if so <= ratio * si:
            good += 1
    if seen == 0:
        return None
    return good >= min(sides_needed, seen)



# ---------------------------------------------------------------------------
def _sampler_sq(image_path: Path, max_side: int = 2000):
    """(sum, sum-of-squares, w, h, scale) for one scan.

    :func:`_sampler`'s sibling. It carries the second integral image, which is
    what turns a per-box mean into a per-box standard deviation in constant
    time, and it is separate rather than folded in because every other caller
    in this module wants means only and would pay twice for nothing.
    """
    import numpy as np
    from PIL import Image
    try:
        img = Image.open(image_path)
        img.load()
    except Exception:  # noqa: BLE001
        return None
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    scale = min(1.0, max_side / max(img.size))
    if scale < 1.0:
        img = img.resize((max(1, int(img.width * scale)),
                          max(1, int(img.height * scale))), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float64)
    lum = ((0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2])
           if arr.ndim == 3 else arr)
    h, w = lum.shape
    i1 = np.zeros((h + 1, w + 1))
    i2 = np.zeros((h + 1, w + 1))
    i1[1:, 1:] = np.cumsum(np.cumsum(lum, axis=0), axis=1)
    i2[1:, 1:] = np.cumsum(np.cumsum(lum * lum, axis=0), axis=1)
    return i1, i2, w, h, scale


def chart_pitch(boxes: Sequence) -> tuple[float, float]:
    """(pitch x, pitch y) in the ``.cht``'s own units — the smallest step from
    one box's edge to the next one's. Falls back to the median box size on a
    chart with a single column or row."""
    import numpy as np
    xs = sorted({round(b.x1, 3) for b in boxes})
    ys = sorted({round(b.y1, 3) for b in boxes})
    dx = min((xs[i + 1] - xs[i] for i in range(len(xs) - 1)), default=0.0)
    dy = min((ys[i + 1] - ys[i] for i in range(len(ys) - 1)), default=0.0)
    if dx <= 0:
        dx = float(np.median([b.x2 - b.x1 for b in boxes]))
    if dy <= 0:
        dy = float(np.median([b.y2 - b.y1 for b in boxes]))
    return float(dx or 1.0), float(dy or 1.0)


def seating_drift(image_path: Path, boxes: Sequence,
                  corners: Sequence[tuple[float, float]],
                  sample_frac: float = SEATING_SAMPLE_AREA,
                  max_side: int = 2000,
                  reach: float = 0.5, step: float = 0.0625) -> "float | None":
    """How far the sheet's own patches say this grid should move, in PITCHES.

    **Why anything new is needed.** Look at what :func:`corners_from_candidate`
    builds out of the five numbers ``scanin`` prints::

        t1 = xscale*cos   t2 = yscale*sin
        t4 = -xscale*sin  t5 = yscale*cos

    The quad's two edge vectors are ``xscale*(cos, -sin)`` and
    ``yscale*(sin, cos)``, whose dot product is exactly zero. **The quad this
    module can return is always a rotated rectangle** — five degrees of freedom
    where a placement needs eight. It cannot express a keystone at any tilt, so
    on a photograph taken even slightly off square the returned grid is
    systematically wrong, worst at one corner and right in the middle. And
    every gate above lets it through: a rank correlation is blind to shear,
    because the patches keep their brightness ORDER while they slide onto their
    neighbours, and :func:`border_agreement` only looks at the sheet's outer
    boundary, which a small keystone barely moves.

    **What this measures instead.** A sample box that sits on its patch sees
    one flat colour and cannot be improved by moving. A box straddling a border
    sees two, and its dispersion drops sharply as soon as it is moved onto
    either side. So for every box in the ``.cht``, search a grid of offsets in
    CHART coordinates for the one that minimises the dispersion inside it, and
    shrink each answer by how much moving actually helped, so a patch whose
    neighbours happen to be the same colour — where the argmin is noise —
    contributes nothing and no "is this box voting" threshold has to be
    guessed.

    Then average those shrunk offsets over regions of the chart and take the
    largest region's magnitude. Noise cancels inside a region; a keystone does
    not, because its error field is smooth and grows towards one corner.

    Returns the drift in patch pitches, or ``None`` when the image cannot be
    read or the chart is too small to divide into regions — and ``None`` means
    *"no evidence either way"*, never *"refuse"*.

    **Two honest limits.** It saturates: a patch more than half a pitch out has
    locked onto its neighbour and reports a small offset, so the number stops
    growing past about 0.27 and is not an estimate of the corner error. And it
    is blind where the chart is: a region whose patches are all the same colour
    has nothing to say.
    """
    import numpy as np
    got = _sampler_sq(image_path, max_side)
    if got is None or not boxes or len(boxes) < 12:
        return None
    i1, i2, w, h, scale = got
    side = math.sqrt(max(1e-9, min(1.0, float(sample_frac))))
    minx = min(b.x1 for b in boxes)
    maxx = max(b.x2 for b in boxes)
    miny = min(b.y1 for b in boxes)
    maxy = max(b.y2 for b in boxes)
    src = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)]
    dst = [(x * scale, y * scale) for x, y in corners]
    a = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    try:
        _, _, vt = np.linalg.svd(np.asarray(a, dtype=float))
    except np.linalg.LinAlgError:
        return None
    hm = vt[-1].reshape(3, 3)
    if not np.isfinite(hm).all() or hm[2, 2] == 0:
        return None
    hm = hm / hm[2, 2]

    def warp(x, y):
        d = hm[2, 0] * x + hm[2, 1] * y + hm[2, 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            return ((hm[0, 0] * x + hm[0, 1] * y + hm[0, 2]) / d,
                    (hm[1, 0] * x + hm[1, 1] * y + hm[1, 2]) / d)

    px, py = chart_pitch(boxes)
    cx = np.array([(b.x1 + b.x2) / 2.0 for b in boxes])
    cy = np.array([(b.y1 + b.y2) / 2.0 for b in boxes])
    hx = np.array([(b.x2 - b.x1) * side / 2.0 for b in boxes])
    hy = np.array([(b.y2 - b.y1) * side / 2.0 for b in boxes])

    ns = max(1, int(round(reach / step)))
    offs = np.arange(-ns, ns + 1) * step
    du, dv = np.meshgrid(offs, offs, indexing="ij")
    du = du.ravel() * px
    dv = dv.ravel() * py
    ux = cx[:, None] + du[None, :]
    uy = cy[:, None] + dv[None, :]
    xs = np.stack([ux - hx[:, None], ux + hx[:, None],
                   ux + hx[:, None], ux - hx[:, None]], axis=0)
    ys = np.stack([uy - hy[:, None], uy - hy[:, None],
                   uy + hy[:, None], uy + hy[:, None]], axis=0)
    wx, wy = warp(xs, ys)
    finite = np.isfinite(wx).all(axis=0) & np.isfinite(wy).all(axis=0)
    with np.errstate(invalid="ignore"):
        x0 = np.floor(np.nanmin(wx, axis=0))
        x1 = np.ceil(np.nanmax(wx, axis=0))
        y0 = np.floor(np.nanmin(wy, axis=0))
        y1 = np.ceil(np.nanmax(wy, axis=0))
    inside = (finite & (x0 >= 0) & (y0 >= 0) & (x1 <= w) & (y1 <= h)
              & (x1 - x0 >= 3) & (y1 - y0 >= 3))
    x0 = np.clip(np.nan_to_num(x0), 0, w).astype(np.int64)
    x1 = np.clip(np.nan_to_num(x1), 0, w).astype(np.int64)
    y0 = np.clip(np.nan_to_num(y0), 0, h).astype(np.int64)
    y1 = np.clip(np.nan_to_num(y1), 0, h).astype(np.int64)
    n = np.maximum(1, (x1 - x0) * (y1 - y0))
    s1 = i1[y1, x1] - i1[y0, x1] - i1[y1, x0] + i1[y0, x0]
    s2 = i2[y1, x1] - i2[y0, x1] - i2[y1, x0] + i2[y0, x0]
    std = np.sqrt(np.maximum(0.0, s2 / n - (s1 / n) ** 2))
    std = np.where(inside, std, np.inf)
    zero = du.size // 2
    std0 = std[:, zero]
    best = np.argmin(std, axis=1)
    stdbest = std[np.arange(len(boxes)), best]
    usable = np.isfinite(std0) & np.isfinite(stdbest)
    if int(usable.sum()) < 12:
        return None
    # HOW MUCH MOVING ACTUALLY HELPED, with a floor under the denominator.
    # `(std0 - stdbest) / std0` alone is a trap: a patch that is perfectly flat
    # at the placement has std0 = 0, every offset ties, and the ratio reports a
    # confident 1.0 about pure tie-breaking. Measured on a synthetic chart
    # drawn in exact flat colours, that put a CORRECT placement at 0.088 -- a
    # false refusal from a chart with nothing wrong with it. One luminance
    # level out of 255 is the smallest difference an 8-bit scan can even carry,
    # so anything under it is not evidence.
    safe0 = np.where(usable, std0, 0.0)
    safeb = np.where(usable, stdbest, 0.0)
    gain = np.clip((safe0 - safeb) / (safe0 + _DISPERSION_FLOOR), 0.0, 1.0)
    su = (du[best] / px) * gain
    sv = (dv[best] / py) * gain

    # Regions, sized so each holds enough patches for its mean to mean
    # something. A 500-patch IT8 gets 4x4; a 24-patch ColorChecker gets 2x2,
    # and a chart with fewer than four patches to a region is not divided.
    #
    # THE CAP IS 4 AND IT WAS MEASURED, not chosen. A region is averaged over,
    # so a region that spans a third of the sheet dilutes an error that grows
    # towards one corner -- which is exactly what a lens distortion does, since
    # it grows radially and continuously. Re-scored at every cap from one set
    # of offsets: worst correct placement / lowest wrong one =
    # 0.0631 / 0.0647 at 2 (no window at all), 0.0631 / 0.0888 at 3,
    # **0.0631 / 0.1469 at 4**, 0.0755 / 0.1542 at 5, 0.0924 / 0.1542 at 6.
    # Four is the widest window, and it is the first cap that sees the
    # lens-distortion cases at all: at 3 it caught 0 of the 19 crossed
    # bow+lens+tilt placements sitting 0.25-0.5 pitch out, at 4 it catches 12.
    fx = (cx - cx.min()) / max(1e-9, cx.max() - cx.min())
    fy = (cy - cy.min()) / max(1e-9, cy.max() - cy.min())
    grid = max(1, min(4, int(math.sqrt(int(usable.sum()) / 6.0))))
    worst = 0.0
    seen = 0
    for i in range(grid):
        for j in range(grid):
            m = (usable
                 & (fx >= i / grid) & (fx <= (i + 1) / grid)
                 & (fy >= j / grid) & (fy <= (j + 1) / grid))
            if int(m.sum()) < 4:
                continue
            seen += 1
            worst = max(worst, math.hypot(float(su[m].mean()),
                                          float(sv[m].mean())))
    if seen == 0:
        return None
    return float(worst)
