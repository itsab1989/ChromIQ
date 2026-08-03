"""Build the #130 demo package: one project per case in the model, plus a
step-by-step document, zipped.

Knut, #130 2026-08-03: *"Create a complete package of demo projects, some with
many runs, others with less. Chart files and measure files must be complete
files, and valid as created by argyllcms, targen, printtarg, and many charts
also made by ChromIQ layout engine, and also measurements, profiles, and many
verification runs. Charts for verification runs shall be smaller than the run's
charts. […] The demo projects content shall be created so that each project or
run in a project is specifically put together to verify each an every case
possible in the Unified Measurement Management model […] The demo package shall
contain a document that describes how every project or run is used, step by
step in ChromIQ, to verify all the combinations of events, actions and warning
windows. Some warnings cannot be reproduced, as they are hardware issues, so
these are ignored. the demo package shall be downloadable as a zip file."*

    python scripts/make_demo_package.py [DEST]        # default: dist/demo-package

Every chart here is real: ``targen`` makes the patch set, and the layout comes
either from **printtarg** or from **ChromIQ's own layout engine** — the document
says which for each project, because the two are meant to be exercised. Profiles
are built by real ``colprof``. Nothing in the package is a stub, because a demo
folder full of files that will not open tests nothing (Knut, #130 2026-07-28).

Deliberately NOT covered, and listed as such in the document: anything that
needs an instrument on the desk — a session that ends by unplugging the device,
a calibration failure, a strip that will not read. Those are hardware, and Knut
excluded them.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.make_demo_projects import (      # noqa: E402
    _argyll, _build_icc, _chart_files, _meta, _report, _ti3_from_ti2,
    _write_manifest, _write_tiff)

#: Patch counts. Small enough that the whole package builds in a few minutes,
#: big enough to be a real chart. The verification charts are deliberately a
#: fraction of the run charts — Knut: *"Charts for verification runs shall be
#: smaller than the run's charts."*
RUN_PATCHES = 210
RUN_ROWS = 15
VERIFY_PATCHES = 45
VERIFY_ROWS = 9


# ---------------------------------------------------------------------------
# a chart laid out by printtarg, for the half of the package that must not use
# the engine
# ---------------------------------------------------------------------------
def _chart_files_printtarg(into: Path, stem: str, *, patches: int,
                           instrument: str = "i1", paper: str = "A4") -> None:
    """A real ``targen`` + real ``printtarg`` chart.

    The counterpart to :func:`scripts.make_demo_projects._chart_files`, which
    lays the same patch set out with ChromIQ's engine. Both exist here on
    purpose: a demo package that only ever exercised one layout path would miss
    every difference between them.

    No ``.channels.json`` is written, because printtarg does not produce one —
    which incidentally makes these the runs that exercise §4a rows 3 and 5 (the
    pages cannot be redrawn) and M-DUPLICATE-BLOCKED.
    """
    into.mkdir(parents=True, exist_ok=True)
    subprocess.run([_argyll("targen"), "-v0", "-d2", "-G", f"-f{patches}", stem],
                   cwd=into, check=True, capture_output=True, timeout=300)
    subprocess.run([_argyll("printtarg"), "-v0", f"-i{instrument}", f"-p{paper}",
                    "-t300", "-L", stem],
                   cwd=into, check=True, capture_output=True, timeout=300)


def _strip(path: Path) -> None:
    path.unlink(missing_ok=True)


def _truncate_ti3(path: Path, keep: int) -> None:
    """Cut a measurement down to *keep* readings, header included — what an
    interrupted session leaves behind."""
    lines = path.read_text().splitlines()
    out, kept, in_data = [], 0, False
    for line in lines:
        if line.startswith("NUMBER_OF_SETS"):
            out.append(f"NUMBER_OF_SETS {keep}")
            continue
        if line.strip() == "BEGIN_DATA":
            in_data = True
            out.append(line)
            continue
        if line.strip() == "END_DATA":
            in_data = False
            out.append(line)
            continue
        if in_data:
            if kept < keep:
                out.append(line)
                kept += 1
            continue
        out.append(line)
    path.write_text("\n".join(out) + "\n")


def _lie_in_the_header(path: Path, claim: int) -> None:
    """Make the header disagree with the rows — §3a's ``B ≠ C``."""
    lines = [f"NUMBER_OF_SETS {claim}" if l.startswith("NUMBER_OF_SETS") else l
             for l in path.read_text().splitlines()]
    path.write_text("\n".join(lines) + "\n")


