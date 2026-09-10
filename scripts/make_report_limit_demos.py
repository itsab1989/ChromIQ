#!/usr/bin/env python3
"""Build the Measurement Report limit demo projects (#182, Knut 2026-09-08).

    *"Claude needs to make very extensive demo test projects with several runs
    and where each run has various verification runs. All with real data, real
    simulated measurements (fakeread?) and various chart sizes for each profile
    run, and the chart run used for each profile run. Some runs must only have
    one verification run, so that settings can be changed. Some runs must have
    many verification runs, where the various profile runs for the verification
    uses different report types and 'judged against' thresholds. The
    measurements must be designed so that every threshold in a report is being
    triggered, maximum two thresholds simultaneously, and then also making
    measurement value reduce after triggering so that values go below
    thresholds again."*

This is a SEPARATE generator from ``scripts/make_demo_projects.py``. That one
feeds the test suite's session-scoped ``demo_projects_root`` fixture, is cached
on disk keyed by its own source, and editing it invalidates that cache for
every gate on every machine. Nothing here touches it.

What is built
-------------
Three projects, eleven profile runs, thirty-one dated verifications::

    Report-Limits-Threshold-Series   the dated series: each judged row crosses
                                     its limit on one date and recovers on the
                                     next. run1 has ELEVEN dated verifications,
                                     run3 has exactly ONE, so its
                                     limit set can still be chosen.
    Report-Limits-Isolated-Rows      four rows that cannot cross alone under
                                     any shipped limit set, isolated by giving
                                     the run its own edited column. One of the
                                     four is judged by no shipped set at all.
                                     run3 has TWO dated verifications with the
                                     lock lifted by hand.
    Report-Limits-Set-Compare        the same measurement, three times, judged
                                     by ChromIQ default / tight / Quick check.

How the measurements are made
-----------------------------
Every chart is a real ArgyllCMS chart (``targen`` designs it, ``printtarg``
lays it out and renders the page TIFFs). Every profile is a real ``colprof``
profile built from a real ``fakeread`` measurement. Every dated verification
starts as a real ``fakeread`` of that run's verification chart through that
run's own profile.

Then a DESIGNED DRIFT is applied on top, patch by patch. Each patch keeps the
direction of the error fakeread actually produced through the real profile, and
only the MAGNITUDE is scaled so that the chart's statistics land exactly where
the date's design says they should. That is what makes "date X crosses row Y and
nothing else" a fact rather than a hope, and it is why the intended/actual table
in the README matches.

The alternative, ``fakeread -r`` random noise, moves every statistic at once and
can neither cross one row alone nor recover on cue.

Run it::

    .venv/bin/python scripts/make_report_limit_demos.py [destination] [--zip]

Default destination: ``demo-projects/ChromIQ-Report-Limit-Demos``.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

import numpy as np

ARGYLL = Path(os.environ.get("CHROMIQ_ARGYLL_BIN", "/Applications/Argyll/bin"))
SRGB = ARGYLL.parent / "ref" / "sRGB.icm"

#: Every Argyll call gets one. A `subprocess.run` without a timeout once sat on
#: a single `targen -G` for two and a half hours with no output.
TIMEOUT_TARGEN = 900
TIMEOUT_PRINTTARG = 600
TIMEOUT_FAKEREAD = 300
TIMEOUT_COLPROF = 900

FOLDER = "ChromIQ-Report-Limit-Demos"
INSTRUMENT = "X-Rite ColorMunki"


# ---------------------------------------------------------------------------
# Running Argyll
# ---------------------------------------------------------------------------
def run(cmd, cwd: Path, timeout: int) -> None:
    args = [str(c) for c in cmd]
    try:
        # `encoding=` and not the platform default: an Argyll tool that writes
        # a non-ASCII byte would otherwise decode differently on another
        # machine, and `tests/test_encoding_is_named.py` refuses a text call
        # site without one.
        r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise SystemExit(
            f"{args[0]} did not finish within {timeout} s in {cwd}. "
            f"Nothing was killed by an error; it simply never returned.")
    if r.returncode != 0:
        raise SystemExit(f"{args[0]} failed (exit {r.returncode}):\n"
                         f"{r.stdout}\n{r.stderr}")


# ---------------------------------------------------------------------------
# Charts and profiles
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ChartRecipe:
    """One chart size. ``grey`` and ``single`` keep the grey ramp and the
    30 to 70 % tone ramps eligible, which the report needs before it can put a
    number on the grey-balance rows at all."""
    patches: int
    grey: int
    single: int
    paper: str
    label: str

    @property
    def targen_args(self) -> list:
        return ["-d2", "-e4", "-B4", f"-g{self.grey}", f"-s{self.single}",
                f"-f{self.patches}"]


CHART_SMALL = ChartRecipe(105, 12, 8, "A4", "105 patches on A4")
CHART_MEDIUM = ChartRecipe(210, 16, 12, "A4", "210 patches on A4")
CHART_LARGE = ChartRecipe(400, 20, 16, "A4", "400 patches on A4")
CHART_WIDE = ChartRecipe(156, 14, 10, "A3", "156 patches on A3")

_chart_cache: "dict[tuple, Path]" = {}


def make_chart(into: Path, stem: str, recipe: ChartRecipe, cache_root: Path) -> None:
    """A real chart: targen designs it, printtarg lays it out and renders the
    pages. Cached per recipe so the same size is not designed twice."""
    into.mkdir(parents=True, exist_ok=True)
    key = (recipe.patches, recipe.grey, recipe.single, recipe.paper)
    src = _chart_cache.get(key)
    if src is None:
        src = cache_root / f"chart-{recipe.patches}-{recipe.paper}"
        src.mkdir(parents=True, exist_ok=True)
        run([ARGYLL / "targen"] + recipe.targen_args + ["chart"],
            src, TIMEOUT_TARGEN)
        run([ARGYLL / "printtarg", "-iCM", f"-p{recipe.paper}", "-t150", "-L",
             "chart"], src, TIMEOUT_PRINTTARG)
        _chart_cache[key] = src
    for p in sorted(src.iterdir()):
        if p.is_file() and p.name.startswith("chart"):
            shutil.copy2(p, into / (stem + p.name[len("chart"):]))


def fakeread(into: Path, stem: str, profile: Path) -> Path:
    """A real fakeread of ``<stem>.ti1`` through *profile*, no noise: the
    designed drift is applied afterwards, deliberately, patch by patch."""
    run([ARGYLL / "fakeread", profile, stem], into, TIMEOUT_FAKEREAD)
    return into / f"{stem}.ti3"


def build_profile(run_dir: Path, stem: str) -> None:
    """fakeread through sRGB plays the bare printer; colprof makes the run's
    own profile from that measurement."""
    fakeread(run_dir, stem, SRGB)
    run([ARGYLL / "colprof", "-v0", "-ql", "-aG", stem], run_dir, TIMEOUT_COLPROF)


# ---------------------------------------------------------------------------
# Colour: the exact inverse of the report's own xyz_to_lab
# ---------------------------------------------------------------------------
from workflow.icc_info import xyz_to_lab as _xyz_to_lab      # noqa: E402

_D50 = (96.42, 100.0, 82.49)


def _lab_to_xyz100(lab) -> tuple:
    """Lab back to XYZ on the 0..100 scale the .ti3 carries. Written as the
    exact inverse of workflow.icc_info.xyz_to_lab so a value survives the round
    trip and the report reads back the ΔE that was designed."""
    L, a, b = (float(v) for v in lab)
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0
    eps = 216.0 / 24389.0
    kap = 24389.0 / 27.0

    def inv(f, is_y):
        t = f ** 3
        if is_y:
            return t if L > kap * eps else L / kap
        return t if t > eps else (116.0 * f - 16.0) / kap

    return (inv(fx, False) * _D50[0], inv(fy, True) * _D50[1],
            inv(fz, False) * _D50[2])


from workflow.ti3_analysis import ciede2000                  # noqa: E402


def _de(lab_a, lab_b) -> float:
    return float(ciede2000(tuple(lab_a), tuple(lab_b)))


def _solve_scale(ref, direction, target_de: float) -> float:
    """The scale *s* for which ciede2000(ref + s*direction, ref) == target_de.

    ΔE00 grows monotonically along a ray out of the reference, so a bisection
    settles it. 60 halvings take the bracket below 1e-15 of its width.
    """
    lo, hi = 0.0, 1.0
    for _ in range(80):
        cand = tuple(ref[i] + hi * direction[i] for i in range(3))
        if _de(cand, ref) >= target_de:
            break
        hi *= 2.0
        if hi > 1e6:
            break
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        cand = tuple(ref[i] + mid * direction[i] for i in range(3))
        if _de(cand, ref) < target_de:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# The designed drift
# ---------------------------------------------------------------------------
GREY_SPREAD_TOL = 1.0        # mirrors workflow.measurement_report
GREY_PAPER_LEVEL = 99.5


def grey_stat_indices(rgb100: np.ndarray) -> "list[int]":
    """The patches the grey-balance rows are computed over: neutral by device
    value, and not the bare paper. The same test grey_balance_block applies."""
    out = []
    for i in range(rgb100.shape[0]):
        if float(rgb100[i].max() - rgb100[i].min()) > GREY_SPREAD_TOL:
            continue
        if float(rgb100[i].mean()) >= GREY_PAPER_LEVEL:
            continue
        out.append(i)
    return out


@dataclass
class Design:
    """What one dated verification's numbers are meant to be.

    The five colour-difference rows are order statistics of one list of ΔE00
    values, so the design is that list's shape:

    ``peak``      the single worst patch (what "All patches, largest" reads)
    ``tail``      the rest of the worst-5 % band (what "Worst 5 %, average"
                  reads, together with the peak)
    ``shoulder``  the top of the best 95 % (what "95th percentile" reads)
    ``bulk``      everything else (what "Best 95 %, average" mostly reads)

    ``target_best95`` overrides ``bulk``: the generator solves for the bulk
    value that puts the best-95 % average exactly there, which is the only way
    to hit that row without arithmetic by hand.

    ``grey_dch`` is the grey ramp's chroma difference, ``grey_spike`` one grey
    step's own.

    ``ramp_dl`` is the lightness error put on ONE step of the grey tone ramp
    between 30 and 70 % tone value, which is the only thing the "30 to 70 %
    ramps, largest lightness difference" row reads. It needs its own knob
    because the grey knob above moves chroma only and pins every grey's L* to
    the reference, so that row could never cross however the rest of the sheet
    was designed: measured over the whole package before this existed, seven of
    the eight rows a ChromIQ verification sheet can compute were crossed by some
    date and this was the eighth. The moved step also carries that lightness
    error into its own ΔE00, which is why the date that uses it expects two
    rows and not one.

    THE BAND SIZES ARE NOT FIXED. The rows are judged on the WITHIN-gamut
    patches (measurement_report.py:1008-1022), so how many patches fall in the
    worst 5 % depends on the chart and the profile, and the bands are sized
    from the real count at build time.
    """
    bulk: float
    shoulder: float
    peak: "float | None" = None
    tail: "float | None" = None
    target_best95: "float | None" = None
    grey_dch: float = 0.5
    grey_spike: "float | None" = None
    ramp_dl: "float | None" = None
    n_shoulder: int = 3


#: Device values at or above this on Argyll's 0..100 scale are the bare paper.
DEVICE_WHITE_MIN = 99.5


def in_gamut_flags(ti2: Path, profile: Path) -> "dict[str, bool]":
    """Which of the chart's colours the profile could actually print.

    The report judges only these (measurement_report.py:686-707 builds the
    split, :1008 makes the verdict read it). The test is made on the chart's
    DESIGN colours, so the answer is a property of the chart and the profile
    and is the same on every date, which is what makes it possible to design a
    date's statistics at all.
    """
    from workflow.gamut_target import MARGIN_SAFE, flags_in_gamut
    from workflow.measurement_report import _reference_labs
    from workflow.ti3_analysis import parse_ti3
    ref = _reference_labs(ti2)
    ids = [s for s in parse_ti3(ti2).sample_ids if s in ref]
    flags = flags_in_gamut([tuple(ref[s]) for s in ids], profile, ARGYLL,
                           margin=MARGIN_SAFE, intent="absolute")
    return {s: bool(f) for s, f in zip(ids, flags)}


def apply_design(ti3: Path, ti2: Path, design: Design,
                 gamut: "dict[str, bool] | None" = None) -> "dict[str, float]":
    """Rewrite the measurement's XYZ so the chart's statistics are the design's.

    THE DESIGN IS LAID OUT IN THE YARDSTICK THE REPORT ACTUALLY USES, which is
    not the obvious one. A sheet printed through the profile with a white
    mapping intent is judged *media-relative* (measurement_report.py:602-626):
    every reading is divided by the sheet's own paper white before the ΔE is
    taken, so that the paper is not counted against the profile. Designing in
    absolute Lab and hoping produced values around 55 % of the intended ones
    on the first run of this generator.

    So the numbers below are the media-relative ones, and the file is written
    back through the inverse of that normalisation. Two consequences follow and
    both are properties of the report, not of this script:

    * the paper-white patch is exactly L*100 a*0 b*0 after normalisation, by
      construction, so its own ΔE is ~0 whatever is written. The device-white
      patches are therefore left at the reference and take no designed value.
    * the paper white the report prints stays the one fakeread measured: the
      normalisation is anchored on it, so it is written back unchanged.

    Returns the predicted rows, so the caller can compare them against what the
    real report reads back.
    """
    from workflow.measurement_report import _reference_labs
    from workflow.ti3_analysis import parse_ti3

    data = parse_ti3(ti3)
    ref = _reference_labs(ti2)
    n = len(data.sample_ids)
    rgb = np.asarray(data.rgb, dtype=float)
    xyz = np.asarray(data.xyz, dtype=float)

    # The anchor: fakeread's own paper white, the lightest reading on the sheet.
    wi = int(np.argmax(xyz[:, 1]))
    white = xyz[wi].copy()
    if float(white.min()) <= 0.0:
        raise SystemExit(f"{ti3}: the lightest patch has a zero channel")
    scale = white / np.array(_D50)

    def to_relative(v) -> tuple:
        return _xyz_to_lab(tuple((np.asarray(v, float) / white * np.array(_D50)) / 100.0))

    measured = [to_relative(x) for x in xyz]
    whites = [i for i in range(n) if float(rgb[i].min()) >= DEVICE_WHITE_MIN]
    white_set = set(whites)

    greys = [i for i in grey_stat_indices(rgb) if i not in white_set]
    grey_set = set(greys)
    spike_at = greys[len(greys) // 2] if (greys and design.grey_spike is not None) else None

    new_lab: "dict[int, tuple]" = {}

    # -- the bare paper: fixed at the reference. The normalisation puts it at
    #    L*100 a*0 b*0 regardless, so a designed value here would be a fiction.
    for i in whites:
        new_lab[i] = (100.0, 0.0, 0.0)

    # -- the grey patches: a pure chroma move of the designed size, so ΔCh is
    #    exactly what the grey-balance rows are meant to read.
    for i in greys:
        r = ref.get(data.sample_ids[i])
        if r is None:
            continue
        da, db = measured[i][1] - r[1], measured[i][2] - r[2]
        mag = math.hypot(da, db)
        if mag < 1e-6:
            da, db, mag = 1.0, 0.0, 1.0
        want = design.grey_spike if i == spike_at else design.grey_dch
        new_lab[i] = (r[0], r[1] + want * da / mag, r[2] + want * db / mag)

    # -- everybody else. The judged population is the within-gamut patches, so
    #    the bands are laid over those and the rest simply carry the bulk value.
    judged = (lambda i: True) if gamut is None \
        else (lambda i: gamut.get(data.sample_ids[i], True))
    others = [i for i in range(n)
              if i not in grey_set and i not in white_set
              and data.sample_ids[i] in ref]
    fixed_in = [i for i in list(white_set) + greys
                if i in new_lab and judged(i)]
    n_in = len(fixed_in) + sum(1 for i in others if judged(i))
    k_in = max(1, min(n_in, int(math.ceil(n_in * 0.95))))
    m_tail = n_in - k_in

    tail_v = design.tail if design.tail is not None else design.shoulder
    band = []
    if design.peak is not None and m_tail:
        band = [design.peak] + [tail_v] * (m_tail - 1)
    elif m_tail:
        band = [tail_v] * m_tail
    band += [design.shoulder] * design.n_shoulder

    in_others = [i for i in others if judged(i)]
    out_others = [i for i in others if not judged(i)]

    def lay(bulk_value: float) -> "dict[int, tuple]":
        plan = list(band) + [bulk_value] * max(0, len(in_others) - len(band))
        made: "dict[int, tuple]" = dict(new_lab)      # the paper and the greys
        for pos, i in enumerate(in_others):
            made[i] = _place(ref[data.sample_ids[i]], measured[i], plan[pos])
        for i in out_others:
            made[i] = _place(ref[data.sample_ids[i]], measured[i], bulk_value)
        return made

    if design.target_best95 is not None:
        # Solve for the bulk value that puts the best-95 % average exactly on
        # the target. The greys and the bare paper are in that average too and
        # are not free, so there is no closed form worth writing.
        lo, hi = 0.0, 40.0
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            made = lay(mid)
            got = _predict_from(made, ref, data.sample_ids, judged)["best95_de00_avg"]
            if got < design.target_best95:
                lo = mid
            else:
                hi = mid
        new_lab.update(lay(0.5 * (lo + hi)))
    else:
        new_lab.update(lay(design.bulk))

    # -- one step of the 30 to 70 % grey ramp, moved in LIGHTNESS only.
    #    The grey knob above pins every grey's L* to the reference, so this row
    #    reads exactly zero on every date unless something moves L*. a* and b*
    #    are left where the grey knob put them, so the grey-balance rows keep
    #    the values they were designed for; only this patch's own ΔE00 grows.
    if design.ramp_dl is not None:
        step = _ramp_step_index(rgb, greys)
        if step is None:
            raise SystemExit(
                f"{ti3}: no grey step lies between {RAMP_TV_LOW} and "
                f"{RAMP_TV_HIGH} % tone value, so ramp_dl has nothing to move")
        r = ref[data.sample_ids[step]]
        a, b = new_lab[step][1], new_lab[step][2]
        new_lab[step] = (r[0] - design.ramp_dl, a, b)

    predicted = _predict_from(new_lab, ref, data.sample_ids, judged)
    if design.ramp_dl is not None:
        predicted["ramps_30_70_dl_max"] = float(design.ramp_dl)
    dchs = [math.hypot(new_lab[i][1] - ref[data.sample_ids[i]][1],
                       new_lab[i][2] - ref[data.sample_ids[i]][2])
            for i in greys if i in new_lab]
    if dchs:
        predicted["grey_balance_neutral_ramp_avg"] = float(np.mean(dchs))
        predicted["grey_balance_neutral_ramp_max"] = float(np.max(dchs))

    out = {}
    for i, v in new_lab.items():
        rel = np.asarray(_lab_to_xyz100(v), dtype=float)
        out[i] = tuple(rel * scale)
    _rewrite_xyz(ti3, out)
    return predicted


#: The band `measurement_report.ramps_block` reads, and the spread it allows a
#: patch before it stops counting as grey. Named here rather than imported so
#: that a change to either shows up as a MISMATCH in this generator's own
#: intended-against-actual check instead of silently moving the design.
RAMP_TV_LOW, RAMP_TV_HIGH = 30.0, 70.0


def _ramp_step_index(rgb, greys: "list[int]") -> "int | None":
    """The middle grey step lying inside the 30 to 70 % tone-value band.

    `ramps_block` reads the largest lightness difference over that band, taking
    the tone value of a grey as ``100 - mean(RGB)``. The middle of the band is
    chosen so the patch is as far as possible from both edges: a step at 30.4 %
    would drop out of the row entirely if the chart's levels ever shifted.
    """
    band = [i for i in greys
            if RAMP_TV_LOW <= (100.0 - float(np.asarray(rgb[i], float).mean()))
            <= RAMP_TV_HIGH]
    if not band:
        return None
    mid = 0.5 * (RAMP_TV_LOW + RAMP_TV_HIGH)
    return min(band, key=lambda i: abs((100.0 - float(np.asarray(rgb[i], float).mean())) - mid))


def _place(r, measured_lab, target_de: float) -> tuple:
    """The patch's new colour: the direction fakeread's own error took, scaled
    until the difference from the reference is *target_de*."""
    d = [measured_lab[j] - r[j] for j in range(3)]
    if max(abs(v) for v in d) < 1e-6:
        d = [0.6, 0.6, 0.4]
    s = _solve_scale(r, d, target_de)
    cand = tuple(r[j] + s * d[j] for j in range(3))
    if cand[0] > 99.0:
        # Nothing may end up lighter than the paper: it would take the paper's
        # place as the anchor of the media-relative yardstick and move the
        # whole sheet.
        d = [-d[0], d[1], d[2]]
        s = _solve_scale(r, d, target_de)
        cand = tuple(r[j] + s * d[j] for j in range(3))
    return cand


def _predict_from(new_lab, ref, sample_ids, judged) -> "dict[str, float]":
    des = [_de(new_lab[i], ref[sample_ids[i]])
           for i in sorted(new_lab) if sample_ids[i] in ref and judged(i)]
    return _predict(des, [])


def _predict(des: "list[float]", dchs: "list[float]") -> "dict[str, float]":
    a = np.sort(np.asarray(des, float))
    n = int(a.size)
    k = max(1, min(n, int(math.ceil(n * 0.95))))
    low, high = a[:k], a[k:]
    out = {
        "all_de00_avg": float(a.mean()),
        "best95_de00_avg": float(low.mean()),
        "worst5_de00_avg": float(high.mean()) if high.size else None,
        "all_de00_max": float(a.max()),
        "all_de00_p95": float(low.max()),
    }
    if dchs:
        out["grey_balance_neutral_ramp_avg"] = float(np.mean(dchs))
        out["grey_balance_neutral_ramp_max"] = float(np.max(dchs))
    return out


def _rewrite_xyz(ti3: Path, xyz_by_index: "dict[int, tuple]") -> None:
    """Put the designed XYZ back into the measurement, leaving every other
    field, keyword and line of the file exactly as fakeread wrote it."""
    lines = ti3.read_text(encoding="utf-8").splitlines()
    fields: "list[str]" = []
    in_fmt = False
    start = end = -1
    for i, line in enumerate(lines):
        s = line.strip()
        if s == "BEGIN_DATA_FORMAT":
            in_fmt = True
            continue
        if s == "END_DATA_FORMAT":
            in_fmt = False
            continue
        if in_fmt and s:
            fields = s.split()
            continue
        if s == "BEGIN_DATA":
            start = i + 1
        elif s == "END_DATA":
            end = i
            break
    if start < 0 or end < 0:
        raise SystemExit(f"{ti3} has no data block")
    try:
        ix = fields.index("XYZ_X")
        iy = fields.index("XYZ_Y")
        iz = fields.index("XYZ_Z")
    except ValueError:
        raise SystemExit(f"{ti3} carries no XYZ fields; fakeread should write them")
    row = 0
    for i in range(start, end):
        if not lines[i].strip():
            continue
        parts = lines[i].split()
        v = xyz_by_index.get(row)
        if v is not None and len(parts) > iz:
            parts[ix] = f"{v[0]:.6f}"
            parts[iy] = f"{v[1]:.6f}"
            parts[iz] = f"{v[2]:.6f}"
            lines[i] = " ".join(parts)
        row += 1
    ti3.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Filing one dated verification
# ---------------------------------------------------------------------------
def stamp(ti3: Path, when: str) -> None:
    from workflow.ti3_analysis import mark_verification_ti3
    mark_verification_ti3(ti3)
    lines = ti3.read_text(encoding="utf-8").splitlines()
    at = next(i for i, l in enumerate(lines) if l.startswith("NUMBER_OF_FIELDS"))
    lines[at:at] = ['KEYWORD "CHROMIQ_MEASURED"',
                    f'CHROMIQ_MEASURED "{when}"',
                    f'TARGET_INSTRUMENT "{INSTRUMENT}"']
    ti3.write_text("\n".join(lines) + "\n", encoding="utf-8")
    t = datetime.fromisoformat(when).timestamp()
    os.utime(ti3, (t, t))


def write_print_record(chart_dir: Path, stem: str, when: str, profile_name: str) -> None:
    """The sheet was printed through this run's own profile.

    NO ``profile_path`` and no ``profile_mtime``: those two keys are the only
    absolute paths a ChromIQ project would otherwise carry, and an absolute path
    is exactly what breaks a project that travels to another machine. Without
    them the report falls back to the run's own built profile, which it finds
    relative to the measurement.
    """
    rec = {"printed_at": when, "colour": "through-profile", "intent": "relative",
           "route": "chromiq", "source_profile": "", "profile": profile_name}
    (chart_dir / f"{stem}.print.json").write_text(
        json.dumps(rec, indent=2), encoding="utf-8")


def snapshot(vdir: Path, stem: str, src: Path) -> Path:
    """The dated check's own chart snapshot. The report prefers it over the
    shared chart, so an old date keeps being judged against the chart it was
    actually measured on. The page TIFFs are deliberately left out: they are
    page images, they are the bulk of the archive, and no report reads them."""
    cdir = vdir / "chart"
    cdir.mkdir(parents=True, exist_ok=True)
    for ext in (".ti1", ".ti2"):
        s = src / f"{stem}{ext}"
        if s.is_file():
            shutil.copy2(s, cdir / s.name)
    return cdir


# ---------------------------------------------------------------------------
# The dated series
# ---------------------------------------------------------------------------
@dataclass
class Date:
    vid: str
    when: str
    title: str
    story: str
    design: Design
    expect: "list[str]"          # row ids intended to cross their limit


ROW_TITLES = {
    "all_de00_avg": "All patches, average",
    "best95_de00_avg": "Best 95 % of patches, average",
    "worst5_de00_avg": "Worst 5 % of patches, average",
    "all_de00_max": "All patches, largest",
    "all_de00_p95": "All patches, 95th percentile",
    "grey_balance_neutral_ramp_avg": "Grey balance of the grey ramp, average",
    "grey_balance_neutral_ramp_max": "Grey balance of the grey ramp, largest",
    "ramps_30_70_dl_max": "Single-colour ramps 30 % to 70 %, largest lightness difference",
}


def _d(vid, when, title, story, design, expect) -> Date:
    return Date(vid, when, title, story, design, expect)


#: THE CENTREPIECE. Judged with ChromIQ default: 2.0 on the three averages,
#: 3.0 on the two maxima, and the grey pair as recommended values of 1.5 and
#: 3.0 (exceeding a recommended value reads COND, never FAIL). Every date that
#: crosses is followed by one that recovers.
SERIES_DEFAULT: "list[Date]" = [
    _d("2026-01-05_100000", "2026-01-05T10:00:00",
       "Everything inside its limit",
       "The healthy baseline. Nothing crosses; the column reads PASS.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50),
       []),
    _d("2026-01-19_100000", "2026-01-19T10:00:00",
       "One patch goes badly wrong",
       "A single patch at 4.5 pushes 'All patches, largest' over 3.0. The "
       "worst-5 % average stays under 2.0 because the other patches in that "
       "band did not move. ONE row crosses.",
       Design(bulk=0.80, shoulder=1.40, peak=4.50, tail=1.50, grey_dch=0.50),
       ["all_de00_max"]),
    _d("2026-02-02_100000", "2026-02-02T10:00:00",
       "The bad patch is gone again",
       "The same sheet without the outlier. 'All patches, largest' is back "
       "inside 3.0 and the column reads PASS again.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50),
       []),
    _d("2026-02-16_100000", "2026-02-16T10:00:00",
       "The hardest colours all drift together",
       "The worst 5 % of patches average about 2.7, over their limit of 2.0, "
       "while the largest single value stays under 3.0. ONE row crosses.",
       Design(bulk=0.80, shoulder=1.40, peak=2.75, tail=2.65, grey_dch=0.50),
       ["worst5_de00_avg"]),
    _d("2026-03-02_100000", "2026-03-02T10:00:00",
       "The hardest colours come back",
       "The worst-5 % average is back under 2.0. PASS again.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50),
       []),
    _d("2026-03-16_100000", "2026-03-16T10:00:00",
       "The whole sheet drifts",
       "The bulk of the chart moves up to just under its own limit and the "
       "worst 5 % go to 2.98, just under theirs. Between them they carry the "
       "all-patch average over 2.0. TWO rows cross, which is the most this "
       "design allows.",
       Design(bulk=2.0, shoulder=2.40, peak=2.98, tail=2.98,
              target_best95=1.98, grey_dch=1.20, n_shoulder=6),
       ["all_de00_avg", "worst5_de00_avg"]),
    _d("2026-03-30_100000", "2026-03-30T10:00:00",
       "The sheet settles",
       "Back to the baseline. Both rows recover together.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50),
       []),
    _d("2026-04-13_100000", "2026-04-13T10:00:00",
       "The greys pick up a cast",
       "Every grey on the ramp is 1.8 off in chroma, over the recommended 1.5, "
       "which reads COND rather than FAIL. The worst-5 % average goes with it "
       "and cannot be held back: 1.8 of chroma error on a neutral IS a colour "
       "difference of 2.55, the grey ramp is most of the worst 5 % of this "
       "chart, and their limit is 2.0. TWO rows cross. Isolated-Rows run 4 "
       "shows the grey average crossing on its own, with a column that allows "
       "for this.",
       Design(bulk=0.80, shoulder=1.00, tail=1.00, grey_dch=1.80),
       ["grey_balance_neutral_ramp_avg", "worst5_de00_avg"]),
    _d("2026-04-27_100000", "2026-04-27T10:00:00",
       "The cast is corrected",
       "The grey ramp is back to 0.5 and the recommended value is met again.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50),
       []),
    _d("2026-05-11_100000", "2026-05-11T10:00:00",
       "One grey step is badly wrong",
       "A single grey step is 3.6 off in chroma. That crosses the recommended "
       "3.0 on the grey maximum, and the same patch is far enough out to carry "
       "'All patches, largest' over 3.0 with it. TWO rows cross, and this pair "
       "cannot be separated: a grey cast this size along a* is over 2.0 as a "
       "colour difference too, which the note further down works out.",
       Design(bulk=0.80, shoulder=1.10, peak=1.50, tail=1.40,
              grey_dch=0.40, grey_spike=3.60),
       ["grey_balance_neutral_ramp_max", "all_de00_max"]),
    _d("2026-05-25_100000", "2026-05-25T10:00:00",
       "The grey step is fixed",
       "The spike is gone. Both rows recover on the same date.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50),
       []),
]

#: run2 of the first project: the SAME kind of sheet, judged with ChromIQ
#: tight (1.0 / 1.0 / 1.0 / 1.5 / 1.5). A sheet that passes comfortably under
#: the default column fails here, which is the whole point of having more than
#: one column.
SERIES_TIGHT: "list[Date]" = [
    _d("2026-02-10_113000", "2026-02-10T11:30:00",
       "Good enough for the default column, not for this one",
       "Exactly the numbers of run 1's healthy baseline, which passed there. "
       "Against ChromIQ tight the worst-5 % average and the largest value are "
       "both over their limits. TWO rows cross.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50),
       ["worst5_de00_avg", "all_de00_max"]),
    _d("2026-03-10_113000", "2026-03-10T11:30:00",
       "Tightened up until this column is happy",
       "Everything roughly halved. Nothing crosses, even against the tight "
       "column.",
       Design(bulk=0.40, shoulder=0.70, peak=1.10, tail=0.90, grey_dch=0.30),
       []),
    _d("2026-04-10_113000", "2026-04-10T11:30:00",
       "One patch out, tight column",
       "A single patch at 2.4 crosses 'All patches, largest' (1.5) on its own, "
       "with the worst-5 % average held just under 1.0. ONE row crosses.",
       Design(bulk=0.40, shoulder=0.70, peak=2.40, tail=0.75, grey_dch=0.30),
       ["all_de00_max"]),
]

#: run3 of the first project: exactly ONE dated verification, so the limit set
#: can still be chosen. Knut asked for a run in this state by name: *"Some runs
#: must only have one verification run, so that settings can be changed."*
SERIES_ONE_DATE: "list[Date]" = [
    _d("2026-06-01_090000", "2026-06-01T09:00:00",
       "The only measurement this run has",
       "One dated verification and nothing else, judged by Quick check "
       "(4 on the three averages, 6 on the two maxima, and the grey pair as "
       "recommended values of 3 and 7: seven rows, not the five this line "
       "used to name). The report window still offers the limit set, "
       "because one measurement is not yet a history to keep comparable.",
       Design(bulk=1.10, shoulder=2.20, peak=3.60, tail=3.00, grey_dch=0.70),
       []),
]

#: run3 of the second project: the history that WOULD lock the run, with the
#: lock lifted by hand. Put it beside Threshold-Series/run2, which has the same
#: kind of history and was never unlocked, and the pair says what the lock does.
SERIES_TWO_DATES_UNLOCKED: "list[Date]" = [
    _d("2026-06-02_090000", "2026-06-02T09:00:00",
       "One patch out, and the lock lifted by hand",
       "A single patch at 1.9 crosses 'All patches, largest' (1.5) on its own, "
       "with the worst-5 % average held at 0.96, just under its limit of 1.0.",
       Design(bulk=0.40, shoulder=0.55, peak=1.90, tail=0.65, grey_dch=0.30),
       ["all_de00_max"]),
    _d("2026-06-16_090000", "2026-06-16T09:00:00",
       "The second date, which is what would normally lock the run",
       "The patch comes back to 1.2 and nothing crosses. This is the date that "
       "gives the run a history: without the hand-lifted lock the limit set "
       "would be fixed from here on, exactly as Threshold-Series/run2's is.",
       Design(bulk=0.40, shoulder=0.55, peak=1.20, tail=0.65, grey_dch=0.30),
       []),
]

#: The tone-ramp row, which NO shipped set judges at all.
#:
#: Every ChromIQ set leaves `ramps_30_70_dl_max` without a limit, so the report
#: prints its number and nothing can cross it. That makes it invisible to a
#: package built only from the shipped sets, and it was: measured over the whole
#: of this package, the seven rows a shipped set puts a number on were all
#: crossed by some date, and this one could not be. It becomes judgeable only
#: when a user types a limit into it, which is what this run's own edited column
#: does, and which is this project's whole purpose.
SERIES_RAMP: "list[Date]" = [
    _d("2026-10-05_110000", "2026-10-05T11:00:00",
       "One step of the grey ramp is too dark",
       "The middle step of the grey tone ramp is 3.0 too dark, over the 2.0 "
       "this run's own column asks for. Every colour-difference limit is "
       "relaxed to 9.0, so the lightness error this puts on that one patch "
       "crosses nothing else. ONE row crosses.",
       Design(bulk=0.60, shoulder=0.90, peak=1.40, tail=1.10, grey_dch=0.40,
              ramp_dl=3.0),
       ["ramps_30_70_dl_max"]),
    _d("2026-10-19_110000", "2026-10-19T11:00:00",
       "The ramp comes back",
       "The same step is 1.0 out, inside the 2.0 limit. The row recovers and "
       "nothing else moved.",
       Design(bulk=0.60, shoulder=0.90, peak=1.40, tail=1.10, grey_dch=0.40,
              ramp_dl=1.0),
       []),
]

#: Rows that cannot cross alone under any shipped set, isolated by
#: giving the run its own edited column. See the README.
SERIES_BEST95: "list[Date]" = [
    _d("2026-07-06_140000", "2026-07-06T14:00:00",
       "The bulk of the chart is over its limit",
       "The best 95 % of patches average 2.4, over the 2.0 this run's own "
       "column asks for, while the deliberately relaxed all-patch, worst-5 %, "
       "largest and 95th-percentile limits stay comfortable. ONE row crosses.",
       Design(bulk=2.4, shoulder=2.70, peak=3.20, tail=2.90,
              target_best95=2.40, grey_dch=1.00),
       ["best95_de00_avg"]),
    _d("2026-07-20_140000", "2026-07-20T14:00:00",
       "The bulk comes back inside",
       "The best-95 % average drops to 1.5. The row recovers and nothing else "
       "changed.",
       Design(bulk=1.5, shoulder=1.80, peak=2.20, tail=2.00,
              target_best95=1.50, grey_dch=1.00),
       []),
]

SERIES_P95: "list[Date]" = [
    _d("2026-08-03_140000", "2026-08-03T14:00:00",
       "The 95th percentile crosses",
       "The value at the 95th percentile is 3.6, over the 3.0 this run's own "
       "column asks for, while the deliberately relaxed averages and maximum "
       "stay comfortable. ONE row crosses.",
       Design(bulk=1.00, shoulder=3.60, peak=4.20, tail=3.90,
              grey_dch=0.80, n_shoulder=4),
       ["all_de00_p95"]),
    _d("2026-08-17_140000", "2026-08-17T14:00:00",
       "The 95th percentile comes back",
       "The shoulder of the distribution drops to 2.0 while the worst few "
       "patches are left exactly where they were. The row recovers on its own.",
       Design(bulk=1.00, shoulder=2.00, peak=4.20, tail=3.90,
              grey_dch=0.80, n_shoulder=4),
       []),
]

#: run4 of the second project: the grey-balance AVERAGE on its own. A grey
#: cast big enough to cross the recommended 1.5 also lifts the worst-5 %
#: average past 2.0 under a stock column, because ΔE00 near a neutral is about
#: 1.41 times the plain chroma difference (measured: ΔCh 1.8 gives ΔE00 2.55,
#: ΔCh 3.6 gives 4.82) and the grey ramp is most of this chart's worst 5 %.
#: This run's own column relaxes the four ΔE rows so the grey row stands alone.
SERIES_GREY_AVG: "list[Date]" = [
    _d("2026-08-31_150000", "2026-08-31T15:00:00",
       "A grey cast, and only the grey row says so",
       "The grey ramp is 1.9 off in chroma, over the recommended 1.5. This "
       "run's own column relaxes the colour-difference rows to 6 and 9 so the "
       "cast is not counted twice. ONE row crosses, and it reads COND because "
       "it is a recommendation, not a requirement.",
       Design(bulk=0.80, shoulder=1.00, tail=1.00, grey_dch=1.90),
       ["grey_balance_neutral_ramp_avg"]),
    _d("2026-09-14_150000", "2026-09-14T15:00:00",
       "The cast is corrected",
       "The grey ramp is back to 0.6 and the recommendation is met again.",
       Design(bulk=0.80, shoulder=1.00, tail=1.00, grey_dch=0.60),
       []),
]

#: The third project: ONE measurement, three columns. The two designs below are
#: used unchanged in all three runs, so the only thing that differs between
#: those reports is the limit set. This project deliberately does NOT hold to
#: "at most two rows at once": showing a whole column go over is the point of
#: it. The row-by-row isolation lives in the first two projects.
COMPARE_MILD = Design(bulk=0.85, shoulder=1.30, peak=2.40, tail=1.50,
                      grey_dch=0.60)
COMPARE_DRIFTED = Design(bulk=1.60, shoulder=2.40, peak=3.40, tail=2.60,
                         grey_dch=1.20)

_C1 = ("2026-09-07_160000", "2026-09-07T16:00:00", "The shared measurement",
       "The same designed sheet as the other two runs of this project. Only "
       "the limit set differs.")
_C2 = ("2026-09-21_160000", "2026-09-21T16:00:00",
       "The shared measurement, drifted",
       "The same sheet a fortnight later, everything a little worse. Again "
       "the only difference between the three runs is the column.")

SERIES_COMPARE_DEFAULT: "list[Date]" = [
    _d(*_C1, COMPARE_MILD, []),
    _d(*_C2, COMPARE_DRIFTED, ["worst5_de00_avg", "all_de00_max"]),
]
SERIES_COMPARE_TIGHT: "list[Date]" = [
    _d(*_C1, COMPARE_MILD, ["worst5_de00_avg", "all_de00_max"]),
    _d(*_C2, COMPARE_DRIFTED,
       ["all_de00_avg", "best95_de00_avg", "worst5_de00_avg",
        "all_de00_max", "all_de00_p95",
        # tight recommends 1.0 on the grey average, not the default's 1.5
        "grey_balance_neutral_ramp_avg"]),
]
SERIES_COMPARE_QUICK: "list[Date]" = [
    _d(*_C1, COMPARE_MILD, []),
    _d(*_C2, COMPARE_DRIFTED, []),
]


# ---------------------------------------------------------------------------
# Building a run
# ---------------------------------------------------------------------------
#: What a run demonstrates about the limit lock, and the sentence that says so.
#:
#: These sentences are NOT written by hand into a description. A challenge
#: round found run3 of the first project describing itself as "Limits bound and
#: LOCKED" when ``is_locked()`` returned False for it, because the lock rule had
#: since gained a second condition and the prose had not moved. Shared demo data
#: that misdescribes itself is worse than none: every later round is told to
#: trust it. So the sentence is derived from ``RunPlan.lock`` and ``build_run``
#: refuses to write a run whose real state disagrees with it.
LOCK_SENTENCES = {
    "locked": "Limits bound and LOCKED: two or more dated verifications, and "
              "the lock was never lifted.",
    "unlocked": "Limits bound, and the lock lifted by hand: this run has the "
                "history that would otherwise fix its limit set.",
    "one-date": "One dated verification only, so the limit set can still be "
                "chosen: one measurement is not yet a history to keep "
                "comparable.",
}


@dataclass
class RunPlan:
    description: str
    profile_chart: ChartRecipe
    verify_chart: ChartRecipe
    set_id: str
    dates: "list[Date]"
    edited_limits: "dict[str, float] | None" = None
    unlocked: bool = False
    note: str = ""
    lock: str = "locked"

    @property
    def full_description(self) -> str:
        """The run's description with its lock state appended, in that order."""
        return f"{self.description} {LOCK_SENTENCES[self.lock]}"

    def lock_complaint(self) -> str:
        """Why this plan cannot produce the lock state it claims, or ""."""
        n = len(self.dates)
        if self.lock not in LOCK_SENTENCES:
            return f"unknown lock state {self.lock!r}"
        if self.lock == "one-date":
            if n != 1:
                return f"claims one-date and has {n} dated verifications"
            if self.unlocked:
                return "claims one-date and also lifts the lock, which says two things"
        elif n < 2:
            return f"claims {self.lock!r} and has only {n} dated verification(s)"
        elif self.unlocked != (self.lock == "unlocked"):
            return (f"claims {self.lock!r} with unlocked={self.unlocked}")
        return ""


