"""Reads a printed chart out of a **flatbed scan** with ArgyllCMS ``scanin``.

Given a scan of a ChromIQ chart plus the chart's ``.cht`` (patch layout) and
``.cie`` (measured reference), ``scanin`` samples each patch's scanner RGB and
writes a ``scan.ti3`` pairing scanner RGB ↔ the measured XYZ. That ``.ti3`` has
``DEVICE_CLASS "INPUT"``, so ``colprof`` then builds a **scanner input profile**
from it (reuse :mod:`workflow.profile_builder`) — the scanner roundtrip (#98).

Two registration paths:

* **Auto** — ``scanin scan.tif chart.cht chart.cie``; scanin finds the chart by
  its edge ticks + corners.
* **Manual (marquee)** — ``scanin -F x1,y1,x2,y2,x3,y3,x4,y4 -p …``; the four
  corners the user placed over the chart (``.cht`` order **TL, TR, BR, BL**),
  ``-p`` compensating for perspective. The robust path, since the engine prints
  no fiducial *marks* (the ``.cht`` ``F`` line gives ``-F`` its reference quad).

``-d`` (e.g. ``-dipon``) additionally writes a **diagnostic image** with the
recognised patch boxes drawn on it, so a mis-read can be seen before profiling.

Mirrors the other Argyll runners (:mod:`workflow.cctiff_apply`): a params
dataclass + a runner that builds the CLI and drives it through the singleton
:class:`~core.argyll_runner.ArgyllRunner`, with structured error parsing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from core.stem_paths import artefact

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner

from core.logger import get_logger

log = get_logger(__name__)

# Corner order scanin -F expects, matching the .cht F line and the marquee.
CORNER_ORDER = ("top-left", "top-right", "bottom-right", "bottom-left")

# ---------------------------------------------------------------------------
# Working-folder tidy-up (#127, Knut's beta.5 report): scanner intermediates
# left behind by EARLIER releases — the "-aligned" template family, prepared
# patchbox/sample copies and diagnostic images written flat next to the scans
# or the chart. New runs write these into cache/; this sweeps the old ones in
# too, so a re-used folder ends up organised the same way. Measurement data
# (-printer.ti2/.ti3, -scanner.ti3, per-shot -pNsK-scanner.ti3, -pN-avg.ti3)
# is NEVER touched — those are real readings, not cache.
# ---------------------------------------------------------------------------

_LEGACY_INTERMEDIATE_RES = (
    re.compile(r"^.+-patchbox\.cht$"),
    re.compile(r"^.+-patchbox-sample\.cht$"),
    re.compile(r"^.+-aligned\.cht$"),
    re.compile(r"^.+-aligned-patchbox.*\.cht$"),
    re.compile(r"^.+-diag\.tif$", re.IGNORECASE),
)
_PLAIN_SAMPLE_RE = re.compile(r"^(?P<base>.+)-sample\.cht$")


def tidy_legacy_intermediates(folder: str | Path) -> list[Path]:
    """Move earlier releases' scanner intermediates from *folder* into its
    ``cache/`` sub-folder. A plain ``<x>-sample.cht`` moves only when the
    ``<x>.cht`` it was derived from sits in the same folder — a user's own
    chart that merely *ends* in ``-sample`` is never touched. Conflict-safe
    (never overwrites) and best-effort per file. Returns the moved paths."""
    from core.file_manager import cache_subdir
    folder = Path(folder)
    if not folder.is_dir():
        return []
    moved: list[Path] = []
    cache = cache_subdir(folder)
    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue
        take = any(rx.match(f.name) for rx in _LEGACY_INTERMEDIATE_RES)
        if not take:
            m = _PLAIN_SAMPLE_RE.match(f.name)
            take = (m is not None
                    and (folder / f"{m.group('base')}.cht").is_file())
        if not take:
            continue
        try:
            cache.mkdir(parents=True, exist_ok=True)
            dst = cache / f.name
            if dst.exists():
                f.unlink()          # same-named copy already tidied → drop dupe
            else:
                f.rename(dst)
                moved.append(dst)
        except OSError as exc:
            log.warning("could not tidy %s into cache/: %s", f, exc)
    if moved:
        log.info("tidied %d older scanner working file(s) into %s",
                 len(moved), cache)
    return moved

_BOX_LINE = re.compile(r"^\s*[XY]\s+\S+\s+\S+\s+\S+\s+\S+\s+"
                       r"([\d.]+)\s+([\d.]+)\s", re.MULTILINE)
_SHRINK_LINE = re.compile(r"^(\s*BOX_SHRINK\s+)([\d.]+)", re.MULTILINE)


def sample_area_box_shrink(cht_text: str, frac: float) -> float | None:
    """The ``BOX_SHRINK`` (cht units, per side) that makes scanin read *frac* of
    each patch's AREA. A patch of side *B* sampled at area fraction *f* keeps an
    inner square of side ``B·√f``, i.e. a per-side shrink of ``B·(1−√f)/2``.
    *B* is the median box side across the chart (exact for a uniform grid, which
    every standard target is). Returns ``None`` for full-area (≥1) or no boxes."""
    frac = max(0.05, min(1.0, float(frac)))
    if frac >= 0.999:
        return 0.0
    sides: list[float] = []
    for w, h in _BOX_LINE.findall(cht_text):
        sides += [float(w), float(h)]
    if not sides:
        return None
    sides.sort()
    b = sides[len(sides) // 2]                      # median side
    return round(b * (1.0 - frac ** 0.5) / 2.0, 3)


def sample_margin(w: float, h: float, frac: float) -> float:
    """The uniform per-edge inset *m* with ``(w-2m)(h-2m) = frac·w·h`` —
    Knut's #119 rule for the read zone: the distance from the sample box to
    the patch border is the SAME on all four sides (it feeds the edge
    detection), while the sampled area is exactly the chosen fraction. On a
    square patch this is the familiar ``w·(1-√f)/2``; on a rectangular patch
    (a Wolf Faust's GS strip) the sample box is a little longer-and-thinner
    than the patch shape, which is the accepted trade."""
    from math import sqrt
    frac = max(0.05, min(1.0, float(frac)))
    span = w + h
    disc = span * span - 4.0 * (1.0 - frac) * w * h   # ≥ (w-h)² ≥ 0
    return (span - sqrt(disc)) / 4.0


def hex_max_sample_fraction(w: float, h: float) -> float:
    """The largest Sample area a HEXAGONAL chart can be read at before the
    sample box escapes the hexagon — from the chart's own patch proportions.

    A hexagonal patch is stored as the rectangle *w* × *h* (flat-to-flat width,
    row pitch), but the ink is a pointy-top hexagon whose corners sit at
    ``(0, ±2h/3)`` and ``(±w/2, ±h/3)``: the rectangle's own top and bottom
    corners are already OUTSIDE it. :func:`sample_margin` insets the read box by
    the same *m* on all four sides, so its corner is at ``(w/2-m, h/2-m)``, and
    the slanted side it must stay behind is ``x = (w/2)(2 - 3y/h)``. That gives
    a hard minimum inset

        m ≥ w·h / (2·(2h + 3w))

    and the fraction below is the area that leaves. It is not a rate but a
    switch: the neighbouring hexagon is flush against this one, so a box one
    percent too big samples the neighbour on EVERY patch, not on a few (measured:
    0 of 150 patches at 60 %, 150 of 150 at 70 %).

    The limit depends on the shape, which is why it is computed and not a
    constant: 64.4 % on a regular hexagon (h/w = 0.866), 64.0 % at h/w = 1,
    61.2 % at h/w = 2 — and 60 % itself is unsafe from h/w ≈ 2.58 upwards.
    Returns 1.0 for a degenerate patch (nothing to clamp)."""
    w, h = float(w), float(h)
    if w <= 0.0 or h <= 0.0:
        return 1.0
    m = w * h / (2.0 * (2.0 * h + 3.0 * w))
    return max(0.05, (w - 2.0 * m) * (h - 2.0 * m) / (w * h))


def sample_margin_inverse(a: float, b: float, frac: float) -> float:
    """Recover the margin from an already-shrunk box: the *m* with
    ``a·b = frac·(a+2m)(b+2m)`` — the exact inverse of
    :func:`sample_margin` (used to grow a prepared .cht's boxes back to the
    full patches)."""
    from math import sqrt
    frac = max(0.05, min(1.0, float(frac)))
    span = a + b
    disc = frac * frac * span * span + 4.0 * frac * (1.0 - frac) * a * b
    return (sqrt(disc) - frac * span) / (4.0 * frac)


_XY_LINE = re.compile(
    r"^(\s*[XY]\s+\S+\s+\S+\s+\S+\s+\S+\s+)"
    r"([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)"
    r"((?:\s+[-+0-9.eE]+){2}\s*)$", re.MULTILINE)


def cht_with_sample_area(cht_text: str, frac: float) -> str:
    """Return *cht_text* with every patch box shrunk to sample-area *frac*,
    using Knut's #119 equal-margin rule (:func:`sample_margin`): each
    ``X``/``Y`` block's box is inset by the SAME distance on all four sides,
    chosen so the remaining area is exactly *frac* of the patch. The margin
    is computed per block from that block's own ``w h`` — a Wolf Faust's GS
    strip gets its own, larger margin than the square main grid — and the
    increments (the patch pitch) are untouched. ``BOX_SHRINK`` is pinned to
    0 so scanin reads exactly these boxes and the diagnostic image shows
    exactly what was sampled. Fiducials (``F``) and diagnostic marks (``D``)
    are never moved. Box-less text is returned unchanged.

    Full area (≥ 0.999) keeps the boxes but still pins ``BOX_SHRINK`` to 0:
    ChromIQ's own chart ``.cht``\\ s carry a baked-in default shrink (a sane
    read margin for third-party use of the sidecar), and letting it survive
    made "100 %" silently read ≈ 50 % of each patch on ChromIQ charts
    (Knut, #119)."""
    frac = max(0.05, min(1.0, float(frac)))
    if not _XY_LINE.search(cht_text):
        return cht_text
    if frac < 0.999:
        def _shrink(m: re.Match) -> str:
            w, h = float(m.group(2)), float(m.group(3))
            ox, oy = float(m.group(4)), float(m.group(5))
            mg = sample_margin(w, h, frac)
            return (f"{m.group(1)}{w - 2.0 * mg:g} {h - 2.0 * mg:g} "
                    f"{ox + mg:g} {oy + mg:g}{m.group(6)}")

        cht_text = _XY_LINE.sub(_shrink, cht_text)
    if _SHRINK_LINE.search(cht_text):
        return _SHRINK_LINE.sub(lambda m: f"{m.group(1)}0.0", cht_text,
                                count=1)
    return cht_text.rstrip() + "\n\nBOX_SHRINK 0.0\n"


def cht_with_patchbox_fiducials(cht_text: str) -> str:
    """Rewrite the ``F`` line so the fiducials sit on the patch-area bounding
    box — **preserving the original corner order**. Each existing fiducial is
    replaced by the bbox corner nearest to it, so the frame shrinks (or grows)
    onto the patch area without changing its orientation.

    That orientation matters: scanin's ``-F`` pairs the marquee corners
    (passed image-style, first = top-left) with the ``F`` corners *by
    position in the line*. Engine charts write their ``F`` in bottom-left-
    origin mm (first corner = ymax = physically top); rectarg/Argyll charts
    use image-style y-down (first corner = ymin = top). A rewrite that emits
    a fixed corner order is right for one convention and **vertically mirrors
    the grid** for the other — which scrambled every engine-chart scanner
    read into per-strip reversed patches while looking perfectly aligned
    (#108: positions stay inside the patch area, only the labels flip).

    Unchanged when there is no ``F`` line or no patch boxes. If the existing
    fiducials don't map 1:1 onto distinct bbox corners (degenerate frame),
    the y-down image-style order is used — the convention of every standard
    target this fallback could apply to."""
    from workflow.cht_parser import ChtParseError, parse_cht
    try:
        geom = parse_cht(cht_text)
    except ChtParseError:
        return cht_text
    if not geom.patches or not re.search(r"(?m)^\s*F .*$", cht_text):
        return cht_text
    xs = [b.x1 for b in geom.patches] + [b.x2 for b in geom.patches]
    ys = [b.y1 for b in geom.patches] + [b.y2 for b in geom.patches]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    bbox = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    corners = bbox                                   # image-style fallback
    if len(geom.fiducials) == 4:
        nearest = [min(bbox, key=lambda c, f=f: (c[0] - f[0]) ** 2 + (c[1] - f[1]) ** 2)
                   for f in geom.fiducials]
        if len(set(nearest)) == 4:
            corners = nearest
    fline = "  F _ _ " + " ".join(f"{x:.2f} {y:.2f}" for x, y in corners)
    return re.sub(r"(?m)^\s*F .*$", fline, cht_text, count=1)


_TI3_STR_FIELDS = {"SAMPLE_ID", "SAMPLE_LOC", "SAMPLE_NAME"}


def _ti3_bad(tok: str) -> bool:
    """True if a token isn't a finite real — nan/inf and Windows' ``1.#IND`` /
    ``1.#QNAN`` / ``-1.#INF`` forms (which fail ``float()``)."""
    try:
        v = float(tok)
        return v != v or v in (float("inf"), float("-inf"))
    except ValueError:
        return True


def sanitize_ti3(text: str) -> tuple[str, int, int]:
    """Make a scanner ``.ti3`` safe for colprof when scanin wrote non-real values
    for a degenerate patch read (colprof otherwise rejects the *whole* file:
    ``Field 'STDEV_B' … is 'non-quoted char string'``).

    A bad ``STDEV_*`` (a patch read fine but its variance is undefined — e.g. a
    single-pixel box) is set to ``0``. A bad **value** column (``RGB_*``/``XYZ_*``/
    ``LAB_*`` — the box caught no usable pixels, so there's no real reading) makes
    the whole patch **dropped** instead of zero-filled, so it can't become a false
    "reads as black" tie point in the profile; ``NUMBER_OF_SETS`` is updated to
    match. Returns ``(new_text, n_zeroed, n_dropped)``; unchanged when clean."""
    lines = text.splitlines()
    try:
        fi = next(i for i, ln in enumerate(lines) if ln.strip() == "BEGIN_DATA_FORMAT")
        fields = lines[fi + 1].split()
        db = next(i for i, ln in enumerate(lines) if ln.strip() == "BEGIN_DATA")
        de = next(i for i, ln in enumerate(lines) if ln.strip() == "END_DATA")
    except (StopIteration, IndexError):
        return text, 0, 0
    stdev_cols = [c for c, f in enumerate(fields) if f.upper().startswith("STDEV")]
    value_cols = [c for c, f in enumerate(fields)
                  if f not in _TI3_STR_FIELDS and not f.upper().startswith("STDEV")]
    zeroed = dropped = 0
    out_rows: list[str] = []
    for li in range(db + 1, de):
        raw = lines[li]
        toks = raw.split()
        if len(toks) != len(fields):
            out_rows.append(raw)                       # leave odd lines alone
            continue
        if any(_ti3_bad(toks[c]) for c in value_cols):
            dropped += 1                               # no real reading → drop
            continue
        changed = False
        for c in stdev_cols:
            if _ti3_bad(toks[c]):
                toks[c] = "0"
                zeroed += 1
                changed = True
        out_rows.append(" ".join(toks) if changed else raw)
    if not zeroed and not dropped:
        return text, 0, 0
    new = lines[:db + 1] + out_rows + lines[de:]
    if dropped:                                        # keep NUMBER_OF_SETS honest
        kept = len(out_rows)
        for i, ln in enumerate(new):
            if ln.strip().upper().startswith("NUMBER_OF_SETS"):
                new[i] = f"NUMBER_OF_SETS {kept}"
                break
    return "\n".join(new) + ("\n" if text.endswith("\n") else ""), zeroed, dropped


def _fmt_corners(corners: list[tuple[float, float]]) -> str:
    """``x1,y1,x2,y2,x3,y3,x4,y4`` from four (x, y) image-pixel corners."""
    if len(corners) != 4:
        raise ValueError("scanin -F needs exactly four corners (TL, TR, BR, BL).")
    return ",".join(f"{v:g}" for xy in corners for v in xy)


def scanin_args(scan_tif: Path, cht: Path, cie: Path,
                corners: list[tuple[float, float]] | None = None,
                perspective: bool = True, diag: Path | None = None,
                robust_mean: bool = True, verbose: bool = True,
                out_name: str | None = None) -> list[str]:
    """Build the ``scanin`` argument list for scanner-profile mode.

    *corners* (four image-pixel (x, y), order TL/TR/BR/BL) switches on manual
    ``-F`` registration; ``None`` uses auto-recognition. *diag* writes a
    diagnostic image (extra ``-dipon`` + the diag path as the trailing arg).
    *out_name* (via ``-O``) sets the output ``.ti3`` filename — used to give the
    scanner ``.ti3`` a distinct ``-scanner`` name so it can never overwrite the
    chart's own measurement / printer profile. Default is scanin's ``<scan>.ti3``."""
    args: list[str] = []
    if verbose:
        args.append("-v")
    if not robust_mean:
        args.append("-m")
    if corners is not None:
        args += ["-F", _fmt_corners(corners)]
    # NOT with the corners. `-p` is scanin's perspective search, and on the
    # manual path it is dead work that can only kill the run: `-F` does not skip
    # recognition — do_scanrd runs calc_lines -> calc_perspective ->
    # calc_rotation before it ever looks at the corners — and the rotation it
    # computes is never read (compute_man_ptrans uses the four corners alone).
    # `calc_perspective` optimises to MINIMISE the variance of detected line
    # angles; on a honeycomb, whose angles are multimodal (0 and +/-30 degrees),
    # it crushes them together, the acceptance window 1.5*sd collapses to
    # +/-0.08 degrees, and calc_rotation aborts with "N consistent lines is not
    # enough". Measured over randomised realistic scans: 23.3% of hexagonal
    # reads failed with -p, 0% without. The values do not change — 42 conditions
    # including genuine keystone, barrel/pincushion lens distortion and Argyll's
    # own ColorChecker and QPcard targets, all bit-identical, diagnostic TIFF
    # included — because s->ptrans, the homography fitted to the four corners,
    # IS the perspective correction. The randomised sweep says the same about
    # accuracy, not just about equality: over the reads that DID succeed, the
    # error against ground truth is 0.385 dE with -p and 0.380 without at the
    # median, with an identical 0.741 worst case. Dropping the flag removes the
    # aborts and the 90 s stalls and costs nothing.
    if perspective and corners is None:
        args.append("-p")
    if diag is not None:
        args.append("-dipon")
    if out_name is not None:
        args += ["-O", out_name]
    args += [str(scan_tif), str(cht), str(cie)]
    if diag is not None:
        args.append(str(diag))
    return args


def scanin_printer_args(scan_tif: Path, cht: Path, scan_profile: Path, pbase: Path,
                        corners: list[tuple[float, float]] | None = None,
                        perspective: bool = True, diag: Path | None = None,
                        verbose: bool = True, accumulate: bool = False) -> list[str]:
    """Build the ``scanin -c`` argument list for **printer-profile** mode.

    Instead of profiling the scanner, this turns the scan into a *printer*
    measurement: it reads ``<pbase>.ti2`` (the chart's printer device values) and,
    converting each scanned patch to real colour through *scan_profile* (a scanner
    ICC the user built earlier), writes ``<pbase>.ti3`` — which colprof turns into
    a printer profile. The flat-bed scanner acts as the measuring instrument.
    ``scanin -c [opts] input.tif recog.cht scanprofile.icc pbase [diag.tif]``."""
    args: list[str] = []
    if verbose:
        args.append("-v")
    args.append("-ca" if accumulate else "-c")   # -ca adds a page to an existing .ti3
    if corners is not None:
        args += ["-F", _fmt_corners(corners)]
    # Same rule as the scanner path above — see the note there.
    if perspective and corners is None:
        args.append("-p")
    if diag is not None:
        args.append("-dipon")
    args += [str(scan_tif), str(cht), str(scan_profile), str(pbase)]
    if diag is not None:
        args.append(str(diag))
    return args


# scanin failure messages → (key, friendly text). Line refs: scanin/scanin.c.
_SCANIN_ERROR_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"Scanin failed with code", re.IGNORECASE),
     "recognition_failed",
     "ScanIn couldn't line the chart up with the scan. Re-place the four "
     "corners over the printed patch area (or straighten/re-scan the sheet), "
     "then try again."),
    (re.compile(r"must be 8 or 16 bits", re.IGNORECASE),
     "bit_depth",
     "The scan must be an 8- or 16-bit-per-channel TIFF. Re-export it from your "
     "scanner software as a plain TIFF."),
    (re.compile(r"must be an? (?:Grey|RGB|CMYK)", re.IGNORECASE),
     "wrong_channels",
     "The scan must be a Grey, RGB or CMYK TIFF. Scan the chart as RGB."),
    (re.compile(r"must be planar", re.IGNORECASE),
     "planar",
     "The scan's pixel layout isn't supported. Re-save it as an uncompressed "
     "RGB TIFF from your scanner software."),
    (re.compile(r"might overwrite the input", re.IGNORECASE),
     "diag_clash",
     "The diagnostic image would overwrite the scan. This is an internal naming "
     "clash — please report it."),
    (re.compile(r"error opening read file '([^']+)'", re.IGNORECASE),
     "open_failed",
     "Couldn't open '{0}'. Check the scan file exists and is readable."),

    # --- reference-file (.cht / .cie) failures ----------------------------
    # These files are written (and pre-validated) by ChromIQ, so in normal use
    # they can't be malformed — but a corrupted/edited file, a mismatched
    # .cht+.cie pair, or a writer regression would otherwise surface as a raw
    # Argyll dump. Collapse the many CGATS complaints into two clear messages.
    #
    # Bucket A — the scanner files are damaged / incomplete (malformed CTI2,
    # empty tables, missing COLOR_REP / SAMPLE_ID / SAMPLE_LOC, unresolvable
    # sample or location). scanin.c L623-882, L1126-1210.
    (re.compile(
        r"isn't a CTI2 format file"
        r"|doesn't contain at least one table"
        r"|doesn't (?:contain any data sets|contain any|have any)"
        r"|(?:has no|no) sets of data"
        r"|doesn't contain keyword COLOR_REPS?"
        r"|keyword COLOR_REPS? has unknown value"
        r"|doesn't contain field SAMPLE_(?:ID|LOC)"
        r"|[Ff]ield SAMPLE_(?:ID|LOC) is wrong type"
        r"|Couldn't find (?:sample|location) '[^']*'",
        re.IGNORECASE),
     "reference_damaged",
     "This chart's scanner files (.cht + .cie) look damaged or incomplete. "
     "Recreate them with Tools ▸ Create scanner target, then try again."),

    # Bucket B — the .cht/.cie don't match this chart's measurement: different
    # patch count, mismatched patch IDs/device values, or a different device
    # space (e.g. a .cht from one chart paired with another's .cie).
    # scanin.c L691, L957-970.
    (re.compile(
        r"[Dd]ifferent number of patches"
        r"|field id's don't match at patch"
        r"|device values .*don't match at patch"
        r"|has different device space",
        re.IGNORECASE),
     "reference_mismatch",
     "The scanner files don't match this chart's measurement (different "
     "patches or device type). Recreate them from this chart's own "
     "measurement with Tools ▸ Create scanner target."),

    # Bucket B2 — THE FILE SAYS HOW MANY COLOURS IT HAS AND THEN LISTS FEWER.
    # An ordinary way to get one: a download that stopped, or a file trimmed by
    # hand without editing NUMBER_OF_SETS. This used to fall through to bucket C
    # and reach the user as "check the files exist and the folder is writable"
    # — about a file that existed, in a folder that was writable, whose real
    # reason ArgyllCMS had printed two lines further up the same log (beta 8,
    # B8-17). cgats.c: "Read %d sets, expected %d sets".
    (re.compile(r"Read (\d+) sets, expected (\d+) sets", re.IGNORECASE),
     "reference_incomplete",
     "This reference file says it lists {1} colours and then gives only {0}. "
     "It is incomplete — get a fresh copy of the reference that came with your "
     "target, then pick it again."),

    # Bucket B3 — NOT PLAIN TEXT. A reference exported from a Windows tool as
    # UTF-16 reaches ArgyllCMS as text with a NUL after every character, and its
    # CGATS parser reports an illegal keyword rather than an encoding. ChromIQ
    # transcodes one on the way in (`reference_convert.utf8_reference`), so this
    # is the belt to that fix's braces — and it is also what a genuinely corrupt
    # file gets, instead of a lecture about folder permissions.
    (re.compile(r"cgats\.add_kword\(\)|keyword '.*' ?is illegal",
                re.IGNORECASE),
     "reference_not_text",
     "ChromIQ couldn't read this reference file as plain text — it may be "
     "saved in UTF-16 (a common export from Windows software) or have stray "
     "characters in it. Re-save it as plain text and pick it again."),

    # Bucket C — a generic CGATS read/write failure on a reference or output
    # file (permission, disk, truncation). scanin.c L596-799, L1165.
    #
    # IT SAYS WHICH HALF IT IS. "Check the files exist and the folder is
    # writable" was printed for a READ failure on a file whose full path was in
    # the same message ArgyllCMS had just written, and sent the user to look at
    # permissions on a file they had just picked in a file dialog.
    (re.compile(r"CGATS file '([^']*)' read error\s*:\s*(\S.*)$", re.IGNORECASE),
     "reference_unreadable",
     "ChromIQ couldn't read '{0}'. ArgyllCMS said: {1}"),
    (re.compile(r"CGATS file '([^']*)' read error", re.IGNORECASE),
     "reference_unreadable",
     "ChromIQ couldn't read '{0}'. Its reason is in the log just above this "
     "line."),
    (re.compile(r"[Ww]rite error to|Can't open file", re.IGNORECASE),
     "reference_io",
     "Couldn't write one of the scanner files. Check the folder the scan sits "
     "in can be written to, then try again."),

    # Out of memory on a very large scan. scanin.c L521, L976.
    (re.compile(r"Malloc failed|Unable to allocate", re.IGNORECASE),
     "out_of_memory",
     "Ran out of memory while processing the scan. Try scanning the chart at a "
     "lower resolution (300–600 dpi is plenty)."),
]