def _verification(run_dir: Path, stem: str, when: datetime, de: float,
                  *, source_ti2: Path) -> None:
    """One dated verification measurement, measured against the smaller
    verification chart that lives beside it."""
    vid = when.strftime("%Y-%m-%d_%H%M%S")
    v = run_dir / "verifications" / vid
    (v / "reports").mkdir(parents=True, exist_ok=True)
    (v / f"{stem}-verify.ti3").write_text(_ti3_from_ti2(source_ti2, drift=de / 10))
    (v / "reports" / f"report_{when:%Y-%m-%d_%H-%M-%S}.json").write_text(
        _report(f"{stem}-verify", when, de))


# ---------------------------------------------------------------------------
# the projects, one case of the model each
# ---------------------------------------------------------------------------
CASES: "list[dict]" = []


def case(**kw):
    """Record what a project is for, so the document and the data cannot drift
    apart: both are generated from this one list."""
    def deco(fn):
        CASES.append({"fn": fn, **kw})
        return fn
    return deco


@case(name="Demo-01-Chart-Only",
      layout="ChromIQ layout engine",
      covers=["§4 row 2 — a chart with nothing measured: no warning",
              "§6e row 1 — no profile yet: no warning"],
      steps=["Load the project, set Profile run = run 1, Run type = Profiling.",
             "Press **Generate Chart**. *Expected: no warning at all* — nothing "
             "has been measured, so a new chart costs only a reprint.",
             "Go to Build Profile. *Expected: no warning* — there is no profile "
             "to replace and no verification history."])
def build_chart_only(root: Path) -> None:
    name = "Demo-01-Chart-Only"
    p = root / name
    _write_manifest(p, name, ["run1"], "run1", 3)
    _chart_files(p / "runs" / "run1", name, patches=RUN_PATCHES, rows=RUN_ROWS)
    _meta(p / "runs" / "run1", "run1", status="in_progress")


@case(name="Demo-02-Partial-Measurement",
      layout="ChromIQ layout engine",
      covers=["§5 M-REPLACE-PARTIAL — starting over a partial measurement",
              "§4 chart + partial .ti3 (Profiling)"],
      steps=["Set Profile run = run 1, Run type = Profiling.",
             "Go to Measure and press **Start Measurement**. *Expected:* “This "
             "run already holds part of a measurement”, saying **38 of the "
             "chart's {n} patches**, pointing at “Refine / resume existing "
             "measurement (-r)” in the options panel, and naming the file. "
             "Press Cancel.",
             "Tick **Refine / resume existing measurement (-r)** and press "
             "Start Measurement again. *Expected: no window* — resuming adds "
             "to the readings instead of replacing them.",
             "Untick it again, go to Create Chart and press **Generate "
             "Chart**. *Expected:* “This run already holds work made with the "
             "chart you are about to replace”, listing the measurement of 38 "
             "patches. Press Cancel."])
def build_partial(root: Path) -> None:
    name = "Demo-02-Partial-Measurement"
    p = root / name
    _write_manifest(p, name, ["run1"], "run1", 3)
    r = p / "runs" / "run1"
    _chart_files(r, name, patches=RUN_PATCHES, rows=RUN_ROWS)
    ti3 = r / f"{name}.ti3"
    ti3.write_text(_ti3_from_ti2(r / f"{name}.ti2"))
    _truncate_ti3(ti3, 38)
    (r / "chart").mkdir(exist_ok=True)
    for f in r.glob(f"{name}.*"):
        if f.suffix != ".ti3":
            shutil.copy2(f, r / "chart" / f.name)
    _meta(r, "run1", status="in_progress")


