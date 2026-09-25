#!/usr/bin/env python3
"""A demo project whose one chart answers every metric.

A chart built FROM PROFILE GAMUT that answers all 18 metrics the window
"Which presets can be used for verification?" counts, and the two
repeatability metrics besides, so every metric the report can compute is seen
judged on one chart, passing and failing. It is built beside the other
projects of the release package:

* **run1**, a profile built from an ordinary 210-patch chart printed on a
  baryta paper, and a verification chart built FROM PROFILE GAMUT through that
  profile: 632 colours chosen from the profile's own gamut, 8 of them printed
  a second time, and the 8 cube corners, 648 patches, laid out by the layout
  engine with the built-in "A4-648p-1page-Portrait-w7.5mm" i1Pro preset (24
  strips by 27 rows on one A4 page, 69 % of it covered). That chart answers
  every one of the 18 metrics, and both of ChromIQ's own repeatability
  metrics as well, because it repeats 8 colours and it is measured three
  times. Every report is judged against Custom ISO 12647-8, the set that puts
  a limit on all 20:

  1. **everything inside its limit**: all 20 metrics PASS, except "Maximum
     ΔE00, the same chart measured again", which is N-A on a first
     measurement;
  2. **the same chart measured again**, as evenly: all 20 PASS, the
     repeated measurement included;
  3. **everything over its limit**: all 20 FAIL. Every colour is 5 ΔE00 off
     its aim (lighter, and yellower), the solids further and turned in hue,
     the paper yellowed, the second print of each repeated colour further
     off than the first, and the sheet drifts from one side to the other,
     which the two evenness metrics catch.

The readings are SYNTHETIC: each patch is what the report compares it with
plus a designed residual, so what every metric should read is known in
advance, and the build refuses a date whose report says otherwise. The
profile, the chart and its colorimetric reference are real (ArgyllCMS and
ChromIQ's own FROM PROFILE GAMUT module). This is a picture of the report's
behaviour, not a measurement of any printer.

    python scripts/make_every_metric_demo.py <dest-folder>
"""
# Asked for by Knut, #182 5832026677 (2026-09-25), K40-3: "Do you want a demo
# project with such a chart added to the demo package?" "yes". The docstring
# above is printed in the package README, so it carries no references.
from __future__ import annotations

import json
import math
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import numpy as np                                             # noqa: E402

NAME = "Report-Limits-Every-Metric"
ARGYLL = Path(os.environ.get("CHROMIQ_ARGYLL_BIN", "/Applications/Argyll/bin"))
#: The built-in preset whose layout the chart takes: one A4 page, i1Pro,
#: 24 strips by 27 rows, the 648 patches K39-8 measured answering 17 of 18.
PRESET = "i1_w75_a4_648p_1page_portrait_w7_5mm"
#: The limit set every report of the run is judged against: the one that
#: puts a number on all twenty metrics ChromIQ can compute.
SET_ID = "custom_iso_12647_8"
#: 632 colours from the profile, 8 of them twice, and the 8 corners: 648.
GAMUT_COLOURS = 632
REPEATS = 8
PAPER = "baryta"
INSTRUMENT = "X-Rite i1Pro 2"

#: What each date is designed to read, row by row (the words `judge` gives).
PASS_ALL = "PASS"
FAIL_ALL = "FAIL"


@dataclass(frozen=True)
class Date:
    vid: str
    when: str
    title: str
    #: residual size on every ordinary patch (ΔE00 off its aim), 0 = none
    shift_de: float
    #: noise, per L*, a*, b* component
    sigma: float
    #: drift across the strips, b* from one side of the sheet to the other
    drift_b: float
    #: the hue turn of the C, M and Y solids, and the extra ΔE00 of the solids
    solid_dh: float
    solid_de: float
    #: ΔE00 of the paper off its reference
    paper_de: float
    #: extra ΔE00 of the second print of each repeated colour
    repeat_de: float
    word: str


