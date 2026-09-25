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
import os
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


#: Where a FROM PROFILE GAMUT chart's reference paper came from (#182 A11).
PAPER_REF_FROM_CHART = "chart"        # recorded in the reference at build time
PAPER_REF_FROM_RUN = "run_profile"    # an older reference: the run's profile
#: #182 K37: the profile the sheet was printed through (its print record).
PAPER_REF_FROM_PRINT = "printed_through"

#: #182 K37: what ``report["paper_white_used"]["from"]`` says. The sheet's own
#: paper patch; the profile's media white, (e); no paper white could be had
#: for a sheet that wanted one, (b), judged in absolute Lab; or the sheet is
#: not judged relative to a paper at all (absolute by its printing, or a
#: colorimetric reference).
PAPER_WHITE_FROM_SHEET = "sheet"
PAPER_WHITE_FROM_PROFILE = "profile"
PAPER_WHITE_UNAVAILABLE = "unavailable"
PAPER_WHITE_NOT_USED = "not_used"


def paper_corner_ids(cref: "dict | None") -> "list[str]":
    """The declared corner ids of a colorimetric reference that are the bare
    paper: device white (`paper_patch_rows`) by the ink amount the reference
    itself records. Empty when it records none. Never raises."""
    if not cref:
        return []
    devices = cref.get("devices") or {}
    ids = [sid for sid in sorted(cref.get("corner_ids") or ())
           if sid in devices]
    if not ids:
        return []
    rows = paper_patch_rows([devices[s] for s in ids], "RGB")
    return [ids[i] for i in rows]


def paper_reference_of(cref: "dict | None", ti3_path: "Path | str | None"
                       ) -> "tuple[tuple[float, float, float], str] | None":
    """``(Lab, where from)`` of the paper a FROM PROFILE GAMUT chart's profile
    describes, or None (#182 A11, Knut 5817809396).

    **MEASURED BEFORE IT WAS CHANGED (beta 41 build, the release demo pack):**
    the row "Paper white, difference from the reference paper" compared the
    bare paper with the reference's W corner, which `gamut_target` writes as
    device white read as sRGB: L* 100.0, a* 0.01, b* -0.01, an ideal white. The
    pack's profiles describe papers of L* 94.0 to 96.0, so a real paper of the
    profile's own white read about 3 ΔE00 on every sheet. Knut: compare it with
    the paper the chart's profile describes, the profile's media white.

    The reference records that white since beta 42 (``CHROMIQ_PROFILE_WHITE_LAB``).
    A reference written before has none, and the run's own built profile is
    asked instead: the profile a FROM PROFILE GAMUT chart of that run is built
    from. None when neither can answer, and the row then keeps its old
    comparison with the W corner's aim. Never raises.
    """
    if cref and cref.get("profile_white_lab") is not None:
        try:
            return (tuple(float(v) for v in cref["profile_white_lab"]),
                    PAPER_REF_FROM_CHART)
        except (TypeError, ValueError):
            pass
    got = _run_profile_white(ti3_path)
    return (got[0], PAPER_REF_FROM_RUN) if got is not None else None


def _run_profile_white(ti3_path: "Path | str | None"
                       ) -> "tuple[tuple[float, float, float], str] | None":
    """``(media white Lab, profile file name)`` of the run's own built
    profile for the measurement at *ti3_path*, or None. THE ONE WAY a report
    asks a run's profile for its paper: `paper_reference_of` (A11) and
    `profile_paper_white` (K37) both come here. Never raises."""
    icc = _run_profile_path(ti3_path)
    if icc is None:
        return None
    try:
        from workflow.gamut_target import profile_media_white_lab
        lab = profile_media_white_lab(icc)
        return (lab, icc.name) if lab is not None else None
    except Exception:                                  # noqa: BLE001
        return None


def _run_profile_path(ti3_path: "Path | str | None") -> "Path | None":
    """The run's own built profile for the measurement at *ti3_path*, when it
    is on disk, else None. THE ONE PROFILE a report asks about a run's paper
    (`_run_profile_white`, A11 and K37) and about the corners of a FROM
    PROFILE GAMUT chart (`profile_corner_predictions`, K37 (i)): the profile
    such a chart of that run is built from. Never raises."""
    if ti3_path is None:
        return None
    try:
        from workflow.run_compliance import run_context_for
        ctx = run_context_for(ti3_path)
        if ctx is None:
            return None
        icc = ctx.run.built_profile_icc()
        return icc if icc.is_file() else None
    except Exception:                                  # noqa: BLE001
        return None


#: #182 K37 (i), what ``report["control_strip"]["corner_aims"]["from"]`` says
#: on a FROM PROFILE GAMUT chart: the seven ink and black corners were
#: compared with the profile's prediction, or (no profile or no ArgyllCMS to
#: ask) with their ideal values as before.
CORNER_AIMS_FROM_PROFILE = "profile"
CORNER_AIMS_IDEAL = "ideal"
#: …and on every other report: its strip holds no such corner.
CORNER_AIMS_NOT_APPLICABLE = "not_applicable"


def profile_corner_predictions(cref: "dict | None",
                               ti3_path: "Path | str | None",
                               argyll_bin: "str | Path | None"
                               ) -> "tuple[dict[str, tuple], str] | None":
    """``({sample id: Lab}, profile file name)``: what the profile predicts
    for the seven ink and black cube corners of a FROM PROFILE GAMUT chart,
    or None when it cannot be asked (#182 K37 (i), Knut 5823088098 "Yes do
    so", on our 5823015844).

    The corner's DEVICE value (the solid, the overprint, the composite black)
    run forward through the run's own built profile (`_run_profile_path`, the
    profile the paper white is read from too) with the chart's own intent, so
    the rung is judged the way every other patch of such a chart is: against
    the colour the profile says that ink amount prints. The bare-paper corner
    is not here: it aims at the profile's paper since §31.5. None without a
    profile, without ArgyllCMS, or when the lookup fails. Never raises.
    """
    if not cref or not argyll_bin:
        return None
    icc = _run_profile_path(ti3_path)
    if icc is None:
        return None
    got = corner_predictions_through(cref, icc, argyll_bin)
    return (got, icc.name) if got is not None else None


def corner_predictions_through(cref: "dict | None", icc: "Path | str",
                               argyll_bin: "str | Path | None"
                               ) -> "dict[str, tuple] | None":
    """``{sample id: Lab}``: *icc*'s forward prediction for the seven ink and
    black corners *cref* declares, with the chart's own intent; None when it
    cannot be asked. The one lookup `profile_corner_predictions` makes, and
    the one the demo generator makes for the charts it designs."""
    if not cref or not argyll_bin:
        return None
    devices = dict(cref.get("devices") or {})
    paper = set(paper_corner_ids(cref))
    ids = [sid for sid in sorted(cref.get("corner_ids") or ())
           if sid in devices and sid not in paper]
    if not ids:
        return None
    try:
        from workflow.gamut_target import intent_letter
        from workflow.xicclu_runner import forward_lab
        labs = forward_lab([tuple(float(v) for v in devices[sid])
                            for sid in ids], icc, argyll_bin,
                           intent=intent_letter(str(cref.get("intent") or "")))
    except Exception as exc:                           # noqa: BLE001
        log.debug("corner predictions skipped: %s", exc)
        return None
    if len(labs) != len(ids):
        return None
    return {sid: tuple(float(v) for v in lab) for sid, lab in zip(ids, labs)}


def profile_paper_white(printing: "dict | None",
                        ti3_path: "Path | str | None") -> "dict | None":
    """The paper white of the profile a sheet was printed through, for a
    sheet whose chart has no paper patch (#182 K37, Knut 5822758830: *"(e),
    with a numbered note on the sheet, and (b) only when no profile can be
    read"*), or None when no profile can be read (then (b)).

    ``{"lab": [L, a, b], "source": PAPER_REF_FROM_PRINT | PAPER_REF_FROM_RUN,
    "profile": "<file name>"}``.

    In order: the profile the print record names, when that file is still on
    disk (a sheet ChromIQ printed through its profile records it); else the
    run's own built profile, the profile such a sheet of that run is printed
    through and the one `paper_reference_of` asks for a FROM PROFILE GAMUT
    chart (A11). Both read the profile's media white the same way
    (`gamut_target.profile_media_white_lab`): the paper the profile was
    measured on. Never raises.
    """
    try:
        from workflow.gamut_target import profile_media_white_lab
        cand = (printing or {}).get("profile_path")
        if cand:
            icc = Path(str(cand))
            if icc.is_file():
                lab = profile_media_white_lab(icc)
                if lab is not None:
                    return {"lab": [round(float(v), 2) for v in lab],
                            "source": PAPER_REF_FROM_PRINT,
                            "profile": icc.name}
    except Exception:                                  # noqa: BLE001
        pass
    got = _run_profile_white(ti3_path)
    if got is None:
        return None
    return {"lab": [round(float(v), 2) for v in got[0]],
            "source": PAPER_REF_FROM_RUN, "profile": got[1]}


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


#: **THE PAPER PATCH IS THE PATCH PRINTED WITH NO INK (#182 A10, B8-806).**
#: Knut, 5817809396, accepting recommendation (a): *"Use the chart's own white
#: patch (device value 100, 100, 100) when there is one, and when there is
#: none say "This chart has no paper patch": Paper white reads N-A, and
#: nothing is judged relative to the paper."* Until beta 42 "Paper white" was
#: the LIGHTEST measured patch, and on a chart with no bare paper patch that is
#: a light colour or grey (an L* 82 grey on one demo chart), which was then
#: printed as the paper, drawn in its graph and divided into every reading of
#: a sheet judged relative to the paper.
#:
#: How close to the corner counts as no ink, on Argyll's 0..100 device scale.
#: A device value is a request, not a measurement, so the honest tolerance is
#: rounding: 0.5 is one code value of 255 (0.39) with room to spare, and far
#: from any real light tint (a 97 % tint is 3 units away).
PAPER_PATCH_TOL = 0.5


def paper_patch_rows(device100, space: str = "RGB") -> "list[int]":
    """The rows of *device100* (device values, 0..100) printed with no ink.

    WHICH CORNER IS "NO INK" DEPENDS ON THE SPACE, the same rule
    `workflow.reference_sets.paper_lab` follows for a reference file:

    * **RGB** (additive, the only space the report reads today): every
      channel at its maximum, 100, 100, 100;
    * **CMY, CMYK and every n-colour ink space** (subtractive): every channel
      at 0. `parse_ti3` refuses such a measurement for the report today
      ("only RGB charts are supported"), so this branch answers the question
      for the day it is lifted rather than leaving it to be guessed then.

    Empty when there are no device values or no such row. Never raises.
    """
    try:
        arr = np.asarray(device100, dtype=float)
    except (TypeError, ValueError):
        return []
    if arr.ndim != 2 or not len(arr):
        return []
    if str(space or "RGB").upper().startswith("RGB"):
        hit = (arr >= 100.0 - PAPER_PATCH_TOL).all(axis=1)
    else:
        hit = (arr <= PAPER_PATCH_TOL).all(axis=1)
    return [int(i) for i in np.flatnonzero(hit)]


def paper_white_row(lab, device100, space: str = "RGB") -> "int | None":
    """The reading that is the paper white: of the rows printed with no ink
    (`paper_patch_rows`), the lightest; None when the chart has none (A10).

    The lightest OF THE PAPER PATCHES, so a chart that carries several bare
    patches (most do) gives exactly the patch it gave before beta 42, and only
    a chart without one changes."""
    rows = paper_patch_rows(device100, space)
    if not rows or lab is None:
        return None
    try:
        return max(rows, key=lambda i: float(lab[i][0]))
    except (IndexError, TypeError, ValueError):
        return None


