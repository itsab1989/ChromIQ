"""Measurement report — statistics for a printed-chart measurement (.ti3).

Knut's request: after measuring, show how the reading compares to the chart's
expected colours (mean / median / worst / spread ΔE00, the worst patches, the
paper white and darkest black), save each report so they can be **compared
over time** on the same printer — surfacing ink ageing, printer drift or
instrument drift.

The "expected" reference is the chart's design colours (the sRGB-derived XYZ
that printtarg / the engine store in the ``.ti2``), matched to the measured
patches by ``SAMPLE_ID``. On a printer the absolute ΔE against sRGB is not
meaningful in isolation, but with a **fixed** reference the *change* between
two dated reports of the same chart is a clean drift signal.

Pure Python (numpy) — no Argyll process. Reuses ``ti3_analysis``.
"""
from __future__ import annotations

import json
import math
import re
import statistics
from datetime import datetime
from pathlib import Path

import numpy as np

from core.logger import get_logger
from core.text_io import read_text
from workflow.ti3_analysis import (
    Ti3ParseError, ciede2000, is_verification_ti3, parse_ti3, xyz_to_lab,
)

log = get_logger(__name__)

# 6: a .ti2 whose design XYZ is normalised 0..1 is rescaled to 0..100, and the
#    .ti2 DESIGN reference is Bradford-adapted D65→D50 as well. printtarg
#    writes an RGB chart's design XYZ as the sRGB estimate of the device values,
#    which is D65, while xyz_to_lab and the measured .ti3 are D50 — so every
#    expected value was skewed (paper white read as Lab 100/-2.3/-19.3 instead of
#    a neutral 100/0/0, and the cube corners looked invented rather than ideal).
# 5: device-derived reference is Bradford-adapted D65→D50, so imported
#    measurements no longer carry a ~1.5 ΔE white-point error (Knut). Bumping the
#    schema makes the dialog rebuild older saved reports from their run .ti3.
REPORT_SCHEMA = 7

# A cube corner counts as "present" in the chart when the nearest measured patch
# sits within this many device units (0..100, per channel) of the ideal corner.
# A full profiling chart has all eight; a minimal verification chart may omit
# some, which the report flags (Knut) so the cube-corner stats aren't misleading.
CORNER_PRESENT_TOL = 12.0

# Default Pass/Fail thresholds (ΔE00) for the report's colour-accuracy verdict.
# The average threshold judges the three *average* metrics, the maximum threshold
# the two *maximum* metrics (Knut). Overridable per report in the window.
DEFAULT_PASS_AVG = 2.0
DEFAULT_PASS_MAX = 3.0

# The five colour-accuracy metrics that carry a Pass/Fail verdict, in display
# order, as (key, which-threshold). Spread is reported too but has no threshold.
ACCURACY_METRICS: "list[tuple[str, str]]" = [
    ("avg_all",   "avg"),
    ("avg_low95", "avg"),
    ("avg_high5", "avg"),
    ("max_all",   "max"),
    ("max_low95", "max"),
]

# The eight corners of the RGB device cube, by device value (0..100). These are
# the paper white, the composite black and the six primary/secondary ink colours
# — so they say as much about the INKS as about the measurement (Knut). Order:
# neutral pair first, then primaries, then secondaries.
CUBE_CORNERS: "list[tuple[str, tuple[float, float, float]]]" = [
    ("W", (100.0, 100.0, 100.0)),
    ("K", (0.0, 0.0, 0.0)),
    ("R", (100.0, 0.0, 0.0)),
    ("G", (0.0, 100.0, 0.0)),
    ("B", (0.0, 0.0, 100.0)),
    ("C", (0.0, 100.0, 100.0)),
    ("M", (100.0, 0.0, 100.0)),
    ("Y", (100.0, 100.0, 0.0)),
]


def _srgb_hex(xyz100: "tuple[float, float, float]") -> str:
    """D50 XYZ (0..100) → #rrggbb for display (Bradford to D65, sRGB gamma)."""
    x, y, z = (v / 100.0 for v in xyz100)
    xd = 0.9555766 * x - 0.0230393 * y + 0.0631636 * z
    yd = -0.0282895 * x + 1.0099416 * y + 0.0210077 * z
    zd = 0.0122982 * x - 0.0204830 * y + 1.3299098 * z
    r = 3.2404542 * xd - 1.5371385 * yd - 0.4985314 * zd
    g = -0.9692660 * xd + 1.8760108 * yd + 0.0415560 * zd
    b = 0.0556434 * xd - 0.2040259 * yd + 1.0572252 * zd

    def enc(c: float) -> int:
        c = max(0.0, min(1.0, c))
        c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        return max(0, min(255, round(c * 255.0)))

    return "#{:02x}{:02x}{:02x}".format(enc(r), enc(g), enc(b))


def _bradford_d65_to_d50(x: float, y: float, z: float) -> "tuple[float, float, float]":
    """Bradford-adapt an XYZ triple from a D65 white point to D50 (Lindbloom
    matrix — the inverse of the D50→D65 adaptation in :func:`_srgb_hex`).

    The device-derived reference comes from ``_patch_xyz`` (device RGB treated as
    sRGB → XYZ under **D65**), but the measured values and ``xyz_to_lab`` work in
    **D50**. Comparing the two directly put the reference white in the wrong place
    and inflated every imported measurement's ΔE by ~1.5. Adapting here lands the
    reference in the same D50 space, so a perfect print scores ≈ 0 (Knut)."""
    return (1.0478112 * x + 0.0228866 * y - 0.0501270 * z,
            0.0295424 * x + 0.9904844 * y - 0.0170491 * z,
            -0.0092345 * x + 0.0150436 * y + 0.7521316 * z)


def _clean_instrument(raw: "str | None") -> str:
    """Tidy the .ti3 TARGET_INSTRUMENT string for display, or a clear fallback."""
    s = str(raw or "").strip().strip('"').strip()
    return s or "Unknown instrument"


# The CIE white points a chart's design XYZ may be expressed under, so the .ti2
# can say which one it used (its APPROX_WHITE_POINT header).
_WHITE_D65 = (95.047, 100.0, 108.883)
_WHITE_D50 = (96.422, 100.0, 82.521)

# Peak Y below which a .ti2's design XYZ can only be the normalised 0..1 form.
_NORMALISED_XYZ_MAX_Y = 5.0


def _design_xyz_to_100(xyz: np.ndarray) -> np.ndarray:
    """A chart's design XYZ on the 0..100 scale the rest of the report assumes.

    printtarg writes it either 0..100 or normalised 0..1 — both turn up in
    charts from the same Argyll version — and no header distinguishes them
    (APPROX_WHITE_POINT is 0..100 either way). A profiling chart always carries
    a near-white patch, so a peak Y this small can only be the normalised form;
    left unscaled it made every expected value 100× too dark (Knut)."""
    if xyz.size:
        peak = float(np.nanmax(xyz[:, 1]))
        if 0.0 < peak <= _NORMALISED_XYZ_MAX_Y:
            return xyz * 100.0
    return xyz


def _design_xyz_is_d65(keywords: "dict[str, str]") -> bool:
    """True when a .ti2's design XYZ is expressed under D65 rather than D50.

    ``printtarg`` derives an RGB chart's design XYZ from the device values via
    sRGB, whose white point is **D65**, and records it in APPROX_WHITE_POINT —
    but :func:`xyz_to_lab` and the measured .ti3 both work in **D50**. Reading
    the header lets a D50 chart (a spectral/CMYK workflow) pass through
    untouched while the far more common D65 one gets adapted. Undecidable
    headers keep the old behaviour rather than guessing."""
    raw = str(keywords.get("APPROX_WHITE_POINT", "")).strip().strip('"')
    parts = raw.replace(",", " ").split()
    if len(parts) != 3:
        return False
    try:
        wp = tuple(float(v) for v in parts)
    except ValueError:
        return False
    if wp[1] <= 0:
        return False
    near = lambda ref: sum((a - b) ** 2 for a, b in zip(wp, ref))  # noqa: E731
    return near(_WHITE_D65) < near(_WHITE_D50)


def _sheet_kind(ti3_path: "Path | str") -> str:
    """``verification`` (in ``runs/runN/verifications/<date>/`` or a ``-verify``
    stem), ``profiling`` (the run's own chart, directly in ``runs/runN/``) or
    ``standalone`` (in no run: an import, a file in Downloads)."""
    import re as _re
    p = Path(ti3_path)
    d = p.parent
    from core.file_manager import VERIFICATIONS_DIRNAME
    if p.stem.endswith("-verify") or d.parent.name == VERIFICATIONS_DIRNAME:
        return "verification"
    if _re.match(r"^run\d+$", d.name) and d.parent.name == "runs":
        return "profiling"
    return "standalone"


def _find_reference_ti2(ti3_path: Path) -> Path:
    """Locate the design ``.ti2`` for a measurement (#130). A verification lives
    in ``runs/runN/verifications/<date>/`` and holds only its ``.ti3``, so the
    reference chart may be next to it, the shared verify chart one level up
    (``verifications/<name>-verify.ti2``), or the run's profiling chart at the
    run root (``runs/runN/<name>.ti2`` when a verification re-measures the same
    chart). Falls back to the sibling path (which then triggers the device
    reference) when nothing is found."""
    same = ti3_path.with_suffix(".ti2")
    if same.is_file():
        return same
    stem = ti3_path.stem
    # The dated verification's own chart/ snapshot OUTRANKS the shared chart:
    # the shared one changes with every regenerate/restore, and judging an
    # old date against whatever chart happens to be live gave nonsense the
    # moment they differed (Sebastian, 2026-08-10: the gamut date's trend
    # point jumped to ΔE ≈ 41 after the chart was swapped — its own honest
    # value is 2.8). The snapshot is written at measure time for exactly this.
    snap = ti3_path.parent / "chart" / f"{stem}.ti2"
    if snap.is_file():
        return snap
    up = ti3_path.parent.parent / f"{stem}.ti2"           # shared verify chart
    if up.is_file():
        return up
    base = stem[:-7] if stem.endswith("-verify") else stem
    run_root = ti3_path.parent.parent.parent              # verifications/<date>/ → runN/
    cand = run_root / f"{base}.ti2"                        # profiling chart at run root
    if cand.is_file():
        return cand
    return same


