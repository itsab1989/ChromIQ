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

from core.file_manager import write_json_atomically
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


def _declared_corner_rows(sample_ids, corner_ids, ref_devices) -> "dict[str, int]":
    """``{corner name: row index}`` from the chart's OWN declaration, or ``{}``.

    A FROM PROFILE GAMUT chart names its eight corner patches by SAMPLE_ID in
    its colorimetric reference (``CHROMIQ_CORNER_IDS``), and those patches are
    the only ones printed at an exact cube corner. Nothing read that
    declaration until 2026-09-18: the corners were found by nearest device
    value over the whole chart, so a selected colour that happens to sit at
    device (0,0,0) was read as the composite black while the declared corner
    beside it was read by nobody — and, being no corner as far as the report
    was concerned, that patch stayed in the ΔE00 statistics as well, counted
    twice. Measured on a 200-colour chart: the K corner came off sample 2
    rather than the declared sample 202, and R off sample 141.

    WHICH declared id is which corner is decided by the ink amount the
    reference itself records for it, not by the order the ids were written in,
    so a reference re-cut in another order still answers correctly. A chart
    that declares nothing (every chart that is not a gamut chart, and every
    gamut chart built before the declaration existed) returns ``{}`` and the
    caller does exactly what it has always done.
    """
    if not corner_ids or not ref_devices:
        return {}
    where: "dict[str, int]" = {}
    for i, sid in enumerate(sample_ids):
        where.setdefault(sid, i)

    def _order(sid: str):
        try:
            return (0, int(sid), "")
        except (TypeError, ValueError):
            return (1, 0, str(sid))

    free = [(sid, ref_devices[sid]) for sid in sorted(corner_ids, key=_order)
            if sid in ref_devices and sid in where]
    out: "dict[str, int]" = {}
    for name, target in CUBE_CORNERS:
        best_sid, best_d = None, None
        for sid, dev in free:
            d = max(abs(float(a) - float(b)) for a, b in zip(dev, target))
            if best_d is None or d < best_d:
                best_sid, best_d = sid, d
        # A declaration that names a patch nowhere near the corner it would
        # have to be is not believed: the nearest-value search below is then
        # the honest answer, and it is also what says "no patch here".
        if best_sid is not None and best_d <= CORNER_PRESENT_TOL:
            out[name] = where[best_sid]
            free = [f for f in free if f[0] != best_sid]
    return out


def corners_block(rgb100, lab, ref, data,
                  corner_ids=None, corner_devices=None) -> "list[dict]":
    """The eight cube corners of one chart, measured or modelled.

    Paper white, composite black and the six ink primaries and secondaries:
    the patch the chart DECLARES as each corner where it declares one, else
    the nearest patch to it by device RGB. Each carries its colour and, when
    a reference exists, its expected colour and ΔE00, so the report says
    something about the inks and not only about the instrument (Knut).
    *rgb100* is device 0..100.

    **A FUNCTION RATHER THAN A PARAGRAPH INSIDE `analyse`, since B8-612.**
    The three rows judged against a colorimetric reference
    (``substrate_de00_max``, ``solids_de00_max``, ``cmy_solids_dhab_max``)
    are computed from this block and from nothing else, so
    `workflow.preset_eligibility` cannot say whether a FROM PROFILE GAMUT
    chart could answer them without building one. It builds it by calling
    THIS, which is what keeps the two windows from acquiring a second opinion
    about which corners a chart has.
    """
    out: "list[dict]" = []
    if rgb100 is None:
        return out
    rgb = rgb100
    declared_rows = _declared_corner_rows(data.sample_ids, corner_ids,
                                          corner_devices)
    for name, target in CUBE_CORNERS:
        ci = declared_rows.get(name)
        declared = ci is not None
        if declared:
            # The chart says this patch IS the corner, so it is present —
            # it was printed at the corner's own ink amount whatever the
            # measurement's device column has since been normalised to.
            present = True
        else:
            diffs = np.abs(rgb - np.array(target))
            ci = int((diffs ** 2).sum(axis=1).argmin())
            # "present" = the chart actually has a patch AT this corner, not
            # just a nearest neighbour miles away. A minimal verification chart
            # may omit some corners; the report flags that (Knut).
            present = bool(float(diffs[ci].max()) <= CORNER_PRESENT_TOL)
        entry: dict = {
            "name": name,
            "loc": data.sample_locs[ci] if data.sample_locs else data.sample_ids[ci],
            # WHICH PATCH THIS IS, unambiguously. `loc` is the sheet
            # position and is the right thing to print, but it cannot be
            # paired back with the chart's own files, so establishing that
            # a corner had been read off the wrong patch took a separate
            # probe (B8-393).
            "sample": data.sample_ids[ci],
            "rgb": [round(v, 1) for v in rgb[ci]],
            "lab": [round(v, 2) for v in lab[ci]],
            "hex": _srgb_hex(tuple(data.xyz[ci])),
            "present": present,
            "declared": declared,
        }
        r = ref.get(data.sample_ids[ci]) if ref else None
        if r is not None:
            entry["expected_lab"] = [round(v, 2) for v in r]
            entry["expected_hex"] = _srgb_hex(ref_xyz(ref, data, ci))
            entry["de"] = round(ciede2000(tuple(lab[ci]), r), 2)
        out.append(entry)
    return out


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


def _reference_ti2_candidates(ti3_path: Path) -> "list[Path]":
    """Every ``.ti2`` a measurement could be paired with, best first.

    Split out of :func:`_find_reference_ti2` so the control-strip declaration
    can be looked for beside EVERY chart this measurement might be paired with
    and not only beside the winner. Driven on screen 2026-09-18: a sidecar
    written beside the run's own chart was invisible, because a dated
    verification is paired with the snapshot in its own ``chart/`` folder, and
    "beside the chart" then meant a folder the user never opens.
    """
    stem = ti3_path.stem
    base = stem[:-7] if stem.endswith("-verify") else stem
    return [
        ti3_path.with_suffix(".ti2"),
        # The dated verification's own chart/ snapshot OUTRANKS the shared
        # chart: the shared one changes with every regenerate/restore, and
        # judging an old date against whatever chart happens to be live gave
        # nonsense the moment they differed (Sebastian, 2026-08-10: the gamut
        # date's trend point jumped to ΔE ≈ 41 after the chart was swapped, its
        # own honest value is 2.8). The snapshot is written at measure time for
        # exactly this.
        ti3_path.parent / "chart" / f"{stem}.ti2",
        ti3_path.parent.parent / f"{stem}.ti2",          # shared verify chart
        # verifications/<date>/ → runN/: the profiling chart at the run root,
        # when a verification re-measures the same chart.
        ti3_path.parent.parent.parent / f"{base}.ti2",
    ]


def _find_reference_ti2(ti3_path: Path) -> Path:
    """Locate the design ``.ti2`` for a measurement (#130). A verification lives
    in ``runs/runN/verifications/<date>/`` and holds only its ``.ti3``, so the
    reference chart may be next to it, the shared verify chart one level up
    (``verifications/<name>-verify.ti2``), or the run's profiling chart at the
    run root (``runs/runN/<name>.ti2`` when a verification re-measures the same
    chart). Falls back to the sibling path (which then triggers the device
    reference) when nothing is found."""
    cands = _reference_ti2_candidates(ti3_path)
    for c in cands:
        if c.is_file():
            return c
    return cands[0]


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


#: The keyword a converted i1Profiler export carries its measurement date in.
_MEASURED_KEYWORD = "CHROMIQ_MEASURED"


def _measured_keyword(ti3_path: Path) -> str:
    """``CHROMIQ_MEASURED`` off a ``.ti3``'s header, without parsing the table.

    A cheap scan, because :func:`created_stamp_for` is asked about the run's
    measurement once per saved report and a full :func:`parse_ti3` of each
    would make opening the report window a job. It reads the header only:
    CGATS keywords stand above ``BEGIN_DATA_FORMAT``, and the loop stops there.

    THROUGH `parse_ti3`'S OWN REGEX, because the two must never disagree.
    `build_report` hands :func:`created_stamp_for` the keywords `parse_ti3`
    found; every other caller makes it read the file. If the two readings can
    differ, a report built from a file stops matching that same file and the
    rebuild is silently skipped for every imported measurement. A hand-rolled
    "split on the first space" was the first cut and it parts company with
    `_KW_RE` on a tab, on runs of spaces and on an unquoted value. Measured
    over 128 .ti3 files on one real disk the two agreed everywhere, and NONE
    of them carried this keyword, so that sample said nothing at all about the
    branch where a drift would live.
    """
    from workflow.ti3_analysis import _KW_RE
    try:
        text = read_text(ti3_path, lenient=True)
    except OSError:
        return ""
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("BEGIN_DATA"):
            break
        m = _KW_RE.match(s)
        if m is not None and m.group(1) == _MEASURED_KEYWORD:
            return m.group(2)
    return ""


#: How far two readings of the LIGHTEST or DARKEST patch may sit apart in L*
#: and still be the same file. Both sides are the same rounding of the same
#: arithmetic, so the honest tolerance is the coarsest rounding any report
#: schema used (one decimal, schema 5). 0.5 is ten times that, and a fifth of
#: the smallest difference measured between two real reads of one chart.
_SAME_FILE_DL = 0.5


def lightest_and_darkest(lab) -> "tuple[int, int] | None":
    """``(lightest, darkest)`` reading by measured L*, or None for no readings.

    ONE RULE, because `build_report` needs the lightest patch a SECOND time —
    the media-relative yardstick divides every reading by the paper white's
    XYZ — and it used to read a local left over from the paper-white block.
    Lifting that block into :func:`measurement_facts` took the local away and
    the suite caught it as a `NameError` in three tests; recomputing it inline
    would have put the two readings of "which patch is the paper" back to being
    two.
    """
    Ls = [l[0] for l in lab]
    if not Ls:
        return None
    return int(np.argmax(Ls)), int(np.argmin(Ls))