@case(name="Demo-03-Complete-And-Profiled",
      layout="printtarg",
      covers=["§5 M-REPLACE-COMPLETE — starting over a finished measurement",
              "§4 chart + complete .ti3 + profile (Profiling)",
              "§4a row 5 — pages that cannot be redrawn (M-CHART-NOPAGES)",
              "M-DUPLICATE-BLOCKED — Duplicate needs a .channels.json"],
      steps=["Set Profile run = run 1, Run type = Profiling.",
             "Press **Start Measurement**. *Expected:* “This chart is fully "
             "measured”, All {n} patches have been read, and the warning that "
             "the profile beside it will no longer match. Press Cancel.",
             "Go to Create Chart and press **Generate Chart**. *Expected:* the "
             "chart warning listing **both** the finished measurement and the "
             "profile built from it, **plus** a paragraph saying the pages "
             "cannot be drawn again (this chart came from printtarg, so it has "
             "no layout recipe), **plus** an explanation that Duplicate is not "
             "available and which file is missing. Press Cancel.",
             "Look at the Profile-run bar: the **Duplicate** button is greyed "
             "out, exactly as the message said."])
def build_complete(root: Path) -> None:
    name = "Demo-03-Complete-And-Profiled"
    p = root / name
    _write_manifest(p, name, ["run1"], "run1", 3)
    r = p / "runs" / "run1"
    _chart_files_printtarg(r, name, patches=RUN_PATCHES)
    (r / f"{name}.ti3").write_text(_ti3_from_ti2(r / f"{name}.ti2"))
    _build_icc(r, name)
    _meta(r, "run1")


@case(name="Demo-04-Mismatched",
      layout="ChromIQ layout engine",
      covers=["§5 / §3a M-TI3-MISMATCH — the measurement and the chart disagree",
              "§3a B ≠ C — the file's header disagrees with its own rows"],
      steps=["Set Profile run = **run 1**, Run type = Profiling.",
             "Press **Start Measurement**. *Expected:* “This run's measurement "
             "and its chart do not match” — 40 readings against {n} patches, "
             "the statement that ChromIQ cannot tell which of the two is "
             "wrong, and a pointer to “Restore Used Chart”. Resume is **not** "
             "offered. Press Cancel.",
             "Switch to **run 2** and press Start Measurement. *Expected:* the "
             "same window, plus the extra sentence that the file's own header "
             "claims 999 readings, so it may be damaged as well as mismatched."])
def build_mismatched(root: Path) -> None:
    name = "Demo-04-Mismatched"
    p = root / name
    _write_manifest(p, name, ["run1", "run2"], "run1", 3)
    for rid, claim in (("run1", None), ("run2", 999)):
        r = p / "runs" / rid
        _chart_files(r, name, patches=RUN_PATCHES, rows=RUN_ROWS)
        ti3 = r / f"{name}.ti3"
        ti3.write_text(_ti3_from_ti2(r / f"{name}.ti2"))
        _truncate_ti3(ti3, 40)
        if claim is not None:
            _lie_in_the_header(ti3, claim)
        (r / "chart").mkdir(exist_ok=True)
        for f in r.glob(f"{name}.*"):
            if f.suffix != ".ti3":
                shutil.copy2(f, r / "chart" / f.name)
        _meta(r, rid)


