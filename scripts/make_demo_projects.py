"""Build demo / dummy ChromIQ projects for testing (#130, Knut 2026-07-28).

    *"Create several full demo/dummy projects with all elements, files and
    folders, measurements, charts, several runs, several verifications with
    files. Downloadable here. The dummy data shall be able to test migration
    from 3.13, as well as perform full test of verification runs and
    reporting."*

Run it::

    python scripts/make_demo_projects.py [destination]     # default ./demo-projects
    python scripts/make_demo_projects.py --zip             # also make one .zip to attach

Four projects are written:

============================  ==================================================
``Demo-Full-RGB``             schema 3, three runs: one finished (chart,
                              measurement, profile, reports, exports), one with
                              two dated verifications, one with a chart only.
``Demo-Verify-History``       one finished run with **five** dated
                              verifications, three months apart, each with its
                              own measurement and report — for exercising the
                              verification history and the report's trend.
``Demo-Legacy-v1``            **the 3.13 layout**, for migration testing.
``Demo-Legacy-v2``            the intermediate layout, with a legacy one-slot
                              ``<stem>-verify.ti3`` at the run root.
============================  ==================================================

**The legacy layouts are taken from the migration code, not from memory.**
``Project._migrate_v1_to_v2`` says exactly which files v1 kept flat *inside each
run folder* (quality checks, refine lists, scanner intermediates) — note that v1
already had ``runs/runN/``; it was the sub-folders that did not exist.
``_migrate_v2_to_v3`` says what v2 left at the run root (a single
``<stem>-verify.ti3``). Generating from those two is why these projects actually
exercise the migration rather than a guess at it.

**A caveat worth keeping.** These are synthesised. They reproduce the *shape* of
an old project faithfully, because the shape is written down in the migration
code — but a genuine 3.13 folder from a real user may hold things this does not
imagine. A real one is still worth more for a final migration check.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

CHART_EXTS = (".ti1", ".ti2", ".cht", ".ps", ".channels.json", ".strips.json")


# ---------------------------------------------------------------------------
# Small fake artefacts — real enough in shape to be recognised, small on disk
# ---------------------------------------------------------------------------
def _ti2(stem: str, patches: int, rows: int) -> str:
    rnd = random.Random(f"{stem}-ti2")
    head = [
        "CTI2", "", 'DESCRIPTOR "Argyll Calibration Target chart information 2"',
        'ORIGINATOR "Argyll printtarg"',
        f'CREATED "{datetime.now():%a %b %d %H:%M:%S %Y}"',
        'KEYWORD "APPROX_WHITE_POINT"', 'APPROX_WHITE_POINT "95.1 100.0 108.9"',
        f'NUMBER_OF_FIELDS 7', "BEGIN_DATA_FORMAT",
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y", "END_DATA_FORMAT",
        f"NUMBER_OF_SETS {patches}", "BEGIN_DATA",
    ]
    letters = "ABCDEFGHIJKLMNOP"
    for i in range(patches):
        loc = f"{letters[i // rows % len(letters)]}{i % rows + 1}"
        r, g, b = (rnd.randrange(0, 101) for _ in range(3))
        head.append(f'{i + 1} "{loc}" {r:.4f} {g:.4f} {b:.4f} '
                    f'{r * 0.9:.4f} {g * 0.95:.4f}')
    head += ["END_DATA", ""]
    return "\n".join(head)


def _ti3_from_ti2(ti2: Path, *, drift: float = 0.0) -> str:
    """A measurement of the chart that is actually there.

    Reads the real ``.ti2`` and writes one reading per patch, so the ``.ti3``
    has the same SAMPLE_IDs and device values as the chart — which is what makes
    it loadable, reportable and refinable. ``drift`` shifts every reading a
    little, so a series of verifications trends instead of repeating.
    """
    rows, fields = [], []
    in_fmt = in_data = False
    for line in ti2.read_text().splitlines():
        s = line.strip()
        if s == "BEGIN_DATA_FORMAT":
            in_fmt = True; continue
        if s == "END_DATA_FORMAT":
            in_fmt = False; continue
        if in_fmt:
            fields = s.split(); continue
        if s == "BEGIN_DATA":
            in_data = True; continue
        if s == "END_DATA":
            break
        if in_data and s:
            rows.append(s.split())
    idx = {n: i for i, n in enumerate(fields)}
    ir, ig, ib = idx.get("RGB_R"), idx.get("RGB_G"), idx.get("RGB_B")

    out = [
        "CTI3", "", 'DESCRIPTOR "Argyll Calibration Target chart information 3"',
        'ORIGINATOR "Argyll chartread"',
        f'CREATED "{datetime.now():%a %b %d %H:%M:%S %Y}"',
        'KEYWORD "DEVICE_CLASS"', 'DEVICE_CLASS "OUTPUT"',
        'KEYWORD "COLOR_REP"', 'COLOR_REP "RGB_XYZ"',
        "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
        f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA",
    ]
    rnd = random.Random(f"{ti2.name}-{drift}")
    for n, row in enumerate(rows, start=1):
        r = float(row[ir]) if ir is not None else rnd.uniform(0, 100)
        g = float(row[ig]) if ig is not None else rnd.uniform(0, 100)
        b = float(row[ib]) if ib is not None else rnd.uniform(0, 100)
        # a plausible printer: slightly dark, slightly warm, plus the drift
        j = rnd.uniform(-0.35, 0.35)
        x = max(0.0, r * 0.86 + b * 0.14 + drift + j)
        y = max(0.0, g * 0.92 + r * 0.06 + drift + j)
        z = max(0.0, b * 1.02 + drift + j)
        out.append(f"{n} {r:.4f} {g:.4f} {b:.4f} {x:.4f} {y:.4f} {z:.4f}")
    out += ["END_DATA", ""]
    return "\n".join(out)


def _ti3(stem: str, patches: int, *, drift: float = 0.0) -> str:
    rnd = random.Random(f"{stem}-ti3-{drift}")
    head = [
        "CTI3", "", 'DESCRIPTOR "Argyll Calibration Target chart information 3"',
        'ORIGINATOR "Argyll chartread"',
        f'CREATED "{datetime.now():%a %b %d %H:%M:%S %Y}"',
        'KEYWORD "DEVICE_CLASS"', 'DEVICE_CLASS "OUTPUT"',
        'KEYWORD "COLOR_REP"', 'COLOR_REP "RGB_XYZ"',
        "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
        f"NUMBER_OF_SETS {patches}", "BEGIN_DATA",
    ]
    for i in range(patches):
        r, g, b = (rnd.randrange(0, 101) for _ in range(3))
        head.append(f"{i + 1} {r:.4f} {g:.4f} {b:.4f} "
                    f"{r * 0.9 + drift:.4f} {g * 0.95 + drift:.4f} "
                    f"{b * 1.08 + drift:.4f}")
    head += ["END_DATA", ""]
    return "\n".join(head)


def _build_icc(run_dir: Path, stem: str) -> bool:
    """Build a REAL ICC profile from the run's measurement, with colprof.

    A stub of the right size would have been quicker, and would have been the
    same mistake as the stub TIFFs: a demo project whose profile cannot be
    opened, inspected or soft-proofed tests nothing. Returns False (with a
    note) if colprof is unavailable, rather than leaving a fake behind.
    """
    import subprocess
    try:
        colprof = _argyll("colprof")
    except SystemExit:
        return False
    try:
        # No -a: an OUTPUT profile can only use the cLUT algorithm, and
        # colprof refuses -aG outright ("Output profile can only be a cLUT
        # algorithm"). -qm keeps it quick enough for a demo.
        subprocess.run([colprof, "-v0", "-qm", f"-D{stem} (demo)", stem],
                       cwd=run_dir, check=True, capture_output=True, timeout=300)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"    (colprof failed for {stem}: {exc}) — no profile written")
        return False
    # ArgyllCMS writes the Windows ICC extension (.icm) on Windows and .icc on
    # macOS/Linux. ChromIQ's demo layout — and Run.profile_icc — is spelled .icc
    # everywhere, so canonicalise the output. Without this a demo built on
    # Windows has <stem>.icm and looks profile-less to any test that checks
    # Run.profile_icc (#130, Windows gate). The app itself tolerates either name
    # via ProfileBuilder.expected_icc_path(); the demo just picks the canonical one.
    icc = run_dir / f"{stem}.icc"
    icm = run_dir / f"{stem}.icm"
    if not icc.is_file() and icm.is_file():
        icm.replace(icc)
    return icc.is_file()


def _write_tiff(path: Path, page: int) -> None:
    """A REAL, small TIFF — used only for the scanner diagnostic stand-in.

    The page images themselves come from the chart engine. This one still has
    to be a valid image: Knut found the first attempt's stubs unopenable, and a
    file that cannot be opened is worse than one that is not there.
    """
    from PIL import Image
    img = Image.new("RGB", (240, 160), (250, 250, 248))
    for x in range(0, 240, 30):
        for y in range(0, 160, 40):
            band = ((x // 30) * 37 + page * 20) % 256
            img.paste((band, (band + 80) % 256, (band + 160) % 256),
                      (x, y, x + 28, y + 38))
    img.save(path, format="TIFF")


def _report(stem: str, when: datetime, de: float) -> str:
    return json.dumps({
        "schema": 5, "created": when.isoformat(timespec="seconds"),
        "chart": stem, "ti3": f"{stem}.ti3", "instrument": "X-Rite ColorMunki",
        "reference_source": "design", "is_verification": True,
        "de00": {"mean": round(de, 3), "max": round(de * 3.1, 3),
                 "p95": round(de * 2.2, 3)},
        "paper_white": {"L": 95.4, "a": 0.8, "b": -2.1},
        "max_black": {"L": 6.2, "a": 0.3, "b": -0.4},
        "patches": 240,
        "worst_patches": [{"id": 118, "de00": round(de * 3.1, 3)}],
    }, indent=2)


# ---------------------------------------------------------------------------
def _argyll(tool: str) -> str:
    for base in ("/Applications/Argyll/bin", "/usr/local/bin", "/opt/homebrew/bin"):
        p = Path(base) / tool
        if p.exists():
            return str(p)
    found = shutil.which(tool)
    if found:
        return found
    # Fall back to ChromIQ's own cross-platform detection. On Windows Argyll
    # lives under %LOCALAPPDATA%\ArgyllCMS\Argyll_V*\bin — neither a macOS path
    # above nor on PATH — so without this the demo fixtures could not build and
    # every test that needs them errored (#130, Windows gate). find_argyll_bin_path()
    # is the same resolver the app uses; argyll_binary() adds the .exe on Windows.
    from core.argyll_detect import find_argyll_bin_path
    from core.resource_path import argyll_binary
    bin_dir = find_argyll_bin_path()
    if bin_dir is not None:
        exe = bin_dir / argyll_binary(tool)
        if exe.exists():
            return str(exe)
    raise SystemExit(f"ArgyllCMS {tool} not found — install it, or set PATH.")


def _chart_files(into: Path, stem: str, *, patches: int, rows: int,
                 pages: int = 1, instrument: str = "CM") -> None:
    """Build a **real** chart: real ``targen`` patches, laid out by ChromIQ's own
    engine, with real page TIFFs and a real layout recipe.

    Knut, #130 2026-07-28: *"The demo projects contain tif files that are not
    viewable, and the projects do not contain json files for the charts, so
    their chart data is not loaded."* The first attempt wrote plausible-looking
    stubs — the folder shape was right and nothing in it worked. Demo data has
    to be **openable**, or it tests nothing.

    So the pipeline here is the same one the application uses: ``targen`` makes
    the patch set, :func:`workflow.layout_engine.chart.build_chart` lays it out,
    and the layout is folded into ``<stem>.channels.json`` exactly as
    ``ChartCreator._embed_layout_geometry`` does — which is what lets the chart
    reopen with its own settings instead of "carries no saved layout recipe".
    """
    import subprocess

    from workflow.layout_engine.chart import build_chart
    from workflow.layout_engine.presets import LayoutRecipe

    into.mkdir(parents=True, exist_ok=True)
    base = into / stem
    # A timeout, because -G is an optimising generator and can wedge: a run of
    # the suite under four parallel workers sat here for two and a half hours
    # with no output, since subprocess.run without one waits for ever. A cap
    # turns a silent hang into a named failure. colprof below has had one all
    # along; this call was simply missed.
    subprocess.run([_argyll("targen"), "-v0", "-d2", "-G", f"-f{patches}", stem],
                   cwd=into, check=True, capture_output=True, timeout=300)
    kwargs = dict(instrument=instrument, paper="A4", randomize=False)
    result = build_chart(base.with_suffix(".ti1"), base, **kwargs)

    # …and the sidecar the application writes, so the chart carries its recipe.
    sidecar = into / f"{stem}.channels.json"
    strips = into / f"{stem}.strips.json"
    doc = {"channels": ["r", "g", "b"]}
    layout = json.loads(strips.read_text()) if strips.exists() else {}
    layout["engine"] = "chromiq"
    layout["engine_version"] = 1
    layout["seed"] = getattr(result, "seed", 0)
    layout["color_rep"] = getattr(result, "color_rep", "RGB")
    layout["recipe"] = LayoutRecipe.from_build_kwargs(kwargs).to_dict()
    doc["layout"] = layout
    sidecar.write_text(json.dumps(doc))
    strips.unlink(missing_ok=True)      # geometry now lives in channels.json


def _write_manifest(root: Path, name: str, runs: list, current: str,
                    schema: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.json").write_text(json.dumps({
        "schema_version": schema,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "target_name": name, "current_run": current, "runs": runs,
    }, indent=2))


def _meta(run_dir: Path, rid: str, **extra) -> None:
    d = {"run_id": rid,
         "created_at": datetime.now().isoformat(timespec="seconds"),
         "parent_run": None, "instrument": "CM", "paper": "A4",
         "status": "complete"}
    d.update(extra)
    (run_dir / "meta.json").write_text(json.dumps(d, indent=2))


def _verification(run_dir: Path, stem: str, when: datetime, de: float) -> None:
    vdir = run_dir / "verifications" / when.strftime("%Y-%m-%d_%H%M%S")
    (vdir / "chart").mkdir(parents=True, exist_ok=True)
    (vdir / "reports").mkdir(parents=True, exist_ok=True)
    verify_ti2 = run_dir / "verifications" / f"{stem}-verify.ti2"
    (vdir / f"{stem}-verify.ti3").write_text(_ti3_from_ti2(verify_ti2, drift=de))
    # The chart snapshot is taken by the REAL application code, not by a second
    # copy of the rule here. Knut, #130 2026-07-29: this used to copy the .ti2
    # alone, so every dated folder was missing the .channels.json a real
    # snapshot carries — and Restore Used Chart then reported a chart it could
    # not redraw, a state ChromIQ itself never produces. Test data has to be
    # made the way the program makes it, or it tests the wrong program.
    from core.file_manager import Run
    from workflow.verify_chart_snapshot import snapshot_chart
    snapshot_chart(Run.for_dir(run_dir).verification(
        when.strftime("%Y-%m-%d_%H%M%S")))
    (vdir / "reports" / f"report_{when:%Y-%m-%d_%H-%M-%S}.json").write_text(
        _report(f"{stem}-verify", when, de))


# ---------------------------------------------------------------------------
# The four projects
# ---------------------------------------------------------------------------
def build_full(root: Path) -> None:
    """Three runs: finished, verified, and chart-only."""
    name = "Demo-Full-RGB"
    p = root / name
    stem = name
    _write_manifest(p, name, ["run1", "run2", "run3"], "run3", 3)
    (p / "cal").mkdir(parents=True, exist_ok=True)
    _chart_files(p / "cal", f"{stem}-cal", patches=60, rows=10)
    (p / "cal" / f"{stem}-cal.ti3").write_text(_ti3_from_ti2(p / "cal" / f"{stem}-cal.ti2"))
    (p / "exports").mkdir(exist_ok=True)
    (p / "exports" / f"{stem}-colours.txt").write_text("# demo export\n")

    # run1 — a finished profile with everything around it
    r1 = p / "runs" / "run1"
    _chart_files(r1, stem, patches=240, rows=15, pages=2)
    (r1 / f"{stem}.ti3").write_text(_ti3_from_ti2(r1 / f"{stem}.ti2"))
    _build_icc(r1, stem)
    (r1 / "chart").mkdir(exist_ok=True)
    _chart_files(r1 / "chart", stem, patches=240, rows=15, pages=2)
    for sub, fname, body in (
            ("reports", f"Quality_Check_1_{stem}.txt", "worst dE 2.4\n"),
            ("reports", f"report_2026-05-02_10-15-00.json",
             _report(stem, datetime(2026, 5, 2, 10, 15), 1.4)),
            ("exports", f"{stem}-i1profiler.txt", "# hand-off\n"),
            ("cache", f"{stem}-diag.tif", None)):
        (r1 / sub).mkdir(exist_ok=True)
        if body is None:
            _write_tiff(r1 / sub / fname, 9)
        else:
            (r1 / sub / fname).write_text(body)
    (r1 / "reads").mkdir(exist_ok=True)
    for n in (1, 2):
        (r1 / "reads" / f"read{n}.ti3").write_text(_ti3_from_ti2(r1 / f"{stem}.ti2", drift=n * 0.2))
    _meta(r1, "run1", averaging_enabled=True, averaging_read_count=2)

    # run2 — refined from run1, and verified twice
    r2 = p / "runs" / "run2"
    _chart_files(r2, stem, patches=240, rows=15, pages=2)
    (r2 / f"{stem}.ti3").write_text(_ti3_from_ti2(r2 / f"{stem}.ti2", drift=0.4))
    _build_icc(r2, stem)
    (r2 / "preconditioning.ti3").write_text(_ti3_from_ti2(r1 / f"{stem}.ti2"))
    shutil.copy2(r1 / f"{stem}.icc", r2 / "preconditioning.icc") if (r1 / f"{stem}.icc").exists() else None
    _chart_files(r2 / "verifications", f"{stem}-verify", patches=60, rows=10)
    for when, de in ((datetime(2026, 5, 20, 9, 5), 0.9),
                     (datetime(2026, 6, 24, 16, 40), 1.5)):
        _verification(r2, stem, when, de)
    _meta(r2, "run2", parent_run="run1", preconditioning_source_run="run1")

    # run3 — a chart waiting to be measured
    r3 = p / "runs" / "run3"
    _chart_files(r3, stem, patches=390, rows=15, pages=3)
    _meta(r3, "run3", status="in_progress")


def build_verify_history(root: Path) -> None:
    """One finished run with five verifications, for the report's trend."""
    name = "Demo-Verify-History"
    p = root / name
    stem = name
    _write_manifest(p, name, ["run1"], "run1", 3)
    r1 = p / "runs" / "run1"
    _chart_files(r1, stem, patches=240, rows=15, pages=2)
    (r1 / f"{stem}.ti3").write_text(_ti3_from_ti2(r1 / f"{stem}.ti2"))
    _build_icc(r1, stem)
    _chart_files(r1 / "verifications", f"{stem}-verify", patches=60, rows=10)
    start = datetime(2026, 1, 12, 11, 0)
    for i, de in enumerate((0.8, 1.0, 1.3, 1.9, 2.6)):   # a drifting printer
        _verification(r1, stem, start + timedelta(days=90 * i), de)
    _meta(r1, "run1")