@dataclass
class ScaninParams:
    """One scanned page → a scanner ``.ti3``. Paths are absolute."""

    scan_tif: Path
    cht: Path
    cie: Path | None = None
    corners: list[tuple[float, float]] | None = None   # None = auto-recognise
    perspective: bool = True
    diag: Path | None = None
    robust_mean: bool = True
    # Distinct output name (via -O) so the scanner .ti3 can never collide with the
    # chart's own <stem>.ti3 / printer profile. Defaults to "<scan>-scanner.ti3".
    out_name: str | None = None
    # Printer-profile mode (scanin -c): convert the scan to real colour through a
    # scanner ICC and read <pbase>.ti2 → write <pbase>.ti3 (a printer measurement).
    scan_profile: Path | None = None
    pbase: Path | None = None
    accumulate: bool = False           # printer mode: -ca adds this page to <pbase>.ti3

    @property
    def is_printer(self) -> bool:
        return self.scan_profile is not None and self.pbase is not None

    @property
    def _out_name(self) -> str:
        return self.out_name or f"{self.scan_tif.stem}-scanner.ti3"

    @property
    def out_ti3(self) -> Path:
        """The ``.ti3`` scanin writes: in printer mode ``<pbase>.ti3``; otherwise
        the scanner ``<scan>-scanner.ti3`` (never the chart's own ``<stem>.ti3``)."""
        if self.is_printer:
            # scanin -c builds its own names by STRCAT (scanin.c:386-388:
            # `strcpy(datout_name,argv[fa]); strcat(datout_name,".ti3")`), so
            # a dotted project stem must be concatenated here too — see
            # core/stem_paths.py.
            return artefact(self.pbase, ".ti3")
        return self.scan_tif.parent / self._out_name


