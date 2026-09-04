"""Fit the four placed corners onto the chart's own patches — the photograph path.

WHY THIS EXISTS, AND WHY IT IS A BUTTON AND NOT A STEP IN THE READ.
A flatbed scan is flat: the sheet lies on glass, the lens is telecentric enough
to ignore, and four corners placed on the patch block describe the whole
geometry. A photograph is none of those things, and the three ways it differs —
the sheet's own bow, the camera's viewpoint, the lens's radial bend — do not
add up, they multiply. Measured on Knut's own Wolf Faust scan, put through a
bow x camera x lens matrix of 48 conditions (beta 8, agent L):

    a 5.5 % bow alone .................... 0 patches wrong
    a 15-degree compound tilt alone ...... 0 patches wrong
    the two together .................. 102 patches over 1 dE00, 44 over 3

Four corners placed on the block's physical corners are the WORST place to put
them when the sheet is not flat, because the corners are exactly where a bowed
sheet has run away from the plane. The same quad, moved a little to balance the
residual across the whole block instead of pinning its ends, reads the same
chart with **0** patches over 1 dE00 in 42 of those 48 conditions, and leaves
one patch wrong in five of the remaining six.

That "moved a little" is all this module does. It searches the eight degrees of
freedom the marquee already has — the four corners, nothing else, no new model
— for the placement at which the chart's own patches look most like flat
patches, and the answer is CLAMPED to three quarters of a patch pitch so it
cannot slide onto a neighbouring patch. That clamp is the whole safety
argument: a grid one pitch out reads every patch as its neighbour and scores
just as well on any within-patch measure, so the distance, not the score, is
what makes this safe. See :data:`CLAMP_PITCHES`.

WHAT THIS DELIBERATELY DOES NOT DO.
* It does not estimate lens distortion. Profiled over k1 with the quad
  re-optimised at every step, the objective moves by less than 1 % across the
  whole plausible range of a real lens — the radial term is not separably
  estimable from eight corner degrees of freedom, and a free one ran off to the
  wrong sign and cost a corner patch 2.5-4.2 dE00 that the plain fit read
  correctly.
* It does not rectify the image. Measured over twelve conditions: reading the
  refined quad on the original photograph and reading a rectified copy of it
  differ by less than the resampling noise. A rectified copy is a second image
  on disk buying nothing.
* It does not run by itself, and nothing in the ordinary read path calls it.
  A flatbed scan that never presses the button is read by byte-identical code.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from core.logger import get_logger

log = get_logger(__name__)

__all__ = ["RefineResult", "refine_corners", "patch_pitch_px", "as_tiff",
           "TIFF_SUFFIXES", "CLAMP_PITCHES", "SEARCH_PITCHES", "MIN_GAIN"]

#: How far any one corner may END UP from where the user put it, in patch
#: pitches. This number is the ENTIRE safety argument of this module, so it is
#: worth saying why it is the only one available.
#:
#: A grid slipped by a WHOLE patch pitch reads every patch as its neighbour and
#: is, by every within-patch measure, exactly as good as the right answer --
#: each box still sits squarely on a flat patch. No objective computed inside
#: the boxes can tell the two apart, and there is no cleverer test to reach
#: for: shifting the fitted quad a pitch and comparing scores returns "just as
#: good" on every real chart, which is the point. What DOES separate them is
#: distance: a one-patch slip needs every corner to travel a full pitch (a
#: uniform slide) or the far pair to travel a full pitch (a one-column stretch),
#: and both are unreachable from a limit below 1.0. 0.75 leaves the fit the room
#: it measurably needs -- a sheet bowed 5.5 % and tilted 15 degrees wants
#: 0.5-0.65 of a pitch -- while keeping a quarter of a pitch of margin under
#: the nearest wrong answer.
CLAMP_PITCHES = 0.75

#: How far the SEARCH may look, in patch pitches. Deliberately wider than
#: :data:`CLAMP_PITCHES`, and the difference is the whole point: a search
#: stopped by its own limit cannot tell "the best fit is here" from "the best
#: fit is further out and I was not allowed to go", and answering with the
#: limit would be answering with a guess. Searching wider and then REFUSING
#: anything past the limit separates the two -- a fit that converges inside
#: half a pitch is used, one that wanted more is refused and the user is asked
#: to move the corners closer first.
SEARCH_PITCHES = 1.0

#: The objective must improve by this fraction before the corners are moved at
#: all — otherwise a placement that is already right is nudged for nothing.
MIN_GAIN = 0.02

#: What ``scanin`` can actually open. Everything else is a photograph's format
#: and has to be converted before Argyll sees it.
TIFF_SUFFIXES = (".tif", ".tiff")


@dataclass
class RefineResult:
    """Where the fit landed, and whether it may be used."""

    corners: list[tuple[float, float]] | None = None
    before: float | None = None          # objective at the user's placement
    after: float | None = None           # objective at the fit
    moved_pitch: float = 0.0             # worst corner move, in patch pitches
    reason: str = ""                     # machine-readable refusal reason

    @property
    def ok(self) -> bool:
        return self.corners is not None


# ---------------------------------------------------------------------------
def as_tiff(path: str | Path, dest_dir: str | Path) -> tuple[Path, bool]:
    """``(path scanin can read, was it converted)``.

    ``scanin`` reads TIFF and nothing else — a JPEG straight out of a camera
    makes it exit with ``Not a TIFF or MDI file, bad magic number``. The file
    picker's "All files" entry lets one be chosen, the preview decodes it
    happily and the marquee aligns on it, so the failure arrives at the very
    end of the job with an Argyll error message.

    A file that is ALREADY a TIFF is returned unchanged and untouched — not
    copied, not re-encoded, not even opened. That is the whole flatbed path,
    and it must stay bit-for-bit what it was.
    """
    path = Path(path)
    if path.suffix.lower() in TIFF_SUFFIXES:
        return path, False
    from PIL import Image
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dst = dest_dir / (path.stem + "-as-tiff.tif")
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(path) as im:
        im.convert("RGB").save(dst, compression="tiff_lzw")
    log.info("converted %s to %s for scanin", path.name, dst.name)
    return dst, True


def patch_pitch_px(boxes: Sequence, corners: Sequence[tuple[float, float]],
                   bbox: tuple[float, float, float, float]) -> float:
    """One patch pitch, in IMAGE pixels, for the quad currently on screen.

    The pitch is the MEDIAN distance from a patch centre to its nearest
    neighbour, in the ``.cht``'s own units, scaled by how many pixels the quad
    gives the chart.

    Not the smallest step between sorted origins, which is the obvious version
    and is wrong on every chart with two blocks. ``it8.cht`` lays its main grid
    at x = 26.625 + 25.625·i and its greyscale strip at x = 25.625·j, so the
    sorted union of origins contains 25.625 and 26.625 — **a one-unit step**,
    twenty-six times too small. That made the clamp two pixels wide and the fit
    refused every real IT8 photograph with "too far to fit". Caught by driving
    the real window, not by a unit test, which is why
    ``test_the_pitch_is_the_patch_pitch_on_a_two_block_chart`` now exists."""
    import math
    import numpy as np
    if len(boxes) < 2:
        return 0.0
    cx = np.array([(b.x1 + b.x2) / 2.0 for b in boxes])
    cy = np.array([(b.y1 + b.y2) / 2.0 for b in boxes])
    d2 = ((cx[:, None] - cx[None, :]) ** 2 + (cy[:, None] - cy[None, :]) ** 2)
    np.fill_diagonal(d2, np.inf)
    step = float(np.median(np.sqrt(d2.min(axis=1))))
    if not (step > 0) or not math.isfinite(step):
        return 0.0
    c = list(corners)
    wpx = (math.dist(c[0], c[1]) + math.dist(c[3], c[2])) / 2.0
    hpx = (math.dist(c[0], c[3]) + math.dist(c[1], c[2])) / 2.0
    x0, y0, x1, y1 = bbox
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return step * min(wpx / (x1 - x0), hpx / (y1 - y0))


# ---------------------------------------------------------------------------
# the objective: how much colour varies INSIDE each sample box
# ---------------------------------------------------------------------------
def _integrals(arr):
    """Summed-area tables for the sum and the sum of squares, so one objective
    evaluation is eight lookups per patch and no pixel loop."""
    import numpy as np
    a = arr if arr.ndim == 3 else arr[:, :, None]
    h, w, c = a.shape
    s = np.zeros((h + 1, w + 1, c)); q = np.zeros((h + 1, w + 1, c))
    s[1:, 1:] = a.cumsum(0).cumsum(1)
    q[1:, 1:] = (a.astype(np.float64) ** 2).cumsum(0).cumsum(1)
    return s, q, w, h


def _homography(src, dst):
    import numpy as np
    a = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, vt = np.linalg.svd(np.asarray(a, float))
    h = vt[-1].reshape(3, 3)
    if h[2, 2] == 0:
        raise ValueError("degenerate quad")
    return h / h[2, 2]


def _nelder_mead(f, x0, step, maxiter=6000, xtol=1e-7, ftol=1e-9):
    """A plain Nelder-Mead. Written here rather than imported because SciPy is
    not a ChromIQ dependency and this is forty lines of it."""
    import numpy as np
    x0 = np.asarray(x0, float)
    n = len(x0)
    step = np.asarray(step, float) * np.ones(n)
    sim = np.array([x0] + [x0 + np.eye(n)[i] * step[i] for i in range(n)])
    fv = np.array([f(p) for p in sim])
    for _ in range(maxiter):
        o = np.argsort(fv); sim, fv = sim[o], fv[o]
        if np.abs(sim[1:] - sim[0]).max() <= xtol and abs(fv[-1] - fv[0]) <= ftol:
            break
        cen = sim[:-1].mean(axis=0)
        xr = cen + (cen - sim[-1]); fr = f(xr)
        if fr < fv[0]:
            xe = cen + 2.0 * (cen - sim[-1]); fe = f(xe)
            sim[-1], fv[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < fv[-2]:
            sim[-1], fv[-1] = xr, fr
        else:
            xc = cen + 0.5 * (sim[-1] - cen); fc = f(xc)
            if fc < fv[-1]:
                sim[-1], fv[-1] = xc, fc
            else:
                sim[1:] = sim[0] + 0.5 * (sim[1:] - sim[0])
                fv[1:] = [f(p) for p in sim[1:]]
    o = np.argsort(fv)
    return sim[o][0], float(fv[o][0])


def _sample_boxes(boxes, frac):
    """Every patch's sample box in ``.cht`` units — the SAME #119 equal-margin
    rule the marquee draws and ``cht_with_sample_area`` writes, so the fit is
    judged on the very area the read will use."""
    import numpy as np
    from workflow.scanin_runner import sample_margin
    out = []
    for b in boxes:
        w, h = b.x2 - b.x1, b.y2 - b.y1
        m = sample_margin(w, h, frac)
        out.append([b.x1 + m, b.y1 + m, b.x2 - m, b.y2 - m])
    return np.asarray(out, float)


def refine_corners(scan: str | Path, boxes: Sequence,
                   corners: Sequence[tuple[float, float]],
                   sample_frac: float = 0.90,
                   clamp_pitches: float = CLAMP_PITCHES,
                   search_pitches: float = SEARCH_PITCHES,
                   max_side: int = 1800,
                   min_gain: float = MIN_GAIN) -> RefineResult:
    """Move the four *corners* onto the chart's patches, or refuse and say why.

    *sample_frac* is the fraction of each patch the FIT looks at, and it is
    deliberately larger than the fraction the READ uses: a small centred box
    stays inside its patch under a misplacement that a large one already
    overhangs, so a small box makes a blind objective. It has no effect on what
    is read — the read's own sample area is untouched.
    """
    import numpy as np
    from PIL import Image

    if len(list(corners)) != 4 or not boxes:
        return RefineResult(reason="nothing-to-fit")
    bbox = (min(b.x1 for b in boxes), min(b.y1 for b in boxes),
            max(b.x2 for b in boxes), max(b.y2 for b in boxes))
    pitch = patch_pitch_px(boxes, corners, bbox)
    if pitch <= 2.0:
        return RefineResult(reason="chart-too-small")
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(scan) as im:
            im = im.convert("RGB")
            W, H = im.size
            scale = min(1.0, max_side / max(W, H))
            if scale < 1.0:
                im = im.resize((max(1, int(W * scale)), max(1, int(H * scale))))
            arr = np.asarray(im, np.float64)
    except Exception:                       # noqa: BLE001 — a fit must not crash
        log.warning("could not open %s for the patch fit", scan, exc_info=True)
        return RefineResult(reason="unreadable")

    s, q, w, h = _integrals(arr)
    sb = _sample_boxes(boxes, sample_frac)
    x0, y0, x1, y1 = bbox
    src = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    c0 = np.asarray(corners, float) * scale
    limit = max(search_pitches, clamp_pitches) * pitch * scale
    # The four corners of every sample box, in .cht units, in one array.
    quads = np.stack([sb[:, [0, 1]], sb[:, [2, 1]], sb[:, [2, 3]], sb[:, [0, 3]]], 1)

    def objective(c):
        try:
            hm = _homography(src, c)
        except (ValueError, np.linalg.LinAlgError):
            return 1e9
        p = quads.reshape(-1, 2)
        d = hm[2, 0] * p[:, 0] + hm[2, 1] * p[:, 1] + hm[2, 2]
        if not np.all(np.abs(d) > 1e-9):
            return 1e9
        u = (hm[0, 0] * p[:, 0] + hm[0, 1] * p[:, 1] + hm[0, 2]) / d
        v = (hm[1, 0] * p[:, 0] + hm[1, 1] * p[:, 1] + hm[1, 2]) / d
        u = u.reshape(-1, 4); v = v.reshape(-1, 4)
        # The axis-aligned box inscribed in each projected sample quad — the
        # same shape the read's own box takes once scanin has mapped it.
        cx = u.mean(1); cy = v.mean(1)
        hw = (u.max(1) - u.min(1)) * 0.36; hh = (v.max(1) - v.min(1)) * 0.36
        ax = np.round(cx - hw).astype(np.int64); bx = np.round(cx + hw).astype(np.int64)
        ay = np.round(cy - hh).astype(np.int64); by = np.round(cy + hh).astype(np.int64)
        if (ax < 0).any() or (ay < 0).any() or (bx > w).any() or (by > h).any():
            return 1e9
        if (bx - ax < 2).any() or (by - ay < 2).any():
            return 1e9
        n = ((bx - ax) * (by - ay))[:, None]
        ss = s[by, bx] - s[ay, bx] - s[by, ax] + s[ay, ax]
        qq = q[by, bx] - q[ay, bx] - q[by, ax] + q[ay, ax]
        mean = ss / n
        sd = np.sqrt(np.maximum(qq / n - mean * mean, 0.0)).mean(axis=1)
        sd.sort()
        # A trimmed mean, because a real target has a patch or two with a mark
        # on it and one bad patch must not steer the whole placement.
        return float(sd[:max(1, int(0.95 * len(sd)))].mean())

    def moved_px(c):
        """How far the furthest corner has travelled, as a DISTANCE.

        Not the larger of its x and y moves: a corner that goes 0.6 of a pitch
        along each axis has travelled 0.85 of one, and the bound this module
        rests on is about distance from the patch it was aimed at. Measuring it
        per axis let a corner out to 0.87 pitches under a 0.75 limit — caught
        by ``test_no_corner_is_ever_moved_further_than_the_clamp``, which asks
        the question in the units the safety argument uses."""
        d = c - c0
        return float(np.hypot(d[:, 0], d[:, 1]).max())

    def bounded(p):
        c = p.reshape(4, 2)
        if moved_px(c) > limit:
            return 1e9
        return objective(c)

    before = objective(c0)
    if before >= 1e9:
        return RefineResult(reason="grid-outside-the-image")
    best, after = _nelder_mead(bounded, c0.flatten(), step=limit / 4.0)
    best, after = _nelder_mead(bounded, best, step=limit / 40.0)
    got = best.reshape(4, 2)
    moved = moved_px(got) / (pitch * scale)
    if after >= before * (1.0 - min_gain):
        return RefineResult(reason="already-the-best-fit", before=before,
                            after=after, moved_pitch=moved)
    if moved > clamp_pitches:
        # The fit is further from the user's corners than may be applied
        # silently. It is not necessarily wrong -- it is simply past the
        # distance at which "the same patch, better centred" stops being the
        # only explanation, so the user is asked to move the corners closer and
        # press again rather than being handed a guess.
        return RefineResult(reason="too-far-to-fit", before=before, after=after,
                            moved_pitch=moved)
    return RefineResult(corners=[(float(x / scale), float(y / scale))
                                 for x, y in got],
                        before=before, after=after, moved_pitch=moved)