DATES = [
    Date("2026-11-02_100000", "2026-11-02T10:00:00",
         "Everything inside its limit",
         0.0, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, PASS_ALL),
    Date("2026-11-09_100000", "2026-11-09T10:00:00",
         "The same chart measured again",
         0.0, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, PASS_ALL),
    Date("2026-11-16_100000", "2026-11-16T10:00:00",
         "Everything over its limit",
         5.0, 0.25, 5.0, 4.0, 5.0, 4.0, 3.5, FAIL_ALL),
]

#: The rows the report judges on this run: every row ChromIQ can compute.
def judged_rows() -> "list[str]":
    from workflow.compliance_sets import ROWS
    return [r.id for r in ROWS if r.status in ("now", "build", "ref")]


def _de(a, b) -> float:
    from workflow.ti3_analysis import ciede2000
    return float(ciede2000(tuple(a), tuple(b)))


def _solve(ref, direction, target: float) -> tuple:
    """*ref* moved along *direction* until it is *target* ΔE00 from *ref*."""
    import make_report_limit_demos as DEMO
    if target <= 0:
        return tuple(ref)
    s = DEMO._solve_scale(ref, direction, target)
    return tuple(ref[i] + s * direction[i] for i in range(3))


def _rotate(lab, dh: float) -> tuple:
    """*lab* with its hue turned so that ΔH*ab is *dh*."""
    L, a, b = (float(v) for v in lab)
    c = math.hypot(a, b)
    if c < 1e-6 or dh <= 0:
        return (L, a, b)
    th = 2.0 * math.asin(min(1.0, dh / (2.0 * c)))
    h = math.atan2(b, a) + th
    return (L, c * math.cos(h), c * math.sin(h))


# ---------------------------------------------------------------------------
# The chart
# ---------------------------------------------------------------------------
def _preset():
    from ui.tabs.tab_chart import KNUT_PRESETS
    return next(p for p in KNUT_PRESETS if p.slug == PRESET)


def _profile(run_dir: Path, stem: str, cache: Path) -> Path:
    """The run's own profile: an ordinary 210-patch chart, read through
    ArgyllCMS's sRGB as the bare printer on a baryta paper, and colprof."""
    import make_report_limit_demos as DEMO
    # `make_chart` remembers where it built each chart size for the rest of
    # the process, and *cache* is a temporary folder removed after this run:
    # the limit generator, built next in the same process, must not be sent
    # to a folder that is gone (measured: it was, and the package build died).
    before = dict(DEMO._chart_cache)
    try:
        DEMO.make_chart(run_dir, stem, DEMO.CHART_MEDIUM, cache)
    finally:
        DEMO._chart_cache.clear()
        DEMO._chart_cache.update(before)
    DEMO.build_profile(run_dir, stem, DEMO.paper_lab_of(PAPER))
    return run_dir / f"{stem}.icc"


def _gamut_chart(folder: Path, stem: str, icc: Path):
    """The FROM PROFILE GAMUT chart, through the app's own module, with
    REPEATS of its colours printed twice, laid out by the layout engine as
    the preset lays it out. Returns ``(ti2, selection, repeated ids)``."""
    from workflow.gamut_target import (select_gamut_targets,
                                       write_colorimetric_reference,
                                       write_gamut_ti1)
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    sel = select_gamut_targets(icc, GAMUT_COLOURS, "safe", "absolute",
                               bin_dir=ARGYLL)
    n = len(sel.targets)
    if n < GAMUT_COLOURS:
        raise SystemExit(f"the profile's gamut gave {n} colours, fewer than "
                         f"the {GAMUT_COLOURS} this chart is designed on")
    # THE REPEATS: eight colours spread through the selection, printed a
    # second time with the same ink amounts, so "Maximum ΔE00, repeat patches
    # on one sheet" has eight groups of two to read.
    picks = [sel.targets[int(k * n / REPEATS)] for k in range(REPEATS)]
    sel.targets = list(sel.targets) + list(picks)
    folder.mkdir(parents=True, exist_ok=True)
    write_gamut_ti1(sel, folder / f"{stem}.ti1")
    write_colorimetric_reference(sel, folder / f"{stem}-reference.ti3")
    p = _preset()
    rec = replace(LayoutRecipe.from_dict(dict(p.layout_recipe)), seed=182,
                  randomize=True)
    res, _ = build_from_recipe(str(folder / f"{stem}.ti1"), str(folder / stem),
                               rec)
    # the geometry Create Chart records, which the page coverage reads
    from dataclasses import asdict
    lay = json.loads((folder / f"{stem}.strips.json").read_text(
        encoding="utf-8"))
    lay.update({"engine": "chromiq", "engine_version": 1, "seed": res.seed,
                "recipe": asdict(rec)})
    (folder / f"{stem}.channels.json").write_text(
        json.dumps({"layout": lay, "colorimetric_reference": True}),
        encoding="utf-8")
    repeated = [str(n + 1 + k) for k in range(REPEATS)]
    _record_verify_settings(folder, rec)
    return Path(res.ti2_path), sel, repeated


