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
           "orientation_scores", "plain_id",
           "corners_from_candidate", "expected_luminance", "parse_candidates",
           "chosen_index", "quad_is_sane", "reference_agreement_at"]

# scanin -v2, scanrd.c::calc_rotation
_CAND_RE = re.compile(
    r"cc\s*=\s*([-\d.eE+]+),\s*irot\s*=\s*([-\d.eE+]+),\s*xoff\s*=\s*([-\d.eE+]+),"
    r"\s*yoff\s*=\s*([-\d.eE+]+),\s*xscale\s*=\s*([-\d.eE+]+),"
    r"\s*yscale\s*=\s*([-\d.eE+]+)")
_CHOSEN_RE = re.compile(r"Chosen rotation\s+([-\d.eE+]+)\s+deg")
_PLAIN_ID_RE = re.compile(r"([A-Za-z]+)0*(\d+)$")


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
    try:
        r = runner(args, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=str(workdir), timeout=timeout,
                   stdin=subprocess.DEVNULL)
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning("auto-align scanin failed: %s", exc)
        return ""
    return (r.stdout or "") + (r.stderr or "")


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
               timeout: int = 300,
               runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
               ) -> AutoAlignResult:
    """Find the four marquee corners for *scan*, or refuse and say why.

    *boxes* are ``.cht`` patch boxes (:mod:`workflow.cht_parser`), *expected_y*
    maps each box name to the chart's known luminance, *current_corners* is
    where the user's quad sits now. The returned corners are in image pixels,
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
    try:
        for extra, source in (((), "auto"), (("-a",), "auto -a")):
            text = _run_scanin(runner, scanin_exe, tmp, scan, cht, cie,
                               extra, timeout)
            log_tail = "\n".join(
                [ln for ln in text.strip().splitlines() if ln.strip()][-3:])
            cands = parse_candidates(text)
            if not cands:
                continue
            best_i = chosen_index(text, cands)
            order = [best_i] + [i for i in range(len(cands)) if i != best_i]
            for i in order:
                seen.append((source, corners_from_candidate(cands[i], bbox)))
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
    return AutoAlignResult(corners=quad, rho=rho, rho_before=rho_before,
                           source=source, candidates=len(seen),
                           log_tail=log_tail, rejected=rejected,
                           margin=best_margin)


# ---------------------------------------------------------------------------
def expected_luminance(cht_text: str, cie: Path | None = None) -> dict[str, float]:
    """``{patch name: reference Y}`` for the agreement check.

    Prefers the ``.cht``'s own ``EXPECTED XYZ`` block (every chart ChromIQ
    writes has one, as do Argyll's bundled targets); falls back to the ``.cie``
    when a hand-made ``.cht`` carries none."""
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
    if out or cie is None:
        return out
    try:
        text = cie.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    rows = text.splitlines()
    try:
        fb = next(i for i, l in enumerate(rows)
                  if l.strip() == "BEGIN_DATA_FORMAT")
        fields = rows[fb + 1].split()
        li = fields.index("SAMPLE_ID")
        yi = fields.index("XYZ_Y")
        db = next(i for i, l in enumerate(rows) if l.strip() == "BEGIN_DATA")
        de = next(i for i, l in enumerate(rows) if l.strip() == "END_DATA")
    except (StopIteration, ValueError, IndexError):
        return out
    for line in rows[db + 1:de]:
        t = line.split()
        if len(t) == len(fields):
            try:
                out[t[li].strip('"')] = float(t[yi])
            except ValueError:
                continue
    return out


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

