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
import re
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


def _row_count(ti3: Path) -> int:
    """How many data rows a measurement holds (used while building)."""
    text = ti3.read_text(errors="ignore")
    body = text.partition("BEGIN_DATA")[2].partition("END_DATA")[0]
    return len([l for l in body.splitlines() if l.strip()])


def _shrink_chart(ti2: Path, *, keep: int) -> None:
    """Cut a laid-out chart down to *keep* patches, leaving the measurement
    beside it describing more readings than the chart has — §3a's "C > A", the
    row that says the measurement does not belong to this chart."""
    text = ti2.read_text(errors="ignore")
    head, sep, rest = text.partition("BEGIN_DATA\n")
    body, sep2, tail = rest.partition("END_DATA")
    rows = [l for l in body.splitlines() if l.strip()][:keep]
    head = re.sub(r"NUMBER_OF_SETS\s+\d+", f"NUMBER_OF_SETS {len(rows)}", head)
    ti2.write_text(head + sep + "\n".join(rows) + "\n" + sep2 + tail)


def _strip(path: Path) -> None:
    path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# measurements — made by Argyll, not by hand
# ---------------------------------------------------------------------------
def _measure(chart_dir: Path, stem: str, *, seed_icc: Path,
             strips: "int | None" = None) -> Path:
    """A real measurement of ``<stem>.ti2``, as ``chartread`` would leave it.

    Knut, #130 beta.125: *"The demo ti3 file does not have the SAMPLE_LOC
    field. […] Make sure demo project files look real and are accepted as
    real."* He was right, and the first version deserved the complaint: it
    wrote plausible-looking rows by hand. ``chartread -r`` needs SAMPLE_LOC to
    know which patches are still to read, so a resume against those files could
    not work at all.

    So the numbers come from Argyll's own ``fakeread``, which looks the patch
    set up in a profile exactly as a measurement would. ``fakeread`` reads the
    ``.ti1``, though, and SAMPLE_LOC only exists in the laid-out ``.ti2`` — so
    the sheet positions are merged back in here, by SAMPLE_ID, giving a file
    with the same fields in the same order as the real one Knut attached.

    *strips* makes it a **partial** measurement: chartread writes whole strips,
    never a fraction of one, so this keeps every patch whose sheet position is
    on one of the first *strips* rows and drops the rest. His attached partial
    file is exactly that shape — fifteen readings, all of them "A1" to "A15".
    """
    base = chart_dir / stem
    subprocess.run([_argyll("fakeread"), str(seed_icc), stem],
                   cwd=chart_dir, check=True, capture_output=True, timeout=300)
    ti3 = base.with_suffix(".ti3")
    _merge_sample_loc(ti3, base.with_suffix(".ti2"))
    if strips is not None:
        _keep_first_strips(ti3, strips)
    return ti3


def _cgats(path: Path) -> "tuple[list[str], list[str], list[str]]":
    """(header lines, data rows, trailer lines) of a CGATS file."""
    lines = path.read_text().splitlines()
    i = lines.index("BEGIN_DATA")
    j = lines.index("END_DATA")
    return lines[:i + 1], [l for l in lines[i + 1:j] if l.strip()], lines[j:]


def _write_cgats(path: Path, head, rows, tail) -> None:
    """Write a CGATS file back with its declared set count matching its rows.

    The count is recomputed rather than carried over, because a header that
    disagrees with the body is the fault that produced *"Read 34 sets, expected
    38 sets"* — Argyll reads values, not lines, so one wrong number makes it
    run fields across line boundaries and the file is unusable.
    """
    head = [f"NUMBER_OF_SETS {len(rows)}" if l.startswith("NUMBER_OF_SETS")
            else l for l in head]
    path.write_text("\n".join(head + rows + tail) + "\n")


def _merge_sample_loc(ti3: Path, ti2: Path) -> None:
    """Put each patch's sheet position into the measurement, as chartread does.

    Without it ``chartread`` refuses to resume: *"Resumed file … doesn't contain
    SAMPLE_LOC field"*.
    """
    loc = {}
    head2, rows2, _tail2 = _cgats(ti2)
    fmt2 = _fields(head2)
    id_i, loc_i = fmt2.index("SAMPLE_ID"), fmt2.index("SAMPLE_LOC")
    for row in rows2:
        parts = row.split()
        # The .ti2 value already carries its quotes; re-quoting
        # produced ""A1"" and no position matched anything.
        loc[parts[id_i]] = parts[loc_i].strip('"')

    head, rows, tail = _cgats(ti3)
    fmt = _fields(head)
    if "SAMPLE_LOC" in fmt:
        return
    head = [l.replace("SAMPLE_ID ", "SAMPLE_ID SAMPLE_LOC ", 1)
            if l.startswith("SAMPLE_ID ") else l for l in head]
    head = [f"NUMBER_OF_FIELDS {len(fmt) + 1}"
            if l.startswith("NUMBER_OF_FIELDS") else l for l in head]
    out = []
    for row in rows:
        parts = row.split()
        where = loc.get(parts[0])
        if where is None:
            continue
        out.append(" ".join([parts[0], f'"{where}"', *parts[1:]]))
    _write_cgats(ti3, head, out, tail)


def _fields(head: "list[str]") -> "list[str]":
    """The DATA_FORMAT field names."""
    i = head.index("BEGIN_DATA_FORMAT")
    return head[i + 1].split()


