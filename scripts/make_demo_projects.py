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


def _icc(stem: str) -> bytes:
    """Not a valid profile — a recognisable stand-in of plausible size."""
    return (b"\x00\x00\x0c\x48acspAPPL" + stem.encode("ascii", "replace")
            .ljust(64, b"\0") + b"\0" * 1024)


def _tiff(page: int) -> bytes:
    return b"II*\x00\x08\x00\x00\x00" + bytes([page]) * 512


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
def _chart_files(into: Path, stem: str, *, patches: int, rows: int,
                 pages: int = 1) -> None:
    into.mkdir(parents=True, exist_ok=True)
    (into / f"{stem}.ti1").write_text(_ti2(stem, patches, rows))
    (into / f"{stem}.ti2").write_text(_ti2(stem, patches, rows))
    (into / f"{stem}.cht").write_text(f"BOXES {patches}\n")
    (into / f"{stem}.ps").write_text("%!PS-Adobe-3.0\n% demo\n")
    (into / f"{stem}.channels.json").write_text(
        json.dumps({"channels": ["r", "g", "b"]}, indent=2))
    (into / f"{stem}.strips.json").write_text(
        json.dumps({"rows": rows, "patches": patches}, indent=2))
    for p in range(1, pages + 1):
        (into / f"{stem}_{p:02d}.tif").write_bytes(_tiff(p))


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
    (vdir / f"{stem}-verify.ti3").write_text(_ti3(stem, 60, drift=de))
    (vdir / "chart" / f"{stem}-verify.ti2").write_text(_ti2(stem, 60, 10))
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
    (p / "cal" / f"{stem}-cal.ti3").write_text(_ti3(f"{stem}-cal", 60))
    (p / "exports").mkdir(exist_ok=True)
    (p / "exports" / f"{stem}-colours.txt").write_text("# demo export\n")

    # run1 — a finished profile with everything around it
    r1 = p / "runs" / "run1"
    _chart_files(r1, stem, patches=240, rows=15, pages=2)
    (r1 / f"{stem}.ti3").write_text(_ti3(stem, 240))
    (r1 / f"{stem}.icc").write_bytes(_icc(stem))
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
            (r1 / sub / fname).write_bytes(_tiff(9))
        else:
            (r1 / sub / fname).write_text(body)
    (r1 / "reads").mkdir(exist_ok=True)
    for n in (1, 2):
        (r1 / "reads" / f"read{n}.ti3").write_text(_ti3(stem, 240, drift=n * 0.2))
    _meta(r1, "run1", averaging_enabled=True, averaging_read_count=2)

    # run2 — refined from run1, and verified twice
    r2 = p / "runs" / "run2"
    _chart_files(r2, stem, patches=240, rows=15, pages=2)
    (r2 / f"{stem}.ti3").write_text(_ti3(stem, 240, drift=0.4))
    (r2 / f"{stem}.icc").write_bytes(_icc(stem))
    (r2 / "preconditioning.ti3").write_text(_ti3(stem, 240))
    (r2 / "preconditioning.icc").write_bytes(_icc(stem))
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
    (r1 / f"{stem}.ti3").write_text(_ti3(stem, 240))
    (r1 / f"{stem}.icc").write_bytes(_icc(stem))
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
        (rd / f"{stem}.ti3").write_text(_ti3(stem, 240))
        (rd / f"{stem}.icc").write_bytes(_icc(stem))
        # …flat, exactly where v1 left them
        (rd / f"Quality_Check_1_{stem}.txt").write_text("worst dE 3.1\n")
        (rd / f"Quality_Check_2_{stem}.txt").write_text("worst dE 2.2\n")
        (rd / f"Refine_Strips_{stem}.txt").write_text("A\nD\nF\n")
        (rd / f"{stem}-patchbox.cht").write_text("BOXES 240\n")
        (rd / f"{stem}-aligned.cht").write_text("BOXES 240\n")
        (rd / f"{stem}-diag.tif").write_bytes(_tiff(3))
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
    (rd / f"{stem}.ti3").write_text(_ti3(stem, 240))
    (rd / f"{stem}.icc").write_bytes(_icc(stem))
    (rd / "reports").mkdir(exist_ok=True)
    (rd / "reports" / f"Quality_Check_1_{stem}.txt").write_text("worst dE 2.8\n")
    # the legacy one-slot verification, flat at the run root
    (rd / f"{stem}-verify.ti3").write_text(_ti3(f"{stem}-verify", 60))
    (rd / f"{stem}-verify.ti2").write_text(_ti2(f"{stem}-verify", 60, 10))
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