def _reference_labs(ti2_path: Path) -> "dict[str, tuple]":
    """{SAMPLE_ID: expected Lab} from the chart's .ti2 design XYZ, or {}.

    The design XYZ is adapted to D50 first when the chart recorded it under D65
    (see :func:`_design_xyz_is_d65`), so the expected colours are the chart's
    true ideals — a neutral paper white and the textbook cube corners — instead
    of every value carrying the white-point skew (Knut)."""
    try:
        d = parse_ti3(ti2_path)
    except (Ti3ParseError, OSError):
        return {}
    xyz = _design_xyz_to_100(np.asarray(d.xyz, dtype=float))
    adapt = _design_xyz_is_d65(d.keywords)
    out = {}
    for i, sid in enumerate(d.sample_ids):
        x, y, z = xyz[i]
        if adapt:
            x, y, z = _bradford_d65_to_d50(x, y, z)
        out[sid] = xyz_to_lab((x / 100.0, y / 100.0, z / 100.0))
    return out


#: How far a patch's device RGB may differ from the chart's before the pairing
#: is called into question, on Argyll's 0..100 device scale.
#:
#: Sized from a real round trip rather than guessed: a 550-patch ChromIQ set
#: taken through i1Profiler and back came out with a worst channel error of
#: **0.5 on the 0..255 scale — 0.196 here — and not one patch above it.** That
#: error is rounding, nothing more (a value of 42.5 came back as 43). So 1.0 is
#: about five times the worst observed error, which leaves room for a different
#: writer's rounding while staying far below a real mix-up: two different
#: patches of a profiling chart are separated by whole device units, not
#: fractions of one.
PATCH_IDENTITY_TOL = 1.0


def verify_patch_identity(measured, ti2_path: "Path | None") -> dict:
    """Is each measured patch really the chart patch the report pairs it with?

    ChromIQ's report pairs a measurement with its chart by ``SAMPLE_ID``. For a
    measurement that came back through i1Profiler that ID is **only the row
    number**: its CxF objects are labelled ``M0_Measurement1``, ``c1`` … and
    carry no trace of the original patch, so ``reference_convert`` numbers them
    1..N by their order in the file. If anything reordered the patches on the
    way, every patch is compared against the wrong one — and the report looks
    entirely normal, because each comparison is against a real patch, just not
    the right one.

    That assumption is checkable, and cheaply. The chart knows what colour each
    patch was *asked* to be; the measurement carries the device values it was
    read from. So this walks **the pairing the report itself uses** and asks
    whether the two agree about the colour. A pairing that is right agrees to
    within rounding; a pairing that is wrong does not agree at all.

    **A shorter measurement is not a fault.** Reading part of a chart is a
    normal, supported state, so fewer patches simply means fewer to check —
    what matters is whether the ones that are there line up.

    A real round trip through i1Profiler (2026-08-08, 550 patches) preserved
    the order exactly, so this is expected to pass. It guards the case that
    does not: i1Profiler's own ``ScramblePatches`` setting, and any future tool
    in the chain.

    Returns a JSON-able verdict; never raises, because a report must still be
    produced when the check itself cannot run.
    """
    out: dict = {"checked": False, "verdict": "unchecked", "reason": "",
                 "compared": 0, "mismatched": 0, "worst": None,
                 "paired_by": "", "tolerance": PATCH_IDENTITY_TOL}
    if measured is None or measured.rgb is None or not len(measured.rgb):
        out["reason"] = "the measurement carries no device values"
        return out
    if ti2_path is None or not Path(ti2_path).is_file():
        out["reason"] = "there is no chart file to compare against"
        return out
    try:
        design = parse_ti3(Path(ti2_path))
    except (Ti3ParseError, OSError) as exc:
        out["reason"] = f"the chart file could not be read ({exc})"
        return out
    if design.rgb is None or not len(design.rgb):
        out["reason"] = "the chart file carries no device values"
        return out

    want = _rgb_to_0_100(np.asarray(design.rgb, dtype=float))
    got = _rgb_to_0_100(np.asarray(measured.rgb, dtype=float))

    # Pair exactly as the report does — by SAMPLE_ID — so this validates the
    # real pairing rather than a second one of its own. Falling back to
    # position when there are no IDs is not a weakness: that IS the i1Profiler
    # case, and the case worth guarding.
    by_id = {sid: i for i, sid in enumerate(design.sample_ids)} \
        if design.sample_ids else {}
    pairs = []
    if by_id and measured.sample_ids:
        for mi, sid in enumerate(measured.sample_ids):
            di = by_id.get(sid)
            if di is not None and di < len(want) and mi < len(got):
                pairs.append((di, mi))
        out["paired_by"] = "SAMPLE_ID"
    if not pairs:
        n = min(len(want), len(got))
        pairs = [(i, i) for i in range(n)]
        out["paired_by"] = "position"

    if not pairs:
        out["reason"] = "there is nothing to compare"
        return out

    diffs = np.array([np.abs(want[di] - got[mi]).max() for di, mi in pairs])
    out.update(checked=True, compared=int(len(pairs)),
               mismatched=int((diffs > PATCH_IDENTITY_TOL).sum()),
               worst=round(float(diffs.max()), 4))
    if out["mismatched"]:
        out["verdict"] = "mismatch"
        out["reason"] = (
            f"{out['mismatched']} of {len(pairs)} patches do not hold the "
            "colour the chart asked for, so the readings may not line up with "
            "the chart")
    else:
        out["verdict"] = "verified"
    return out


def per_patch_overlay(ti3_path: "str | Path",
                      ti2_path: "str | Path | None" = None) -> "list[dict]":
    """Per-patch expected-vs-measured data for the split-patch overlay (#134).

    Returns ``[{loc, exyz, xyz, de}, …]`` — one entry per patch that matches
    between the measured ``.ti3`` and its chart ``.ti2`` (by ``SAMPLE_ID``):

      * ``loc``  — the patch location (``SAMPLE_LOC``, e.g. ``"A1"``) used to
        place it on the chart page.
      * ``exyz`` — the chart's EXPECTED XYZ (D50-adapted, Y≈100), the same
        colour-correct reference the Measurement Report uses.
      * ``xyz``  — the MEASURED XYZ from the ``.ti3`` (Y≈100).
      * ``de``   — ΔE00 between them.

    This is exactly the shape ``TabMeasure._on_chart_measured`` renders, so a
    measurement already on disk can be shown as the overlay without re-reading.
    Returns ``[]`` when the reference ``.ti2`` is missing/unreadable or nothing
    matches (e.g. a foreign ``.ti3`` from a different chart) — the caller then
    falls back to the tabular "Inspect a measurement" view."""
    ti3_path = Path(ti3_path)
    ti2 = Path(ti2_path) if ti2_path else _find_reference_ti2(ti3_path)
    try:
        measured = parse_ti3(ti3_path)
        design = parse_ti3(ti2)
    except (Ti3ParseError, OSError):
        return []
    dxyz = _design_xyz_to_100(np.asarray(design.xyz, dtype=float))
    adapt = _design_xyz_is_d65(design.keywords)
    ref: "dict[str, tuple]" = {}
    for i, sid in enumerate(design.sample_ids):
        x, y, z = (float(v) for v in dxyz[i])
        if adapt:
            x, y, z = _bradford_d65_to_d50(x, y, z)
        loc = design.sample_locs[i] if i < len(design.sample_locs) else sid
        ref[sid] = (loc, (x, y, z))
    out: "list[dict]" = []
    for i, sid in enumerate(measured.sample_ids):
        if sid not in ref:
            continue
        loc, exyz = ref[sid]
        mxyz = tuple(float(v) for v in measured.xyz[i])
        de = ciede2000(
            xyz_to_lab(tuple(v / 100.0 for v in mxyz)),
            xyz_to_lab(tuple(v / 100.0 for v in exyz)))
        out.append({"loc": loc, "exyz": list(exyz),
                    "xyz": list(mxyz), "de": round(float(de), 2)})
    return out


def _stats(vals: "list[float]") -> dict:
    """The colour-accuracy metrics (Knut's revised set): averages and maxima over
    all patches, over the best 95 %, and over the worst 5 %, plus the spread.

    Splitting off the worst 5 % separates "how good is the bulk of the chart"
    (the 95 % averages/maxima) from "how bad are the few hardest patches" (the
    worst-5 % average) — far more telling than a single mean. ``mean``/``max``/
    ``p95`` are kept as aliases so the older trend series still reads.
    """
    if not vals:
        return {"n": 0}
    a = np.sort(np.asarray(vals, float))
    n = int(a.size)
    # #182 (CH-28, recorded in docs/design/measurement_report_limits.md): the
    # 95th percentile is the NEAREST-RANK
    # value, rank ceil(0.95 n), the ordinary meaning of the term and the one
    # the standards' rows use. `round(0.95 n)` was one rank lower on 48 % of
    # chart sizes, i.e. the lenient side. The same rank splits "best 95 %" from
    # "worst 5 %", so "95th percentile" and "largest of the best 95 %" are the
    # same patch by construction. Below 20 patches the worst-5 % set is EMPTY
    # (floor(0.05 n) = 0): its average is None, and the best 95 % is every
    # patch, which `small_sample` says so the report can say it too.
    k = max(1, min(n, int(math.ceil(n * 0.95))))
    low = a[:k]                              # the best 95 %
    high = a[k:]                             # the worst 5 % (empty below n = 20)
    return {
        "n": n,
        "avg_all":   round(float(a.mean()), 3),
        "avg_low95": round(float(low.mean()), 3),
        "avg_high5": round(float(high.mean()), 3) if high.size else None,
        "max_all":   round(float(a.max()), 3),
        "max_low95": round(float(low.max()), 3),
        "std":       round(float(a.std(ddof=1)) if n > 1 else 0.0, 3),
        "p95_rule":  "nearest-rank",
        "small_sample": bool(high.size == 0),
        # aliases kept for the trend series (report_trend reads mean/max/p95)
        "mean":  round(float(a.mean()), 3),
        "max":   round(float(a.max()), 3),
        "p95":   round(float(low.max()), 3),
    }