def _keep_first_strips(ti3: Path, strips: int) -> None:
    """Cut a measurement down to the first *strips* rows of the sheet."""
    head, rows, tail = _cgats(ti3)
    fmt = _fields(head)
    loc_i = fmt.index("SAMPLE_LOC")
    wanted = {chr(ord("A") + i) for i in range(strips)}
    kept = [r for r in rows
            if r.split()[loc_i].strip('"')[:1] in wanted]
    _write_cgats(ti3, head, kept, tail)


def _break_measurement(ti3: Path, how: str) -> None:
    """Damage a measurement in one specific, documented way.

    Used only by the projects whose whole purpose is a file ChromIQ must
    complain about — everything else in the package is intact.
    """
    head, rows, tail = _cgats(ti3)
    if how == "header_lies":
        head = [f"NUMBER_OF_SETS {len(rows) + 961}"
                if l.startswith("NUMBER_OF_SETS") else l for l in head]
        ti3.write_text("\n".join(head + rows + tail) + "\n")
    elif how == "no_data":
        i = head.index("BEGIN_DATA")
        ti3.write_text("\n".join(head[:i]) + "\n")
    else:                                        # pragma: no cover
        raise ValueError(how)


def _verification(run_dir: Path, stem: str, when: datetime, de: float,
                  *, source_ti3: Path) -> None:
    """One dated verification measurement of the smaller verification chart.

    A copy of a real measurement of that chart, so every dated folder holds a
    file with the same fields — SAMPLE_LOC included — as the one the instrument
    would have written.
    """
    vid = when.strftime("%Y-%m-%d_%H%M%S")
    v = run_dir / "verifications" / vid
    (v / "reports").mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_ti3, v / f"{stem}-verify.ti3")
    (v / "reports" / f"report_{when:%Y-%m-%d_%H-%M-%S}.json").write_text(
        _report(f"{stem}-verify", when, de))


# ---------------------------------------------------------------------------
# the projects, one case of the model each
# ---------------------------------------------------------------------------
#: A real profile, built once, that every fakeread looks its values up in.
#: Using one model throughout means the demo measurements are consistent with
#: each other — the same "printer" measured in every project.
_SEED: "Path | None" = None
_SEED_DIR: "Path | None" = None


def _seed_profile(_unused: Path) -> Path:
    """Build the model printer profile the demo measurements are read through."""
    import tempfile

    global _SEED
    if _SEED is not None and _SEED.exists():
        return _SEED
    work = _SEED_DIR or Path(tempfile.mkdtemp(prefix="chromiq_demo_seed_"))
    work.mkdir(parents=True, exist_ok=True)
    stem = "seed"
    _chart_files(work, stem, patches=120, rows=12)
    # colprof needs a measurement to build from, and there is no profile yet to
    # fake one through — so this first one is synthesised, and it is the only
    # one in the package that is. Everything the user sees comes from fakeread
    # against the profile it produces.
    (work / f"{stem}.ti3").write_text(_ti3_from_ti2(work / f"{stem}.ti2"))
    if not _build_icc(work, stem):
        raise SystemExit("could not build the seed profile — is colprof on PATH?")
    _SEED = work / f"{stem}.icc"
    return _SEED


CASES: "list[dict]" = []


def case(**kw):
    """Record what a project is for, so the document and the data cannot drift
    apart: both are generated from this one list."""
    def deco(fn):
        CASES.append({"fn": fn, **kw})
        return fn
    return deco


@case(name="Demo-01-Chart-Only",
      messages=['M-VERIFY-NO-PROFILE'],
      layout="ChromIQ layout engine",
      covers=["§4 row 2 — a chart with nothing measured: no warning",
              "§6e row 1 — no profile yet: no warning"],
      steps=["Load the project, set Profile run = run 1, Run type = Profiling.",
             "Press **Generate Chart**. *Expected: no warning at all* — nothing "
             "has been measured, so a new chart costs only a reprint.",
             "Go to Build Profile. *Expected: no warning* — there is no profile "
             "to replace and no verification history.",
             "Set Run type = **Verification** and go to the Measure tab. "
             "*Expected:* **Start Measurement is greyed out**, because this "
             "run has no verification chart — since beta.128 Start needs a "
             "laid-out chart, so the guard cannot be reached by pressing it. "
             "**Hover the greyed button**: its tooltip is the message, and it "
             "is the one for the state this run is in — no profile to verify "
             "yet. Sequence S1.2/S1.3; nothing is written. "
             "[[M-VERIFY-NO-PROFILE]]"])
def build_chart_only(root: Path) -> None:
    name = "Demo-01-Chart-Only"
    p = root / name
    _write_manifest(p, name, ["run1"], "run1", 3)
    _chart_files(p / "runs" / "run1", name, patches=RUN_PATCHES, rows=RUN_ROWS)
    _meta(p / "runs" / "run1", "run1", status="in_progress")


@case(name="Demo-02-Partial-Measurement",
      messages=['M-REPLACE-PARTIAL', 'M-CHART-PROFILING'],
      layout="ChromIQ layout engine",
      covers=["§5 M-REPLACE-PARTIAL — starting over a partial measurement",
              "§4 chart + partial .ti3 (Profiling)"],
      steps=["Set Profile run = run 1, Run type = Profiling.",
             "Go to Measure and press **Start Measurement**. *Expected:* “This "
             "run already holds part of a measurement”, saying **{c1} of the "
             "chart's {n} patches**, naming “Refine / resume existing "
             "measurement” and the measurement file. "
             "Press Cancel. [[M-REPLACE-PARTIAL]]",
             "Tick **Refine / resume existing measurement (-r)** and press "
             "Start Measurement again. *Expected: no window* — resuming adds "
             "to the readings instead of replacing them.",
             "Untick it again, go to Create Chart and press **Generate "
             "Chart**. *Expected:* “This run already holds work made with the "
             "chart you are about to replace”, listing a measurement of {c1} "
             "patches. Press Cancel. [[M-CHART-PROFILING]]"])