class ScaninRunner:
    def __init__(self, runner: "ArgyllRunner") -> None:
        self._runner = runner
        self._last_log = ""
        self._matched_errors: list[tuple[str, str]] = []

    def run(self, params: ScaninParams, on_line: Callable[[str], None],
            on_finish: Callable[[int], None]) -> None:
        args = self._build_args(params)
        cwd = params.scan_tif.parent
        log.info("scanin: %s  [cwd=%s]", " ".join(args), cwd)
        self._last_log = ""
        self._matched_errors = []

        def _accumulate(line: str) -> None:
            self._last_log += line + "\n"
            self._scan_line(line)
            on_line(line)

        self._runner.run("scanin", args, cwd, on_line=_accumulate, on_finish=on_finish)

    def _scan_line(self, line: str) -> None:
        for pattern, key, fmt in _SCANIN_ERROR_PATTERNS:
            m = pattern.search(line)
            if m:
                groups = tuple(g or "" for g in m.groups())
                self._matched_errors.append((key, fmt.format(*groups)))

    def primary_failure(self) -> tuple[str, str] | None:
        return self._matched_errors[0] if self._matched_errors else None

    @property
    def last_log(self) -> str:
        return self._last_log

    def _build_args(self, p: ScaninParams) -> list[str]:
        if p.is_printer:
            return scanin_printer_args(p.scan_tif, p.cht, p.scan_profile, p.pbase,
                                       p.corners, p.perspective, p.diag,
                                       accumulate=p.accumulate)
        return scanin_args(p.scan_tif, p.cht, p.cie, p.corners, p.perspective,
                           p.diag, p.robust_mean, out_name=p._out_name)