def _device_values_of(data, ti3_path: "Path | None" = None):
    """Device values (0..100) per reading of *data*, or None.

    From the measurement's own device columns; for a measurement that carries
    none (an i1Profiler export of a chart it did not generate, `parse_ti3`),
    from the chart it is paired with, by SAMPLE_ID, which is how the rest of
    the report pairs it. None when neither can say."""
    rgb = getattr(data, "rgb", None)
    if rgb is not None and len(rgb):
        return _rgb_to_0_100(np.asarray(rgb, dtype=float))
    if ti3_path is None:
        return None
    try:
        ti2 = _find_reference_ti2(Path(ti3_path))
        if not ti2.is_file():
            return None
        chart = parse_ti3(ti2)
        if chart.rgb is None or not len(chart.rgb):
            return None
        by_id = dict(zip(chart.sample_ids,
                         _rgb_to_0_100(np.asarray(chart.rgb, dtype=float))))
        rows = [by_id.get(sid) for sid in data.sample_ids]
        if any(r is None for r in rows):
            # a reading the chart does not name cannot be the paper; give it
            # a value no paper test can pass
            rows = [r if r is not None else np.array([50.0, 50.0, 50.0])
                    for r in rows]
        return np.asarray(rows, dtype=float)
    except Exception:                                  # noqa: BLE001
        return None


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
    _lightest, bi = extremes
    # THE PAPER IS THE PATCH WITH NO INK, not the lightest reading (A10).
    wi = paper_white_row(lab, _device_values_of(data, ti3_path))
    if wi is None:
        # "This chart has no paper patch": no paper white is recorded, and
        # `paper_patch` says why, so a reader can tell it from a report
        # written before beta 42 (which carries neither key's absence).
        return {
            "patches": data.n_patches,
            "paper_patch": False,
            "max_black": {
                "loc": (data.sample_locs[bi] if data.sample_locs
                        else data.sample_ids[bi]),
                "lab": [round(v, 2) for v in lab[bi]],
                "hex": _srgb_hex(tuple(data.xyz[bi])),
            },
        }
    return {
        "patches": data.n_patches,
        "paper_patch": True,
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
    swatch was right. The demo pack's white was Lab 100.0 / -2.3 / -19.4 (XYZ
    95.08 / 100 / 108.93, close to D65), and only the L* was printed, so
    nothing on the page explained the colour.
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
    # The readings as MEASURED, kept because `lab` may be re-read below in the
    # media-relative yardstick, and one row must not see both (K15).
    absolute_lab = lab

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
    _cref = None
    if state == STATE_CONVERTED:
        from workflow.gamut_target import read_colorimetric_reference
        cref = read_colorimetric_reference(colorimetric_reference_for(ref_ti2))
        if cref is None:
            state = STATE_CONVERTED_REF_MISSING
        else:
            _cref = cref
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
            # #182 A11 (Knut, 5817809396): the paper the chart's profile
            # describes, which "Paper white, difference from the reference
            # paper" compares the bare paper with. Recorded in the reference
            # since beta 42; for an older reference, the run's own profile.
            _pw = paper_reference_of(cref, ti3_path)
            if _pw is not None:
                report["colorimetric"]["paper_reference_lab"] = [
                    round(float(v), 2) for v in _pw[0]]
                report["colorimetric"]["paper_reference_from"] = _pw[1]
                # THE BARE-PAPER CORNER AIMS AT THAT PAPER, so the row, the
                # cube-corner table and a control-strip rung on that patch all
                # read one comparison. (`read_colorimetric_reference` has done
                # this already for a reference that records the white.)
                ref = dict(ref)
                for _sid in paper_corner_ids(cref):
                    ref[_sid] = tuple(float(v) for v in _pw[0])
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
    #: #182 K37: which paper white the colours were judged relative to, on
    #: every report (so a report saved before it is worked out again, §6).
    report["paper_white_used"] = {"from": PAPER_WHITE_NOT_USED}
    #: #182 E8: the aims EVENNESS compares the absolute readings with. The
    #: ΔE00 aims as they are, unless the sheet is read media-relative below.
    evenness_ref = None
    if ref_source in ("design", "device") and printing:
        _col = printing.get("colour")
        _route = printing.get("route")
        _intent = str(printing.get("intent") or "")
        white_mapping = (_col == "through-profile"
                         and (_intent not in ("", "absolute")
                              or _route == "external-cm"))
        # THE PAPER PATCH, NOT THE LIGHTEST READING (A10). With no paper
        # patch nothing is judged relative to the paper: the sheet stays in
        # absolute Lab, and the paper white line's note says so.
        _wi = paper_white_row(lab, rgb100 if rgb100 is not None
                              else _device_values_of(data, ti3_path))
        white_xyz = None
        if white_mapping and _wi is not None:
            white_xyz = np.asarray(data.xyz[_wi], dtype=float)
            report["paper_white_used"] = {"from": PAPER_WHITE_FROM_SHEET}
        if white_mapping and _wi is None:
            report["yardstick_no_paper"] = True
            # #182 K37 (Knut, 5822758830): "(e), with a numbered note on the
            # sheet, and (b) only when no profile can be read". (e): the
            # paper white of the profile the sheet was printed through, the
            # paper that profile was measured on. (b): none can be read, and
            # the sheet stays in absolute Lab with a note on every row that
            # moves. Measured on the demo pack (§33 of the design record).
            _pp = profile_paper_white(printing, ti3_path)
            if _pp is not None:
                from workflow.ti3_analysis import _lab_to_xyz_array
                white_xyz = np.asarray(_lab_to_xyz_array(
                    np.asarray([_pp["lab"]], dtype=float))[0], dtype=float)
                report["paper_white_used"] = dict(
                    _pp, **{"from": PAPER_WHITE_FROM_PROFILE})
            else:
                report["paper_white_used"] = {
                    "from": PAPER_WHITE_UNAVAILABLE}
        if white_xyz is not None:
            if float(white_xyz.min()) > 0.0:
                _d50 = np.array([96.42, 100.0, 82.49])
                lab = [xyz_to_lab(tuple(
                    (np.asarray(x, dtype=float) / white_xyz * _d50) / 100.0))
                    for x in data.xyz]
                report["yardstick"] = "media-relative"
                # #182 E8: evenness keeps the READINGS as measured and
                # carries the AIMS onto this paper instead (see below).
                evenness_ref = aims_on_the_paper(ref, white_xyz)
            else:
                # a paper reading with a zero channel cannot divide anything:
                # the sheet stays as measured, and the record says so
                report["paper_white_used"] = {"from": PAPER_WHITE_NOT_USED}

    # The eight cube corners (paper white, composite black, the six ink
    # primaries/secondaries) — the patch the chart DECLARES as each corner
    # where it declares one, else the nearest patch to it by device RGB. Each
    # carries its measured colour and, when a reference exists, its expected
    # colour and ΔE00, so the report says something about the inks, not only the
    # instrument (Knut). rgb is device 0..100.
    report["corners"] = corners_block(rgb100, lab, ref, data,
                                      corner_ids, corner_devices)

    in_gamut_ids: "set[str] | None" = None
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
                        # the same split, by patch, for the evenness rows:
                        # where the words judge the within-gamut figures,
                        # evenness is judged on the within-gamut patches
                        in_gamut_ids = {data.sample_ids[_i]
                                        for (_d, _i), f in zip(des, flags) if f}
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
        # K31 option (a): on a chart built FROM PROFILE GAMUT the grey steps
        # are its neutral AIMS, which `ref` holds on the colorimetric branch.
        report["grey_balance"] = grey_balance_block(
            rgb100, lab, ref, data.sample_ids,
            neutral_aims=ref if ref_source == "colorimetric" else None,
            corner_ids=corner_ids)
        # K40-2: …and the grey axis of its 30 to 70 % tone ramp too.
        report["ramps_30_70"] = ramps_block(
            rgb100, lab, ref, data.sample_ids,
            neutral_aims=ref if ref_source == "colorimetric" else None,
            corner_ids=corner_ids)
        # #182 S2w (Knut, 2026-09-18): the two gamut populations ChromIQ now
        # defines for itself. Written even when the chart cannot supply them,
        # with the reason, exactly as the two blocks above are.
        report["gamut_populations"] = gamut_populations_block(
            rgb100, lab, ref, data.sample_ids)
    else:
        # NO DEVICE VALUES: say so, rather than leave the blocks out. An
        # absent block is `not_computed`, which is the truth about a report
        # saved before a row existed and a falsehood about this one (K22).
        _none = {"eligible": False, "reason": REASON_NO_DEVICE_VALUES}
        report["grey_balance"] = dict(_none)
        report["ramps_30_70"] = dict(_none)
        report["gamut_populations"] = {"surface": dict(_none),
                                       "outer": dict(_none)}

    # ChromIQ'S OWN TWO REPEATABILITY ROWS, and neither asks for a reference.
    # Row A compares the sheet's repeated patches WITH EACH OTHER, and Row B
    # compares this measurement with the one before it, so both are answerable
    # on a chart that carries no aim values at all. That is the point of them:
    # they work for a user who holds no document and whose chart was never
    # built from a profile. Written with their reason when they cannot be
    # answered, as every block above is.
    report["repeat_within_sheet"] = repeat_within_sheet_block(rgb100, lab)
    #
    # **ROW B COMPARES TWO MEASUREMENTS, SO BOTH ARE READ THE SAME WAY (K15).**
    # It reads the EARLIER sheet straight off its XYZ, which is absolute Lab,
    # and it was handed THIS sheet's `lab`, which is media-relative whenever
    # the sheet was printed through its profile with a white-mapping intent.
    # On a paper whose white is not exactly the D50 white that is not a
    # comparison at all: measured on the rebuilt demo pack (paper L* 95.5),
    # two sheets designed 2.6 apart read 3.53, and two IDENTICAL sheets read
    # far from zero. It went unseen because every simulated sheet in the pack
    # had a paper of L* 100, where the two yardsticks nearly coincide. The
    # measurement against the measurement is a physical question, so both are
    # absolute; a paper that changed between the two sheets is part of the
    # answer, not an error in it.
    report["repeat_across_sheets"] = repeat_across_sheets_block(
        ti3_path, absolute_lab, data.sample_ids, rgb100)

    # EVENNESS ACROSS THE SHEET (Knut, 2026-09-22): every patch against its
    # own aim, the SAME aim as the ΔE00 rows above, averaged over the nine
    # areas of the page the chart's own layout puts it in. Written with its
    # reason when the sheet cannot answer it.
    #
    # **ALWAYS IN ABSOLUTE LAB, WHATEVER THE PRINT'S INTENT** (#182 E8, Knut,
    # 2026-09-23, 5795087247: "Yes"). Until beta 39 it took `lab`, which is
    # media-relative on a sheet printed with an intent that maps paper white:
    # every reading divided by the sheet's LIGHTEST PATCH. That patch sits in
    # one of the nine areas, so where that area really is lighter the whole
    # sheet was rescaled by a local deviation, by a different amount per
    # colour, and the demo's noise went from 0.3 to 3.7 (both rows N-A).
    # Every published uniformity test compares absolute readings of one sheet
    # with itself (E8-research.md), and evenness is a property of the printer
    # and the paper, not of how the sheet was colour-managed.
    #
    # **THE READINGS STAY AS MEASURED; ON SUCH A SHEET THE AIMS MOVE.** The
    # design aims of a white-mapped print describe an ideal white paper, so
    # against the READINGS of a real paper every patch is off by the paper's
    # own tint, by a different amount per colour. Measured on the 837-patch
    # demo chart as a relative print on a paper of L* 95.5, a* 0.5, b* -3
    # (`~/Desktop/ChromIQ-beta39-proof/k28-a/e8_three_ways.txt`): that raises
    # the sheet's noise from 0.18 to 1.0 and turns a drift that fails (1.51)
    # into a pass (1.33). So each aim is carried onto the paper
    # (`aims_on_the_paper`): the colour the print was asked to measure there.
    # That is ONE scale for every patch in every area, so it cannot make one
    # ninth read differently from another, which is what the old division
    # did; the noise returns to 0.17 and the drift fails again (1.47).
    #
    # WHERE THE WORDS JUDGE THE WITHIN-GAMUT FIGURES, SO DOES EVENNESS: a
    # colour the profile could never print is far from its aim wherever it
    # sits, so it is noise to a question about places, and the verdict above
    # already sets it aside. (Which patches are in gamut is read off the AIMS,
    # so it does not depend on the yardstick.)
    report["evenness"] = evenness_block(
        absolute_lab, evenness_ref if evenness_ref is not None else ref,
        data.sample_ids, rgb100,
        ref_ti2 if ref_ti2.is_file() else None, corner_ids,
        only_ids=in_gamut_ids)
    report["evenness"]["aims"] = ("on_the_paper" if evenness_ref is not None
                                  else "as_designed")

    # …and the control strip, which is a DECLARATION rather than a measurement:
    # it needs the chart file, not the device values, so it is written whether
    # or not the measurement carries device columns.
    #
    # #182 K37 (i) (Knut, 5823088098): ON A FROM PROFILE GAMUT CHART the
    # seven ink and black corner rungs of the strip are compared with the
    # profile's PREDICTION for their device value, the in-gamut corner, as
    # every other patch of such a chart is. The cube-corner table and its
    # graph keep the ideal values (§32.5, Knut's "no"). Without a profile to
    # ask, today's comparison stays and the block says so.
    strip_ref = ref
    corner_aims = None
    # written on EVERY report, so one saved before K37 (i) is worked out
    # again when the window reads it (ALWAYS_BUILT_BLOCKS, §6)
    report["strip_corner_aims"] = {"from": CORNER_AIMS_NOT_APPLICABLE}
    if ref_source == "colorimetric" and _cref is not None:
        _pred = profile_corner_predictions(_cref, ti3_path, argyll_bin)
        if _pred is not None:
            strip_ref = dict(ref)
            strip_ref.update(_pred[0])
            corner_aims = {"from": CORNER_AIMS_FROM_PROFILE,
                           "profile": _pred[1],
                           "ids": sorted(_pred[0])}
        else:
            corner_aims = {"from": CORNER_AIMS_IDEAL}
    report["control_strip"] = control_strip_block(
        lab, strip_ref, data.sample_ids,
        control_strip_declaration(ti3_path,
                                  ref_ti2 if ref_ti2.is_file() else None))
    if corner_aims is not None:
        _decl_ids = set()
        try:
            _decl = control_strip_declaration(
                ti3_path, ref_ti2 if ref_ti2.is_file() else None)
            _decl_ids = set((_decl or {}).get("ids") or ())
        except Exception:                              # noqa: BLE001
            pass
        _corners_in_strip = sorted(
            (set(_cref.get("corner_ids") or ())
             - set(paper_corner_ids(_cref))) & _decl_ids)
        if _corners_in_strip:
            corner_aims["in_strip"] = _corners_in_strip
            report["strip_corner_aims"] = corner_aims
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


#: **K23, THE TWO PARTS OF A DOCUMENT OF SEVERAL MEASUREMENTS.** Knut,
#: 2026-09-23 (#182, comments 5787117741 and 5787380408): a report of ONE
#: measurement lives in that measurement's own `reports/`; a report of several
#: dates of one profile run lives in `runN/verifications/reports/`; a report
#: across profile runs in `<project>/reports/`. And, accepted in the same
#: exchange, every dated verification keeps its own small verdict record in
#: its own folder, because the lock and the comparability of the dates are
#: built on it, and that record "is not a report, it is never listed or
#: counted".
#:
#: So a document of several measurements is written as:
#:
#: * one file whose block says ``"role": "document"``, in `document_home`;
#: * one file per measurement written, in that measurement's folder, whose
#:   block says ``"role": "record"``: the same full per-measurement report
#:   ChromIQ has always written, verdict and all, so every reader of a date's
#:   verdict (the trend, `_gather_runs`, recalculation, the delete rule) goes
#:   on finding it under the same `report_*.json` name.
#:
#: A block with NO role is what every file before K23 carries and what a
#: one-measurement document still carries: that file is the report and the
#: record at once. An older ChromIQ ignores the key, sees the records share
#: one id, and shows the document once, which is the downgrade we want.
#: **K31 (Knut, #182 5801677743): NO MORE RECORDS ARE WRITTEN.** *"Should a
#: report of several measurements stop writing verdict records altogether?"*
#: *"Agreed."* A report of several measurements is now ONE document file whose
#: list of measurements carries each one's verdict (`JUDGED_KEY`), and a date's
#: own verdict is its own report of one date. Records already on disk are
#: read-only history of the report they were written for: never listed or
#: counted (as before), shown only while that report is loaded, never the
#: date's own row, and never rewritten, moved or archived by anything.
#: Nothing on disk is deleted or rewritten for this.
ROLE_RECORD = "record"
ROLE_DOCUMENT = "document"
DOCUMENT_ROLES = (ROLE_RECORD, ROLE_DOCUMENT)


def document_role(report_or_block: "dict | None") -> str:
    """``"record"``, ``"document"`` or "" for a saved report or its block."""
    if not isinstance(report_or_block, dict):
        return ""
    block = report_or_block.get(DOCUMENT_BLOCK)
    if not isinstance(block, dict):
        block = report_or_block
    role = block.get("role")
    return role if isinstance(role, str) and role in DOCUMENT_ROLES else ""


def is_verdict_record(report_or_block: "dict | None") -> bool:
    """True for a measurement's verdict record of a several-measurement
    document (K23): kept, read for the verdict, never listed or counted."""
    return document_role(report_or_block) == ROLE_RECORD


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
                   updated: "list[str] | None" = None,
                   role: str = "") -> dict:
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
    # **WHICH PART OF A DOCUMENT THIS FILE IS (K23).** Left out for a document
    # of one measurement, which is one file that is both the report and that
    # measurement's verdict record, exactly as every file before K23. A
    # document of several measurements is a DOCUMENT FILE in its own folder
    # (`document_home`) plus a VERDICT RECORD in each measurement's folder;
    # see `ROLE_RECORD`.
    if role in DOCUMENT_ROLES:
        report[DOCUMENT_BLOCK]["role"] = role
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
    role = d.get("role")
    if isinstance(role, str) and role in DOCUMENT_ROLES:
        out["role"] = role
    else:
        out.pop("role", None)
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


def _is_dated(d: Path) -> bool:
    from core.file_manager import VERIFICATIONS_DIRNAME
    return d.parent.name == VERIFICATIONS_DIRNAME


#: The folder a project's calibration lives in (`core.file_manager.
#: Calibration.dir`), by name.
CAL_DIRNAME = "cal"


def _is_cal(d: Path) -> bool:
    """Whether *d* is a project's calibration folder, BY NAME (#182 beta 39).

    Name only, like the ``runs/`` test beside it, because it is asked of the
    folders a saved report RECORDS, and a project that has moved (every
    downloaded demo pack) is no longer where they say. What a window lists
    and counts asks the disk as well (`measurement_dir_kind`)."""
    return d.name == CAL_DIRNAME


def _run_folder_of(d: Path) -> Path:
    """The profile run a measurement folder belongs to: the run itself, or
    the run above a dated verification folder."""
    return d.parent.parent if _is_dated(d) else d


def _project_folder_of(d: Path) -> "Path | None":
    """The project a measurement folder belongs to, or None outside a
    ``<project>/runs/runN`` layout. A project's ``cal/`` folder belongs to
    the project above it (#182 beta 39)."""
    if _is_cal(d):
        return d.parent
    run = _run_folder_of(d)
    return run.parent.parent if run.parent.name == "runs" else None


def is_calibration_dir(d: "str | Path") -> bool:
    """Whether *d* is a ChromIQ project's calibration folder ON DISK: named
    ``cal`` with the project's manifest beside it. A user's own folder that
    happens to be called ``cal`` is not one (#182 beta 39)."""
    d = Path(str(d))
    if not str(d) or not _is_cal(d):
        return False
    try:
        return (d.parent / "project.json").is_file()
    except OSError:
        return False


def measurement_dir_kind(d: "str | Path") -> str:
    """The kind a measurement FOLDER holds: a dated verification folder is
    ``verification``; a project's ``cal/`` folder is ``calibration`` (#182
    beta 39, Knut 5794078008); anything else (a run's own folder, a loose
    file's folder) is ``profiling``."""
    d = Path(str(d))
    if is_calibration_dir(d):
        return KIND_CALIBRATION
    return KIND_VERIFICATION if _is_dated(d) else KIND_PROFILING


def project_relative(d: "str | Path") -> str:
    """A measurement folder named from the project down
    (``runs/run1/verifications/<date>``), or the whole path outside a
    project layout.

    **A PROJECT MOVES.** Every downloaded demo pack has, and so has every
    project restored from a backup; a document records its measurements by
    ABSOLUTE folder (`document_measurement_key`), so a comparison on the whole
    path finds nothing after a move. Named from `runs/` down, it finds the
    same folders wherever the project now lives (K23, and B8-810 R3A-2).
    """
    # A PROJECT'S CALIBRATION is ``cal`` from the project down (#182 beta
    # 39), as a run is ``runs/run1``.
    if _is_cal(Path(str(d))):
        return CAL_DIRNAME
    parts = Path(str(d)).parts
    for i in range(len(parts) - 2, -1, -1):
        if parts[i] == "runs":
            return "/".join(parts[i:])
    return str(Path(str(d)))


def project_home_of(path: "str | Path") -> "Path | None":
    """The project folder *path* is inside: the nearest folder above it (or
    itself) that holds a ``project.json``; None when there is none.

    Asked of the disk, so it answers for a report FILE as well as for a
    measurement folder, wherever the project now lives (#182 beta 38, F2).
    """
    if not str(path):
        return None
    p = Path(str(path))
    for cand in [p, *p.parents][:8]:
        try:
            if (cand / "project.json").is_file():
                return cand
        except OSError:
            return None
    return None


_NAMES_CACHE: "dict[str, tuple[int, frozenset]]" = {}


def names_of_project(project: "str | Path") -> "frozenset[str]":
    """Every name *project* is known by, NFC: its folder's name, the name its
    files carry and every name it had before a rename (``former_names``,
    written by `Project.rename`). #182 beta 38, F2.

    A saved report records its measurements' folders under the name the
    project had when the report was written, so after a rename that name is
    this project's old one; these are the names that are THIS project."""
    from core.file_manager import nfc
    p = Path(str(project))
    names = {nfc(p.name)}
    mp = p / "project.json"
    try:
        stamp = mp.stat().st_mtime_ns
    except OSError:
        return frozenset(names)
    hit = _NAMES_CACHE.get(str(mp))
    if hit is None or hit[0] != stamp:
        try:
            data = json.loads(mp.read_text(encoding="utf-8"))
        except Exception:                            # noqa: BLE001
            data = {}
        got = set()
        if isinstance(data, dict):
            if isinstance(data.get("target_name"), str):
                got.add(nfc(data["target_name"]))
            for n in data.get("former_names") or []:
                if isinstance(n, str):
                    got.add(nfc(n))
        hit = (stamp, frozenset(got))
        _NAMES_CACHE[str(mp)] = hit
    return frozenset(names | set(hit[1]))


