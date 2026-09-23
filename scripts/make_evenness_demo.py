#!/usr/bin/env python3
"""A demo project for evenness across the sheet (#182, Knut, 2026-09-22).

No project in the report-limit demo pack can show the two evenness rows
JUDGED: every verification chart in it is a ColorMunki A4 or A3 chart with 6
or 7 strips on a page, under Knut's 9 by 9 floor. This builds one project that
can, beside the pack, so the rows can be driven on screen:

* **run1**, Knut's 837-patch i1Pro A4 preset with no clip border, laid out
  by the layout engine (its patches cover 80 % of the page, about 90 in each
  ninth), measured four times:

  1. evenly printed: both rows PASS;
  2. a drift across the strips, about 2.2 ΔE b* from one side to the other:
     the pairwise row FAILs first, the from-the-mean row still passes;
  3. one ninth of the page 1.35 L* lighter, a blotch: the from-the-mean row
     FAILs first, the pairwise row still passes;
  4. a noisy sheet, no place effect at all: both rows N-A, the noise named;

* **run2**, Knut's 84-patch i1Pro3 A4 preset (7 strips): both rows N-A
  because no page has 9 strips;
* **run3**, the 837-patch chart again with no verification measured, so the
  Measure tab's pre-flight is due on it;
* **run4** (#182 E2, beta 38), Knut's 572-patch i1Pro A4 preset: 22 strips by
  26 rows, but with the i1Pro's 26 mm clip border and its 38 mm top its
  patches cover 68 % of the page, under the 75 % floor, so both rows N-A;
* **run5** (#182 E4, beta 38), Knut's 308-patch i1Pro 3 Plus A4 preset on two
  pages, 11 strips by 14 rows each: the grid and the noise estimate would let
  it be judged, and its patches cover 65 % of each page, so both rows N-A.

The readings are SYNTHETIC: each patch is the chart's own aim plus the
residual named above, so what every area should read is known in advance. The
profile beside each run is Argyll's own sRGB profile, standing in for a built
one so the report's in-gamut split has a referee. This is a picture of the
report's behaviour, not a measurement of any printer.

    python scripts/make_evenness_demo.py <dest-folder>
"""
from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

NAME = "Report-Limits-Evenness"
ARGYLL = Path(os.environ.get("CHROMIQ_ARGYLL_BIN", "/Applications/Argyll/bin"))
SRGB = ARGYLL.parent / "ref" / "sRGB.icm"
LARGE = "i1_w75max_a4_837p_1page_portrait_w7_5mm_maximised_no_clip_border"
SMALL = "p3_a4_84p_1page_portrait_w25_0mm"
#: #182 E2: 22 x 26 on one page, 68.4 % of it covered.
UNCOVERED = "i1_w8_a4_572p_1page_portrait_w8_0mm"
#: #182 E4: i1Pro 3 Plus, two pages of 11 x 14, 65.3 % of each covered.
P3_TWO_PAGES = "p3_a4_308p_2pages_portrait_w16_0mm"

#: (vid, when, title, residual(page, strip on page, row, strips, rows, rng))
_SIGMA = 0.25


def _even(page, s, r, S, R, rng):
    return rng.normal(0, _SIGMA, 3)


def _drift(page, s, r, S, R, rng):
    d = rng.normal(0, _SIGMA, 3)
    d[2] += (s / (S - 1) - 0.5) * 2.2
    return d


def _blotch(page, s, r, S, R, rng):
    import workflow.measurement_report as MR
    a, m, _ = MR.evenness_bands(S)
    ra, rm, _ = MR.evenness_bands(R)
    d = rng.normal(0, _SIGMA, 3)
    if s >= a + m and r >= ra + rm:
        d[0] += 1.35
    return d


def _noisy(page, s, r, S, R, rng):
    return rng.normal(0, 2.4, 3)


DATES_LARGE = [
    ("2026-10-01_100000", "2026-10-01T10:00:00", "even", _even),
    ("2026-10-08_100000", "2026-10-08T10:00:00", "drift across the strips",
     _drift),
    ("2026-10-15_100000", "2026-10-15T10:00:00", "one area lighter", _blotch),
    ("2026-10-22_100000", "2026-10-22T10:00:00", "noisy", _noisy),
]
DATES_SMALL = [
    ("2026-10-01_110000", "2026-10-01T11:00:00", "even", _even),
]
DATES_UNCOVERED = [
    ("2026-10-01_120000", "2026-10-01T12:00:00", "even", _even),
]
DATES_P3 = [
    ("2026-10-01_130000", "2026-10-01T13:00:00", "even", _even),
]


