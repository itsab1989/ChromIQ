"""The pre-``runs/`` mover must pick up run files and nothing else.

Combined round 5 over beta 20. `migrate_flat_project` is the only code in this
release that MOVES a user's own measurements, and two of its rules were a shade
too loose. Both are proved here against the disk, before and after.

1. THE PROJECT'S OWN MANIFEST IS NOT A CHART. The chain is matched on the
   FOLDER's name, so a project a person names ``project`` makes ``project.json``
   match it exactly and the mover carried the manifest into ``runs/run1``.
   `save_manifest` wrote it back at the root a moment later, so nothing was
   lost - what was left was a stray copy of the manifest inside the run folder
   and a warning on every load from then on, saying the run already held a
   chart of its own.

2. ``:`` IS A PATH SEPARATOR ON WINDOWS. The mover's traversal guard listed
   ``/``, ``\\`` and NUL and missed the drive letter, so ``current_run: "D:"``
   was accepted; ``Path(root) / "runs" / "D:"`` is ``D:``, another drive
   entirely, and ``"C:"`` collapses to the ``runs`` folder rather than a run
   inside it. `current_run` is unsanitised on the load path and a project
   travels as a zip, which is the threat the guard was written for.

The promise being defended in both is the one in `migrate_flat_project`'s own
docstring: it moves nothing, or it finishes.
"""
from pathlib import Path

import pytest

from core.file_manager import (Project, flat_legacy_chain, is_a_plain_folder_name,
                               migrate_flat_project)


def _listing(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.is_dir() or p.stat().st_size)
            for p in sorted(root.rglob("*"))}


def _flat_project(root: Path, stem: str = None) -> Path:
    """A pre-redesign project: chart, measurement and profile loose."""
    root.mkdir(parents=True, exist_ok=True)
    stem = stem or root.name
    for ext in (".ti1", ".ti2", ".ti3", ".icc"):
        (root / f"{stem}{ext}").write_text(f"content of {stem}{ext}", encoding="utf-8")
    for i in (1, 2, 3):
        (root / f"{stem}_{i:02d}.tif").write_text(f"page {i}", encoding="utf-8")
    return root


# --------------------------------------------------------------- the manifest

def test_a_project_named_project_keeps_its_manifest_at_the_root(tmp_path):
    """`project.json` matches `project(_NN)?.<ext>`, and must still not move."""
    root = tmp_path / "project"
    Project.create(root, "project")

    assert [f.name for f in flat_legacy_chain(root)] == [], (
        "the project's own manifest was read as a run's chart file")

    before = _listing(root)
    Project.load(root)
    Project.load(root)                      # and the load after that one

    assert not (root / "runs" / "run1" / Project.MANIFEST).exists(), (
        "a copy of the manifest was left inside the run folder")
    assert (root / Project.MANIFEST).is_file(), "the manifest left the root"
    assert _listing(root) == before, (
        "opening a project named 'project' moved something")


def test_a_project_named_project_does_not_warn_on_every_open(tmp_path, caplog):
    """The stray copy made the run look like it held a chart, for ever after."""
    root = tmp_path / "project"
    Project.create(root, "project")
    Project.load(root)
    caplog.clear()
    with caplog.at_level("WARNING", logger="core.file_manager"):
        Project.load(root)
    assert not [r for r in caplog.records if "flat migration" in r.getMessage()], (
        "opening the project warns about a chart the user never made")


def test_the_readme_is_not_a_run_file_either(tmp_path):
    """The other name at the project root that the chain can spell."""
    root = tmp_path / "Where are my files"
    root.mkdir()
    (root / Project.README).write_text("the folder guide", encoding="utf-8")
    (root / f"{root.name}.ti3").write_text("a real measurement", encoding="utf-8")

    chain = [f.name for f in flat_legacy_chain(root)]
    assert chain == [f"{root.name}.ti3"], f"the folder guide was picked up: {chain}"

    assert migrate_flat_project(root, "run1") == 1
    assert (root / Project.README).is_file(), "the folder guide was moved into a run"


def test_a_real_chart_chain_is_still_moved_whole(tmp_path):
    """The exclusion must not cost the mover anything it is for."""
    root = _flat_project(tmp_path / "Printer-A4-Matte")
    assert migrate_flat_project(root, "run1") == 7
    assert sorted(p.name for p in (root / "runs" / "run1").iterdir()) == sorted(
        f"{root.name}{e}" for e in
        (".icc", ".ti1", ".ti2", ".ti3", "_01.tif", "_02.tif", "_03.tif"))
    assert flat_legacy_chain(root) == []


# ------------------------------------------------------------- the run id

@pytest.mark.parametrize("run_id", [
    "C:", "D:", "c:", "Z:x", "run1:stream",      # the drive letter and its kin
    "../..", "..", ".", "...", "", None,         # the shapes already refused
    "/tmp/escape", "a/b", "..\\..", "run1\0x",
    " run1", "run1 ", " ",                       # not already a clean name
])
def test_a_run_id_that_is_not_a_plain_folder_name_moves_nothing(tmp_path, run_id):
    root = _flat_project(tmp_path / "Printer-A4-Matte")
    before = _listing(root)

    assert migrate_flat_project(root, run_id) == 0, f"{run_id!r} was accepted"
    assert _listing(root) == before, f"{run_id!r} changed the disk"


def test_a_drive_letter_cannot_name_a_child_folder():
    """Why ``:`` is refused: pathlib itself says the join leaves the project."""
    from pathlib import PureWindowsPath
    inside = PureWindowsPath(r"C:\Users\a\ChromIQ\Proj") / "runs"
    assert str(inside / "D:") == "D:", "the premise of this guard has changed"
    assert not is_a_plain_folder_name("D:")
    assert is_a_plain_folder_name("run1")


def test_the_reader_and_the_mover_share_one_rule(tmp_path):
    """`peek_project` dropped ids by its own copy of the check. One rule now."""
    import inspect

    from core import file_manager as fm
    src = inspect.getsource(fm.peek_project)
    assert "is_a_plain_folder_name" in src, (
        "peek_project no longer shares the mover's rule")
    assert '"/" not in v' not in src, (
        "peek_project has grown its own copy of the rule again")


def test_a_manifest_naming_a_drive_leaves_the_project_where_it_is(tmp_path):
    """End to end: the shape a mailed, hand-edited project arrives in."""
    import json

    root = _flat_project(tmp_path / "Printer-A4-Matte")
    (root / Project.MANIFEST).write_text(json.dumps(
        {"schema_version": 3, "target_name": root.name,
         "current_run": "D:", "runs": ["D:"]}), encoding="utf-8")
    # Only the chain, because a load legitimately backfills the folder guide.
    before = {k: v for k, v in _listing(root).items() if root.name in k}

    Project.load(root)

    assert {k: v for k, v in _listing(root).items() if root.name in k} == before, (
        "a drive-letter run id moved the project's files")
    assert not (root / "runs").exists(), "a run folder was built for 'D:'"
    assert len(flat_legacy_chain(root)) == 7, (
        "the chart chain left the project folder")