def build_run(proj, run, plan: RunPlan, cache_root: Path,
              results: list) -> None:
    from workflow.compliance_sets import Limit, row_verdict, set_summary
    from workflow.measurement_report import (build_report, rewrite_report,
                                             save_report, row_values,
                                             stamp_verdict)
    from workflow.run_compliance import (bind_run, run_limits, set_run_limits,
                                         set_run_unlocked)

    run.ensure_dir()
    stem = run.stem
    print(f"  {run.id}: profiling chart, {plan.profile_chart.label}")
    make_chart(run.dir, stem, plan.profile_chart, cache_root)
    build_profile(run.dir, stem)
    icc = run.built_profile_icc()

    print(f"  {run.id}: verification chart, {plan.verify_chart.label}")
    make_chart(run.verifications_dir, run.verify_stem, plan.verify_chart, cache_root)

    meta = run.load_meta()
    meta.description = plan.full_description
    meta.instrument = INSTRUMENT
    meta.paper = "Demo matte 200 g"
    meta.status = "complete"
    meta.verify_chart_notes = plan.note
    run.save_meta(meta)

    # The binding. bind_run copies the set's numbers onto the run, exactly as
    # the first verification measurement does in the app.
    limits_rec = bind_run(run, plan.set_id, {},
                          when=datetime.fromisoformat(plan.dates[0].when))
    if plan.edited_limits:
        edited = dict(limits_rec.limits)
        for rid, v in plan.edited_limits.items():
            base = edited.get(rid)
            edited[rid] = (Limit.should(v) if (base is not None and base.is_should)
                           else Limit.value(v))
        set_run_limits(run, edited)
        limits_rec = run_limits(run, {})
    if plan.unlocked:
        set_run_unlocked(run, True)
        limits_rec = run_limits(run, {})

    vstem = run.verify_stem
    gamut = in_gamut_flags(run.verifications_dir / f"{vstem}.ti2", icc)
    print(f"  {run.id}: {sum(gamut.values())} of {len(gamut)} chart colours are "
          f"within the profile's gamut and therefore judged")
    for date in plan.dates:
        v = run.verification(date.vid)
        v.ensure_dir()
        work = v.dir / "_work"
        work.mkdir(exist_ok=True)
        for ext in (".ti1", ".ti2"):
            shutil.copy2(run.verifications_dir / f"{vstem}{ext}", work / f"{vstem}{ext}")
        ti3 = fakeread(work, vstem, icc)
        predicted = apply_design(ti3, work / f"{vstem}.ti2", date.design, gamut)
        stamp(ti3, date.when)
        shutil.move(str(ti3), str(v.dir / f"{vstem}.ti3"))
        cdir = snapshot(v.dir, vstem, work)
        write_print_record(cdir, vstem, date.when, icc.name)
        shutil.rmtree(work)

        # The report, built by the app's own code, saved under the measurement
        # date rather than the moment this script ran.
        rep = build_report(v.measurement_ti3, argyll_bin=ARGYLL)
        stamp_verdict(rep, limits_rec.limits, set_id=limits_rec.set_id,
                      set_label=limits_rec.label_en, edited=limits_rec.edited)
        save_report(rep, v.dir)
        for old in sorted(v.reports_dir.glob("report_*.json")):
            old.unlink()
        when_dt = datetime.fromisoformat(date.when)
        rewrite_report(v.reports_dir / f"report_{when_dt:%Y-%m-%d_%H-%M-%S}.json", rep)

        actual = _crossed_rows(rep, limits_rec.limits, row_values, row_verdict,
                               set_summary)
        results.append({
            "project": "",
            "run": run.id,
            "set": limits_rec.label_en + (" (edited for this run)"
                                          if limits_rec.edited else ""),
            "date": date.vid,
            "title": date.title,
            "story": date.story,
            "intended": list(date.expect),
            "actual": actual["crossed"],
            "verdict": actual["overall"],
            "values": actual["values"],
            "predicted": predicted,
        })
        flag = "OK " if sorted(actual["crossed"]) == sorted(date.expect) else "!! "
        print(f"    {flag}{date.vid}  {actual['overall']:<5} "
              f"intended={date.expect} actual={actual['crossed']}")

    # The run is finished, so ask the SHIPPED rule what it made, rather than
    # trusting the plan. This is the check that was missing when the lock rule
    # gained its second condition and run3's description went on claiming a
    # state the code no longer produced.
    from workflow.run_compliance import is_bound, is_locked, measured_dates
    really = is_locked(run)
    if really != (plan.lock == "locked") or not is_bound(run):
        raise SystemExit(
            f"{run.id} claims lock={plan.lock!r} and its description says so, "
            f"but the app reads bound={is_bound(run)}, "
            f"dates={measured_dates(run)}, locked={really}. Fix the plan or "
            f"the sentence, never the description alone.")