def _record_verify_settings(folder: Path, rec) -> None:
    """The Create Chart settings the app stores for a chart it built FROM
    PROFILE GAMUT and laid out with the layout engine, so the chart opens on
    what it is (the pack's rule, `make_report_limit_demos.
    record_chart_settings`, for an engine chart)."""
    from core.file_manager import Run
    store = Run.for_dir(folder)
    meta = store.load_meta()
    meta.create_chart_settings = {
        "printtarg-i": {"enabled": True, "value": rec.instrument},
        "printtarg-p": {"enabled": True, "value": rec.paper},
    }
    meta.create_chart_ui = {"mode": "gamut", "engine_on": True,
                            "guided": {"instrument": rec.instrument,
                                       "paper": rec.paper, "pages": 1,
                                       "double_density": False,
                                       "triple_density": False,
                                       "left_border": True,
                                       "no_strip_limit": False,
                                       "precond": ""},
                            "engine_recipe": replace(rec, seed=None).to_dict()}
    store.save_meta(meta)


# ---------------------------------------------------------------------------
# A measured sheet
# ---------------------------------------------------------------------------
#: Where an ordinary patch moves on the date that designs a shift: lighter
#: and yellower, the way a print that has dried down on a warm paper does.
_SHIFT = (0.55, 0.15, 0.82)
#: Where the paper moves: yellower, never darker (a paper stays the lightest
#: patch on the sheet).
_PAPER_SHIFT = (0.0, 0.12, 0.99)