def resolve_recorded_folder(d: "str | Path", homes, *,
                            one_project: bool = False,
                            must_exist: bool = True) -> "Path | None":
    """Where a measurement folder a saved report RECORDS is now, seen from
    the project(s) the report's own files live in (*homes*); None when it is
    this project's and not on disk here. #182 beta 38, F2.

    A report records its measurements by absolute folder, under the name the
    project had when it was written. After a Finder duplicate is renamed,
    that name is its ORIGINAL's, and the report window reached into the
    original beside it: the copy's window listed the original's
    measurements, and filed every one of the copy's reports under "Reports
    including multiple projects". In order:

    1. a home whose names (`names_of_project`: folder, files, former names)
       include the recorded project's name: the same folder in THAT home,
       or None when that home does not have it; never the recorded path,
       which for a renamed duplicate is the original's;
    2. a report naming ONE project (*one_project*) whose files live in one
       home: that home, because a report of one project is only ever filed
       inside that project (`document_home`); None when it is not there;
    3. only when the recorded folder no longer holds a project, or a
       home's original stands beside it (a copied pack, K25) (B8-955):
       a project of the recorded name beside a home (a report across
       projects names its other projects that way); 3b, the one project
       beside a home that answers to the name; 3c, the one project in the
       ChromIQ folder (top level or one level down) that answers to it;
    4. the recorded folder itself, for a project that is none of these.

    With *must_exist* a folder counts only when it is on disk. Never raises.
    """
    from core.file_manager import nfc
    d = Path(str(d))
    recorded = _project_folder_of(d)
    homes = [Path(str(h)) for h in (homes or []) if h]
    if recorded is None or not homes:
        return d
    rel = project_relative(d)
    if not (rel.startswith("runs/") or rel == CAL_DIRNAME):
        return d
    rname = nfc(recorded.name)

    def _ok(p: Path) -> bool:
        try:
            return (not must_exist) or p.is_dir()
        except OSError:
            return False
    ours = [h for h in homes if rname in names_of_project(h)]
    for h in ours:
        if _ok(h / rel):
            return h / rel
    if ours:
        return None
    if one_project and len(homes) == 1:
        return homes[0] / rel if _ok(homes[0] / rel) else None
    # **A RECORDED FOLDER THAT STILL HOLDS A PROJECT IS THAT PROJECT
    # (B8-926, B8-955).** Every step below looks for a NAMESAKE: a project
    # of the recorded name beside a home (3), one that answers to it (3b),
    # one elsewhere in the ChromIQ folder (3c). While the recorded folder
    # still holds a project.json, a namesake is another project of the same
    # name, and taking it filled the report window with that project's
    # dates. B8-926 guarded 3c only; a Finder copy beside the home ("Q
    # copy", or renamed to Q) still won through 3 and 3b. The rewrite side
    # (`core.report_refs.refers_here`) already refused such a reference.
    #
    # **UNLESS THE HOME WAS COPIED FROM BESIDE IT (K25).** A copied pack
    # (P, Q and reports/ copied together, the originals kept) records the
    # ORIGINAL Q, which is still there, and the copy's own Q beside the copy
    # of P is the one meant. That is told apart by the recorded folder's
    # neighbours: a project beside the recorded Q that answers to a home's
    # name, and is not that home, is the home's original, so the two were
    # together where the report was written and the home's neighbour is Q.
    try:
        still_there = (recorded / "project.json").is_file()
    except OSError:
        still_there = False
    if still_there and not _copied_from_beside(recorded, homes):
        return d
    for h in homes:
        beside = h.parent / recorded.name
        try:
            is_project = (beside / "project.json").is_file()
        except OSError:
            is_project = False
        if is_project and _ok(beside / rel):
            return beside / rel
    # 3b. **A PROJECT BESIDE A HOME THAT WAS CALLED THAT (challenge C, beta
    # 39, #2).** A rename keeps the old name in ``former_names``, and a
    # report across projects written before it (or one the rename could
    # not rewrite) still names the old folder. Looked up by the recorded
    # name alone, the renamed project was never found from the other side:
    # "1 of the 3", and an Update narrowed the report to what it found.
    # Only an UNAMBIGUOUS claim counts: two projects that both answer to
    # the name (a duplicate and its original, both renamed) are neither.
    claims = _projects_answering_to(rname, homes)
    if len(claims) == 1 and _ok(claims[0] / rel):
        return claims[0] / rel
    if claims:
        return d
    # 3c. **A PROJECT MOVED INTO ANOTHER FOLDER OF THE ChromIQ FOLDER
    # (re-challenge R1, beta 39, #6).** §24.4 lets projects live in
    # sub-folders of the ChromIQ folder, and a report across projects names
    # the other project where it WAS. Moved into ``Group/``, it was found
    # from neither side: the window loaded 1 of the 2 dates with no note,
    # and Generate said "Nothing was changed". The ChromIQ folder and its
    # sub-folders are searched for the ONE project that answers to the
    # recorded name (`names_of_project`); two that do are neither.
    #
    # Only when the recorded folder is gone (B8-926, and B8-955 above).
    found = _projects_in_the_chromiq_folder(rname, homes)
    if len(found) == 1 and _ok(found[0] / rel):
        return found[0] / rel
    return d


def _copied_from_beside(recorded: Path, homes) -> bool:
    """Whether a home's original stands beside *recorded*: a project folder
    in *recorded*'s parent that answers to one of the home's names
    (`names_of_project`) and is not the home itself (B8-955, K25). Never
    raises."""
    for h in homes:
        try:
            names = names_of_project(h)
        except Exception:                              # noqa: BLE001
            continue
        for n in names:
            twin = recorded.parent / n
            try:
                if (twin / "project.json").is_file() and not \
                        os.path.samefile(str(twin), str(h)):
                    return True
            except OSError:
                continue
    return False


def _projects_in_the_chromiq_folder(name: str, homes) -> "list[Path]":
    """The projects in the ChromIQ folder (`chromiq_folder`) and in its
    sub-folders, one level down, that answer to *name* (NFC), the *homes*
    excluded. A project's own folders are not searched. Never raises."""
    try:
        root = chromiq_folder()
    except Exception:                                  # noqa: BLE001
        return []
    skip = {os.path.realpath(str(h)) for h in homes or []}
    out: "list[Path]" = []

    def _is_project(c: Path) -> bool:
        try:
            return (c / "project.json").is_file()
        except OSError:
            return False

    def _kids(folder: Path) -> "list[Path]":
        try:
            return sorted(c for c in folder.iterdir()
                          if c.is_dir() and not c.name.startswith(".")
                          and c.name not in ("reports", "old"))
        except OSError:
            return []

    for c in _kids(root):
        cands = [c] if _is_project(c) else [g for g in _kids(c)
                                            if _is_project(g)]
        for g in cands:
            if os.path.realpath(str(g)) in skip:
                continue
            if name in names_of_project(g) and g not in out:
                out.append(g)
    return out


#: Why a measurement a saved report covers is not there any more
#: (`update_losses`). The words are `measurement_messages.report_gone_line`'s.
GONE_PROJECT = "project"        # no project of the recorded name can be found
GONE_RUN = "run_deleted"        # its profile run was deleted (bar Delete)
GONE_FOLDER = "folder"          # the project is there, the folder is not
GONE_FILE = "file"              # the folder is there, the measurement is not


def deleted_runs_of(doc: "dict | None") -> "list[tuple[str, str]]":
    """``[(project, run number)]`` of the profile runs a saved report covered
    that have since been deleted, in the report's own order (#182 A6).

    The bar's Delete turns such a reference into ``runs/runN.deleted``
    (`core.report_refs`), and N is the number the run had when the report
    was written. Empty for a report that names no deleted run. Never raises.
    """
    from core.report_refs import DELETED_RUN_SUFFIX
    out: "list[tuple[str, str]]" = []
    for m in ((doc or {}).get("measurements") or []):
        if not isinstance(m, dict):
            continue
        parts = list(Path(str(m.get("dir") or "")).parts)
        if "runs" not in parts:
            continue
        i = len(parts) - 1 - parts[::-1].index("runs")
        run = parts[i + 1] if i + 1 < len(parts) else ""
        if not run.endswith(DELETED_RUN_SUFFIX):
            continue
        num = run[:-len(DELETED_RUN_SUFFIX)]
        num = num[3:] if num.startswith("run") else num
        entry = (parts[i - 1] if i >= 1 else "", num)
        if entry not in out:
            out.append(entry)
    return out


def _gone_reason(d: str, name: str, homes, *, one_project: bool
                 ) -> "tuple[str, Path | None]":
    """``(reason, folder)`` for one recorded measurement: reason "" when its
    measurement file is on disk; *folder* where it is (or would be)."""
    from core.report_refs import DELETED_RUN_SUFFIX
    rel = project_relative(d)
    parts = rel.split("/")
    if len(parts) >= 2 and parts[0] == "runs" \
            and parts[1].endswith(DELETED_RUN_SUFFIX):
        return GONE_RUN, None
    folder = resolve_recorded_folder(d, homes, one_project=one_project)
    if folder is None:
        return GONE_FOLDER, None
    try:
        there = folder.is_dir()
    except OSError:
        there = False
    if not there:
        project = _project_folder_of(Path(str(folder)))
        try:
            known = project is not None and (project / "project.json").is_file()
        except OSError:
            known = False
        return (GONE_FOLDER if known else GONE_PROJECT), None
    if name:
        ti3 = folder / name
        if not ti3.is_file():
            alts = {renamed_file_name(name, d, folder),
                    current_chart_name(name, folder)} - {None, "", name}
            if not any((folder / a).is_file() for a in alts):
                return GONE_FILE, folder
    return "", folder


def recorded_dir_kind(d: "str | Path") -> str:
    """The kind of measurement a folder a saved report RECORDS holds, by the
    folder's name alone (the project may have moved since): ``cal`` is a
    calibration, a dated folder under ``verifications`` a verification, and
    anything else a profiling sheet."""
    p = Path(str(d))
    if _is_cal(p):
        return KIND_CALIBRATION
    return KIND_VERIFICATION if _is_dated(p) else KIND_PROFILING


def update_may_cover(recorded, members) -> "list[dict]":
    """The *members* an UPDATE of a saved report may cover: those of a kind
    the report records (`recorded_dir_kind`), in order (second check R3,
    beta 39, B8-925).

    An Update rewrites a report about ITS measurements. With every
    verification of a report gone, the window listed the run's two
    profiling sheets ticked under it, and "Update without them" rewrote the
    verification report (same id, "All dates") to cover sheets it had never
    covered. A report of one kind never takes another kind's measurements;
    a report that records none (written before the document record) takes
    what the press covers, as before. Never raises."""
    kinds = {recorded_dir_kind(str(m.get("dir") or ""))
             for m in (recorded or [])
             if isinstance(m, dict) and m.get("dir")}
    if not kinds:
        return list(members or [])
    return [m for m in (members or [])
            if recorded_dir_kind(str(m.get("dir") or "")) in kinds]


def update_losses(recorded, members, homes) -> "list[dict]":
    """Every measurement an UPDATE of a saved report would lose without the
    user choosing it (challenge C, beta 39, #1 and #11), oldest first.

    *recorded* is the report's own list (``document.measurements``),
    *members* what the press would write (``{"dir", "created", "ti3",
    "key"}`` of each measurement it covers), *homes* the project folders the
    report's files are in (`resolve_recorded_folder`).

    * A recorded measurement the press does NOT cover and that cannot be
      found on disk: the report would be narrowed to what this side found.
      Measured: an Update from the side that could not find a renamed
      project archived the whole report and rewrote it about one date.
    * A measurement the press DOES cover whose measurement file is gone
      (the window shows it from its saved record): §13.11 leaves such a
      folder out, and the Update must say so before it rewrites.

    A recorded measurement that IS found and simply is not ticked is not
    here: leaving that out is what the user chose. Each entry is the
    recorded (or member) dict with ``reason`` (a ``GONE_*``) and, for a
    member, ``key``, the identity the press would leave out. Never raises.
    """
    homes = [Path(str(h)) for h in (homes or []) if h]
    dirs = [str(m.get("dir") or "") for m in (recorded or [])
            if isinstance(m, dict)]
    one = len({measurement_place(d)[0] for d in dirs if d}) <= 1

    def _ident(d: str, created: str) -> tuple:
        from core.file_manager import nfc
        project = _project_folder_of(Path(str(d)))
        pname = nfc(project.name) if project is not None else ""
        return (pname, project_relative(d), str(created or "")[:19])

    covered: "set[tuple]" = set()
    out: "list[dict]" = []
    for m in members or []:
        d = str(m.get("dir") or "")
        if not d:
            continue
        covered.add(_ident(d, m.get("created")))
        try:
            reason, _f = _gone_reason(d, str(m.get("ti3") or ""), [],
                                      one_project=True)
        except Exception:                              # noqa: BLE001
            reason = ""
        if reason:
            out.append({**m, "reason": reason})
    for m in recorded or []:
        if not isinstance(m, dict):
            continue
        d = str(m.get("dir") or "")
        if not d:
            continue
        try:
            reason, folder = _gone_reason(d, str(m.get("ti3") or ""), homes,
                                          one_project=one)
        except Exception:                              # noqa: BLE001
            continue
        if folder is not None and _ident(str(folder), m.get("created")) \
                in covered:
            continue
        if _ident(d, m.get("created")) in covered:
            continue
        if reason:
            out.append({**{k: v for k, v in m.items() if k != "key"},
                        "reason": reason})
    out.sort(key=lambda e: str(e.get("created") or ""))
    return out


def _projects_answering_to(name: str, homes) -> "list[Path]":
    """The projects beside any of *homes* (not the homes themselves) whose
    names (`names_of_project`) include *name*, NFC. Never raises."""
    out: "list[Path]" = []
    seen: "set[str]" = set()
    for h in homes or []:
        parent = Path(str(h)).parent
        if str(parent) in seen:
            continue
        seen.add(str(parent))
        try:
            kids = sorted(parent.iterdir())
        except OSError:
            continue
        for c in kids:
            try:
                if not (c / "project.json").is_file():
                    continue
            except OSError:
                continue
            if any(str(c) == str(Path(str(x))) for x in homes):
                continue
            if name in names_of_project(c) and c not in out:
                out.append(c)
    return out


def current_chart_name(chart: str, origin_dir: "str | Path | None") -> str:
    """*chart*, a name a saved report recorded, as the project whose folder
    *origin_dir* is inside is called NOW (challenge C, beta 39, #3).

    A report written before a rename names the chart by the project's old
    name (``X-verify``), and the Report Scope went on printing it under the
    renamed project. When the name starts with one of the project's former
    names (`names_of_project`) followed by one of ChromIQ's own separators,
    that part becomes the folder's name; anything else is left alone."""
    from core.file_manager import nfc
    name = str(chart or "")
    if not name or not origin_dir:
        return name
    home = project_home_of(origin_dir)
    if home is None:
        return name
    now = nfc(home.name)
    n = nfc(name)
    if n == now or n.startswith(now) and n[len(now):len(now) + 1] in "-._":
        return name
    for old in sorted(names_of_project(home) - {now}, key=len, reverse=True):
        if n == old:
            return home.name
        if n.startswith(old) and n[len(old):len(old) + 1] in ("-", ".", "_"):
            return home.name + n[len(old):]
    return name


def renamed_file_name(name: str, recorded_dir: "str | Path",
                      folder: "str | Path") -> "str | None":
    """*name*, a file a report recorded in *recorded_dir*, as it is called in
    *folder* after its project was renamed; None when the name does not start
    with the recorded project's name or the folder is in no project.

    A rename gives the project's files its new name (`Project.rename`), so a
    measurement recorded as ``X-verify.ti3`` is ``X-copy-verify.ti3`` in the
    renamed project (#182 beta 38, F2)."""
    from core.file_manager import nfc
    recorded = _project_folder_of(Path(str(recorded_dir)))
    home = project_home_of(folder)
    if recorded is None or home is None:
        return None
    old, n = nfc(recorded.name), nfc(str(name))
    if not n.startswith(old) or nfc(home.name) == old:
        return None
    return home.name + n[len(old):]


def relative_measurement_key(key: str) -> str:
    """`document_measurement_key` with its folder made `project_relative`."""
    head, sep, tail = str(key).partition("|")
    return project_relative(head) + sep + tail if sep else str(key)


def chromiq_folder() -> Path:
    """The ChromIQ folder: Preferences' output folder, else the default
    (`FileManager.root_dir`'s rule, read through the sandboxable store).
    Where a report across projects that are not side by side lives (K30)."""
    from core.platform_paths import default_output_root
    try:
        from core.settings import AppSettings
        custom = str(AppSettings().get("custom_output_path", "") or "")
    except Exception:                                    # noqa: BLE001
        custom = ""
    return Path(custom) if custom else default_output_root()