def build_legacy_v1(root: Path) -> None:
    """The 3.13 layout: runs existed, the sub-folders did not.

    Straight from ``Project._migrate_v1_to_v2`` — quality checks and refine
    lists sat in the run folder, and the scanner intermediates with them.
    """
    name = "Demo-Legacy-v1"
    p = root / name
    stem = name
    _write_manifest(p, name, ["run1", "run2"], "run2", 1)
    for rid in ("run1", "run2"):
        rd = p / "runs" / rid
        _chart_files(rd, stem, patches=240, rows=15, pages=2)
        (rd / f"{stem}.ti3").write_text(_ti3_from_ti2(rd / f"{stem}.ti2"))
        _build_icc(rd, stem)
        # …flat, exactly where v1 left them
        (rd / f"Quality_Check_1_{stem}.txt").write_text("worst dE 3.1\n")
        (rd / f"Quality_Check_2_{stem}.txt").write_text("worst dE 2.2\n")
        (rd / f"Refine_Strips_{stem}.txt").write_text("A\nD\nF\n")
        (rd / f"{stem}-patchbox.cht").write_text("BOXES 240\n")
        (rd / f"{stem}-aligned.cht").write_text("BOXES 240\n")
        _write_tiff(rd / f"{stem}-diag.tif", 3)
        _meta(rd, rid)
    cal = p / "cal"
    _chart_files(cal, f"{stem}-cal", patches=60, rows=10)
    (cal / f"{stem}-cal-patchbox.cht").write_text("BOXES 60\n")