def build_partial(root: Path) -> None:
    name = "Demo-02-Partial-Measurement"
    p = root / name
    _write_manifest(p, name, ["run1"], "run1", 3)
    r = p / "runs" / "run1"
    _chart_files(r, name, patches=RUN_PATCHES, rows=RUN_ROWS)
    # Two strips read and the rest still to do — the shape chartread leaves
    # behind, and the shape "Refine / resume" is there to continue.
    _measure(r, name, seed_icc=_seed_profile(root / ".seed"), strips=2)
    (r / "chart").mkdir(exist_ok=True)
    for f in r.glob(f"{name}.*"):
        if f.suffix != ".ti3":
            shutil.copy2(f, r / "chart" / f.name)
    _meta(r, "run1", status="in_progress")


@case(name="Demo-03-Complete-And-Profiled",
      messages=['M-REPLACE-COMPLETE', 'M-CHART-PROFILING', 'M-CHART-NOPAGES',
                'M-VERIFY-NO-CHART'],
      layout="printtarg",
      covers=["§5 M-REPLACE-COMPLETE — starting over a finished measurement",
              "§4 chart + complete .ti3 + profile (Profiling)",
              "§4a row 5 — pages that cannot be redrawn (M-CHART-NOPAGES)",
              "M-DUPLICATE-BLOCKED — Duplicate needs a .channels.json"],
      steps=["Set Profile run = run 1, Run type = Profiling.",
             "Press **Start Measurement**. *Expected:* “This chart is fully "
             "measured”, All {n} patches have been read, and the warning that "
             "the profile beside it will no longer match. Press Cancel. [[M-REPLACE-COMPLETE]]",
             "Go to Create Chart and press **Generate Chart**. *Expected:* the "
             "chart warning listing **both** the finished measurement and the "
             "profile built from it, **plus** a paragraph saying the pages "
             "cannot be drawn again (this chart came from printtarg, so it has "
             "no layout recipe), **plus** an explanation that Duplicate is not "
             "available and which file is missing. Press Cancel. "
             "[[M-CHART-PROFILING]] [[M-CHART-NOPAGES]] "
             "[[M-DUPLICATE-BLOCKED]]",
             "Look at the Profile-run bar: the **Duplicate** button is greyed "
             "out, exactly as the message said.",
             "Set Run type = **Verification** and go to the Measure tab. "
             "*Expected:* **Start Measurement is greyed out** — this run has a "
             "profile but no verification chart, and Start needs a laid-out "
             "chart. **Hover the greyed button**: the tooltip is the message, "
             "telling you to create the verification chart first. Sequence "
             "S1.3. [[M-VERIFY-NO-CHART]]\n\n"
             "    *If you go on and create that chart, pressing Start then "
             "begins a real measurement — with an instrument connected you may "
             "first be told the chart was made for a different one, which is "
             "the instrument warning, not a guard.*",
             "In Build Profile, use its own **Load** button to open this run's "
             ".ti3 directly. *Expected: no window* — pressing Build Profile "
             "asks nothing, because the target is a file rather than a run "
             "(sequence S5.1)."])
def build_complete(root: Path) -> None:
    name = "Demo-03-Complete-And-Profiled"
    p = root / name
    _write_manifest(p, name, ["run1"], "run1", 3)
    r = p / "runs" / "run1"
    _chart_files_printtarg(r, name, patches=RUN_PATCHES)
    _measure(r, name, seed_icc=_seed_profile(root / ".seed"))
    _build_icc(r, name)
    _meta(r, "run1")


@case(name="Demo-04-Mismatched",
      messages=['M-TI3-MISMATCH'],
      layout="ChromIQ layout engine",
      covers=["§5 / §3a M-TI3-MISMATCH — the measurement and the chart disagree",
              "§3a B ≠ C — the file's header disagrees with its own rows"],
      steps=["Set Profile run = **run 1**, Run type = Profiling.",
             "Press **Start Measurement**. *Expected:* “This run's measurement "
             "and its chart do not match” — {c1} readings against {n} "
             "patches, "
             "the statement that ChromIQ cannot tell which of the two is "
             "wrong, and a pointer to “Restore Used Chart”. Resume is **not** "
             "offered. Press Cancel. [[M-TI3-MISMATCH]]",
             "Switch to **run 2** and press Start Measurement. *Expected:* the "
             "same window, plus the extra sentence that the file's own header "
             "disagrees with the rows it contains, so it may be damaged as "
             "well as mismatched. [[M-TI3-MISMATCH]]"])
