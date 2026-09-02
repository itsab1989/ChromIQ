#!/usr/bin/env python3
"""Build ``Demo-Report-Matrix`` — the measurement-report test project (Knut).

    *"…update and extend the demo package made for testing the measurement
    report, so that all new features and variations of input data sources and
    selected options are tested against the report output. … regenerate all
    the test data with multiple verification runs, using proper generated
    charts, measurements, icc profiles, and verification charts through
    existing profile etc."*  (2026-08-10)

Every artefact is made by the REAL pipeline — nothing hand-written:

    targen → printtarg → fakeread (Argyll's sRGB.icm plays the printer)
    → colprof (the run's profile) → per-case verification measurements
    (fakeread again, raw / through the profile, with noise for drift)
    → the FROM PROFILE GAMUT chart via workflow.gamut_target.

One project, two runs, twelve dated verification cases (V1–V12 below +
P1/P2 for profiling). ``README.md`` inside the project describes every case
and what the Measurement Report must show for it.
``scripts/drive_report_demo_onscreen.py`` opens the real report window on
each case, checks those expectations, and exports one PDF per case.

Run::

    .venv/bin/python scripts/make_report_demo.py [destination]
    # default destination: ./demo-projects
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from core.proc_text import run_text

ARGYLL = Path("/Applications/Argyll/bin")
SRGB = Path("/Applications/Argyll/ref/sRGB.icm")
NAME = "Demo-Report-Matrix"

#: case id → (dated folder, how the sheet was "printed", i.e. which print
#: record lands in the date's chart/ snapshot; None = no record at all).
#: Data: raw sheets are fakeread through sRGB (the bare "printer"),
#: through sheets are fakeread through the run's own profile.
CASES = """\
V1  2026-05-01_100000  raw sheet #1 (drift baseline)          record: raw/chromiq
V2  2026-06-01_100000  raw sheet #2 (drifted, more noise)     record: raw/chromiq
V3  2026-06-15_100000  through profile, RELATIVE intent       record: through/chromiq/relative
V4  2026-07-01_100000  through profile, ABSOLUTE intent       record: through/chromiq/absolute
V5  2026-07-10_100000  printed in another app with CM         record: through/external-cm/unknown, asked-at-measure
V6  2026-07-20_100000  no print record at all                 record: none
V7  2026-08-01_100000  gamut chart check #1                   record: raw/chromiq (colorimetric reference)
V8  2026-08-08_100000  gamut chart check #2 (noisier)         record: raw/chromiq (colorimetric reference)
V9  2026-08-09_100000  gamut chart, reference file REMOVED    → the report must refuse, not guess
V10 2026-08-10_090000  imported measurement (keyword-stamped) record: none (asked-at-measure external)
V11 2026-08-10_100000  different instrument (i1Pro3)          record: raw/chromiq → mixed-instruments warning
V12 2026-08-10_110000  profile rebuilt after printing         record: through/chromiq/relative + old mtime
"""


def run(cmd, cwd, timeout=300):
    r = run_text([str(c) for c in cmd], cwd=str(cwd),
                 capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise SystemExit(f"{cmd[0]} failed:\n{r.stdout}\n{r.stderr}")
    return r


def make_chart(into: Path, stem: str, patches: int) -> None:
    """A REAL chart: targen designs it, printtarg lays it out (.ti2 with
    SAMPLE_LOC — chartread's actual input)."""
    into.mkdir(parents=True, exist_ok=True)
    run([ARGYLL / "targen", "-d2", "-e4", f"-f{patches}", stem], into)
    run([ARGYLL / "printtarg", "-iCM", "-pA4", "-t150", "-L", stem], into)


def fakeread(into: Path, stem: str, profile: Path, noise: float = 0.0) -> Path:
    args = [ARGYLL / "fakeread"]
    if noise:
        args += ["-r", str(noise)]
    args += [profile, stem]
    run(args, into)
    return into / f"{stem}.ti3"


def stamp(ti3: Path, when: str, instrument: str = "X-Rite ColorMunki") -> None:
    """The keywords a real ChromIQ measurement carries — via the same helpers
    the app uses, never by ad-hoc text surgery."""
    from workflow.ti3_analysis import mark_verification_ti3
    mark_verification_ti3(ti3)
    text = ti3.read_text(encoding="utf-8")
    lines = text.splitlines()
    at = next(i for i, l in enumerate(lines)
              if l.startswith("NUMBER_OF_FIELDS"))
    lines[at:at] = ['KEYWORD "CHROMIQ_MEASURED"',
                    f'CHROMIQ_MEASURED "{when}"',
                    f'TARGET_INSTRUMENT "{instrument}"']
    ti3.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # The file's own time tells the same story as the keyword — the mtime is
    # the fallback date for measurements without the keyword, and Finder
    # sorting the dates correctly makes the package self-explaining.
    import os
    t = datetime.fromisoformat(when).timestamp()
    os.utime(ti3, (t, t))


def snapshot(vdir: Path, chart_stem: str, src_dir: Path,
             extra: "list[Path]" = ()) -> Path:
    """A dated check's chart/ snapshot, the layout the app writes."""
    cdir = vdir / "chart"
    cdir.mkdir(parents=True, exist_ok=True)
    for ext in (".ti1", ".ti2", ".channels.json"):
        s = src_dir / f"{chart_stem}{ext}"
        if s.is_file():
            shutil.copy2(s, cdir / s.name)
    for e in extra:
        if Path(e).is_file():
            shutil.copy2(e, cdir / Path(e).name)
    return cdir


def record(cdir: Path, stem: str, *, colour, route, intent, profile,
           asked=False, printed="2026-05-01T09:00:00") -> None:
    import json
    rec = {"printed_at": printed, "colour": colour, "intent": intent,
           "route": route, "source_profile": "",
           "profile": profile.name if profile else None}
    if profile is not None:
        rec["profile_path"] = str(profile)
        rec["profile_mtime"] = datetime.fromtimestamp(
            profile.stat().st_mtime).isoformat(timespec="seconds")
    if asked:
        rec["recorded"] = "asked-at-measure"
        rec.pop("printed_at")
    (cdir / f"{stem}.print.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")


def main(argv=None) -> int:
    dest = Path((argv or sys.argv[1:] or ["demo-projects"])[0]).resolve()
    if not (ARGYLL / "targen").exists() or not SRGB.exists():
        print("ArgyllCMS (with ref/sRGB.icm) is required.")
        return 2
    root = dest / NAME
    if root.exists():
        # Never delete: the previous package is archived, like the app would.
        old = dest / "old" / f"{NAME}-{datetime.now():%Y-%m-%d_%H%M%S}"
        old.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(root), str(old))
        print(f"previous package archived to {old}")

    from core.file_manager import Project
    proj = Project.create(root, NAME)
    run1 = proj.current_run()
    run1.ensure_dir()
    stem = NAME

    print("== run1: profiling chart, measurement, profile (all real Argyll)")
    make_chart(run1.dir, stem, 210)
    fakeread(run1.dir, stem, SRGB, noise=0.3)
    r = run_text([str(ARGYLL / "colprof"), "-v", "-ql", "-aG", stem],
                 cwd=str(run1.dir), capture_output=True, timeout=600)
    if r.returncode != 0:
        raise SystemExit(f"colprof failed:\n{r.stdout}\n{r.stderr}")
    icc = run1.built_profile_icc()
    made = run1.dir / f"{stem}.icc"
    if made != icc:
        shutil.move(str(made), str(icc))

    print("== run1: the design verification chart")
    vroot = run1.verifications_dir
    vstem = f"{stem}-verify"
    make_chart(vroot, vstem, 105)

    print("== run1: the FROM PROFILE GAMUT chart (feature B, real xicclu)")
    from workflow.gamut_target import (mark_chart_as_colorimetric,
                                       select_gamut_targets,
                                       write_colorimetric_reference,
                                       write_gamut_ti1)
    gdir = run1.dir / "gamut-work"
    gdir.mkdir(exist_ok=True)
    sel = select_gamut_targets(icc, 100, "safe", "absolute", bin_dir=ARGYLL)
    gstem = f"{stem}-gamut"
    write_gamut_ti1(sel, gdir / f"{gstem}.ti1")
    run([ARGYLL / "printtarg", "-iCM", "-pA4", "-t150", "-L", gstem], gdir)
    # House conventions (feature B): the reference is <stem>-reference.ti3
    # beside the chart, and the marking lives in <stem>.channels.json.
    gref = gdir / f"{gstem}-reference.ti3"
    write_colorimetric_reference(sel, gref)
    mark_chart_as_colorimetric(gdir / f"{gstem}.ti2", gref)

    print("== the twelve dated verification cases")
    def dated(vid, chart_dir, chart_stem, profile, noise, when,
              instrument="X-Rite ColorMunki"):
        v = run1.verification(vid)
        v.ensure_dir()
        work = v.dir / "_work"
        work.mkdir()
        for ext in (".ti1", ".ti2"):
            shutil.copy2(chart_dir / f"{chart_stem}{ext}",
                         work / f"{vstem}{ext}")
        ti3 = fakeread(work, vstem, profile, noise)
        stamp(ti3, when, instrument)
        shutil.move(str(ti3), str(v.measurement_ti3))
        extra = []
        if (chart_dir / f"{chart_stem}-colorimetric.json").is_file():
            extra = [chart_dir / f"{chart_stem}-colorimetric.json"]
        cdir = snapshot(v.dir, vstem, work, extra)
        # the snapshot keeps the DESIGN chart's stem so read_print_record and
        # _find_reference_ti2 resolve exactly as for an app-made date
        shutil.rmtree(work)
        return v, cdir

    # V1/V2 — raw drift pair
    v, c = dated("2026-05-01_100000", vroot, vstem, SRGB, 0.3,
                 "2026-05-01T10:00:00")
    record(c, vstem, colour="raw", route="chromiq", intent="", profile=None)
    v, c = dated("2026-06-01_100000", vroot, vstem, SRGB, 1.2,
                 "2026-06-01T10:00:00")
    record(c, vstem, colour="raw", route="chromiq", intent="", profile=None)
    # V3/V4 — through the profile, relative / absolute
    v, c = dated("2026-06-15_100000", vroot, vstem, icc, 0.4,
                 "2026-06-15T10:00:00")
    record(c, vstem, colour="through-profile", route="chromiq",
           intent="relative", profile=icc)
    v, c = dated("2026-07-01_100000", vroot, vstem, icc, 0.4,
                 "2026-07-01T10:00:00")
    record(c, vstem, colour="through-profile", route="chromiq",
           intent="absolute", profile=icc)
    # V5 — another app with colour management (answered at measure time)
    v, c = dated("2026-07-10_100000", vroot, vstem, icc, 0.8,
                 "2026-07-10T10:00:00")
    record(c, vstem, colour="through-profile", route="external-cm",
           intent="unknown", profile=None, asked=True)
    # V6 — no record at all
    v, c = dated("2026-07-20_100000", vroot, vstem, SRGB, 0.6,
                 "2026-07-20T10:00:00")
    # V7/V8 — the gamut chart, twice
    for vid, when, noise in (("2026-08-01_100000", "2026-08-01T10:00:00", 0.3),
                             ("2026-08-08_100000", "2026-08-08T10:00:00", 0.9)):
        v = run1.verification(vid)
        v.ensure_dir()
        work = v.dir / "_work"
        work.mkdir()
        for ext in (".ti1", ".ti2"):
            shutil.copy2(gdir / f"{gstem}{ext}", work / f"{vstem}{ext}")
        # keep the colorimetric marking intact under the verify stem
        shutil.copy2(gref, work / f"{vstem}-reference.ti3")
        mark_chart_as_colorimetric(work / f"{vstem}.ti2",
                                   work / f"{vstem}-reference.ti3")
        ti3 = fakeread(work, vstem, icc, noise)
        stamp(ti3, when)
        shutil.move(str(ti3), str(v.measurement_ti3))
        cdir = snapshot(v.dir, vstem, work,
                        [work / f"{vstem}-reference.ti3"])
        record(cdir, vstem, colour="raw", route="chromiq", intent="",
               profile=None)
        shutil.rmtree(work)
    # V9 — gamut chart whose colorimetric reference file is gone
    v = run1.verification("2026-08-09_100000")
    v.ensure_dir()
    work = v.dir / "_work"; work.mkdir()
    for ext in (".ti1", ".ti2"):
        shutil.copy2(gdir / f"{gstem}{ext}", work / f"{vstem}{ext}")
    shutil.copy2(gref, work / f"{vstem}-reference.ti3")
    mark_chart_as_colorimetric(work / f"{vstem}.ti2",
                               work / f"{vstem}-reference.ti3")
    ti3 = fakeread(work, vstem, icc, 0.4)
    stamp(ti3, "2026-08-09T10:00:00")
    shutil.move(str(ti3), str(v.measurement_ti3))
    (work / f"{vstem}-reference.ti3").unlink()   # the missing reference
    snapshot(v.dir, vstem, work)
    shutil.rmtree(work)
    # V10 — imported (external measurement filed like the IMPORT module does)
    v, c = dated("2026-08-10_090000", vroot, vstem, icc, 0.7,
                 "2026-08-10T09:00:00")
    record(c, vstem, colour="through-profile", route="external-cm",
           intent="unknown", profile=None, asked=True)
    # V11 — a different instrument → the mixed-instruments warning
    v, c = dated("2026-08-10_100000", vroot, vstem, SRGB, 0.5,
                 "2026-08-10T10:00:00", instrument="X-Rite i1Pro3")
    record(c, vstem, colour="raw", route="chromiq", intent="", profile=None)
    # V12 — profile rebuilt since the sheet was printed
    v, c = dated("2026-08-10_110000", vroot, vstem, icc, 0.4,
                 "2026-08-10T11:00:00")
    import json as _json
    rec = {"printed_at": "2026-08-10T08:00:00", "colour": "through-profile",
           "intent": "relative", "route": "chromiq", "source_profile": "",
           "profile": icc.name, "profile_path": str(icc),
           "profile_mtime": "2026-01-01T00:00:00"}    # older than the file
    (c / f"{vstem}.print.json").write_text(_json.dumps(rec, indent=2), encoding="utf-8")

    print("== run2: no profile — the split must degrade, never error")
    run2 = proj.new_run()
    run2.ensure_dir()
    make_chart(run2.verifications_dir, f"{stem}-verify", 105)
    v = run2.verification("2026-08-10_120000")
    v.ensure_dir()
    work = v.dir / "_work"; work.mkdir()
    for ext in (".ti1", ".ti2"):
        shutil.copy2(run2.verifications_dir / f"{stem}-verify{ext}",
                     work / f"{vstem}{ext}")
    ti3 = fakeread(work, vstem, SRGB, 0.5)
    stamp(ti3, "2026-08-10T12:00:00")
    shutil.move(str(ti3), str(v.measurement_ti3))
    snapshot(v.dir, vstem, work)
    shutil.rmtree(work)

    shutil.rmtree(gdir, ignore_errors=True)
    (root / "README.md").write_text(README, encoding="utf-8")
    print(f"\nDemo-Report-Matrix written to {root}")
    print("Next: .venv/bin/python scripts/drive_report_demo_onscreen.py")
    return 0