@case(name="Demo-05-Unreadable-Measurements",
      layout="ChromIQ layout engine",
      covers=["§3a empty / header-only — a measurement file with nothing in it",
              "§5 a measurement with readings but no chart to count against"],
      steps=["Set Profile run = **run 1** (a .ti3 that holds no readable "
             "data) and press **Start Measurement**. *Expected:* “This run "
             "already holds a measurement file”, saying ChromIQ cannot tell "
             "how many readings it contains and naming the file. It must "
             "**not** suggest Refine / resume — there is nothing to resume "
             "from. Press Cancel.",
             "Switch to **run 2** (readings, but the chart file has been "
             "removed) and press Start Measurement. *Expected:* “This run "
             "already holds part of a measurement” saying **60 readings have "
             "been taken** and that ChromIQ cannot tell how many patches the "
             "chart has. Never “60 of ? patches”.",
             "In run 2, press **Generate Chart**. *Expected:* the chart "
             "warning still appears, and its bullet says the measurement file "
             "no longer describes the chart — the measurement is protected "
             "even though the chart files are incomplete."])
def build_unreadable(root: Path) -> None:
    name = "Demo-05-Unreadable-Measurements"
    p = root / name
    _write_manifest(p, name, ["run1", "run2"], "run1", 3)

    r1 = p / "runs" / "run1"
    _chart_files(r1, name, patches=RUN_PATCHES, rows=RUN_ROWS)
    (r1 / f"{name}.ti3").write_text(
        "CTI3\n\nDESCRIPTOR \"Argyll Calibration Target chart information 3\"\n"
        "KEYWORD \"DEVICE_CLASS\"\nDEVICE_CLASS \"OUTPUT\"\n"
        "NUMBER_OF_FIELDS 7\n")            # a header and then nothing at all
    _meta(r1, "run1")

    r2 = p / "runs" / "run2"
    _chart_files(r2, name, patches=RUN_PATCHES, rows=RUN_ROWS)
    ti3 = r2 / f"{name}.ti3"
    ti3.write_text(_ti3_from_ti2(r2 / f"{name}.ti2"))
    _truncate_ti3(ti3, 60)
    _strip(r2 / f"{name}.ti2")             # readings with nothing to count against
    _meta(r2, "run2")


@case(name="Demo-06-Verification-History",
      layout="ChromIQ layout engine (run chart) + printtarg (verification chart)",
      covers=["§6e rows 5 and 6 — M-PROFILE-VERIFY",
              "§4 W4 — regenerating the chart of a run with a history",
              "§4 W5 — M-CHART-VERIFY, replacing the verification chart",
              "§6d — the “don't show this again for this run” checkbox"],
      steps=["Set Profile run = **run 1**, Run type = Profiling.",
             "Go to Build Profile and press **Build Profile**. *Expected:* "
             "“The verification measurements in this run were made against the "
             "profile you are about to replace”, saying **4 dated verification "
             "measurements, going back to 2026-02-14**, with three buttons. "
             "Press Cancel.",
             "Press Build Profile again, tick **Don't show this again for this "
             "run**, then press Cancel. *Expected:* Cancel never silences the "
             "question — press Build Profile once more and it is still there.",
             "Press Build Profile, tick the box and press **Build here "
             "anyway**. *Expected:* the build runs; afterwards `runs/run1/old/` "
             "holds the previous profile and "
             "`runs/run1/verifications/old/` holds the four dated folders, "
             "both under the same timestamp. Nothing is deleted.",
             "**Undo by re-copying the project from the zip**, then try the "
             "other branch: press Build Profile and choose **Duplicate the run "
             "and build there**. *Expected:* the bar's own Duplicate "
             "confirmation appears, the copy becomes the selected run, and "
             "run 1 keeps its profile and all four verifications.",
             "Back on the original copy: Create Chart, Run type = Profiling, "
             "press **Generate Chart**. *Expected:* the W4 window — “This "
             "would undo the whole run, not just its chart” — naming the "
             "measurement, the profile **and** the 4 verifications.",
             "Set Run type = **Verification** and press Generate Chart. "
             "*Expected:* the W5 window — “The verification measurements "
             "already made in this run used the chart you are about to "
             "replace”, which before this release said nothing at all."])