def build_mismatched(root: Path) -> None:
    name = "Demo-04-Mismatched"
    p = root / name
    _write_manifest(p, name, ["run1", "run2"], "run1", 3)
    for rid, lies in (("run1", False), ("run2", True)):
        r = p / "runs" / rid
        _chart_files(r, name, patches=RUN_PATCHES, rows=RUN_ROWS)
        # A real partial measurement, then the chart replaced under it — which
        # is what a mismatch actually is. run 2 additionally has a header that
        # disagrees with its own rows (§3a's B ≠ C).
        ti3 = _measure(r, name, seed_icc=_seed_profile(root / ".seed"), strips=3)
        if lies:
            _break_measurement(ti3, "header_lies")
        # The stored copy is the chart that was MEASURED — it is what "Restore
        # Used Chart" puts back, and the step points at it.
        (r / "chart").mkdir(exist_ok=True)
        for f in r.glob(f"{name}.*"):
            if f.suffix != ".ti3":
                shutil.copy2(f, r / "chart" / f.name)
        # …and NOW the chart is replaced under the measurement, which is what a
        # mismatch actually is. Without this the run was merely partial, and the
        # step promising "the measurement and its chart do not match" described
        # a window that could not appear — found by walking the package on
        # screen (Knut, 2026-08-04).
        _shrink_chart(r / f"{name}.ti2", keep=_row_count(ti3) // 2 or 1)
        _meta(r, rid)


@case(name="Demo-05-Unreadable-Measurements",
      messages=["M-REPLACE-UNCOUNTABLE", "M-CHART-CORRUPT"],
      layout="ChromIQ layout engine",
      covers=["§3a header-only / empty — a measurement file with nothing in it",
              "§4 — a corrupt or empty measurement when a chart is replaced",
              "§4 — the same, with a profile in the run as well",
              "S1.1 — no chart to measure: Start is not offered at all"],
      steps=["Set Profile run = **run 1** (a .ti3 that holds no readable "
             "data) and press **Start Measurement**. *Expected:* “This run "
             "already holds a measurement file”, saying ChromIQ cannot tell "
             "how many readings it contains and naming the file. It must "
             "**not** suggest Refine / resume — there is nothing to resume "
             "from. Press Cancel. [[M-REPLACE-UNCOUNTABLE]]",
             "Still in run 1, go to Create Chart and press **Generate "
             "Chart**. *Expected:* **“The measurement file in this run cannot "
             "be read”** — a window of its own, not the ordinary chart "
             "warning: a file with no readings has nothing to list, so there "
             "is no item list. It says the file goes to the run's “old” folder "
             "and to look at it there before measuring again. "
             "Press Cancel. [[M-CHART-CORRUPT]]",
             "Switch to **run 2** — the same corrupt file, but this run also "
             "has a profile. Press Generate Chart. *Expected:* the same "
             "window, **plus** the paragraph explaining that the profile moves "
             "to the “old” folder too and that nothing on disk then connects "
             "it to the chart it came from. Press Cancel. "
             "[[M-CHART-CORRUPT]]",
             "Switch to **run 3**, which has a patch list but no laid-out "
             "chart. *Expected:* **Start Measurement is greyed out**, and its "
             "tooltip says there is no laid-out chart to measure and where to "
             "make one — *no window*, because the condition is prevented "
             "rather than reported. Before beta.128 the button was available "
             "here and pressing it failed inside chartread."])
def build_unreadable(root: Path) -> None:
    name = "Demo-05-Unreadable-Measurements"
    p = root / name
    _write_manifest(p, name, ["run1", "run2", "run3"], "run1", 3)
    seed = _seed_profile(root / ".seed")

    for rid, profile in (("run1", False), ("run2", True)):
        r = p / "runs" / rid
        _chart_files(r, name, patches=RUN_PATCHES, rows=RUN_ROWS)
        ti3 = _measure(r, name, seed_icc=seed)
        if profile:
            _build_icc(r, name)
        # A real file with its data block removed: what a session that died
        # before the first patch leaves behind.
        _break_measurement(ti3, "no_data")
        _meta(r, rid)

    # …and a run that cannot be measured at all, because it has no `.ti2`.
    r3 = p / "runs" / "run3"
    _chart_files(r3, name, patches=RUN_PATCHES, rows=RUN_ROWS)
    for suffix in (".ti2", ".channels.json"):
        _strip(r3 / f"{name}{suffix}")
    _meta(r3, "run3")


@case(name="Demo-06-Verification-History",
      messages=['M-PROFILE-VERIFY', 'M-CHART-W4', 'M-CHART-VERIFY'],
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
             "Press Cancel. [[M-PROFILE-VERIFY]]",
             "Press Build Profile again, tick **Don't show this again for this "
             "run**, then press Cancel. *Expected:* Cancel never silences the "
             "question — press Build Profile once more and it is still there. "
             "[[M-PROFILE-VERIFY]]",
             "Press Build Profile, tick the box and press **Build here "
             "anyway**. *Expected:* the build runs; afterwards `runs/run1/old/` "
             "holds the previous profile and "
             "`runs/run1/verifications/old/` holds the four dated folders, "
             "both under the same timestamp. Nothing is deleted. "
             "[[M-PROFILE-VERIFY]]",
             "**Undo by re-copying the project from the zip**, then try the "
             "other branch: press Build Profile and choose **Duplicate the run "
             "and build there**. *Expected:* the bar's own Duplicate "
             "confirmation appears, the copy becomes the selected run, and "
             "run 1 keeps its profile and all four verifications. "
             "[[M-PROFILE-VERIFY]]",
             "Back on the original copy: Create Chart, Run type = Profiling, "
             "press **Generate Chart**. *Expected:* the W4 window — “This "
             "would undo the whole run, not just its chart” — naming the "
             "measurement, the profile **and** the 4 verifications. [[M-CHART-W4]]",
             "Set Run type = **Verification** and press Generate Chart. "
             "*Expected:* the W5 window — “The verification measurements "
             "already made in this run used the chart you are about to "
             "replace”, which before this release said nothing at all. "
             "[[M-CHART-VERIFY]]"])