def build_legacy_v2(root: Path) -> None:
    """The intermediate layout: sub-folders in place, but a verification still
    written as one flat ``<stem>-verify.ti3`` at the run root (what
    ``_migrate_v2_to_v3`` folds into a dated folder)."""
    name = "Demo-Legacy-v2"
    p = root / name
    stem = name
    _write_manifest(p, name, ["run1"], "run1", 2)
    rd = p / "runs" / "run1"
    _chart_files(rd, stem, patches=240, rows=15, pages=2)
    (rd / f"{stem}.ti3").write_text(_ti3_from_ti2(rd / f"{stem}.ti2"))
    _build_icc(rd, stem)
    (rd / "reports").mkdir(exist_ok=True)
    (rd / "reports" / f"Quality_Check_1_{stem}.txt").write_text("worst dE 2.8\n")
    # The legacy one-slot verification, flat at the run root — a real chart, so
    # the migrated result is something you can actually open afterwards.
    _chart_files(rd, f"{stem}-verify", patches=60, rows=10)
    (rd / f"{stem}-verify.ti3").write_text(
        _ti3_from_ti2(rd / f"{stem}-verify.ti2"))
    _meta(rd, "run1")


BUILDERS = {
    "Demo-Full-RGB": build_full,
    "Demo-Verify-History": build_verify_history,
    "Demo-Legacy-v1": build_legacy_v1,
    "Demo-Legacy-v2": build_legacy_v2,
}