def _rgb_to_0_100(rgb):
    """Device RGB on Argyll's 0..100 scale, whatever scale it arrived on.

    i1Profiler measurement exports carry 0..255 code values; ChromIQ's own
    charts are already 0..100. One rule, used by every caller — comparing a
    0..100 array against a 0..255 one would make identical patches look
    completely different, which is exactly the failure this normalisation
    exists to avoid.
    """
    arr = np.asarray(rgb, dtype=float)
    return arr * (100.0 / 255.0) if float(arr.max()) > 101.0 else arr


def build_report(ti3_path: str | Path, worst_n: int = 16,
                 argyll_bin: "str | Path | None" = None) -> dict:
    """Compute a measurement report from a measured ``.ti3``.

    Finds the sibling ``.ti2`` for the expected reference. Returns a JSON-able
    dict; ``de`` blocks are absent when no reference is available (then only
    white/black and patch-count are reported).
    """
    ti3_path = Path(ti3_path)
    data = parse_ti3(ti3_path)
    lab = [xyz_to_lab((x / 100.0, y / 100.0, z / 100.0)) for x, y, z in data.xyz]

    # Date the report by the MEASUREMENT date when the .ti3 carries one
    # (CHROMIQ_MEASURED, written by Convert i1Profiler → TI3 from the export's
    # date), so imported runs trend by when they were measured, not when the
    # report is built. Native chartread files have no such keyword → build time.
    _measured = str(data.keywords.get("CHROMIQ_MEASURED") or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$", _measured):
        _created = _measured if _measured.count(":") == 2 else _measured + ":00"
    elif re.match(r"^\d{4}-\d{2}-\d{2}$", _measured):
        _created = f"{_measured}T00:00:00"
    else:
        # No keyword: the FILE's own time, not now() — a history rebuilt for
        # the trend must date each point by when it was measured, or every
        # date collapses onto the moment the window was opened (Sebastian,
        # 2026-08-10: four dates, one identical timestamp).
        try:
            _created = datetime.fromtimestamp(
                ti3_path.stat().st_mtime).isoformat(timespec="seconds")
        except OSError:
            _created = datetime.now().isoformat(timespec="seconds")
    report: dict = {
        "schema": REPORT_SCHEMA,
        "created": _created,
        "ti3": ti3_path.name,
        "chart": ti3_path.stem,
        "patches": data.n_patches,
        # The measuring instrument, from the .ti3's TARGET_INSTRUMENT keyword
        # (chartread writes it). Used in Report Scope and to warn when runs from
        # different instruments are mixed into one report (Knut).
        "instrument": _clean_instrument(data.keywords.get("TARGET_INSTRUMENT")),
        # True when this measurement is a colour-managed verification (carries
        # CHROMIQ_VERIFICATION) — chooses the report's title/scope wording and
        # keeps verification trends separate from profiling ones (#130).
        "is_verification": is_verification_ti3(data) or _sheet_kind(ti3_path) == "verification",
        # #182 (review F1): a sheet's KIND from where it lives, not from the
        # marker keyword alone. A verification measured before the keyword
        # existed (June 2026) sits in runs/runN/verifications/<date>/ and must
        # stay a graded verification; a file that is in no run at all (an
        # i1Profiler export in Downloads) is judged as it always was.
        "sheet_kind": ("verification" if is_verification_ti3(data)
                       else _sheet_kind(ti3_path)),
    }

    # Paper white (lightest) and darkest black by measured L*.
    Ls = [l[0] for l in lab]
    wi = int(np.argmax(Ls))
    bi = int(np.argmin(Ls))
    report["paper_white"] = {
        "loc": data.sample_locs[wi] if data.sample_locs else data.sample_ids[wi],
        "lab": [round(v, 2) for v in lab[wi]],
        "hex": _srgb_hex(tuple(data.xyz[wi])),
    }
    report["max_black"] = {
        "loc": data.sample_locs[bi] if data.sample_locs else data.sample_ids[bi],
        "lab": [round(v, 2) for v in lab[bi]],
        "hex": _srgb_hex(tuple(data.xyz[bi])),
    }

    # Device RGB, normalised to Argyll's 0..100 device scale. i1Profiler
    # measurement exports carry 0..255 code values; ChromIQ's own charts are
    # already 0..100. Normalise once so corner detection and the device-RGB
    # reference fallback below are correct regardless of the source (Knut).
    rgb100 = None
    if data.rgb is not None and len(data.rgb):
        rgb100 = _rgb_to_0_100(np.asarray(data.rgb, dtype=float))

    # Expected reference — three sources, in strict priority (#133 §9.1):
    #
    # "colorimetric" — the stored Lab targets beside a chart whose colours
    #   were already converted through the profile at build time (the From-
    #   profile-gamut charts). For such a chart the .ti2's XYZ is only the
    #   sRGB reading of ink amounts — a quantity with no relation to the Lab
    #   targets those amounts were computed to produce — so the sRGB paths
    #   below must be UNREACHABLE for it: a chart that claims a colorimetric
    #   reference whose file is gone gets no ΔE at all ("colorimetric-missing")
    #   rather than a plausible number from the wrong yardstick.
    # "design" — the sibling .ti2's design XYZ, matched by SAMPLE_ID.
    # "device" — no .ti2 matches (a stand-alone i1Profiler import): the
    #   reference is synthesised from the measurement's own device RGB read as
    #   sRGB, so an imported measurement is self-contained (Knut).
    ref_ti2 = _find_reference_ti2(ti3_path)
    ref: "dict[str, tuple]" = {}
    ref_source = "design"
    corner_ids: "set[str]" = set()
    from workflow.verification_print import (STATE_CONVERTED,
                                             STATE_CONVERTED_REF_MISSING,
                                             chart_conversion_state,
                                             colorimetric_reference_for)
    state = chart_conversion_state(ref_ti2 if ref_ti2.is_file() else None)
    if state == STATE_CONVERTED:
        from workflow.gamut_target import read_colorimetric_reference
        cref = read_colorimetric_reference(colorimetric_reference_for(ref_ti2))
        if cref is None:
            state = STATE_CONVERTED_REF_MISSING
        else:
            ref = cref["labs"]
            ref_source = "colorimetric"
            corner_ids = set(cref["corner_ids"])
            report["colorimetric"] = {
                "set_version": cref["set_version"],
                "intent": cref["intent"],
                "margin": cref["margin"],
                "master_total": cref["master_total"],
                "in_gamut": cref["in_gamut"],
            }
    if state == STATE_CONVERTED_REF_MISSING:
        ref_source = "colorimetric-missing"          # §9.1: refuse, never guess
    elif ref_source != "colorimetric":
        ref = _reference_labs(ref_ti2)
        matched_ids = sum(1 for sid in data.sample_ids if sid in ref) if ref else 0
        if not matched_ids and rgb100 is not None:
            from workflow.i1profiler_import import _patch_xyz
            ref = {}
            for i, sid in enumerate(data.sample_ids):
                r, g, b = (float(v) for v in rgb100[i])
                # _patch_xyz is sRGB→XYZ under D65; adapt to D50 so the
                # reference sits in the same space as the measured values.
                xyz_d50 = _bradford_d65_to_d50(*_patch_xyz(r, g, b))
                ref[sid] = xyz_to_lab(tuple(v / 100.0 for v in xyz_d50))
            ref_source = "device"
    report["reference_source"] = ref_source

    # Is row n really patch n? Reported, never acted on: this release only
    # states the answer, so no existing figure changes on the strength of it.
    report["patch_identity"] = verify_patch_identity(
        data, _find_reference_ti2(ti3_path))

    # How the sheet was produced (#130 feature A, §3.3 A15–A18): through the
    # profile or raw, which intent, which profile file, and who printed it —
    # read from the print record beside the chart. Absent for sheets printed
    # before the record existed; the report says so rather than guessing.
    from workflow.verification_print import read_print_record
    printing = read_print_record(ti3_path)
    if printing:
        # A17: a profile rebuilt after the sheet was printed invalidates the
        # comparison — the report can say so because the record carries the
        # file's modification time from print day.
        ppath, pmtime = printing.get("profile_path"), printing.get("profile_mtime")
        if ppath and pmtime:
            try:
                now_mtime = datetime.fromtimestamp(
                    Path(ppath).stat().st_mtime).isoformat(timespec="seconds")
                printing["profile_changed_since_print"] = now_mtime != pmtime
            except OSError:
                printing["profile_missing_now"] = True
        report["printing"] = printing

    # Pairing 3 (Knut, 2026-08-10): a sheet printed through the profile with
    # a white-mapping intent (relative/perceptual — anything but absolute)
    # maps the source white to PAPER white, so judging it against the design
    # reference's ideal L*=100 white counts the paper against the profile.
    # For exactly that case — and only against the design/device reference;
    # the colorimetric reference already includes the paper — the measured
    # values are normalised to the sheet's own paper white before comparing.
    # The physical readouts above (paper white, max black) stay absolute:
    # they describe the paper and ink, not the profile. Everything downstream
    # (corners, ΔE00, worst patches) inherits the chosen yardstick.
    report["yardstick"] = "absolute"
    if ref_source in ("design", "device") and printing:
        _col = printing.get("colour")
        _route = printing.get("route")
        _intent = str(printing.get("intent") or "")
        white_mapping = (_col == "through-profile"
                         and (_intent not in ("", "absolute")
                              or _route == "external-cm"))
        if white_mapping:
            white_xyz = np.asarray(data.xyz[wi], dtype=float)
            if float(white_xyz.min()) > 0.0:
                _d50 = np.array([96.42, 100.0, 82.49])
                lab = [xyz_to_lab(tuple(
                    (np.asarray(x, dtype=float) / white_xyz * _d50) / 100.0))
                    for x in data.xyz]
                report["yardstick"] = "media-relative"

    # The eight cube corners (paper white, composite black, the six ink
    # primaries/secondaries) — nearest patch to each corner by device RGB. Each
    # carries its measured colour and, when a reference exists, its expected
    # colour and ΔE00, so the report says something about the inks, not only the
    # instrument (Knut). rgb is device 0..100.
    report["corners"] = []
    if rgb100 is not None:
        rgb = rgb100
        for name, target in CUBE_CORNERS:
            diffs = np.abs(rgb - np.array(target))
            ci = int((diffs ** 2).sum(axis=1).argmin())
            # "present" = the chart actually has a patch AT this corner, not just
            # a nearest neighbour miles away. A minimal verification chart may omit
            # some corners; the report flags that (Knut).
            present = bool(float(diffs[ci].max()) <= CORNER_PRESENT_TOL)
            entry: dict = {
                "name": name,
                "loc": data.sample_locs[ci] if data.sample_locs else data.sample_ids[ci],
                "rgb": [round(v, 1) for v in rgb[ci]],
                "lab": [round(v, 2) for v in lab[ci]],
                "hex": _srgb_hex(tuple(data.xyz[ci])),
                "present": present,
            }
            r = ref.get(data.sample_ids[ci]) if ref else None
            if r is not None:
                entry["expected_lab"] = [round(v, 2) for v in r]
                entry["expected_hex"] = _srgb_hex(ref_xyz(ref, data, ci))
                entry["de"] = round(ciede2000(tuple(lab[ci]), r), 2)
            report["corners"].append(entry)

    if ref:
        des: list[tuple[float, int]] = []
        for i, sid in enumerate(data.sample_ids):
            # §9a rule 2: the eight cube corners are deliberately unreachable
            # colours — in the statistics they would drag every average and
            # maximum toward a number that says nothing about the profile.
            # They keep their own section (report["corners"]) instead.
            if sid in corner_ids:
                continue
            r = ref.get(sid)
            if r is not None:
                des.append((ciede2000(tuple(lab[i]), r), i))
        if des:
            report["de00"] = _stats([d for d, _ in des])
            # The in/out-of-gamut split (Knut, 2026-08-10): only against the
            # design reference — a colorimetric reference is in-gamut by
            # construction — and only when an Argyll path is provided; the
            # report degrades to exactly its old self when the test cannot
            # run (no Argyll, no profile on disk), never to an error. The
            # referee is the profile the sheet went through when the print
            # record names one that still exists, else the run's own built
            # profile — the only honest judge of "could this colour be
            # reached" for raw and unrecorded sheets.
            if ref_source == "design" and argyll_bin:
                try:
                    referee = None
                    if printing and printing.get("profile_path"):
                        cand = Path(printing["profile_path"])
                        referee = cand if cand.is_file() else None
                    if referee is None:
                        from core.file_manager import (Run,
                                                       VERIFICATIONS_DIRNAME)
                        d = ti3_path.parent
                        if d.parent.name == VERIFICATIONS_DIRNAME:
                            run_dir = d.parent.parent
                        else:
                            run_dir = d
                        cand = Run.for_dir(run_dir).built_profile_icc()
                        referee = cand if cand and cand.is_file() else None
                    if referee is not None:
                        from workflow.gamut_target import (MARGIN_SAFE,
                                                           flags_in_gamut)
                        ref_labs = [tuple(ref[data.sample_ids[i]])
                                    for _d, i in des]
                        flags = flags_in_gamut(ref_labs, referee, argyll_bin,
                                               margin=MARGIN_SAFE,
                                               intent="absolute")
                        d_in = [d for (d, _i), f in zip(des, flags) if f]
                        d_out = [d for (d, _i), f in zip(des, flags) if not f]
                        report["gamut_split"] = {
                            "profile": referee.name,
                            "margin": MARGIN_SAFE,
                            "n_in": len(d_in),
                            "n_out": len(d_out),
                            "de00_in": _stats(d_in) if d_in else None,
                            "de00_out": _stats(d_out) if d_out else None,
                        }
                except Exception as exc:      # noqa: BLE001 — degrade, never fail
                    log.debug("gamut split skipped: %s", exc)
            worst = sorted(des, key=lambda t: -t[0])[:worst_n]
            report["worst_patches"] = [{
                "loc": data.sample_locs[i] if data.sample_locs else data.sample_ids[i],
                "de": round(de, 2),
                "expected_hex": _srgb_hex(ref_xyz(ref, data, i)),
                "measured_hex": _srgb_hex(tuple(data.xyz[i])),
                "expected_lab": [round(v, 2) for v in ref[data.sample_ids[i]]],
                "measured_lab": [round(v, 2) for v in lab[i]],
            } for de, i in worst]

    # #182: the grey ramp and the 30 to 70 % tone ramps, under the same
    # yardstick as everything above. Both blocks are written even when the
    # chart cannot supply them, with the reason, so the report can say
    # "not computed, and why" (Knut, D25) instead of leaving a row blank.
    if rgb100 is not None:
        report["grey_balance"] = grey_balance_block(rgb100, lab, ref, data.sample_ids)
        report["ramps_30_70"] = ramps_block(rgb100, lab, ref, data.sample_ids)
    return report


def ref_xyz(ref_labs, data, i):
    """Expected XYZ(0..100) for patch i, recovered from its reference Lab."""
    from workflow.ti3_analysis import _lab_to_xyz_array
    lab = np.array([ref_labs[data.sample_ids[i]]])
    # _lab_to_xyz_array already scales to 0..100 (it multiplies the white point
    # by 100 internally); a second ×100 here overflowed _srgb_hex to white on
    # every expected swatch (worst-patches and cube corners). One scale only.
    return tuple(_lab_to_xyz_array(lab)[0])


def annotate_raw_drift(runs: "list[dict]") -> None:
    """Give every RAW verification sheet a drift figure (Knut, 2026-08-11).

    A raw sheet is expected to sit far from the design, so grading it against
    the profile's Pass thresholds fails a healthy printer forever. What a raw
    sheet can honestly answer is *"has the printer moved since last time?"* —
    the model of Argyll's own ``colverify``, which compares a measurement
    against a previous measurement. So, oldest-first, each recorded-raw
    design-referenced run is compared PRINT AGAINST PRINT with the previous
    such run: measured Lab vs measured Lab, patch by patch, matched by sample
    location. The first raw check becomes the baseline; a pair made with
    different charts is refused rather than mispaired (their device values
    must agree patch for patch — the same guarantee the per-date chart
    snapshots give).

    Mutates the run dicts: ``raw_drift`` = ``{"baseline": True}`` |
    ``{"avg", "max", "n", "prev"}`` | ``{"incomparable": True}``. Runs it
    cannot read are skipped silently — the report must never fail for a
    drift number.
    """
    prev: "dict | None" = None
    prev_data = None
    for r in runs:
        if not r.get("is_verification"):
            continue
        if r.get("reference_source") not in ("design", "device"):
            continue
        if (r.get("printing") or {}).get("colour") != "raw":
            continue
        origin = r.get("_origin_dir")
        name = r.get("ti3")
        if not origin or not name:
            continue
        try:
            data = parse_ti3(Path(origin) / str(name))
        except Ti3ParseError:
            continue
        if prev is None:
            r["raw_drift"] = {"baseline": True}
            prev, prev_data = r, data
            continue
        locs_a = prev_data.sample_locs or prev_data.sample_ids
        locs_b = data.sample_locs or data.sample_ids
        by_loc = {loc: i for i, loc in enumerate(locs_b)}
        same_chart = (len(locs_a) == len(locs_b)
                      and all(loc in by_loc for loc in locs_a))
        if same_chart and prev_data.rgb is not None and data.rgb is not None:
            import numpy as _np
            a = _np.asarray(prev_data.rgb, dtype=float)
            b = _np.asarray(data.rgb, dtype=float)[
                [by_loc[loc] for loc in locs_a]]
            # identical charts carry identical device values — anything else
            # means the chart changed between the checks
            same_chart = a.shape == b.shape and bool(
                _np.abs(a - b).max() <= 0.51)
        if not same_chart:
            r["raw_drift"] = {"incomparable": True,
                              "prev": prev.get("created")}
            prev, prev_data = r, data
            continue
        lab_a = [xyz_to_lab((x / 100.0, y / 100.0, z / 100.0))
                 for x, y, z in prev_data.xyz]
        lab_b = [xyz_to_lab((x / 100.0, y / 100.0, z / 100.0))
                 for x, y, z in data.xyz]
        des = [ciede2000(tuple(lab_a[i]), tuple(lab_b[by_loc[loc]]))
               for i, loc in enumerate(locs_a)]
        r["raw_drift"] = {
            "avg": round(sum(des) / len(des), 2),
            "max": round(max(des), 2),
            "n": len(des),
            "prev": prev.get("created"),
        }
        prev, prev_data = r, data


def save_report(report: dict, run_dir: str | Path) -> Path:
    """Write the report as timestamped JSON under ``<run_dir>/reports/`` and
    return the path. Timestamped so a printer's reports accrue for comparison."""
    from core.file_manager import reports_subdir
    reports = reports_subdir(run_dir)
    reports.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = reports / f"report_{ts}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info("measurement report saved: %s", path)
    return path


def list_reports(run_dir: str | Path) -> list[Path]:
    """All saved reports for a run, oldest first."""
    from core.file_manager import reports_subdir
    reports = reports_subdir(run_dir)
    if not reports.is_dir():
        return []
    return sorted(reports.glob("report_*.json"))


def list_project_reports(run_dir: str | Path) -> list[Path]:
    """Every saved report across ALL runs of this project — the printer's full
    measurement history (#40, Knut). *run_dir* is any run folder; its sibling
    ``run*`` folders are the printer's other builds. Sorted oldest-first by the
    report's ``created`` stamp (falling back to the filename). Falls back to the
    single run's reports when the folder isn't a ``runs/runN`` layout."""
    from core.file_manager import REPORTS_DIRNAME, VERIFICATIONS_DIRNAME
    run_dir = Path(run_dir)
    runs_root = run_dir.parent
    paths: list[Path] = []
    # #130: a dated verification folder (…/verifications/<date>/) trends across
    # ALL of this run's verification dates — a physically separate area from the
    # profiling runs/*/reports/, so profiling and verification never mix.
    if runs_root.name == VERIFICATIONS_DIRNAME:
        paths = list(runs_root.glob(f"*/{REPORTS_DIRNAME}/report_*.json"))
    elif runs_root.is_dir() and run_dir.name.startswith("run"):
        paths = list(runs_root.glob(f"*/{REPORTS_DIRNAME}/report_*.json"))
    if not paths:                                   # not a runs/runN layout
        paths = list_reports(run_dir)

    def _created(p: Path) -> str:
        try:
            return str(json.loads(read_text(p)).get("created", "")) or p.name
        except Exception:  # noqa: BLE001
            return p.name
    return sorted(paths, key=_created)


def report_trend(reports: "list[dict]") -> "list[dict]":
    """A time series for the trend chart from a list of report dicts (#40).

    One point per report that carries at least one plottable metric, in the
    input order (already oldest-first from :func:`list_project_reports`):
    ``{"created", "chart", "mean", "max", "p95", "white_L", "black_L"}`` —
    metric keys absent when the report lacks them (no design reference)."""
    series: list[dict] = []
    for r in reports:
        pt: dict = {"created": r.get("created"), "chart": r.get("chart")}
        de = r.get("de00") or {}
        # The five accuracy metrics the colour-accuracy chart plots (Knut), plus
        # the mean/max aliases older points used.
        for k in ("mean", "max", "p95",
                  "avg_all", "avg_low95", "avg_high5", "max_all", "max_low95"):
            if de.get(k) is not None:
                pt[k] = float(de[k])
        w, b = r.get("paper_white"), r.get("max_black")
        if w and w.get("lab"):
            pt["white_L"] = float(w["lab"][0])
        if b and b.get("lab"):
            pt["black_L"] = float(b["lab"][0])
        # Per-corner ΔE00-from-design, so the cube-corner chart can plot how
        # each ink drifts over time (Knut).
        corners = {c["name"]: float(c["de"])
                   for c in (r.get("corners") or []) if c.get("de") is not None}
        if corners:
            pt["corners"] = corners
        # #130 feature A: how the sheet was printed, so a trend can mark the
        # point where the method — and with it the question — changed (Q3).
        colour = (r.get("printing") or {}).get("colour")
        if colour:
            pt["printing_colour"] = colour
        if len(pt) > 2:                             # more than just created+chart
            series.append(pt)
    return series


def compare_reports(older: dict, newer: dict) -> dict:
    """Summarise the change between two reports of the same chart — the drift
    signal Knut wants (ink/printer/instrument ageing over time)."""
    out = {"older": older.get("created"), "newer": newer.get("created")}
    for key in ("mean", "median", "max", "p95", "std"):
        o = (older.get("de00") or {}).get(key)
        n = (newer.get("de00") or {}).get(key)
        if o is not None and n is not None:
            out[f"de00_{key}_delta"] = round(n - o, 3)
    # Paper white / black drift (ΔE00 between the two datings' white & black).
    for pt in ("paper_white", "max_black"):
        a, b = older.get(pt), newer.get(pt)
        if a and b:
            out[f"{pt}_de"] = round(
                ciede2000(tuple(a["lab"]), tuple(b["lab"])), 2)
    return out


def accuracy_verdict(de00: dict, avg_thr: float, max_thr: float) -> "tuple[list, bool]":
    """Per-metric Pass/Fail for one run's colour-accuracy stats.

    Returns ``(rows, all_pass)`` where each row is
    ``{"key", "value", "threshold", "pass"}`` for the five threshold-bearing
    metrics (:data:`ACCURACY_METRICS`); ``pass`` is None when the value is
    missing (no design reference). Pass = measured ≤ its threshold."""
    thr = {"avg": float(avg_thr), "max": float(max_thr)}
    rows: list[dict] = []
    all_pass = True
    de00 = de00 or {}
    for key, which in ACCURACY_METRICS:
        val = de00.get(key)
        t = thr[which]
        if val is None:
            rows.append({"key": key, "value": None, "threshold": t, "pass": None})
            continue
        ok = float(val) <= t + 1e-9
        all_pass = all_pass and ok
        rows.append({"key": key, "value": float(val), "threshold": t, "pass": ok})
    return rows, all_pass


# ---------------------------------------------------------------------------
# A saved report keeps the verdict it was given
# ---------------------------------------------------------------------------
#
# The thresholds are a GLOBAL setting (`core/settings.py`,
# `report_pass_threshold_avg` / `_max`), read afresh every time the report
# window is built. Until this was fixed, a saved report stored neither the
# thresholds it had been judged with nor the verdict it was given, and the
# window re-derived Pass and Fail from today's numbers — so nudging one spin
# box silently re-graded every historical report the user had ever made, and a
# dated record that changes its own verdict after the fact is not a record.
#
# Knut, #182, 2026-09-04: *"Verdict should be saved for each dated run."*
#
# So the report carries two more keys, written once, at the moment it is saved:
#
#   "pass_thresholds": {"avg": 2.0, "max": 3.0}
#   "verdict": {"rows": [...], "all_pass": true, "source": "gamut_in",
#               "graded": true}
#
# `rows` is stored as well as the thresholds, rather than instead of them,
# because the two answer different questions. The thresholds say what the user
# asked of this print; the rows say what ChromIQ actually concluded — which
# stays true even if a later version changes ACCURACY_METRICS or the in-gamut
# rule underneath it. A record has to survive its own software.
#
# NOTHING IS BUMPED AND NOTHING IS REWRITTEN. `REPORT_SCHEMA` stays at 7: the
# window treats a report with an older schema as stale and rebuilds it from the
# run's .ti3, so a bump would silently re-derive every report on disk — the
# exact thing this fix exists to stop. Both keys are optional; a report saved by
# an earlier ChromIQ simply does not have them, is detected by their ABSENCE,
# and is left exactly as it lies on disk.

#: The report TYPES (#182, W-A). The six names are Knut's own, approved
#: 2026-09-09: *"I would say we should use the names supplied for testing. This
#: may be changed later. Standards number is fine as part of the name."*
#:
#: These are the stored ids and they never change; the labels a user reads live
#: in the window and go through `tr()`.
REPORT_TYPE_SUMMARY   = "t1_colour_summary"      # one page, to hand over
REPORT_TYPE_FULL      = "t2_full_colour_check"   # today's report, unchanged
REPORT_TYPE_GREY      = "t3_grey_and_tone"
REPORT_TYPE_RECORD    = "t4_printing_record"     # nothing is graded, INFO only
REPORT_TYPE_ISO_8     = "t5_validation_print"    # ISO 12647-8
REPORT_TYPE_ISO_7     = "t6_contract_proof"      # ISO 12647-7

REPORT_TYPES: "tuple[str, ...]" = (
    REPORT_TYPE_SUMMARY, REPORT_TYPE_FULL, REPORT_TYPE_GREY,
    REPORT_TYPE_RECORD, REPORT_TYPE_ISO_8, REPORT_TYPE_ISO_7,
)

#: What a report with no type recorded IS. T2 is defined as today's report
#: unchanged, so this is what makes the feature ship invisible: every report
#: written before the dropdown existed, and every run nobody has chosen for,
#: renders exactly as it does today.
REPORT_TYPE_DEFAULT = REPORT_TYPE_FULL


def report_type(report: "dict | None") -> str:
    """The type a report was SAVED as, or T2 when it says nothing.

    ABSENCE IS THE SIGNAL, and it has to be, because `REPORT_SCHEMA` may not be
    bumped for this. The window treats an older schema as stale and rebuilds
    the report from the run's `.ti3`, so a bump would silently re-derive every
    report on disk. See the note above `VERDICT_SOURCE_IN_GAMUT`, where the
    same rule was written for the stored verdict, and
    `docs/design/measurement_report_limits.md` §6 for the precedent
    `compliance` set.

    An unknown id is treated as absent rather than honoured: a report written
    by a LATER ChromIQ that knows a seventh type must still open here, and
    rendering it as today's report is the one answer that cannot be wrong about
    the numbers.
    """
    t = (report or {}).get("report_type")
    return t if t in REPORT_TYPES else REPORT_TYPE_DEFAULT


#: The pulldown, in the order Knut approved (issue #182, section 19). Each
#: entry: id, the English NAME, and the one line under it that says when to
#: use it. English only in here; the window wraps both in `tr()`.
#:
#: `built` says whether ChromIQ can actually produce that document today. The
#: two ISO types cannot: the figures they judge against are behind a paywall
#: and ChromIQ has no permission to ship them. Knut, 2026-09-09: *"those
#: metrics, compliance sets and report types that depend on information in
#: documents that are behind the ISO paywall are marked as not yet implemented
#: and a reason for it."* So they are SHOWN and cannot be chosen, which is the
#: honest state, rather than hidden, which would say nothing at all.
REPORT_TYPE_MENU: "tuple[tuple[str, str, str, bool], ...]" = (
    (REPORT_TYPE_SUMMARY, "Colour summary (one page)",
     "One page to print and hand over with a job.", False),
    (REPORT_TYPE_FULL, "Full colour check",
     "Everything ChromIQ measures, in full. This is the report you know.",
     True),
    (REPORT_TYPE_GREY, "Grey and tone check",
     "The neutral axis and the mid-tone ramps, on their own.", False),
    (REPORT_TYPE_RECORD, "Printing record (not graded)",
     "A record of what was printed and measured, with nothing judged.", False),
    (REPORT_TYPE_ISO_8, "Validation print check (ISO 12647-8)",
     "Your print against a printing condition you supply.", False),
    (REPORT_TYPE_ISO_7, "Contract proof check (ISO 12647-7)",
     "The same, at the strictest level the trade uses.", False),
)

#: The heading that separates the two halves of the pulldown. The formal types
#: judge against a printing condition the USER supplies; the four above judge
#: against ChromIQ's own limit sets, and the heading does more work than any
#: word inside a name could.
REPORT_TYPE_MENU_HEADING = "Against a printing condition you supply"

#: Above this id in `REPORT_TYPE_MENU`, the heading is drawn.
REPORT_TYPE_MENU_SPLIT = REPORT_TYPE_ISO_8


def report_type_is_built(type_id: str) -> bool:
    """Whether ChromIQ can produce that document today."""
    for tid, _name, _blurb, built in REPORT_TYPE_MENU:
        if tid == type_id:
            return built
    return False


def report_type_name(type_id: str) -> str:
    """The English name. The window translates it."""
    for tid, name, _blurb, _built in REPORT_TYPE_MENU:
        if tid == type_id:
            return name
    return ""


def set_report_type(report: dict, type_id: str) -> None:
    """Record the type on a report, additively.

    Refuses an unknown id rather than storing it, because the id is what a
    later ChromIQ reads back and a typo would render as today's report for ever
    with nothing to say why.
    """
    if type_id not in REPORT_TYPES:
        raise ValueError(f"unknown report type {type_id!r}")
    report["report_type"] = type_id


#: The verdict's ``source``: which delta-E block it was passed on.
VERDICT_SOURCE_IN_GAMUT = "gamut_in"
VERDICT_SOURCE_ALL = "de00"
VERDICT_SOURCE_NONE = "none"


def is_drift_check(report: dict) -> bool:
    """True for a recorded-raw verification sheet judged against the design.

    Its job is drift, not accuracy: Pass/Fail against the profile thresholds
    would fail a healthy printer for ever (Knut, 2026-08-11). Unrecorded sheets
    keep the ordinary grading — nobody knows how they were printed.

    Lives here rather than in the report window because the STORED verdict and
    the DISPLAYED one have to agree about which sheets are graded at all, and
    two copies of that rule would eventually disagree.
    """
    report = report or {}
    return bool(report.get("is_verification")
                and report.get("reference_source") in ("design", "device")
                and (report.get("printing") or {}).get("colour") == "raw")


def graded_de00(report: dict) -> "tuple[dict, str]":
    """``(the delta-E block the verdict is passed on, its source name)``.

    A run with the in/out-of-gamut split is judged on its WITHIN-gamut figures:
    colours outside the gamut were never printable, so grading them against the
    thresholds would fail a healthy profile for its paper (Knut, 2026-08-10).
    Runs without a split are judged on all patches.
    """
    report = report or {}
    d_in = (report.get("gamut_split") or {}).get("de00_in")
    if d_in:
        return dict(d_in), VERDICT_SOURCE_IN_GAMUT
    de = report.get("de00")
    if de:
        return dict(de), VERDICT_SOURCE_ALL
    return {}, VERDICT_SOURCE_NONE


def stamp_verdict(report: dict, limits_or_avg, max_thr: "float | None" = None,
                  *, set_id: str = "", set_label: str = "",
                  edited: bool = False) -> dict:
    """Record the limit set and the verdict ON the report, and return it.

    Called once, by whoever is about to :func:`save_report` (or, after an
    unlock, :func:`rewrite_report`), never at display time. Mutates and returns
    *report* so it reads as one step at the call site.

    New form: ``stamp_verdict(report, limits, set_id=…, set_label=…)`` with
    *limits* a ``{row_id: Limit}`` mapping (a run's copy, see
    ``workflow.run_compliance``). Old form kept for callers and tests that
    still speak in two numbers: ``stamp_verdict(report, avg, max)``.

    What is written (#182, all additive, ``REPORT_SCHEMA`` stays 7):

    * ``pass_thresholds = {"avg", "max"}``: the all-patch average and maximum
      limits, so every reader of the old block still works;
    * ``compliance = {"set_id", "set_label", "thresholds", "edited"}``: the
      set and the run's copy of its limits at the moment of judging;
    * ``verdict = {"rows", "all_pass", "source", "graded", "overall",
      "summary"}``: one row per judged row with its word, and the column's
      one word with the numbers behind it.
    """
    from workflow.compliance_sets import (FAIL, N_A, PASS, legacy_pair,
                                          limits_to_json)
    if isinstance(limits_or_avg, (int, float)):
        limits = limits_from_pair(float(limits_or_avg), float(max_thr))
        if not set_id:
            set_id, set_label = "pair", "two thresholds"
    else:
        limits = dict(limits_or_avg)
        if not set_id:
            set_id, set_label = "chromiq_default", "ChromIQ default (recommended)"
    _de, source = graded_de00(report)
    graded = is_graded_sheet(report)
    rows = judge(report, limits)
    summary = summarise(report, limits, rows, set_id, set_label)
    judged = [r for r in rows if r["word"] in (PASS, FAIL)]
    avg_thr, mx_thr = legacy_pair(limits)
    report["pass_thresholds"] = {"avg": float(avg_thr), "max": float(mx_thr)}
    report["compliance"] = {
        "set_id": set_id,
        "set_label": set_label,
        "thresholds": limits_to_json(limits),
        "edited": bool(edited),
    }
    report["verdict"] = {
        "rows": rows,
        # A sheet that is not graded carries None, not a pass and not a fail.
        "all_pass": (all(r["word"] == PASS for r in judged)
                     if graded and source != VERDICT_SOURCE_NONE and judged
                     else None),
        "source": source,
        "graded": graded,
        "overall": summary.word if source != VERDICT_SOURCE_NONE else N_A,
        "summary": {"checked": summary.checked, "total": summary.total,
                    "failed": summary.failed, "cond": summary.conditional,
                    "not_computed": summary.not_computed,
                    "reason": summary.reason},
    }
    return report


def recorded_verdict(report: dict) -> "dict | None":
    """The verdict this report was SAVED with, or None if it carries none.

    None means "saved by a ChromIQ that did not record one" — never "it
    failed". The caller must say which of the two it is showing.
    """
    v = (report or {}).get("verdict")
    if not isinstance(v, dict) or not isinstance(v.get("rows"), list):
        return None
    return v


def recorded_thresholds(report: dict) -> "tuple[float, float] | None":
    """The ``(average, maximum)`` thresholds this report was judged with, or
    None when it was saved before ChromIQ recorded them."""
    t = (report or {}).get("pass_thresholds")
    if not isinstance(t, dict):
        return None
    try:
        return float(t["avg"]), float(t["max"])
    except (KeyError, TypeError, ValueError):
        return None


def _run_label(r: dict) -> str:
    """A run's ``Profile @ date`` label for warning lists (no quotes)."""
    return f'{r.get("chart") or "?"} @ {str(r.get("created") or "")[:19]}'


def report_scope(runs: "list[dict]") -> dict:
    """Aggregate the runs included in a report into the Report Scope summary
    (Knut): the profiles involved (name + instrument + run count), the total run
    count, the overall date range, and any red-flag warnings.

    Warnings — because the report can't tell which printer a run belongs to, and
    the cube-corner stats need all eight corners:
      * ``instrument`` — runs whose instrument differs from the dominant one
        (mixing instruments, or possibly mixing printers).
      * ``corners`` — runs whose chart is missing one or more cube corners.
    """
    from collections import Counter

    profiles: "dict[str, dict]" = {}
    for r in runs:
        name = r.get("chart") or "?"
        p = profiles.setdefault(name, {"name": name, "instruments": [], "n": 0})
        p["instruments"].append(r.get("instrument") or "Unknown instrument")
        p["n"] += 1
    prof_list = [{"name": p["name"],
                  "instrument": Counter(p["instruments"]).most_common(1)[0][0],
                  "n": p["n"]}
                 for p in profiles.values()]

    dates = sorted(str(r.get("created") or "")[:10] for r in runs if r.get("created"))
    date_range = (dates[0], dates[-1]) if dates else ("", "")

    warnings: list[dict] = []
    insts = [r.get("instrument") or "Unknown instrument" for r in runs]
    if len(set(insts)) > 1:
        dominant = Counter(insts).most_common(1)[0][0]
        odd = [{"run": _run_label(r), "instrument": r.get("instrument") or "Unknown instrument"}
               for r in runs
               if (r.get("instrument") or "Unknown instrument") != dominant]
        warnings.append({"kind": "instrument", "dominant": dominant, "runs": odd})

    missing = []
    for r in runs:
        miss = [c["name"] for c in (r.get("corners") or []) if c.get("present") is False]
        if miss:
            missing.append({"run": _run_label(r), "missing": miss})
    if missing:
        warnings.append({"kind": "corners", "runs": missing})

    # #130 feature A (Q3): verifications printed different ways answer
    # different questions — through the profile grades the profile, raw grades
    # the printer — so a report mixing them must mark where the method
    # changed, or the trend silently changes meaning at that point.
    verifs = [r for r in runs if r.get("is_verification")]
    if verifs:
        def _method(r: dict) -> str:
            # A gamut chart printed raw is its own method — the profile is
            # inside the chart, so it never belongs in the "printed raw"
            # group of the mixed-methods warning (Knut, 2026-08-11).
            if r.get("reference_source") in ("colorimetric",
                                             "colorimetric-missing"):
                return "gamut"
            pr = r.get("printing") or {}
            if pr.get("colour") == "through-profile" \
                    and pr.get("route") == "external-cm":
                return "external-cm"
            return pr.get("colour") or "unrecorded"
        methods = {_method(r) for r in verifs}
        if len(methods) > 1:
            warnings.append({
                "kind": "printing",
                "runs": [{"run": _run_label(r), "method": _method(r)}
                         for r in verifs],
            })

    # #182 (D9): every dated verification of one profile run is judged with
    # one limit set. Two sets in one report can only come from archived
    # history or from runs of different projects, and the reader must see
    # where the yardstick changed.
    sets = {}
    for r in runs:
        c = recorded_compliance(r)
        if c:
            sets[str(c.get("set_label") or c.get("set_id"))] = True
    if len(sets) > 1:
        warnings.append({
            "kind": "compliance",
            "runs": [{"run": _run_label(r),
                      "set": str((recorded_compliance(r) or {}).get("set_label")
                                 or (recorded_compliance(r) or {}).get("set_id")
                                 or "")}
                     for r in runs if recorded_compliance(r)],
        })

    return {"profiles": prof_list, "total": len(runs),
            "date_range": date_range, "warnings": warnings}


# ---------------------------------------------------------------------------
# #182: the grey ramp, the tone ramps, and the per-row values a limit set judges
# ---------------------------------------------------------------------------
#
# A row of the limits table is a statistic over a POPULATION of patches. The
# five ΔE00 rows are the statistics `_stats` has always produced; the two
# grey-balance rows and the tone-ramp row are computed here. The rules are
# CH-10, recorded in docs/design/measurement_report_limits.md:
#
#   grey ramp   = every patch with max(R,G,B) − min(R,G,B) ≤ 1.0 device units;
#                 eligible when it has at least 8 distinct levels (levels within
#                 0.5 count as one, the PAPER patch counts as a level), reaches
#                 ≥ 90 at the light end and ≤ 10 at the dark end. The
#                 statistics leave the bare paper out (its ΔCh is 0 by
#                 construction under the media-relative yardstick and the
#                 paper's own tint under the absolute one; the report has a
#                 paper-white row) and keep the composite black in.
#   ΔCh         = hypot(Δa*, Δb*) against each patch's REFERENCE value under the
#                 report's yardstick (ISO 12647-7:2016 §3.2; the same arithmetic
#                 as the standards' near-neutral rows, so shape A's merged row
#                 is one arithmetic). Not TR 015's substrate-relative aim: a
#                 perfect relative-intent print scores 0 here and up to 1.78 ΔCh
#                 there (measured, CS §1.3).
#   tone ramps  = per device axis, the patches whose other two channels are
#                 within 1.0 of 100; tone value TV = 100 − channel; the row uses
#                 30 ≤ TV ≤ 70 and needs ≥ 3 distinct TVs with the outermost
#                 ≥ 20 apart. The R=G=B ramp is the fourth axis (the K analogue).
#                 |ΔL*| against the reference, largest.
GREY_SPREAD_TOL = 1.0
GREY_LEVEL_TOL = 0.5
GREY_MIN_LEVELS = 8
GREY_LIGHTEST_MIN = 90.0
GREY_DARKEST_MAX = 10.0
GREY_PAPER_LEVEL = 99.5
RAMP_OTHER_CHANNELS_MIN = 99.0
RAMP_TV_LOW, RAMP_TV_HIGH = 30.0, 70.0
RAMP_MIN_STEPS = 3
RAMP_MIN_SPAN = 20.0

#: Reason codes for a row that could not be computed. The report window turns
#: them into sentences through tr(); the JSON keeps the code.
REASON_NO_GREYS = "no_greys"
REASON_TOO_FEW_STEPS = "too_few_steps"
REASON_NO_WHITE = "no_white"
REASON_NO_BLACK = "no_black"
REASON_NO_REFERENCE = "no_reference"
REASON_NEEDS_REFERENCE_FILE = "needs_reference_file"
REASON_NO_RAMP = "no_ramp"
REASON_SMALL_SAMPLE = "small_sample"
REASON_PRINTING_UNRECORDED = "printing_unrecorded"
REASON_NO_CORNERS = "no_corners"
REASON_NOT_COMPUTED = "not_computed"     # the block is missing from this report


def _distinct_levels(levels: "list[float]", tol: float = GREY_LEVEL_TOL) -> int:
    """How many distinct values a sorted list holds when values within *tol*
    of each other count as one."""
    n = 0
    last = None
    for v in sorted(levels):
        if last is None or v - last > tol:
            n += 1
            last = v
    return n


def grey_balance_block(rgb100, lab, ref: "dict[str, tuple]",
                       sample_ids: "list[str]") -> dict:
    """The grey-ramp block of a report (see the notes above)."""
    rgb = np.asarray(rgb100, dtype=float)
    idx = [i for i in range(len(sample_ids))
           if float(rgb[i].max() - rgb[i].min()) <= GREY_SPREAD_TOL]
    block: dict = {"n_greys": len(idx), "levels": 0, "eligible": False,
                   "reason": None, "avg": None, "max": None, "per_level": []}
    if not idx:
        block["reason"] = REASON_NO_GREYS
        return block
    levels = [float(rgb[i].mean()) for i in idx]
    block["levels"] = _distinct_levels(levels)
    if block["levels"] < GREY_MIN_LEVELS:
        block["reason"] = REASON_TOO_FEW_STEPS
    elif max(levels) < GREY_LIGHTEST_MIN:
        block["reason"] = REASON_NO_WHITE
    elif min(levels) > GREY_DARKEST_MAX:
        block["reason"] = REASON_NO_BLACK
    else:
        block["eligible"] = True
    per: list[dict] = []
    for i in idx:
        level = float(rgb[i].mean())
        if level >= GREY_PAPER_LEVEL:
            continue                       # the bare paper: not in the statistics
        r = ref.get(sample_ids[i]) if ref else None
        if r is None:
            continue
        dch = math.hypot(lab[i][1] - r[1], lab[i][2] - r[2])
        per.append({"level": round(level, 1), "dch": round(float(dch), 3),
                    "loc": sample_ids[i]})
    block["per_level"] = sorted(per, key=lambda d: -d["level"])
    if block["eligible"]:
        if not per:
            block["eligible"] = False
            block["reason"] = REASON_NO_REFERENCE
        else:
            vals = [d["dch"] for d in per]
            block["avg"] = round(float(np.mean(vals)), 3)
            block["max"] = round(float(np.max(vals)), 3)
    return block


def ramps_block(rgb100, lab, ref: "dict[str, tuple]",
                sample_ids: "list[str]") -> dict:
    """The 30 to 70 % tone-ramp block of a report (ISO 12647-8:2021 4.2.7 is
    the row that reads it; a *should*)."""
    rgb = np.asarray(rgb100, dtype=float)
    axes: dict = {}
    overall_max = None
    any_eligible = False
    for name, ch, others in (("R", 0, (1, 2)), ("G", 1, (0, 2)), ("B", 2, (0, 1)),
                             ("grey", None, ())):
        if ch is None:
            members = [i for i in range(len(sample_ids))
                       if float(rgb[i].max() - rgb[i].min()) <= GREY_SPREAD_TOL]
            tv_of = lambda i: 100.0 - float(rgb[i].mean())   # noqa: E731
        else:
            members = [i for i in range(len(sample_ids))
                       if all(float(rgb[i][o]) >= RAMP_OTHER_CHANNELS_MIN for o in others)]
            tv_of = lambda i, ch=ch: 100.0 - float(rgb[i][ch])   # noqa: E731
        band = [i for i in members if RAMP_TV_LOW <= tv_of(i) <= RAMP_TV_HIGH]
        tvs = [tv_of(i) for i in band]
        distinct = _distinct_levels(tvs)
        span = (max(tvs) - min(tvs)) if tvs else 0.0
        eligible = distinct >= RAMP_MIN_STEPS and span >= RAMP_MIN_SPAN
        dls = []
        for i in band:
            r = ref.get(sample_ids[i]) if ref else None
            if r is not None:
                dls.append(abs(float(lab[i][0]) - float(r[0])))
        axis = {"steps": distinct, "span": round(span, 1), "eligible": eligible,
                "max_dl": round(float(max(dls)), 3) if (eligible and dls) else None}
        axes[name] = axis
        if eligible and dls:
            any_eligible = True
            overall_max = max(overall_max or 0.0, axis["max_dl"])
    return {"axes": axes, "eligible": any_eligible,
            "reason": None if any_eligible else REASON_NO_RAMP,
            "max_dl": round(float(overall_max), 3) if overall_max is not None else None}


def is_graded_sheet(report: dict) -> bool:
    """Whether a measurement is judged against limits at all.

    Graded: a verification sheet, or a file that is in no run at all (an
    i1Profiler export, a file in Downloads), with a reference, that is not a
    raw drift check. Not graded (every row INFO): a raw drift check
    (:func:`is_drift_check`), and the run's own PROFILING chart, which is
    printed raw by definition and whose distance from the chart's design says
    nothing a limit could judge (CH-16). The kind comes from ``sheet_kind``
    (where the file lives, review F1), so a verification measured before the
    marker keyword existed keeps its verdict. ONE rule for the stored verdict
    and the window, as :func:`is_drift_check` already is.
    """
    report = report or {}
    kind = report.get("sheet_kind") or (
        "verification" if report.get("is_verification") else "profiling")
    if kind == "profiling":
        return False
    if is_drift_check(report):
        return False
    return graded_de00(report)[1] != VERDICT_SOURCE_NONE


def _hue_difference_ab(lab_a, lab_b) -> float:
    """CIE 1976 metric hue difference ΔH*ab, unsigned (CS Q6)."""
    dl = float(lab_a[0]) - float(lab_b[0])
    da = float(lab_a[1]) - float(lab_b[1])
    db = float(lab_a[2]) - float(lab_b[2])
    de_ab2 = dl * dl + da * da + db * db
    ca = math.hypot(float(lab_a[1]), float(lab_a[2]))
    cb = math.hypot(float(lab_b[1]), float(lab_b[2]))
    dc = ca - cb
    return math.sqrt(max(0.0, de_ab2 - dl * dl - dc * dc))


def row_values(report: dict) -> "dict[str, dict]":
    """``{row_id: {"value", "reason", "graded"}}`` for every row ChromIQ can
    compute from *report*. ``value`` is None with a reason code when the chart
    or the reference cannot supply the row; ``graded`` is False for a row that
    is shown for information only on this sheet (CH-17), None to inherit the
    sheet's own grading.
    """
    report = report or {}
    de, source = graded_de00(report)
    out: "dict[str, dict]" = {}

    def put(rid, value, reason=None, graded=None):
        out[rid] = {"value": (float(value) if value is not None else None),
                    "reason": reason, "graded": graded}

    # -- the five ΔE00 rows
    from workflow.compliance_sets import ROWS
    if source == VERDICT_SOURCE_NONE:
        for r in ROWS:
            if r.metric_key:
                put(r.id, None, REASON_NO_REFERENCE)
    else:
        for r in ROWS:
            if not r.metric_key:
                continue
            v = de.get(r.metric_key)
            if v is None:
                put(r.id, None, REASON_SMALL_SAMPLE if de.get("small_sample")
                    else REASON_NO_REFERENCE)
            else:
                put(r.id, v)

    # -- grey balance (INFO when nobody recorded how the sheet was printed and
    #    the reference is the chart's design: in absolute Lab the paper's own
    #    tint would fail the row, CH-17)
    gb = report.get("grey_balance") or {}
    grey_graded = None
    if (not report.get("printing")
            and report.get("reference_source") in ("design", "device")):
        grey_graded = False
    if not gb:
        # an older report, or one whose measurement file could not be read
        # again: the block is absent, which is not the same as "no greys" (N9)
        put("grey_balance_neutral_ramp_avg", None, REASON_NOT_COMPUTED)
        put("grey_balance_neutral_ramp_max", None, REASON_NOT_COMPUTED)
    elif gb.get("eligible") and gb.get("avg") is not None:
        put("grey_balance_neutral_ramp_avg", gb["avg"],
            REASON_PRINTING_UNRECORDED if grey_graded is False else None, grey_graded)
        put("grey_balance_neutral_ramp_max", gb["max"],
            REASON_PRINTING_UNRECORDED if grey_graded is False else None, grey_graded)
    else:
        put("grey_balance_neutral_ramp_avg", None, gb.get("reason") or REASON_NO_GREYS)
        put("grey_balance_neutral_ramp_max", None, gb.get("reason") or REASON_NO_GREYS)

    # -- the 30 to 70 % ramps
    rp = report.get("ramps_30_70") or {}
    if rp.get("eligible") and rp.get("max_dl") is not None:
        put("ramps_30_70_dl_max", rp["max_dl"])
    else:
        put("ramps_30_70_dl_max", None, rp.get("reason") or REASON_NO_RAMP)

    # -- rows that need a reference for the printing condition: computable
    #    from the corners only against a colorimetric reference (CS Q9)
    corners = {c.get("name"): c for c in (report.get("corners") or [])}
    if report.get("reference_source") == "colorimetric":
        w = corners.get("W")
        if w and w.get("present") and w.get("de") is not None:
            put("substrate_de00_max", w["de"])
        else:
            put("substrate_de00_max", None, REASON_NO_CORNERS)
        solid = [corners[k]["de"] for k in ("C", "M", "Y", "K")
                 if corners.get(k) and corners[k].get("present")
                 and corners[k].get("de") is not None]
        if solid:
            put("solids_de00_max", max(solid))
        else:
            put("solids_de00_max", None, REASON_NO_CORNERS)
        hues = [_hue_difference_ab(corners[k]["lab"], corners[k]["expected_lab"])
                for k in ("C", "M", "Y")
                if corners.get(k) and corners[k].get("present")
                and corners[k].get("expected_lab") is not None]
        if hues:
            put("cmy_solids_dhab_max", max(hues))
        else:
            put("cmy_solids_dhab_max", None, REASON_NO_CORNERS)
    else:
        for rid in ("substrate_de00_max", "solids_de00_max", "cmy_solids_dhab_max"):
            put(rid, None, REASON_NEEDS_REFERENCE_FILE)
    return out


def judge(report: dict, limits: "dict") -> "list[dict]":
    """Every row of one report against one limit set.

    Returns rows in table order, one per row that produces a verdict word:
    ``{"row_id", "key", "value", "threshold", "should", "pass", "word",
    "reason"}``. ``key`` is the old ``de00`` key for the five ChromIQ rows (so
    older readers of the verdict block still find ``avg_all`` and friends) and
    the row id otherwise; ``pass`` keeps the old True / False / None shape
    (True for PASS, False for FAIL, None for every other word).
    """
    from workflow.compliance_sets import (FAIL, PASS, ROWS, Limit,
                                          row_verdict)
    graded_sheet = is_graded_sheet(report)
    values = row_values(report)
    rows: list[dict] = []
    for r in ROWS:
        lim = limits.get(r.id)
        if lim is None or not isinstance(lim, Limit):
            lim = Limit.none()
        cell = values.get(r.id)
        value = cell["value"] if cell else None
        graded = graded_sheet
        if cell and cell.get("graded") is False:
            graded = False
        word = row_verdict(lim, value, graded)
        if word is None:
            continue
        rows.append({
            "row_id": r.id,
            "key": r.metric_key or r.id,
            "value": value,
            "threshold": lim.number if lim.is_numeric else None,
            "should": bool(lim.is_should),
            "pass": True if word == PASS else (False if word == FAIL else None),
            "word": word,
            "reason": (cell or {}).get("reason"),
        })
    return rows


def summarise(report: dict, limits: "dict", rows: "list[dict]", set_id: str,
              set_label: str = ""):
    """The column summary for *rows* (see :func:`compliance_sets.set_summary`).

    *set_label* is what the run stored. It matters only when this ChromIQ no
    longer defines *set_id*: the label is then the only evidence left of what
    the sheet was judged against, and a column named after a standard may not
    print an unqualified PASS.
    """
    from workflow.compliance_sets import (SET_BY_ID, Limit, set_summary,
                                          applies_a_standard)
    s = SET_BY_ID.get(set_id)
    pairs = []
    for row in rows:
        lim = limits.get(row["row_id"])
        pairs.append((lim if isinstance(lim, Limit) else Limit.none(), row["word"]))
    # THE RAW ID, NOT THE RESOLVED SET'S. `getattr(s, "id", None)` is None for
    # a set this ChromIQ no longer defines, which threw away the only evidence
    # left about what the run was judged against.
    return set_summary(pairs,
                       set_is_iso=applies_a_standard(set_id, set_label),
                       graded=is_graded_sheet(report))


def limits_from_pair(avg_thr: float, max_thr: float) -> "dict":
    """The old two-number model as a limit set: the average threshold on the
    three average rows, the maximum threshold on the two maximum rows."""
    from workflow.compliance_sets import (OLD_AVG_ROWS, OLD_MAX_ROWS, Limit,
                                          factory_limits)
    limits = factory_limits("chromiq_default")
    for rid in OLD_AVG_ROWS:
        limits[rid] = Limit.value(avg_thr)
    for rid in OLD_MAX_ROWS:
        limits[rid] = Limit.value(max_thr)
    return limits


def recorded_compliance(report: dict) -> "dict | None":
    """The limit-set block a report was SAVED with, or None (an older
    ChromIQ, or a damaged block). None never means "it failed"."""
    c = (report or {}).get("compliance")
    if not isinstance(c, dict) or not isinstance(c.get("thresholds"), dict):
        return None
    return c


def rewrite_report(path: "str | Path", report: dict) -> Path:
    """Write *report* back to the file it came from, same name, same date.

    #182 (CH-29): recalculating a run's dated reports after an unlock must not
    call :func:`save_report`, which names the file by now() and would leave two
    live reports per date. The caller archives first (``Verification.
    archive_reports``); this only rewrites.
    """
    path = Path(path)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path