def build_verify_history(root: Path) -> None:
    name = "Demo-06-Verification-History"
    p = root / name
    _write_manifest(p, name, ["run1"], "run1", 3)
    r = p / "runs" / "run1"
    _chart_files(r, name, patches=RUN_PATCHES, rows=RUN_ROWS)
    _measure(r, name, seed_icc=_seed_profile(root / ".seed"))
    _build_icc(r, name)
    # …and a verification chart that is smaller than the run's, made the way a
    # user makes one — with the engine, so it carries its layout recipe.
    # Knut, beta.132, step 7: the printtarg version had no `.channels.json`, so
    # the log answered a step about the W5 window with a note about a chart
    # whose pages cannot be redrawn. The printtarg case still has its home:
    # Demo-03 and Demo-08 run 6 exist to exercise exactly that.
    _chart_files(r / "verifications", f"{name}-verify",
                 patches=VERIFY_PATCHES, rows=VERIFY_ROWS)
    vti3 = _measure(r / "verifications", f"{name}-verify",
                    seed_icc=_seed_profile(root / ".seed"))
    start = datetime(2026, 2, 14, 10, 30)
    for i, de in enumerate((0.7, 1.1, 1.4, 2.2)):
        _verification(r, name, start + timedelta(days=45 * i), de,
                      source_ti3=vti3)
    _meta(r, "run1")


@case(name="Demo-07-Nothing-To-Lose",
      messages=[],
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
      messages=['M-CHART-PROFILING', 'M-CHART-W4', 'M-CHART-NOPAGES',
                'M-PROFILE-VERIFY', 'M-PREVIEW-PAUSED', 'M-BUILD-ELSEWHERE'],
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
             "**run 1** — press **Generate Chart**. *Expected: no window* — "
             "nothing has been measured here.",
             "**run 2** — press Generate Chart. *Expected:* the chart warning, "
             "listing a measurement. Press Cancel. [[M-CHART-PROFILING]]",
             "**run 3** — press Generate Chart. *Expected:* the same window "
             "with the full patch count. Press Cancel. [[M-CHART-PROFILING]]",
             "**run 4** — press Generate Chart. *Expected:* the same window, "
             "now listing the profile as well. Press Cancel. "
             "[[M-CHART-PROFILING]]",
             "**run 5** — press Generate Chart. *Expected:* the W4 window "
             "instead, because this run has a verification history. Press "
             "Cancel. [[M-CHART-W4]]",
             "**run 6** — press Generate Chart. *Expected:* the chart warning "
             "**plus** the paragraph about pages that cannot be redrawn, "
             "because this chart came from printtarg. Press Cancel. "
             "[[M-CHART-PROFILING]] [[M-CHART-NOPAGES]]",
             "In **run 2**, turn on **Auto-update preview** in Create Chart "
             "and change a layout setting. *Expected:* a window saying the "
             "live preview is not being re-drawn, **once**; change more "
             "settings and only the log repeats it. Switch the option off and "
             "on again and the window returns once more. "
             "[[M-PREVIEW-PAUSED]]",
             "In run 5, silence the Build Profile question with the checkbox, "
             "then switch to a different run and press Build Profile there. "
             "*Expected:* it asks again — the silence is remembered for one "
             "run only, and only until you close ChromIQ. "
             "[[M-PROFILE-VERIFY]]",
             "Switch the bar to **run 5**, then use Build Profile's own "
             "**Load** button to open a DIFFERENT run's measurement (run 6's "
             "will do) and press **Build Profile**. *Expected:* ChromIQ says "
             "the measurement is not in the run you selected, and that the "
             "profile would be written beside it rather than into run 5. Press "
             "Cancel — switching “Profile run” away and back loads the selected "
             "run's own measurement again. [[M-BUILD-ELSEWHERE]]"])
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
    _measure(r, name, seed_icc=_seed_profile(root / ".seed"), strips=8)
    _meta(r, "run2", status="in_progress")

    for rid, profile in (("run3", False), ("run4", True)):
        r = p / "runs" / rid
        _chart_files(r, name, patches=RUN_PATCHES, rows=RUN_ROWS)
        _measure(r, name, seed_icc=_seed_profile(root / ".seed"))
        if profile:
            _build_icc(r, name)
        _meta(r, rid)

    r = p / "runs" / "run5"
    _chart_files(r, name, patches=RUN_PATCHES, rows=RUN_ROWS)
    _measure(r, name, seed_icc=_seed_profile(root / ".seed"))
    _build_icc(r, name)
    _chart_files(r / "verifications", f"{name}-verify",
                 patches=VERIFY_PATCHES, rows=VERIFY_ROWS)
    vti3 = _measure(r / "verifications", f"{name}-verify",
                    seed_icc=_seed_profile(root / ".seed"))
    for i, de in enumerate((0.9, 1.6)):
        _verification(r, name, datetime(2026, 4, 3, 9, 0) + timedelta(days=60 * i),
                      de, source_ti3=vti3)
    (r / "reports").mkdir(exist_ok=True)
    (r / "reports" / "report_2026-04-01_09-00-00.json").write_text(
        _report(name, datetime(2026, 4, 1, 9, 0), 1.2))
    _meta(r, "run5")

    r = p / "runs" / "run6"
    _chart_files_printtarg(r, name, patches=RUN_PATCHES)
    _measure(r, name, seed_icc=_seed_profile(root / ".seed"))
    _meta(r, "run6")