def build_verify_history(root: Path) -> None:
    name = "Demo-06-Verification-History"
    p = root / name
    _write_manifest(p, name, ["run1"], "run1", 3)
    r = p / "runs" / "run1"
    _chart_files(r, name, patches=RUN_PATCHES, rows=RUN_ROWS)
    (r / f"{name}.ti3").write_text(_ti3_from_ti2(r / f"{name}.ti2"))
    _build_icc(r, name)
    # …and a verification chart that is smaller than the run's, from printtarg.
    _chart_files_printtarg(r / "verifications", f"{name}-verify",
                           patches=VERIFY_PATCHES)
    vti2 = r / "verifications" / f"{name}-verify.ti2"
    start = datetime(2026, 2, 14, 10, 30)
    for i, de in enumerate((0.7, 1.1, 1.4, 2.2)):
        _verification(r, name, start + timedelta(days=45 * i), de,
                      source_ti2=vti2)
    _meta(r, "run1")


@case(name="Demo-07-Nothing-To-Lose",
      layout="targen only / images only",
      covers=["§4a row 1 — nothing on disk",
              "§4a row 2 — a patch list is not a chart",
              "§4a row 7 — page images with no chart behind them",
              "§4a row 8 — dot-files are the operating system's, not the chart's"],
      steps=["Try **Generate Chart** in each of the four runs in turn.",
             "*Expected in every one: no warning.* run 1 is empty, run 2 has "
             "only a patch list (.ti1), run 3 has only page images, run 4 has "
             "only a `.DS_Store`. None of them holds work, so there is nothing "
             "a warning could protect."])
def build_nothing_to_lose(root: Path) -> None:
    name = "Demo-07-Nothing-To-Lose"
    p = root / name
    _write_manifest(p, name, ["run1", "run2", "run3", "run4"], "run1", 3)
    for rid in ("run1", "run2", "run3", "run4"):
        (p / "runs" / rid).mkdir(parents=True, exist_ok=True)
        _meta(p / "runs" / rid, rid)
    r2 = p / "runs" / "run2"
    subprocess.run([_argyll("targen"), "-v0", "-d2", "-G", "-f60", name],
                   cwd=r2, check=True, capture_output=True, timeout=300)
    for f in r2.glob(f"{name}.*"):
        if f.suffix != ".ti1":
            f.unlink()
    for i in (1, 2):
        _write_tiff(p / "runs" / "run3" / f"{name}_{i:02d}.tif", 9)
    (p / "runs" / "run4" / ".DS_Store").write_bytes(b"\x00" * 16)


@case(name="Demo-08-Many-Runs",
      layout="mixed — printtarg and ChromIQ layout engine",
      covers=["a project with a real history: six runs in every state at once",
              "§6e row 4 — the silence is per run, not global",
              "§4 the whole table, run by run, in one project"],
      steps=["This is the project to keep open while you work through the "
             "others: every run is in a different state, so the same button "
             "produces a different window depending only on which run is "
             "selected.",
             "run 1 — chart only. run 2 — partial measurement. run 3 — "
             "complete measurement. run 4 — measurement and profile. run 5 — "
             "measurement, profile and two verifications. run 6 — a printtarg "
             "chart with no layout recipe.",
             "Step through runs 1 to 6 pressing **Generate Chart** in each, "
             "cancelling every time. *Expected:* silence, then the partial "
             "wording, the finished wording, the profile added, the W4 "
             "wording, and finally the “pages cannot be redrawn” paragraph.",
             "In run 5, silence the Build Profile question with the checkbox, "
             "then switch to a different run and press Build Profile there. "
             "*Expected:* it asks again — the silence is remembered for one "
             "run only, and only until you close ChromIQ."])