def measurement_facts(ti3_path: "str | Path", *, data=None,
                      lab=None) -> dict:
    """What a saved report records ABOUT ITS OWN MEASUREMENT. THE ONE RULE.

    ``patches``, ``paper_white`` and ``max_black``: how many readings the sheet
    holds and the lightest and darkest of them. `build_report` writes them and
    :func:`facts_disagree` reads them back, so the writer and the reader cannot
    drift — the failure this project has met three times in one day is two
    places deciding the same question differently.

    Cheap on purpose: no reference chart, no ArgyllCMS, one `parse_ti3`.
    """
    ti3_path = Path(ti3_path)
    if data is None:
        data = parse_ti3(ti3_path)
    if lab is None:
        lab = [xyz_to_lab((x / 100.0, y / 100.0, z / 100.0))
               for x, y, z in data.xyz]
    extremes = lightest_and_darkest(lab)
    if extremes is None:
        return {"patches": data.n_patches}
    wi, bi = extremes
    return {
        "patches": data.n_patches,
        "paper_white": {
            "loc": data.sample_locs[wi] if data.sample_locs else data.sample_ids[wi],
            "lab": [round(v, 2) for v in lab[wi]],
            "hex": _srgb_hex(tuple(data.xyz[wi])),
        },
        "max_black": {
            "loc": data.sample_locs[bi] if data.sample_locs else data.sample_ids[bi],
            "lab": [round(v, 2) for v in lab[bi]],
            "hex": _srgb_hex(tuple(data.xyz[bi])),
        },
    }


def point_lightness(point) -> "float | None":
    """The L* of a report's ``paper_white`` / ``max_black``, whichever shape it
    is in. Schema 5 wrote ``{"L": .., "a": .., "b": ..}``; 6 and 7 write
    ``{"loc": .., "lab": [L, a, b], ..}``. Both are on this machine's disk.

    **PUBLIC, AND THE ONLY READER OF THAT FIELD (R24-F2).** It was private, so
    three other places read ``["lab"][0]`` for themselves and one schema-5
    measurement came out three different ways in ONE document: the detailed
    section printed *White - L* 95.4*, the Overview table printed a dash for
    the same run, and the paper-white trend chart had no point for it at all.
    A reader comparing two papers reads that dash as "not measured", and a
    trend whose whole job is to show drift silently dropped every measurement
    written before the shape changed. Anything wanting the L* of one of those
    two records asks this, and there is one answer.
    """
    if not isinstance(point, dict):
        return None
    if isinstance(point.get("lab"), (list, tuple)) and point["lab"]:
        try:
            return float(point["lab"][0])
        except (TypeError, ValueError):
            return None
    try:
        return float(point["L"])
    except (KeyError, TypeError, ValueError):
        return None


def point_lab(point) -> "tuple[float, float, float] | None":
    """All three of L*, a*, b* of a ``paper_white`` / ``max_black``, or None.

    The same two shapes :func:`point_lightness` reads. **For the line under
    the swatch, and the reason it exists is K5** (Knut, beta 34): a paper
    white of *L* 100.0* beside a light blue swatch reads as a fault, and the
    swatch was right. The demo pack's white was Lab 100.0 / -2.4 / -19.4, and
    only the L* was printed, so nothing on the page explained the colour.
    """
    if not isinstance(point, dict):
        return None
    try:
        if isinstance(point.get("lab"), (list, tuple)):
            vals = [float(v) for v in point["lab"][:3]]
        else:
            vals = [float(point["L"]), float(point["a"]), float(point["b"])]
    except (KeyError, TypeError, ValueError):
        return None
    return tuple(vals) if len(vals) == 3 else None


def facts_disagree(rep: dict, ti3_path: "str | Path") -> bool:
    """True when a saved report CANNOT be about the file standing here.

    THE FILE ITSELF IS ASKED, rather than the folder around it. Every
    measurement of one run carries the same file name, so the name says
    nothing; the ``created`` stamp says it when it matches, and where the stamp
    has moved for an innocent reason (a demo package writing the date it wants
    the history to show, a renamed target) this is what can still tell a
    replacement from a re-stamp. It is deliberately one-sided: agreement is NOT
    taken as proof, because the folder tests in
    `MeasurementReportDialog._measurement_for` still have to run.

    Answers False, not True, for a report that records nothing comparable and
    for a file that cannot be read — "I cannot tell" must never be read as
    "it is a different measurement", which is the shape that took the accuracy
    block off every dated verification once already (B8-206).
    """
    want_n = rep.get("patches")
    try:
        facts = _facts_cached(Path(ti3_path))
    except Exception:  # noqa: BLE001 — unreadable is not evidence
        return False
    if not facts:
        return False
    if isinstance(want_n, int) and isinstance(facts.get("patches"), int) \
            and want_n != facts["patches"]:
        return True
    for key in ("paper_white", "max_black"):
        a, b = point_lightness(rep.get(key)), point_lightness(facts.get(key))
        if a is not None and b is not None and abs(a - b) > _SAME_FILE_DL:
            return True
    return False


def _facts_cached(ti3_path: Path) -> dict:
    """:func:`measurement_facts`, remembered per (path, size, mtime).

    The report window asks this once per saved report, and a run on a real disk
    holds twenty-seven of them naming ONE file. Keyed on the file's own stamp
    so an edited file is read again.
    """
    try:
        st = ti3_path.stat()
        key = (str(ti3_path), st.st_size, st.st_mtime_ns)
    except OSError:
        return {}
    hit = _FACTS_CACHE.get(key)
    if hit is None:
        hit = measurement_facts(ti3_path)
        if len(_FACTS_CACHE) > 64:
            _FACTS_CACHE.clear()
        _FACTS_CACHE[key] = hit
    return hit


_FACTS_CACHE: dict = {}