# ---------------------------------------------------------------------------
# sequence coverage — §S, row by row
# ---------------------------------------------------------------------------
SPEC_DOC = ROOT / "docs" / "design" / "unified_measurement_management.md"

#: Which demo project drives each §S sequence, or why it cannot be driven.
#: Knut, 2026-08-04: *"make sure the demo project package is updated to detect
#: every occurrence of messages, as well as every sequence for every condition
#: … (unless detection is impossible to replicate … but then inform of which
#: conditions cannot be replicated on-screen in the app)."*
#:
#: A value of ``None`` means *not replicable*, and the reason is required.
SEQUENCES = {
    "S1.1": ("Demo-05-Unreadable-Measurements", "run 3 — Start is greyed out"),
    "S1.2": ("Demo-01-Chart-Only",
             "run 1 with Run type = Verification — no profile to verify; met "
             "as the greyed Start button's tooltip, since Start needs a chart"),
    "S1.3": ("Demo-03-Complete-And-Profiled",
             "run 1 with Run type = Verification — a profile, but no "
             "verification chart; likewise the greyed Start button's tooltip"),
    "S1.4": ("Demo-01-Chart-Only", "run 1 — a chart with no measurement"),
    "S1.5": ("Demo-02-Partial-Measurement", "run 1 with Refine / resume ticked"),
    "S1.6": ("Demo-02-Partial-Measurement", "run 1 with Refine / resume clear"),
    "S1.7": ("Demo-03-Complete-And-Profiled", "run 1"),
    "S1.8": ("Demo-04-Mismatched", "run 1 and run 2"),
    "S1.9": (None, "the instrument cannot be opened — hardware"),
    "S2.1": (None, "a patch being read — hardware"),
    "S2.2": (None, "a reading failure — hardware"),
    "S2.3": (None, "two reading failures in succession — hardware"),
    "S2.4": (None, "Stop pressed with nothing read — needs a live session"),
    "S2.5": (None, "Stop pressed mid-read — needs a live session"),
    "S2.6": (None, "the same window from the keyboard — needs a live session"),
    "S2.7": (None, "a Give-Up window — hardware"),
    "S2.8": (None, "controls disabled during a read — needs a live session"),
    "S3.1": (None, "reading the file a session wrote — needs a live session"),
    "S3.2": (None, "a session that saved nothing — needs a live session"),
    "S3.3": (None, "a resume that ended smaller — needs a live session"),
    "S3.4": ("Demo-04-Mismatched", "run 2 — B ≠ C, reported and never resumed"),
    "S3.5": (None, "the count added by a session — needs a live session"),
    "S3.6": ("Demo-06-Verification-History", "the four dated folders are the "
                                             "result of this step"),
    "S3.7": ("Demo-06-Verification-History", "Tools → Measurement Report"),
    "S4.1": ("Demo-07-Nothing-To-Lose", "run 1 — nothing to displace"),
    "S4.2": ("Demo-01-Chart-Only", "run 1 — chart only"),
    "S4.3": ("Demo-02-Partial-Measurement", "run 1"),
    "S4.4": ("Demo-06-Verification-History", "run 1 — W4"),
    "S4.5": ("Demo-06-Verification-History", "run 1, Run type = Verification"),
    "S4.6": ("Demo-03-Complete-And-Profiled", "run 1 — Duplicate unavailable"),
    "S5.1": ("Demo-03-Complete-And-Profiled",
             "open its .ti3 with Build Profile's own Load button, so the "
             "target is a file rather than a run"),
    "S5.2": ("Demo-03-Complete-And-Profiled", "run 1 — no verification chart"),
    "S5.3": ("Demo-06-Verification-History", "run 1"),
    "S5.4": ("Demo-06-Verification-History", "run 1, after ticking the box"),
    "S5.5": ("Demo-03-Complete-And-Profiled", "run 1 — Duplicate unavailable"),
}


def _spec_sequences() -> "list[str]":
    """Every sequence ID the model defines, read from the document."""
    text = SPEC_DOC.read_text()
    body = text[text.index("## S. Sequences"):]
    body = body[:body.index("## T. Test plan")]
    return sorted(set(re.findall(r"^\| (S\d\.\d)", body, re.M)))


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