README = """# Demo-Report-Matrix — the Measurement Report test package

Built by `scripts/make_report_demo.py` (every file made by real ArgyllCMS:
targen → printtarg → fakeread → colprof; the gamut chart via xicclu).
Argyll's sRGB.icm plays the printer; the run's own profile was built from a
real fakeread measurement of a real 210-patch chart.

`scripts/drive_report_demo_onscreen.py` opens the real Measurement Report on
every case, checks the expectations below, and exports one PDF per case into
`pdfs/` beside this file.

## run1 — twelve dated verification cases

| Case | Date | What it is | The report must show |
|---|---|---|---|
| V1 | 2026-05-01 | raw sheet, little noise | "printed raw — no profile"; judged as measured — no white adjustment; split blocks present (run profile referees); Result column says "drift", detail says this check **becomes the baseline** |
| V2 | 2026-06-01 | raw sheet, more noise | same as V1, worse figures → visible drift V1→V2 in the trend; detail shows **"Drift since the previous raw check"** with avg/max ΔE00 vs V1 — no Pass/Fail |
| V3 | 2026-06-15 | through profile, relative intent | "through this run's profile · relative colorimetric"; judged relative to paper white (media-relative); split present |
| V4 | 2026-07-01 | through profile, absolute intent | as-measured (absolute) yardstick, split present |
| V5 | 2026-07-10 | another app with colour management | "printed in another app with colour management"; "(your answer when the sheet was measured)"; media-relative |
| V6 | 2026-07-20 | no print record | "printing method not recorded"; judged as measured |
| V7 | 2026-08-01 | gamut chart #1 | reference = the profile's own colorimetric targets; NO split (all colours printable by design); corners excluded from stats; produced-block says it measured **the profile's accuracy against its own promise** (never "drift check"); run row says "gamut check — profile applied at build" |
| V8 | 2026-08-08 | gamut chart #2, noisier | same, worse figures → drift V7→V8 |
| V9 | 2026-08-09 | gamut chart, reference REMOVED | "No colour-accuracy figures, on purpose." — refusal, never a guessed number |
| V10 | 2026-08-10 09:00 | imported from another program | CHROMIQ keywords present; treated as external-CM (answered at measure) |
| V11 | 2026-08-10 10:00 | measured with an i1Pro3 | red "mixed instruments" warning names this date |
| V12 | 2026-08-10 11:00 | profile rebuilt after printing | "the profile has been rebuilt since this sheet was printed" warning; V10–V12 share one day, so their table columns and trend labels carry the **time** |

## run2 — one case

| Case | Date | What it is | The report must show |
|---|---|---|---|
| R2 | 2026-08-10 12:00 | verification, run has NO profile | report renders fully; no split blocks (no referee profile) — degraded, not broken |

## Options to exercise by hand (the driver does all of them too)

* **Show all measurement runs** on/off — trend + side-by-side vs one run.
* **Show detailed data for each run** on/off — detail chapters appear/disappear;
  Report Results wording follows.
* **Un-tick single runs** in the list — Report Scope says "hidden by you",
  the PDF's proposed folder follows the selection (four-tier design).
* **Pass thresholds** — Result flips; with the split, Pass/Fail judges the
  within-gamut figures.
* **Save report as PDF** — proposed folder: one date → that date's
  `reports/`; several dates of run1 → `verifications/reports/`; both runs →
  the project's `reports/`.

All options are remembered between openings.
"""


if __name__ == "__main__":
    sys.exit(main())