def build_many_runs(root: Path) -> None:
    name = "Demo-08-Many-Runs"
    p = root / name
    rids = [f"run{i}" for i in range(1, 7)]
    _write_manifest(p, name, rids, "run5", 3)

    r = p / "runs" / "run1"
    _chart_files(r, name, patches=RUN_PATCHES, rows=RUN_ROWS)
    _meta(r, "run1", status="in_progress")

    r = p / "runs" / "run2"
    _chart_files(r, name, patches=RUN_PATCHES, rows=RUN_ROWS)
    ti3 = r / f"{name}.ti3"
    ti3.write_text(_ti3_from_ti2(r / f"{name}.ti2"))
    _truncate_ti3(ti3, 120)
    _meta(r, "run2", status="in_progress")

    for rid, profile in (("run3", False), ("run4", True)):
        r = p / "runs" / rid
        _chart_files(r, name, patches=RUN_PATCHES, rows=RUN_ROWS)
        (r / f"{name}.ti3").write_text(_ti3_from_ti2(r / f"{name}.ti2"))
        if profile:
            _build_icc(r, name)
        _meta(r, rid)

    r = p / "runs" / "run5"
    _chart_files(r, name, patches=RUN_PATCHES, rows=RUN_ROWS)
    (r / f"{name}.ti3").write_text(_ti3_from_ti2(r / f"{name}.ti2"))
    _build_icc(r, name)
    _chart_files(r / "verifications", f"{name}-verify",
                 patches=VERIFY_PATCHES, rows=VERIFY_ROWS)
    vti2 = r / "verifications" / f"{name}-verify.ti2"
    for i, de in enumerate((0.9, 1.6)):
        _verification(r, name, datetime(2026, 4, 3, 9, 0) + timedelta(days=60 * i),
                      de, source_ti2=vti2)
    (r / "reports").mkdir(exist_ok=True)
    (r / "reports" / "report_2026-04-01_09-00-00.json").write_text(
        _report(name, datetime(2026, 4, 1, 9, 0), 1.2))
    _meta(r, "run5")

    r = p / "runs" / "run6"
    _chart_files_printtarg(r, name, patches=RUN_PATCHES)
    (r / f"{name}.ti3").write_text(_ti3_from_ti2(r / f"{name}.ti2"))
    _meta(r, "run6")


# ---------------------------------------------------------------------------
# the document
# ---------------------------------------------------------------------------
HARDWARE_ONLY = [
    ("§1 rows 1–4, 6–12 — every way a measurement can end (M-END)",
     "needs a reading session in progress"),
    ("§1 row 5 — ending with nothing read (M-END-EMPTY)",
     "needs a reading session in progress"),
    ("§3a / §2a — the file a session wrote holds no readings (M-TI3-EMPTY)",
     "needs a session that ends before the first patch is read"),
    ("§3b — a resume ended with fewer readings than it started with "
     "(M-TI3-SHRANK)",
     "needs a resumed session against a real instrument"),
    ("§7 — instrument, calibration and strip-reading events",
     "all of them come from the instrument itself"),
]


def _patch_count(ti2: Path) -> "int | None":
    """What ``targen`` actually produced. It rounds a requested count up to fit
    its generator, so the number on screen is never quite the number asked
    for — and the document must quote the one the tester will see."""
    try:
        for line in ti2.read_text(errors="replace").splitlines():
            if line.startswith("NUMBER_OF_SETS"):
                return int(line.split()[1])
    except Exception:      # noqa: BLE001
        pass
    return None


def _real_counts(dest: Path, name: str) -> "tuple[int | None, int | None]":
    """(run chart patches, verification chart patches) for a built project."""
    runs = sorted((dest / name / "runs").glob("run*")) if (dest / name).exists() else []
    run_n = verify_n = None
    for r in runs:
        for ti2 in r.glob("*.ti2"):
            run_n = run_n or _patch_count(ti2)
        for ti2 in (r / "verifications").glob("*.ti2"):
            verify_n = verify_n or _patch_count(ti2)
    return run_n, verify_n