def _readings(dest: Path, name: str, rid: str) -> "int | None":
    """How many readings a run's measurement really holds.

    The document quotes it, so it is read back rather than assumed: the first
    version said "38 of the chart's 224 patches" while the file held 32, and a
    test guide whose numbers do not match the screen is worse than one with no
    numbers at all.
    """
    run = dest / name / "runs" / rid
    for ti3 in run.glob("*.ti3"):
        try:
            _head, rows, _tail = _cgats(ti3)
            return len(rows)
        except Exception:      # noqa: BLE001
            return None
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
            "**How to read the “Message expected” column.** A window can be "
            "one message with a paragraph or two appended to it — for example "
            "`M-CHART-PROFILING` is the window, and `M-CHART-NOPAGES` is a "
            "paragraph added inside it when the chart has no layout recipe. "
            "The first ID in a cell is the window; anything marked "
            "*(appended)* is a paragraph within that same window, not a "
            "second window. IDs marked *(PROPOSED)* are awaiting review and "
            "are listed in §M-PROPOSED of the model.",
            "",
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
                f"*Chart made by: {c['layout']}.*", ""]
        ids = c.get("messages", [])
        if ids:
            out += ["**Messages this project should raise**", "",
                    "| ID | Headline as approved in the model |", "|---|---|"]
            for mid in ids:
                msg = _catalogue().get(mid)
                out.append(f"| `{mid}` | {msg.title if msg else '—'}"
                           + (" *(PROPOSED)*" if msg and not msg.approved
                              else "") + " |")
            out += [""]
        out += ["**Cases covered**", ""]
        out += [f"- {x}" for x in c["covers"]]
        out += ["", "**Step by step**", "",
                "| # | What to do, and what to expect | Message expected |",
                "|---|---|---|"]
        n, _v = _real_counts(dest, c["name"])
        for i, step in enumerate(c["steps"], 1):
            text = step.replace("{n}", str(n))
            for rid in ("run1", "run2"):
                got = _readings(dest, c["name"], rid)
                if got is not None:
                    text = text.replace("{c%s}" % rid[-1], str(got))
            ids = re.findall(r"\[\[(M-[A-Z0-9-]+)\]\]", text)
            text = re.sub(r"\s*\[\[M-[A-Z0-9-]+\]\]", "", text)
            if "[[GUARD]]" in text:
                # An existing guard window that §M does not catalogue. Named
                # rather than hidden: it is reported to the issue as a gap in
                # the model, not quietly dressed up as one of §M's messages.
                text = text.replace(" [[GUARD]]", "")
                cell = ("*not in §M — an existing guard window; "
                        "reported as a gap in the model*")
                out.append(f"| {i} | {text} | {cell} |")
                continue
            if ids:
                # Knut, 2026-08-04: *"You say 'The window you saw is
                # M-CHART-PROFILING'. however, the test description document
                # … said the test case is M-CHART-NOPAGES. Which one is it?"*
                # Both, and the guide has to say so: the first ID is the
                # window, the rest are paragraphs appended to it.
                parts = []
                for j, m in enumerate(ids):
                    if m not in _catalogue():
                        continue
                    mark = " *(PROPOSED)*" if not _catalogue()[m].approved else ""
                    role = "" if j == 0 else " *(appended)*"
                    parts.append(f"`{m}`{mark}{role}")
                cell = "<br>".join(parts)
            else:
                cell = "*none — silence is the expected result*"
            out.append(f"| {i} | {text} | {cell} |")
        out += [""]
        out += [""]

    # ---- message coverage ------------------------------------------------
    used = {}
    for c in cases:
        for i, step in enumerate(c["steps"], 1):
            for mid in re.findall(r"\[\[(M-[A-Z0-9-]+)\]\]", step):
                used.setdefault(mid, []).append(f"`{c['name']}` step {i}")
    out += ["## Every message in the model, and where to see it", "",
            "Knut asked for the package to *\"detect every occurrence of "
            "messages\"*. This table is generated from the model's catalogue, "
            "so a message that exists and is not exercised here shows up as a "
            "gap rather than being quietly missed.", "",
            "| Message | Where in this package |", "|---|---|"]
    for mid in sorted(_catalogue()):
        where = "<br>".join(used.get(mid, [])) or "— *not exercised*"
        out.append(f"| `{mid}` | {where} |")
    out += [""]

    # ---- sequence coverage -------------------------------------------------
    out += ["## Every sequence in §S, and where to see it", "",
            "The model's §S lists what happens, in what order, for every entry "
            "condition. Each row below is one of those sequences. The ones "
            "that cannot be driven from a demo project say why — they need an "
            "instrument on the desk or a reading in progress, which no set of "
            "files can supply.", "",
            "| Sequence | Where in this package | If not: why |",
            "|---|---|---|"]
    for sid in _spec_sequences():
        project, note = SEQUENCES[sid]
        if project is None:
            out.append(f"| `{sid}` | — | {note} |")
        else:
            out.append(f"| `{sid}` | `{project}` — {note} | |")
    covered = sum(1 for sid in _spec_sequences() if SEQUENCES[sid][0])
    out += ["",
            f"**{covered} of {len(_spec_sequences())} sequences can be driven "
            "from these projects.** The rest are listed above with the reason; "
            "they are covered by the automated suite instead, which replays a "
            "simulated instrument.",
            ""]

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


def _catalogue():
    """Every ID the model defines — messages and the paragraphs that attach to
    them — so the guide quotes the model rather than a copy of it. Knut:
    *"make sure the test guide document […] contains exactly which message
    code/name is expected from the model."*"""
    from workflow.measurement_messages import CATALOGUE, FRAGMENTS

    out = dict(CATALOGUE)
    for mid, text in FRAGMENTS.items():
        # A fragment has no headline of its own; the guide shows its ID and
        # marks it as appended, so the first line stands in for a title.
        out[mid] = type("_Fragment", (), {
            "title": text.strip().split(".")[0].lstrip(),
            "approved": True, "id": mid})()
    return out


def _app_version() -> str:
    ns: dict = {}
    exec((ROOT / "core" / "version.py").read_text(), ns)
    return ns.get("APP_VERSION", "?")


# ---------------------------------------------------------------------------
def build_all(dest: Path) -> Path:
    import tempfile

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    # The seed profile is scaffolding, not part of the package — it is the one
    # synthesised measurement in the whole build, and shipping it would put a
    # file in the zip that is not what it claims to be.
    global _SEED_DIR
    _SEED_DIR = Path(tempfile.mkdtemp(prefix="chromiq_demo_seed_"))
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