def document_home(member_dirs, chromiq_root=None) -> "Path | None":
    """The ``reports`` folder a document covering *member_dirs* lives in (K23).

    Knut, 2026-09-23: *"For single measurements: …/runN/verifications/
    <date_time>/reports/. For multiple measurements within same measurement
    set (within same profile run): …/runN/verifications/reports/. For
    multiple measurements across different measurement sets of different
    profile runs: …/printer_profile_project_name/reports/"*, and for a
    profiling sheet *"…/runN/reports/"* or the project's.

    ======================================  ================================
    the document covers                     it lives in
    ======================================  ================================
    one folder                              ``<that folder>/reports``
    several dates of ONE profile run        ``<run>/verifications/reports``
    anything across profile runs            ``<project>/reports``
    projects side by side                   ``<their folder>/reports``
    projects anywhere else (K30)            ``<ChromIQ folder>/reports``
    ======================================  ================================

    Outside a project layout (loose files, which have no run to save into)
    it answers with the folders' common ancestor, so it never raises. None
    for an empty list. Nothing is created here.
    """
    import os
    from core.file_manager import REPORTS_DIRNAME, VERIFICATIONS_DIRNAME
    dirs: "list[Path]" = []
    seen: "set[str]" = set()
    for d in member_dirs or []:
        if not str(d):
            continue
        d = Path(str(d))
        if str(d) not in seen:
            seen.add(str(d))
            dirs.append(d)
    if not dirs:
        return None
    if len(dirs) == 1:
        return dirs[0] / REPORTS_DIRNAME
    runs = {str(_run_folder_of(d)) for d in dirs}
    if len(runs) == 1 and all(_is_dated(d) for d in dirs):
        return _run_folder_of(dirs[0]) / VERIFICATIONS_DIRNAME / REPORTS_DIRNAME
    projects = {str(_project_folder_of(d)) for d in dirs}
    project = _project_folder_of(dirs[0])
    if len(projects) == 1 and project is not None:
        return project / REPORTS_DIRNAME
    # **PROJECTS THAT ARE NOT SIDE BY SIDE SHARE THE ChromIQ FOLDER'S
    # reports/ (#182 K30, Knut 5798461562).** *"I propose that the ChromIQ
    # default folder is always used, in this situation, no matter if one of
    # the projects, or both, are kept is sub folders of ChromIQ default
    # folder."* Side by side (one parent folder) they keep that folder's
    # `reports/`, as K25 built it; anywhere else there is no common folder
    # that is anybody's, so the report goes to the ChromIQ folder.
    folders = [_project_folder_of(d) for d in dirs]
    if all(f is not None for f in folders):
        parents = {str(f.parent) for f in folders}
        if len(parents) == 1:
            return folders[0].parent / REPORTS_DIRNAME
        return Path(str(chromiq_root or chromiq_folder())) / REPORTS_DIRNAME
    try:
        return Path(os.path.commonpath([str(d) for d in dirs])) / REPORTS_DIRNAME
    except ValueError:
        return dirs[0] / REPORTS_DIRNAME


def measurement_place(d: "str | Path") -> "tuple[str, str]":
    """``(project, run)`` a measurement folder belongs to, as folder NAMES
    (K25, the grouping of "Report shown").

    By name, not by path, because a project MOVES (every downloaded demo
    pack has) and a document records the folders it covered where they were
    when it was written. A folder outside a ``<project>/runs/runN`` layout
    (a loose file's folder) is its own "run", and the folder above it its
    "project", so it never raises and never invents a run number.
    """
    d = Path(str(d))
    run = _run_folder_of(d)
    project = _project_folder_of(d)
    if project is None:
        return (run.parent.name, run.name)
    return (project.name, run.name)


def shared_report_folders(measurement_dirs) -> "list[Path]":
    """The folders where a document of SEVERAL of these measurements may
    live: each dated verification's ``verifications/reports``, each
    project's ``reports``, and the folder `document_home` files a report
    across PROJECTS in. A measurement's own ``reports`` is not here; it is
    read as it always was.

    **THE LAST ONE WAS MISSING (K25).** A report covering two projects is
    filed in the projects' common folder (`document_home`: for two projects
    in one output folder, ``<output>/reports``), and nothing read that
    folder, so such a report was written, never listed and never counted.
    It is now read for every project's parent, and for the common folder of
    all the projects given when they are not side by side.
    """
    import os
    from core.file_manager import REPORTS_DIRNAME, VERIFICATIONS_DIRNAME
    out: "list[Path]" = []
    seen: "set[str]" = set()
    projects: "list[Path]" = []
    for d in measurement_dirs or []:
        d = Path(str(d))
        cands = []
        if _is_dated(d):
            cands.append(d.parent.parent / VERIFICATIONS_DIRNAME
                         / REPORTS_DIRNAME)
        project = _project_folder_of(d)
        if project is not None:
            # A CALIBRATION'S REPORTS ARE NEVER IN THE PROJECT'S OWN
            # `reports/` (#182 beta 39, Knut 5794078008): one calibration's
            # live in `cal/reports/`, several projects' in the folder across
            # projects below. The project's folder holds the RUNS' reports.
            if not _is_cal(d):
                cands.append(project / REPORTS_DIRNAME)
            if str(project) not in {str(p) for p in projects}:
                projects.append(project)
        for c in cands:
            if str(c) not in seen:
                seen.add(str(c))
                out.append(c)
    across: "list[Path]" = [p.parent / REPORTS_DIRNAME for p in projects]
    # AND THE ChromIQ FOLDER'S (K30), where a report across projects that are
    # not side by side lives, wherever the window's own project is.
    if projects:
        across.append(chromiq_folder() / REPORTS_DIRNAME)
    if len(projects) > 1:
        try:
            across.append(Path(os.path.commonpath(
                [str(p) for p in projects])) / REPORTS_DIRNAME)
        except ValueError:
            pass
    for c in across:
        if str(c) not in seen:
            seen.add(str(c))
            out.append(c)
    return out


def _coverage_key(d: "str | Path") -> str:
    """What `shared_documents` compares a recorded folder by:
    `project_relative`, and for a CALIBRATION the project's name with it
    (#182 beta 39). Every project has a ``cal``, so ``cal`` alone would offer
    a report across P and Q in R's window as well."""
    d = Path(str(d))
    if _is_cal(d):
        from core.file_manager import nfc
        return nfc(d.parent.name) + "/" + CAL_DIRNAME
    return project_relative(d)


def shared_documents(measurement_dirs) -> "list[tuple[Path, dict]]":
    """``[(file, block)]`` for every document FILE in the shared folders
    (`shared_report_folders`) that covers at least one of *measurement_dirs*.

    **WHAT A DOCUMENT COVERS IS WHAT IT RECORDS**, compared from the project
    down (`project_relative`) so a moved project still finds its documents.
    A file there that is not a report object, carries no document block or
    is a verdict record is not a document of several measurements: ChromIQ
    never wrote one, and this skips it rather than guess what it covers.
    Oldest first by file name. Never raises.
    """
    here = {_coverage_key(d) for d in (measurement_dirs or []) if str(d)}
    # **ACROSS PROJECTS, THE PROJECT IS COMPARED TOO (#182 beta 39, G7).**
    # From `runs/` down alone, a report of P/run1 and Q/run1 in the folder
    # across projects also "covered" R/run1, because every project has a
    # `runs/run1`, and R's window listed and counted it. The calibration
    # matching already carries the project (`_coverage_key`); a run folder
    # does now as well, but ONLY for a document found outside every project:
    # a document inside a project can only be that project's, and comparing
    # its names there would lose the reports of a project renamed by hand.
    # The window's side is every name its project has had
    # (`names_of_project`), so a renamed project still finds its reports.
    here_named = _named_coverage_keys(measurement_dirs)
    out: "list[tuple[Path, dict]]" = []
    for folder in shared_report_folders(measurement_dirs):
        outside = project_home_of(folder) is None
        try:
            paths = (sorted(folder.glob("report_*.json"))
                     if folder.is_dir() else [])
        except OSError:
            continue
        for path in paths:
            try:
                rep = json.loads(read_text(path))
            except Exception:                    # noqa: BLE001
                continue
            block = recorded_document(report_object(rep))
            if block is None or is_verdict_record(block):
                continue
            if outside:
                covers = {_named_coverage_key(m.get("dir") or "")
                          for m in block.get("measurements") or []
                          if m.get("dir")}
                if covers & here_named:
                    out.append((path, block))
                continue
            covers = {_coverage_key(m.get("dir") or "")
                      for m in block.get("measurements") or []
                      if m.get("dir")}
            if covers & here:
                out.append((path, block))
    return out


def _named_coverage_key(d: "str | Path") -> str:
    """A recorded folder as ``<project name>/<runs/... or cal>`` (NFC), or
    `project_relative` alone outside a project layout (#182 beta 39, G7)."""
    from core.file_manager import nfc
    d = Path(str(d))
    project = _project_folder_of(d)
    if project is None:
        return project_relative(d)
    return nfc(project.name) + "/" + project_relative(d)


def _named_coverage_keys(measurement_dirs) -> "set[str]":
    """Every `_named_coverage_key` the window's own folders answer to: one
    per name their project has had (`names_of_project`)."""
    from core.file_manager import nfc
    out: "set[str]" = set()
    for d in measurement_dirs or []:
        if not str(d):
            continue
        d = Path(str(d))
        project = _project_folder_of(d)
        if project is None:
            out.add(project_relative(d))
            continue
        rel = project_relative(d)
        for name in names_of_project(project) | {nfc(project.name)}:
            out.add(nfc(name) + "/" + rel)
    return out


def document_spans_places(member_dirs) -> bool:
    """Whether a document of *member_dirs* spans more than one PLACE: more
    than one profile run, or calibrations of more than one project (#182
    beta 39, G7). Several dates of one run are one place (K23)."""
    places = {str(_run_folder_of(Path(str(d))))
              for d in (member_dirs or []) if str(d)}
    return len(places) > 1


#: Why a document across places cannot be written (G7), or "" when it can.
ACROSS_OK = ""
ACROSS_OUTSIDE = "outside"


def across_places_refusal(member_dirs) -> str:
    """"" when a document across places may be written, else a reason code.

    Knut names ONE folder for a report across projects, *"the <ChromIQ
    default folder>/reports/"* (5794078008), so every measurement must be in
    a ChromIQ project on disk. Projects that are not side by side used to
    be refused as well; since K30 (Knut, 5798461562) their report lives in
    the ChromIQ folder's ``reports/`` (`document_home`).
    """
    projects: "set[str]" = set()
    parents: "set[str]" = set()
    for d in member_dirs or []:
        if not str(d):
            continue
        project = _project_folder_of(Path(str(d)))
        try:
            ok = project is not None and (project / "project.json").is_file()
        except OSError:
            ok = False
        if not ok:
            return ACROSS_OUTSIDE
        projects.add(str(project))
        parents.add(str(project.parent))
    # PROJECTS IN TWO FOLDERS ARE NO LONGER REFUSED (#182 K30): their report
    # lives in the ChromIQ folder's `reports/` (`document_home`).
    return ACROSS_OK


#: The key, inside one measurement entry of a document FILE across places,
#: that carries that measurement's verdict against the document's own set
#: (G7): ``{"pass_thresholds", "compliance", "verdict"}``, as `stamp_verdict`
#: writes them onto a report.
JUDGED_KEY = "judged"


#: What a report of several dates records, per measurement, of HOW its
#: colours were judged, beside the verdict (challenge 5 of beta 42, M1,
#: B8-1091): the yardstick, and the rule blocks that decide it. A document
#: that is opened again is a record, and its notes must be the ones that
#: were true when its words were written, not a later version's.
JUDGED_EXPLANATION_KEYS: "tuple[str, ...]" = (
    "yardstick", "yardstick_no_paper", "paper_patch", "paper_white_used",
    "strip_corner_aims")


def judged_block(report: dict) -> dict:
    """The three keys `stamp_verdict` wrote on *report*, as a `JUDGED_KEY`
    value, with how the colours were judged (`JUDGED_EXPLANATION_KEYS`)."""
    return {k: report[k] for k in ("pass_thresholds", "compliance", "verdict")
            + JUDGED_EXPLANATION_KEYS if k in report}


def recorded_judgement(block: "dict | None", key: str,
                       origin_dir: "str | Path") -> "dict | None":
    """The verdict a document across places recorded for one measurement
    (*key*, `document_measurement_key`), or None (G7).

    Matched by the exact key first, then, for a project that has moved, by
    its project's name and the key from ``runs/`` (or ``cal``) down. A value
    that is not the shape this build writes is not a verdict (R27-F2): None.
    """
    if not isinstance(block, dict):
        return None
    ms = [m for m in (block.get("measurements") or []) if isinstance(m, dict)]

    def _ok(m):
        j = m.get(JUDGED_KEY)
        if (isinstance(j, dict) and isinstance(j.get("verdict"), dict)
                and isinstance(j["verdict"].get("rows"), list)
                and isinstance(j.get("compliance"), dict)):
            return j
        return None
    for m in ms:
        if str(m.get("key") or "") == str(key):
            return _ok(m)
    want = (_named_coverage_key(origin_dir), relative_measurement_key(key))
    hits = [m for m in ms
            if (_named_coverage_key(m.get("dir") or ""),
                relative_measurement_key(str(m.get("key") or ""))) == want]
    return _ok(hits[0]) if len(hits) == 1 else None


def document_file(*, doc_id: str, created: str, type_id: str,
                  compliance: "dict | None", detail: bool,
                  measurements: "list[dict]", scope: str = "",
                  updated: "list[str] | None" = None) -> dict:
    """The DOCUMENT FILE of a document of several measurements (K23).

    It carries what the document is (its block, `stamp_document`, with
    ``role: document``) and the three top-level keys a reader of any report
    file asks first, and NO measurement data: each measurement's numbers are
    read from its own folder, and since G7 (across places) and K31
    (everywhere) each measurement's VERDICT in this report is in the block's
    list of measurements (`JUDGED_KEY`). No verdict record is written.
    """
    body = {"schema": REPORT_SCHEMA, "created": str(created),
            "report_type": str(type_id or ""),
            "compliance": dict(compliance) if isinstance(compliance, dict)
            else None}
    return stamp_document(body, doc_id=doc_id, created=created,
                          type_id=type_id, compliance=compliance,
                          detail=detail, measurements=measurements,
                          scope=scope, updated=updated, role=ROLE_DOCUMENT)