def _crossed_rows(report, limits, row_values, row_verdict, set_summary) -> dict:
    """Which rows the REAL report says are over their limit."""
    from workflow.compliance_sets import COND, FAIL, ROW_BY_ID
    from workflow.measurement_report import is_graded_sheet
    graded_sheet = is_graded_sheet(report)
    vals = row_values(report)
    crossed, values, rows = [], {}, []
    for rid, lim in limits.items():
        if rid not in ROW_BY_ID:
            continue
        info = vals.get(rid) or {}
        val = info.get("value")
        graded = graded_sheet if info.get("graded") is None else bool(info["graded"])
        word = row_verdict(lim, val, graded)
        rows.append((lim, word))
        if lim.is_numeric and val is not None:
            values[rid] = round(float(val), 3)
        if word in (FAIL, COND):
            crossed.append(rid)
    summary = set_summary(rows, set_is_iso=False, graded=graded_sheet)
    return {"crossed": sorted(crossed), "values": values, "overall": summary.word}


# ---------------------------------------------------------------------------
# The projects
# ---------------------------------------------------------------------------
PROJECTS = [
    ("Report-Limits-Threshold-Series", [
        RunPlan("The dated series: every judged row crosses on one date and "
                "recovers on the next.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_default", SERIES_DEFAULT,
                note="The series chart. Do not regenerate it: every date is "
                     "judged against its own snapshot of this chart."),
        RunPlan("The same kind of sheet judged with ChromIQ tight.",
                CHART_LARGE, CHART_WIDE, "chromiq_tight", SERIES_TIGHT),
        RunPlan("The small chart, measured once.",
                CHART_SMALL, CHART_SMALL, "chromiq_quick", SERIES_ONE_DATE,
                lock="one-date"),
    ]),
    ("Report-Limits-Isolated-Rows", [
        RunPlan("Best 95 % average isolated by this run's own edited column.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_default", SERIES_BEST95,
                edited_limits={"all_de00_avg": 6.0, "worst5_de00_avg": 8.0,
                               "best95_de00_avg": 2.0, "all_de00_max": 9.0,
                               "all_de00_p95": 9.0}),
        RunPlan("95th percentile isolated by this run's own edited column.",
                CHART_WIDE, CHART_MEDIUM, "chromiq_default", SERIES_P95,
                edited_limits={"all_de00_avg": 9.0, "worst5_de00_avg": 9.0,
                               "best95_de00_avg": 9.0, "all_de00_max": 9.0,
                               "all_de00_p95": 3.0}),
        RunPlan("The small chart, measured twice.",
                CHART_SMALL, CHART_SMALL, "chromiq_tight",
                SERIES_TWO_DATES_UNLOCKED, unlocked=True, lock="unlocked"),
        RunPlan("Grey balance average isolated by this run's own edited column.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_default", SERIES_GREY_AVG,
                edited_limits={"all_de00_avg": 6.0, "worst5_de00_avg": 6.0,
                               "best95_de00_avg": 6.0, "all_de00_max": 9.0,
                               "all_de00_p95": 9.0}),
        RunPlan("The tone-ramp row, which no shipped set judges, given a "
                "limit by this run's own edited column.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_default", SERIES_RAMP,
                edited_limits={"all_de00_avg": 9.0, "worst5_de00_avg": 9.0,
                               "best95_de00_avg": 9.0, "all_de00_max": 9.0,
                               "all_de00_p95": 9.0,
                               "ramps_30_70_dl_max": 2.0}),
    ]),
    ("Report-Limits-Set-Compare", [
        RunPlan("The shared measurement judged with ChromIQ default.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_default", SERIES_COMPARE_DEFAULT),
        RunPlan("The shared measurement judged with ChromIQ tight.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_tight", SERIES_COMPARE_TIGHT),
        RunPlan("The shared measurement judged with Quick check.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_quick", SERIES_COMPARE_QUICK),
    ]),
]