def _sheet(ti2: Path, out: Path, d: Date, seed: int, *, cref: dict,
           strip_aims: dict, paper_white: tuple, repeated: "list[str]",
           originals: "dict[str, str]", when: str) -> Path:
    import make_report_limit_demos as DEMO
    import workflow.measurement_report as MR
    from workflow.ti3_analysis import _lab_to_xyz_array, parse_ti3
    rng = np.random.default_rng(seed)
    grid = MR.chart_grid(ti2)
    chart = parse_ti3(ti2)
    rgb = MR._rgb_to_0_100(np.asarray(chart.rgb, float))
    aims = {str(k): tuple(v) for k, v in cref["labs"].items()}
    corners = set(str(c) for c in cref.get("corner_ids") or ())
    paper_ids = set(MR.paper_corner_ids(cref))
    budgets = DEMO._corner_budgets(_limits())
    labs = {}
    for sid in chart.sample_ids:
        aim = aims[sid]
        page, s, r = grid["slot"][sid]
        S = grid["pages"][page]
        noise = rng.normal(0.0, d.sigma, 3)
        drift = np.array([0.0, 0.0, (s / (S - 1) - 0.5) * d.drift_b])
        if sid in paper_ids:
            # the paper: its reference is the profile's own paper white
            base = _solve(paper_white, _PAPER_SHIFT, d.paper_de)
            lab = np.asarray(base, float) + np.array([0.0, 0.0, 0.0])
        elif sid in corners:
            # §34 (K37 i): a solid (C, M, Y, one ink off) and the black are
            # judged against their IDEAL value by the corner rows and against
            # the profile's PREDICTION by the control strip, so they go
            # between the two (`_between_two_aims`); the overprints R, G, B
            # (two inks off) are judged only in the strip and go on the
            # prediction, which is what a printer prints.
            pred = strip_aims.get(sid)
            dev = [float(x) for x in (cref.get("devices") or {}).get(sid, ())]
            overprint = sum(1 for x in dev if x <= 0.5) == 2
            if pred is not None and overprint:
                base = tuple(pred)
            elif pred is not None:
                base = DEMO._between_two_aims(aim, pred, None, budgets)
            else:
                base = aim
            base = _rotate(base, d.solid_dh)
            base = _solve(base, _SHIFT, d.solid_de) if d.solid_de else base
            lab = np.asarray(base, float) + noise * 0.4
        else:
            base = _solve(aim, _SHIFT, d.shift_de)
            if sid in repeated and d.repeat_de:
                base = _solve(base, (-0.3, 0.9, 0.3), d.repeat_de)
            lab = np.asarray(base, float) + noise + drift
        lab[0] = min(float(lab[0]), 100.0)
        labs[sid] = lab
    # the paper stays the lightest patch on the sheet
    ceiling = min(float(labs[s][0]) for s in paper_ids) - 0.3 if paper_ids \
        else 100.0
    for sid, lab in labs.items():
        if sid not in paper_ids and lab[0] > ceiling:
            lab[0] = ceiling
    rows = []
    for i, sid in enumerate(chart.sample_ids):
        x = _lab_to_xyz_array(np.asarray(labs[sid])[None])[0]
        rows.append(f"{sid} {rgb[i][0]:.4f} {rgb[i][1]:.4f} {rgb[i][2]:.4f} "
                    f"{x[0]:.5f} {x[1]:.5f} {x[2]:.5f}")
    text = "\n".join([
        "CTI3", "", 'DESCRIPTOR "Argyll Calibration Target chart information 3"',
        'ORIGINATOR "ChromIQ every-metric demo (synthetic readings)"',
        f'TARGET_INSTRUMENT "{INSTRUMENT}"', 'DEVICE_CLASS "OUTPUT"',
        'COLOR_REP "RGB_XYZ"', 'KEYWORD "CHROMIQ_MEASURED"',
        f'CHROMIQ_MEASURED "{when}"', "", "NUMBER_OF_FIELDS 7",
        "BEGIN_DATA_FORMAT", "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
        "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA",
        *rows, "END_DATA", ""])
    out.write_text(text, encoding="utf-8")
    t = datetime.fromisoformat(when).timestamp()
    os.utime(out, (t, t))
    return out


def _limits():
    from workflow.compliance_sets import effective_limits
    return effective_limits(SET_ID, {})