def generated_report_types(run, kind: "str | None" = None,
                           default_type: str = "",
                           measurement_dirs=None) -> "dict[str, int]":
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

    Never raises: a run whose folder cannot be read has produced nothing this
    can promise.

    **AND ONLY WHAT THE RUN TYPE CAN HAVE (K19).** Knut, 2026-09-23, on a
    Verification window: *"Already generated for this run: … Printing record
    (not graded) (2)"* over a pulldown holding no Printing record, because
    this counted the run's OWN folder, where its profiling reports live, as
    well as the dated verifications. *"It has been specified that the
    counting of reports when in run type verification shall only count
    reports that can exist as report types for a verification run. Also, when
    run type is profiling, then only reports that are of type 'Printing
    record' shall be counted."* So *kind* chooses the folders (a profiling
    sheet's reports live in the run's folder, a verification's in its dated
    folders) and the types (`report_types_for_kind`); None keeps both, for a
    caller with no run type.

    A report that records no type is counted as what it renders as for its
    folder's kind (`report_type_default_for`, the rule the list's label uses,
    round 3A R3A-3), not as today's full report.
    """
    out: "dict[str, int]" = {}
    from workflow.run_compliance import report_type_default_for
    if measurement_dirs is not None:
        # **THE FOLDERS OF THE MEASUREMENTS IN THE LIST (K23).** Knut: the
        # reports counted *"must look in the folders that are relevant for the
        # measurements added in the 'Included measurements..' list"*. The
        # window hands them over; the kind still decides which of them count.
        dirs = []
        for d in measurement_dirs:
            if not str(d):
                continue
            dk = measurement_dir_kind(d)
            if kind is None or dk == kind:
                dirs.append((Path(str(d)), dk))
    else:
        if run is None:
            return out
        try:
            verifs = [v.dir for v in run.verifications() if v.exists()]
        except Exception as exc:                     # noqa: BLE001
            log.warning("could not list the reports of a run: %s", exc)
            return out
        if kind == KIND_PROFILING:
            dirs = [(run.dir, KIND_PROFILING)]
        elif kind == KIND_VERIFICATION:
            dirs = [(d, KIND_VERIFICATION) for d in verifs]
        else:
            dirs = ([(run.dir, KIND_PROFILING)]
                    + [(d, KIND_VERIFICATION) for d in verifs])
    allowed = set(report_types_for_kind(kind))
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
    for d, dir_kind in dirs:
        for path in list_reports(d):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            block = recorded_document(doc)
            # **A VERDICT RECORD IS NOT A REPORT (K23).** It is one date's
            # recorded result of a document of several measurements, and that
            # document is counted once, from its own folder, below.
            if is_verdict_record(block):
                continue
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
                tid = str(block.get("type") or "") or recorded_report_type(doc)
            else:
                tid = recorded_report_type(doc)
            if not tid:
                tid = report_type_default_for(run, default_type, dir_kind)
            if tid not in allowed:
                continue
            out[tid] = out.get(tid, 0) + 1
    # **AND THE DOCUMENTS OF SEVERAL MEASUREMENTS, WHERE THEY LIVE (K23)**:
    # `runN/verifications/reports/` and `<project>/reports/`, each counted
    # once, and only when it covers one of these measurements.
    for _path, block in shared_documents([d for d, _k in dirs]):
        doc_id = str(block.get("id") or "")
        if doc_id in seen:
            continue
        seen.add(doc_id)
        tid = str(block.get("type") or "")
        if not tid or tid not in allowed:
            continue
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


#: The rows that get a trend tab of their own (#182 K20/K21, Knut
#: 5787117741 and 5787380408). Grouped in the dialog, at most two per tab.
#:
#: **EVERY ROW A LIMIT SET CAN LIMIT AND CHROMIQ CAN MEASURE (K47, Knut #182
#: 5840152058).** Knut: every data line with a threshold gets its dotted line
#: and its sentence. Until K47 four such rows had no graph at all, although
#: the ISO and Custom sets limit them: the control strip's maximum (ISO
#: 12647-7 judges it, the graph plotted only the average and the 95th
#: percentile), the two solid-colour rows and the two selected-patch
#: averages. `tests/test_k47_every_limited_row_has_a_graph.py` holds this
#: tuple to every computable row a set limits.
TREND_ROW_IDS: "tuple[str, ...]" = (
    "substrate_de00_max",
    "solids_de00_max", "cmy_solids_dhab_max",
    "grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max",
    "ramps_30_70_dl_max",
    "control_strip_de00_avg", "control_strip_de00_p95",
    "control_strip_de00_max",
    "outer_gamut_226_de00_avg", "surface_gamut_de00_avg",
    "repeat_patches_de00_max", "repeat_measurement_de00_max",
    "uniformity_sd", "uniformity_de00_max_from_mean",
)


def _trend_row_values(report: dict) -> "tuple[dict, dict]":
    """``({row_id: value}, {row_id: noise_p95})`` for :data:`TREND_ROW_IDS`.

    Only rows with a number. The noise travels with an evenness value because
    whether that value may be judged depends on the limit (`evenness_withheld`),
    which the series does not know."""
    try:
        cells = row_values(report)
    except Exception:  # noqa: BLE001 — a trend point must never take the window down
        return {}, {}
    vals, noise = {}, {}
    for rid in TREND_ROW_IDS:
        cell = cells.get(rid) or {}
        if cell.get("value") is None:
            continue
        vals[rid] = float(cell["value"])
        if cell.get("noise_p95") is not None:
            noise[rid] = float(cell["noise_p95"])
    return vals, noise


def report_trend(reports: "list[dict]") -> "list[dict]":
    """A time series for the trend chart from a list of report dicts (#40).

    One point per report that carries at least one plottable metric, in the
    input order (already oldest-first from :func:`list_project_reports`):
    ``{"created", "chart", "mean", "max", "p95", "white_L", "black_L"}`` —
    metric keys absent when the report lacks them (no design reference)."""
    series: list[dict] = []
    for r in reports:
        pt: dict = {"created": r.get("created"), "chart": r.get("chart")}
        # **THE FIGURES THE VERDICT JUDGED (K26, Knut 5792484060, Q4: "Yes,
        # use the within-gamut figures").** A sheet whose colours were split
        # by the profile's gamut is judged on its within-gamut figures
        # (`graded_de00`), and this plotted the all-patch ones against the
        # same Avg / Max lines: on one demo date the graph drew 1.36 where the
        # verdict had used 1.95. Asked of the one function the verdict asks,
        # so the two cannot part again; which population it was is recorded
        # so the graph can say so.
        de, source = graded_de00(r)
        if de:
            pt["de00_population"] = ("in_gamut"
                                     if source == VERDICT_SOURCE_IN_GAMUT
                                     else "all")
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
        # #182 K20/K21: the judged rows that have a trend tab of their own,
        # read through `row_values`, the one place a row's number comes from,
        # so the graph plots exactly what the results table judges.
        rows, noise = _trend_row_values(r)
        if rows:
            pt["rows"] = rows
        if noise:
            pt["rows_noise"] = noise
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
#: `built` says whether ChromIQ can produce that document today. All six can.
#: The two ISO types were once SHOWN greyed because their standards' values
#: could not be shipped (Knut, 2026-09-09: *"marked as not yet implemented
#: and a reason for it"*); the values ship since K33 (§23, §30.6), so the
#: only condition left is that they are LOADED, which `report_type_is_built`
#: asks. A type whose values are missing is still shown greyed and says why,
#: rather than hidden, which would say nothing at all.
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
    # **BUILT SINCE K33 (B8-994), AND OFFERED ONLY WHILE THEIR STANDARD'S
    # VALUES ARE THERE.** Knut, #182 5816565326: *"for run type
    # verification, the report type options often do not allow selecting
    # the "Validation print check" or "Contract proof check". These should
    # be available now."* The values ship (§23), so the paywall reason is
    # gone. What such a report IS: the Full colour check document, headed
    # with its own name; which set it is judged against is the "Judged
    # against" pulldown's, as for every type. `report_type_is_built` adds
    # the one condition this flag cannot: the set's values must be loaded.
    (REPORT_TYPE_ISO_8, "Validation print check (ISO 12647-8)",
     "For a validation print, to be judged against the values of "
     "ISO 12647-8.", True),
    # **NOT "A PRINTING CONDITION YOU SUPPLY" (challenge 3 of beta 42,
    # B8-1031).** The values ship; a licence holder may lay a file of their
    # own over them, and both are still "the values of ISO 12647-x". Neither
    # line claims a print conforms: ChromIQ judges, it does not certify.
    (REPORT_TYPE_ISO_7, "Contract proof check (ISO 12647-7)",
     "For a contract proof, to be judged against the values of "
     "ISO 12647-7, the stricter of the two.", True),
)

#: Which read-only limit set an ISO report type is named after. Such a type
#: can be produced only while that set holds values (`report_type_is_built`).
REPORT_TYPE_ISO_SET: "dict[str, str]" = {
    REPORT_TYPE_ISO_8: "iso_12647_8",
    REPORT_TYPE_ISO_7: "iso_12647_7",
}


#: **K36-1 (Knut, #182 5820871320): AN ISO REPORT TYPE IS JUDGED AGAINST
#: AN ISO SET.** *"I think (a), but a user should only be allowed to select
#: between the 4 ISO options in judged against, and the other options are
#: greyed while having selected Validation print check or Contract proof
#: check. Then the user still has room for playing around with limit
#: values."* These are the four. Choosing an ISO type moves "Judged against"
#: to its own standard's set (`REPORT_TYPE_ISO_SET`); the user may then move
#: among the four, and every other set is shown greyed.
ISO_JUDGED_AGAINST: "tuple[str, ...]" = (
    "iso_12647_7", "iso_12647_8", "custom_iso_12647_7", "custom_iso_12647_8",
)


def set_allowed_for_type(type_id: str, set_id: str) -> bool:
    """May a NEW report of *type_id* be judged against *set_id* (K36-1)?

    Every set, for every type but the two ISO types; for those, only the four
    ISO sets. A saved report that combines them otherwise was written before
    this rule and opens as it was saved; only a new Generate is held to it.
    """
    return (type_id not in REPORT_TYPE_ISO_SET
            or str(set_id or "") in ISO_JUDGED_AGAINST)


def set_held_to_type(type_id: str, set_id: str) -> str:
    """*set_id*, or, when *type_id* does not allow it, the type's own
    standard's set (K36-1): what a NEW report of that type is judged
    against when the starting choice (Preferences, the run's own default)
    is not an ISO set."""
    if set_allowed_for_type(type_id, set_id):
        return set_id
    return REPORT_TYPE_ISO_SET[type_id]


def iso_type_values_missing(type_id: str) -> bool:
    """True when *type_id* is an ISO type whose standard's values are not
    loaded (neither shipped nor supplied), so it cannot be produced."""
    sid = REPORT_TYPE_ISO_SET.get(type_id)
    if sid is None:
        return False
    from workflow.compliance_sets import factory_limits, limit_bearing
    return not limit_bearing(factory_limits(sid))

#: The heading that separates the two halves of the pulldown. The two formal
#: types are made for a published ISO standard; the four above are ChromIQ's
#: own documents, and the heading does more work than any word inside a name
#: could. It said "Against a printing condition you supply" until the values
#: began to ship (B8-1031): true of neither the shipped values nor a licence
#: holder's own file laid over them, both of which are the standard's.
REPORT_TYPE_MENU_HEADING = "For a published ISO standard"

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
    """Whether ChromIQ can produce that document today.

    The menu's flag, and for the two ISO types one more condition: their
    standard's values must be loaded (`iso_type_values_missing`). A report
    saved as one of them on a machine that has the values renders as the full
    report on one that has not, exactly as an unbuilt type does.
    """
    for tid, _name, _blurb, built in REPORT_TYPE_MENU:
        if tid == type_id:
            return built and not iso_type_values_missing(tid)
    return False


#: The kinds of measurement a report can be about (K13), and the third,
#: a project's calibration (#182 beta 39, Knut 5794078008).
KIND_PROFILING = "profiling"
KIND_VERIFICATION = "verification"
KIND_CALIBRATION = "calibration"


def report_types_for_kind(kind: "str | None") -> "tuple[str, ...]":
    """Which report types a measurement of *kind* may be made into.

    **KNUT, ON BETA 34 (K13):** *"The report type 'Printing record' is still
    available when run type is verification, but should not be available.
    And, when run type is Profiling, all report types are still available,
    but only 'Printing record' should be available."* A profiling measurement
    is the sheet a profile was BUILT from, so nothing on it is judged and the
    Printing record is its report; a verification is judged, so it gets every
    other type. ``None`` (a measurement in no project, which has no run type)
    keeps every type, as it always has.

    Built or not is a separate question (`report_type_is_built`): this says
    what a kind ALLOWS, and the menu still shows an unbuilt type greyed.
    """
    if kind == KIND_PROFILING:
        return (REPORT_TYPE_RECORD,)
    # **RUN TYPE CALIBRATION: EVERY TYPE BUT THE PRINTING RECORD (#182 beta
    # 39).** Knut, 5794078008: *"Allowed report types are all except the
    # printing record"*. This replaces K26's "no report at all" (§18.1).
    if kind == KIND_VERIFICATION:
        return tuple(t for t in REPORT_TYPES if t != REPORT_TYPE_RECORD)
    # **AND NOT THE TWO ISO TYPES (K36-2).** Knut, #182 5820871320, asked
    # whether a Calibration run should offer them: *"No, but the limit sets
    # can still be chosen, if the user wants to use those metrics and
    # threshold values in the report."* So "Judged against" keeps every set
    # for a calibration report, the ISO sets included (K36-1 does not reach
    # it, because no ISO type can be chosen here).
    if kind == KIND_CALIBRATION:
        return tuple(t for t in REPORT_TYPES
                     if t != REPORT_TYPE_RECORD
                     and t not in REPORT_TYPE_ISO_SET)
    return tuple(REPORT_TYPES)


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
    chart = current_chart_name(r.get("chart") or "", r.get("_origin_dir"))
    return f'{chart or "?"} @ {str(r.get("created") or "")[:19]}'


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
        # THE NAME IT HAS NOW (challenge C, beta 39, #3): a report saved
        # before a rename names the chart by the project's old name.
        name = current_chart_name(r.get("chart") or "",
                                  r.get("_origin_dir")) or "?"
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
#
#   spacing     = (#182 B8-483, Knut 2026-09-23, 5795087247: "Yes") the
#                 GREY_MIN_LEVELS steps the rule asks for must be pickable
#                 ROUGHLY EVENLY SPACED out of the chart's grey levels, so a
#                 ramp cannot meet "8 steps, white to black" with one black and
#                 seven greys huddled at the light end. See
#                 :func:`pick_even_grey_steps`.
GREY_SPREAD_TOL = 1.0
GREY_LEVEL_TOL = 0.5
GREY_MIN_LEVELS = 8
GREY_LIGHTEST_MIN = 90.0
GREY_DARKEST_MAX = 10.0
#: How far a picked grey step may sit from its evenly spaced position, in
#: device units of the 0 to 100 scale, i.e. PERCENT OF FULL SCALE. Knut: *"within
#: a few percent of full scale"*. 4, because it is the number the gap bound
#: proposed to him on 2026-09-22 (5776479532: "none over 22 %") comes out of:
#: two neighbouring picks sit at most 100 / 7 + 2 x 4 = 22.3 apart on a full
#: ramp. MEASURED: none of the 181 built-in charts that had an eligible grey
#: ramp before this rule is refused at 3, 4 or 5; a ramp of 0 plus 90 to 93.6
#: (the demo pack's Q1) is refused at all three.
GREY_SPACING_TOL = 4.0
GREY_PAPER_LEVEL = 99.5
RAMP_OTHER_CHANNELS_MIN = 99.0
RAMP_TV_LOW, RAMP_TV_HIGH = 30.0, 70.0
RAMP_MIN_STEPS = 3
RAMP_MIN_SPAN = 20.0
#: **K31, RULE A** (Knut, #182 5801677743, answering 5798697107 section 4:
#: *"Implement rule A"*). The grey ramp's spacing rule of K28a, applied to the
#: 30 to 70 % band of each ramp: RAMP_MIN_STEPS positions evenly spaced from
#: the ramp's OWN lowest to its own highest step in the band, and a step within
#: this many tone-value points (percent of full scale) of each, by the same
#: :func:`pick_even_grey_steps`. Measured before it was built (the presets
#: window's own code over every preset): 185 of 185 built-in presets still
#: answer, and of the demo presets only the one bunched on purpose (40, 59.4,
#: 60) is refused.
RAMP_SPACING_TOL = GREY_SPACING_TOL

#: **K31, OPTION (a)** (Knut, #182 5801677743, answering 5798697107 section
#: 7: *"On a FROM PROFILE GAMUT chart, use the chart's neutral AIMS as its grey
#: steps"*). A FROM PROFILE GAMUT chart is printed in the profile's own
#: numbers, so a neutral aim comes out with R, G and B up to 1.5 apart and the
#: device test above does not see it as grey (challenge A, F2: the six
#: lightest of 30 neutral aims on a 400-patch chart). On such a chart a patch
#: is a grey step when its AIM is neutral: ``hypot(a*, b*)`` of the reference
#: below this, the same test Create Chart uses to pick those neutrals
#: (`gamut_target.select_gamut_targets`, ``_is_neutral``). The eight cube corners are
#: never steps: their reference is the ideal device corner, not an aim.
NEUTRAL_AIM_CHROMA_MAX = 1.0
#: …each step placed by its aim's L* (0 to 100), and the ends asked of the
#: chart itself: its lightest neutral aim within this many L* of the lightest
#: aim on the chart, its darkest within this many of the darkest. The device
#: rule's fixed 90 and 10 would refuse every paper whose black is lighter than
#: L* 10, which is most matte papers, and "reaches white" means "reaches as
#: far as this printing condition reaches" on a chart made of what it can
#: print. 10, because it is the distance the device rule allows at each end.
NEUTRAL_AIM_END_REACH = 10.0

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

# ---------------------------------------------------------------------------
# Evenness across the sheet, nine locations (#182, Knut, 2026-09-22)
# ---------------------------------------------------------------------------
#: **KNUT'S GEOMETRIC FLOOR: every page used has at least this many strips AND
#: this many rows.** 5744704621 requirement 1, kept on 2026-09-22 when he was
#: offered a patch count instead: *"Yes, keep 9 by nine minimum rule. The test
#: is supposed to judge uniformity across the various areas of a page."*
#:
#: ONE CONSTANT FOR BOTH DIRECTIONS, because he has said he may raise it (to
#: 12 by 12 was the figure named) and that must be a one-line change. Every
#: sentence that quotes the floor reads it from here.
EVENNESS_MIN_GRID = 9

#: **KNUT'S SECOND FLOOR: THE PATCH BLOCK COVERS AT LEAST THIS SHARE OF THE
#: PAGE** (#182 E2, 5789263863, approved at 75 % in 5789539407). *"9 strips and
#: 9 rows may still cover just a limited part of a page, thus the uniformity
#: test has limited value."* A page under it is left out of evenness exactly as
#: a page under :data:`EVENNESS_MIN_GRID` is. The share is Knut's formula over
#: the four "Measured from Preview" margins, computed in
#: :mod:`workflow.page_coverage`. ONE CONSTANT, read by every sentence that
#: quotes it.
EVENNESS_MIN_PAGE_COVERAGE = 0.60

#: How many times the patches are shuffled across the nine areas to measure
#: the sheet's own noise. Knut, 2026-09-22, ruling 6, on the F1 proposal:
#: *"Your suggestion is good. Do not use the stricter version."* A shuffle puts
#: every patch in a random area, so whatever the two numbers read afterwards is
#: noise by construction (instrument, profile, the chart's own mix of colours),
#: and the 95th percentile of 500 such readings is the level a real difference
#: has to clear. Five hundred gives that percentile to about +-0.02 on the real
#: sheet the F1 analysis used; more buys nothing a verdict can see.
EVENNESS_SHUFFLES = 500

#: The shuffles are drawn from a FIXED seed, so the same measurement gives the
#: same noise figure every time it is reported, on every machine. A report that
#: changed its N-A to a PASS on being opened again would be worse than either.
EVENNESS_SEED = 182

#: The place a residual is evaluated at. A deviation has no colour of its own,
#: and ΔE00 needs one; a neutral mid grey is where ΔE00 weighs L*, a* and b*
#: most nearly evenly, and it is the construction the F1 analysis used for the
#: numbers Knut was shown and ruled on (0.81 and 0.45 on the real sheet, noise
#: 0.27 and 0.16, "about 30 patches per area" at 1.5).
EVENNESS_BASE_LAB = (50.0, 0.0, 0.0)

#: **THE PRE-PRINT ESTIMATE, AND ONLY THAT.** The presets window and the
#: Measure tab's pre-flight answer before anything is printed, so they cannot
#: measure a sheet's noise; they estimate it for a typical print by giving each
#: patch a random residual of this size (ΔL*, Δa*, Δb* each, normal, fixed
#: seed) and running the SAME shuffle as the report.
#:
#: CALIBRATED ON NOISE, NOT ON ΔE00. The F1 analysis measured a real Pro300 /
#: i1Studio sheet against a profile that never saw the patches: noise p95 of
#: the pairwise row 2.57 at 10 patches per area, 1.41 at 30, 1.18 at 45. A
#: residual of 1.1 per component reproduces 2.4, 1.41 and 1.17. A residual
#: matched to the same sheet's per-patch ΔE00 instead (median 0.71) predicts a
#: third of that, because a saturated patch's chroma error is discounted in its
#: own ΔE00 and weighed in full at mid grey. The report measures the real
#: figure; this number never reaches a report.
EVENNESS_TYPICAL_SIGMA = 1.1

#: The estimate's shuffles. Fewer than the report's, because the presets
#: window runs it for every preset on one click and an estimate's 95th
#: percentile does not need the report's precision: 200 moves it by about
#: 0.03 on the real sheet, a tenth of the step between a chart that can and
#: one that cannot be judged.
EVENNESS_ESTIMATE_SHUFFLES = 200

#: Reason codes for a row that could not be computed. The report window turns
#: them into sentences through tr(); the JSON keeps the code.
REASON_NO_GREYS = "no_greys"
REASON_TOO_FEW_STEPS = "too_few_steps"
#: #182 B8-483: enough grey steps, reaching white and black, but not
#: GREY_MIN_LEVELS of them roughly evenly spaced (`pick_even_grey_steps`). Its
#: own code, because the too-few sentence ("has 20 grey steps; at least 8 are
#: needed") would be false on the chart that reaches it.
REASON_GREY_STEPS_BUNCHED = "grey_steps_bunched"
REASON_NO_WHITE = "no_white"
REASON_NO_BLACK = "no_black"
REASON_NO_REFERENCE = "no_reference"
REASON_NEEDS_REFERENCE_FILE = "needs_reference_file"
REASON_NO_RAMP = "no_ramp"
#: K31 rule A: a ramp with enough steps spanning enough of the band, whose
#: steps are bunched (`RAMP_SPACING_TOL`). Its own code, because "no tone ramp
#: with at least three steps" would be false on the chart that reaches it.
REASON_RAMP_STEPS_BUNCHED = "ramp_steps_bunched"
#: K31 option (a): the grey-ramp reasons of a FROM PROFILE GAMUT chart, whose
#: grey steps are its neutral AIMS. Their own codes, because the device
#: sentences ("add grey steps", "R = G = B") are false on such a chart: its
#: patches come from the profile, not from a grey step setting. Spelled again
#: in `compliance_sets.GREY_AIM_REASONS`, which cannot import this module.
REASON_TOO_FEW_NEUTRAL_AIMS = "too_few_neutral_aims"
#: **K40-2 (Knut, #182 5832026677: "Yes")**: on a FROM PROFILE GAMUT chart the
#: 30 to 70 % tone row's grey axis is the chart's neutral AIMS, as the grey
#: rows' steps are (K31 option a). Two reasons of their own, for the same
#: reason the grey rows have theirs: "raise Single Channel Steps or Grey Axis
#: Steps" is a lever such a chart does not have, and its level is an L*.
REASON_RAMP_TOO_FEW_NEUTRAL_AIMS = "ramp_too_few_neutral_aims"
REASON_RAMP_NEUTRAL_AIMS_BUNCHED = "ramp_neutral_aims_bunched"
REASON_NEUTRAL_AIMS_BUNCHED = "neutral_aims_bunched"
REASON_NEUTRAL_AIMS_NO_WHITE = "neutral_aims_no_white"
REASON_NEUTRAL_AIMS_NO_BLACK = "neutral_aims_no_black"
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
#: The measurement carries no device values, so no patch can be found to be a
#: grey, a ramp step or on the gamut's surface (B8-845, question 3). Written by
#: `build_report` into the grey, ramp and gamut blocks it could not compute,
#: where it used to leave them out and the report then said "this value is not
#: in this saved report" of a report built a second ago.
REASON_NO_DEVICE_VALUES = "no_device_values"
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
#: …and the two evenness rows, one code per thing the MEASURED CHART lacks
#: (Knut, 2026-09-23: a note says what is missing in the measured chart, never
#: what to add or where):
#:
#: * no chart layout beside the measurement at all (a stand-alone import);
#: * a layout whose patch locations cannot be read as strip and row;
#: * no page with at least :data:`EVENNESS_MIN_GRID` strips and rows;
#: * an area of the nine with no patch carrying an aim value;
#: * the sheet's own noise is not below the limit, once per row, because each
#:   row has its own limit and its own noise.
#:
#: (A preset that has not been laid out yet has a seventh answer, "not known
#: yet", which no measured sheet can give; it lives in `preset_eligibility`.)
REASON_EVENNESS_NO_LAYOUT = "evenness_no_layout"
REASON_EVENNESS_NO_POSITIONS = "evenness_no_positions"
REASON_EVENNESS_GRID_TOO_SMALL = "evenness_grid_too_small"
REASON_EVENNESS_EMPTY_AREA = "evenness_empty_area"
REASON_EVENNESS_NOISY_PAIRWISE = "evenness_noisy_pairwise"
REASON_EVENNESS_NOISY_FROM_MEAN = "evenness_noisy_from_mean"
#: #182 E2 (Knut, 2026-09-23): every page of at least 9 by 9 covers less than
#: :data:`EVENNESS_MIN_PAGE_COVERAGE` of its paper with patches…
REASON_EVENNESS_PAGE_COVERAGE = "evenness_page_coverage_too_small"
#: …or the chart's files do not record where its patch block sits on the page
#: (no engine geometry, no page image, no derived rectangles): a chart ChromIQ
#: cannot lay out, such as an imported one.
REASON_EVENNESS_NO_PAGE_GEOMETRY = "evenness_no_page_geometry"
EVENNESS_REASONS: "tuple[str, ...]" = (
    REASON_EVENNESS_NO_LAYOUT, REASON_EVENNESS_NO_POSITIONS,
    REASON_EVENNESS_GRID_TOO_SMALL, REASON_EVENNESS_EMPTY_AREA,
    REASON_EVENNESS_NOISY_PAIRWISE, REASON_EVENNESS_NOISY_FROM_MEAN,
    REASON_EVENNESS_PAGE_COVERAGE, REASON_EVENNESS_NO_PAGE_GEOMETRY,
)
#: The two of those that are about the measurement's FILES rather than the
#: chart's patches: no layout beside the measurement, or one that cannot be
#: read. Adding patches in Create Chart and printing again answers neither,
#: so the report window's strip, whose message promises exactly that, does not
#: name a row withheld for one of these (the row still reads N-A with its note).
EVENNESS_FILE_REASONS: "tuple[str, ...]" = (
    REASON_EVENNESS_NO_LAYOUT, REASON_EVENNESS_NO_POSITIONS,
    REASON_EVENNESS_NO_PAGE_GEOMETRY,
)
#: The two that are about the MEASUREMENT's noise: the sheet's own readings
#: scatter too much for the rule to judge the row (Knut's ruling 6). A chart
#: change is not the remedy, so the report window's strip does not name them
#: and their note names the noise and no patch count (beta 37, A-F3/B-H2).
EVENNESS_NOISE_REASONS: "tuple[str, ...]" = (
    REASON_EVENNESS_NOISY_PAIRWISE, REASON_EVENNESS_NOISY_FROM_MEAN,
)
#: The two row ids, and which of the block's two numbers each reads.
EVENNESS_ROWS: "dict[str, str]" = {
    "uniformity_sd": "pairwise",
    "uniformity_de00_max_from_mean": "from_mean",
}

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

#: **WHAT CAN MAKE A SHEET UNEVEN, ON EVERY EVENNESS VERDICT.** Knut,
#: 2026-09-22: information on what type of faults may result in uniformity
#: issues must be *"mentioned in the help text, but also as notes on the
#: results in the report text, for any report type that has enabled this
#: metric."* A comment ON a verdict, so it is a note and not a reason, and it
#: is attached whether the row passed or failed: a cause listed only beside a
#: failure would read as an excuse for it.
NOTE_EVENNESS_CAUSES = "evenness_causes"

#: #182 K37, (b) of Knut's answer 5822758830: a sheet printed with an intent
#: that maps white to the paper, whose chart has no paper patch, and for which
#: no profile could be read to take the paper white from, is judged in
#: absolute Lab. The text is `measurement_messages.
#: M_REPORT_JUDGED_ABSOLUTE_NO_PAPER_WHITE`.
NOTE_JUDGED_ABSOLUTE_NO_PAPER_WHITE = "absolute_no_paper_white"

#: #182 K37 (i), Knut 5823088098: on a FROM PROFILE GAMUT chart a corner
#: patch has two comparisons (the ideal value in the cube-corner table, the
#: profile's prediction in the control strip), and the strip rows say so. The
#: texts are `measurement_messages.M_REPORT_STRIP_CORNERS_PREDICTED` and, when
#: no profile could be asked, `M_REPORT_STRIP_CORNERS_IDEAL`.
NOTE_STRIP_CORNERS_PREDICTED = "strip_corners_predicted"
NOTE_STRIP_CORNERS_IDEAL = "strip_corners_ideal"

#: The rows whose numbers such a sheet moves, measured in §32.6: the five
#: colour-difference statistics, the three control-strip rows, the two gamut
#: populations, both grey-balance rows, the 30 to 70 % tone ramps and the two
#: evenness rows (less, because evenness compares areas with each other).
#: Not the two repeatability rows (readings against readings), and not the
#: rows that need a colorimetric reference (such a sheet never has one).
ROWS_MOVED_BY_THE_PAPER_WHITE: "tuple[str, ...]" = (
    "all_de00_avg", "best95_de00_avg", "worst5_de00_avg", "all_de00_max",
    "all_de00_p95",
    "control_strip_de00_avg", "control_strip_de00_max",
    "control_strip_de00_p95",
    "surface_gamut_de00_avg", "outer_gamut_226_de00_avg",
    "grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max",
    "ramps_30_70_dl_max",
    "uniformity_sd", "uniformity_de00_max_from_mean",
)


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


def pick_even_grey_steps(levels: "list[float]", n: int = GREY_MIN_LEVELS,
                         tol: float = GREY_SPACING_TOL
                         ) -> "tuple[list[float] | None, float | None]":
    """The *n* grey levels that meet the step rule, roughly evenly spaced.

    Knut, #182 B8-483 (5775993270, ruled 5795087247): *"the patches that
    represent the minimum number should be picked out from the existing
    neutral grey patches, and those should have an approximate even spacing,
    else the outer black and white positions can be fulfilled, but the patches
    between them cramped into lumps"*; *"within a few percent of full scale"*.

    Built as: *m* positions evenly spaced from the ramp's own darkest to its
    own lightest level (the end rules, <= 10 and >= 90, are asked separately),
    and for each the nearest grey level on the chart, which must lie within
    *tol* device units (percent of full scale) of it and be a different level
    from every other pick. The ends are always their own pick.

    *m* starts at *n*, the number required, and the first *m* that works is
    taken. It may be MORE than *n*, and that is not a loophole: a perfectly
    even 11-step ramp (0, 10 … 100) holds no 8 steps within 4 of an 8-step
    spacing (14.3 sits 4.3 from both 10 and 20), yet its steps are as evenly
    spaced as steps can be. Either way the picked steps sit no more than
    ``(hi - lo) / 7 + 2 * tol`` apart (22.3 on a full ramp), so a ramp whose
    steps between the two ends are cramped into lumps fails at every *m*.

    Returns ``(picked, None)``, lightest first, or ``(None, position)`` with
    the first evenly spaced position of the *n*-step spacing that has no grey
    level near it.
    """
    vals = sorted({round(float(v), 3) for v in levels})
    if len(vals) < 2 or n < 2:
        return None, None
    lo, hi = vals[0], vals[-1]

    def attempt(m: int) -> "tuple[list[float] | None, float | None]":
        picked: "list[float]" = []
        for k in range(m):
            target = lo + k * (hi - lo) / (m - 1)
            near = min(vals, key=lambda v: abs(v - target))
            if abs(near - target) > tol or (picked and near == picked[-1]):
                return None, round(target, 1)
            picked.append(near)
        return picked, None

    first_miss: "float | None" = None
    for m in range(n, len(vals) + 1):
        picked, miss = attempt(m)
        if picked is not None:
            return sorted(picked, reverse=True), None
        if first_miss is None:
            first_miss = miss
    return None, first_miss


def _neutral_aim_grey_block(rgb, lab, aims: "dict[str, tuple]",
                            sample_ids: "list[str]",
                            corner_ids: "set[str]") -> dict:
    """The grey-ramp block of a FROM PROFILE GAMUT chart (K31, option a).

    The same rules as the device ramp, asked of the chart's neutral AIMS:
    a patch is a step when its aim's ``hypot(a*, b*)`` is below
    `NEUTRAL_AIM_CHROMA_MAX`, placed by the aim's L*; at least
    `GREY_MIN_LEVELS` distinct steps, reaching within `NEUTRAL_AIM_END_REACH`
    of the lightest and the darkest aim on the chart, and `GREY_MIN_LEVELS`
    of them within `GREY_SPACING_TOL` L* of an even spacing
    (:func:`pick_even_grey_steps`). The ΔCh is each step's measured a*, b*
    against its aim, over every step, as on the device ramp.
    """
    corners = {str(c) for c in (corner_ids or ())}
    usable = [i for i, sid in enumerate(sample_ids)
              if sid not in corners and aims.get(sid) is not None]
    idx = [i for i in usable
           if math.hypot(float(aims[sample_ids[i]][1]),
                         float(aims[sample_ids[i]][2])) < NEUTRAL_AIM_CHROMA_MAX]
    block: dict = {"n_greys": len(idx), "levels": 0, "eligible": False,
                   "reason": None, "avg": None, "max": None, "per_level": [],
                   "picked_levels": [], "spacing_tol": GREY_SPACING_TOL,
                   "source": "neutral_aims"}
    if len(idx) == 0:
        block["reason"] = REASON_TOO_FEW_NEUTRAL_AIMS
        return block
    levels = [float(aims[sample_ids[i]][0]) for i in idx]
    all_l = [float(aims[sample_ids[i]][0]) for i in usable]
    block["levels"] = _distinct_levels(levels)
    block["chart_lightest"] = round(max(all_l), 1)
    block["chart_darkest"] = round(min(all_l), 1)
    if block["levels"] < GREY_MIN_LEVELS:
        block["reason"] = REASON_TOO_FEW_NEUTRAL_AIMS
    elif max(levels) < max(all_l) - NEUTRAL_AIM_END_REACH:
        block["reason"] = REASON_NEUTRAL_AIMS_NO_WHITE
    elif min(levels) > min(all_l) + NEUTRAL_AIM_END_REACH:
        block["reason"] = REASON_NEUTRAL_AIMS_NO_BLACK
    else:
        picked, missing = pick_even_grey_steps(levels)
        if picked is None:
            block["reason"] = REASON_NEUTRAL_AIMS_BUNCHED
            block["missing_level"] = missing
        else:
            block["picked_levels"] = [round(v, 1) for v in picked]
            block["eligible"] = True
    per: list[dict] = []
    for i in idx:
        # the bare paper is left out of the figure here as on a device ramp
        if rgb is not None and len(rgb) > i \
                and float(np.min(rgb[i])) >= GREY_PAPER_LEVEL:
            continue
        a = aims[sample_ids[i]]
        dch = math.hypot(lab[i][1] - a[1], lab[i][2] - a[2])
        per.append({"level": round(float(a[0]), 1), "dch": round(float(dch), 3),
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


def grey_balance_block(rgb100, lab, ref: "dict[str, tuple]",
                       sample_ids: "list[str]",
                       neutral_aims: "dict[str, tuple] | None" = None,
                       corner_ids: "set[str] | None" = None) -> dict:
    """The grey-ramp block of a report (see the notes above).

    *neutral_aims* is given for a chart built FROM PROFILE GAMUT, whose
    colorimetric reference it is: its grey steps are then its neutral AIMS
    (K31, :func:`_neutral_aim_grey_block`), and *corner_ids* names the eight
    cube corners, which are never steps."""
    rgb = np.asarray(rgb100, dtype=float)
    if neutral_aims is not None:
        return _neutral_aim_grey_block(rgb, lab, neutral_aims, sample_ids,
                                       set(corner_ids or ()))
    idx = [i for i in range(len(sample_ids))
           if float(rgb[i].max() - rgb[i].min()) <= GREY_SPREAD_TOL]
    block: dict = {"n_greys": len(idx), "levels": 0, "eligible": False,
                   "reason": None, "avg": None, "max": None, "per_level": [],
                   "picked_levels": [], "spacing_tol": GREY_SPACING_TOL}
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
        # #182 B8-483: the required steps, roughly evenly spaced. The
        # STATISTICS below still run over every grey patch (CH-10): this
        # decides whether the ramp meets the step rule, not what is averaged.
        picked, missing = pick_even_grey_steps(levels)
        if picked is None:
            block["reason"] = REASON_GREY_STEPS_BUNCHED
            block["missing_level"] = missing
        else:
            block["picked_levels"] = [round(v, 1) for v in picked]
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


#: **K43 (Knut, #182 5833695633: "Analyse and simulate, as well as search
#: online for normal practice").** The tone value of a neutral AIM on a FROM
#: PROFILE GAMUT chart is measured between the chart's own paper (0 %) and its
#: own darkest neutral aim (100 %), on L*: ISO 20654:2017's spot colour tone
#: value (SCTV), whose three "value" components are all L* for a neutral
#: colour, so for a neutral on a neutral paper it is exactly
#: ``100 (L*paper - L*) / (L*paper - L*darkest)``. Every printing standard
#: measures a tone value between the paper and the solid (ISO 12647-1's
#: Murray-Davies, G7's CIE-Y tone value, ISO 20654), none between L* 100 and
#: L* 0, which no paper and no ink reach. It replaces K40-2's ``100 - L*``,
#: which put the 30 to 70 % band into the shadows of every paper whose black
#: is not near L* 0 (measured: on a plain paper with a black of L* 20 it
#: judged 33 to 87 % of the paper-to-black range, on a gloss paper with a
#: black of L* 3 26 to 69 %). The analysis: `~/Desktop/ChromIQ-beta44-proof/
#: k43/REPORT.md`.
def neutral_aim_tone_scale(neutral_ls: "list[float]",
                           paper_ls: "list[float]" = ()
                           ) -> "tuple[float, float] | None":
    """``(L*paper, L*darkest)`` of a FROM PROFILE GAMUT chart's tone scale:
    the paper is the lightest of the chart's paper aim (its bare-paper corner,
    which aims at the profile's own paper) and its neutral aims, so a
    media-relative chart (paper at L* 100) and an absolute one (paper at the
    profile's white) are both measured from their own paper; the black is the
    darkest neutral aim. None when there are fewer than two distinct levels,
    because a scale needs two ends."""
    ls = [float(v) for v in neutral_ls]
    if not ls:
        return None
    paper = max(ls + [float(v) for v in paper_ls])
    black = min(ls)
    if paper - black < GREY_LEVEL_TOL:
        return None
    return paper, black


def neutral_aim_tone_value(l_star: float,
                           scale: "tuple[float, float] | None") -> float:
    """The tone value of a neutral aim of lightness *l_star* on *scale*
    (:func:`neutral_aim_tone_scale`): 0 at the paper, 100 at the darkest
    neutral aim. With no scale, -1, which no band holds."""
    if scale is None:
        return -1.0
    paper, black = scale
    return 100.0 * (paper - float(l_star)) / (paper - black)


def _paper_corner_sids(rgb, sample_ids: "list[str]", corners: "set[str]",
                       aims: dict) -> "list[str]":
    """The declared corners of a FROM PROFILE GAMUT chart that are the bare
    paper (device white), and carry an aim."""
    out = []
    for i, sid in enumerate(sample_ids):
        if sid in corners and aims.get(sid) is not None and len(rgb) > i \
                and float(np.min(rgb[i])) >= GREY_PAPER_LEVEL:
            out.append(sid)
    return out


def ramps_block(rgb100, lab, ref: "dict[str, tuple]",
                sample_ids: "list[str]",
                neutral_aims: "dict[str, tuple] | None" = None,
                corner_ids: "set[str] | None" = None) -> dict:
    """The 30 to 70 % tone-ramp block of a report (ISO 12647-8:2021 4.2.7 is
    the row that reads it; a *should*).

    *neutral_aims* is given for a chart built FROM PROFILE GAMUT, whose
    colorimetric reference it is (K40-2, Knut #182 5832026677: "Yes", the
    way the grey rows take them, K31 option a). The GREY axis is then the
    patches whose AIM is neutral (``hypot(a*, b*)`` under
    `NEUTRAL_AIM_CHROMA_MAX`, the eight *corner_ids* never), each placed at
    its tone value between the chart's OWN paper and its own darkest neutral
    aim (K43, :func:`neutral_aim_tone_value`: ISO 20654's spot colour tone
    value, which for a neutral is ``100 (L*paper - L*) / (L*paper -
    L*darkest)``), and the count, span and spacing rules are asked of those
    tone values unchanged. The ΔL* is each step's measured L* against its
    aim. The R, G and B axes stay device axes, as on every chart.
    """
    rgb = np.asarray(rgb100, dtype=float)
    axes: dict = {}
    overall_max = None
    any_eligible = False
    #: K31 rule A: the first axis that has the steps and the span but not
    #: their spacing, and the tone value no step is near, for the N-A note.
    bunched: "tuple[str, float | None] | None" = None
    corners = {str(c) for c in (corner_ids or ())}
    for name, ch, others in (("R", 0, (1, 2)), ("G", 1, (0, 2)), ("B", 2, (0, 1)),
                             ("grey", None, ())):
        aim_of = ref
        if ch is None and neutral_aims is not None:
            # K40-2: the neutral aims; K43: placed by their tone value
            # between the chart's own paper and its darkest neutral aim
            aim_of = neutral_aims
            members = [i for i, sid in enumerate(sample_ids)
                       if sid not in corners
                       and neutral_aims.get(sid) is not None
                       and math.hypot(float(neutral_aims[sid][1]),
                                      float(neutral_aims[sid][2]))
                       < NEUTRAL_AIM_CHROMA_MAX]
            scale = neutral_aim_tone_scale(
                [float(neutral_aims[sample_ids[i]][0]) for i in members],
                [float(neutral_aims[sid][0]) for sid in
                 _paper_corner_sids(rgb, sample_ids, corners, neutral_aims)])
            tv_of = (lambda i, sc=scale: neutral_aim_tone_value(  # noqa: E731
                float(neutral_aims[sample_ids[i]][0]), sc))
        elif ch is None:
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
        picked: "list[float]" = []
        if eligible:
            # K31 rule A: RAMP_MIN_STEPS of them roughly evenly spaced from
            # the ramp's own lowest to its own highest step in the band.
            got, miss = pick_even_grey_steps(tvs, n=RAMP_MIN_STEPS,
                                             tol=RAMP_SPACING_TOL)
            if got is None:
                eligible = False
                if bunched is None:
                    bunched = (name, miss)
            else:
                picked = sorted(round(v, 1) for v in got)
        dls = []
        for i in band:
            r = aim_of.get(sample_ids[i]) if aim_of else None
            if r is not None:
                dls.append(abs(float(lab[i][0]) - float(r[0])))
        axis = {"steps": distinct, "span": round(span, 1), "eligible": eligible,
                "picked": picked,
                "max_dl": round(float(max(dls)), 3) if (eligible and dls) else None}
        if ch is None and neutral_aims is not None:
            axis["source"] = "neutral_aims"
            # K43: the two ends the tone values were measured between
            axis["tone_scale"] = (None if scale is None
                                  else [round(scale[0], 2), round(scale[1], 2)])
        axes[name] = axis
        if eligible and dls:
            any_eligible = True
            overall_max = max(overall_max or 0.0, axis["max_dl"])
    out = {"axes": axes, "eligible": any_eligible,
           "reason": None if any_eligible else REASON_NO_RAMP,
           "spacing_tol": RAMP_SPACING_TOL,
           "max_dl": round(float(overall_max), 3) if overall_max is not None else None}
    if not any_eligible and neutral_aims is not None:
        # K40-2: on a FROM PROFILE GAMUT chart the lever is a larger chart,
        # never a step setting, so the reason says which of the aims' rules
        # was not met, and a bunched grey axis names its LIGHTNESS
        out["neutral_aims"] = True
        if bunched is not None and bunched[0] == "grey":
            out["reason"] = REASON_RAMP_NEUTRAL_AIMS_BUNCHED
            out["bunched_axis"] = "grey"
            sc = axes["grey"].get("tone_scale")
            out["missing_level"] = (
                None if (bunched[1] is None or sc is None)
                else round(sc[0] - bunched[1] / 100.0 * (sc[0] - sc[1]), 1))
            # the spacing tolerance in the same units as the level it is
            # read beside: tone-value points of THIS chart's scale, in L*
            out["spacing_tol_l"] = (None if sc is None else round(
                RAMP_SPACING_TOL / 100.0 * (sc[0] - sc[1]), 1))
        elif bunched is not None:
            out["reason"] = REASON_RAMP_STEPS_BUNCHED
            out["bunched_axis"] = bunched[0]
            out["missing_level"] = bunched[1]
        else:
            out["reason"] = REASON_RAMP_TOO_FEW_NEUTRAL_AIMS
        return out
    if not any_eligible and bunched is not None:
        out["reason"] = REASON_RAMP_STEPS_BUNCHED
        out["bunched_axis"] = bunched[0]
        out["missing_level"] = bunched[1]
    return out


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


# ---------------------------------------------------------------------------
# Evenness across the sheet, nine locations (Knut, #182, 2026-09-22)
# ---------------------------------------------------------------------------
def evenness_bands(n: int) -> "list[int]":
    """*n* whole strips or rows split into three bands, the remainder to the
    MIDDLE one. Knut, 5745765820: *"Where the remainder goes. Answer: middle
    section."* So 10 is 3 + 4 + 3 and 11 is 3 + 5 + 3."""
    b = int(n) // 3
    return [b, int(n) - 2 * b, b]


_LOC_ALPHA_NUM = re.compile(r"^([A-Za-z]+)(\d+)$")
_LOC_NUM_ALPHA = re.compile(r"^(\d+)([A-Za-z]+)$")


def _kw(keywords: dict, key: str, default: str = "") -> str:
    return str(keywords.get(key, default) or default).strip().strip('"').strip()


def chart_grid(ti2_path: "str | Path | None") -> dict:
    """Where every patch of a laid-out chart sits: page, strip, row.

    Read off the chart's ``.ti2``, never off the measurement: a chartread
    ``.ti3`` carries no ``SAMPLE_LOC`` (checked on the demo pack), and the
    chart is what was printed. The strip part and the row part of a location
    are told apart by which index pattern is alphabetic, which is how Argyll
    and the layout engine write them (``STRIP_INDEX_PATTERN "A-Z, A-Z"``,
    ``PATCH_INDEX_PATTERN "0-9,@-9,@-9;1-999"``: strip ``Y``, row ``14``).

    Returns ``{"reason": code}`` when the chart cannot say, else ``{"pages":
    [strips per page], "rows": steps, "slot": {sample_id: (page, strip on the
    page, row)}, "strip_label": {global strip: label}, "row_label": {row:
    label}, "rgb": {sample_id: device 0..100}}``.
    """
    if ti2_path is None or not Path(ti2_path).is_file():
        return {"reason": REASON_EVENNESS_NO_LAYOUT}
    try:
        d = parse_ti3(ti2_path)
    except (Ti3ParseError, OSError):
        return {"reason": REASON_EVENNESS_NO_LAYOUT}
    kw = d.keywords or {}
    pages = [int(x) for x in re.findall(r"\d+", _kw(kw, "PASSES_IN_STRIPS2"))]
    try:
        rows = int(_kw(kw, "STEPS_IN_PASS", "0"))
    except ValueError:
        rows = 0
    if not pages or rows < 1 or not d.sample_locs:
        return {"reason": REASON_EVENNESS_NO_LAYOUT}
    strip_alpha = "A-Z" in _kw(kw, "STRIP_INDEX_PATTERN", "A-Z, A-Z").upper()
    patch_alpha = "A-Z" in _kw(kw, "PATCH_INDEX_PATTERN", "0-9").upper()
    if strip_alpha == patch_alpha:
        # both parts letters or both digits: "12" cannot be split into a
        # strip and a row, so no position is known
        return {"reason": REASON_EVENNESS_NO_POSITIONS}
    from core.strip_utils import letter_to_idx
    starts = np.cumsum([0] + pages)
    n_strips = int(starts[-1])
    slot: "dict[str, tuple[int, int, int]]" = {}
    strip_label: "dict[int, str]" = {}
    row_label: "dict[int, str]" = {}
    for sid, loc in zip(d.sample_ids, d.sample_locs):
        loc = str(loc).strip().strip('"')
        m = _LOC_ALPHA_NUM.match(loc) or _LOC_NUM_ALPHA.match(loc)
        if not m:
            return {"reason": REASON_EVENNESS_NO_POSITIONS}
        a, b = m.group(1), m.group(2)
        letters, digits = (a, b) if a.isalpha() else (b, a)
        s_txt, r_txt = (letters, digits) if strip_alpha else (digits, letters)
        s = letter_to_idx(s_txt) if strip_alpha else int(s_txt) - 1
        r = int(r_txt) - 1 if strip_alpha else letter_to_idx(r_txt)
        if not (0 <= s < n_strips and 0 <= r < rows):
            return {"reason": REASON_EVENNESS_NO_POSITIONS}
        page = int(np.searchsorted(starts, s, side="right") - 1)
        slot[sid] = (page, int(s - starts[page]), r)
        strip_label.setdefault(s, s_txt)
        row_label.setdefault(r, r_txt)
    rgb = {}
    if d.rgb is not None and len(d.rgb):
        for sid, v in zip(d.sample_ids, _rgb_to_0_100(np.asarray(d.rgb, float))):
            rgb[sid] = v
    from workflow.page_coverage import chart_page_coverage
    cov = chart_page_coverage(ti2_path, len(pages))
    return {"pages": pages, "rows": rows, "slot": slot,
            "strip_label": strip_label, "row_label": row_label, "rgb": rgb,
            "coverage": cov["pages"], "coverage_source": cov["source"]}


def evenness_grid_from_layout(strips_per_page: "list[int]", rows: int,
                              total: int,
                              coverage: "list | None" = None) -> dict:
    """The same grid for a chart that has not been laid out yet, from the
    layout arithmetic alone (the presets window).

    The engine and printtarg both fill slots ``0 .. total-1`` strip by strip
    and only PERMUTE which patch lands in which slot, so how many patches each
    area holds does not depend on the seed. Synthetic ids ``"0" .. "total-1"``
    stand in for the patches; nothing reads them but the area arithmetic.

    *coverage* is the per-page list :mod:`workflow.page_coverage` returns
    (each a dict with ``coverage``, or None). Without it no page's coverage is
    known, and the block says so (#182 E2).
    """
    starts = np.cumsum([0] + list(strips_per_page))
    k = np.arange(int(total))
    s, r = np.divmod(k, int(rows))
    keep = s < int(starts[-1])
    s, r, k = s[keep], r[keep], k[keep]
    page = np.searchsorted(starts, s, side="right") - 1
    return {"pages": list(strips_per_page), "rows": int(rows),
            "ids": [str(x) for x in k], "page": page,
            "strip": s - starts[page], "row": r,
            "strip_label": {}, "row_label": {}, "rgb": {},
            "coverage": list(coverage) if coverage is not None else None}


def _grid_arrays(grid: dict) -> "tuple[list, np.ndarray, np.ndarray, np.ndarray]":
    """``(ids, page, strip on the page, row)`` as arrays, whichever form the
    grid came in (the per-id ``slot`` map of a laid-out chart, or the arrays
    of a predicted one)."""
    if "ids" in grid:
        return (list(grid["ids"]), np.asarray(grid["page"], int),
                np.asarray(grid["strip"], int), np.asarray(grid["row"], int))
    ids = list(grid["slot"])
    if not ids:
        z = np.zeros(0, int)
        return ids, z, z, z
    arr = np.asarray([grid["slot"][i] for i in ids], int)
    return ids, arr[:, 0], arr[:, 1], arr[:, 2]


def _bands_of(idx: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Which of :func:`evenness_bands`' three bands each index falls in, for
    its own *n*, over arrays."""
    b = n // 3
    m = n - 2 * b
    return np.where(idx < b, 0, np.where(idx < b + m, 1, 2))


def _nearest_rank_p95(a: np.ndarray) -> float:
    """The 95th percentile by nearest rank, the rule every p95 in this report
    uses (`_stats`, CH-28)."""
    s = np.sort(np.asarray(a, float))
    k = max(1, min(s.size, int(math.ceil(0.95 * s.size))))
    return float(s[k - 1])


_IU = np.triu_indices(9, 1)


def _nine_numbers(means: np.ndarray) -> "tuple[np.ndarray, np.ndarray]":
    """``(pairwise max, largest from the mean)`` for stacks of nine area
    residual means, shape ``(k, 9, 3)`` -> two arrays of length ``k``.

    Each area's colour is :data:`EVENNESS_BASE_LAB` plus its mean residual;
    "the mean of all nine" is the plain mean of the nine area colours, each
    area counting once whatever it holds.
    """
    from workflow.profile_engine.metrics import delta_e_2000
    labs = np.asarray(means, float) + np.asarray(EVENNESS_BASE_LAB)
    k = labs.shape[0]
    a = labs[:, _IU[0], :].reshape(-1, 3)
    b = labs[:, _IU[1], :].reshape(-1, 3)
    pw = delta_e_2000(a, b).reshape(k, -1).max(axis=1)
    centre = labs.mean(axis=1, keepdims=True)
    fm = delta_e_2000(labs.reshape(-1, 3),
                      np.repeat(centre, 9, axis=1).reshape(-1, 3)
                      ).reshape(k, 9).max(axis=1)
    return pw, fm


def _area_means(areas: np.ndarray, resid: np.ndarray,
                counts: np.ndarray) -> np.ndarray:
    return np.stack([np.bincount(areas, weights=resid[:, c], minlength=9)
                     for c in range(3)], axis=-1) / counts[:, None]


def evenness_from_residuals(grid: dict, residuals, *,
                            shuffles: int = EVENNESS_SHUFFLES,
                            seed: int = EVENNESS_SEED) -> dict:
    """The two evenness numbers and their noise, from a grid and a residual
    (measured minus aim, Lab) per sample id.

    *residuals* is ``{sample_id: (dL, da, db)}``, or an ``(n, 3)`` array in
    the order of the grid's own ids (the pre-print estimate, which has a
    residual for every slot).

    ONE FUNCTION FOR THE REPORT AND FOR THE PRE-PRINT ESTIMATE, so the presets
    window and the Measure tab's pre-flight run the arithmetic the report runs
    and differ from it only in where the residuals come from.
    """
    block: dict = {
        "eligible": False, "reason": None,
        "pairwise": None, "from_mean": None,
        "noise_pairwise_p95": None, "noise_from_mean_p95": None,
        "min_grid": EVENNESS_MIN_GRID,
        "shuffles": int(shuffles), "seed": int(seed),
        "base_lab": list(EVENNESS_BASE_LAB),
    }
    if "reason" in grid:
        block["reason"] = grid["reason"]
        return block
    pages, rows = list(grid["pages"]), int(grid["rows"])
    big = [p for p, s in enumerate(pages)
           if s >= EVENNESS_MIN_GRID and rows >= EVENNESS_MIN_GRID]
    # #182 E2: THE SECOND FLOOR, PAGE BY PAGE. A page of 9 by 9 whose patch
    # block covers less than EVENNESS_MIN_PAGE_COVERAGE of the paper is left
    # out exactly as a smaller page is; a page whose coverage nobody can say
    # is left out too, because the rule cannot be shown to hold on it.
    cov = _page_coverages(grid.get("coverage"), len(pages))
    used = [p for p in big
            if cov[p] is not None and cov[p] >= EVENNESS_MIN_PAGE_COVERAGE]
    block["pages"] = [[int(s), rows] for s in pages]
    block["pages_used"] = [p + 1 for p in used]
    block["largest_page"] = [int(max(pages)), rows]
    block["min_coverage"] = EVENNESS_MIN_PAGE_COVERAGE
    block["coverage"] = [None if c is None else round(float(c), 4)
                         for c in cov]
    block["coverage_source"] = grid.get("coverage_source") or ""
    block["pages_small"] = [p + 1 for p in range(len(pages)) if p not in big]
    block["pages_uncovered"] = [p + 1 for p in big
                                if cov[p] is not None
                                and cov[p] < EVENNESS_MIN_PAGE_COVERAGE]
    block["pages_unmeasured"] = [p + 1 for p in big if cov[p] is None]
    if not big:
        block["reason"] = REASON_EVENNESS_GRID_TOO_SMALL
        return block
    if not used:
        block["reason"] = (REASON_EVENNESS_PAGE_COVERAGE
                           if block["pages_uncovered"]
                           else REASON_EVENNESS_NO_PAGE_GEOMETRY)
        return block
    ids, page, strip, row = _grid_arrays(grid)
    on_used = np.isin(page, used)
    if isinstance(residuals, dict):
        have = np.fromiter((i in residuals for i in ids), bool, len(ids))
        keep = on_used & have
        resid = np.asarray([residuals[i] for i, k in zip(ids, keep) if k],
                           dtype=float).reshape(-1, 3)
    else:
        keep = on_used
        resid = np.asarray(residuals, dtype=float).reshape(-1, 3)[keep]
    page_strips = np.asarray(pages, int)[page[keep]]
    areas = (_bands_of(strip[keep], page_strips) * 3
             + _bands_of(row[keep], np.full(int(keep.sum()), rows)))
    counts = np.bincount(areas, minlength=9).astype(float) if areas.size \
        else np.zeros(9)
    block["n_patches"] = int(areas.size)
    block["counts"] = [int(c) for c in counts]
    if areas.size == 0 or (counts == 0).any():
        block["reason"] = REASON_EVENNESS_EMPTY_AREA
        return block
    means = _area_means(areas, resid, counts)
    pw, fm = _nine_numbers(means[None])
    # the noise: the same patches, their areas shuffled. One array of
    # shuffles and one bincount per Lab component over all of them at once:
    # the presets window runs this for 170 charts on one click.
    rng = np.random.default_rng(int(seed))
    k = int(shuffles)
    perm = rng.permuted(np.tile(areas, (k, 1)), axis=1)
    flat = (np.arange(k)[:, None] * 9 + perm).ravel()
    sums = np.stack([np.bincount(flat, weights=np.tile(resid[:, c], k),
                                 minlength=9 * k) for c in range(3)], axis=-1)
    sh_means = sums.reshape(k, 9, 3) / counts[None, :, None]
    npw, nfm = _nine_numbers(sh_means)
    block.update({
        "eligible": True, "reason": None,
        "pairwise": round(float(pw[0]), 3),
        "from_mean": round(float(fm[0]), 3),
        "noise_pairwise_p95": round(_nearest_rank_p95(npw), 3),
        "noise_from_mean_p95": round(_nearest_rank_p95(nfm), 3),
    })
    # WHERE: each area's own deviation, so the report can say which part of
    # the page it is (Knut, 2026-09-22: *"return indications of which part of
    # the page are not uniform against other areas"*).
    from workflow.profile_engine.metrics import delta_e_2000
    labs = means + np.asarray(EVENNESS_BASE_LAB)
    centre = labs.mean(axis=0)
    dfm = delta_e_2000(labs, np.repeat(centre[None], 9, axis=0))
    pair_de = delta_e_2000(labs[_IU[0]], labs[_IU[1]])
    worst = int(np.argmax(pair_de))
    block["worst_pair"] = [int(_IU[0][worst]), int(_IU[1][worst])]
    block["worst_area"] = int(np.argmax(dfm))
    area_rows = []
    for a in range(9):
        c, r = divmod(a, 3)
        area_rows.append({
            "area": a, "strip_band": c, "row_band": r, "n": int(counts[a]),
            "dL": round(float(means[a, 0]), 3),
            "da": round(float(means[a, 1]), 3),
            "db": round(float(means[a, 2]), 3),
            "de_from_mean": round(float(dfm[a]), 3),
            "strips": _band_labels(grid, used, c),
            "rows": _row_band_labels(grid, rows, r),
        })
    block["areas"] = area_rows
    return block


def _page_coverages(coverage, n_pages: int) -> "list[float | None]":
    """One share per page, 0..1, or None where it is not known."""
    out: "list[float | None]" = [None] * int(n_pages)
    for i, c in enumerate(list(coverage or [])[:int(n_pages)]):
        if isinstance(c, dict):
            c = c.get("coverage")
        if isinstance(c, (int, float)):
            out[i] = float(c)
    return out


def _band_labels(grid: dict, used: "list[int]", band: int) -> "list[list[str]]":
    """The first and last strip label of one strip band, per page used."""
    pages = grid["pages"]
    starts = np.cumsum([0] + list(pages))
    out = []
    for p in used:
        a, m, _ = evenness_bands(pages[p])
        lo = (0, a, a + m)[band]
        hi = (a, a + m, pages[p])[band] - 1
        g_lo, g_hi = int(starts[p] + lo), int(starts[p] + hi)
        lab = grid.get("strip_label") or {}
        out.append([str(lab.get(g_lo, g_lo + 1)), str(lab.get(g_hi, g_hi + 1))])
    return out


def _row_band_labels(grid: dict, rows: int, band: int) -> "list[str]":
    a, m, _ = evenness_bands(rows)
    lo = (0, a, a + m)[band]
    hi = (a, a + m, rows)[band] - 1
    lab = grid.get("row_label") or {}
    return [str(lab.get(lo, lo + 1)), str(lab.get(hi, hi + 1))]


#: The D50 white the media-relative yardstick maps the paper onto, in the
#: 0..100 XYZ scale the .ti3 carries.
_D50_XYZ_100 = (96.42, 100.0, 82.49)


def aims_on_the_paper(ref: "dict[str, tuple]", paper_xyz) -> "dict[str, tuple]":
    """Each aim Lab carried onto a paper whose white measures *paper_xyz*.

    #182 E8: evenness reads a sheet as MEASURED, whatever its intent. On a
    sheet printed with an intent that maps paper white, the design aims
    describe an ideal white paper, and what the print is asked to measure on
    the real one is each aim's XYZ times ``paper / D50``: the ICC.1 6.3.2.2
    media-relative scaling run the other way, on the AIMS, so the readings are
    never touched. One scale for every patch, wherever it sits, so it adds
    nothing that differs from one ninth of the page to another.
    """
    from workflow.ti3_analysis import _lab_to_xyz_array
    if not ref:
        return {}
    ids = list(ref)
    xyz = _lab_to_xyz_array(np.asarray([ref[i] for i in ids], dtype=float))
    scale = np.asarray(paper_xyz, dtype=float) / np.asarray(_D50_XYZ_100)
    return {sid: xyz_to_lab(tuple(x * scale / 100.0))
            for sid, x in zip(ids, xyz)}


def evenness_block(lab, ref: "dict[str, tuple]", sample_ids: "list[str]",
                   rgb100, ti2_path: "str | Path | None",
                   corner_ids: "set[str] | None" = None,
                   only_ids: "set[str] | None" = None) -> dict:
    """Evenness across the sheet, nine locations, for one measured sheet.

    Knut's rulings of 2026-09-22 (#182, 5785774676), in order:

    1. *each patch against its own expected colour, averaged per area*: the
       residual is measured Lab minus the aim the ΔE00 rows use (`ref`), with
       the declared cube corners left out as the ΔE00 statistics leave them
       out. *lab* is the ABSOLUTE reading, as measured, whatever intent the
       sheet was printed with (#182 E8, Knut 2026-09-23); `build_report`
       hands in `absolute_lab`, never its media-relative re-reading, and on a
       white-mapped sheet hands in the aims carried onto the paper
       (:func:`aims_on_the_paper`);
    2. three by three areas per page, whole strips and rows, remainder to the
       middle, every page pooled (5745765820), and only pages with at least
       :data:`EVENNESS_MIN_GRID` strips and rows;
    3. the pairwise maximum and the largest difference from the mean;
    6. the noise, from :data:`EVENNESS_SHUFFLES` shuffles of the same patches
       across the areas. The COMPARISON with a limit is made in :func:`judge`
       by :func:`evenness_withheld`, because this function never sees one.

    A patch whose device values here disagree with the chart's is left out and
    counted: its position on the sheet is the chart's, and a measurement of a
    different chart under the same ids would put it in the wrong area.
    """
    grid = chart_grid(ti2_path)
    if "reason" in grid:
        return evenness_from_residuals(grid, {})
    if not ref:
        out = evenness_from_residuals({"reason": REASON_NO_REFERENCE}, {})
        return out
    corner_ids = corner_ids or set()
    mine_rgb = (dict(zip(sample_ids, np.asarray(rgb100, dtype=float)))
                if rgb100 is not None and len(rgb100) else {})
    chart_rgb = grid.get("rgb") or {}
    residuals: "dict[str, tuple]" = {}
    mismatched = 0
    for i, sid in enumerate(sample_ids):
        aim = ref.get(sid)
        if aim is None or sid in corner_ids or sid not in grid["slot"]:
            continue
        if only_ids is not None and sid not in only_ids:
            continue
        if sid in mine_rgb and sid in chart_rgb and float(
                np.abs(mine_rgb[sid] - chart_rgb[sid]).max()) > PATCH_IDENTITY_TOL:
            mismatched += 1
            continue
        residuals[sid] = tuple(float(lab[i][k]) - float(aim[k]) for k in range(3))
    block = evenness_from_residuals(grid, residuals)
    block["n_mismatched"] = mismatched
    block["population"] = "in_gamut" if only_ids is not None else "all"
    # #182 E8: what the residuals were read in, so a saved report says so.
    block["yardstick"] = "absolute"
    return block


def evenness_withheld(row_id: str, cell: "dict | None", lim) -> "str | None":
    """The reason code that withholds an evenness verdict, or None.

    Knut, 2026-09-22, ruling 6: no verdict when the sheet's own noise (its
    95th percentile) is not below the limit. ONE RULE, asked by :func:`judge`
    and by `preset_eligibility`, so the report and the two pre-print windows
    cannot disagree about what a chart can be judged on.
    """
    key = EVENNESS_ROWS.get(row_id)
    if key is None or not cell or cell.get("value") is None:
        return None
    noise = cell.get("noise_p95")
    if noise is None or not getattr(lim, "is_numeric", False):
        return None
    if float(noise) >= float(lim.number):
        return (REASON_EVENNESS_NOISY_PAIRWISE if key == "pairwise"
                else REASON_EVENNESS_NOISY_FROM_MEAN)
    return None


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
        # #182 A11: the W corner's aim is the paper the chart's profile
        # describes since beta 42 (`paper_reference_of`, set in
        # `build_report`), so its ΔE00 is this row. A report written before
        # carries the ideal-white aim until it is updated.
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

    # -- evenness across the sheet, nine locations (Knut, 2026-09-22).
    #
    # The value is the sheet's; whether it may be JUDGED depends on the limit
    # as well (the noise rule), which this function never sees, so the noise
    # travels in the cell and `judge` asks `evenness_withheld`. Every verdict
    # on these rows carries the note on likely causes.
    ev = report.get("evenness")
    for rid, key in EVENNESS_ROWS.items():
        if not isinstance(ev, dict):
            put(rid, None, REASON_NOT_COMPUTED)
        elif ev.get("eligible") and ev.get(key) is not None:
            put(rid, ev[key], notes=[NOTE_EVENNESS_CAUSES])
            out[rid]["noise_p95"] = ev.get(f"noise_{key}_p95")
        else:
            put(rid, None, ev.get("reason") or REASON_EVENNESS_NO_LAYOUT)

    # -- #182 K37, (b): a sheet that should have been judged relative to its
    # paper white and could not be (no paper patch, no profile to read one
    # from) is judged in absolute Lab, and every row that moves carries a
    # note saying why it may read worse than the print is.
    # -- #182 K37 (i): on a FROM PROFILE GAMUT chart the strip's corner rungs
    # are compared with the profile's prediction (or, with no profile to ask,
    # with their ideal values): the three strip rows say which.
    _ca = (report.get("strip_corner_aims") or {}).get("from")
    _ca_note = {CORNER_AIMS_FROM_PROFILE: NOTE_STRIP_CORNERS_PREDICTED,
                CORNER_AIMS_IDEAL: NOTE_STRIP_CORNERS_IDEAL}.get(_ca)
    if _ca_note:
        for rid in _CS_ROWS:
            cell = out.get(rid)
            if cell and cell["value"] is not None:
                cell["notes"].append(_ca_note)

    if (report.get("paper_white_used") or {}).get("from") \
            == PAPER_WHITE_UNAVAILABLE:
        for rid in ROWS_MOVED_BY_THE_PAPER_WHITE:
            cell = out.get(rid)
            if cell and cell["value"] is not None \
                    and NOTE_JUDGED_ABSOLUTE_NO_PAPER_WHITE not in cell["notes"]:
                cell["notes"].append(NOTE_JUDGED_ABSOLUTE_NO_PAPER_WHITE)
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
    from workflow.compliance_sets import (COND, FAIL, N_A, PASS, ROWS, Limit,
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
        # THE EVENNESS NOISE RULE, which needs the limit and so lives here
        # beside the other rule that does (`_row_notes`). It withholds a PASS
        # or a FAIL, never an INFO: an ungraded sheet shows its number anyway.
        withheld = (evenness_withheld(r.id, cell, lim)
                    if word in (PASS, FAIL) else None)
        if withheld:
            word = N_A
            cell = dict(cell or {}, reason=withheld)
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