def _document(cases, dest: Path) -> str:
    out = ["# ChromIQ demo package — Unified Measurement Management",
           "",
           "Built by `scripts/make_demo_package.py` from ChromIQ "
           f"{_app_version()}, on {datetime.now():%Y-%m-%d}.",
           "",
           "Every project here exists to raise one specific window from the "
           "model in "
           "[issue #130](https://github.com/itsab1989/ChromIQ/issues/130) — the "
           "specification is in the repository at "
           "`docs/design/unified_measurement_management.md`.",
           "",
           "## Before you start",
           "",
           "1. Unzip the package.",
           "2. Copy the `Demo-*` folders into your ChromIQ folder "
           "(`~/ChromIQ/` on macOS and Linux, `Documents\\ChromIQ\\` on "
           "Windows). They are ordinary project folders.",
           "3. Start ChromIQ and pick the project by name in the Profile-run "
           "bar.",
           "",
           "**Nothing here needs an instrument.** Every step below is a button "
           "press and a window; no measurement is ever taken. Cancel is always "
           "safe, and where a step does change files, it says so and says "
           "where the originals go.",
           "",
           "**Work on a copy.** Several steps deliberately archive files into "
           "`old/`. Keep the zip so you can put a project back to its starting "
           "state by copying it again.",
           "",
           "## What is in the package",
           "",
           "| Project | Chart made by | What it is for |",
           "|---|---|---|"]
    for c in cases:
        out.append(f"| `{c['name']}` | {c['layout']} | {c['covers'][0]} |")
    run_n, verify_n = _real_counts(dest, "Demo-06-Verification-History")
    out += ["",
            "Verification charts are deliberately **smaller** than the run "
            f"charts they sit under ({verify_n} patches against {run_n} in "
            "`Demo-06-Verification-History`), so the two are never confused on "
            "screen or on paper.",
            "",
            "Patch counts are whatever `targen` produced: it rounds a "
            "requested count up to fit its generator, so the numbers quoted "
            "below are the ones you will actually see on screen.",
            ""]

    for c in cases:
        out += [f"## {c['name']}", "",
                f"*Chart made by: {c['layout']}.*", "",
                "**Cases covered**", ""]
        out += [f"- {x}" for x in c["covers"]]
        out += ["", "**Step by step**", ""]
        n, _v = _real_counts(dest, c["name"])
        out += [f"{i}. {step.replace('{n}', str(n))}"
                for i, step in enumerate(c["steps"], 1)]
        out += [""]

    out += ["## What this package deliberately does not cover", "",
            "Knut, #130: *\"Some warnings cannot be reproduced, as they are "
            "hardware issues, so these are ignored.\"* These need an "
            "instrument on the desk and a reading in progress, so no demo "
            "project can raise them:", "",
            "| Case | Why it cannot be in a demo project |", "|---|---|"]
    out += [f"| {what} | {why} |" for what, why in HARDWARE_ONLY]
    out += ["",
            "They are covered by the automated suite instead — "
            "`tests/test_unified_ending.py`, `tests/test_measurement_session.py` "
            "and `tests/test_session_guard_wiring.py` drive those paths with a "
            "replayed instrument.", ""]
    return "\n".join(out)


def _app_version() -> str:
    ns: dict = {}
    exec((ROOT / "core" / "version.py").read_text(), ns)
    return ns.get("APP_VERSION", "?")


# ---------------------------------------------------------------------------
def build_all(dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for i, c in enumerate(CASES, 1):
        print(f"[{i}/{len(CASES)}] {c['name']} …", flush=True)
        c["fn"](dest)
    (dest / "README.md").write_text(_document(CASES, dest))
    return dest


def zip_up(folder: Path) -> Path:
    archive = folder.with_suffix(".zip")
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(folder.parent))
    return archive