# ---------------------------------------------------------------------------
# The project
# ---------------------------------------------------------------------------
def build(dest: Path) -> "list[str]":
    """Build the project into *dest*. Returns one line per date, and stops
    the build when a date's report does not read as designed."""
    import make_report_limit_demos as DEMO
    from core.file_manager import Project
    from workflow.compliance_sets import SET_BY_ID
    from workflow.gamut_target import (profile_media_white_lab,
                                       read_colorimetric_reference)
    from workflow.measurement_report import (KIND_PROFILING, KIND_VERIFICATION,
                                             REPORT_TYPE_FULL, build_report,
                                             corner_predictions_through,
                                             recorded_verdict, stamp_verdict)
    from workflow.run_compliance import RunLimits, set_run_default_set
    from workflow.ti3_analysis import mark_verification_ti3

    root = dest / NAME
    if root.exists():
        shutil.rmtree(root)
    dest.mkdir(parents=True, exist_ok=True)
    print(f"== {NAME}")
    proj = Project.create(root, NAME)
    run = proj.current_run()
    run.ensure_dir()
    stem, vstem = run.stem, run.verify_stem
    with tempfile.TemporaryDirectory(prefix="chromiq-every-metric-") as tmp:
        icc = _profile(run.dir, stem, Path(tmp))
    ti2, sel, repeated = _gamut_chart(run.verifications_dir, vstem, icc)
    DEMO.record_chart_settings(run.dir, "A4", DEMO._targen_settings(
        DEMO.CHART_MEDIUM), instrument="CM")
    decl = DEMO.declare_control_strip(run.verifications_dir, vstem)
    if not decl.written or not decl.selection.p95_ready:
        raise SystemExit(f"{NAME}: the chart must declare a control strip of "
                         f"20 rungs or more; ChromIQ filled "
                         f"{decl.selection.n}")
    cref = read_colorimetric_reference(
        run.verifications_dir / f"{vstem}-reference.ti3")
    strip_aims = corner_predictions_through(cref, icc, ARGYLL) or {}
    paper_white = tuple(profile_media_white_lab(icc))

    meta = run.load_meta()
    meta.description = (
        "A FROM PROFILE GAMUT chart of 648 patches on one A4 page that "
        "answers every metric, measured three times: everything inside its "
        "limit, the same chart measured again, and everything over its "
        "limit. Judged against Custom ISO 12647-8, which limits all twenty.")
    meta.instrument = INSTRUMENT
    meta.paper = DEMO.paper_name_of(PAPER)
    meta.status = "complete"
    meta.verify_chart_notes = (
        "A From-profile-gamut chart. Do not regenerate it as an ordinary "
        "chart: the colorimetric reference beside it is what makes the paper, "
        "solid and hue metrics computable.")
    run.save_meta(meta)
    set_run_default_set(run, SET_ID, "chromiq_default")
    limits = RunLimits(SET_ID, SET_BY_ID[SET_ID].label, _limits(),
                       label_en=SET_BY_ID[SET_ID].label)

    # the run's own profiling sheet keeps the report the app gives it
    first = datetime.fromisoformat(DATES[0].when)
    prof_when = (first - timedelta(days=7)).isoformat(timespec="seconds")
    DEMO.stamp_profiling(run.dir / f"{stem}.ti3", prof_when, INSTRUMENT)
    rep = build_report(run.dir / f"{stem}.ti3", argyll_bin=ARGYLL)
    stamp_verdict(rep, limits.limits, set_id=limits.set_id,
                  set_label=limits.label_en, edited=False)
    DEMO.file_report(rep, run.dir / f"{stem}.ti3", run, KIND_PROFILING,
                     prof_when)

    lines: "list[str]" = []
    want = judged_rows()
    for k, d in enumerate(DATES, start=1):
        v = run.verification(d.vid)
        v.ensure_dir()
        ti3 = _sheet(ti2, v.dir / f"{vstem}.ti3", d, 4000 + k, cref=cref,
                     strip_aims=strip_aims, paper_white=paper_white,
                     repeated=repeated, originals={}, when=d.when)
        mark_verification_ti3(ti3)
        cdir = DEMO.snapshot(v.dir, vstem, run.verifications_dir)
        # A converted chart is printed with no profile applied: the Print tab
        # forces Raw for it (§3.1a), and so does this record.
        DEMO.write_print_record(cdir, vstem, d.when, f"{stem}.icc", "raw")
        rep = build_report(v.measurement_ti3, argyll_bin=ARGYLL)
        stamp_verdict(rep, limits.limits, set_id=limits.set_id,
                      set_label=limits.label_en, edited=False)
        DEMO.file_report(rep, v.measurement_ti3, run, KIND_VERIFICATION,
                         d.when, type_id=REPORT_TYPE_FULL)
        words = {r["row_id"]: (r.get("word"), r.get("value"), r.get("reason"))
                 for r in recorded_verdict(rep)["rows"]}
        wrong = []
        for rid in want:
            w = (words.get(rid) or (None,))[0]
            expect = d.word
            if rid == "repeat_measurement_de00_max" and k == 1:
                expect = "N-A"      # nothing measured before it
            if w != expect:
                wrong.append(f"{rid}: {w} (value {words.get(rid, (0, 0))[1]}, "
                             f"{words.get(rid, (0, 0, 0))[2]}), want {expect}")
        line = (f"  {d.vid} {d.title:<32} "
                + ("as designed" if not wrong else "MISSED: " + "; ".join(wrong)))
        print(line)
        lines.append(line)
        if wrong and not os.environ.get("CHROMIQ_EVERY_METRIC_KEEP_GOING"):
            raise SystemExit(f"{NAME}/{run.id}/{d.vid} does not read as "
                             f"designed:\n  " + "\n  ".join(wrong))
    return lines


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # no window: files only
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    from workflow import compliance_sets as _cs
    os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(
        ROOT / "data" / "compliance_sets" / "iso12647.json")
    _cs.reset_iso_cache()
    build(Path(sys.argv[1]).resolve())