def _preset(slug: str):
    from ui.tabs.tab_chart import KNUT_PRESETS
    return next(p for p in KNUT_PRESETS if p.slug == slug)


def _lay_out(slug: str, folder: Path, stem: str) -> Path:
    """The preset's chart, laid out by the engine as Create Chart lays it
    out, as ``folder/stem.ti1/.ti2/.tif``."""
    from core.resource_path import resource_path
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    p = _preset(slug)
    ti1 = Path(resource_path(p.ti1_asset))
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ti1, folder / f"{stem}.ti1")
    from dataclasses import replace
    # A FIXED SEED, so the demo lays the same patches out the same way on
    # every build and its numbers can be quoted.
    rec = replace(LayoutRecipe.from_dict(dict(p.layout_recipe)), seed=182,
                  randomize=True)
    res, _ = build_from_recipe(str(folder / f"{stem}.ti1"), str(folder / stem),
                               rec)
    # THE GEOMETRY THE APP RECORDS (#182 E2). Create Chart folds the engine's
    # strips.json and the recipe into channels.json
    # (`ChartCreator._embed_layout_geometry`); "Measured from Preview" and the
    # evenness rows' page coverage read it from there.
    import json
    from dataclasses import asdict
    lay = json.loads((folder / f"{stem}.strips.json").read_text(
        encoding="utf-8"))
    lay.update({"engine": "chromiq", "engine_version": 1, "seed": res.seed,
                "recipe": asdict(rec)})
    (folder / f"{stem}.channels.json").write_text(
        json.dumps({"layout": lay}), encoding="utf-8")
    return Path(res.ti2_path)


def _sheet(ti2: Path, out: Path, residual, seed: int, instrument: str,
           when: str) -> Path:
    """A measured `.ti3` of *ti2*: every patch its aim plus *residual*."""
    import numpy as np
    import workflow.measurement_report as MR
    from workflow.ti3_analysis import _lab_to_xyz_array, parse_ti3
    aims = MR._reference_labs(ti2)
    grid = MR.chart_grid(ti2)
    chart = parse_ti3(ti2)
    rng = np.random.default_rng(seed)
    rows = []
    rgb = MR._rgb_to_0_100(np.asarray(chart.rgb, float))
    for i, sid in enumerate(chart.sample_ids):
        page, s, r = grid["slot"][sid]
        d = residual(page, s, r, grid["pages"][page], grid["rows"], rng)
        lab = np.asarray(aims[sid]) + d
        lab[0] = min(lab[0], 100.0)
        x = _lab_to_xyz_array(lab[None])[0]
        rows.append(f"{sid} {rgb[i][0]:.4f} {rgb[i][1]:.4f} {rgb[i][2]:.4f} "
                    f"{x[0]:.5f} {x[1]:.5f} {x[2]:.5f}")
    text = "\n".join([
        "CTI3", "", 'DESCRIPTOR "Argyll Calibration Target chart information 3"',
        'ORIGINATOR "ChromIQ evenness demo (synthetic readings)"',
        f'TARGET_INSTRUMENT "{instrument}"', 'DEVICE_CLASS "OUTPUT"',
        'COLOR_REP "RGB_XYZ"', 'KEYWORD "CHROMIQ_MEASURED"',
        f'CHROMIQ_MEASURED "{when}"', "", "NUMBER_OF_FIELDS 7",
        "BEGIN_DATA_FORMAT", "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
        "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA",
        *rows, "END_DATA", ""])
    out.write_text(text, encoding="utf-8")
    t = datetime.fromisoformat(when).timestamp()
    os.utime(out, (t, t))
    return out