# ---------------------------------------------------------------------------
# the package checks its own claims
# ---------------------------------------------------------------------------
#: What each run must actually make the app decide. Written as the *outcome*
#: rather than the file list, because a demo project whose document promises a
#: window it cannot raise is worse than no demo project at all — the tester
#: concludes the feature is broken. Verified by :func:`verify`, which calls the
#: same functions the windows call.
EXPECTED = {
    "Demo-01-Chart-Only":            {"run1": ("chart", False)},
    "Demo-02-Partial-Measurement":   {"run1": ("chart", True)},
    "Demo-03-Complete-And-Profiled": {"run1": ("chart", True),
                                      "run1:nopages": True,
                                      "run1:noduplicate": True},
    "Demo-04-Mismatched":            {"run1": ("chart", True),
                                      "run2": ("chart", True)},
    "Demo-05-Unreadable-Measurements": {"run1": ("chart", True),
                                        "run2": ("chart", True)},
    "Demo-06-Verification-History":  {"run1": ("chart", True),
                                      "run1:w4": True,
                                      "run1:w5": True,
                                      "run1:rebuild": 4},
    "Demo-07-Nothing-To-Lose":       {"run1": ("chart", False),
                                      "run2": ("chart", False),
                                      "run3": ("chart", False),
                                      "run4": ("chart", False)},
    "Demo-08-Many-Runs":             {"run1": ("chart", False),
                                      "run2": ("chart", True),
                                      "run3": ("chart", True),
                                      "run4": ("chart", True),
                                      "run5": ("chart", True),
                                      "run5:w4": True,
                                      "run5:rebuild": 2,
                                      "run6": ("chart", True),
                                      "run6:nopages": True},
}


def verify(dest: Path) -> "list[str]":
    """Ask the real decision code what each run would do, and compare it with
    what the document says. Returns the disagreements."""
    from core.file_manager import Run
    from workflow.chart_integrity import (Blast, assess_profiling_chart,
                                          assess_verification_chart)
    from workflow.profile_rebuild_guard import assess as assess_rebuild

    problems = []
    readme = dest / "README.md"
    if readme.exists():
        text = readme.read_text()
        for token in ("{n}", "{v}", "None patches", "{c}"):
            if token in text:
                problems.append(
                    f"README.md still contains the placeholder {token!r} — "
                    "the same rule the windows follow: no placeholder reaches "
                    "the reader")
    for project, wants in EXPECTED.items():
        for key, want in wants.items():
            rid, _, aspect = key.partition(":")
            run = Run.for_dir(dest / project / "runs" / rid)
            cost = assess_profiling_chart(run)
            where = f"{project}/{rid}" + (f" [{aspect}]" if aspect else "")
            if not aspect:
                if cost.warn is not want[1]:
                    problems.append(
                        f"{where}: Generate Chart "
                        f"{'warns' if cost.warn else 'is silent'}, "
                        f"the document says the opposite")
            elif aspect == "nopages":
                if cost.can_redraw_pages:
                    problems.append(f"{where}: the pages CAN be redrawn, so no "
                                    "M-CHART-NOPAGES paragraph appears")
            elif aspect == "noduplicate":
                if cost.can_duplicate:
                    problems.append(f"{where}: Duplicate is available, so no "
                                    "M-DUPLICATE-BLOCKED paragraph appears")
            elif aspect == "w4":
                if cost.blast is not Blast.RUN_AND_HISTORY:
                    problems.append(f"{where}: blast is {cost.blast}, not W4")
            elif aspect == "w5":
                v = assess_verification_chart(run)
                if v.blast is not Blast.VERIFY_HISTORY:
                    problems.append(f"{where}: no W5 window — {v.reason}")
            elif aspect == "rebuild":
                w = assess_rebuild(run)
                if not w.needed or w.dated != want:
                    problems.append(
                        f"{where}: Build Profile warns={w.needed} "
                        f"dated={w.dated}, the document says {want}")
    return problems


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dest = Path(argv[0]) if argv else ROOT / "dist" / "demo-package"
    build_all(dest)

    problems = verify(dest)
    if problems:
        print("\nThe package does not do what its document claims:")
        for line in problems:
            print(f"  ✗ {line}")
        return 1
    print(f"\nVerified: every run raises the window its document promises "
          f"({sum(len(v) for v in EXPECTED.values())} checks).")

    archive = zip_up(dest)
    size = archive.stat().st_size / 1e6
    print(f"{archive}  ({size:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