def build_project(dest: Path, name: str, plans: "list[RunPlan]",
                  cache_root: Path, results: list,
                  lock_rows: "list[dict] | None" = None) -> Path:
    from core.file_manager import Project
    from workflow.run_compliance import is_locked, measured_dates
    root = dest / name
    if root.exists():
        shutil.rmtree(root)
    print(f"== {name}")
    proj = Project.create(root, name)
    run = proj.current_run()
    for i, plan in enumerate(plans):
        if i:
            run = proj.new_run()
        before = len(results)
        build_run(proj, run, plan, cache_root, results)
        for r in results[before:]:
            r["project"] = name
        if lock_rows is not None:
            lock_rows.append({
                "run": f"{name.replace('Report-Limits-', '')}/{run.id}",
                "dates": measured_dates(run),
                "lifted": bool(run.load_meta().compliance_unlocked),
                "locked": is_locked(run),
                "claimed": plan.lock,
                "edited": bool(plan.edited_limits),
            })
    return root


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dest", nargs="?", default=str(_HERE.parent / "demo-projects" / FOLDER))
    ap.add_argument("--zip", action="store_true",
                    help="also write <dest>.zip beside the folder")
    ap.add_argument("--report", default="",
                    help="write the intended/actual table as JSON to this path")
    args = ap.parse_args(argv)

    if not (ARGYLL / "targen").exists() or not SRGB.exists():
        print(f"ArgyllCMS with ref/sRGB.icm is required ({ARGYLL}).")
        return 2

    dest = Path(args.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    cache_root = dest / "_charts"
    cache_root.mkdir(exist_ok=True)

    bad_plans = [(n, i + 1, c)
                 for n, plans in PROJECTS
                 for i, plan in enumerate(plans)
                 if (c := plan.lock_complaint())]
    for n, i, c in bad_plans:
        print(f"  PLAN {n}/run{i}: {c}")
    if bad_plans:
        return 2

    results: list = []
    lock_rows: list = []
    for name, plans in PROJECTS:
        build_project(dest, name, plans, cache_root, results, lock_rows)
    shutil.rmtree(cache_root, ignore_errors=True)

    cov = coverage(dest, results)
    (dest / "README.txt").write_text(readme(results, lock_rows, cov, dest),
                                     encoding="utf-8")
    (dest / "intended-vs-actual.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8")
    if args.report:
        Path(args.report).write_text(json.dumps(results, indent=2), encoding="utf-8")

    bad = [r for r in results if sorted(r["intended"]) != sorted(r["actual"])]
    print(f"\n{len(results)} dated verifications, "
          f"{len(results) - len(bad)} matching their design.")
    for r in bad:
        print(f"  MISMATCH {r['project']}/{r['run']}/{r['date']}: "
              f"intended {r['intended']} actual {r['actual']}")

    if args.zip:
        archive = dest.parent / f"{dest.name}"
        made = shutil.make_archive(str(archive), "zip", root_dir=str(dest.parent),
                                   base_dir=dest.name)
        size = Path(made).stat().st_size
        print(f"archive: {made}  ({size / 1e6:.1f} MB)")
    print(f"written to {dest}")
    return 1 if bad else 0


#: Small numbers as words, for a heading that must agree with a computed list.
_WORDS = {0: "no", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
          6: "six", 7: "seven", 8: "eight"}

#: Rows that are ordered against another row, and therefore cannot cross their
#: limit while that other row stays inside its own. The ORDER is a fact about
#: the statistics; whether it forces a second crossing depends on the NUMBERS,
#: so it is read from the shipped sets rather than asserted.
_ORDERED_UNDER = {
    "best95_de00_avg": "worst5_de00_avg",
    "all_de00_avg": "worst5_de00_avg",
    "all_de00_p95": "all_de00_max",
}


def _forced_pairs() -> "list[tuple[str, str]]":
    """`(row, why)` for every row that cannot cross alone under every set.

    THE COUNT IN THIS README HAS BEEN WRONG TWICE, in both directions: it
    claimed three rows and one of them was direction-dependent, then claimed
    two and missed one that really is forced. So it is computed. A row counts
    only when EVERY shipped set gives its companion a limit no larger than its
    own, which is what makes the crossing unavoidable rather than merely
    likely.
    """
    from workflow.compliance_sets import SET_BY_ID, effective_limits
    sets = [sid for sid in SET_BY_ID if sid.startswith("chromiq_")]
    out: "list[tuple[str, str]]" = []
    for rid, other in _ORDERED_UNDER.items():
        forced = True
        for sid in sets:
            lim = effective_limits(sid, {})
            a_, b_ = lim.get(rid), lim.get(other)
            if (a_ is None or b_ is None
                    or a_.number is None or b_.number is None
                    or b_.number > a_.number):
                forced = False
                break
        if forced and sets:
            out.append((rid, ROW_TITLES.get(other, other)
                        + " crossing at the same time"))
    return out


def _chart_label(dest: Path, project: str, run_id: str, recipe,
                 verify: bool = False) -> str:
    """The recipe's label with the patch count the BUILT chart really carries.

    Falls back to the label when the sheet cannot be read, and says so rather
    than quietly printing the requested number as though it were measured.
    """
    import re as _re
    if dest is None:
        return recipe.label
    d = dest / project / "runs" / run_id
    if verify:
        d = d / "verifications"
    try:
        ti2 = next(iter(sorted(d.glob("*.ti2"))), None)
        if ti2 is None:
            return recipe.label
        m = _re.search(r"^NUMBER_OF_SETS\s+(\d+)", ti2.read_text(
            encoding="utf-8", errors="replace"), _re.M)
        if not m:
            return recipe.label
        real = int(m.group(1))
    except OSError:
        return recipe.label
    if real == recipe.patches:
        return recipe.label
    return _re.sub(r"^\d+", str(real), recipe.label, count=1) + \
        f" (asked for {recipe.patches}; printtarg padded)"


def _lock_index(lock_rows: "list[dict]") -> "list[tuple[str, str]]":
    """The three lock lines of the README's index, named from MEASURED state.

    These three lines were hand-written, and a challenge round found them still
    saying "exactly one dated verification, LOCKED ... Threshold-Series, run3"
    after the lock rule had changed and after that run had gained a twin with
    two dates. The table forty lines above them was already correct and read
    back from the app; the index contradicted it on the same page, and the index
    is the half a reader acts on, because it says which run to open.

    The guard added with that table did not cover this, because it bans the word
    "lock" from a plan's DESCRIPTION and these lines are prose in the README.
    So they are generated too, and from the same measured rows.
    """
    want = [("locked, so the set cannot be changed", lambda r: r["locked"]),
            ("one date only, so the set is still offered",
             lambda r: not r["locked"] and r["dates"] < 2),
            ("two dates, but the lock lifted by hand",
             lambda r: not r["locked"] and r["dates"] >= 2 and r["lifted"])]
    out: "list[tuple[str, str]]" = []
    for label, pick in want:
        # The SIMPLEST example of each state, so the reader opens the run where
        # the state is the only interesting thing rather than the busiest one.
        # An unedited column first, then the fewest dates, and only then the
        # name: sorting by size alone landed the locked line on a run whose own
        # README entry says "(edited for this run)", which is a second thing to
        # explain in a line that exists to demonstrate one.
        hits = sorted((r for r in lock_rows if pick(r)),
                      key=lambda r: (r.get("edited", False), r["dates"], r["run"]))
        if hits:
            out.append((label, hits[0]["run"].replace("/", ", ")))
    return out


def coverage(dest: Path, results: list) -> dict:
    """Which report rows these projects actually exercise, read back from the
    saved reports rather than from the designs that asked for them.

    A challenge round's rule: a row no date ever crosses is a row on which a
    clean verdict proves nothing, so it has to be NAMED rather than counted as
    covered. This is what names it.
    """
    from core.file_manager import Run
    from workflow.measurement_report import row_values
    from workflow.run_compliance import run_limits

    with_value: set = set()
    for rep in sorted(dest.rglob("report_*.json")):
        for rid, info in (row_values(json.loads(rep.read_text(encoding="utf-8")))
                          or {}).items():
            if info.get("value") is not None:
                with_value.add(rid)

    # WHICH ROWS ARE JUDGED IS READ FROM THE RUNS, NOT FROM WHAT CROSSED.
    # Deriving it from the crossings would make this check answer itself: a row
    # that stopped crossing would also stop counting as judged, and the summary
    # would go on saying nothing is untested.
    judged: set = set()
    for pd in sorted(dest.glob("Report-Limits-*")):
        for rd in sorted((pd / "runs").glob("run*")):
            for rid, lim in run_limits(Run.for_dir(rd), {}).limits.items():
                if lim.number is not None:
                    judged.add(rid)
    judged &= with_value

    crossed: set = set()
    for r in results:
        crossed |= set(r["actual"])
    # AND HOW MANY A SHIPPED SET JUDGES, which is a different number from how
    # many any run judges: one run's edited column adds the tone-ramp row. The
    # README stated both, one typed and one computed, and they disagreed.
    from workflow.compliance_sets import SET_BY_ID, effective_limits
    shipped: set = set()
    for sid in SET_BY_ID:
        if not sid.startswith("chromiq_"):
            continue
        for rid, lim in effective_limits(sid, {}).items():
            if lim.number is not None:
                shipped.add(rid)
    return {"with_value": sorted(with_value), "judged": sorted(judged),
            "shipped_judged": sorted(shipped & with_value),
            "crossed": sorted(crossed & with_value),
            "uncrossed": sorted(judged - crossed)}


def readme(results: list, _lock_rows: "list[dict]", _cov: dict,
           dest: "Path | None" = None) -> str:
    from workflow.compliance_sets import ROW_BY_ID
    lines: list = []
    a = lines.append
    a("ChromIQ Measurement Report: the limit demo projects")
    a("=" * 52)
    a("")
    a("Built by scripts/make_report_limit_demos.py for issue #182.")
    a("")
    a("TWO WAYS IN, AND THE FIRST IS USUALLY THE RIGHT ONE")
    a("---------------------------------------------------")
    a("")
    a("1. DOWNLOAD this folder as the zip attached to the beta release, unzip")
    a("   it anywhere, and point ChromIQ at it: Settings, output folder, pick")
    a("   the unzipped folder. All three projects then appear in the project")
    a("   list. Nothing inside a project names a folder on the machine that")
    a("   built it, so it opens the same wherever it lands.")
    a("")
    a("2. GENERATE it yourself, if you want the data to match a ChromIQ newer")
    a("   than the archive:")
    a("")
    a("       .venv/bin/python scripts/make_report_limit_demos.py")
    a("")
    a("   ArgyllCMS 3.5.0 in /Applications/Argyll is required. The whole set")
    a("   builds in about fifteen seconds and is deterministic: the same")
    a("   command on the same Argyll gives the same numbers, every time.")
    a("   (Timed on the machine that wrote this: 12.8 s, cold, all three")
    a("   projects.)")
    a("")
    a("   Prefer the download when you just want to look at reports. Prefer")
    a("   generating when the report code has moved on and you want the saved")
    a("   verdicts rebuilt against it.")
    a("")
    a("WHAT IS IN HERE")
    a("---------------")
    a("")
    a("Three projects. Each project holds several profile runs, and each")
    a("profile run holds its own chart, its own profile, and its dated")
    a("verifications.")
    a("")
    for name, plans in PROJECTS:
        a(f"  {name}")
        for i, plan in enumerate(plans, start=1):
            a(f"      run{i}  {plan.description}")
            # THE COUNT IS READ OFF THE SHEET, NOT OFF THE REQUEST.
            # `ChartRecipe.label` is typed beside the number asked for, and
            # printtarg PADS: two of the eleven runs ship charts of 168 and 405
            # patches under labels saying 156 and 400. The other nine agree,
            # which is exactly why a typed label survived this long.
            a(f"            profile chart "
              f"{_chart_label(dest, name, f'run{i}', plan.profile_chart)}, "
              f"verification chart "
              f"{_chart_label(dest, name, f'run{i}', plan.verify_chart, True)}")
        a("")
    a("WHICH RUNS ARE LOCKED, AND WHY")
    a("------------------------------")
    a("")
    a("A run's limit set is fixed, and the report window stops offering it,")
    a("once two conditions are both true: the set has been copied onto the run")
    a("by a first verification measurement, and the run has at least TWO dated")
    a("verifications. One measurement is not yet a history, so at that point")
    a("the set can still be chosen. The lock can also be lifted by hand.")
    a("")
    a("Every line below was read back from the built projects with the app's")
    a("own is_locked(), not copied from the plan that asked for it.")
    a("")
    a(f"  {'run':<34}{'dates':>6}  {'lifted':<7}{'locked':<7}")
    for row in _lock_rows:
        a(f"  {row['run']:<34}{row['dates']:>6}  "
          f"{'yes' if row['lifted'] else 'no':<7}"
          f"{'YES' if row['locked'] else 'no':<7}")
    a("")
    a("All three states are present on purpose, and the index further down")
    a("this file names a run for each of them, from the same measured rows as")
    a("the table above. THEY ARE NOT LISTED AGAIN HERE. The last version of")
    a("this file answered the question twice, once from a generated line and")
    a("once from a hand-written one, and the hand-written half named a run")
    a("with three dated verifications as the example of a run with two.")
    a("")
    a("HOW THE MEASUREMENTS WERE MADE")
    a("------------------------------")
    a("")
    a("Every chart is a real ArgyllCMS chart and every profile is a real")
    a("colprof profile built from a real fakeread measurement. Every dated")
    a("verification begins as a real fakeread of that run's verification chart")
    a("through that run's own profile.")
    a("")
    a("A designed drift is then applied on top, patch by patch. Each patch")
    a("keeps the direction of the error fakeread produced through the real")
    a("profile; only the size of that error is scaled, so that the chart's")
    a("statistics land exactly where the date's design says. That is what lets")
    a("one row cross its limit on one date while the others stay put, and it")
    a("is why the table below matches. Random noise cannot do that: it moves")
    a("every statistic at once.")
    a("")
    a("WHICH ROWS ARE COVERED, AND WHICH CANNOT BE")
    a("-------------------------------------------")
    a("")
    a("A report has thirty rows and most of them cannot be filled in from an")
    a("ordinary printed sheet at all: they belong to a standard's own control")
    a("strip, or ask about fading, gloss or repeat measurements. The rows that")
    a("matter here are the ones a ChromIQ verification sheet puts a NUMBER on,")
    a("and of those, the ones some limit set actually judges.")
    a("")
    a(f"  rows a ChromIQ verification sheet computes : {len(_cov['with_value'])}")
    a(f"  of those, judged by a limit somewhere      : {len(_cov['judged'])}")
    a(f"  of those, crossed by at least one date     : {len(_cov['crossed'])}")
    a("")
    if _cov["uncrossed"]:
        a("NOT CROSSED BY ANY DATE, so a clean verdict on these proves nothing:")
        for rid in _cov["uncrossed"]:
            a(f"  {ROW_TITLES.get(rid, rid)}")
    else:
        a("Every row that can be judged is crossed by at least one date, and")
        a("comes back inside its limit on another. Nothing here is untested.")
    a("")
    a("One of them needed a run of its own. No shipped limit set judges the")
    a("30 to 70 % tone ramps, so that row prints a number nothing can cross;")
    a("Isolated-Rows/run5 gives it a limit in the run's own edited column,")
    a("which is the only way a user can have it judged either.")
    a("")
    a("WHICH DATE CROSSES WHICH LIMIT")
    a("------------------------------")
    a("")
    a("'Crossed' means the report gave that row FAIL (over a required limit)")
    a("or COND (over a recommended one). Intended is what the design asked")
    a("for; actual is what the report read back after it was built.")
    a("")
    cur = None
    for r in results:
        head = f"{r['project']} / {r['run']}"
        if head != cur:
            cur = head
            a("")
            a(head)
            a(f"  judged against: {r['set']}")
        a("")
        a(f"  {r['date']}   {r['title']}")
        a(f"      {r['story']}")
        if r["intended"]:
            a("      intended to cross: "
              + ", ".join(ROW_TITLES.get(x, x) for x in r["intended"]))
        else:
            a("      intended to cross: nothing")
        if r["actual"]:
            a("      actually crossed:  "
              + ", ".join(ROW_TITLES.get(x, x) for x in r["actual"]))
        else:
            a("      actually crossed:  nothing")
        a(f"      the report's word for the column: {r['verdict']}")
    a("")
    a("")
    a("WHAT A CLEAN VERDICT HERE DOES NOT PROVE")
    a("----------------------------------------")
    a("")
    a(f"{_WORDS.get(len(_cov['shipped_judged']), len(_cov['shipped_judged'])).capitalize()} "
      f"rows of the report can be judged by a SHIPPED limit set")
    a("today: the five all-patch colour differences and the two grey-balance")
    a("rows. An edited column can judge one more, which is what")
    a("Isolated-Rows/run5 is for, and that is why the count below is larger.")
    a("")
    a("The other rows in the table are there and are honest, but no limit set")
    a("this ChromIQ ships puts a number on them, so they never carry a verdict")
    a("and this data cannot make them cross:")
    a("")
    for rid, row in ROW_BY_ID.items():
        if rid in ROW_TITLES:
            continue
        why = {"ref": "needs a reference file for the printing condition",
               "unknown": "the limit is in a clause ChromIQ does not hold",
               "unmeasurable": row.note or "ChromIQ cannot measure it",
               "build": "computed, but no shipped set puts a limit on it",
               "now": "computed, but no shipped set puts a limit on it",
               }.get(row.status, row.status)
        a(f"  {row.label}: {why}")
    a("")
    a(f"So a green column in these projects means the "
      f"{_WORDS.get(len(_cov['judged']), len(_cov['judged']))} judged rows")
    a("passed, counting the row an edited column adds. Both numbers in this")
    a("section are computed from the sets themselves; one of them used to be")
    a("typed, and the two disagreed.")
    a("It does not mean the rest were checked.")
    a("")
    _forced = _forced_pairs()
    _n = _WORDS.get(len(_forced), str(len(_forced)))
    a(f"{_n.upper()} ROWS CANNOT CROSS ALONE UNDER A STOCK COLUMN, AND A")
    a("FURTHER ONE DEPENDS ON WHICH WAY THE CAST GOES")
    a("-" * 68)
    a("")
    a("THE COUNT HAS BEEN WRONG TWICE, in both directions, AND THEN THE")
    a("HEADING WAS WRONG A THIRD TIME while the list under it was right,")
    a("because the list was computed and the number above it was typed. Both")
    a("come from the same place now. A row cannot cross alone when another row")
    a("is forced over its own limit at the same moment.")
    a("")
    a(f"{_n.capitalize()} of them by arithmetic, and the reason is that the")
    a("three averages are ordered: 'Best 95 % of patches, average' is always")
    a("less than or equal to 'All patches, average', which is always less than")
    a("or equal to 'Worst 5 % of patches, average'. Every shipped set gives")
    a("those three the SAME number, so:")
    a("")
    for _rid, _why in _forced:
        a(f"  {ROW_TITLES.get(_rid, _rid)}")
        a(f"      cannot cross without {_why}")
    a("")
    a("The rest of the numeric rows can cross by themselves, because nothing")
    a("above them in an ordering has a limit small enough to be dragged over")
    a("with them.")
    a("")
    a("The further one is the grey-balance average, and it depends on WHICH")
    a("WAY the cast goes, which the first version of this note did not say.")
    a("")
    a("The grey rows are measured in chroma difference and the others in")
    a("colour difference, and near a neutral those are not the same size. But")
    a("the ratio is not one number. Measured with the app's own CIEDE2000, at")
    a("every lightness:")
    a("")
    a("    chroma 1.8   ->   2.545 along a*,   1.730 along b*")
    a("    chroma 3.6   ->   4.815 along a*,   3.330 along b*")
    a("")
    a("The rescaling is CIEDE2000's own, and it is a* that it stretches. So a")
    a("cast toward red or green of 1.8 does put every grey patch over 2.0,")
    a("while the same size of cast toward yellow or blue leaves them at 1.73,")
    a("under it. THE GREY AVERAGE CAN THEREFORE CROSS ALONE, on a b* cast,")
    a("which is why it is not in the computed list above.")
    a("")
    a("These projects build an a* cast, which is why the pairing holds in")
    a("them: Threshold-Series 2026-04-13 shows it, with two rows crossing.")
    a("Isolated-Rows/run4 shows the grey average crossing alone, and it gets")
    a("there with an edited column rather than by choosing the direction.")
    a("")
    _edited = [f"run{i}" for i, _p in enumerate(
        dict(PROJECTS)["Report-Limits-Isolated-Rows"], start=1) if _p.edited_limits]
    a("Report-Limits-Isolated-Rows exists for the rows that cannot. "
      + ", ".join(_edited[:-1]) + " and " + _edited[-1] + " each")
    a("carry their own edited limit column that relaxes the companion rows, so")
    a("the row of interest crosses on its own and can be looked at alone.")
    a("")
    a("REPORT TYPES ARE NOT IN HERE, AND THAT IS NOT AN OVERSIGHT")
    a("---------------------------------------------------------")
    a("")
    a("The request asked for verifications that use different report TYPES as")
    a("well as different limits. Report types are a design at the moment, not")
    a("a feature: nothing in this ChromIQ can select one. The data is built so")
    a("that when they arrive, no new measurements are needed. Every dated")
    a("verification keeps its own chart snapshot, its own measurement and its")
    a("own saved report, so a report type can be applied to what is already")
    a("here.")
    a("")
    a("FOR THE NEXT PERSON WHO NEEDS A REPORT WITH DATED VERIFICATIONS")
    a("--------------------------------------------------------------")
    a("")
    a("Open one of these rather than inventing another set. Which one:")
    a("")
    a("  a row crossing and then recovering ......... Threshold-Series, run1")
    a("  many dated verifications on one run ........ Threshold-Series, run1")
    a("  a second limit set on the same kind of sheet  Threshold-Series, run2")
    for _what, _where in _lock_index(_lock_rows):
        a(f"  {(_what + ' '):.<44} {_where}")
    a("  a run with its own edited limit column ..... Isolated-Rows, runs 1, 2, 4, 5")
    a("  one measurement judged three ways .......... Set-Compare, all runs")
    a("  the grey AVERAGE crossing on its own ...... Isolated-Rows, run4")
    a("  a row no shipped set judges at all ......... Isolated-Rows, run5")
    a("  a recommended value (COND, not FAIL) ....... Isolated-Rows, run4")
    a("")
    a("DO NOT edit these in place if the data is to stay reproducible. In")
    a("particular do not regenerate a verification chart: each dated check is")
    a("judged against its own chart/ snapshot, and replacing the shared chart")
    a("makes the two disagree. Copy the project folder, work on the copy, or")
    a("run the generator again. Regenerating is cheap: see the timing above.")
    a("")
    a("Page TIFFs of the charts are included for the profile and verification")
    a("charts themselves, but not inside the dated snapshots: no report reads")
    a("them and they are most of the weight. printtarg rebuilds them from the")
    a("chart's .ti1 at any time.")
    a("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
