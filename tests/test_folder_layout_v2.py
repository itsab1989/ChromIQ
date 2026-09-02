"""v1 → v2 folder-layout migration (#127).

Replays the committed schema-1 fixture (``tests/golden/project_v1`` — generated
by ``make_v1_fixture.py`` against the pre-#127 code) through ``Project.load``
and asserts the full migration matrix: every ChromIQ file family lands in its
v2 home, user files and the Argyll chain never move, the migration is
idempotent and interruption-safe, and a schema newer than this build opens
without being touched.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from core.file_manager import (CACHE_DIRNAME, EXPORTS_DIRNAME, REPORTS_DIRNAME,
                               SCHEMA_VERSION, Project)

FIXTURE = Path(__file__).parent / "golden" / "project_v1" / "Golden-Printer"
NAME = "Golden-Printer"


def _copy_fixture(tmp_path: Path) -> Path:
    root = tmp_path / NAME
    shutil.copytree(FIXTURE, root)
    return root


def manifest_of(root: Path) -> list[str]:
    """Sorted relative POSIX paths of every file under ``root``."""
    return sorted(p.relative_to(root).as_posix()
                  for p in root.rglob("*") if p.is_file())


def test_fixture_is_schema_1() -> None:
    m = json.loads((FIXTURE / "project.json").read_text(encoding="utf-8"))
    assert m["schema_version"] == 1


def test_migration_bumps_schema_and_persists(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    proj = Project.load(root)
    assert not proj.schema_too_new
    on_disk = json.loads((root / "project.json").read_text(encoding="utf-8"))
    assert on_disk["schema_version"] == SCHEMA_VERSION == 3


def test_migration_full_v2_manifest(tmp_path: Path) -> None:
    """The golden assertion: the COMPLETE post-migration tree, file by file."""
    root = _copy_fixture(tmp_path)
    Project.load(root)
    got = manifest_of(root)
    expected = sorted([
        "Where are my files.txt",
        "project.json",
        # cal/ — chain flat, sidecars in exports/
        f"cal/{NAME}-cal.cal", f"cal/{NAME}-cal.cht", f"cal/{NAME}-cal.icc",
        f"cal/{NAME}-cal.ps", f"cal/{NAME}-cal.ti1", f"cal/{NAME}-cal.ti2",
        f"cal/{NAME}-cal.ti3", f"cal/{NAME}-cal_01.tif", "cal/meta.json",
        f"cal/exports/{NAME}-cal-colours.txt",
        f"cal/exports/{NAME}-cal-i1profiler.pxf",
        f"cal/exports/{NAME}-cal-i1profiler.txt",
        # project-level exports untouched
        f"exports/{NAME}-i1profiler.txt",
        # run1 — Argyll chain + valuables flat
        f"runs/run1/{NAME}.channels.json", f"runs/run1/{NAME}.cht",
        f"runs/run1/{NAME}.cie", f"runs/run1/{NAME}.icc",
        f"runs/run1/{NAME}.pdf", f"runs/run1/{NAME}.ps",
        f"runs/run1/{NAME}.strips.json", f"runs/run1/{NAME}.ti1",
        f"runs/run1/{NAME}.ti2", f"runs/run1/{NAME}.ti3",
        f"runs/run1/{NAME}_01.tif", f"runs/run1/{NAME}_02.tif",
        "runs/run1/calibrated.icc", "runs/run1/merged.icc",
        "runs/run1/merged.ti3", "runs/run1/meta.json",
        "runs/run1/preconditioning.icc", "runs/run1/preconditioning.ti3",
        # user files stay put
        "runs/run1/my own notes.txt", f"runs/run1/{NAME}-notes.txt",
        # reads/ + reports/ (report json was already there; checks moved in)
        "runs/run1/reads/read1.ti3", "runs/run1/reads/read2.ti3",
        "runs/run1/reports/report_2026-07-18_10-00-00.json",
        f"runs/run1/reports/Quality_Check_1_{NAME}.txt",
        f"runs/run1/reports/Quality_Check_2_{NAME}.txt",
        f"runs/run1/reports/Refine_Strips_{NAME}.txt",
        # exports/
        f"runs/run1/exports/{NAME}-colours.txt",
        f"runs/run1/exports/{NAME}-i1profiler.pxf",
        f"runs/run1/exports/{NAME}-i1profiler.txt",
        # cache/ — current and legacy scanner debris
        f"runs/run1/cache/{NAME}-patchbox.cht",
        f"runs/run1/cache/{NAME}-patchbox-sample.cht",
        f"runs/run1/cache/{NAME}_01-sample.cht",
        f"runs/run1/cache/{NAME}-aligned.cht",
        f"runs/run1/cache/{NAME}-aligned-patchbox.cht",
        "runs/run1/cache/scan-of-page1-diag.tif",
        # run2 — sparse
        f"runs/run2/{NAME}.ti1", f"runs/run2/{NAME}.ti2",
        f"runs/run2/reports/Quality_Check_1_{NAME}.txt",
        "runs/run2/meta.json",
    ])
    assert got == expected


def test_migration_preserves_file_contents(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    before = (root / "runs/run1" / f"Quality_Check_1_{NAME}.txt").read_text(
        encoding="utf-8")
    Project.load(root)
    after = (root / "runs/run1" / REPORTS_DIRNAME /
             f"Quality_Check_1_{NAME}.txt").read_text(encoding="utf-8")
    assert before == after
    # a valuable never moves and never changes
    assert (root / "runs/run1" / f"{NAME}.ti3").read_text(
        encoding="utf-8") == "CTI3 stand-in measurement\n"


def test_migration_idempotent(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    Project.load(root)
    first = manifest_of(root)
    Project.load(root)      # second load: schema already 2 → no-op
    assert manifest_of(root) == first


def test_migration_resumes_after_interruption(tmp_path: Path) -> None:
    """A half-done migration (some files already moved, schema still 1) is
    healed by simply loading again."""
    root = _copy_fixture(tmp_path)
    rd = root / "runs" / "run1"
    (rd / REPORTS_DIRNAME).mkdir(exist_ok=True)
    shutil.move(str(rd / f"Quality_Check_1_{NAME}.txt"),
                str(rd / REPORTS_DIRNAME / f"Quality_Check_1_{NAME}.txt"))
    Project.load(root)
    assert (rd / REPORTS_DIRNAME / f"Quality_Check_2_{NAME}.txt").exists()
    assert (rd / EXPORTS_DIRNAME / f"{NAME}-colours.txt").exists()


def test_migration_skips_on_conflict(tmp_path: Path) -> None:
    """A same-named file already in the destination is never overwritten —
    the source stays where it is."""
    root = _copy_fixture(tmp_path)
    rd = root / "runs" / "run1"
    (rd / REPORTS_DIRNAME).mkdir(exist_ok=True)
    blocker = rd / REPORTS_DIRNAME / f"Refine_Strips_{NAME}.txt"
    blocker.write_text("existing — do not clobber\n", encoding="utf-8")
    Project.load(root)
    assert blocker.read_text(encoding="utf-8") == "existing — do not clobber\n"
    assert (rd / f"Refine_Strips_{NAME}.txt").exists()   # source left in place


def test_migration_never_touches_user_files(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    Project.load(root)
    rd = root / "runs" / "run1"
    assert (rd / "my own notes.txt").exists()
    assert (rd / f"{NAME}-notes.txt").exists()


def test_migration_protects_chart_chain_of_tricky_project_name(tmp_path: Path) -> None:
    """A project whose NAME ends in a cache-pattern tail must keep its chart
    chain — 'X-sample.cht' is the chart, not scanner debris."""
    name = "X-sample"
    root = tmp_path / name
    run = root / "runs" / "run1"
    run.mkdir(parents=True)
    (root / "project.json").write_text(json.dumps({
        "schema_version": 1, "target_name": name,
        "current_run": "run1", "runs": ["run1"]}), encoding="utf-8")
    for ext in (".cht", ".tif", ".ti2"):
        (run / f"{name}{ext}").write_text("chain\n", encoding="utf-8")
    (run / f"{name}_01.tif").write_text("page\n", encoding="utf-8")
    Project.load(root)
    for fname in (f"{name}.cht", f"{name}.tif", f"{name}.ti2",
                  f"{name}_01.tif"):
        assert (run / fname).exists(), f"{fname} was wrongly moved"
    assert not (run / CACHE_DIRNAME).exists()


def test_schema_too_new_opens_untouched(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    m = json.loads((root / "project.json").read_text(encoding="utf-8"))
    m["schema_version"] = 99
    (root / "project.json").write_text(json.dumps(m), encoding="utf-8")
    before = manifest_of(root)
    proj = Project.load(root)
    assert proj.schema_too_new
    after = json.loads((root / "project.json").read_text(encoding="utf-8"))
    assert after["schema_version"] == 99          # never downgraded
    assert manifest_of(root) == before            # nothing moved or written


def test_migration_regenerates_folder_guide(tmp_path: Path) -> None:
    """The one deliberate README overwrite: after migration the guide
    describes the v2 layout (and the real project name, not {name})."""
    root = _copy_fixture(tmp_path)
    (root / Project.README).write_text("user-edited v1 guide", encoding="utf-8")
    Project.load(root)
    text = (root / Project.README).read_text(encoding="utf-8")
    assert "cache" in text and "reports" in text
    assert "{name}" not in text
    assert NAME in text


def test_fresh_projects_are_schema_2(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "Fresh", "Fresh")
    on_disk = json.loads((tmp_path / "Fresh" / "project.json").read_text(
        encoding="utf-8"))
    assert on_disk["schema_version"] == SCHEMA_VERSION
    assert not proj.schema_too_new


def test_declutter_folder_sorts_chromiq_files_only(tmp_path: Path) -> None:
    """declutter_folder (#36) moves only the files ChromIQ writes into
    reports/exports/cache; user files and the chart chain stay put; a name
    clash is left in place; nothing is renamed or deleted."""
    from core.file_manager import declutter_folder
    d = tmp_path / "legacy"
    d.mkdir()
    files = {
        "Quality_Check_1_Foo.txt": REPORTS_DIRNAME,
        "Refine_Strips_Foo.txt": REPORTS_DIRNAME,
        "report_2026-01-01.json": REPORTS_DIRNAME,
        "Foo-colours.txt": EXPORTS_DIRNAME,
        "Foo-i1profiler.pxf": EXPORTS_DIRNAME,
        "Foo-patchbox.cht": CACHE_DIRNAME,
        "scan-diag.tif": CACHE_DIRNAME,
    }
    stay = ("Foo.ti2", "Foo.icc", "Foo.cht", "Foo.cie", "my-notes.txt")
    for name in list(files) + list(stay):
        (d / name).write_text("x", encoding="utf-8")

    moved = declutter_folder(d)
    assert moved == len(files)
    for name, sub in files.items():
        assert (d / sub / name).is_file()
        assert not (d / name).exists()
    for name in stay:                              # user files + chart chain untouched
        assert (d / name).is_file()

    # Idempotent: a second run moves nothing.
    assert declutter_folder(d) == 0

    # A folder with nothing to tidy gets no empty sub-folders.
    empty = tmp_path / "plain"; empty.mkdir()
    (empty / "photo.jpg").write_text("x", encoding="utf-8")
    assert declutter_folder(empty) == 0
    assert not (empty / REPORTS_DIRNAME).exists()


def test_declutter_name_clash_leaves_file(tmp_path: Path) -> None:
    from core.file_manager import declutter_folder
    d = tmp_path / "legacy2"; (d / REPORTS_DIRNAME).mkdir(parents=True)
    (d / "Refine_Strips_Foo.txt").write_text("new", encoding="utf-8")
    (d / REPORTS_DIRNAME / "Refine_Strips_Foo.txt").write_text("existing", encoding="utf-8")
    assert declutter_folder(d) == 0                 # clash → skipped
    assert (d / "Refine_Strips_Foo.txt").read_text(encoding="utf-8") == "new"