def _run(proj, run, slug: str, instrument: str, description: str,
         dates: list, seed0: int) -> list:
    import make_report_limit_demos as DEMO
    from workflow.measurement_report import (KIND_PROFILING, KIND_VERIFICATION,
                                             build_report, stamp_verdict)
    from workflow.run_compliance import bind_run, run_limits
    from workflow.ti3_analysis import mark_verification_ti3
    run.ensure_dir()
    stem, vstem = run.stem, run.verify_stem
    print(f"  {run.id}: {slug}")
    ti2 = _lay_out(slug, run.dir, stem)
    shutil.copy2(SRGB, run.dir / f"{stem}.icc")
    vti2 = _lay_out(slug, run.verifications_dir, vstem)
    meta = run.load_meta()
    meta.description = description
    meta.instrument = instrument
    meta.paper = "Demo matte 200 g"
    meta.status = "complete"
    run.save_meta(meta)
    first = datetime.fromisoformat(dates[0][1] if dates
                                   else "2026-10-01T09:00:00")
    limits = (bind_run(run, "chromiq_default", {}, when=first) if dates
              else run_limits(run, {}, "chromiq_default"))
    prof_when = (first - timedelta(days=7)).isoformat(timespec="seconds")
    prof = _sheet(ti2, run.dir / f"{stem}.ti3", _even, seed0, instrument,
                  prof_when)
    rep = build_report(prof, argyll_bin=ARGYLL)
    stamp_verdict(rep, limits.limits, set_id=limits.set_id,
                  set_label=limits.label_en, edited=limits.edited)
    DEMO.file_report(rep, prof, run, KIND_PROFILING, prof_when)
    out = []
    for k, (vid, when, title, residual) in enumerate(dates, start=1):
        v = run.verification(vid)
        v.ensure_dir()
        ti3 = _sheet(vti2, v.dir / f"{vstem}.ti3", residual, seed0 + k,
                     instrument, when)
        mark_verification_ti3(ti3)
        cdir = DEMO.snapshot(v.dir, vstem, run.verifications_dir)
        DEMO.write_print_record(cdir, vstem, when, f"{stem}.icc",
                                "through-profile")
        # ABSOLUTE colorimetric, so the report judges in absolute Lab. With a
        # white-mapping intent the report divides every reading by the sheet's
        # lightest patch, and a demo whose "one area lighter" happens to hold
        # that patch would then shift every colour by its own amount: a real
        # effect, and not the one this demo is about.
        import json
        pj = cdir / f"{vstem}.print.json"
        rec = json.loads(pj.read_text(encoding="utf-8"))
        rec["intent"] = "absolute"
        pj.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        rep = build_report(v.measurement_ti3, argyll_bin=ARGYLL)
        stamp_verdict(rep, limits.limits, set_id=limits.set_id,
                      set_label=limits.label_en, edited=limits.edited)
        DEMO.file_report(rep, v.measurement_ti3, run, KIND_VERIFICATION, when)
        ev = rep.get("evenness") or {}
        from workflow.measurement_report import recorded_verdict
        words = {r["row_id"]: r["word"] for r in recorded_verdict(rep)["rows"]
                 if r["row_id"] in ("uniformity_sd",
                                    "uniformity_de00_max_from_mean")}
        line = (f"    {vid} {title:<24} pairwise={ev.get('pairwise')} "
                f"(noise {ev.get('noise_pairwise_p95')}) from_mean="
                f"{ev.get('from_mean')} (noise {ev.get('noise_from_mean_p95')}) "
                f"reason={ev.get('reason')} words={words}")
        print(line)
        out.append(line)
    return out


def build(dest: Path) -> Path:
    from core.file_manager import Project
    root = dest / NAME
    if root.exists():
        shutil.rmtree(root)
    dest.mkdir(parents=True, exist_ok=True)
    print(f"== {NAME}")
    proj = Project.create(root, NAME)
    run1 = proj.current_run()
    _run(proj, run1, LARGE, "X-Rite i1Pro 2",
         "An 837-patch i1Pro sheet with no clip border, its patches covering "
         "80 % of the page, measured four times: evenly printed, with a drift "
         "across the strips, with one area lighter, and noisy.",
         DATES_LARGE, 100)
    run2 = proj.new_run()
    _run(proj, run2, SMALL, "X-Rite i1Pro 3",
         "An 84-patch sheet with 7 strips on its page, fewer than the 9 "
         "evenness across the sheet needs.", DATES_SMALL, 200)
    run3 = proj.new_run()
    _run(proj, run3, LARGE, "X-Rite i1Pro 2",
         "The same 837-patch chart as run 1, not measured yet: what the Measure "
         "tab says before the first verification.", [], 300)
    run4 = proj.new_run()
    _run(proj, run4, UNCOVERED, "X-Rite i1Pro 2",
         "A 572-patch i1Pro sheet, 22 strips by 26 rows, whose patches cover "
         "68 % of the page.", DATES_UNCOVERED, 400)
    run5 = proj.new_run()
    _run(proj, run5, P3_TWO_PAGES, "X-Rite i1Pro 3 Plus",
         "A 308-patch i1Pro 3 Plus chart on two pages, 11 strips by 14 rows "
         "each, whose patches cover 65 % of each page.", DATES_P3, 500)
    return root


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # no window: files only
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    build(Path(sys.argv[1]).resolve())