#: The two ready-made downloads (Knut, #130 2026-07-28): one for checking the
#: upgrade from 3.13, one for exercising the current version.
LEGACY_PROJECTS = ("Demo-Legacy-v1", "Demo-Legacy-v2")
CURRENT_PROJECTS = ("Demo-Full-RGB", "Demo-Verify-History")


def build_all(dest: Path) -> "list[Path]":
    dest.mkdir(parents=True, exist_ok=True)
    made = []
    for name, fn in BUILDERS.items():
        target = dest / name
        if target.exists():
            shutil.rmtree(target)
        fn(dest)
        made.append(target)
    return made


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dest", nargs="?", default="demo-projects",
                    help="where to write them (default: ./demo-projects)")
    ap.add_argument("--zip", action="store_true",
                    help="also write the two ready-made archives beside them")
    args = ap.parse_args(argv)

    dest = Path(args.dest).expanduser().resolve()
    made = build_all(dest)
    for m in made:
        files = sum(1 for _ in m.rglob("*") if _.is_file())
        print(f"  {m.name:24} {files:4d} files   {m}")
    if args.zip:
        # Two downloads, not one (Knut, #130 2026-07-28): "one for 3.13 and one
        # for testing latest version". Someone checking the upgrade wants the
        # old layouts and nothing else; someone exercising verifications and
        # reporting wants the current ones and nothing else.
        for suffix, names in (("3.13", LEGACY_PROJECTS),
                              ("latest", CURRENT_PROJECTS)):
            staged = dest.parent / f"_stage-{suffix}"
            if staged.exists():
                shutil.rmtree(staged)
            staged.mkdir(parents=True)
            for name in names:
                shutil.copytree(dest / name, staged / name)
            archive = shutil.make_archive(
                str(dest.parent / f"chromiq-demo-projects-{suffix}"),
                "zip", root_dir=staged)
            shutil.rmtree(staged)
            size = Path(archive).stat().st_size / 1024
            print(f"  archive: {Path(archive).name:38} ({size:>5.0f} KB)  "
                  f"{', '.join(names)}")
    print(f"\n{len(made)} demo projects written to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