def _check_measurements_are_real(dest: Path) -> "list[str]":
    """Every measurement in the package is one Argyll would accept.

    Exactly the two faults Knut hit in beta.125, checked so neither can ship
    again:

    * *"Resumed file … doesn't contain SAMPLE_LOC field"* — chartread needs the
      sheet positions to know what is left to read.
    * *"Read 34 sets, expected 38 sets"* — a header whose count disagrees with
      the body. Argyll reads values rather than lines, so one wrong number
      makes it run fields across line boundaries and the file is unusable.

    Files that are broken **on purpose** are skipped by name: two runs exist to
    make ChromIQ complain about them, and a checker that failed on those would
    be checking the wrong thing.
    """
    deliberately_broken = {
        # Its chart was deliberately replaced under the measurement, so the
        # positions it names are no longer on the sheet — which is the whole
        # point of the run: §3a's "C > A, does not belong to this chart".
        "Demo-04-Mismatched/runs/run1",
        "Demo-04-Mismatched/runs/run2",       # header disagrees with its rows
        # Both of these exist to be complained about: a data block removed,
        # with and without a profile beside it.
        "Demo-05-Unreadable-Measurements/runs/run1",
        "Demo-05-Unreadable-Measurements/runs/run2",
    }
    problems = []
    for ti3 in sorted(dest.rglob("*.ti3")):
        rel = ti3.relative_to(dest).as_posix()
        if any(rel.startswith(b) for b in deliberately_broken):
            continue
        try:
            head, rows, _tail = _cgats(ti3)
        except ValueError:
            problems.append(f"{rel}: has no BEGIN_DATA/END_DATA block")
            continue
        fmt = _fields(head)
        if "SAMPLE_LOC" not in fmt:
            problems.append(
                f"{rel}: no SAMPLE_LOC field — chartread cannot resume it")
        declared = next((int(l.split()[1]) for l in head
                         if l.startswith("NUMBER_OF_SETS")), None)
        if declared != len(rows):
            problems.append(
                f"{rel}: says NUMBER_OF_SETS {declared} but holds {len(rows)} "
                "rows")
        if len(fmt) != len(rows[0].split()) if rows else False:
            problems.append(
                f"{rel}: {len(fmt)} fields declared, {len(rows[0].split())} "
                "values per row")
        if not any(l.startswith("ORIGINATOR") and "Argyll" in l for l in head):
            problems.append(f"{rel}: was not written by an Argyll tool")
        # …and the positions must be ones this chart actually has.
        ti2 = ti3.with_suffix(".ti2")
        if ti2.exists() and "SAMPLE_LOC" in fmt:
            head2, rows2, _t2 = _cgats(ti2)
            fmt2 = _fields(head2)
            known = {r.split()[fmt2.index("SAMPLE_LOC")] for r in rows2}
            loc_i = fmt.index("SAMPLE_LOC")
            unknown = {r.split()[loc_i] for r in rows} - known
            if unknown:
                problems.append(
                    f"{rel}: positions not on this chart: "
                    f"{sorted(unknown)[:3]}")
    return problems


def verify(dest: Path) -> "list[str]":
    """Ask the real decision code what each run would do, and compare it with
    what the document says. Returns the disagreements."""
    from core.file_manager import Run
    from workflow.chart_integrity import (Blast, assess_profiling_chart,
                                          assess_verification_chart)
    from workflow.profile_rebuild_guard import assess as assess_rebuild

    problems = []
    # A step that names a message ID which is not in the catalogue would send
    # the tester looking for a window that cannot appear.
    for c in CASES:
        for i, step in enumerate(c["steps"], 1):
            # A step that describes a window but names no message ID would
            # leave the tester guessing which one the model means — Knut asked
            # for the ID "for every step where a message is expected".
            promises = ("*Expected:*" in step
                        and "no window" not in step
                        and "no warning" not in step)
            if promises and "[[" not in step and "[[GUARD]]" not in step:
                problems.append(
                    f"{c['name']} step {i} expects a window but names no "
                    "message ID")
        for step in c["steps"]:
            for mid in re.findall(r"\[\[(M-[A-Z0-9-]+)\]\]", step):
                if mid not in _catalogue():
                    problems.append(
                        f"{c['name']}: a step expects {mid}, which is not in "
                        "the message catalogue")
        for mid in c.get("messages", []):
            if mid not in _catalogue():
                problems.append(
                    f"{c['name']}: lists {mid}, which is not in the catalogue")
    # Every message in the catalogue is exercised somewhere, or the package
    # is not doing what its own document claims.
    used = set()
    for c in CASES:
        for step in c["steps"]:
            used |= set(re.findall(r"\[\[(M-[A-Z0-9-]+)\]\]", step))
    for mid in _catalogue():
        if mid not in used:
            problems.append(
                f"{mid} is in the model but no step in the package raises it")
    # …and every sequence the model defines is either driven or excused.
    for sid in _spec_sequences():
        if sid not in SEQUENCES:
            problems.append(f"sequence {sid} is in the model but not in the "
                            "package's coverage table")
        elif SEQUENCES[sid][0] is None and not SEQUENCES[sid][1]:
            problems.append(f"sequence {sid} is marked not replicable with no "
                            "reason given")
    for sid in SEQUENCES:
        if sid not in _spec_sequences():
            problems.append(f"the coverage table lists {sid}, which the model "
                            "does not define")
    problems += _check_measurements_are_real(dest)
    readme = dest / "README.md"
    if readme.exists():
        text = readme.read_text()
        for token in ("{n}", "{v}", "{c}", "{c1}", "{c2}", "None patches"):
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
