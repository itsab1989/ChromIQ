#!/usr/bin/env python3
"""A demo project that reaches every N-A reason the report can print (#182 G12).

Knut, 2026-09-22 (5774852534): *"Yes, check that all notes are printed."* The
report-limit demo pack and the evenness demo between them reach about half of
the reasons a row can read N-A for. This builds ONE project, beside them, whose
runs each lack something on purpose, so every reason can be opened on screen
and saved to a PDF:

* **run1, tiny**: fifteen mid-cube colours on a 3 by 5 page: no grey patch,
  no tone ramp, fewer than 20 patches, none on the surface of the cube, a
  small most-saturated quarter, no repeated colour, no control strip, a
  design reference only, and a page too small for evenness. Its profiling
  sheet is the Printing record the G12 change is about.
* **run2, greys**: three dated charts of 144 patches: a grey ramp of five
  steps with one colour repeated, a ramp that stops short of white, and one
  that stops short of black. The charts change between the dates, so the
  second and third share too few patches with the one before.
* **run3, strip**: a control strip of five patches declared beside the chart.
* **run4, colorimetric**: a chart judged against stored Lab aims (the way a
  FROM PROFILE GAMUT chart is) that holds no patch at the cube corners, as
  such charts did before the corners were added (F4).
* **run5, evenness**: five dated sheets of one 144-patch colour set: patch
  positions no strip and row can be read from, no record of where the patches
  sit on the page, a measurement with no readings in one ninth of the page,
  patches covering 30 % of the page, and a noisy sheet.
* **run6, history**: three dated sheets whose first two reports are in the
  shapes older ChromIQ saved: one without the control-strip and evenness
  blocks whose measurement file is no longer beside it, and one whose grey
  rows were shown for information because the printing was not recorded
  (before 2026-09-13).
* **run7, no device values**: a profiling measurement with readings and no
  device values, and no chart beside it.

Every run's own "This run" column puts a number on every row ChromIQ can
measure, which is what a user does in Report limits to have every row asked;
a row the set leaves at "-" is never judged and so never carries a note.

The readings are SYNTHETIC: each patch is its aim plus a small residual, so
what every row reads is known in advance. The profile beside each run is
Argyll's own sRGB profile. A picture of the report's behaviour, not a
measurement of any printer.

    python scripts/make_notes_demo.py <dest-folder>
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

NAME = "Report-Notes-Every-Reason"
ARGYLL = Path(os.environ.get("CHROMIQ_ARGYLL_BIN", "/Applications/Argyll/bin"))
SRGB = ARGYLL.parent / "ref" / "sRGB.icm"
INSTRUMENT = "X-Rite i1Pro 2"

#: The number every row ChromIQ can measure gets in the runs' own column. The
#: rows ChromIQ default already limits keep its number.
_EXTRA_LIMITS = {
    "substrate_de00_max": 3.0, "solids_de00_max": 5.0,
    "cmy_solids_dhab_max": 5.0, "control_strip_de00_avg": 1.5,
    "control_strip_de00_max": 3.0, "control_strip_de00_p95": 2.5,
    "outer_gamut_226_de00_avg": 3.0, "surface_gamut_de00_avg": 3.0,
    "ramps_30_70_dl_max": 3.0,
}


# ---------------------------------------------------------------------------
# colours
# ---------------------------------------------------------------------------
def _aim(rgb) -> tuple:
    """The design Lab of a device colour: sRGB, D65 adapted to D50, the same
    estimate the report makes when a chart carries no XYZ of its own."""
    from workflow.i1profiler_import import _patch_xyz
    from workflow.measurement_report import _bradford_d65_to_d50
    from workflow.ti3_analysis import xyz_to_lab
    x = _bradford_d65_to_d50(*_patch_xyz(*(float(v) for v in rgb)))
    return tuple(float(v) for v in xyz_to_lab(tuple(v / 100.0 for v in x)))


def _xyz(lab) -> tuple:
    import numpy as np
    from workflow.ti3_analysis import _lab_to_xyz_array
    return tuple(float(v) for v in _lab_to_xyz_array(np.asarray(lab, float)[None])[0])


def _random_colours(n: int, seed: int, lo=5.0, hi=95.0) -> list:
    """*n* colours inside the cube, none of them grey and no two alike."""
    import numpy as np
    rng = np.random.default_rng(seed)
    out: list = []
    while len(out) < n:
        c = tuple(round(float(v), 2) for v in rng.uniform(lo, hi, 3))
        if max(c) - min(c) <= 6.0:
            continue
        if any(max(abs(a - b) for a, b in zip(c, o)) < 3.0 for o in out):
            continue
        out.append(c)
    return out


def _greys(levels) -> list:
    return [(float(v), float(v), float(v)) for v in levels]


# ---------------------------------------------------------------------------
# files
# ---------------------------------------------------------------------------
def _loc(s: int, r: int) -> str:
    from workflow.layout_engine.permutation import alpha_label
    return f"{alpha_label(s + 1)}{r + 1}"


def write_chart(path: Path, colours: list, strips: int, rows: int, *,
                seed: int = 1, bad_locations: bool = False,
                coverage: "float | None" = 0.85) -> Path:
    """A laid-out ``.ti2`` of *colours* on one page of *strips* by *rows*,
    shuffled over the slots by *seed*, with the page geometry written beside
    it when *coverage* is given (the derived rectangles a chart's files carry).

    *bad_locations* names each patch's position ``S01P01`` style, which no
    strip-and-row reading can take apart: a chart laid out by a program that
    numbers its positions its own way."""
    import numpy as np
    n = len(colours)
    assert n <= strips * rows, (n, strips, rows)
    slots = np.random.default_rng(seed).permutation(strips * rows)[:n]
    lines = ["CTI2", "", 'DESCRIPTOR "Argyll Calibration Target chart '
             'information 2"', 'ORIGINATOR "ChromIQ notes demo"',
             f'STEPS_IN_PASS "{rows}"', f'PASSES_IN_STRIPS2 "{strips}"',
             'STRIP_INDEX_PATTERN "A-Z, A-Z"',
             'PATCH_INDEX_PATTERN "0-9,@-9,@-9;1-999"',
             'INDEX_ORDER "STRIP_THEN_PATCH"', "", "NUMBER_OF_FIELDS 8",
             "BEGIN_DATA_FORMAT",
             "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i, c in enumerate(colours):
        s, r = divmod(int(slots[i]), rows)
        loc = f"S{s + 1:02d}P{r + 1:02d}" if bad_locations else _loc(s, r)
        x = _xyz(_aim(c))
        lines.append(f'{i + 1} "{loc}" {c[0]:.4f} {c[1]:.4f} {c[2]:.4f} '
                     f'{x[0]:.6f} {x[1]:.6f} {x[2]:.6f}')
    lines += ["END_DATA", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    geo = path.with_suffix(".channels.json")
    if geo.exists():
        geo.unlink()
    if coverage is not None:
        _write_geometry(path, strips, rows, coverage)
    return path


def _write_geometry(ti2: Path, strips: int, rows: int, share: float) -> None:
    """``<stem>.channels.json``: one rectangle per slot, a regular block
    centred on an A4 page and covering *share* of it (the "derived" layout a
    prebuilt chart ships, which is what the evenness rows' page coverage
    reads)."""
    import math
    w, h, dpi = 210.0, 297.0, 100
    k = dpi / 25.4
    f = math.sqrt(float(share))
    bw, bh = w * f, h * f
    x0, y0 = (w - bw) / 2.0, (h - bh) / 2.0
    pw, ph = bw / strips, bh / rows
    rects = [{"loc": f"{s}:{r}", "page": 0, "x": (x0 + s * pw) * k,
              "y": (y0 + r * ph) * k, "w": pw * k, "h": ph * k}
             for s in range(strips) for r in range(rows)]
    ti2.with_suffix(".channels.json").write_text(json.dumps(
        {"layout": {"engine": "derived", "patches": rects, "dpi": dpi,
                    "paper_mm": [w, h]}}), encoding="utf-8")


def write_reference(ti2: Path, colours: list) -> Path:
    """The stored colorimetric aims beside a chart (``<stem>-reference.ti3``),
    in the shape a FROM PROFILE GAMUT chart carries, with NO corner ids: the
    chart has no patch at a cube corner."""
    lines = ["CTI3", "", 'DESCRIPTOR "ChromIQ colorimetric reference"',
             'ORIGINATOR "ChromIQ notes demo"', 'CHROMIQ_SET_VERSION "1"',
             'CHROMIQ_INTENT "relative"', 'CHROMIQ_MARGIN "0"',
             f'CHROMIQ_MASTER_TOTAL "{len(colours)}"',
             f'CHROMIQ_IN_GAMUT "{len(colours)}"', "", "NUMBER_OF_FIELDS 7",
             "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B LAB_L LAB_A LAB_B",
             "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(colours)}",
             "BEGIN_DATA"]
    for i, c in enumerate(colours):
        L, a, b = _aim(c)
        lines.append(f"{i + 1} {c[0]:.4f} {c[1]:.4f} {c[2]:.4f} "
                     f"{L:.4f} {a:.4f} {b:.4f}")
    lines += ["END_DATA", ""]
    out = ti2.with_name(f"{ti2.stem}-reference.ti3")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_sheet(out: Path, colours: list, when: str, *, seed: int,
                sigma: float = 0.25, omit: "set | None" = None,
                device_values: bool = True) -> Path:
    """A measured ``.ti3`` of *colours*: each patch its aim plus a normal
    residual of *sigma* per component. *omit* leaves those sample ids out of
    the measurement; *device_values* False writes the readings alone."""
    import numpy as np
    rng = np.random.default_rng(seed)
    rows = []
    for i, c in enumerate(colours):
        sid = str(i + 1)
        d = rng.normal(0, sigma, 3)
        if omit and sid in omit:
            continue
        lab = np.asarray(_aim(c)) + d
        lab[0] = min(lab[0], 100.0)
        x = _xyz(lab)
        rows.append((f"{sid} {c[0]:.4f} {c[1]:.4f} {c[2]:.4f} " if device_values
                     else f"{sid} ") + f"{x[0]:.5f} {x[1]:.5f} {x[2]:.5f}")
    fields = ("SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z" if device_values
              else "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z")
    text = "\n".join([
        "CTI3", "", 'DESCRIPTOR "Argyll Calibration Target chart information 3"',
        'ORIGINATOR "ChromIQ notes demo (synthetic readings)"',
        f'TARGET_INSTRUMENT "{INSTRUMENT}"', 'DEVICE_CLASS "OUTPUT"',
        f'COLOR_REP "{"RGB_XYZ" if device_values else "XYZ"}"',
        'KEYWORD "CHROMIQ_MEASURED"', f'CHROMIQ_MEASURED "{when}"', "",
        f"NUMBER_OF_FIELDS {len(fields.split())}", "BEGIN_DATA_FORMAT", fields,
        "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA",
        *rows, "END_DATA", ""])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    t = datetime.fromisoformat(when).timestamp()
    os.utime(out, (t, t))
    return out


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------
def _limits(run, when: datetime):
    """Bind the run to ChromIQ default, then put a number on every row ChromIQ
    can measure in the run's own column (the Report limits window's "This
    run" edit)."""
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import bind_run, run_limits, set_run_limits
    lim = bind_run(run, "chromiq_default", {}, when=when)
    mine = dict(lim.limits)
    for rid, v in _EXTRA_LIMITS.items():
        mine[rid] = Limit.value(v)
    set_run_limits(run, mine)
    return run_limits(run, {})


def _snapshot(vdir: Path, vstem: str, src_ti2: Path) -> Path:
    """The dated check's own copy of the chart it was measured on, with every
    sidecar that belongs to it (geometry, colorimetric aims, control strip)."""
    cdir = vdir / "chart"
    cdir.mkdir(parents=True, exist_ok=True)
    for suffix in (".ti2", ".channels.json", "-reference.ti3",
                   ".control-strip.json"):
        s = src_ti2.with_name(src_ti2.stem + suffix) if suffix.startswith("-") \
            else src_ti2.with_suffix(suffix)
        if s.is_file():
            shutil.copy2(s, cdir / f"{vstem}{suffix}")
    return cdir


def _print_record(cdir: Path, vstem: str, when: str, profile: str) -> None:
    import make_report_limit_demos as DEMO
    DEMO.write_print_record(cdir, vstem, when, profile, "through-profile")
    pj = cdir / f"{vstem}.print.json"
    rec = json.loads(pj.read_text(encoding="utf-8"))
    rec["intent"] = "absolute"          # judged in absolute Lab, as measured
    pj.write_text(json.dumps(rec, indent=2), encoding="utf-8")


def _report(ti3: Path, run, kind: str, when: str, limits) -> dict:
    import make_report_limit_demos as DEMO
    from workflow.measurement_report import build_report, stamp_verdict
    rep = build_report(ti3, argyll_bin=ARGYLL)
    stamp_verdict(rep, limits.limits, set_id=limits.set_id,
                  set_label=limits.label_en, edited=limits.edited)
    DEMO.file_report(rep, ti3, run, kind, when)
    return rep


def _reasons(rep: dict) -> dict:
    from workflow.measurement_report import recorded_verdict
    return {r["row_id"]: r.get("reason") for r in recorded_verdict(rep)["rows"]
            if r.get("word") == "N-A"}


def _profiling(run, colours, strips, rows, when: str, limits, *,
               chart: bool = True, device_values: bool = True) -> dict:
    """The run's own chart, profile and profiling sheet."""
    from workflow.measurement_report import KIND_PROFILING
    stem = run.stem
    if chart:
        write_chart(run.dir / f"{stem}.ti2", colours, strips, rows, seed=7)
    shutil.copy2(SRGB, run.dir / f"{stem}.icc")
    ti3 = write_sheet(run.dir / f"{stem}.ti3", colours, when, seed=5,
                      device_values=device_values)
    return _report(ti3, run, KIND_PROFILING, when, limits)


def _verification(run, vid: str, when: str, chart_ti2: Path, colours, limits,
                  *, seed: int, sigma: float = 0.25,
                  omit: "set | None" = None) -> dict:
    from workflow.measurement_report import KIND_VERIFICATION
    from workflow.ti3_analysis import mark_verification_ti3
    v = run.verification(vid)
    v.ensure_dir()
    vstem = run.verify_stem
    ti3 = write_sheet(v.dir / f"{vstem}.ti3", colours, when, seed=seed,
                      sigma=sigma, omit=omit)
    mark_verification_ti3(ti3)
    cdir = _snapshot(v.dir, vstem, chart_ti2)
    _print_record(cdir, vstem, when, f"{run.stem}.icc")
    return _report(v.measurement_ti3, run, KIND_VERIFICATION, when, limits)


def _describe(run, text: str) -> None:
    meta = run.load_meta()
    meta.description = text
    meta.instrument = INSTRUMENT
    meta.paper = "Demo matte 200 g"
    meta.status = "complete"
    run.save_meta(meta)


def _say(run, label: str, rep: dict, out: list) -> None:
    line = f"  {run.id} {label}: N-A {_reasons(rep)}"
    print(line)
    out.append(line)


def build(dest: Path) -> "tuple[Path, list]":
    from core.file_manager import Project
    root = dest / NAME
    if root.exists():
        shutil.rmtree(root)
    dest.mkdir(parents=True, exist_ok=True)
    print(f"== {NAME}")
    proj = Project.create(root, NAME)
    log: list = []
    t0 = datetime(2026, 11, 2, 10, 0, 0)

    # -- run1: tiny --------------------------------------------------------
    run = proj.current_run()
    run.ensure_dir()
    _describe(run, "Fifteen mid-cube colours on a page of 3 strips by 5 rows: "
              "no grey, no tone ramp, no repeat, no control strip.")
    lim = _limits(run, t0)
    mids = [c for c in ((r, g, b) for r in (25, 50, 75) for g in (25, 50, 75)
                        for b in (25, 50, 75)) if len(set(c)) > 1][:15]
    mids = [tuple(float(v) for v in c) for c in mids]
    _say(run, "profiling", _profiling(run, mids, 3, 5, "2026-11-01T10:00:00",
                                      lim), log)
    vti2 = write_chart(run.verifications_dir / f"{run.verify_stem}.ti2",
                       mids, 3, 5, seed=7)
    _say(run, "2026-11-02", _verification(
        run, "2026-11-02_100000", "2026-11-02T10:00:00", vti2, mids, lim,
        seed=11), log)

    # -- run2: greys -------------------------------------------------------
    run = proj.new_run()
    run.ensure_dir()
    _describe(run, "Three charts of 144 patches: a grey ramp of five steps "
              "with one colour repeated, a ramp without white, a ramp "
              "without black.")
    lim = _limits(run, t0)
    rest = _random_colours(134, 21)
    five = _greys((0, 25, 50, 75, 100)) + rest[:1] + rest[:1] + rest[1:138]
    five = five[:144]
    no_white = _greys(range(0, 90, 9))[:10] + _random_colours(134, 22)
    no_black = _greys(range(20, 101, 9))[:10] + _random_colours(134, 23)
    _say(run, "profiling", _profiling(run, five, 12, 12, "2026-11-01T11:00:00",
                                      lim), log)
    charts = run.verifications_dir
    for k, (vid, when, cols, seed) in enumerate((
            ("2026-11-02_110000", "2026-11-02T11:00:00", five, 31),
            ("2026-11-09_110000", "2026-11-09T11:00:00", no_white, 32),
            ("2026-11-16_110000", "2026-11-16T11:00:00", no_black, 33))):
        c = write_chart(charts / f"{run.verify_stem}.ti2", cols, 12, 12,
                        seed=seed)
        _say(run, vid, _verification(run, vid, when, c, cols, lim,
                                     seed=40 + k), log)

    # -- run3: strip -------------------------------------------------------
    run = proj.new_run()
    run.ensure_dir()
    _describe(run, "A 144-patch chart with a control strip of five patches.")
    lim = _limits(run, t0)
    cols = _greys(range(0, 101, 10)) + _random_colours(133, 24)
    _say(run, "profiling", _profiling(run, cols, 12, 12, "2026-11-01T12:00:00",
                                      lim), log)
    c = write_chart(run.verifications_dir / f"{run.verify_stem}.ti2", cols, 12,
                    12, seed=8)
    c.with_suffix(".control-strip.json").write_text(json.dumps(
        {"name": "Five-patch strip", "sample_ids": ["12", "13", "14", "15",
                                                   "16"]}), encoding="utf-8")
    _say(run, "2026-11-02", _verification(
        run, "2026-11-02_120000", "2026-11-02T12:00:00", c, cols, lim,
        seed=51), log)

    # -- run4: colorimetric, no corners -------------------------------------
    run = proj.new_run()
    run.ensure_dir()
    _describe(run, "A 144-patch chart judged against stored Lab aims, with no "
              "patch at a corner of the device cube.")
    lim = _limits(run, t0)
    cols = _random_colours(144, 25, lo=12.0, hi=88.0)
    _say(run, "profiling", _profiling(run, cols, 12, 12, "2026-11-01T13:00:00",
                                      lim), log)
    c = write_chart(run.verifications_dir / f"{run.verify_stem}.ti2", cols, 12,
                    12, seed=9)
    write_reference(c, cols)
    _say(run, "2026-11-02", _verification(
        run, "2026-11-02_130000", "2026-11-02T13:00:00", c, cols, lim,
        seed=61), log)

    # -- run5: evenness ----------------------------------------------------
    run = proj.new_run()
    run.ensure_dir()
    _describe(run, "One 144-patch colour set measured five times on five "
              "charts: positions no strip and row can be read from, no page "
              "geometry, a ninth of the page not measured, 30 % of the page "
              "covered, a noisy sheet.")
    lim = _limits(run, t0)
    cols = _greys(range(0, 101, 10)) + _random_colours(133, 26)
    _say(run, "profiling", _profiling(run, cols, 12, 12, "2026-11-01T14:00:00",
                                      lim), log)
    vdir = run.verifications_dir
    stem = run.verify_stem
    # the ninth of the page a measurement leaves out: strips A to D, rows 1
    # to 4 of the chart laid out with seed 104
    import numpy as np
    slots = np.random.default_rng(104).permutation(144)[:len(cols)]
    top_left = {str(i + 1) for i, s in enumerate(slots)
                if (int(s) // 12) < 4 and (int(s) % 12) < 4}
    plan = [
        ("2026-11-02_140000", "2026-11-02T14:00:00", "positions",
         dict(seed=101, bad_locations=True), {}),
        ("2026-11-09_140000", "2026-11-09T14:00:00", "no geometry",
         dict(seed=102, coverage=None), {}),
        ("2026-11-16_140000", "2026-11-16T14:00:00", "ninth not measured",
         dict(seed=104), dict(omit=top_left)),
        ("2026-11-23_140000", "2026-11-23T14:00:00", "30 % covered",
         dict(seed=105, coverage=0.30), {}),
        ("2026-11-30_140000", "2026-11-30T14:00:00", "noisy",
         dict(seed=106), dict(sigma=2.5)),
    ]
    for k, (vid, when, title, chart_kw, sheet_kw) in enumerate(plan):
        c = write_chart(vdir / f"{stem}.ti2", cols, 12, 12, **chart_kw)
        _say(run, f"{vid} {title}", _verification(
            run, vid, when, c, cols, lim, seed=70 + k, **sheet_kw), log)

    # -- run6: history -----------------------------------------------------
    run = proj.new_run()
    run.ensure_dir()
    _describe(run, "Three dated sheets; the first two reports were saved by "
              "older ChromIQ.")
    lim = _limits(run, t0)
    cols = _greys(range(0, 101, 10)) + _random_colours(133, 27)
    _say(run, "profiling", _profiling(run, cols, 12, 12, "2026-11-01T15:00:00",
                                      lim), log)
    c = write_chart(run.verifications_dir / f"{run.verify_stem}.ti2", cols, 12,
                    12, seed=10)
    dates = [("2026-11-02_150000", "2026-11-02T15:00:00"),
             ("2026-11-09_150000", "2026-11-09T15:00:00"),
             ("2026-11-16_150000", "2026-11-16T15:00:00")]
    for k, (vid, when) in enumerate(dates):
        _say(run, vid, _verification(run, vid, when, c, cols, lim,
                                     seed=80 + k), log)
    _age_the_first_two(run, dates)

    # -- run7: no device values --------------------------------------------
    run = proj.new_run()
    run.ensure_dir()
    _describe(run, "A profiling measurement of readings alone: no device "
              "values and no chart beside it.")
    lim = _limits(run, t0)
    cols = _random_colours(40, 28)
    _say(run, "profiling", _profiling(run, cols, 5, 8, "2026-11-01T16:00:00",
                                      lim, chart=False, device_values=False),
         log)
    return root, log


def _age_the_first_two(run, dates) -> None:
    """Put the first two reports of *run* into the shapes older ChromIQ saved.

    1. The first was saved before the control-strip and evenness blocks
       existed, and before the verdict was kept with the report, and its measurement was measured again since, so the file it
       was made from is in the run's ``old/`` folder: nothing beside the
       report can rebuild the missing blocks, and those rows read
       ``not_computed``.
    2. The second was saved before 2026-09-13, when a grey row on a sheet
       whose printing was not recorded was shown for information with the
       reason ``printing_unrecorded`` instead of being judged.
    """
    from core.file_manager import reports_subdir
    first = run.verification(dates[0][0])
    rep_path = next(reports_subdir(first.dir).glob("report_*.json"))
    doc = json.loads(rep_path.read_text(encoding="utf-8"))
    # …and before the verdict was kept with the report (#182), so its words
    # are worked out when the report is read, from the blocks it has
    for block in ("control_strip", "evenness", "verdict"):
        doc.pop(block, None)
    rep_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    old = run.dir / "old" / first.dir.name
    old.mkdir(parents=True, exist_ok=True)
    shutil.move(str(first.measurement_ti3), str(old / first.measurement_ti3.name))

    second = run.verification(dates[1][0])
    rep_path = next(reports_subdir(second.dir).glob("report_*.json"))
    doc = json.loads(rep_path.read_text(encoding="utf-8"))
    for row in (doc.get("verdict") or {}).get("rows") or []:
        if row.get("row_id") in ("grey_balance_neutral_ramp_avg",
                                 "grey_balance_neutral_ramp_max"):
            row["word"] = "INFO"
            row["pass"] = None
            row["reason"] = "printing_unrecorded"
            row["notes"] = []
            row["graded"] = False
    rep_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # no window: files only
    os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(
        ROOT / "data" / "compliance_sets" / "iso12647.json")
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    root, lines = build(Path(sys.argv[1]).resolve())
    (root.parent / f"{NAME}.txt").write_text("\n".join(lines) + "\n",
                                             encoding="utf-8")