def created_stamp_for(ti3_path: str | Path, *,
                      keywords: "dict | None" = None) -> str:
    """The ``created`` stamp a report of *ti3_path* carries. THE ONE RULE.

    Date the report by the MEASUREMENT date when the ``.ti3`` carries one
    (``CHROMIQ_MEASURED``, written by Convert i1Profiler → TI3 from the
    export's date), so imported runs trend by when they were measured and not
    by when the report was built. Native chartread files have no such keyword,
    so the FILE's own time is used — not ``now()``, or every date on a history
    rebuilt for the trend collapses onto the moment the window was opened
    (Sebastian, 2026-08-10: four dates, one identical timestamp).

    IT IS A FUNCTION BECAUSE IT IS AN IDENTITY, not only a date. A saved report
    keeps the measurement's bare file NAME, and every measurement of one run
    carries the same name: the run's chart is re-measured, the previous file is
    copied into ``old/<stamp>/`` and the new one takes its place. So the only
    thing on disk that tells one of a run's measurements from another is this
    stamp, and :meth:`MeasurementReportDialog._measurement_for` matches a saved
    report to its own measurement with it. Two callers, one rule, so a report
    built from a file always matches that file.
    """
    ti3_path = Path(ti3_path)
    if keywords is None:
        measured = _measured_keyword(ti3_path)
    else:
        measured = str(keywords.get(_MEASURED_KEYWORD) or "")
    measured = measured.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$", measured):
        return measured if measured.count(":") == 2 else measured + ":00"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", measured):
        return f"{measured}T00:00:00"
    try:
        return datetime.fromtimestamp(
            ti3_path.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return datetime.now().isoformat(timespec="seconds")


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

    _created = created_stamp_for(ti3_path, keywords=data.keywords)
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

    # Paper white (lightest) and darkest black by measured L* — THE ONE RULE,
    # in `measurement_facts`, because these three numbers are also the only
    # record a saved report keeps OF WHICH MEASUREMENT IT IS ABOUT, and the
    # reader of that record must not compute them a second way.
    report.update(measurement_facts(ti3_path, data=data, lab=lab))

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
    corner_devices: "dict[str, tuple]" = {}
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
            corner_devices = dict(cref.get("devices") or {})
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
        _extremes = lightest_and_darkest(lab)
        if white_mapping and _extremes is not None:
            white_xyz = np.asarray(data.xyz[_extremes[0]], dtype=float)
            if float(white_xyz.min()) > 0.0:
                _d50 = np.array([96.42, 100.0, 82.49])
                lab = [xyz_to_lab(tuple(
                    (np.asarray(x, dtype=float) / white_xyz * _d50) / 100.0))
                    for x in data.xyz]
                report["yardstick"] = "media-relative"

    # The eight cube corners (paper white, composite black, the six ink
    # primaries/secondaries) — the patch the chart DECLARES as each corner
    # where it declares one, else the nearest patch to it by device RGB. Each
    # carries its measured colour and, when a reference exists, its expected
    # colour and ΔE00, so the report says something about the inks, not only the
    # instrument (Knut). rgb is device 0..100.
    report["corners"] = corners_block(rgb100, lab, ref, data,
                                      corner_ids, corner_devices)

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

            # #182 T1, Knut 2026-09-11: *"The 16 colors must just be
            # distributed and represent the profile tested … all the colors
            # and grays tested must come from the actual test chart that was
            # used for verification."*
            #
            # So they are CHOSEN FROM THE CHART, not from a list ChromIQ keeps.
            # A fixed list of sixteen nice colours would name patches a chart
            # may not contain, and would say nothing about the profile this
            # measurement is of.
            report["summary_patches"] = [{
                "loc": data.sample_locs[i] if data.sample_locs else data.sample_ids[i],
                "de": round(de, 2),
                "expected_hex": _srgb_hex(ref_xyz(ref, data, i)),
                "measured_hex": _srgb_hex(tuple(data.xyz[i])),
                "expected_lab": [round(v, 2) for v in ref[data.sample_ids[i]]],
                "measured_lab": [round(v, 2) for v in lab[i]],
            } for de, i in _spread_over_colour(
                [(d, i) for d, i in des],
                [ref[data.sample_ids[i]] for _d, i in des], SUMMARY_PATCH_COUNT)]

    # #182: the grey ramp and the 30 to 70 % tone ramps, under the same
    # yardstick as everything above. Both blocks are written even when the
    # chart cannot supply them, with the reason, so the report can say
    # "not computed, and why" (Knut, D25) instead of leaving a row blank.
    if rgb100 is not None:
        report["grey_balance"] = grey_balance_block(rgb100, lab, ref, data.sample_ids)
        report["ramps_30_70"] = ramps_block(rgb100, lab, ref, data.sample_ids)
        # #182 S2w (Knut, 2026-09-18): the two gamut populations ChromIQ now
        # defines for itself. Written even when the chart cannot supply them,
        # with the reason, exactly as the two blocks above are.
        report["gamut_populations"] = gamut_populations_block(
            rgb100, lab, ref, data.sample_ids)

    # ChromIQ'S OWN TWO REPEATABILITY ROWS, and neither asks for a reference.
    # Row A compares the sheet's repeated patches WITH EACH OTHER, and Row B
    # compares this measurement with the one before it, so both are answerable
    # on a chart that carries no aim values at all. That is the point of them:
    # they work for a user who holds no document and whose chart was never
    # built from a profile. Written with their reason when they cannot be
    # answered, as every block above is.
    report["repeat_within_sheet"] = repeat_within_sheet_block(rgb100, lab)
    report["repeat_across_sheets"] = repeat_across_sheets_block(
        ti3_path, lab, data.sample_ids, rgb100)

    # …and the control strip, which is a DECLARATION rather than a measurement:
    # it needs the chart file, not the device values, so it is written whether
    # or not the measurement carries device columns.
    report["control_strip"] = control_strip_block(
        lab, ref, data.sample_ids,
        control_strip_declaration(ti3_path,
                                  ref_ti2 if ref_ti2.is_file() else None))
    return report


#: How many example colours the one-page report shows. Knut asked for sixteen.
SUMMARY_PATCH_COUNT = 16


def _spread_over_colour(des, labs, n):
    """Pick *n* of *des* spread as widely as possible through colour.

    Farthest-point sampling in the chart's own reference Lab: start at the
    patch nearest mid grey, then repeatedly take the patch furthest from
    everything picked so far. That gives a set that is distributed by
    construction, comes entirely from the chart that was measured, and is the
    same set every time the same chart is measured, so two dated reports of one
    chart show the same colours and can be compared.

    Returns ``[(de, index)]`` in the order picked, which is widest-first.
    """
    if not des or n <= 0:
        return []
    if len(des) <= n:
        return list(des)
    pts = np.asarray(labs, dtype=float)
    # mid grey in Lab, which is where a person's eye starts on a colour sheet
    start = int(np.argmin(((pts - np.array([50.0, 0.0, 0.0])) ** 2).sum(1)))
    picked = [start]
    far = ((pts - pts[start]) ** 2).sum(1)
    while len(picked) < n:
        nxt = int(np.argmax(far))
        if far[nxt] <= 0:
            break                      # every remaining patch is a duplicate
        picked.append(nxt)
        far = np.minimum(far, ((pts - pts[nxt]) ** 2).sum(1))
    return [des[i] for i in picked]


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
    # A SECOND IS NOT FINE ENOUGH ANY MORE. One measurement a second was the
    # only way reports arrived until the Generate report button existed; now a
    # user can keep three types of one measurement in the time it takes to
    # click three times, and the stamp names one file. Found by the test for
    # Knut's own ruling: three generates produced one report.
    #
    # A SUFFIX, NOT A FINER STAMP. The filename is a date a person reads, and
    # `list_reports` sorts by it; "_2" keeps both true and keeps every report
    # already on disk readable by the same glob.
    if path.exists():
        n = 2
        while (reports / f"report_{ts}_{n}.json").exists():
            n += 1
        path = reports / f"report_{ts}_{n}.json"
    # ATOMICALLY, BECAUSE A HALF-WRITTEN REPORT HAS A REAL REPORT'S NAME.
    # `Path.write_text` leaves exactly that when the process is killed
    # mid-write, and combined round 3 drove what the window then does with it:
    # on a dated verification holding one good report and one truncated file,
    # Delete came up enabled with no reason beside it, the confirmation said
    # "0 saved reports of it are left afterwards", and the press left the date
    # with no verdict the window could read. The dialog was hardened to count
    # only the files it can actually parse; this stops the file existing.
    # `write_json_atomically` already pays for every trap `os.replace` has cost
    # this project: it resolves a symlink first, fsyncs before the rename,
    # carries mode, times and flags across, and drops the immutable bits from
    # the scratch file so a locked target cannot leave an undeletable .tmp.
    write_json_atomically(path, report)
    log.info("measurement report saved: %s", path)
    return path


# ---------------------------------------------------------------------------
# The DOCUMENT record (#182, Knut 2026-09-18; §13.4 of
# docs/design/measurement_report_limits.md, register B8-383)
# ---------------------------------------------------------------------------
#: The additive block. **`REPORT_SCHEMA` STAYS 7 AND NOTHING ON DISK MOVES.**
#: Every report a user already has was written without this key, opens without
#: it, and is listed, rendered and judged exactly as it was; a file that has no
#: block is its own one-file document (see :func:`document_key`). The block is
#: only ever ADDED, by the press of Generate that writes the file.
DOCUMENT_BLOCK = "document"


def new_document_id(when: "datetime | None" = None) -> str:
    """A fresh document id: time-ordered, and unique within the same second.

    ONE PRESS OF GENERATE IS ONE DOCUMENT, and a document can be several files
    — one per measurement it covers, in that measurement's own folder, because
    that is where a dated verification's verdict has to live (§5). The id is
    what makes those files one thing, so the id has to be decided once, before
    the first file is written, and handed to every file of the press.

    Time-ordered so the list can be sorted on it without reading a clock out of
    the block, and salted because a user can press Generate twice in one
    second: `save_report` already learned that lesson the hard way and grew a
    `_2` suffix for it.
    """
    import secrets
    stamp = (when or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return f"doc_{stamp}_{secrets.token_hex(3)}"


#: The three date-scope flags a generated report's NAME carries (B8-392, Knut
#: 2026-09-18). Stored as an ID and translated when the name is DISPLAYED: a
#: name built on a German machine has to mean the same thing on an English one,
#: and every other part of this block is stored in its stable form too (the set
#: id beside its English label, the type id).
SCOPE_ALL_DATES = "all_dates"
SCOPE_ONE_DATE = "one_date"
SCOPE_MULTIPLE_DATES = "multiple_dates"
DOCUMENT_SCOPES = (SCOPE_ALL_DATES, SCOPE_ONE_DATE, SCOPE_MULTIPLE_DATES)


def document_scope_of(doc: "dict | None") -> str:
    """The date-scope flag of a document block, derived when it records none.

    Knut's four cases (B8-392) reduce to what the document already knows: a
    document covering one measurement is *"One date"*, one covering every
    measurement with none left out is *"All dates"*, and one covering several
    but not all is *"Multiple dates"*. A block written before this carried the
    flag records the measurements it covers and both tick boxes, so the first
    and the third are still exact; only "all of them" needs the tick box, which
    is what `all_runs` is.
    """
    if not doc:
        return SCOPE_ONE_DATE
    recorded = str(doc.get("scope") or "")
    if recorded in DOCUMENT_SCOPES:
        return recorded
    n = len(doc.get("measurements") or [])
    if n <= 1:
        return SCOPE_ONE_DATE
    return SCOPE_ALL_DATES if doc.get("all_runs") else SCOPE_MULTIPLE_DATES


#: **DOES A SECOND UPDATE APPEND A SECOND STAMP, OR REPLACE THE FIRST?**
#: Knut ruled that **Update** appends *" - updated <date> <time>"* to the
#: selected report's name (2026-09-19, #182) and did not say what a SECOND
#: update does. The question is open with him; the default taken here is
#: **replace**, so a name says when the report was created and when it was
#: last updated and nothing else. Every stamp is still kept on disk, in order,
#: so flipping this to ``True`` shows the whole history in the name and
#: nothing has to be recovered from anywhere.
NAME_SHOWS_EVERY_UPDATE = False


def document_updated_stamps(doc: "dict | None") -> "list[str]":
    """Every "updated" stamp a document block carries, oldest first.

    A block written before Update existed carries none, which is the honest
    answer for it: it has never been updated.
    """
    if not isinstance(doc, dict):
        return []
    raw = doc.get("updated")
    if isinstance(raw, str):
        return [raw] if raw else []
    if not isinstance(raw, list):
        return []
    return [str(v) for v in raw if isinstance(v, (str, int, float)) and str(v)]


def stamp_document(report: dict, *, doc_id: str, created: str, type_id: str,
                   compliance: "dict | None", detail: bool,
                   measurements: "list[dict]", scope: str = "",
                   all_runs: bool = False,
                   updated: "list[str] | None" = None) -> dict:
    """Record, on one file, which DOCUMENT it belongs to and how that document
    was made. Returns *report*, stamped in place.

    §13.4 names the fields and this writes exactly them: the type, the limit
    set with its label and the thresholds copy it was judged against, both tick
    boxes, and the list of measurements the document covers. Nothing here is
    derived at read time, because the whole point is that selecting the
    document restores the settings it was MADE with (L.2), not the settings the
    run happens to carry today.
    """
    report[DOCUMENT_BLOCK] = {
        "id": str(doc_id),
        "created": str(created),
        "type": str(type_id or ""),
        "compliance": dict(compliance) if isinstance(compliance, dict) else None,
        # **`all_runs` IS DEAD AND IS STILL WRITTEN (B8-590).** The box it
        # recorded was removed from the window with the feature behind it, so
        # nothing sets it and nothing in this build reads it back for a new
        # document. It stays in the block, and the parameter stays with a
        # default, because `document_scope_of` falls back to it for a document
        # written BEFORE `scope` was recorded, and dropping the key would
        # re-label every one of those. New documents always carry `scope`.
        "all_runs": bool(all_runs),
        "detail": bool(detail),
        "measurements": [dict(m) for m in (measurements or [])],
    }
    # **WHEN THIS DOCUMENT WAS UPDATED, AND NOT WHEN IT WAS CREATED.** Knut,
    # 2026-09-19: *"Update button will keep the current selected report, then
    # append on the ending of the report name ' - updated <date> <time>', then
    # recalculate and update the report text according to the new settings."*
    # So `created` never moves — it is what the name LEADS with — and this is
    # the separate record of every press of Update. Left out of the block
    # entirely when there is none, so a report written by Generate is byte-for-
    # byte what it was before this field existed.
    stamps = [str(v) for v in (updated or []) if str(v)]
    if stamps:
        report[DOCUMENT_BLOCK]["updated"] = stamps
    # THE DATE-SCOPE FLAG, as an id (B8-392). An empty or unknown value is left
    # out rather than stored, so `document_scope_of` derives it exactly as it
    # does for a block written before this field existed.
    if scope in DOCUMENT_SCOPES:
        report[DOCUMENT_BLOCK]["scope"] = scope
    return report


def recorded_document(report: "dict | None") -> "dict | None":
    """The document block a report was saved with, or None.

    None is the honest answer for every report written before this existed and
    is never an error: such a file is a document of one file (`document_key`).

    **AND THE BLOCK'S OWN FIELDS ARE THE NEXT R25-F1 (R27-F2).**
    :func:`report_object` made the TOP level of a saved report safe, because
    `json.loads` is happy with `[]`, `"x"` and `5`; this block is a level
    below it and every reader trusted its shape. Driven in a real window on
    `Report-Limits-Report-Types`, one report file per case, with nothing else
    touched: `measurements` as a string, as a dict, as a number, as a list of
    strings, and `compliance` as a string each took the WHOLE MEASUREMENT
    REPORT WINDOW DOWN before it appeared — the exception is raised inside
    `MeasurementReportDialog(...)`, so there is no window to close and no
    message to read. Three doors, all reached from one bad file:
    `_apply_document` iterating `measurements`, `_document_label` reading
    `compliance`, and `document_scope_of` taking `len(measurements)`.

    A block is a RECORD OF FIELDS, so it is read as those fields and a value
    that is not the shape this build writes is dropped rather than carried
    into the window. Nothing on disk is changed: this reads, and the file
    keeps whatever it holds for a ChromIQ that knows what to do with it. A
    fresh dict is returned for the same reason `report_object` returns one —
    a reader cannot write back through it by accident.
    """
    d = report_object(report).get(DOCUMENT_BLOCK)
    if not isinstance(d, dict) or not str(d.get("id") or ""):
        return None
    # A measurement entry that is not an object cannot answer "which
    # measurement is this", so it is not one. The list keeps the entries that
    # can, in order, which is what `_apply_document` matches its rows against.
    raw = d.get("measurements")
    members = [m for m in raw if isinstance(m, dict)] if isinstance(raw, list) \
        else []
    comp = d.get("compliance")
    scope = str(d.get("scope") or "") if isinstance(d.get("scope"), str) else ""
    out = dict(d)
    out.update({
        "id": str(d.get("id") or ""),
        "created": str(d.get("created") or "")
        if isinstance(d.get("created"), (str, int, float)) else "",
        "type": str(d.get("type") or "") if isinstance(d.get("type"), str) else "",
        "compliance": comp if isinstance(comp, dict) else None,
        "all_runs": bool(d.get("all_runs")),
        "detail": bool(d.get("detail")),
        "measurements": members,
    })
    # The update stamps get the same treatment every other field of this block
    # gets (R27-F2): a value that is not the shape this build writes is dropped
    # rather than carried into the window, and the key is left out when there
    # is nothing in it, so `stamp_document`'s own omission round-trips.
    stamps = document_updated_stamps(d)
    if stamps:
        out["updated"] = stamps
    else:
        out.pop("updated", None)
    if scope:
        out["scope"] = scope
    else:
        out.pop("scope", None)
    return out


def document_key(report: "dict | None", path: "str | Path") -> str:
    """Which document one saved report file belongs to.

    A file carrying a block answers with its id. **A file without one answers
    with its own path**, so every report already on disk stays in the list as
    its own entry, named as it is named today, and the list a user has been
    looking at does not change under them.
    """
    return document_key_of(recorded_document(report), path)


def document_key_of(doc: "dict | None", path: "str | Path") -> str:
    """:func:`document_key`, for a caller that has already read the block.

    One rule in one place: the report window reads each file's block once per
    mtime and caches it, so it never has the whole report to hand when it needs
    the key.
    """
    if doc is not None:
        return f"id:{doc['id']}"
    return f"file:{Path(path)}"


def document_measurement_key(origin_dir: "str | Path", created: str,
                             ti3: str) -> str:
    """The identity of ONE measurement inside a document's list.

    The same three parts the report window's `_run_key` uses, in the same
    order, because the window has to match a document's recorded list against
    the rows it has loaded and two answers to "which measurement is this" is
    one answer too many.
    """
    return f"{origin_dir}|{created}|{ti3}"


def document_old_dir(member_dirs: "list[Path] | list[str]",
                     when: "datetime | None" = None) -> "Path | None":
    """Where **Delete Selected Report** moves a document's files (L.7).

    Knut, 2026-09-18: *"which then creates a dated report folder in the old/
    folder where the files for that report is moved to. If it is several dated
    verification runs, it will land in the old/ folder in the verifications/
    folder. If it is only one dated verification run included in the report,
    then the report files will be moved to the old/ folder in the dated folder
    for that verification run. If the included measurements for the report span
    several profile runs, then the report files will be moved to the old/
    folder for the project (common for all the runs)."*

    So the destination is decided by the document's SPAN, and the three answers
    are:

    ============================== ==========================================
    the document covers            it is moved to
    ============================== ==========================================
    one folder                     ``<that folder>/reports/old/<stamp>/``
    several dates of ONE run       ``<run>/verifications/old/<stamp>/``
    several profile runs           ``<project>/old/<stamp>/``
    ============================== ==========================================

    ``reports/old/`` is this project's existing word for an archived report
    (``Verification.archive_reports``), so the one-folder answer uses it rather
    than inventing a second place for the same thing.

    Returns None when *member_dirs* is empty. **Nothing is created here** and
    nothing is deleted anywhere: this only names the folder.
    """
    from core.file_manager import REPORTS_DIRNAME, VERIFICATIONS_DIRNAME
    dirs = [Path(d) for d in (member_dirs or []) if str(d)]
    if not dirs:
        return None
    stamp = (when or datetime.now()).strftime("%Y-%m-%d_%H%M%S")
    uniq = sorted({str(d) for d in dirs})
    if len(uniq) == 1:
        return dirs[0] / REPORTS_DIRNAME / "old" / stamp

    def _run_of(d: Path) -> "Path | None":
        """The profile run a measurement folder belongs to: the run itself, or
        the run above a dated verification folder."""
        if d.parent.name == VERIFICATIONS_DIRNAME:
            return d.parent.parent
        return d

    runs = {str(_run_of(d)) for d in dirs}
    if len(runs) == 1:
        run = _run_of(dirs[0])
        return run / VERIFICATIONS_DIRNAME / "old" / stamp
    # Several profile runs: the project is the folder above `runs/`.
    run = _run_of(dirs[0])
    project = run.parent.parent if run.parent.name == "runs" else run.parent
    return project / "old" / stamp


def list_reports(run_dir: str | Path) -> list[Path]:
    """All saved reports for a run, oldest first."""
    from core.file_manager import reports_subdir
    reports = reports_subdir(run_dir)
    if not reports.is_dir():
        return []
    return sorted(reports.glob("report_*.json"))


def generated_report_types(run) -> "dict[str, int]":
    """``{type_id: how many}`` for the reports a RUN has already produced.

    **Knut, 2026-09-11:** *"A user should be allowed to print several report
    types for a run, as the user may have several uses for different reports.
    The Report window must thus show which type of reports have been
    generated."* He offered an alternative, generating all six every time, on
    condition it costs a second or two; it does not, so this is the half he
    asked for.

    Counted from what is on disk, across every dated verification of the run,
    never from anything the window remembers: a report is generated by a
    measurement the window was not open for, and another window may have
    generated one a moment ago.

    A report saved before the type existed counts as what it renders as, which
    is today's report, because that is what it IS. Never raises: a run whose
    folder cannot be read has produced nothing this can promise.
    """
    out: "dict[str, int]" = {}
    if run is None:
        return out
    try:
        dirs = [run.dir] + [v.dir for v in run.verifications() if v.exists()]
    except Exception as exc:                     # noqa: BLE001
        log.warning("could not list the reports of a run: %s", exc)
        return out
    # **IT COUNTS REPORTS, NOT FILES (B8-593).** Knut, 2026-09-20: *"The Text
    # 'Already generated for this run: Full colour check (11), Printing Record
    # (not graded)(1)', while the pulldown for Run shown only has one
    # report"*, and later *"(32) … while the pulldown … only has 13 reports"*.
    #
    # Both numbers were right about what they counted, and that was the fault.
    # ONE press of Generate writes ONE FILE PER TICKED MEASUREMENT, all
    # carrying the same document id (`_write_the_document` decides the id once
    # before its loop). Twelve dated measurements therefore leave twelve files
    # and ONE report. This line counted the files; "Report shown" lists the
    # documents, de-duplicated by that id. A line above a pulldown that
    # contradicts the pulldown is telling the user one of them is broken.
    #
    # So a report with a document id is counted ONCE, under the type of its
    # document block, and a legacy file with no document block still counts as
    # itself, because for those a file IS a report.
    seen: "set[str]" = set()
    for d in dirs:
        for path in list_reports(d):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            block = recorded_document(doc)
            doc_id = str((block or {}).get("id") or "")
            if doc_id:
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                # THE DOCUMENT BLOCK'S OWN TYPE, NOT THE FILE'S. A press that
                # narrows a document re-types the files it writes and leaves
                # the ones it no longer covers with their old top-level type,
                # which is how one report came to be counted under two names
                # ("Full colour check (11), Printing Record (not graded)(1)"
                # for a single document of twelve files).
                tid = str(block.get("type") or "") or report_type(doc)
            else:
                tid = report_type(doc)
            out[tid] = out.get(tid, 0) + 1
    return out


def report_object(obj) -> dict:
    """A saved report as a dict, or an empty one for anything that is not.

    **`json.loads` IS HAPPY WITH `[]`, `null`, `"x"` AND `5` (R25-F1).** Every
    reader of a saved report guarded itself with `(report or {}).get(...)`,
    which catches None and an empty dict and lets a string, a list and a number
    straight through: `5 or {}` is `5`. One such file anywhere under
    `runs/*/reports/` then took the whole Measurement Report window down for
    every measurement of every run, with the list empty, all three pulldowns
    blank, Generate, PDF, Reveal and Delete dead, and the message naming no
    file. Driven in a real window in all four shapes.

    ChromIQ writes no such file. The doors are a shared project, a hand edit
    and the declutter migration, which is enough: a report is a record of
    somebody's measurement and a folder of them is not ours to assume clean.
    """
    return obj if isinstance(obj, dict) else {}


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
        # WHICHEVER SHAPE THE FILE IS IN (R24-F2). This read ``lab`` only, so a
        # schema-5 report -- which is what ChromIQ's own demo projects hold --
        # contributed no point to the paper-white or the black trend, with
        # nothing anywhere saying a point was missing.
        white_L = point_lightness(r.get("paper_white"))
        black_L = point_lightness(r.get("max_black"))
        if white_L is not None:
            pt["white_L"] = white_L
        if black_L is not None:
            pt["black_L"] = black_L
        # Per-corner ΔE00-from-design, so the cube-corner chart can plot how
        # each ink drifts over time (Knut).
        #
        # **A CORNER THE CHART DOES NOT HAVE IS NOT PLOTTED** -- B8-290. Each
        # corner entry is built from the NEAREST patch in device RGB, and
        # `present` False says that patch is not at the corner at all; its
        # DeltaE00 then describes a different colour. Plotted under this ink's
        # name it became a drift line for an ink the sheet never carried, and
        # on the reported project Red and Blue would have drawn the SAME line,
        # because both resolved to one neutral patch. Filtered here rather than
        # in the builder so every report already on disk is read correctly too.
        corners = {c["name"]: float(c["de"])
                   for c in (r.get("corners") or [])
                   if c.get("de") is not None and c.get("present", True)}
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

    A KNOWN id this build cannot PRODUCE is the same case wearing a familiar
    name, and it was being honoured. The two ISO types are declared here so the
    pulldown can show them and refuse them, and a project made on a later
    ChromIQ that builds one of them carries that id home in its meta.json or in
    a saved report. Opened here, the window sat on "Validation print check
    (ISO 12647-8)" over a full colour check, and the "already generated" line
    named a document ChromIQ had not written. What this build renders is what
    it must say it rendered, so an unbuilt type falls back exactly as an unknown
    one does — and nothing is rewritten, so the later ChromIQ still finds the
    user's choice where it left it.
    """
    t = report_object(report).get("report_type")
    return t if t in REPORT_TYPES and report_type_is_built(t) \
        else REPORT_TYPE_DEFAULT


def recorded_report_type(report: "dict | None") -> str:
    """The type a report RECORDS, or "" when it records none (R27-F3).

    :func:`report_type` answers T2 for a file that says nothing, because that
    is what such a file RENDERS as and every caller wanted a type it could
    draw. This answers the other question — *did this file choose?* — and the
    two are not the same the moment a run has a type of its own: §10 of
    `docs/design/measurement_report_limits.md` says a report with no type of
    its own *"still follows the run"*, and a caller that cannot tell absence
    from the default makes it follow T2 instead.

    Same treatment of an id this build cannot draw as `report_type` gives it,
    and for the same reason: a seventh type from a later ChromIQ is not a
    choice this window can honour, so it is not one it may claim either.
    """
    t = report_object(report).get("report_type")
    return t if t in REPORT_TYPES and report_type_is_built(t) else ""


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
     "One page to print and hand over with a job.", True),
    (REPORT_TYPE_FULL, "Full colour check",
     "Everything ChromIQ measures, in full. This is the report you know.",
     True),
    # "on their own" was measured against the document and was not true: the
    # RESULTS are the neutral axis alone, and the pages around them are still
    # the full report's. Knut's brief says two pages, so the document itself
    # has more to lose before it matches; until it does, the line says what is
    # actually true today rather than what it will be.
    (REPORT_TYPE_GREY, "Grey and tone check",
     "Judges the neutral axis and the mid-tone ramps; the colour rows are "
     "left out.", True),
    (REPORT_TYPE_RECORD, "Printing record (not graded)",
     "A record of what was printed and measured, with nothing judged.", True),
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


#: The rows T3, "Grey and tone check", is ABOUT. Everything else is dropped
#: from that document rather than shown as not applicable: a report whose
#: subject is the neutral axis does not gain by listing the colour rows it
#: deliberately leaves out.
#:
#: Row ids, from `workflow.compliance_sets.ROWS`. The two grey-balance rows are
#: the neutral axis; the 30-70 ramp row is the tone half of the same question,
#: and Knut's module H pairs them.
REPORT_TYPE_ROWS: "dict[str, tuple[str, ...]]" = {
    REPORT_TYPE_GREY: ("grey_balance_neutral_ramp_avg",
                       "grey_balance_neutral_ramp_max",
                       "ramps_30_70_dl_max"),
}


def rows_for_report_type(type_id: str) -> "tuple[str, ...] | None":
    """Which rows that type's results table is about, or None for all of them."""
    return REPORT_TYPE_ROWS.get(type_id)


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


def stamp_report_type(report: dict, run) -> dict:
    """Record on the report which KIND of document the run produces.

    Called beside :func:`stamp_verdict`, for the same reason and at the same
    moment: the run's choice at the moment of the measurement is what this
    report was produced under, and a report archived into ``reports/old/``
    should say what it was as well as what it was judged against.

    IT WAS BUILT AND THEN NOT CALLED. The storage, the strict writer, the
    forgiving reader and their mutations all landed in the first commit of
    this feature, and nothing anywhere wrote one: an adversarial round grepped
    for the writer and found only its own tests.

    **AND IT DOES NOT CARRY A CHOICE MADE OUTSIDE A PROJECT.** A previous
    version of this docstring said it did. It cannot: the report is saved at
    the moment of the measurement, before any report window exists, so nothing
    at this call site can know what a user later picks for a file that has no
    run to remember it. `run=None` records `REPORT_TYPE_DEFAULT`, which is what
    such a file renders as, so the record is true; it is not the user's choice,
    and for a measurement outside a project that choice is still session-only.
    A third adversarial round drove exactly that and the claim was withdrawn
    rather than the behaviour patched, because the behaviour is right and the
    sentence was wrong.

    Never raises: a report that cannot be stamped is still a report, and the
    run remains the source of truth for anything inside a project.
    """
    try:
        from workflow.run_compliance import run_report_type
        set_report_type(report, run_report_type(run))
    except Exception as exc:                    # noqa: BLE001
        log.warning("could not record the report type: %s", exc)
    return report


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

    # **A PLAIN NOTE, AND DELIBERATELY NOT A WARNING** (#182, Knut,
    # 2026-09-22): *"where selected measurements come from charts with
    # different patch counts, the report carries a plain warning that judged
    # metrics may differ slightly for that reason and that it shows in the
    # trend graphs. Not an error."*
    #
    # It is returned under `notes` rather than appended to `warnings` because
    # `_scope_warnings_html` paints everything it is given in the report's FAIL
    # colour. A note about a legitimate mixture of charts, printed in red under
    # the heading "Warning", would say the opposite of what he asked for, and
    # nothing in the rendering would have to change for that to happen: it
    # would simply be the colour the block already is.
    notes: "list[dict]" = []
    counts = [r.get("patches") for r in runs
              if isinstance(r.get("patches"), int) and r["patches"] > 0]
    # ORDERED BY THE COLUMNS, NOT SORTED, and duplicates dropped: the sentence
    # names the distinct counts in the order a reader meets them across the
    # table, so "1617 and 918" matches what is on the page.
    distinct: "list[int]" = []
    for n in counts:
        if n not in distinct:
            distinct.append(n)
    if len(distinct) > 1:
        notes.append({"kind": "patch_counts", "counts": distinct})

    return {"profiles": prof_list, "total": len(runs),
            "date_range": date_range, "warnings": warnings, "notes": notes}


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

# --- #182 S2w: the control strip, and the two gamut populations -------------
#
# Knut approved these three detection rules on 2026-09-18, after they had
# waited as proposals since 2026-09-14 (`docs/design/issue_182_answers.md`
# S2w). Before them, five rows of the limits table had NO detection method at
# all and their help icons said so: ChromIQ could not tell whether a chart
# carried the patches those rows are about, so the rows were never judged.
#
# The control strip is DECLARED BY THE CHART, never guessed. ChromIQ does not
# hold any standard's published patch list and may not invent one, so the
# question the detection answers is *"does this chart say which of its patches
# make up a control strip, and are there enough of them"* — which is the
# question Knut asked the detection to answer, and it reads no standard.
#
#: ``<chart stem>.control-strip.json`` beside the chart, holding
#: ``{"name": "<the strip's own name>", "sample_ids": ["A1", "A2", ...]}``.
CONTROL_STRIP_SIDECAR = ".control-strip.json"
#: …or the same ids in a CGATS keyword on the ``.ti1`` / ``.ti2``.
CONTROL_STRIP_KEYWORD = "CONTROL_STRIP_IDS"
#: **k**, the count of declared ids that are in the measurement AND carry a
#: reference value. Below eight an average over the strip says nothing.
CONTROL_STRIP_MIN = 8
#: The 95th-percentile row needs more, and the reason is arithmetic rather
#: than taste: the nearest rank ``ceil(0.95 k)`` equals ``k`` for every k below
#: 20 (`_stats` computes it), so the row would simply repeat the largest.
CONTROL_STRIP_P95_MIN = 20

#: **Surface-gamut patches**: every patch whose device values touch the
#: surface of the device cube, ``min(v, 100 - v) <= 2.0`` for at least one of
#: R, G, B. This is ChromIQ's OWN definition of the population, which is why
#: the group heading lost the words "of the standard's chart" in the same
#: change (Knut, 2026-09-18).
SURFACE_GAMUT_TOL = 2.0
#: …computable with at least ten such patches carrying a reference.
SURFACE_GAMUT_MIN = 10
#: **Outer-gamut patches**: the top quartile by chroma, ``C*ab`` of each
#: patch's REFERENCE value (the population is a property of the chart, not of
#: how well it printed).
OUTER_GAMUT_FRACTION = 0.25
#: …and the quartile itself must hold at least twenty patches, so the average
#: is not one or two readings. That wants roughly eighty referenced patches on
#: the chart.
OUTER_GAMUT_MIN = 20

# ---------------------------------------------------------------------------
# The two repeatability populations, which are CHROMIQ'S OWN
# ---------------------------------------------------------------------------
#: **These two rows are not anybody's published criterion, and the whole point
#: of them is that they are not.** Every other numeric row in the table comes
#: from a document somebody else wrote. These are computed from the user's own
#: measurements of the user's own prints; no standard defines them, nobody
#: licenses them, and they work for a printer user who holds no document at
#: all. Nothing here was looked up in, derived from, or checked against any
#: standard, and the row labels and help text say ChromIQ's name for that
#: reason.
#:
#: `compliance_sets.repeatability_de00_max` is a DIFFERENT row and stays
#: exactly as it is, `unmeasurable`: it is a standard's criterion over that
#: standard's own timed protocol, and pointing it at a number ChromIQ can
#: compute would be the false attribution this file already records being
#: made twice.

#: **Row A, repeat patches within one sheet.** The least number of repeat
#: GROUPS below which the largest difference is not worth reporting.
#:
#: DERIVED, not chosen. A group is one device colour asked for more than once,
#: so the maximum over a single group is a statement about that one colour,
#: while the row is offered as a property of the SHEET. Measured on the charts
#: on this machine: where a chart repeats anything at all it repeats the two
#: ENDS, bare paper and solid black (the demo chart's two groups are exactly
#: RGB 0,0,0 and RGB 100,100,100), so a one-group reading would be a reading
#: of one extreme and would stand for nothing else on the sheet. Two is the
#: least that can disagree, so it is the least a sheet-level worst case can be
#: read from.
#:
#: And it refuses nothing a real chart offers: of 101 measured sheets on this
#: machine that carry repeats at all, not one carries fewer than two groups.
#: The floor exists to stop a hand-built chart being judged on a single
#: colour, not to withhold the row from ordinary work.
REPEAT_WITHIN_MIN_GROUPS = 2

#: **Row B, the same chart measured again.** The least number of patches the
#: two measurements must still share.
#:
#: DERIVED from the same five per cent the rest of the table is cut at. The
#: row is a maximum, and a maximum over *n* patches is worth reporting when it
#: has a fair chance of having touched the worst twentieth of the chart: the
#: chance that none of *n* patches falls in the worst 5 % is ``0.95 ** n``, and
#: ``0.95 ** n <= 0.5`` first holds at ``n = ceil(ln 0.5 / ln 0.95) = 14``.
#: Below that the largest of what was read says more about which patches
#: happened to match than about the printer.
#:
#: Measured against the demo pack's dated series: a genuine re-measurement of
#: the same chart shares 105 or 108 patches, and the two pairs where the chart
#: itself had been changed share 4. Fourteen separates those cleanly.
REPEAT_ACROSS_MIN_PATCHES = 14

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
#: KEPT ONLY TO READ REPORTS SAVED BEFORE 2026-09-13. It was a REASON, which
#: in this module means "why this row has no verdict", and rows carrying it
#: were shown for information instead of being graded (CH-17). Knut overruled
#: that: *"the grey metric tests is not about the printer, it is about
#: verifying that the profile created for a specific paper or process condition
#: measures within set acceptable thresholds. The verdicts should be given, but
#: a note can be given in a numbered list of notes, where a verdict is
#: commented."* A saved report keeps the verdicts it was saved with, so this
#: constant still has to be recognised on the way in; nothing writes it any more.
REASON_PRINTING_UNRECORDED = "printing_unrecorded"
REASON_NO_CORNERS = "no_corners"
REASON_NOT_COMPUTED = "not_computed"     # the block is missing from this report
#: S2w, approved 2026-09-18. TWO codes for the control strip, because they
#: send a reader to different places: one asks the chart to declare a strip at
#: all, the other says the strip it declares is too short to average over.
REASON_NO_CONTROL_STRIP = "no_control_strip"
REASON_CONTROL_STRIP_TOO_SMALL = "control_strip_too_small"
#: …and one per gamut population, for the same reason: the patches to add are
#: different colours and the reader is sent to a different corner of Create
#: Chart.
REASON_TOO_FEW_SURFACE_PATCHES = "too_few_surface_patches"
REASON_TOO_FEW_OUTER_PATCHES = "too_few_outer_patches"
#: …and two per repeatability row, for the same reason again: each sends a
#: reader somewhere different. A chart with no repeated colour at all and a
#: chart that repeats one colour are different situations; so are a chart that
#: has never been measured twice and a pair of measurements that turn out not
#: to be of the same chart.
REASON_NO_REPEAT_PATCHES = "no_repeat_patches"
REASON_TOO_FEW_REPEAT_GROUPS = "too_few_repeat_groups"
REASON_NO_EARLIER_MEASUREMENT = "no_earlier_measurement"
REASON_TOO_FEW_SHARED_PATCHES = "too_few_shared_patches"
#: …and these four are the ONLY codes that never reach the preset window,
#: because `preset_eligibility.rows_asked` does not ask the two rows that
#: produce them (`compliance_sets.POPULATION_MAY_BE_ABSENT`). Named here, and
#: not spelled out again in the guard that sweeps this module, so the two
#: cannot drift apart.
REPEATABILITY_REASONS: "tuple[str, ...]" = (
    REASON_NO_REPEAT_PATCHES, REASON_TOO_FEW_REPEAT_GROUPS,
    REASON_NO_EARLIER_MEASUREMENT, REASON_TOO_FEW_SHARED_PATCHES,
)

# ---------------------------------------------------------------------------
# Notes: a comment ON a verdict, which is not a reason for withholding one
# ---------------------------------------------------------------------------
#: A NOTE and a REASON answer different questions and must never be merged.
#:
#: * a **reason** says why a row has no verdict. The row reads N-A or INFO and
#:   the reason explains the absence.
#: * a **note** comments a verdict that WAS given. The row reads PASS, FAIL or
#:   CONDITIONAL, the number stands, and the note says what a reader should
#:   know when weighing it.
#:
#: They were one thing until Knut's ruling above, and merging them is what
#: produced a grey row with no verdict on a chart that had supplied every
#: value it needed.
NOTE_PRINTING_UNRECORDED = "printing_unrecorded"

#: A ROW WHOSE LIMIT THE SET RECOMMENDS RATHER THAN REQUIRES. Knut retired COND
#: as a row word on 2026-09-21 and asked, in the same message, for what takes
#: its place: *"there should be a note associated with the metric its self,
#: like a reference number at the end of the metric label-name, pointing to a
#: note below the table in the Report Limits window (and in the report text
#: also a number on the metric name, pointing to a note in the report text)."*
#:
#: THE ONE NOTE HERE THAT COMES FROM THE LIMIT AND NOT FROM THE VALUE. Every
#: other code is attached in `row_values`, where the measurement is examined.
#: This one cannot be: whether a row is a recommendation is a fact about the
#: SET the report is judged against, which `row_values` never sees. It is
#: attached in :func:`judge`, the one place that holds a value and its limit at
#: the same moment. The text is `measurement_messages.M_LIMIT_RECOMMENDED`.
NOTE_RECOMMENDED_LIMIT = "recommended_limit"


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


# ---------------------------------------------------------------------------
# The control strip a chart declares for itself (#182 S2w)
# ---------------------------------------------------------------------------
#: The header of a CGATS file, one keyword per line, above BEGIN_DATA_FORMAT.
_CGATS_KW_RE = re.compile(r'^([A-Z][A-Z0-9_]*)\s+"?(.*?)"?\s*$')


def _cgats_keyword(path: Path, key: str) -> str:
    """One CGATS keyword from a ``.ti1`` / ``.ti2`` / ``.ti3`` header, or ``""``.

    Read directly rather than through :func:`parse_ti3`, and that is the point:
    a ``.ti1`` need not carry any colour column at all, and ``parse_ti3``
    refuses a file with no measurement table. The control-strip declaration
    lives in the header, so a chart that declares one must be readable whether
    or not its file would survive being parsed as a measurement.
    """
    try:
        text = read_text(path, lenient=True)
    except OSError:
        return ""
    for ln in text.splitlines():
        s = ln.strip()
        if s == "BEGIN_DATA_FORMAT":
            break
        if not s.startswith(key):
            continue
        m = _CGATS_KW_RE.match(s)
        if m and m.group(1) == key:
            return m.group(2)
    return ""


def _split_ids(text: str) -> "list[str]":
    """``"A1 A2, A3"`` → ``["A1", "A2", "A3"]``, order kept, duplicates dropped."""
    parts = [p for p in re.split(r"[,\s]+", str(text or "").strip()) if p]
    return list(dict.fromkeys(parts))


def control_strip_declaration(ti3_path: "str | Path",
                              chart_path: "Path | None" = None) -> "dict | None":
    """What the chart says its own control strip is, or None when it says nothing.

    Knut's S2w rule, approved 2026-09-18:

        A chart carries a control strip when a sidecar
        ``<chart stem>.control-strip.json`` sits beside it holding
        ``{"name": "<the strip's own name>", "sample_ids": ["A1", "A2", ...]}``,
        or when the ``.ti1`` / ``.ti2`` carries a CGATS keyword
        ``CONTROL_STRIP_IDS`` naming the same ids.

    The sidecar wins where both exist, because it is the one a user can edit
    without rewriting a chart file. Anything unreadable is passed over with a
    log line and the next candidate tried: a broken sidecar leaves the chart
    where it was, undeclared, which is the state every chart is in today.

    Returns ``{"name", "ids", "source", "file"}``. ``source`` is ``"sidecar"``
    or ``"keyword"`` so the report can say where the declaration came from.
    """
    ti3_path = Path(ti3_path)
    chart_path = Path(chart_path) if chart_path else None
    # BESIDE ANY CHART THIS MEASUREMENT COULD BE PAIRED WITH, not only beside
    # the one that won. A dated verification is paired with the snapshot in its
    # own `chart/` folder, so a sidecar beside the run's chart, which is the
    # file a user opens and names, was invisible; measured on screen while
    # photographing this, on the demo pack. The order is the report's own
    # pairing order, then the measurement itself, because a user who drops a
    # sidecar next to the file they measured means it.
    for base in [*_reference_ti2_candidates(ti3_path),
                 *( [chart_path] if chart_path else [] ), ti3_path]:
        if base is None:
            continue
        p = base.parent / (base.stem + CONTROL_STRIP_SIDECAR)
        if not p.is_file():
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("control-strip sidecar %s unreadable (%s); "
                        "the chart declares no strip", p, exc)
            continue
        if not isinstance(doc, dict):
            log.warning("control-strip sidecar %s is not an object", p)
            continue
        ids = _split_ids(" ".join(str(s) for s in (doc.get("sample_ids") or [])))
        if not ids:
            log.warning("control-strip sidecar %s names no sample_ids", p)
            continue
        return {"name": str(doc.get("name") or "").strip(), "ids": ids,
                "source": "sidecar", "file": p.name}
    seen: "set[Path]" = set()
    for base in [*_reference_ti2_candidates(ti3_path),
                 *( [chart_path] if chart_path else [] )]:
        for cand in (base, base.with_suffix(".ti1"), base.with_suffix(".ti2")):
            if cand in seen:
                continue
            seen.add(cand)
            if not cand.is_file():
                continue
            ids = _split_ids(_cgats_keyword(cand, CONTROL_STRIP_KEYWORD))
            if ids:
                name = _cgats_keyword(cand, "CONTROL_STRIP_NAME")
                return {"name": name.strip(), "ids": ids,
                        "source": "keyword", "file": cand.name}
    return None


def control_strip_block(lab, ref: "dict[str, tuple]", sample_ids: "list[str]",
                        declaration: "dict | None") -> dict:
    """The control-strip block of a report (see :func:`control_strip_declaration`).

    ``n`` is **k**: the declared ids that are in this measurement AND carry a
    reference value. S2w states those two conditions separately ("k, the count
    of those ids present in the measured .ti3 … and when a reference exists for
    them"); counting them as one number is never more lenient than counting
    them apart, and it is the population the statistics are actually taken
    over, which is what the eight and the twenty are about. ``n_present``
    keeps the other count so the two can be told apart: a strip that is all
    there and has no reference reads ``no_reference``, not "too small", because
    those send a reader to different places.
    """
    block: dict = {
        "declared": declaration is not None,
        "name": (declaration or {}).get("name", ""),
        "source": (declaration or {}).get("source", ""),
        "declared_ids": len((declaration or {}).get("ids", ())),
        "n_present": 0, "n": 0, "eligible": False, "p95_eligible": False,
        "reason": REASON_NO_CONTROL_STRIP,
        "avg": None, "max": None, "p95": None,
    }
    if declaration is None:
        return block
    index = {sid: i for i, sid in enumerate(sample_ids)}
    present = [sid for sid in declaration["ids"] if sid in index]
    block["n_present"] = len(present)
    des = [ciede2000(tuple(lab[index[sid]]), tuple(ref[sid]))
           for sid in present if ref and sid in ref]
    block["n"] = k = len(des)
    if len(present) >= CONTROL_STRIP_MIN and k == 0:
        block["reason"] = REASON_NO_REFERENCE
        return block
    if k < CONTROL_STRIP_MIN:
        block["reason"] = REASON_CONTROL_STRIP_TOO_SMALL
        return block
    s = _stats(des)
    block["eligible"] = True
    block["reason"] = None
    block["avg"] = s["avg_all"]
    block["max"] = s["max_all"]
    # THE 95TH PERCENTILE IS A SEPARATE ELIGIBILITY, not a separate statistic.
    # `_stats` computes it as the nearest rank ceil(0.95 k), which IS k below
    # twenty, so the number exists at every size and is simply the largest
    # again. Publishing it there would be a second row saying what the row
    # above it already says.
    block["p95_eligible"] = k >= CONTROL_STRIP_P95_MIN
    block["p95"] = s["max_low95"] if block["p95_eligible"] else None
    return block


# ---------------------------------------------------------------------------
# The two gamut populations ChromIQ defines for itself (#182 S2w)
# ---------------------------------------------------------------------------
def gamut_populations_block(rgb100, lab, ref: "dict[str, tuple]",
                            sample_ids: "list[str]") -> dict:
    """The surface-gamut and outer-gamut populations, and their averages.

    These two rows were missing the DEFINITION of their population, not the
    detection: the standards name their own lists of patches and ChromIQ does
    not hold them. Knut's S2w ruling gives ChromIQ its own definitions and
    changes the group heading to "Selected patches of the chart" in the same
    breath, so the rows describe the chart in front of the user and claim
    nothing about anybody's published list.

    The cube corners are IN both populations. They are surface patches by
    construction and the most saturated patches on any chart, and S2w excludes
    nothing; the ΔE00 statistics above exclude them for a different reason
    (they are unreachable by design on a from-profile-gamut chart) and that
    exclusion is not carried over here.
    """
    rgb = np.asarray(rgb100, dtype=float)
    n_rows = len(sample_ids)
    surface: dict = {"n_surface": 0, "n": 0, "eligible": False,
                     "reason": REASON_TOO_FEW_SURFACE_PATCHES, "avg": None}
    outer: dict = {"n_referenced": 0, "n": 0, "eligible": False,
                   "reason": REASON_TOO_FEW_OUTER_PATCHES, "avg": None,
                   "chroma_floor": None}

    on_surface = [i for i in range(n_rows)
                  if float(np.min(np.minimum(rgb[i], 100.0 - rgb[i])))
                  <= SURFACE_GAMUT_TOL]
    surface["n_surface"] = len(on_surface)
    sdes = [ciede2000(tuple(lab[i]), tuple(ref[sample_ids[i]]))
            for i in on_surface if ref and sample_ids[i] in ref]
    surface["n"] = len(sdes)
    if len(on_surface) >= SURFACE_GAMUT_MIN and not sdes:
        surface["reason"] = REASON_NO_REFERENCE
    elif len(sdes) >= SURFACE_GAMUT_MIN:
        surface["eligible"] = True
        surface["reason"] = None
        surface["avg"] = round(float(np.mean(sdes)), 3)

    # The population is the top quartile BY THE REFERENCE'S chroma, so it is a
    # property of the chart and the same patches every time that chart is
    # measured. Ordered by chroma and then by sample id, so a tie at the
    # quartile boundary is broken the same way on every run.
    referenced = [i for i in range(n_rows) if ref and sample_ids[i] in ref]
    outer["n_referenced"] = len(referenced)
    if not referenced:
        outer["reason"] = REASON_NO_REFERENCE
        return {"surface": surface, "outer": outer}
    ranked = sorted(referenced,
                    key=lambda i: (-math.hypot(float(ref[sample_ids[i]][1]),
                                               float(ref[sample_ids[i]][2])),
                                   sample_ids[i]))
    k = max(1, int(math.ceil(len(referenced) * OUTER_GAMUT_FRACTION)))
    top = ranked[:k]
    outer["n"] = len(top)
    outer["chroma_floor"] = round(
        float(math.hypot(float(ref[sample_ids[top[-1]]][1]),
                         float(ref[sample_ids[top[-1]]][2]))), 2)
    if len(top) >= OUTER_GAMUT_MIN:
        odes = [ciede2000(tuple(lab[i]), tuple(ref[sample_ids[i]])) for i in top]
        outer["eligible"] = True
        outer["reason"] = None
        outer["avg"] = round(float(np.mean(odes)), 3)
    return {"surface": surface, "outer": outer}


# ---------------------------------------------------------------------------
# The two repeatability populations ChromIQ defines for itself
# ---------------------------------------------------------------------------
def repeat_within_sheet_block(rgb100, lab) -> dict:
    """Row A: how far apart the repeats of one colour landed on ONE sheet.

    A chart that asks for the same device colour more than once gives a direct
    read on the instrument and the print together, with no profile, no aim
    values and no second sheet in it: the two patches were asked for the same
    thing, so everything between them is the printer and the reader.

    The grouping is :func:`ti3_analysis.device_repeat_groups`, the same
    function the Ti3 Info window's own duplicate figure uses, so the two
    windows cannot disagree about which patches are repeats. The STATISTIC is
    ΔE00 here and ΔEab there, deliberately: this row stands beside thirty
    other ΔE00 rows and is judged against a ΔE00 limit, and the Ti3 Info
    window's long-standing number is not changed to suit it.

    Written even when the sheet cannot supply it, with the reason, exactly as
    the blocks above are.
    """
    from workflow.ti3_analysis import device_repeat_groups
    block: dict = {"n_groups": 0, "n_comparisons": 0, "eligible": False,
                   "reason": REASON_NO_REPEAT_PATCHES, "max": None}
    if rgb100 is None or not len(rgb100):
        return block
    groups = device_repeat_groups(np.asarray(rgb100, dtype=float))
    block["n_groups"] = len(groups)
    if not groups:
        return block
    des: "list[float]" = []
    for members in groups:
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                des.append(ciede2000(tuple(lab[members[a]]),
                                     tuple(lab[members[b]])))
    block["n_comparisons"] = len(des)
    if len(groups) < REPEAT_WITHIN_MIN_GROUPS:
        block["reason"] = REASON_TOO_FEW_REPEAT_GROUPS
        return block
    block["eligible"] = True
    block["reason"] = None
    block["max"] = round(float(max(des)), 3)
    return block


def _earlier_measurements_of(ti3_path: Path) -> "list[Path]":
    """Every dated measurement of this chart taken BEFORE *ti3_path*, newest
    first, or ``[]`` when this file is not a dated verification at all.

    A verification lives in ``runs/runN/verifications/<date>/`` and the folder
    id IS the timestamp, so "before" is the folder ordering `Run.verifications`
    already relies on. Nothing else in the run is considered: the run's own
    profiling chart is a different sheet printed a different way, and reading
    it as an earlier print of this chart is exactly the mispairing that
    produced a trend point of ΔE 41 once before.
    """
    from core.file_manager import VERIFICATIONS_DIRNAME
    d = ti3_path.parent
    if d.parent.name != VERIFICATIONS_DIRNAME:
        return []
    mine = d.name
    out: "list[Path]" = []
    try:
        siblings = sorted(p for p in d.parent.iterdir() if p.is_dir())
    except OSError:
        return []
    for sib in siblings:
        if sib.name >= mine:
            continue
        for cand in sorted(sib.glob("*.ti3")):
            out.append(cand)
            break
    out.reverse()                       # newest of the earlier ones first
    return out


def repeat_across_sheets_block(ti3_path: "str | Path", lab,
                               sample_ids: "list[str]", rgb100) -> dict:
    """Row B: this measurement against the one before it, patch for patch.

    Print-to-print and day-to-day, which is what a printer user means by "is
    my printer steady" and the population ISO 12647-8 treats separately from
    anything read off a single sheet. ChromIQ computes it from the user's own
    dated verifications and claims nothing about that or any other standard.

    **The comparison is with the measurement IMMEDIATELY BEFORE this one**, not
    with the first of the series. Repeatability is the scatter between
    repeats; distance from a baseline is a different question, and a
    worst-over-all-history would grow for ever and leave one bad day condemning
    every measurement after it.

    **And it must really be the same chart.** Patches are paired by SAMPLE_ID,
    as the rest of the report pairs them, and a pair is then kept only when the
    two files agree about the device values that patch was asked for, within
    the report's own :data:`PATCH_IDENTITY_TOL`. A chart that was regenerated
    between the two dates therefore drops out of the population instead of
    being read as printer drift, which is measured behaviour: two of the demo
    pack's eleven consecutive pairs are chart changes and fall from 105 shared
    patches to 4.
    """
    ti3_path = Path(ti3_path)
    block: dict = {"n_shared": 0, "eligible": False,
                   "reason": REASON_NO_EARLIER_MEASUREMENT, "max": None,
                   "compared_with": None}
    earlier = _earlier_measurements_of(ti3_path)
    if not earlier:
        return block
    prev = earlier[0]
    try:
        pdata = parse_ti3(prev)
    except (Ti3ParseError, OSError):
        return block
    block["compared_with"] = prev.parent.name
    plab = {sid: xyz_to_lab((x / 100.0, y / 100.0, z / 100.0))
            for sid, (x, y, z) in zip(pdata.sample_ids, pdata.xyz)}
    prgb = (dict(zip(pdata.sample_ids,
                     _rgb_to_0_100(np.asarray(pdata.rgb, dtype=float))))
            if pdata.rgb is not None and len(pdata.rgb) else {})
    mine_rgb = (dict(zip(sample_ids, np.asarray(rgb100, dtype=float)))
                if rgb100 is not None and len(rgb100) else {})
    des: "list[float]" = []
    for i, sid in enumerate(sample_ids):
        if sid not in plab:
            continue
        if prgb and mine_rgb and sid in prgb and sid in mine_rgb:
            if float(np.abs(prgb[sid] - mine_rgb[sid]).max()) > PATCH_IDENTITY_TOL:
                continue                # a different colour under the same id
        des.append(ciede2000(tuple(plab[sid]), tuple(lab[i])))
    block["n_shared"] = len(des)
    if len(des) < REPEAT_ACROSS_MIN_PATCHES:
        block["reason"] = REASON_TOO_FEW_SHARED_PATCHES
        return block
    block["eligible"] = True
    block["reason"] = None
    block["max"] = round(float(max(des)), 3)
    return block


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
    """``{row_id: {"value", "reason", "graded", "notes"}}`` for every row
    ChromIQ can compute from *report*.

    ``value`` is None with a ``reason`` code when the chart or the reference
    cannot supply the row. ``graded`` is False for a row that cannot be judged
    on this sheet at all, None to inherit the sheet's own grading. ``notes`` is
    a list of note codes commenting a verdict that WAS given: see
    :data:`NOTE_PRINTING_UNRECORDED` for why the two are not the same thing.

    Nothing sets ``graded`` False here any more. CH-17 did, on the grey rows,
    and Knut overruled it on 2026-09-13.
    """
    report = report or {}
    de, source = graded_de00(report)
    out: "dict[str, dict]" = {}

    def put(rid, value, reason=None, graded=None, notes=None):
        out[rid] = {"value": (float(value) if value is not None else None),
                    "reason": reason, "graded": graded,
                    "notes": ([notes] if isinstance(notes, str)
                              else list(notes or []))}

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

    # -- grey balance. GRADED, WITH A NOTE, since Knut's ruling of 2026-09-13.
    #
    # CH-17 withheld the verdict here whenever nobody recorded how the sheet
    # was printed and the reference was the chart's own design, on the argument
    # that in absolute Lab the paper's own tint lands in the row. The
    # observation is true; the conclusion was his to make and he made the other
    # one: *"The verdicts should be given, but a note can be given in a
    # numbered list of notes, where a verdict is commented, for example
    # regarding the tint of a paper and profile combination."*
    #
    # So the condition that used to switch grading off now attaches a note, and
    # the row is judged like every other row.
    gb = report.get("grey_balance") or {}
    grey_note = None
    if (not report.get("printing")
            and report.get("reference_source") in ("design", "device")):
        grey_note = NOTE_PRINTING_UNRECORDED
    if not gb:
        # an older report, or one whose measurement file could not be read
        # again: the block is absent, which is not the same as "no greys" (N9)
        put("grey_balance_neutral_ramp_avg", None, REASON_NOT_COMPUTED)
        put("grey_balance_neutral_ramp_max", None, REASON_NOT_COMPUTED)
    elif gb.get("eligible") and gb.get("avg") is not None:
        put("grey_balance_neutral_ramp_avg", gb["avg"], notes=grey_note)
        put("grey_balance_neutral_ramp_max", gb["max"], notes=grey_note)
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

    # -- the control strip the chart declares for itself (S2w, 2026-09-18)
    #
    # A report saved before this existed carries no block, which is not the
    # same thing as "this chart declares no strip" (N9, the same distinction
    # the grey rows draw above): it says nothing at all, and the sentence for
    # `not_computed` says exactly that.
    _CS_ROWS = ("control_strip_de00_avg", "control_strip_de00_max",
                "control_strip_de00_p95")
    cstrip = report.get("control_strip")
    if not isinstance(cstrip, dict):
        for rid in _CS_ROWS:
            put(rid, None, REASON_NOT_COMPUTED)
    elif cstrip.get("eligible"):
        put("control_strip_de00_avg", cstrip.get("avg"))
        put("control_strip_de00_max", cstrip.get("max"))
        if cstrip.get("p95") is not None:
            put("control_strip_de00_p95", cstrip["p95"])
        else:
            # THE STRIP IS BIG ENOUGH FOR TWO OF THE THREE ROWS AND NOT THE
            # THIRD, and that is the whole reason the 95th percentile carries
            # its own threshold. The same code, because it is the same thing
            # to do about it: a longer strip.
            put("control_strip_de00_p95", None, REASON_CONTROL_STRIP_TOO_SMALL)
    else:
        for rid in _CS_ROWS:
            put(rid, None, cstrip.get("reason") or REASON_NO_CONTROL_STRIP)

    # -- the two gamut populations (S2w, 2026-09-18)
    gp = report.get("gamut_populations")
    if not isinstance(gp, dict):
        put("surface_gamut_de00_avg", None, REASON_NOT_COMPUTED)
        put("outer_gamut_226_de00_avg", None, REASON_NOT_COMPUTED)
    else:
        surf = gp.get("surface") or {}
        if surf.get("eligible") and surf.get("avg") is not None:
            put("surface_gamut_de00_avg", surf["avg"])
        else:
            put("surface_gamut_de00_avg", None,
                surf.get("reason") or REASON_TOO_FEW_SURFACE_PATCHES)
        outr = gp.get("outer") or {}
        if outr.get("eligible") and outr.get("avg") is not None:
            put("outer_gamut_226_de00_avg", outr["avg"])
        else:
            put("outer_gamut_226_de00_avg", None,
                outr.get("reason") or REASON_TOO_FEW_OUTER_PATCHES)

    # -- ChromIQ's own two repeatability rows.
    #
    # A report saved before these existed carries no block, which is not the
    # same thing as "this sheet has no repeats" and not the same thing as
    # "this chart has never been measured twice" -- the same N9 distinction the
    # grey rows and the control strip draw above.
    rw = report.get("repeat_within_sheet")
    if not isinstance(rw, dict):
        put("repeat_patches_de00_max", None, REASON_NOT_COMPUTED)
    elif rw.get("eligible") and rw.get("max") is not None:
        put("repeat_patches_de00_max", rw["max"])
    else:
        put("repeat_patches_de00_max", None,
            rw.get("reason") or REASON_NO_REPEAT_PATCHES)

    ra = report.get("repeat_across_sheets")
    if not isinstance(ra, dict):
        put("repeat_measurement_de00_max", None, REASON_NOT_COMPUTED)
    elif ra.get("eligible") and ra.get("max") is not None:
        put("repeat_measurement_de00_max", ra["max"])
    else:
        put("repeat_measurement_de00_max", None,
            ra.get("reason") or REASON_NO_EARLIER_MEASUREMENT)
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
    from workflow.compliance_sets import (COND, FAIL, PASS, ROWS, Limit,
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
            # A NOTE TRAVELS WITH THE ROW IT COMMENTS, and only where there is
            # a verdict to comment. A note beside an N-A would be a footnote on
            # an absence, which is what `reason` is already for.
            "notes": (_row_notes(cell, lim)
                      if word in (PASS, FAIL, COND) else []),
        })
    return rows


def _row_notes(cell: "dict | None", lim) -> "list[str]":
    """The note codes one judged row carries.

    The measurement's own notes, then the limit's. A recommended limit is
    commented WHETHER IT PASSED OR FAILED, because the note says what the
    standard calls the metric rather than what the number did: a reader of a
    passing row is owed the same fact as a reader of a failing one, and a note
    that appeared only on failures would read as an excuse for the failure --
    which is the reading Knut withdrew on 2026-09-21.
    """
    notes = list((cell or {}).get("notes") or [])
    if getattr(lim, "is_should", False) and NOTE_RECOMMENDED_LIMIT not in notes:
        notes.append(NOTE_RECOMMENDED_LIMIT)
    return notes


def numbered_notes(rows: "list[dict]") -> "list[tuple[int, str, list[str]]]":
    """``[(number, note_code, [row_id, ...])]`` for the notes *rows* carry.

    Knut's ruling of 2026-09-13 asks for *"a numbered list of notes, where a
    verdict is commented"*, so the number is the thing that ties a verdict cell
    to its comment and it has to be stable and shared. One function computes it
    and every renderer asks: a second copy of the numbering in the window and
    in the PDF is two documents that disagree about which note is note 1.

    Numbered in ROW ORDER, from 1, one number per distinct code however many
    rows carry it. A code that appears on three rows is one note naming three
    rows, not three notes saying the same thing.

    Rows are not mutated. The caller asks :func:`note_numbers_for` for a row's
    markers.
    """
    order: "list[str]" = []
    who: "dict[str, list[str]]" = {}
    for row in rows or ():
        rid = row.get("row_id") or row.get("key")
        for code in (row.get("notes") or ()):
            if code not in who:
                order.append(code)
                who[code] = []
            if rid not in who[code]:
                who[code].append(rid)
    return [(i + 1, code, who[code]) for i, code in enumerate(order)]


def note_label(n: int) -> str:
    """How note *n* is written, both as the raised marker on a verdict and as
    the item label in the list under the table.

    ONE FUNCTION, because the marker and the list have to read the same. Knut
    asked for the marker on 2026-09-13: *"the verdict line in a table which
    applies to a note should snow a number as a reference to the note that
    applies to it, f.ex. a note as a raised number, ex. '1)' '2)' or 'a)'
    'b)'"*. The first build printed a bare superscript digit beside the verdict
    and a "1." in the list, which is two notations for one thing and neither of
    them the one he named.
    """
    return f"{int(n)})"


def note_numbers_for(row: dict,
                     numbering: "list[tuple[int, str, list[str]]]") -> "list[int]":
    """The note numbers to print beside one row's verdict, ascending."""
    want = set(row.get("notes") or ())
    return sorted(n for (n, code, _rows) in (numbering or ()) if code in want)


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
        # THE ROW ID TRAVELS WITH THE PAIR, because the column's completeness
        # arithmetic has to know which row an N-A came from: a row whose
        # population may honestly not exist is not a gap (`compliance_sets.
        # POPULATION_MAY_BE_ABSENT`). Dropping it here is how a first
        # verification measurement would read COND instead of PASS.
        pairs.append((lim if isinstance(lim, Limit) else Limit.none(),
                      row["word"], row["row_id"]))
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


def _comparable(value):
    """*value* as something two limit copies can be compared by.

    A stored threshold is JSON, so it is a number, a string ("x", "?"), None,
    or a two-item list (the value and "should") for a recommendation. Lists
    become tuples and dicts become sorted tuples of pairs, so the whole copy
    can go into a set.
    """
    if isinstance(value, dict):
        return tuple(sorted((str(k), _comparable(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_comparable(v) for v in value)
    return value


def yardstick_key(compliance: "dict | None") -> "tuple | None":
    """The limit set a report was judged against, as one comparable key.

    **THE NUMBERS, NOT THE NAME.** Two runs can both say "ChromIQ default
    (recommended)" and be judged against different numbers: a run carries a
    COPY of the set it was bound to (§5 of
    ``docs/design/measurement_report_limits.md``), and Preferences overrides,
    an edit and a later factory change all move one copy without moving the
    other. The window derives "(edited)" from exactly that difference and shows
    it beside the name. So a key made of the name alone calls two different
    yardsticks one yardstick, which is the mix this function exists to stop.

    None when the report carries no record of what it was judged against; that
    is not a set, and a caller must decide what such a column is judged with
    rather than pretend it matches something.
    """
    if not isinstance(compliance, dict):
        return None
    thr = compliance.get("thresholds")
    if not isinstance(thr, dict):
        return None
    return (str(compliance.get("set_id") or ""), _comparable(thr))


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
    write_json_atomically(path, report)      # see the note in `save_report`
    return path
